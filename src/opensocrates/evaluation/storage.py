"""Owned, bounded storage. Never traverses host logs or unrelated workspaces."""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .model import LabError

MARKER = "opensocrates.office-lab/1\n"
STATE_LIMIT = 8 * 1024 * 1024


def ensure_plain(path: Path) -> None:
    for component in (path, *path.parents):
        if not component.exists() and not component.is_symlink():
            continue
        entry = component.lstat()
        if stat.S_ISLNK(entry.st_mode) or getattr(entry, "st_file_attributes", 0) & 0x400:
            raise LabError("unsafe_path")


def read_bytes(path: Path, limit: int) -> bytes:
    ensure_plain(path)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NONBLOCK", 0)
    )
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit or info.st_nlink != 1:
                raise LabError("unsafe_file")
            result = stream.read(limit + 1)
        if len(result) > limit:
            raise LabError("too_large")
        return result
    except FileNotFoundError as exc:
        raise LabError("missing_file") from exc


def read_json(path: Path, limit: int = STATE_LIMIT) -> dict[str, Any]:
    try:
        result = json.loads(read_bytes(path, limit))
    except (UnicodeError, ValueError) as exc:
        raise LabError("invalid_json") from exc
    if not isinstance(result, dict):
        raise LabError("invalid_json")
    return result


def atomic_write(path: Path, content: bytes) -> None:
    ensure_plain(path)
    temporary = path.with_name(f".{path.name}.pending")
    ensure_plain(temporary)
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write(path, json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8"))


class Storage:
    def __init__(self, root: Path) -> None:
        self.root = root.absolute()

    def owned(self) -> bool:
        ensure_plain(self.root)
        marker = self.root / ".office-lab"
        if not self.root.exists():
            return False
        if not marker.exists():
            raise LabError("unowned_root")
        if read_bytes(marker, 100) != MARKER.encode():
            raise LabError("unowned_root")
        return True

    def initialize(self) -> None:
        ensure_plain(self.root)
        if self.root.exists():
            raise LabError("root_exists")
        self.root.mkdir(parents=True, mode=0o700)
        atomic_write(self.root / ".office-lab", MARKER.encode())
        for name in ("actors", "approved", "exports", "inputs"):
            (self.root / name).mkdir(mode=0o700)

    @contextmanager
    def locked(self) -> Iterator[None]:
        if not self.owned():
            raise LabError("not_initialized")
        lock = self.root / ".lock"
        ensure_plain(lock)
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise LabError("study_locked") from exc
        try:
            os.close(descriptor)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def load(self) -> dict[str, Any]:
        if not self.owned():
            raise LabError("not_initialized")
        state = read_json(self.root / "state.json")
        if state.get("schema") != "opensocrates.office-state/1":
            raise LabError("invalid_state")
        return state

    def save(self, state: dict[str, Any]) -> None:
        write_json(self.root / "state.json", state)
