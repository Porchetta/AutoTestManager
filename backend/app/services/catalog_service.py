from __future__ import annotations

import shlex
from collections import defaultdict
import re

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, HostConfig, RtdConfig, User
from app.services.session_service import get_runtime_session_payload, upsert_runtime_session
from app.utils.enums import TestType

RULE_ERROR_ITEM = "error"


def get_business_units(db: Session, current_user: User) -> list[str]:
    items = db.query(distinct(RtdConfig.business_unit)).order_by(RtdConfig.business_unit.asc()).all()
    if items:
        return [value for (value,) in items]
    return [current_user.module_name]


def get_lines_by_business_unit(db: Session, business_unit: str, _: User) -> list[str]:
    items = db.query(RtdConfig.line_name).filter(RtdConfig.business_unit == business_unit).order_by(RtdConfig.line_name.asc()).all()
    if items:
        return [value for (value,) in items]
    return [f"{business_unit}_LINE_A", f"{business_unit}_LINE_B"]


def get_rules_by_line_name(db: Session, current_user: User, line_name: str) -> list[str]:
    catalog = _get_or_fetch_rtd_catalog(db, current_user, line_name)
    return catalog["rules"] or [RULE_ERROR_ITEM]


def get_rule_versions_by_line_name(db: Session, current_user: User, line_name: str, rule_name: str) -> list[str]:
    if rule_name == RULE_ERROR_ITEM:
        return [RULE_ERROR_ITEM]

    catalog = _get_or_fetch_rtd_catalog(db, current_user, line_name)
    versions = catalog["versions"].get(rule_name, [])
    return versions or ([RULE_ERROR_ITEM] if catalog["error"] else [])


def find_rule_file_name_in_session(
    db: Session,
    current_user: User,
    line_name: str,
    rule_name: str,
    version: str,
) -> str | None:
    catalog = _get_or_fetch_rtd_catalog(db, current_user, line_name)
    for item in catalog.get("files", []):
        if item.get("rule_name") == rule_name and item.get("version") == version:
            return item.get("file_name")
    return None


def compare_macros_by_rule_targets(
    db: Session,
    current_user: User,
    line_name: str,
    selected_rule_targets: list[dict[str, str]],
) -> dict:
    if not selected_rule_targets:
        return {
            "old_macros": [],
            "new_macros": [],
            "has_diff": False,
        }

    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise ValueError("RTD config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("RTD host config not found")

    old_macro_diff: set[str] = set()
    new_macro_diff: set[str] = set()

    for item in selected_rule_targets:
        rule_name = item.get("rule_name", "")
        old_version = item.get("old_version", "")
        new_version = item.get("new_version", "")
        if not rule_name or not old_version or not new_version:
            continue

        old_file_name = find_rule_file_name_in_session(db, current_user, line_name, rule_name, old_version)
        new_file_name = find_rule_file_name_in_session(db, current_user, line_name, rule_name, new_version)
        if not old_file_name or not new_file_name:
            continue

        old_macros = set(get_macro_list_by_rule_name(db, current_user, line_name, rule_name, old_version))
        new_macros = set(get_macro_list_by_rule_name(db, current_user, line_name, rule_name, new_version))
        old_macro_diff.update(sorted(old_macros - new_macros, key=str.lower))
        new_macro_diff.update(sorted(new_macros - old_macros, key=str.lower))

    old_items = sorted(old_macro_diff, key=str.lower)
    new_items = sorted(new_macro_diff, key=str.lower)
    return {
        "old_macros": old_items,
        "new_macros": new_items,
        "has_diff": bool(old_items or new_items),
    }


def get_macro_list_by_rule_name(
    db: Session,
    current_user: User,
    line_name: str,
    rule_name: str,
    version: str,
) -> list[str]:
    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise ValueError("RTD config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("RTD host config not found")

    file_name = find_rule_file_name_in_session(db, current_user, line_name, rule_name, version)
    if not file_name:
        raise ValueError("Rule file not found in session cache")

    content = _read_remote_file(host, config.home_dir_path, file_name)
    return _extract_macro_lines(content)


def get_macros_by_rule_name(rule_name: str) -> list[str]:
    prefix = rule_name.upper().replace("-", "_")
    return [f"{prefix}_MACRO_01", f"{prefix}_MACRO_02"]


def get_rule_versions(_: str) -> list[str]:
    return ["1.0.0", "1.1.0", "2.0.0"]


def get_target_lines_by_business_unit(db: Session, business_unit: str, current_user: User) -> list[str]:
    lines = get_lines_by_business_unit(db, business_unit, current_user)
    return [f"{line}_TARGET" for line in lines]


def get_ezdfs_modules(db: Session, current_user: User) -> list[str]:
    items = db.query(EzdfsConfig.module_name).order_by(EzdfsConfig.module_name.asc()).all()
    if items:
        return [value for (value,) in items]
    return [f"{current_user.module_name}_EZDFS_01", f"{current_user.module_name}_EZDFS_02"]


def get_ezdfs_rules(module_name: str) -> list[str]:
    prefix = module_name.upper().replace("-", "_")
    return [f"{prefix}_RULE_01", f"{prefix}_RULE_02"]


def _get_or_fetch_rtd_catalog(db: Session, current_user: User, line_name: str) -> dict:
    session_payload = get_runtime_session_payload(db, current_user.user_id, TestType.RTD)
    cached = session_payload.get("catalog_cache", {})

    if cached.get("line_name") == line_name and cached.get("rules"):
        return {
            "line_name": cached.get("line_name"),
            "files": cached.get("files", []),
            "rules": cached.get("rules", []),
            "versions": cached.get("versions", {}),
            "error": cached.get("error"),
        }

    try:
        catalog = _fetch_rtd_catalog_over_ssh(db, line_name)
    except Exception as exc:  # noqa: BLE001
        catalog = {
            "line_name": line_name,
            "files": [],
            "rules": [RULE_ERROR_ITEM],
            "versions": {},
            "error": str(exc),
        }

    session_payload["catalog_cache"] = catalog
    upsert_runtime_session(db, current_user.user_id, TestType.RTD, session_payload)
    return catalog


def _fetch_rtd_catalog_over_ssh(db: Session, line_name: str) -> dict:
    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise ValueError("RTD config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("RTD host config not found")

    remote_files = _list_remote_files(host, config.home_dir_path)
    catalog_files = _parse_rule_versions(remote_files)
    versions_by_rule = _group_versions_by_rule(catalog_files)
    rules = sorted(versions_by_rule.keys(), key=str.lower)

    return {
        "line_name": line_name,
        "files": catalog_files,
        "rules": rules,
        "versions": {rule_name: versions_by_rule[rule_name] for rule_name in rules},
        "error": None,
    }


def _list_remote_files(host: HostConfig, home_dir_path: str) -> list[str]:
    try:
        import paramiko
    except ModuleNotFoundError as exc:
        raise RuntimeError("paramiko is not installed") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    command = f"bash -lc 'cd {shlex.quote(home_dir_path)} && find . -maxdepth 1 -type f -printf \"%f\\n\"'"

    try:
        client.connect(
            hostname=host.ip,
            username=host.login_user,
            password=host.login_password,
            timeout=5,
            auth_timeout=5,
            banner_timeout=5,
        )
        _, stdout, stderr = client.exec_command(command, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore")
        error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SSH connection failed: {exc}") from exc
    finally:
        client.close()

    if exit_status != 0:
        raise RuntimeError(error_output or "Failed to list remote files")

    return [line.strip() for line in output.splitlines() if line.strip()]


def _read_remote_file(host: HostConfig, home_dir_path: str, file_name: str) -> str:
    try:
        import paramiko
    except ModuleNotFoundError as exc:
        raise RuntimeError("paramiko is not installed") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    command = f"bash -lc 'cd {shlex.quote(home_dir_path)} && cat {shlex.quote(file_name)}'"

    try:
        client.connect(
            hostname=host.ip,
            username=host.login_user,
            password=host.login_password,
            timeout=5,
            auth_timeout=5,
            banner_timeout=5,
        )
        _, stdout, stderr = client.exec_command(command, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore")
        error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SSH file read failed: {exc}") from exc
    finally:
        client.close()

    if exit_status != 0:
        raise RuntimeError(error_output or f"Failed to read remote file: {file_name}")

    return output


def _parse_rule_versions(file_names: list[str]) -> list[dict[str, str]]:
    catalog_files: list[dict[str, str]] = []

    for file_name in file_names:
        if "_PC" not in file_name:
            continue

        rule_name, version_name = file_name.split("_PC", 1)
        rule_name = rule_name.strip("._- ")
        version_name = version_name.strip("._- ").replace(".rule", "").strip("._- ")

        if not rule_name or not version_name:
            continue

        catalog_files.append(
            {
                "file_name": file_name,
                "rule_name": rule_name,
                "version": version_name,
            }
        )

    return sorted(catalog_files, key=lambda item: (item["rule_name"].lower(), item["version"].lower()))


def _group_versions_by_rule(catalog_files: list[dict[str, str]]) -> dict[str, list[str]]:
    versions_by_rule: dict[str, set[str]] = defaultdict(set)
    for item in catalog_files:
        versions_by_rule[item["rule_name"]].add(item["version"])

    return {
        rule_name: sorted(version_names, key=str.lower)
        for rule_name, version_names in versions_by_rule.items()
    }


def _extract_macro_lines(content: str) -> list[str]:
    items: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("//") or line.startswith("#") or line.startswith(";"):
            continue

        normalized = re.split(r"\s*(?://|#|;)\s*", line, maxsplit=1)[0].strip()
        if not normalized:
            continue

        items.append(normalized)

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
