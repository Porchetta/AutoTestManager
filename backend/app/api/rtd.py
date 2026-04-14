from __future__ import annotations

import io
import re
import zipfile

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import User
from app.schemas.testing import (
    RtdActionRequest,
    RtdMacroCompareRequest,
    RtdSessionPayload,
    SvnUploadRequest,
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
    get_rtd_raw_rule_file_map,
)
from app.services.session_service import clear_runtime_session, get_runtime_session_payload, upsert_runtime_session
from app.services.svn_upload_custom import perform_rtd_svn_upload
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


def _sanitize_download_token(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return sanitized.strip("._-") or "report"


def _build_rtd_raw_txt_name(task, rule_name: str) -> str:
    line_name = _sanitize_download_token(_normalize_target_line_name(task.target_name))
    return f"{line_name}-{_sanitize_download_token(rule_name)}.txt"


def _build_rtd_task_requests(
    payload: RtdActionRequest,
    action_type: ActionType,
) -> list[tuple[str, dict]]:
    request_payload = payload.model_dump()
    sorted_target_lines = sorted(
        payload.target_lines,
        key=lambda item: _normalize_target_line_name(str(item or "")).lower(),
    )
    return [(target_line, request_payload) for target_line in sorted_target_lines]


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


@router.post("/svn-upload")
def svn_upload(
    payload: SvnUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = perform_rtd_svn_upload(db, current_user, payload.ad_user, payload.ad_password)
    return success_response({"svn_upload": result})


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
    if action_type in {ActionType.TEST, ActionType.RETEST} and not payload.payload.get("selected_rule_targets"):
        raise HTTPException(status_code=422, detail="selected_rule_targets is required")

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

    task_requests = _build_rtd_task_requests(
        RtdActionRequest(target_lines=target_lines, payload=payload.payload),
        action_type,
    )
    if action_type in {ActionType.TEST, ActionType.RETEST} and not task_requests:
        raise HTTPException(status_code=422, detail="selected_rule_targets is required")

    items = []
    for target_line, requested_payload in task_requests:
        task = create_test_task(
            db=db,
            test_type=TestType.RTD,
            action_type=action_type,
            owner_user_id=current_user.user_id,
            target_name=target_line,
            requested_payload=requested_payload,
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
    session_payload = get_runtime_session_payload(db, current_user.user_id, TestType.RTD)
    items = list_rtd_target_monitor_items(
        db,
        target_items,
        current_user.user_id,
        session_payload.get("monitor_rule_selection", {}),
    )
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
    selected_rule: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id, TestType.RTD)
    sections = {
        rule_name: file_path.read_text(encoding="utf-8", errors="ignore")
        for rule_name, file_path in get_rtd_raw_rule_file_map(task).items()
    }
    normalized_rule = str(selected_rule or "").strip()

    if not sections:
        raise HTTPException(status_code=404, detail="Rule raw data files not found for this RTD task")

    if normalized_rule and normalized_rule != "__ALL__":
        content = sections.get(normalized_rule)
        if content is None:
            raise HTTPException(status_code=404, detail="Selected rule raw data not found")
        filename = _build_rtd_raw_txt_name(task, normalized_rule)
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rule_name, content in sections.items():
            archive.writestr(_build_rtd_raw_txt_name(task, rule_name), content)
    zip_buffer.seek(0)
    zip_name = f"{_sanitize_download_token(_normalize_target_line_name(task.target_name))}-raw.zip"
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


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
