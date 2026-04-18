from __future__ import annotations

"""
ezDFS catalog custom flow

1. fetch_rule_source_file_names()
   deployed 디렉토리에서 현재 rule `.rul` 파일명을 읽는다.
2. fetch_backup_rule_source_file_names()
   backup 디렉토리에서 old version 후보 `.rul` 파일명을 읽는다.
3. parse_rule_catalog_entries()
   파일명을 `rule_name + version` 형태의 catalog row로 변환한다.
4. read_rule_source_text() / read_rule_source_bytes()
   선택한 deployed rule 파일 본문을 문자열이나 바이트로 읽는다.
5. extract_sub_rule_list_from_rule_text() / resolve_recursive_sub_rule_list()
   rule 안에 참조된 sub rule을 직접 추출하고, 필요하면 하위 rule까지 재귀적으로 확장한다.
"""

import posixpath
import re
import shlex

from app.core.exceptions import CatalogError, SSHConnectionError
from app.models.entities import HostConfig
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.ssh_helpers import build_clean_bash_command


def fetch_rule_source_file_names(host: HostConfig, login_user: str, home_dir_path: str) -> list[str]:
    """
    Discover ezDFS deployed rule filenames from the remote module directory.

    Input:
    - host: SSH connection target that owns the ezDFS module files.
    - home_dir_path: ezDFS module home path from admin config.

    Returns:
    - list[str]: Bare `.rul` filenames found in the deployed directory.

    Behavior:
    - resolves `<home_dir_path>/repository/container/dfsdev/deployed`
    - lists only top-level `.rul` files
    - ignores hidden files
    """
    deployed_dir = _deployed_dir_from_home(home_dir_path)
    command = build_clean_bash_command(
        f"cd {shlex.quote(deployed_dir)} && find . -maxdepth 1 -type f -name '*.rul' -printf \"%f\\n\""
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
        raise CatalogError(error_output or "Failed to list ezDFS rule files")

    return [line.strip() for line in output.splitlines() if line.strip() and not line.startswith(".")]


def fetch_backup_rule_source_file_names(host: HostConfig, login_user: str, home_dir_path: str) -> list[str]:
    """
    Discover backup ezDFS rule filenames from the remote backup directory.

    Input:
    - host: SSH connection target.
    - home_dir_path: ezDFS module home path.

    Returns:
    - list[str]: Bare `.rul` filenames found in the backup directory.

    Behavior:
    - resolves `<home_dir_path>/repository/container/dfsdev/backup`
    - lists only top-level `.rul` files
    - used to find old-version candidates for comparison
    """
    backup_dir = _backup_dir_from_home(home_dir_path)
    command = build_clean_bash_command(
        f"cd {shlex.quote(backup_dir)} && find . -maxdepth 1 -type f -name '*.rul' -printf \"%f\\n\""
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
        raise CatalogError(error_output or "Failed to list ezDFS backup rule files")

    return [line.strip() for line in output.splitlines() if line.strip() and not line.startswith(".")]


def parse_rule_catalog_entries(file_names: list[str]) -> list[dict[str, str]]:
    """
    Convert raw ezDFS filenames into catalog rows.

    Input:
    - file_names: Raw `.rul` filenames from deployed or backup directories.

    Returns:
    - list[dict[str, str]]: Sorted catalog rows with:
      - file_name: original filename
      - rule_name: logical ezDFS rule name
      - version: parsed version token including `ver.`

    Expected filename format:
    - `{rule_name}-ver.{version}.{timestamp}.rul`

    Behavior:
    - preserves the original file name
    - parses `rule_name`
    - parses `version`
    - ignores the trailing timestamp token
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


def read_rule_source_text(host: HostConfig, login_user: str, home_dir_path: str, file_name: str) -> str:
    """
    Read one deployed ezDFS rule file over SSH.

    Input:
    - host: SSH connection target.
    - home_dir_path: ezDFS module home path.
    - file_name: Bare deployed `.rul` filename.

    Returns:
    - str: Full rule file text.
    """
    deployed_dir = _deployed_dir_from_home(home_dir_path)
    command = build_clean_bash_command(
        f"cd {shlex.quote(deployed_dir)} && cat {shlex.quote(file_name)}"
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
        raise RuntimeError(error_output or f"Failed to read ezDFS rule file: {file_name}")

    return output


def read_rule_source_bytes(host: HostConfig, login_user: str, home_dir_path: str, file_name: str) -> bytes:
    """Read one deployed ezDFS rule file as raw bytes over SFTP."""
    deployed_dir = _deployed_dir_from_home(home_dir_path)
    remote_path = f"{deployed_dir.rstrip('/')}/{file_name}"

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


def extract_sub_rule_list_from_rule_text(rule_text: str, rule_name: str) -> list[str]:
    """
    Extract direct sub-rule references from one ezDFS rule text.

    Input:
    - rule_text: Full deployed ezDFS rule file text.
    - rule_name: Current root rule name. Unused for now, but kept so custom
      parsers can use rule-specific heuristics later.

    Returns:
    - list[str]: Unique sub-rule names in first-seen order, without `.rul`.

    Behavior:
    - scans each line for `*.rul` references
    - ignores blank lines and comment-only lines
    - strips trailing inline comments
    - removes duplicates while preserving order
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
    login_user: str,
    home_dir_path: str,
    root_rule_text: str,
    catalog_files: list[dict[str, str]],
    preferred_version: str = "",
) -> list[str]:
    """
    Resolve the full recursive ezDFS sub-rule tree starting from one root rule.

    Input:
    - host: SSH connection target.
    - home_dir_path: ezDFS module home path.
    - root_rule_text: Full text of the selected root rule.
    - catalog_files: Catalog rows used to map `rule_name -> file_name`.
    - preferred_version: Optional version preference when multiple rule files
      exist for the same rule name.

    Returns:
    - list[str]: Unique sub-rule names discovered through recursive traversal.

    Behavior:
    - extracts direct sub-rules from the current rule text
    - resolves the corresponding child file from catalog metadata
    - reads the child rule file and repeats the same scan
    - keeps first-seen order across the whole tree
    """
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
                child_rule_text = read_rule_source_text(host, login_user, home_dir_path, child_file_name)
            except (CatalogError, OSError):
                continue

            walk_source_text(child_rule_text)

    walk_source_text(root_rule_text)
    return resolved


def _deployed_dir_from_home(home_dir_path: str) -> str:
    """Resolve the deployed ezDFS directory from one module home path."""
    return posixpath.normpath(posixpath.join(home_dir_path, "repository/container/dfsdev/deployed"))


def _backup_dir_from_home(home_dir_path: str) -> str:
    """Resolve the backup ezDFS directory from one module home path."""
    return posixpath.normpath(posixpath.join(home_dir_path, "repository/container/dfsdev/backup"))


def _find_catalog_file_name_by_rule_name(
    catalog_files: list[dict[str, str]],
    rule_name: str,
    preferred_version: str = "",
) -> str | None:
    """Find the most appropriate ezDFS file name for one rule, optionally by version."""
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
    """
    Pick the newest available backup version for one ezDFS rule.

    Input:
    - backup_catalog_files: Parsed backup catalog rows.
    - rule_name: Rule whose old version is needed.
    - excluded_version: Current deployed version to exclude from candidates.

    Returns:
    - str: Best matching old version, or empty string when unavailable.
    """
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
