"""Bounded text inputs and sole-writer candidate publication."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Callable

MAX_FILE = 262144
MAX_FILES = 8388608


class BoundaryError(ValueError):
    """A fixed public reason; never interpolate caller content."""


def encoded(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def identity(value: Any) -> str:
    return digest(encoded(value))


def relative(value: str, *, artifact: bool = False) -> str:
    parts = PurePosixPath(value).parts
    if (
        not parts
        or value != "/".join(parts)
        or value.startswith("/")
        or "\\" in value
        or ":" in value
        or any(part in (".", "..") or part.startswith(".") for part in parts)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        or unicodedata.normalize("NFC", value) != value
        or (artifact and parts[0].casefold() in {"inputs", "control"})
    ):
        raise BoundaryError("unsafe_path")
    return value


def root_path(value: str, *, existing: bool = True) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise BoundaryError("unsafe_root")
    # System aliases such as /var -> /private/var are canonicalized. Explicit
    # workspace/output leaf links and every path beneath a root are rejected.
    if path.is_symlink():
        raise BoundaryError("unsafe_root")
    path = path.resolve(strict=existing)
    if existing and not path.is_dir():
        raise BoundaryError("root_unavailable")
    return path


def checked_path(root: Path, name: str) -> Path:
    relative(name)
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            raise BoundaryError("unsafe_path")
        if path.exists() and path != root / name and not path.is_dir():
            raise BoundaryError("unsafe_path")
    if not path.is_relative_to(root):
        raise BoundaryError("unsafe_path")
    return path


def read_text(root: Path, name: str) -> bytes:
    path = checked_path(root, name)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE:
            raise BoundaryError("unsafe_or_oversized_file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_FILE + 1)
        after = os.fstat(fd)
        if len(data) > MAX_FILE or (info.st_size, info.st_mtime_ns, info.st_ino) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ino,
        ):
            raise BoundaryError("source_changed")
        data.decode("utf-8")
        if b"\x00" in data:
            raise BoundaryError("binary_input")
        return data
    finally:
        os.close(fd)


def write_files(root: Path, files: dict[str, bytes]) -> None:
    if sum(map(len, files.values())) > MAX_FILES:
        raise BoundaryError("artifact_budget")
    for name, data in files.items():
        path = checked_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)


def manifest(files: dict[str, bytes]) -> list[dict[str, Any]]:
    return [
        {"path": name, "sha256": digest(data), "bytes": len(data)}
        for name, data in sorted(files.items())
    ]


def verify_files(root: Path, files: dict[str, bytes]) -> bool:
    try:
        return all(read_text(root, name) == data for name, data in files.items())
    except (OSError, ValueError):
        return False


def ownership(paths: list[str]) -> None:
    seen: list[str] = []
    for name in paths:
        key = relative(name, artifact=True).casefold()
        if any(
            key == old or key.startswith(old + "/") or old.startswith(key + "/") for old in seen
        ):
            raise BoundaryError("overlapping_ownership")
        seen.append(key)


def _required_file_flag(name: str) -> int:
    value: object = getattr(os, name, None)
    if type(value) is not int or value <= 0:
        raise BoundaryError("directory_capability_unavailable")
    return value


def _directory_identity(info: os.stat_result) -> tuple[int, int]:
    if not stat.S_ISDIR(info.st_mode):
        raise BoundaryError("unsafe_directory")
    return info.st_dev, info.st_ino


def _canonical_directory(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise BoundaryError("unsafe_root")
    # Resolve only the operating system's known aliases, before holding the
    # ancestry. User-controlled ancestor links are not authorization.
    aliases = {"/tmp": "/private/tmp", "/var": "/private/var", "/etc": "/private/etc"}
    current = Path("/")
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            target = os.readlink(current)
            expected = aliases.get(str(current))
            if expected is None or target not in {expected, expected.lstrip("/")}:
                raise BoundaryError("unsafe_directory_ancestor")
            current = Path(expected)
    return current


class BoundDirectory:
    """Held POSIX directory ancestry; never reopen a caller path for a write."""

    def __init__(self, value: str) -> None:
        self.entries: list[tuple[str, int, tuple[int, int]]] = []
        self.path = Path(value)
        if (
            os.name != "posix"
            or not hasattr(os, "O_NOFOLLOW")
            or not hasattr(os, "O_DIRECTORY")
            or not {os.open, os.mkdir, os.stat} <= os.supports_dir_fd
            or os.stat not in os.supports_follow_symlinks
        ):
            raise BoundaryError("directory_capability_unavailable")
        self.path = _canonical_directory(value)
        try:
            self._append("/", os.open("/", self._flags()))
            for name in self.path.parts[1:]:
                self._append(name, os.open(name, self._flags(), dir_fd=self.fd))
            self.verify()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _flags() -> int:
        return (
            os.O_RDONLY
            | _required_file_flag("O_DIRECTORY")
            | _required_file_flag("O_NOFOLLOW")
            | getattr(os, "O_CLOEXEC", 0)
        )

    def _append(self, name: str, descriptor: int) -> None:
        try:
            self.entries.append((name, descriptor, _directory_identity(os.fstat(descriptor))))
        except BaseException:
            os.close(descriptor)
            raise

    @property
    def fd(self) -> int:
        if not self.entries:
            raise BoundaryError("closed_directory_capability")
        return self.entries[-1][1]

    def verify(self) -> None:
        for index, (name, descriptor, expected) in enumerate(self.entries):
            current = os.stat(
                name, dir_fd=self.entries[index - 1][1] if index else None, follow_symlinks=False
            )
            if (
                _directory_identity(current) != expected
                or _directory_identity(os.fstat(descriptor)) != expected
            ):
                raise BoundaryError("directory_identity_changed")
        if not self.entries:
            raise BoundaryError("closed_directory_capability")

    def child(self, name: str, *, create: bool = False) -> BoundDirectory:
        if relative(name) != name or "/" in name:
            raise BoundaryError("unsafe_directory_component")
        self.verify()
        if create:
            os.mkdir(name, mode=0o700, dir_fd=self.fd)
        expected = _directory_identity(os.stat(name, dir_fd=self.fd, follow_symlinks=False))
        child = object.__new__(BoundDirectory)
        child.entries = []
        child.path = self.path / name
        try:
            for component, descriptor, _ in self.entries:
                child._append(component, os.dup(descriptor))
            child._append(name, os.open(name, self._flags(), dir_fd=self.fd))
            if child.entries[-1][2] != expected:
                raise BoundaryError("directory_identity_changed")
            child.verify()
            return child
        except BaseException:
            child.close()
            raise

    def read(self, name: str) -> bytes:
        from contextlib import ExitStack

        relative(name)
        with ExitStack() as cleanup:
            directory = self
            for component in PurePosixPath(name).parts[:-1]:
                directory = directory.child(component)
                cleanup.callback(directory.close)
            directory.verify()
            descriptor = os.open(
                PurePosixPath(name).name,
                os.O_RDONLY | _required_file_flag("O_NOFOLLOW"),
                dir_fd=directory.fd,
            )
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE:
                    raise BoundaryError("unsafe_or_oversized_file")
                with os.fdopen(descriptor, "rb", closefd=False) as stream:
                    data = stream.read(MAX_FILE + 1)
                directory.verify()
                current = os.stat(
                    PurePosixPath(name).name, dir_fd=directory.fd, follow_symlinks=False
                )
                if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                    info.st_dev,
                    info.st_ino,
                    info.st_size,
                    info.st_mtime_ns,
                ):
                    raise BoundaryError("source_changed")
                data.decode("utf-8")
                if len(data) > MAX_FILE or b"\x00" in data:
                    raise BoundaryError("source_size_or_type")
                return data
            finally:
                os.close(descriptor)

    def close(self) -> None:
        interrupted = False
        while self.entries:
            _, descriptor, _ = self.entries.pop()
            try:
                os.close(descriptor)
            except KeyboardInterrupt:
                interrupted = True
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            except OSError:
                pass
        if interrupted:
            raise KeyboardInterrupt

    def __del__(self) -> None:
        try:
            self.close()
        except BaseException:
            pass


def write_bound_files(
    root: BoundDirectory,
    files: dict[str, bytes],
    guard: Callable[[], None],
    started: Callable[[str], None],
    completed: Callable[[str, bytes], None],
) -> None:
    """Create only new owned descendants through held, non-following handles."""
    from contextlib import ExitStack

    if sum(map(len, files.values())) > MAX_FILES:
        raise BoundaryError("artifact_budget")
    directories = {"": root}
    with ExitStack() as cleanup:
        for name, data in files.items():
            relative(name)
            guard()
            directory, prefix = root, ""
            for component in PurePosixPath(name).parts[:-1]:
                prefix = prefix + "/" + component if prefix else component
                if prefix not in directories:
                    directories[prefix] = directory.child(component, create=True)
                    cleanup.callback(directories[prefix].close)
                directory = directories[prefix]
            directory.verify()
            started(name)
            descriptor = os.open(
                PurePosixPath(name).name,
                os.O_RDWR | os.O_CREAT | os.O_EXCL | _required_file_flag("O_NOFOLLOW"),
                0o600,
                dir_fd=directory.fd,
            )
            try:
                _write_bound_file(directory, PurePosixPath(name).name, descriptor, data, guard)
                completed(name, data)
            finally:
                os.close(descriptor)


def _write_bound_file(
    directory: BoundDirectory, name: str, descriptor: int, data: bytes, guard: Callable[[], None]
) -> None:
    offset = 0
    info = os.fstat(descriptor)
    while offset < len(data):
        guard()
        directory.verify()
        current = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(current.st_mode)
            or current.st_nlink != 1
            or (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino)
        ):
            raise BoundaryError("publication_file_changed")
        written = os.write(descriptor, data[offset:])
        if not written:
            raise BoundaryError("publication_write_incomplete")
        offset += written
    guard()
    directory.verify()
    current = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
    if (
        not stat.S_ISREG(current.st_mode)
        or current.st_nlink != 1
        or (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino)
    ):
        raise BoundaryError("publication_file_changed")
    os.lseek(descriptor, 0, os.SEEK_SET)
    if os.read(descriptor, len(data) + 1) != data:
        raise BoundaryError("publication_changed")
