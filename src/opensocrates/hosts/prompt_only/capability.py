"""Capability profile for a skills/context-only host surface."""

from __future__ import annotations

from datetime import datetime, timezone

from ...constants import CAPABILITY_KEYS
from ...domain.capability import derive_capability_tier
from ...domain.enums import CapabilityEvidenceKind, CapabilityStatus, HostId
from ...domain.models import CapabilityEntry, CapabilityProfile
from ...version import PRODUCT_VERSION


def _entry(key: str) -> CapabilityEntry:
    if key in {"prompt_context_injection", "method_skill_invocation"}:
        return CapabilityEntry(
            status=CapabilityStatus.DEGRADED,
            evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
            source_url=None,
            source_checked_at="2026-07-15",
            live_probe_id=None,
            limitation_key="prompt_only_no_lifecycle_hooks",
        )
    if key == "rich_card_widget":
        return CapabilityEntry(
            status=CapabilityStatus.UNAVAILABLE,
            evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
            source_url=None,
            source_checked_at="2026-07-15",
            live_probe_id=None,
            limitation_key="product_contract_no_rich_card_widget",
        )
    return CapabilityEntry(
        status=CapabilityStatus.UNAVAILABLE,
        evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
        source_url=None,
        source_checked_at="2026-07-15",
        live_probe_id=None,
        limitation_key=f"prompt_only_{key}",
    )


def default_capability_profile(
    *,
    host: HostId = HostId.PROMPT_ONLY,
    adapter_version: str = PRODUCT_VERSION,
) -> CapabilityProfile:
    entries = {key: _entry(key) for key in CAPABILITY_KEYS}
    checked_at = (
        datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
    return CapabilityProfile(
        host=host,
        host_version_range="prompt-only",
        checked_at=checked_at,
        adapter_version=adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


capability_profile = default_capability_profile


__all__ = ["capability_profile", "default_capability_profile"]
