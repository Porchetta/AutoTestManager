from __future__ import annotations

"""
ezDFS report custom flow

1. file_service가 완료된 ezDFS test task 하나 또는 여러 개를 넘긴다.
2. build_ezdfs_test_report_file()
   task 목록을 받아 Excel 결과서를 생성한다.
3. _build_ezdfs_report_row()
   각 task를 결과서 row 한 줄로 변환한다.
4. _read_ezdfs_meta_text() / _read_ezdfs_raw_text()
   `_meta.txt`에서 실행 command를 읽고, rule 이름으로 저장된 raw txt에서 상세 결과를 읽는다.
"""

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.models.entities import TestTask


def build_ezdfs_test_report_file(tasks: TestTask | list[TestTask], output_path: Path) -> Path:
    """
    Build the ezDFS Excel summary report from one or more completed tasks.

    Input:
    - tasks: Single completed task or a list of completed ezDFS tasks.
    - output_path: Final `.xlsx` file path to create.

    Returns:
    - Path: Saved Excel file path.

    Behavior:
    - normalizes the input to a task list
    - writes one row per ezDFS task
    - reads command from `_meta.txt`
    - reads detail text from the rule-named raw txt file

    Customize this function if the offline environment needs a different
    workbook layout or richer parsing of raw outputs.
    """
    normalized_tasks = tasks if isinstance(tasks, list) else [tasks]

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "ezdfs_test_report"

    sheet.append(_ezdfs_report_headers())
    for task in normalized_tasks:
        requested_payload = json.loads(task.requested_payload_json or "{}")
        payload = requested_payload.get("payload") if isinstance(requested_payload.get("payload"), dict) else requested_payload
        sheet.append(_build_ezdfs_report_row(task, requested_payload, payload))

    _style_ezdfs_report_sheet(sheet)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path


def _ezdfs_report_headers() -> list[str]:
    """Return the fixed ezDFS report header row."""
    return [
        "모듈명",
        "rule name",
        "old version",
        "new version",
        "sub rule list",
        "주요 변경 항목",
        "test command",
        "테스트 실행결과 상세",
    ]


def _build_ezdfs_report_row(task: TestTask, requested_payload: dict, payload: dict) -> list[str]:
    """
    Convert one ezDFS task into one Excel row.

    Input:
    - task: Completed ezDFS TEST/RETEST task.
    - requested_payload: Full JSON payload stored on the task.
    - payload: Nested ezDFS screen/session payload when present.

    Returns:
    - list[str]: Final row values for the ezDFS report.

    Behavior:
    - resolves rule/module/version values from payload
    - filters sub-rule list to the currently selected sub-rules
    - reads command from `_meta.txt`
    - reads plain test result text from the rule-named raw txt file
    """
    rule_name = payload.get("selected_rule") or requested_payload.get("rule_name", task.target_name)
    major_change_items = payload.get("major_change_items") if isinstance(payload.get("major_change_items"), dict) else {}
    sub_rule_map = payload.get("sub_rule_map") if isinstance(payload.get("sub_rule_map"), dict) else {}
    selected_sub_rules = payload.get("selected_sub_rules") if isinstance(payload.get("selected_sub_rules"), list) else []
    major_change_text = str(major_change_items.get(rule_name, "")).strip()
    rule_sub_rules = [
        str(item).strip()
        for item in sub_rule_map.get(rule_name, [])
        if str(item).strip()
    ]
    if selected_sub_rules:
        selected_set = {str(item).strip() for item in selected_sub_rules if str(item).strip()}
        rule_sub_rules = [item for item in rule_sub_rules if item in selected_set]

    meta_text = _read_ezdfs_meta_text(task.raw_result_path)
    raw_text = _read_ezdfs_raw_text(task.raw_result_path)
    test_command = _extract_ezdfs_command(meta_text)
    detail_text = raw_text.strip()

    return [
        payload.get("selected_module") or requested_payload.get("module_name", ""),
        rule_name,
        payload.get("selected_rule_old_version", ""),
        payload.get("selected_rule_version", ""),
        "\n".join(rule_sub_rules),
        major_change_text,
        test_command,
        detail_text or task.message or "",
    ]


def _read_ezdfs_meta_text(raw_result_path: str | None) -> str:
    """Read the saved ezDFS `_meta.txt` file text, if it exists."""
    if not raw_result_path:
        return ""

    path = Path(raw_result_path)
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="ignore")


def _read_ezdfs_raw_text(raw_result_path: str | None) -> str:
    """Read the saved ezDFS rule-named raw txt content, if it exists."""
    if not raw_result_path:
        return ""

    meta_path = Path(raw_result_path)
    meta_text = _read_ezdfs_meta_text(raw_result_path)
    rule_name = _extract_ezdfs_rule_name(meta_text)
    raw_file_name = f"{_sanitize_ezdfs_path_token(rule_name) if rule_name else 'raw'}.txt"
    raw_path = meta_path.parent / raw_file_name
    if not raw_path.exists():
        return ""

    return raw_path.read_text(encoding="utf-8", errors="ignore")


def _extract_ezdfs_command(meta_text: str) -> str:
    """Extract the executed ezDFS command from `_meta.txt`."""
    if not meta_text:
        return ""

    for line in meta_text.splitlines():
        if line.startswith("command="):
            return line.split("=", 1)[1].strip()
    return ""


def _extract_ezdfs_rule_name(meta_text: str) -> str:
    """Extract the ezDFS rule name from `_meta.txt` target metadata."""
    if not meta_text:
        return ""

    for line in meta_text.splitlines():
        if line.startswith("target_name="):
            return line.split("=", 1)[1].strip()
    return ""


def _sanitize_ezdfs_path_token(value: str) -> str:
    """Sanitize one ezDFS rule name into a safe txt filename token."""
    normalized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "").strip())
    normalized = normalized.strip("._")
    return normalized or "raw"


def _style_ezdfs_report_sheet(sheet) -> None:
    """Apply basic styling and column widths to the ezDFS workbook."""
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
        "E": 28,
        "F": 32,
        "G": 32,
        "H": 48,
    }
    for column_name, width in column_widths.items():
        sheet.column_dimensions[column_name].width = width
