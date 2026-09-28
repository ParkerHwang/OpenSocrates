"""Closed orchestration contracts and cross-field plan validation."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

from ..project_memory.contracts import validate
from .paths import BoundaryError, encoded, ownership, relative, root_path

MAX_REQUEST = 262144
MAX_ASSIGNMENT = 524288
MAX_RESPONSE = 16777216
MAX_OUTPUT = 262144
RESPONSE_SCHEMA = "opensocrates.orchestration.response/1.0.0"


def assets_root() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    return Path(frozen) if isinstance(frozen, str) else Path(__file__).resolve().parents[3]


def schema(kind: str) -> dict[str, Any]:
    if kind not in {"request", "assignment", "candidate", "assessment", "response"}:
        raise BoundaryError("unknown_schema")
    value = json.loads((assets_root() / f"schemas/v1/orchestration-{kind}.schema.json").read_text())
    if not isinstance(value, dict):
        raise BoundaryError("schema_unavailable")
    return value


def checked(value: Any, kind: str, budget: int) -> dict[str, Any]:
    if len(encoded(value)) > budget:
        raise BoundaryError("context_budget_exceeded")
    validate(value, schema(kind))
    return cast(dict[str, Any], value)


def _unique(items: list[str]) -> None:
    if len(items) != len(set(items)):
        raise BoundaryError("duplicate_identity")


def _unit(unit: dict[str, Any], units: set[str], sources: set[str], requirements: set[str]) -> None:  # noqa: C901  # Cross-field ownership, domain, and evidence contracts are explicit.
    for field in ("dependencies", "source_ids", "requirement_ids", "specialists"):
        _unique(unit[field])
    if not set(unit["dependencies"]) <= units or unit["unit_id"] in unit["dependencies"]:
        raise BoundaryError("invalid_dependency")
    if not set(unit["source_ids"]) <= sources or not set(unit["requirement_ids"]) <= requirements:
        raise BoundaryError("missing_input_identity")
    if unit["specialists"] and (unit["domain"] != "software" or unit["task_kind"] == "mechanical"):
        raise BoundaryError("inapplicable_specialist")
    if not any(item["required"] for item in unit["obligations"]):
        raise BoundaryError("required_acceptance_obligation_missing")
    obligations = {item["id"] for item in unit["obligations"]}
    _unique([item["id"] for item in unit["obligations"]])
    _unique([item["check_id"] for item in unit["checks"]])
    if any(item["requirement_id"] not in unit["requirement_ids"] for item in unit["obligations"]):
        raise BoundaryError("unowned_requirement")
    for check in unit["checks"]:
        _unique(check["obligation_ids"])
        if (
            not set(check["obligation_ids"]) <= obligations
            or not Path(check["argv"][0]).is_absolute()
        ):
            raise BoundaryError("invalid_check_scope")
        if any("\x00" in item for item in check["argv"]):
            raise BoundaryError("invalid_check_argv")
    if unit["seed"] is not None:
        candidate_files(unit["seed"]["files"], unit)


def order_units(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    done: set[str] = set()
    ordered: list[dict[str, Any]] = []
    while len(done) < len(units):
        ready = [
            unit
            for unit in units
            if unit["unit_id"] not in done and set(unit["dependencies"]) <= done
        ]
        if not ready:
            raise BoundaryError("dependency_cycle")
        ordered.extend(ready)
        done.update(unit["unit_id"] for unit in ready)
    return ordered


def plan(value: Any) -> dict[str, Any]:
    request = checked(value, "request", MAX_REQUEST)
    _unique([unit["unit_id"] for unit in request["units"]])
    _unique([item["id"] for item in request["constraints"]])
    _unique([item["id"] for item in request["sources"]])
    ownership([name for unit in request["units"] for name in unit["owned_paths"]])
    _unique(request["required_artifacts"])
    if not set(request["required_artifacts"]) <= {
        name for unit in request["units"] for name in unit["owned_paths"]
    }:
        raise BoundaryError("unowned_required_artifact")
    for source in request["sources"]:
        relative(source["path"])
    for unit in request["units"]:
        _unit(
            unit,
            {u["unit_id"] for u in request["units"]},
            {s["id"] for s in request["sources"]},
            {c["id"] for c in request["constraints"]},
        )
    order_units(request["units"])
    source_root = root_path(request["source_root"])
    target = root_path(request["candidate_root"], existing=False)
    if (
        target.exists()
        or not target.parent.is_dir()
        or target.is_relative_to(source_root)
        or source_root.is_relative_to(target)
    ):
        raise BoundaryError("candidate_root_must_be_new_and_separate")
    client = Path(request["client_path"])
    if not client.is_absolute():
        raise BoundaryError("invalid_client_path")
    if request["memory"] is not None:
        _unique(request["memory"]["record_ids"])
    return request


def candidate_files(files: list[dict[str, str]], unit: dict[str, Any]) -> dict[str, bytes]:
    names = [item["path"] for item in files]
    ownership(names)
    if set(names) != set(unit["owned_paths"]):
        raise BoundaryError("candidate_ownership_mismatch")
    result = {item["path"]: item["content"].encode("utf-8") for item in files}
    if (
        any(b"\x00" in value or len(value) > 65536 for value in result.values())
        or sum(map(len, result.values())) > MAX_OUTPUT
    ):
        raise BoundaryError("candidate_size_or_type")
    return result
