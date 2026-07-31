"""Safe, typed status projection from settings and observed capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ..constants import CAPABILITY_KEYS
from ..domain.enums import CapabilityStatus, RecordingMode, Rigor
from ..domain.models import CapabilityEntry, CapabilityProfile, UserSettings
from ..version import PRODUCT_VERSION
from .change_settings import effective_recording_mode


class CapabilityClaim(StrEnum):
    """User-safe capability summary; no host tier or internal key is exposed."""

    FULL = "full"
    DEGRADED = "degraded"
    PROMPT_ONLY = "prompt_only"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StatusProjection:
    """Content-free status values suitable for a localized renderer."""

    locale: str
    locale_preference: str | None
    default_rigor: Rigor
    recording_mode: RecordingMode
    recording_effective: bool
    onboarding_complete: bool
    record_retention_days: int
    record_size_limit_bytes: int
    capability_state: CapabilityClaim
    storage_state: CapabilityStatus


_FULL_REQUIRED_KEYS: Final[frozenset[str]] = frozenset(CAPABILITY_KEYS) - {"rich_card_widget"}
_PROMPT_CONTEXT_KEYS: Final[tuple[str, ...]] = (
    "prompt_context_injection",
    "method_skill_invocation",
)


def _status(entry: CapabilityEntry | None) -> CapabilityStatus:
    if not isinstance(entry, CapabilityEntry):
        return CapabilityStatus.UNKNOWN
    return entry.status


def _profile_statuses(profile: CapabilityProfile) -> dict[str, CapabilityStatus]:
    return {key: _status(profile.capabilities.get(key)) for key in CAPABILITY_KEYS}


def capability_claim(profile: CapabilityProfile) -> CapabilityClaim:
    """Derive an honest user-safe claim from every required capability entry.

    Unknown is deliberately checked first.  A stale/profile-supplied tier is
    never trusted as authority, and an unknown required capability can never
    produce a full claim.
    """

    if not isinstance(profile, CapabilityProfile):
        raise TypeError("status projection requires CapabilityProfile")
    statuses = _profile_statuses(profile)
    required = [statuses[key] for key in _FULL_REQUIRED_KEYS]
    if any(status is CapabilityStatus.UNKNOWN for status in required):
        return CapabilityClaim.UNKNOWN
    if all(status is CapabilityStatus.SUPPORTED for status in required):
        return CapabilityClaim.FULL

    context_statuses = [statuses[key] for key in _PROMPT_CONTEXT_KEYS]
    context_available = any(
        status in {CapabilityStatus.SUPPORTED, CapabilityStatus.DEGRADED}
        for status in context_statuses
    )
    if not context_available:
        return CapabilityClaim.UNAVAILABLE
    control = statuses["local_control_execution"]
    method_observation = statuses["method_invocation_observation"]
    if (
        control is not CapabilityStatus.SUPPORTED
        or method_observation is not CapabilityStatus.SUPPORTED
    ):
        return CapabilityClaim.PROMPT_ONLY
    return CapabilityClaim.DEGRADED


def project_status(
    settings: UserSettings,
    profile: CapabilityProfile,
    *,
    locale: str = "en",
    current_onboarding_version: str = PRODUCT_VERSION,
) -> StatusProjection:
    """Project only safe scalar settings and capability-health values."""

    if not isinstance(settings, UserSettings):
        raise TypeError("status projection requires UserSettings")
    if not isinstance(profile, CapabilityProfile):
        raise TypeError("status projection requires CapabilityProfile")
    if locale not in {"en", "ko"}:
        raise ValueError("status locale must be en or ko")
    statuses = _profile_statuses(profile)
    storage = statuses["local_record_write"]
    complete = settings.onboarding_version_seen == current_onboarding_version
    effective_mode = effective_recording_mode(
        settings,
        current_onboarding_version=current_onboarding_version,
    )
    recording_effective = (
        effective_mode is RecordingMode.LOCAL_PUBLIC_ARTIFACTS
        and storage is CapabilityStatus.SUPPORTED
    )
    return StatusProjection(
        locale=locale,
        locale_preference=settings.locale_preference,
        default_rigor=settings.default_rigor,
        recording_mode=effective_mode,
        recording_effective=recording_effective,
        onboarding_complete=complete,
        record_retention_days=settings.record_retention_days,
        record_size_limit_bytes=settings.record_size_limit_bytes,
        capability_state=capability_claim(profile),
        storage_state=storage,
    )


status_projection = project_status
derive_capability_claim = capability_claim


__all__ = [
    "CapabilityClaim",
    "StatusProjection",
    "capability_claim",
    "derive_capability_claim",
    "project_status",
    "status_projection",
]
