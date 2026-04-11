from __future__ import annotations

import posixpath
import re
import shlex

from app.models.entities import HostConfig
from app.services.ssh_runtime import open_limited_ssh_client


def fetch_rule_source_file_names(host: HostConfig, home_dir_path: str) -> list[str]:
    """
    Default implementation for Rule/Version source discovery.

    Customize this function if the offline environment needs a different rule
    file listing strategy.
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
    Default implementation for converting raw file names into:
    - file_name
    - rule_name
    - version

    Customize this function if the rule/version naming convention changes.
    """
    catalog_files: list[dict[str, str]] = []

    for file_name in file_names:
        if "_PC" not in file_name:
            continue

        rule_name, version_name = file_name.split("_PC", 1)
        rule_name = rule_name.strip("._- ")
        version_name = version_name.strip("._- ").replace(".rule", "").strip("._- ")

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
    Default implementation for reading a .rule source file.

    Customize this function if rule contents must be loaded differently.
    """
    return read_remote_source_text(host, home_dir_path, file_name)


def read_macro_source_text(host: HostConfig, home_dir_path: str, macro_name: str) -> str:
    """
    Default implementation for reading a macro file.

    Macro files are expected under `<home_dir_path>/../Macro`.
    Customize this function if the macro directory or naming rule changes.
    """
    macro_dir = posixpath.normpath(posixpath.join(home_dir_path, "..", "Macro"))
    return read_remote_source_text(host, macro_dir, macro_name)


def read_remote_source_text(host: HostConfig, remote_dir_path: str, file_name: str) -> str:
    """
    Shared remote file reader used by both rule files and macro files.
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


def extract_macro_list_from_rule_text(rule_text: str, rule_name: str) -> list[str]:
    """
    Default implementation for extracting macros from rule file text.

    Current behavior:
    - split by lines
    - ignore blank lines
    - ignore comment-only lines starting with //, #, ;
    - strip trailing comments

    Customize this function if macro parsing rules differ in the offline
    environment.
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


def resolve_recursive_macro_list(
    host: HostConfig,
    home_dir_path: str,
    rule_text: str,
    rule_name: str,
) -> list[str]:
    """
    Resolve macros recursively.

    Flow:
    - read rule text
    - find direct macros
    - for each macro, read the corresponding macro file
    - scan that macro text again for nested macros
    - repeat recursively

    The default implementation assumes:
    - each macro name maps to a file with the same name
    - macro files live under `<home_dir_path>/../Macro`

    Missing nested macro files are ignored so the visible top-level macro list
    still remains available.
    """
    resolved: list[str] = []
    seen_macros: set[str] = set()
    visited_macro_files: set[str] = set()

    def walk_source_text(source_text: str, source_name: str) -> None:
        for macro_name in extract_macro_list_from_rule_text(source_text, source_name):
            normalized = str(macro_name or "").strip()
            if not normalized or normalized == "error":
                continue

            if normalized not in seen_macros:
                seen_macros.add(normalized)
                resolved.append(normalized)

            if normalized in visited_macro_files:
                continue

            visited_macro_files.add(normalized)

            try:
                nested_text = read_macro_source_text(host, home_dir_path, normalized)
            except RuntimeError:
                continue

            walk_source_text(nested_text, normalized)

    walk_source_text(rule_text, rule_name)
    return resolved


def _build_clean_bash_command(command: str) -> str:
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"
