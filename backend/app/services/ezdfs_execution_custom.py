from __future__ import annotations

"""
ezDFS execution custom flow

1. task_service가 ezDFS TEST / RETEST task를 시작한다.
2. execute_ezdfs_test_action()
   요청 payload에서 module과 rule을 꺼낸다.
3. _get_ezdfs_module_context()
   module 설정과 SSH host 정보를 조회한다.
4. _run_ezdfs_test_binary()
   원격 `ezDFS_test` 바이너리를 실행한다.
5. 결과 raw output과 실행 command를 task raw/result 파일 생성에 넘긴다.
"""

import posixpath
import shlex
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, HostConfig, TestTask
from app.services.ssh_runtime import open_limited_ssh_client


def execute_ezdfs_test_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
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
      - test_command: Executed command string for raw/report rendering

    Behavior:
    - resolves selected module and rule from request/session payload
    - finds module config and host
    - runs `ezDFS_test {rule_name}` on the remote module home directory

    Intended customization point:
    - default command example: `<home_dir>/ezDFS_test {rule_name}`
    """
    session_payload = _extract_session_payload(payload)
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
    output, executed_command = _run_ezdfs_test_binary(host, config.home_dir_path, rule_name)

    return {
        "message": f"Test completed: module={config.module_name}, rule={rule_name}",
        "raw_output": output,
        "test_command": executed_command,
    }


def _extract_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return nested ezDFS session payload when the API wrapper uses `payload`."""
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        return nested_payload
    return payload


def _get_ezdfs_module_context(db: Session, module_name: str) -> tuple[EzdfsConfig, HostConfig]:
    """Resolve one ezDFS module config and its HostConfig by module name."""
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise ValueError(f"ezDFS config not found: {module_name}")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError(f"Host config not found: {config.host_name}")

    return config, host


def _run_remote_command(host: HostConfig, working_dir: str, command: str, timeout: int = 120) -> str:
    """Run one remote command inside `working_dir` and return trimmed stdout."""
    remote_command = _build_clean_bash_command(f"cd {shlex.quote(working_dir)} && {command}")
    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Remote command failed on host={host.name}: {exc}") from exc

    if exit_status != 0:
        raise RuntimeError(error_output or f"Remote command failed with exit status {exit_status}")

    return output


def _run_ezdfs_test_binary(
    host: HostConfig,
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
    remote_command = _build_clean_bash_command(
        " && ".join(
            [
                f"cd {shlex.quote(working_dir)}",
                f"test -x {shlex.quote(binary_path)}",
                executable_command,
            ]
        )
    )

    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Remote command failed on host={host.name}: {exc}") from exc

    if exit_status != 0:
        raise RuntimeError(
            error_output
            or f"ezDFS_test execution failed in {working_dir} for rule={rule_name}"
        )

    return output, executable_command


def _build_clean_bash_command(command: str) -> str:
    """Wrap shell snippets in a minimal bash invocation for predictable execution."""
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"
