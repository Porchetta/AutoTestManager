from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RtdSessionPayload(BaseModel):
    current_step: int = 1
    selected_business_unit: str | None = None
    selected_line_name: str | None = None
    selected_rules: list[str] = Field(default_factory=list)
    selected_rule_targets: list[dict[str, Any]] = Field(default_factory=list)
    selected_macros: dict[str, Any] = Field(default_factory=dict)
    selected_versions: dict[str, str] = Field(default_factory=dict)
    major_change_items: dict[str, str] = Field(default_factory=dict)
    target_lines: list[str] = Field(default_factory=list)
    monitor_rule_selection: dict[str, str] = Field(default_factory=dict)
    active_task_ids: list[str] = Field(default_factory=list)
    copy_visibility_map: dict[str, bool] = Field(default_factory=dict)
    sync_visibility_map: dict[str, bool] = Field(default_factory=dict)
    compile_visibility_map: dict[str, bool] = Field(default_factory=dict)
    test_visibility_map: dict[str, bool] = Field(default_factory=dict)
    svn_upload: dict[str, Any] = Field(default_factory=dict)


class EzdfsSessionPayload(BaseModel):
    current_step: int = 1
    selected_module: str | None = None
    selected_rule: str | None = None
    selected_rule_version: str | None = None
    selected_rule_old_version: str | None = None
    selected_rule_file_name: str | None = None
    selected_rules: list[dict[str, str]] = Field(default_factory=list)
    sub_rules_searched: bool = False
    sub_rules: list[str] = Field(default_factory=list)
    sub_rule_map: dict[str, list[str]] = Field(default_factory=dict)
    selected_sub_rules: list[str] = Field(default_factory=list)
    major_change_items: dict[str, str] = Field(default_factory=dict)
    active_task_id: str | None = None
    latest_status: str | None = None
    catalog_cache: dict[str, Any] = Field(default_factory=dict)
    svn_upload: dict[str, Any] = Field(default_factory=dict)


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


class EzdfsAggregateSummaryRequest(BaseModel):
    module_name: str
    task_ids: list[str] = Field(default_factory=list)


class SvnUploadRequest(BaseModel):
    ad_user: str
    ad_password: str
