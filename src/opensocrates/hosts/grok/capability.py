"""Observed capability profile for Grok Build 1.0.3."""

from __future__ import annotations

from datetime import datetime, timezone

from ...constants import CAPABILITY_KEYS
from ...domain.capability import derive_capability_tier
from ...domain.enums import CapabilityEvidenceKind, CapabilityStatus, HostId
from ...domain.models import CapabilityEntry, CapabilityProfile
from ...version import PRODUCT_VERSION

_CHECKED_AT = "2026-08-13"
_SKILLS_URL = "https://docs.x.ai/build/features/skills-plugins-marketplaces"
_HOOKS_URL = "https://docs.x.ai/build/features/hooks"
_LIVE_PROBE_ID = "grok-build-1.0.3-2026-08-13"


def _entry(key: str) -> CapabilityEntry:
    if key in {"method_skill_invocation", "model_initiated_method_skill_activation"}:
        return CapabilityEntry(
            status=CapabilityStatus.SUPPORTED,
            evidence_kind=CapabilityEvidenceKind.LOCAL_PROBE,
            source_url=_SKILLS_URL,
            source_checked_at=_CHECKED_AT,
            live_probe_id=_LIVE_PROBE_ID,
            limitation_key=None,
        )
    if key == "prompt_context_injection":
        return CapabilityEntry(
            status=CapabilityStatus.DEGRADED,
            evidence_kind=CapabilityEvidenceKind.LOCAL_PROBE,
            source_url=_HOOKS_URL,
            source_checked_at=_CHECKED_AT,
            live_probe_id=_LIVE_PROBE_ID,
            limitation_key="grok_native_skill_context_only_passive_hook_output_ignored",
        )
    if key in {
        "local_control_execution",
        "method_invocation_observation",
        "post_tool_observation",
        "post_tool_batch_observation",
        "completion_candidate_observation",
        "bounded_completion_continuation",
        "compaction_reinjection",
        "published_artifact_confirmation",
        "local_record_write",
        "deterministic_trace_render",
        "rich_card_widget",
    }:
        return CapabilityEntry(
            status=CapabilityStatus.UNAVAILABLE,
            evidence_kind=CapabilityEvidenceKind.LOCAL_PROBE,
            source_url=_HOOKS_URL if "observation" in key or "continuation" in key else None,
            source_checked_at=_CHECKED_AT,
            live_probe_id=_LIVE_PROBE_ID,
            limitation_key="grok_content_only_no_runtime",
        )
    return CapabilityEntry(
        status=CapabilityStatus.UNKNOWN,
        evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
        source_url=_HOOKS_URL,
        source_checked_at=_CHECKED_AT,
        live_probe_id=None,
        limitation_key="grok_capability_not_observed",
    )


def default_capability_profile(*, adapter_version: str = PRODUCT_VERSION) -> CapabilityProfile:
    entries = {key: _entry(key) for key in CAPABILITY_KEYS}
    checked_at = (
        datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
    return CapabilityProfile(
        host=HostId.GROK_BUILD,
        host_version_range=">=1.0.3",
        checked_at=checked_at,
        adapter_version=adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


capability_profile = default_capability_profile


__all__ = ["capability_profile", "default_capability_profile"]
