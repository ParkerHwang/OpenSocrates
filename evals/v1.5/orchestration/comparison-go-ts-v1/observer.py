"""Privacy-safe external call timing, identical for single and coordinator arms."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opensocrates.orchestration.adapter import MAX_OUTPUT, CodexAdapter, null_usage, reported_usage
from opensocrates.orchestration.paths import BoundaryError, digest, relative


OBSERVER_REVISION = 2


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


class ObservedAdapter(CodexAdapter):
    def __init__(self, client_path: str, observation_path: Path) -> None:
        super().__init__(client_path)
        self.observation_path = observation_path
        self.observation_failures: list[dict[str, str]] = []
        self.role_event_summaries: list[dict[str, Any]] = []
        self.candidate_diagnostics: list[dict[str, Any]] = []

    def _candidate_diagnostic(self, assignment: dict[str, Any], value: dict[str, Any]) -> None:
        if assignment["role"] not in {"design", "production"} or not isinstance(value.get("files"), list):
            return
        owned = set(assignment["owned_paths"])
        for name in owned:
            relative(name)  # Never write a model-controlled traversal path.
        returned = value["files"]
        counts: dict[str, int] = {}
        for item in returned:
            name = item.get("path") if isinstance(item, dict) else None
            if isinstance(name, str) and name in owned:
                counts[name] = counts.get(name, 0) + 1
        metadata: dict[str, Any] = {
            "schema": "opensocrates.go-ts.candidate-diagnostic/2",
            "assignment_id": assignment["assignment_id"],
            "unit_id": assignment["unit_id"], "role": assignment["role"],
            "blocked_reason": value.get("blocked_reason"),
            "owned_path_count": len(owned), "returned_path_count": len(returned),
            "returned_owned_path_count": sum(counts.values()),
            "unowned_path_count": len(returned) - sum(counts.values()),
            "duplicate_owned_path_count": sum(count - 1 for count in counts.values() if count > 1),
            "owned_path_set_matches": set(counts) == owned and len(returned) == len(owned)
                                     and all(count == 1 for count in counts.values()),
            "owned_file_hashes": {}, "quarantined_owned_paths": [],
            "rejected_owned_hashes": {},
            "invalid_owned_bytes": 0,
            "qualification": "unqualified; independent native/external checks still required",
            "raw_unowned_path_names_or_invalid_json_retained": False,
        }
        quarantine = self.observation_path.parent / "quarantine" / assignment["assignment_id"]
        quarantine.mkdir(mode=0o700, parents=True, exist_ok=False)
        byte_total = 0
        for item in returned:
            if not isinstance(item, dict):
                continue
            name, content = item.get("path"), item.get("content")
            if not isinstance(name, str) or name not in owned or counts.get(name) != 1 or not isinstance(content, str):
                continue
            data = content.encode("utf-8")
            if b"\x00" in data or len(data) > 65536 or byte_total + len(data) > MAX_OUTPUT:
                metadata["invalid_owned_bytes"] += 1
                metadata["rejected_owned_hashes"][name] = digest(data)
                continue
            byte_total += len(data)
            target = quarantine / name
            if not target.resolve().is_relative_to(quarantine.resolve()):
                metadata["invalid_owned_bytes"] += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as out:
                out.write(data)
                out.flush()
                os.fsync(out.fileno())
            metadata["owned_file_hashes"][name] = digest(data)
            metadata["quarantined_owned_paths"].append(name)
        with (quarantine / "metadata.json").open("x", encoding="utf-8") as out:
            json.dump(metadata, out, sort_keys=True, separators=(",", ":"))
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        self.candidate_diagnostics.append(metadata)

    def _append(self, item: dict[str, Any]) -> None:
        try:
            with self.observation_path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
                out.flush()
                os.fsync(out.fileno())
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
            if result.value is not None:
                try:
                    self._candidate_diagnostic(assignment, result.value)
                except (OSError, ValueError, TypeError, KeyError) as error:
                    self.observation_failures.append({
                        "kind": "candidate_diagnostic", "identity": assignment["assignment_id"],
                        "phase": type(error).__name__,
                    })
            return result
        finally:
            self._current_event_summary = None
            ended, ended_utc = time.monotonic_ns(), utc()
            receipt = result.receipt if result is not None else {}
            self._append({
                **identity, "phase": "terminal", "utc": ended_utc,
                "elapsed_ns": ended - started,
                "status": receipt.get("status", "unavailable"),
                "reason": receipt.get("reason"),
                "process_exit_code": receipt.get("process_exit_code"),
                "input_sha256": receipt.get("input_sha256"),
                "output_sha256": receipt.get("output_sha256"),
                "thread_sha256": receipt.get("thread_sha256"),
                "model": receipt.get("model", assignment.get("model")),
                "usage": receipt.get("usage") or null_usage(),
                "backend_attempts": receipt.get("backend_attempts"),
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
