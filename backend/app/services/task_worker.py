from __future__ import annotations

"""
Background task worker.

Tasks run in daemon threads. Each worker opens its own SQLAlchemy session,
acquires any required serialization queues (per RTD line / ezDFS module),
dispatches to the appropriate `*_custom.py` action, persists the result,
and writes a raw result file when applicable.
"""

import json
import threading
from datetime import datetime, timezone

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import TestTask
from app.services import ezdfs_execution_custom, rtd_execution_custom
from app.services.file_service import generate_raw_file
from app.services.rtd_execution_custom import (
    execute_compile_action,
    execute_copy_action,
    execute_sync_action,
)
from app.services.task_queue import (
    build_rtd_queue_key,
    enter_ezdfs_module_queue,
    enter_rtd_line_queue,
    extract_ezdfs_module_name,
    leave_ezdfs_module_queue,
    leave_rtd_line_queue,
    requires_ezdfs_module_queue,
    requires_rtd_line_queue,
    wait_for_ezdfs_module_turn,
    wait_for_rtd_line_turn,
)
from app.utils.enums import ActionType, TaskStatus, TaskStep, TestType


def queue_task(
    background_tasks: BackgroundTasks,
    task_id: str,
    step: TaskStep,
    test_type: TestType,
) -> None:
    background_tasks.add_task(_start_task_thread, task_id, step.value, test_type.value)


def _start_task_thread(task_id: str, step: str, test_type: str) -> None:
    worker = threading.Thread(
        target=run_task,
        args=(task_id, step),
        daemon=True,
        name=f"{test_type.lower()}-task-{task_id[:8]}",
    )
    worker.start()


def run_task(task_id: str, step: str) -> None:
    db = SessionLocal()
    ezdfs_module_name = ""
    ezdfs_queue_acquired = False
    rtd_queue_key = ""
    rtd_queue_acquired = False
    try:
        task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
        if task is None:
            return

        payload = json.loads(task.requested_payload_json or "{}")
        if requires_rtd_line_queue(task):
            rtd_queue_key = build_rtd_queue_key(task.user_id, task.target_name)
            enter_rtd_line_queue(db, task, rtd_queue_key)
            wait_for_rtd_line_turn(task.task_id, rtd_queue_key)
            rtd_queue_acquired = True
        if requires_ezdfs_module_queue(task, payload):
            ezdfs_module_name = extract_ezdfs_module_name(payload)
            enter_ezdfs_module_queue(db, task, ezdfs_module_name)
            wait_for_ezdfs_module_turn(task.task_id, ezdfs_module_name)
            ezdfs_queue_acquired = True

        task = db.query(TestTask).filter(TestTask.task_id == task_id).first()
        if task is None:
            return

        task.status = TaskStatus.RUNNING.value
        task.current_step = step
        task.started_at = datetime.now(timezone.utc)
        task.message = f"{task.action_type.title()} in progress"
        db.add(task)
        db.commit()
        db.refresh(task)

        try:
            execution_result = _run_custom_action(db, task, payload)
            task.message = execution_result["message"]
            task.status = TaskStatus.DONE.value
            task.current_step = step
            task.ended_at = datetime.now(timezone.utc)
            db.add(task)
            db.commit()
            db.refresh(task)

            if task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}:
                raw_output = execution_result.get("raw_output") or ""
                test_command = execution_result.get("test_command") or ""
                if test_command:
                    raw_output = "\n".join(filter(None, [f"command={test_command}", raw_output]))
                generate_raw_file(
                    db,
                    task,
                    raw_output,
                    execution_result.get("raw_outputs_by_rule"),
                )
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAIL.value
            task.current_step = step
            task.ended_at = datetime.now(timezone.utc)
            task.message = str(exc)
            db.add(task)
            db.commit()
    finally:
        if rtd_queue_acquired and rtd_queue_key:
            leave_rtd_line_queue(task_id, rtd_queue_key)
        if ezdfs_queue_acquired and ezdfs_module_name:
            leave_ezdfs_module_queue(task_id, ezdfs_module_name)
        db.close()


def _run_custom_action(db: Session, task: TestTask, payload: dict) -> dict[str, str]:
    if task.test_type == TestType.RTD.value:
        if task.action_type == ActionType.COPY.value:
            return execute_copy_action(db, task, payload)
        if task.action_type == ActionType.SYNC.value:
            return execute_sync_action(db, task, payload)
        if task.action_type == ActionType.COMPILE.value:
            return execute_compile_action(db, task, payload)
        if task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}:
            return rtd_execution_custom.execute_test_action(db, task, payload)

    if task.test_type == TestType.EZDFS.value:
        if task.action_type in {ActionType.TEST.value, ActionType.RETEST.value}:
            return ezdfs_execution_custom.execute_test_action(db, task, payload)

    return {"message": f"{task.action_type.title()} completed", "raw_output": ""}
