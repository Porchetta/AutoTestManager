from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RtdMacroReviewPayload(BaseModel):
    old_macros: list[str] = Field(default_factory=list)
    new_macros: list[str] = Field(default_factory=list)
    has_diff: bool = False
    error: str = ""


class RtdSessionPayload(BaseModel):
    current_step: int = 1
    selected_business_unit: str | None = None
    selected_line_name: str | None = None
    selected_rules: list[str] = Field(default_factory=list)
    selected_rule_targets: list[dict[str, str]] = Field(default_factory=list)
    selected_macros: list[str] = Field(default_factory=list)
    selected_versions: dict[str, str] = Field(default_factory=dict)
    macro_review: RtdMacroReviewPayload = Field(default_factory=RtdMacroReviewPayload)
    target_lines: list[str] = Field(default_factory=list)
    active_task_ids: list[str] = Field(default_factory=list)


class EzdfsSessionPayload(BaseModel):
    selected_module: str | None = None
    selected_rule: str | None = None
    active_task_id: str | None = None
    latest_status: str | None = None


class RtdActionRequest(BaseModel):
    target_lines: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class RtdMacroCompareRequest(BaseModel):
    line_name: str
    selected_rule_targets: list[dict[str, str]] = Field(default_factory=list)


class EzdfsActionRequest(BaseModel):
    module_name: str
    rule_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
