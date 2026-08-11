"""Ephemeral parser for the documented Codex command-hook contract.

The parser is intentionally narrower than the native event envelope.  It
checks the bounded JSON shape, extracts only fields needed by the normalized
event projection or the Codex-only selector request, and never returns a
native mapping to application or domain code. Prompt, transcript, path,
command, tool payload, and assistant text fields are transient and discarded
by :mod:`opensocrates.hosts.codex` after the native callback completes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import islice
from pathlib import Path
from typing import Any

from ...constants import INSTRUCTION_ARTIFACT_END_MARKER, MAX_CONTROL_DEPTH
from ...domain.enums import HostId

# Native hook envelopes are deliberately kept below the host-control limit.
# A successful Read callback may carry one complete bounded instruction
# artifact; only that envelope gets the larger bound, and its response is
# reduced to a terminal-marker boolean before leaving this parser.
MAX_NATIVE_BYTES = 32 * 1024
MAX_POST_TOOL_NATIVE_BYTES = 2 * 1024 * 1024
MAX_FINAL_MESSAGE_BYTES = 256 * 1024
MAX_NATIVE_OBJECT_MEMBERS = 128
MAX_NATIVE_COLLECTION_ITEMS = 256
# A Read response is one plain string or a file envelope whose key names are not
# a stable host contract.  The terminator search walks it shape-agnostically and
# stays bounded by this depth plus the collection limits above.
_MAX_READ_RESPONSE_DEPTH = 4

KNOWN_EVENTS = (
    "SessionStart",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PermissionRequest",
    "PreCompact",
    "PostCompact",
    "Stop",
    "SessionEnd",
)
NORMALIZED_TO_NATIVE = {
    "session_started": frozenset({"SessionStart"}),
    "user_prompt_submitted": frozenset({"UserPromptSubmit"}),
    # The fixed launcher uses one tool lane for PreToolUse metadata and
    # PostToolUse observations.  The native hook_event_name remains the
    # authority for whether normalization is a no-op or a tool event.
    "tool_succeeded": frozenset({"PreToolUse", "PostToolUse"}),
    "tool_failed": frozenset({"PostToolUse"}),
    "completion_candidate": frozenset({"Stop"}),
    "pre_compaction": frozenset({"PreCompact"}),
    "post_compaction": frozenset({"PostCompact"}),
    "session_ended": frozenset({"SessionEnd"}),
}
_START_SOURCES = frozenset({"startup", "resume", "clear", "compact"})
_CLAUDE_START_SOURCES = _START_SOURCES | {"fork"}
_COMPACTION_TRIGGERS = frozenset({"manual", "auto"})
_SESSION_END_REASONS = frozenset({"other"})
_CLAUDE_SESSION_END_REASONS = frozenset(
    {"clear", "resume", "logout", "prompt_input_exit", "bypass_permissions_disabled", "other"}
)
_FAILURE_CLASSES = frozenset({"permission", "timeout", "api_error", "interrupted", "unknown"})


class NativeParseError(ValueError):
    """Base class for malformed or unsafe native input."""

    code = "native_invalid"


class NativeInputTooLarge(NativeParseError):
    """Native input exceeded the bounded JSON or final-message limit."""

    code = "input_too_large"


class NativeWrongType(NativeParseError):
    """A documented native field has the wrong type."""

    code = "native_wrong_type"


class NativeInputNotObject(NativeParseError):
    """The hook body decoded successfully but was not a JSON object."""

    code = "native_input_not_object"


class NativeUnknownEvent(NativeParseError):
    """The host supplied an event outside the captured Codex contract."""

    code = "native_unknown_event"


@dataclass(frozen=True, slots=True)
class CodexNativeEvent:
    """Typed transient facts extracted from one Codex callback."""

    native_event: str
    host: HostId
    native_version: str
    session_id: str | None = field(default=None, repr=False)
    turn_id: str | None = field(default=None, repr=False)
    prompt: str | None = field(default=None, repr=False)
    transcript_path: Path | None = field(default=None, repr=False)
    cwd: Path | None = field(default=None, repr=False)
    model: str | None = field(default=None, repr=False)
    source: str | None = None
    tool_name: str | None = field(default=None, repr=False)
    tool_use_id: str | None = field(default=None, repr=False)
    tool_file_path: Path | None = field(default=None, repr=False)
    tool_read_offset: int | None = field(default=None, repr=False)
    tool_read_limit: int | None = field(default=None, repr=False)
    tool_read_end_marker_seen: bool = field(default=False, repr=False)
    result_present: bool = False
    result_size: int | None = field(default=None, repr=False)
    failure_class: str | None = None
    stop_hook_active: bool = False
    final_message: str | None = field(default=None, repr=False)
    trigger: str | None = None
    reason: str | None = None
    diagnostics: tuple[str, ...] = ()
    ignored_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NativeParseResult:
    """Fail-safe parser result; malformed input never reaches normalization."""

    event: CodexNativeEvent | None
    diagnostics: tuple[str, ...] = ()
    error_code: str | None = None
    ignored_fields: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.event is not None and self.error_code is None

    @property
    def pass_through(self) -> bool:
        return self.event is None


def _json_bytes(value: Mapping[str, Any] | str | bytes | bytearray) -> bytes:
    if isinstance(value, Mapping):
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise NativeParseError("native input is not JSON compatible") from exc
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    raise NativeParseError("native input must be an object or UTF-8 JSON")


def _depth_and_shape(value: object, *, depth: int = 0) -> None:
    if depth > MAX_CONTROL_DEPTH:
        raise NativeInputTooLarge("native JSON nesting exceeds the bounded limit")
    if isinstance(value, Mapping):
        if len(value) > MAX_NATIVE_OBJECT_MEMBERS:
            raise NativeInputTooLarge("native object has too many members")
        for key, child in value.items():
            if not isinstance(key, str):
                raise NativeWrongType("native object keys must be text")
            _depth_and_shape(child, depth=depth + 1)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > MAX_NATIVE_COLLECTION_ITEMS:
            raise NativeInputTooLarge("native collection has too many items")
        for child in value:
            _depth_and_shape(child, depth=depth + 1)


_COMMON_FIELDS = frozenset(
    {
        "hook_event_name",
        "session_id",
        "transcript_path",
        "cwd",
        "permission_mode",
        "model",
        "version",
        "host_version",
        "turn_id",
        "prompt_id",
    }
)
_KNOWN_FIELDS = {
    "SessionStart": _COMMON_FIELDS | {"source"},
    "UserPromptSubmit": _COMMON_FIELDS | {"prompt"},
    "PreToolUse": _COMMON_FIELDS | {"tool_name", "tool_use_id", "tool_input"},
    "PostToolUse": _COMMON_FIELDS
    | {
        "tool_name",
        "tool_use_id",
        "tool_input",
        "tool_response",
        "output_size",
        "result_size",
        "tool_exit_code",
        "exit_code",
        "success",
        "ok",
        "status",
        "error_class",
        "is_interrupt",
        "error",
        "duration_ms",
    },
    "PermissionRequest": _COMMON_FIELDS | {"tool_name", "tool_input", "description"},
    "PreCompact": _COMMON_FIELDS | {"trigger"},
    "PostCompact": _COMMON_FIELDS | {"trigger"},
    "Stop": _COMMON_FIELDS
    | {"stop_hook_active", "last_assistant_message", "declared_content_bytes"},
    "SessionEnd": _COMMON_FIELDS | {"reason"},
}


def _decode(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    value: Mapping[str, Any] | str | bytes | bytearray,
    event_name: str | None,
) -> tuple[dict[str, Any], str, tuple[str, ...]]:
    requested = event_name
    if requested is not None and not isinstance(requested, str):
        raise NativeWrongType("event_name must be text")
    if (
        requested is not None
        and requested not in KNOWN_EVENTS
        and requested not in NORMALIZED_TO_NATIVE
    ):
        raise NativeUnknownEvent(f"unsupported Codex event lane {requested!r}")
    raw = _json_bytes(value)
    if len(raw) > MAX_POST_TOOL_NATIVE_BYTES:
        raise NativeInputTooLarge(f"native event exceeds {MAX_POST_TOOL_NATIVE_BYTES} bytes")
    if len(raw) > MAX_NATIVE_BYTES and requested != "PostToolUse":
        raise NativeInputTooLarge(f"native event exceeds {MAX_NATIVE_BYTES} bytes")
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        # S07 uses a marker for the deliberately non-object malformed case.
        if isinstance(value, str) and value.startswith("<synthetic-non-object>"):
            raise NativeInputNotObject("native input must be an object") from exc
        raise NativeParseError("native input is not strict UTF-8 JSON") from exc
    if not isinstance(decoded, Mapping):
        raise NativeInputNotObject("native input must be an object")
    document = dict(decoded)
    candidate = document.get("hook_event_name")
    post_tool_envelope = candidate == "PostToolUse" or requested == "PostToolUse"
    read_response_envelope = post_tool_envelope and document.get("tool_name") == "Read"
    if len(raw) > MAX_NATIVE_BYTES and not read_response_envelope:
        raise NativeInputTooLarge(f"native event exceeds {MAX_NATIVE_BYTES} bytes")
    shape_document = dict(document)
    if read_response_envelope:
        # A successful Read callback can contain the complete bounded instruction
        # artifact.  Its result is never retained or projected; shape-check only
        # the metadata that this boundary consumes.
        shape_document["tool_response"] = None
    _depth_and_shape(shape_document)
    selected: str | None
    if requested in NORMALIZED_TO_NATIVE:
        if not isinstance(candidate, str):
            raise NativeParseError("native event name is unavailable")
        if candidate not in NORMALIZED_TO_NATIVE[requested]:
            raise NativeParseError("normalized event lane disagrees with hook_event_name")
        selected = candidate
    else:
        selected = requested
        if selected is None and isinstance(candidate, str):
            selected = candidate
    if selected is None or not isinstance(selected, str):
        raise NativeParseError("native event name is unavailable")
    native_name = document.get("hook_event_name", selected)
    if not isinstance(native_name, str):
        raise NativeWrongType("hook_event_name must be text")
    if native_name != selected and requested not in NORMALIZED_TO_NATIVE:
        raise NativeParseError("native event name disagrees with hook_event_name")
    ignored = tuple(
        sorted(key for key in document if key not in _KNOWN_FIELDS.get(native_name, frozenset()))
    )
    return document, native_name, ignored


def _text(
    document: Mapping[str, Any],
    key: str,
    *,
    required: bool = False,
    max_bytes: int = 4096,
) -> str | None:
    value = document.get(key)
    if value is None:
        if required:
            raise NativeWrongType(f"{key} is required")
        return None
    if not isinstance(value, str):
        raise NativeWrongType(f"{key} must be text")
    if len(value.encode("utf-8")) > max_bytes or "\x00" in value:
        raise NativeInputTooLarge(f"{key} exceeds its bounded size")
    return value


def _path(document: Mapping[str, Any], key: str) -> Path | None:
    """Return one bounded, untrusted host path without resolving or opening it."""

    value = _text(document, key, max_bytes=4096)
    if value is None:
        return None
    if not value:
        raise NativeWrongType(f"{key} must not be empty")
    return Path(value)


def _version(document: Mapping[str, Any]) -> str:
    value = document.get("version")
    if value is None:
        value = document.get("host_version")
    if value is None:
        # S07's synthetic SessionStart marker uses the optional model field as
        # a version-shaped value.  It is not evidence for a host capability.
        value = document.get("model")
    if value is None:
        return "unknown"
    if not isinstance(value, str):
        raise NativeWrongType("native version marker must be text")
    if len(value.encode("utf-8")) > 64:
        raise NativeInputTooLarge("native version marker is too large")
    return value


def _tool_name(document: Mapping[str, Any]) -> str:
    value = document.get("tool_name")
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > 256:
        raise NativeWrongType("tool_name must be bounded text")
    return value


def _optional_read_integer(tool_input: Mapping[str, Any], key: str) -> int | None:
    value = tool_input.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NativeWrongType(f"Read.{key} must be a nonnegative integer")
    return value


def _read_tool_input(
    document: Mapping[str, Any],
    tool_name: str,
) -> tuple[Path | None, int | None, int | None]:
    """Return optional receipt metadata without invalidating the host event."""

    if tool_name != "Read":
        return None, None, None
    value = document.get("tool_input")
    if not isinstance(value, Mapping):
        return None, None, None
    raw_path = value.get("file_path")
    try:
        if (
            not isinstance(raw_path, str)
            or not raw_path
            or "\x00" in raw_path
            or len(raw_path.encode("utf-8")) > 4096
        ):
            return None, None, None
        path = Path(raw_path)
        if not path.is_absolute():
            return None, None, None
        return (
            path,
            _optional_read_integer(value, "offset"),
            _optional_read_integer(value, "limit"),
        )
    except (NativeWrongType, UnicodeError):
        return None, None, None


def _size(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NativeWrongType("output size must be a nonnegative integer")
    return value


def _failure_class(document: Mapping[str, Any]) -> str:
    if document.get("is_interrupt") is True:
        return "interrupted"
    value = document.get("error_class")
    if isinstance(value, str) and value in _FAILURE_CLASSES:
        return value
    return "unknown"


def _post_tool_failed(document: Mapping[str, Any], tool_name: str) -> bool:
    """Read only closed result metadata; never retain the response value."""

    success = document.get("success")
    if isinstance(success, bool):
        return not success
    ok = document.get("ok")
    if isinstance(ok, bool):
        return not ok
    for key in ("tool_exit_code", "exit_code"):
        value = document.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value != 0
    status = document.get("status")
    if isinstance(status, str) and status.casefold() in {"error", "failed", "failure", "nonzero"}:
        return True
    response = document.get("tool_response")
    if isinstance(response, Mapping):
        response_success = response.get("success")
        if isinstance(response_success, bool):
            return not response_success
        response_exit = response.get("exit_code")
        if isinstance(response_exit, int) and not isinstance(response_exit, bool):
            return response_exit != 0
        response_status = response.get("status")
        if isinstance(response_status, str) and response_status.casefold() in {
            "error",
            "failed",
            "failure",
            "nonzero",
        }:
            return True
    # The synthetic S07 non-zero fixture deliberately omits the raw result and
    # uses Bash as the documented failure path.  No other tool name is inferred.
    return tool_name == "Bash" and response is None


def _marker_in_read_response(response: object, *, depth: int = 0) -> bool:
    """Search one Read response for the artifact terminator, whatever its shape.

    A host may return the read body as one plain string or wrap it in a file
    envelope, and the envelope's key names are not a stable host contract.
    Naming the keys this boundary expects would make an unfamiliar wrapper look
    like an incomplete read, which costs a compliant turn a repair pass.  The
    walk is therefore shape-agnostic, and bounded by an explicit depth limit
    plus the collection limits the rest of this boundary already uses, so an
    adversarial response object cannot drive unbounded work.

    Searching every string is safe rather than permissive here: the caller has
    already required this callback to be a successful Read of the artifact's own
    absolute path, and the terminator is an OpenSocrates constant that only that
    artifact carries.
    """

    if isinstance(response, str):
        return INSTRUCTION_ARTIFACT_END_MARKER in response
    if depth >= _MAX_READ_RESPONSE_DEPTH:
        return False
    if isinstance(response, Mapping):
        for value in islice(response.values(), MAX_NATIVE_OBJECT_MEMBERS):
            if _marker_in_read_response(value, depth=depth + 1):
                return True
        return False
    if isinstance(response, Sequence) and not isinstance(response, (str, bytes, bytearray)):
        for value in islice(response, MAX_NATIVE_COLLECTION_ITEMS):
            if _marker_in_read_response(value, depth=depth + 1):
                return True
    return False


def _read_end_marker_seen(document: Mapping[str, Any], tool_name: str) -> bool:
    """Confirm transiently that a successful Read response reached the artifact terminator.

    This is a terminator test, not a proof of delivery.  It establishes that a
    successful Read callback naming the exact artifact path returned content
    reaching the authored terminator; it does not cryptographically prove that
    every artifact byte was returned, and a synthetic marker-only payload would
    satisfy it.  That is not model-reachable: the terminator is the artifact's
    last line, so any truncation removes it, and the model does not author
    ``tool_response``.  Anything able to forge this envelope already controls
    the hook's stdin and is outside the boundary this gate defends.
    """

    if tool_name != "Read":
        return False
    return _marker_in_read_response(document.get("tool_response"))


def _build(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    document: Mapping[str, Any],
    native_name: str,
    host: HostId,
    ignored: tuple[str, ...],
) -> CodexNativeEvent:
    session_id = _text(document, "session_id", max_bytes=256)
    turn_id = _text(document, "turn_id", max_bytes=256)
    if turn_id is None and host in {HostId.CLAUDE_CODE, HostId.CLAUDE_COWORK}:
        turn_id = _text(document, "prompt_id", max_bytes=256)
    transcript_path = _path(document, "transcript_path")
    cwd = _path(document, "cwd")
    model = _text(document, "model", max_bytes=512)
    version = _version(document)
    diagnostics = ("native_unknown_field_ignored",) if ignored else ()
    if native_name == "SessionStart":
        source = _text(document, "source", required=True, max_bytes=32)
        allowed_sources = (
            _CLAUDE_START_SOURCES
            if host in {HostId.CLAUDE_CODE, HostId.CLAUDE_COWORK}
            else _START_SOURCES
        )
        if source not in allowed_sources:
            raise NativeWrongType("SessionStart.source is not a closed value")
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            source=source,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    if native_name == "UserPromptSubmit":
        prompt = _text(document, "prompt", required=True, max_bytes=MAX_FINAL_MESSAGE_BYTES)
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            prompt=prompt,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    if native_name in {"PreToolUse", "PermissionRequest"}:
        name = _tool_name(document)
        use_id = _text(document, "tool_use_id", max_bytes=256)
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            tool_name=name,
            tool_use_id=use_id,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    if native_name == "PostToolUse":
        name = _tool_name(document)
        use_id = _text(document, "tool_use_id", max_bytes=256)
        file_path, read_offset, read_limit = _read_tool_input(document, name)
        failed = _post_tool_failed(document, name)
        result_size = _size(document.get("output_size"))
        if result_size is None:
            result_size = _size(document.get("result_size"))
        end_marker_seen = _read_end_marker_seen(document, name) and not failed
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            tool_name=name,
            tool_use_id=use_id,
            tool_file_path=file_path,
            tool_read_offset=read_offset,
            tool_read_limit=read_limit,
            tool_read_end_marker_seen=end_marker_seen,
            result_present=not failed,
            result_size=result_size,
            failure_class=_failure_class(document) if failed else None,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    if native_name in {"PreCompact", "PostCompact"}:
        trigger = _text(document, "trigger", required=True, max_bytes=16)
        if trigger not in _COMPACTION_TRIGGERS:
            raise NativeWrongType("compact trigger is not a closed value")
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            trigger=trigger,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    if native_name == "Stop":
        active = document.get("stop_hook_active", False)
        if not isinstance(active, bool):
            raise NativeWrongType("stop_hook_active must be boolean")
        declared = document.get("declared_content_bytes")
        if declared is not None:
            if isinstance(declared, bool) or not isinstance(declared, int) or declared < 0:
                raise NativeWrongType("declared_content_bytes must be a nonnegative integer")
            if declared > MAX_FINAL_MESSAGE_BYTES:
                raise NativeInputTooLarge("last_assistant_message exceeds 256 KiB")
        final = document.get("last_assistant_message")
        if final is not None and not isinstance(final, str):
            raise NativeWrongType("last_assistant_message must be text or null")
        if isinstance(final, str) and len(final.encode("utf-8")) > MAX_FINAL_MESSAGE_BYTES:
            raise NativeInputTooLarge("last_assistant_message exceeds 256 KiB")
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            stop_hook_active=active,
            final_message=final,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    if native_name == "SessionEnd":
        reason = _text(document, "reason", required=True, max_bytes=32)
        allowed_reasons = (
            _CLAUDE_SESSION_END_REASONS
            if host in {HostId.CLAUDE_CODE, HostId.CLAUDE_COWORK}
            else _SESSION_END_REASONS
        )
        if reason not in allowed_reasons:
            raise NativeWrongType("SessionEnd.reason is not a closed value")
        return CodexNativeEvent(
            native_event=native_name,
            host=host,
            native_version=version,
            session_id=session_id,
            turn_id=turn_id,
            transcript_path=transcript_path,
            cwd=cwd,
            model=model,
            reason=reason,
            diagnostics=diagnostics,
            ignored_fields=ignored,
        )
    raise NativeUnknownEvent(f"unsupported Codex event {native_name!r}")


def try_parse_codex_event(
    value: Mapping[str, Any] | str | bytes | bytearray,
    *,
    event_name: str | None = None,
    host: HostId = HostId.CODEX_CLI,
) -> NativeParseResult:
    """Parse one Codex native event and return a safe result on error."""

    try:
        if not isinstance(host, HostId):
            host = HostId(host)
        document, native_name, ignored = _decode(value, event_name)
        if native_name not in KNOWN_EVENTS:
            raise NativeUnknownEvent(f"unsupported Codex event {native_name!r}")
        event = _build(document, native_name, host, ignored)
        return NativeParseResult(event=event, diagnostics=event.diagnostics, ignored_fields=ignored)
    except NativeParseError as exc:
        return NativeParseResult(event=None, diagnostics=(exc.code,), error_code=exc.code)
    except (TypeError, ValueError, OverflowError, UnicodeError):
        return NativeParseResult(
            event=None, diagnostics=("native_invalid",), error_code="native_invalid"
        )


def parse_codex_event(
    value: Mapping[str, Any] | str | bytes | bytearray,
    *,
    event_name: str | None = None,
    host: HostId = HostId.CODEX_CLI,
) -> CodexNativeEvent:
    """Strict parser for callers that want an exception on invalid input."""

    result = try_parse_codex_event(value, event_name=event_name, host=host)
    if result.event is None:
        raise NativeParseError(result.error_code or "native_invalid")
    return result.event


def parse_fixture(path: str | Path) -> NativeParseResult:
    """Parse one S07 fixture's ``native_input`` only.

    Availability/unsupported fixtures intentionally contain no native input;
    they return a safe availability diagnostic rather than fabricating an
    event.  The fixture expectation is never consulted.
    """

    fixture = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(fixture, Mapping):
        return NativeParseResult(None, ("fixture_not_object",), "fixture_not_object")
    native_input = fixture.get("native_input")
    native_name = fixture.get("native_event")
    if native_input is None:
        return NativeParseResult(None, ("availability_state",), "availability_state")
    raw_host = fixture.get("host", HostId.CODEX_CLI.value)
    try:
        host = HostId(raw_host)
    except (TypeError, ValueError):
        host = HostId.CODEX_CLI
    return try_parse_codex_event(
        native_input,
        event_name=native_name if isinstance(native_name, str) else None,
        host=host,
    )


try_parse_native_event = try_parse_codex_event
parse_native_event = parse_codex_event


__all__ = [
    "CodexNativeEvent",
    "KNOWN_EVENTS",
    "NORMALIZED_TO_NATIVE",
    "MAX_FINAL_MESSAGE_BYTES",
    "MAX_NATIVE_BYTES",
    "MAX_NATIVE_COLLECTION_ITEMS",
    "MAX_NATIVE_OBJECT_MEMBERS",
    "MAX_POST_TOOL_NATIVE_BYTES",
    "NativeInputNotObject",
    "NativeInputTooLarge",
    "NativeParseError",
    "NativeParseResult",
    "NativeUnknownEvent",
    "NativeWrongType",
    "parse_codex_event",
    "parse_fixture",
    "parse_native_event",
    "try_parse_codex_event",
    "try_parse_native_event",
]
