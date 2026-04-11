from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import TestTask, User
from app.services.file_service import generate_raw_file
from app.services.rtd_execution_custom import (
    execute_compile_action,
    execute_copy_action,
    execute_test_action,
)
from app.utils.enums import ActionType, TaskStatus, TestType, TaskStep


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
    duplicate = (
        db.query(TestTask)
        .filter(
            TestTask.user_id == owner_user_id,
            TestTask.test_type == test_type.value,
            TestTask.action_type == action_type.value,
            TestTask.target_name == target_name,
            TestTask.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value]),
        )
        .first()
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


def queue_mock_task(background_tasks: BackgroundTasks, task_id: str, step: TaskStep) -> None:
    background_tasks.add_task(_start_mock_task_thread, task_id, step.value)


def _start_mock_task_thread(task_id: str, step: str) -> None:
    worker = threading.Thread(
        target=run_mock_task,
        args=(task_id, step),
        daemon=True,
        name=f"rtd-task-{task_id[:8]}",
    )
    worker.start()


def run_mock_task(task_id: str, step: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
        if task is None:
            return

        payload = json.loads(task.requested_payload_json or "{}")
        task.status = TaskStatus.RUNNING.value
        task.current_step = step
        task.started_at = _now()
        task.message = f"{task.action_type.title()} in progress"
        db.add(task)
        db.commit()
        db.refresh(task)

        try:
            execution_result = _run_rtd_custom_action(db, task, payload)
            task.message = execution_result["message"]
            task.status = TaskStatus.DONE.value
            task.current_step = step
            task.ended_at = _now()
            db.add(task)
            db.commit()
            db.refresh(task)

            if task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}:
                generate_raw_file(db, task, execution_result.get("raw_output"))
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAIL.value
            task.current_step = step
            task.ended_at = _now()
            task.message = str(exc)
            db.add(task)
            db.commit()
    finally:
        db.close()


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


def list_rtd_target_monitor_items(db: Session, target_names: list[str], current_user_id: str) -> list[dict]:
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
        items.append(_build_rtd_target_monitor_item(target_name, target_tasks, current_user_id, user_name_map))
    return items


def serialize_task(task: TestTask) -> dict:
    return {
        "task_id": task.task_id,
        "test_type": task.test_type,
        "action_type": task.action_type,
        "target_name": task.target_name,
        "status": task.status,
        "current_step": task.current_step,
        "message": task.message,
        "requested_at": task.requested_at,
        "started_at": task.started_at,
        "ended_at": task.ended_at,
        "raw_result_ready": bool(task.raw_result_path),
        "summary_result_ready": bool(task.summary_result_path),
    }


def _run_rtd_custom_action(db: Session, task: TestTask, payload: dict) -> dict[str, str]:
    if task.test_type != TestType.RTD.value:
        return {"message": f"{task.action_type.title()} completed", "raw_output": ""}

    if task.action_type == ActionType.COPY.value:
        return execute_copy_action(db, task, payload)
    if task.action_type == ActionType.COMPILE.value:
        return execute_compile_action(db, task, payload)
    if task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}:
        return execute_test_action(db, task, payload)
    return {"message": f"{task.action_type.title()} completed", "raw_output": ""}


def _build_rtd_target_monitor_item(
    target_name: str,
    target_tasks: list[TestTask],
    current_user_id: str,
    user_name_map: dict[str, str],
) -> dict:
    active_task = next((task for task in target_tasks if task.status == TaskStatus.RUNNING.value), None)
    if active_task is None:
        active_task = next((task for task in target_tasks if task.status == TaskStatus.PENDING.value), None)

    latest_copy_task = _select_latest_task_for_actions(
        target_tasks,
        [ActionType.COPY.value],
        include_finished=True,
    )
    latest_compile_task = _select_latest_task_for_actions(target_tasks, [ActionType.COMPILE.value])
    latest_test_task = _select_latest_task_for_actions(
        target_tasks,
        [ActionType.TEST.value, ActionType.RETEST.value],
    )

    latest_user_test_task = next(
        (
            task
            for task in target_tasks
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
        "compile": _serialize_monitor_action(latest_compile_task, "컴파일"),
        "test": _serialize_monitor_action(latest_test_task, "테스트"),
        "raw_download": {
            "enabled": bool(raw_download_task),
            "task_id": raw_download_task.task_id if raw_download_task else None,
            "label": "다운로드 가능" if raw_download_task else "없음",
        },
    }


def _build_current_status_text(task: TestTask | None, user_name_map: dict[str, str]) -> str:
    if task is None:
        return "대기 없음"

    action_label = "테스트" if task.action_type == ActionType.RETEST.value else {
        ActionType.COPY.value: "복사",
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
