"""Thin command adapters for the authoritative settings application service."""

from __future__ import annotations

from typing import Any

from ..application.change_settings import persist_preferences_reset, persist_rigor
from ..domain.enums import Rigor


def _safe_settings(settings: Any) -> dict[str, object]:
    value = getattr(settings, "to_dict", lambda: {})()  # type: ignore[var-annotated]  # Closed runtime boundary validates this value.
    if not isinstance(value, dict):
        return {"status": "unavailable", "error_code": "settings_invalid"}
    # Only the public rigor projection belongs in this command response.
    rigor = getattr(settings, "default_rigor", None)
    return {
        "status": "ok",
        "rigor": getattr(rigor, "value", rigor)
        if isinstance(getattr(rigor, "value", rigor), str)
        else "unknown",
        "revision": int(getattr(settings, "revision", 0))
        if isinstance(getattr(settings, "revision", 0), int)
        else 0,
    }


def handle_rigor_get(repository: Any) -> dict[str, object]:
    if repository is None or not callable(getattr(repository, "load", None)):
        return {"status": "unavailable", "error_code": "settings_store_unavailable"}
    try:
        return _safe_settings(repository.load())
    except Exception:
        return {"status": "unavailable", "error_code": "settings_store_unavailable"}


def handle_rigor_set(repository: Any, level: str, *, once: bool = False) -> dict[str, object]:
    try:
        rigor = Rigor(level)
    except ValueError:
        return {"status": "rejected", "error_code": "invalid_rigor"}
    if repository is None:
        return {"status": "unavailable", "error_code": "settings_store_unavailable"}
    try:
        if once:
            settings = repository.load()
            return {
                **_safe_settings(settings),
                "status": "accepted",
                "scope": "next_task",
                "rigor": rigor.value,
            }
        return {
            **_safe_settings(persist_rigor(repository, rigor)),
            "status": "ok",
            "scope": "default",
        }
    except Exception:
        return {"status": "unavailable", "error_code": "settings_write_unavailable"}


def handle_rigor_reset(repository: Any) -> dict[str, object]:
    if repository is None:
        return {"status": "unavailable", "error_code": "settings_store_unavailable"}
    try:
        result = persist_rigor(repository, Rigor.TOGETHER)
        # Reset the intervention preference state through its own authoritative
        # application function; a failure here does not expose store detail.
        try:
            result = persist_preferences_reset(repository)
        except Exception:
            pass
        return {**_safe_settings(result), "status": "ok", "scope": "default"}
    except Exception:
        return {"status": "unavailable", "error_code": "settings_write_unavailable"}


__all__ = ["handle_rigor_get", "handle_rigor_reset", "handle_rigor_set"]
