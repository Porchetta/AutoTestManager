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
        if "login_user" not in rtd_columns:
            connection.execute(
                text("ALTER TABLE rtd_configs ADD COLUMN login_user VARCHAR(100) NOT NULL DEFAULT ''")
            )

        ezdfs_columns = {column["name"] for column in inspector.get_columns("ezdfs_configs")}
        if "modifier" not in ezdfs_columns:
            connection.execute(
                text("ALTER TABLE ezdfs_configs ADD COLUMN modifier VARCHAR(100) NOT NULL DEFAULT ''")
            )
        if "login_user" not in ezdfs_columns:
            connection.execute(
                text("ALTER TABLE ezdfs_configs ADD COLUMN login_user VARCHAR(100) NOT NULL DEFAULT ''")
            )

        host_columns = {column["name"] for column in inspector.get_columns("host_configs")}
        if "login_user" in host_columns and "login_password" in host_columns:
            _migrate_host_credentials(connection)

        _ensure_test_task_indexes(connection)


def _ensure_test_task_indexes(connection) -> None:
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_test_tasks_user_type_requested "
        "ON test_tasks (user_id, test_type, requested_at)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_test_tasks_user_type_target "
        "ON test_tasks (user_id, test_type, target_name)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_test_tasks_active "
        "ON test_tasks (status, requested_at, id) "
        "WHERE status IN ('RUNNING','PENDING')"
    ))
    connection.execute(text("ANALYZE test_tasks"))


def _migrate_host_credentials(connection) -> None:
    legacy_hosts = connection.execute(
        text(
            "SELECT id, name, login_user, login_password, modifier FROM host_configs"
        )
    ).fetchall()

    for host_row in legacy_hosts:
        host_id, host_name, login_user, login_password, modifier = host_row
        if not login_user:
            continue

        existing = connection.execute(
            text(
                "SELECT id FROM host_credentials WHERE host_id = :host_id AND login_user = :login_user"
            ),
            {"host_id": host_id, "login_user": login_user},
        ).first()
        if existing is None:
            connection.execute(
                text(
                    "INSERT INTO host_credentials (host_id, login_user, login_password, modifier,"
                    " created_at, updated_at) VALUES (:host_id, :login_user, :login_password,"
                    " :modifier, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ),
                {
                    "host_id": host_id,
                    "login_user": login_user,
                    "login_password": login_password or "",
                    "modifier": modifier or "",
                },
            )

        connection.execute(
            text(
                "UPDATE rtd_configs SET login_user = :login_user"
                " WHERE host_name = :host_name AND (login_user IS NULL OR login_user = '')"
            ),
            {"login_user": login_user, "host_name": host_name},
        )
        connection.execute(
            text(
                "UPDATE ezdfs_configs SET login_user = :login_user"
                " WHERE host_name = :host_name AND (login_user IS NULL OR login_user = '')"
            ),
            {"login_user": login_user, "host_name": host_name},
        )

    try:
        connection.execute(text("ALTER TABLE host_configs DROP COLUMN login_password"))
        connection.execute(text("ALTER TABLE host_configs DROP COLUMN login_user"))
    except Exception:
        _rebuild_host_configs_without_legacy_columns(connection)


def _rebuild_host_configs_without_legacy_columns(connection) -> None:
    connection.execute(text("PRAGMA foreign_keys = OFF"))
    try:
        connection.execute(
            text(
                "CREATE TABLE host_configs_new ("
                " id INTEGER NOT NULL PRIMARY KEY,"
                " name VARCHAR(100) NOT NULL UNIQUE,"
                " ip VARCHAR(100) NOT NULL,"
                " modifier VARCHAR(100) NOT NULL DEFAULT '',"
                " created_at DATETIME NOT NULL,"
                " updated_at DATETIME NOT NULL"
                ")"
            )
        )
        connection.execute(
            text(
                "INSERT INTO host_configs_new (id, name, ip, modifier, created_at, updated_at)"
                " SELECT id, name, ip, modifier, created_at, updated_at FROM host_configs"
            )
        )
        connection.execute(text("DROP TABLE host_configs"))
        connection.execute(text("ALTER TABLE host_configs_new RENAME TO host_configs"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_host_configs_id ON host_configs (id)")
        )
    finally:
        connection.execute(text("PRAGMA foreign_keys = ON"))
