from __future__ import annotations

"""Shared SSH helper functions used across custom execution/catalog modules."""

import shlex
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.entities import HostConfig


def build_clean_bash_command(command: str) -> str:
    """Wrap a shell snippet in a minimal non-interactive bash invocation."""
    return f"bash --noprofile --norc -lc {shlex.quote(command)}"


def run_remote_command(
    host: HostConfig,
    working_dir: str,
    command: str,
    timeout: int = 120,
) -> str:
    """Run one command inside ``working_dir`` on a remote host and return trimmed stdout."""
    from app.services.ssh_runtime import open_limited_ssh_client

    remote_command = build_clean_bash_command(f"cd {shlex.quote(working_dir)} && {command}")
    from app.core.exceptions import RemoteCommandError, SSHConnectionError

    try:
        with open_limited_ssh_client(host) as client:
            _, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error_output = stderr.read().decode("utf-8", errors="ignore").strip()
    except (SSHConnectionError, OSError) as exc:
        raise SSHConnectionError(f"Remote command failed on host={host.name}: {exc}") from exc

    if exit_status != 0:
        raise RemoteCommandError(
            error_output or f"Remote command failed with exit status {exit_status}",
            host=host.name,
            exit_status=exit_status,
        )

    return output


def extract_session_payload(payload: dict) -> dict:
    """Return the nested session payload when the API wrapper uses a ``payload`` key."""
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        return nested_payload
    return payload
