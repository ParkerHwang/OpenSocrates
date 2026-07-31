"""Explicit public-record deletion controls.

Only exact public short IDs are resolved here.  An injected secure store
performs the atomic, path-safe deletion of a record, its lock, derived
references, and cache; quarantine data is passed through only when the caller
explicitly opts in.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Protocol


class DeleteValidationError(ValueError):
    """Raised when a deletion request or record index is malformed."""


class RecordNotFound(LookupError):
    """Raised when no record has the requested exact public short ID."""


class AmbiguousPublicShortId(LookupError):
    """Raised when more than one record has the requested short ID."""


class RecordProtected(PermissionError):
    """Raised when quarantine deletion was not explicitly selected."""


class DeleteConfirmationRequired(PermissionError):
    """Raised when ``--all`` is missing its explicit confirmation phrase."""

    def __init__(self, scope: "DeleteScope") -> None:
        self.scope = scope
        super().__init__("explicit confirmation is required to delete all records")


class DeleteOutcome(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    NONE = "none"
    INTERRUPTED = "interrupted"


ALL_DELETE_CONFIRMATION = "DELETE ALL RECORDS"
ALL_CONFIRMATION = ALL_DELETE_CONFIRMATION
_PUBLIC_SHORT_ID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{8}$")
_OPAQUE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")


def _validate_short_id(value: object) -> str:
    if not isinstance(value, str) or _PUBLIC_SHORT_ID_RE.fullmatch(value) is None:
        raise DeleteValidationError(
            "public short ID must be exactly eight uppercase Crockford characters"
        )
    return value


def _validate_ref(value: object) -> str:
    if not isinstance(value, str) or _OPAQUE_REF_RE.fullmatch(value) is None:
        raise DeleteValidationError("record reference must be an opaque safe identifier")
    if ".." in value or "/" in value or "\\" in value or "\x00" in value:
        raise DeleteValidationError("record reference may not contain path syntax")
    return value


def _timestamp(value: datetime | None) -> str:
    current = datetime.now(timezone.utc) if value is None else value
    if current.tzinfo is None:
        raise DeleteValidationError("receipt timestamp must be timezone-aware")
    return current.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class RecordHandle:
    """A short-ID-indexed opaque deletion handle."""

    public_short_id: str
    record_ref: str
    quarantined: bool = False

    def __post_init__(self) -> None:
        _validate_short_id(self.public_short_id)
        _validate_ref(self.record_ref)
        if not isinstance(self.quarantined, bool):
            raise DeleteValidationError("quarantined must be boolean")


@dataclass(frozen=True, slots=True)
class DeleteRequest:
    """One exact-ID or explicitly confirmed all-record request."""

    public_short_id: str | None = None
    all_records: bool = False
    confirmation: str | None = None
    include_quarantine: bool = False

    def __post_init__(self) -> None:
        if self.public_short_id is not None:
            _validate_short_id(self.public_short_id)
        if not isinstance(self.all_records, bool):
            raise DeleteValidationError("all_records must be boolean")
        if not isinstance(self.include_quarantine, bool):
            raise DeleteValidationError("include_quarantine must be boolean")
        if self.all_records and self.public_short_id is not None:
            raise DeleteValidationError("an all-record request cannot include a short ID")
        if not self.all_records and self.public_short_id is None:
            raise DeleteValidationError("a deletion request needs a public short ID or all_records")
        if self.confirmation is not None and not isinstance(self.confirmation, str):
            raise DeleteValidationError("confirmation must be text")

    @property
    def short_id(self) -> str | None:
        return self.public_short_id


@dataclass(frozen=True, slots=True)
class DeleteScope:
    """The records a request would delete; IDs are not part of the receipt."""

    handles: tuple[RecordHandle, ...]

    @property
    def count(self) -> int:
        return len(self.handles)

    @property
    def public_short_ids(self) -> tuple[str, ...]:
        return tuple(handle.public_short_id for handle in self.handles)

    def to_public_dict(self) -> dict[str, object]:
        return {"count": self.count}


@dataclass(frozen=True, slots=True)
class DeleteReceipt:
    """Content-free deletion receipt with exactly three public fields."""

    count: int
    timestamp: str
    outcome: DeleteOutcome

    def __post_init__(self) -> None:
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 0:
            raise DeleteValidationError("delete receipt count must be non-negative")
        if not isinstance(self.timestamp, str) or not self.timestamp:
            raise DeleteValidationError("delete receipt timestamp is required")
        if not isinstance(self.outcome, DeleteOutcome):
            raise DeleteValidationError("delete receipt outcome is closed")

    def to_public_dict(self) -> dict[str, object]:
        return {"count": self.count, "timestamp": self.timestamp, "outcome": self.outcome.value}


@dataclass(frozen=True, slots=True)
class DeleteResult:
    scope: DeleteScope
    receipt: DeleteReceipt


class SecureDeleteStore(Protocol):
    """Injected secure deletion operations.

    ``delete_record`` must remove the record JSONL, lock, derived references,
    and cache as one safe operation.  It must remove quarantine data only when
    ``include_quarantine`` is true; it must reject path traversal and symlink
    escapes internally.
    """

    def list_records(self) -> Sequence[RecordHandle]: ...

    def delete_record(
        self, record_ref: str, *, include_quarantine: bool = False
    ) -> bool | None: ...


def _materialize(records: Iterable[RecordHandle]) -> tuple[RecordHandle, ...]:
    if isinstance(records, (str, bytes, bytearray, dict)):
        raise DeleteValidationError("records must be typed handles, not raw JSON or mappings")
    try:
        materialized = tuple(records)
    except TypeError as error:
        raise DeleteValidationError("records must be iterable") from error
    if any(not isinstance(record, RecordHandle) for record in materialized):
        raise DeleteValidationError("records must contain RecordHandle values")
    refs = [record.record_ref for record in materialized]
    if len(set(refs)) != len(refs):
        raise DeleteValidationError("record references must be unique")
    return materialized


def resolve_public_short_id(
    records: Iterable[RecordHandle],
    public_short_id: str,
) -> RecordHandle:
    """Resolve one exact eight-character ID, never a prefix or substring."""

    _validate_short_id(public_short_id)
    matches = tuple(
        record for record in _materialize(records) if record.public_short_id == public_short_id
    )
    if not matches:
        raise RecordNotFound(public_short_id)
    if len(matches) != 1:
        raise AmbiguousPublicShortId(public_short_id)
    return matches[0]


def _scope_for(request: DeleteRequest, records: tuple[RecordHandle, ...]) -> DeleteScope:
    if request.all_records:
        selected = tuple(
            record for record in records if request.include_quarantine or not record.quarantined
        )
        return DeleteScope(selected)
    assert request.public_short_id is not None
    handle = resolve_public_short_id(records, request.public_short_id)
    if handle.quarantined and not request.include_quarantine:
        raise RecordProtected(request.public_short_id)
    return DeleteScope((handle,))


def delete_records(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    request: DeleteRequest,
    *,
    store: SecureDeleteStore,
    now: datetime | None = None,
) -> DeleteResult:
    """Resolve and delete records through the injected secure store."""

    if not isinstance(request, DeleteRequest):
        raise DeleteValidationError("delete requires DeleteRequest")
    list_records = getattr(store, "list_records", None)
    if not callable(list_records):
        raise DeleteValidationError("secure delete store has no list_records operation")
    records = _materialize(list_records())
    scope = _scope_for(request, records)
    if request.all_records and request.confirmation != ALL_DELETE_CONFIRMATION:
        raise DeleteConfirmationRequired(scope)

    timestamp = _timestamp(now)
    if not scope.handles:
        receipt = DeleteReceipt(0, timestamp, DeleteOutcome.NONE)
        return DeleteResult(scope, receipt)

    operation = getattr(store, "delete_record", None)
    if not callable(operation):
        raise DeleteValidationError("secure delete store has no delete_record operation")
    count = 0
    interrupted = False
    failed = False
    for handle in scope.handles:
        try:
            result = operation(handle.record_ref, include_quarantine=request.include_quarantine)
        except (Exception, KeyboardInterrupt):
            interrupted = True
            break
        if result is False:
            failed = True
            continue
        count += 1

    if interrupted:
        outcome = DeleteOutcome.INTERRUPTED
    elif count == len(scope.handles):
        outcome = DeleteOutcome.COMPLETED
    elif count:
        outcome = DeleteOutcome.PARTIAL
    elif failed:
        outcome = DeleteOutcome.FAILED
    else:
        outcome = DeleteOutcome.NONE
    return DeleteResult(scope, DeleteReceipt(count, timestamp, outcome))


delete_record = delete_records
delete_all_records = delete_records


__all__ = [
    "ALL_CONFIRMATION",
    "ALL_DELETE_CONFIRMATION",
    "AmbiguousPublicShortId",
    "DeleteConfirmationRequired",
    "DeleteOutcome",
    "DeleteReceipt",
    "DeleteRequest",
    "DeleteResult",
    "DeleteScope",
    "DeleteValidationError",
    "RecordHandle",
    "RecordNotFound",
    "RecordProtected",
    "SecureDeleteStore",
    "delete_all_records",
    "delete_record",
    "delete_records",
    "resolve_public_short_id",
]
