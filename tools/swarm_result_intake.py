#!/usr/bin/env python3
"""Intake manually curated public synthetic results; never extract host events.

Python 3.12 standard library only. Input is UTF-8 JSONL with exactly two keys
per row: "result" (the unchanged launch-v1 result) and "intake" (safe manual
control metadata). At most 54 cells from one run are accepted. No directory walk,
host invocation, authentication access, stream/transcript extraction, redaction,
scoring, or retry is implemented. The input file itself must already be safe to
retain. Schema acceptance is NOT a guarantee of de-identification or permission
to publish: a human must check each public answer and its metadata first.

--output receives only launch-v1 results; --review-output receives separate safe
control records keyed by cell_id and exact public result hash. Neither file may
exist. Control records are published first; a crash can leave control alone and
requires operator reconciliation, never an automatic retry or overwrite.

Launch interfaces-v1 result fields are preserved. Required intake control fields:
schema_version=1, source_id="manual-public-synthetic", run_id (public opaque
label, equal to S043 study_id), attempt_id=run_id+":"+cell_id+":a1",
case_id=family+"-"+locale, locale=en|ko,
manual_review, delivery_mode, independent_evaluation, and unknown_reasons. Each cell_id is
case_id+"-"+arm+"-r"+repeat, using the three launch families/arms/repeats.

manual_review has exactly status, synthetic_only, sensitive_content_checked,
and final_answer_only. With an answer, status is APPROVED and all three checks
are true. Without an answer, status is NO_PUBLIC_OUTPUT and the checks are null.
This is the central operator's attestation, not an automatic privacy finding.
independent_evaluation is unknown|unavailable|not_assessed; this intake never
certifies an evaluator's independence or a native application receipt.

All fields, including nullable result and identity fields, must be present.
unknown_reasons maps EACH null field to a safe reason code; identity fields use
the prefix "identity.". No non-null field may have an unknown reason. Reason
codes: UNKNOWN, UNAVAILABLE, NOT_OBSERVED, NOT_APPLICABLE, NOT_RUN,
WITHHELD_PENDING_REVIEW. No other free-form reason text is accepted.

identity has exactly the launch source_identity fields. repository must be
ParkerHwang/OpenSocrates or its canonical HTTPS URL. source_sha is an exact
40-character lowercase commit SHA or null. Remaining identity values are short
public product/host/model labels or null, never account IDs, paths or credentials.
Observed model/tier values must be actually observed, never copied from requests.

failure_reason is null or a safe category: EXECUTION_FAILED, TIMEOUT, INTERRUPTED,
RESOURCE_BLOCKED, ISOLATION_UNVERIFIED, BUDGET_EXHAUSTED, HOST_UNAVAILABLE,
OUTPUT_UNAVAILABLE, PRIVACY_REVIEW_PENDING, CANCELLED, or UNKNOWN. A FAILED,
TIMEOUT or BLOCKED record requires a category. critical_error_labels is a list
of predeclared public rubric labels (lowercase letters/digits/hyphens only).
The fixed lowercase S043/S039 safe failure categories are also accepted verbatim;
there is no rewriting of upstream failure status or reason.
application_evidence is unverified|unknown|unavailable, never "applied"/"proven".
delivery_mode is none|general-check|native-installed|unknown|unavailable and must
agree with the assigned arm when known. A manual-canonical treatment is rejected
as out of this launch protocol, never relabeled as native-installed. Even the
native-installed label is a curator's provenance assertion, not an install/read/
application receipt from this tool.

The files are a snapshot: every supplied attempt, including failures/timeouts,
is emitted unchanged or validation fails without creating an output.
There is no append/update/overwrite, selective dropping, or success conversion.
Missing assigned cells and other files' attempts remain the assignment ledger's
responsibility; this local tool does not authorize or certify model-call budgets.
NOT_RUN/BLOCKED rows do not become actor calls. No input is executed or imported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_RECORD_BYTES = 256 * 1024
MAX_ANSWER_BYTES = 128 * 1024
MAX_RECORDS = 54
FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
ARMS = ("plain", "general-check", "native-opensocrates")
STATUSES = frozenset({"NOT_RUN", "STARTED", "COMPLETED", "FAILED", "TIMEOUT", "BLOCKED"})
UNKNOWN_REASONS = frozenset(
    {
        "UNKNOWN",
        "UNAVAILABLE",
        "NOT_OBSERVED",
        "NOT_APPLICABLE",
        "NOT_RUN",
        "WITHHELD_PENDING_REVIEW",
    }
)
FAILURE_REASONS = frozenset(
    {
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
)
IDENTITY_FIELDS = frozenset(
    {
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
)
NULLABLE_RESULT_FIELDS = frozenset(
    {
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
)
INTAKE_FIELDS = frozenset(
    {
        "schema_version",
        "source_id",
        "run_id",
        "attempt_id",
        "case_id",
        "locale",
        "manual_review",
        "delivery_mode",
        "independent_evaluation",
        "unknown_reasons",
    }
)
RESULT_FIELDS = (
    frozenset({"cell_id", "status", "critical_error_labels", "application_evidence", "identity"})
    | NULLABLE_RESULT_FIELDS
)
REVIEW_FIELDS = frozenset(
    {"status", "synthetic_only", "sensitive_content_checked", "final_answer_only"}
)
LABEL = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", re.ASCII)
PUBLIC_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", re.ASCII)
PUBLIC_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._+():/-]{0,127}", re.ASCII)
SHA = re.compile(r"[0-9a-f]{40}", re.ASCII)
TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|\+00:00)", re.ASCII)
REPOSITORIES = frozenset(
    {"ParkerHwang/OpenSocrates", "https://github.com/ParkerHwang/OpenSocrates"}
)
FORBIDDEN_KEYS = {
    "FORBIDDEN_REASONING": frozenset(
        {
            "reasoning",
            "analysis",
            "chainofthought",
            "cot",
            "hiddenreasoning",
            "thoughts",
            "thinking",
        }
    ),
    "FORBIDDEN_AUTH": frozenset(
        {
            "auth",
            "authorization",
            "authentication",
            "apikey",
            "accesstoken",
            "refreshtoken",
            "credentials",
            "credential",
            "password",
            "secret",
            "cookie",
            "cookies",
            "oauth",
        }
    ),
    "FORBIDDEN_ACCOUNT": frozenset(
        {"account", "accountid", "userid", "email", "username", "organizationid", "sessionid"}
    ),
    "FORBIDDEN_SCREENSHOT": frozenset(
        {"screenshot", "screenshots", "screencapture", "image", "images", "imageurl"}
    ),
    "FORBIDDEN_RAW_STREAM": frozenset(
        {
            "raw",
            "rawstream",
            "rawoutput",
            "rawlog",
            "rawlogs",
            "events",
            "eventstream",
            "transcript",
            "transcripts",
            "messages",
            "toolcalls",
            "stdout",
            "stderr",
            "conversation",
        }
    ),
    "FORBIDDEN_PRIVATE_PROMPT": frozenset(
        {
            "prompt",
            "prompts",
            "privateprompt",
            "userprompt",
            "systemprompt",
            "input",
            "instructions",
        }
    ),
}


class IntakeError(Exception):
    """A fixed code only; never retain caller-controlled text in an error."""

    def __init__(self, code: str, record: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.record = record


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse's usual error includes untrusted argument/path values.
        raise IntakeError("CLI_ARGUMENTS")


def reject_key(key: str) -> None:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    for code, keys in FORBIDDEN_KEYS.items():
        if normalized in keys:
            raise IntakeError(code)
    raise IntakeError("UNKNOWN_FIELD")


def strict_object(value: Any, fields: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntakeError("OBJECT_REQUIRED")
    for key in value:
        if key not in fields:
            reject_key(key)
    if set(value) != fields:
        raise IntakeError("MISSING_FIELD")
    return value


def one_of(value: Any, choices: Any) -> None:
    if not isinstance(value, str) or value not in choices:
        raise IntakeError("INVALID_ENUM")


def nullable_bool(value: Any) -> None:
    if value is not None and type(value) is not bool:
        raise IntakeError("INVALID_BOOLEAN")


def nullable_number(value: Any, *, integer: bool = False) -> None:
    if value is None:
        return
    valid_types = (int,) if integer else (int, float)
    if type(value) not in valid_types or value < 0 or not math.isfinite(value):
        raise IntakeError("INVALID_NUMBER")


def utc_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or TIMESTAMP.fullmatch(value) is None:
        raise IntakeError("INVALID_TIMESTAMP")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        raise IntakeError("INVALID_TIMESTAMP") from None


def validate_identifiers(row: dict[str, Any]) -> None:
    if type(row["schema_version"]) is not int or row["schema_version"] != 1:
        raise IntakeError("SCHEMA_VERSION")
    one_of(row["source_id"], {"manual-public-synthetic"})
    if not isinstance(row["run_id"], str) or PUBLIC_ID.fullmatch(row["run_id"]) is None:
        raise IntakeError("INVALID_IDENTIFIER")
    one_of(row["locale"], {"en", "ko"})
    case_ids = {f"{family}-{row['locale']}" for family in FAMILIES}
    one_of(row["case_id"], case_ids)
    cell_ids = {f"{row['case_id']}-{arm}-r{repeat}" for arm in ARMS for repeat in (1, 2, 3)}
    one_of(row["cell_id"], cell_ids)
    if row["attempt_id"] != f"{row['run_id']}:{row['cell_id']}:a1":
        raise IntakeError("ATTEMPT_ID")


def validate_identity(value: Any) -> dict[str, Any]:
    identity = strict_object(value, IDENTITY_FIELDS)
    for key, item in identity.items():
        if item is None:
            continue
        if not isinstance(item, str) or PUBLIC_IDENTITY.fullmatch(item) is None:
            raise IntakeError("INVALID_IDENTITY")
        if key == "repository":
            one_of(item, REPOSITORIES)
        if key == "source_sha" and SHA.fullmatch(item) is None:
            raise IntakeError("INVALID_SOURCE_SHA")
    return identity


def validate_unknowns(row: dict[str, Any], identity: dict[str, Any]) -> None:
    allowed = NULLABLE_RESULT_FIELDS | {f"identity.{key}" for key in IDENTITY_FIELDS}
    reasons = row["unknown_reasons"]
    if not isinstance(reasons, dict):
        raise IntakeError("OBJECT_REQUIRED")
    for key, reason in reasons.items():
        if key not in allowed:
            reject_key(key)
        one_of(reason, UNKNOWN_REASONS)
    expected = {key for key in NULLABLE_RESULT_FIELDS if row[key] is None}
    expected |= {f"identity.{key}" for key in IDENTITY_FIELDS if identity[key] is None}
    if set(reasons) != expected:
        raise IntakeError("NULL_REASON_MISMATCH")


def validate_review(row: dict[str, Any]) -> None:
    review = strict_object(row["manual_review"], REVIEW_FIELDS)
    answer = row["public_final_answer"]
    checks = ("synthetic_only", "sensitive_content_checked", "final_answer_only")
    if answer is None:
        if review["status"] != "NO_PUBLIC_OUTPUT" or any(review[key] is not None for key in checks):
            raise IntakeError("MANUAL_REVIEW_REQUIRED")
        return
    if not isinstance(answer, str) or not answer.strip():
        raise IntakeError("INVALID_PUBLIC_ANSWER")
    if len(answer.encode("utf-8")) > MAX_ANSWER_BYTES:
        raise IntakeError("PUBLIC_ANSWER_TOO_LARGE")
    if review["status"] != "APPROVED" or any(review[key] is not True for key in checks):
        raise IntakeError("MANUAL_REVIEW_REQUIRED")


def validate_status(row: dict[str, Any]) -> None:
    status = row["status"]
    one_of(status, STATUSES)
    if status in {"FAILED", "TIMEOUT", "BLOCKED"} and row["failure_reason"] is None:
        raise IntakeError("FAILURE_REASON_REQUIRED")
    if status in {"NOT_RUN", "STARTED", "COMPLETED"} and row["failure_reason"] is not None:
        raise IntakeError("STATUS_CONFLICT")
    if status != "COMPLETED" and row["task_complete"] is True:
        raise IntakeError("STATUS_CONFLICT")
    if status in {"NOT_RUN", "BLOCKED"}:
        absent = NULLABLE_RESULT_FIELDS - {"failure_reason"}
        if any(row[key] is not None for key in absent) or row["critical_error_labels"]:
            raise IntakeError("STATUS_CONFLICT")
    if status == "STARTED":
        absent = ("ended_at", "public_final_answer", "task_complete")
        if any(row[key] is not None for key in absent):
            raise IntakeError("STATUS_CONFLICT")


def validate_delivery(row: dict[str, Any]) -> None:
    mode = row["delivery_mode"]
    if mode == "manual-canonical":
        raise IntakeError("MANUAL_TREATMENT_OUT_OF_SCOPE")
    known = {
        "plain": "none",
        "general-check": "general-check",
        "native-opensocrates": "native-installed",
    }
    for arm, expected in known.items():
        if row["cell_id"].startswith(f"{row['case_id']}-{arm}-r"):
            one_of(mode, {expected, "unknown", "unavailable"})
            return
    raise IntakeError("DELIVERY_MODE_CONFLICT")


def validate_observations(row: dict[str, Any]) -> None:
    for key in ("task_complete", "entry_emitted", "canonical_full_read"):
        nullable_bool(row[key])
    nullable_number(row["elapsed_ms"])
    nullable_number(row["input_tokens"], integer=True)
    nullable_number(row["output_tokens"], integer=True)
    start, end = utc_timestamp(row["started_at"]), utc_timestamp(row["ended_at"])
    if start is not None and end is not None and end < start:
        raise IntakeError("TIMESTAMP_ORDER")
    if row["failure_reason"] is not None:
        one_of(row["failure_reason"], FAILURE_REASONS)
    one_of(row["application_evidence"], {"unverified", "unknown", "unavailable"})
    one_of(row["independent_evaluation"], {"unknown", "unavailable", "not_assessed"})


def validate_labels(value: Any) -> None:
    if not isinstance(value, list) or len(value) > 32:
        raise IntakeError("INVALID_LABELS")
    for label in value:
        if not isinstance(label, str) or len(label) > 64 or LABEL.fullmatch(label) is None:
            raise IntakeError("INVALID_LABELS")
    if len(set(value)) != len(value):
        raise IntakeError("INVALID_LABELS")


def validate_record(value: Any) -> dict[str, Any]:
    envelope = strict_object(value, frozenset({"result", "intake"}))
    result = strict_object(envelope["result"], RESULT_FIELDS)
    intake = strict_object(envelope["intake"], INTAKE_FIELDS)
    row = {**result, **intake}
    validate_identifiers(row)
    identity = validate_identity(row["identity"])
    validate_observations(row)
    validate_labels(row["critical_error_labels"])
    validate_review(row)
    validate_unknowns(row, identity)
    validate_status(row)
    validate_delivery(row)
    return row


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IntakeError("DUPLICATE_FIELD")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise IntakeError("INVALID_JSON_NUMBER")


def decode_record(line: bytes, number: int) -> dict[str, Any]:
    try:
        value = json.loads(
            line.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant
        )
        return validate_record(value)
    except IntakeError as exc:
        raise IntakeError(exc.code, number) from None
    except (ValueError, TypeError, RecursionError, OverflowError):
        # Do not print JSONDecodeError, a Unicode error, source lines or values.
        raise IntakeError("INVALID_JSON", number) from None


def open_input(path: Path) -> Any:
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    fd = os.open(path, flags)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise IntakeError("INPUT_NOT_REGULAR")
        if info.st_size > MAX_INPUT_BYTES:
            raise IntakeError("INPUT_TOO_LARGE")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def read_results(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open_input(path) as stream:
        total = 0
        while line := stream.readline(MAX_RECORD_BYTES + 1):
            number = len(rows) + 1
            total += len(line)
            if len(line) > MAX_RECORD_BYTES or total > MAX_INPUT_BYTES:
                raise IntakeError("INPUT_TOO_LARGE", number)
            if number > MAX_RECORDS:
                raise IntakeError("RECORD_LIMIT", number)
            if not line.strip():
                raise IntakeError("EMPTY_RECORD", number)
            rows.append(decode_record(line, number))
    if not rows:
        raise IntakeError("EMPTY_INPUT")
    validate_batch(rows)
    return rows


def validate_batch(rows: list[dict[str, Any]]) -> None:
    if len({row["run_id"] for row in rows}) != 1:
        raise IntakeError("MIXED_RUNS")
    seen: set[str] = set()
    for number, row in enumerate(rows, 1):
        if row["cell_id"] in seen:
            raise IntakeError("DUPLICATE_CELL", number)
        seen.add(row["cell_id"])


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


def split_records(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    results, controls = [], []
    for row in rows:
        result = {key: row[key] for key in RESULT_FIELDS}
        control = {key: row[key] for key in INTAKE_FIELDS}
        control["cell_id"] = row["cell_id"]
        control["result_sha256"] = hashlib.sha256(
            canonical_json(result).encode("utf-8")
        ).hexdigest()
        results.append(result)
        controls.append(control)
    return results, controls


def stage_results(path: Path, rows: list[dict[str, Any]]) -> tuple[int, str, str]:
    """Stage a 0600 file; no result path is touched before all data is valid."""
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    temporary = f".swarm-intake-{secrets.token_hex(12)}.tmp"
    created = False
    try:
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        created = True
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(canonical_json(row) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return directory, temporary, path.name
    except BaseException:
        try:
            if created:
                os.unlink(temporary, dir_fd=directory)
        finally:
            os.close(directory)
        raise


def publish_staged(staged: tuple[int, str, str]) -> None:
    directory, temporary, name = staged
    try:
        os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
    except FileExistsError:
        raise IntakeError("OUTPUT_EXISTS") from None


def discard_stage(staged: tuple[int, str, str]) -> None:
    directory, temporary, _ = staged
    try:
        os.unlink(temporary, dir_fd=directory)
    finally:
        os.close(directory)


def rollback_control(staged: tuple[int, str, str]) -> None:
    directory, temporary, name = staged
    original = os.stat(temporary, dir_fd=directory, follow_symlinks=False)
    current = os.stat(name, dir_fd=directory, follow_symlinks=False)
    if (original.st_dev, original.st_ino) != (current.st_dev, current.st_ino):
        raise IntakeError("OUTPUT_RECOVERY_REQUIRED")
    os.unlink(name, dir_fd=directory)


def write_results(output: Path, review_output: Path, rows: list[dict[str, Any]]) -> None:
    """Create both new paths, control first; never replace an existing file/link."""
    results, controls = split_records(rows)
    staged_control = stage_results(review_output, controls)
    staged_result = None
    control_published = False
    result_published = False
    try:
        staged_result = stage_results(output, results)
        publish_staged(staged_control)
        control_published = True
        publish_staged(staged_result)
        result_published = True
    finally:
        try:
            if control_published and not result_published:
                rollback_control(staged_control)
        finally:
            try:
                if staged_result is not None:
                    discard_stage(staged_result)
            finally:
                discard_stage(staged_control)


def emit_error(error: IntakeError) -> None:
    message: dict[str, Any] = {"error": error.code}
    if error.record is not None:
        message["record"] = error.record
    print(json.dumps(message, sort_keys=True), file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(
        description="Strict intake of manually reviewed public synthetic result JSONL; no automatic de-identification.",
        epilog="No model calls, event extraction, publication, scoring, retry, or overwrite. Unknowns require null plus safe reasons.",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Already curated UTF-8 JSONL; regular file, not a host log.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New safe-results.jsonl path in an existing directory; must not exist.",
    )
    parser.add_argument(
        "--review-output",
        required=True,
        type=Path,
        help="Separate new intake-review.jsonl path for safe manual control records; must not exist.",
    )
    try:
        args = parser.parse_args(argv)
        rows = read_results(args.input)
        write_results(args.output, args.review_output, rows)
    except IntakeError as exc:
        emit_error(exc)
        return 2
    except OSError:
        emit_error(IntakeError("FILE_IO"))
        return 3
    except KeyboardInterrupt:
        emit_error(IntakeError("INTERRUPTED"))
        return 130
    except Exception:
        # Unexpected failures must also avoid tracebacks containing input values.
        emit_error(IntakeError("INTERNAL_ERROR"))
        return 4
    print(json.dumps({"records_written": len(rows), "schema_version": 1}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
