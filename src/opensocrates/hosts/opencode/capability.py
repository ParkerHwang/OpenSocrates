"""Evidence-bounded capability profile for stable OpenCode 1.18.18."""

from __future__ import annotations

from datetime import datetime, timezone

from ...constants import CAPABILITY_KEYS
from ...domain.capability import derive_capability_tier
from ...domain.enums import CapabilityEvidenceKind, CapabilityStatus, HostId
from ...domain.models import CapabilityEntry, CapabilityProfile
from ...version import PRODUCT_VERSION

_DOCS_CHECKED_AT = "2026-08-13"
_PLUGINS_URL = "https://opencode.ai/docs/plugins/"
_SKILLS_URL = "https://opencode.ai/docs/skills/"
_LIVE_PROBE_ID = "opencode-1.18.18-run-tui-deepseek-v4-flash-2026-08-13"


def _entry(key: str) -> CapabilityEntry:
    if key == "prompt_context_injection":
        return CapabilityEntry(
            status=CapabilityStatus.SUPPORTED,
            evidence_kind=CapabilityEvidenceKind.LOCAL_PROBE,
            source_url=_PLUGINS_URL,
            source_checked_at=_DOCS_CHECKED_AT,
            live_probe_id=_LIVE_PROBE_ID,
            limitation_key=None,
        )
    if key == "method_skill_invocation":
        return CapabilityEntry(
            status=CapabilityStatus.DEGRADED,
            evidence_kind=CapabilityEvidenceKind.LOCAL_PROBE,
            source_url=_SKILLS_URL,
            source_checked_at=_DOCS_CHECKED_AT,
            live_probe_id=_LIVE_PROBE_ID,
            limitation_key="opencode_skill_discovered_not_live_invoked",
        )
    if key == "model_initiated_method_skill_activation":
        return CapabilityEntry(
            status=CapabilityStatus.DEGRADED,
            evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
            source_url=_SKILLS_URL,
            source_checked_at=_DOCS_CHECKED_AT,
            live_probe_id=None,
            limitation_key="opencode_native_skill_advertised_not_provider_matrixed",
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
            limitation_key="opencode_bridge_has_no_native_or_python_runtime",
        )
    return CapabilityEntry(
        status=CapabilityStatus.UNAVAILABLE,
        evidence_kind=CapabilityEvidenceKind.HOST_CONTRACT,
        source_url=_PLUGINS_URL,
        source_checked_at=_DOCS_CHECKED_AT,
        live_probe_id=None,
        limitation_key=f"opencode_no_{key}_hook",
    )


def default_capability_profile(*, adapter_version: str = PRODUCT_VERSION) -> CapabilityProfile:
    entries = {key: _entry(key) for key in CAPABILITY_KEYS}
    checked_at = (
        datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
    return CapabilityProfile(
        host=HostId.OPENCODE_CLI,
        host_version_range=">=1.18.18,<2.0.0",
        checked_at=checked_at,
        adapter_version=adapter_version,
        computed_tier=derive_capability_tier(entries),
        capabilities=entries,
    )


capability_profile = default_capability_profile


__all__ = ["capability_profile", "default_capability_profile"]
