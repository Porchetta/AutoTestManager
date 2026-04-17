from __future__ import annotations

"""Custom exception classes for the AutoTestManager backend.

These exceptions replace raw ``RuntimeError`` / ``ValueError`` raises in
service code and are converted to HTTP responses by the exception handlers
registered in ``main.py``.
"""


class SSHConnectionError(RuntimeError):
    """SSH connection or authentication failure."""


class RemoteCommandError(RuntimeError):
    """A remote command exited with a non-zero status or produced an error."""

    def __init__(self, message: str, *, host: str = "", exit_status: int | None = None) -> None:
        super().__init__(message)
        self.host = host
        self.exit_status = exit_status


class ConfigNotFoundError(ValueError):
    """A required RTD / ezDFS / Host configuration record was not found."""


class TaskConflictError(Exception):
    """Duplicate or conflicting task request (e.g. same action already running)."""


class CatalogError(RuntimeError):
    """Failure during rule catalog fetch, parse, or cache operations."""
