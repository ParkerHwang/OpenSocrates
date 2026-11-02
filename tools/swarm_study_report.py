#!/usr/bin/env python3
"""Render a bilingual exploratory report from an explicit, public-only JSON projection.

Python 3.12 standard library only; no host, model, sibling-tool or network calls.
``--input`` is one JSON object and ``--output`` is a NEW directory containing
study-report.md and summary.json. An empty object is a valid NOT_RUN input.

Integration contract (schema_version=1; every key below is optional):
  study_id: "swarm-20261015"; retention: "public-synthetic-only"
  identity: launch-v1 source_identity fields, plus unknown_reasons {field: code}
  sources: {protocol|privacy|analysis_plan|results|usage|adjudication|audit:
            {path: repository-relative public artifact, sha256: 64 hex}}
  freeze: launch-v1 freeze object (input_files use path/sha256)
  assignments: launch-v1 cell objects (fixed 54-cell matrix)
  results: launch-v1 result objects; public_final_answer is NEVER echoed or hashed
  usage: {state: NOT_RUN|PARTIAL|COMPLETE, source_sha: SHA|null,
          elapsed_ms|input_tokens|output_tokens:
            {observed_total: number|null, observed_cells: integer}}
  adjudication: {state: NOT_RUN|PARTIAL|COMPLETE, source_sha: SHA|null,
    judges: [{kind: self-review|independent-ai|independent-human,
              model_requested: label|null, model_observed: label|null}],
    cells: [{cell_id: fixed ID, pass: bool|null, disagreement: bool|null,
             resolved: bool|null}]}
  audit: {state: NOT_RUN|PARTIAL|PASS|FAIL, source_sha: SHA|null,
          checks: [{check_id: safe label, status: NOT_RUN|PASS|FAIL|UNKNOWN}]}

Nonempty results require retention and a results source reference. Upstream
artifacts must be projected into this closed schema by the integrator; arbitrary
upstream objects, raw events, free-text notes, prompts and account fields are
rejected. References are displayed, never opened. Supplied public answers are
not automatically certified synthetic; producers must follow the privacy
contract before calling this tool. This report is not a sanitizer for raw logs.
COMPLETE describes report coverage, NEVER efficacy or release qualification.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import stat
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

BASE_SHA = "227a528996d93c423851db1d663f9572be534e59"
REPOSITORY = "https://github.com/ParkerHwang/OpenSocrates"
FAMILIES = ("email-agreement", "changed-recommendation", "price-profit")
LOCALES = ("en", "ko")
ARMS = ("plain", "general-check", "native-opensocrates")
TERMINAL = {"COMPLETED", "FAILED", "TIMEOUT"}
ATTEMPTED = TERMINAL | {"STARTED"}
STATUSES = ATTEMPTED | {"NOT_RUN", "BLOCKED"}
STATES = {"NOT_RUN", "PARTIAL", "COMPLETE"}
METRICS = ("elapsed_ms", "input_tokens", "output_tokens")
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
SOURCE_KINDS = {"protocol", "privacy", "analysis_plan", "results", "usage", "adjudication", "audit"}
MATRIX = {
    f"{family}-{locale}-{arm}-r{repeat}": {
        "case_id": f"{family}-{locale}",
        "family": family,
        "locale": locale,
        "arm": arm,
        "repeat": repeat,
    }
    for family in FAMILIES
    for locale in LOCALES
    for arm in ARMS
    for repeat in (1, 2, 3)
}
MAX_INPUT_BYTES = 16 * 1024 * 1024


class ReportInputError(ValueError):
    """Privacy-safe error; never include supplied field names or values."""


def require(condition: bool, category: str) -> None:
    if not condition:
        raise ReportInputError(category)


def closed(value: Any, keys: set[str], category: str) -> dict[str, Any]:
    require(isinstance(value, dict), category + ":object-required")
    require(set(value) <= keys, category + ":unrecognized-fields")
    return value


def rows(value: Any, category: str, limit: int = 54) -> list[Any]:
    require(isinstance(value, list) and len(value) <= limit, category + ":array-limit")
    return value


def choice(value: Any, allowed: Any, category: str) -> Any:
    require(isinstance(value, str) and value in allowed, category + ":invalid-enum")
    return value


def label(value: Any, category: str) -> str:
    require(
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+:-]{0,95}", value) is not None,
        category + ":safe-label-required",
    )
    require(
        re.search(r"(?i)(sk-|bearer|oauth|password|secret|credential|@)", value) is None,
        category + ":sensitive-label-rejected",
    )
    return value


def digest(value: Any, length: int, category: str) -> Any:
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value),
        category + ":digest-required",
    )
    return value


def number(value: Any, category: str, *, integer: bool = False) -> Any:
    if value is not None:
        kind = type(value) is int if integer else type(value) in (int, float)
        require(kind and math.isfinite(value) and value >= 0, category + ":nonnegative-number")
    return value


def boolean(value: Any, category: str) -> Any:
    require(value is None or type(value) is bool, category + ":boolean-or-null")
    return value


def timestamp(value: Any) -> Any:
    if value is not None:
        require(isinstance(value, str) and len(value) <= 40, "timestamp:invalid")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ReportInputError("timestamp:invalid") from None
        require(parsed.tzinfo is not None, "timestamp:timezone-required")
    return value


def has_attempt(row: dict[str, Any]) -> bool:
    return row["status"] in ATTEMPTED or row.get("started_at") is not None


def source_ref(value: Any, *, study_only: bool = True) -> dict[str, str]:
    value = closed(value, {"path", "sha256"}, "source")
    path = value.get("path")
    require(isinstance(path, str) and len(path) <= 240, "source:invalid-path")
    require(re.fullmatch(r"[A-Za-z0-9_./-]+", path) is not None, "source:invalid-path")
    parts = PurePosixPath(path).parts
    require(not path.startswith("/") and ".." not in parts, "source:relative-path-required")
    if study_only:
        require(path.startswith("evals/swarm-20261015/"), "source:public-study-path-required")
    else:
        require(
            parts
            and (
                parts[0]
                in {
                    "content",
                    "docs",
                    "evals",
                    "plugin-src",
                    "schemas",
                    "src",
                    "tools",
                    "installer",
                }
                or path
                in {
                    "AGENTS.md",
                    "CONTRIBUTING.md",
                    "SECURITY.md",
                    "README.md",
                    "pyproject.toml",
                    "uv.lock",
                    "Makefile",
                    "package.json",
                    "package-lock.json",
                }
            ),
            "source:public-repository-path-required",
        )
    require(
        not any(
            re.search(r"(?i)(auth|credential|transcript|screenshot|secret|raw[-_]?log)", p)
            for p in parts
        ),
        "source:private-artifact-rejected",
    )
    return {"path": path, "sha256": digest(value.get("sha256"), 64, "source")}


def identity(value: Any) -> dict[str, Any]:
    value = closed(value, IDENTITY_FIELDS | {"unknown_reasons"}, "identity")
    reasons = closed(value.get("unknown_reasons", {}), IDENTITY_FIELDS, "identity-reasons")
    result: dict[str, Any] = {}
    for key in sorted(IDENTITY_FIELDS):
        item = value.get(key)
        if item is None:
            reason = label(reasons.get(key, "not-provided"), "identity-reason")
            result[key] = None
            result.setdefault("unknown_reasons", {})[key] = reason
        elif key == "repository":
            require(item == REPOSITORY, "identity:repository-mismatch")
            result[key] = item
        elif key == "source_sha":
            result[key] = digest(item, 40, "identity-source")
        elif key == "content_revision" and type(item) is int:
            result[key] = number(item, "identity-content-revision", integer=True)
        else:
            result[key] = label(item, "identity-value")
    return result


def freeze(value: Any) -> dict[str, Any]:
    value = closed(
        value,
        {
            "state",
            "source_sha",
            "input_files",
            "isolation_state",
            "quota",
            "frozen_at",
            "approved_by",
        },
        "freeze",
    )
    result = {
        "state": choice(value.get("state", "DRAFT"), {"DRAFT", "FROZEN", "INVALIDATED"}, "freeze"),
        "source_sha": value.get("source_sha"),
        "input_files": [
            source_ref(v, study_only=False)
            for v in rows(value.get("input_files", []), "freeze-inputs", 100)
        ],
        "isolation_state": choice(
            value.get("isolation_state", "UNVERIFIED"),
            {"UNVERIFIED", "VERIFIED", "BLOCKED"},
            "isolation",
        ),
        "quota": value.get("quota", 54),
        "frozen_at": timestamp(value.get("frozen_at")),
        "approved_by": value.get("approved_by"),
    }
    require(result["quota"] == 54 and type(result["quota"]) is int, "freeze:budget-mismatch")
    if result["source_sha"] is not None:
        digest(result["source_sha"], 40, "freeze-source")
    require(result["approved_by"] in (None, "S001"), "freeze:owner-mismatch")
    return result


def assignments(value: Any) -> list[dict[str, Any]]:
    result = []
    seen: set[str] = set()
    orders: set[int] = set()
    for row in rows(value, "assignments"):
        row = closed(
            row,
            {"cell_id", "case_id", "arm", "repeat", "order_index", "assignment_seed", "status"},
            "assignment",
        )
        cell = choice(row.get("cell_id"), MATRIX, "assignment-cell")
        require(cell not in seen, "assignment:duplicate-cell")
        for key in ("case_id", "arm", "repeat"):
            require(row.get(key) == MATRIX[cell][key], "assignment:matrix-mismatch")
        order = number(row.get("order_index"), "assignment-order", integer=True)
        require(
            order is not None and 1 <= order <= 54 and order not in orders,
            "assignment:invalid-order",
        )
        seed = row.get("assignment_seed")
        require(type(seed) in (int, str), "assignment:seed-required")
        label(str(seed), "assignment-seed")
        choice(row.get("status", "NOT_RUN"), STATUSES, "assignment-status")
        result.append(dict(row))
        seen.add(cell)
        orders.add(order)
    return result


def results(value: Any) -> list[dict[str, Any]]:  # noqa: C901 - closed public field validation
    output = []
    seen: set[str] = set()
    allowed = {
        "cell_id",
        "status",
        "public_final_answer",
        "started_at",
        "ended_at",
        *METRICS,
        "critical_error_labels",
        "task_complete",
        "entry_emitted",
        "canonical_full_read",
        "application_evidence",
        "failure_reason",
        "identity",
    }
    for row in rows(value, "results"):
        row = closed(row, allowed, "result")
        cell = choice(row.get("cell_id"), MATRIX, "result-cell")
        require(cell not in seen, "result:duplicate-cell-no-reruns")
        seen.add(cell)
        item = {"cell_id": cell, "status": choice(row.get("status"), STATUSES, "result-status")}
        item.update(
            {k: number(row.get(k), "result-metric", integer=k != "elapsed_ms") for k in METRICS}
        )
        for key in ("task_complete", "entry_emitted", "canonical_full_read"):
            item[key] = boolean(row.get(key), "result-observation")
        for key in ("started_at", "ended_at"):
            item[key] = timestamp(row.get(key))
        if item["started_at"] is not None and item["ended_at"] is not None:
            require(
                datetime.fromisoformat(item["ended_at"].replace("Z", "+00:00"))
                >= datetime.fromisoformat(item["started_at"].replace("Z", "+00:00")),
                "result:reversed-timestamps",
            )
        require(
            item["status"] != "NOT_RUN" or item["started_at"] is None,
            "result:not-run-with-start-evidence",
        )
        item["critical_error_labels"] = [
            label(v, "critical-label")
            for v in rows(row.get("critical_error_labels", []), "critical-labels", 100)
        ]
        require(
            row.get("application_evidence", "unverified") in (None, "unverified"),
            "result:application-receipt-unsupported",
        )
        item["application_evidence"] = "unverified"
        reason = row.get("failure_reason")
        item["failure_reason"] = label(reason, "failure-category") if reason is not None else None
        item["identity"] = identity(row.get("identity", {}))
        answer = row.get("public_final_answer")
        if answer is not None:
            require(isinstance(answer, str) and len(answer) <= 200000, "result:answer-limit")
            require(has_attempt(item), "result:unattempted-answer")
            item["public_answer_available"] = True
        else:
            item["public_answer_available"] = False
        if not has_attempt(item):
            require(all(item[k] is None for k in METRICS), "result:unattempted-metrics")
        output.append(item)
    return output


def summary_header(
    value: Any, extra: set[str], category: str, states: set[str] = STATES
) -> dict[str, Any]:
    value = closed(value, {"state", "source_sha"} | extra, category)
    value.setdefault("state", "NOT_RUN")
    value.setdefault("source_sha", None)
    choice(value["state"], states, category)
    if value.get("source_sha") is not None:
        digest(value["source_sha"], 40, category)
    return value


def usage(value: Any) -> dict[str, Any]:
    value = summary_header(value, set(METRICS), "usage")
    for key in METRICS:
        if key not in value:
            continue
        entry = closed(value[key], {"observed_total", "observed_cells"}, "usage-metric")
        number(entry.get("observed_total"), "usage-total", integer=key != "elapsed_ms")
        count = number(entry.get("observed_cells"), "usage-count", integer=True)
        require(count is not None and count <= 54, "usage:coverage-required")
    return value


def adjudication(value: Any) -> dict[str, Any]:
    value = summary_header(value, {"judges", "cells"}, "adjudication")
    value.setdefault("judges", [])
    value.setdefault("cells", [])
    for judge in rows(value["judges"], "judges", 20):
        judge = closed(judge, {"kind", "model_requested", "model_observed"}, "judge")
        choice(judge.get("kind"), {"self-review", "independent-ai", "independent-human"}, "judge")
        for field in ("model_requested", "model_observed"):
            if judge.get(field) is not None:
                label(judge[field], "judge-model")
    seen: set[str] = set()
    for row in rows(value["cells"], "adjudication-cells"):
        row = closed(row, {"cell_id", "pass", "disagreement", "resolved"}, "score")
        cell = choice(row.get("cell_id"), MATRIX, "score-cell")
        require(cell not in seen, "score:duplicate-cell")
        seen.add(cell)
        for key in ("pass", "disagreement", "resolved"):
            boolean(row.get(key), "score")
        require(
            row.get("resolved") is not True or row.get("disagreement") is True,
            "score:resolution-without-disagreement",
        )
    return value


def audit(value: Any) -> dict[str, Any]:
    value = summary_header(value, {"checks"}, "audit", {"NOT_RUN", "PARTIAL", "PASS", "FAIL"})
    value.setdefault("checks", [])
    seen: set[str] = set()
    for row in rows(value["checks"], "audit-checks", 100):
        row = closed(row, {"check_id", "status"}, "audit-check")
        key = label(row.get("check_id"), "audit-check")
        require(key not in seen, "audit:duplicate-check")
        seen.add(key)
        choice(row.get("status"), {"NOT_RUN", "PASS", "FAIL", "UNKNOWN"}, "audit-check")
    return value


def parse(value: Any) -> dict[str, Any]:
    value = closed(
        value,
        {
            "schema_version",
            "study_id",
            "retention",
            "identity",
            "sources",
            "freeze",
            "assignments",
            "results",
            "usage",
            "adjudication",
            "audit",
        },
        "input",
    )
    require(
        type(value.get("schema_version", 1)) is int and value.get("schema_version", 1) == 1,
        "input:unsupported-schema",
    )
    require(value.get("study_id", "swarm-20261015") == "swarm-20261015", "input:study-mismatch")
    require(value.get("retention") in (None, "public-synthetic-only"), "input:retention-mismatch")
    refs = closed(value.get("sources", {}), SOURCE_KINDS, "sources")
    output = {
        "identity": identity(value.get("identity", {})),
        "sources": {k: source_ref(v) for k, v in refs.items()},
        "freeze": freeze(value.get("freeze", {})),
        "assignments": assignments(value.get("assignments", [])),
        "results": results(value.get("results", [])),
        "usage": usage(value.get("usage", {})),
        "adjudication": adjudication(value.get("adjudication", {})),
        "audit": audit(value.get("audit", {})),
    }
    if output["results"]:
        require(
            value.get("retention") == "public-synthetic-only" and "results" in refs,
            "input:public-result-provenance-required",
        )
    return output


def metric(rows_: list[dict[str, Any]], name: str) -> dict[str, Any]:
    attempted = [r for r in rows_ if has_attempt(r)]
    observed = [r[name] for r in attempted if r[name] is not None]
    complete = bool(attempted) and len(observed) == len(attempted)
    return {
        "observed_cells": len(observed),
        "attempted_denominator": len(attempted),
        "observed_total": sum(observed) if observed else None,
        "total": sum(observed) if complete else None,
        "mean": sum(observed) / len(observed) if complete else None,
        "reason": None if complete else "no-attempts-or-incomplete-coverage",
    }


def score_summary(rows_: list[dict[str, Any]], scores: dict[str, Any]) -> dict[str, Any]:  # noqa: C901 - explicit P/F/U dispositions
    attempted = [r for r in rows_ if has_attempt(r)]
    passed = 0
    failed = 0
    unavailable = 0
    pending = 0
    for row in attempted:
        score = scores.get(row["cell_id"], {})
        if row["status"] in {"FAILED", "TIMEOUT"}:
            require(score.get("pass") is not True, "score:failed-attempt-cannot-pass")
            unavailable += 1
        elif row["status"] != "COMPLETED":
            require(score.get("pass") is not True, "score:nonfinal-attempt-cannot-pass")
            unavailable += 1
        elif score.get("pass") is None or (
            score.get("disagreement") is True and score.get("resolved") is not True
        ):
            if row["public_answer_available"]:
                pending += 1
            else:
                unavailable += 1
        elif score.get("pass") is False:
            failed += 1
        elif score.get("pass") is True:
            require(
                row["status"] == "COMPLETED"
                and row["task_complete"] is True
                and not row["critical_error_labels"]
                and row["public_answer_available"],
                "score:critical-error-or-incomplete-pass",
            )
            passed += 1
    unknown = unavailable + pending
    return {
        "planned_denominator": len(rows_),
        "attempted_denominator": len(attempted),
        "passed": passed if attempted else None,
        "failed_completed": failed if attempted else None,
        "execution_unavailable": unavailable if attempted else None,
        "completed_score_pending": pending if attempted else None,
        "unresolved_or_unscored": unknown if attempted else None,
        "pass_fraction": passed / len(attempted) if attempted and unknown == 0 else None,
        "observed_success_fraction": passed / len(attempted) if attempted else None,
        "success_across_assignment": passed / len(rows_) if attempted and rows_ else None,
        "attempt_coverage": len(attempted) / len(rows_) if rows_ else None,
        "missing_score_bounds": [passed / len(attempted), (passed + pending) / len(attempted)]
        if attempted
        else None,
        "observed_critical_cells": sum(bool(r["critical_error_labels"]) for r in attempted)
        if attempted
        else None,
        "critical_label_counts": dict(
            sorted(
                Counter(
                    label_ for r in attempted for label_ in set(r["critical_error_labels"])
                ).items()
            )
        ),
        "critical_absence": "unverified-unless-adjudicated",
        "reason": "conditional-observation-only" if attempted else "experiment-not-run",
    }


def blockers(data: dict[str, Any], scores: dict[str, Any]) -> list[str]:  # noqa: C901 - explicit coverage gates
    missing = []
    frozen = data["freeze"]
    sha = data["identity"]["source_sha"]
    if (
        frozen["state"] != "FROZEN"
        or frozen["isolation_state"] != "VERIFIED"
        or frozen["frozen_at"] is None
        or frozen["approved_by"] != "S001"
        or not frozen["input_files"]
        or sha is None
        or frozen["source_sha"] != sha
    ):
        missing.append("freeze-or-isolation-not-established")
    starts = [r["started_at"] for r in data["results"] if has_attempt(r)]
    if starts and (None in starts or frozen["frozen_at"] is None):
        missing.append("pre-outcome-freeze-time-unverified")
    elif starts and any(
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        < datetime.fromisoformat(frozen["frozen_at"].replace("Z", "+00:00"))
        for s in starts
    ):
        missing.append("attempt-precedes-freeze")
    if any(r["ended_at"] is None for r in data["results"] if r["status"] in TERMINAL):
        missing.append("terminal-result-time-unverified")
    if len(data["assignments"]) != 54:
        missing.append("assignment-ledger-incomplete")
    for kind in ("usage", "adjudication", "audit"):
        expected = "PASS" if kind == "audit" else "COMPLETE"
        if data[kind]["state"] != expected or sha is None or data[kind].get("source_sha") != sha:
            missing.append(kind + "-not-complete-at-source")
    if not data["audit"]["checks"] or any(c["status"] != "PASS" for c in data["audit"]["checks"]):
        missing.append("audit-checks-not-passed")
    if set(data["sources"]) != SOURCE_KINDS:
        missing.append("public-source-references-incomplete")
    for row in data["results"]:
        item_sha = row["identity"]["source_sha"]
        if has_attempt(row) and (sha is None or item_sha != sha):
            missing.append("result-source-identity-unverified")
            break
    if len(scores) != 54 or not data["adjudication"]["judges"]:
        missing.append("adjudication-coverage-or-provenance-incomplete")
    return missing


def group_summary(rows_: list[dict[str, Any]], scores: dict[str, Any]) -> dict[str, Any]:
    observations = {}
    for name in ("task_complete", "entry_emitted", "canonical_full_read"):
        observations[name] = {
            "true": sum(r.get(name) is True for r in rows_),
            "false": sum(r.get(name) is False for r in rows_),
            "unknown": sum(r.get(name) is None for r in rows_),
        }
    return {
        "score": score_summary(rows_, scores),
        "metrics": {k: metric(rows_, k) for k in METRICS},
        "observations": observations,
    }


def contrasts(strata: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    index = {(r["family"], r["locale"], r["arm"]): r["score"] for r in strata}
    for family in FAMILIES:
        for locale in LOCALES:
            for left, right in (
                ("native-opensocrates", "plain"),
                ("native-opensocrates", "general-check"),
                ("general-check", "plain"),
            ):
                a, b = index[family, locale, left], index[family, locale, right]
                complete = (
                    a["attempted_denominator"] == b["attempted_denominator"] == 3
                    and a["unresolved_or_unscored"] == b["unresolved_or_unscored"] == 0
                )
                difference = a["passed"] - b["passed"] if complete else None
                output.append(
                    {
                        "family": family,
                        "locale": locale,
                        "left": left,
                        "right": right,
                        "left_attempted": a["attempted_denominator"],
                        "right_attempted": b["attempted_denominator"],
                        "pass_count_difference": difference,
                        "percentage_point_difference": difference / 3 * 100
                        if difference is not None
                        else None,
                        "reason": "conditional-count-contrast-only"
                        if complete
                        else "incomplete-or-unresolved-stratum",
                    }
                )
    return output


def build(data: dict[str, Any]) -> dict[str, Any]:  # noqa: C901 - fixed-matrix report assembly
    actual = {r["cell_id"]: r for r in data["results"]}
    planned = {r["cell_id"]: r for r in data["assignments"]}
    all_rows = []
    for cell in MATRIX:
        declared = planned.get(cell, {}).get("status", "MISSING")
        placeholder = {
            "cell_id": cell,
            "status": declared,
            "task_complete": None,
            "critical_error_labels": [],
            "public_answer_available": False,
            **{k: None for k in METRICS},
        }
        row = actual.get(cell, placeholder)
        require(
            declared not in ATTEMPTED or has_attempt(row), "ledger:attempt-evidence-contradiction"
        )
        all_rows.append(row)
    scores = {r["cell_id"]: r for r in data["adjudication"]["cells"]}
    for cell in scores:
        require(cell in actual and has_attempt(actual[cell]), "score:unattempted-cell")
    counts = Counter(r["status"] for r in all_rows)
    attempted = sum(has_attempt(r) for r in all_rows)
    metrics = {k: metric(all_rows, k) for k in METRICS}
    for key in METRICS:
        if key in data["usage"]:
            supplied = data["usage"][key]
            require(
                supplied.get("observed_total") == metrics[key]["observed_total"]
                and supplied.get("observed_cells") == metrics[key]["observed_cells"],
                "usage:aggregate-result-mismatch",
            )
    score = score_summary(all_rows, scores)
    gaps = blockers(data, scores)
    if sum(counts[s] for s in TERMINAL) != 54:
        gaps.append("terminal-result-coverage-incomplete")
    if len(actual) != 54:
        gaps.append("result-records-incomplete")
    if score["unresolved_or_unscored"]:
        gaps.append("scores-incomplete-or-disputed")
    status = "NOT_RUN" if not attempted else ("PARTIAL" if gaps else "COMPLETE")
    strata = []
    for family in FAMILIES:
        for locale in LOCALES:
            for arm in ARMS:
                subset = [
                    r
                    for r in all_rows
                    if all(
                        MATRIX[r["cell_id"]][k] == v
                        for k, v in (("family", family), ("locale", locale), ("arm", arm))
                    )
                ]
                strata.append(
                    {
                        "family": family,
                        "locale": locale,
                        "arm": arm,
                        "planned_cells": 3,
                        **group_summary(subset, scores),
                    }
                )
    groups = {}
    for dimension, values in (("family", FAMILIES), ("locale", LOCALES), ("arm", ARMS)):
        groups[dimension] = {
            v: group_summary([r for r in all_rows if MATRIX[r["cell_id"]][dimension] == v], scores)
            for v in values
        }
    cell_details = []
    for row in all_rows:
        cell = row["cell_id"]
        decision = scores.get(cell, {})
        verdict = decision.get("pass")
        if decision.get("disagreement") is True and decision.get("resolved") is not True:
            verdict = None
        detail = {
            "cell_id": cell,
            **MATRIX[cell],
            "order_index": planned.get(cell, {}).get("order_index"),
            "status": row["status"] if row["status"] != "MISSING" else None,
            "status_reason": "unrecorded" if row["status"] == "MISSING" else None,
            "result_record_present": cell in actual,
            "score": verdict,
            "disagreement": decision.get("disagreement"),
            "resolved": decision.get("resolved"),
            "critical_error_labels": row["critical_error_labels"],
            "failure_reason": row.get("failure_reason"),
            "started_at": row.get("started_at"),
            "ended_at": row.get("ended_at"),
            "task_complete": row.get("task_complete"),
            "entry_emitted": row.get("entry_emitted"),
            "canonical_full_read": row.get("canonical_full_read"),
            "application_evidence": "unverified",
            "source_sha": row.get("identity", {}).get("source_sha"),
            **{k: row[k] for k in METRICS},
        }
        cell_details.append(detail)
    judges = data["adjudication"]["judges"]
    disputed = [r for r in scores.values() if r.get("disagreement") is True]
    return {
        "schema_version": 1,
        "study_id": "swarm-20261015",
        "status": status,
        "status_meaning": "report-data-coverage-only-not-efficacy",
        "assigned_baseline_sha": BASE_SHA,
        "identity": data["identity"],
        "baseline_relation": "unknown"
        if data["identity"]["source_sha"] is None
        else ("same" if data["identity"]["source_sha"] == BASE_SHA else "different"),
        "fixed_design": {
            "families": list(FAMILIES),
            "locales": list(LOCALES),
            "arms": list(ARMS),
            "repeats": [1, 2, 3],
            "actor_budget": 54,
            "execution_owner": "S078",
            "reruns_permitted": False,
            "authoring_chats_are_controls": False,
        },
        "freeze": data["freeze"],
        "sources": data["sources"],
        "counts": {s: counts[s] for s in sorted(STATUSES)},
        "attempted": attempted,
        "attempted_status_counts": dict(
            sorted(Counter(r["status"] for r in all_rows if has_attempt(r)).items())
        ),
        "missing_result_records": 54 - len(actual),
        "unrecorded_status_cells": counts["MISSING"],
        "score": score,
        "metrics": metrics,
        "strata": strata,
        "groups": groups,
        "contrasts": contrasts(strata),
        "cells": cell_details,
        "adjudication": {
            "state": data["adjudication"]["state"],
            "judges": judges,
            "independent_evaluator": any(j["kind"] != "self-review" for j in judges)
            if judges
            else None,
            "disagreements": len(disputed) if attempted and scores else None,
            "unresolved_disagreements": sum(r.get("resolved") is not True for r in disputed)
            if attempted and scores
            else None,
        },
        "audit": data["audit"],
        "coverage_gaps": sorted(set(gaps)),
        "evidence_levels": {
            "implementation": "report-tool-only",
            "local_validation": None,
            "release_qualification": None,
            "live_attempts_recorded": bool(attempted),
            "efficacy": None,
            "reason": "neither-generated-reports-nor-coverage-prove-efficacy",
        },
        "failure_categories": dict(
            sorted(
                Counter(r["failure_reason"] for r in actual.values() if r["failure_reason"]).items()
            )
        ),
        "publication": {"state": "BLOCKED", "reason": "separate-exact-bundle-review-required"},
        "public_answer_references": [
            {"cell_id": r["cell_id"], "path": data["sources"]["results"]["path"]}
            for r in actual.values()
            if r["public_answer_available"]
        ],
    }


def display(value: Any) -> str:
    if value is None:
        return "unknown / 미확인"
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def render(summary: dict[str, Any]) -> str:  # noqa: C901 - bilingual report sections
    lines = [
        "# Exploratory study draft / 탐색적 실험 보고서 초안",
        "",
        f"Status / 상태: **{summary['status']}**",
        "",
        "Status describes record coverage only. It does not establish better answers, savings, "
        "or proven efficacy. / 상태는 기록의 완결성만 나타내며 더 나은 답변, 절감 또는 효과 입증을 뜻하지 않습니다.",
        "NOT_RUN means no actor attempt is recorded in this input; missing records are unknown. "
        "/ NOT_RUN은 이 입력에 기록된 actor 시도가 없다는 뜻이며 누락 기록의 실제 상태는 미확인입니다.",
        "",
        "## Fixed conditions / 고정 조건",
        "",
        "3 task families × EN/KO × 3 arms × 3 repeats = 54 single-turn actor answers. "
        "S078 owns execution. No favorable reruns; failures and timeouts stay in the attempted denominator. "
        "/ 3과제 × 영한 × 3조건 × 3반복 = 단일턴 답변 54개. 실행 담당은 S078이며 "
        "유리한 재실행 및 실패·시간초과의 분모 제외를 허용하지 않습니다.",
        "",
        "Arms / 조건: plain; general-check; native-opensocrates.",
        "",
        "The 100 authoring chats are not experimental controls. Historical studies are not current outcomes. "
        "/ 작성 채팅 100개는 실험 대조군이 아니며 과거 연구는 이번 결과가 아닙니다.",
        "",
        f"Assigned baseline / 배정 기준: `{BASE_SHA}`.",
        f"Reported source / 보고 원본: {display(summary['identity']['source_sha'])}.",
        f"Baseline relation / 기준과 관계: {summary['baseline_relation']}.",
        f"Freeze / 동결: {summary['freeze']['state']}; isolation / 격리: "
        f"{summary['freeze']['isolation_state']}.",
        "",
        "## Evidence levels / 증거 수준",
        "",
        "Implementation: report tool only. Local validation and release qualification: unknown. "
        "Efficacy: unknown. / 구현: 보고 도구만 해당. 로컬 검증·릴리스 적격성·효과: 미확인.",
        "",
        f"Recorded actor attempts / 기록된 actor 시도: {summary['attempted']}.",
        "",
        "| Identity / 식별 항목 | Reported value / 보고값 | Unknown reason / 미확인 사유 |",
        "| --- | --- | --- |",
    ]
    for key in sorted(IDENTITY_FIELDS):
        lines.append(
            f"| {key} | {display(summary['identity'][key])} | "
            f"{summary['identity'].get('unknown_reasons', {}).get(key, '—')} |"
        )
    lines += [
        "",
        "## Failures and missing attempts / 실패와 미실행",
        "",
        "| Status / 상태 | Cells / 셀 |",
        "| --- | ---: |",
    ]
    lines += [f"| {key} | {count} |" for key, count in summary["counts"].items()]
    lines += [
        f"| Missing result records / 결과 기록 누락 | {summary['missing_result_records']} |",
        f"| Unrecorded status / 상태 미확인 | {summary['unrecorded_status_cells']} |",
    ]
    lines += [
        "",
        "Failure categories are labels only; raw errors are not retained. "
        "/ 실패는 범주만 보존하며 원시 오류를 보존하지 않습니다.",
        "",
    ]
    lines += [f"- {key}: {count}" for key, count in summary["failure_categories"].items()]
    lines += [
        "",
        "## Metrics / 지표",
        "",
        "All quality and cost observations are conditional on these fixed tasks. "
        "Missing usage is unknown, never zero. / 품질·비용 관찰은 고정 과제 조건에 한정되며 "
        "누락된 사용량은 0이 아닌 미확인입니다.",
        "",
        "| Metric / 지표 | Observed value / 관측값 | Coverage / 관측 범위 |",
        "| --- | --- | --- |",
        f"| Observed successful attempts P/A | {display(summary['score']['observed_success_fraction'])} | "
        f"P={display(summary['score']['passed'])}, A={summary['score']['attempted_denominator']} |",
        f"| P / fixed assignment | {display(summary['score']['success_across_assignment'])} | S=54 |",
        f"| Completed failures F | {display(summary['score']['failed_completed'])} | "
        "adjudicated / 판정됨 |",
        f"| Unscored or unavailable U | {display(summary['score']['unresolved_or_unscored'])} | "
        "retained in A / A에 포함 |",
        f"| Observed critical cells | {display(summary['score']['observed_critical_cells'])} | "
        "missing assessment is unknown / 누락 평가는 미확인 |",
    ]
    for key, item in summary["metrics"].items():
        lines.append(
            f"| {key} observed total | {display(item['observed_total'])} | "
            f"{item['observed_cells']}/{item['attempted_denominator']} |"
        )
    lines += [
        "",
        "Partial observed totals are not full-interaction cost. Missing-score bounds "
        "in summary.json are logical bounds, not confidence intervals. / 부분 관측 합계는 "
        "전체 상호작용 비용이 아닙니다. summary.json의 미채점 범위는 논리적 범위이며 신뢰구간이 아닙니다.",
    ]
    lines += [
        "",
        "| Family / 과제 | Locale / 언어 | Arm / 조건 | Attempts / 시도 | "
        "Pass fraction / 통과 비율 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in summary["strata"]:
        lines.append(
            f"| {row['family']} | {row['locale']} | {row['arm']} | "
            f"{row['score']['attempted_denominator']} | "
            f"{display(row['score']['pass_fraction'])} |"
        )
    lines += [
        "",
        "Conditional contrasts appear only with all three attempts adjudicated in "
        "both arms; unknown contrasts remain unknown. / 두 조건 모두 3시도 판정이 끝난 "
        "경우에만 조건부 차이를 표시하며 그 외에는 미확인입니다.",
        "",
        "| Family / 과제 | Locale / 언어 | Contrast / 대비 | Pass count difference / 통과 수 차이 |",
        "| --- | --- | --- | --- |",
    ]
    for row in summary["contrasts"]:
        lines.append(
            f"| {row['family']} | {row['locale']} | {row['left']} vs {row['right']} | "
            f"{display(row['pass_count_difference'])} |"
        )
    lines += [
        "",
        "## Every planned cell / 전체 계획 셀",
        "",
        "Assignment order is not a paired random seed. Detailed public observations and "
        "usage are in summary.json. / 배정 순서는 쌍별 난수가 아닙니다. 공개 관찰·사용량 "
        "세부 기록은 summary.json에 있습니다.",
        "",
        "| Cell | Order / 순서 | Status / 상태 | Score / 점수 | Critical labels / 치명 오류 라벨 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in sorted(summary["cells"], key=lambda r: (r["order_index"] or 55, r["cell_id"])):
        lines.append(
            f"| {row['cell_id']} | {display(row['order_index'])} | {display(row['status'])} | "
            f"{display(row['score'])} | {', '.join(row['critical_error_labels']) or '—'} |"
        )
    lines += [
        "",
        "## Disagreements and evaluation / 이견과 평가",
        "",
        f"Independent evaluator reported / 독립 평가자 보고: "
        f"{display(summary['adjudication']['independent_evaluator'])}.",
        f"Disagreements / 이견: {display(summary['adjudication']['disagreements'])}; "
        f"unresolved / 미해결: {display(summary['adjudication']['unresolved_disagreements'])}.",
        "Self-review does not establish independent evaluation. Backend model identity is "
        "unknown unless observed; requested identity is separate. / 자기 검토는 독립 평가가 아닙니다. "
        "백엔드 모델은 관측되지 않으면 미확인이며 요청 모델과 구분합니다.",
        "",
        f"Audit / 감사: {summary['audit']['state']}.",
        "",
        "## Limitations / 한계",
        "",
        "Installation, entry emission, full canonical reading, application and usefulness "
        "are separate claims. Native installation is not manual canonical injection. "
        "No native application receipt is created. / 설치·진입 안내·정본 전체 읽기·적용·유용성은 "
        "별도 주장입니다. 네이티브 설치와 수동 정본 주입은 구분하며 네이티브 적용 영수증을 만들지 않습니다.",
        "",
        "Public answer bodies are omitted and are not hashed; only supplied public artifact "
        "digests and source locations are retained. Publication is BLOCKED pending a separate "
        "review of the exact bundle. This renderer cannot verify synthetic provenance, blinding, "
        "historical execution or causal effects. / 공개 답변 본문은 복사·해시하지 않으며 공급된 "
        "공개 산출물 해시와 출처 위치만 보존합니다. 별도 정확한 묶음 검토 전 공개는 BLOCKED입니다. "
        "생성기만으로 합성 출처·눈가림·실제 실행 이력·인과 효과를 검증할 수 없습니다.",
        "",
    ]
    lines += [f"- {gap}" for gap in summary["coverage_gaps"]]
    lines += ["", "## Next decisions / 다음 결정", ""]
    if summary["status"] == "NOT_RUN":
        lines += [
            "Freeze the protocol, input hashes, isolation and finite budget before any actor call. "
            "Only S078 may execute after central authorization. No efficacy decision is available. "
            "/ actor 호출 전에 프로토콜·입력 해시·격리·유한 예산을 동결합니다. 중앙 승인 후 S078만 "
            "실행하며 현재 효능 판단은 미확인입니다."
        ]
    else:
        lines += [
            "Resolve coverage and audit gaps without rerunning favorable outcomes or "
            "rewriting the frozen protocol. Use task-specific observations to design a separately "
            "frozen follow-up; no superiority conclusion is generated. / 유리한 결과 재실행이나 "
            "동결 프로토콜 변경 없이 누락·감사 문제를 해결합니다. 과제별 관찰로 별도 동결한 "
            "후속 실험을 설계하며 우월성 결론은 자동 생성하지 않습니다."
        ]
    lines += ["", "## Public source references / 공개 출처", ""]
    if not summary["sources"]:
        lines += ["unknown / 미확인"]
    for key, ref in sorted(summary["sources"].items()):
        lines.append(f"- {key}: `{ref['path']}`; SHA-256 `{ref['sha256']}`")
    return "\n".join(lines) + "\n"


def no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output = {}
    for key, value in pairs:
        require(key not in output, "input:duplicate-json-key")
        output[key] = value
    return output


def reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        require(not component.is_symlink(), "filesystem:symlink-refused")


def publish(output: Path, summary: dict[str, Any]) -> None:
    reject_links(output)
    require(not output.exists(), "output:already-exists")
    require(output.parent.is_dir(), "output:parent-directory-required")
    staging = Path(tempfile.mkdtemp(prefix=".swarm-report-", dir=output.parent))
    try:
        (staging / "study-report.md").write_text(render(summary), encoding="utf-8")
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        require(not output.exists(), "output:already-exists")
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--input", required=True, type=Path, help="Explicit public-only report projection JSON"
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New directory for study-report.md and summary.json",
    )
    args = parser.parse_args()
    try:
        reject_links(args.input)
        info = args.input.stat()
        require(
            stat.S_ISREG(info.st_mode) and info.st_size <= MAX_INPUT_BYTES,
            "input:regular-file-size-limit",
        )
        with args.input.open(encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=no_duplicate_keys)
        summary = build(parse(value))
        publish(args.output, summary)
    except ReportInputError as exc:
        parser.exit(2, f"swarm-study-report: {exc}\n")
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, OverflowError):
        parser.exit(2, "swarm-study-report: input-or-output-unavailable-or-malformed\n")
    print(f"swarm-study-report: {summary['status']}; study-report.md and summary.json written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
