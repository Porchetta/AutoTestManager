from __future__ import annotations

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from app.models.entities import TestTask


def build_ezdfs_test_report_file(tasks: TestTask | list[TestTask], output_path: Path) -> Path:
    """
    Default implementation for ezDFS summary report generation.

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

    raw_text = _read_raw_text(task.raw_result_path)
    test_command, detail_text = _extract_command_and_detail(raw_text)

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


def _read_raw_text(raw_result_path: str | None) -> str:
    if not raw_result_path:
        return ""

    path = Path(raw_result_path)
    if not path.exists():
        return ""

    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_command_and_detail(raw_text: str) -> tuple[str, str]:
    if not raw_text:
        return "", ""

    command = ""
    detail_lines: list[str] = []
    metadata_prefixes = (
        "task_id=",
        "test_type=",
        "action_type=",
        "target_name=",
        "status=",
        "requested_at=",
    )

    for line in raw_text.splitlines():
        if line.startswith("command="):
            command = line.split("=", 1)[1].strip()
            continue
        if line.startswith(metadata_prefixes):
            continue
        detail_lines.append(line)

    return command, "\n".join(detail_lines).strip()


def _style_ezdfs_report_sheet(sheet) -> None:
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
