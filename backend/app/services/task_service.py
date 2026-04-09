from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import TestTask
from app.services.file_service import generate_raw_file
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
        message="Mock task queued",
        requested_payload_json=json.dumps(requested_payload),
        requested_at=_now(),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def queue_mock_task(background_tasks: BackgroundTasks, task_id: str, step: TaskStep) -> None:
    background_tasks.add_task(run_mock_task, task_id, step.value)


def run_mock_task(task_id: str, step: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
        if task is None:
            return

        task.status = TaskStatus.RUNNING.value
        task.current_step = step
        task.started_at = _now()
        task.message = f"Mock {task.action_type.lower()} in progress"
        db.add(task)
        db.commit()
        db.refresh(task)

        time.sleep(1.0)

        task.status = TaskStatus.DONE.value
        task.current_step = step
        task.ended_at = _now()
        task.message = f"Mock {task.action_type.lower()} completed"
        db.add(task)
        db.commit()
        db.refresh(task)

        if task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}:
            generate_raw_file(db, task)
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

