#!/usr/bin/env python3
"""Review supplied categorical isolation observations; never inspect a host.

Python 3.12 standard library only. Input is the S042 observation contract, not
raw host output. Required checks with missing, stale or assertion-only evidence
are UNKNOWN and block the experiment. PASS means consistent supplied summaries,
not independent attestation, native method application or execution permission.

Usage: python tools/swarm_isolation_preflight.py --input observations.json
           --output /existing/run-directory/isolation-preflight.json
Exit codes: 0 PASS; 1 FAIL; 2 UNKNOWN or invalid input/output. Output is created
exclusively, never overwritten. No host command, network request, environment
change, credential read/copy, package operation or model call is performed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

BASE_SHA = "227a528996d93c423851db1d663f9572be534e59"
ARMS = ("plain", "general-check", "native-opensocrates")
MAX_INPUT_BYTES = 1024 * 1024
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
SHA = re.compile(r"[a-f0-9]{40}\Z")
DIGEST = re.compile(r"[a-f0-9]{64}\Z")
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
PATH_FIELDS = {"home", "host_config", "temporary", "workspace"}
FORBIDDEN_ARTIFACT_PARTS = {
    ".codex",
    ".claude",
    ".agents",
    ".ssh",
    ".aws",
    ".config",
    ".gnupg",
    "auth.json",
    "credentials.json",
    "config.toml",
}


class InputError(ValueError):
    """A fixed safe error category; never include supplied text in errors."""


@dataclass(frozen=True)
class Rule:
    kind: str
    coverage: frozenset[str]
    control_value: str
    native_value: str
    failure_values: frozenset[str]


def rule(kind: str, coverage: str, control: str, native: str, failures: str) -> Rule:
    return Rule(kind, frozenset(coverage.split()), control, native, frozenset(failures.split()))


ARM_RULES = {
    "runtime": rule(
        "manual-runtime-inspection",
        "host surface version model effort tier tools limits sandbox base-instructions sampling",
        "matches-frozen-shared-runtime",
        "matches-frozen-shared-runtime",
        "runtime-mismatch extra-model-call expanded-budget",
    ),
    "environment": rule(
        "manual-scope-inspection",
        "os-profile os-home host-config temporary workspace aliases global-discovery",
        "separate-profile-inspected",
        "separate-profile-inspected",
        "shared-profile shared-scope alias-to-other-arm",
    ),
    "installation": rule(
        "host-inventory-summary",
        "registration cache managed-package package-identity",
        "opensocrates-absent",
        "exact-native-package-present",
        "unexpected-package control-package-present package-identity-mismatch",
    ),
    "hooks": rule(
        "host-discovery-summary",
        "session-start submission stop trust active-config",
        "no-opensocrates-hook-active",
        "native-discovery-hooks-approved",
        "control-hook-active native-hooks-missing unexpected-hook",
    ),
    "skills": rule(
        "host-discovery-summary",
        "account global workspace plugin-cache controller",
        "opensocrates-undiscoverable",
        "native-controller-discoverable",
        "control-skill-discoverable native-controller-missing manual-canonical-injection",
    ),
    "memory": rule(
        "manual-scope-inspection",
        "account-memory custom-instructions project-context conversation-history inherited-context",
        "no-inherited-intervention-inspected",
        "no-inherited-intervention-inspected",
        "inherited-intervention memory-contamination",
    ),
    "workspace": rule(
        "manual-workspace-inventory",
        "synthetic-files parent-instructions rules skills linked-roots prior-artifacts",
        "synthetic-only-inspected",
        "synthetic-only-inspected",
        "foreign-content inherited-instructions linked-treatment-content",
    ),
    "intervention_paths": rule(
        "host-discovery-summary",
        "installation hooks skills memory workspace parent-context manual-injection",
        "all-opensocrates-paths-absent",
        "native-only-no-manual-injection",
        "control-intervention-visible manual-canonical-injection unaccounted-intervention",
    ),
    "credential_boundary": rule(
        "manual-boundary-inspection",
        "normal-login no-auth-copy no-home-clone no-global-mutation",
        "existing-authorized-login-no-copy",
        "existing-authorized-login-no-copy",
        "credential-copy home-clone global-mutation unauthorized-login",
    ),
}
GLOBAL_RULES = {
    "source": rule(
        "source-identity-review",
        "candidate-sha assigned-base remote-main package-identity",
        "current-source-and-base-recorded",
        "current-source-and-base-recorded",
        "source-mismatch historical-source-only",
    ),
    "protocol": rule(
        "frozen-manifest-review",
        "input-hashes source-sha pre-result-freeze 54-cell-budget no-rerun failures-counted timeouts-counted",
        "frozen-before-first-call",
        "frozen-before-first-call",
        "not-frozen actor-already-started budget-changed favorable-rerun excluded-failure",
    ),
    "privacy": rule(
        "manual-boundary-inspection",
        "synthetic-inputs public-final-answers no-raw-logs no-private-prompts no-secrets no-screenshots no-hidden-reasoning",
        "safe-retention-contract-inspected",
        "safe-retention-contract-inspected",
        "prohibited-retention private-source-input",
    ),
}
ALL_RULES = {**ARM_RULES, **GLOBAL_RULES}
NON_OBSERVATIONAL_KINDS = {
    "declaration",
    "new-thread",
    "authoring-chat",
    "historical-report",
    "model-self-report",
}
PROTOCOL_FIELDS = {
    "state",
    "source_sha",
    "frozen_at",
    "input_files",
    "actor_budget_total",
    "started_actor_calls",
    "dimension_counts",
    "one_attempt_per_cell",
    "count_failures",
    "count_timeouts",
    "run_owner",
    "native_mode",
}


def obj(value: Any, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(value) <= fields:
        raise InputError("unexpected-object-or-field")
    return value


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise InputError("invalid-opaque-identifier")
    return value


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise InputError("invalid-timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("invalid-timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InputError("timestamp-without-timezone")
    return parsed


def digest(value: Any, pattern: re.Pattern[str] = SHA) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise InputError("invalid-digest")
    return value


def strings(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 32:
        raise InputError("invalid-categorical-list")
    result = [identifier(item) for item in value]
    if len(result) != len(set(result)):
        raise InputError("duplicate-categorical-value")
    return result


def validate_identity(value: Any) -> dict[str, Any]:
    identity = obj(value, IDENTITY_FIELDS)
    for key, item in identity.items():
        if item is None:
            continue
        if key == "source_sha":
            digest(item)
        elif key == "repository":
            if item != "ParkerHwang/OpenSocrates":
                raise InputError("unexpected-repository")
        elif not isinstance(item, str) or not re.fullmatch(r"[A-Za-z0-9_.:/+ -]{1,100}", item):
            raise InputError("invalid-identity-category")
    return {key: identity.get(key) for key in sorted(IDENTITY_FIELDS)}


def validate_paths(value: Any) -> dict[str, str]:
    paths = obj(value, PATH_FIELDS)
    for item in paths.values():
        if (
            not isinstance(item, str)
            or not re.fullmatch(r"/scope-map/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", item)
            or any(part in {".", ".."} for part in PurePosixPath(item).parts)
        ):
            raise InputError("expected-synthetic-scope-path-alias")
    # Lexical comparison only: no stat, expanduser, resolve or read of these paths.
    return {key: str(PurePosixPath(item)) for key, item in paths.items()}


def validate_arm(value: Any) -> dict[str, Any]:
    arm = obj(
        value, {"arm", "scope_id", "os_profile_id", "paths", "runtime_sha256", "declarations"}
    )
    if arm.get("arm") not in ARMS:
        raise InputError("unknown-arm")
    for key in ("scope_id", "os_profile_id"):
        if key in arm:
            identifier(arm[key])
    if "runtime_sha256" in arm:
        digest(arm["runtime_sha256"], DIGEST)
    arm["paths"] = validate_paths(arm.get("paths", {}))
    declarations = obj(arm.get("declarations", {}), {"isolated", "new_thread", "plugin_free"})
    if any(type(item) is not bool for item in declarations.values()):
        raise InputError("invalid-declaration")
    return arm


def validate_protocol(value: Any) -> dict[str, Any]:
    protocol = obj(value, PROTOCOL_FIELDS)
    for key in ("source_sha",):
        if key in protocol:
            digest(protocol[key])
    if "frozen_at" in protocol:
        timestamp(protocol["frozen_at"])
    if "input_files" in protocol:
        files = protocol["input_files"]
        if not isinstance(files, list) or len(files) > 256:
            raise InputError("invalid-input-file-inventory")
        names = []
        for item in files:
            entry = obj(item, {"path", "sha256"})
            path = entry.get("path")
            if (
                not isinstance(path, str)
                or not path
                or path.startswith(("/", ".", "\\"))
                or "\\" in path
                or ":" in path
                or ".." in path.split("/")
                or not re.fullmatch(r"[A-Za-z0-9_./-]{1,240}", path)
            ):
                raise InputError("invalid-public-input-reference")
            digest(entry.get("sha256"), DIGEST)
            names.append(path)
        if len(names) != len(set(names)):
            raise InputError("duplicate-input-reference")
    return protocol


def validate_observation(value: Any) -> dict[str, Any]:
    observation = obj(
        value,
        {
            "observation_id",
            "arm",
            "scope_id",
            "check",
            "value",
            "kind",
            "observer",
            "observed_at",
            "snapshot_id",
            "source_sha",
            "coverage",
        },
    )
    check = observation.get("check")
    if check not in ALL_RULES:
        raise InputError("unknown-observation-check")
    for key in ("observation_id", "scope_id", "snapshot_id"):
        identifier(observation.get(key))
    if observation.get("observer") not in {"S001", "S076", "S078"}:
        raise InputError("unsupported-observer")
    expected_arm = {"study"} if check in GLOBAL_RULES else set(ARMS)
    if observation.get("arm") not in expected_arm:
        raise InputError("observation-arm-mismatch")
    policy = ALL_RULES[check]
    if observation.get("kind") not in {policy.kind, *NON_OBSERVATIONAL_KINDS}:
        raise InputError("unsupported-observation-kind")
    if observation.get("value") not in {
        policy.control_value,
        policy.native_value,
        "unavailable",
        *policy.failure_values,
    }:
        raise InputError("unsupported-observation-value")
    timestamp(observation.get("observed_at"))
    digest(observation.get("source_sha"))
    coverage = strings(observation.get("coverage"))
    if not set(coverage) <= policy.coverage:
        raise InputError("unexpected-coverage-category")
    return observation


def validate_baseline(value: Any) -> dict[str, Any]:
    baseline = obj(value, {"assigned_base_sha", "remote_main_sha"})
    for item in baseline.values():
        if item is not None:
            digest(item)
    return baseline


def validate_records(
    value: Any, limit: int, key: str, validator: Callable[[Any], dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > limit:
        raise InputError("invalid-record-list")
    records = [validator(item) for item in value]
    ids = [item[key] for item in records]
    if len(ids) != len(set(ids)):
        raise InputError("duplicate-record-identity")
    return records


def validate_input(value: Any) -> dict[str, Any]:
    data = obj(
        value,
        {
            "schema_version",
            "study_id",
            "snapshot_id",
            "as_of",
            "source_identity",
            "baseline",
            "protocol",
            "arms",
            "observations",
            "availability",
            "runtime_sha256",
        },
    )
    if type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise InputError("unsupported-schema-version")
    for key in ("study_id", "snapshot_id"):
        identifier(data.get(key))
    timestamp(data.get("as_of"))
    if "runtime_sha256" in data:
        digest(data["runtime_sha256"], DIGEST)
    data["source_identity"] = validate_identity(data.get("source_identity", {}))
    data["baseline"] = validate_baseline(data.get("baseline", {}))
    data["protocol"] = validate_protocol(data.get("protocol", {}))
    data["arms"] = validate_records(data.get("arms", []), 3, "arm", validate_arm)
    data["observations"] = validate_records(
        data.get("observations", []), 256, "observation_id", validate_observation
    )
    availability = obj(
        data.get("availability", {}), {"independent_evaluator", "backend_model_identity"}
    )
    if any(item not in {"available", "unavailable", "unknown"} for item in availability.values()):
        raise InputError("invalid-availability-category")
    data["availability"] = availability
    return data


def row(check: str, status: str, reason: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {"check": check, "status": status, "reason": reason, "evidence_ids": evidence or []}


def aggregate(rows: list[dict[str, Any]]) -> str:
    states = {item["status"] for item in rows}
    if "FAIL" in states:
        return "FAIL"
    return "UNKNOWN" if "UNKNOWN" in states or not states else "PASS"


def observation_qualifies(
    item: dict[str, Any], data: dict[str, Any], scope: str, rule_: Rule
) -> bool:
    frozen_at = data["protocol"].get("frozen_at")
    if frozen_at is None:
        return False
    return (
        item["kind"] == rule_.kind
        and item["snapshot_id"] == data["snapshot_id"]
        and item["scope_id"] == scope
        and item["source_sha"] == data["source_identity"].get("source_sha")
        and timestamp(frozen_at) <= timestamp(item["observed_at"]) <= timestamp(data["as_of"])
    )


def review_observations(data: dict[str, Any], arm: str, scope: str, check: str) -> dict[str, Any]:
    policy = ALL_RULES[check]
    candidates = [
        item for item in data["observations"] if item["arm"] == arm and item["check"] == check
    ]
    usable = [item for item in candidates if observation_qualifies(item, data, scope, policy)]
    ids = sorted(item["observation_id"] for item in usable)
    if any(item["value"] in policy.failure_values for item in usable):
        return row(check, "FAIL", "observed-boundary-failure", ids)
    expected = policy.native_value if arm == "native-opensocrates" else policy.control_value
    other_values = {policy.control_value, policy.native_value} - {expected}
    if any(item["value"] in other_values for item in usable):
        return row(check, "FAIL", "observed-condition-mismatch", ids)
    if not usable or len(usable) != len(candidates):
        return row(check, "UNKNOWN", "missing-or-unqualified-observation", ids)
    if any(set(item["coverage"]) != policy.coverage for item in usable):
        return row(check, "UNKNOWN", "incomplete-intervention-path-coverage", ids)
    if any(item["value"] != expected for item in usable):
        return row(check, "UNKNOWN", "unavailable-or-conflicting-observations", ids)
    return row(check, "PASS", "consistent-provided-observation-summaries", ids)


def source_configuration(data: dict[str, Any]) -> dict[str, Any]:
    baseline = data["baseline"]
    identity = data["source_identity"]
    if baseline.get("assigned_base_sha") not in {None, BASE_SHA}:
        return row("source_configuration", "FAIL", "assigned-base-mismatch")
    if baseline.get("remote_main_sha") not in {None, BASE_SHA}:
        return row(
            "source_configuration", "FAIL", "remote-main-drift-requires-integration-decision"
        )
    required = {"assigned_base_sha", "remote_main_sha"}
    if any(baseline.get(key) is None for key in required) or not identity.get("source_sha"):
        return row("source_configuration", "UNKNOWN", "missing-source-identity")
    if identity.get("repository") != "ParkerHwang/OpenSocrates":
        return row("source_configuration", "UNKNOWN", "missing-repository-identity")
    common = {
        "product_version",
        "content_revision",
        "host",
        "platform",
        "model_requested",
        "effort",
        "service_tier_requested",
    }
    if any(not identity.get(key) for key in common):
        return row("source_configuration", "UNKNOWN", "missing-common-runtime-identity")
    if identity["service_tier_requested"] != "priority":
        return row("source_configuration", "FAIL", "requested-tier-contract-mismatch")
    return row(
        "source_configuration", "PASS", "declared-source-consistent-observation-also-required"
    )


def protocol_configuration(data: dict[str, Any]) -> dict[str, Any]:
    protocol = data["protocol"]
    if not PROTOCOL_FIELDS <= set(protocol):
        return row("protocol_configuration", "UNKNOWN", "incomplete-protocol-declaration")
    # A protocol-only lock may precede isolation review. The final S041 study
    # freeze consumes that review; requiring it here would make a cycle.
    if protocol["state"] not in ("INPUTS_LOCKED", "FROZEN"):
        return row("protocol_configuration", "UNKNOWN", "protocol-not-locked-before-calls")
    expected = {
        "source_sha": data["source_identity"].get("source_sha"),
        "actor_budget_total": 54,
        "started_actor_calls": 0,
        "dimension_counts": {"tasks": 3, "locales": 2, "arms": 3, "repeats": 3},
        "one_attempt_per_cell": True,
        "count_failures": True,
        "count_timeouts": True,
        "run_owner": "S078",
        "native_mode": "installed-plugin",
    }
    if any(
        type(protocol[key]) is not type(wanted) or protocol[key] != wanted
        for key, wanted in expected.items()
    ):
        return row(
            "protocol_configuration", "FAIL", "protocol-budget-or-treatment-contract-mismatch"
        )
    if not protocol["input_files"] or timestamp(protocol["frozen_at"]) > timestamp(data["as_of"]):
        return row("protocol_configuration", "UNKNOWN", "missing-frozen-inputs-or-future-freeze")
    return row(
        "protocol_configuration", "PASS", "declared-protocol-consistent-observation-also-required"
    )


def scopes_overlap(left: str, right: str) -> bool:
    a, b = PurePosixPath(left), PurePosixPath(right)
    return a == b or a in b.parents or b in a.parents


def scope_configuration(arm: dict[str, Any], arms: list[dict[str, Any]]) -> dict[str, Any]:
    required = {"scope_id", "os_profile_id", "paths"}
    if not required <= set(arm) or set(arm["paths"]) != PATH_FIELDS:
        return row("scope_configuration", "UNKNOWN", "missing-explicit-scope-identities")
    for other in arms:
        if other["arm"] == arm["arm"]:
            continue
        if any(arm[key] == other.get(key) for key in ("scope_id", "os_profile_id")):
            return row("scope_configuration", "FAIL", "shared-os-profile-or-scope")
        if any(
            scopes_overlap(a, b) for a in arm["paths"].values() for b in other["paths"].values()
        ):
            return row("scope_configuration", "FAIL", "overlapping-arm-paths")
    return row("scope_configuration", "PASS", "declared-scopes-disjoint-observation-also-required")


def runtime_configuration(data: dict[str, Any], arm: dict[str, Any]) -> dict[str, Any]:
    expected = data.get("runtime_sha256")
    observed = arm.get("runtime_sha256")
    if expected is None or observed is None:
        return row("runtime_configuration", "UNKNOWN", "missing-public-runtime-digest")
    if expected != observed:
        return row("runtime_configuration", "FAIL", "arm-runtime-digest-mismatch")
    return row(
        "runtime_configuration", "PASS", "declared-runtime-matches-observation-also-required"
    )


def evaluate(data: dict[str, Any]) -> dict[str, Any]:
    global_rows = [source_configuration(data), protocol_configuration(data)]
    global_rows.extend(
        review_observations(data, "study", data["study_id"], key) for key in GLOBAL_RULES
    )
    arm_reports = []
    for name in ARMS:
        arm = next((item for item in data["arms"] if item["arm"] == name), {"arm": name})
        checks = [scope_configuration(arm, data["arms"]), runtime_configuration(data, arm)]
        checks.extend(
            review_observations(data, name, arm.get("scope_id", ""), key) for key in ARM_RULES
        )
        arm_reports.append(
            {
                "arm": name,
                "status": aggregate(checks),
                "checks": checks,
                "declarations_used_as_evidence": False,
                "installation_is_application_proof": False,
                "application_evidence": "unverified",
            }
        )
    all_rows = global_rows + [check for arm in arm_reports for check in arm["checks"]]
    status = aggregate(all_rows)
    return {
        "schema_version": 1,
        "tool": "swarm-isolation-preflight",
        "status": status,
        "study_id": data["study_id"],
        "snapshot_id": data["snapshot_id"],
        "as_of": data["as_of"],
        "source_identity": data["source_identity"],
        "baseline": data["baseline"],
        "identity_unknown_reasons": {
            key: (
                "not-observed-by-supported-host"
                if key in {"model_observed", "service_tier_observed"}
                else "not-provided"
            )
            for key, value in data["source_identity"].items()
            if value is None
        },
        "isolation_blocked": status != "PASS",
        "experiment_blocked": True,
        "execution_authorized": False,
        "final_study_freeze_and_lease_required": True,
        "evidence_level": "provided-summary-consistency-only",
        "global_checks": global_rows,
        "arms": arm_reports,
        "blocking_checks": [
            {"arm": "study", **item} for item in global_rows if item["status"] != "PASS"
        ]
        + [
            {"arm": arm["arm"], **item}
            for arm in arm_reports
            for item in arm["checks"]
            if item["status"] != "PASS"
        ],
        "availability": {
            key: {
                "reported_state": data["availability"].get(key, "unknown"),
                "verification": "unverified",
                "reason": "not-independently-established-by-this-preflight",
            }
            for key in ("independent_evaluator", "backend_model_identity")
        },
        "limits": [
            "No host was inspected and no observation was independently authenticated by this tool.",
            "PASS covers required isolation summaries only; central approval and an active resource lease remain necessary.",
            "Independent evaluation and backend model identity availability are separate reported study limitations.",
            "No native read, application, efficacy, clean-machine or control-answer-quality receipt is created.",
            "This snapshot must be invalidated on any host, source, configuration or scope change before actor calls.",
        ],
    }


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError("duplicate-json-key")
        result[key] = value
    return result


def artifact_path(path: Path) -> Path:
    if not path.is_absolute() or FORBIDDEN_ARTIFACT_PARTS.intersection(path.parts):
        raise InputError("unsafe-artifact-path")
    if ".." in path.parts or path.is_symlink():
        raise InputError("linked-or-relative-artifact-path")
    # Resolve only explicitly selected artifact parents (e.g. macOS /tmp), never
    # the observation scope aliases. No directory is created by this tool.
    parent = path.parent.resolve(strict=True)
    if FORBIDDEN_ARTIFACT_PARTS.intersection(parent.parts):
        raise InputError("unsafe-artifact-path")
    return parent / path.name


def write_report(output: Path, report: dict[str, Any]) -> None:
    output = artifact_path(output)
    if output.name != "isolation-preflight.json":
        raise InputError("output-name-must-be-isolation-preflight-json")
    # Link publishes a complete new report atomically and refuses existing paths.
    # These operations touch only the explicitly selected output directory.
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            prefix=".isolation-preflight-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, ensure_ascii=True, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_input(path: Path) -> bytes:
    path = artifact_path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise InputError("input-must-be-regular-single-link-file")
        raw = stream.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise InputError("input-size-limit")
    return raw


def error_report(category: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "tool": "swarm-isolation-preflight",
        "status": "FAIL",
        "isolation_blocked": True,
        "experiment_blocked": True,
        "execution_authorized": False,
        "error_category": category,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Absolute path to categorical observation JSON only; never raw host output",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Absolute new isolation-preflight.json in an existing artifact directory",
    )
    args = parser.parse_args(argv)
    input_error = False
    try:
        raw = read_input(args.input)
        data = json.loads(raw, object_pairs_hook=reject_duplicate_keys)
        report = evaluate(validate_input(data))
    except InputError as exc:
        input_error = True
        report = error_report(str(exc))
    except (OSError, ValueError, TypeError, RecursionError):
        input_error = True
        report = error_report("unreadable-or-invalid-input")
    try:
        write_report(args.output, report)
    except (OSError, InputError):
        print(
            "isolation preflight: output-not-created; experiment remains blocked", file=sys.stderr
        )
        return 2
    print(f"isolation preflight: {report['status']}; execution authorization is separate")
    return 2 if input_error else {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
