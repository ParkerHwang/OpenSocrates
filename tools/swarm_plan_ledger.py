#!/usr/bin/env python3
"""Prepare a fixed 54-cell plan and maintain its single-attempt budget ledger.

Python 3.12 standard library only. No host, network, model, agent, subprocess,
authentication, result-text storage, or retry implementation exists here.

Central-owner contract
----------------------
S078 alone initializes and records the one selected plan/ledger. ``--owner`` is
an operator assertion, not authentication. Filesystem ownership and S001's
selection/resource lease remain external requirements. Do not copy the selected
plan to bypass its persistent .initialized receipt or create a second budget.
The caller also checks the authorized stop time and live host/scope stability.

Before EVERY actual call, S078 records STARTED with the current ledger revision,
the frozen manifest and verified isolation evidence. Only after a successful
durable write may S078 make that one call. A STARTED cell is a durable central
execution reservation: another cell cannot start until it is terminal. A crash
after STARTED consumes that attempt; explicitly close it as FAILED or TIMEOUT,
never rerun it. Terminal records cannot be replaced, even with the same status.
On any write error or lost success response, do not dispatch; reconcile the
persisted reservation conservatively without issuing another actor call.
NOT_RUN -> BLOCKED is terminal and makes no call. Failure/timeout stays in the
attempt denominator; BLOCKED/NOT_RUN remains visible in the assigned 54.

Files use fail-fast exclusive sidecar locks, revision compare-and-swap, temp
files, fsync and atomic replacement. A crash can leave a .lock or .initialized
receipt: reconcile it manually against the ledger; never delete/retry it
automatically. Locks serialize compliant writers, not a hostile same-user writer.

CLI (all paths explicit; authoring this tool does not execute these examples):
  plan --input config.json --output assignment-plan.json
  init --input assignment-plan.json --output assignment-ledger.json --owner S078
       [--freeze freeze-manifest.json --isolation isolation-preflight.json]
  record --input assignment-ledger.json --output assignment-ledger.json
         --event event.json --expected-revision 0 --owner S078
         [--freeze freeze-manifest.json --isolation isolation-preflight.json]

Init without evidence creates an inert ledger so missing approvals can be recorded
as BLOCKED. It never reserves a call. STARTED always needs both evidence files.
The first STARTED pins their digests; later starts must match those exact bytes.

Config: {"study_id":"swarm-20261015", "source_sha":"<40 lowercase hex>",
         "assignment_seed":20261015}. All keys are required; extras rejected.
Event: {"cell_id":"email-agreement-en-plain-r1", "attempt_id":"<from plan>",
        "status":"STARTED"}. Terminal failure/timeout/blocked additionally needs
``failure_reason`` from SAFE_REASONS. No free text or public answers enter this
ledger; S044 owns the separately sanitized answer store.

Freeze uses launch v1: FROZEN, exact source_sha, isolation_state VERIFIED,
quota 54, approved_by S001, UTC frozen_at, unique input_files {path, sha256}.
The immutable assignment-plan file MUST be among those frozen input digests.
Isolation consumes S042's report: tool swarm-isolation-preflight, status PASS,
isolation_blocked false, experiment_blocked true, execution_authorized false,
matching study_id and source_identity.source_sha, as_of UTC timestamp, and all
required structured isolation checks PASS. Final study freeze and a live lease
remain separate requirements. Coordinator approval comes from the freeze;
PASS alone never grants call permission. Both exact file
digests are pinned on first use, avoiding a circular freeze/report hash.
Additional upstream evidence keys are ignored, never retained. These are local
summary-consistency assertions, not attestations or proof of method application.
Native installation differs from manual canonical injection; independent judges
and observed backend model remain unknown/unavailable until separately evidenced.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
REPEATS = (1, 2, 3)
OWNER = "S078"
BUDGET = 54
ALGORITHM = "sha256-seed-cell-v1"
STATUSES = ("NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED")
TERMINAL = {"COMPLETED", "FAILED", "TIMEOUT", "BLOCKED"}
SAFE_REASONS = {
    "call_failed",
    "deadline_exceeded",
    "interrupted_after_start",
    "call_outcome_unknown",
    "freeze_unavailable",
    "isolation_unverified",
    "resource_unavailable",
    "host_unavailable",
    "owner_stopped",
}
MAX_JSON_BYTES = 2_000_000


class LedgerError(Exception):
    """A safe error category; never include input payloads or raw host errors."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise LedgerError(category)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def timestamp(value: Any) -> datetime:
    require(isinstance(value, str), "invalid_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise LedgerError("invalid_timestamp") from None
    require(parsed.utcoffset() is not None, "timestamp_requires_timezone")
    require(parsed.utcoffset().total_seconds() == 0, "timestamp_requires_utc")
    return parsed


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def hex_value(value: Any, length: int) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def exact_keys(value: Any, required: set[str], optional: set[str] | None = None) -> None:
    require(isinstance(value, dict), "object_required")
    require(required <= value.keys(), "missing_field")
    require(value.keys() <= required | (optional or set()), "unexpected_field")


def pairs_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def reject_constant(_value: str) -> None:
    raise LedgerError("nonfinite_json_number")


def local_file(path: Path) -> Path:
    """Resolve parent aliases so all compliant writers share one sidecar lock."""
    require(path.name not in {"", ".", ".."}, "invalid_file_path")
    require(not path.is_symlink(), "linked_file_refused")
    parent = path.absolute().parent.resolve(strict=True)
    require(parent.is_dir(), "parent_directory_required")
    return parent / path.name


def load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    require(path.is_file() and not path.is_symlink(), "regular_input_file_required")
    with path.open("rb") as stream:
        payload = stream.read(MAX_JSON_BYTES + 1)
    require(len(payload) <= MAX_JSON_BYTES, "json_size_limit")
    try:
        value = json.loads(payload, object_pairs_hook=pairs_object, parse_constant=reject_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise LedgerError("invalid_json") from None
    require(isinstance(value, dict), "object_required")
    return value, payload


def sync_directory(parent: Path) -> None:
    descriptor = os.open(parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def exclusive_lock(path: Path):
    lock = path.with_name(path.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise LedgerError("writer_locked_manual_reconciliation_required") from None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded({"owner": OWNER, "created_at": utc_now()}))
            stream.flush()
            os.fsync(stream.fileno())
        sync_directory(lock.parent)
        yield
    finally:
        lock.unlink()
        sync_directory(lock.parent)


def atomic_json(path: Path, value: Any, *, replace: bool = False) -> None:
    """Publish a whole JSON document, never a partially written ledger."""
    descriptor, temporary = tempfile.mkstemp(prefix=".swarm-ledger-", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded(value))
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            require(path.is_file() and not path.is_symlink(), "regular_output_file_required")
            os.replace(temporary_path, path)
        else:
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                raise LedgerError("output_exists_no_overwrite") from None
        sync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_config(config: dict[str, Any]) -> None:
    exact_keys(config, {"study_id", "source_sha", "assignment_seed"})
    require(
        isinstance(config["study_id"], str)
        and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", config["study_id"]) is not None,
        "invalid_study_id",
    )
    require(hex_value(config["source_sha"], 40), "invalid_source_sha")
    seed = config["assignment_seed"]
    require(type(seed) is int and 0 <= seed < 2**64, "invalid_assignment_seed")


def assignment_cells(config: dict[str, Any]) -> list[dict[str, Any]]:
    cells = []
    for family in FAMILIES:
        for locale in LOCALES:
            case_id = f"{family}-{locale}"
            for arm in ARMS:
                for repeat in REPEATS:
                    cell_id = f"{case_id}-{arm}-r{repeat}"
                    cells.append(
                        {
                            "cell_id": cell_id,
                            "case_id": case_id,
                            "family": family,
                            "locale": locale,
                            "arm": arm,
                            "repeat": repeat,
                            "assignment_seed": config["assignment_seed"],
                            "attempt_id": f"{config['study_id']}:{cell_id}:a1",
                            "status": "NOT_RUN",
                        }
                    )
    cells.sort(
        key=lambda cell: (
            digest(f"{config['assignment_seed']}\0{cell['cell_id']}".encode()),
            cell["cell_id"],
        )
    )
    for order, cell in enumerate(cells, 1):
        cell["order_index"] = order
    return cells


def validate_plan(plan: dict[str, Any]) -> None:
    exact_keys(
        plan,
        {
            "schema_version",
            "kind",
            "config",
            "ordering_algorithm",
            "actor_budget",
            "owner",
            "execution_allowed",
            "cells",
        },
    )
    validate_config(plan["config"])
    require(
        type(plan["schema_version"]) is int
        and plan["schema_version"] == 1
        and plan["kind"] == "assignment-plan",
        "invalid_plan",
    )
    require(plan["ordering_algorithm"] == ALGORITHM, "invalid_ordering_algorithm")
    require(type(plan["actor_budget"]) is int and plan["actor_budget"] == BUDGET, "invalid_budget")
    require(plan["owner"] == OWNER and plan["execution_allowed"] is False, "invalid_plan_owner")
    require(
        encoded(plan["cells"]) == encoded(assignment_cells(plan["config"])),
        "invalid_or_duplicate_cells",
    )


def freeze_inputs(freeze: dict[str, Any], plan_sha: str) -> None:
    inputs = freeze.get("input_files")
    require(isinstance(inputs, list) and bool(inputs), "frozen_inputs_required")
    seen = set()
    hashes = set()
    for item in inputs:
        require(isinstance(item, dict), "invalid_frozen_input")
        name, sha = item.get("path"), item.get("sha256")
        require(isinstance(name, str) and bool(name), "invalid_frozen_path")
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts, "invalid_frozen_path")
        require("\\" not in name and path.as_posix() == name, "invalid_frozen_path")
        require(name not in seen and hex_value(sha, 64), "duplicate_or_invalid_frozen_input")
        seen.add(name)
        hashes.add(sha)
    require(plan_sha in hashes, "assignment_plan_not_frozen")


def isolation_check_rows(rows: Any, expected: set[str]) -> None:
    """Require the complete S042 v1 check inventory, not a vacuous PASS label."""
    require(isinstance(rows, list) and len(rows) == len(expected), "isolation_checks_missing")
    names = []
    for row in rows:
        require(isinstance(row, dict), "invalid_isolation_check")
        require(row.get("status") == "PASS", "isolation_check_not_pass")
        name = row.get("check")
        require(isinstance(name, str), "invalid_isolation_check")
        names.append(name)
    require(len(set(names)) == len(names) and set(names) == expected, "isolation_check_inventory")


def isolation_report_checks(report: dict[str, Any]) -> None:
    """Check supplied summary consistency without upgrading it to permission."""
    require(report.get("isolation_blocked") is False, "isolation_blocked")
    require(report.get("experiment_blocked") is True, "isolation_is_not_authorization")
    require(report.get("execution_authorized") is False, "isolation_is_not_authorization")
    require(
        report.get("final_study_freeze_and_lease_required") is True,
        "isolation_central_gates_required",
    )
    require(
        report.get("evidence_level") == "provided-summary-consistency-only",
        "isolation_evidence_level_mismatch",
    )
    require(report.get("blocking_checks") == [], "isolation_blocking_checks_present")
    isolation_check_rows(
        report.get("global_checks"),
        {"source_configuration", "protocol_configuration", "source", "protocol", "privacy"},
    )
    arms = report.get("arms")
    require(isinstance(arms, list) and len(arms) == len(ARMS), "isolation_arms_missing")
    names = []
    expected = {
        "scope_configuration",
        "runtime_configuration",
        "runtime",
        "environment",
        "installation",
        "hooks",
        "skills",
        "memory",
        "workspace",
        "intervention_paths",
        "credential_boundary",
    }
    for arm in arms:
        require(isinstance(arm, dict), "invalid_isolation_arm")
        name = arm.get("arm")
        require(isinstance(name, str) and name in ARMS, "invalid_isolation_arm")
        require(arm.get("status") == "PASS", "isolation_arm_not_pass")
        require(
            arm.get("declarations_used_as_evidence") is False
            and arm.get("installation_is_application_proof") is False
            and arm.get("application_evidence") == "unverified",
            "isolation_application_claim_refused",
        )
        isolation_check_rows(arm.get("checks"), expected)
        names.append(name)
    require(len(set(names)) == len(ARMS), "isolation_duplicate_arm")


def gate_evidence(
    freeze_path: Path,
    isolation_path: Path,
    source_sha: str,
    plan_sha: str,
    study_id: str,
) -> dict[str, str]:
    freeze, freeze_bytes = load_json(freeze_path)
    isolation, isolation_bytes = load_json(isolation_path)
    require(
        type(freeze.get("schema_version")) is int and freeze["schema_version"] == 1,
        "invalid_freeze_schema",
    )
    require(freeze.get("state") == "FROZEN", "protocol_not_frozen")
    require(freeze.get("source_sha") == source_sha, "freeze_source_mismatch")
    require(freeze.get("isolation_state") == "VERIFIED", "freeze_isolation_unverified")
    require(
        type(freeze.get("quota")) is int and freeze["quota"] == BUDGET, "freeze_budget_mismatch"
    )
    require(freeze.get("approved_by") == "S001", "freeze_approval_missing")
    require(timestamp(freeze.get("frozen_at")) <= datetime.now(UTC), "freeze_in_future")
    freeze_inputs(freeze, plan_sha)
    require(isolation.get("tool") == "swarm-isolation-preflight", "invalid_isolation_report")
    require(
        type(isolation.get("schema_version")) is int and isolation["schema_version"] == 1,
        "invalid_isolation_schema",
    )
    require(isolation.get("status") == "PASS", "isolation_unverified")
    isolation_report_checks(isolation)
    require(isolation.get("study_id") == study_id, "isolation_study_mismatch")
    identity = isolation.get("source_identity")
    require(isinstance(identity, dict), "isolation_identity_missing")
    require(identity.get("source_sha") == source_sha, "isolation_source_mismatch")
    require(timestamp(isolation.get("as_of")) <= datetime.now(UTC), "isolation_in_future")
    freeze_sha = digest(freeze_bytes)
    return {"freeze_sha256": freeze_sha, "isolation_sha256": digest(isolation_bytes)}


def plan_command(args: argparse.Namespace) -> dict[str, Any]:
    config, _payload = load_json(local_file(args.input))
    validate_config(config)
    plan = {
        "schema_version": 1,
        "kind": "assignment-plan",
        "config": config,
        "ordering_algorithm": ALGORITHM,
        "actor_budget": BUDGET,
        "owner": OWNER,
        "execution_allowed": False,
        "cells": assignment_cells(config),
    }
    output = local_file(args.output)
    with exclusive_lock(output):
        atomic_json(output, plan)
    return {"status": "PLANNED", "cells": BUDGET, "plan_sha256": digest(encoded(plan))}


def init_command(args: argparse.Namespace) -> dict[str, Any]:
    plan_path, output = local_file(args.input), local_file(args.output)
    require(plan_path != output, "plan_is_immutable_choose_ledger_path")
    receipt_path = plan_path.with_name(plan_path.name + ".initialized")
    require(output != receipt_path, "reserved_sidecar_path")
    with exclusive_lock(plan_path), exclusive_lock(output):
        plan, plan_bytes = load_json(plan_path)
        validate_plan(plan)
        require(plan_bytes == encoded(plan), "plan_requires_canonical_tool_output")
        plan_sha = digest(plan_bytes)
        require(bool(args.freeze) == bool(args.isolation), "both_gate_files_required")
        gates = None
        if args.freeze is not None:
            gates = gate_evidence(
                local_file(args.freeze),
                local_file(args.isolation),
                plan["config"]["source_sha"],
                plan_sha,
                plan["config"]["study_id"],
            )
        require(not output.exists(), "output_exists_no_overwrite")
        ledger = {
            "schema_version": 1,
            "kind": "assignment-ledger",
            "ledger_path": str(output),
            "plan": plan,
            "plan_sha256": plan_sha,
            "owner": OWNER,
            "revision": 0,
            "initialized_at": utc_now(),
            "gate_evidence": gates,
            "events": [],
            "cells": plan["cells"],
        }
        # Claim FIRST. A failed/crashed init is blocked, never a new budget.
        atomic_json(receipt_path, {"plan_sha256": plan_sha, "ledger_path": str(output)})
        atomic_json(output, ledger)
    return {"status": "INITIALIZED", "revision": 0, "cells": BUDGET}


def initial_cells(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {cell["cell_id"]: dict(cell) for cell in plan["cells"]}


def validate_event(event: dict[str, Any]) -> None:
    exact_keys(event, {"cell_id", "attempt_id", "status"}, {"failure_reason"})
    require(event["status"] in STATUSES[1:], "invalid_event_status")
    reason = event.get("failure_reason")
    if event["status"] in {"FAILED", "TIMEOUT", "BLOCKED"}:
        require(isinstance(reason, str) and reason in SAFE_REASONS, "safe_failure_reason_required")
    else:
        require("failure_reason" not in event, "unexpected_failure_reason")


def apply_event(cells: dict[str, dict[str, Any]], event: dict[str, Any]) -> None:
    cell_id = event["cell_id"]
    require(isinstance(cell_id, str) and cell_id in cells, "unknown_cell")
    cell = cells[cell_id]
    require(event["attempt_id"] == cell["attempt_id"], "attempt_id_mismatch")
    old, new = cell["status"], event["status"]
    require(old not in TERMINAL, "terminal_attempt_is_immutable")
    if old == "NOT_RUN":
        require(new in {"STARTED", "BLOCKED"}, "invalid_status_transition")
    else:
        require(old == "STARTED" and new in TERMINAL - {"BLOCKED"}, "invalid_status_transition")
    if new == "STARTED":
        require(not any(item["status"] == "STARTED" for item in cells.values()), "call_in_flight")
        remaining = [item for item in cells.values() if item["status"] == "NOT_RUN"]
        require(
            cell_id == min(remaining, key=lambda item: item["order_index"])["cell_id"],
            "out_of_order_start",
        )
    cell["status"] = new
    if new == "STARTED":
        cell["started_at"] = event["recorded_at"]
    else:
        cell["ended_at"] = event["recorded_at"]
    if "failure_reason" in event:
        cell["failure_reason"] = event["failure_reason"]


def replay_ledger(ledger: dict[str, Any], ledger_path: Path) -> dict[str, dict[str, Any]]:
    exact_keys(
        ledger,
        {
            "schema_version",
            "kind",
            "ledger_path",
            "plan",
            "plan_sha256",
            "owner",
            "revision",
            "initialized_at",
            "gate_evidence",
            "events",
            "cells",
        },
    )
    require(
        type(ledger["schema_version"]) is int
        and ledger["schema_version"] == 1
        and ledger["kind"] == "assignment-ledger",
        "invalid_ledger",
    )
    require(ledger["owner"] == OWNER, "invalid_ledger_owner")
    require(ledger["ledger_path"] == str(ledger_path), "ledger_copy_or_path_mismatch")
    validate_plan(ledger["plan"])
    require(digest(encoded(ledger["plan"])) == ledger["plan_sha256"], "invalid_plan_digest")
    if ledger["gate_evidence"] is not None:
        validate_gates(ledger["gate_evidence"])
    require(type(ledger["revision"]) is int and ledger["revision"] >= 0, "invalid_revision")
    events = ledger["events"]
    require(isinstance(events, list) and len(events) <= 2 * BUDGET, "invalid_event_count")
    require(ledger["revision"] == len(events), "revision_history_mismatch")
    previous = timestamp(ledger["initialized_at"])
    cells = initial_cells(ledger["plan"])
    for revision, event in enumerate(events, 1):
        replay_event(event, revision, ledger["gate_evidence"])
        current = timestamp(event["recorded_at"])
        require(previous <= current <= datetime.now(UTC), "nonmonotonic_event_time")
        apply_event(cells, event)
        previous = current
    require(encoded(ledger["cells"]) == encoded(list(cells.values())), "cell_history_mismatch")
    return cells


def validate_gates(gates: Any) -> None:
    exact_keys(gates, {"freeze_sha256", "isolation_sha256"})
    require(all(hex_value(value, 64) for value in gates.values()), "invalid_gate_digest")


def replay_event(event: Any, revision: int, gates: dict[str, Any] | None) -> None:
    exact_keys(
        event,
        {"cell_id", "attempt_id", "status", "revision", "recorded_at"},
        {"failure_reason", "gate_evidence"},
    )
    validate_event(
        {
            key: value
            for key, value in event.items()
            if key not in {"revision", "recorded_at", "gate_evidence"}
        }
    )
    require(
        type(event["revision"]) is int and event["revision"] == revision, "event_revision_mismatch"
    )
    if event["status"] == "STARTED":
        require(gates is not None, "started_without_frozen_evidence")
        require(event.get("gate_evidence") == gates, "event_gate_mismatch")
    else:
        require("gate_evidence" not in event, "unexpected_event_gate")


def record_command(args: argparse.Namespace) -> dict[str, Any]:
    source, output = local_file(args.input), local_file(args.output)
    require(source == output, "record_requires_same_input_output")
    event, _event_bytes = load_json(local_file(args.event))
    validate_event(event)
    with exclusive_lock(output):
        ledger, original = load_json(source)
        cells = replay_ledger(ledger, source)
        require(ledger["revision"] == args.expected_revision, "revision_conflict")
        if event["status"] == "STARTED":
            require(
                args.freeze is not None and args.isolation is not None,
                "fresh_gate_evidence_required",
            )
            gates = gate_evidence(
                local_file(args.freeze),
                local_file(args.isolation),
                ledger["plan"]["config"]["source_sha"],
                ledger["plan_sha256"],
                ledger["plan"]["config"]["study_id"],
            )
            if ledger["gate_evidence"] is None:
                ledger["gate_evidence"] = gates
            require(gates == ledger["gate_evidence"], "frozen_evidence_changed")
            event["gate_evidence"] = gates
        event["revision"] = ledger["revision"] + 1
        event["recorded_at"] = utc_now()
        previous = (
            ledger["events"][-1]["recorded_at"] if ledger["events"] else ledger["initialized_at"]
        )
        require(timestamp(event["recorded_at"]) >= timestamp(previous), "clock_moved_backwards")
        apply_event(cells, event)
        ledger["events"].append(event)
        ledger["revision"] = event["revision"]
        ledger["cells"] = list(cells.values())
        require(source.read_bytes() == original, "concurrent_ledger_change")
        atomic_json(output, ledger, replace=True)
    counts = Counter(cell["status"] for cell in ledger["cells"])
    return {
        "status": "RECORDED",
        "revision": ledger["revision"],
        "cell_id": event["cell_id"],
        "attempt_id": event["attempt_id"],
        "cell_status": event["status"],
        "status_counts": {status: counts[status] for status in STATUSES},
        "assigned": BUDGET,
        "attempted": sum(
            counts[status] for status in ("STARTED", "COMPLETED", "FAILED", "TIMEOUT")
        ),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = result.add_subparsers(dest="command", required=True)
    for name in ("plan", "init", "record"):
        command = commands.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        if name in {"init", "record"}:
            command.add_argument("--owner", choices=[OWNER], required=True)
            command.add_argument("--freeze", type=Path)
            command.add_argument("--isolation", type=Path)
        if name == "record":
            command.add_argument("--event", type=Path, required=True)
            command.add_argument("--expected-revision", type=int, required=True)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        handler = {"plan": plan_command, "init": init_command, "record": record_command}[
            args.command
        ]
        result = handler(args)
    except LedgerError as exc:
        print(json.dumps({"status": "REFUSED", "reason": str(exc)}), file=sys.stderr)
        return 2
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError):
        # No raw exception text, input snippets, authentication or host logs.
        print(
            json.dumps({"status": "REFUSED", "reason": "invalid_input_or_local_io"}),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
