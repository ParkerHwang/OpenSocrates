"""Stdlib-only ULID, UUIDv7, and task-local identifier generation."""

from __future__ import annotations

import base64
import os
import re
import secrets
import threading
import uuid
from dataclasses import dataclass

from .clock import Clock, SystemClock
from .errors import IdentifierError

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_UUID7_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
_LOCAL_ID_RE = re.compile(r"^(?P<prefix>[JCEAKI])(?P<number>[0-9]{6})$")
_METHOD_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_DECIMAL_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def _encode_crockford(value: int, length: int) -> str:
    chars = ["0"] * length
    for index in range(length - 1, -1, -1):
        value, remainder = divmod(value, 32)
        chars[index] = _CROCKFORD[remainder]
    if value:
        raise IdentifierError("value does not fit Crockford encoding")
    return "".join(chars)


def _decode_crockford(value: str) -> int:
    result = 0
    for character in value:
        result = (result << 5) | _CROCKFORD.index(character)
    return result


@dataclass
class _MonotonicState:
    pid: int
    millisecond: int = -1
    counter: int = 0


class _IdGenerator:
    def __init__(self, bits: int) -> None:
        self._bits = bits
        self._state = _MonotonicState(os.getpid())
        self._lock = threading.Lock()

    def next(self, clock: Clock) -> tuple[int, int]:
        with self._lock:
            pid = os.getpid()
            now = clock.unix_time_ns() // 1_000_000
            if pid != self._state.pid:
                self._state = _MonotonicState(pid)
            if now > self._state.millisecond:
                self._state.millisecond = now
                self._state.counter = secrets.randbits(self._bits)
            else:
                self._state.counter += 1
                if self._state.counter >= 1 << self._bits:
                    self._state.millisecond += 1
                    self._state.counter = secrets.randbits(self._bits)
            return self._state.millisecond, self._state.counter


_ULID_GENERATOR = _IdGenerator(80)
_UUID7_GENERATOR = _IdGenerator(74)


def new_task_id(clock: Clock | None = None) -> str:
    """Generate a monotonic, uppercase Crockford ULID task identifier."""

    milliseconds, randomness = _ULID_GENERATOR.next(clock or SystemClock())
    if milliseconds < 0 or milliseconds >= 1 << 48:
        raise IdentifierError("ULID timestamp does not fit 48 bits")
    value = (milliseconds << 80) | randomness
    return _encode_crockford(value, 26)


def new_event_id(clock: Clock | None = None) -> str:
    """Generate a lowercase RFC 9562 UUIDv7 with a process-local guard."""

    milliseconds, randomness = _UUID7_GENERATOR.next(clock or SystemClock())
    if milliseconds < 0 or milliseconds >= 1 << 48:
        raise IdentifierError("UUIDv7 timestamp does not fit 48 bits")
    high = (randomness >> 62) & 0xFFF
    low = randomness & ((1 << 62) - 1)
    raw = bytearray(16)
    raw[0:6] = milliseconds.to_bytes(6, "big")
    raw[6] = 0x70 | (high >> 8)
    raw[7] = high & 0xFF
    raw[8] = 0x80 | ((low >> 56) & 0x3F)
    raw[9:16] = (low & ((1 << 56) - 1)).to_bytes(7, "big")
    return str(uuid.UUID(bytes=bytes(raw)))


def new_turn_token() -> str:
    """Generate a 32-byte unpadded base64url turn token (always 43 ASCII chars)."""

    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def new_local_id(prefix: str, sequence: int) -> str:
    """Create a task-local six-digit identifier for an allowed prefix."""

    if prefix not in {"J", "C", "E", "A", "K", "I"} or not 1 <= sequence <= 999_999:
        raise IdentifierError("invalid task-local identifier allocation")
    return f"{prefix}{sequence:06d}"


def validate_task_id(value: str, clock: Clock | None = None) -> str:
    if not isinstance(value, str) or not _ULID_RE.fullmatch(value):
        raise IdentifierError("TaskId must be 26 uppercase Crockford characters")
    if _decode_crockford(value) >> 128:
        raise IdentifierError("TaskId has an invalid leading digit")
    timestamp_ms = _decode_crockford(value) >> 80
    now_ms = (clock or SystemClock()).unix_time_ns() // 1_000_000
    if timestamp_ms > now_ms + 300_000:
        raise IdentifierError("TaskId timestamp is more than five minutes in the future")
    return value


def validate_event_id(value: str, clock: Clock | None = None) -> str:
    if not isinstance(value, str) or not _UUID7_RE.fullmatch(value):
        raise IdentifierError("EventId must be lowercase canonical UUIDv7 text")
    parsed = uuid.UUID(value)
    if parsed.version != 7 or parsed.variant != uuid.RFC_4122:
        raise IdentifierError("EventId must use UUIDv7 version and RFC 9562 variant")
    timestamp_ms = int.from_bytes(parsed.bytes[0:6], "big")
    now_ms = (clock or SystemClock()).unix_time_ns() // 1_000_000
    if timestamp_ms > now_ms + 300_000:
        raise IdentifierError("EventId timestamp is more than five minutes in the future")
    return value


def validate_local_id(value: str, prefix: str | None = None) -> str:
    if not isinstance(value, str):
        raise IdentifierError("task-local identifier must be text")
    match = _LOCAL_ID_RE.fullmatch(value)
    if match is None or (prefix is not None and match.group("prefix") != prefix):
        raise IdentifierError("invalid task-local identifier")
    return value


def validate_turn_token(value: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 43
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", value)
    ):
        raise IdentifierError("TurnToken must be 43 unpadded base64url characters")
    try:
        decoded = base64.urlsafe_b64decode(value + "=")
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise IdentifierError("TurnToken is not valid base64url") from exc
    if len(decoded) != 32:
        raise IdentifierError("TurnToken must decode to 32 bytes")
    return value


def validate_method_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 2 <= len(value) <= 64
        or not _METHOD_ID_RE.fullmatch(value)
    ):
        raise IdentifierError("MethodId must be lowercase kebab-case of length 2..64")
    return value


def validate_semver(value: str) -> str:
    if not isinstance(value, str) or _SEMVER_RE.fullmatch(value) is None:
        raise IdentifierError("SemVer must be MAJOR.MINOR.PATCH without prerelease")
    return value


def validate_sha256(value: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise IdentifierError("Sha256 must be sha256: followed by 64 lowercase hex digits")
    return value


def validate_decimal_string(value: str) -> str:
    if not isinstance(value, str) or _DECIMAL_RE.fullmatch(value) is None:
        raise IdentifierError("DecimalString has an invalid representation")
    return value


def validate_timestamp(value: str) -> str:
    if not isinstance(value, str) or _TIMESTAMP_RE.fullmatch(value) is None:
        raise IdentifierError("timestamp must be RFC 3339 UTC with millisecond precision")
    return value
