from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    modifier: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    credentials: Mapped[list["HostCredential"]] = relationship(
        "HostCredential",
        back_populates="host",
        cascade="all, delete-orphan",
        order_by="HostCredential.login_user",
    )


class HostCredential(TimestampMixin, Base):
    __tablename__ = "host_credentials"
    __table_args__ = (
        UniqueConstraint("host_id", "login_user", name="uq_host_credential_host_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    host_id: Mapped[int] = mapped_column(
        ForeignKey("host_configs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    login_user: Mapped[str] = mapped_column(String(100), nullable=False)
    login_password: Mapped[str] = mapped_column(String(255), nullable=False)
    modifier: Mapped[str] = mapped_column(String(100), nullable=False, default="")

    host: Mapped[HostConfig] = relationship("HostConfig", back_populates="credentials")


class RtdConfig(TimestampMixin, Base):
    __tablename__ = "rtd_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    line_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    line_id: Mapped[str] = mapped_column(String(100), nullable=False)
    business_unit: Mapped[str] = mapped_column(String(100), nullable=False)
    home_dir_path: Mapped[str] = mapped_column(String(255), nullable=False)
    host_name: Mapped[str] = mapped_column(ForeignKey("host_configs.name"), nullable=False)
    login_user: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    modifier: Mapped[str] = mapped_column(String(100), nullable=False)


class EzdfsConfig(TimestampMixin, Base):
    __tablename__ = "ezdfs_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    module_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    home_dir_path: Mapped[str] = mapped_column(String(255), nullable=False)
    host_name: Mapped[str] = mapped_column(ForeignKey("host_configs.name"), nullable=False)
    login_user: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    modifier: Mapped[str] = mapped_column(String(100), nullable=False)


class TestTask(TimestampMixin, Base):
    __tablename__ = "test_tasks"
    __table_args__ = (
        Index(
            "ix_test_tasks_user_type_requested",
            "user_id", "test_type", "requested_at",
        ),
        Index(
            "ix_test_tasks_user_type_target",
            "user_id", "test_type", "target_name",
        ),
        Index(
            "ix_test_tasks_active",
            "status", "requested_at", "id",
            sqlite_where=text("status IN ('RUNNING','PENDING')"),
        ),
    )

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


class TaskHistoryDaily(Base):
    """일별 사용자/테스트타입 단위 태스크 카운트 집계.

    Why: TestTask는 보존 정책에 따라 삭제되지만, Dashboard/MyPage 차트는
    영향을 받으면 안 되므로 차트 소스를 별도 집계 테이블로 분리한다.
    """

    __tablename__ = "task_history_daily"
    __table_args__ = (
        UniqueConstraint("date", "user_id", "test_type", name="uq_task_history_daily_key"),
        Index("ix_task_history_daily_date", "date"),
        Index("ix_task_history_daily_user_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False)
    test_type: Mapped[str] = mapped_column(String(20), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class DashboardLike(TimestampMixin, Base):
    __tablename__ = "dashboard_likes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.user_id"), unique=True, index=True, nullable=False)
