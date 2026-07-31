"""Non-invasive Codex capability probe/status source.

The adapter cannot manufacture host evidence.  This module accepts an
explicit, content-free receipt from an outer installation/probe runner and
otherwise returns the dated contract baseline with an unavailable-live-probe
diagnostic.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ...clock import Clock, utc_timestamp
from ...domain.enums import HostId
from ...domain.models import CapabilityProfile
from ...version import PRODUCT_VERSION
from .capability import (
    build_capability_profile,
    capability_summary,
    default_capability_profile,
    profile_expired,
)
from .capability import (
    capability_status as profile_capability_status,
)

PROBE_RECEIPT_SCHEMA = "opensocrates.codex-probe-receipt/1.0.0"


@dataclass(frozen=True, slots=True)
class CodexProbeResult:
    """Typed, content-free output of one probe/status read."""

    profile: CapabilityProfile
    status: str
    source: str
    receipt_id: str | None = None
    diagnostics: tuple[str, ...] = ()
    evidence_expired: bool = False

    @property
    def summary(self) -> dict[str, Any]:
        return capability_summary(self.profile)

    @property
    def capabilities(self) -> CapabilityProfile:
        return self.profile

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": PROBE_RECEIPT_SCHEMA,
            "status": self.status,
            "source": self.source,
            "receipt_id": self.receipt_id,
            "diagnostics": list(self.diagnostics),
            "profile": self.summary,
            "evidence_expired": self.evidence_expired,
        }


def _receipt_fields(
    receipt: Mapping[str, Any],
) -> tuple[str | None, Mapping[str, object] | None, str | None]:
    probe_id = receipt.get("probe_id", receipt.get("receipt_id"))
    receipt_id = probe_id if isinstance(probe_id, str) and probe_id else None
    capabilities = receipt.get("capabilities")
    if not isinstance(capabilities, Mapping):
        capabilities = receipt.get("statuses")
    if not isinstance(capabilities, Mapping):
        capabilities = None
    host_version = receipt.get("host_version", receipt.get("host_version_range"))
    return receipt_id, capabilities, host_version if isinstance(host_version, str) else None


def probe_capabilities(
    receipt: Mapping[str, Any] | None = None,
    *,
    host: HostId = HostId.CODEX_CLI,
    host_version_range: str = "unknown",
    adapter_version: str = PRODUCT_VERSION,
    clock: Clock | None = None,
) -> CodexProbeResult:
    """Build a profile from an explicit receipt, or report no live probe."""

    if not isinstance(receipt, Mapping):
        profile = default_capability_profile(
            host,
            clock=clock,
            host_version_range=host_version_range,
            adapter_version=adapter_version,
        )
        return CodexProbeResult(
            profile=profile,
            status="unavailable",
            source="host_contract",
            diagnostics=("live_probe_unavailable",),
            evidence_expired=profile_expired(profile),
        )
    receipt_id, capabilities, receipt_version = _receipt_fields(receipt)
    if not receipt_id or capabilities is None:
        profile = default_capability_profile(
            host,
            clock=clock,
            host_version_range=host_version_range,
            adapter_version=adapter_version,
        )
        return CodexProbeResult(
            profile=profile,
            status="rejected",
            source="host_contract",
            diagnostics=("probe_receipt_missing_id_or_capabilities",),
            evidence_expired=profile_expired(profile),
        )
    version_range = receipt_version or host_version_range
    profile = build_capability_profile(
        host,
        live_probe=capabilities,
        host_version_range=version_range,
        checked_at=utc_timestamp(clock),
        adapter_version=adapter_version,
        receipt_id=receipt_id,
    )
    return CodexProbeResult(
        profile=profile,
        status="accepted",
        source="local_probe",
        receipt_id=receipt_id,
        diagnostics=(),
        evidence_expired=profile_expired(profile, host_version=version_range),
    )


def capability_status(
    profile_or_result: CapabilityProfile | CodexProbeResult,
    *,
    host_version: str | None = None,
) -> dict[str, Any]:
    """Return only safe status scalars, never receipt payload or native data."""

    profile = (
        profile_or_result.profile
        if isinstance(profile_or_result, CodexProbeResult)
        else profile_or_result
    )
    return profile_capability_status(profile, host_version=host_version)


def diagnose(
    profile_or_result: CapabilityProfile | CodexProbeResult,
    *,
    host_version: str | None = None,
) -> dict[str, Any]:
    return capability_status(profile_or_result, host_version=host_version)


status_source = probe_capabilities
probe = probe_capabilities
capability_probe = probe_capabilities


__all__ = [
    "CodexProbeResult",
    "PROBE_RECEIPT_SCHEMA",
    "capability_probe",
    "capability_status",
    "diagnose",
    "probe",
    "probe_capabilities",
    "status_source",
]
