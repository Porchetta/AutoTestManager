from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.ezdfs import router as ezdfs_router
from app.api.mypage import router as mypage_router
from app.api.rtd import router as rtd_router
from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.bootstrap import ensure_default_admin, ensure_storage_dirs
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
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
