from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.models.entities import TestTask


def build_rtd_test_report_file(tasks: list[TestTask], output_path: Path) -> Path:
    """
    Default implementation for aggregated RTD test report generation.

    One row is produced per `line x rule_name` combination.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "rtd_test_report"

    sheet.append(_rtd_report_headers())
    for task in tasks:
      requested_payload = json.loads(task.requested_payload_json or "{}")
      payload = (
          requested_payload.get("payload")
          if isinstance(requested_payload.get("payload"), dict)
          else requested_payload
      )
      for row in _build_rtd_report_rows(task, requested_payload, payload):
          sheet.append(row)

    _style_rtd_report_sheet(sheet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def _rtd_report_headers() -> list[str]:
    return [
        "Line",
        "Rule Name",
        "old version",
        "new version",
        "주요 변경항목",
        "Test command",
        "테스트 실행결과(text)",
    ]


def _build_rtd_report_rows(task: TestTask, requested_payload: dict, payload: dict) -> list[list[str]]:
    selected_rule_targets = (
        payload.get("selected_rule_targets")
        if isinstance(payload.get("selected_rule_targets"), list)
        else []
    )
    major_change_items = (
        payload.get("major_change_items")
        if isinstance(payload.get("major_change_items"), dict)
        else {}
    )
    line_name = _normalize_target_line_name(task.target_name)
    detail_text = _extract_rtd_detail_text(task.raw_result_path) or task.message or ""

    rows: list[list[str]] = []
    for item in selected_rule_targets:
        rule_name = str(item.get("rule_name", "")).strip()
        if not rule_name:
            continue

        rows.append(
            [
                line_name,
                rule_name,
                str(item.get("old_version", "")).strip(),
                str(item.get("new_version", "")).strip(),
                str(major_change_items.get(rule_name, "")).strip(),
                f"./atm_testscript {rule_name} {line_name}",
                detail_text,
            ]
        )

    if rows:
        return rows

    fallback_rule_name = str(requested_payload.get("rule_name", "")).strip()
    if fallback_rule_name:
        return [
            [
                line_name,
                fallback_rule_name,
                "",
                "",
                str(major_change_items.get(fallback_rule_name, "")).strip(),
                f"./atm_testscript {fallback_rule_name} {line_name}",
                detail_text,
            ]
        ]

    return []


def _extract_rtd_detail_text(raw_result_path: str | None) -> str:
    if not raw_result_path:
        return ""

    path = Path(raw_result_path)
    if not path.exists():
        return ""

    raw_text = path.read_text(encoding="utf-8", errors="ignore")
    detail_lines: list[str] = []
    metadata_prefixes = (
        "task_id=",
        "test_type=",
        "action_type=",
        "target_name=",
        "status=",
        "requested_at=",
        "command=",
    )
    for line in raw_text.splitlines():
        if line.startswith(metadata_prefixes):
            continue
        detail_lines.append(line)

    return "\n".join(detail_lines).strip()


def _normalize_target_line_name(line_name: str) -> str:
    normalized = str(line_name or "").strip()
    if normalized.endswith("_TARGET"):
        return normalized[: -len("_TARGET")]
    return normalized


def _style_rtd_report_sheet(sheet) -> None:
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    body_alignment = Alignment(vertical="top", wrap_text=True)

    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.alignment = header_alignment

    for row in sheet.iter_rows(min_row=2):
        row_has_multiline = False
        for cell in row:
            cell.alignment = body_alignment
            if isinstance(cell.value, str) and "\n" in cell.value:
                row_has_multiline = True
        if row_has_multiline:
            sheet.row_dimensions[row[0].row].height = 54

    column_widths = {
        "A": 16,
        "B": 28,
        "C": 16,
        "D": 16,
        "E": 32,
        "F": 30,
        "G": 48,
    }
    for column_name, width in column_widths.items():
        sheet.column_dimensions[column_name].width = width
