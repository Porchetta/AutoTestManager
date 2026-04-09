from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import User
from app.schemas.testing import EzdfsActionRequest, EzdfsSessionPayload
from app.services.catalog_service import get_ezdfs_modules, get_ezdfs_rules
from app.services.file_service import generate_summary_file, get_existing_download_path
from app.services.session_service import clear_runtime_session, get_runtime_session_payload, upsert_runtime_session
from app.services.task_service import (
    create_test_task,
    ensure_task_owner,
    list_tasks_by_type,
    queue_mock_task,
    serialize_task,
)
from app.utils.enums import ActionType, TaskStep, TestType

router = APIRouter(prefix="/api/ezdfs", tags=["ezdfs"])


@router.get("/modules")
def modules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_ezdfs_modules(db, current_user)})


@router.get("/rules")
def rules(module_name: str):
    return success_response({"items": get_ezdfs_rules(module_name)})


@router.get("/session")
def get_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = get_runtime_session_payload(db, current_user.user_id, TestType.EZDFS)
    return success_response({"session": payload})


@router.put("/session")
def save_session(
    payload: EzdfsSessionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = upsert_runtime_session(db, current_user.user_id, TestType.EZDFS, payload.model_dump())
    return success_response({"session": session})


@router.delete("/session")
def delete_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clear_runtime_session(db, current_user.user_id, TestType.EZDFS)
    return success_response({"message": "ezDFS session cleared"})


def _create_ezdfs_task(
    payload: EzdfsActionRequest,
    action_type: ActionType,
    background_tasks: BackgroundTasks,
    current_user: User,
    db: Session,
):
    task = create_test_task(
        db=db,
        test_type=TestType.EZDFS,
        action_type=action_type,
        owner_user_id=current_user.user_id,
        target_name=payload.module_name,
        requested_payload=payload.model_dump(),
        current_step=TaskStep.TESTING,
    )
    queue_mock_task(background_tasks, task.task_id, TaskStep.TESTING)
    return success_response({"task": serialize_task(task)})


@router.post("/actions/test")
def test_action(
    payload: EzdfsActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_ezdfs_task(payload, ActionType.TEST, background_tasks, current_user, db)


@router.post("/actions/retest")
def retest_action(
    payload: EzdfsActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_ezdfs_task(payload, ActionType.RETEST, background_tasks, current_user, db)


@router.get("/status")
def list_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = list_tasks_by_type(db, current_user.user_id, TestType.EZDFS)
    return success_response({"items": [serialize_task(task) for task in items]})


@router.get("/status/{task_id}")
def get_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.EZDFS)
    return success_response({"task": serialize_task(task)})


@router.get("/results/{task_id}/raw")
def download_raw(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.EZDFS)
    path = get_existing_download_path(task, kind="raw")
    return FileResponse(path=path, filename=path.name, media_type="text/plain")


@router.post("/results/{task_id}/summary")
def generate_summary(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.EZDFS)
    generate_summary_file(db, task)
    return success_response({"task": serialize_task(task)})


@router.get("/results/{task_id}/summary")
def download_summary(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.EZDFS)
    path = get_existing_download_path(task, kind="summary")
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

