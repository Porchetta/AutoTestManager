from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings
from app.core.exceptions import SSHConnectionError
from app.db.session import SessionLocal
from app.models.entities import HostConfig, HostCredential
from app.utils.ssh_helpers import build_clean_bash_command

SSH_CONNECT_TIMEOUT = 5
SSH_AUTH_TIMEOUT = 5
SSH_BANNER_TIMEOUT = 12
DEFAULT_SSH_PARALLEL_LIMIT = 10

settings = get_settings()

_host_limit_cache: dict[str, int] = {}
_host_limit_source_cache: dict[str, str] = {}
_host_semaphore_cache: dict[str, threading.BoundedSemaphore] = {}
_cache_lock = threading.Lock()


@contextmanager
def open_limited_ssh_client(host: HostConfig, login_user: str) -> Iterator[object]:
    semaphore = _get_host_semaphore(host, login_user)
    semaphore.acquire()
    try:
        client = _open_raw_ssh_client(host, login_user)
        try:
            yield client
        finally:
            client.close()
    finally:
        semaphore.release()


def get_host_parallel_limit(host: HostConfig, login_user: str) -> int:
    with _cache_lock:
        if host.name in _host_limit_cache:
            return _host_limit_cache[host.name]

    return probe_host_parallel_limit(host, login_user)


def probe_host_parallel_limit(host: HostConfig, login_user: str) -> int:
    info = probe_host_parallel_limit_info(host, login_user)
    return int(info["parallel_limit"])


def get_host_parallel_limit_info(host: HostConfig) -> dict[str, object]:
    with _cache_lock:
        limit = _host_limit_cache.get(host.name, DEFAULT_SSH_PARALLEL_LIMIT)
        source = _host_limit_source_cache.get(host.name, "unknown")
    return {
        "host_name": host.name,
        "parallel_limit": limit,
        "source": source,
    }


def probe_host_parallel_limit_info(host: HostConfig, login_user: str) -> dict[str, object]:
    try:
        limit = _probe_remote_parallel_limit(host, login_user)
        source = "remote"
    except Exception as exc:  # noqa: BLE001
        limit = DEFAULT_SSH_PARALLEL_LIMIT
        source = "default"
        _append_admin_alert(
            f"[SSH_LIMIT_FALLBACK] host={host.name} ip={host.ip} "
            f"user={login_user} reason={exc} fallback={DEFAULT_SSH_PARALLEL_LIMIT}"
        )

    _update_host_limit_cache(host.name, limit, source)
    return {
        "host_name": host.name,
        "parallel_limit": limit,
        "source": source,
    }


def _get_host_semaphore(host: HostConfig, login_user: str) -> threading.BoundedSemaphore:
    limit = get_host_parallel_limit(host, login_user)
    with _cache_lock:
        semaphore = _host_semaphore_cache.get(host.name)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(limit)
            _host_semaphore_cache[host.name] = semaphore
        return semaphore


def _probe_remote_parallel_limit(host: HostConfig, login_user: str) -> int:
    command = build_clean_bash_command(
        "if [ -x /usr/sbin/sshd ]; then "
        "/usr/sbin/sshd -T 2>/dev/null | awk '/^maxstartups /{print $2; exit}'; "
        "elif command -v sshd >/dev/null 2>&1; then "
        "sshd -T 2>/dev/null | awk '/^maxstartups /{print $2; exit}'; "
        "fi"
    )

    with open_limited_ssh_client_raw(host, login_user) as client:
        _, stdout, stderr = client.exec_command(command, timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode("utf-8", errors="ignore").strip()
        error_output = stderr.read().decode("utf-8", errors="ignore").strip()

    if exit_status != 0:
        raise RuntimeError(error_output or "Failed to inspect remote sshd config")
    if not output:
        raise RuntimeError("Remote sshd maxstartups value is empty")

    match = re.match(r"^(\d+)(?::\d+:\d+)?$", output)
    if not match:
        raise RuntimeError(f"Unrecognized maxstartups value: {output}")

    parsed = int(match.group(1))
    if parsed <= 0:
        raise RuntimeError(f"Invalid maxstartups value: {output}")
    return parsed


@contextmanager
def open_limited_ssh_client_raw(host: HostConfig, login_user: str) -> Iterator[object]:
    client = _open_raw_ssh_client(host, login_user)
    try:
        yield client
    finally:
        client.close()


@contextmanager
def open_direct_ssh_client(
    host_name: str,
    ip: str,
    login_user: str,
    login_password: str,
) -> Iterator[object]:
    """Open an SSH client using inline credentials (e.g. SVN upload env host).

    This bypasses the HostCredential table lookup and is intended for hosts
    whose credentials live outside the Host admin page (e.g. env vars).
    Uses the same per-host semaphore cache, keyed by ``host_name``.
    """

    with _cache_lock:
        semaphore = _host_semaphore_cache.get(host_name)
        if semaphore is None:
            semaphore = threading.BoundedSemaphore(DEFAULT_SSH_PARALLEL_LIMIT)
            _host_semaphore_cache[host_name] = semaphore

    semaphore.acquire()
    try:
        client = _open_raw_ssh_client_direct(host_name, ip, login_user, login_password)
        try:
            yield client
        finally:
            client.close()
    finally:
        semaphore.release()


def _open_raw_ssh_client_direct(
    host_name: str,
    ip: str,
    login_user: str,
    login_password: str,
):
    try:
        import paramiko
    except ModuleNotFoundError as exc:
        raise RuntimeError("paramiko is not installed") from exc

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=ip,
            username=login_user,
            password=login_password,
            timeout=SSH_CONNECT_TIMEOUT,
            auth_timeout=SSH_AUTH_TIMEOUT,
            banner_timeout=SSH_BANNER_TIMEOUT,
        )
    except (paramiko.SSHException, OSError) as exc:
        client.close()
        raise SSHConnectionError(
            f"SSH connection failed for host={host_name} user={login_user}: {exc}"
        ) from exc
    return client


def _resolve_credential(host: HostConfig, login_user: str) -> HostCredential:
    if not login_user:
        raise SSHConnectionError(
            f"SSH connection failed for host={host.name}: login_user is empty"
        )

    with SessionLocal() as session:
        credential = (
            session.query(HostCredential)
            .filter(
                HostCredential.host_id == host.id,
                HostCredential.login_user == login_user,
            )
            .first()
        )
        if credential is None:
            raise SSHConnectionError(
                f"SSH credential not found for host={host.name} user={login_user}"
            )
        session.expunge(credential)
    return credential


def _open_raw_ssh_client(host: HostConfig, login_user: str):
    try:
        import paramiko
    except ModuleNotFoundError as exc:
        raise RuntimeError("paramiko is not installed") from exc

    credential = _resolve_credential(host, login_user)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host.ip,
            username=credential.login_user,
            password=credential.login_password,
            timeout=SSH_CONNECT_TIMEOUT,
            auth_timeout=SSH_AUTH_TIMEOUT,
            banner_timeout=SSH_BANNER_TIMEOUT,
        )
    except (paramiko.SSHException, OSError) as exc:
        client.close()
        raise SSHConnectionError(
            f"SSH connection failed for host={host.name} user={login_user}: {exc}"
        ) from exc
    return client


def _append_admin_alert(message: str) -> None:
    log_dir = Path(settings.result_base_path).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "admin_alert.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{timestamp} {message}\n")


def _update_host_limit_cache(host_name: str, limit: int, source: str) -> None:
    with _cache_lock:
        _host_limit_cache[host_name] = limit
        _host_limit_source_cache[host_name] = source
        _host_semaphore_cache[host_name] = threading.BoundedSemaphore(limit)
