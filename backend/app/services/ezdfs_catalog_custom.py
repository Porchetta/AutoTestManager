from __future__ import annotations

"""
ezDFS catalog custom flow

Public API:
1. get_rule_file_list()
   deployed 디렉토리에서 `{file_name, rule_name, version}` catalog row
   리스트를 1-step으로 반환한다.
2. get_backup_file_list()
   backup 디렉토리에서 같은 스키마로 반환 (old version 후보 조회용).
3. get_version_from_filename()
   파일명에서 `ver.x.y.z` 토큰만 추출하는 pure helper.
4. get_subrule_file_list()
   rule 파일이 **재귀적으로** 참조하는 sub rule 이름 목록을 반환한다.
   caller가 이미 catalog를 들고 있으면 `catalog_files`로 전달해 재조회를
   피할 수 있다.
5. read_rule_source_text() / read_rule_source_bytes()
   선택된 deployed rule 파일 본문을 문자열/바이트로 읽는다.
6. find_latest_backup_version()
   backup catalog에서 하나의 rule에 대한 최신 버전을 선택한다.
"""

import posixpath
import re
import shlex

from app.core.exceptions import CatalogError, SSHConnectionError
from app.models.entities import HostConfig
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.ssh_helpers import build_clean_bash_command


_EZDFS_FILE_RE = re.compile(
    r"^(?P<rule_name>.+?)-(?P<version>ver\.[^.]+(?:\.[^.]+)*)\.(?P<timestamp>[^.]+)\.rul$",
    flags=re.IGNORECASE,
)


def get_rule_file_list(
    host: HostConfig, login_user: str, home_dir_path: str
) -> list[dict[str, str]]:
    """
    Discover ezDFS deployed rule files and return structured catalog rows
    in a single step.

    Returns:
    - list[dict[str, str]]: rows with `file_name`, `rule_name`, `version`.
      Sorted by (rule_name, version) case-insensitively.
    """
    deployed_dir = _deployed_dir_from_home(home_dir_path)
    file_names = _list_rul_file_names(host, login_user, deployed_dir, "deployed")
    return _parse_rule_catalog_entries(file_names)


def get_backup_file_list(
    host: HostConfig, login_user: str, home_dir_path: str
) -> list[dict[str, str]]:
    """
    Discover ezDFS backup rule files and return structured catalog rows
    for old-version lookups.
    """
    backup_dir = _backup_dir_from_home(home_dir_path)
    file_names = _list_rul_file_names(host, login_user, backup_dir, "backup")
    return _parse_rule_catalog_entries(file_names)


def get_version_from_filename(file_name: str) -> str:
    """
    Extract the ezDFS version token (`ver.x.y.z`) from one `.rul` filename.

    Format: `{rule_name}-ver.{version}.{timestamp}.rul`.
    Returns `""` when the filename does not match this convention.
    """
    normalized = str(file_name or "").strip()
    match = _EZDFS_FILE_RE.match(normalized)
    if not match:
        return ""
    return str(match.group("version") or "").strip("._- ")


def get_subrule_file_list(
    host: HostConfig,
    login_user: str,
    home_dir_path: str,
    rule_file_name: str,
    catalog_files: list[dict[str, str]] | None = None,
) -> list[str]:
    """
    Return sub-rule **rule_names** (not file names) reachable from one root
    deployed rule file via recursive traversal.

    Input:
    - rule_file_name: A `file_name` from `get_rule_file_list()` (the root).
    - catalog_files: Optional pre-fetched catalog. When None the function
      fetches it once via `get_rule_file_list()`.

    Returns:
    - list[str]: Unique sub-rule `rule_name`s in first-seen order.
      Note that the returned values are logical rule_names. The on-disk
      file convention is `{rule_name}-ver.{version}.{timestamp}.rul` so
      callers that need the actual file must resolve via the catalog.
    """
    catalog = (
        catalog_files
        if catalog_files is not None
        else get_rule_file_list(host, login_user, home_dir_path)
    )

    normalized_root_name = str(rule_file_name or "").strip()
    root_entry = next(
        (item for item in catalog if str(item.get("file_name", "")).strip() == normalized_root_name),
        None,
    )
    preferred_version = str(root_entry.get("version", "")).strip() if root_entry else ""

    try:
        root_text = read_rule_source_text(host, login_user, home_dir_path, rule_file_name)
    except (CatalogError, OSError):
        return []

    resolved: list[str] = []
    seen_rules: set[str] = set()

    def walk(rule_text: str) -> None:
        for sub_rule_name in _extract_sub_rule_names_from_text(rule_text):
            if sub_rule_name not in resolved:
                resolved.append(sub_rule_name)

            if sub_rule_name in seen_rules:
                continue
            seen_rules.add(sub_rule_name)

            child_file_name = _find_catalog_file_name_by_rule_name(
                catalog,
                sub_rule_name,
                preferred_version=preferred_version,
            )
            if not child_file_name:
                continue

            try:
                child_text = read_rule_source_text(host, login_user, home_dir_path, child_file_name)
            except (CatalogError, OSError):
                continue

            walk(child_text)

    walk(root_text)
    return resolved


def read_rule_source_text(
    host: HostConfig, login_user: str, home_dir_path: str, file_name: str
) -> str:
    """Read one deployed ezDFS rule file body as UTF-8 text over SSH."""
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


def read_rule_source_bytes(
    host: HostConfig, login_user: str, home_dir_path: str, file_name: str
) -> bytes:
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


def find_latest_backup_version(
    backup_catalog_files: list[dict[str, str]],
    rule_name: str,
    excluded_version: str = "",
) -> str:
    """Pick the newest available backup version for one ezDFS rule."""
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


def _list_rul_file_names(
    host: HostConfig, login_user: str, remote_dir: str, label: str
) -> list[str]:
    """List bare `.rul` filenames directly under the given remote directory."""
    command = build_clean_bash_command(
        f"cd {shlex.quote(remote_dir)} && find . -maxdepth 1 -type f -name '*.rul' -printf \"%f\\n\""
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
        raise CatalogError(error_output or f"Failed to list ezDFS {label} rule files")

    return [
        line.strip()
        for line in output.splitlines()
        if line.strip() and not line.startswith(".")
    ]


def _parse_rule_catalog_entries(file_names: list[str]) -> list[dict[str, str]]:
    """Convert raw `.rul` filenames into sorted catalog rows."""
    catalog_files: list[dict[str, str]] = []

    for file_name in file_names:
        normalized = str(file_name or "").strip()
        if not normalized:
            continue

        match = _EZDFS_FILE_RE.match(normalized)
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


def _extract_sub_rule_names_from_text(rule_text: str) -> list[str]:
    """Parse direct sub-rule references (`*.rul`) from one ezDFS rule text."""
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
