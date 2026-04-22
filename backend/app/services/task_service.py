from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import TestTask, User
from app.utils.enums import ActionType, TaskStatus, TaskStep, TestType


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_test_task(
    db: Session,
    test_type: TestType,
    action_type: ActionType,
    owner_user_id: str,
    target_name: str,
    requested_payload: dict,
    current_step: TaskStep,
) -> TestTask:
    duplicate_candidates = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == owner_user_id,
            TestTask.test_type == test_type.value,
            TestTask.action_type == action_type.value,
            TestTask.target_name == target_name,
            TestTask.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]),
        )
        .all()
    )
    duplicate = next(
        (
            candidate
            for candidate in duplicate_candidates
            if _is_same_task_scope(test_type, action_type, requested_payload, candidate.requested_payload_json)
        ),
        None,
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A task is already running for the same target")

    task = TestTask(
        task_id=uuid.uuid4().hex,
        test_type=test_type.value,
        action_type=action_type.value,
        user_id=owner_user_id,
        target_name=target_name,
        status=TaskStatus.PENDING.value,
        current_step=current_step.value,
        message="Task queued",
        requested_payload_json=json.dumps(requested_payload),
        requested_at=_now(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def fail_inflight_tasks_on_startup(db: Session) -> int:
    inflight_tasks = (
        db.query(TestTask)
        .filter(TestTask.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]))
        .all()
    )
    if not inflight_tasks:
        return 0

    ended_at = _now()
    for task in inflight_tasks:
        was_pending = task.status == TaskStatus.PENDING.value
        task.status = TaskStatus.FAIL.value
        task.ended_at = ended_at
        if was_pending:
            task.started_at = task.started_at or ended_at
        task.message = "Marked as FAIL on server startup: backend restarted before completion"
        db.add(task)
    db.commit()
    return len(inflight_tasks)


def list_tasks_by_type(db: Session, user_id: str, test_type: TestType, limit: int = 50) -> list[TestTask]:
    return (
        db.query(TestTask)
        .filter(TestTask.user_id == user_id, TestTask.test_type == test_type.value)
        .order_by(TestTask.requested_at.desc())
        .limit(limit)
        .all()
    )


def ensure_task_owner(
    db: Session,
    task_id: str,
    user_id: str,
    test_type: TestType | None = None,
) -> TestTask:
    query = db.query(TestTask).filter(TestTask.task_id == task_id, TestTask.user_id == user_id)
    if test_type is not None:
        query = query.filter(TestTask.test_type == test_type.value)

    task = query.first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def list_rtd_target_monitor_items(
    db: Session,
    target_names: list[str],
    current_user_id: str,
    rule_selection_map: dict[str, str] | None = None,
) -> list[dict]:
    normalized_targets = list(dict.fromkeys(target_names))
    if not normalized_targets:
        return []

    tasks = (
        db.query(TestTask)
        .filter(
            TestTask.test_type == TestType.RTD.value,
            TestTask.target_name.in_(normalized_targets),
        )
        .order_by(TestTask.requested_at.desc(), TestTask.id.desc())
        .all()
    )

    owner_user_ids = sorted({task.user_id for task in tasks})
    user_name_map = {
        user.user_id: user.user_name
        for user in db.query(User).filter(User.user_id.in_(owner_user_ids)).all()
    }

    items: list[dict] = []
    for target_name in normalized_targets:
        target_tasks = [task for task in tasks if task.target_name == target_name]
        selected_rule = (rule_selection_map or {}).get(target_name, "__ALL__")
        items.append(
            _build_rtd_target_monitor_item(
                target_name,
                target_tasks,
                current_user_id,
                user_name_map,
                selected_rule,
            )
        )
    return items


def serialize_task(task: TestTask) -> dict:
    requested_payload = json.loads(task.requested_payload_json or "{}")
    payload = requested_payload.get("payload") if isinstance(requested_payload.get("payload"), dict) else requested_payload
    return {
        "task_id": task.task_id,
        "test_type": task.test_type,
        "action_type": task.action_type,
        "target_name": task.target_name,
        "module_name": payload.get("selected_module") or requested_payload.get("module_name"),
        "rule_name": payload.get("selected_rule") or requested_payload.get("rule_name"),
        "rule_file_name": payload.get("selected_rule_file_name"),
        "status": task.status,
        "current_step": task.current_step,
        "message": task.message,
        "requested_at": task.requested_at,
        "started_at": task.started_at,
        "ended_at": task.ended_at,
        "raw_result_ready": bool(task.raw_result_path),
        "summary_result_ready": bool(task.summary_result_path),
    }


def _is_same_task_scope(
    test_type: TestType,
    action_type: ActionType,
    requested_payload: dict,
    existing_requested_payload_json: str,
) -> bool:
    if test_type != TestType.RTD or action_type not in {ActionType.TEST, ActionType.RETEST}:
        return True

    try:
        existing_requested_payload = json.loads(existing_requested_payload_json or "{}")
    except (json.JSONDecodeError, ValueError):
        return False

    return _extract_rtd_primary_rule_name(requested_payload) == _extract_rtd_primary_rule_name(existing_requested_payload)


def _extract_rtd_primary_rule_name(requested_payload: dict) -> str:
    nested_payload = (
        requested_payload.get("payload")
        if isinstance(requested_payload.get("payload"), dict)
        else requested_payload
    )
    selected_rule = str(
        nested_payload.get("selected_rule")
        or requested_payload.get("rule_name")
        or ""
    ).strip()
    if selected_rule:
        return selected_rule

    selected_rule_targets = (
        nested_payload.get("selected_rule_targets")
        if isinstance(nested_payload.get("selected_rule_targets"), list)
        else []
    )
    for item in selected_rule_targets:
        rule_name = str(item.get("rule_name", "")).strip()
        if rule_name:
            return rule_name
    return ""


def _build_rtd_target_monitor_item(
    target_name: str,
    target_tasks: list[TestTask],
    current_user_id: str,
    user_name_map: dict[str, str],
    selected_rule: str = "__ALL__",
) -> dict:
    filtered_tasks = _filter_rtd_tasks_by_selected_rule(target_tasks, selected_rule)

    active_task = next((task for task in filtered_tasks if task.status == TaskStatus.RUNNING.value), None)
    if active_task is None:
        active_task = next((task for task in filtered_tasks if task.status == TaskStatus.PENDING.value), None)

    latest_copy_task = _select_latest_task_for_actions(
        filtered_tasks,
        [ActionType.COPY.value],
        include_finished=True,
    )
    latest_sync_task = _select_latest_task_for_actions(
        filtered_tasks,
        [ActionType.SYNC.value],
        include_finished=True,
    )
    latest_compile_task = _select_latest_task_for_actions(filtered_tasks, [ActionType.COMPILE.value])
    latest_test_task = _select_latest_task_for_actions(
        filtered_tasks,
        [ActionType.TEST.value, ActionType.RETEST.value],
    )

    latest_user_test_task = next(
        (
            task
            for task in filtered_tasks
            if task.user_id == current_user_id
            and task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}
        ),
        None,
    )
    raw_download_task = (
        latest_user_test_task
        if latest_user_test_task is not None and bool(latest_user_test_task.raw_result_path)
        else None
    )

    return {
        "target_name": target_name,
        "status": active_task.status if active_task else "IDLE",
        "status_text": _build_current_status_text(active_task, user_name_map),
        "copy": _serialize_monitor_action(latest_copy_task, "복사"),
        "sync": _serialize_monitor_action(latest_sync_task, "Sync"),
        "compile": _serialize_monitor_action(latest_compile_task, "컴파일"),
        "test": _serialize_monitor_action(latest_test_task, "테스트"),
        "selected_rule": selected_rule,
        "raw_download": {
            "enabled": bool(raw_download_task),
            "task_id": raw_download_task.task_id if raw_download_task else None,
            "label": "다운로드 가능" if raw_download_task else "없음",
        },
    }


def _filter_rtd_tasks_by_selected_rule(target_tasks: list[TestTask], selected_rule: str) -> list[TestTask]:
    normalized_selected_rule = str(selected_rule or "").strip()
    if not normalized_selected_rule or normalized_selected_rule == "__ALL__":
        return target_tasks

    filtered: list[TestTask] = []
    for task in target_tasks:
        rule_names = _extract_rtd_task_rule_names(task)
        if normalized_selected_rule in rule_names:
            filtered.append(task)
    return filtered


def _extract_rtd_task_rule_names(task: TestTask) -> set[str]:
    try:
        requested_payload = json.loads(task.requested_payload_json or "{}")
    except (json.JSONDecodeError, ValueError):
        return set()

    nested_payload = (
        requested_payload.get("payload")
        if isinstance(requested_payload.get("payload"), dict)
        else requested_payload
    )
    selected_rule_targets = nested_payload.get("selected_rule_targets", [])
    rule_names = {
        str(item.get("rule_name", "")).strip()
        for item in selected_rule_targets
        if str(item.get("rule_name", "")).strip()
    }
    fallback_rule_name = str(requested_payload.get("rule_name", "")).strip()
    if fallback_rule_name:
        rule_names.add(fallback_rule_name)
    return rule_names


def _build_current_status_text(task: TestTask | None, user_name_map: dict[str, str]) -> str:
    if task is None:
        return "대기 없음"

    action_label = "테스트" if task.action_type == ActionType.RETEST.value else {
        ActionType.COPY.value: "복사",
        ActionType.SYNC.value: "Sync",
        ActionType.COMPILE.value: "컴파일",
        ActionType.TEST.value: "테스트",
    }.get(task.action_type, task.action_type)
    suffix = "중" if task.status == TaskStatus.RUNNING.value else "대기중"
    owner_name = user_name_map.get(task.user_id, task.user_id)
    return f"{action_label} {suffix} ({owner_name})"


def _select_latest_task_for_actions(
    target_tasks: list[TestTask],
    action_types: list[str],
    include_finished: bool = True,
) -> TestTask | None:
    running_task = next(
        (task for task in target_tasks if task.action_type in action_types and task.status == TaskStatus.RUNNING.value),
        None,
    )
    if running_task is not None:
        return running_task

    pending_task = next(
        (task for task in target_tasks if task.action_type in action_types and task.status == TaskStatus.PENDING.value),
        None,
    )
    if pending_task is not None:
        return pending_task

    if not include_finished:
        return None

    return next((task for task in target_tasks if task.action_type in action_types), None)


def _serialize_monitor_action(task: TestTask | None, label: str) -> dict:
    if task is None:
        return {
            "label": label,
            "status": "IDLE",
            "status_text": "이력 없음",
            "message": "-",
        }

    return {
        "label": label,
        "status": task.status,
        "status_text": _task_status_text(task.status),
        "message": task.message or "-",
    }


def _task_status_text(status: str) -> str:
    if status == TaskStatus.RUNNING.value:
        return "진행중"
    if status == TaskStatus.PENDING.value:
        return "대기중"
    if status == TaskStatus.DONE.value:
        return "성공"
    if status == TaskStatus.FAIL.value:
        return "실패"
    return status
