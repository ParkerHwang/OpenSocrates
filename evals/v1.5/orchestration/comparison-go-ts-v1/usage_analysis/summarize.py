#!/usr/bin/env python3
"""Deterministic, privacy-safe usage/timing readout from frozen cohort receipts.

This script never calls a model, replays a candidate, reads hidden reasoning or
estimates billing. It counts observed role calls from response receipts and
reconciles them with role-only observer events. Native checks are distinct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELDS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
          "output_tokens", "reasoning_output_tokens")
PRODUCERS = {"production", "design"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("expected_object:" + path.name)
    return value


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("naive_timestamp")
    return parsed.astimezone(timezone.utc)


def seconds(start: str, end: str) -> float:
    result = (instant(end) - instant(start)).total_seconds()
    if result < 0:
        raise ValueError("negative_interval")
    return result


def quantiles(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"count": 0, "min": None, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    def at(p: float) -> float:
        position = (len(ordered) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return round(ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower), 3)
    return {"count": len(values), "min": round(ordered[0], 3), "p50": at(.5),
            "p95": at(.95), "max": round(ordered[-1], 3)}


def usage_profile(calls: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Sum known fields while preserving nulls; never add subset fields."""
    errors = []
    fields = {}
    for field in FIELDS:
        known, missing = 0, 0
        for call in calls:
            value = (call.get("usage") or {}).get(field)
            if type(value) is int and value >= 0:
                known += value
            else:
                missing += 1
        fields[field] = {"known_sum": known, "complete_sum": known if missing == 0 else None,
                         "present_calls": len(calls) - missing, "missing_calls": missing}
    uncached_known = nonreasoning_known = combined_known = 0
    uncached_missing = nonreasoning_missing = combined_missing = 0
    for call in calls:
        usage = call.get("usage") or {}
        input_value, cached = usage.get("input_tokens"), usage.get("cached_input_tokens")
        output_value, reasoning = usage.get("output_tokens"), usage.get("reasoning_output_tokens")
        if type(input_value) is int and type(cached) is int and input_value >= 0 and cached >= 0:
            if cached > input_value:
                errors.append("cached_input_exceeds_input")
                uncached_missing += 1
            else:
                uncached_known += input_value - cached
        else:
            uncached_missing += 1
        if type(output_value) is int and type(reasoning) is int and output_value >= 0 and reasoning >= 0:
            if reasoning > output_value:
                errors.append("reasoning_output_exceeds_output")
                nonreasoning_missing += 1
            else:
                nonreasoning_known += output_value - reasoning
        else:
            nonreasoning_missing += 1
        if type(input_value) is int and type(output_value) is int and input_value >= 0 and output_value >= 0:
            combined_known += input_value + output_value
        else:
            combined_missing += 1
    derived = {
        "uncached_input_tokens": {"known_sum": uncached_known,
                                  "complete_sum": uncached_known if uncached_missing == 0 else None,
                                  "missing_calls": uncached_missing},
        "nonreasoning_output_tokens": {"known_sum": nonreasoning_known,
                                       "complete_sum": nonreasoning_known if nonreasoning_missing == 0 else None,
                                       "missing_calls": nonreasoning_missing},
        "input_plus_output_tokens": {"known_sum": combined_known,
                                     "complete_sum": combined_known if combined_missing == 0 else None,
                                     "missing_calls": combined_missing},
    }
    return {"call_count": len(calls), "fields": fields, "derived": derived,
            "nonadditive_attributes": ["cached_input_tokens", "cache_write_input_tokens",
                                       "reasoning_output_tokens"],
            "additive_total_rule": "input_tokens + output_tokens only when both reported",
            "billing_verified": False, "private_reasoning_content_accessed": False}, errors


def summary_usage_errors(summary: dict[str, Any], calls: list[dict[str, Any]], profile: dict[str, Any]) -> list[str]:
    observed = summary.get("usage") or {}
    errors = []
    if observed.get("call_count") != len(calls):
        errors.append("summary_call_count_mismatch")
    for field in FIELDS:
        expected = profile["fields"][field]
        # The runner deliberately emits null for a zero-call episode.
        complete = expected["complete_sum"] if calls else None
        if (observed.get("reported_usage") or {}).get(field) != complete:
            errors.append("summary_usage_mismatch:" + field)
        if (observed.get("missing_call_count") or {}).get(field) != expected["missing_calls"]:
            errors.append("summary_missingness_mismatch:" + field)
    if observed.get("derived_uncached_input_tokens") != (profile["derived"]["uncached_input_tokens"]["complete_sum"] if calls else None):
        errors.append("summary_uncached_mismatch")
    if observed.get("combined_input_plus_output_tokens") != (profile["derived"]["input_plus_output_tokens"]["complete_sum"] if calls else None):
        errors.append("summary_input_output_mismatch")
    return errors


def event_reconciliation(calls: list[dict[str, Any]], versions: list[dict[str, Any]],
                         observation: list[dict[str, Any]], summary: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Classify every marker by kind before comparing it to a model call."""
    errors = []
    role_starts = Counter(item["assignment_id"] for item in observation
                          if item.get("kind") == "role" and item.get("phase") == "start")
    role_ends = Counter(item["assignment_id"] for item in observation
                        if item.get("kind") == "role" and item.get("phase") == "terminal")
    check_starts = Counter(item["check_id"] for item in observation
                           if item.get("kind") == "native_check" and item.get("phase") == "start")
    check_ends = Counter(item["check_id"] for item in observation
                         if item.get("kind") == "native_check" and item.get("phase") == "terminal")
    call_ids = Counter(call.get("assignment_id") for call in calls)
    check_receipts = Counter(check["check_id"] for version in versions
                             for check in version.get("checks", []))
    if call_ids != role_starts or role_starts != role_ends:
        errors.append("role_assignment_markers_do_not_match_call_receipts")
    if check_receipts != check_starts or check_starts != check_ends:
        errors.append("native_check_markers_do_not_match_check_receipts")
    repeated = sum(count - 1 for count in call_ids.values() if count > 1)
    if repeated:
        errors.append("repeated_assignment_identity")
    threads = Counter(call.get("thread_sha256") for call in calls if call.get("thread_sha256"))
    repeated_threads = sum(count - 1 for count in threads.values() if count > 1)
    if repeated_threads:
        errors.append("repeated_thread_identity")
    event_summaries = Counter(item.get("assignment_id") for item in summary.get("role_event_summaries", []))
    if event_summaries != call_ids:
        errors.append("role_event_summary_identity_mismatch")
    rec = summary.get("observation_reconciliation") or {}
    total_start = sum(role_starts.values()) + sum(check_starts.values())
    total_end = sum(role_ends.values()) + sum(check_ends.values())
    if rec.get("start_count") != total_start or rec.get("terminal_count") != total_end:
        errors.append("all_marker_reconciliation_mismatch")
    if rec.get("start_without_terminal"):
        errors.append("observer_start_without_terminal")
    role_intervals, check_intervals = [], []
    role_durations_by_identity: dict[str, list[float]] = defaultdict(list)
    for kind, key, target in (("role", "assignment_id", role_intervals),
                              ("native_check", "check_id", check_intervals)):
        open_by_id: dict[str, deque[str]] = defaultdict(deque)
        for item in observation:
            if item.get("kind") != kind:
                continue
            identity = item.get(key)
            if item.get("phase") == "start":
                open_by_id[identity].append(item["utc"])
            elif item.get("phase") == "terminal":
                if not open_by_id[identity]:
                    errors.append(kind + "_terminal_without_start")
                    continue
                started = open_by_id[identity].popleft()
                elapsed = seconds(started, item["utc"])
                target.append((started, item["utc"], elapsed))
                if kind == "role":
                    role_durations_by_identity[identity].append(elapsed)
                nanos = item.get("elapsed_ns")
                if type(nanos) is not int or nanos < 0 or abs(elapsed - nanos / 1e9) > 1.0:
                    errors.append(kind + "_elapsed_mismatch")
        if any(open_by_id.values()):
            errors.append(kind + "_open_intervals")
    return {
        "role_start_markers": sum(role_starts.values()),
        "role_terminal_markers": sum(role_ends.values()),
        "native_check_start_markers": sum(check_starts.values()),
        "native_check_terminal_markers": sum(check_ends.values()),
        "all_start_markers": total_start, "all_terminal_markers": total_end,
        "call_receipts": len(calls), "native_check_receipts": sum(check_receipts.values()),
        "repeated_assignment_identities": repeated,
        "repeated_thread_identities": repeated_threads,
        "role_intervals": role_intervals, "check_intervals": check_intervals,
        "role_durations_by_identity": dict(role_durations_by_identity),
        "explanation": "observer all-marker counts include role invocations AND local native checks; only role markers consume model calls",
    }, errors


def peak_overlap(intervals: list[tuple[str, str]]) -> int:
    events = []
    for start, end in intervals:
        if instant(end) < instant(start):
            raise ValueError("negative_overlap_interval")
        events.extend(((instant(start), 1), (instant(end), -1)))
    active = peak = 0
    for _, delta in sorted(events, key=lambda item: (item[0], item[1])):
        active += delta
        peak = max(peak, active)
    return peak


def episode_read(root: Path, cell: dict[str, Any], *, require_complete: bool) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[str]]:
    folder = root / cell["id"]
    errors = []
    started_path, terminal_path = folder / "started.json", folder / "terminal.json"
    response_path, summary_path = folder / "response.json", folder / "summary.json"
    observation_path = folder / "observation.jsonl"
    if not started_path.is_file():
        errors.append("episode_missing_start")
        return {"cell_id": cell["id"], "complete": False, "call_count": None}, [], {}, errors
    started = read(started_path)
    terminal = read(terminal_path) if terminal_path.is_file() else None
    if terminal is None and require_complete:
        errors.append("episode_missing_terminal")
    response = read(response_path) if response_path.is_file() else None
    summary = read(summary_path) if summary_path.is_file() else None
    if response is None or summary is None:
        if require_complete:
            errors.append("episode_missing_response_or_summary")
        return {"cell_id": cell["id"], "complete": terminal is not None,
                "call_count": None, "episode_elapsed_seconds": seconds(started["utc"], terminal["utc"]) if terminal else None}, [], {}, errors
    observation = []
    if observation_path.is_file():
        for raw in observation_path.read_text().splitlines():
            try:
                item = json.loads(raw)
                if not isinstance(item, dict):
                    raise ValueError("nonobject")
                observation.append(item)
            except ValueError:
                errors.append("malformed_observation_line")
    elif require_complete:
        errors.append("episode_missing_observation")
    calls = response.get("calls") or []
    if not isinstance(calls, list):
        errors.append("calls_not_list")
        calls = []
    versions = [version for unit in response.get("units", []) for version in unit.get("versions", [])]
    events, event_errors = event_reconciliation(calls, versions, observation, summary)
    errors.extend(event_errors)
    profile, usage_errors = usage_profile(calls)
    errors.extend(usage_errors)
    errors.extend(summary_usage_errors(summary, calls, profile))
    if terminal and instant(summary["ended_utc"]) > instant(terminal["utc"]) and seconds(terminal["utc"], summary["ended_utc"]) > 1:
        errors.append("summary_ended_after_terminal")
    if instant(summary["started_utc"]) < instant(started["utc"]) and seconds(summary["started_utc"], started["utc"]) > 1:
        errors.append("summary_started_before_episode")
    if len(summary.get("role_event_summaries", [])) != len(calls):
        errors.append("role_event_summary_count_mismatch")
    model = cell["model"]
    effort = cell["effort"]
    for call in calls:
        label = call.get("model") or {}
        if not isinstance(label, dict) or label.get("name") != model or label.get("effort") != effort:
            errors.append("call_model_or_effort_drift")
    status_counts = Counter(call.get("status", "unknown") for call in calls)
    reasons = Counter(call.get("reason", "unknown") for call in calls)
    roles = Counter(call.get("role", "unknown") for call in calls)
    process_exits = Counter(str(call.get("process_exit_code")) for call in calls)
    units = Counter((unit.get("unit_id", "unknown"), unit.get("status", "unknown"))
                    for unit in response.get("units", []))
    native_status = Counter(check.get("status", "unknown") for version in versions
                            for check in version.get("checks", []))
    producer_calls = Counter(call.get("unit_id") for call in calls if call.get("role") in PRODUCERS)
    extra_producer = sum(max(0, count - 1) for count in producer_calls.values())
    repair_versions = sum(max(0, len(unit.get("versions", [])) - 1)
                          for unit in response.get("units", []))
    call_rows = []
    for call in calls:
        elapsed = events["role_durations_by_identity"].get(call.get("assignment_id"), [])
        call_rows.append({"cell_id": cell["id"], "arm": cell.get("arm"),
                          "model": model, "effort": effort, "model_effort": model + "/" + effort,
                          "_assignment_id": call.get("assignment_id"),
                          "_thread_sha256": call.get("thread_sha256"),
                          "locale": cell.get("locale"), "condition": cell.get("condition"),
                          "unit_id": call.get("unit_id"), "role": call.get("role"),
                          "status": call.get("status"), "reason": call.get("reason"),
                          "process_exit_code": call.get("process_exit_code"),
                          "usage": call.get("usage"),
                          "role_elapsed_seconds": elapsed[0] if len(elapsed) == 1 else None,
                          "backend_attempts": call.get("backend_attempts"),
                          "failed_turn_events": call.get("failed_turn_events"),
                          "provider_error_events": call.get("provider_error_events")})
    episode_elapsed = seconds(started["utc"], terminal["utc"]) if terminal else None
    child_elapsed = seconds(summary["started_utc"], summary["ended_utc"])
    record = {
        "cell_id": cell["id"], "model": model, "effort": effort,
        "arm": cell.get("arm"), "locale": cell.get("locale"),
        "condition": cell.get("condition"), "complete": terminal is not None,
        "response_status": response.get("status"), "call_count": len(calls),
        "role_call_counts": dict(sorted(roles.items())),
        "call_status_counts": dict(sorted(status_counts.items())),
        "call_reason_counts": dict(sorted(reasons.items())),
        "process_exit_code_counts": dict(sorted(process_exits.items())),
        "native_unit_status_counts": [
            {"unit_id": unit, "status": status, "count": count}
            for (unit, status), count in sorted(units.items())],
        "native_check_status_counts": dict(sorted(native_status.items())),
        "native_check_process_count": events["native_check_receipts"],
        "observed_extra_producer_calls": extra_producer,
        "repair_versions": repair_versions,
        "usage": profile,
        "episode_elapsed_seconds": round(episode_elapsed, 3) if episode_elapsed is not None else None,
        "child_elapsed_seconds": round(child_elapsed, 3),
        "role_elapsed_seconds_sum": round(sum(item[2] for item in events["role_intervals"]), 3),
        "native_check_elapsed_seconds_sum": round(sum(item[2] for item in events["check_intervals"]), 3),
        "marker_reconciliation": {key: value for key, value in events.items()
                                  if key not in {"role_intervals", "check_intervals", "role_durations_by_identity"}},
        "backend_attempts_observable": all(type(call.get("backend_attempts")) is int for call in calls),
        "integrity_errors": sorted(set(errors)),
    }
    return record, call_rows, {"episode_interval": (started["utc"], terminal["utc"]) if terminal else None,
                               "role_intervals": [(start, end) for start, end, _ in events["role_intervals"]],
                               "role_elapsed": [item[2] for item in events["role_intervals"]],
                               "native_check_elapsed": [item[2] for item in events["check_intervals"]],
                               "native_check_count": events["native_check_receipts"],
                               "call_count": len(calls),
                               "observation_kind_counts": Counter(item.get("kind", "unknown") for item in observation),
                               "summary_status": summary.get("status")}, errors


def group_calls(calls: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in calls:
        grouped[str(call.get(key) if call.get(key) is not None else "not_applicable")].append(call)
    result = {}
    for label, selected in sorted(grouped.items()):
        usage, issues = usage_profile(selected)
        elapsed = [call["role_elapsed_seconds"] for call in selected
                   if call["role_elapsed_seconds"] is not None]
        result[label] = {"call_count": len(selected), "usage": usage,
                         "status_counts": dict(sorted(Counter(call["status"] for call in selected).items())),
                         "role_elapsed_seconds": quantiles(elapsed),
                         "role_elapsed_seconds_sum": round(sum(elapsed), 3),
                         "usage_integrity_errors": sorted(set(issues))}
    return result


def duplicate_id_counts(calls: list[dict[str, Any]]) -> tuple[int, int]:
    assignments = Counter(call.get("_assignment_id") for call in calls if call.get("_assignment_id"))
    threads = Counter(call.get("_thread_sha256") for call in calls if call.get("_thread_sha256"))
    return (sum(count - 1 for count in assignments.values() if count > 1),
            sum(count - 1 for count in threads.values() if count > 1))


def inventory(root: Path, cells: list[dict[str, Any]], freeze: Path,
              dispatch: Path | None, external: Path | None) -> tuple[list[dict[str, str]], str]:
    files: list[tuple[str, Path]] = [("freeze.json", freeze)]
    if dispatch and dispatch.is_file():
        files.append(("dispatch-index.json", dispatch))
    if external and external.is_file():
        files.append((str(external.relative_to(root)), external))
    for cell in cells:
        episode = root / cell["id"]
        for name in ("started.json", "terminal.json", "startup-failure.json",
                     "response.json", "summary.json", "observation.jsonl", "memory-setup.json"):
            path = episode / name
            if path.is_file():
                files.append((f"{cell['id']}/{name}", path))
    for folder_name in ("external-qualification", "external-qualification-continuity", "external-qualification-S"):
        folder = root / folder_name
        if folder.is_dir():
            for path in folder.rglob("receipt.json"):
                files.append((str(path.relative_to(root)), path))
            for path in folder.rglob("post-role-state.json"):
                files.append((str(path.relative_to(root)), path))
    entries = [{"path": name, "sha256": "sha256:" + sha(path.read_bytes())}
               for name, path in sorted(files)]
    digest = "sha256:" + sha(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode())
    return entries, digest


def aggregate_cohort(root: Path, freeze_path: Path, cohort: str,
                     *, require_complete: bool = True, snapshot_at: str | None = None) -> dict[str, Any]:
    freeze = read(freeze_path)
    cells = freeze.get("cells") or []
    if not isinstance(cells, list) or len(cells) != len(freeze.get("cell_ids", [])):
        raise ValueError("freeze_cell_set_invalid")
    if {cell["id"] for cell in cells} != set(freeze["cell_ids"]):
        raise ValueError("freeze_cell_ids_mismatch")
    if not require_complete and not snapshot_at:
        raise ValueError("incomplete_snapshot_requires_explicit_as_of")
    errors = []
    records = []
    calls = []
    episode_intervals: list[tuple[str, str]] = []
    role_intervals: list[tuple[str, str]] = []
    role_elapsed: list[float] = []
    native_elapsed: list[float] = []
    kinds = Counter()
    native_checks = 0
    for cell in cells:
        record, call_rows, times, issues = episode_read(root, cell, require_complete=require_complete)
        records.append(record)
        calls.extend(call_rows)
        errors.extend({"cell_id": cell["id"], "code": issue} for issue in issues)
        if times.get("episode_interval"):
            episode_intervals.append(times["episode_interval"])
        role_intervals.extend(times.get("role_intervals", []))
        role_elapsed.extend(times.get("role_elapsed", []))
        native_elapsed.extend(times.get("native_check_elapsed", []))
        native_checks += times.get("native_check_count", 0)
        kinds.update(times.get("observation_kind_counts", {}))
    if require_complete and (len(role_elapsed) != len(calls) or len(native_elapsed) != native_checks):
        errors.append({"cell_id": None, "code": "timed_marker_count_mismatch"})
    usage, usage_issues = usage_profile(calls)
    errors.extend({"cell_id": None, "code": code} for code in usage_issues)
    repeated_assignments, repeated_threads = duplicate_id_counts(calls)
    if repeated_assignments:
        errors.append({"cell_id": None, "code": "cohort_repeated_assignment_identity"})
    if repeated_threads:
        errors.append({"cell_id": None, "code": "cohort_repeated_thread_identity"})
    by_arm = group_calls(calls, "arm")
    by_role = group_calls(calls, "role")
    by_unit = group_calls(calls, "unit_id")
    by_model = group_calls(calls, "model")
    by_model_effort = group_calls(calls, "model_effort")
    by_condition = group_calls(calls, "condition")
    for group_name, grouping in (("arm", by_arm), ("role", by_role), ("unit", by_unit),
                                 ("model", by_model), ("model_effort", by_model_effort),
                                 ("condition", by_condition)):
        if sum(item["call_count"] for item in grouping.values()) != len(calls):
            errors.append({"cell_id": None, "code": "group_call_count_mismatch:" + group_name})
        for field in FIELDS:
            if (sum(item["usage"]["fields"][field]["known_sum"] for item in grouping.values())
                != usage["fields"][field]["known_sum"] or
                sum(item["usage"]["fields"][field]["missing_calls"] for item in grouping.values())
                != usage["fields"][field]["missing_calls"]):
                errors.append({"cell_id": None, "code": "group_usage_mismatch:" + group_name + ":" + field})
    call_status = Counter(call["status"] for call in calls)
    call_reason = Counter(call["reason"] for call in calls)
    nonzero_exit_calls = sum(type(call["process_exit_code"]) is int and call["process_exit_code"] != 0 for call in calls)
    unknown_exit_calls = sum(type(call["process_exit_code"]) is not int for call in calls)
    unit_status = Counter((row["unit_id"], row["status"])
                          for record in records for row in record.get("native_unit_status_counts", [])
                          for _ in range(row["count"]))
    check_status = Counter(status for record in records
                           for status, count in record.get("native_check_status_counts", {}).items()
                           for _ in range(count))
    failed_turn_events = provider_error_events = 0
    failed_turn_missing = provider_error_missing = backend_attempt_missing = 0
    for call in calls:
        for field in ("failed_turn_events", "provider_error_events"):
            value = call.get(field)
            if type(value) is int and value >= 0:
                if field == "failed_turn_events":
                    failed_turn_events += value
                else:
                    provider_error_events += value
            elif field == "failed_turn_events":
                failed_turn_missing += 1
            else:
                provider_error_missing += 1
        if type(call.get("backend_attempts")) is not int:
            backend_attempt_missing += 1
    dispatch_path = root / "dispatch-index.json"
    dispatch = read(dispatch_path) if dispatch_path.is_file() else None
    observed_peak_episodes = peak_overlap(episode_intervals)
    observed_peak_roles = peak_overlap(role_intervals)
    complete_episodes = sum(record["complete"] for record in records)
    if require_complete and complete_episodes != len(cells):
        errors.append({"cell_id": None, "code": "cohort_not_terminal"})
    if dispatch:
        for field, expected in (
            ("scheduled_cells", len(cells)),
            ("returned_cells", len(cells) if require_complete else complete_episodes),
            ("completed_role_intervals", len(role_intervals)),
            ("observed_peak_episode_overlap", observed_peak_episodes),
            ("observed_peak_role_overlap", observed_peak_roles),
        ):
            if dispatch.get(field) != expected:
                errors.append({"cell_id": None, "code": "dispatch_index_mismatch:" + field})
        if require_complete and (not dispatch.get("episode_overlap_complete") or not dispatch.get("role_overlap_complete")):
            errors.append({"cell_id": None, "code": "dispatch_observation_incomplete"})
    elif require_complete:
        errors.append({"cell_id": None, "code": "dispatch_index_missing"})
    external_path = next((root / name for name in (
        "external-qualification/index.json", "external-qualification-continuity/index.json",
        "external-qualification-S/index.json") if (root / name).is_file()), None)
    external = read(external_path) if external_path else None
    if external:
        if external.get("scheduled_cells") != len(cells):
            errors.append({"cell_id": None, "code": "external_index_cell_count_mismatch"})
        if external.get("model_calls") != 0:
            errors.append({"cell_id": None, "code": "external_index_model_calls_nonzero_or_unknown"})
    elif require_complete:
        errors.append({"cell_id": None, "code": "external_index_missing"})
    setup_call_values = []
    for cell in cells:
        path = root / cell["id"] / "memory-setup.json"
        if path.is_file():
            setup_call_values.append(read(path).get("role_model_calls"))
    if any(value != 0 for value in setup_call_values):
        errors.append({"cell_id": None, "code": "memory_setup_model_calls_nonzero_or_unknown"})
    freeze_dry = (freeze.get("dry_run") or {}).get("model_calls")
    if freeze_dry not in (None, 0):
        errors.append({"cell_id": None, "code": "freeze_preparation_model_calls_nonzero"})
    entries, inventory_sha = inventory(root, cells, freeze_path, dispatch_path if dispatch else None, external_path)
    complete_durations = [record["episode_elapsed_seconds"] for record in records
                          if record.get("episode_elapsed_seconds") is not None]
    child_durations = [record["child_elapsed_seconds"] for record in records
                       if record.get("child_elapsed_seconds") is not None]
    starts = [start for start, _ in episode_intervals]
    ends = [end for _, end in episode_intervals]
    wall = seconds(min(starts), max(ends)) if starts and ends else None
    result = {
        "schema": "opensocrates.go-ts.usage-timing-analysis/1",
        "cohort": cohort, "evidence_state": "complete_original_receipts" if complete_episodes == len(cells) else "partial_snapshot",
        "snapshot_at_utc": snapshot_at if complete_episodes != len(cells) else None,
        "planned_episodes": len(cells), "completed_episodes": complete_episodes,
        "episodes_with_response": sum(record["call_count"] is not None for record in records),
        "role_model_call_receipts": len(calls),
        "native_check_processes": native_checks,
        "observer_kind_counts": dict(sorted(kinds.items())),
        "role_call_status_counts": dict(sorted(call_status.items())),
        "role_call_reason_counts": dict(sorted(call_reason.items())),
        "failed_or_invalid_role_calls": sum(status != "completed" for status in call_status.elements()),
        "nonzero_process_exit_role_calls": nonzero_exit_calls,
        "unknown_process_exit_role_calls": unknown_exit_calls,
        "native_unit_status_counts": [
            {"unit_id": unit, "status": status, "count": count}
            for (unit, status), count in sorted(unit_status.items())],
        "blocked_dependency_units": sum(count for (_, status), count in unit_status.items()
                                        if status == "blocked_dependency"),
        "native_check_status_counts": dict(sorted(check_status.items())),
        "observed_extra_producer_invocations": sum(record.get("observed_extra_producer_calls", 0) for record in records),
        "repair_versions": sum(record.get("repair_versions", 0) for record in records),
        "episodes_with_extra_producer_invocations": sum(record.get("observed_extra_producer_calls", 0) > 0 for record in records),
        "usage": usage,
        "usage_by_arm": by_arm,
        "usage_by_role": by_role,
        "usage_by_unit": by_unit,
        "usage_by_model": by_model,
        "usage_by_model_effort": by_model_effort,
        "usage_by_condition": by_condition,
        "role_elapsed_seconds": quantiles(role_elapsed),
        "role_elapsed_seconds_sum": round(sum(role_elapsed), 3),
        "native_check_elapsed_seconds": quantiles(native_elapsed),
        "native_check_elapsed_seconds_sum": round(sum(native_elapsed), 3),
        "episode_elapsed_seconds": quantiles(complete_durations),
        "child_elapsed_seconds": quantiles(child_durations),
        "cohort_wall_span_seconds": round(wall, 3) if wall is not None else None,
        "observed_peak_episode_overlap": observed_peak_episodes,
        "observed_peak_role_overlap": observed_peak_roles,
        "observer_dispatch_index_sha256": "sha256:" + sha(dispatch_path.read_bytes()) if dispatch else None,
        "external_qualification": {
            "variant_count": len(external.get("variants", [])) if external else None,
            "status_counts": dict(sorted(Counter(item.get("status", "unknown") for item in external.get("variants", [])).items())) if external else None,
            "reported_model_calls": external.get("model_calls") if external else None,
            "usage_added_to_subject_total": False,
        },
        "preparation_and_helper_usage": {
            "freeze_dry_run_model_calls": freeze_dry,
            "real_memory_setup_receipts": len(setup_call_values),
            "real_memory_setup_role_model_calls_reported": sum(setup_call_values) if setup_call_values else None,
            "other_helper_usage_outside_these_roots": "not_observed",
            "added_to_subject_total": False,
        },
        "event_counts_not_model_calls": {
            "failed_turn_events_known_sum": failed_turn_events,
            "failed_turn_events_missing_call_count": failed_turn_missing,
            "provider_error_events_known_sum": provider_error_events,
            "provider_error_events_missing_call_count": provider_error_missing,
            "backend_attempts_null_or_unavailable_calls": backend_attempt_missing,
        },
        "episodes": records,
        "integrity": {"passed": not errors, "error_count": len(errors), "errors": errors,
                      "all_role_assignment_ids_matched": not any("role_assignment" in item["code"] for item in errors),
                      "all_native_check_ids_matched": not any("native_check_markers" in item["code"] for item in errors),
                      "duplicate_attempt_identity_count": repeated_assignments,
                      "duplicate_thread_identity_count": repeated_threads},
        "provenance": {"freeze_sha256": "sha256:" + sha(freeze_path.read_bytes()),
                       "summarizer_sha256": "sha256:" + sha(Path(__file__).read_bytes()),
                       "input_inventory_sha256": inventory_sha,
                       "input_inventory": entries,
                       "source_root_paths_retained": False,
                       "raw_prompts_transcripts_reasoning_or_tool_outputs_retained": False},
        "limits": ["Exposed token counters are not a billed-cost measurement.",
                   "Cached input and cache-write input are reported alongside input, not added to it; reasoning output is within output.",
                   "Internal backend attempts and private reasoning content are unobservable here.",
                   "Completion, latency and token use do not establish answer quality.",
                   "Concurrent episode durations cannot be summed into cohort wall time."],
    }
    return result


def render_markdown(result: dict[str, Any]) -> str:
    def number(value: int | None) -> str:
        return f"{value:,}" if value is not None else "unavailable"
    def token(field: str) -> str:
        entry = result["usage"]["fields"][field]
        if entry["complete_sum"] is None:
            return f"unavailable (known {number(entry['known_sum'])}; {entry['missing_calls']} missing calls)"
        return number(entry["complete_sum"])
    def interval(value: dict[str, Any]) -> str:
        return (f"n={value['count']}, p50={value['p50']:.3f}s, p95={value['p95']:.3f}s"
                if value["count"] else "unavailable")

    lines = [
        f"# {result['cohort']} usage and timing from original receipts",
        "",
        f"Evidence state: **{result['evidence_state']}**. Scheduled episodes: **{result['planned_episodes']}**; terminal episodes: **{result['completed_episodes']}**; response receipts: **{result['episodes_with_response']}**.",
        "",
        f"Observed model-role calls: **{result['role_model_call_receipts']}**, including every returned status. Local native-check processes: **{result['native_check_processes']}**. The observer's all-marker count is the sum of these two kinds; native checks have no model-token usage.",
        "",
        f"Role-call statuses: {', '.join(f'{key} {value}' for key, value in result['role_call_status_counts'].items()) or 'none'}. Nonzero role process exits: {result['nonzero_process_exit_role_calls']}; unknown process exits: {result['unknown_process_exit_role_calls']}. Native-check statuses: {', '.join(f'{key} {value}' for key, value in result['native_check_status_counts'].items()) or 'none'}. Blocked dependency units: {result['blocked_dependency_units']} (these are units whose downstream role calls were not made).",
        "Native unit states (not call counts): " + (", ".join(f"{row['unit_id']} {row['status']} {row['count']}" for row in result["native_unit_status_counts"]) or "none") + ".",
        f"Observed provider-error event items: {result['event_counts_not_model_calls']['provider_error_events_known_sum']}; failed-turn event items: {result['event_counts_not_model_calls']['failed_turn_events_known_sum']}. Backend-attempt counts were null/unavailable for {result['event_counts_not_model_calls']['backend_attempts_null_or_unavailable_calls']} role calls. These event items are not additional role calls.",
        "",
        "| Exposed category | Cohort total | Missing calls | Accounting meaning |",
        "| --- | ---: | ---: | --- |",
    ]
    meanings = {
        "input_tokens": "Input; additive across observed calls",
        "cached_input_tokens": "Included within input; do not add again",
        "cache_write_input_tokens": "Reported input attribute; kept separate from additive total",
        "output_tokens": "Output; additive across observed calls",
        "reasoning_output_tokens": "Included within output; count only, no reasoning content",
    }
    for field in FIELDS:
        entry = result["usage"]["fields"][field]
        lines.append(f"| {field} | {token(field)} | {entry['missing_calls']} | {meanings[field]} |")
    combined = result["usage"]["derived"]["input_plus_output_tokens"]
    uncached = result["usage"]["derived"]["uncached_input_tokens"]
    lines += [
        "",
        f"Reported input + output, without subset double counting: **{number(combined['complete_sum'])}**. Derived uncached input (input minus cached input): **{number(uncached['complete_sum'])}**. These are token counters, **not billed cost**.",
        "",
        f"Observed extra producer invocations: **{result['observed_extra_producer_invocations']}**; additional version numbers after v1: **{result['repair_versions']}**. The two measures are kept separate because a producer call need not yield a retained version.",
        "",
        f"Role elapsed time: {interval(result['role_elapsed_seconds'])}; summed role-process time {result['role_elapsed_seconds_sum']:.3f}s. Whole-episode elapsed time: {interval(result['episode_elapsed_seconds'])}. Cohort wall span: {result['cohort_wall_span_seconds']:.3f}s." if result["cohort_wall_span_seconds"] is not None else "Role/episode time is incomplete.",
        f"Observed peak overlap: {result['observed_peak_episode_overlap']} episodes and {result['observed_peak_role_overlap']} role processes. These are measured intervals, not account/backend independence attestations.",
        "",
        "| Role | Calls | Input | Cached input | Output | Reasoning-output subset | Role elapsed sum |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for role, item in result["usage_by_role"].items():
        fields = item["usage"]["fields"]
        lines.append(f"| {role} | {item['call_count']} | {number(fields['input_tokens']['complete_sum'])} | {number(fields['cached_input_tokens']['complete_sum'])} | {number(fields['output_tokens']['complete_sum'])} | {number(fields['reasoning_output_tokens']['complete_sum'])} | {item['role_elapsed_seconds_sum']:.3f}s |")
    axis = "arm" if any(name != "not_applicable" for name in result["usage_by_arm"]) else "condition"
    lines += ["", f"| {axis.title()} | Calls | Input | Output | Missing input/output calls |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for name, item in result["usage_by_" + axis].items():
        fields = item["usage"]["fields"]
        missing = max(fields["input_tokens"]["missing_calls"], fields["output_tokens"]["missing_calls"])
        lines.append(f"| {name} | {item['call_count']} | {number(fields['input_tokens']['complete_sum'])} | {number(fields['output_tokens']['complete_sum'])} | {missing} |")
    lines += ["", "| Model / effort | Calls | Input | Output |",
              "| --- | ---: | ---: | ---: |"]
    for name, item in result["usage_by_model_effort"].items():
        fields = item["usage"]["fields"]
        lines.append(f"| {name} | {item['call_count']} | {number(fields['input_tokens']['complete_sum'])} | {number(fields['output_tokens']['complete_sum'])} |")
    external = result["external_qualification"]
    prep = result["preparation_and_helper_usage"]
    lines += [
        "",
        f"External qualification variants: {external['variant_count'] if external['variant_count'] is not None else 'unavailable'}; its reported model calls: {external['reported_model_calls'] if external['reported_model_calls'] is not None else 'unavailable'}. Preparation dry-run reported model calls: {prep['freeze_dry_run_model_calls'] if prep['freeze_dry_run_model_calls'] is not None else 'unavailable'}; disposable memory setup receipts: {prep['real_memory_setup_receipts']}, with reported role model calls {prep['real_memory_setup_role_model_calls_reported'] if prep['real_memory_setup_role_model_calls_reported'] is not None else 'unavailable'}. Neither category was added to subject-role tokens. Other helper usage outside these receipt roots is unobserved.",
        "",
        f"Integrity cross-check: **{'passed' if result['integrity']['passed'] else 'failed'}** ({result['integrity']['error_count']} issues). Original input inventory: {len(result['provenance']['input_inventory'])} files; manifest digest `{result['provenance']['input_inventory_sha256']}`; freeze digest `{result['provenance']['freeze_sha256']}`.",
        "",
        "The role-assignment IDs in response calls were compared with **role-only** start and terminal markers; native-check IDs were compared separately with check receipts. All-marker reconciliation therefore does not create a missing-model-call warning. Duplicate attempt identities are reported rather than silently deduplicated.",
        "",
        "Limits: reported usage does not prove billed cost or internal backend retry count. The reasoning-output field is a count, not access to private reasoning. Completion, latency and token use do not establish answer quality. Concurrent episode durations must not be added to infer wall time.",
        "",
    ]
    if result["integrity"]["errors"]:
        lines += ["Integrity issues:", ""]
        for item in result["integrity"]["errors"]:
            lines.append(f"- {item['cell_id'] or 'cohort'}: {item['code']}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--md-out", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    parser.add_argument("--snapshot-at", help="required UTC as-of timestamp for an incomplete snapshot")
    args = parser.parse_args()
    if args.json_out.exists() or args.md_out.exists():
        parser.error("output already exists")
    result = aggregate_cohort(args.root.resolve(), args.freeze.resolve(), args.cohort,
                              require_complete=not args.allow_incomplete,
                              snapshot_at=args.snapshot_at)
    with args.json_out.open("x", encoding="utf-8") as out:
        json.dump(result, out, indent=2, sort_keys=True, ensure_ascii=False)
        out.write("\n")
    with args.md_out.open("x", encoding="utf-8") as out:
        out.write(render_markdown(result))
    print(json.dumps({"cohort": result["cohort"], "integrity_passed": result["integrity"]["passed"],
                      "calls": result["role_model_call_receipts"],
                      "native_checks": result["native_check_processes"],
                      "inventory_sha256": result["provenance"]["input_inventory_sha256"]}, sort_keys=True))
    return 0 if result["integrity"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
