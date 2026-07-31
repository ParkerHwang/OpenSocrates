"""Plan and apply safe, restartable record retention pruning.

The application layer deals only in validated record metadata and opaque
record references.  A concrete secure store owns path resolution, locks,
symlink checks, and deletion of a record's related files; no filesystem path
is accepted or constructed here.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from typing import Protocol


class PruneValidationError(ValueError):
    """Raised when record metadata or a retention policy is unsafe."""


class PruneApplyError(RuntimeError):
    """Raised by a store when a planned deletion cannot be completed."""


class PruneOutcome(StrEnum):
    BELOW_WATERMARK = "below_watermark"
    NO_ELIGIBLE = "no_eligible"
    COMPLETED = "completed"
    PARTIAL = "partial"
    INTERRUPTED = "interrupted"


_PUBLIC_SHORT_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
_OPAQUE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_MIN_BYTES = 10 * 1024 * 1024
_MAX_BYTES = 10 * 1024 * 1024 * 1024


def _validate_short_id(value: object) -> str:
    if not isinstance(value, str) or _PUBLIC_SHORT_ID_RE.fullmatch(value) is None:
        raise PruneValidationError(
            "public_short_id must be exactly eight uppercase Crockford characters"
        )
    return value


def _validate_ref(value: object) -> str:
    # A store may interpret this as a database key, filename token, or another
    # opaque handle.  Reject path syntax at this boundary so a mistaken caller
    # cannot smuggle traversal into a secure implementation.
    if not isinstance(value, str) or _OPAQUE_REF_RE.fullmatch(value) is None:
        raise PruneValidationError("record_ref must be an opaque safe identifier")
    if ".." in value or "/" in value or "\\" in value or "\x00" in value:
        raise PruneValidationError("record_ref may not contain path syntax")
    return value


def _utc_day(value: date | datetime | str | None, *, field: str) -> date:
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise PruneValidationError(f"{field} must be timezone-aware")
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise PruneValidationError(f"{field} must be an ISO date") from error
    raise PruneValidationError(f"{field} must be a date, datetime, or ISO date")


def _timestamp(value: datetime | None) -> str:
    current = datetime.now(timezone.utc) if value is None else value
    if current.tzinfo is None:
        raise PruneValidationError("receipt timestamp must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class RecordCandidate:
    """Validated metadata supplied by a secure record index.

    ``record_ref`` is deliberately opaque.  The flags are repeated at plan
    time and checked again at apply time so a record that becomes active,
    corrupt, quarantined, or migration-pending is protected automatically.
    """

    public_short_id: str
    record_ref: str
    size_bytes: int
    terminal_at: date | datetime | str | None
    terminal: bool = True
    validated: bool = True
    active: bool = False
    quarantined: bool = False
    corrupt: bool = False
    migration_pending: bool = False

    def __post_init__(self) -> None:
        _validate_short_id(self.public_short_id)
        _validate_ref(self.record_ref)
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise PruneValidationError("size_bytes must be a non-negative integer")
        if not isinstance(self.terminal, bool):
            raise PruneValidationError("terminal must be boolean")
        if not isinstance(self.validated, bool):
            raise PruneValidationError("validated must be boolean")
        if not isinstance(self.active, bool):
            raise PruneValidationError("active must be boolean")
        if not isinstance(self.quarantined, bool):
            raise PruneValidationError("quarantined must be boolean")
        if not isinstance(self.corrupt, bool):
            raise PruneValidationError("corrupt must be boolean")
        if not isinstance(self.migration_pending, bool):
            raise PruneValidationError("migration_pending must be boolean")
        if self.terminal_at is not None:
            _utc_day(self.terminal_at, field="terminal_at")

    @property
    def terminal_day(self) -> date | None:
        return None if self.terminal_at is None else _utc_day(self.terminal_at, field="terminal_at")

    @property
    def protected(self) -> bool:
        return (
            not self.terminal
            or not self.validated
            or self.active
            or self.quarantined
            or self.corrupt
            or self.migration_pending
        )

    @property
    def eligible(self) -> bool:
        return not self.protected and self.terminal_day is not None and self.size_bytes > 0


PrunableRecord = RecordCandidate


@dataclass(frozen=True, slots=True)
class PrunePolicy:
    """High/low watermarks and age cutoff for automatic pruning."""

    high_watermark_bytes: int = 100 * 1024 * 1024
    low_watermark_bytes: int = 80 * 1024 * 1024
    retention_days: int = 90

    def __post_init__(self) -> None:
        for name, value in (
            ("high_watermark_bytes", self.high_watermark_bytes),
            ("low_watermark_bytes", self.low_watermark_bytes),
        ):
            minimum = _MIN_BYTES if name == "high_watermark_bytes" else 0
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= _MAX_BYTES
            ):
                raise PruneValidationError(
                    f"{name} must be between {_MIN_BYTES} bytes and 10 GiB"
                    if name == "high_watermark_bytes"
                    else f"{name} must be non-negative and below the high watermark"
                )
        if self.low_watermark_bytes >= self.high_watermark_bytes:
            raise PruneValidationError("low watermark must be below high watermark")
        if (
            isinstance(self.retention_days, bool)
            or not isinstance(self.retention_days, int)
            or not 7 <= self.retention_days <= 3650
        ):
            raise PruneValidationError("retention_days must be between 7 and 3650")

    @property
    def threshold_bytes(self) -> int:
        return self.high_watermark_bytes

    @property
    def target_bytes(self) -> int:
        return self.low_watermark_bytes


DEFAULT_PRUNE_POLICY = PrunePolicy()


@dataclass(frozen=True, slots=True)
class PrunePlan:
    """Read-only result of the plan phase."""

    plan_id: str
    policy: PrunePolicy
    cutoff_day: date
    total_size_before: int
    projected_size: int
    eligible: tuple[RecordCandidate, ...]
    selected: tuple[RecordCandidate, ...]

    @property
    def bytes_to_free(self) -> int:
        return sum(item.size_bytes for item in self.selected)

    @property
    def changed(self) -> bool:
        return bool(self.selected)


@dataclass(frozen=True, slots=True)
class PruneReceipt:
    """Content-free apply receipt: count, timestamp, and outcome only."""

    count: int
    timestamp: str
    outcome: PruneOutcome

    def __post_init__(self) -> None:
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 0:
            raise PruneValidationError("prune receipt count must be non-negative")
        if not isinstance(self.timestamp, str) or not self.timestamp:
            raise PruneValidationError("prune receipt timestamp is required")
        if not isinstance(self.outcome, PruneOutcome):
            raise PruneValidationError("prune receipt outcome is closed")

    def to_public_dict(self) -> dict[str, object]:
        return {"count": self.count, "timestamp": self.timestamp, "outcome": self.outcome.value}


class SecurePruneStore(Protocol):
    """Injected secure operations; implementations own all related files."""

    def inspect_record(self, record_ref: str) -> RecordCandidate | None: ...

    def delete_record(self, record_ref: str) -> bool | None: ...


class PruneJournal(Protocol):
    """Durable journal seam used to make apply restart-safe."""

    def begin(self, plan: PrunePlan) -> None: ...

    def completed(self, plan_id: str) -> frozenset[str]: ...

    def mark_deleted(self, plan_id: str, public_short_id: str) -> None: ...

    def finish(self, plan_id: str, outcome: PruneOutcome) -> None: ...

    def abort(self, plan_id: str) -> None: ...


class InMemoryPruneJournal:
    """Small deterministic journal useful for application-boundary wiring."""

    def __init__(self) -> None:
        self._completed: dict[str, set[str]] = {}
        self._outcomes: dict[str, PruneOutcome] = {}

    def begin(self, plan: PrunePlan) -> None:
        self._completed.setdefault(plan.plan_id, set())

    def completed(self, plan_id: str) -> frozenset[str]:
        return frozenset(self._completed.get(plan_id, set()))

    def mark_deleted(self, plan_id: str, public_short_id: str) -> None:
        self._completed.setdefault(plan_id, set()).add(public_short_id)

    def finish(self, plan_id: str, outcome: PruneOutcome) -> None:
        self._outcomes[plan_id] = outcome

    def abort(self, plan_id: str) -> None:
        self._outcomes[plan_id] = PruneOutcome.INTERRUPTED


def _validate_candidates(records: Iterable[RecordCandidate]) -> tuple[RecordCandidate, ...]:
    if isinstance(records, (str, bytes, bytearray, dict)):
        raise PruneValidationError("records must be typed metadata, not raw JSON or mappings")
    try:
        materialized = tuple(records)
    except TypeError as error:
        raise PruneValidationError("records must be iterable") from error
    if any(not isinstance(record, RecordCandidate) for record in materialized):
        raise PruneValidationError("records must contain RecordCandidate values")
    ids = [record.public_short_id for record in materialized]
    refs = [record.record_ref for record in materialized]
    if len(set(ids)) != len(ids):
        raise PruneValidationError("public short IDs must be unique")
    if len(set(refs)) != len(refs):
        raise PruneValidationError("record references must be unique")
    return materialized


def _plan_id(
    policy: PrunePolicy,
    cutoff_day: date,
    total_size: int,
    selected: Sequence[RecordCandidate],
) -> str:
    # The digest is only an internal idempotency key.  It is intentionally not
    # rendered in a receipt and contains no event content.
    material = "|".join(
        (
            str(policy.high_watermark_bytes),
            str(policy.low_watermark_bytes),
            str(policy.retention_days),
            cutoff_day.isoformat(),
            str(total_size),
            *(
                f"{item.public_short_id}:{item.record_ref}:{item.size_bytes}:{item.terminal_day}"
                for item in selected
            ),
        )
    )
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def plan_prune(
    records: Iterable[RecordCandidate],
    *,
    policy: PrunePolicy = DEFAULT_PRUNE_POLICY,
    now: date | datetime | str | None = None,
    total_size_bytes: int | None = None,
) -> PrunePlan:
    """Build a read-only oldest-first plan.

    A record is eligible only when terminal, validated, older than the age
    cutoff, and free of active/quarantine/corrupt/migration-pending flags.
    Planning never calls a store or mutates a journal.
    """

    if not isinstance(policy, PrunePolicy):
        raise PruneValidationError("policy must be PrunePolicy")
    candidates = _validate_candidates(records)
    if total_size_bytes is None:
        total = sum(item.size_bytes for item in candidates)
    elif (
        isinstance(total_size_bytes, bool)
        or not isinstance(total_size_bytes, int)
        or total_size_bytes < 0
    ):
        raise PruneValidationError("total_size_bytes must be a non-negative integer")
    else:
        total = total_size_bytes
    today = _utc_day(now, field="now")
    cutoff = today - timedelta(days=policy.retention_days)
    eligible = tuple(
        sorted(
            (
                item
                for item in candidates
                if item.eligible and item.terminal_day is not None and item.terminal_day < cutoff
            ),
            key=lambda item: (item.terminal_day, item.public_short_id),
        )
    )
    selected: list[RecordCandidate] = []
    projected = total
    if total > policy.high_watermark_bytes:
        for item in eligible:
            selected.append(item)
            projected -= item.size_bytes
            if projected <= policy.low_watermark_bytes:
                break
    else:
        projected = total
    return PrunePlan(
        plan_id=_plan_id(policy, cutoff, total, selected),
        policy=policy,
        cutoff_day=cutoff,
        total_size_before=total,
        projected_size=max(projected, 0),
        eligible=eligible,
        selected=tuple(selected),
    )


def _same_plan_candidate(
    current: RecordCandidate, planned: RecordCandidate, plan: PrunePlan
) -> bool:
    return (
        current.public_short_id == planned.public_short_id
        and current.record_ref == planned.record_ref
        and current.size_bytes == planned.size_bytes
        and current.eligible
        and current.terminal_day is not None
        and current.terminal_day < plan.cutoff_day
    )


def _delete(store: SecurePruneStore, record_ref: str) -> bool:
    operation = getattr(store, "delete_record", None)
    if not callable(operation):
        raise PruneApplyError("secure prune store has no delete_record operation")
    result = operation(record_ref)
    return result is not False


def apply_prune(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    plan: PrunePlan,
    *,
    store: SecurePruneStore,
    journal: PruneJournal,
    now: datetime | None = None,
) -> PruneReceipt:
    """Apply a plan through secure operations and a durable journal."""

    if not isinstance(plan, PrunePlan):
        raise PruneValidationError("apply requires a PrunePlan")
    if not callable(getattr(store, "inspect_record", None)):
        raise PruneApplyError("secure prune store has no inspect_record operation")
    for item in plan.selected:
        if not _same_plan_candidate(item, item, plan):
            raise PruneValidationError("plan contains an ineligible record")
    timestamp = _timestamp(now)
    if not plan.selected:
        outcome = (
            PruneOutcome.BELOW_WATERMARK
            if plan.total_size_before <= plan.policy.high_watermark_bytes
            else PruneOutcome.NO_ELIGIBLE
        )
        return PruneReceipt(0, timestamp, outcome)

    journal.begin(plan)
    done = set(journal.completed(plan.plan_id))
    count = 0
    protected = False
    try:
        for planned in plan.selected:
            if planned.public_short_id in done:
                continue
            current = store.inspect_record(planned.record_ref)
            if current is None:
                protected = True
                continue
            if not isinstance(current, RecordCandidate) or not _same_plan_candidate(
                current, planned, plan
            ):
                protected = True
                continue
            if not _delete(store, planned.record_ref):
                protected = True
                continue
            journal.mark_deleted(plan.plan_id, planned.public_short_id)
            done.add(planned.public_short_id)
            count += 1
        outcome = (
            PruneOutcome.PARTIAL
            if protected or len(done) < len(plan.selected)
            else PruneOutcome.COMPLETED
        )
        journal.finish(plan.plan_id, outcome)
        return PruneReceipt(count, timestamp, outcome)
    except (Exception, KeyboardInterrupt):
        journal.abort(plan.plan_id)
        return PruneReceipt(count, timestamp, PruneOutcome.INTERRUPTED)


build_prune_plan = plan_prune
apply_prune_plan = apply_prune


__all__ = [
    "DEFAULT_PRUNE_POLICY",
    "InMemoryPruneJournal",
    "PrunableRecord",
    "PruneApplyError",
    "PruneJournal",
    "PruneOutcome",
    "PrunePlan",
    "PrunePolicy",
    "PruneReceipt",
    "PruneValidationError",
    "RecordCandidate",
    "SecurePruneStore",
    "apply_prune",
    "apply_prune_plan",
    "build_prune_plan",
    "plan_prune",
]
