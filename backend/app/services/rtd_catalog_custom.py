from __future__ import annotations

import re
import shlex

from app.models.entities import HostConfig


def fetch_rule_source_file_names(host: HostConfig, home_dir_path: str) -> list[str]:
    """
    Default implementation for Rule/Version source discovery.

    Customize this function if the offline environment needs a different rule
    file listing strategy.
    """
    try:
        import paramiko
    except ModuleNotFoundError as exc:
        raise RuntimeError("paramiko is not installed") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    command = _build_clean_bash_command(
        f"cd {shlex.quote(home_dir_path)} && find . -maxdepth 1 -type f -printf \"%f\\n\""
    )

    try:
        client.connect(
            hostname=host.ip,
            username=host.login_user,
            password=host.login_password,
            timeout=5,
            auth_timeout=5,
            banner_timeout=5,
        )
        _, stdout, stderr = client.exec_command(command, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore")
        error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SSH connection failed: {exc}") from exc
    finally:
        client.close()

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
    try:
        import paramiko
    except ModuleNotFoundError as exc:
        raise RuntimeError("paramiko is not installed") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    command = _build_clean_bash_command(
        f"cd {shlex.quote(home_dir_path)} && cat {shlex.quote(file_name)}"
    )

    try:
        client.connect(
            hostname=host.ip,
            username=host.login_user,
            password=host.login_password,
            timeout=5,
            auth_timeout=5,
            banner_timeout=5,
        )
        _, stdout, stderr = client.exec_command(command, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore")
        error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SSH file read failed: {exc}") from exc
    finally:
        client.close()

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


def _build_clean_bash_command(command: str) -> str:
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"
