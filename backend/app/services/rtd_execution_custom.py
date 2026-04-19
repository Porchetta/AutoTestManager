from __future__ import annotations

"""
RTD execution custom flow

1. task_service가 RTD COPY / COMPILE / TEST task를 시작한다.
2. 각 task는 여기의 execute_*_action()으로 들어온다.
3. execute_copy_action()
   선택된 rule report와 macro report를 target line으로 복사한다.
4. execute_compile_action()
   macro report를 우선순위 역순으로 먼저 컴파일하고, 마지막에 rule report를 컴파일한다.
5. execute_test_action()
   선택된 rule들을 같은 line task 안에서 순서대로 테스트하고, rule별 raw section을 남긴다.
"""

import posixpath
import shlex
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import ConfigNotFoundError, RemoteCommandError, SSHConnectionError
from app.models.entities import HostConfig, RtdConfig, TestTask
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.naming import normalize_target_line_name
from app.utils.ssh_helpers import build_clean_bash_command, extract_session_payload, run_remote_command


def execute_copy_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Copy selected rule reports and dependent macro reports to one target line.

    Input:
    - db: SQLAlchemy session used to resolve RTD configs and session cache.
    - task: The RTD COPY task being executed. `task.target_name` is the target line.
    - payload: Original task request payload. The actual RTD selections are read
      from `payload["payload"]` when present.

    Returns:
    - dict[str, str]:
      - message: Human-readable copy summary for monitor hover text
      - raw_output: Reserved raw console output, empty for copy

    Behavior:
    - resolves the selected dev line from runtime/session payload
    - finds selected rule file names from the cached catalog
    - collects selected macro file names
    - copies Dispatcher files and Macro files with remote `cp`
    - returns copied counts and copied item names

    Current path convention:
    - source rule files: <dev_home_dir>/
    - source macro files: <dev_home_dir>/../Macro/
    - target rule files: <target_home_dir>/
    - target macro files: <target_home_dir>/../Macro/
    """
    session_payload = extract_session_payload(payload)
    dev_line_name = session_payload.get("selected_line_name") or payload.get("selected_line_name") or ""
    if not dev_line_name:
        raise ValueError("selected_line_name is required for copy action")

    source_config, source_host = _get_rtd_line_context(db, dev_line_name)
    target_config, target_host = _get_rtd_line_context(db, task.target_name)

    rule_file_names = _collect_rule_file_names_from_payload(session_payload)
    macro_file_names = _collect_macro_file_names_from_payload(session_payload)

    if not rule_file_names:
        raise ValueError("No rule files resolved for copy action")

    copied_rule_count = 0
    copied_macro_count = 0

    if rule_file_names:
        copied_rule_count = _copy_files_between_hosts(
            source_host=source_host,
            source_login_user=source_config.login_user,
            source_dir=source_config.home_dir_path,
            target_host=target_host,
            target_dir=target_config.home_dir_path,
            file_names=rule_file_names,
        )

    if macro_file_names:
        copied_macro_count = _copy_files_between_hosts(
            source_host=source_host,
            source_login_user=source_config.login_user,
            source_dir=_macro_dir_from_home(source_config.home_dir_path),
            target_host=target_host,
            target_dir=_macro_dir_from_home(target_config.home_dir_path),
            file_names=macro_file_names,
        )

    return {
        "message": (
            f"Copy completed\n"
            f"dev={source_config.line_name}\n"
            f"target={target_config.line_name}\n"
            f"rules={copied_rule_count}\n"
            f"macros={copied_macro_count}"
            f"{_format_copied_items_summary(rule_file_names, macro_file_names)}"
        ),
        "raw_output": "",
    }


def execute_compile_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Compile selected macro reports first, then selected rule reports.

    Input:
    - db: SQLAlchemy session used to resolve RTD config and host info.
    - task: The RTD COMPILE task. `task.target_name` identifies the line.
    - payload: Original task request payload or nested RTD session payload.

    Returns:
    - dict[str, str]:
      - message: Compile summary shown in the monitor overlay
      - raw_output: Joined remote command output for debugging/logging

    Behavior:
    - resolves one target line and host
    - gets selected rule names and selected macro names
    - compiles macros first in reverse discovery order
    - compiles selected rules last
    - concatenates remote outputs into both summary and raw_output

    Intended customization point:
    - command example: `atm_compiler {ReportName} {LineName}`
    """
    session_payload = extract_session_payload(payload)
    config, host = _get_rtd_line_context(db, task.target_name)
    rule_names = _collect_selected_rule_names(session_payload)
    macro_names = _collect_macro_file_names_from_payload(session_payload)
    if not rule_names:
        raise ValueError("selected_rule_targets is required for compile action")

    outputs: list[str] = []
    # Higher-priority macros are discovered earlier in the rule source,
    # so compile starts from the lowest-priority end of that ordered list.
    for macro_name in reversed(macro_names):
        command = f"./atm_compiler {shlex.quote(macro_name)} {shlex.quote(config.line_name)}"
        outputs.append(run_remote_command(host, config.login_user, config.home_dir_path, command))
    for rule_name in rule_names:
        command = f"./atm_compiler {shlex.quote(rule_name)} {shlex.quote(config.line_name)}"
        outputs.append(run_remote_command(host, config.login_user, config.home_dir_path, command))

    return {
        "message": (
            f"Compile completed\n"
            f"line={config.line_name}\n"
            f"rules={len(rule_names)}\n"
            f"macros={len(macro_names)}"
            f"{_format_compile_items_summary(rule_names)}"
            f"{_summarize_remote_outputs(outputs)}"
        ),
        "raw_output": "\n\n".join(outputs),
    }


def execute_test_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Execute RTD tests for the selected rules sequentially on one target line.

    Input:
    - db: SQLAlchemy session used to resolve RTD config and host info.
    - task: The RTD TEST/RETEST task. One task represents one target line.
    - payload: Original task request payload or nested RTD session payload.

    Returns:
    - dict[str, str]:
      - message: Test summary shown in the monitor overlay
      - raw_output: Reserved aggregate raw text, kept for task-level logging
      - raw_outputs_by_rule: Per-rule raw text used for saved raw txt files

    Behavior:
    - resolves one target line and host
    - collects all selected rules from the payload
    - runs `atm_testscript` once per rule in sequence
    - returns per-rule raw output so file_service can save `line x rule` txt
      files directly, without reparsing a large combined file later

    Intended customization point:
    - command example: `atm_testscript {ReportName} {LineName}`
    """
    session_payload = extract_session_payload(payload)
    config, host = _get_rtd_line_context(db, task.target_name)
    rule_names = _collect_selected_rule_names(session_payload)
    if not rule_names:
        raise ValueError("selected_rule_targets is required for test action")

    outputs: list[str] = []
    output_by_rule: list[tuple[str, str]] = []
    for rule_name in rule_names:
        command = f"./atm_testscript {shlex.quote(rule_name)} {shlex.quote(config.line_name)}"
        output = run_remote_command(host, config.login_user, config.home_dir_path, command)
        outputs.append(output)
        output_by_rule.append((rule_name, output))

    return {
        "message": _format_test_summary_message(config.line_name, rule_names, outputs),
        "raw_output": _format_test_raw_output(config.line_name, output_by_rule),
        "raw_outputs_by_rule": {rule_name: output for rule_name, output in output_by_rule},
    }


def _macro_dir_from_home(home_dir_path: str) -> str:
    """Resolve the sibling Macro directory from a Dispatcher home path."""
    return posixpath.normpath(posixpath.join(home_dir_path, "..", "Macro"))


def _get_rtd_line_context(db: Session, line_name: str) -> tuple[RtdConfig, HostConfig]:
    """Resolve one RTD line config and its HostConfig from a line or target name."""
    resolved_line_name = normalize_target_line_name(line_name)
    config = db.query(RtdConfig).filter(RtdConfig.line_name == resolved_line_name).first()
    if config is None:
        raise ValueError(f"RTD config not found: {resolved_line_name}")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError(f"Host config not found: {config.host_name}")

    return config, host


def _collect_rule_file_names_from_payload(session_payload: dict[str, Any]) -> list[str]:
    """
    Resolve rule/report filenames directly from session payload.

    `selected_rule_targets[*]` is expected to carry `old_file_name` and
    `new_file_name` for each rule (recorded at the Rule-select step).
    Missing filenames raise ValueError listing the offending rule:version.
    """
    rule_files: list[str] = []
    seen: set[str] = set()
    missing_items: list[str] = []

    for item in _sorted_selected_rule_targets(session_payload):
        rule_name = str(item.get("rule_name", "")).strip()
        if not rule_name:
            continue

        for version_key, file_key in (
            ("old_version", "old_file_name"),
            ("new_version", "new_file_name"),
        ):
            version = str(item.get(version_key, "")).strip()
            file_name = str(item.get(file_key, "")).strip()
            if not version:
                continue
            if not file_name:
                missing_items.append(f"{rule_name}:{version}")
                continue
            if file_name in seen:
                continue
            seen.add(file_name)
            rule_files.append(file_name)

    if missing_items:
        raise ValueError(
            "Rule file name missing in selected_rule_targets for: "
            + ", ".join(sorted(missing_items))
        )

    return rule_files


def _collect_macro_file_names_from_payload(session_payload: dict[str, Any]) -> list[str]:
    """
    Collect the full macro closure from session payload.

    Reads `selected_macros.per_rule[*].old_macros + new_macros` union in
    first-seen order. copy / compile targets are the full per-rule closure.
    """
    selected_macros = session_payload.get("selected_macros")
    macro_items: list[str] = []

    if isinstance(selected_macros, dict):
        per_rule = selected_macros.get("per_rule")
        if isinstance(per_rule, list):
            for entry in per_rule:
                if not isinstance(entry, dict):
                    continue
                for key in ("old_macros", "new_macros"):
                    for name in entry.get(key, []) or []:
                        macro_items.append(name)

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
    """Return unique selected rule names sorted by rule name."""
    seen: set[str] = set()
    result: list[str] = []
    for item in _sorted_selected_rule_targets(session_payload):
        rule_name = str(item.get("rule_name", "")).strip()
        if not rule_name or rule_name in seen:
            continue
        seen.add(rule_name)
        result.append(rule_name)
    return result


def _sorted_selected_rule_targets(session_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return selected RTD rule targets sorted by rule name.

    This keeps copy / compile / test execution order stable regardless of the
    order in which the user added rules in the UI.
    """
    selected_rule_targets = (
        session_payload.get("selected_rule_targets", [])
        if isinstance(session_payload.get("selected_rule_targets"), list)
        else []
    )
    return sorted(
        selected_rule_targets,
        key=lambda item: (
            str(item.get("rule_name", "")).strip().lower(),
            str(item.get("new_version", "")).strip().lower(),
            str(item.get("old_version", "")).strip().lower(),
        ),
    )


def _copy_files_between_hosts(
    source_host: HostConfig,
    source_login_user: str,
    source_dir: str,
    target_host: HostConfig,
    target_dir: str,
    file_names: list[str],
) -> int:
    """
    Copy multiple files between two RTD directories on the same remote host.

    Returns:
    - int: Number of files successfully copied.
    """
    if not file_names:
        return 0

    _assert_cp_supported_between_hosts(source_host, target_host)
    _assert_remote_directory_exists(source_host, source_login_user, source_dir, "source")
    _assert_remote_directory_exists(source_host, source_login_user, target_dir, "target")

    copied_count = 0
    for file_name in file_names:
        source_path = posixpath.join(source_dir, file_name)
        target_path = posixpath.join(target_dir, posixpath.basename(file_name))
        _copy_remote_file_with_cp(source_host, source_login_user, source_path, target_path)
        copied_count += 1

    return copied_count


def _run_remote_shell_command(host: HostConfig, login_user: str, command: str, timeout: int = 120) -> str:
    """Run one raw shell command without changing directories and return stdout."""
    remote_command = build_clean_bash_command(command)
    try:
        with open_limited_ssh_client(host, login_user) as client:
            _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except (SSHConnectionError, OSError) as exc:
        raise SSHConnectionError(f"Remote command failed on host={host.name}: {exc}") from exc

    if exit_status != 0:
        raise RemoteCommandError(
            error_output or f"Remote command failed with exit status {exit_status}",
            host=host.name,
            exit_status=exit_status,
        )

    return output


def _assert_cp_supported_between_hosts(source_host: HostConfig, target_host: HostConfig) -> None:
    """Guard the current copy strategy, which only supports same-host `cp`."""
    if source_host.name != target_host.name:
        raise RuntimeError(
            "cp-based copy requires source and target to be accessible from the same host"
        )


def _assert_remote_directory_exists(host: HostConfig, login_user: str, directory: str, label: str) -> None:
    """Validate a remote directory before file copy starts."""
    normalized = posixpath.normpath(directory)
    try:
        _run_remote_shell_command(
            host,
            login_user,
            f"test -d {shlex.quote(normalized)}",
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"{label} directory not found or inaccessible on host={host.name}: {normalized}"
        ) from exc


def _copy_remote_file_with_cp(host: HostConfig, login_user: str, source_path: str, target_path: str) -> None:
    """Copy one remote file with `cp -f`, validating the source file first."""
    source_normalized = posixpath.normpath(source_path)
    target_normalized = posixpath.normpath(target_path)
    try:
        _run_remote_shell_command(
            host,
            login_user,
            f"test -f {shlex.quote(source_normalized)}",
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"source file not found or inaccessible on host={host.name}: {source_normalized}"
        ) from exc

    try:
        _run_remote_shell_command(
            host,
            login_user,
            f"cp -f -- {shlex.quote(source_normalized)} {shlex.quote(target_normalized)}",
        )
    except RuntimeError as exc:
        raise RuntimeError(
            f"copy failed on host={host.name}: {source_normalized} -> {target_normalized}"
        ) from exc


def _summarize_remote_outputs(outputs: list[str]) -> str:
    """Compress multiple remote outputs into one short single-line summary string."""
    summarized = [output for output in outputs if output]
    if not summarized:
        return ""
    combined = " | ".join(summarized)
    if len(combined) > 180:
        combined = f"{combined[:177]}..."
    return f"\noutput={combined}"


def _format_test_summary_message(line_name: str, rule_names: list[str], outputs: list[str]) -> str:
    """Build the monitor-friendly multiline summary for one RTD test task."""
    return (
        f"Test completed\n"
        f"line={line_name}\n"
        f"rules={len(rule_names)}"
        f"{_format_compile_items_summary(rule_names)}"
        f"{_summarize_remote_outputs(outputs)}"
    )


def _format_test_raw_output(line_name: str, output_by_rule: list[tuple[str, str]]) -> str:
    """Build a lightweight aggregate raw string for task-level logging/debugging."""
    sections: list[str] = [f"line={line_name}"]
    for rule_name, output in output_by_rule:
        sections.append(f"[{rule_name}]")
        sections.append(output or "")
    return "\n".join(sections).strip()


def _format_copied_items_summary(rule_file_names: list[str], macro_file_names: list[str]) -> str:
    """Append copied report names to the COPY monitor summary."""
    segments: list[str] = []
    if rule_file_names:
        segments.append("rules=" + ", ".join(rule_file_names))
    if macro_file_names:
        segments.append("macros=" + ", ".join(macro_file_names))
    if not segments:
        return ""
    return "\n" + "\n".join(segments)


def _format_compile_items_summary(rule_names: list[str]) -> str:
    """Append compiled rule names to the COMPILE/TEST monitor summary."""
    if not rule_names:
        return ""
    return "\n" + "rules=" + ", ".join(rule_names)
