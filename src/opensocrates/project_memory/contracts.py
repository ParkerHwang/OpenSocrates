"""Closed wire validation against the shipped, generated v1.5 schemas."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


class ContractError(ValueError):
    """A request does not satisfy its closed public contract."""


_BASIS_REFERENCE = re.compile(r"^[a-z][a-z0-9_-]*:[A-Za-z0-9._/#-]{1,120}$")
_FORBIDDEN_BASIS_PREFIXES = frozenset(
    {
        "api_key",
        "password",
        "secret",
        "token",
        "prompt",
        "transcript",
        "credential",
        "cookie",
        "reasoning",
    }
)


def validate_basis_reference(value: Any) -> str:
    """Allow a short attribution pointer, never free-form instruction content."""
    if (
        not isinstance(value, str)
        or _BASIS_REFERENCE.fullmatch(value) is None
        or value.split(":", 1)[0] in _FORBIDDEN_BASIS_PREFIXES
    ):
        raise ContractError("authorization basis must be a bounded reference")
    return value


def _schema_root() -> Path:
    frozen = getattr(sys, "_MEIPASS", None)
    root = Path(frozen) if isinstance(frozen, str) else Path(__file__).resolve().parents[3]
    return root / "schemas" / "v1"


def load_schema(filename: str) -> dict[str, Any]:
    if filename not in {
        "project-memory-request.schema.json",
        "project-memory-response.schema.json",
        "project-memory-record.schema.json",
        "project-memory-snapshot.schema.json",
        "project-memory-context-pack.schema.json",
    }:
        raise ContractError("unknown schema")
    value = json.loads((_schema_root() / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("invalid installed schema")
    return value


def validate(value: Any, schema: dict[str, Any], *, path: str = "$") -> None:  # noqa: C901  # Closed recursive contract assertions.
    """Validate the supported closed schema vocabulary without external imports."""

    expected = schema.get("type")
    types = expected if isinstance(expected, list) else [expected] if expected else []
    if types:
        matched = False
        for kind in types:
            matched |= (
                (kind == "object" and isinstance(value, dict))
                or (kind == "array" and isinstance(value, list))
                or (kind == "string" and isinstance(value, str))
                or (kind == "boolean" and type(value) is bool)
                or (kind == "integer" and type(value) is int)
                or (kind == "null" and value is None)
            )
        if not matched:
            raise ContractError(f"{path}: invalid type")
    if "const" in schema and value != schema["const"]:
        raise ContractError(f"{path}: invalid constant")
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(f"{path}: invalid enum")
    if isinstance(value, dict):
        allowed = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(allowed):
            raise ContractError(f"{path}: unknown field")
        if set(schema.get("required", [])) - set(value):
            raise ContractError(f"{path}: required field missing")
        for name, item in value.items():
            if name in allowed:
                validate(item, allowed[name], path=f"{path}.{name}")
    elif isinstance(value, list):
        if len(value) > schema.get("maxItems", 1 << 30) or len(value) < schema.get("minItems", 0):
            raise ContractError(f"{path}: invalid array size")
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            validate(item, item_schema, path=f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) > schema.get("maxLength", 1 << 30) or len(value) < schema.get("minLength", 0):
            raise ContractError(f"{path}: invalid text length")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            raise ContractError(f"{path}: invalid text pattern")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ContractError(f"{path}: invalid timestamp") from error
    elif type(value) is int:
        if value < schema.get("minimum", -(1 << 63)) or value > schema.get("maximum", 1 << 63):
            raise ContractError(f"{path}: invalid integer range")


def validate_request(value: Any) -> dict[str, Any]:  # noqa: C901  # Closed operation envelopes require explicit branches.
    schema = load_schema("project-memory-request.schema.json")
    validate(value, schema)
    if not isinstance(value, dict):
        raise ContractError("request must be an object")
    operation = value["operation"]
    payload = value["payload"]
    required: dict[str, set[str]] = {
        "init": {"root", "apply", "mode", "capture_policy", "excluded_paths"},
        "status": set(),
        "observe": {"idempotency_key"},
        "record": {
            "idempotency_key",
            "expected_record_version",
            "kind",
            "scope",
            "summary",
            "origin",
            "support",
            "source_refs",
            "revalidation",
        },
        "accept": {
            "record_id",
            "expected_record_version",
            "idempotency_key",
            "acceptance_basis",
            "acceptance_attribution",
        },
        "checkpoint": {
            "idempotency_key",
            "expected_checkpoint_version",
            "objective",
            "constraints",
            "completion_conditions",
            "completed_actions",
            "remaining_actions",
            "next_action",
            "blockers",
            "decision_refs",
            "source_refs",
            "snapshot_id",
            "conflict_ids",
            "pending_effects",
            "parent_checkpoint_id",
        },
        "recall": {"need", "budget_bytes"},
        "refresh": {"idempotency_key"},
        "inspect": set(),
        "supersede": {
            "record_id",
            "new_record_id",
            "expected_record_version",
            "expected_new_record_version",
            "idempotency_key",
            "reason",
        },
        "export": {"format"},
        "disable": {"expected_policy_version", "idempotency_key"},
        "delete": {"intent", "idempotency_key"},
        "prune": {"dry_run", "retention_days"},
    }
    if not required[operation] <= set(payload):
        raise ContractError("operation payload is missing required fields")
    allowed: dict[str, set[str]] = {
        "init": required["init"]
        | {
            "disclosure_digest",
            "authorization_basis",
            "authorization_attribution",
            "expected_policy_version",
            "idempotency_key",
        },
        "status": {"root"},
        "observe": {"path", "symbol", "query", "scope_paths", "idempotency_key"},
        "record": required["record"] | {"record_id", "rationale", "snapshot_id", "conflict_ids"},
        "accept": required["accept"],
        "checkpoint": required["checkpoint"],
        "recall": required["recall"] | {"scope_paths"},
        "refresh": required["refresh"] | {"scope_paths"},
        "inspect": {"record_id"},
        "supersede": required["supersede"],
        "export": required["export"] | {"cursor"},
        "disable": required["disable"],
        "delete": required["delete"]
        | {"record_id", "expected_record_version", "expected_policy_version"},
        "prune": required["prune"] | {"idempotency_key"},
    }
    if set(payload) - allowed[operation]:
        raise ContractError("operation payload contains unrelated fields")
    if operation == "init" and payload["apply"]:
        if not {
            "disclosure_digest",
            "authorization_basis",
            "authorization_attribution",
            "idempotency_key",
        } <= set(payload):
            raise ContractError(
                "enrollment requires matching disclosure and attributed authorization"
            )
    if operation == "prune" and not payload["dry_run"] and "idempotency_key" not in payload:
        raise ContractError("prune apply requires an idempotency key")
    if operation == "observe" and (("path" in payload) == ("query" in payload)):
        raise ContractError("observe requires exactly one file path or search query")
    if operation != "init" and value["project_id"] is None and operation != "status":
        raise ContractError("registered project identity is required")
    if operation in {"checkpoint", "recall"} and value["workspace_id"] is None:
        raise ContractError("workspace identity is required")
    if operation == "checkpoint" and value["task_id"] is None:
        raise ContractError("task identity is required")
    return value


def response(
    request_id: str | None,
    status: str,
    result: Any = None,
    *,
    limitations: list[str] | None = None,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "schema": "opensocrates.project-memory.response/1.0.0",
        "request_id": request_id,
        "status": status,
        "result": result,
        "limitations": limitations or [],
        "retryable": retryable,
    }
