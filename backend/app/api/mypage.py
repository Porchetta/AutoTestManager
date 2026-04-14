from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import RtdConfig, TestTask, User
from app.services.file_service import (
    generate_summary_file,
    get_ezdfs_raw_content_path,
    get_existing_download_path,
    get_rtd_raw_rule_file_map,
)
from app.services.task_service import ensure_task_owner, list_tasks_by_type, serialize_task
from app.utils.enums import ActionType, TaskStatus, TestType

router = APIRouter(prefix="/api/mypage", tags=["mypage"])

_RESULT_TEST_ACTIONS = [ActionType.TEST.value, ActionType.RETEST.value]
_PAGE_SIZE = 5


# ─── helpers ────────────────────────────────────────────────────────────────

def _normalize_line(target_name: str) -> str:
    s = str(target_name or "").strip()
    return s[: -len("_TARGET")] if s.endswith("_TARGET") else s


def _task_rule_name(task: TestTask) -> str:
    try:
        p = json.loads(task.requested_payload_json or "{}")
        n = p.get("payload") if isinstance(p.get("payload"), dict) else p
        return str(n.get("selected_rule") or p.get("rule_name") or "").strip()
    except Exception:  # noqa: BLE001
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
    except Exception:  # noqa: BLE001
        return []


def _task_module_name(task: TestTask) -> str:
    try:
        p = json.loads(task.requested_payload_json or "{}")
        n = p.get("payload") if isinstance(p.get("payload"), dict) else p
        return str(n.get("selected_module") or p.get("module_name") or "").strip()
    except Exception:  # noqa: BLE001
        return ""


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

    return success_response({
        "rtd_daily":     {"labels": daily_labels,   "counts": list(rtd_daily_map.values())},
        "rtd_monthly":   {"labels": monthly_labels, "counts": list(rtd_monthly_map.values())},
        "ezdfs_daily":   {"labels": daily_labels,   "counts": list(ezdfs_daily_map.values())},
        "ezdfs_monthly": {"labels": monthly_labels, "counts": list(ezdfs_monthly_map.values())},
    })


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
    lines = sorted({_normalize_line(t.target_name) for t in tasks if t.target_name})
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
            or_(TestTask.target_name == line, TestTask.target_name == line + "_TARGET")
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
                    "line": _normalize_line(t.target_name),
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

    line_names = {_normalize_line(t.target_name) for t in tasks}
    bu_map = {
        c.line_name: c.business_unit
        for c in db.query(RtdConfig).filter(RtdConfig.line_name.in_(line_names)).all()
    }

    paged, total, pages = _paginate(tasks, page)
    items = [
        {
            "task_id": t.task_id,
            "business_unit": bu_map.get(_normalize_line(t.target_name), _normalize_line(t.target_name)),
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
    if kind == "summary" and not task.summary_result_path:
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
