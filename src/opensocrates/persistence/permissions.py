"""Owner-only permission checks and write-readiness gates.

Permission failures are represented as a report so callers can continue with
useful in-memory behavior while disabling new durable writes.  No caller is
given a way to bypass the owner-only policy for production state.
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
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


class CreatedOwnerOnlyTempfile:
    """Factory-issued capability for one exclusively created temporary file."""

    __slots__ = (
        "__active",
        "__descriptor",
        "__file_identity",
        "__issuer",
        "__path",
        "__windows_capability",
    )

    def __init__(
        self,
        *,
        descriptor: int,
        path: Path,
        file_identity: tuple[int, int],
        windows_capability: object | None,
        issuer: object,
    ) -> None:
        if issuer is not _TEMPFILE_CAPABILITY_ISSUER:
            raise TypeError("temporary-file capabilities are factory-issued")
        self.__descriptor = descriptor
        self.__path = Path(path)
        self.__file_identity = file_identity
        self.__windows_capability = windows_capability
        self.__issuer: object | None = issuer
        self.__active = True

    @property
    def descriptor(self) -> int:
        return self.__descriptor

    @property
    def path(self) -> Path:
        return self.__path

    @property
    def active(self) -> bool:
        return self.__issuer is _TEMPFILE_CAPABILITY_ISSUER and self.__active

    def _identity(self) -> tuple[int, int]:
        return self.__file_identity

    def _windows(self) -> object | None:
        return self.__windows_capability

    def _consume(self) -> None:
        self.__active = False
        self.__issuer = None


_TEMPFILE_CAPABILITY_ISSUER = object()


def _owner_ok(info: os.stat_result) -> bool:
    if sys.platform == "win32":
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
    symlink_ok = not stat.S_ISLNK(info.st_mode) and not (
        getattr(info, "st_file_attributes", 0) & 0x400
    )
    owner_ok = symlink_ok and _owner_ok(info)
    expected_type = directory == is_directory
    if sys.platform == "win32":
        from .windows_acl import inspect_acl

        try:
            owner_ok, private_acl = inspect_acl(path)
        except OSError:
            owner_ok, private_acl = False, False
        mode_ok = expected_type and private_acl
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
    if sys.platform == "win32":
        from .windows_acl import secure_acl

        secure_acl(path, directory=directory)
        return
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    if directory:
        flags |= getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        opened_is_directory = stat.S_ISDIR(opened.st_mode)
        if (
            opened_is_directory != directory
            or not _owner_ok(opened)
            or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
        ):
            raise PermissionSecurityError("permission target identity changed")
        os.fchmod(descriptor, 0o700 if directory else 0o600)
        refreshed = os.fstat(descriptor)
        named = path.lstat()
        if (
            (refreshed.st_dev, refreshed.st_ino) != (info.st_dev, info.st_ino)
            or stat.S_IMODE(refreshed.st_mode) != (0o700 if directory else 0o600)
            or stat.S_ISLNK(named.st_mode)
            or stat.S_ISDIR(named.st_mode) != directory
            or not _owner_ok(named)
            or stat.S_IMODE(named.st_mode) != (0o700 if directory else 0o600)
            or (named.st_dev, named.st_ino) != (info.st_dev, info.st_ino)
        ):
            raise PermissionSecurityError("permission target mode verification failed")
    finally:
        os.close(descriptor)


def ensure_new_owner_only(path: Path, *, directory: bool) -> None:
    """Apply owner-only mode without granting any new-object owner exception."""

    path = Path(path)
    report = check_permissions(path, directory=directory)
    if not report.exists:
        raise PermissionSecurityError("permission target disappeared")
    if sys.platform == "win32" or not report.mode_ok:
        secure_mode(path, directory=directory)


def create_owner_only_file(path: Path, *, flags: int, share_delete: bool = False) -> int:
    """Exclusively create one owner-only file and return its live descriptor."""

    path = Path(path)
    if sys.platform == "win32":
        from opensocrates.windows_security import create_private_file

        return create_private_file(path, flags=flags, share_delete=share_delete)
    descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
    except OSError:
        discard_created_file(descriptor, path)
        os.close(descriptor)
        raise
    return descriptor


def open_owner_only_file(path: Path, *, flags: int, share_delete: bool = False) -> int:
    """Open one existing owner-only file through a stable Windows handle."""

    path = Path(path)
    if sys.platform == "win32":
        from opensocrates.windows_security import open_private_file

        return open_private_file(path, flags=flags, share_delete=share_delete)
    return os.open(path, flags)


def create_owner_only_tempfile(
    *, prefix: str, suffix: str, directory: Path
) -> CreatedOwnerOnlyTempfile:
    """Create one randomized owner-only temporary file capability."""

    if sys.platform == "win32":
        from opensocrates.windows_security import create_private_tempfile

        native = create_private_tempfile(prefix=prefix, suffix=suffix, directory=directory)
        try:
            info = os.fstat(native.descriptor)
            return CreatedOwnerOnlyTempfile(
                descriptor=native.descriptor,
                path=Path(native.path),
                file_identity=(info.st_dev, info.st_ino),
                windows_capability=native,
                issuer=_TEMPFILE_CAPABILITY_ISSUER,
            )
        except Exception:
            from opensocrates.windows_security import discard_created_private_tempfile

            try:
                discard_created_private_tempfile(native)
            finally:
                os.close(native.descriptor)
            raise
    descriptor, name = tempfile.mkstemp(prefix=prefix, suffix=suffix, dir=directory)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
    except OSError:
        discard_created_file(descriptor, Path(name))
        os.close(descriptor)
        raise
    try:
        info = os.fstat(descriptor)
        return CreatedOwnerOnlyTempfile(
            descriptor=descriptor,
            path=Path(name),
            file_identity=(info.st_dev, info.st_ino),
            windows_capability=None,
            issuer=_TEMPFILE_CAPABILITY_ISSUER,
        )
    except Exception:
        try:
            discard_created_file(descriptor, Path(name))
        finally:
            os.close(descriptor)
        raise


def discard_created_tempfile(created: CreatedOwnerOnlyTempfile) -> None:
    """Delete a live temporary file through its exact creation capability."""

    if type(created) is not CreatedOwnerOnlyTempfile or not created.active:
        return
    try:
        if sys.platform == "win32":
            from opensocrates.windows_security import (
                CreatedPrivateTempfile,
                discard_created_private_tempfile,
            )

            native = created._windows()
            if type(native) is not CreatedPrivateTempfile:
                raise PermissionSecurityError("Windows temporary-file capability is missing")
            discard_created_private_tempfile(native)
        else:
            opened = os.fstat(created.descriptor)
            if (opened.st_dev, opened.st_ino) != created._identity():
                raise PermissionSecurityError("temporary-file descriptor identity changed")
            discard_created_file(created.descriptor, created.path)
    finally:
        created._consume()


def discard_created_file(descriptor: int, path: Path) -> None:
    """Delete only the just-created object still identified by ``descriptor``."""

    if sys.platform == "win32":
        from opensocrates.windows_security import discard_created_file_descriptor

        discard_created_file_descriptor(descriptor)
        return
    try:
        opened = os.fstat(descriptor)
        named = Path(path).lstat()
    except OSError:
        return
    if (
        stat.S_ISREG(opened.st_mode)
        and not stat.S_ISLNK(named.st_mode)
        and opened.st_dev == named.st_dev
        and opened.st_ino == named.st_ino
    ):
        try:
            Path(path).unlink()
        except OSError:
            pass


def replace_created_file(created: CreatedOwnerOnlyTempfile, destination: Path) -> None:
    """Rename only the just-created object represented by a live capability."""

    if type(created) is not CreatedOwnerOnlyTempfile or not created.active:
        raise PermissionSecurityError("temporary-file capability is not active")
    source = created.path
    destination = Path(destination)
    if source.parent != destination.parent:
        raise PermissionSecurityError("atomic replacement must remain in one directory")
    if sys.platform == "win32":
        from opensocrates.windows_security import (
            CreatedPrivateTempfile,
            replace_created_file_descriptor,
        )

        native = created._windows()
        if type(native) is not CreatedPrivateTempfile:
            raise PermissionSecurityError("Windows temporary-file capability is missing")
        replace_created_file_descriptor(native, destination)
        created._consume()
        return
    opened = os.fstat(created.descriptor)
    named = source.lstat()
    if (
        not stat.S_ISREG(opened.st_mode)
        or stat.S_ISLNK(named.st_mode)
        or (opened.st_dev, opened.st_ino) != created._identity()
        or opened.st_dev != named.st_dev
        or opened.st_ino != named.st_ino
    ):
        raise PermissionSecurityError("atomic source no longer identifies the created file")
    os.replace(source, destination)
    created._consume()


def _create_windows_owner_only_directory(path: Path, *, parents: bool) -> bool:
    from opensocrates.windows_security import create_private_directory

    if not parents:
        try:
            create_private_directory(path)
        except FileExistsError:
            return False
        return True
    missing: list[Path] = []
    current = path
    while True:
        try:
            current.lstat()
            break
        except FileNotFoundError:
            missing.append(current)
        parent = current.parent
        if parent == current:
            raise PermissionSecurityError("private directory has no existing ancestor")
        current = parent
    created_final = False
    for directory_path in reversed(missing):
        try:
            create_private_directory(directory_path)
        except FileExistsError as error:
            raise PermissionSecurityError(
                "private directory creation raced with an existing path"
            ) from error
        created_final |= directory_path == path
    return created_final


def create_owner_only_directory(path: Path, *, parents: bool = False) -> bool:
    """Create one private directory, or leave an existing path untouched."""

    path = Path(path)
    if sys.platform == "win32":
        return _create_windows_owner_only_directory(path, parents=parents)
    try:
        path.mkdir(parents=parents, exist_ok=False, mode=0o700)
    except FileExistsError:
        return False
    created_identity: tuple[int, int] | None = None
    try:
        created_info = path.lstat()
        if stat.S_ISLNK(created_info.st_mode) or not stat.S_ISDIR(created_info.st_mode):
            raise PermissionSecurityError("new private directory is not a real directory")
        created_identity = (created_info.st_dev, created_info.st_ino)
        ensure_new_owner_only(path, directory=True)
        final_info = path.lstat()
        if (
            stat.S_ISLNK(final_info.st_mode)
            or not stat.S_ISDIR(final_info.st_mode)
            or not _owner_ok(final_info)
            or stat.S_IMODE(final_info.st_mode) != 0o700
            or (final_info.st_dev, final_info.st_ino) != created_identity
        ):
            raise PermissionSecurityError("new private directory identity changed")
    except OSError:
        try:
            current = path.lstat()
            if (
                created_identity is not None
                and stat.S_ISDIR(current.st_mode)
                and not stat.S_ISLNK(current.st_mode)
                and (current.st_dev, current.st_ino) == created_identity
            ):
                path.rmdir()
        except OSError:
            pass
        raise
    return True


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
