from __future__ import annotations

"""
SVN Upload custom flow

1. RTD / ezDFS 세션에서 현재 선택 상태를 읽는다.
2. Rule 원본 파일은 기존 RTD / ezDFS host 설정을 통해 SSH로 읽는다.
3. SVN Upload는 별도 환경변수 host(IP / 계정 / 비밀번호)로 SSH 접속한다.
4. 원격 {SVN_UPLOAD_DIR}/{user_id} 작업 디렉토리를 비운 뒤 new version 파일만 업로드한다.
5. 해당 디렉토리에서 svn_bin_checkin 을 실행하고 출력에서 svn no. 를 추출한다.
6. 결과(svn no., 업로드 파일 목록)는 각 세션 payload의 svn_upload 필드에 저장한다.
"""

import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import EzdfsConfig, HostConfig, RtdConfig, User
from app.services.catalog_service import (
    find_ezdfs_rule_file_name_in_session,
    find_rule_file_name_in_session,
)
from app.services.ezdfs_catalog_custom import (
    read_rule_source_bytes as read_ezdfs_rule_source_bytes,
)
from app.services.rtd_catalog_custom import (
    _build_clean_bash_command as build_rtd_clean_bash_command,
    read_rule_source_bytes as read_rtd_rule_source_bytes,
)
from app.services.session_service import (
    get_runtime_session_payload,
    upsert_runtime_session,
)
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.enums import TestType

settings = get_settings()


@dataclass
class SvnUploadHost:
    """SVN Upload 전용 원격 접속 정보."""

    name: str
    ip: str
    login_user: str
    login_password: str


def perform_rtd_svn_upload(
    db: Session,
    current_user: User,
    ad_user: str,
    ad_password: str,
) -> dict[str, object]:
    """
    Run SVN Upload for the current RTD session.

    Inputs:
    - db: active SQLAlchemy session.
    - current_user: 로그인 사용자.
    - ad_user / ad_password: 팝업(패널)에서 입력한 SVN 인증값.

    Returns:
    - {"ad_user", "svn_no", "uploaded_at", "confirmed", "uploaded_files"}

    Behavior:
    - RTD 세션에서 선택된 rule target을 읽는다.
    - 각 rule의 new version 파일명을 세션 cache에서 찾는다.
    - RTD host에서 실제 rule 파일 본문을 읽는다.
    - SVN Upload 전용 host에 업로드/실행하고 svn no.를 세션에 저장한다.
    """

    session_payload = get_runtime_session_payload(db, current_user.user_id, TestType.RTD)
    line_name = str(session_payload.get("selected_line_name") or "").strip()
    selected_rule_targets = (
        session_payload.get("selected_rule_targets")
        if isinstance(session_payload.get("selected_rule_targets"), list)
        else []
    )
    selected_macros = (
        session_payload.get("selected_macros")
        if isinstance(session_payload.get("selected_macros"), list)
        else []
    )
    if not line_name:
        raise ValueError("selected_line_name is required for SVN Upload")
    if not selected_rule_targets:
        raise ValueError("selected_rule_targets is required for SVN Upload")

    config = db.query(RtdConfig).filter(RtdConfig.line_name == line_name).first()
    if config is None:
        raise ValueError("RTD config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("RTD host config not found")

    svn_host = _build_svn_upload_host()
    file_contents: dict[str, str] = {}

    for item in selected_rule_targets:
        rule_name = str(item.get("rule_name") or "").strip()
        new_version = str(item.get("new_version") or "").strip()
        if not rule_name or not new_version:
            continue

        file_name = find_rule_file_name_in_session(
            db,
            current_user,
            line_name,
            rule_name,
            new_version,
        )
        if not file_name:
            raise ValueError(
                f"RTD new version file not found in session cache: {rule_name} / {new_version}"
            )

        file_contents[file_name] = read_rtd_rule_source_bytes(
            host,
            config.home_dir_path,
            file_name,
        )

    macro_review = session_payload.get("macro_review") or {}
    new_macros = set(macro_review.get("new_macros") or [])

    for macro_file_name in _collect_selected_macro_file_names(selected_macros):
        if macro_file_name not in new_macros:
            continue
        file_contents[macro_file_name] = _read_rtd_macro_source_bytes(
            host,
            config.home_dir_path,
            macro_file_name,
        )

    if not file_contents:
        raise ValueError("No RTD new version files found for SVN Upload")

    result = _run_svn_upload(
        svn_host,
        current_user.user_id,
        file_contents,
        ad_user,
        ad_password,
        mode="4",
    )
    return _persist_svn_upload_result(
        db,
        current_user.user_id,
        TestType.RTD,
        session_payload,
        ad_user,
        result,
    )


def perform_ezdfs_svn_upload(
    db: Session,
    current_user: User,
    ad_user: str,
    ad_password: str,
) -> dict[str, object]:
    """
    Run SVN Upload for the current ezDFS session.

    Inputs / Returns:
    - RTD 버전과 동일하다.

    Behavior:
    - ezDFS 세션의 selected_rules에서 file_name을 읽는다.
    - ezDFS host에서 rule 본문을 읽는다.
    - SVN Upload 전용 host에 파일 업로드 후 svn_bin_checkin 을 실행한다.
    """

    session_payload = get_runtime_session_payload(db, current_user.user_id, TestType.EZDFS)
    module_name = str(session_payload.get("selected_module") or "").strip()
    selected_rules = (
        session_payload.get("selected_rules")
        if isinstance(session_payload.get("selected_rules"), list)
        else []
    )
    selected_sub_rules = (
        session_payload.get("selected_sub_rules")
        if isinstance(session_payload.get("selected_sub_rules"), list)
        else []
    )
    if not module_name:
        raise ValueError("selected_module is required for SVN Upload")
    if not selected_rules:
        raise ValueError("selected_rules is required for SVN Upload")

    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise ValueError("ezDFS config not found")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError("ezDFS host config not found")

    svn_host = _build_svn_upload_host()
    file_contents: dict[str, bytes] = {}

    for item in selected_rules:
        file_name = str(item.get("file_name") or "").strip()
        if not file_name:
            continue
        cleaned_file_name = re.sub(r"-ver\..+\.rul$", ".rul", file_name, flags=re.IGNORECASE)
        file_contents[cleaned_file_name] = read_ezdfs_rule_source_bytes(
            host,
            config.home_dir_path,
            file_name,
        )

    for sub_rule_name in _collect_selected_sub_rule_names(selected_sub_rules):
        sub_rule_file_name = find_ezdfs_rule_file_name_in_session(
            db,
            current_user,
            module_name,
            sub_rule_name,
        )
        if not sub_rule_file_name:
            raise ValueError(f"ezDFS sub rule file not found in session cache: {sub_rule_name}")
        
        cleaned_file_name = re.sub(r"-ver\..+\.rul$", ".rul", sub_rule_file_name, flags=re.IGNORECASE)
        file_contents[cleaned_file_name] = read_ezdfs_rule_source_bytes(
            host,
            config.home_dir_path,
            sub_rule_file_name,
        )

    if not file_contents:
        raise ValueError("No ezDFS new version files found for SVN Upload")

    result = _run_svn_upload(
        svn_host,
        current_user.user_id,
        file_contents,
        ad_user,
        ad_password,
        mode="3",
    )
    return _persist_svn_upload_result(
        db,
        current_user.user_id,
        TestType.EZDFS,
        session_payload,
        ad_user,
        result,
    )


def _persist_svn_upload_result(
    db: Session,
    user_id: str,
    session_type: TestType,
    session_payload: dict,
    ad_user: str,
    result: dict[str, object],
) -> dict[str, object]:
    """Store the parsed svn upload result back into the runtime session."""

    svn_upload = {
        "ad_user": ad_user,
        "svn_no": str(result["svn_no"]),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "confirmed": True,
        "uploaded_files": list(result.get("uploaded_files", [])),
        "checkin_output": str(result.get("checkin_output", "")),
    }
    next_payload = {**session_payload, "svn_upload": svn_upload}
    upsert_runtime_session(db, user_id, session_type, next_payload)
    return svn_upload


def _run_svn_upload(
    host: SvnUploadHost,
    user_id: str,
    file_contents: dict[str, bytes],
    ad_user: str,
    ad_password: str,
    mode: str,
) -> dict[str, object]:
    """
    Upload files to the remote SVN work dir and execute svn_bin_checkin.

    Inputs:
    - host: SVN Upload 전용 SSH 접속 정보.
    - user_id: 작업 디렉토리를 구분할 사용자 id.
    - file_contents: {file_name: text}.
    - ad_user / ad_password: svn_bin_checkin stdin 입력값.
    - mode: ezDFS=3, RTD=4.

    Returns:
    - {"svn_no", "uploaded_files"}
    """

    uploaded_file_names = sorted(file_contents.keys(), key=str.lower)
    command_input = "\n".join(["Y", ad_user, ad_password, mode]) + "\n"
    work_dir = Path(settings.svn_upload_dir) / user_id

    _prepare_remote_work_dir(host, str(work_dir))
    _upload_remote_files(host, str(work_dir), file_contents, uploaded_file_names)
    output = _run_remote_svn_checkin(host, str(work_dir), command_input)

    svn_no = _extract_svn_no(output)
    if not svn_no:
        raise RuntimeError(output or "Failed to parse svn no. from svn_bin_checkin output")

    return {
        "svn_no": svn_no,
        "uploaded_files": uploaded_file_names,
        "checkin_output": output,
    }


def _prepare_remote_work_dir(host: SvnUploadHost, work_dir: str) -> None:
    """Create the remote work dir and clear previous files under it."""

    quoted_work_dir = shlex.quote(work_dir)
    command = (
        f"mkdir -p {quoted_work_dir} && "
        f"find {quoted_work_dir} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +"
    )
    _run_remote_shell_command(host, command)


def _upload_remote_files(
    host: SvnUploadHost,
    work_dir: str,
    file_contents: dict[str, bytes],
    uploaded_file_names: list[str],
) -> None:
    """Copy each prepared rule file to the remote work directory over SFTP."""

    with open_limited_ssh_client(host) as client:
        sftp = client.open_sftp()
        try:
            for file_name in uploaded_file_names:
                remote_path = str(Path(work_dir) / file_name)
                with sftp.file(remote_path, "wb") as remote_file:
                    remote_file.write(file_contents[file_name] or b"")
        finally:
            sftp.close()


def _run_remote_svn_checkin(
    host: SvnUploadHost,
    work_dir: str,
    command_input: str,
    timeout: int = 120,
) -> str:
    """
    Execute svn_bin_checkin in the remote work dir and return combined output text.
    """

    quoted_dir = shlex.quote(work_dir)
    command_path = str(settings.svn_upload_command or "svn_bin_checkin").strip()
    remote_command = (
        "bash --noprofile --norc -lc "
        + shlex.quote(f"cd {quoted_dir} && {shlex.quote(command_path)}")
    )
    with open_limited_ssh_client(host) as client:
        stdin, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
        stdin.write(command_input)
        stdin.flush()
        stdin.channel.shutdown_write()
        exit_status = stdout.channel.recv_exit_status()
        output = "\n".join(
            [
                stdout.read().decode("utf-8", errors="ignore").strip(),
                stderr.read().decode("utf-8", errors="ignore").strip(),
            ]
        ).strip()
    if exit_status != 0:
        raise RuntimeError(output or f"{command_path} failed with exit status {exit_status}")
    return output


def _run_remote_shell_command(
    host: SvnUploadHost,
    command: str,
    timeout: int = 30,
) -> str:
    """Run a simple non-interactive shell command on the remote SVN host."""

    remote_command = "bash --noprofile --norc -lc " + shlex.quote(command)
    with open_limited_ssh_client(host) as client:
        _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
        exit_status = stdout.channel.recv_exit_status()
        output = "\n".join(
            [
                stdout.read().decode("utf-8", errors="ignore").strip(),
                stderr.read().decode("utf-8", errors="ignore").strip(),
            ]
        ).strip()
    if exit_status != 0:
        raise RuntimeError(output or f"remote command failed with exit status {exit_status}")
    return output


def _build_svn_upload_host() -> SvnUploadHost:
    """Build the dedicated SVN upload SSH target from environment variables."""

    host_ip = str(settings.svn_upload_host_ip or "").strip()
    if not host_ip:
        raise ValueError("SVN_UPLOAD_HOST_IP is not configured")

    login_user = str(settings.svn_upload_host_user or "").strip()
    if not login_user:
        raise ValueError("SVN_UPLOAD_HOST_USER is not configured")

    login_password = str(settings.svn_upload_host_password or "")
    if not login_password:
        raise ValueError("SVN_UPLOAD_HOST_PASSWORD is not configured")

    return SvnUploadHost(
        name="svn-upload-host",
        ip=host_ip,
        login_user=login_user,
        login_password=login_password,
    )


def _extract_svn_no(output: str) -> str:
    """Extract the numeric svn no. token from svn_bin_checkin output text."""

    match = re.search(r"svn[_\s-]*no\.?\s*([0-9]+)", str(output or ""), flags=re.IGNORECASE)
    return str(match.group(1)) if match else ""


def _collect_selected_macro_file_names(selected_macros: list[object]) -> list[str]:
    """Return selected RTD macro/report file names in stable first-seen order."""

    seen: set[str] = set()
    result: list[str] = []
    for item in selected_macros:
        normalized = str(item or "").strip()
        if not normalized or normalized == "error" or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _collect_selected_sub_rule_names(selected_sub_rules: list[object]) -> list[str]:
    """Return checked ezDFS sub rule names in stable first-seen order."""

    seen: set[str] = set()
    result: list[str] = []
    for item in selected_sub_rules:
        normalized = str(item or "").strip()
        if not normalized or normalized == "error" or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _read_rtd_macro_source_bytes(host: HostConfig, home_dir_path: str, file_name: str) -> bytes:
    """Read one RTD macro/report file from the sibling Macro directory via SFTP."""
    macro_dir = _macro_dir_from_home(home_dir_path)
    remote_path = f"{macro_dir.rstrip('/')}/{file_name}"

    try:
        with open_limited_ssh_client(host) as client:
            sftp = client.open_sftp()
            try:
                with sftp.open(remote_path, "rb") as remote_file:
                    return remote_file.read()
            finally:
                sftp.close()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SFTP macro file byte read failed: {exc}") from exc


def _macro_dir_from_home(home_dir_path: str) -> str:
    """Resolve the sibling Macro directory from an RTD Dispatcher home path."""

    return str(Path(home_dir_path).parent / "Macro")
