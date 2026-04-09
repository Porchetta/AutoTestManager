from __future__ import annotations

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, RtdConfig, User


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


def get_rules_by_line_name(line_name: str) -> list[str]:
    prefix = line_name.upper().replace("-", "_")
    return [f"{prefix}_RULE_01", f"{prefix}_RULE_02", f"{prefix}_RULE_03"]


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

