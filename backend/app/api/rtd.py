from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import User
from app.schemas.testing import (
    RtdActionRequest,
    RtdSessionPayload,
)
from app.services.catalog_service import (
    get_business_units,
    get_lines_by_business_unit,
    get_macros_by_rule_name,
    get_rule_versions,
    get_rules_by_line_name,
    get_target_lines_by_business_unit,
)
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

router = APIRouter(prefix="/api/rtd", tags=["rtd"])


@router.get("/business-units")
def business_units(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_business_units(db, current_user)})


@router.get("/lines")
def lines(
    business_unit: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_lines_by_business_unit(db, business_unit, current_user)})


@router.get("/rules")
def rules(line_name: str):
    return success_response({"items": get_rules_by_line_name(line_name)})


@router.get("/macros")
def macros(rule_name: str):
    return success_response({"items": get_macros_by_rule_name(rule_name)})


@router.get("/versions/rules")
def rule_versions(rule_name: str):
    return success_response({"items": get_rule_versions(rule_name)})


@router.get("/versions/macros")
def macro_versions(macro_name: str):
    return success_response({"items": get_rule_versions(macro_name)})


@router.get("/target-lines")
def target_lines(
    business_unit: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_target_lines_by_business_unit(db, business_unit, current_user)})


@router.get("/session")
def get_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payload = get_runtime_session_payload(db, current_user.user_id, TestType.RTD)
    return success_response({"session": payload})


@router.put("/session")
def save_session(
    payload: RtdSessionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = upsert_runtime_session(db, current_user.user_id, TestType.RTD, payload.model_dump())
    return success_response({"session": session})


@router.delete("/session")
def delete_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clear_runtime_session(db, current_user.user_id, TestType.RTD)
    return success_response({"message": "RTD session cleared"})


def _create_rtd_tasks(
    background_tasks: BackgroundTasks,
    db: Session,
    current_user: User,
    payload: RtdActionRequest,
    action_type: ActionType,
    step: TaskStep,
):
    if not payload.target_lines:
        raise HTTPException(status_code=422, detail="target_lines is required")

    items = []
    for target_line in payload.target_lines:
        task = create_test_task(
            db=db,
            test_type=TestType.RTD,
            action_type=action_type,
            owner_user_id=current_user.user_id,
            target_name=target_line,
            requested_payload=payload.model_dump(),
            current_step=step,
        )
        queue_mock_task(background_tasks, task.task_id, step)
        items.append(serialize_task(task))

    return success_response({"items": items})


@router.post("/actions/copy")
def copy_action(
    payload: RtdActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_rtd_tasks(background_tasks, db, current_user, payload, ActionType.COPY, TaskStep.COPYING)


@router.post("/actions/compile")
def compile_action(
    payload: RtdActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_rtd_tasks(background_tasks, db, current_user, payload, ActionType.COMPILE, TaskStep.COMPILING)


@router.post("/actions/test")
def test_action(
    payload: RtdActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_rtd_tasks(background_tasks, db, current_user, payload, ActionType.TEST, TaskStep.TESTING)


@router.post("/actions/retest")
def retest_action(
    payload: RtdActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _create_rtd_tasks(background_tasks, db, current_user, payload, ActionType.RETEST, TaskStep.TESTING)


@router.get("/status")
def list_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = list_tasks_by_type(db, current_user.user_id, TestType.RTD)
    return success_response({"items": [serialize_task(task) for task in items]})


@router.get("/status/{task_id}")
def get_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.RTD)
    return success_response({"task": serialize_task(task)})


@router.get("/results/{task_id}/raw")
def download_raw(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.RTD)
    path = get_existing_download_path(task, kind="raw")
    return FileResponse(path=path, filename=path.name, media_type="text/plain")


@router.post("/results/{task_id}/summary")
def generate_summary(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.RTD)
    generate_summary_file(db, task)
    return success_response({"task": serialize_task(task)})


@router.get("/results/{task_id}/summary")
def download_summary(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.RTD)
    path = get_existing_download_path(task, kind="summary")
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

