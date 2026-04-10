from __future__ import annotations

from collections import defaultdict

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, HostConfig, RtdConfig, User
from app.services.rtd_catalog_custom import (
    extract_macro_list_from_rule_text,
    fetch_rule_source_file_names,
    parse_rule_catalog_entries,
    read_rule_source_text,
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
    return extract_macro_list_from_rule_text(content, rule_name)


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


def _group_versions_by_rule(catalog_files: list[dict[str, str]]) -> dict[str, list[str]]:
    versions_by_rule: dict[str, set[str]] = defaultdict(set)
    for item in catalog_files:
        versions_by_rule[item["rule_name"]].add(item["version"])

    return {
        rule_name: sorted(version_names, key=str.lower)
        for rule_name, version_names in versions_by_rule.items()
    }
