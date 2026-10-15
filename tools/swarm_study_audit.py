#!/usr/bin/env python3
"""Audit the supplied public swarm study artifacts without running an experiment.

Python 3.12 standard library only. No sibling tool imports, network requests,
host access, authentication reads, prompt collection, or reasoning inspection.

Usage::

    python tools/swarm_study_audit.py --input request.json --output study-audit.json \
        --candidate-root /approved/candidate --candidate-sha <selected-sha> \
        --public-evidence-root /approved/public-study

The coordinator supplies candidate/evidence roots independently of the request.
Never construct these trusted CLI arguments from a received request. References
must stay in the approved public evidence root(s), with no traversal or linked
ancestors. The request itself must also be in an approved evidence root. Root
binding failure stops before artifact reads or source helpers. To check tracked
source cleanliness, the trusted caller may additionally provide --git-dir and
--git-common-dir. Without that independent metadata binding source stays UNKNOWN.
Source Git runs in a temporary configuration/index view, with no repository,
global or system config and no inherited Git/credential environment. Only fixed
/usr/bin/git is used; unavailable plumbing stays UNKNOWN. No user config changes.

Request (relative paths are based on request.json, within approved evidence)::

    {
      "schema_version": 1,
      "repository_root": "candidate-checkout",
      "freeze_manifest": "freeze-manifest.json",
      "assignment_ledger": "assignment-ledger.json",
      "safe_results": "safe-results.jsonl",
      "intake_review": "intake-review.jsonl",
      "isolation_preflight": "isolation-preflight.json",
      "required_input_paths": {
        "protocol": "evals/swarm-20261015/PROTOCOL.md",
        "cases": ["evals/swarm-20261015/cases.json"],
        "rubric": "evals/swarm-20261015/rubric.json",
        "assignments": "evals/swarm-20261015/assignment-plan.json"
      },
      "freeze_sha256": null,
      "protocol_policy": null,
      "adjudication_summary": null
    }

The freeze object and cell/result records use control/interfaces-v1.json.
Ledger envelopes may use ``cells`` or ``assignments``; a bare cell list is also
accepted. Results are JSONL, one result per cell, including failures/timeouts.
The immutable assignment plan must be frozen separately if the live ledger's
status fields are mutable. Frozen task/protocol/rubric/assignment files are
hashed in full; no historical experiment is imported as current evidence.

Optional protocol_policy is a *frozen repository-relative JSON file* containing
boolean ``require_known_model_identity`` and ``require_independent_judge``.
Without that extension the launch-v1 policy permits explicitly unknown backend
identity and unavailable independent judgment as limitations. A supplied policy
must be hash-bound to the freeze; an unbound policy cannot relax a gate.
Optional adjudication_summary uses ``independent_judge`` with ``available`` and
``independent`` booleans and a nonempty ``provenance`` string. These are reported
assertions, never authenticated human judgments.

S042's isolation report is consumed directly: tool swarm-isolation-preflight,
status PASS, isolation_blocked false, experiment_blocked true,
execution_authorized false,
source_identity.source_sha and as_of. A standalone VERIFIED assertion without
the structured S042 report leaves the isolation gate blocked.
The S043 event history and pinned gate digests are audited when supplied.
S044's separate manual-review, identity-reason and delivery records are supported.
S043 and S044 must agree on study:cell:a1 and run_id/study_id; no attempt label
is silently rewritten or accepted from the superseded draft label convention.
The separate intake_review JSONL contains S044 control records keyed by cell_id
and result_sha256; its digest binds each unchanged launch-v1 result to manual
review, run/attempt identity, delivery mode and null reasons. Result hashes use
UTF-8 json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True),
without a trailing LF. No sidecar fields are added to the supplied result file.

Output does not copy answer text, arbitrary supplied strings, local paths, or
raw exceptions. REPORTABLE means the supplied metadata passes these bounded
consistency gates, with explicit limitations; it does not certify application,
efficacy, complete disclosure, authenticity, or independence. HOLD means an
integrity/gating defect; UNKNOWN means missing evidence without a known defect.
Exit codes: 0 REPORTABLE, 1 HOLD, 2 UNKNOWN, 3 input/output error. No reruns occur.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

BUDGET = 54
FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
REPEATS = (1, 2, 3)
STATUSES = {"NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED"}
ATTEMPTED = {"STARTED", "COMPLETED", "FAILED", "TIMEOUT"}
TERMINAL_ATTEMPTED = {"COMPLETED", "FAILED", "TIMEOUT"}
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_RESULTS_BYTES = 64 * 1024 * 1024
MAX_RECORD_BYTES = 1024 * 1024
MAX_HASH_BYTES = 256 * 1024 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
IDENTITY_FIELDS = {
    "repository",
    "source_sha",
    "product_version",
    "content_revision",
    "host",
    "platform",
    "model_requested",
    "model_observed",
    "effort",
    "service_tier_requested",
    "service_tier_observed",
}
UNKNOWN_IDENTITY_FIELDS = {"model_observed", "service_tier_observed"}
REQUIRED_EXECUTION_IDENTITY = {
    "repository",
    "source_sha",
    "host",
    "platform",
    "model_requested",
    "effort",
    "service_tier_requested",
}
CORE_RESULT_FIELDS = {
    "cell_id",
    "status",
    "public_final_answer",
    "started_at",
    "ended_at",
    "elapsed_ms",
    "input_tokens",
    "output_tokens",
    "critical_error_labels",
    "task_complete",
    "entry_emitted",
    "canonical_full_read",
    "application_evidence",
    "failure_reason",
    "identity",
}
INTAKE_FIELDS = {
    "schema_version",
    "source_id",
    "run_id",
    "case_id",
    "locale",
    "manual_review",
    "delivery_mode",
    "independent_evaluation",
    "unknown_reasons",
    "attempt_id",
}
RESULT_FIELDS = CORE_RESULT_FIELDS | INTAKE_FIELDS
NULLABLE_RESULT_FIELDS = {
    "public_final_answer",
    "started_at",
    "ended_at",
    "elapsed_ms",
    "input_tokens",
    "output_tokens",
    "task_complete",
    "entry_emitted",
    "canonical_full_read",
    "failure_reason",
}
UNKNOWN_REASON_CODES = {
    "UNKNOWN",
    "UNAVAILABLE",
    "NOT_OBSERVED",
    "NOT_APPLICABLE",
    "NOT_RUN",
    "WITHHELD_PENDING_REVIEW",
}
FAILURE_REASONS = {
    "EXECUTION_FAILED",
    "TIMEOUT",
    "INTERRUPTED",
    "RESOURCE_BLOCKED",
    "ISOLATION_UNVERIFIED",
    "BUDGET_EXHAUSTED",
    "HOST_UNAVAILABLE",
    "OUTPUT_UNAVAILABLE",
    "PRIVACY_REVIEW_PENDING",
    "CANCELLED",
    "UNKNOWN",
    "call_failed",
    "deadline_exceeded",
    "interrupted_after_start",
    "call_outcome_unknown",
    "freeze_unavailable",
    "isolation_unverified",
    "resource_unavailable",
    "host_unavailable",
    "owner_stopped",
    "preflight_unavailable",
    "host_error",
    "timeout",
    "interrupted",
    "dispatch_uncertain",
    "answer_unavailable",
    "budget_exhausted",
    "other_safe_category",
}
FORBIDDEN_ARTIFACT_NAMES = {
    "auth.json",
    "credentials.json",
    "config.toml",
    "id_rsa",
    "id_ed25519",
    "keychain",
}
FREEZE_FIELDS = {
    "schema_version",
    "state",
    "draft",
    "frozen",
    "source_sha",
    "source_sha_evidence",
    "input",
    "input_files",
    "isolation_state",
    "isolation_evidence",
    "quota",
    "budget_contract",
    "frozen_at",
    "approved_by",
    "approval_preconditions",
    "approval",
    "identity",
    "unknown_reasons",
    "independent_evaluator",
    "independent_evaluator_reason",
    "native_installation_or_application_receipt",
    "evidence_boundary",
}
ISOLATION_FIELDS = {
    "schema_version",
    "tool",
    "status",
    "study_id",
    "snapshot_id",
    "as_of",
    "source_identity",
    "baseline",
    "identity_unknown_reasons",
    "isolation_blocked",
    "experiment_blocked",
    "execution_authorized",
    "final_study_freeze_and_lease_required",
    "evidence_level",
    "global_checks",
    "arms",
    "blocking_checks",
    "availability",
    "limits",
}
EXPECTED_CELLS = {
    f"{family}-{locale}-{arm}-r{repeat}": (f"{family}-{locale}", arm, repeat)
    for family in FAMILIES
    for locale in LOCALES
    for arm in ARMS
    for repeat in REPEATS
}


class InputError(ValueError):
    """A safe input category; never propagate arbitrary file content."""


@dataclass(frozen=True)
class TrustedContext:
    """Operator-selected public roots; never deserialize this from request JSON."""

    candidate_root: Path
    candidate_sha: str
    evidence_roots: tuple[Path, ...]
    git_dir: Path | None = None
    git_common_dir: Path | None = None


def trusted_context(
    candidate_root: Path,
    candidate_sha: str,
    evidence_roots: list[Path],
    git_dir: Path | None = None,
    git_common_dir: Path | None = None,
) -> TrustedContext:
    if not valid_commit(candidate_sha) or not evidence_roots:
        raise InputError("trusted_context_invalid")
    roots = tuple(approved_directory(path) for path in evidence_roots)
    metadata = tuple(
        approved_directory(path) if path is not None else None for path in (git_dir, git_common_dir)
    )
    return TrustedContext(approved_directory(candidate_root), candidate_sha, roots, *metadata)


def approved_directory(path: Path) -> Path:
    if not path.is_absolute():
        raise InputError("trusted_root_requires_absolute_path")
    canonical = path.resolve(strict=True)
    if not canonical.is_dir() or canonical == Path(canonical.anchor):
        raise InputError("trusted_root_invalid")
    return canonical


class Audit:
    def __init__(self) -> None:
        self.findings: dict[tuple[str, str], dict[str, Any]] = {}
        self.input_digests: dict[str, str] = {}
        self.summary: dict[str, Any] = {}

    def add(self, severity: str, code: str, cell_id: Any = None, count: int = 1) -> None:
        item = self.findings.setdefault(
            (severity, code), {"severity": severity, "code": code, "count": 0, "cells": []}
        )
        item["count"] += count
        if isinstance(cell_id, str) and cell_id in EXPECTED_CELLS and cell_id not in item["cells"]:
            item["cells"].append(cell_id)

    def report(self) -> dict[str, Any]:
        severities = {severity for severity, _ in self.findings}
        state = "REPORTABLE"
        if "blocker" in severities:
            state = "HOLD"
        elif "unknown" in severities:
            state = "UNKNOWN"
        return {
            "schema_version": 1,
            "artifact": "study-audit",
            "reportability": state,
            "execution_authorized": False,
            "audit_scope": "supplied_public_artifacts_and_local_candidate_only",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.summary,
            # A rejected audit never publishes a fingerprint of supplied bytes.
            "input_digests": {} if "blocker" in severities else self.input_digests,
            "digests_omitted_on_hold": "blocker" in severities,
            "findings": sorted(
                self.findings.values(), key=lambda item: (item["severity"], item["code"])
            ),
            "claims": {
                "native_application_certified": False,
                "private_reasoning_inspected": False,
                "efficacy_certified": False,
                "manifest_authorship_authenticated": False,
                "undisclosed_calls_detectable": False,
                "historical_experiments_promoted": False,
            },
        }


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate_json_key")
        result[key] = value
    return result


def decode_json(data: bytes) -> Any:
    try:
        return json.loads(
            data,
            object_pairs_hook=no_duplicate_keys,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (UnicodeError, ValueError, RecursionError) as error:
        raise InputError("invalid_json") from error


def reject_constant(_value: str) -> None:
    raise InputError("nonfinite_json_number")


def finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise InputError("nonfinite_json_number")
    return number


def status_of(row: dict[str, Any]) -> str | None:
    value = row.get("status")
    return value if isinstance(value, str) else None


def read_bytes(path: Path, limit: int) -> bytes:
    with os.fdopen(open_without_links(path), "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise InputError("not_a_regular_single_link_file")
        data = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    if len(data) > limit:
        raise InputError("input_size_limit")
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise InputError("input_changed_during_read")
    return data


def open_without_links(path: Path) -> int:
    """Walk directory descriptors without following any ancestor or final link."""
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise InputError("safe_local_open_unavailable")
    absolute = Path(os.path.abspath(path))
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(absolute.anchor, directory_flags)
    try:
        for part in absolute.parts[1:-1]:
            child = os.open(part, directory_flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
        return os.open(absolute.name, flags, dir_fd=descriptor)
    finally:
        os.close(descriptor)


def lexical_path(base: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise InputError("invalid_artifact_path")
    path = Path(value)
    if any(part == ".." for part in path.parts):
        raise InputError("path_traversal_refused")
    return Path(os.path.abspath(path if path.is_absolute() else base / path))


def artifact_path(base: Path, value: Any, context: TrustedContext | None = None) -> Path:
    if context is None:
        raise InputError("trusted_evidence_context_missing")
    path = lexical_path(base, value)
    for root in context.evidence_roots:
        if path.is_relative_to(root):
            return confined_path(root, path)
    raise InputError("artifact_outside_approved_public_evidence")


def confined_path(root: Path, path: Path) -> Path:
    if root.is_symlink() or not root.is_dir() or not path.is_relative_to(root):
        raise InputError("path_outside_approved_root")
    cursor = root
    for part in path.relative_to(root).parts:
        if part.startswith(".") or part.lower() in FORBIDDEN_ARTIFACT_NAMES:
            raise InputError("nonpublic_artifact_path_refused")
        cursor = cursor / part
        if cursor.is_symlink():
            raise InputError("linked_path_refused")
    return path


def closed_object(value: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not required <= value.keys() <= allowed:
        raise InputError("wrong_artifact_role_schema")
    return value


def validate_role(key: str, value: Any) -> None:
    validators = {
        "freeze_manifest": validate_freeze_role,
        "assignment_ledger": validate_ledger_role,
        "isolation_preflight": validate_isolation_role,
        "adjudication_summary": validate_judge_role,
    }
    if key not in validators:
        raise InputError("unknown_artifact_role")
    validators[key](value)


def validate_freeze_role(value: Any) -> None:
    required = {
        "state",
        "source_sha",
        "input_files",
        "isolation_state",
        "quota",
        "frozen_at",
        "approved_by",
    }
    data = closed_object(value, FREEZE_FIELDS, required)
    if not valid_commit(data["source_sha"]) or type(data["quota"]) is not int:
        raise InputError("wrong_freeze_role_schema")
    files = data["input_files"]
    if not isinstance(files, list) or not files or len(files) > 512:
        raise InputError("wrong_freeze_inventory_schema")
    for entry in files:
        row = closed_object(entry, {"path", "sha256", "role", "bytes"}, {"path", "sha256"})
        repository_relative_name(row["path"])
        if not isinstance(row["sha256"], str) or not SHA256.fullmatch(row["sha256"]):
            raise InputError("wrong_freeze_inventory_schema")
    if data.get("identity") is not None:
        validate_public_identity(data["identity"])
    for field, keys in (
        ("input", {"path", "sha256"}),
        ("approval", {"path", "sha256", "evidence"}),
    ):
        if data.get(field) is not None:
            closed_object(data[field], keys, keys)


def validate_cells_role(cells: Any) -> None:
    allowed = {
        "cell_id",
        "case_id",
        "family",
        "locale",
        "arm",
        "repeat",
        "assignment_seed",
        "attempt_id",
        "status",
        "order_index",
        "failure_reason",
    }
    required = {"cell_id", "case_id", "arm", "repeat", "status", "order_index"}
    if not isinstance(cells, list) or len(cells) > 10000:
        raise InputError("wrong_cells_role_schema")
    for cell in cells:
        data = closed_object(cell, allowed, required)
        if not isinstance(data["cell_id"], str) or status_of(data) not in STATUSES:
            raise InputError("wrong_cells_role_schema")
        for field in ("case_id", "arm", "family", "locale", "attempt_id"):
            if field in data and not isinstance(data[field], str):
                raise InputError("wrong_cells_role_schema")
        for field in ("repeat", "order_index", "assignment_seed"):
            if field in data and type(data[field]) is not int:
                raise InputError("wrong_cells_role_schema")
        if data.get("failure_reason") is not None and not safe_failure(data["failure_reason"]):
            raise InputError("wrong_cells_role_schema")


def validate_ledger_role(value: Any) -> None:
    if isinstance(value, list):
        validate_cells_role(value)
        return
    allowed = {
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
        "assignments",
    }
    data = closed_object(value, allowed, set())
    validate_cells_role(data.get("cells", data.get("assignments")))
    if "plan" in data:
        plan = closed_object(
            data["plan"],
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
            {"cells", "config"},
        )
        closed_object(
            plan["config"],
            {"study_id", "source_sha", "assignment_seed"},
            {"study_id", "source_sha", "assignment_seed"},
        )
        validate_cells_role(plan["cells"])
    if "events" in data:
        validate_event_role(data["events"])
    if data.get("gate_evidence") is not None:
        validate_gate_role(data["gate_evidence"])


def validate_gate_role(value: Any) -> None:
    data = closed_object(
        value, {"freeze_sha256", "isolation_sha256"}, {"freeze_sha256", "isolation_sha256"}
    )
    if any(not isinstance(item, str) or not SHA256.fullmatch(item) for item in data.values()):
        raise InputError("wrong_gate_role_schema")


def validate_event_role(events: Any) -> None:
    if not isinstance(events, list) or len(events) > 10000:
        raise InputError("wrong_events_role_schema")
    for event in events:
        data = closed_object(
            event,
            {
                "cell_id",
                "attempt_id",
                "status",
                "revision",
                "recorded_at",
                "failure_reason",
                "gate_evidence",
            },
            {"cell_id", "attempt_id", "status", "revision", "recorded_at"},
        )
        if data.get("gate_evidence") is not None:
            validate_gate_role(data["gate_evidence"])


def validate_isolation_role(value: Any) -> None:
    data = closed_object(
        value,
        ISOLATION_FIELDS,
        {
            "tool",
            "status",
            "source_identity",
            "as_of",
            "isolation_blocked",
            "experiment_blocked",
            "execution_authorized",
        },
    )
    if data["tool"] != "swarm-isolation-preflight" or data["status"] not in (
        "PASS",
        "FAIL",
        "UNKNOWN",
    ):
        raise InputError("wrong_isolation_role_schema")
    validate_public_identity(data["source_identity"])
    for field in ("isolation_blocked", "experiment_blocked", "execution_authorized"):
        if type(data[field]) is not bool:
            raise InputError("wrong_isolation_role_schema")
    validate_isolation_rows(data.get("global_checks", []))
    validate_isolation_rows(data.get("blocking_checks", []), blocking=True)
    arms = data.get("arms", [])
    if not isinstance(arms, list):
        raise InputError("wrong_isolation_role_schema")
    for arm in arms:
        fields = {
            "arm",
            "status",
            "checks",
            "declarations_used_as_evidence",
            "installation_is_application_proof",
            "application_evidence",
        }
        item = closed_object(arm, fields, {"arm", "status", "checks"})
        validate_isolation_rows(item["checks"])


def validate_isolation_rows(value: Any, blocking: bool = False) -> None:
    if not isinstance(value, list):
        raise InputError("wrong_isolation_role_schema")
    fields = {"check", "status", "reason", "evidence_ids"}
    allowed = fields | {"arm"} if blocking else fields
    for item in value:
        row = closed_object(item, allowed, {"check", "status", "reason"})
        if any(not isinstance(row[field], str) for field in ("check", "status", "reason")):
            raise InputError("wrong_isolation_role_schema")
        evidence = row.get("evidence_ids", [])
        if not isinstance(evidence, list) or any(not isinstance(label, str) for label in evidence):
            raise InputError("wrong_isolation_role_schema")


def validate_judge_role(value: Any) -> None:
    data = closed_object(value, {"schema_version", "independent_judge"}, {"independent_judge"})
    closed_object(
        data["independent_judge"], {"available", "independent", "provenance"}, {"available"}
    )


def validate_public_identity(value: Any) -> None:
    data = closed_object(value, IDENTITY_FIELDS, IDENTITY_FIELDS)
    for field, item in data.items():
        if item is not None and not isinstance(item, str):
            raise InputError("wrong_identity_role_schema")
        if isinstance(item, str) and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 ._+():/-]{0,127}", item
        ):
            raise InputError("wrong_identity_role_schema")
        if field == "source_sha" and item is not None and not valid_commit(item):
            raise InputError("wrong_identity_role_schema")


def bind_candidate(request: dict[str, Any], base: Path, context: TrustedContext) -> Path:
    path = lexical_path(base, request.get("repository_root"))
    if path != context.candidate_root:
        raise InputError("candidate_root_not_independently_approved")
    return context.candidate_root


def repo_path(root: Path, value: Any) -> Path:
    relative = repository_relative_name(value)
    path = root / value
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise InputError("repository_path_escape")
    return path


def repository_relative_name(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise InputError("invalid_repository_path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or PureWindowsPath(value).is_absolute():
        raise InputError("invalid_repository_path")
    if any(part in {"", ".", "..", ".git"} for part in value.split("/")):
        raise InputError("invalid_repository_path")
    check_study_prefix(value)
    return relative


def check_study_prefix(value: str) -> None:
    allowed = value.startswith(("evals/swarm-20261015/", "build/", "dist/"))
    if not allowed and not (value.startswith("tools/swarm_") and value.endswith(".py")):
        raise InputError("outside_explicit_study_package_or_driver_roots")


def timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.utcoffset() is not None else None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    """Hash only an explicitly frozen file; package bytes are never retained."""
    with os.fdopen(open_without_links(path), "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise InputError("not_a_regular_single_link_file")
        hasher = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            if size > MAX_HASH_BYTES:
                raise InputError("input_size_limit")
            hasher.update(chunk)
        after = os.fstat(handle.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise InputError("input_changed_during_read")
    return hasher.hexdigest()


def load_artifact(
    audit: Audit,
    request: dict[str, Any],
    base: Path,
    key: str,
    required: bool = True,
    context: TrustedContext | None = None,
) -> Any:
    if request.get(key) is None and not required:
        return None
    try:
        raw = read_bytes(artifact_path(base, request.get(key), context), MAX_DOCUMENT_BYTES)
        value = decode_json(raw)
        validate_role(key, value)
        audit.input_digests[key] = digest(raw)
        return value
    except InputError:
        audit.input_digests.pop(key, None)
        audit.add("blocker", f"{key}_rejected")
        return None
    except OSError:
        audit.add("unknown", f"{key}_unavailable_or_invalid")
        return None


def check_freeze(audit: Audit, freeze: Any, request: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(freeze, dict):
        audit.add("blocker", "freeze_missing")
        return {}
    check_freeze_fields(audit, freeze)
    check_freeze_pin(audit, request.get("freeze_sha256"))
    if any(severity == "blocker" for severity, _ in audit.findings):
        audit.input_digests.pop("freeze_manifest", None)
        return {}
    audit.summary["frozen_source_sha"] = (
        freeze.get("source_sha") if valid_commit(freeze.get("source_sha")) else None
    )
    return freeze


def valid_commit(value: Any) -> bool:
    return isinstance(value, str) and COMMIT.fullmatch(value) is not None


def check_freeze_fields(audit: Audit, freeze: dict[str, Any]) -> None:
    checks = (
        (freeze.get("state") == "FROZEN", "freeze_not_frozen"),
        (valid_commit(freeze.get("source_sha")), "freeze_source_identity_missing"),
        (type(freeze.get("quota")) is int and freeze["quota"] == BUDGET, "freeze_quota_not_54"),
        (timestamp(freeze.get("frozen_at")) is not None, "freeze_timestamp_missing_or_invalid"),
        (freeze.get("approved_by") == "S001", "freeze_selection_owner_unconfirmed"),
    )
    for passed, category in checks:
        if not passed:
            audit.add("blocker", category)
    frozen_at = timestamp(freeze.get("frozen_at"))
    if frozen_at is not None and frozen_at > datetime.now(timezone.utc):
        audit.add("blocker", "freeze_timestamp_in_future")


def check_freeze_pin(audit: Audit, pin: Any) -> None:
    if pin is None:
        audit.add("limitation", "freeze_digest_not_externally_pinned")
    elif not isinstance(pin, str) or not SHA256.fullmatch(pin):
        audit.add("blocker", "freeze_digest_pin_invalid")
    elif pin != audit.input_digests.get("freeze_manifest"):
        audit.add("blocker", "freeze_manifest_digest_changed")


def check_inventory(audit: Audit, freeze: dict[str, Any], root: Path) -> set[str]:
    files = freeze.get("input_files")
    if not isinstance(files, list) or not files or len(files) > 512:
        audit.add("blocker", "frozen_input_inventory_missing_or_unbounded")
        return set()
    inventory: set[str] = set()
    matched: set[str] = set()
    for entry in files:
        name = check_inventory_entry(audit, root, entry, inventory)
        if name is not None:
            matched.add(name)
    audit.summary["frozen_inputs"] = {"declared": len(files), "matched": len(matched)}
    return matched


def check_inventory_entry(audit: Audit, root: Path, entry: Any, seen: set[str]) -> str | None:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        audit.add("blocker", "frozen_input_entry_invalid")
        return None
    name = entry["path"]
    if name in seen:
        audit.add("blocker", "frozen_input_duplicate_path")
    seen.add(name)
    expected = entry.get("sha256")
    if not isinstance(expected, str) or not SHA256.fullmatch(expected):
        audit.add("blocker", "frozen_input_digest_invalid")
        return None
    try:
        actual = file_digest(repo_path(root, name))
    except (OSError, InputError):
        audit.add("blocker", "frozen_input_unavailable_or_unsafe")
        return None
    if actual != expected:
        audit.add("blocker", "post_freeze_input_hash_drift")
        return None
    return name


def input_roles(request: dict[str, Any], freeze: dict[str, Any]) -> dict[str, Any]:
    explicit = request.get("required_input_paths")
    if isinstance(explicit, dict):
        return explicit
    roles: dict[str, Any] = {}
    aliases = {
        "protocol": "protocol",
        "fixture": "cases",
        "rubric": "rubric",
        "assignment": "assignments",
    }
    files = freeze.get("input_files")
    for entry in files if isinstance(files, list) else []:
        if (
            isinstance(entry, dict)
            and isinstance(entry.get("role"), str)
            and entry["role"] in aliases
        ):
            roles.setdefault(aliases[entry["role"]], []).append(entry.get("path"))
    return roles


def check_required_inputs(audit: Audit, roles: dict[str, Any], matched: set[str]) -> None:
    if not isinstance(roles, dict):
        audit.add("unknown", "required_input_role_mapping_missing")
        return
    for role in ("protocol", "cases", "rubric", "assignments"):
        paths = roles.get(role)
        if isinstance(paths, str):
            paths = [paths]
        if not isinstance(paths, list) or not paths:
            audit.add("unknown", f"required_{role}_mapping_missing")
        elif any(not isinstance(path, str) or path not in matched for path in paths):
            audit.add("blocker", f"required_{role}_not_frozen_or_changed")


def frozen_assignments(
    audit: Audit, root: Path, roles: dict[str, Any], matched: set[str], source_sha: Any
) -> tuple[dict[str, dict[str, Any]], str | None]:
    paths = roles.get("assignments", [])
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list) or len(paths) != 1:
        audit.add("unknown", "one_immutable_assignment_plan_required")
        return {}, None
    name = paths[0]
    if not isinstance(name, str) or name not in matched:
        return {}, None
    try:
        raw = read_bytes(repo_path(root, name), MAX_DOCUMENT_BYTES)
        plan = decode_json(raw)
        cells = ledger_cells(audit, plan)
        audit.input_digests["assignment_plan"] = digest(raw)
        return check_ledger(audit, cells), assignment_study_id(audit, plan, source_sha)
    except (OSError, InputError):
        audit.add("blocker", "frozen_assignment_plan_unreadable")
        return {}, None


def assignment_study_id(audit: Audit, plan: Any, source_sha: Any) -> str | None:
    config = plan.get("config", {}) if isinstance(plan, dict) else {}
    if not isinstance(config, dict) or config.get("source_sha") != source_sha:
        audit.add("blocker", "assignment_plan_source_mismatch_or_missing")
        return None
    study_id = config.get("study_id")
    return study_id if isinstance(study_id, str) else None


def bind_plan(
    audit: Audit,
    ledger: Any,
    by_id: dict[str, dict[str, Any]],
    frozen_cells: dict[str, dict[str, Any]],
) -> None:
    immutable = ("case_id", "arm", "repeat", "order_index", "assignment_seed", "attempt_id")
    for cell_id, expected in frozen_cells.items():
        actual = by_id.get(cell_id, {})
        if any(actual.get(key) != expected.get(key) for key in immutable):
            audit.add("blocker", "post_freeze_assignment_plan_drift", cell_id)
    if not isinstance(ledger, dict):
        audit.add("unknown", "ledger_event_provenance_unavailable")
        return
    declared = ledger.get("plan_sha256")
    if declared is not None and declared != audit.input_digests.get("assignment_plan"):
        audit.add("blocker", "ledger_plan_digest_mismatch")
    embedded = ledger.get("plan")
    if embedded is not None:
        encoded = (
            json.dumps(embedded, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        if digest(encoded) != declared:
            audit.add("blocker", "ledger_embedded_plan_digest_mismatch")


def check_event_gate(audit: Audit, event: dict[str, Any], ledger_gate: Any) -> None:
    if event.get("gate_evidence") != ledger_gate:
        audit.add("blocker", "event_frozen_gate_digest_changed", event.get("cell_id"))
    if not isinstance(ledger_gate, dict):
        audit.add("blocker", "attempt_frozen_gate_provenance_missing")
        return
    for key, artifact in (
        ("freeze_sha256", "freeze_manifest"),
        ("isolation_sha256", "isolation_preflight"),
    ):
        if ledger_gate.get(key) != audit.input_digests.get(artifact):
            audit.add("blocker", f"attempt_{key}_mismatch")


def event_transition(
    audit: Audit,
    event: dict[str, Any],
    states: dict[str, str],
    frozen_cells: dict[str, dict[str, Any]],
) -> None:
    cell_id = event.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in frozen_cells:
        audit.add("blocker", "event_outside_frozen_assignment")
        return
    if event.get("attempt_id") != frozen_cells[cell_id].get("attempt_id"):
        audit.add("blocker", "event_attempt_identity_changed", cell_id)
    old, new = states.get(cell_id, "NOT_RUN"), status_of(event)
    if not valid_transition(old, new):
        audit.add("blocker", "duplicate_or_invalid_attempt_transition", cell_id)
    if new == "STARTED" and "STARTED" in states.values():
        audit.add("blocker", "central_ledger_parallel_call_overlap", cell_id)
    if new == "STARTED":
        check_event_order(audit, cell_id, states, frozen_cells)
    if new is not None:
        states[cell_id] = new


def valid_transition(old: str, new: str | None) -> bool:
    return (old == "NOT_RUN" and new in {"STARTED", "BLOCKED"}) or (
        old == "STARTED" and new in TERMINAL_ATTEMPTED
    )


def check_event_order(
    audit: Audit, cell_id: str, states: dict[str, str], frozen_cells: dict[str, dict[str, Any]]
) -> None:
    remaining = [key for key, state in states.items() if state == "NOT_RUN"]
    ordered = [key for key in remaining if type(frozen_cells[key].get("order_index")) is int]
    if ordered and min(ordered, key=lambda key: frozen_cells[key]["order_index"]) != cell_id:
        audit.add("blocker", "post_freeze_execution_order_changed", cell_id)


def event_time(
    audit: Audit,
    event: dict[str, Any],
    previous: datetime | None,
    frozen_at: datetime | None,
    isolated_at: datetime | None,
) -> datetime | None:
    current = timestamp(event.get("recorded_at"))
    if current is None:
        audit.add("blocker", "event_timestamp_provenance_missing")
        return previous
    if previous is not None and current < previous:
        audit.add("blocker", "ledger_event_time_order_invalid")
    if current > datetime.now(timezone.utc):
        audit.add("blocker", "ledger_event_timestamp_in_future")
    if status_of(event) == "STARTED":
        if frozen_at is not None and current < frozen_at:
            audit.add("blocker", "ledger_attempt_precedes_freeze")
        if isolated_at is not None and current < isolated_at:
            audit.add("blocker", "ledger_attempt_precedes_isolation")
    return current


def check_event_history(
    audit: Audit,
    ledger: Any,
    by_id: dict[str, dict[str, Any]],
    frozen_cells: dict[str, dict[str, Any]],
    freeze: dict[str, Any],
    isolated_at: datetime | None,
) -> int:
    events = ledger.get("events") if isinstance(ledger, dict) else None
    if not isinstance(events, list) or len(events) > 10000:
        audit.add("unknown", "ledger_event_provenance_unavailable")
        return 0
    check_ledger_header(audit, ledger, len(events))
    states: dict[str, str] = {cell_id: "NOT_RUN" for cell_id in frozen_cells}
    previous = timestamp(ledger.get("initialized_at"))
    starts = 0
    for revision, event in enumerate(events, 1):
        starts += check_event_record(audit, event, revision, states, frozen_cells, ledger)
        if isinstance(event, dict):
            previous = event_time(
                audit, event, previous, timestamp(freeze.get("frozen_at")), isolated_at
            )
    check_history_states(audit, by_id, states)
    if starts > BUDGET:
        audit.add("blocker", "actor_budget_exceeded")
    audit.summary["ledger_started_events"] = starts
    return starts


def check_ledger_header(audit: Audit, ledger: dict[str, Any], event_count: int) -> None:
    if type(ledger.get("revision")) is not int or ledger["revision"] != event_count:
        audit.add("blocker", "ledger_revision_history_disagreement")
    if ledger.get("owner") != "S078":
        audit.add("blocker", "ledger_execution_owner_not_s078")


def check_event_record(
    audit: Audit,
    event: Any,
    revision: int,
    states: dict[str, str],
    frozen_cells: dict[str, dict[str, Any]],
    ledger: dict[str, Any],
) -> int:
    if not isinstance(event, dict):
        audit.add("blocker", "ledger_event_invalid")
        return 0
    if type(event.get("revision")) is not int or event["revision"] != revision:
        audit.add("blocker", "ledger_event_revision_invalid")
    event_transition(audit, event, states, frozen_cells)
    if status_of(event) == "STARTED":
        check_event_gate(audit, event, ledger.get("gate_evidence"))
        return 1
    return 0


def check_history_states(
    audit: Audit, by_id: dict[str, dict[str, Any]], states: dict[str, str]
) -> None:
    for cell_id, final_state in states.items():
        if cell_id in by_id and status_of(by_id[cell_id]) != final_state:
            audit.add("blocker", "ledger_current_state_disagrees_with_history", cell_id)


def check_source(
    audit: Audit, freeze: dict[str, Any], root: Path, context: TrustedContext | None = None
) -> None:
    if context is None or root != context.candidate_root:
        audit.add("unknown", "source_context_not_independently_bound")
        return
    if freeze.get("state") != "FROZEN" or freeze.get("source_sha") != context.candidate_sha:
        audit.add("blocker", "source_not_bound_to_selected_frozen_candidate")
        return
    try:
        validate_git_binding(context)
        sha = metadata_head(context)
        if sha != context.candidate_sha:
            audit.add("blocker", "post_freeze_source_commit_drift")
            return
        dirty = isolated_source_diff(context, sha)
        if metadata_head(context) != sha:
            raise InputError("source_identity_changed_during_audit")
        audit.summary["audited_source_sha"] = sha
        if dirty == 1:
            audit.add("blocker", "post_freeze_tracked_source_worktree_drift")
        elif dirty != 0:
            audit.add("unknown", "tracked_source_cleanliness_unavailable")
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        audit.add("unknown", "local_source_identity_unavailable")


def metadata_file(root: Path, name: str) -> Path:
    """Only fixed public Git metadata names under independently approved roots."""
    path = root / name
    cursor = root
    for part in Path(name).parts:
        if part in {".", ".."}:
            raise InputError("metadata_path_invalid")
        cursor = cursor / part
        if cursor.is_symlink():
            raise InputError("linked_metadata_refused")
    return path


def validate_git_binding(context: TrustedContext) -> None:
    git_dir, common = context.git_dir, context.git_common_dir
    if git_dir is None or common is None:
        raise InputError("trusted_git_metadata_context_missing")
    marker = context.candidate_root / ".git"
    if marker.is_symlink():
        raise InputError("linked_metadata_refused")
    if marker.is_dir():
        if marker != git_dir or git_dir != common:
            raise InputError("git_metadata_binding_mismatch")
    else:
        validate_worktree_marker(context, marker)
    objects = metadata_file(common, "objects")
    if not objects.is_dir():
        raise InputError("git_objects_unavailable")
    alternate = metadata_file(objects, "info/alternates")
    if alternate.exists():
        raise InputError("external_object_alternates_not_supported")
    validate_object_store(objects)


def validate_object_store(objects: Path) -> None:
    """Refuse object links/foreign inode aliases before fixed Git reads them."""
    count = 0
    for directory, directories, files in os.walk(
        objects, followlinks=False, onerror=object_walk_error
    ):
        for name in directories + files:
            count += 1
            if count > 50000:
                raise InputError("object_metadata_inventory_limit")
            info = (Path(directory) / name).lstat()
            if not stat.S_ISDIR(info.st_mode) and not stat.S_ISREG(info.st_mode):
                raise InputError("linked_or_special_object_metadata_refused")
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise InputError("linked_or_special_object_metadata_refused")


def object_walk_error(_error: OSError) -> None:
    raise InputError("object_metadata_unavailable")


def validate_worktree_marker(context: TrustedContext, marker: Path) -> None:
    line = read_bytes(marker, 4096).decode("utf-8").strip()
    if not line.startswith("gitdir: "):
        raise InputError("git_metadata_binding_mismatch")
    named = Path(os.path.abspath(context.candidate_root / line[8:]))
    if named != context.git_dir:
        raise InputError("git_metadata_binding_mismatch")
    git_dir = context.git_dir
    if git_dir is None:
        raise InputError("trusted_git_metadata_context_missing")
    back = read_bytes(metadata_file(git_dir, "gitdir"), 4096).decode("utf-8").strip()
    common = read_bytes(metadata_file(git_dir, "commondir"), 4096).decode("utf-8").strip()
    if Path(os.path.abspath(git_dir / back)) != marker:
        raise InputError("git_metadata_binding_mismatch")
    if Path(os.path.abspath(git_dir / common)) != context.git_common_dir:
        raise InputError("git_metadata_binding_mismatch")


def metadata_head(context: TrustedContext) -> str:
    if context.git_dir is None or context.git_common_dir is None:
        raise InputError("trusted_git_metadata_context_missing")
    head = read_bytes(metadata_file(context.git_dir, "HEAD"), 4096).decode("ascii").strip()
    if valid_commit(head):
        return head
    if not head.startswith("ref: refs/heads/"):
        raise InputError("unsupported_head_reference")
    ref = head[5:]
    if not re.fullmatch(r"refs/heads/[A-Za-z0-9_./-]+", ref) or ".." in ref:
        raise InputError("unsupported_head_reference")
    loose = metadata_file(context.git_common_dir, ref)
    if loose.exists():
        value = read_bytes(loose, 4096).decode("ascii").strip()
    else:
        value = packed_head(context.git_common_dir, ref)
    if not valid_commit(value):
        raise InputError("source_identity_unavailable")
    return value


def packed_head(common: Path, ref: str) -> str:
    lines = (
        read_bytes(metadata_file(common, "packed-refs"), MAX_DOCUMENT_BYTES)
        .decode("ascii")
        .splitlines()
    )
    matches = [fields[0] for line in lines if len(fields := line.split()) == 2 and fields[1] == ref]
    if len(matches) != 1:
        raise InputError("source_identity_unavailable")
    return matches[0]


def source_git_environment(objects: Path) -> dict[str, str]:
    # No inherited GIT_CONFIG_*, GIT_DIR, trace, askpass, SSH, credentials or PATH.
    return {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_COUNT": "0",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_PROTOCOL_FROM_USER": "0",
        "GIT_OBJECT_DIRECTORY": str(objects),
        "GIT_ALTERNATE_OBJECT_DIRECTORIES": "",
    }


def isolated_source_diff(context: TrustedContext, sha: str) -> int:
    """No candidate config/worktree config/hooks/global config enters this view."""
    if context.git_dir is None or context.git_common_dir is None:
        raise InputError("trusted_git_metadata_context_missing")
    original_index = metadata_file(context.git_dir, "index")
    index = read_bytes(original_index, MAX_DOCUMENT_BYTES)
    if not index.startswith(b"DIRC"):
        raise InputError("unsupported_source_index")
    with tempfile.TemporaryDirectory(prefix="study-audit-git-") as temporary:
        scratch = Path(temporary)
        (scratch / "objects").mkdir()
        (scratch / "refs").mkdir()
        (scratch / "HEAD").write_text(sha + "\n", encoding="ascii")
        (scratch / "index").write_bytes(index)
        (scratch / "config").write_text(
            "[core]\nrepositoryformatversion = 0\nbare = false\nfsmonitor = false\n"
            f"hooksPath = {os.devnull}\nattributesFile = {os.devnull}\nautocrlf = false\n",
            encoding="ascii",
        )
        code = run_source_diff(context, scratch)
        if read_bytes(original_index, MAX_DOCUMENT_BYTES) != index:
            raise InputError("source_index_changed_during_audit")
        return code


def run_source_diff(context: TrustedContext, scratch: Path) -> int:
    if context.git_common_dir is None:
        raise InputError("trusted_git_metadata_context_missing")
    result = subprocess.run(
        [
            "/usr/bin/git",
            "--no-optional-locks",
            "--no-pager",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            f"--git-dir={scratch}",
            f"--work-tree={context.candidate_root}",
            "diff",
            "--quiet",
            "--no-ext-diff",
            "--no-textconv",
            "--ignore-submodules=all",
            "HEAD",
            "--",
        ],
        cwd=scratch,
        env=source_git_environment(context.git_common_dir / "objects"),
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    )
    return result.returncode


def load_policy(
    audit: Audit, request: dict[str, Any], root: Path, matched: set[str]
) -> dict[str, bool]:
    policy = {"require_known_model_identity": False, "require_independent_judge": False}
    name = request.get("protocol_policy")
    if name is None:
        audit.add("limitation", "launch_v1_policy_no_stricter_machine_readable_policy")
        return policy
    if not isinstance(name, str) or name not in matched:
        audit.add("blocker", "protocol_policy_not_frozen_or_changed")
        return policy
    try:
        data = decode_json(read_bytes(repo_path(root, name), MAX_DOCUMENT_BYTES))
        if not isinstance(data, dict) or any(type(data.get(key)) is not bool for key in policy):
            raise InputError("invalid_protocol_policy")
        return {key: data[key] for key in policy}
    except (OSError, InputError):
        audit.add("blocker", "protocol_policy_invalid")
        return policy


def check_isolation(audit: Audit, freeze: dict[str, Any], isolation: Any) -> datetime | None:
    if freeze.get("isolation_state") != "VERIFIED":
        audit.add("blocker", "freeze_isolation_unverified")
    if not isinstance(isolation, dict):
        audit.add("blocker", "isolation_evidence_missing")
        return None
    if isolation.get("tool") == "swarm-isolation-preflight":
        return check_s042_isolation(audit, freeze, isolation)
    audit.add("blocker", "isolation_report_format_unrecognized")
    return None


def check_s042_isolation(
    audit: Audit, freeze: dict[str, Any], isolation: dict[str, Any]
) -> datetime | None:
    if isolation.get("status") != "PASS" or isolation.get("isolation_blocked") is not False:
        audit.add("blocker", "isolation_preflight_not_verified")
    if (
        isolation.get("execution_authorized") is not False
        or isolation.get("experiment_blocked") is not True
    ):
        audit.add("blocker", "isolation_report_misstates_execution_authority")
    if isolation.get("final_study_freeze_and_lease_required", True) is not True:
        audit.add("blocker", "isolation_report_misstates_execution_authority")
    identity = isolation.get("source_identity")
    if not isinstance(identity, dict) or identity.get("source_sha") != freeze.get("source_sha"):
        audit.add("blocker", "isolation_source_mismatch_or_missing")
    verified = timestamp(isolation.get("as_of"))
    if verified is None:
        audit.add("blocker", "isolation_verification_time_missing")
    check_isolation_details(audit, isolation)
    audit.add("limitation", "isolation_report_is_summary_consistency_not_independent_attestation")
    return verified


def check_isolation_details(audit: Audit, isolation: dict[str, Any]) -> None:
    arms = isolation.get("arms")
    global_checks = isolation.get("global_checks")
    if not isinstance(arms, list) or not isinstance(global_checks, list) or not global_checks:
        audit.add("blocker", "isolation_structured_checks_missing")
        return
    check_isolation_arm_names(audit, arms)
    for arm in arms:
        check_isolation_arm(audit, arm)
    check_isolation_global_rows(audit, isolation, global_checks)


def check_isolation_arm_names(audit: Audit, arms: list[Any]) -> None:
    names = [arm.get("arm") for arm in arms if isinstance(arm, dict)]
    if len(arms) != len(ARMS) or any(not isinstance(name, str) for name in names):
        audit.add("blocker", "isolation_arm_coverage_missing")
    elif set(names) != set(ARMS):
        audit.add("blocker", "isolation_arm_coverage_missing")


def check_isolation_global_rows(
    audit: Audit, isolation: dict[str, Any], global_checks: list[Any]
) -> None:
    if any(not isinstance(check, dict) or check.get("status") != "PASS" for check in global_checks):
        audit.add("blocker", "isolation_global_checks_not_passed")
    if isolation.get("blocking_checks") != []:
        audit.add("blocker", "isolation_blocking_checks_present_or_unknown")


def check_isolation_arm(audit: Audit, arm: Any) -> None:
    if not isinstance(arm, dict) or arm.get("status") != "PASS":
        audit.add("blocker", "isolation_arm_not_passed")
        return
    checks = arm.get("checks")
    if not isinstance(checks, list) or not checks:
        audit.add("blocker", "isolation_arm_checks_missing")
    elif any(not isinstance(check, dict) or check.get("status") != "PASS" for check in checks):
        audit.add("blocker", "isolation_arm_checks_not_passed")


def ledger_cells(audit: Audit, ledger: Any) -> list[dict[str, Any]]:
    cells = ledger
    if isinstance(ledger, dict):
        if (
            "cells" in ledger
            and "assignments" in ledger
            and ledger["cells"] != ledger["assignments"]
        ):
            audit.add("blocker", "assignment_envelopes_disagree")
        cells = ledger.get("cells", ledger.get("assignments"))
    if not isinstance(cells, list) or len(cells) > 10000:
        audit.add("blocker", "assignment_ledger_missing_or_invalid")
        return []
    if any(not isinstance(cell, dict) for cell in cells):
        audit.add("blocker", "assignment_record_invalid")
    return [cell for cell in cells if isinstance(cell, dict)]


def check_assignment(audit: Audit, cell: dict[str, Any]) -> None:
    cell_id = cell.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in EXPECTED_CELLS:
        audit.add("blocker", "assignment_outside_frozen_factorial")
        return
    expected = EXPECTED_CELLS[cell_id]
    if (cell.get("case_id"), cell.get("arm"), cell.get("repeat")) != expected:
        audit.add("blocker", "assignment_factor_identity_changed", cell_id)
    if type(cell.get("repeat")) is not int:
        audit.add("blocker", "assignment_repeat_invalid", cell_id)
    if type(cell.get("order_index")) is not int or not 1 <= cell["order_index"] <= BUDGET:
        audit.add("blocker", "assignment_order_invalid", cell_id)
    if status_of(cell) not in STATUSES:
        audit.add("blocker", "assignment_status_invalid", cell_id)


def check_ledger(audit: Audit, cells: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    orders: Counter[int] = Counter()
    for cell in cells:
        check_assignment(audit, cell)
        cell_id = cell.get("cell_id")
        if isinstance(cell_id, str):
            if cell_id in by_id:
                audit.add("blocker", "duplicate_assignment", cell_id)
            by_id[cell_id] = cell
        if type(cell.get("order_index")) is int:
            orders[cell["order_index"]] += 1
    if len(cells) != BUDGET or set(by_id) != set(EXPECTED_CELLS):
        audit.add("blocker", "assignment_factorial_coverage_incomplete")
    check_order_permutation(audit, orders)
    return by_id


def check_order_permutation(audit: Audit, orders: Counter[int]) -> None:
    if set(orders) != set(range(1, BUDGET + 1)) or any(count != 1 for count in orders.values()):
        audit.add("blocker", "assignment_order_not_a_permutation")


def load_results(
    audit: Audit, request: dict[str, Any], base: Path, context: TrustedContext | None = None
) -> list[dict[str, Any]]:
    return load_jsonl(audit, request, base, "safe_results", context)


def load_jsonl(
    audit: Audit,
    request: dict[str, Any],
    base: Path,
    key: str,
    context: TrustedContext | None = None,
) -> list[dict[str, Any]]:
    try:
        raw = read_bytes(artifact_path(base, request.get(key), context), MAX_RESULTS_BYTES)
        rows = parse_role_jsonl(raw, key)
        audit.input_digests[key] = digest(raw)
        return rows
    except InputError:
        audit.input_digests.pop(key, None)
        audit.add("blocker", f"{key}_rejected")
        return []
    except OSError:
        audit.add("unknown", f"{key}_unavailable")
        return []


def parse_role_jsonl(raw: bytes, key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if not line.strip() or len(line) > MAX_RECORD_BYTES or len(rows) >= 10000:
            raise InputError("jsonl_record_or_inventory_invalid")
        row = decode_json(line)
        validate_result_role(row, key)
        rows.append(row)
    return rows


def validate_result_role(value: Any, key: str) -> None:
    if key == "safe_results":
        data = closed_object(value, CORE_RESULT_FIELDS, CORE_RESULT_FIELDS)
        validate_public_identity(data["identity"])
        if status_of(data) not in STATUSES:
            raise InputError("wrong_result_role_schema")
        validate_public_result_values(data)
    elif key == "intake_review":
        allowed = INTAKE_FIELDS | {"cell_id", "result_sha256"}
        data = closed_object(value, allowed, allowed)
        closed_object(
            data["manual_review"],
            {"status", "synthetic_only", "sensitive_content_checked", "final_answer_only"},
            {"status", "synthetic_only", "sensitive_content_checked", "final_answer_only"},
        )
        if not isinstance(data["result_sha256"], str) or not SHA256.fullmatch(
            data["result_sha256"]
        ):
            raise InputError("wrong_result_role_schema")
        if not isinstance(data["unknown_reasons"], dict):
            raise InputError("wrong_result_role_schema")
    else:
        raise InputError("unknown_jsonl_role")


def validate_public_result_values(data: dict[str, Any]) -> None:
    for field in ("public_final_answer", "started_at", "ended_at"):
        if data[field] is not None and not isinstance(data[field], str):
            raise InputError("wrong_result_value_schema")
    for field in ("elapsed_ms", "input_tokens", "output_tokens"):
        if data[field] is not None and invalid_measurement(data[field]):
            raise InputError("wrong_result_value_schema")
    for field in ("task_complete", "entry_emitted", "canonical_full_read"):
        if data[field] is not None and type(data[field]) is not bool:
            raise InputError("wrong_result_value_schema")
    labels = data["critical_error_labels"]
    if not isinstance(labels, list) or any(not isinstance(label, str) for label in labels):
        raise InputError("wrong_result_value_schema")
    if data["failure_reason"] is not None and not safe_failure(data["failure_reason"]):
        raise InputError("wrong_result_value_schema")


def intake_controls(audit: Audit, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    allowed = INTAKE_FIELDS | {"cell_id", "result_sha256"}
    for row in rows:
        cell_id = row.get("cell_id")
        if not isinstance(cell_id, str) or cell_id not in EXPECTED_CELLS:
            audit.add("blocker", "intake_review_cell_outside_assignment")
            continue
        if set(row) != allowed:
            audit.add("blocker", "intake_review_fields_missing_or_unapproved", cell_id)
            audit.input_digests.pop("intake_review", None)
        if cell_id in controls:
            audit.add("blocker", "duplicate_intake_review", cell_id)
        controls[cell_id] = row
    return controls


def join_intake(
    audit: Audit, rows: list[dict[str, Any]], controls: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    joined = []
    represented: set[str] = set()
    for row in rows:
        if set(row) != CORE_RESULT_FIELDS:
            audit.add(
                "blocker", "launch_v1_result_fields_missing_or_unapproved", row.get("cell_id")
            )
            audit.input_digests.pop("safe_results", None)
        cell_id = row.get("cell_id")
        control = controls.get(cell_id) if isinstance(cell_id, str) else None
        if control is None:
            audit.add("unknown", "result_intake_provenance_missing", cell_id)
            joined.append(row)
            continue
        represented.add(cell_id)
        check_intake_digest(audit, row, control)
        joined.append({**row, **{key: control.get(key) for key in INTAKE_FIELDS}})
    for cell_id in controls.keys() - represented:
        audit.add("unknown", "intake_review_has_no_public_result", cell_id)
    return joined


def check_intake_digest(audit: Audit, row: dict[str, Any], control: dict[str, Any]) -> None:
    cell_id = row.get("cell_id")
    encoded = json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True).encode("utf-8")
    if digest(encoded) != control.get("result_sha256"):
        audit.add("blocker", "public_result_differs_from_intake_review_digest", cell_id)
    if type(control.get("schema_version")) is not int or control["schema_version"] != 1:
        audit.add("blocker", "intake_review_schema_invalid", cell_id)
    if control.get("source_id") != "manual-public-synthetic":
        audit.add("blocker", "intake_public_synthetic_provenance_missing", cell_id)
    check_control_case(audit, control)
    check_null_reasons(audit, row, control)


def check_control_case(audit: Audit, control: dict[str, Any]) -> None:
    cell_id = control.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in EXPECTED_CELLS:
        return
    case_id = EXPECTED_CELLS[cell_id][0]
    if control.get("case_id") != case_id or control.get("locale") != case_id.rsplit("-", 1)[1]:
        audit.add("blocker", "intake_case_or_locale_mismatch", cell_id)


def check_null_reasons(audit: Audit, row: dict[str, Any], control: dict[str, Any]) -> None:
    expected = {key for key in NULLABLE_RESULT_FIELDS if row.get(key) is None}
    identity = row.get("identity")
    if isinstance(identity, dict):
        expected.update(f"identity.{key}" for key in IDENTITY_FIELDS if identity.get(key) is None)
    reasons = control.get("unknown_reasons")
    if not isinstance(reasons, dict) or set(reasons) != expected:
        audit.add(
            "blocker", "intake_null_reason_provenance_missing_or_inconsistent", row.get("cell_id")
        )
        return
    if any(
        not isinstance(reason, str) or reason not in UNKNOWN_REASON_CODES
        for reason in reasons.values()
    ):
        audit.add("blocker", "intake_null_reason_category_invalid", row.get("cell_id"))
        audit.input_digests.pop("intake_review", None)


def unknown_reason(row: dict[str, Any], identity: dict[str, Any], field: str) -> bool:
    for reasons in (
        row.get("identity_unknown_reasons"),
        row.get("unknown_reasons"),
        identity.get("unknown_reasons"),
    ):
        if isinstance(reasons, dict):
            for key in (field, f"identity.{field}"):
                if isinstance(reasons.get(key), str) and reasons[key].strip():
                    return True
    return False


def check_identity(
    audit: Audit, row: dict[str, Any], freeze: dict[str, Any], policy: dict[str, bool]
) -> None:
    cell_id = row.get("cell_id")
    identity = row.get("identity")
    if not isinstance(identity, dict):
        audit.add("blocker", "attempt_identity_missing", cell_id)
        return
    for field in IDENTITY_FIELDS - UNKNOWN_IDENTITY_FIELDS:
        check_required_identity_field(audit, identity, field, cell_id)
    if identity.get("source_sha") != freeze.get("source_sha"):
        audit.add("blocker", "attempt_source_differs_from_freeze", cell_id)
    for field in UNKNOWN_IDENTITY_FIELDS:
        check_observed_identity_field(audit, row, identity, field)
    if policy["require_known_model_identity"] and identity.get("model_observed") is None:
        audit.add("blocker", "protocol_requires_observed_model_identity", cell_id)


def check_required_identity_field(
    audit: Audit, identity: dict[str, Any], field: str, cell_id: Any
) -> None:
    value = identity.get(field)
    if field not in identity:
        audit.add("blocker", f"identity_{field}_missing", cell_id)
    elif value is None:
        severity = "blocker" if field in REQUIRED_EXECUTION_IDENTITY else "unknown"
        audit.add(severity, f"identity_{field}_unknown", cell_id)
    elif not isinstance(value, str) or not value.strip():
        audit.add("blocker", f"identity_{field}_invalid", cell_id)
    if field == "repository" and value not in (
        "ParkerHwang/OpenSocrates",
        "https://github.com/ParkerHwang/OpenSocrates",
    ):
        audit.add("blocker", "identity_repository_mismatch", cell_id)


def check_observed_identity_field(
    audit: Audit, row: dict[str, Any], identity: dict[str, Any], field: str
) -> None:
    value = identity.get(field)
    cell_id = row.get("cell_id")
    if value is None:
        audit.add("limitation", f"identity_{field}_unknown", cell_id)
        if not unknown_reason(row, identity, field):
            audit.add("unknown", f"identity_{field}_reason_missing", cell_id)
    elif not isinstance(value, str) or not value.strip():
        audit.add("blocker", f"identity_{field}_invalid", cell_id)
    elif value.lower() in {"unknown", "unavailable", "not-observed", "not_observed"}:
        audit.add("blocker", f"identity_{field}_must_be_null_when_unknown", cell_id)


def check_result_times(
    audit: Audit, row: dict[str, Any], freeze: dict[str, Any], isolated_at: datetime | None
) -> None:
    cell_id = row.get("cell_id")
    start = timestamp(row.get("started_at"))
    end = timestamp(row.get("ended_at"))
    frozen_at = timestamp(freeze.get("frozen_at"))
    if start is None:
        audit.add("blocker", "attempt_start_provenance_missing", cell_id)
    if status_of(row) in TERMINAL_ATTEMPTED and end is None:
        audit.add("blocker", "attempt_end_provenance_missing", cell_id)
    compare_times(audit, frozen_at, start, "attempt_precedes_protocol_freeze", cell_id)
    compare_times(audit, isolated_at, start, "attempt_precedes_isolation_verification", cell_id)
    compare_times(audit, start, end, "attempt_time_order_invalid", cell_id)
    compare_times(audit, start, datetime.now(timezone.utc), "attempt_timestamp_in_future", cell_id)
    compare_times(audit, end, datetime.now(timezone.utc), "attempt_timestamp_in_future", cell_id)


def compare_times(
    audit: Audit, before: datetime | None, after: datetime | None, code: str, cell_id: Any
) -> None:
    if before is not None and after is not None and before > after:
        audit.add("blocker", code, cell_id)


def check_public_metadata(audit: Audit, row: dict[str, Any]) -> None:
    cell_id = row.get("cell_id")
    if set(row) - RESULT_FIELDS:
        audit.add("blocker", "result_contains_unapproved_fields", cell_id)
    identity = row.get("identity")
    if not isinstance(identity, dict) or set(identity) != IDENTITY_FIELDS:
        audit.add("blocker", "identity_fields_missing_or_unapproved", cell_id)
        audit.input_digests.pop("safe_results", None)
    check_measurements(audit, row)
    check_result_availability(audit, row)
    if "delivery_mode" in row:
        check_delivery(audit, row)
    check_answer_review(audit, row)


def check_measurements(audit: Audit, row: dict[str, Any]) -> None:
    cell_id = row.get("cell_id")
    for field in ("elapsed_ms", "input_tokens", "output_tokens"):
        value = row.get(field)
        if value is not None and invalid_measurement(value):
            audit.add("blocker", f"{field}_invalid", cell_id)
    for field in ("task_complete", "entry_emitted", "canonical_full_read"):
        if row.get(field) is not None and type(row[field]) is not bool:
            audit.add("blocker", f"{field}_invalid", cell_id)


def check_result_availability(audit: Audit, row: dict[str, Any]) -> None:
    cell_id = row.get("cell_id")
    if row.get("status") == "COMPLETED":
        answer = row.get("public_final_answer")
        if not isinstance(answer, str) or not answer.strip():
            audit.add("unknown", "completed_public_answer_unavailable", cell_id)
    if status_of(row) in {"FAILED", "TIMEOUT"} and not row.get("failure_reason"):
        audit.add("unknown", "failure_safe_category_missing", cell_id)
    evidence = row.get("application_evidence", "unverified")
    if evidence not in ("unverified", "unknown", "unavailable"):
        audit.add("blocker", "native_application_evidence_overclaimed", cell_id)
    failure = row.get("failure_reason")
    if failure is not None and not safe_failure(failure):
        audit.add("blocker", "failure_reason_is_not_a_safe_category", cell_id)
        audit.input_digests.pop("safe_results", None)


def safe_failure(value: Any) -> bool:
    return isinstance(value, str) and value in FAILURE_REASONS


def check_delivery(audit: Audit, row: dict[str, Any]) -> None:
    cell_id = row.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in EXPECTED_CELLS:
        return
    expected = {
        "plain": "none",
        "general-check": "general-check",
        "native-opensocrates": "native-installed",
    }
    mode = row.get("delivery_mode")
    if mode in ("unknown", "unavailable"):
        audit.add("unknown", "delivery_mode_unverified", cell_id)
    elif mode != expected[EXPECTED_CELLS[cell_id][1]]:
        audit.add("blocker", "native_manual_or_arm_delivery_conflated", cell_id)


def check_answer_review(audit: Audit, row: dict[str, Any]) -> None:
    review = row.get("manual_review")
    if not isinstance(review, dict):
        audit.add("unknown", "public_answer_privacy_review_unavailable", row.get("cell_id"))
        return
    fields = {"status", "synthetic_only", "sensitive_content_checked", "final_answer_only"}
    has_answer = row.get("public_final_answer") is not None
    expected_status = "APPROVED" if has_answer else "NO_PUBLIC_OUTPUT"
    expected_value = True if has_answer else None
    approved = set(review) == fields and review.get("status") == expected_status
    approved = approved and all(
        review.get(field) is expected_value for field in fields - {"status"}
    )
    if not approved:
        audit.add("blocker", "public_answer_safe_retention_review_not_approved", row.get("cell_id"))
        audit.input_digests.pop("intake_review", None)


def attempted(row: dict[str, Any]) -> bool:
    return (
        status_of(row) in ATTEMPTED
        or row.get("started_at") is not None
        or row.get("public_final_answer") is not None
    )


def invalid_measurement(value: Any) -> bool:
    if type(value) not in {int, float}:
        return True
    return value < 0 or (type(value) is float and not math.isfinite(value))


def check_result(
    audit: Audit,
    row: dict[str, Any],
    ledger: dict[str, dict[str, Any]],
    freeze: dict[str, Any],
    policy: dict[str, bool],
    isolated_at: datetime | None,
) -> None:
    cell_id = row.get("cell_id")
    if not isinstance(cell_id, str) or cell_id not in EXPECTED_CELLS:
        audit.add("blocker", "result_outside_assigned_factorial")
    elif cell_id not in ledger:
        audit.add("blocker", "result_has_no_assignment", cell_id)
    elif ledger[cell_id].get("status") != row.get("status"):
        audit.add("blocker", "ledger_result_status_disagreement", cell_id)
    if status_of(row) not in STATUSES:
        audit.add("blocker", "result_status_invalid", cell_id)
    if row.get("attempt", 1) != 1 or type(row.get("attempt", 1)) is not int:
        audit.add("blocker", "retry_or_attempt_number_invalid", cell_id)
    check_public_metadata(audit, row)
    if attempted(row):
        check_identity(audit, row, freeze, policy)
        check_result_times(audit, row, freeze, isolated_at)
        if status_of(row) not in ATTEMPTED:
            audit.add("blocker", "attempt_hidden_as_not_run_or_blocked", cell_id)


def check_missing_results(
    audit: Audit, ledger: dict[str, dict[str, Any]], rows: list[dict[str, Any]]
) -> tuple[int, Counter[str]]:
    represented = {row["cell_id"] for row in rows if isinstance(row.get("cell_id"), str)}
    missing_attempts = 0
    counts: Counter[str] = Counter()
    for cell_id, cell in ledger.items():
        if status_of(cell) in STATUSES:
            counts[status_of(cell)] += 1
        if cell_id in represented:
            continue
        if status_of(cell) in ATTEMPTED:
            missing_attempts += 1
            audit.add("blocker", "attempted_cell_result_missing", cell_id)
        elif status_of(cell) in {"NOT_RUN", "BLOCKED"}:
            audit.add("unknown", "assigned_cell_not_attempted", cell_id)
    return missing_attempts, counts


def summarize_results(
    audit: Audit, ledger: dict[str, dict[str, Any]], rows: list[dict[str, Any]], event_starts: int
) -> None:
    check_duplicate_results(audit, rows)
    missing_attempts, ledger_statuses = check_missing_results(audit, ledger, rows)
    attempted_rows = [row for row in rows if attempted(row)]
    total = max(len(attempted_rows) + missing_attempts, event_starts)
    if total > BUDGET:
        audit.add("blocker", "actor_budget_exceeded")
    check_pending_results(audit, rows)
    result_statuses = Counter(status_of(row) for row in rows if status_of(row) in STATUSES)
    audit.summary.update(
        {
            "budget": {
                "limit": BUDGET,
                "attempted_lower_bound": total,
                "observed_attempt_records": len(attempted_rows),
                "attempted_cells_with_missing_result": missing_attempts,
            },
            "denominators": {
                "assigned_cells": len(ledger),
                "attempted_records": total,
                "observed_failed_records": result_statuses["FAILED"],
                "observed_timeout_records": result_statuses["TIMEOUT"],
                "not_run": ledger_statuses["NOT_RUN"],
                "blocked": ledger_statuses["BLOCKED"],
                "failures_and_timeouts_included": True,
            },
            "result_status_counts": {
                status: result_statuses[status] for status in sorted(STATUSES)
            },
            "ledger_status_counts": {
                status: ledger_statuses[status] for status in sorted(STATUSES)
            },
            "arms": arm_coverage(attempted_rows),
        }
    )


def check_duplicate_results(audit: Audit, rows: list[dict[str, Any]]) -> None:
    seen: Counter[str] = Counter()
    for row in rows:
        if isinstance(row.get("cell_id"), str):
            seen[row["cell_id"]] += 1
    for cell_id, count in seen.items():
        if count > 1:
            audit.add("blocker", "duplicate_result_or_repeated_attempt", cell_id, count - 1)


def check_pending_results(audit: Audit, rows: list[dict[str, Any]]) -> None:
    if any(row.get("status") == "STARTED" for row in rows):
        audit.add("unknown", "attempt_still_in_progress")
    if any(status_of(row) in {"NOT_RUN", "BLOCKED"} for row in rows):
        audit.add("unknown", "assigned_cell_not_attempted")


def check_result_binding(
    audit: Audit,
    rows: list[dict[str, Any]],
    frozen_cells: dict[str, dict[str, Any]],
    study_id: str | None,
) -> None:
    for row in rows:
        cell_id = row.get("cell_id")
        if not isinstance(cell_id, str) or cell_id not in frozen_cells:
            continue
        if study_id is not None and row.get("run_id") != study_id:
            audit.add("blocker", "result_study_identity_missing_or_mismatched", cell_id)
        identifier = frozen_cells[cell_id].get("attempt_id")
        if not isinstance(row.get("attempt_id"), str) or row["attempt_id"] != identifier:
            audit.add("blocker", "result_attempt_identity_missing_or_mismatched", cell_id)


def check_runtime_identity(audit: Audit, rows: list[dict[str, Any]]) -> None:
    values: dict[str, set[str]] = {key: set() for key in IDENTITY_FIELDS - {"repository"}}
    for row in rows:
        collect_runtime_identity(row, values)
    for key, observed in values.items():
        if len(observed) > 1:
            audit.add("blocker", f"cross_cell_identity_{key}_drift")


def collect_runtime_identity(row: dict[str, Any], values: dict[str, set[str]]) -> None:
    identity = row.get("identity")
    if not attempted(row) or not isinstance(identity, dict):
        return
    for key in values:
        value = identity.get(key)
        if isinstance(value, str) and value.strip():
            values[key].add(value)


def arm_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    coverage = {}
    for arm in ARMS:
        cells = {
            row["cell_id"]
            for row in rows
            if isinstance(row.get("cell_id"), str)
            and row["cell_id"] in EXPECTED_CELLS
            and EXPECTED_CELLS[row["cell_id"]][1] == arm
        }
        coverage[arm] = {"expected_cells": 18, "attempted_unique_cells": len(cells)}
    return coverage


def check_judging(audit: Audit, adjudication: Any, policy: dict[str, bool]) -> None:
    judge = adjudication.get("independent_judge") if isinstance(adjudication, dict) else None
    available = (
        isinstance(judge, dict)
        and judge.get("available") is True
        and judge.get("independent") is True
        and isinstance(judge.get("provenance"), str)
        and bool(judge["provenance"].strip())
    )
    availability = "unknown"
    if available:
        availability = "reported_available"
    elif isinstance(judge, dict) and judge.get("available") is False:
        availability = "unavailable"
    audit.summary["independent_judge"] = {
        "availability": availability,
        "reported_available_with_provenance": bool(available),
        "independence_authenticated": False,
    }
    if not available:
        audit.add("limitation", "independent_judge_unavailable_or_unknown")
        if policy["require_independent_judge"]:
            audit.add("blocker", "protocol_requires_independent_judge")


def audit_request(
    request: dict[str, Any], base: Path, audit: Audit, context: TrustedContext | None = None
) -> None:
    root = request_candidate(audit, request, base, context)
    if root is None or context is None:
        return
    freeze = check_freeze(
        audit, load_artifact(audit, request, base, "freeze_manifest", context=context), request
    )
    if not freeze:
        return
    if freeze.get("source_sha") != context.candidate_sha:
        audit.input_digests.pop("freeze_manifest", None)
        audit.summary.pop("frozen_source_sha", None)
        audit.add("blocker", "freeze_not_bound_to_selected_candidate")
        return
    matched = check_inventory(audit, freeze, root)
    roles = input_roles(request, freeze)
    check_required_inputs(audit, roles, matched)
    policy = load_policy(audit, request, root, matched)
    isolation = load_artifact(audit, request, base, "isolation_preflight", context=context)
    isolated_at = check_isolation(audit, freeze, isolation)
    ledger_artifact = load_artifact(audit, request, base, "assignment_ledger", context=context)
    ledger = check_ledger(audit, ledger_cells(audit, ledger_artifact))
    frozen_cells, study_id = frozen_assignments(
        audit, root, roles, matched, freeze.get("source_sha")
    )
    if (
        isinstance(isolation, dict)
        and study_id is not None
        and isolation.get("study_id") != study_id
    ):
        audit.add("blocker", "isolation_study_identity_mismatch")
    bind_plan(audit, ledger_artifact, ledger, frozen_cells)
    event_starts = check_event_history(
        audit, ledger_artifact, ledger, frozen_cells, freeze, isolated_at
    )
    result_rows = load_results(audit, request, base, context)
    controls = intake_controls(audit, load_jsonl(audit, request, base, "intake_review", context))
    rows = join_intake(audit, result_rows, controls)
    for row in rows:
        check_result(audit, row, ledger, freeze, policy, isolated_at)
    summarize_results(audit, ledger, rows, event_starts)
    check_result_binding(audit, rows, frozen_cells, study_id)
    check_runtime_identity(audit, rows)
    check_judging(
        audit,
        load_artifact(
            audit, request, base, "adjudication_summary", required=False, context=context
        ),
        policy,
    )
    if any(severity == "blocker" for severity, _ in audit.findings):
        audit.add("unknown", "source_check_skipped_for_unverified_inputs")
    else:
        check_source(audit, freeze, root, context)
    audit.add("limitation", "metadata_audit_not_native_application_or_efficacy_evidence")
    audit.add("limitation", "provided_artifacts_cannot_prove_no_undisclosed_calls")


def request_candidate(
    audit: Audit, request: Any, base: Path, context: TrustedContext | None
) -> Path | None:
    if context is None:
        audit.add("blocker", "trusted_calling_context_missing")
        return None
    allowed = {
        "schema_version",
        "repository_root",
        "freeze_manifest",
        "assignment_ledger",
        "safe_results",
        "intake_review",
        "isolation_preflight",
        "required_input_paths",
        "freeze_sha256",
        "protocol_policy",
        "adjudication_summary",
    }
    try:
        required = {
            "schema_version",
            "repository_root",
            "freeze_manifest",
            "assignment_ledger",
            "safe_results",
            "intake_review",
            "isolation_preflight",
        }
        data = closed_object(request, allowed, required)
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise InputError("request_schema_version_invalid")
        root = bind_candidate(data, base, context)
        validate_request_paths(data, base, context)
        return root
    except (OSError, ValueError, RuntimeError):
        audit.add("blocker", "request_or_candidate_context_rejected")
        return None


def validate_request_paths(request: dict[str, Any], base: Path, context: TrustedContext) -> None:
    for key in (
        "freeze_manifest",
        "assignment_ledger",
        "safe_results",
        "intake_review",
        "isolation_preflight",
        "adjudication_summary",
    ):
        if request.get(key) is not None:
            artifact_path(base, request[key], context)
    if request.get("protocol_policy") is not None:
        repo_path(context.candidate_root, request["protocol_policy"])


def output_conflicts(
    output: Path, input_path: Path, request: dict[str, Any], context: TrustedContext
) -> bool:
    inputs = {input_path.resolve()}
    for key in (
        "freeze_manifest",
        "assignment_ledger",
        "safe_results",
        "intake_review",
        "isolation_preflight",
        "adjudication_summary",
    ):
        if request.get(key) is not None:
            try:
                inputs.add(artifact_path(input_path.parent, request[key], context))
            except InputError:
                pass  # The audit records a category; never resolve outside approved roots.
    if output.resolve().is_relative_to(context.candidate_root):
        return True
    return output.is_symlink() or output.resolve() in inputs


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    fd, name = tempfile.mkstemp(prefix=".study-audit-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input", type=Path, required=True, help="explicit public artifact request JSON"
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="audit JSON outside the candidate repository"
    )
    parser.add_argument(
        "--candidate-root",
        type=Path,
        required=True,
        help="independently approved candidate checkout",
    )
    parser.add_argument(
        "--candidate-sha", required=True, help="independently selected candidate commit"
    )
    parser.add_argument(
        "--public-evidence-root",
        type=Path,
        action="append",
        required=True,
        help="independently approved public study directory; repeat for more roots",
    )
    parser.add_argument(
        "--git-dir", type=Path, help="independently approved candidate worktree Git metadata"
    )
    parser.add_argument(
        "--git-common-dir", type=Path, help="independently approved public Git object/ref metadata"
    )
    args = parser.parse_args(argv)
    audit = Audit()
    try:
        context = trusted_context(
            args.candidate_root,
            args.candidate_sha,
            args.public_evidence_root,
            args.git_dir,
            args.git_common_dir,
        )
        input_path = artifact_path(Path.cwd(), str(args.input), context)
        request = decode_json(read_bytes(input_path, MAX_DOCUMENT_BYTES))
        if not isinstance(request, dict):
            raise InputError("request_not_object")
        if output_conflicts(args.output, input_path, request, context):
            raise InputError("output_may_not_overwrite_evidence_or_source")
        audit_request(request, input_path.parent, audit, context)
        report = audit.report()
        write_report(args.output, report)
    except (OSError, ValueError, RuntimeError):
        print(
            "study-audit: input/output error; no raw exception or source material retained",
            file=sys.stderr,
        )
        return 3
    print(f"study-audit: {report['reportability']}")
    return {"REPORTABLE": 0, "HOLD": 1, "UNKNOWN": 2}[report["reportability"]]


if __name__ == "__main__":
    raise SystemExit(main())
