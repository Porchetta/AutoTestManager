from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_utc,
        onupdate=now_utc,
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_name: Mapped[str] = mapped_column(String(100), nullable=False)
    module_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class HostConfig(TimestampMixin, Base):
    __tablename__ = "host_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ip: Mapped[str] = mapped_column(String(100), nullable=False)
    login_user: Mapped[str] = mapped_column(String(100), nullable=False)
    login_password: Mapped[str] = mapped_column(String(255), nullable=False)
    modifier: Mapped[str] = mapped_column(String(100), nullable=False, default="")


class RtdConfig(TimestampMixin, Base):
    __tablename__ = "rtd_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    line_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    line_id: Mapped[str] = mapped_column(String(100), nullable=False)
    business_unit: Mapped[str] = mapped_column(String(100), nullable=False)
    home_dir_path: Mapped[str] = mapped_column(String(255), nullable=False)
    host_name: Mapped[str] = mapped_column(ForeignKey("host_configs.name"), nullable=False)
    modifier: Mapped[str] = mapped_column(String(100), nullable=False)


class EzdfsConfig(TimestampMixin, Base):
    __tablename__ = "ezdfs_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    home_dir_path: Mapped[str] = mapped_column(String(255), nullable=False)
    host_name: Mapped[str] = mapped_column(ForeignKey("host_configs.name"), nullable=False)
    modifier: Mapped[str] = mapped_column(String(100), nullable=False)


class TestTask(TimestampMixin, Base):
    __tablename__ = "test_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    test_type: Mapped[str] = mapped_column(String(20), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    target_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_step: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    requested_payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    raw_result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    summary_result_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RuntimeSession(Base):
    __tablename__ = "runtime_sessions"
    __table_args__ = (UniqueConstraint("user_id", "session_type", name="uq_runtime_session_user_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False)


class DashboardLike(TimestampMixin, Base):
    __tablename__ = "dashboard_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), unique=True, index=True, nullable=False)
