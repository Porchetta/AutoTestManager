from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.entities import User

settings = get_settings()


def ensure_storage_dirs():
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(settings.result_base_path).mkdir(parents=True, exist_ok=True)


def ensure_default_admin():
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.user_id == settings.default_admin_user_id).first()
        if existing:
            return

        admin = User(
            user_id=settings.default_admin_user_id,
            password_hash=get_password_hash(settings.default_admin_password),
            user_name=settings.default_admin_name,
            module_name=settings.default_admin_module_name,
            is_admin=True,
            is_approved=True,
        )
        db.add(admin)
        db.commit()
    finally:
        db.close()

