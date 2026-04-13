from __future__ import annotations

import posixpath
import re
import shlex

from app.models.entities import HostConfig
from app.services.ssh_runtime import open_limited_ssh_client


def fetch_rule_source_file_names(host: HostConfig, home_dir_path: str) -> list[str]:
    """
    Default implementation for ezDFS rule discovery.

    Rules are discovered from `.rul` files under `<home_dir_path>/repository/container/dfsdev/deployed`.
    Customize this function if the offline environment uses a different
    directory structure or filtering rule.
    """
    deployed_dir = _deployed_dir_from_home(home_dir_path)
    command = _build_clean_bash_command(
        f"cd {shlex.quote(deployed_dir)} && find . -maxdepth 1 -type f -name '*.rul' -printf \"%f\\n\""
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
        raise RuntimeError(error_output or "Failed to list ezDFS rule files")

    return [line.strip() for line in output.splitlines() if line.strip() and not line.startswith(".")]


def fetch_backup_rule_source_file_names(host: HostConfig, home_dir_path: str) -> list[str]:
    """
    Discover old-version ezDFS rule files from the backup directory.

    Old-version candidates are discovered from `.rul` files under
    `<home_dir_path>/repository/container/dfsdev/backup`.
    """
    backup_dir = _backup_dir_from_home(home_dir_path)
    command = _build_clean_bash_command(
        f"cd {shlex.quote(backup_dir)} && find . -maxdepth 1 -type f -name '*.rul' -printf \"%f\\n\""
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
        raise RuntimeError(error_output or "Failed to list ezDFS backup rule files")

    return [line.strip() for line in output.splitlines() if line.strip() and not line.startswith(".")]


def parse_rule_catalog_entries(file_names: list[str]) -> list[dict[str, str]]:
    """
    Convert raw file names to ezDFS rule catalog entries.

    Current behavior:
    - expected file name format: `{rule_name}-ver.{version}.{timestamp}.rul`
    - keep the original file_name
    - parse `rule_name`
    - parse `version` including the `ver.` prefix
    - ignore `timestamp`
    """
    catalog_files: list[dict[str, str]] = []

    for file_name in file_names:
        normalized = str(file_name or "").strip()
        if not normalized:
            continue

        match = re.match(
            r"^(?P<rule_name>.+?)-(?P<version>ver\.[^.]+(?:\.[^.]+)*)\.(?P<timestamp>[^.]+)\.rul$",
            normalized,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        rule_name = str(match.group("rule_name") or "").strip("._- ")
        version = str(match.group("version") or "").strip("._- ")
        if not rule_name or not version:
            continue

        catalog_files.append(
            {
                "file_name": normalized,
                "rule_name": rule_name,
                "version": version,
            }
        )

    return sorted(
        catalog_files,
        key=lambda item: (item["rule_name"].lower(), item["version"].lower()),
    )


def read_rule_source_text(host: HostConfig, home_dir_path: str, file_name: str) -> str:
    """
    Read one ezDFS rule file from `<home_dir_path>/repository/container/dfsdev/deployed`.
    """
    deployed_dir = _deployed_dir_from_home(home_dir_path)
    command = _build_clean_bash_command(
        f"cd {shlex.quote(deployed_dir)} && cat {shlex.quote(file_name)}"
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
        raise RuntimeError(error_output or f"Failed to read ezDFS rule file: {file_name}")

    return output


def extract_sub_rule_list_from_rule_text(rule_text: str, rule_name: str) -> list[str]:
    """
    Default implementation for ezDFS sub-rule extraction.

    Current behavior:
    - scan each line for `{rule_name}.rul` references
    - ignore blank lines
    - ignore comment-only lines starting with //, #, ;
    - strip trailing inline comments
    - return the referenced `rule_name` values without `.rul`
    - keep first-seen order

    Customize this function if the offline environment uses a different
    sub-rule parsing convention.
    """
    _ = rule_name
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

        for matched_rule in re.findall(r"([A-Za-z0-9_.-]+)\.rul\b", normalized, flags=re.IGNORECASE):
            cleaned_rule = str(matched_rule or "").strip("._- ")
            if cleaned_rule:
                items.append(cleaned_rule)

    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def resolve_recursive_sub_rule_list(
    host: HostConfig,
    home_dir_path: str,
    root_rule_text: str,
    catalog_files: list[dict[str, str]],
    preferred_version: str = "",
) -> list[str]:
    resolved: list[str] = []
    seen_rules: set[str] = set()

    def walk_source_text(rule_text: str) -> None:
        direct_items = extract_sub_rule_list_from_rule_text(rule_text, "")
        for item in direct_items:
            if item not in resolved:
                resolved.append(item)

            normalized_rule_name = str(item or "").strip()
            if not normalized_rule_name or normalized_rule_name in seen_rules:
                continue

            seen_rules.add(normalized_rule_name)
            child_file_name = _find_catalog_file_name_by_rule_name(
                catalog_files,
                normalized_rule_name,
                preferred_version=preferred_version,
            )
            if not child_file_name:
                continue

            try:
                child_rule_text = read_rule_source_text(host, home_dir_path, child_file_name)
            except Exception:  # noqa: BLE001
                continue

            walk_source_text(child_rule_text)

    walk_source_text(root_rule_text)
    return resolved


def _build_clean_bash_command(command: str) -> str:
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"


def _deployed_dir_from_home(home_dir_path: str) -> str:
    return posixpath.normpath(posixpath.join(home_dir_path, "repository/container/dfsdev/deployed"))


def _backup_dir_from_home(home_dir_path: str) -> str:
    return posixpath.normpath(posixpath.join(home_dir_path, "repository/container/dfsdev/backup"))


def _find_catalog_file_name_by_rule_name(
    catalog_files: list[dict[str, str]],
    rule_name: str,
    preferred_version: str = "",
) -> str | None:
    normalized_rule_name = str(rule_name or "").strip().lower()
    normalized_version = str(preferred_version or "").strip().lower()

    if normalized_version:
        for item in catalog_files:
            if (
                str(item.get("rule_name", "")).strip().lower() == normalized_rule_name
                and str(item.get("version", "")).strip().lower() == normalized_version
            ):
                return str(item.get("file_name", "")).strip() or None

    for item in catalog_files:
        if str(item.get("rule_name", "")).strip().lower() == normalized_rule_name:
            return str(item.get("file_name", "")).strip() or None
    return None


def find_latest_backup_version(
    backup_catalog_files: list[dict[str, str]],
    rule_name: str,
    excluded_version: str = "",
) -> str:
    normalized_rule_name = str(rule_name or "").strip().lower()
    normalized_excluded_version = str(excluded_version or "").strip().lower()

    matching_versions = [
        str(item.get("version", "")).strip()
        for item in backup_catalog_files
        if str(item.get("rule_name", "")).strip().lower() == normalized_rule_name
        and str(item.get("version", "")).strip()
        and str(item.get("version", "")).strip().lower() != normalized_excluded_version
    ]

    if not matching_versions:
        return ""

    return max(matching_versions, key=_version_sort_key)


def _version_sort_key(version: str) -> tuple:
    normalized = str(version or "").strip()
    if normalized.lower().startswith("ver."):
        normalized = normalized[4:]

    parts: list[tuple[int, int | str]] = []
    for piece in normalized.split("."):
        piece = piece.strip()
        if piece.isdigit():
            parts.append((0, int(piece)))
        else:
            parts.append((1, piece.lower()))

    return tuple(parts)
