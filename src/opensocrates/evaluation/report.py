"""Allowlisted exports and descriptive per-cell denominators."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from .model import (
    FINAL_LIMIT,
    PHASES,
    LabError,
    boolean,
    cells,
    enum,
    fields,
    integer,
    text,
)
from .model import (
    identifier as safe_identifier,
)

EXPORT_LIMIT = 32 * 1024 * 1024


def _preference_counts() -> dict[str, int]:
    return {"A": 0, "B": 0, "C": 0, "tie": 0, "all_unusable": 0}


def _isolation_stratum(primary: list[dict[str, Any]]) -> str:
    records = [run["preflight"] for run in primary]
    if any(record is None for record in records):
        return "unresolved"
    if any(record["exploratory"] or record["isolation"] != "clear" for record in records):
        return "exploratory"
    return "attested_clear"


def _judgment_counts(
    state: dict[str, Any], groups: list[dict[str, Any]], primary: list[dict[str, Any]]
) -> dict[str, Any]:
    preferences = _preference_counts()
    strata = {
        name: _preference_counts() for name in ("attested_clear", "exploratory", "unresolved")
    }
    recognition = {"unknown": 0, "guessed": 0, "known": 0}
    for group in groups:
        judgment = state["judgments"].get(group["id"])
        if judgment:
            choice = judgment["choice"]
            key = group["mapping"].get(choice, choice)
            preferences[key] += 1
            records = [run for run in primary if run["group_id"] == group["id"]]
            strata[_isolation_stratum(records)][key] += 1
            recognition[judgment["recognition"]] += 1
    return {
        "preferences": preferences,
        "preferences_by_isolation": strata,
        "recognition_counts": recognition,
    }


def _cell_report(state: dict[str, Any], cell: dict[str, Any]) -> dict[str, Any]:
    runs = [run for run in state["runs"] if run["cell_id"] == cell["id"]]
    primary = [run for run in runs if run["attempt"] == 1]
    groups = [group for group in state["groups"] if group["cell_id"] == cell["id"]]
    counts = {
        status: sum(run["status"] == status for run in primary)
        for status in (
            "planned",
            "prepared",
            "running",
            "completed",
            "failed",
            "blocked",
            "aborted",
            "timed_out",
        )
    }
    preflights = [run["preflight"] for run in primary if run["preflight"] is not None]
    return {
        "cell_id": cell["id"],
        "primary_assigned": len(primary),
        "primary_status_counts": counts,
        "started_attempts": sum(bool(run["started_at"]) for run in runs),
        "retry_attempts": sum(run["attempt"] > 1 for run in runs),
        "groups": len(groups),
        "judged_groups": sum(group["judged"] for group in groups),
        "incomplete_groups": sum(group["status"] != "complete" for group in groups),
        "exploratory_primary": sum(
            record["exploratory"] or record["isolation"] == "unknown" for record in preflights
        ),
        "unknown_execution_mode_primary": sum(
            record["execution_mode"] == "unknown" for record in preflights
        ),
        **_judgment_counts(state, groups, primary),
    }


def report(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "cells": [_cell_report(state, cell) for cell in state["cells"]],
        "partial_blinding": True,
        "limitations": [
            "Single owner preferences are not general user or causal effect evidence.",
            "Cells are separate; no pooled quality, cost or token saving is inferred.",
            "Observed final-file arrival is not model completion or method application evidence.",
            "Model and isolation checks are operator attestations.",
        ],
    }


def make_export(state: dict[str, Any], answers: dict[str, str]) -> dict[str, Any]:
    runs = [
        {
            key: deepcopy(run[key])
            for key in (
                "id",
                "group_id",
                "cell_id",
                "case_id",
                "attempt",
                "status",
                "preflight",
                "started_at",
                "finished_at",
                "metrics",
            )
        }
        for run in state["runs"]
    ]
    groups = []
    for group in state["groups"]:
        item = {
            key: deepcopy(group[key])
            for key in (
                "id",
                "cell_id",
                "case_id",
                "status",
                "judged",
            )
        }
        if group["judged"]:
            item["mapping"] = deepcopy(group["mapping"])
        groups.append(item)
    return {
        "schema": "opensocrates.office-export/1",
        "study_id": state["study_id"],
        "pack": deepcopy(state["pack"]),
        "content_version": "1.5.3",
        "phase": state["phase"],
        "cells": deepcopy(state["cells"]),
        "criteria": deepcopy(state["criteria"]),
        "controller_environment": deepcopy(state["controller_environment"]),
        "runs": runs,
        "groups": groups,
        "judgments": deepcopy(state["judgments"]),
        "answers": answers,
        "report": report(state),
    }


def _opaque(value: Any) -> str:
    result = text(value, 24)
    if not re.fullmatch(r"[0-9a-f]{24}", result):
        raise LabError("invalid_export")
    return result


def _timestamp(value: Any) -> None:
    if value is not None and not re.fullmatch(r"[0-9T:.+Z-]{20,40}", text(value, 40)):
        raise LabError("invalid_export")


def _export_preflight(value: Any) -> None:
    if value is None:
        return
    options = {
        "observed_model": ("gpt-6-luna", "claude-haiku-5-5", "gemini-3.8-flash-medium", "unknown"),
        "observed_effort": ("max", "medium", "unknown"),
        "execution_mode": ("local", "cloud", "sync", "unknown"),
        "isolation": ("clear", "contaminated", "unknown"),
        "environment": ("fresh_os", "clean_snapshot", "new_user", "new_folder", "unknown"),
        "opensocrates": ("absent", "enabled", "unknown"),
    }
    keys = set(options) | {
        "host_version",
        "model_mapping_confirmed",
        "exploratory",
        "pack_approved",
    }
    fields(value, keys, keys)
    for key, allowed in options.items():
        enum(value[key], allowed)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}", text(value["host_version"], 64)):
        raise LabError("invalid_export")
    for key in ("model_mapping_confirmed", "exploratory", "pack_approved"):
        boolean(value[key])


def _export_metrics(value: Any) -> None:
    if value == {}:
        return
    keys = {"intake", "clarification_count", "delivery", "application", "tokens", "elapsed_seconds"}
    fields(value, keys, keys)
    enum(value["intake"], ("file", "manual"))
    integer(value["clarification_count"], 0, 100)
    enum(value["delivery"], ("observed", "operator_reported", "unknown"))
    enum(value["application"], ("self_reported", "unknown"))
    for key in ("tokens", "elapsed_seconds"):
        if value[key] is not None:
            integer(value[key], 0, 10**9)


def _export_runs(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = {
        "id",
        "group_id",
        "cell_id",
        "case_id",
        "attempt",
        "status",
        "preflight",
        "started_at",
        "finished_at",
        "metrics",
    }
    result: dict[str, dict[str, Any]] = {}
    allowed_cells = {cell["id"] for cell in data["cells"]}
    for run in data["runs"]:
        fields(run, keys, keys)
        run_id = _opaque(run["id"])
        if run_id in result or run["cell_id"] not in allowed_cells:
            raise LabError("invalid_export")
        _opaque(run["group_id"])
        safe_identifier(run["case_id"])
        integer(run["attempt"], 1, 360)
        enum(
            run["status"],
            (
                "planned",
                "prepared",
                "running",
                "completed",
                "failed",
                "blocked",
                "aborted",
                "timed_out",
            ),
        )
        _export_preflight(run["preflight"])
        _export_metrics(run["metrics"])
        _timestamp(run["started_at"])
        _timestamp(run["finished_at"])
        result[run_id] = run
    return result


def _export_groups(
    data: dict[str, Any], runs: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    keys = {"id", "cell_id", "case_id", "status", "judged"}
    groups: dict[str, dict[str, Any]] = {}
    for group in data["groups"]:
        fields(group, keys | {"mapping"}, keys)
        identifier = _opaque(group["id"])
        if identifier in groups:
            raise LabError("invalid_export")
        enum(group["status"], ("complete", "incomplete"))
        boolean(group["judged"])
        primary = [
            run for run in runs.values() if run["group_id"] == identifier and run["attempt"] == 1
        ]
        if len(primary) != 3 or any(
            run["cell_id"] != group["cell_id"] or run["case_id"] != group["case_id"]
            for run in primary
        ):
            raise LabError("invalid_export")
        _export_mapping(group)
        groups[identifier] = group
    if any(run["group_id"] not in groups for run in runs.values()):
        raise LabError("invalid_export")
    return groups


def _export_mapping(group: dict[str, Any]) -> None:
    if not group["judged"]:
        if "mapping" in group:
            raise LabError("invalid_export")
        return
    mapping = group.get("mapping")
    if not isinstance(mapping, dict) or sorted(mapping.values()) != ["A", "B", "C"]:
        raise LabError("invalid_export")
    if any(
        not isinstance(key, str) or not re.fullmatch(r"Answer-[0-9a-f]{8}", key) for key in mapping
    ):
        raise LabError("invalid_export")


def _export_judgments(data: dict[str, Any], groups: dict[str, dict[str, Any]]) -> None:
    keys = {
        "group_id",
        "choice",
        "first_reaction",
        "confidence",
        "recognition",
        "reproduced_experience",
        "created_at",
    }
    for identifier, judgment in data["judgments"].items():
        if identifier not in groups or not groups[identifier]["judged"]:
            raise LabError("invalid_export")
        fields(judgment, keys | {"edit"}, keys)
        if judgment["group_id"] != identifier:
            raise LabError("invalid_export")
        enum(judgment["choice"], (*groups[identifier]["mapping"], "tie", "all_unusable"))
        text(judgment["first_reaction"], 16000, empty=True)
        if len(judgment["first_reaction"]) > 4000:
            raise LabError("invalid_export")
        enum(judgment["confidence"], ("low", "medium", "high"))
        enum(judgment["recognition"], ("unknown", "guessed", "known"))
        enum(judgment["reproduced_experience"], ("yes", "no", "uncertain"))
        _timestamp(judgment["created_at"])
        if "edit" in judgment:
            text(judgment["edit"], FINAL_LIMIT, empty=True)
    if set(data["judgments"]) != {key for key, group in groups.items() if group["judged"]}:
        raise LabError("invalid_export")


def _export_header(data: dict[str, Any]) -> None:
    keys = {
        "schema",
        "study_id",
        "pack",
        "content_version",
        "phase",
        "cells",
        "criteria",
        "runs",
        "groups",
        "judgments",
        "answers",
        "report",
        "controller_environment",
    }
    fields(data, keys, keys)
    if data["schema"] != "opensocrates.office-export/1" or data["content_version"] != "1.5.3":
        raise LabError("invalid_export")
    _opaque(data["study_id"])
    fields(data["pack"], {"id", "version", "sha256"}, {"id", "version", "sha256"})
    safe_identifier(data["pack"]["id"])
    text(data["pack"]["version"], 100)
    if not re.fullmatch(r"[0-9a-f]{64}", text(data["pack"]["sha256"], 64)):
        raise LabError("invalid_export")
    enum(data["phase"], PHASES)
    environment = data["controller_environment"]
    fields(environment, {"os", "arch", "source"}, {"os", "arch", "source"})
    enum(environment["os"], ("macos", "windows", "unsupported"))
    enum(environment["arch"], ("arm64", "x64", "unknown"))
    enum(environment["source"], ("local_platform",))
    available = cells()
    if not isinstance(data["cells"], list) or not 1 <= len(data["cells"]) <= 6:
        raise LabError("invalid_export")
    if any(cell not in available for cell in data["cells"]):
        raise LabError("invalid_export")
    if len({cell["id"] for cell in data["cells"]}) != len(data["cells"]):
        raise LabError("invalid_export")


def _export_collections(data: dict[str, Any]) -> None:
    for key, maximum in (("runs", 360), ("groups", 60)):
        if not isinstance(data[key], list) or not 1 <= len(data[key]) <= maximum:
            raise LabError("invalid_export")
    for key in ("judgments", "answers", "report"):
        if not isinstance(data[key], dict):
            raise LabError("invalid_export")
    if data["criteria"] is not None:
        fields(
            data["criteria"],
            {"text", "discovery_reference", "created_at"},
            {"text", "discovery_reference", "created_at"},
        )
        text(data["criteria"]["text"], 16000)
        text(data["criteria"]["discovery_reference"], 1000)
        _timestamp(data["criteria"]["created_at"])


def validate_export(data: dict[str, Any]) -> dict[str, Any]:
    """Validate untrusted exported JSON, preserving only the exact closed schema."""
    try:
        if len(json.dumps(data, ensure_ascii=False).encode("utf-8")) > EXPORT_LIMIT:
            raise LabError("export_too_large")
        _export_header(data)
        _export_collections(data)
        runs = _export_runs(data)
        groups = _export_groups(data, runs)
        _export_judgments(data, groups)
        completed = {key for key, run in runs.items() if run["status"] == "completed"}
        if set(data["answers"]) != completed or len(completed) > 180:
            raise LabError("invalid_export")
        for answer in data["answers"].values():
            text(answer, FINAL_LIMIT)
        # A report cannot introduce undeclared text or private metadata: recompute it.
        if data["report"] != report(data):
            raise LabError("invalid_export")
        return deepcopy(data)
    except (TypeError, KeyError, ValueError, RecursionError) as exc:
        raise LabError("invalid_export") from exc
