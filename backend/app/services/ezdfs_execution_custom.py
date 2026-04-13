from __future__ import annotations

import posixpath
import shlex
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import EzdfsConfig, HostConfig, TestTask
from app.services.ssh_runtime import open_limited_ssh_client


def execute_ezdfs_test_action(db: Session, task: TestTask, payload: dict[str, Any]) -> dict[str, str]:
    """
    Default implementation for ezDFS TEST / RETEST.

    Intended customization point:
    - input: module, rule
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
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        return nested_payload
    return payload


def _get_ezdfs_module_context(db: Session, module_name: str) -> tuple[EzdfsConfig, HostConfig]:
    config = db.query(EzdfsConfig).filter(EzdfsConfig.module_name == module_name).first()
    if config is None:
        raise ValueError(f"ezDFS config not found: {module_name}")

    host = db.query(HostConfig).filter(HostConfig.name == config.host_name).first()
    if host is None:
        raise ValueError(f"Host config not found: {config.host_name}")

    return config, host


def _run_remote_command(host: HostConfig, working_dir: str, command: str, timeout: int = 120) -> str:
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
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"
