"""Bounded text inputs and sole-writer candidate publication."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

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
