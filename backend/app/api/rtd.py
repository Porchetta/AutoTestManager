from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import User
from app.schemas.testing import (
    RtdActionRequest,
    RtdMacroCompareRequest,
    RtdSessionPayload,
)
from app.services.catalog_service import (
    compare_macros_by_rule_targets,
    get_business_units,
    get_lines_by_business_unit,
    get_rule_versions_by_line_name,
    get_rules_by_line_name,
    get_target_lines_by_business_unit,
)
from app.services.file_service import (
    generate_aggregate_rtd_summary_file,
    generate_summary_file,
    get_existing_download_path,
)
from app.services.session_service import clear_runtime_session, get_runtime_session_payload, upsert_runtime_session
from app.services.task_service import (
    create_test_task,
    ensure_task_owner,
    list_rtd_target_monitor_items,
    list_tasks_by_type,
    queue_mock_task,
    serialize_task,
)
from app.utils.enums import ActionType, TaskStep, TestType

router = APIRouter(prefix="/api/rtd", tags=["rtd"])


def _normalize_target_line_name(line_name: str) -> str:
    return str(line_name or "").replace("_TARGET", "")


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
def rules(
    line_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_rules_by_line_name(db, current_user, line_name)})


@router.post("/macros/compare")
def compare_macros(
    payload: RtdMacroCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = compare_macros_by_rule_targets(db, current_user, payload.line_name, payload.selected_rule_targets)
        result["searched"] = True
    except Exception as exc:  # noqa: BLE001
        result = {
            "searched": True,
            "old_macros": ["error"],
            "new_macros": ["error"],
            "has_diff": False,
            "error": str(exc),
        }

    session_payload = get_runtime_session_payload(db, current_user.user_id, TestType.RTD)
    session_payload["macro_review"] = result
    upsert_runtime_session(db, current_user.user_id, TestType.RTD, session_payload)
    return success_response(result)


@router.get("/versions/rules")
def rule_versions(
    rule_name: str,
    line_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_rule_versions_by_line_name(db, current_user, line_name, rule_name)})


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
    existing_payload = get_runtime_session_payload(db, current_user.user_id, TestType.RTD)
    session_payload = payload.model_dump()

    cached_catalog = existing_payload.get("catalog_cache")
    if cached_catalog and cached_catalog.get("line_name") == session_payload.get("selected_line_name"):
        session_payload["catalog_cache"] = cached_catalog

    session = upsert_runtime_session(db, current_user.user_id, TestType.RTD, session_payload)
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

    target_lines = payload.target_lines
    if action_type == ActionType.COPY:
        selected_line_name = str(payload.payload.get("selected_line_name", "")).strip()
        target_lines = [
            target_line
            for target_line in payload.target_lines
            if _normalize_target_line_name(target_line) != selected_line_name
        ]

    if not target_lines:
        return success_response({"items": []})

    items = []
    for target_line in target_lines:
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


@router.get("/monitor")
def monitor_status(
    target_lines: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_items = [item.strip() for item in target_lines.split(",") if item.strip()]
    items = list_rtd_target_monitor_items(db, target_items, current_user.user_id)
    return success_response({"items": items})


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


@router.get("/results/aggregate-summary")
def download_aggregate_summary(
    target_lines: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target_items = [item.strip() for item in target_lines.split(",") if item.strip()]
    path = generate_aggregate_rtd_summary_file(db, current_user.user_id, target_items)
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
