from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import User
from app.schemas.testing import EzdfsActionRequest, EzdfsAggregateSummaryRequest, EzdfsSessionPayload, SvnUploadRequest
from app.services.catalog_service import (
    get_ezdfs_modules,
    get_ezdfs_rules,
    get_ezdfs_sub_rules,
)
from app.services.file_download import (
    generate_aggregate_ezdfs_summary_file,
    get_ezdfs_raw_content_path,
    get_existing_download_path,
)
from app.services.file_service import generate_summary_file
from app.services.rule_favorites import list_favorite_rule_names, set_favorite
from app.services.session_service import clear_runtime_session, get_runtime_session_payload, upsert_runtime_session
from app.services.svn_upload_custom import perform_ezdfs_svn_upload
from app.services.task_service import (
    create_test_task,
    ensure_task_owner,
    list_tasks_by_type,
    serialize_task,
)
from app.services.task_worker import queue_task
from app.utils.enums import ActionType, TaskStep, TestType

router = APIRouter(prefix="/api/ezdfs", tags=["ezdfs"])


@router.get("/modules")
def modules(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return success_response({"items": get_ezdfs_modules(db, current_user)})


@router.get("/rules")
def rules(
    module_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = get_ezdfs_rules(db, current_user, module_name)
    favorites_db = list_favorite_rule_names(
        db, current_user.user_id, TestType.EZDFS, module_name
    )
    available_rule_names = {str(item.get("rule_name") or "") for item in items}
    favorite_names = sorted(name for name in favorites_db if name in available_rule_names)
    favorite_set = set(favorite_names)
    favored = [item for item in items if str(item.get("rule_name") or "") in favorite_set]
    rest = [item for item in items if str(item.get("rule_name") or "") not in favorite_set]
    return success_response({"items": favored + rest, "favorite_names": favorite_names})


class _EzdfsFavoriteRequest(BaseModel):
    module_name: str
    rule_name: str
    favorite: bool


@router.post("/rules/favorite")
def toggle_rule_favorite(
    payload: _EzdfsFavoriteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new_state = set_favorite(
        db,
        current_user.user_id,
        TestType.EZDFS,
        payload.module_name,
        payload.rule_name,
        payload.favorite,
    )
    favorites_db = list_favorite_rule_names(
        db, current_user.user_id, TestType.EZDFS, payload.module_name
    )
    return success_response({
        "rule_name": payload.rule_name,
        "favorite": new_state,
        "favorite_names": sorted(favorites_db),
    })


@router.get("/sub-rules")
def sub_rules(
    module_name: str,
    rule_name: str,
    file_name: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        items = get_ezdfs_sub_rules(db, current_user, module_name, rule_name, file_name=file_name)
        return success_response({"items": items, "error": ""})
    except (ValueError, OSError, RuntimeError) as exc:
        return success_response({"items": ["error"], "error": str(exc)})


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
    existing_payload = get_runtime_session_payload(db, current_user.user_id, TestType.EZDFS)
    session_payload = payload.model_dump()

    cached_catalog = existing_payload.get("catalog_cache")
    if cached_catalog and cached_catalog.get("module_name") == session_payload.get("selected_module"):
        session_payload["catalog_cache"] = cached_catalog

    session = upsert_runtime_session(db, current_user.user_id, TestType.EZDFS, session_payload)
    return success_response({"session": session})


@router.delete("/session")
def delete_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clear_runtime_session(db, current_user.user_id, TestType.EZDFS)
    return success_response({"message": "ezDFS session cleared"})


@router.post("/svn-upload")
def svn_upload(
    payload: SvnUploadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = perform_ezdfs_svn_upload(db, current_user, payload.ad_user, payload.ad_password)
    return success_response({"svn_upload": result})


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
        target_name=payload.rule_name,
        requested_payload=payload.model_dump(),
        current_step=TaskStep.TESTING,
    )
    queue_task(background_tasks, task.task_id, TaskStep.TESTING, TestType.EZDFS)
    return success_response({"task": serialize_task(task)})


@router.post("/actions/sync")
def sync_action(
    payload: EzdfsActionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = create_test_task(
        db=db,
        test_type=TestType.EZDFS,
        action_type=ActionType.SYNC,
        owner_user_id=current_user.user_id,
        target_name=payload.rule_name,
        requested_payload=payload.model_dump(),
        current_step=TaskStep.SYNCING,
    )
    queue_task(background_tasks, task.task_id, TaskStep.SYNCING, TestType.EZDFS)
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
    path = get_ezdfs_raw_content_path(task) or get_existing_download_path(task, kind="raw")
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


@router.post("/results/aggregate-summary")
def download_aggregate_summary(
    payload: EzdfsAggregateSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    path = generate_aggregate_ezdfs_summary_file(
        db,
        current_user.user_id,
        payload.module_name,
        payload.task_ids,
    )
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
