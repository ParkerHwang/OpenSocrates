"""Bounded installed-package integrity checks for the diagnose command."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..version import CONTENT_REVISION, PRODUCT_VERSION

_CHECKSUMS_FILENAME = "checksums.sha256"
_RELEASE_MANIFEST_FILENAME = "release-manifest.json"
_RELEASE_MANIFEST_SCHEMA = "opensocrates.plugin-release-manifest/1.0.0"
_HOSTS = frozenset({"claude", "codex"})
_CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([^\x00\r\n]+)$")
_MAX_ANCESTORS = 8
_MAX_MANIFEST_BYTES = 8 * 1024 * 1024
_MAX_FILES = 100_000
_MAX_TOTAL_BYTES = 512 * 1024 * 1024
_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class RuntimeIntegrity:
    """Content-free integrity result safe for the public diagnose projection."""

    manifest_status: str = "unavailable"
    manifest_version: str | None = None
    checksum_status: str = "unavailable"


def _regular_file(path: Path, *, maximum: int | None = None) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise OSError("integrity input is not a regular file")
    if maximum is not None and info.st_size > maximum:
        raise OSError("integrity input exceeds its bound")
    return info


def _read_bounded(path: Path, *, maximum: int) -> bytes:
    _regular_file(path, maximum=maximum)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    chunks: list[bytes] = []
    remaining = maximum + 1
    try:
        while remaining > 0:
            chunk = os.read(descriptor, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    data = b"".join(chunks)
    if len(data) > maximum:
        raise OSError("integrity input exceeds its bound")
    return data


def _plugin_root(executable: str | Path | None) -> Path | None:
    try:
        binary = Path(executable or sys.executable).resolve(strict=True)
    except (OSError, TypeError, ValueError):
        return None
    for candidate in tuple(binary.parents)[:_MAX_ANCESTORS]:
        try:
            info = candidate.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                continue
            if (candidate / _CHECKSUMS_FILENAME).is_file() and (
                candidate / _RELEASE_MANIFEST_FILENAME
            ).is_file():
                return candidate
        except OSError:
            continue
    return None


def _manifest_result(root: Path, host: str | None) -> tuple[str, str | None]:
    try:
        decoded = json.loads(
            _read_bounded(
                root / _RELEASE_MANIFEST_FILENAME,
                maximum=_MAX_MANIFEST_BYTES,
            ).decode("utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return "unavailable", None
    if not isinstance(decoded, dict):
        return "unverified", None
    version = decoded.get("product_version")
    manifest_host = decoded.get("host")
    revision = decoded.get("content_revision")
    safe_version = (
        version
        if isinstance(version, str)
        and version.isascii()
        and 0 < len(version) <= 64
        and "\x00" not in version
        else None
    )
    if (
        decoded.get("schema") != _RELEASE_MANIFEST_SCHEMA
        or safe_version is None
        or manifest_host not in _HOSTS
        or not isinstance(revision, int)
        or isinstance(revision, bool)
        or revision < 1
    ):
        return "unverified", safe_version
    matches_runtime = (
        safe_version == PRODUCT_VERSION
        and (host is None or manifest_host == host)
        and revision == CONTENT_REVISION
    )
    return ("verified" if matches_runtime else "mismatch"), safe_version


def _checksum_entries(root: Path) -> dict[str, str] | None:
    try:
        text = _read_bounded(
            root / _CHECKSUMS_FILENAME,
            maximum=_MAX_MANIFEST_BYTES,
        ).decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    entries: dict[str, str] = {}
    lines = text.splitlines()
    if not lines or len(lines) > _MAX_FILES:
        return None
    for line in lines:
        matched = _CHECKSUM_LINE.fullmatch(line)
        if matched is None:
            return None
        digest, raw_path = matched.groups()
        relative = PurePosixPath(raw_path)
        if (
            relative.is_absolute()
            or "\\" in raw_path
            or any(part in {"", ".", ".."} for part in relative.parts)
            or relative.as_posix() != raw_path
            or raw_path == _CHECKSUMS_FILENAME
            or raw_path in entries
        ):
            return None
        entries[raw_path] = digest
    return entries


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        while True:
            chunk = os.read(descriptor, _CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def _inventory(root: Path) -> set[str] | None:
    files: set[str] = set()
    visited = 0
    try:
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            parent = Path(directory)
            for name in dirnames:
                visited += 1
                if visited > _MAX_FILES:
                    return None
                info = (parent / name).lstat()
                if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                    return None
            for name in filenames:
                visited += 1
                if visited > _MAX_FILES:
                    return None
                path = parent / name
                _regular_file(path)
                relative = path.relative_to(root).as_posix()
                if relative != _CHECKSUMS_FILENAME:
                    files.add(relative)
    except (OSError, ValueError):
        return None
    return files


def _checksum_result(root: Path) -> str:
    entries = _checksum_entries(root)
    if entries is None:
        return "unavailable"
    inventory = _inventory(root)
    if inventory is None:
        return "unavailable"
    if inventory != set(entries):
        return "mismatch"
    total_bytes = 0
    try:
        for raw_path, expected in entries.items():
            path = root.joinpath(*PurePosixPath(raw_path).parts)
            info = _regular_file(path)
            total_bytes += max(0, int(info.st_size))
            if total_bytes > _MAX_TOTAL_BYTES or _sha256(path) != expected:
                return "mismatch"
    except OSError:
        return "mismatch"
    return "verified"


def verify_runtime_integrity(
    *, host: str | None = None, executable: str | Path | None = None
) -> RuntimeIntegrity:
    """Verify one installed package without exposing paths or filenames."""

    selected_host = host if host in _HOSTS else None
    root = _plugin_root(executable)
    if root is None:
        return RuntimeIntegrity()
    manifest_status, manifest_version = _manifest_result(root, selected_host)
    return RuntimeIntegrity(
        manifest_status=manifest_status,
        manifest_version=manifest_version,
        checksum_status=_checksum_result(root),
    )


__all__ = ["RuntimeIntegrity", "verify_runtime_integrity"]
