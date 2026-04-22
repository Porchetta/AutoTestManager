from __future__ import annotations

"""Shared naming/sanitization helpers used across services and API routes."""

import re

from app.utils.constants import TARGET_SUFFIX


def normalize_target_line_name(line_name: str) -> str:
    """Strip the ``_TARGET`` suffix so names map back to RTD config line names."""
    normalized = str(line_name or "").strip()
    if normalized.endswith(TARGET_SUFFIX):
        return normalized[: -len(TARGET_SUFFIX)]
    return normalized


def sanitize_path_token(value: str) -> str:
    """Sanitize a value for safe use in filesystem paths."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "").strip())
    return sanitized.strip("._-") or "report"
