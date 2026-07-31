"""Short-lived per-file locks for cross-process persistence updates."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock as ThreadLock
from typing import IO

from .permissions import PermissionSecurityError, check_permissions


class LockTimeoutError(TimeoutError):
    """Raised when the bounded lock policy expires."""


class LockError(OSError):
    """Raised for a lock path that is unsafe or cannot be opened."""


@dataclass(frozen=True, slots=True)
class LockPolicy:
    timeout_seconds: float = 0.5
    poll_seconds: float = 0.01

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0 or self.timeout_seconds > 2:
            raise ValueError("lock timeout must be positive and bounded")
        if self.poll_seconds <= 0 or self.poll_seconds > self.timeout_seconds:
            raise ValueError("lock poll interval is invalid")


def _open_lock(path: Path) -> IO[bytes]:
    path = Path(path)
    flags = os.O_RDWR | os.O_CREAT
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    flags |= no_follow
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as error:
        raise LockError("unable to open persistence lock") from error
    handle = os.fdopen(fd, "r+b", buffering=0)
    try:
        report = check_permissions(path, directory=False)
        if not report.write_allowed:
            raise PermissionSecurityError("lock path is not owner-only")
    except (PermissionError, OSError, PermissionSecurityError) as error:
        handle.close()
        raise LockError("persistence lock is not owner-only") from error
    return handle


class FileLock:
    """Advisory lock backed by an owner-only lock file."""

    def __init__(self, path: Path, *, policy: LockPolicy | None = None) -> None:
        self.path = Path(path)
        self.policy = policy or LockPolicy()
        self._handle: IO[bytes] | None = None
        self._locked = False

    def acquire(self) -> "FileLock":
        if self._locked:
            return self
        handle = _open_lock(self.path)
        deadline = time.monotonic() + self.policy.timeout_seconds
        try:
            while True:
                if _try_lock(handle):
                    self._handle = handle
                    self._locked = True
                    return self
                if time.monotonic() >= deadline:
                    raise LockTimeoutError("persistence lock timeout")
                time.sleep(min(self.policy.poll_seconds, max(0.0, deadline - time.monotonic())))
        except BaseException:
            handle.close()
            raise

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            _unlock(handle)
        finally:
            handle.close()
            self._locked = False

    def __enter__(self) -> "FileLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()


def _try_lock(handle: IO[bytes]) -> bool:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
            return True
        except OSError:
            return False
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle: IO[bytes]) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
        except OSError:
            pass
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class InMemoryLock:
    """Equivalent lock for focused in-memory repository demonstrations."""

    def __init__(self, lock: ThreadLock | None = None, *, policy: LockPolicy | None = None) -> None:
        self._lock = lock or ThreadLock()
        self.policy = policy or LockPolicy()
        self._locked = False

    def acquire(self) -> "InMemoryLock":
        acquired = self._lock.acquire(timeout=self.policy.timeout_seconds)
        if not acquired:
            raise LockTimeoutError("in-memory persistence lock timeout")
        self._locked = True
        return self

    def release(self) -> None:
        if self._locked:
            self._locked = False
            self._lock.release()

    def __enter__(self) -> "InMemoryLock":
        return self.acquire()

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.release()
