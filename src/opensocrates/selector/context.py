"""Bounded, read-only context access for one selector turn.

Raw context stays behind this capability.  The selector receives only
availability metadata until it explicitly calls the capability; paths are
never included in the model input or tool result.
"""

from __future__ import annotations

import os
import stat
import threading
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path, PurePath

from .models import SelectorConfig, SelectorRequest

MAX_CONTEXT_CALLS = 8
MAX_CONTEXT_READ_BYTES = 32 * 1024
MAX_CONTEXT_TOTAL_BYTES = 256 * 1024
MAX_CONTEXT_DIRECTORY_ENTRIES = 128
_MAX_RELATIVE_PATH_BYTES = 4096


class ContextAccessError(ValueError):
    """Raised for an invalid context capability definition."""


class ContextKind(StrEnum):
    """The only non-web context classes available to the selector."""

    TRANSCRIPT = "transcript"
    WORKSPACE = "workspace"
    REFERENCED_FILES = "referenced_files"
    TOOL_DATA = "tool_data"


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class SelectorContextHandles:
    """Opaque, read-only handles permitted for one selector request."""

    transcript_path: Path | None = field(default=None, repr=False)
    cwd: Path | None = field(default=None, repr=False)
    transcript_referenced_file_paths: tuple[Path, ...] = field(default=(), repr=False)
    tool_data_handle: object | None = field(default=None, repr=False, compare=False)
    transcript_access_enabled: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.transcript_access_enabled, bool):
            raise ContextAccessError("transcript_access_enabled must be boolean")
        if not isinstance(self.transcript_referenced_file_paths, tuple):
            raise ContextAccessError("referenced-file handles must be an immutable tuple")
        if not self.transcript_access_enabled and (
            self.transcript_path is not None or self.transcript_referenced_file_paths
        ):
            raise ContextAccessError("transcript opt-out forbids transcript-derived handles")

    def permits(self, kind: ContextKind) -> bool:
        """Return whether one approved handle class is available for on-demand reading."""

        if kind is ContextKind.TRANSCRIPT:
            return self.transcript_access_enabled and self.transcript_path is not None
        if kind is ContextKind.WORKSPACE:
            return self.cwd is not None
        if kind is ContextKind.REFERENCED_FILES:
            return self.transcript_access_enabled and bool(self.transcript_referenced_file_paths)
        if kind is ContextKind.TOOL_DATA:
            return self.tool_data_handle is not None
        return False

    def __repr__(self) -> str:
        return "SelectorContextHandles(<transient-redacted>)"


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class UntrustedContext:
    """A raw on-demand context value that must never become selector instructions."""

    kind: ContextKind
    value: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ContextKind):
            raise ContextAccessError("context kind must be closed")

    def __repr__(self) -> str:
        return f"UntrustedContext(kind={self.kind.value!r}, value=<redacted>)"


def _relative_parts(value: str, *, allow_empty: bool) -> tuple[str, ...] | None:
    if not isinstance(value, str) or "\x00" in value:
        return None
    try:
        if len(value.encode("utf-8")) > _MAX_RELATIVE_PATH_BYTES:
            return None
    except UnicodeError:
        return None
    path = PurePath(value)
    if path.is_absolute():
        return None
    parts = path.parts
    if not parts and allow_empty:
        return ()
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return tuple(parts)


def _open_flags(*, directory: bool) -> int | None:
    required: tuple[str, ...] = ("O_CLOEXEC", "O_NOFOLLOW")
    if directory:
        required += ("O_DIRECTORY",)
    if any(not hasattr(os, name) for name in required):
        return None
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    if directory:
        flags |= os.O_DIRECTORY
    return flags


def _open_exact(path: Path, *, directory: bool) -> int | None:
    flags = _open_flags(directory=directory)
    if os.name != "posix" or not path.is_absolute() or flags is None:
        return None
    parent_descriptor: int | None = None
    descriptor: int | None = None
    try:
        if path == Path(path.anchor):
            descriptor = os.open(path, flags)
        else:
            parent = path.parent.resolve(strict=True)
            parent_flags = _open_flags(directory=True)
            if parent_flags is None:
                return None
            parent_descriptor = os.open(parent, parent_flags)
            descriptor = os.open(path.name, flags, dir_fd=parent_descriptor)
        info = os.fstat(descriptor)
    except (OSError, RuntimeError):
        if descriptor is not None:
            os.close(descriptor)
        return None
    finally:
        if parent_descriptor is not None:
            os.close(parent_descriptor)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode):
        os.close(descriptor)
        return None
    result = descriptor
    descriptor = None
    return result


def _open_beneath(root: Path, parts: tuple[str, ...], *, directory: bool) -> int | None:
    if root == Path(root.anchor):
        return None
    descriptor = _open_exact(root, directory=True)
    if descriptor is None:
        return None
    try:
        for index, part in enumerate(parts):
            is_directory = directory or index < len(parts) - 1
            flags = _open_flags(directory=is_directory)
            if flags is None:
                return None
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        info = os.fstat(descriptor)
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(info.st_mode):
            return None
        result = descriptor
        descriptor = -1
        return result
    except OSError:
        return None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _decode_utf8_chunk(data: bytes) -> tuple[str, int] | None:
    candidate = data
    for _ in range(4):
        try:
            return candidate.decode("utf-8"), len(candidate)
        except UnicodeDecodeError as exc:
            if exc.end != len(candidate) or exc.reason != "unexpected end of data":
                return None
            candidate = candidate[:-1]
    return None


def _directory_entry_kind(entry: os.DirEntry[str]) -> str:
    if entry.is_file(follow_symlinks=False):
        return "file"
    if entry.is_dir(follow_symlinks=False):
        return "directory"
    if entry.is_symlink():
        return "symlink"
    return "other"


def _scan_directory(
    descriptor: int,
    *,
    bytes_remaining: int,
) -> tuple[list[dict[str, str]], bool, int] | None:
    entries: list[dict[str, str]] = []
    encoded_bytes = 0
    try:
        with os.scandir(descriptor) as iterator:
            for entry in iterator:
                if len(entries) >= MAX_CONTEXT_DIRECTORY_ENTRIES:
                    return entries, True, encoded_bytes
                try:
                    name_bytes = len(entry.name.encode("utf-8"))
                except UnicodeError:
                    return None
                if encoded_bytes + name_bytes > bytes_remaining:
                    return entries, True, encoded_bytes
                entries.append({"kind": _directory_entry_kind(entry), "name": entry.name})
                encoded_bytes += name_bytes
    except OSError:
        return None
    return entries, False, encoded_bytes


class SelectorContextAccessor:
    """One-turn, bounded context capability used by the SDK dynamic tool.

    Construction stores opaque handles only.  Filesystem access happens only
    after one of the explicit read methods is called.  Workspace paths are
    relative, traversed component-by-component with ``O_NOFOLLOW``, and never
    allowed to escape the authorized root.
    """

    __slots__ = ("_bytes_used", "_calls", "_handles", "_lock")

    def __init__(self, handles: SelectorContextHandles) -> None:
        if not isinstance(handles, SelectorContextHandles):
            raise ContextAccessError("expected selector context handles")
        self._handles = handles
        self._calls = 0
        self._bytes_used = 0
        self._lock = threading.Lock()

    @property
    def calls(self) -> int:
        """Return the privacy-safe count of attempted context operations."""

        with self._lock:
            return self._calls

    @property
    def bytes_read(self) -> int:
        """Return the privacy-safe count of context bytes released this turn."""

        with self._lock:
            return self._bytes_used

    def available_operations(self) -> tuple[str, ...]:
        """Return capability names without inspecting or opening their targets."""

        operations: list[str] = []
        if self._handles.permits(ContextKind.TRANSCRIPT):
            operations.append("read_transcript")
        if self._handles.permits(ContextKind.WORKSPACE):
            operations.extend(("list_workspace", "read_workspace_file"))
        if self._handles.permits(ContextKind.REFERENCED_FILES):
            operations.append("read_referenced_file")
        # Native UserPromptSubmit does not provide a bounded tool-data capability.
        # Prior tool results remain available only if the permitted transcript contains them.
        return tuple(operations)

    def _begin_call(self) -> bool:
        if self._calls >= MAX_CONTEXT_CALLS:
            return False
        self._calls += 1
        return True

    def _read_descriptor(
        self,
        descriptor: int,
        *,
        kind: ContextKind,
        offset: int,
    ) -> UntrustedContext | None:
        if type(offset) is not int or offset < 0:
            return None
        remaining = MAX_CONTEXT_TOTAL_BYTES - self._bytes_used
        if remaining <= 0:
            return None
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or offset > info.st_size:
                return None
            requested = min(MAX_CONTEXT_READ_BYTES, remaining)
            data = os.pread(descriptor, requested, offset)
        except OSError:
            return None
        decoded = _decode_utf8_chunk(data)
        if decoded is None:
            return None
        text, consumed = decoded
        self._bytes_used += consumed
        next_offset = offset + consumed
        return UntrustedContext(
            kind=kind,
            value={
                "data": text,
                "has_more": next_offset < info.st_size,
                "next_offset": next_offset,
                "offset": offset,
            },
        )

    def _read_exact_file(
        self,
        path: Path,
        *,
        kind: ContextKind,
        offset: int,
    ) -> UntrustedContext | None:
        descriptor = _open_exact(path, directory=False)
        if descriptor is None:
            return None
        try:
            return self._read_descriptor(descriptor, kind=kind, offset=offset)
        finally:
            os.close(descriptor)

    def read_transcript(self, *, offset: int = 0) -> UntrustedContext | None:
        """Read one UTF-8 chunk from the exact transcript handle."""

        with self._lock:
            path = self._handles.transcript_path
            if not self._begin_call() or not self._handles.permits(ContextKind.TRANSCRIPT):
                return None
            if path is None:
                return None
            return self._read_exact_file(path, kind=ContextKind.TRANSCRIPT, offset=offset)

    def read_workspace_file(
        self, relative_path: str, *, offset: int = 0
    ) -> UntrustedContext | None:
        """Read one UTF-8 chunk from a contained, non-symlink workspace file."""

        with self._lock:
            if not self._begin_call() or not self._handles.permits(ContextKind.WORKSPACE):
                return None
            parts = _relative_parts(relative_path, allow_empty=False)
            root = self._handles.cwd
            if parts is None or root is None:
                return None
            descriptor = _open_beneath(root, parts, directory=False)
            if descriptor is None:
                return None
            try:
                return self._read_descriptor(
                    descriptor,
                    kind=ContextKind.WORKSPACE,
                    offset=offset,
                )
            finally:
                os.close(descriptor)

    def list_workspace(self, relative_directory: str = "") -> UntrustedContext | None:
        """List a bounded set of contained workspace entries without following links."""

        with self._lock:
            if not self._begin_call() or not self._handles.permits(ContextKind.WORKSPACE):
                return None
            parts = _relative_parts(relative_directory, allow_empty=True)
            root = self._handles.cwd
            if parts is None or root is None:
                return None
            descriptor = _open_beneath(root, parts, directory=True)
            if descriptor is None:
                return None
            try:
                scanned = _scan_directory(
                    descriptor,
                    bytes_remaining=MAX_CONTEXT_TOTAL_BYTES - self._bytes_used,
                )
            finally:
                os.close(descriptor)
            if scanned is None:
                return None
            entries, has_more, encoded_bytes = scanned
            entries.sort(key=lambda entry: entry["name"])
            self._bytes_used += encoded_bytes
            return UntrustedContext(
                kind=ContextKind.WORKSPACE,
                value={"entries": entries, "has_more": has_more},
            )

    def read_referenced_file(self, index: int, *, offset: int = 0) -> UntrustedContext | None:
        """Read one exact transcript-referenced file by opaque numeric index."""

        with self._lock:
            paths = self._handles.transcript_referenced_file_paths
            if not self._begin_call() or not self._handles.permits(ContextKind.REFERENCED_FILES):
                return None
            if type(index) is not int or index < 0 or index >= len(paths):
                return None
            return self._read_exact_file(
                paths[index],
                kind=ContextKind.REFERENCED_FILES,
                offset=offset,
            )


ReadOnlyContextAccessor = SelectorContextAccessor


def handles_for_request(
    request: SelectorRequest, config: SelectorConfig
) -> tuple[SelectorRequest, SelectorContextHandles]:
    """Apply transcript opt-out before a request reaches the SDK selector seam."""

    if not isinstance(request, SelectorRequest):
        raise ContextAccessError("expected a selector request")
    if not isinstance(config, SelectorConfig):
        raise ContextAccessError("expected selector configuration")
    effective_request = request
    if not config.transcript_access_enabled:
        effective_request = request.without_transcript_context()
    handles = SelectorContextHandles(
        transcript_path=effective_request.transcript_path,
        cwd=effective_request.cwd,
        transcript_referenced_file_paths=effective_request.transcript_referenced_file_paths,
        tool_data_handle=effective_request.tool_data_handle,
        transcript_access_enabled=config.transcript_access_enabled,
    )
    return effective_request, handles


__all__ = [
    "ContextAccessError",
    "ContextKind",
    "MAX_CONTEXT_CALLS",
    "MAX_CONTEXT_DIRECTORY_ENTRIES",
    "MAX_CONTEXT_READ_BYTES",
    "MAX_CONTEXT_TOTAL_BYTES",
    "ReadOnlyContextAccessor",
    "SelectorContextAccessor",
    "SelectorContextHandles",
    "UntrustedContext",
    "handles_for_request",
]
