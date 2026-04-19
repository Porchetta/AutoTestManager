from __future__ import annotations

from collections import defaultdict

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, HostConfig, RtdConfig, User
from app.services.ezdfs_catalog_custom import (
    find_latest_backup_version,
    get_backup_file_list as get_ezdfs_backup_file_list,
    get_rule_file_list as get_ezdfs_rule_file_list,
    get_subrule_file_list as get_ezdfs_subrule_file_list,
)
from app.services.rtd_catalog_custom import (
    get_macro_file_list,
    get_rule_file_list,
)
from app.services.session_service import get_runtime_session_payload, upsert_runtime_session
from app.utils.constants import RULE_ERROR_ITEM
from app.utils.enums import TestType


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
        return {"per_rule": [], "has_any": False}

    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise ValueError("RTD config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("RTD host config not found")

    per_rule: list[dict[str, object]] = []

    for item in selected_rule_targets:
        rule_name = str(item.get("rule_name") or "").strip()
        old_version = str(item.get("old_version") or "").strip()
        new_version = str(item.get("new_version") or "").strip()
        if not rule_name or not old_version or not new_version:
            continue

        old_file_name = find_rule_file_name_in_session(db, current_user, line_name, rule_name, old_version)
        new_file_name = find_rule_file_name_in_session(db, current_user, line_name, rule_name, new_version)
        if not old_file_name or not new_file_name:
            continue

        old_macros = get_macro_list_by_rule_name(db, current_user, line_name, rule_name, old_version)
        new_macros = get_macro_list_by_rule_name(db, current_user, line_name, rule_name, new_version)

        per_rule.append(
            {
                "rule_name": rule_name,
                "old_version": old_version,
                "new_version": new_version,
                "old_macros": old_macros,
                "new_macros": new_macros,
            }
        )

    has_any = any(entry["old_macros"] or entry["new_macros"] for entry in per_rule)
    return {"per_rule": per_rule, "has_any": has_any}


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

    return get_macro_file_list(host, config.login_user, config.home_dir_path, file_name)


def get_target_lines_by_business_unit(db: Session, business_unit: str, current_user: User) -> list[str]:
    return get_lines_by_business_unit(db, business_unit, current_user)


def get_ezdfs_modules(db: Session, current_user: User) -> list[str]:
    items = db.query(EzdfsConfig.module_name).order_by(EzdfsConfig.module_name.asc()).all()
    if items:
        return [value for (value,) in items]
    return [f"{current_user.module_name}_EZDFS_01", f"{current_user.module_name}_EZDFS_02"]


def get_ezdfs_rules(db: Session, current_user: User, module_name: str) -> list[dict[str, str]]:
    catalog = _get_or_fetch_ezdfs_catalog(db, current_user, module_name, force_refresh=True)
    return catalog["rules"] or [{"file_name": RULE_ERROR_ITEM, "rule_name": RULE_ERROR_ITEM, "version": "", "old_version": ""}]


def get_ezdfs_sub_rules(
    db: Session,
    current_user: User,
    module_name: str,
    rule_name: str,
    file_name: str | None = None,
) -> list[str]:
    if rule_name == RULE_ERROR_ITEM:
        return [RULE_ERROR_ITEM]

    catalog = _get_or_fetch_ezdfs_catalog(db, current_user, module_name)
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise ValueError("ezDFS config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("ezDFS host config not found")

    resolved_file_name = file_name or find_ezdfs_rule_file_name_in_session(db, current_user, module_name, rule_name)
    if not resolved_file_name:
        raise ValueError("ezDFS rule file not found in session cache")

    return get_ezdfs_subrule_file_list(
        host,
        config.login_user,
        config.home_dir_path,
        resolved_file_name,
        catalog_files=catalog.get("files", []),
    )


def find_ezdfs_rule_file_name_in_session(
    db: Session,
    current_user: User,
    module_name: str,
    rule_name: str,
) -> str | None:
    catalog = _get_or_fetch_ezdfs_catalog(db, current_user, module_name)
    for item in catalog.get("files", []):
        if item.get("rule_name") == rule_name:
            return item.get("file_name")
    return None


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
    except (ValueError, OSError) as exc:
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


def _get_or_fetch_ezdfs_catalog(
    db: Session,
    current_user: User,
    module_name: str,
    force_refresh: bool = False,
) -> dict:
    session_payload = get_runtime_session_payload(db, current_user.user_id, TestType.EZDFS)
    cached = session_payload.get("catalog_cache", {})

    if not force_refresh and cached.get("module_name") == module_name:
        normalized_catalog = _normalize_ezdfs_cached_catalog(module_name, cached)
        if normalized_catalog is not None:
            if normalized_catalog != cached:
                session_payload["catalog_cache"] = normalized_catalog
                upsert_runtime_session(db, current_user.user_id, TestType.EZDFS, session_payload)
            return normalized_catalog

    try:
        catalog = _fetch_ezdfs_catalog_over_ssh(db, module_name)
    except (ValueError, OSError) as exc:
        catalog = {
            "module_name": module_name,
            "files": [],
            "rules": [{"file_name": RULE_ERROR_ITEM, "rule_name": RULE_ERROR_ITEM, "version": "", "old_version": ""}],
            "error": str(exc),
        }

    session_payload["catalog_cache"] = catalog
    upsert_runtime_session(db, current_user.user_id, TestType.EZDFS, session_payload)
    return catalog


def _fetch_rtd_catalog_over_ssh(db: Session, line_name: str) -> dict:
    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise ValueError("RTD config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("RTD host config not found")

    catalog_files = get_rule_file_list(host, config.login_user, config.home_dir_path)
    versions_by_rule = _group_versions_by_rule(catalog_files)
    rules = sorted(versions_by_rule.keys(), key=str.lower)

    return {
        "line_name": line_name,
        "files": catalog_files,
        "rules": rules,
        "versions": {rule_name: versions_by_rule[rule_name] for rule_name in rules},
        "error": None,
    }


def _fetch_ezdfs_catalog_over_ssh(db: Session, module_name: str) -> dict:
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise ValueError("ezDFS config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("ezDFS host config not found")

    catalog_files = get_ezdfs_rule_file_list(host, config.login_user, config.home_dir_path)
    try:
        backup_catalog_files = get_ezdfs_backup_file_list(host, config.login_user, config.home_dir_path)
    except (OSError, RuntimeError):
        backup_catalog_files = []
    files_with_old_version = [
        {
            **item,
            "old_version": find_latest_backup_version(
                backup_catalog_files,
                item["rule_name"],
                excluded_version=item["version"],
            ),
        }
        for item in catalog_files
    ]
    rules = [
        {
            "file_name": item["file_name"],
            "rule_name": item["rule_name"],
            "version": item["version"],
            "old_version": item.get("old_version", ""),
        }
        for item in files_with_old_version
    ]

    return {
        "module_name": module_name,
        "home_dir_path": config.home_dir_path,
        "host_name": config.host_name,
        "files": files_with_old_version,
        "rules": rules,
        "error": None,
    }


def _group_versions_by_rule(catalog_files: list[dict[str, str]]) -> dict[str, list[str]]:
    versions_by_rule: dict[str, set[str]] = defaultdict(set)
    for item in catalog_files:
        versions_by_rule[item["rule_name"]].add(item["version"])

    return {
        rule_name: sorted(version_names, key=str.lower)
        for rule_name, version_names in versions_by_rule.items()
    }


def _normalize_ezdfs_cached_catalog(module_name: str, cached: dict) -> dict | None:
    files = cached.get("files", [])
    rules = cached.get("rules", [])
    error = cached.get("error")

    normalized_files = _normalize_ezdfs_catalog_entries(files)
    normalized_rules = _normalize_ezdfs_catalog_entries(rules)

    if normalized_rules:
        if not normalized_files:
            normalized_files = normalized_rules
        return {
            "module_name": module_name,
            "home_dir_path": cached.get("home_dir_path"),
            "host_name": cached.get("host_name"),
            "files": normalized_files,
            "rules": normalized_rules,
            "error": error,
        }

    if normalized_files:
        return {
            "module_name": module_name,
            "home_dir_path": cached.get("home_dir_path"),
            "host_name": cached.get("host_name"),
            "files": normalized_files,
            "rules": normalized_files,
            "error": error,
        }

    return None


def _normalize_ezdfs_catalog_entries(items: list) -> list[dict[str, str]]:
    if not isinstance(items, list) or not items:
        return []

    if all(_is_valid_ezdfs_catalog_entry(item) for item in items):
        return [
            {
                "file_name": str(item.get("file_name", "")).strip(),
                "rule_name": str(item.get("rule_name", "")).strip(),
                "version": str(item.get("version", "")).strip(),
                "old_version": str(item.get("old_version", "")).strip(),
            }
            for item in items
            if _is_valid_ezdfs_catalog_entry(item)
        ]

    return []


def _is_valid_ezdfs_catalog_entry(item: object) -> bool:
    if not isinstance(item, dict):
        return False

    file_name = str(item.get("file_name", "")).strip()
    rule_name = str(item.get("rule_name", "")).strip()
    version = str(item.get("version", "")).strip()
    return bool(file_name and rule_name and version)
