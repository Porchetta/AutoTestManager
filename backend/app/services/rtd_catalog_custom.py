from __future__ import annotations

"""
RTD catalog custom flow

1. fetch_rule_source_file_names()
   Remote Dispatcher 디렉토리에서 `.report` 파일명을 읽는다.
2. parse_rule_catalog_entries()
   파일명을 `rule_name + version` 형태의 catalog row로 변환한다.
3. read_rule_source_text() / read_rule_source_bytes()
   사용자가 고른 rule/report 파일 본문을 원격에서 문자열이나 바이트로 읽는다.
4. extract_macro_list()
   해당 rule/report 안에 적힌 dependent Macro report 목록을 순서대로 추출한다.
"""

import re
import shlex

from app.models.entities import HostConfig
from app.services.ssh_runtime import open_limited_ssh_client


def fetch_rule_source_file_names(host: HostConfig, home_dir_path: str) -> list[str]:
    """
    Discover raw RTD source filenames from the remote Dispatcher directory.

    Input:
    - host: SSH connection target that owns the RTD line files.
    - home_dir_path: Remote Dispatcher directory path.

    Returns:
    - list[str]: Bare filenames found directly under `home_dir_path`.

    Behavior:
    - opens SSH with the configured host account
    - lists only maxdepth-1 files under the target directory
    - returns names only, without directory prefixes

    Customize this function if the offline environment uses a different
    listing command or directory layout.
    """
    command = _build_clean_bash_command(
        f"cd {shlex.quote(home_dir_path)} && find . -maxdepth 1 -type f -printf \"%f\\n\""
    )

    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(command, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore")
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SSH connection failed: {exc}") from exc

    if exit_status != 0:
        raise RuntimeError(error_output or "Failed to list remote files")

    return [line.strip() for line in output.splitlines() if line.strip()]


def parse_rule_catalog_entries(file_names: list[str]) -> list[dict[str, str]]:
    """
    Convert remote `.report` filenames into RTD catalog entries.

    Input:
    - file_names: Raw filenames returned by `fetch_rule_source_file_names()`.

    Returns:
    - list[dict[str, str]]: Sorted catalog rows with:
      - file_name: original filename
      - rule_name: logical rule name before `_PC`
      - version: version token after `_PC`, without `.report`

    Behavior:
    - accepts only filenames that contain `_PC` and end with `.report`
    - splits the name into `rule_name` and `version`
    - sorts by rule name, then version

    Customize this function if the report/version naming convention changes.
    """
    catalog_files: list[dict[str, str]] = []

    for file_name in file_names:
        if "_PC" not in file_name or not file_name.endswith(".report"):
            continue

        rule_name, version_name = file_name.split("_PC", 1)
        rule_name = rule_name.strip("._- ")
        version_name = _strip_report_suffix(version_name)

        if not rule_name or not version_name:
            continue

        catalog_files.append(
            {
                "file_name": file_name,
                "rule_name": rule_name,
                "version": version_name,
            }
        )

    return sorted(catalog_files, key=lambda item: (item["rule_name"].lower(), item["version"].lower()))


def read_rule_source_text(host: HostConfig, home_dir_path: str, file_name: str) -> str:
    """
    Read one RTD source `.report` file from the remote Dispatcher directory.

    Input:
    - host: SSH connection target.
    - home_dir_path: Remote Dispatcher directory path.
    - file_name: File to open within `home_dir_path`.

    Returns:
    - str: Full remote file text.

    Customize this function if report contents must be loaded differently.
    """
    return read_remote_source_text(host, home_dir_path, file_name)


def read_remote_source_text(host: HostConfig, remote_dir_path: str, file_name: str) -> str:
    """
    Shared remote text reader for RTD `.report` files.

    Input:
    - host: SSH connection target.
    - remote_dir_path: Remote directory that contains the file.
    - file_name: Bare filename to read.

    Returns:
    - str: Full decoded UTF-8 file content.

    Behavior:
    - runs `cat` through a clean bash shell
    - raises `RuntimeError` when SSH or remote read fails
    """
    command = _build_clean_bash_command(
    f"cd {shlex.quote(remote_dir_path)} && cat {shlex.quote(file_name)}"
    )

    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(command, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore")
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SSH file read failed: {exc}") from exc

    if exit_status != 0:
        raise RuntimeError(error_output or f"Failed to read remote file: {file_name}")

    return output


def read_rule_source_bytes(host: HostConfig, home_dir_path: str, file_name: str) -> bytes:
    """Read one RTD source `.report` file as raw bytes via SFTP."""
    return read_remote_source_bytes(host, home_dir_path, file_name)


def read_remote_source_bytes(host: HostConfig, remote_dir_path: str, file_name: str) -> bytes:
    """Shared remote byte reader for RTD `.report` files via SFTP."""
    remote_path = f"{remote_dir_path.rstrip('/')}/{file_name}"
    try:
        with open_limited_ssh_client(host) as client:
            sftp = client.open_sftp()
            try:
                with sftp.open(remote_path, "rb") as remote_file:
                    return remote_file.read()
            finally:
                sftp.close()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SFTP byte read failed: {exc}") from exc


def extract_macro_list(host: HostConfig, home_dir_path: str, rule_text: str, rule_name: str) -> list[str]:
    """
    Extract dependent Macro `.report` names from one rule/report text.

    Input:
    - host: Unused in the current implementation. Kept for compatibility with
      the service call chain.
    - home_dir_path: Unused in the current implementation. Kept for compatibility.
    - rule_text: Full text of the selected rule/report file.
    - rule_name: Logical rule name, useful when this parser is customized later.

    Returns:
    - list[str]: Unique dependent report names in first-seen order.

    Behavior:
    - parses the current rule text only once
    - ignores blank lines and comment-only lines
    - strips trailing inline comments
    - preserves discovery order because compile priority depends on it

    Source reports already contain the full dependent list, so no recursive
    file reads happen here.
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


def _build_clean_bash_command(command: str) -> str:
    """Wrap a raw shell snippet so it runs in a minimal non-interactive bash."""
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"


def _strip_report_suffix(version_name: str) -> str:
    """Remove the trailing `.report` suffix from a parsed version token."""
    normalized = version_name.strip("._- ")
    if normalized.endswith(".report"):
        return normalized[: -len(".report")].strip("._- ")
    return normalized
