from __future__ import annotations

from collections import defaultdict

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, HostConfig, RtdConfig, User
from app.services.ezdfs_catalog_custom import (
    fetch_backup_rule_source_file_names as fetch_ezdfs_backup_rule_source_file_names,
    fetch_rule_source_file_names as fetch_ezdfs_rule_source_file_names,
    find_latest_backup_version,
    parse_rule_catalog_entries as parse_ezdfs_rule_catalog_entries,
    read_rule_source_text as read_ezdfs_rule_source_text,
    resolve_recursive_sub_rule_list,
)
from app.services.rtd_catalog_custom import (
    fetch_rule_source_file_names,
    parse_rule_catalog_entries,
    read_rule_source_text,
    resolve_recursive_macro_list,
)
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

    content = read_rule_source_text(host, config.home_dir_path, file_name)
    return resolve_recursive_macro_list(host, config.home_dir_path, content, rule_name)


def get_target_lines_by_business_unit(db: Session, business_unit: str, current_user: User) -> list[str]:
    lines = get_lines_by_business_unit(db, business_unit, current_user)
    return [f"{line}_TARGET" for line in lines]


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

    content = read_ezdfs_rule_source_text(host, config.home_dir_path, resolved_file_name)
    selected_entry = next(
        (item for item in catalog.get("files", []) if item.get("file_name") == resolved_file_name),
        None,
    )
    return resolve_recursive_sub_rule_list(
        host,
        config.home_dir_path,
        content,
        catalog.get("files", []),
        preferred_version=str(selected_entry.get("version", "")) if selected_entry else "",
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
    except Exception as exc:  # noqa: BLE001
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

    remote_files = fetch_rule_source_file_names(host, config.home_dir_path)
    catalog_files = parse_rule_catalog_entries(remote_files)
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

    remote_files = fetch_ezdfs_rule_source_file_names(host, config.home_dir_path)
    catalog_files = parse_ezdfs_rule_catalog_entries(remote_files)
    try:
        backup_remote_files = fetch_ezdfs_backup_rule_source_file_names(host, config.home_dir_path)
        backup_catalog_files = parse_ezdfs_rule_catalog_entries(backup_remote_files)
    except Exception:  # noqa: BLE001
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

    if all(isinstance(item, str) for item in items):
        return parse_ezdfs_rule_catalog_entries(items)

    return []


def _is_valid_ezdfs_catalog_entry(item: object) -> bool:
    if not isinstance(item, dict):
        return False

    file_name = str(item.get("file_name", "")).strip()
    rule_name = str(item.get("rule_name", "")).strip()
    version = str(item.get("version", "")).strip()
    return bool(file_name and rule_name and version)
