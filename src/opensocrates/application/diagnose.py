"""Content-free runtime diagnosis projections.

Diagnosis is deliberately an aggregate boundary.  It accepts typed capability
profiles and a typed health summary, then exposes only release identities,
closed capability states, manifest status, and bounded counts.  Paths, task
identifiers, prompts, source URLs, native account fields, and credentials have
no representation in this module.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from ..constants import CAPABILITY_KEYS, SELECTOR_OUTCOME_LABELS
from ..domain.models import CapabilityProfile, CompiledContentBundle
from ..version import (
    CONTENT_REVISION,
    PRODUCT_VERSION,
    ROUTER_VERSION,
    RULESET_VERSION,
    SCHEMA_VERSION,
    VERIFIER_VERSION,
    version_info,
)

_SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")
_SAFE_LABEL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
_MANIFEST_STATES = frozenset({"verified", "unverified", "mismatch", "unavailable", "unknown"})


def _code(value: object, *, fallback: str = "unknown") -> str:
    if isinstance(value, str) and _SAFE_CODE.fullmatch(value.casefold()):
        return value.casefold()
    return fallback


def _label(value: object, *, fallback: str = "unknown") -> str:
    if isinstance(value, str) and _SAFE_LABEL.fullmatch(value.casefold()):
        return value.casefold()
    return fallback


def _bounded_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return min(value, 2**31 - 1)


@dataclass(frozen=True, slots=True)
class HealthAggregate:
    """Safe aggregate health values; no individual file names are retained."""

    status: str = "unknown"
    permissions: str = "unknown"
    record_count: int = 0
    record_bytes: int = 0
    metric_count: int = 0
    metric_bytes: int = 0
    turn_state_count: int = 0
    quarantine_count: int = 0
    error_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _code(self.status))
        object.__setattr__(self, "permissions", _code(self.permissions))
        for name in (
            "record_count",
            "record_bytes",
            "metric_count",
            "metric_bytes",
            "turn_state_count",
            "quarantine_count",
        ):
            object.__setattr__(self, name, _bounded_count(getattr(self, name)))
        codes = tuple(
            sorted(
                {
                    _code(item)
                    for item in self.error_codes
                    if _SAFE_CODE.fullmatch(str(item).casefold())
                }
            )
        )
        object.__setattr__(self, "error_codes", codes[:16])

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "permissions": self.permissions,
            "record_count": self.record_count,
            "record_bytes": self.record_bytes,
            "metric_count": self.metric_count,
            "metric_bytes": self.metric_bytes,
            "turn_state_count": self.turn_state_count,
            "quarantine_count": self.quarantine_count,
            "error_codes": list(self.error_codes),
        }


@dataclass(frozen=True, slots=True)
class DiagnoseSnapshot:
    """Stable, shareable diagnosis data with no sensitive identifiers."""

    versions: Mapping[str, object]
    platform: Mapping[str, str]
    capabilities: Mapping[str, Mapping[str, object]]
    manifest: Mapping[str, object]
    selector: Mapping[str, object]
    health: HealthAggregate

    def to_dict(self) -> dict[str, object]:
        return {
            "versions": dict(self.versions),
            "platform": dict(self.platform),
            "capabilities": {
                key: dict(self.capabilities[key]) for key in sorted(self.capabilities)
            },
            "manifest": dict(self.manifest),
            "selector": dict(self.selector),
            "health": self.health.to_dict(),
        }


def _profile_projection(profile: CapabilityProfile) -> dict[str, object]:
    statuses: dict[str, str] = {}
    limitations: list[str] = []
    for key in sorted(set(profile.capabilities).intersection(CAPABILITY_KEYS)):
        entry = profile.capabilities[key]
        status = getattr(entry.status, "value", entry.status)
        statuses[str(key)] = _code(status)
        limitation = entry.limitation_key
        if isinstance(limitation, str) and _SAFE_CODE.fullmatch(limitation.casefold()):
            limitations.append(limitation.casefold())
    tier = getattr(profile.computed_tier, "value", profile.computed_tier)
    tier_value = (
        tier
        if isinstance(tier, str) and tier in {"A", "B", "C"}
        else _code(tier, fallback="unknown")
    )
    return {
        "host": _label(getattr(profile.host, "value", profile.host)),
        "host_version_range": _code(profile.host_version_range, fallback="unknown"),
        "checked_at": _code(profile.checked_at, fallback="unknown"),
        "adapter_version": _code(str(profile.adapter_version), fallback="unknown"),
        "computed_tier": tier_value,
        "capabilities": dict(list(statuses.items())[: len(CAPABILITY_KEYS)]),
        "limitations": sorted(set(limitations))[:16],
    }


def _content_projection(bundle: CompiledContentBundle | None) -> dict[str, object]:
    if bundle is None:
        return {
            "content_revision": CONTENT_REVISION,
            "method_count": 0,
            "source_tree_hash": None,
            "normalized_semantic_hash": None,
            "status": "unavailable",
        }
    source_hash = (
        bundle.source_tree_hash
        if isinstance(bundle.source_tree_hash, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", bundle.source_tree_hash)
        else None
    )
    semantic_hash = (
        bundle.normalized_semantic_hash
        if isinstance(bundle.normalized_semantic_hash, str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", bundle.normalized_semantic_hash)
        else None
    )
    return {
        "content_revision": int(bundle.content_revision),
        "method_count": min(len(bundle.method_ids), 1000),
        "source_tree_hash": source_hash,
        "normalized_semantic_hash": semantic_hash,
        "status": "loaded"
        if source_hash is not None and semantic_hash is not None
        else "unverified",
    }


def _selector_projection(
    outcomes: Mapping[str, object] | None, *, available: bool
) -> dict[str, object]:
    """Project only fixed content-free outcome labels and bounded counts."""

    if not available:
        return {
            "status": "unavailable",
            "attempt_count": None,
            "outcome_counts": None,
        }
    selected = outcomes or {}
    counts = {label: _bounded_count(selected.get(label, 0)) for label in SELECTOR_OUTCOME_LABELS}
    attempt_count = min(sum(counts.values()), 2**31 - 1)
    return {
        "status": "observed" if attempt_count else "not_observed",
        "attempt_count": attempt_count,
        "outcome_counts": counts,
    }


def build_diagnose(
    *,
    profiles: Mapping[str, CapabilityProfile] | None = None,
    bundle: CompiledContentBundle | None = None,
    health: HealthAggregate | None = None,
    manifest_status: str = "unknown",
    manifest_version: str | None = None,
    checksum_status: str = "unknown",
    platform_name: str = "unknown",
    architecture: str = "unknown",
    selector_outcomes: Mapping[str, object] | None = None,
    selector_outcomes_available: bool = True,
) -> DiagnoseSnapshot:
    """Build a safe diagnosis snapshot from typed aggregates.

    The function intentionally does not discover files or inspect host
    payloads.  Callers that own those boundaries must first reduce them to
    :class:`HealthAggregate` and :class:`CapabilityProfile` values.
    """

    selected: dict[str, Mapping[str, object]] = {}
    for name, profile in tuple((profiles or {}).items())[:8]:
        if isinstance(profile, CapabilityProfile):
            selected[_label(name, fallback=_label(getattr(profile.host, "value", "unknown")))] = (
                _profile_projection(profile)
            )
    versions = dict(version_info())
    versions.update(
        {
            "runtime_version": PRODUCT_VERSION,
            "content_revision": CONTENT_REVISION,
            "schema_version": SCHEMA_VERSION,
            "router_version": ROUTER_VERSION,
            "verifier_version": VERIFIER_VERSION,
            "ruleset_version": RULESET_VERSION,
            "content": _content_projection(bundle),  # type: ignore[dict-item]  # Closed runtime boundary validates this value.
        }
    )
    manifest = {
        "status": manifest_status if manifest_status in _MANIFEST_STATES else "unknown",
        "version": _code(manifest_version, fallback="unknown") if manifest_version else None,
        "checksum_status": checksum_status if checksum_status in _MANIFEST_STATES else "unknown",
    }
    return DiagnoseSnapshot(
        versions=versions,
        platform={"os": _label(platform_name), "architecture": _label(architecture)},
        capabilities=selected,
        manifest=manifest,
        selector=_selector_projection(
            selector_outcomes,
            available=selector_outcomes_available,
        ),
        health=health or HealthAggregate(),
    )


diagnose = build_diagnose


__all__ = ["DiagnoseSnapshot", "HealthAggregate", "build_diagnose", "diagnose"]
