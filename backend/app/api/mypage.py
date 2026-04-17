from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import DashboardLike, RtdConfig, TestTask, User
from app.services.file_service import (
    generate_summary_file,
    get_ezdfs_raw_content_path,
    get_existing_download_path,
    get_rtd_raw_rule_file_map,
)
from app.services.task_service import ensure_task_owner, list_tasks_by_type, serialize_task
from app.utils.enums import ActionType, TaskStatus, TestType
from app.utils.constants import TARGET_SUFFIX
from app.utils.naming import normalize_target_line_name

router = APIRouter(prefix="/api/mypage", tags=["mypage"])

_RESULT_TEST_ACTIONS = [ActionType.TEST.value, ActionType.RETEST.value]
_PAGE_SIZE = 8


def _task_rule_name(task: TestTask) -> str:
    try:
        p = json.loads(task.requested_payload_json or "{}")
        n = p.get("payload") if isinstance(p.get("payload"), dict) else p
        return str(n.get("selected_rule") or p.get("rule_name") or "").strip()
    except (json.JSONDecodeError, ValueError):
        return ""


def _task_rule_names(task: TestTask) -> list[str]:
    try:
        p = json.loads(task.requested_payload_json or "{}")
        n = p.get("payload") if isinstance(p.get("payload"), dict) else p
        selected_rule_targets = (
            n.get("selected_rule_targets")
            if isinstance(n.get("selected_rule_targets"), list)
            else []
        )
        rule_names = [
            str(item.get("rule_name", "")).strip()
            for item in selected_rule_targets
            if str(item.get("rule_name", "")).strip()
        ]
        if rule_names:
            return rule_names
        fallback_rule = str(n.get("selected_rule") or p.get("rule_name") or "").strip()
        return [fallback_rule] if fallback_rule else []
    except (json.JSONDecodeError, ValueError):
        return []


def _task_module_name(task: TestTask) -> str:
    try:
        p = json.loads(task.requested_payload_json or "{}")
        n = p.get("payload") if isinstance(p.get("payload"), dict) else p
        return str(n.get("selected_module") or p.get("module_name") or "").strip()
    except (json.JSONDecodeError, ValueError):
        return ""


def _rtd_action_display_name(action_type: str) -> str:
    normalized = str(action_type or "").strip().upper()
    if normalized == ActionType.COPY.value:
        return "Copy"
    if normalized == ActionType.COMPILE.value:
        return "Compile"
    if normalized in {ActionType.TEST.value, ActionType.RETEST.value}:
        return "Testing"
    return normalized.title() if normalized else ""


def _queue_status_priority(status: str) -> int:
    normalized = str(status or "").strip().upper()
    if normalized == TaskStatus.RUNNING.value:
        return 0
    if normalized == TaskStatus.PENDING.value:
        return 1
    return 9


def _paginate(items: list, page: int) -> tuple[list, int, int]:
    total = len(items)
    start = (page - 1) * _PAGE_SIZE
    pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    return items[start : start + _PAGE_SIZE], total, pages


# ─── existing endpoints ───────────────────────────────────────────────────────

@router.get("/rtd/recent")
def recent_rtd(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = list_tasks_by_type(db, current_user.user_id, TestType.RTD, limit=20)
    return success_response({"items": [serialize_task(task) for task in tasks]})


@router.get("/ezdfs/recent")
def recent_ezdfs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = list_tasks_by_type(db, current_user.user_id, TestType.EZDFS, limit=20)
    return success_response({"items": [serialize_task(task) for task in tasks]})


@router.get("/stats")
def usage_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()

    daily_dates = [today - timedelta(days=i) for i in range(13, -1, -1)]
    daily_labels = [d.strftime("%m/%d") for d in daily_dates]
    daily_start = daily_dates[0].isoformat()
    daily_end = (today + timedelta(days=1)).isoformat()

    daily_rows = (
        db.query(
            func.strftime("%Y-%m-%d", TestTask.requested_at).label("day"),
            TestTask.test_type,
            func.count().label("cnt"),
        )
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.requested_at >= daily_start,
            TestTask.requested_at < daily_end,
        )
        .group_by("day", TestTask.test_type)
        .all()
    )

    rtd_daily_map = {d.isoformat(): 0 for d in daily_dates}
    ezdfs_daily_map = {d.isoformat(): 0 for d in daily_dates}
    for row in daily_rows:
        if row.test_type == TestType.RTD.value:
            rtd_daily_map[row.day] = row.cnt
        elif row.test_type == TestType.EZDFS.value:
            ezdfs_daily_map[row.day] = row.cnt

    monthly_keys: list[tuple[int, int]] = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        monthly_keys.append((y, m))

    monthly_labels = [f"{m}월" for _, m in monthly_keys]
    m_start = f"{monthly_keys[0][0]}-{monthly_keys[0][1]:02d}-01"
    last_y, last_m = monthly_keys[-1]
    m_end_y, m_end_m = (last_y + 1, 1) if last_m == 12 else (last_y, last_m + 1)
    monthly_end = f"{m_end_y}-{m_end_m:02d}-01"

    monthly_rows = (
        db.query(
            func.strftime("%Y-%m", TestTask.requested_at).label("ym"),
            TestTask.test_type,
            func.count().label("cnt"),
        )
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.requested_at >= m_start,
            TestTask.requested_at < monthly_end,
        )
        .group_by("ym", TestTask.test_type)
        .all()
    )

    rtd_monthly_map = {f"{y}-{m:02d}": 0 for y, m in monthly_keys}
    ezdfs_monthly_map = {f"{y}-{m:02d}": 0 for y, m in monthly_keys}
    for row in monthly_rows:
        if row.test_type == TestType.RTD.value:
            rtd_monthly_map[row.ym] = row.cnt
        elif row.test_type == TestType.EZDFS.value:
            ezdfs_monthly_map[row.ym] = row.cnt

    return success_response({
        "rtd_daily":     {"labels": daily_labels,   "counts": list(rtd_daily_map.values())},
        "rtd_monthly":   {"labels": monthly_labels, "counts": list(rtd_monthly_map.values())},
        "ezdfs_daily":   {"labels": daily_labels,   "counts": list(ezdfs_daily_map.values())},
        "ezdfs_monthly": {"labels": monthly_labels, "counts": list(ezdfs_monthly_map.values())},
    })


# ─── Global stats (Dashboard용, 전체 유저) ────────────────────────────────────

@router.get("/stats/global")
def global_stats(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()

    daily_dates = [today - timedelta(days=i) for i in range(13, -1, -1)]
    daily_labels = [d.strftime("%m/%d") for d in daily_dates]
    daily_start = daily_dates[0].isoformat()
    daily_end = (today + timedelta(days=1)).isoformat()

    daily_rows = (
        db.query(
            func.strftime("%Y-%m-%d", TestTask.requested_at).label("day"),
            TestTask.test_type,
            func.count().label("cnt"),
        )
        .filter(
            TestTask.requested_at >= daily_start,
            TestTask.requested_at < daily_end,
        )
        .group_by("day", TestTask.test_type)
        .all()
    )

    rtd_daily_map = {d.isoformat(): 0 for d in daily_dates}
    ezdfs_daily_map = {d.isoformat(): 0 for d in daily_dates}
    for row in daily_rows:
        if row.test_type == TestType.RTD.value:
            rtd_daily_map[row.day] = row.cnt
        elif row.test_type == TestType.EZDFS.value:
            ezdfs_daily_map[row.day] = row.cnt

    monthly_keys: list[tuple[int, int]] = []
    for i in range(11, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        monthly_keys.append((y, m))

    monthly_labels = [f"{m}월" for _, m in monthly_keys]
    m_start = f"{monthly_keys[0][0]}-{monthly_keys[0][1]:02d}-01"
    last_y, last_m = monthly_keys[-1]
    m_end_y, m_end_m = (last_y + 1, 1) if last_m == 12 else (last_y, last_m + 1)
    monthly_end = f"{m_end_y}-{m_end_m:02d}-01"

    monthly_rows = (
        db.query(
            func.strftime("%Y-%m", TestTask.requested_at).label("ym"),
            TestTask.test_type,
            func.count().label("cnt"),
        )
        .filter(
            TestTask.requested_at >= m_start,
            TestTask.requested_at < monthly_end,
        )
        .group_by("ym", TestTask.test_type)
        .all()
    )

    rtd_monthly_map = {f"{y}-{m:02d}": 0 for y, m in monthly_keys}
    ezdfs_monthly_map = {f"{y}-{m:02d}": 0 for y, m in monthly_keys}
    for row in monthly_rows:
        if row.test_type == TestType.RTD.value:
            rtd_monthly_map[row.ym] = row.cnt
        elif row.test_type == TestType.EZDFS.value:
            ezdfs_monthly_map[row.ym] = row.cnt

    like_count = db.query(func.count(DashboardLike.id)).scalar() or 0

    return success_response({
        "rtd_daily":     {"labels": daily_labels,   "counts": list(rtd_daily_map.values())},
        "rtd_monthly":   {"labels": monthly_labels, "counts": list(rtd_monthly_map.values())},
        "ezdfs_daily":   {"labels": daily_labels,   "counts": list(ezdfs_daily_map.values())},
        "ezdfs_monthly": {"labels": monthly_labels, "counts": list(ezdfs_monthly_map.values())},
        "dashboard_like_count": int(like_count),
    })


@router.get("/dashboard/like")
def get_dashboard_like(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    liked = (
        db.query(DashboardLike)
        .filter(DashboardLike.user_id == current_user.user_id)
        .first()
        is not None
    )
    like_count = db.query(func.count(DashboardLike.id)).scalar() or 0
    return success_response({"liked": liked, "count": int(like_count)})


@router.post("/dashboard/like/toggle")
def toggle_dashboard_like(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(DashboardLike)
        .filter(DashboardLike.user_id == current_user.user_id)
        .first()
    )
    if existing is None:
        db.add(DashboardLike(user_id=current_user.user_id))
        liked = True
    else:
        db.delete(existing)
        liked = False

    db.commit()
    like_count = db.query(func.count(DashboardLike.id)).scalar() or 0
    return success_response({"liked": liked, "count": int(like_count)})


# ─── Today counts (Dashboard용) ──────────────────────────────────────────────

@router.get("/stats/today")
def today_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = datetime.now(timezone.utc).date()
    day_start = today.isoformat()
    day_end = (today + timedelta(days=1)).isoformat()

    rows = (
        db.query(TestTask.test_type, func.count().label("cnt"))
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.requested_at >= day_start,
            TestTask.requested_at < day_end,
        )
        .group_by(TestTask.test_type)
        .all()
    )

    counts = {row.test_type: row.cnt for row in rows}
    return success_response({
        "rtd": counts.get(TestType.RTD.value, 0),
        "ezdfs": counts.get(TestType.EZDFS.value, 0),
    })


@router.get("/dashboard/queue")
def dashboard_queue(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(TestTask)
        .filter(TestTask.status.in_([TaskStatus.RUNNING.value, TaskStatus.PENDING.value]))
        .order_by(
            TestTask.status.asc(),
            TestTask.requested_at.asc(),
            TestTask.id.asc(),
        )
        .limit(12)
        .all()
    )

    owner_user_ids = sorted({task.user_id for task in tasks})
    user_name_map = {
        user.user_id: user.user_name
        for user in db.query(User).filter(User.user_id.in_(owner_user_ids)).all()
    }

    rtd_line_names = sorted(
        {
            normalize_target_line_name(task.target_name)
            for task in tasks
            if task.test_type == TestType.RTD.value
        }
    )
    rtd_business_unit_map = {
        config.line_name: config.business_unit
        for config in db.query(RtdConfig).filter(RtdConfig.line_name.in_(rtd_line_names)).all()
    }

    grouped_items: dict[tuple[str, ...], dict] = {}
    for task in tasks:
        serialized = serialize_task(task)
        module_name = str(serialized.get("module_name") or task.target_name or "").strip()
        rule_name = str(serialized.get("rule_name") or "").strip()
        user_name = user_name_map.get(task.user_id, task.user_id)

        if task.test_type == TestType.RTD.value:
            line_name = normalize_target_line_name(task.target_name)
            business_unit = rtd_business_unit_map.get(line_name, line_name)
            action_label = _rtd_action_display_name(task.action_type)
            group_key = ("RTD", business_unit, action_label, task.user_id)
            queue_title = business_unit
            queue_meta = f"{action_label} · {user_name}"
        else:
            group_key = ("EZDFS", module_name, task.user_id)
            queue_title = module_name
            queue_meta = user_name

        candidate = {
            "task_id": task.task_id,
            "test_type": task.test_type,
            "action_type": task.action_type,
            "status": task.status,
            "target_name": task.target_name,
            "user_id": task.user_id,
            "user_name": user_name,
            "module_name": module_name,
            "rule_name": rule_name,
            "business_unit": business_unit if task.test_type == TestType.RTD.value else "",
            "requested_at": task.requested_at.isoformat() if task.requested_at else None,
            "message": task.message,
            "queue_title": queue_title,
            "queue_meta": queue_meta,
        }

        current = grouped_items.get(group_key)
        if current is None:
            grouped_items[group_key] = candidate
            continue

        current_requested_at = current.get("requested_at") or ""
        candidate_requested_at = candidate.get("requested_at") or ""
        current_priority = _queue_status_priority(str(current.get("status", "")))
        candidate_priority = _queue_status_priority(task.status)
        if (
            candidate_priority < current_priority
            or (
                candidate_priority == current_priority
                and candidate_requested_at < current_requested_at
            )
        ):
            grouped_items[group_key] = candidate

    items = sorted(
        grouped_items.values(),
        key=lambda item: (
            item["test_type"],
            _queue_status_priority(str(item["status"])),
            str(item["queue_title"]).lower(),
            str(item["queue_meta"]).lower(),
        ),
    )
    return success_response({"items": items})


# ─── RTD Raw Data ─────────────────────────────────────────────────────────────

@router.get("/rtd/results/raw/options")
def rtd_raw_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.test_type == TestType.RTD.value,
            TestTask.action_type.in_(_RESULT_TEST_ACTIONS),
            TestTask.raw_result_path.isnot(None),
        )
        .all()
    )
    lines = sorted({normalize_target_line_name(t.target_name) for t in tasks if t.target_name})
    rules = sorted({rule_name for t in tasks for rule_name in (_task_rule_names(t) or get_rtd_raw_rule_file_map(t).keys()) if rule_name})
    return success_response({"lines": lines, "rules": rules})


@router.get("/rtd/results/raw")
def rtd_raw_list(
    line: str | None = Query(default=None),
    rule: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.test_type == TestType.RTD.value,
            TestTask.action_type.in_(_RESULT_TEST_ACTIONS),
            TestTask.raw_result_path.isnot(None),
        )
        .order_by(TestTask.requested_at.desc())
    )
    if line:
        q = q.filter(
            or_(TestTask.target_name == line, TestTask.target_name == line + TARGET_SUFFIX)
        )
    items_all: list[dict[str, str | None]] = []
    for t in q.all():
        rule_file_map = get_rtd_raw_rule_file_map(t)
        rule_names = sorted(rule_file_map.keys()) or _task_rule_names(t)
        for rule_name in rule_names:
            if rule and rule_name != rule:
                continue
            items_all.append(
                {
                    "task_id": t.task_id,
                    "line": normalize_target_line_name(t.target_name),
                    "rule": rule_name,
                    "requested_at": t.requested_at.isoformat() if t.requested_at else None,
                }
            )

    paged, total, pages = _paginate(items_all, page)
    items = paged
    return success_response({"items": items, "total": total, "page": page, "pages": pages})


# ─── RTD Report ───────────────────────────────────────────────────────────────

@router.get("/rtd/results/summary")
def rtd_summary_list(
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.test_type == TestType.RTD.value,
            TestTask.action_type.in_(_RESULT_TEST_ACTIONS),
            TestTask.status == TaskStatus.DONE.value,
        )
        .order_by(TestTask.requested_at.desc())
        .all()
    )

    line_names = {normalize_target_line_name(t.target_name) for t in tasks}
    bu_map = {
        c.line_name: c.business_unit
        for c in db.query(RtdConfig).filter(RtdConfig.line_name.in_(line_names)).all()
    }

    paged, total, pages = _paginate(tasks, page)
    items = [
        {
            "task_id": t.task_id,
            "business_unit": bu_map.get(normalize_target_line_name(t.target_name), normalize_target_line_name(t.target_name)),
            "requested_at": t.requested_at.isoformat() if t.requested_at else None,
        }
        for t in paged
    ]
    return success_response({"items": items, "total": total, "page": page, "pages": pages})


# ─── ezDFS Raw Data ───────────────────────────────────────────────────────────

@router.get("/ezdfs/results/raw")
def ezdfs_raw_list(
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.test_type == TestType.EZDFS.value,
            TestTask.action_type.in_(_RESULT_TEST_ACTIONS),
            TestTask.raw_result_path.isnot(None),
        )
        .order_by(TestTask.requested_at.desc())
        .all()
    )
    paged, total, pages = _paginate(tasks, page)
    items = [
        {
            "task_id": t.task_id,
            "rule": _task_rule_name(t),
            "requested_at": t.requested_at.isoformat() if t.requested_at else None,
        }
        for t in paged
    ]
    return success_response({"items": items, "total": total, "page": page, "pages": pages})


# ─── ezDFS Report ─────────────────────────────────────────────────────────────

@router.get("/ezdfs/results/summary")
def ezdfs_summary_list(
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == current_user.user_id,
            TestTask.test_type == TestType.EZDFS.value,
            TestTask.action_type.in_(_RESULT_TEST_ACTIONS),
            TestTask.status == TaskStatus.DONE.value,
        )
        .order_by(TestTask.requested_at.desc())
        .all()
    )
    paged, total, pages = _paginate(tasks, page)
    items = [
        {
            "task_id": t.task_id,
            "module": _task_module_name(t) or t.target_name,
            "requested_at": t.requested_at.isoformat() if t.requested_at else None,
        }
        for t in paged
    ]
    return success_response({"items": items, "total": total, "page": page, "pages": pages})


# ─── Download ─────────────────────────────────────────────────────────────────

@router.get("/results/{task_id}/download")
def download_result(
    task_id: str,
    kind: str | None = Query(default=None),
    rule: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id)
    if kind not in ("raw", "summary"):
        kind = "summary" if task.summary_result_path else "raw"
    if kind == "summary" and task.test_type in {TestType.RTD.value, TestType.EZDFS.value}:
        generate_summary_file(db, task)
        db.refresh(task)
    elif kind == "summary" and not task.summary_result_path:
        generate_summary_file(db, task)
        db.refresh(task)

    if kind == "raw":
        if task.test_type == TestType.RTD.value:
            normalized_rule = str(rule or "").strip()
            if not normalized_rule:
                normalized_rule = _task_rule_name(task)
            rule_file_map = get_rtd_raw_rule_file_map(task)
            if normalized_rule and normalized_rule in rule_file_map:
                path = rule_file_map[normalized_rule]
            else:
                raise HTTPException(status_code=404, detail="RTD raw data file not found for the selected rule")
        elif task.test_type == TestType.EZDFS.value:
            path = get_ezdfs_raw_content_path(task)
            if path is None:
                raise HTTPException(status_code=404, detail="ezDFS raw data file not found")
        else:
            path = get_existing_download_path(task, kind=kind)
    else:
        path = get_existing_download_path(task, kind=kind)

    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if kind == "summary"
        else "text/plain"
    )
    return FileResponse(path=path, filename=path.name, media_type=media_type)
