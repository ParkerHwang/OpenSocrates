"""Content-free capability probe/show command projections."""

from __future__ import annotations

import re

from ..domain.models import CapabilityProfile

_SAFE_VALUE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:+<>=,* -]{0,127}$")
_SAFE_CODE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,63}$")


def _safe_value(value: object, *, fallback: str = "unknown") -> str:
    if (
        isinstance(value, str)
        and _SAFE_VALUE.fullmatch(value)
        and "/" not in value
        and "\\" not in value
    ):
        return value
    return fallback


def _safe_code(value: object) -> str | None:
    if isinstance(value, str) and _SAFE_CODE.fullmatch(value.casefold()):
        return value.casefold()
    return None


def capability_summary(profile: CapabilityProfile | None) -> dict[str, object]:
    if not isinstance(profile, CapabilityProfile):
        return {"status": "unavailable", "error_code": "capability_profile_unavailable"}
    tier = getattr(profile.computed_tier, "value", "unknown")
    return {
        "status": "ok",
        "host": _safe_code(getattr(profile.host, "value", None)) or "unknown",
        "host_version_range": _safe_value(profile.host_version_range),
        "adapter_version": _safe_value(str(profile.adapter_version)),
        "checked_at": _safe_value(profile.checked_at),
        "computed_tier": _safe_code(tier) or "unknown",
        "capabilities": {
            key: _safe_code(getattr(entry.status, "value", None)) or "unknown"
            for key, entry in sorted(profile.capabilities.items())
        },
        "limitations": {
            key: _safe_code(entry.limitation_key)
            for key, entry in sorted(profile.capabilities.items())
            if _safe_code(entry.limitation_key) is not None
        },
    }


def show_capabilities(profile: CapabilityProfile | None) -> dict[str, object]:
    return capability_summary(profile)


def probe_capabilities(host: str, *, profile: CapabilityProfile | None = None) -> dict[str, object]:
    """Report only the injected profile; absence is never inferred as support."""

    result = capability_summary(profile)
    if result.get("status") == "unavailable":
        return {"status": "unavailable", "host": host, "error_code": "live_probe_unavailable"}
    result["probe"] = "not_run"
    result["host"] = host
    return result


__all__ = ["capability_summary", "probe_capabilities", "show_capabilities"]
