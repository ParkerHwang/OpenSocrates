"""Injectable UTC clocks used by deterministic domain code and ID generators."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Protocol

UTC = timezone.utc


class Clock(Protocol):
    """Minimal wall-clock port; domain code never reads global time directly."""

    def unix_time_ns(self) -> int:
        """Return UTC Unix time in nanoseconds."""

    def now_utc(self) -> datetime:
        """Return an aware UTC datetime."""


class SystemClock:
    """Production wall clock backed by the standard library."""

    def unix_time_ns(self) -> int:
        return time.time_ns()

    def now_utc(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """Deterministic clock for development and focused contract checks."""

    def __init__(self, value: datetime | int) -> None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("FrozenClock requires an aware datetime")
            self._unix_time_ns = int(value.astimezone(UTC).timestamp() * 1_000_000_000)
        else:
            self._unix_time_ns = int(value)

    def unix_time_ns(self) -> int:
        return self._unix_time_ns

    def now_utc(self) -> datetime:
        return datetime.fromtimestamp(self._unix_time_ns / 1_000_000_000, UTC)

    def advance(self, delta: timedelta) -> None:
        self._unix_time_ns += int(delta.total_seconds() * 1_000_000_000)

    def advance_ms(self, milliseconds: int) -> None:
        self._unix_time_ns += milliseconds * 1_000_000


def utc_timestamp(clock: Clock | None = None) -> str:
    """Format a clock value as RFC 3339 UTC with exactly millisecond precision."""

    current = (clock or SystemClock()).now_utc().astimezone(UTC)
    milliseconds = current.microsecond // 1000
    return current.strftime("%Y-%m-%dT%H:%M:%S") + f".{milliseconds:03d}Z"


def utc_date(clock: Clock | None = None) -> str:
    """Format a clock value as an ISO UTC calendar date."""

    return (clock or SystemClock()).now_utc().astimezone(UTC).strftime("%Y-%m-%d")
