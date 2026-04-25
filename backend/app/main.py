from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.ezdfs import router as ezdfs_router
from app.api.mypage import router as mypage_router
from app.api.rtd import router as rtd_router
from app.core.config import get_settings
from app.core.exceptions import (
    CatalogError,
    ConfigNotFoundError,
    RemoteCommandError,
    SSHConnectionError,
    TaskConflictError,
)
from app.db.session import SessionLocal, init_db
from app.services.bootstrap import ensure_default_admin, ensure_storage_dirs
from app.services.task_history import backfill_from_test_tasks, start_retention_sweeper
from app.services.task_service import fail_inflight_tasks_on_startup

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_dirs()
    init_db()
    ensure_default_admin()
    db = SessionLocal()
    try:
        fail_inflight_tasks_on_startup(db)
        backfill_from_test_tasks(db)
    finally:
        db.close()
    start_retention_sweeper()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = [
    origin.strip()
    for origin in settings.cors_origins.split(",")
    if origin.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(rtd_router)
app.include_router(ezdfs_router)
app.include_router(mypage_router)


# ─── Custom exception handlers ────────────────────────────────────────────


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": code, "message": message},
        },
    )


@app.exception_handler(SSHConnectionError)
async def ssh_connection_error_handler(_: Request, exc: SSHConnectionError) -> JSONResponse:
    return _error_response(502, "SSH_CONNECTION_ERROR", str(exc))


@app.exception_handler(RemoteCommandError)
async def remote_command_error_handler(_: Request, exc: RemoteCommandError) -> JSONResponse:
    return _error_response(502, "REMOTE_COMMAND_ERROR", str(exc))


@app.exception_handler(ConfigNotFoundError)
async def config_not_found_error_handler(_: Request, exc: ConfigNotFoundError) -> JSONResponse:
    return _error_response(404, "CONFIG_NOT_FOUND", str(exc))


@app.exception_handler(TaskConflictError)
async def task_conflict_error_handler(_: Request, exc: TaskConflictError) -> JSONResponse:
    return _error_response(409, "TASK_CONFLICT", str(exc))


@app.exception_handler(CatalogError)
async def catalog_error_handler(_: Request, exc: CatalogError) -> JSONResponse:
    return _error_response(502, "CATALOG_ERROR", str(exc))


@app.get("/health")
def health_check():
    return {
        "success": True,
        "data": {
            "app_name": settings.app_name,
            "status": "ok",
            "env": settings.app_env,
        },
    }
