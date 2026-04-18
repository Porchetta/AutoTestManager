from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import RtdConfig, TestTask
from app.services.ezdfs_report_custom import build_ezdfs_test_report_file
from app.services.file_service import _build_ezdfs_raw_file_name
from app.services.rtd_report_custom import build_rtd_test_report_file
from app.services.session_service import get_runtime_session_payload
from app.utils.constants import TARGET_SUFFIX
from app.utils.enums import TaskStatus, TestType
from app.utils.naming import normalize_target_line_name, sanitize_path_token

settings = get_settings()


def get_existing_download_path(task: TestTask, kind: str) -> Path:
    if kind == "raw":
        if not task.raw_result_path:
            raise HTTPException(status_code=404, detail="Raw result file not found")
        path = Path(task.raw_result_path)
    else:
        if not task.summary_result_path:
            raise HTTPException(status_code=404, detail="Summary result file not found")
        path = Path(task.summary_result_path)

    if not path.exists():
        raise HTTPException(status_code=404, detail="Result file does not exist")

    return path


def get_rtd_raw_rule_file_map(task: TestTask) -> dict[str, Path]:
    """
    Return saved per-rule raw txt files for one RTD test task.

    RTD raw data is stored as:
    - `<raw_root>/<task_id>/_meta.txt`
    - `<raw_root>/<task_id>/index.json`
    - `<raw_root>/<task_id>/<line>-<rule>.txt`

    If `index.json` is missing, the task is treated as not having valid RTD
    rule raw files.
    """
    if not task.raw_result_path:
        return {}

    meta_path = Path(task.raw_result_path)
    raw_task_dir = meta_path.parent
    index_path = raw_task_dir / "index.json"
    if not index_path.exists():
        return {}

    try:
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError):
        return {}

    rule_files = index_payload.get("rule_files", {})
    result: dict[str, Path] = {}
    for rule_name, file_name in rule_files.items():
        normalized_rule_name = str(rule_name or "").strip()
        normalized_file_name = str(file_name or "").strip()
        if not normalized_rule_name or not normalized_file_name:
            continue
        file_path = raw_task_dir / normalized_file_name
        if file_path.exists():
            result[normalized_rule_name] = file_path
    return result


def get_ezdfs_raw_content_path(task: TestTask) -> Path | None:
    """Return the saved ezDFS rule-named raw content txt path for one ezDFS test task."""
    if not task.raw_result_path:
        return None

    meta_path = Path(task.raw_result_path)
    raw_task_dir = meta_path.parent
    raw_path = raw_task_dir / _build_ezdfs_raw_file_name(task)
    if raw_path.exists():
        return raw_path
    return None


def generate_aggregate_rtd_summary_file(
    db: Session,
    user_id: str,
    target_lines: list[str],
) -> Path:
    if not target_lines:
        raise HTTPException(status_code=422, detail="target_lines is required")

    target_set = list(dict.fromkeys(normalize_target_line_name(line) for line in target_lines if line))
    legacy_target_set = [f"{line}{TARGET_SUFFIX}" for line in target_set]
    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == user_id,
            TestTask.test_type == "RTD",
            or_(
                TestTask.target_name.in_(target_set),
                TestTask.target_name.in_(legacy_target_set),
            ),
            TestTask.action_type.in_(["TEST", "RETEST"]),
            TestTask.status == TaskStatus.DONE.value,
        )
        .order_by(TestTask.requested_at.desc(), TestTask.id.desc())
        .all()
    )

    if not tasks:
        raise HTTPException(status_code=404, detail="No RTD test results found for selected target lines")

    runtime_payload = get_runtime_session_payload(db, user_id, TestType.RTD)
    fallback_major_change_items = (
        runtime_payload.get("major_change_items")
        if isinstance(runtime_payload.get("major_change_items"), dict)
        else {}
    )
    selected_rule_targets = (
        runtime_payload.get("selected_rule_targets")
        if isinstance(runtime_payload.get("selected_rule_targets"), list)
        else []
    )
    selected_rule_names = list(
        dict.fromkeys(
            str(item.get("rule_name") or "").strip()
            for item in selected_rule_targets
            if str(item.get("rule_name") or "").strip()
        )
    )

    latest_tasks = _pick_latest_rtd_tasks_per_rule(tasks, target_set, selected_rule_names)

    report_dir = Path(settings.result_base_path) / "rtd" / "reports" / sanitize_path_token(user_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    business_unit_token = _build_business_unit_token(db, target_set)
    output_path = report_dir / f"{business_unit_token}-{timestamp}.xlsx"
    return build_rtd_test_report_file(
        latest_tasks,
        output_path,
        fallback_major_change_items,
        selected_rule_names,
    )


def generate_aggregate_ezdfs_summary_file(
    db: Session,
    user_id: str,
    module_name: str,
    task_ids: list[str],
) -> Path:
    if not module_name:
        raise HTTPException(status_code=422, detail="module_name is required")
    if not task_ids:
        raise HTTPException(status_code=422, detail="task_ids is required")

    ordered_task_ids = list(dict.fromkeys(task_ids))
    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == user_id,
            TestTask.test_type == "EZDFS",
            TestTask.task_id.in_(ordered_task_ids),
            TestTask.action_type.in_(["TEST", "RETEST"]),
        )
        .all()
    )
    done_tasks = [task for task in tasks if task.status == TaskStatus.DONE.value]
    done_tasks.sort(key=lambda task: (task.requested_at, task.id), reverse=True)
    if not done_tasks:
        raise HTTPException(status_code=404, detail="No completed ezDFS test results found for selected rules")

    runtime_payload = get_runtime_session_payload(db, user_id, TestType.EZDFS)
    selected_rules = (
        runtime_payload.get("selected_rules")
        if isinstance(runtime_payload.get("selected_rules"), list)
        else []
    )
    selected_rule_names = list(
        dict.fromkeys(
            str(item.get("rule_name") or "").strip()
            for item in selected_rules
            if isinstance(item, dict) and str(item.get("rule_name") or "").strip()
        )
    )
    if not selected_rule_names:
        selected_rule = str(runtime_payload.get("selected_rule") or "").strip()
        if selected_rule:
            selected_rule_names = [selected_rule]

    report_dir = Path(settings.result_base_path) / "ezdfs" / "reports" / sanitize_path_token(user_id)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = report_dir / f"{sanitize_path_token(module_name)}-{timestamp}.xlsx"
    fallback_major_change_items = (
        runtime_payload.get("major_change_items")
        if isinstance(runtime_payload.get("major_change_items"), dict)
        else {}
    )
    return build_ezdfs_test_report_file(
        done_tasks,
        output_path,
        selected_rule_names,
        fallback_major_change_items,
    )


def _pick_latest_rtd_tasks_per_rule(
    tasks: list[TestTask],
    target_lines: list[str],
    selected_rule_names: list[str],
) -> list[TestTask]:
    """
    Filter tasks to the newest one covering each (line, rule_name) pair.

    Why: `build_rtd_test_report_file` already dedups by (line, rule_name) with
    first-seen-wins logic on a newest-first stream, but it still iterates every
    historical task. This helper pre-filters so only the tasks that actually
    contribute a row make it through.
    """
    line_set = {line for line in target_lines if line}
    rule_filter = {name for name in selected_rule_names if name}

    seen_keys: set[tuple[str, str]] = set()
    picked: list[TestTask] = []
    for task in tasks:
        line_name = normalize_target_line_name(task.target_name)
        if line_set and line_name not in line_set:
            continue
        try:
            requested_payload = json.loads(task.requested_payload_json or "{}")
        except (json.JSONDecodeError, ValueError):
            requested_payload = {}
        payload = (
            requested_payload.get("payload")
            if isinstance(requested_payload.get("payload"), dict)
            else requested_payload
        )
        rule_names = _collect_rtd_task_rule_names(requested_payload, payload)
        contributes = False
        for rule_name in rule_names:
            if rule_filter and rule_name not in rule_filter:
                continue
            key = (line_name, rule_name)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            contributes = True
        if contributes:
            picked.append(task)
    return picked


def _collect_rtd_task_rule_names(requested_payload: dict, payload: dict) -> list[str]:
    """Extract rule names from a RTD task payload in the same order the report builder sees them."""
    targets = (
        payload.get("selected_rule_targets")
        if isinstance(payload.get("selected_rule_targets"), list)
        else []
    )
    names: list[str] = []
    for item in targets:
        if not isinstance(item, dict):
            continue
        rule_name = str(item.get("rule_name", "")).strip()
        if rule_name:
            names.append(rule_name)
    if names:
        return names
    fallback = str(requested_payload.get("rule_name", "")).strip()
    return [fallback] if fallback else []


def _build_business_unit_token(db: Session, target_lines: list[str]) -> str:
    business_units: list[str] = []
    for line in target_lines:
        normalized_line = normalize_target_line_name(line)
        config = db.query(RtdConfig).filter(RtdConfig.line_name == normalized_line).first()
        if config and config.business_unit:
            business_units.append(config.business_unit)

    normalized_units = list(dict.fromkeys(sanitize_path_token(unit) for unit in business_units if unit))
    if not normalized_units:
        return "business_unit"
    if len(normalized_units) == 1:
        return normalized_units[0]
    return f"{normalized_units[0]}__and_{len(normalized_units) - 1}_more"
