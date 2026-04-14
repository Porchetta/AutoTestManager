from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AutoTestManager Backend"
    app_env: str = "local"
    log_level: str = "INFO"

    jwt_secret_key: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24

    db_path: str = str(BASE_DIR / "data" / "autotestmanager.db")
    result_base_path: str = str(BASE_DIR / "data" / "results")
    svn_upload_host_ip: str = ""
    svn_upload_host_user: str = ""
    svn_upload_host_password: str = ""
    svn_upload_dir: str = str(BASE_DIR / "data" / "svn_repo")
    svn_upload_command: str = "svn_bin_checkin"

    default_admin_user_id: str = "admin"
    default_admin_password: str = "admin1234"
    default_admin_name: str = "Default Admin"
    default_admin_module_name: str = "SYSTEM"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
