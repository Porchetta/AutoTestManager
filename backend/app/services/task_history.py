from __future__ import annotations

"""
Task history aggregation + retention.

집계 테이블 `TaskHistoryDaily`에 (date, user_id, test_type) 단위로
태스크 카운트를 누적한다. Dashboard / MyPage 차트는 이 집계 테이블만
조회하므로 원본 `TestTask` 행이 보존 정책에 의해 삭제되어도 차트는
영향받지 않는다.
"""

import logging
import shutil
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.entities import TaskHistoryDaily, TestTask

logger = logging.getLogger(__name__)
settings = get_settings()


def record_task_requested(db: Session, task: TestTask) -> None:
    """태스크 생성 시점에 일별 집계를 +1 한다."""
    requested_at = task.requested_at or datetime.now(timezone.utc)
    bump_aggregate(db, requested_at.date(), task.user_id, task.test_type, 1)


def bump_aggregate(
    db: Session,
    aggregate_date: date,
    user_id: str,
    test_type: str,
    delta: int,
) -> None:
    if delta == 0:
        return
    row = (
        db.query(TaskHistoryDaily)
        .filter(
            TaskHistoryDaily.date == aggregate_date,
            TaskHistoryDaily.user_id == user_id,
            TaskHistoryDaily.test_type == test_type,
        )
        .first()
    )
    if row is None:
        row = TaskHistoryDaily(
            date=aggregate_date,
            user_id=user_id,
            test_type=test_type,
            count=max(0, delta),
        )
        db.add(row)
        try:
            db.commit()
            return
        except IntegrityError:
            # 동시성 경합 시: 기존 row 재조회 후 누적
            db.rollback()
            row = (
                db.query(TaskHistoryDaily)
                .filter(
                    TaskHistoryDaily.date == aggregate_date,
                    TaskHistoryDaily.user_id == user_id,
                    TaskHistoryDaily.test_type == test_type,
                )
                .first()
            )
            if row is None:
                return
    row.count = max(0, (row.count or 0) + delta)
    db.add(row)
    db.commit()


def backfill_from_test_tasks(db: Session) -> int:
    """기존 TestTask로부터 집계가 비어있는 경우에만 1회 백필.

    이미 집계 row가 한 건이라도 있으면 백필을 스킵한다 (중복 누적 방지).
    """
    has_any = db.query(TaskHistoryDaily.id).first()
    if has_any is not None:
        return 0

    rows = (
        db.query(
            func.date(TestTask.requested_at).label("d"),
            TestTask.user_id,
            TestTask.test_type,
            func.count().label("cnt"),
        )
        .group_by("d", TestTask.user_id, TestTask.test_type)
        .all()
    )
    inserted = 0
    for row in rows:
        if not row.d:
            continue
        agg_date = row.d if isinstance(row.d, date) else date.fromisoformat(str(row.d))
        db.add(
            TaskHistoryDaily(
                date=agg_date,
                user_id=row.user_id,
                test_type=row.test_type,
                count=int(row.cnt or 0),
            )
        )
        inserted += 1
    if inserted:
        db.commit()
    return inserted


# ─── Retention ────────────────────────────────────────────────────────────────


def _delete_task_files(task: TestTask) -> None:
    if not settings.task_retention_delete_files:
        return
    for path_str in (task.raw_result_path, task.summary_result_path):
        if not path_str:
            continue
        path = Path(path_str)
        try:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)
            # raw 파일은 task_id 디렉토리 하위에 있으므로 디렉토리 정리
            parent = path.parent
            if parent.exists() and parent.name == task.task_id and not any(parent.iterdir()):
                parent.rmdir()
        except OSError as exc:
            logger.warning("retention: failed to remove %s: %s", path, exc)


def sweep_retention(db: Session) -> dict[str, int]:
    """보존 정책에 따라 오래된/초과분 TestTask를 삭제한다.

    - 나이 초과: requested_at < now - retention_days
    - 사용자별 최대 개수 초과: 오래된 순으로 삭제
    """
    deleted_by_age = 0
    deleted_by_count = 0

    retention_days = max(1, int(settings.task_retention_days or 0))
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    aged_tasks = (
        db.query(TestTask)
        .filter(TestTask.requested_at < cutoff)
        .all()
    )
    for task in aged_tasks:
        _delete_task_files(task)
        db.delete(task)
        deleted_by_age += 1
    if deleted_by_age:
        db.commit()

    max_per_user = int(settings.task_retention_max_per_user or 0)
    if max_per_user > 0:
        user_ids = [row[0] for row in db.query(TestTask.user_id).distinct().all()]
        for user_id in user_ids:
            total = (
                db.query(func.count(TestTask.id))
                .filter(TestTask.user_id == user_id)
                .scalar()
                or 0
            )
            overflow = int(total) - max_per_user
            if overflow <= 0:
                continue
            stale = (
                db.query(TestTask)
                .filter(TestTask.user_id == user_id)
                .order_by(TestTask.requested_at.asc(), TestTask.id.asc())
                .limit(overflow)
                .all()
            )
            for task in stale:
                _delete_task_files(task)
                db.delete(task)
                deleted_by_count += 1
        if deleted_by_count:
            db.commit()

    return {"deleted_by_age": deleted_by_age, "deleted_by_count": deleted_by_count}


_sweeper_started = False
_sweeper_lock = threading.Lock()


def start_retention_sweeper() -> None:
    """애플리케이션 lifespan에서 1회 호출. 데몬 스레드로 주기 실행."""
    global _sweeper_started
    with _sweeper_lock:
        if _sweeper_started:
            return
        _sweeper_started = True

    interval = max(60, int(settings.task_retention_sweep_interval_seconds or 0))

    def _run() -> None:
        while True:
            try:
                db = SessionLocal()
                try:
                    result = sweep_retention(db)
                    if result["deleted_by_age"] or result["deleted_by_count"]:
                        logger.info("task retention sweep: %s", result)
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("task retention sweep failed: %s", exc)
            time.sleep(interval)

    thread = threading.Thread(target=_run, daemon=True, name="task-retention-sweeper")
    thread.start()
