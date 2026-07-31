"""Append-only, typed judgment event storage with integrity recovery."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from opensocrates.clock import Clock, SystemClock, utc_timestamp
from opensocrates.constants import MAX_RECORD_EVENT_BYTES
from opensocrates.domain.enums import RecordEventType
from opensocrates.domain.models import JudgmentEvent
from opensocrates.domain.record_event import (
    RecordEvent,
    RecordEventError,
    RecoveredFromTornTailPayload,
)
from opensocrates.errors import OpenSocratesError
from opensocrates.ids import new_event_id, validate_task_id
from opensocrates.verification.secret_filter import reject_forbidden_keys, reject_secrets

from .atomic import (
    AtomicWriteError,
    append_fsync,
    canonical_json_bytes,
    read_bytes,
)
from .locks import FileLock, LockPolicy, LockTimeoutError
from .paths import DataRoot, DataRootLayout, PathSecurityError, current_month
from .permissions import PermissionManager, PermissionSecurityError
from .quarantine import (
    QuarantineError,
    QuarantineReason,
    quarantine_record,
    recover_prefix,
)


class RecordStoreError(OSError):
    """Base class for bounded persistence failures."""


class RecordCorruptionError(RecordStoreError):
    """Raised after a complete-line corruption is quarantined."""


class RecordSequenceError(RecordStoreError):
    """Raised when an event would create a sequence gap or duplicate."""


class RecordUnavailableError(RecordStoreError):
    """Raised when owner-only write readiness is not available."""


@dataclass(frozen=True, slots=True)
class AppendReceipt:
    path: Path
    event: RecordEvent
    recovery_event: RecordEvent | None = None


@dataclass(frozen=True, slots=True)
class _Inspection:
    events: tuple[RecordEvent, ...]
    complete_prefix: bytes
    torn_tail: bytes

    @property
    def is_torn(self) -> bool:
        return bool(self.torn_tail)


def _coerce_event(event: RecordEvent | JudgmentEvent) -> RecordEvent:
    """Close the S01 generic envelope before it reaches the byte boundary."""

    if isinstance(event, RecordEvent):
        return event
    if isinstance(event, JudgmentEvent):
        try:
            return RecordEvent.from_judgment_event(event)
        except RecordEventError as error:
            raise RecordStoreError("judgment event payload is not a closed public event") from error
    raise TypeError("record store accepts RecordEvent or JudgmentEvent only")


def _read_existing(path: Path) -> bytes:
    try:
        return read_bytes(path, max_bytes=100 * 1024 * 1024)
    except FileNotFoundError:
        return b""
    except AtomicWriteError as error:
        raise RecordStoreError("record file could not be read") from error


def _event_bytes(event: RecordEvent) -> bytes:
    """Validate the event's positive allowlist at the persistence boundary."""

    value = event.to_json_value()
    reject_forbidden_keys(value)
    reject_secrets(value)
    try:
        return canonical_json_bytes(value, max_bytes=MAX_RECORD_EVENT_BYTES)
    except (TypeError, ValueError) as error:
        raise RecordStoreError("record event is not canonical JSON") from error


def _validate_lines(data: bytes, *, expected_task_id: str) -> _Inspection:
    if not data:
        return _Inspection((), b"", b"")
    if data.endswith(b"\n"):
        complete_prefix = data
        torn_tail = b""
    else:
        boundary = data.rfind(b"\n")
        complete_prefix = data[: boundary + 1] if boundary >= 0 else b""
        torn_tail = data[boundary + 1 :] if boundary >= 0 else data
    events: list[RecordEvent] = []
    seen_ids: set[str] = set()
    for line in complete_prefix.splitlines(keepends=True):
        if not line.endswith(b"\n") or line in {b"\n", b"\r\n"}:
            raise RecordCorruptionError("record contains a malformed complete line")
        try:
            event = RecordEvent.from_json_bytes(line)
        except RecordEventError as error:
            raise RecordCorruptionError("record contains malformed JSON or schema") from error
        if _event_bytes(event) != line:
            raise RecordCorruptionError("record line is not canonical JSON")
        if event.task_id != expected_task_id:
            raise RecordCorruptionError("record contains a foreign task id")
        if event.event_id in seen_ids:
            raise RecordCorruptionError("record contains a duplicate event id")
        seen_ids.add(event.event_id)
        expected_sequence = len(events) + 1
        if event.sequence != expected_sequence:
            raise RecordCorruptionError("record sequence is not contiguous")
        events.append(event)
    return _Inspection(tuple(events), complete_prefix, torn_tail)


def _copy_with_sequence(event: RecordEvent, sequence: int) -> RecordEvent:
    return RecordEvent(
        event_id=new_event_id(),
        task_id=event.task_id,
        sequence=sequence,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        host=event.host,
        host_version=event.host_version,
        adapter_version=event.adapter_version,
        locale=event.locale,
        payload=event.payload,
        schema=event.schema,
    )


class JsonlRecordStore:
    """One authoritative append-only JSONL file per task."""

    def __init__(
        self,
        data_root: DataRoot | DataRootLayout,
        *,
        clock: Clock | None = None,
        lock_policy: LockPolicy | None = None,
        permission_manager: PermissionManager | None = None,
    ) -> None:
        self.layout = data_root.layout if isinstance(data_root, DataRoot) else data_root
        self.clock = clock or SystemClock()
        self.lock_policy = lock_policy or LockPolicy()
        self.permissions = permission_manager or PermissionManager()

    def _path(self, task_id: str, month: str) -> Path:
        try:
            validate_task_id(task_id)
        except (OpenSocratesError, ValueError) as error:
            raise RecordStoreError("invalid task id") from error
        try:
            return self.layout.task_record(task_id, month)
        except (OpenSocratesError, ValueError) as error:
            raise RecordStoreError("invalid record partition") from error

    def _lock_path(self, task_id: str, month: str) -> Path:
        try:
            return self.layout.task_lock(task_id, month)
        except (OpenSocratesError, ValueError) as error:
            raise RecordStoreError("invalid record lock partition") from error

    def _ensure_month_dir(self, month: str) -> Path:
        month_dir = self.layout.month_dir(month)
        root_report = self.permissions.root_report(self.layout.root)
        records_report = self.permissions.root_report(self.layout.records_dir)
        if not root_report.write_allowed or not records_report.write_allowed:
            raise RecordUnavailableError("record writes disabled by data-root permissions")
        try:
            existed = month_dir.exists()
            month_dir.mkdir(mode=0o700, exist_ok=True)
            if month_dir.is_symlink():
                raise RecordUnavailableError("record partition may not be a symlink")
            if not existed and os.name != "nt":
                os.chmod(month_dir, 0o700)
        except (OSError, PermissionError) as error:
            raise RecordUnavailableError("record partition is unavailable") from error
        report = self.permissions.root_report(month_dir)
        if not report.write_allowed:
            raise RecordUnavailableError("record writes disabled by partition permissions")
        return month_dir

    def _has_blocking_quarantine(self, task_id: str) -> bool:
        try:
            entries = self.layout.quarantine_dir.iterdir()
        except OSError:
            return False
        prefix = f"{task_id}."
        return any(
            entry.name.startswith(prefix)
            and f".{QuarantineReason.TORN_TAIL.value}." not in entry.name
            for entry in entries
        )

    def _recovery_event(
        self, last: RecordEvent, complete_count: int, original_name: str
    ) -> RecordEvent:
        return RecordEvent.new(
            task_id=last.task_id,
            sequence=last.sequence + 1,
            event_type=RecordEventType.RECOVERED_FROM_TORN_TAIL,
            payload=RecoveredFromTornTailPayload(
                source_record_safe_identifier=original_name,
                complete_line_count=complete_count,
            ),
            occurred_at=utc_timestamp(self.clock),
            host=last.host,
            host_version=last.host_version,
            adapter_version=last.adapter_version,
            locale=last.locale,
        )

    def _append_line(self, path: Path, event: RecordEvent) -> None:
        try:
            append_fsync(path, _event_bytes(event), max_bytes=MAX_RECORD_EVENT_BYTES)
        except (AtomicWriteError, PermissionSecurityError) as error:
            raise RecordUnavailableError("record append failed") from error

    def append(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self, event: RecordEvent | JudgmentEvent, *, month: str | None = None
    ) -> AppendReceipt:
        """Append one typed event, recovering a torn final tail if possible."""

        event = _coerce_event(event)
        partition = month or event.occurred_at[:7]
        self._ensure_month_dir(partition)
        path = self._path(event.task_id, partition)
        if self._has_blocking_quarantine(event.task_id) and not path.exists():
            raise RecordCorruptionError("task id is quarantined; a new task id is required")
        lock_path = self._lock_path(event.task_id, partition)
        try:
            with FileLock(lock_path, policy=self.lock_policy):
                data = _read_existing(path)
                if not data:
                    if event.sequence != 1:
                        raise RecordSequenceError("first event sequence must be one")
                    self._append_line(path, event)
                    return AppendReceipt(path=path, event=event)
                try:
                    inspection = _validate_lines(data, expected_task_id=event.task_id)
                except RecordCorruptionError as error:
                    try:
                        quarantine_record(
                            path,
                            self.layout.quarantine_dir,
                            reason=QuarantineReason.MID_FILE_CORRUPTION,
                        )
                    except QuarantineError as quarantine_error:
                        raise RecordStoreError(
                            "record corruption could not be quarantined"
                        ) from quarantine_error
                    raise error

                recovery_event: RecordEvent | None = None
                persisted_event = event
                if inspection.is_torn:
                    if not inspection.events:
                        try:
                            quarantine_record(
                                path,
                                self.layout.quarantine_dir,
                                reason=QuarantineReason.TORN_TAIL,
                            )
                        except QuarantineError as quarantine_error:
                            raise RecordStoreError(
                                "torn record could not be quarantined"
                            ) from quarantine_error
                        raise RecordCorruptionError("record has no recoverable complete prefix")
                    try:
                        recover_prefix(
                            path,
                            inspection.complete_prefix,
                            self.layout.quarantine_dir,
                            complete_line_count=len(inspection.events),
                        )
                    except QuarantineError as error:
                        raise RecordStoreError("torn record could not be recovered") from error
                    recovery_event = self._recovery_event(
                        inspection.events[-1],
                        len(inspection.events),
                        path.name,
                    )
                    self._append_line(path, recovery_event)
                    expected = recovery_event.sequence + 1
                    if event.sequence == recovery_event.sequence:
                        persisted_event = _copy_with_sequence(event, expected)
                    elif event.sequence != expected:
                        raise RecordSequenceError(
                            "event sequence does not follow torn-tail recovery"
                        )
                else:
                    expected = inspection.events[-1].sequence + 1
                    if event.sequence != expected:
                        raise RecordSequenceError("event sequence is not contiguous")
                self._append_line(path, persisted_event)
                return AppendReceipt(
                    path=path, event=persisted_event, recovery_event=recovery_event
                )
        except LockTimeoutError as error:
            raise RecordUnavailableError("record lock timeout") from error

    def read_events(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self,
        task_id: str,
        *,
        month: str | None = None,
        recover_torn_tail: bool = True,
    ) -> tuple[RecordEvent, ...]:
        """Read and validate a task log; torn tails recover under the lock."""

        partition = month or current_month(now=self.clock.now_utc())
        # Reading must remain useful when a caller discovers that a mutable
        # root has become non-writable.  The write path performs the stricter
        # owner-only readiness check; reads only require an existing real
        # partition and still reject symlink hops through the typed layout.
        try:
            month_dir = self.layout.month_dir(partition)
            info = month_dir.lstat()
        except FileNotFoundError:
            return ()
        except PathSecurityError as error:
            raise RecordUnavailableError("record partition path is unsafe") from error
        except OSError as error:
            raise RecordUnavailableError("record partition cannot be inspected") from error
        if not month_dir.is_dir() or stat.S_ISLNK(info.st_mode):
            raise RecordUnavailableError("record partition is not a real directory")
        path = self._path(task_id, partition)
        if not path.exists():
            if self._has_blocking_quarantine(task_id):
                raise RecordCorruptionError("task id is quarantined; record replay is unavailable")
            return ()
        lock_path = self._lock_path(task_id, partition)
        try:
            with FileLock(lock_path, policy=self.lock_policy):
                data = _read_existing(path)
                if not data:
                    return ()
                try:
                    inspection = _validate_lines(data, expected_task_id=task_id)
                except RecordCorruptionError as error:
                    try:
                        quarantine_record(
                            path,
                            self.layout.quarantine_dir,
                            reason=QuarantineReason.MID_FILE_CORRUPTION,
                        )
                    except QuarantineError as quarantine_error:
                        raise RecordStoreError(
                            "record corruption could not be quarantined"
                        ) from quarantine_error
                    raise error
                if not inspection.is_torn:
                    return inspection.events
                if not recover_torn_tail or not inspection.events:
                    try:
                        quarantine_record(
                            path, self.layout.quarantine_dir, reason=QuarantineReason.TORN_TAIL
                        )
                    except QuarantineError as quarantine_error:
                        raise RecordStoreError(
                            "torn record could not be quarantined"
                        ) from quarantine_error
                    raise RecordCorruptionError("torn final record tail is unavailable")
                try:
                    recover_prefix(
                        path,
                        inspection.complete_prefix,
                        self.layout.quarantine_dir,
                        complete_line_count=len(inspection.events),
                    )
                except QuarantineError as error:
                    raise RecordStoreError("torn record could not be recovered") from error
                recovery = self._recovery_event(
                    inspection.events[-1], len(inspection.events), path.name
                )
                self._append_line(path, recovery)
                return (*inspection.events, recovery)
        except LockTimeoutError as error:
            raise RecordUnavailableError("record lock timeout") from error


__all__ = [
    "AppendReceipt",
    "RecordStoreError",
    "RecordCorruptionError",
    "RecordSequenceError",
    "RecordUnavailableError",
    "JsonlRecordStore",
]
