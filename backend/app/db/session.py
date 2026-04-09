from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db():
    from app.models import entities  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_legacy_columns()


def _ensure_legacy_columns():
    with engine.begin() as connection:
        inspector = inspect(connection)

        host_columns = {column["name"] for column in inspector.get_columns("host_configs")}
        if "modifier" not in host_columns:
            connection.execute(
                text("ALTER TABLE host_configs ADD COLUMN modifier VARCHAR(100) NOT NULL DEFAULT ''")
            )

        rtd_columns = {column["name"] for column in inspector.get_columns("rtd_configs")}
        if "modifier" not in rtd_columns:
            connection.execute(
                text("ALTER TABLE rtd_configs ADD COLUMN modifier VARCHAR(100) NOT NULL DEFAULT ''")
            )

        ezdfs_columns = {column["name"] for column in inspector.get_columns("ezdfs_configs")}
        if "modifier" not in ezdfs_columns:
            connection.execute(
                text("ALTER TABLE ezdfs_configs ADD COLUMN modifier VARCHAR(100) NOT NULL DEFAULT ''")
            )
