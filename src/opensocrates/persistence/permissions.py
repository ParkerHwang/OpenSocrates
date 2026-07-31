"""Owner-only permission checks and write-readiness gates.

Permission failures are represented as a report so callers can continue with
useful in-memory behavior while disabling new durable writes.  No caller is
given a way to bypass the owner-only policy for production state.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path


class PermissionSecurityError(PermissionError):
    """Raised when a caller explicitly requires a secure writable path."""


@dataclass(frozen=True, slots=True)
class PermissionReport:
    path: Path
    exists: bool
    owner_ok: bool
    mode_ok: bool
    symlink_ok: bool
    writable: bool
    issues: tuple[str, ...]

    @property
    def write_allowed(self) -> bool:
        return self.exists and self.owner_ok and self.mode_ok and self.symlink_ok and self.writable


def _owner_ok(info: os.stat_result) -> bool:
    if os.name == "nt":
        return True
    try:
        return info.st_uid == os.getuid()
    except AttributeError:
        return True


def check_permissions(path: Path, *, directory: bool) -> PermissionReport:
    """Inspect a path without changing it."""

    path = Path(path)
    try:
        info = path.lstat()
    except FileNotFoundError:
        return PermissionReport(
            path=path,
            exists=False,
            owner_ok=False,
            mode_ok=False,
            symlink_ok=True,
            writable=False,
            issues=("missing",),
        )
    except OSError:
        return PermissionReport(
            path=path,
            exists=False,
            owner_ok=False,
            mode_ok=False,
            symlink_ok=False,
            writable=False,
            issues=("uninspectable",),
        )

    is_directory = stat.S_ISDIR(info.st_mode)
    symlink_ok = not stat.S_ISLNK(info.st_mode)
    owner_ok = symlink_ok and _owner_ok(info)
    expected_type = directory == is_directory
    if os.name == "nt":
        mode_ok = expected_type
    else:
        mode = stat.S_IMODE(info.st_mode)
        mode_ok = expected_type and (mode & 0o077) == 0
    writable = symlink_ok and os.access(path, os.W_OK)
    issues: list[str] = []
    if not expected_type:
        issues.append("wrong_type")
    if not symlink_ok:
        issues.append("symlink")
    if not owner_ok:
        issues.append("owner")
    if not mode_ok:
        issues.append("broader_permissions")
    if not writable:
        issues.append("not_writable")
    return PermissionReport(
        path=path,
        exists=True,
        owner_ok=owner_ok,
        mode_ok=mode_ok,
        symlink_ok=symlink_ok,
        writable=writable,
        issues=tuple(issues),
    )


def secure_mode(path: Path, *, directory: bool) -> None:
    """Apply owner-only mode to a path after rejecting symlinks."""

    path = Path(path)
    try:
        info = path.lstat()
    except OSError as error:
        raise PermissionSecurityError("cannot inspect permission target") from error
    if stat.S_ISLNK(info.st_mode):
        raise PermissionSecurityError("refusing to chmod a symlink")
    if not _owner_ok(info):
        raise PermissionSecurityError("permission target is not owned by the current user")
    if os.name != "nt":
        os.chmod(path, 0o700 if directory else 0o600)


def ensure_new_owner_only(path: Path, *, directory: bool) -> None:
    """Apply the initial owner-only mode to a newly created path only."""

    path = Path(path)
    report = check_permissions(path, directory=directory)
    if not report.exists:
        raise PermissionSecurityError("permission target disappeared")
    if os.name != "nt" and report.mode_ok:
        return
    secure_mode(path, directory=directory)


def require_writable(report: PermissionReport) -> None:
    """Raise a stable error when durable writes are not safe."""

    if not report.write_allowed:
        reason = ",".join(report.issues) or "not_write_ready"
        raise PermissionSecurityError(f"durable writes disabled: {reason}")


class PermissionManager:
    """Small cross-platform abstraction used by persistence repositories."""

    def root_report(self, root: Path) -> PermissionReport:
        return check_permissions(root, directory=True)

    def file_report(self, path: Path) -> PermissionReport:
        return check_permissions(path, directory=False)

    def write_ready(self, root: Path) -> bool:
        return self.root_report(root).write_allowed

    def repair_directory(self, path: Path) -> PermissionReport:
        secure_mode(path, directory=True)
        return check_permissions(path, directory=True)

    def repair_file(self, path: Path) -> PermissionReport:
        secure_mode(path, directory=False)
        return check_permissions(path, directory=False)
