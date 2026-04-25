from __future__ import annotations

"""
사용자 룰 즐겨찾기.

서버(라인/모듈)별로 룰 셋이 달라서, 즐겨찾기한 룰이 현재 scope에 존재하지
않을 수 있다. DB는 favorite을 항상 보존하고, 노출 시점에만 현재 catalog와
교집합을 취해 표시한다 (호출 측 책임).
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import RuleFavorite
from app.utils.enums import TestType


def list_favorite_rule_names(
    db: Session,
    user_id: str,
    test_type: TestType,
    scope_key: str,
) -> set[str]:
    rows = (
        db.query(RuleFavorite.rule_name)
        .filter(
            RuleFavorite.user_id == user_id,
            RuleFavorite.test_type == test_type.value,
            RuleFavorite.scope_key == scope_key,
        )
        .all()
    )
    return {row[0] for row in rows}


def set_favorite(
    db: Session,
    user_id: str,
    test_type: TestType,
    scope_key: str,
    rule_name: str,
    favorite: bool,
) -> bool:
    if not (user_id and scope_key and rule_name):
        return False

    existing = (
        db.query(RuleFavorite)
        .filter(
            RuleFavorite.user_id == user_id,
            RuleFavorite.test_type == test_type.value,
            RuleFavorite.scope_key == scope_key,
            RuleFavorite.rule_name == rule_name,
        )
        .first()
    )

    if favorite:
        if existing is not None:
            return True
        db.add(
            RuleFavorite(
                user_id=user_id,
                test_type=test_type.value,
                scope_key=scope_key,
                rule_name=rule_name,
            )
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        return True

    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return False


def reorder_favorites_first(items: list[str], favorite_names: set[str]) -> list[str]:
    """기존 정렬을 보존하면서 favorite을 앞으로 끌어올린다."""
    if not favorite_names:
        return items
    favored = [item for item in items if item in favorite_names]
    rest = [item for item in items if item not in favorite_names]
    return favored + rest
