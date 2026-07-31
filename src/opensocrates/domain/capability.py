"""Pure capability-profile validation and tier derivation."""

from __future__ import annotations

from collections.abc import Mapping

from ..constants import CAPABILITY_KEYS
from ..errors import ValidationError
from .enums import CapabilityStatus, CapabilityTier
from .models import CapabilityEntry, CapabilityProfile

# The canonical registry is closed in constants.py; this policy only derives
# a tier from that exact set and never adds host-specific keys.

_TIER_A_KEYS = frozenset(CAPABILITY_KEYS) - {"rich_card_widget"}
_TIER_B_CORE = frozenset(
    {
        "prompt_context_injection",
        "local_control_execution",
        "method_skill_invocation",
        "completion_candidate_observation",
        "bounded_completion_continuation",
        "local_record_write",
        "deterministic_trace_render",
    }
)


def _capability_entries(
    profile_or_capabilities: CapabilityProfile | Mapping[str, CapabilityEntry],
) -> Mapping[str, CapabilityEntry]:
    if isinstance(profile_or_capabilities, CapabilityProfile):
        capabilities = profile_or_capabilities.capabilities
    elif isinstance(profile_or_capabilities, Mapping):
        capabilities = profile_or_capabilities  # type: ignore[assignment]  # Closed runtime boundary validates this value.
    else:
        raise ValidationError("capability tier: expected CapabilityProfile or capability mapping")
    if set(capabilities) != set(CAPABILITY_KEYS):
        raise ValidationError("capability tier: exact 14-key capability set is required")
    for key, entry in capabilities.items():
        if not isinstance(key, str) or not isinstance(entry, CapabilityEntry):
            raise ValidationError("capability tier: entries must be typed CapabilityEntry values")
    return capabilities


def _available(status: CapabilityStatus) -> bool:
    # Unknown is deliberately fail-closed and therefore not available for a
    # required tier claim.
    return status in {CapabilityStatus.SUPPORTED, CapabilityStatus.DEGRADED}


def _supported(capabilities: Mapping[str, CapabilityEntry], key: str) -> bool:
    return capabilities[key].status is CapabilityStatus.SUPPORTED


def derive_capability_tier(
    profile_or_capabilities: CapabilityProfile | Mapping[str, CapabilityEntry],
) -> CapabilityTier:
    """Derive A/B/C/unsupported using the frozen precedence ladder."""

    capabilities = _capability_entries(profile_or_capabilities)

    # A: every canonical capability except the intentionally unavailable rich
    # widget is supported.  The ignored widget status cannot affect A.
    if all(_supported(capabilities, key) for key in _TIER_A_KEYS):
        return CapabilityTier.A

    # B: all lifecycle-core capabilities are supported and post-tool
    # observation is at least observable on a best-effort basis.  An unknown
    # value is not accepted by either requirement.
    if all(_supported(capabilities, key) for key in _TIER_B_CORE) and capabilities[
        "post_tool_observation"
    ].status in {CapabilityStatus.SUPPORTED, CapabilityStatus.DEGRADED}:
        return CapabilityTier.B

    # C: prompt-only support is honest whenever either canonical entry can
    # inject context or activate a method, including degraded support.
    if any(
        _available(capabilities[key].status)
        for key in ("prompt_context_injection", "method_skill_invocation")
    ):
        return CapabilityTier.C
    return CapabilityTier.UNSUPPORTED


def validate_capability_profile(profile: CapabilityProfile) -> CapabilityProfile:
    """Reject a stored profile whose computed tier is not authoritative."""

    if not isinstance(profile, CapabilityProfile):
        raise ValidationError("capability profile: expected CapabilityProfile")
    expected = derive_capability_tier(profile)
    if profile.computed_tier is not expected:
        raise ValidationError(
            f"capability profile: stored computed_tier {profile.computed_tier.value!r} "
            f"does not match derived tier {expected.value!r}"
        )
    return profile


# Common names used by capability probe/application ports.
compute_capability_tier = derive_capability_tier
derive_tier = derive_capability_tier
compute_tier = derive_capability_tier
validate_computed_tier = validate_capability_profile


__all__ = [
    "CAPABILITY_KEYS",
    "compute_capability_tier",
    "compute_tier",
    "derive_capability_tier",
    "derive_tier",
    "validate_capability_profile",
    "validate_computed_tier",
]
