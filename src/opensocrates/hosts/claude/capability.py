"""Dated Claude Code/Cowork capability contract without synthetic receipts."""

from __future__ import annotations

from ...clock import Clock, utc_timestamp
from ...constants import CAPABILITY_KEYS
from ...domain.capability import derive_capability_tier
from ...domain.enums import (
    CapabilityEvidenceKind,
    CapabilityStatus,
    HostId,
)
from ...domain.models import CapabilityEntry, CapabilityProfile
from ...version import PRODUCT_VERSION

EVIDENCE_CAPTURE_DATE = "2026-08-05"
CLAUDE_HOOKS_SOURCE = "https://code.claude.com/docs/en/hooks"
CLAUDE_PLUGINS_SOURCE = "https://code.claude.com/docs/en/plugins-reference"
CLAUDE_CHAT_PLUGINS_SOURCE = "https://support.claude.com/en/articles/13837440-use-plugins-in-claude"


def _source_for(key: str) -> str:
    if key in {"method_skill_invocation", "model_initiated_method_skill_activation"}:
        return CLAUDE_PLUGINS_SOURCE
    if key == "rich_card_widget":
        return CLAUDE_CHAT_PLUGINS_SOURCE
    return CLAUDE_HOOKS_SOURCE


def _contract_entry(key: str) -> CapabilityEntry:
    if key == "rich_card_widget":
        return CapabilityEntry(
            status=CapabilityStatus.UNAVAILABLE,
            evidence_kind=CapabilityEvidenceKind.PRODUCT_CONTRACT,
            source_url=_source_for(key),
            source_checked_at=EVIDENCE_CAPTURE_DATE,
            limitation_key="product-contract-no-rich-card-widget",
        )
    if key == "post_tool_observation":
        return CapabilityEntry(
            status=CapabilityStatus.DEGRADED,
            evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
            source_url=_source_for(key),
            source_checked_at=EVIDENCE_CAPTURE_DATE,
            limitation_key="plugin-package-does-not-enable-tool-observation",
        )
    return CapabilityEntry(
        status=CapabilityStatus.UNKNOWN,
        evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
        source_url=_source_for(key),
        source_checked_at=EVIDENCE_CAPTURE_DATE,
        limitation_key="no-live-probe-receipt",
    )


def default_capability_profile(
    host: HostId = HostId.CLAUDE_CODE,
    *,
    clock: Clock | None = None,
    host_version_range: str = ">=2.1.205",
    adapter_version: str = PRODUCT_VERSION,
) -> CapabilityProfile:
    entries = {key: _contract_entry(key) for key in CAPABILITY_KEYS}
    return CapabilityProfile(
        host=host,
        host_version_range=host_version_range,
        checked_at=utc_timestamp(clock),
        adapter_version=adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


__all__ = [
    "CLAUDE_CHAT_PLUGINS_SOURCE",
    "CLAUDE_HOOKS_SOURCE",
    "CLAUDE_PLUGINS_SOURCE",
    "EVIDENCE_CAPTURE_DATE",
    "default_capability_profile",
]
