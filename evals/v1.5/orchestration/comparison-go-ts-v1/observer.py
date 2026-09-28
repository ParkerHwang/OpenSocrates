"""Privacy-safe external call timing, identical for single and coordinator arms."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensocrates.orchestration.adapter import MAX_OUTPUT, CodexAdapter, reported_usage
from opensocrates.orchestration.paths import BoundaryError, digest


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class ObservedAdapter(CodexAdapter):
    def __init__(self, client_path: str, observation_path: Path) -> None:
        super().__init__(client_path)
        self.observation_path = observation_path
        self.observation_failures: list[dict[str, str]] = []
        self.role_event_summaries: list[dict[str, Any]] = []

    def _append(self, item: dict[str, Any]) -> None:
        try:
            with self.observation_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
        except OSError:
            # A completed native receipt/usage must survive observer failure.
            # The runner publishes these bounded post-call harness failures.
            self.observation_failures.append({
                "kind": item["kind"],
                "identity": item.get("assignment_id", item.get("check_id", "unknown")),
                "phase": item["phase"],
            })

    def invoke(self, assignment: dict[str, Any], cwd: Path):
        started_utc, started = utc(), time.monotonic_ns()
        identity = {"kind": "role", "assignment_id": assignment["assignment_id"],
                    "unit_id": assignment["unit_id"], "role": assignment["role"]}
        self._append({**identity, "phase": "start", "utc": started_utc})
        result = None
        current_summary = {
            "assignment_id": assignment["assignment_id"],
            "unit_id": assignment["unit_id"], "role": assignment["role"],
            "event_stream_observed": False, "event_stream_complete": False,
            "command_started": None, "command_completed": None,
            "other_tool_started": None, "other_tool_completed": None,
            "unclassified_error_items": None, "public_message_count": None,
        }
        self.role_event_summaries.append(current_summary)
        self._current_event_summary = current_summary
        try:
            result = super().invoke(assignment, cwd)
            return result
        finally:
            self._current_event_summary = None
            ended, ended_utc = time.monotonic_ns(), utc()
            receipt = result.receipt if result is not None else {}
            self._append({
                **identity, "phase": "terminal", "utc": ended_utc,
                "elapsed_ns": ended - started,
                "status": receipt.get("status", "unavailable"),
                "provider_error_events": receipt.get("provider_error_events"),
                "failed_turn_events": receipt.get("failed_turn_events"),
                "tool_action_count": None,
            })

    def _events(self, process, receipt):
        """Native event projection plus typed counts, with every body discarded."""
        summary = self._current_event_summary
        summary.update({
            "event_stream_observed": True,
            "command_started": 0, "command_completed": 0,
            "other_tool_started": 0, "other_tool_completed": 0,
            "unclassified_error_items": 0, "public_message_count": 0,
        })
        final = None
        completed = False
        non_tools = {"agent_message", "reasoning", "todo_list", "plan"}
        while line := process.stdout.readline(4 * MAX_OUTPUT + 1):
            if len(line) > 4 * MAX_OUTPUT:
                raise BoundaryError("event_size_limit")
            event = json.loads(line)
            if not isinstance(event, dict):
                raise BoundaryError("invalid_event")
            kind = event.get("type")
            if kind == "error":
                receipt["provider_error_events"] += 1
            elif kind == "turn.failed":
                receipt["failed_turn_events"] += 1
            elif kind == "thread.started" and isinstance(event.get("thread_id"), str):
                receipt["thread_sha256"] = digest(event["thread_id"].encode())
            elif kind == "turn.completed":
                completed = True
                receipt["usage"] = reported_usage(event.get("usage"))
            elif kind in {"item.started", "item.completed"}:
                item = event.get("item") or {}
                item_type = item.get("type")
                if item_type == "command_execution":
                    key = "command_started" if kind == "item.started" else "command_completed"
                    summary[key] += 1
                elif item_type == "error":
                    # This is a distinct client item, not evidence of a second
                    # executed command. Its cause stays unknown.
                    if kind == "item.completed":
                        summary["unclassified_error_items"] += 1
                elif isinstance(item_type, str) and item_type not in non_tools:
                    key = "other_tool_started" if kind == "item.started" else "other_tool_completed"
                    summary[key] += 1
                if kind == "item.completed" and item_type == "agent_message" and isinstance(item.get("text"), str):
                    if len(item["text"].encode()) > MAX_OUTPUT:
                        raise BoundaryError("candidate_size_limit")
                    final = item["text"]
                    summary["public_message_count"] += 1
        summary["event_stream_complete"] = completed
        return final, completed

    def check(self, check: dict[str, Any], cwd: Path, files: dict[str, bytes], candidate_sha256: str):
        started_utc, started = utc(), time.monotonic_ns()
        identity = {"kind": "native_check", "check_id": check["check_id"],
                    "candidate_sha256": candidate_sha256}
        self._append({**identity, "phase": "start", "utc": started_utc})
        result = None
        try:
            result = super().check(check, cwd, files, candidate_sha256)
            return result
        finally:
            ended, ended_utc = time.monotonic_ns(), utc()
            self._append({
                **identity, "phase": "terminal", "utc": ended_utc,
                "elapsed_ns": ended - started,
                "status": result["status"] if result is not None else "unavailable",
            })


def reconcile(path: Path) -> dict[str, Any]:
    """Find calls that started but lack a terminal timing record.

    The journal intentionally contains identities and aggregate timing only.
    A process crash can leave a start without a terminal; it is not a retry cue.
    """
    starts: dict[tuple[str, str], int] = {}
    terminals: dict[tuple[str, str], int] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            item = json.loads(raw)
            key = (item["kind"], item.get("assignment_id", item.get("check_id")))
            target = starts if item["phase"] == "start" else terminals
            target[key] = target.get(key, 0) + 1
    open_calls = [
        {"kind": kind, "identity": identity, "unmatched_starts": count - terminals.get((kind, identity), 0)}
        for (kind, identity), count in sorted(starts.items())
        if count > terminals.get((kind, identity), 0)
    ]
    return {
        "start_count": sum(starts.values()), "terminal_count": sum(terminals.values()),
        "start_without_terminal": open_calls,
    }
