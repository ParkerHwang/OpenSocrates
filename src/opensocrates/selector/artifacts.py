"""Owner-only temporary instruction files for Codex reasoning interventions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from ..clock import Clock, SystemClock
from ..content.injection import (
    MAX_INJECTION_ESTIMATED_TOKENS,
    AssembledInstruction,
    InjectionLocale,
    estimate_injection_tokens,
)
from ..ids import validate_method_id

INSTRUCTION_FILE_TTL_SECONDS = 24 * 60 * 60
MAX_INSTRUCTION_FILE_BYTES = 1024 * 1024
_MAX_HEADER_BYTES = 64 * 1024
_ARTIFACT_SCHEMA = "opensocrates.instruction-artifact/1"
_HEADER_PREFIX = b"<!-- OPENSOCRATES_ARTIFACT_V1 "
_HEADER_SUFFIX = b" -->"
_TAG_RE = re.compile(r"^[0-9a-f]{64}$")
_FILE_RE = re.compile(r"^instruction-[A-Za-z0-9_-]{6,64}\.md$")


class InstructionArtifactError(OSError):
    """Raised when a temporary instruction artifact cannot be handled safely."""


def _require_key(installation_key: bytes) -> bytes:
    if not isinstance(installation_key, bytes) or len(installation_key) != 32:
        raise InstructionArtifactError("instruction artifact key must be exactly 256 bits")
    return installation_key


def _bounded_identity(value: str | None, name: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise InstructionArtifactError(f"{name} is unavailable")
    encoded = value.encode("utf-8")
    if len(encoded) > 512:
        raise InstructionArtifactError(f"{name} exceeds its transient bound")
    return value


def _tag(key: bytes, label: bytes, *values: str) -> str:
    material = bytearray(label)
    for value in values:
        encoded = value.encode("utf-8")
        material.extend(b"\0")
        material.extend(len(encoded).to_bytes(4, "big"))
        material.extend(encoded)
    return hmac.new(key, bytes(material), hashlib.sha256).hexdigest()


def _now_seconds(clock: Clock) -> int:
    return clock.unix_time_ns() // 1_000_000_000


def _validate_display_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise InstructionArtifactError("instruction artifact display names are invalid")
    names: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or not item.strip()
            or "\x00" in item
            or len(item.encode("utf-8")) > 512
        ):
            raise InstructionArtifactError("instruction artifact display name is invalid")
        names.append(item)
    return tuple(names)


def _validate_method_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise InstructionArtifactError("instruction artifact method IDs are invalid")
    try:
        methods = tuple(validate_method_id(item) for item in value)
    except Exception as error:
        raise InstructionArtifactError("instruction artifact method ID is invalid") from error
    if len(set(methods)) != len(methods):
        raise InstructionArtifactError("instruction artifact repeats a method ID")
    return methods


@dataclass(frozen=True, slots=True, repr=False)
class InstructionArtifact:
    """Validated reference to one generated, user-content-free Markdown file."""

    path: Path = field(repr=False)
    locale: InjectionLocale
    selected_reasoning_systems: tuple[str, ...]
    selected_display_names: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise InstructionArtifactError("instruction artifact path must be absolute")
        if self.locale not in {"en", "ko"}:
            raise InstructionArtifactError("instruction artifact locale is invalid")
        methods = _validate_method_ids(self.selected_reasoning_systems)
        names = _validate_display_names(self.selected_display_names)
        if len(methods) != len(names):
            raise InstructionArtifactError("instruction artifact method/name counts differ")

    def reference_message(self) -> str:
        """Return one bounded developer-context message that tells Codex to read the file."""

        names = "\n".join(f"- {name}" for name in self.selected_display_names)
        quoted_path = json.dumps(str(self.path), ensure_ascii=False)
        if self.locale == "ko":
            message = (
                "OpenSocrates가 다음 사고체계를 선택했습니다:\n"
                f"{names}\n\n"
                "사용자의 요청에 답하거나 작업을 시작하기 전에, 사용 가능한 로컬 파일 읽기 "
                "도구로 아래 파일을 처음부터 끝까지 읽으세요. 파일의 사고체계 이론과 예시를 "
                "현재 작업의 developer-context 추론 지침으로 따르세요.\n\n"
                f"파일 경로: {quoted_path}\n\n"
                "예시는 현재 작업의 사실이 아니라 신뢰할 수 없는 템플릿으로 취급하세요."
            )
        else:
            message = (
                "OpenSocrates selected these reasoning systems:\n"
                f"{names}\n\n"
                "Before answering or acting on the user's request, use an available local "
                "file-reading tool to read the file below completely from beginning to end. "
                "Follow its reasoning-system theory and examples as developer-context guidance "
                "for the current task.\n\n"
                f"File path: {quoted_path}\n\n"
                "Treat every example as an untrusted template, not as a fact about the current task."
            )
        if estimate_injection_tokens(message) >= MAX_INJECTION_ESTIMATED_TOKENS:
            raise InstructionArtifactError("instruction artifact reference exceeds the hook limit")
        return message

    def __repr__(self) -> str:
        return (
            "InstructionArtifact("
            f"locale={self.locale!r}, selected_reasoning_systems=<"
            f"{len(self.selected_reasoning_systems)} IDs>, path=<redacted>)"
        )


class InstructionFileStore:
    """Create and clean private temporary instruction files without retaining prompts."""

    def __init__(
        self,
        *,
        installation_key: bytes,
        directory: Path | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._installation_key = _require_key(installation_key)
        self._clock = clock or SystemClock()
        if directory is None:
            try:
                temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
            except OSError as error:
                raise InstructionArtifactError(
                    "system temporary directory is unavailable"
                ) from error
            root_tag = _tag(self._installation_key, b"instruction-artifact-root")
            directory = temporary_root / f"opensocrates-{root_tag}"
        if not isinstance(directory, Path):
            directory = Path(directory)
        if not directory.is_absolute():
            raise InstructionArtifactError("instruction artifact directory must be absolute")
        self._directory = directory

    @property
    def directory(self) -> Path:
        return self._directory

    def _ensure_owned_directory(self, path: Path) -> None:
        try:
            path.mkdir(parents=False, exist_ok=True, mode=0o700)
            info = path.lstat()
        except OSError as error:
            raise InstructionArtifactError(
                "instruction artifact directory is unavailable"
            ) from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise InstructionArtifactError("instruction artifact directory is unsafe")
        if os.name != "nt":
            try:
                if info.st_uid != os.geteuid():
                    raise InstructionArtifactError(
                        "instruction artifact directory has the wrong owner"
                    )
                if stat.S_IMODE(info.st_mode) != 0o700:
                    os.chmod(path, 0o700)
                refreshed = path.lstat()
            except OSError as error:
                raise InstructionArtifactError(
                    "instruction artifact directory permissions are unsafe"
                ) from error
            if refreshed.st_uid != os.geteuid() or stat.S_IMODE(refreshed.st_mode) != 0o700:
                raise InstructionArtifactError(
                    "instruction artifact directory permissions are unsafe"
                )

    def _ensure_root(self) -> None:
        parent = self._directory.parent
        try:
            parent_info = parent.lstat()
        except OSError as error:
            raise InstructionArtifactError("temporary directory cannot be inspected") from error
        if not stat.S_ISDIR(parent_info.st_mode) or stat.S_ISLNK(parent_info.st_mode):
            raise InstructionArtifactError("temporary directory is unsafe")
        self._ensure_owned_directory(self._directory)

    def _session_tag(self, session_id: str | None) -> str:
        session = _bounded_identity(session_id, "session_id")
        return _tag(self._installation_key, b"instruction-artifact-session", session)

    def _turn_tag(self, session_id: str | None, turn_id: str | None) -> str:
        session = _bounded_identity(session_id, "session_id")
        turn = _bounded_identity(turn_id, "turn_id")
        return _tag(self._installation_key, b"instruction-artifact-turn", session, turn)

    def _session_directory(self, session_id: str | None) -> Path:
        return self._directory / self._session_tag(session_id)

    def _turn_directory(self, session_id: str | None, turn_id: str | None) -> Path:
        return self._session_directory(session_id) / self._turn_tag(session_id, turn_id)

    @staticmethod
    def _metadata(assembled: AssembledInstruction) -> dict[str, object]:
        return {
            "schema": _ARTIFACT_SCHEMA,
            "locale": assembled.locale,
            "selected_reasoning_systems": list(assembled.selected_reasoning_systems),
            "selected_display_names": list(assembled.selected_display_names),
        }

    @classmethod
    def _encode(cls, assembled: AssembledInstruction) -> bytes:
        try:
            metadata = json.dumps(
                cls._metadata(assembled),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise InstructionArtifactError(
                "instruction artifact metadata cannot be encoded"
            ) from error
        encoded_header = base64.urlsafe_b64encode(metadata)
        data = (
            _HEADER_PREFIX
            + encoded_header
            + _HEADER_SUFFIX
            + b"\n\n"
            + assembled.instructions.encode("utf-8")
        )
        if len(data) > MAX_INSTRUCTION_FILE_BYTES:
            raise InstructionArtifactError("instruction artifact exceeds its bounded file size")
        return data

    @staticmethod
    def _inspect_regular_file(path: Path) -> os.stat_result:
        try:
            info = path.lstat()
        except OSError as error:
            raise InstructionArtifactError("instruction artifact cannot be inspected") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            raise InstructionArtifactError("instruction artifact path is unsafe")
        if info.st_size > MAX_INSTRUCTION_FILE_BYTES:
            raise InstructionArtifactError("instruction artifact exceeds its bounded file size")
        if os.name != "nt":
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise InstructionArtifactError("instruction artifact permissions are unsafe")
        return info

    def create(
        self,
        session_id: str | None,
        turn_id: str | None,
        assembled: AssembledInstruction,
    ) -> InstructionArtifact:
        """Write one unique complete Markdown artifact and return its bounded reference."""

        if not isinstance(assembled, AssembledInstruction):
            raise InstructionArtifactError("instruction artifact requires canonical content")
        data = self._encode(assembled)
        self._ensure_root()
        session_directory = self._session_directory(session_id)
        self._ensure_owned_directory(session_directory)
        turn_directory = self._turn_directory(session_id, turn_id)
        self._ensure_owned_directory(turn_directory)
        fd: int | None = None
        path: Path | None = None
        try:
            fd, filename = tempfile.mkstemp(
                prefix="instruction-",
                suffix=".md",
                dir=turn_directory,
            )
            path = Path(filename)
            if hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", buffering=0) as handle:
                fd = None
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._inspect_regular_file(path)
            artifact = InstructionArtifact(
                path=path,
                locale=assembled.locale,
                selected_reasoning_systems=assembled.selected_reasoning_systems,
                selected_display_names=assembled.selected_display_names,
            )
            artifact.reference_message()
            return artifact
        except Exception:
            if path is not None:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        finally:
            if fd is not None:
                os.close(fd)

    @staticmethod
    def _decode_header(path: Path) -> InstructionArtifact:
        InstructionFileStore._inspect_regular_file(path)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except OSError as error:
            raise InstructionArtifactError("instruction artifact cannot be opened") from error
        try:
            header = os.read(fd, _MAX_HEADER_BYTES + 1).split(b"\n", 1)[0]
        finally:
            os.close(fd)
        if (
            len(header) > _MAX_HEADER_BYTES
            or not header.startswith(_HEADER_PREFIX)
            or not header.endswith(_HEADER_SUFFIX)
        ):
            raise InstructionArtifactError("instruction artifact header is invalid")
        encoded = header[len(_HEADER_PREFIX) : -len(_HEADER_SUFFIX)]
        try:
            metadata = json.loads(base64.urlsafe_b64decode(encoded).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InstructionArtifactError("instruction artifact header is invalid") from error
        expected = {
            "schema",
            "locale",
            "selected_reasoning_systems",
            "selected_display_names",
        }
        if not isinstance(metadata, dict) or set(metadata) != expected:
            raise InstructionArtifactError("instruction artifact metadata shape is invalid")
        if metadata["schema"] != _ARTIFACT_SCHEMA or metadata["locale"] not in {"en", "ko"}:
            raise InstructionArtifactError("instruction artifact metadata is invalid")
        return InstructionArtifact(
            path=path,
            locale=cast(InjectionLocale, metadata["locale"]),
            selected_reasoning_systems=_validate_method_ids(metadata["selected_reasoning_systems"]),
            selected_display_names=_validate_display_names(metadata["selected_display_names"]),
        )

    def latest_for_session(  # noqa: C901  # Branch-explicit symlink and type checks.
        self, session_id: str | None
    ) -> InstructionArtifact | None:
        """Return the newest live artifact in a session without reading its instruction body."""

        try:
            session_directory = self._session_directory(session_id)
            info = session_directory.lstat()
        except (OSError, InstructionArtifactError):
            return None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            return None
        candidates: list[tuple[int, Path]] = []
        try:
            turn_directories = tuple(session_directory.iterdir())
        except OSError:
            return None
        for turn_directory in turn_directories:
            if _TAG_RE.fullmatch(turn_directory.name) is None:
                continue
            try:
                turn_info = turn_directory.lstat()
                if stat.S_ISLNK(turn_info.st_mode) or not stat.S_ISDIR(turn_info.st_mode):
                    continue
                files = tuple(turn_directory.iterdir())
            except OSError:
                continue
            for path in files:
                if _FILE_RE.fullmatch(path.name) is None:
                    continue
                try:
                    file_info = self._inspect_regular_file(path)
                except InstructionArtifactError:
                    continue
                candidates.append((file_info.st_mtime_ns, path))
        for _mtime, path in sorted(candidates, reverse=True):
            try:
                artifact = self._decode_header(path)
                artifact.reference_message()
                return artifact
            except InstructionArtifactError:
                continue
        return None

    def _remove_tree(self, path: Path) -> int:
        """Remove an exact artifact subtree without following symlinks."""

        try:
            path.relative_to(self._directory)
            info = path.lstat()
        except (ValueError, OSError):
            return 0
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            try:
                path.unlink()
                return 1
            except OSError:
                return 0
        if os.name != "nt" and info.st_uid != os.geteuid():
            return 0
        removed = 0
        try:
            children = tuple(path.iterdir())
        except OSError:
            return 0
        for child in children:
            removed += self._remove_tree(child)
        try:
            path.rmdir()
        except OSError:
            pass
        else:
            removed += 1
        return removed

    def delete_turn(self, session_id: str | None, turn_id: str | None) -> int:
        """Best-effort immediate cleanup for every artifact created by one turn."""

        try:
            turn_directory = self._turn_directory(session_id, turn_id)
            session_directory = turn_directory.parent
        except InstructionArtifactError:
            return 0
        removed = self._remove_tree(turn_directory)
        try:
            session_directory.rmdir()
        except OSError:
            pass
        else:
            removed += 1
        return removed

    def delete_session(self, session_id: str | None) -> int:
        """Best-effort cleanup for every artifact in one completed session."""

        try:
            session_directory = self._session_directory(session_id)
        except InstructionArtifactError:
            return 0
        return self._remove_tree(session_directory)

    def sweep_expired(  # noqa: C901  # Branch-explicit best-effort cleanup.
        self,
    ) -> int:
        """Delete artifact files older than the confirmed 24-hour crash-recovery TTL."""

        try:
            self._ensure_root()
            sessions = tuple(self._directory.iterdir())
        except (OSError, InstructionArtifactError):
            return 0
        cutoff_ns = (_now_seconds(self._clock) - INSTRUCTION_FILE_TTL_SECONDS) * 1_000_000_000
        removed = 0
        for session_directory in sessions:
            if _TAG_RE.fullmatch(session_directory.name) is None:
                continue
            try:
                session_info = session_directory.lstat()
                if stat.S_ISLNK(session_info.st_mode) or not stat.S_ISDIR(session_info.st_mode):
                    continue
                turns = tuple(session_directory.iterdir())
            except OSError:
                continue
            for turn_directory in turns:
                if _TAG_RE.fullmatch(turn_directory.name) is None:
                    continue
                try:
                    turn_info = turn_directory.lstat()
                    if stat.S_ISLNK(turn_info.st_mode) or not stat.S_ISDIR(turn_info.st_mode):
                        continue
                    files = tuple(turn_directory.iterdir())
                except OSError:
                    continue
                for path in files:
                    if _FILE_RE.fullmatch(path.name) is None:
                        continue
                    try:
                        info = path.lstat()
                        if (
                            stat.S_ISREG(info.st_mode)
                            and not stat.S_ISLNK(info.st_mode)
                            and info.st_mtime_ns <= cutoff_ns
                        ):
                            path.unlink()
                            removed += 1
                    except OSError:
                        continue
                try:
                    turn_directory.rmdir()
                except OSError:
                    pass
                else:
                    removed += 1
            try:
                session_directory.rmdir()
            except OSError:
                pass
            else:
                removed += 1
        return removed

    def __repr__(self) -> str:
        return "InstructionFileStore(<private-temporary-root>)"


__all__ = [
    "INSTRUCTION_FILE_TTL_SECONDS",
    "MAX_INSTRUCTION_FILE_BYTES",
    "InstructionArtifact",
    "InstructionArtifactError",
    "InstructionFileStore",
]
