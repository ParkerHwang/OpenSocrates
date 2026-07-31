"""Codex CLI/Desktop native adapter and generated-package contracts."""

from .adapter import CodexAdapter, CodexAdapterConfig, CodexHandleResult
from .capability import (
    build_capability_profile,
    capability_profile_for_availability,
    capability_status,
    capability_summary,
    default_capability_profile,
    profile_expired,
)
from .commands import (
    CODEX_NATIVE_EVENTS,
    NATIVE_TO_NORMALIZED,
    build_hooks,
    fixed_control_command,
    fixed_launcher_command,
)
from .events import normalize_codex_event, project_codex_payload
from .native import (
    CodexNativeEvent,
    NativeInputNotObject,
    NativeInputTooLarge,
    NativeParseError,
    NativeParseResult,
    NativeUnknownEvent,
    NativeWrongType,
    parse_codex_event,
    parse_fixture,
    try_parse_codex_event,
)
from .probe import CodexProbeResult, diagnose, probe_capabilities
from .responses import (
    NativeResponseError,
    pass_through_response,
    serialize_codex_response,
)

__all__ = [
    "CODEX_NATIVE_EVENTS",
    "NATIVE_TO_NORMALIZED",
    "CodexAdapter",
    "CodexAdapterConfig",
    "CodexHandleResult",
    "CodexNativeEvent",
    "CodexProbeResult",
    "NativeInputNotObject",
    "NativeInputTooLarge",
    "NativeParseError",
    "NativeParseResult",
    "NativeResponseError",
    "NativeUnknownEvent",
    "NativeWrongType",
    "build_capability_profile",
    "build_hooks",
    "capability_profile_for_availability",
    "capability_status",
    "capability_summary",
    "default_capability_profile",
    "diagnose",
    "fixed_control_command",
    "fixed_launcher_command",
    "normalize_codex_event",
    "parse_codex_event",
    "parse_fixture",
    "pass_through_response",
    "probe_capabilities",
    "profile_expired",
    "project_codex_payload",
    "serialize_codex_response",
    "try_parse_codex_event",
]
