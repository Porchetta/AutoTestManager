from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.responses import success_response
from app.models.entities import User
from app.services.file_service import get_existing_download_path
from app.services.task_service import ensure_task_owner, list_tasks_by_type, serialize_task
from app.utils.enums import TestType

router = APIRouter(prefix="/api/mypage", tags=["mypage"])


@router.get("/rtd/recent")
def recent_rtd(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = list_tasks_by_type(db, current_user.user_id, TestType.RTD, limit=20)
    return success_response({"items": [serialize_task(task) for task in tasks]})


@router.get("/ezdfs/recent")
def recent_ezdfs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = list_tasks_by_type(db, current_user.user_id, TestType.EZDFS, limit=20)
    return success_response({"items": [serialize_task(task) for task in tasks]})


@router.get("/results/{task_id}/download")
def download_result(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = ensure_task_owner(db, task_id, current_user.user_id)
    kind = "summary" if task.summary_result_path else "raw"
    path = get_existing_download_path(task, kind=kind)
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if kind == "summary"
        else "text/plain"
    )
    return FileResponse(path=path, filename=path.name, media_type=media_type)

