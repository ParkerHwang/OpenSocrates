"""Canonical JSON and same-directory atomic file primitives."""

from __future__ import annotations

import json
import math
import os
import stat
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from .permissions import PermissionSecurityError, check_permissions


class AtomicWriteError(OSError):
    """Raised when a safe atomic write cannot complete."""


class JsonDocument(Protocol):
    """Typed serializer accepted by :func:`atomic_write_document`."""

    def to_json_value(self) -> object:
        """Return a schema-validated JSON-compatible value."""


def _validate_json_value(value: object, *, depth: int = 0) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if depth > 12:
        raise ValueError("JSON nesting exceeds the runtime limit")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            if "\x00" in key:
                raise ValueError("NUL is not allowed in JSON keys")
            _validate_json_value(child, depth=depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        for child in value:
            _validate_json_value(child, depth=depth + 1)
        return
    raise TypeError("unsupported JSON value")


def canonical_json_bytes(value: object, *, max_bytes: int | None = None) -> bytes:
    """Encode a validated value as compact sorted-key JSON followed by LF."""

    _validate_json_value(value)
    encoded = (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    if max_bytes is not None and len(encoded) > max_bytes:
        raise ValueError("canonical JSON exceeds the configured size limit")
    return encoded


def decode_json_bytes(data: bytes, *, max_bytes: int | None = None) -> object:
    """Decode strict UTF-8 JSON after enforcing a byte limit."""

    if max_bytes is not None and len(data) > max_bytes:
        raise ValueError("JSON exceeds the configured size limit")
    if not data.endswith(b"\n"):
        raise ValueError("JSON document must end with LF")
    try:
        value = json.loads(data[:-1].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid canonical JSON") from error
    _validate_json_value(value)
    return value


def _reject_symlink(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    except OSError as error:
        raise AtomicWriteError("cannot inspect atomic-write destination") from error
    if stat.S_ISLNK(info.st_mode):
        raise AtomicWriteError("atomic-write destination may not be a symlink")


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_replace_bytes(path: Path, data: bytes) -> None:
    """Replace one file atomically using an exclusive same-directory temp."""

    path = Path(path)
    directory = path.parent
    if not directory.is_absolute() or not directory.is_dir():
        raise AtomicWriteError("atomic-write parent is unavailable")
    _reject_symlink(directory)
    _reject_symlink(path)
    temporary: Path | None = None
    fd: int | None = None
    try:
        fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=directory)
        temporary = Path(name)
        os.fchmod(fd, 0o600) if hasattr(os, "fchmod") else None
        with os.fdopen(fd, "wb", buffering=0) as handle:
            fd = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _reject_symlink(temporary)
        os.replace(temporary, path)
        temporary = None
        _fsync_directory(directory)
    except (OSError, ValueError) as error:
        raise AtomicWriteError("atomic file replacement failed") from error
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def atomic_write_document(
    path: Path, document: JsonDocument, *, max_bytes: int | None = None
) -> None:
    """Serialize a typed document and atomically replace its destination."""

    try:
        encoded = canonical_json_bytes(document.to_json_value(), max_bytes=max_bytes)
    except (TypeError, ValueError) as error:
        raise AtomicWriteError("typed document is not valid canonical JSON") from error
    atomic_replace_bytes(path, encoded)


def atomic_write_json(path: Path, document: JsonDocument, *, max_bytes: int | None = None) -> None:
    """Write a typed JSON document using the atomic replacement primitive."""

    atomic_write_document(path, document, max_bytes=max_bytes)


def read_bytes(path: Path, *, max_bytes: int) -> bytes:
    """Read a bounded owner-only file without following its final symlink."""

    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise AtomicWriteError("unable to read persistence file") from error
    try:
        info = os.fstat(fd)
        if stat.S_ISLNK(info.st_mode):
            raise AtomicWriteError("persistence file may not be a symlink")
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            block = os.read(fd, min(64 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        data = b"".join(chunks)
        if len(data) > max_bytes:
            raise AtomicWriteError("persistence file exceeds the configured size")
        return data
    finally:
        os.close(fd)


def append_fsync(path: Path, line: bytes, *, max_bytes: int) -> None:
    """Append one already-canonical LF-terminated line and fsync it."""

    if not line.endswith(b"\n") or len(line) > max_bytes:
        raise AtomicWriteError("invalid append line")
    path = Path(path)
    _reject_symlink(path)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as error:
        raise AtomicWriteError("unable to open append record") from error
    try:
        report = check_permissions(path, directory=False)
        if not report.write_allowed:
            raise PermissionSecurityError("append path is not owner-only")
        written = os.write(fd, line)
        if written != len(line):
            raise AtomicWriteError("short append write")
        os.fsync(fd)
    except (OSError, PermissionSecurityError) as error:
        if isinstance(error, AtomicWriteError):
            raise
        raise AtomicWriteError("append fsync failed") from error
    finally:
        os.close(fd)
