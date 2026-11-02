"""Create a local study manifest from an explicit list, without running a study.

Python 3.12 standard library only. Metadata/output paths are confined to this
checkout's evals/swarm-20261015 directory; the output parent must exist.
Explicit driver inputs may use tools/swarm_*.py, and package inputs may use
build/ or dist/ inside the same checkout. No external files are opened.
No directory discovery, Git, authentication, network, or model calls occur.

The input JSON has schema_version=1, state="DRAFT", source_sha (40 lowercase
hex), quota=54, isolation_state, input_files=[{"role": ..., "path": ...}],
and privacy_declaration={"public_synthetic_only": true,
"contains_private_material": false}. File paths are repository relative.
Required draft roles are protocol, fixture, arm, rubric, and budget. FROZEN
additionally requires privacy, analysis-plan, assignment, driver, runner-config,
package, and isolation roles. Identity and unknown_reasons are optional.

Only --approval plus a separately pinned --approval-sha256 can emit FROZEN.
Approval is a local coordinator record, not an authenticated human signature
or proof of isolation, execution, method application, or useful results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STUDY_PREFIX = Path("evals/swarm-20261015")
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_INPUT_FILES = 128
REQUIRED_ROLES = {"protocol", "fixture", "arm", "rubric", "budget"}
ROLES = REQUIRED_ROLES | {
    "privacy",
    "analysis-plan",
    "assignment",
    "driver",
    "runner-config",
    "package",
    "isolation",
}
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
INPUT_FIELDS = {
    "schema_version",
    "state",
    "source_sha",
    "quota",
    "isolation_state",
    "input_files",
    "privacy_declaration",
    "identity",
    "unknown_reasons",
}
APPROVAL_FIELDS = {
    "schema_version",
    "state",
    "approved_by",
    "source_sha",
    "input_sha256",
    "input_files",
    "quota",
    "isolation_state",
    "actor_responses_started",
    "frozen_at",
    "preconditions",
}
PRECONDITIONS = {
    "complete_input_inventory",
    "execution_choices_resolved",
    "fixed_order_recorded",
    "safe_capture_path_approved",
    "resource_lease_verified",
}


class ContractError(ValueError):
    """A safe, fixed error category, without input contents or private paths."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise ContractError(category)


def object_fields(value: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    require(isinstance(value, dict), "expected_json_object")
    require(required <= value.keys() <= allowed, "unexpected_or_missing_fields")
    return value


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(value: Any, length: int = 64) -> str:
    require(isinstance(value, str), "invalid_digest")
    require(re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None, "invalid_digest")
    return value


def project_path(
    root: Path,
    raw: str,
    *,
    relative_only: bool = False,
    prefixes: tuple[Path, ...] = (STUDY_PREFIX,),
) -> Path:
    require(isinstance(raw, str) and bool(raw), "invalid_path")
    value = Path(raw)
    require(not relative_only or not value.is_absolute(), "expected_repo_relative_path")
    path = value if value.is_absolute() else root / value
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ContractError("path_outside_allowed_study_root") from error
    require(
        any(relative.is_relative_to(prefix) and relative != prefix for prefix in prefixes),
        "path_outside_allowed_project_roots",
    )
    for part in relative.parts:
        require(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) is not None,
            "unsafe_path_component",
        )
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        require(not cursor.is_symlink(), "symlink_path_refused")
    return path


def read_file(path: Path, maximum: int, *, retain: bool) -> tuple[bytes, str, int]:
    # Only explicitly named regular, single-link files are read. O_NOFOLLOW
    # also closes a final-component symlink swap between the path check and open.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), "non_regular_input_refused")
        require(before.st_nlink == 1, "hardlinked_input_refused")
        require(before.st_size <= maximum, "input_too_large")
        chunks = []
        hasher = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(chunk)
            require(size <= maximum, "input_too_large")
            hasher.update(chunk)
            if retain:
                chunks.append(chunk)
        after = os.fstat(stream.fileno())
    require(
        (before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        == (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
        "input_changed_during_read",
    )
    return b"".join(chunks), hasher.hexdigest(), size


def file_bytes(path: Path) -> bytes:
    return read_file(path, MAX_FILE_BYTES, retain=True)[0]


def json_object(value: bytes) -> dict[str, Any]:
    try:
        result = json.loads(value.decode("utf-8"), object_pairs_hook=unique_object)
    except ContractError:
        raise
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ContractError("invalid_utf8_json") from error
    require(isinstance(result, dict), "expected_json_object")
    return result


def input_contract(value: dict[str, Any]) -> dict[str, Any]:
    required = INPUT_FIELDS - {"identity", "unknown_reasons"}
    object_fields(value, INPUT_FIELDS, required)
    require(
        type(value["schema_version"]) is int and value["schema_version"] == 1,
        "unsupported_schema_version",
    )
    require(value["state"] == "DRAFT", "input_must_be_draft")
    sha(value["source_sha"], 40)
    require(type(value["quota"]) is int and value["quota"] == 54, "quota_must_be_54")
    require(
        value["isolation_state"] in ("UNVERIFIED", "VERIFIED", "BLOCKED"), "invalid_isolation_state"
    )
    require(
        value["privacy_declaration"]
        == {"public_synthetic_only": True, "contains_private_material": False}
        and isinstance(value["privacy_declaration"], dict)
        and all(type(item) is bool for item in value["privacy_declaration"].values()),
        "public_synthetic_declaration_required",
    )
    rows = value["input_files"]
    require(
        isinstance(rows, list) and 1 <= len(rows) <= MAX_INPUT_FILES, "invalid_input_file_count"
    )
    return value


def source_path(root: Path, row: dict[str, Any]) -> Path:
    prefixes = (STUDY_PREFIX,)
    if row["role"] == "driver":
        prefixes = (Path("tools"),)
    elif row["role"] == "package":
        prefixes = (STUDY_PREFIX, Path("build"), Path("dist"))
    path = project_path(root, row["path"], relative_only=True, prefixes=prefixes)
    if row["role"] == "driver":
        require(
            path.parent == root / "tools"
            and path.name.startswith("swarm_")
            and path.suffix == ".py",
            "expected_swarm_driver_source",
        )
    return path


def inventory(root: Path, rows: list[Any], excluded: set[Path]) -> list[dict[str, Any]]:
    result = []
    seen: set[Path] = set()
    for row in rows:
        object_fields(row, {"role", "path"}, {"role", "path"})
        require(isinstance(row["role"], str) and row["role"] in ROLES, "invalid_file_role")
        path = source_path(root, row)
        require(path not in seen and path not in excluded, "duplicate_or_self_input")
        seen.add(path)
        _, file_hash, size = read_file(path, MAX_SOURCE_BYTES, retain=False)
        result.append(
            {
                "path": path.relative_to(root).as_posix(),
                "role": row["role"],
                "sha256": file_hash,
                "bytes": size,
            }
        )
    require(REQUIRED_ROLES <= {row["role"] for row in result}, "missing_required_file_role")
    return sorted(result, key=lambda row: row["path"])


def identity_metadata(value: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    supplied = object_fields(value.get("identity", {}), IDENTITY_FIELDS, set())
    reasons = object_fields(value.get("unknown_reasons", {}), IDENTITY_FIELDS, set())
    result: dict[str, Any] = dict.fromkeys(sorted(IDENTITY_FIELDS))
    result.update(supplied)
    require(result["source_sha"] in (None, value["source_sha"]), "identity_source_mismatch")
    result["source_sha"] = value["source_sha"]
    unknowns = {}
    for key, item in result.items():
        require(
            item is None
            or (
                isinstance(item, str)
                and 0 < len(item) <= 200
                and all(character.isprintable() for character in item)
            ),
            "invalid_identity_value",
        )
        if item is None:
            reason = reasons.get(key, "unavailable: not observed by this local hashing tool")
            require(
                isinstance(reason, str)
                and 0 < len(reason) <= 200
                and all(character.isprintable() for character in reason),
                "invalid_unknown_reason",
            )
            unknowns[key] = reason
    return result, unknowns


def frozen_time(value: Any) -> str:
    require(isinstance(value, str), "invalid_frozen_at")
    require(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is not None,
        "invalid_frozen_at",
    )
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ContractError("invalid_frozen_at") from error
    require(timestamp <= datetime.now(timezone.utc), "future_approval_refused")
    return value


def approval_record(
    path: Path,
    pinned_sha: str,
    value: dict[str, Any],
    input_sha: str,
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = file_bytes(path)
    require(digest(raw) == sha(pinned_sha), "approval_digest_mismatch")
    approval = object_fields(json_object(raw), APPROVAL_FIELDS, APPROVAL_FIELDS)
    require(
        type(approval["schema_version"]) is int and approval["schema_version"] == 1,
        "unsupported_approval_schema",
    )
    require(
        approval["state"] == "APPROVED" and approval["approved_by"] == "S001",
        "coordinator_approval_required",
    )
    require(approval["source_sha"] == value["source_sha"], "approval_source_mismatch")
    require(approval["input_sha256"] == input_sha, "approval_input_mismatch")
    expected = [{"path": row["path"], "sha256": row["sha256"]} for row in files]
    require(approval["input_files"] == expected, "approval_inventory_mismatch")
    require(type(approval["quota"]) is int and approval["quota"] == 54, "approval_quota_mismatch")
    require(
        approval["isolation_state"] == value["isolation_state"] == "VERIFIED",
        "verified_isolation_record_required",
    )
    require(
        type(approval["actor_responses_started"]) is int
        and approval["actor_responses_started"] == 0,
        "results_already_started",
    )
    require(ROLES <= {row["role"] for row in files}, "incomplete_freeze_roles")
    preconditions = object_fields(approval["preconditions"], PRECONDITIONS, PRECONDITIONS)
    require(all(item is True for item in preconditions.values()), "unresolved_freeze_preconditions")
    frozen_time(approval["frozen_at"])
    return approval


def make_manifest(
    root: Path,
    input_path: Path,
    output_path: Path,
    approval_path: Path | None,
    approval_sha: str | None,
) -> dict[str, Any]:
    require(input_path != output_path, "output_cannot_replace_input")
    require(approval_path not in {input_path, output_path}, "approval_must_be_separate")
    raw = file_bytes(input_path)
    value = input_contract(json_object(raw))
    excluded = {input_path, output_path}
    if approval_path is not None:
        excluded.add(approval_path)
    files = inventory(root, value["input_files"], excluded)
    identity, unknowns = identity_metadata(value)
    approval = None
    if approval_path is not None and approval_sha is not None:
        approval = approval_record(approval_path, approval_sha, value, digest(raw), files)
    return {
        "schema_version": 1,
        "state": "FROZEN" if approval else "DRAFT",
        "draft": approval is None,
        "frozen": approval is not None,
        "source_sha": value["source_sha"],
        "source_sha_evidence": "caller_declared; checkout/commit relation not checked",
        "input": {"path": input_path.relative_to(root).as_posix(), "sha256": digest(raw)},
        "input_files": files,
        "isolation_state": value["isolation_state"],
        "isolation_evidence": "caller_declared; no host or credential inspection",
        "quota": 54,
        "budget_contract": {
            "unit": "single-turn actor responses",
            "dimensions": {"families": 3, "locales": 2, "arms": 3, "repeats": 3},
            "actor_owner": "S078",
            "quality_reruns": 0,
            "unbudgeted_infrastructure_retries": 0,
            "failed_and_timed_out_attempts_remain_counted": True,
            "authoring_chats_are_experimental_controls": False,
        },
        "frozen_at": approval["frozen_at"] if approval else None,
        "approved_by": approval["approved_by"] if approval else None,
        "approval_preconditions": approval["preconditions"] if approval else None,
        "approval": (
            {
                "path": approval_path.relative_to(root).as_posix(),
                "sha256": approval_sha,
                "evidence": "separately hash-pinned local coordinator record; unsigned",
            }
            if approval and approval_path
            else None
        ),
        "identity": identity,
        "unknown_reasons": unknowns,
        "independent_evaluator": None,
        "independent_evaluator_reason": "unavailable: not established by manifest creation",
        "native_installation_or_application_receipt": None,
        "evidence_boundary": (
            "Hashes describe explicit bytes only. Creating this document does not approve "
            "research or verify source identity, isolation, native installation, canonical "
            "manual injection, model application, independent judging, or answer usefulness. "
            "FROZEN requires separate pinned approval and is not an authenticated signature."
        ),
    }


def write_new(root: Path, path: Path, value: dict[str, Any]) -> None:
    # Publish complete JSON with an atomic no-clobber link. Neither an existing
    # manifest nor a source file can be replaced. No parent directories are made.
    project_path(root, str(path))
    require(path.parent.is_dir(), "output_parent_missing")
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    descriptor, temporary = tempfile.mkstemp(prefix=".freeze-draft-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        project_path(root, str(path))
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Explicit draft input JSON path")
    parser.add_argument("--output", required=True, help="New manifest path; never overwritten")
    parser.add_argument("--approval", help="Separate local S001 approval JSON; optional")
    parser.add_argument("--approval-sha256", help="Previously fixed approval file SHA-256")
    args = parser.parse_args()
    if bool(args.approval) != bool(args.approval_sha256):
        parser.error("--approval and --approval-sha256 must be supplied together")
    root = Path(__file__).resolve().parent.parent
    try:
        input_path = project_path(root, args.input)
        output_path = project_path(root, args.output)
        approval_path = project_path(root, args.approval) if args.approval else None
        require(not output_path.exists(), "output_already_exists")
        result = make_manifest(root, input_path, output_path, approval_path, args.approval_sha256)
        write_new(root, output_path, result)
    except ContractError as error:
        print(f"freeze manifest: refused ({error})", file=sys.stderr)
        return 2
    except OSError:
        print("freeze manifest: refused (local_file_operation_failed)", file=sys.stderr)
        return 2
    print(f"freeze manifest: {result['state']} ({len(result['input_files'])} explicit files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
