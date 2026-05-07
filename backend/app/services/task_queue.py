from __future__ import annotations

"""
RTD line / ezDFS module queue primitives.

Background workers call the queue functions to serialize task execution against
a shared remote host. RTD tasks are serialized per user+line, ezDFS tasks per
module name. Pending tasks' `message` field is kept in sync with their queue
position so the UI can render the wait state.
"""

import json
import threading

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import TestTask
from app.utils.enums import ActionType, TaskStatus, TaskStep, TestType
from app.utils.naming import normalize_target_line_name

_EZDFS_QUEUE_CONDITION = threading.Condition()
_EZDFS_MODULE_QUEUES: dict[str, list[str]] = {}
_RTD_QUEUE_CONDITION = threading.Condition()
_RTD_LINE_QUEUES: dict[str, list[str]] = {}


def requires_ezdfs_module_queue(task: TestTask, payload: dict) -> bool:
    return (
        task.test_type == TestType.EZDFS.value
        and task.action_type in {ActionType.SYNC.value, ActionType.TEST.value, ActionType.RETEST.value}
        and bool(extract_ezdfs_module_name(payload))
    )


def requires_rtd_line_queue(task: TestTask) -> bool:
    return task.test_type == TestType.RTD.value and task.action_type in {
        ActionType.COPY.value,
        ActionType.SYNC.value,
        ActionType.COMPILE.value,
        ActionType.TEST.value,
        ActionType.RETEST.value,
    }


def build_rtd_queue_key(user_id: str, target_name: str) -> str:
    return f"{user_id}::{normalize_target_line_name(target_name)}"


def enter_ezdfs_module_queue(db: Session, task: TestTask, module_name: str) -> None:
    with _EZDFS_QUEUE_CONDITION:
        queue = _EZDFS_MODULE_QUEUES.setdefault(module_name, [])
        if task.task_id not in queue:
            queue.append(task.task_id)
        position = queue.index(task.task_id) + 1
        current_head_task_id = queue[0] if queue else ""

    task.status = TaskStatus.PENDING.value
    task.current_step = task.current_step or TaskStep.TESTING.value
    task.message = (
        f"Queue: {_get_ezdfs_task_rule_name(db, current_head_task_id) or module_name} ({position})"
        if position > 1
        else f"Queued: {_get_ezdfs_task_rule_name(db, task.task_id) or task.target_name}"
    )
    db.add(task)
    db.commit()
    db.refresh(task)


def wait_for_ezdfs_module_turn(task_id: str, module_name: str) -> None:
    with _EZDFS_QUEUE_CONDITION:
        while True:
            queue = _EZDFS_MODULE_QUEUES.get(module_name, [])
            if queue and queue[0] == task_id:
                return
            _refresh_ezdfs_wait_message(task_id, module_name, queue[0] if queue else "")
            _EZDFS_QUEUE_CONDITION.wait(timeout=1.0)


def leave_ezdfs_module_queue(task_id: str, module_name: str) -> None:
    with _EZDFS_QUEUE_CONDITION:
        queue = _EZDFS_MODULE_QUEUES.get(module_name, [])
        if task_id in queue:
            queue.remove(task_id)
        if not queue:
            _EZDFS_MODULE_QUEUES.pop(module_name, None)
        _EZDFS_QUEUE_CONDITION.notify_all()


def enter_rtd_line_queue(db: Session, task: TestTask, queue_key: str) -> None:
    with _RTD_QUEUE_CONDITION:
        queue = _RTD_LINE_QUEUES.setdefault(queue_key, [])
        if task.task_id not in queue:
            queue.append(task.task_id)
        position = queue.index(task.task_id) + 1
        current_head_task_id = queue[0] if queue else ""

    task.status = TaskStatus.PENDING.value
    task.current_step = task.current_step or TaskStep.TESTING.value
    task.message = (
        f"Queue: {_get_rtd_task_display_name(db, current_head_task_id)} ({position})"
        if position > 1
        else f"Queued: {_get_rtd_task_display_name(db, task.task_id)}"
    )
    db.add(task)
    db.commit()
    db.refresh(task)


def wait_for_rtd_line_turn(task_id: str, queue_key: str) -> None:
    with _RTD_QUEUE_CONDITION:
        while True:
            queue = _RTD_LINE_QUEUES.get(queue_key, [])
            if queue and queue[0] == task_id:
                return
            _refresh_rtd_wait_message(task_id, queue_key, queue[0] if queue else "")
            _RTD_QUEUE_CONDITION.wait(timeout=1.0)


def leave_rtd_line_queue(task_id: str, queue_key: str) -> None:
    with _RTD_QUEUE_CONDITION:
        queue = _RTD_LINE_QUEUES.get(queue_key, [])
        if task_id in queue:
            queue.remove(task_id)
        if not queue:
            _RTD_LINE_QUEUES.pop(queue_key, None)
        _RTD_QUEUE_CONDITION.notify_all()


def extract_ezdfs_module_name(payload: dict) -> str:
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        return str(
            payload.get("module_name")
            or nested_payload.get("selected_module")
            or ""
        ).strip()
    return str(payload.get("module_name") or "").strip()


def _extract_ezdfs_rule_name(payload: dict) -> str:
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        return str(
            payload.get("rule_name")
            or nested_payload.get("selected_rule")
            or ""
        ).strip()
    return str(payload.get("rule_name") or "").strip()


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


def _refresh_ezdfs_wait_message(task_id: str, module_name: str, current_head_task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
        if task is None or task.status != TaskStatus.PENDING.value:
            return

        rule_name = _get_ezdfs_task_rule_name(db, current_head_task_id) or module_name
        with _EZDFS_QUEUE_CONDITION:
            queue = _EZDFS_MODULE_QUEUES.get(module_name, [])
            position = queue.index(task_id) + 1 if task_id in queue else 0

        next_message = f"Queue: {rule_name} ({position})" if position > 1 else f"Queued: {rule_name}"
        if task.message == next_message:
            return

        task.message = next_message
        db.add(task)
        db.commit()
    finally:
        db.close()


def _refresh_rtd_wait_message(task_id: str, queue_key: str, current_head_task_id: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
        if task is None or task.status != TaskStatus.PENDING.value:
            return

        current_label = _get_rtd_task_display_name(db, current_head_task_id) or normalize_target_line_name(task.target_name)
        with _RTD_QUEUE_CONDITION:
            queue = _RTD_LINE_QUEUES.get(queue_key, [])
            position = queue.index(task_id) + 1 if task_id in queue else 0

        next_message = f"Queue: {current_label} ({position})" if position > 1 else f"Queued: {_get_rtd_task_display_name(db, task_id)}"
        if task.message == next_message:
            return

        task.message = next_message
        db.add(task)
        db.commit()
    finally:
        db.close()


def _get_rtd_task_display_name(db: Session, task_id: str) -> str:
    task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
    if task is None:
        return ""

    action_label = "테스트" if task.action_type == ActionType.RETEST.value else {
        ActionType.COPY.value: "복사",
        ActionType.COMPILE.value: "컴파일",
        ActionType.TEST.value: "테스트",
    }.get(task.action_type, task.action_type)
    rule_name = _extract_rtd_task_primary_rule_name(task)
    if rule_name:
        return f"{action_label} {rule_name}"
    return f"{action_label} {normalize_target_line_name(task.target_name)}"


def _extract_rtd_task_primary_rule_name(task: TestTask) -> str:
    try:
        requested_payload = json.loads(task.requested_payload_json or "{}")
    except (json.JSONDecodeError, ValueError):
        return ""
    return _extract_rtd_primary_rule_name(requested_payload)


def _get_ezdfs_task_rule_name(db: Session, task_id: str) -> str:
    task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
    if task is None:
        return ""

    try:
        payload = json.loads(task.requested_payload_json or "{}")
    except (json.JSONDecodeError, ValueError):
        return task.target_name

    return _extract_ezdfs_rule_name(payload) or task.target_name
