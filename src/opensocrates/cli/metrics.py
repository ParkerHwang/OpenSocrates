"""Aggregate-only local metrics command handlers."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from .runtime import write_safe_export


def _read_metrics(store: Any) -> tuple[Any, ...]:
    if store is None:
        raise RuntimeError("metrics store unavailable")
    reader = getattr(store, "read", None)
    if not callable(reader):
        raise RuntimeError("metrics store unavailable")
    try:
        value = reader()
    except TypeError:
        value = reader(month=datetime.now(timezone.utc).strftime("%Y-%m"))
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes, dict)):
        raise RuntimeError("metrics result is invalid")
    return tuple(value)


def aggregate_metrics(store: Any) -> dict[str, object]:
    try:
        metrics = _read_metrics(store)
    except Exception:
        return {"status": "unavailable", "error_code": "metrics_store_unavailable"}
    events = Counter()  # type: ignore[var-annotated]  # Closed runtime boundary validates this value.
    hosts = Counter()  # type: ignore[var-annotated]  # Closed runtime boundary validates this value.
    locales = Counter()  # type: ignore[var-annotated]  # Closed runtime boundary validates this value.
    for metric in metrics:
        event = getattr(
            getattr(metric, "event", None), "value", getattr(metric, "event", "unknown")
        )
        host = getattr(getattr(metric, "host", None), "value", getattr(metric, "host", "unknown"))
        locale = getattr(metric, "locale", "unknown")
        events[str(event)] += 1
        hosts[str(host)] += 1
        locales[str(locale)] += 1
    return {
        "status": "ok",
        "count": len(metrics),
        "events": dict(sorted(events.items())),
        "hosts": dict(sorted(hosts.items())),
        "locales": dict(sorted(locales.items())),
    }


def show_metrics(store: Any) -> dict[str, object]:
    return aggregate_metrics(store)


def export_metrics(
    store: Any, destination: str | None = None, *, overwrite: bool = False
) -> dict[str, object]:
    result = aggregate_metrics(store)
    if destination is None or result.get("status") != "ok":
        return result
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    try:
        write_safe_export(destination, payload, overwrite=overwrite)
    except Exception:
        return {"status": "rejected", "error_code": "unsafe_export_destination"}
    return {"status": "ok", "exported": True, "count": result.get("count", 0)}


def reset_metrics(store: Any) -> dict[str, object]:
    reset = getattr(store, "reset", None)
    if callable(reset):
        try:
            reset()
            return {"status": "ok", "reset": True}
        except Exception:
            pass
    # The append-only filesystem store intentionally has no broad reset API;
    # do not reach into arbitrary paths from the CLI.
    return {"status": "unsupported", "error_code": "metrics_reset_unavailable"}


__all__ = ["aggregate_metrics", "export_metrics", "reset_metrics", "show_metrics"]
