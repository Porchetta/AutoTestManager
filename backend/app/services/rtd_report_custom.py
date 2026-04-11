from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from app.models.entities import TestTask


def build_rtd_test_report_file(tasks: list[TestTask], output_path: Path) -> Path:
    """
    Default implementation for aggregated RTD test report generation.

    Customize this function if the offline environment needs a different
    workbook layout, extra sheets, or custom parsing of raw outputs.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "rtd_test_report"

    headers = [
        "target_line",
        "task_id",
        "action_type",
        "status",
        "requested_at",
        "started_at",
        "ended_at",
        "message",
        "raw_result_path",
    ]
    sheet.append(headers)

    for task in tasks:
        sheet.append(
            [
                task.target_name,
                task.task_id,
                task.action_type,
                task.status,
                task.requested_at.isoformat() if task.requested_at else "",
                task.started_at.isoformat() if task.started_at else "",
                task.ended_at.isoformat() if task.ended_at else "",
                task.message,
                task.raw_result_path or "",
            ]
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)
    return output_path
