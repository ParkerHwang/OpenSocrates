"""Evidence-bound Codex capability profiles and content-free status output."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from ...clock import Clock, utc_timestamp
from ...constants import CAPABILITY_KEYS
from ...domain.capability import derive_capability_tier
from ...domain.enums import CapabilityEvidenceKind, CapabilityStatus, HostId
from ...domain.models import CapabilityEntry, CapabilityProfile
from ...version import PRODUCT_VERSION

EVIDENCE_CAPTURE_DATE = "2026-07-15"
CAPABILITY_EVIDENCE_MAX_AGE_DAYS = 7
CODEX_HOOKS_SOURCE = "https://learn.chatgpt.com/docs/hooks"
CODEX_BUILD_SOURCE = "https://learn.chatgpt.com/docs/build-plugins"
CODEX_PLUGINS_SOURCE = "https://learn.chatgpt.com/docs/plugins"

_SOURCE_BY_CAPABILITY = {
    "prompt_context_injection": CODEX_HOOKS_SOURCE,
    "local_control_execution": CODEX_BUILD_SOURCE,
    "method_skill_invocation": CODEX_BUILD_SOURCE,
    "model_initiated_method_skill_activation": CODEX_HOOKS_SOURCE,
    "method_invocation_observation": CODEX_HOOKS_SOURCE,
    "post_tool_observation": CODEX_HOOKS_SOURCE,
    "post_tool_batch_observation": CODEX_HOOKS_SOURCE,
    "completion_candidate_observation": CODEX_HOOKS_SOURCE,
    "bounded_completion_continuation": CODEX_HOOKS_SOURCE,
    "compaction_reinjection": CODEX_HOOKS_SOURCE,
    "published_artifact_confirmation": CODEX_HOOKS_SOURCE,
    "local_record_write": CODEX_BUILD_SOURCE,
    "deterministic_trace_render": CODEX_BUILD_SOURCE,
    "rich_card_widget": CODEX_PLUGINS_SOURCE,
}


def _checked_date(value: str | None) -> str:
    candidate = value or EVIDENCE_CAPTURE_DATE
    datetime.strptime(candidate, "%Y-%m-%d")
    return candidate


def _status(value: object) -> CapabilityStatus:
    if isinstance(value, CapabilityStatus):
        return value
    if isinstance(value, str):
        try:
            return CapabilityStatus(value)
        except ValueError:
            return CapabilityStatus.UNKNOWN
    if value is True:
        return CapabilityStatus.SUPPORTED
    if value is False:
        return CapabilityStatus.UNAVAILABLE
    return CapabilityStatus.UNKNOWN


def _probe_status(value: object, *, receipt_id: str | None) -> tuple[CapabilityStatus, str | None]:
    """Require a concrete receipt before claiming a probe-derived status."""

    candidate = value
    local_receipt = receipt_id
    if isinstance(value, Mapping):
        candidate = value.get("status", value.get("supported"))
        probe = value.get("probe_id", value.get("receipt_id"))
        if isinstance(probe, str) and probe:
            local_receipt = probe
    status = _status(candidate)
    if status in {CapabilityStatus.SUPPORTED, CapabilityStatus.DEGRADED} and not local_receipt:
        return CapabilityStatus.UNKNOWN, None
    if not isinstance(local_receipt, str) or not local_receipt:
        local_receipt = None
    return status, local_receipt


def _entry(
    key: str,
    *,
    status: CapabilityStatus = CapabilityStatus.UNKNOWN,
    evidence_kind: CapabilityEvidenceKind = CapabilityEvidenceKind.HOST_CONTRACT,
    source_checked_at: str = EVIDENCE_CAPTURE_DATE,
    live_probe_id: str | None = None,
    limitation_key: str | None = None,
) -> CapabilityEntry:
    return CapabilityEntry(
        status=status,
        evidence_kind=evidence_kind,
        source_url=_SOURCE_BY_CAPABILITY.get(key),
        source_checked_at=source_checked_at,
        live_probe_id=live_probe_id,
        limitation_key=limitation_key,
    )


def _contract_default(key: str, checked_date: str) -> CapabilityEntry:
    # This is the one documented partial observation surface.  It is not a
    # claim that every Codex tool is observable: unified_exec, WebSearch, and
    # other non-shell/non-MCP paths remain explicit gaps.
    if key == "post_tool_observation":
        return _entry(
            key,
            status=CapabilityStatus.DEGRADED,
            source_checked_at=checked_date,
            limitation_key="documented-tool-observation-gaps",
        )
    if key == "post_tool_batch_observation":
        return _entry(
            key,
            source_checked_at=checked_date,
            limitation_key="no-official-equivalent-or-live-receipt",
        )
    if key == "rich_card_widget":
        return _entry(
            key,
            status=CapabilityStatus.UNAVAILABLE,
            evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
            source_checked_at=checked_date,
            limitation_key="product-contract-no-rich-card-widget",
        )
    return _entry(
        key,
        source_checked_at=checked_date,
        limitation_key="no-live-probe-receipt",
    )


def build_capability_profile(
    host: HostId = HostId.CODEX_CLI,
    *,
    live_probe: Mapping[str, object] | None = None,
    host_version_range: str = "unknown",
    checked_at: str | None = None,
    adapter_version: str = PRODUCT_VERSION,
    receipt_id: str | None = None,
    source_checked_at: str | None = None,
) -> CapabilityProfile:
    """Build all 14 entries from host-contract facts and explicit receipts.

    The host name and package manifest do not grant support.  Only the dated
    contract defaults above and caller-supplied, receipt-bearing probe facts
    can change an entry.
    """

    checked_date = _checked_date(source_checked_at)
    probes = live_probe or {}
    entries: dict[str, CapabilityEntry] = {}
    for key in CAPABILITY_KEYS:
        base = _contract_default(key, checked_date)
        # v1's rich-card surface is a product contract, not a host probe
        # capability.  No receipt may upgrade it.
        if key == "rich_card_widget":
            entries[key] = base
            continue
        if key not in probes:
            entries[key] = base
            continue
        status, probe_id = _probe_status(probes[key], receipt_id=receipt_id)
        entries[key] = _entry(
            key,
            status=status,
            evidence_kind=CapabilityEvidenceKind.LOCAL_PROBE
            if probe_id
            else CapabilityEvidenceKind.HOST_CONTRACT,
            source_checked_at=checked_date,
            live_probe_id=probe_id,
            limitation_key=None if status is CapabilityStatus.SUPPORTED else key,
        )
    return CapabilityProfile(
        host=host,
        host_version_range=host_version_range or "unknown",
        checked_at=checked_at or utc_timestamp(),
        adapter_version=adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


def default_capability_profile(
    host: HostId = HostId.CODEX_CLI,
    *,
    clock: Clock | None = None,
    host_version_range: str = "unknown",
    adapter_version: str = PRODUCT_VERSION,
) -> CapabilityProfile:
    """Return the no-live-probe profile; lifecycle claims remain unknown."""

    return build_capability_profile(
        host,
        host_version_range=host_version_range,
        checked_at=utc_timestamp(clock),
        adapter_version=adapter_version,
    )


def _availability_state(
    *,
    hooks_enabled: bool | None,
    trust_state: str,
    allow_managed_hooks_only: bool,
    plugin_hooks_loaded: bool | None,
    managed_hooks_loaded: bool | None,
) -> tuple[str | None, str | None]:
    if hooks_enabled is False:
        return "hooks-disabled", "hooks_disabled"
    if allow_managed_hooks_only and plugin_hooks_loaded is not True:
        return "managed-only-policy", "plugin_source_excluded_by_policy"
    folded = trust_state.casefold() if isinstance(trust_state, str) else "unknown"
    if folded in {"unknown", "untrusted", "unverified", "pending_review", "pending"}:
        return "plugin-hook-trust-required", "plugin_hook_trust_required"
    if plugin_hooks_loaded is False and managed_hooks_loaded is True:
        return "plugin-hook-not-loaded", "plugin_hook_not_loaded"
    return None, None


def capability_profile_for_availability(
    *,
    hooks_enabled: bool | None = None,
    trust_state: str = "unknown",
    allow_managed_hooks_only: bool = False,
    plugin_hooks_loaded: bool | None = None,
    managed_hooks_loaded: bool | None = None,
    features_hooks: bool | None = None,
    features: Mapping[str, object] | None = None,
    host: HostId = HostId.CODEX_CLI,
    clock: Clock | None = None,
    adapter_version: str = PRODUCT_VERSION,
    host_version_range: str = "unknown",
) -> CapabilityProfile:
    """Represent disabled, untrusted, and managed-only states honestly."""

    if hooks_enabled is None:
        hooks_enabled = features_hooks
    if hooks_enabled is None and isinstance(features, Mapping):
        candidate = features.get("hooks")
        hooks_enabled = candidate if isinstance(candidate, bool) else None
    state, limitation = _availability_state(
        hooks_enabled=hooks_enabled,
        trust_state=trust_state,
        allow_managed_hooks_only=allow_managed_hooks_only,
        plugin_hooks_loaded=plugin_hooks_loaded,
        managed_hooks_loaded=managed_hooks_loaded,
    )
    evidence: dict[str, object] = {}
    if state is not None:
        evidence = {
            "prompt_context_injection": {
                "status": "degraded",
                "probe_id": state,
            },
            "method_skill_invocation": {
                "status": "degraded",
                "probe_id": state,
            },
        }
    profile = build_capability_profile(
        host,
        live_probe=evidence,
        host_version_range=host_version_range,
        checked_at=utc_timestamp(clock),
        adapter_version=adapter_version,
    )
    if state is None:
        return profile
    # Attach one stable state limitation to the two surfaces that are
    # degraded.  The status projection remains content-free.
    entries = dict(profile.capabilities)
    for key in ("prompt_context_injection", "method_skill_invocation"):
        entry = entries[key]
        entries[key] = _entry(
            key,
            status=entry.status,
            evidence_kind=entry.evidence_kind,
            source_checked_at=entry.source_checked_at,
            live_probe_id=entry.live_probe_id,
            limitation_key=limitation,
        )
    return CapabilityProfile(
        host=profile.host,
        host_version_range=profile.host_version_range,
        checked_at=profile.checked_at,
        adapter_version=profile.adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


def profile_expired(
    profile: CapabilityProfile,
    *,
    now: datetime | None = None,
    host_version: str | None = None,
    max_age_days: int = CAPABILITY_EVIDENCE_MAX_AGE_DAYS,
) -> bool:
    """Return true when dated evidence is stale or version-bound mismatch."""

    if not isinstance(profile, CapabilityProfile):
        return True
    if max_age_days < 0:
        return True
    try:
        checked = datetime.strptime(profile.checked_at, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return True
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if current - checked > timedelta(days=max_age_days):
        return True
    if host_version and profile.host_version_range not in {"unknown", host_version}:
        return True
    return False


def capability_summary(
    profile: CapabilityProfile, *, host_version: str | None = None
) -> dict[str, Any]:
    """Return a content-free diagnostic projection for status commands."""

    expired = profile_expired(profile, host_version=host_version)
    statuses = {key: entry.status.value for key, entry in profile.capabilities.items()}
    if all(
        entry.status is CapabilityStatus.UNKNOWN
        for entry in profile.capabilities.values()
        if entry.status is not CapabilityStatus.UNAVAILABLE
    ):
        tier = "unknown"
    else:
        tier = profile.computed_tier.value
    return {
        "host": profile.host.value,
        "host_version_range": profile.host_version_range,
        "adapter_version": str(profile.adapter_version),
        "checked_at": profile.checked_at,
        "evidence_expired": expired,
        "computed_tier": tier,
        "capabilities": statuses,
        "limitations": {
            key: entry.limitation_key
            for key, entry in profile.capabilities.items()
            if entry.limitation_key is not None
        },
    }


def capability_status(
    profile: CapabilityProfile, *, host_version: str | None = None
) -> dict[str, Any]:
    """Compatibility/status alias used by the Codex probe command."""

    return capability_summary(profile, host_version=host_version)


profile_for_availability = capability_profile_for_availability
compute_capability_profile = build_capability_profile
diagnose_capabilities = capability_summary


__all__ = [
    "CAPABILITY_EVIDENCE_MAX_AGE_DAYS",
    "CODEX_BUILD_SOURCE",
    "CODEX_HOOKS_SOURCE",
    "CODEX_PLUGINS_SOURCE",
    "EVIDENCE_CAPTURE_DATE",
    "build_capability_profile",
    "capability_profile_for_availability",
    "capability_status",
    "capability_summary",
    "compute_capability_profile",
    "default_capability_profile",
    "diagnose_capabilities",
    "profile_expired",
    "profile_for_availability",
]
