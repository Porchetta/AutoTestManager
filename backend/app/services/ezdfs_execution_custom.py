from __future__ import annotations

"""
ezDFS execution custom flow

1. task_service가 ezDFS TEST / RETEST task를 시작한다.
2. execute_test_action()
   요청 payload에서 module과 rule을 꺼낸다.
3. _get_ezdfs_module_context()
   module 설정과 SSH host 정보를 조회한다.
4. _run_ezdfs_test_binary()
   원격 `ezDFS_test` 바이너리를 실행한다.
5. 결과 raw output과 실행 command를 task raw/result 파일 생성에 넘긴다.
   file_service가 command는 `_meta.txt`, 본문은 rule 이름 txt로 분리 저장한다.
"""

import posixpath
import shlex
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import RemoteCommandError, SSHConnectionError
from app.models.entities import EzdfsConfig, HostConfig, TestTask
from app.services.ssh_runtime import open_limited_ssh_client
from app.utils.ssh_helpers import build_clean_bash_command, extract_session_payload, run_remote_command


def execute_test_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Execute one ezDFS TEST / RETEST task for a selected module and rule.

    Input:
    - db: SQLAlchemy session used to resolve ezDFS config and host info.
    - task: The ezDFS task currently being executed.
    - payload: Original task request payload. The real screen selections are
      read from `payload["payload"]` when present.

    Returns:
    - dict[str, str]:
      - message: Monitor/status summary
      - raw_output: Raw stdout text from the remote test binary
      - test_command: Executed command string. 저장 단계에서 `_meta.txt`에 기록된다.

    Behavior:
    - resolves selected module and rule from request/session payload
    - finds module config and host
    - runs `ezDFS_test {rule_name}` on the remote module home directory

    Intended customization point:
    - default command example: `<home_dir>/ezDFS_test {rule_name}`
    """
    session_payload = extract_session_payload(payload)
    module_name = str(
        payload.get("module_name")
        or session_payload.get("selected_module")
        or ""
    ).strip()
    rule_name = str(
        payload.get("rule_name")
        or session_payload.get("selected_rule")
        or ""
    ).strip()
    if not module_name:
        raise ValueError("module_name is required for ezDFS test action")
    if not rule_name:
        raise ValueError("rule_name is required for ezDFS test action")

    config, host = _get_ezdfs_module_context(db, module_name)
    output, executed_command = _run_ezdfs_test_binary(
        host, config.login_user, config.home_dir_path, rule_name
    )

    return {
        "message": f"Test completed: module={config.module_name}, rule={rule_name}",
        "raw_output": output,
        "test_command": executed_command,
    }


def execute_sync_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Run `./class_sync_file.sh` in the ezDFS module's home directory.

    Mirrors the RTD sync hook so that the same sync script can be deployed
    on ezDFS module hosts. The actual script name is an offline-adaptation
    point and may differ per environment.
    """
    session_payload = extract_session_payload(payload)
    module_name = str(
        payload.get("module_name")
        or session_payload.get("selected_module")
        or ""
    ).strip()
    if not module_name:
        raise ValueError("module_name is required for ezDFS sync action")

    config, host = _get_ezdfs_module_context(db, module_name)
    output = run_remote_command(host, config.login_user, config.home_dir_path, "./class_sync_file.sh")

    return {
        "message": f"Sync completed: module={config.module_name}",
        "raw_output": output,
    }


def _get_ezdfs_module_context(db: Session, module_name: str) -> tuple[EzdfsConfig, HostConfig]:
    """Resolve one ezDFS module config and its HostConfig by module name."""
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise ValueError(f"ezDFS config not found: {module_name}")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError(f"Host config not found: {config.host_name}")

    return config, host


def _run_ezdfs_test_binary(
    host: HostConfig,
    login_user: str,
    working_dir: str,
    rule_name: str,
    timeout: int = 1200,
) -> tuple[str, str]:
    """
    Run the remote `ezDFS_test` binary for one rule.

    Input:
    - host: SSH connection target.
    - working_dir: ezDFS module home directory.
    - rule_name: Selected ezDFS rule name.
    - timeout: Remote command timeout in seconds.

    Returns:
    - tuple[str, str]:
      - stdout text
      - executed command string

    Behavior:
    - validates that `<working_dir>/ezDFS_test` exists and is executable
    - runs the binary with the selected rule name
    - returns stdout plus the exact executed command for later reporting
    """
    binary_path = posixpath.join(working_dir, "ezDFS_test")
    executable_command = f"{shlex.quote(binary_path)} {shlex.quote(rule_name)}"
    remote_command = build_clean_bash_command(
        " && ".join(
            [
                f"cd {shlex.quote(working_dir)}",
                f"test -x {shlex.quote(binary_path)}",
                executable_command,
            ]
        )
    )

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
            error_output
            or f"ezDFS_test execution failed in {working_dir} for rule={rule_name}",
            host=host.name,
            exit_status=exit_status,
        )

    return output, executable_command


