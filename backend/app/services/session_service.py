from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.entities import RuntimeSession
from app.utils.enums import TestType


def get_runtime_session_payload(db: Session, user_id: str, session_type: TestType) -> dict:
    session = (
        db.query(RuntimeSession)
        .filter(RuntimeSession.user_id == user_id, RuntimeSession.session_type == session_type.value)
        .first()
    )
    if session is None:
        return {}
    return json.loads(session.payload_json)


def upsert_runtime_session(db: Session, user_id: str, session_type: TestType, payload: dict) -> dict:
    session = (
        db.query(RuntimeSession)
        .filter(RuntimeSession.user_id == user_id, RuntimeSession.session_type == session_type.value)
        .first()
    )
    payload_json = json.dumps(payload)
    if session is None:
        session = RuntimeSession(user_id=user_id, session_type=session_type.value, payload_json=payload_json)
    else:
        session.payload_json = payload_json

    db.add(session)
    db.commit()
    db.refresh(session)
    return json.loads(session.payload_json)


def clear_runtime_session(db: Session, user_id: str, session_type: TestType) -> None:
    session = (
        db.query(RuntimeSession)
        .filter(RuntimeSession.user_id == user_id, RuntimeSession.session_type == session_type.value)
        .first()
    )
    if session is not None:
        db.delete(session)
        db.commit()

