"""Process-supervised adapter for the approved Codex selector prototype.

The third-party SDK is imported only inside the isolated worker.  This module
therefore remains importable on legacy paths where ``openai-codex`` is absent.
Every failure is represented by ``None`` and no diagnostic contains selector
input or output.
"""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from multiprocessing.connection import Connection, wait
from multiprocessing.process import BaseProcess

from ..domain.models import SelectionCatalog
from .context import SelectorContextHandles
from .models import MAX_SELECTOR_DEADLINE_SECONDS, SelectorRequest
from .policy import MediumReasoningEffortPolicy, ReasoningEffortPolicy
from .sdk_worker import SelectorWorkerRequest, run_selector_worker

_EXPECTED_CANDIDATE_FIELDS = frozenset({"intervene", "selected_reasoning_systems", "instructions"})
_MAX_SELECTION_CATALOG_BYTES = 512 * 1024
_MAX_REAP_RESERVE_SECONDS = 0.25
_MAX_GRACEFUL_CLOSE_SECONDS = 3.0


@dataclass(slots=True, eq=False)
class _WorkerRecord:
    process: BaseProcess
    group_ready_connection: Connection
    cancel_connection: Connection
    cancel_sender: Connection
    group_ready: bool = False
    cancel_requested: bool = False
    ready_lock: threading.Lock = field(default_factory=threading.Lock)
    cancel_lock: threading.Lock = field(default_factory=threading.Lock)


def _serialized_catalog(catalog: SelectionCatalog) -> str:
    if not isinstance(catalog, SelectionCatalog):
        raise TypeError("catalog must be a SelectionCatalog")
    encoded = json.dumps(
        catalog.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(encoded.encode("utf-8")) > _MAX_SELECTION_CATALOG_BYTES:
        raise ValueError("selection catalog exceeds the transient SDK bound")
    return encoded


def _context_matches_request(request: SelectorRequest, context: SelectorContextHandles) -> bool:
    if context.cwd != request.cwd or context.tool_data_handle is not request.tool_data_handle:
        return False
    if context.transcript_access_enabled:
        return (
            context.transcript_path == request.transcript_path
            and context.transcript_referenced_file_paths == request.transcript_referenced_file_paths
        )
    return context.transcript_path is None and not context.transcript_referenced_file_paths


def _worker_request(
    request: SelectorRequest,
    context: SelectorContextHandles,
    *,
    selection_catalog: str,
    reasoning_effort: str,
) -> SelectorWorkerRequest:
    transcript_path = None
    referenced_paths: tuple[str, ...] = ()
    if context.transcript_access_enabled:
        if context.transcript_path is not None:
            transcript_path = str(context.transcript_path)
        referenced_paths = tuple(str(path) for path in context.transcript_referenced_file_paths)
    return SelectorWorkerRequest(
        current_prompt=request.prompt,
        selection_catalog=selection_catalog,
        reasoning_effort=reasoning_effort,
        transcript_access_enabled=context.transcript_access_enabled,
        transcript_path=transcript_path,
        workspace_path=str(context.cwd) if context.cwd is not None else None,
        transcript_referenced_file_paths=referenced_paths,
    )


def _refresh_group_ready(record: _WorkerRecord) -> bool:
    with record.ready_lock:
        if record.group_ready:
            return True
        try:
            if record.group_ready_connection.poll():
                record.group_ready = record.group_ready_connection.recv() is True
        except (EOFError, OSError, TypeError, ValueError):
            return False
        return record.group_ready


def _signal_worker(record: _WorkerRecord, requested_signal: signal.Signals) -> None:
    process = record.process
    try:
        pid = process.pid
        if os.name == "posix" and pid is not None and _refresh_group_ready(record):
            os.killpg(pid, requested_signal)
        elif process.is_alive() and requested_signal == signal.SIGTERM:
            process.terminate()
        elif process.is_alive():
            process.kill()
    except (OSError, ProcessLookupError, ValueError, AssertionError):
        return


def _request_worker_cancellation(record: _WorkerRecord) -> None:
    with record.cancel_lock:
        if not record.cancel_requested:
            try:
                record.cancel_sender.send(True)
            except (BrokenPipeError, EOFError, OSError, TypeError, ValueError):
                pass
            record.cancel_requested = True
    _signal_worker(record, signal.SIGTERM)


def _join_until(process: BaseProcess, deadline: float) -> None:
    try:
        process.join(timeout=max(0.0, deadline - time.monotonic()))
    except (AssertionError, ValueError):
        return


def _close_process_handle(process: BaseProcess) -> None:
    try:
        if not process.is_alive():
            process.close()
    except (AssertionError, ValueError):
        return


def _receive_candidate(connection: Connection) -> Mapping[str, object] | None:
    try:
        value = connection.recv()
    except (EOFError, OSError, TypeError, ValueError):
        return None
    if not isinstance(value, Mapping) or set(value) != _EXPECTED_CANDIDATE_FIELDS:
        return None
    return dict(value)


def _cancel_and_reap(record: _WorkerRecord, *, kill_at: float, hard_deadline: float) -> None:
    process = record.process
    _signal_worker(record, signal.SIGTERM)
    remaining = max(0.0, kill_at - time.monotonic())
    wait((process.sentinel,), timeout=remaining)
    if process.is_alive():
        _signal_worker(record, signal.SIGKILL)
    _join_until(process, hard_deadline)


def _supervise_worker(
    record: _WorkerRecord,
    connection: Connection,
    *,
    cancel_at: float,
    kill_at: float,
    hard_deadline: float,
) -> Mapping[str, object] | None:
    process = record.process
    try:
        remaining = max(0.0, cancel_at - time.monotonic())
        ready = wait(
            (connection, record.cancel_connection, process.sentinel),
            timeout=remaining,
        )
        if record.cancel_connection in ready:
            close_started = time.monotonic()
            close_deadline = min(
                hard_deadline,
                close_started + _MAX_GRACEFUL_CLOSE_SECONDS,
            )
            close_kill_at = max(
                close_started,
                close_deadline - _MAX_REAP_RESERVE_SECONDS,
            )
            _cancel_and_reap(
                record,
                kill_at=close_kill_at,
                hard_deadline=close_deadline,
            )
            return None
        if connection in ready:
            candidate = _receive_candidate(connection)
            _join_until(process, kill_at)
            if process.is_alive():
                _signal_worker(record, signal.SIGKILL)
                _join_until(process, hard_deadline)
            return candidate
        if process.sentinel in ready:
            _signal_worker(record, signal.SIGTERM)
            _signal_worker(record, signal.SIGKILL)
            _join_until(process, kill_at)
            return None

        _cancel_and_reap(record, kill_at=kill_at, hard_deadline=hard_deadline)
        return None
    except (OSError, RuntimeError, TypeError, ValueError, AssertionError):
        _cancel_and_reap(record, kill_at=kill_at, hard_deadline=hard_deadline)
        return None


class CodexReasoningSelector:
    """A fresh-process ``ReasoningSelector`` implementation for Codex 0.144.4."""

    def __init__(
        self,
        catalog: SelectionCatalog,
        *,
        effort_policy: ReasoningEffortPolicy | None = None,
    ) -> None:
        self._selection_catalog = _serialized_catalog(catalog)
        self._effort_policy = effort_policy or MediumReasoningEffortPolicy()
        self._state_lock = threading.Lock()
        self._active_workers: set[_WorkerRecord] = set()
        self._closed = False

    def __enter__(self) -> "CodexReasoningSelector":
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def _start_worker(
        self, worker_input: SelectorWorkerRequest, *, cancel_at: float
    ) -> tuple[_WorkerRecord, Connection] | None:
        try:
            process_context = multiprocessing.get_context("spawn")
            parent_connection, child_connection = process_context.Pipe(duplex=False)
            ready_connection, ready_child_connection = process_context.Pipe(duplex=False)
            cancel_connection, cancel_sender = process_context.Pipe(duplex=False)
            process = process_context.Process(
                target=run_selector_worker,
                args=(worker_input, child_connection, ready_child_connection, cancel_at),
                name="opensocrates-selector",
                daemon=False,
            )
            record = _WorkerRecord(
                process=process,
                group_ready_connection=ready_connection,
                cancel_connection=cancel_connection,
                cancel_sender=cancel_sender,
            )
        except (OSError, RuntimeError, TypeError, ValueError):
            return None

        with self._state_lock:
            if self._closed:
                parent_connection.close()
                child_connection.close()
                ready_connection.close()
                ready_child_connection.close()
                cancel_connection.close()
                cancel_sender.close()
                return None
            try:
                process.start()
            except (OSError, RuntimeError, TypeError, ValueError):
                parent_connection.close()
                child_connection.close()
                ready_connection.close()
                ready_child_connection.close()
                cancel_connection.close()
                cancel_sender.close()
                return None
            self._active_workers.add(record)
        child_connection.close()
        ready_child_connection.close()
        return record, parent_connection

    def select(
        self,
        request: SelectorRequest,
        context: SelectorContextHandles,
        *,
        deadline_seconds: int,
        reasoning_effort: str,
    ) -> Mapping[str, object] | None:
        """Return one untrusted exact-shape SDK candidate, or fail open."""

        if not isinstance(request, SelectorRequest) or not isinstance(
            context, SelectorContextHandles
        ):
            return None
        if (
            type(deadline_seconds) is not int
            or not 1 <= deadline_seconds <= MAX_SELECTOR_DEADLINE_SECONDS
        ):
            return None
        try:
            approved_effort = self._effort_policy.effort_for(request)
        except Exception:
            return None
        if approved_effort != "medium" or reasoning_effort != approved_effort:
            return None
        if not _context_matches_request(request, context):
            return None

        worker_input = _worker_request(
            request,
            context,
            selection_catalog=self._selection_catalog,
            reasoning_effort=approved_effort,
        )
        operation_started = time.monotonic()
        hard_deadline = operation_started + deadline_seconds
        graceful_close = min(
            _MAX_GRACEFUL_CLOSE_SECONDS,
            max(0.25, deadline_seconds * 0.2),
        )
        reap_reserve = min(_MAX_REAP_RESERVE_SECONDS, deadline_seconds * 0.1)
        cancel_at = hard_deadline - graceful_close
        kill_at = hard_deadline - reap_reserve

        started = self._start_worker(worker_input, cancel_at=cancel_at)
        if started is None:
            return None
        record, parent_connection = started
        process = record.process

        try:
            return _supervise_worker(
                record,
                parent_connection,
                cancel_at=cancel_at,
                kill_at=kill_at,
                hard_deadline=hard_deadline,
            )
        finally:
            try:
                parent_connection.close()
            except OSError:
                pass
            with self._state_lock:
                self._active_workers.discard(record)
            try:
                record.group_ready_connection.close()
            except OSError:
                pass
            try:
                record.cancel_connection.close()
                record.cancel_sender.close()
            except OSError:
                pass
            _close_process_handle(process)

    def cancel(self) -> None:
        """Request cancellation of every currently active selector process."""

        with self._state_lock:
            active = tuple(self._active_workers)
        for record in active:
            _request_worker_cancellation(record)

    def close(self) -> None:
        """Prevent new selections and request close on active workers."""

        with self._state_lock:
            self._closed = True
            active = tuple(self._active_workers)
        for record in active:
            _request_worker_cancellation(record)

    def __repr__(self) -> str:
        return "CodexReasoningSelector(<isolated>)"


__all__ = ["CodexReasoningSelector"]
