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

    def __init__(
        self,
        message: str,
        *,
        code: str = "contract_violation",
        path: str = "$",
        allowed: tuple[Any, ...] = (),
        example: str | None = None,
    ) -> None:
        super().__init__(f"{path}: {message}" if path != "$" else message)
        self.code = code
        self.field_path = path
        self.allowed = allowed
        self.example = example

    def diagnostic(self) -> dict[str, Any]:
        """Only fixed codes and schema-derived paths, never input values/unknown keys."""
        return {
            "code": self.code,
            "field_path": self.field_path,
            **({"allowed_values": list(self.allowed)} if self.allowed else {}),
            **({"example": self.example} if self.example else {}),
        }


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
        "project-memory-request-v2.schema.json",
        "project-memory-context-pack-v2.schema.json",
        "assistance-request-v2.schema.json",
        "assistance-plan-v2.schema.json",
        "documentation-request.schema.json",
        "documentation-pack.schema.json",
    }:
        raise ContractError("unknown schema")
    value = json.loads((_schema_root() / filename).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ContractError("invalid installed schema")
    return value


def validate(value: Any, schema: dict[str, Any], *, path: str = "$") -> None:  # noqa: C901  # Closed recursive contract assertions.
    """Validate the supported closed schema vocabulary without external imports."""

    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            try:
                validate(value, candidate, path=path)
                return
            except ContractError:
                continue
        raise ContractError("invalid alternative", code="invalid_type", path=path)
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
            raise ContractError("invalid type", code="invalid_type", path=path)
    if "const" in schema and value != schema["const"]:
        raise ContractError(
            "invalid constant", code="invalid_constant", path=path, allowed=(schema["const"],)
        )
    if "enum" in schema and value not in schema["enum"]:
        raise ContractError(
            "invalid enum", code="invalid_enum", path=path, allowed=tuple(schema["enum"])
        )
    if isinstance(value, dict):
        allowed = schema.get("properties", {})
        if schema.get("additionalProperties") is False and set(value) - set(allowed):
            raise ContractError("unknown field", code="unknown_field", path=path)
        missing = sorted(set(schema.get("required", [])) - set(value))
        if missing:
            raise ContractError(
                "required field missing", code="missing_field", path=f"{path}.{missing[0]}"
            )
        for name, item in value.items():
            if name in allowed:
                validate(item, allowed[name], path=f"{path}.{name}")
    elif isinstance(value, list):
        if len(value) > schema.get("maxItems", 1 << 30) or len(value) < schema.get("minItems", 0):
            raise ContractError("invalid array size", code="invalid_size", path=path)
        item_schema = schema.get("items", {})
        for index, item in enumerate(value):
            validate(item, item_schema, path=f"{path}[{index}]")
    elif isinstance(value, str):
        if len(value) > schema.get("maxLength", 1 << 30) or len(value) < schema.get("minLength", 0):
            raise ContractError("invalid text length", code="invalid_size", path=path)
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            raise ContractError("invalid text pattern", code="invalid_pattern", path=path)
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ContractError(
                    "invalid timestamp", code="invalid_timestamp", path=path
                ) from error
    elif type(value) is int:
        if value < schema.get("minimum", -(1 << 63)) or value > schema.get("maximum", 1 << 63):
            raise ContractError("invalid integer range", code="invalid_range", path=path)


def validate_request(value: Any) -> dict[str, Any]:  # noqa: C901  # Closed operation envelopes require explicit branches.
    if (
        isinstance(value, dict)
        and value.get("schema") == "opensocrates.project-memory.request/1.0.0"
        and value.get("operation") == "prepare"
    ):
        raise ContractError(
            "prepare needs the versioned request",
            code="request_version_mismatch",
            path="$.schema",
            allowed=("opensocrates.project-memory.request/1.1.0",),
            example="references/assistance/memory-prepare.json",
        )
    revised = (
        isinstance(value, dict)
        and value.get("schema") == "opensocrates.project-memory.request/1.1.0"
    )
    schema = load_schema(
        "project-memory-request-v2.schema.json" if revised else "project-memory-request.schema.json"
    )
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
        "prepare": {"target_operation"},
    }
    if not required[operation] <= set(payload):
        missing = sorted(required[operation] - set(payload))
        raise ContractError(
            "operation payload is missing required fields",
            code="missing_field",
            path=f"$.payload.{missing[0]}",
        )
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
        "prepare": required["prepare"],
    }
    if set(payload) - allowed[operation]:
        raise ContractError(
            "operation payload contains unrelated fields", code="unrelated_field", path="$.payload"
        )
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
    if operation in {"checkpoint", "recall", "prepare"} and value["workspace_id"] is None:
        raise ContractError(
            "workspace identity is required", code="missing_identity", path="$.workspace_id"
        )
    if operation in {"checkpoint", "prepare"} and value["task_id"] is None:
        raise ContractError("task identity is required", code="missing_identity", path="$.task_id")
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
