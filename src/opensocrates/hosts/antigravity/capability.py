"""Evidence-bounded capability profile for Antigravity v1.2."""

from __future__ import annotations

from datetime import datetime, timezone

from ...constants import CAPABILITY_KEYS
from ...domain.capability import derive_capability_tier
from ...domain.enums import CapabilityEvidenceKind, CapabilityStatus, HostId
from ...domain.models import CapabilityEntry, CapabilityProfile
from ...version import PRODUCT_VERSION

_DOCS_CHECKED_AT = "2026-08-12"
_SKILLS_URL = "https://antigravity.google/docs/skills"
_PLUGINS_URL = "https://antigravity.google/docs/ide/plugins"


def _entry(key: str) -> CapabilityEntry:
    if key == "method_skill_invocation":
        return CapabilityEntry(
            status=CapabilityStatus.DEGRADED,
            evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
            source_url=_SKILLS_URL,
            source_checked_at=_DOCS_CHECKED_AT,
            live_probe_id=None,
            limitation_key="antigravity_explicit_skill_only",
        )
    if key == "rich_card_widget":
        return CapabilityEntry(
            status=CapabilityStatus.UNAVAILABLE,
            evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
            source_url=None,
            source_checked_at=_DOCS_CHECKED_AT,
            live_probe_id=None,
            limitation_key="product_contract_no_rich_card_widget",
        )
    if key in {"local_record_write", "deterministic_trace_render"}:
        return CapabilityEntry(
            status=CapabilityStatus.UNAVAILABLE,
            evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
            source_url=None,
            source_checked_at=_DOCS_CHECKED_AT,
            live_probe_id=None,
            limitation_key="antigravity_no_runtime",
        )
    return CapabilityEntry(
        status=CapabilityStatus.UNKNOWN,
        evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
        source_url=_PLUGINS_URL,
        source_checked_at=_DOCS_CHECKED_AT,
        live_probe_id=None,
        limitation_key="antigravity_no_live_hook_receipt",
    )


def default_capability_profile(*, adapter_version: str = PRODUCT_VERSION) -> CapabilityProfile:
    entries = {key: _entry(key) for key in CAPABILITY_KEYS}
    checked_at = (
        datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
    return CapabilityProfile(
        host=HostId.ANTIGRAVITY_CLI,
        host_version_range=">=1.0.0",
        checked_at=checked_at,
        adapter_version=adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


capability_profile = default_capability_profile


__all__ = ["capability_profile", "default_capability_profile"]
