from __future__ import annotations

import posixpath
import shlex
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import HostConfig, RtdConfig, TestTask
from app.services.session_service import get_runtime_session_payload
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.enums import TestType


def execute_copy_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Default implementation for COPY.

    Current behavior:
    - source rule files: <dev_home_dir>/
    - source macro files: <dev_home_dir>/../Macro/
    - target rule files: <target_home_dir>/
    - target macro files: <target_home_dir>/../Macro/

    Customize this function if the offline environment needs different
    relative locations or file resolution rules.
    """
    session_payload = _extract_session_payload(payload)
    dev_line_name = session_payload.get("selected_line_name") or payload.get("selected_line_name") or ""
    if not dev_line_name:
        raise ValueError("selected_line_name is required for copy action")

    source_config, source_host = _get_rtd_line_context(db, dev_line_name)
    target_config, target_host = _get_rtd_line_context(db, task.target_name)

    rule_file_names = _collect_rule_file_names(db, task.user_id, source_config.line_name, session_payload)
    macro_file_names = _collect_macro_file_names(session_payload)

    if not rule_file_names:
        raise ValueError("No rule files resolved for copy action")

    copied_rule_count = 0
    copied_macro_count = 0

    if rule_file_names:
        copied_rule_count = _copy_files_between_hosts(
            source_host=source_host,
            source_dir=source_config.home_dir_path,
            target_host=target_host,
            target_dir=target_config.home_dir_path,
            file_names=rule_file_names,
        )

    if macro_file_names:
        copied_macro_count = _copy_files_between_hosts(
            source_host=source_host,
            source_dir=_macro_dir_from_home(source_config.home_dir_path),
            target_host=target_host,
            target_dir=_macro_dir_from_home(target_config.home_dir_path),
            file_names=macro_file_names,
        )

    return {
        "message": (
            f"Copy completed: dev={source_config.line_name}, target={target_config.line_name}, "
            f"rules={copied_rule_count}, macros={copied_macro_count}"
        ),
        "raw_output": "",
    }


def execute_compile_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Default implementation for COMPILE.

    Intended customization point:
    - input: line, rule
    - command example: atm_compiler {Rulename} {Linename}
    """
    session_payload = _extract_session_payload(payload)
    config, host = _get_rtd_line_context(db, task.target_name)
    rule_names = _collect_selected_rule_names(session_payload)
    if not rule_names:
        raise ValueError("selected_rule_targets is required for compile action")

    outputs: list[str] = []
    for rule_name in rule_names:
        command = f"./atm_compiler {shlex.quote(rule_name)} {shlex.quote(config.line_name)}"
        outputs.append(_run_remote_command(host, config.home_dir_path, command))

    return {
        "message": (
            f"Compile completed: line={config.line_name}, rules={len(rule_names)}"
            f"{_summarize_remote_outputs(outputs)}"
        ),
        "raw_output": "\n\n".join(outputs),
    }


def execute_test_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Default implementation for TEST / RETEST.

    Intended customization point:
    - input: line, rule
    - command example: atm_testscript {Rulename} {Linename}
    """
    session_payload = _extract_session_payload(payload)
    config, host = _get_rtd_line_context(db, task.target_name)
    rule_names = _collect_selected_rule_names(session_payload)
    if not rule_names:
        raise ValueError("selected_rule_targets is required for test action")

    outputs: list[str] = []
    for rule_name in rule_names:
        command = f"./atm_testscript {shlex.quote(rule_name)} {shlex.quote(config.line_name)}"
        outputs.append(_run_remote_command(host, config.home_dir_path, command))

    return {
        "message": (
            f"Test completed: line={config.line_name}, rules={len(rule_names)}"
            f"{_summarize_remote_outputs(outputs)}"
        ),
        "raw_output": "\n\n".join(outputs),
    }


def _extract_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        return nested_payload
    return payload


def _macro_dir_from_home(home_dir_path: str) -> str:
    return posixpath.normpath(posixpath.join(home_dir_path, "..", "Macro"))


def _get_rtd_line_context(db: Session, line_name: str) -> tuple[RtdConfig, HostConfig]:
    resolved_line_name = _normalize_target_line_name(line_name)
    config = db.query(RtdConfig).filter(RtdConfig.line_name == resolved_line_name).first()
    if config is None:
        raise ValueError(f"RTD config not found: {resolved_line_name}")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError(f"Host config not found: {config.host_name}")

    return config, host


def _normalize_target_line_name(line_name: str) -> str:
    if line_name.endswith("_TARGET"):
        return line_name[: -len("_TARGET")]
    return line_name


def _collect_rule_file_names(
    db: Session,
    user_id: str,
    line_name: str,
    session_payload: dict[str, Any],
) -> list[str]:
    runtime_payload = get_runtime_session_payload(db, user_id, TestType.RTD)
    catalog_cache = runtime_payload.get("catalog_cache", {})
    if catalog_cache.get("line_name") != line_name:
        raise ValueError("Rule catalog cache is missing or does not match the selected line")

    selected_rule_targets = session_payload.get("selected_rule_targets", [])
    rule_files: list[str] = []
    seen: set[str] = set()
    missing_items: list[str] = []

    for item in selected_rule_targets:
        rule_name = item.get("rule_name")
        if not rule_name:
            continue

        for version_key in ("old_version", "new_version"):
            version = item.get(version_key)
            if not version:
                continue

            file_name = _find_catalog_file_name(catalog_cache, rule_name, version)
            if not file_name:
                missing_items.append(f"{rule_name}:{version}")
                continue

            if file_name in seen:
                continue

            seen.add(file_name)
            rule_files.append(file_name)

    if missing_items:
        raise ValueError(
            "Rule file not found in session cache for: " + ", ".join(sorted(missing_items))
        )

    return rule_files


def _collect_macro_file_names(session_payload: dict[str, Any]) -> list[str]:
    macro_items = session_payload.get("selected_macros", [])
    if not macro_items and "selected_macros" not in session_payload:
        macro_review = session_payload.get("macro_review", {})
        macro_items = [
            *macro_review.get("old_macros", []),
            *macro_review.get("new_macros", []),
        ]

    seen: set[str] = set()
    result: list[str] = []
    for macro_name in macro_items:
        normalized = str(macro_name or "").strip()
        if not normalized or normalized in seen or normalized == "error":
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _collect_selected_rule_names(session_payload: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in session_payload.get("selected_rule_targets", []):
        rule_name = str(item.get("rule_name", "")).strip()
        if not rule_name or rule_name in seen:
            continue
        seen.add(rule_name)
        result.append(rule_name)
    return result


def _find_catalog_file_name(catalog_cache: dict[str, Any], rule_name: str, version: str) -> str | None:
    for item in catalog_cache.get("files", []):
        if item.get("rule_name") == rule_name and item.get("version") == version:
            return item.get("file_name")
    return None


def _copy_files_between_hosts(
    source_host: HostConfig,
    source_dir: str,
    target_host: HostConfig,
    target_dir: str,
    file_names: list[str],
) -> int:
    if not file_names:
        return 0

    _assert_cp_supported_between_hosts(source_host, target_host)
    _assert_remote_directory_exists(source_host, source_dir, "source")
    _assert_remote_directory_exists(source_host, target_dir, "target")

    copied_count = 0
    for file_name in file_names:
        source_path = posixpath.join(source_dir, file_name)
        target_path = posixpath.join(target_dir, posixpath.basename(file_name))
        _copy_remote_file_with_cp(source_host, source_path, target_path)
        copied_count += 1

    return copied_count


def _run_remote_command(host: HostConfig, working_dir: str, command: str, timeout: int = 120) -> str:
    remote_command = _build_clean_bash_command(f"cd {shlex.quote(working_dir)} && {command}")
    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Remote command failed on host={host.name}: {exc}") from exc

    if exit_status != 0:
        raise RuntimeError(error_output or f"Remote command failed with exit status {exit_status}")

    return output


def _run_remote_shell_command(host: HostConfig, command: str, timeout: int = 120) -> str:
    remote_command = _build_clean_bash_command(command)
    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Remote command failed on host={host.name}: {exc}") from exc

    if exit_status != 0:
        raise RuntimeError(error_output or f"Remote command failed with exit status {exit_status}")

    return output


def _assert_cp_supported_between_hosts(source_host: HostConfig, target_host: HostConfig) -> None:
    if source_host.name != target_host.name:
        raise RuntimeError(
            "cp-based copy requires source and target to be accessible from the same host"
        )


def _assert_remote_directory_exists(host: HostConfig, directory: str, label: str) -> None:
    normalized = posixpath.normpath(directory)
    _run_remote_shell_command(
        host,
        f"test -d {shlex.quote(normalized)}",
    )


def _copy_remote_file_with_cp(host: HostConfig, source_path: str, target_path: str) -> None:
    source_normalized = posixpath.normpath(source_path)
    target_normalized = posixpath.normpath(target_path)
    command = " && ".join(
        [
            f"test -f {shlex.quote(source_normalized)}",
            f"cp -f -- {shlex.quote(source_normalized)} {shlex.quote(target_normalized)}",
        ]
    )
    _run_remote_shell_command(host, command)


def _build_clean_bash_command(command: str) -> str:
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"


def _summarize_remote_outputs(outputs: list[str]) -> str:
    summarized = [output for output in outputs if output]
    if not summarized:
        return ""
    combined = " | ".join(summarized)
    if len(combined) > 180:
        combined = f"{combined[:177]}..."
    return f" [{combined}]"
