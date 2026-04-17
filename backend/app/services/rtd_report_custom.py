from __future__ import annotations

"""
RTD report custom flow

1. file_service.generate_aggregate_rtd_summary_file()가 완료된 RTD test task들을 모은다.
2. build_rtd_test_report_file()
   task 목록을 받아 Excel 결과서를 생성한다.
3. _build_rtd_report_rows()
   각 task를 `line x rule` row 후보로 펼친다.
4. _extract_rtd_detail_by_rule()
   raw result 파일에서 rule별 테스트 결과를 다시 분리한다.
5. _collect_major_change_items()
   task payload와 현재 세션에서 rule별 주요 변경항목을 모아 row에 채운다.
"""

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.models.entities import TestTask
from app.utils.naming import normalize_target_line_name


def build_rtd_test_report_file(
    tasks: list[TestTask],
    output_path: Path,
    fallback_major_change_items: dict[str, str] | None = None,
    selected_rule_names: list[str] | None = None,
) -> Path:
    """
    Build the aggregate RTD Excel report from completed RTD test tasks.

    Input:
    - tasks: Completed RTD TEST/RETEST tasks, ordered newest-first by caller.
    - output_path: Final `.xlsx` file path to create.
    - fallback_major_change_items: Optional rule -> text map, typically loaded
      from the current RTD runtime session when a task payload does not carry
      the latest major change input.

    Returns:
    - Path: Saved Excel file path.

    Behavior:
    - writes one row per `line x rule_name`
    - de-duplicates rows by `(line_name, rule_name)` using the first task seen
    - merges major change text from task payloads and fallback session values
    - if `selected_rule_names` is provided, only those rules are emitted
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "rtd_test_report"

    sheet.append(_rtd_report_headers())
    merged_major_change_items = _collect_major_change_items(tasks, fallback_major_change_items or {})
    selected_rule_set = {
        str(rule_name or "").strip()
        for rule_name in (selected_rule_names or [])
        if str(rule_name or "").strip()
    }
    seen_keys: set[tuple[str, str]] = set()
    row_items: list[dict[str, str | list[str]]] = []
    for task in tasks:
        requested_payload = json.loads(task.requested_payload_json or "{}")
        print(f"target : {task.target_name}")
        payload = (
            requested_payload.get("payload")
            if isinstance(requested_payload.get("payload"), dict)
            else requested_payload
        )
        for row_item in _build_rtd_report_rows(task, requested_payload, payload, merged_major_change_items):
            if selected_rule_set and str(row_item["rule_name"]) not in selected_rule_set:
                continue
            row_key = (row_item["line_name"], row_item["rule_name"])
            if row_key in seen_keys:
                continue
            seen_keys.add(row_key)
            row_items.append(row_item)

    for row_item in sorted(
        row_items,
        key=lambda item: (
            str(item["line_name"]).lower(),
            str(item["rule_name"]).lower(),
        ),
    ):
        sheet.append(row_item["row"])

    _style_rtd_report_sheet(sheet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def _rtd_report_headers() -> list[str]:
    """Return the fixed RTD aggregate report header row."""
    return [
        "Line",
        "Rule Name",
        "old version",
        "new version",
        "주요 변경항목",
        "Test command",
        "테스트 실행결과(text)",
    ]


def _build_rtd_report_rows(
    task: TestTask,
    requested_payload: dict,
    payload: dict,
    merged_major_change_items: dict[str, str],
) -> list[dict[str, str | list[str]]]:
    """
    Expand one RTD task into report row candidates.

    Input:
    - task: Completed RTD TEST/RETEST task.
    - requested_payload: Full JSON payload stored on the task record.
    - payload: Nested RTD selection payload when present.
    - merged_major_change_items: Rule -> text lookup already merged across
      tasks and current session state.

    Returns:
    - list[dict]: Row descriptors with:
      - line_name: normalized RTD line name
      - rule_name: logical rule name
      - row: actual Excel row values

    Behavior:
    - prefers `selected_rule_targets` because one line task may contain many rules
    - pulls per-rule test detail from structured raw output
    - fills major change text from task payload first, then merged fallback map
    """
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
    line_name = normalize_target_line_name(task.target_name)
    detail_by_rule = _extract_rtd_detail_by_rule(task.raw_result_path)

    rows: list[dict[str, str | list[str]]] = []
    for item in selected_rule_targets:
        rule_name = str(item.get("rule_name", "")).strip()
        if not rule_name:
            continue
        detail_text = detail_by_rule.get(rule_name) or task.message or ""

        major_change_text = str(
            major_change_items.get(rule_name, "") or merged_major_change_items.get(rule_name, "")
        ).strip()
        rows.append(
            {
                "line_name": line_name,
                "rule_name": rule_name,
                "row": [
                line_name,
                rule_name,
                str(item.get("old_version", "")).strip(),
                str(item.get("new_version", "")).strip(),
                major_change_text,
                f"./atm_testscript {rule_name} {line_name}",
                detail_text,
                ],
            }
        )

    if rows:
        return rows

    fallback_rule_name = str(requested_payload.get("rule_name", "")).strip()
    if fallback_rule_name:
        detail_text = detail_by_rule.get(fallback_rule_name) or task.message or ""
        major_change_text = str(
            major_change_items.get(fallback_rule_name, "") or merged_major_change_items.get(fallback_rule_name, "")
        ).strip()
        return [
            {
                "line_name": line_name,
                "rule_name": fallback_rule_name,
                "row": [
                    line_name,
                    fallback_rule_name,
                    "",
                    "",
                    major_change_text,
                    f"./atm_testscript {fallback_rule_name} {line_name}",
                    detail_text,
                ],
            }
        ]

    return []


def _extract_rtd_detail_by_rule(raw_result_path: str | None) -> dict[str, str]:
    """
    Read saved RTD rule raw txt files and return `rule_name -> detail_text`.

    Returns:
    - dict[str, str]: Per-rule test detail strings.

    Behavior:
    - expects the RTD raw task directory to contain `index.json`
    - reads each saved `line-rule.txt` file directly
    - does not support legacy single-file raw parsing
    """
    if not raw_result_path:
        return {}

    path = Path(raw_result_path)
    if not path.exists():
        return {}

    return _read_rtd_indexed_rule_details(path)


def _read_rtd_indexed_rule_details(meta_path: Path) -> dict[str, str]:
    """Read `index.json` and the saved per-rule raw txt files for one RTD task."""
    index_path = meta_path.parent / "index.json"
    if not index_path.exists():
        return {}

    try:
        index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        return {}

    rule_files = index_payload.get("rule_files", {})
    result: dict[str, str] = {}
    for rule_name, file_name in rule_files.items():
        normalized_rule_name = str(rule_name or "").strip()
        normalized_file_name = str(file_name or "").strip()
        if not normalized_rule_name or not normalized_file_name:
            continue
        file_path = meta_path.parent / normalized_file_name
        if not file_path.exists():
            continue
        result[normalized_rule_name] = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    return result


def _collect_major_change_items(
    tasks: list[TestTask],
    fallback_major_change_items: dict[str, str],
) -> dict[str, str]:
    """
    Merge rule-level major change text from stored tasks and current session.

    Current session values win so the report reflects what the user has typed
    at report-generation time.
    """
    merged: dict[str, str] = {}
    for task in tasks:
        try:
            requested_payload = json.loads(task.requested_payload_json or "{}")
        except (json.JSONDecodeError, ValueError):
            continue
        payload = (
            requested_payload.get("payload")
            if isinstance(requested_payload.get("payload"), dict)
            else requested_payload
        )
        major_change_items = (
            payload.get("major_change_items")
            if isinstance(payload.get("major_change_items"), dict)
            else {}
        )
        for rule_name, text in major_change_items.items():
            normalized_rule = str(rule_name or "").strip()
            normalized_text = str(text or "").strip()
            if normalized_rule and normalized_text:
                merged[normalized_rule] = normalized_text
    for rule_name, text in (fallback_major_change_items or {}).items():
        normalized_rule = str(rule_name or "").strip()
        normalized_text = str(text or "").strip()
        if normalized_rule and normalized_text:
            merged[normalized_rule] = normalized_text
    return merged


def _style_rtd_report_sheet(sheet) -> None:
    """Apply basic header/body styling and column widths to the RTD workbook."""
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
