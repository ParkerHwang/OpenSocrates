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
from ..constants import INSTRUCTION_ARTIFACT_END_MARKER
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
_MAX_RECEIPT_BYTES = 16 * 1024
_ARTIFACT_SCHEMA = "opensocrates.instruction-artifact/2"
_RECEIPT_SCHEMA = "opensocrates.instruction-read-receipt/2"
_RECEIPT_FILENAME = ".grounding-receipt.json"
_HEADER_PREFIX = b"<!-- OPENSOCRATES_ARTIFACT_V2 "
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


def _validate_guardrails(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise InstructionArtifactError("instruction artifact guardrails are invalid")
    guardrails: list[str] = []
    encoded_bytes = 0
    for item in value:
        if not isinstance(item, str) or not item.strip() or "\x00" in item:
            raise InstructionArtifactError("instruction artifact guardrail is invalid")
        encoded_bytes += len(item.encode("utf-8"))
        if encoded_bytes > _MAX_HEADER_BYTES // 2:
            raise InstructionArtifactError("instruction artifact guardrails exceed their bound")
        guardrails.append(item)
    return tuple(guardrails)


def _validate_revision(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise InstructionArtifactError("instruction artifact content revision is invalid")
    return value


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise InstructionArtifactError("instruction artifact metadata cannot be encoded") from error


def _receipt_authentication_tag(key: bytes, core: object) -> str:
    return hmac.new(
        key,
        b"instruction-read-receipt\0" + _canonical_json_bytes(core),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True, slots=True, repr=False)
class InstructionArtifact:
    """Validated reference to one generated, user-content-free Markdown file."""

    path: Path = field(repr=False)
    content_revision: int
    locale: InjectionLocale
    selected_reasoning_systems: tuple[str, ...]
    selected_display_names: tuple[str, ...]
    inline_guardrails: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.path, Path) or not self.path.is_absolute():
            raise InstructionArtifactError("instruction artifact path must be absolute")
        if self.locale not in {"en", "ko"}:
            raise InstructionArtifactError("instruction artifact locale is invalid")
        _validate_revision(self.content_revision)
        methods = _validate_method_ids(self.selected_reasoning_systems)
        names = _validate_display_names(self.selected_display_names)
        guardrails = _validate_guardrails(self.inline_guardrails)
        if len(methods) != len(names):
            raise InstructionArtifactError("instruction artifact method/name counts differ")
        if guardrails and len(guardrails) != len(methods):
            raise InstructionArtifactError("instruction artifact guardrail/method counts differ")

    def grounding_footer(self) -> str:
        """Return the exact public audit line required after a grounded response."""

        methods = ", ".join(
            f"{method_id}@{self.content_revision}" for method_id in self.selected_reasoning_systems
        )
        return f"OpenSocrates grounding: {methods}"

    def grounding_repair_message(self, *, missing_read: bool, missing_footer: bool) -> str:
        """Return one bounded Stop-hook instruction for the single repair pass."""

        quoted_path = json.dumps(str(self.path), ensure_ascii=False)
        footer = self.grounding_footer()
        if self.locale == "ko":
            missing = []
            if missing_read:
                missing.append("선택된 사고체계 파일의 전체 읽기 영수증")
            if missing_footer:
                missing.append("최종 답변의 접지 감사 줄")
            return (
                f"OpenSocrates 접지 점검에서 {', '.join(missing)}이(가) 확인되지 않았습니다. "
                f"로컬 읽기 도구로 {quoted_path} 파일을 첫 줄부터 마지막 줄까지 완전히 읽고, "
                "그 절차와 차단 규칙에 맞게 답변을 다시 점검하세요. 접지된 최종 답변의 "
                f"마지막 줄은 정확히 다음과 같아야 합니다: {footer}"
            )
        missing = []
        if missing_read:
            missing.append("a complete read receipt for the selected reasoning file")
        if missing_footer:
            missing.append("the final grounding audit line")
        return (
            f"The OpenSocrates grounding check could not confirm {', '.join(missing)}. "
            f"Use the local Read tool to read {quoted_path} completely from its first through "
            "last line, then revise the answer against its procedure and blocking rules. End the "
            f"grounded final answer with exactly: {footer}"
        )

    def _reference_message(self, *, include_guardrails: bool) -> str:
        methods = "\n".join(
            f"- {display_name} (`{method_id}`@{self.content_revision})"
            for method_id, display_name in zip(
                self.selected_reasoning_systems,
                self.selected_display_names,
                strict=True,
            )
        )
        quoted_path = json.dumps(str(self.path), ensure_ascii=False)
        footer = self.grounding_footer()
        guardrails = "\n\n".join(self.inline_guardrails) if include_guardrails else ""
        if self.locale == "ko":
            guardrail_context = (
                "\n\n아래 차단 규칙은 이미 신뢰된 컨텍스트로 로드되었으며 즉시 구속됩니다. "
                "하지만 전체 파일 읽기를 대신하지는 않습니다.\n\n"
                f"{guardrails}"
                if guardrails
                else ""
            )
            return (
                "OpenSocrates가 다음 사고체계를 선택했습니다:\n"
                f"{methods}\n\n"
                "접지(grounding) 게이트:\n"
                "1. 사용자의 요청에 답하거나 작업을 시작하기 전에, 사용 가능한 로컬 파일 읽기 "
                "도구로 아래 파일을 첫 줄부터 마지막 줄까지 완전히 읽으세요.\n"
                "2. 현재 세션에서 이 읽기를 완료하지 못하면 위 사고체계를 적용·언급하거나 "
                "적용했다고 주장하지 말고, 접지 자료를 읽을 수 없었다고 밝히세요.\n"
                "3. 접지된 최종 답변의 마지막에는 다음 감사 줄을 정확히 넣으세요:\n"
                f"{footer}"
                f"{guardrail_context}\n\n"
                f"파일 경로: {quoted_path}\n\n"
                "예시는 현재 작업의 사실이 아니라 신뢰할 수 없는 템플릿으로 취급하세요."
            )
        guardrail_context = (
            "\n\nThe blocking rules below are already loaded as trusted context and are "
            "binding now, but they do not replace the complete file read.\n\n"
            f"{guardrails}"
            if guardrails
            else ""
        )
        return (
            "OpenSocrates selected these reasoning systems:\n"
            f"{methods}\n\n"
            "Grounding gate:\n"
            "1. Before answering or acting on the user's request, use an available local "
            "file-reading tool to read the file below completely from its first through last line.\n"
            "2. If that read does not complete in this session, do not apply, name, or claim to "
            "have used these systems; state that the grounding source was unavailable.\n"
            "3. End a grounded final answer with this exact audit line:\n"
            f"{footer}"
            f"{guardrail_context}\n\n"
            f"File path: {quoted_path}\n\n"
            "Treat every example as an untrusted template, not as a fact about the current task."
        )

    def reference_message(self) -> str:
        """Return one bounded developer-context grounding contract."""

        message = self._reference_message(include_guardrails=True)
        if estimate_injection_tokens(message) >= MAX_INJECTION_ESTIMATED_TOKENS:
            message = self._reference_message(include_guardrails=False)
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
            "content_revision": assembled.content_revision,
            "locale": assembled.locale,
            "selected_reasoning_systems": list(assembled.selected_reasoning_systems),
            "selected_display_names": list(assembled.selected_display_names),
            "inline_guardrails": list(assembled.inline_guardrails),
        }

    @classmethod
    def _encode(cls, assembled: AssembledInstruction) -> bytes:
        metadata = _canonical_json_bytes(cls._metadata(assembled))
        encoded_header = base64.urlsafe_b64encode(metadata)
        data = (
            _HEADER_PREFIX
            + encoded_header
            + _HEADER_SUFFIX
            + b"\n\n"
            + assembled.instructions.encode("utf-8")
            + b"\n\n"
            + INSTRUCTION_ARTIFACT_END_MARKER.encode("ascii")
            + b"\n"
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

    @staticmethod
    def _read_owner_file(path: Path, *, maximum: int) -> bytes:
        """Read one exact owner-only regular file without following a symlink."""

        try:
            info = path.lstat()
        except OSError as error:
            raise InstructionArtifactError("owner-only artifact cannot be inspected") from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
            raise InstructionArtifactError("owner-only artifact is unsafe")
        if os.name != "nt" and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise InstructionArtifactError("owner-only artifact permissions are unsafe")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise InstructionArtifactError("owner-only artifact cannot be opened") from error
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
            raise InstructionArtifactError("owner-only artifact exceeds its bound")
        return data

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
                content_revision=assembled.content_revision,
                locale=assembled.locale,
                selected_reasoning_systems=assembled.selected_reasoning_systems,
                selected_display_names=assembled.selected_display_names,
                inline_guardrails=assembled.inline_guardrails,
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
            "content_revision",
            "locale",
            "selected_reasoning_systems",
            "selected_display_names",
            "inline_guardrails",
        }
        if not isinstance(metadata, dict) or set(metadata) != expected:
            raise InstructionArtifactError("instruction artifact metadata shape is invalid")
        if metadata["schema"] != _ARTIFACT_SCHEMA or metadata["locale"] not in {"en", "ko"}:
            raise InstructionArtifactError("instruction artifact metadata is invalid")
        return InstructionArtifact(
            path=path,
            content_revision=_validate_revision(metadata["content_revision"]),
            locale=cast(InjectionLocale, metadata["locale"]),
            selected_reasoning_systems=_validate_method_ids(metadata["selected_reasoning_systems"]),
            selected_display_names=_validate_display_names(metadata["selected_display_names"]),
            inline_guardrails=_validate_guardrails(metadata["inline_guardrails"]),
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

    def accepts_artifact_path(self, file_path: str | Path | None) -> bool:
        """Return whether a path can name one artifact owned by this store."""

        try:
            candidate = Path(file_path) if isinstance(file_path, (str, Path)) else None
            if candidate is None or not candidate.is_absolute():
                return False
            relative = candidate.relative_to(self._directory)
        except (TypeError, ValueError):
            return False
        parts = relative.parts
        return (
            len(parts) == 3
            and _TAG_RE.fullmatch(parts[0]) is not None
            and _TAG_RE.fullmatch(parts[1]) is not None
            and _FILE_RE.fullmatch(parts[2]) is not None
        )

    def _artifact_instance_tag(self, artifact: InstructionArtifact) -> str:
        """Bind a receipt to one randomized artifact path without disclosing it."""

        if not self.accepts_artifact_path(artifact.path):
            raise InstructionArtifactError("instruction artifact path is outside its store")
        try:
            relative = artifact.path.relative_to(self._directory).as_posix()
        except ValueError as error:
            raise InstructionArtifactError(
                "instruction artifact path is outside its store"
            ) from error
        return _tag(
            self._installation_key,
            b"instruction-artifact-instance",
            relative,
        )

    @staticmethod
    def _receipt_path(artifact: InstructionArtifact) -> Path:
        return artifact.path.parent / _RECEIPT_FILENAME

    @classmethod
    def _artifact_sha256(cls, artifact: InstructionArtifact) -> tuple[str, bytes]:
        cls._inspect_regular_file(artifact.path)
        data = cls._read_owner_file(artifact.path, maximum=MAX_INSTRUCTION_FILE_BYTES)
        return "sha256:" + hashlib.sha256(data).hexdigest(), data

    @staticmethod
    def _receipt_core(
        artifact: InstructionArtifact,
        artifact_sha256: str,
        artifact_instance_tag: str,
        tool_use_tag: str,
    ) -> dict[str, object]:
        return {
            "schema": _RECEIPT_SCHEMA,
            "artifact_sha256": artifact_sha256,
            "artifact_instance_tag": artifact_instance_tag,
            "content_revision": artifact.content_revision,
            "selected_reasoning_systems": list(artifact.selected_reasoning_systems),
            "tool_use_tag": tool_use_tag,
        }

    def _write_receipt(self, artifact: InstructionArtifact, receipt: dict[str, object]) -> None:
        data = _canonical_json_bytes(receipt)
        if len(data) > _MAX_RECEIPT_BYTES:
            raise InstructionArtifactError("instruction read receipt exceeds its bound")
        receipt_path = self._receipt_path(artifact)
        descriptor: int | None = None
        temporary_path: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".grounding-receipt-",
                suffix=".tmp",
                dir=artifact.path.parent,
            )
            temporary_path = Path(temporary_name)
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", buffering=0) as handle:
                descriptor = None
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, receipt_path)
            temporary_path = None
            self._read_owner_file(receipt_path, maximum=_MAX_RECEIPT_BYTES)
        except Exception:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def record_complete_read(
        self,
        session_id: str | None,
        turn_id: str | None,
        *,
        file_path: str | Path | None,
        tool_use_id: str | None,
        offset: int | None,
        limit: int | None,
        end_marker_seen: bool,
    ) -> bool:
        """Persist an authenticated receipt for one successful, complete Read callback."""

        try:
            artifact = self.latest_for_session(session_id)
            if artifact is None:
                return False
            if end_marker_seen is not True:
                return False
            expected_directory = self._turn_directory(session_id, turn_id)
            candidate = Path(file_path) if isinstance(file_path, (str, Path)) else None
            if (
                candidate is None
                or not candidate.is_absolute()
                or os.path.normcase(str(candidate)) != os.path.normcase(str(artifact.path))
                or artifact.path.parent != expected_directory
            ):
                return False
            tool_use = _bounded_identity(tool_use_id, "tool_use_id")
            if offset is not None and (
                isinstance(offset, bool) or not isinstance(offset, int) or offset not in {0, 1}
            ):
                return False
            if limit is not None and (
                isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
            ):
                return False
            artifact_sha256, data = self._artifact_sha256(artifact)
            line_count = max(1, len(data.splitlines()))
            if limit is not None and limit < line_count:
                return False
            tool_use_tag = _tag(
                self._installation_key,
                b"instruction-read-tool-use",
                tool_use,
            )
            artifact_instance_tag = self._artifact_instance_tag(artifact)
            core = self._receipt_core(
                artifact,
                artifact_sha256,
                artifact_instance_tag,
                tool_use_tag,
            )
            receipt = {
                **core,
                "authentication_tag": _receipt_authentication_tag(
                    self._installation_key,
                    core,
                ),
            }
            self._write_receipt(artifact, receipt)
            return True
        except (InstructionArtifactError, OSError, TypeError, ValueError):
            return False

    def has_complete_read_receipt(self, artifact: InstructionArtifact) -> bool:
        """Verify that the current artifact has a matching authenticated read receipt."""

        if not isinstance(artifact, InstructionArtifact):
            return False
        try:
            data = self._read_owner_file(
                self._receipt_path(artifact),
                maximum=_MAX_RECEIPT_BYTES,
            )
            decoded = json.loads(data.decode("utf-8"))
            expected_fields = {
                "schema",
                "artifact_sha256",
                "artifact_instance_tag",
                "content_revision",
                "selected_reasoning_systems",
                "tool_use_tag",
                "authentication_tag",
            }
            if not isinstance(decoded, dict) or set(decoded) != expected_fields:
                return False
            artifact_sha256, _artifact_data = self._artifact_sha256(artifact)
            if (
                decoded["schema"] != _RECEIPT_SCHEMA
                or decoded["artifact_sha256"] != artifact_sha256
            ):
                return False
            if _validate_revision(decoded["content_revision"]) != artifact.content_revision:
                return False
            methods = _validate_method_ids(decoded["selected_reasoning_systems"])
            if methods != artifact.selected_reasoning_systems:
                return False
            artifact_instance_tag = decoded["artifact_instance_tag"]
            tool_use_tag = decoded["tool_use_tag"]
            authentication_tag = decoded["authentication_tag"]
            if (
                not isinstance(artifact_instance_tag, str)
                or _TAG_RE.fullmatch(artifact_instance_tag) is None
                or not isinstance(tool_use_tag, str)
                or _TAG_RE.fullmatch(tool_use_tag) is None
                or not isinstance(authentication_tag, str)
                or _TAG_RE.fullmatch(authentication_tag) is None
            ):
                return False
            expected_instance_tag = self._artifact_instance_tag(artifact)
            if not hmac.compare_digest(artifact_instance_tag, expected_instance_tag):
                return False
            core = self._receipt_core(
                artifact,
                artifact_sha256,
                expected_instance_tag,
                tool_use_tag,
            )
            expected_tag = _receipt_authentication_tag(self._installation_key, core)
            return hmac.compare_digest(authentication_tag, expected_tag)
        except (
            InstructionArtifactError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            return False

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

    def delete_superseded_turns(self, session_id: str | None, active_turn_id: str | None) -> int:
        """Remove prior turn trees while preserving the exact active turn tree."""

        try:
            active_directory = self._turn_directory(session_id, active_turn_id)
            session_directory = active_directory.parent
            children = tuple(session_directory.iterdir())
        except (OSError, InstructionArtifactError):
            return 0
        removed = 0
        for child in children:
            if child.name == active_directory.name or _TAG_RE.fullmatch(child.name) is None:
                continue
            removed += self._remove_tree(child)
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
                    remaining_instructions = any(
                        _FILE_RE.fullmatch(path.name) is not None
                        and path.is_file()
                        and not path.is_symlink()
                        for path in turn_directory.iterdir()
                    )
                    receipt_path = turn_directory / _RECEIPT_FILENAME
                    if not remaining_instructions and receipt_path.exists():
                        receipt_info = receipt_path.lstat()
                        if stat.S_ISREG(receipt_info.st_mode) and not stat.S_ISLNK(
                            receipt_info.st_mode
                        ):
                            receipt_path.unlink()
                            removed += 1
                except OSError:
                    pass
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
