from __future__ import annotations

"""
RTD catalog custom flow

Public API:
1. get_rule_file_list()
   Dispatcher 디렉토리를 조회해 `{file_name, rule_name, version}` catalog row
   리스트를 1-step으로 반환한다.
2. get_macro_file_list()
   선택한 rule report가 참조하는 전체 macro `.report` 이름 리스트를 반환한다.
3. get_version_from_filename()
   파일명에서 version 토큰만 추출하는 pure helper.
4. read_rule_source_text() / read_rule_source_bytes()
   선택된 rule report 본문을 원격에서 문자열/바이트로 읽는다.
"""

import re
import shlex

from app.core.exceptions import CatalogError, SSHConnectionError
from app.models.entities import HostConfig
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.ssh_helpers import build_clean_bash_command


def get_rule_file_list(
    host: HostConfig, login_user: str, home_dir_path: str
) -> list[dict[str, str]]:
    """
    Discover RTD rule reports under the remote Dispatcher directory and
    return structured catalog rows in a single step.

    Input:
    - host: SSH connection target that owns the RTD line files.
    - login_user: SSH login account.
    - home_dir_path: Remote Dispatcher directory path.

    Returns:
    - list[dict[str, str]]: catalog rows with
      - file_name: original filename
      - rule_name: logical rule name before `_PC`
      - version: version token after `_PC`, without `.report`
      Sorted by (rule_name, version) case-insensitively.

    Customize this function if the report/version naming convention or
    remote layout changes.
    """
    file_names = _fetch_rule_source_file_names(host, login_user, home_dir_path)
    return _parse_rule_catalog_entries(file_names)


def get_macro_file_list(
    host: HostConfig,
    login_user: str,
    home_dir_path: str,
    rule_file_name: str,
) -> list[str]:
    """
    Return the full list of Macro `.report` names referenced by one rule
    report. This is the entire dependency closure, NOT the old/new diff
    shown on the Step 4 UI.

    Input:
    - host, login_user, home_dir_path: SSH target + Dispatcher directory.
    - rule_file_name: One `file_name` from `get_rule_file_list()`.

    Returns:
    - list[str]: Unique dependent macro report names, first-seen order.
    """
    rule_text = read_rule_source_text(host, login_user, home_dir_path, rule_file_name)
    return _extract_macro_list_from_text(rule_text)


def get_version_from_filename(file_name: str) -> str:
    """
    Extract the RTD version token from one report file name.

    Format: `{rule_name}_PC{version}.report` (e.g. `RULE_A_PCv1.report`).
    Returns `""` when the filename does not match this convention.
    """
    if "_PC" not in file_name or not file_name.endswith(".report"):
        return ""
    _, version_part = file_name.split("_PC", 1)
    normalized = version_part.strip("._- ")
    if normalized.endswith(".report"):
        normalized = normalized[: -len(".report")].strip("._- ")
    return normalized


def read_rule_source_text(
    host: HostConfig, login_user: str, home_dir_path: str, file_name: str
) -> str:
    """Read one RTD `.report` file body as UTF-8 text over SSH."""
    command = build_clean_bash_command(
        f"cd {shlex.quote(home_dir_path)} && cat {shlex.quote(file_name)}"
    )

    try:
        with open_limited_ssh_client(host, login_user) as client:
            _, stdout, stderr = client.exec_command(command, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore")
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except (SSHConnectionError, OSError) as exc:
        raise CatalogError(f"SSH file read failed: {exc}") from exc

    if exit_status != 0:
        raise CatalogError(error_output or f"Failed to read remote file: {file_name}")

    return output


def read_rule_source_bytes(
    host: HostConfig, login_user: str, home_dir_path: str, file_name: str
) -> bytes:
    """Read one RTD `.report` file as raw bytes via SFTP."""
    remote_path = f"{home_dir_path.rstrip('/')}/{file_name}"
    try:
        with open_limited_ssh_client(host, login_user) as client:
            sftp = client.open_sftp()
            try:
                with sftp.open(remote_path, "rb") as remote_file:
                    return remote_file.read()
            finally:
                sftp.close()
    except (SSHConnectionError, OSError) as exc:
        raise CatalogError(f"SFTP byte read failed: {exc}") from exc


def _fetch_rule_source_file_names(
    host: HostConfig, login_user: str, home_dir_path: str
) -> list[str]:
    """List bare filenames directly under the remote Dispatcher directory."""
    command = build_clean_bash_command(
        f"cd {shlex.quote(home_dir_path)} && find . -maxdepth 1 -type f -printf \"%f\\n\""
    )

    try:
        with open_limited_ssh_client(host, login_user) as client:
            _, stdout, stderr = client.exec_command(command, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore")
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except (SSHConnectionError, OSError) as exc:
        raise CatalogError(f"SSH connection failed: {exc}") from exc

    if exit_status != 0:
        raise CatalogError(error_output or "Failed to list remote files")

    return [line.strip() for line in output.splitlines() if line.strip()]


def _parse_rule_catalog_entries(file_names: list[str]) -> list[dict[str, str]]:
    """Convert raw `.report` filenames into sorted catalog rows."""
    catalog_files: list[dict[str, str]] = []

    for file_name in file_names:
        if "_PC" not in file_name or not file_name.endswith(".report"):
            continue

        rule_name, _version_part = file_name.split("_PC", 1)
        rule_name = rule_name.strip("._- ")
        version_name = get_version_from_filename(file_name)

        if not rule_name or not version_name:
            continue

        catalog_files.append(
            {
                "file_name": file_name,
                "rule_name": rule_name,
                "version": version_name,
            }
        )

    return sorted(
        catalog_files,
        key=lambda item: (item["rule_name"].lower(), item["version"].lower()),
    )


def _extract_macro_list_from_text(rule_text: str) -> list[str]:
    """
    Parse dependent Macro `.report` names from one rule report text.

    Returns entries in first-seen order (compile priority depends on it).
    """
    items: list[str] = []

    for raw_line in rule_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("//") or line.startswith("#") or line.startswith(";"):
            continue

        normalized = re.split(r"\s*(?://|#|;)\s*", line, maxsplit=1)[0].strip()
        if not normalized:
            continue

        items.append(normalized)

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
