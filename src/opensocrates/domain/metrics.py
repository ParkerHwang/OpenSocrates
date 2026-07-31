"""Closed, content-free constructors for local metrics.

``LocalMetric`` is a schema model shared with the persistence layer.  This
module is the stricter construction boundary: callers may create metrics only
through the closed event/attribute table below.  It intentionally has no
filesystem, host, network, prompt, card, or model dependency.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from math import isfinite
from types import MappingProxyType
from typing import Final

from ..clock import Clock, SystemClock, utc_date
from ..constants import CAPABILITY_KEYS
from ..errors import OpenSocratesError
from ..version import PRODUCT_VERSION
from .enums import (
    DurationBucket,
    HostId,
    InterventionClass,
    MetricEventName,
    Rigor,
)
from .models import LocalMetric
from .validation import validate_model


class MetricValidationError(ValueError):
    """Raised when a metric event or attribute is outside the closed contract."""


# Keep the table explicit.  The values are the only attribute names that may
# reach a LocalMetric JSON object for the corresponding event.
METRIC_ATTRIBUTE_ALLOWLIST: Final = MappingProxyType(
    {
        MetricEventName.JUDGMENT_STARTED: frozenset(),
        MetricEventName.CARD_RENDERED: frozenset(),
        MetricEventName.CARD_VALIDATED: frozenset({"first_session"}),
        MetricEventName.RIGOR_CHANGED: frozenset({"from_rigor", "to_rigor"}),
        MetricEventName.INTERVENTION_EMITTED: frozenset({"class"}),
        MetricEventName.INTERVENTION_EXPLICITLY_ACCEPTED: frozenset({"class"}),
        MetricEventName.INTERVENTION_EXPLICITLY_DISMISSED: frozenset({"class"}),
        MetricEventName.CONCLUSION_CHANGED: frozenset(),
        MetricEventName.TRACE_REQUESTED: frozenset(),
        MetricEventName.RUNTIME_DEGRADED: frozenset({"capability_key"}),
    }
)

# The aliases make the table discoverable to adapters without creating a
# second source of truth.
ATTRIBUTE_ALLOWLIST: Final = METRIC_ATTRIBUTE_ALLOWLIST
METRIC_ATTRIBUTES: Final = METRIC_ATTRIBUTE_ALLOWLIST

_REQUIRED_ATTRIBUTES: Final = MappingProxyType(
    {
        MetricEventName.RIGOR_CHANGED: frozenset({"from_rigor", "to_rigor"}),
        MetricEventName.INTERVENTION_EMITTED: frozenset({"class"}),
        MetricEventName.INTERVENTION_EXPLICITLY_ACCEPTED: frozenset({"class"}),
        MetricEventName.INTERVENTION_EXPLICITLY_DISMISSED: frozenset({"class"}),
        MetricEventName.RUNTIME_DEGRADED: frozenset({"capability_key"}),
    }
)

TASK_SCOPED_METRICS: Final = frozenset(
    event for event in MetricEventName if event is not MetricEventName.RUNTIME_DEGRADED
)
DURATION_BUCKETS: Final = (
    DurationBucket.UNDER_50,
    DurationBucket.MS_50_99,
    DurationBucket.MS_100_249,
    DurationBucket.MS_250_999,
    DurationBucket.MS_1000_PLUS,
)

_CAPABILITY_KEYS = frozenset(CAPABILITY_KEYS)
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FORBIDDEN_ATTRIBUTE_WORDS = frozenset(
    {
        "account",
        "card",
        "credential",
        "install",
        "model",
        "output",
        "path",
        "prompt",
        "raw",
        "reasoning",
        "secret",
        "session",
        "source",
        "task",
        "token",
        "transcript",
        "url",
    }
)


def _event(value: MetricEventName | str) -> MetricEventName:
    try:
        return value if isinstance(value, MetricEventName) else MetricEventName(value)
    except (TypeError, ValueError) as error:
        raise MetricValidationError("metric event is not in the closed allowlist") from error


def _day(value: str | date | datetime | None, *, clock: Clock | None) -> str:
    if value is None:
        return utc_date(clock or SystemClock())
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise MetricValidationError("metric day datetime must be timezone-aware")
        candidate = value.astimezone(timezone.utc).date().isoformat()
    elif isinstance(value, date):
        candidate = value.isoformat()
    else:
        candidate = value
    if not isinstance(candidate, str) or _DAY_RE.fullmatch(candidate) is None:
        raise MetricValidationError("metric occurred_at_day must be YYYY-MM-DD")
    try:
        date.fromisoformat(candidate)
    except ValueError as error:
        raise MetricValidationError("metric occurred_at_day is not a calendar date") from error
    return candidate


def duration_bucket(milliseconds: int | float | None) -> DurationBucket | None:
    """Convert an in-memory duration to the closed day-safe bucket vocabulary."""

    if milliseconds is None:
        return None
    if isinstance(milliseconds, bool) or not isinstance(milliseconds, (int, float)):
        raise MetricValidationError("metric duration must be a number of milliseconds")
    if isinstance(milliseconds, float) and not isfinite(milliseconds):
        raise MetricValidationError("metric duration must be finite")
    if milliseconds < 0:
        raise MetricValidationError("metric duration must not be negative")
    if milliseconds < 50:
        return DurationBucket.UNDER_50
    if milliseconds < 100:
        return DurationBucket.MS_50_99
    if milliseconds < 250:
        return DurationBucket.MS_100_249
    if milliseconds < 1000:
        return DurationBucket.MS_250_999
    return DurationBucket.MS_1000_PLUS


bucket_duration = duration_bucket
bucket_duration_ms = duration_bucket


def _scalar_attribute(key: str, value: object) -> object:
    if not isinstance(key, str) or not key or key.casefold() in _FORBIDDEN_ATTRIBUTE_WORDS:
        raise MetricValidationError(f"metric attribute name is not allowed: {key!r}")
    if isinstance(value, bool):
        return value
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        if isinstance(value, int):
            return value
        if not value or "\n" in value or "\r" in value or "\x00" in value:
            raise MetricValidationError(f"metric attribute {key!r} is not a safe scalar")
        if any(word in value.casefold() for word in ("http://", "https://", "/", "\\")):
            raise MetricValidationError(f"metric attribute {key!r} may not carry a path or URL")
        return value
    raise MetricValidationError(f"metric attribute {key!r} must be a closed scalar")


def _attributes(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    event: MetricEventName, attributes: Mapping[str, object] | None
) -> dict[str, object]:
    if attributes is None:
        candidate: dict[str, object] = {}
    elif not isinstance(attributes, Mapping):
        raise MetricValidationError("metric attributes must be a mapping")
    else:
        candidate = dict(attributes)
    allowed = METRIC_ATTRIBUTE_ALLOWLIST[event]
    unknown = set(candidate) - set(allowed)
    if unknown:
        raise MetricValidationError(f"metric attributes are not allowed: {sorted(unknown)}")
    required = _REQUIRED_ATTRIBUTES.get(event, frozenset())
    if set(candidate) != set(required) and required:
        missing = sorted(required - set(candidate))
        extras = sorted(set(candidate) - set(required))
        raise MetricValidationError(
            f"metric attributes for {event.value} must include {missing} and reject {extras}"
        )
    result: dict[str, object] = {}
    for key, value in candidate.items():
        scalar = _scalar_attribute(key, value)
        if key == "first_session" and not isinstance(scalar, bool):
            raise MetricValidationError("first_session must be boolean")
        if key in {"from_rigor", "to_rigor"}:
            try:
                scalar = Rigor(scalar)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            except (TypeError, ValueError) as error:
                raise MetricValidationError(f"{key} must be a closed rigor value") from error
            scalar = scalar.value
        elif key == "class":
            try:
                scalar = InterventionClass(scalar)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            except (TypeError, ValueError) as error:
                raise MetricValidationError("class must be a closed intervention value") from error
            scalar = scalar.value
        elif key == "capability_key":
            if not isinstance(scalar, str) or scalar not in _CAPABILITY_KEYS:
                raise MetricValidationError("capability_key must be a closed capability code")
        result[key] = scalar
    return {key: result[key] for key in sorted(result)}


def validate_local_metric(metric: LocalMetric) -> LocalMetric:
    """Validate a LocalMetric, including this module's closed attributes."""

    if not isinstance(metric, LocalMetric):
        raise MetricValidationError("expected LocalMetric")
    event = _event(metric.event)
    expected = _attributes(event, metric.attributes)
    if expected != metric.attributes:
        raise MetricValidationError("metric attributes are not canonically ordered/typed")
    try:
        validate_model(metric)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise MetricValidationError("metric model is invalid") from error
    return metric


def build_local_metric(
    event: MetricEventName | str,
    *,
    host: HostId | str,
    locale: str,
    rigor: Rigor | str,
    attributes: Mapping[str, object] | None = None,
    occurred_at_day: str | date | datetime | None = None,
    duration_ms: int | float | None = None,
    product_version: str = PRODUCT_VERSION,
    recording_enabled: bool = True,
    task_scoped: bool | None = None,
    clock: Clock | None = None,
) -> LocalMetric | None:
    """Build one closed metric or return ``None`` for a disabled task metric."""

    metric_event = _event(event)
    if not isinstance(recording_enabled, bool):
        raise MetricValidationError("recording_enabled must be boolean")
    scoped = metric_event in TASK_SCOPED_METRICS if task_scoped is None else task_scoped
    if not isinstance(scoped, bool):
        raise MetricValidationError("task_scoped must be boolean")
    if scoped and not recording_enabled:
        return None
    if not isinstance(locale, str) or locale not in {"en", "ko"}:
        raise MetricValidationError("metric locale must be en or ko")
    try:
        metric_host = host if isinstance(host, HostId) else HostId(host)
        metric_rigor = rigor if isinstance(rigor, Rigor) else Rigor(rigor)
    except (TypeError, ValueError) as error:
        raise MetricValidationError("metric host or rigor is not closed") from error
    metric = LocalMetric(
        event=metric_event,
        occurred_at_day=_day(occurred_at_day, clock=clock),
        product_version=product_version,
        host=metric_host,
        locale=locale,
        rigor=metric_rigor,
        duration_bucket_ms=duration_bucket(duration_ms),
        attributes=_attributes(metric_event, attributes),
    )
    return validate_local_metric(metric)


make_local_metric = build_local_metric
local_metric = build_local_metric


class LocalMetricFactory:
    """Dependency-free factory useful at application boundaries."""

    def __init__(
        self, *, clock: Clock | None = None, product_version: str = PRODUCT_VERSION
    ) -> None:
        self.clock = clock
        self.product_version = product_version

    def build(self, event: MetricEventName | str, **kwargs: object) -> LocalMetric | None:
        kwargs.setdefault("clock", self.clock)
        kwargs.setdefault("product_version", self.product_version)
        return build_local_metric(event, **kwargs)  # type: ignore[arg-type]


__all__ = [
    "ATTRIBUTE_ALLOWLIST",
    "DURATION_BUCKETS",
    "LocalMetricFactory",
    "METRIC_ATTRIBUTES",
    "METRIC_ATTRIBUTE_ALLOWLIST",
    "MetricValidationError",
    "TASK_SCOPED_METRICS",
    "bucket_duration",
    "bucket_duration_ms",
    "build_local_metric",
    "duration_bucket",
    "local_metric",
    "make_local_metric",
    "validate_local_metric",
]
