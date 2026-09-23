"""Canonical closed v1.5 JSON contracts, generated into schemas/v1.

Operation-specific rules that JSON Schema cannot express without a discriminator
are also checked by the runtime. No schema in this module permits unknown keys.
"""

from __future__ import annotations

from typing import Any

UUID = {
    "type": "string",
    "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
}
TEXT = {"type": "string", "maxLength": 8192}
SHORT = {"type": "string", "maxLength": 1024}
PATH = {"type": "string", "minLength": 1, "maxLength": 1024}
DIGEST = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
TIME = {"type": "string", "format": "date-time"}
BOOL = {"type": "boolean"}
POSITIVE = {"type": "integer", "minimum": 1}
NONNEGATIVE = {"type": "integer", "minimum": 0}


def obj(properties: dict[str, Any], required: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(required),
    }


def arr(items: dict[str, Any], maximum: int = 32) -> dict[str, Any]:
    return {"type": "array", "items": items, "maxItems": maximum}


def nullable(schema: dict[str, Any]) -> dict[str, Any]:
    if "enum" in schema:
        return {"enum": [*schema["enum"], None]}
    return {"type": [schema["type"], "null"], **{k: v for k, v in schema.items() if k != "type"}}


TASK = obj(
    {
        "task_kind": {"enum": ["mechanical", "judgment"]},
        "task_family": {"enum": ["coding", "planning", "research", "writing", "other"]},
        "complexity": {"enum": ["bounded", "coupled"]},
        "stakes": {"enum": ["ordinary", "consequential"]},
        "uncertainty": {"enum": ["resolved", "bounded", "material"]},
        "context_need": {"enum": ["none", "current_evidence", "continuity"]},
        "completion": {"enum": ["in_progress", "checks_satisfied", "dependent_input_missing"]},
        "material_change": BOOL,
    },
    (
        "task_kind",
        "task_family",
        "complexity",
        "stakes",
        "uncertainty",
        "context_need",
        "completion",
        "material_change",
    ),
)
MODEL_CONTEXT = obj(
    {
        "model": nullable(SHORT),
        "effort": nullable(SHORT),
        "client": nullable(SHORT),
        "attribution": {
            "enum": ["host_reported", "operator_declared", "agent_reported", "unknown"]
        },
    },
    ("model", "effort", "client", "attribution"),
)
PROFILE_OVERRIDE = obj(
    {
        "profile_id": SHORT,
        "revision": POSITIVE,
        "authorization_basis": SHORT,
    },
    ("profile_id", "revision", "authorization_basis"),
)

SCOPE = obj(
    {
        "level": {"enum": ["project", "workspace", "task"]},
        "workspace_id": nullable(UUID),
        "task_id": nullable(UUID),
        "module_paths": arr(PATH),
    },
    ("level",),
)
ORIGIN = obj(
    {
        "producer_kind": {"enum": ["user", "maintainer", "agent", "runtime_observer", "import"]},
        "source_reference": nullable(SHORT),
        "attestation": {
            "enum": [
                "operator_declared",
                "agent_reported_user_instruction",
                "host_attested",
                "local_file_observation",
                "agent_reported",
                "imported",
            ]
        },
    },
    ("producer_kind", "source_reference", "attestation"),
)
LOCATOR = obj(
    {
        "path": PATH,
        "symbol": nullable(SHORT),
        "line_start": nullable(POSITIVE),
        "line_end": nullable(POSITIVE),
    },
    ("path",),
)
COVERAGE = obj(
    {
        "kind": {"enum": ["file", "definition", "search", "document", "decision"]},
        "complete_for_scope": BOOL,
        "scope": SHORT,
        "omitted": arr(SHORT),
    },
    ("kind", "complete_for_scope", "scope"),
)
SOURCE_REF = obj(
    {
        "ref_id": SHORT,
        "type": {
            "enum": [
                "source_file",
                "repository_document",
                "project_document",
                "tool_result",
                "decision_reference",
            ]
        },
        "locator": LOCATOR,
        "digest": DIGEST,
        "collected_at": TIME,
        "collector": SHORT,
        "coverage": COVERAGE,
    },
    ("ref_id", "type", "locator", "digest", "collected_at", "collector", "coverage"),
)
REVALIDATION = obj(
    {
        "dependency_paths": arr(PATH),
        "negative_claim": BOOL,
        "on_change": {"enum": ["refresh_or_mark_stale", "mark_stale", "not_applicable"]},
    },
    ("dependency_paths", "negative_claim", "on_change"),
)
ACTION = obj(
    {
        "action": SHORT,
        "execution_state": {"enum": ["not_started", "attempted", "completed", "unknown"]},
        "support": {
            "enum": ["runtime_observed", "tool_reported", "agent_reported", "inferred", "imported"]
        },
        "source_refs": arr(SHORT),
    },
    ("action", "execution_state", "support", "source_refs"),
)
EFFECT = obj(
    {
        "effect": SHORT,
        "state": {"enum": ["planned", "attempted", "confirmed", "unknown"]},
        "reference": nullable(SHORT),
    },
    ("effect", "state"),
)
CHECKPOINT = obj(
    {
        "objective": TEXT,
        "constraints": arr(SHORT),
        "completion_conditions": arr(SHORT),
        "completed_actions": arr(ACTION),
        "remaining_actions": arr(SHORT),
        "next_action": SHORT,
        "blockers": arr(SHORT),
        "decision_refs": arr(UUID),
        "source_refs": arr(SHORT),
        "snapshot_id": nullable(UUID),
        "conflict_ids": arr(UUID),
        "pending_effects": arr(EFFECT),
        "parent_checkpoint_id": nullable(UUID),
        "checkpoint_version": POSITIVE,
    },
    (
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
        "checkpoint_version",
    ),
)

MEMORY_PAYLOAD = obj(
    {
        "root": PATH,
        "apply": BOOL,
        "disclosure_digest": DIGEST,
        "authorization_basis": SHORT,
        "authorization_attribution": {
            "enum": ["operator_declared", "agent_reported_user_instruction"]
        },
        "mode": {"enum": ["read_only", "read_write"]},
        "capture_policy": {"enum": ["manual", "milestones"]},
        "excluded_paths": arr(PATH),
        "expected_policy_version": NONNEGATIVE,
        "record_id": UUID,
        "expected_record_version": NONNEGATIVE,
        "expected_new_record_version": POSITIVE,
        "expected_checkpoint_version": NONNEGATIVE,
        "idempotency_key": UUID,
        "kind": {"enum": ["decision", "observation", "lesson"]},
        "scope": SCOPE,
        "summary": TEXT,
        "rationale": nullable(TEXT),
        "source_refs": arr(SHORT),
        "snapshot_id": nullable(UUID),
        "revalidation": REVALIDATION,
        "origin": ORIGIN,
        "support": {"enum": ["agent_reported", "inferred", "imported"]},
        "acceptance_basis": SHORT,
        "acceptance_attribution": {
            "enum": ["operator_declared", "agent_reported_user_instruction"]
        },
        "new_record_id": UUID,
        "reason": SHORT,
        "objective": TEXT,
        "constraints": arr(SHORT),
        "completion_conditions": arr(SHORT),
        "completed_actions": arr(ACTION),
        "remaining_actions": arr(SHORT),
        "next_action": SHORT,
        "blockers": arr(SHORT),
        "decision_refs": arr(UUID),
        "conflict_ids": arr(UUID),
        "pending_effects": arr(EFFECT),
        "parent_checkpoint_id": nullable(UUID),
        "need": SHORT,
        "budget_bytes": {"type": "integer", "minimum": 1, "maximum": 65536},
        "scope_paths": arr(PATH),
        "path": PATH,
        "symbol": SHORT,
        "query": SHORT,
        "format": {"enum": ["json", "markdown"]},
        "cursor": nullable(SHORT),
        "intent": SHORT,
        "dry_run": BOOL,
        "retention_days": {"type": "integer", "minimum": 1, "maximum": 3650},
    },
    (),
)

SCHEMAS: dict[str, dict[str, Any]] = {
    "assistance-profiles.schema.json": obj(
        {
            "schema": {"const": "opensocrates.assistance.profiles/1.0.0"},
            "revision": POSITIVE,
            "profiles": arr(
                obj(
                    {
                        "profile_id": SHORT,
                        "revision": POSITIVE,
                        "state": {"enum": ["candidate", "validated", "withdrawn"]},
                        "model": SHORT,
                        "effort": SHORT,
                        "client": SHORT,
                        "task_families": arr(
                            {"enum": ["coding", "planning", "research", "writing", "other"]}, 5
                        ),
                        "observed_failure_categories": arr(SHORT),
                        "raise_to_structured": BOOL,
                        "optional_components": arr(
                            {"enum": ["evidence_need", "bounded_subgoal", "verification_target"]}, 3
                        ),
                        "evaluation_reference": SHORT,
                        "validation_reference": nullable(SHORT),
                    },
                    (
                        "profile_id",
                        "revision",
                        "state",
                        "model",
                        "effort",
                        "client",
                        "task_families",
                        "observed_failure_categories",
                        "raise_to_structured",
                        "optional_components",
                        "evaluation_reference",
                        "validation_reference",
                    ),
                ),
                32,
            ),
        },
        ("schema", "revision", "profiles"),
    ),
    "assistance-request.schema.json": obj(
        {
            "schema": {"const": "opensocrates.assistance.request/1.0.0"},
            "request_id": UUID,
            "locale": {"enum": ["en", "ko"]},
            "task": TASK,
            "model_context": MODEL_CONTEXT,
            "profile_override": nullable(PROFILE_OVERRIDE),
        },
        ("schema", "request_id", "locale", "task", "model_context"),
    ),
    "assistance-plan.schema.json": obj(
        {
            "schema": {"const": "opensocrates.assistance.plan/1.0.0"},
            "request_id": UUID,
            "status": {"enum": ["ok", "invalid_request", "unavailable"]},
            "assistance_level": nullable({"enum": ["none", "light", "structured"]}),
            "profile_id": nullable(SHORT),
            "profile_revision": nullable(POSITIVE),
            "profile_evidence": nullable(
                {"enum": ["task_default", "candidate_evaluation", "validated_run"]}
            ),
            "validation_reference": nullable(SHORT),
            "context_pack_budget_bytes": NONNEGATIVE,
            "guidance_components": arr(
                {
                    "enum": [
                        "goal",
                        "constraints",
                        "evidence_need",
                        "bounded_subgoal",
                        "verification_target",
                        "completion_cue",
                    ]
                },
                6,
            ),
            "reason_codes": arr(
                {
                    "enum": [
                        "mechanical",
                        "completed_unchanged",
                        "bounded_judgment",
                        "coupled_task",
                        "consequential_stakes",
                        "material_uncertainty",
                        "matched_support_rule",
                        "profile_fallback",
                        "dependency_missing",
                    ]
                },
                9,
            ),
            "next_action": nullable({"enum": ["continue", "finish", "resolve_dependency"]}),
            "limitations": arr(SHORT),
            "application": {"const": "unverified"},
        },
        ("schema", "request_id", "status", "limitations", "application"),
    ),
    "project-memory-request.schema.json": obj(
        {
            "schema": {"const": "opensocrates.project-memory.request/1.0.0"},
            "operation": {
                "enum": [
                    "init",
                    "status",
                    "observe",
                    "record",
                    "accept",
                    "checkpoint",
                    "recall",
                    "refresh",
                    "inspect",
                    "supersede",
                    "export",
                    "disable",
                    "delete",
                    "prune",
                ]
            },
            "request_id": UUID,
            "project_id": nullable(UUID),
            "workspace_id": nullable(UUID),
            "task_id": nullable(UUID),
            "payload": MEMORY_PAYLOAD,
        },
        ("schema", "operation", "request_id", "project_id", "workspace_id", "task_id", "payload"),
    ),
    "project-memory-response.schema.json": obj(
        {
            "schema": {"const": "opensocrates.project-memory.response/1.0.0"},
            "request_id": nullable(UUID),
            "status": {
                "enum": [
                    "ok",
                    "disabled",
                    "needs_refresh",
                    "partial",
                    "conflict",
                    "budget_insufficient",
                    "busy",
                    "unavailable",
                    "invalid_request",
                ]
            },
            "result": {},
            "limitations": arr(SHORT),
            "retryable": BOOL,
        },
        ("schema", "request_id", "status", "result", "limitations", "retryable"),
    ),
    "project-memory-record.schema.json": obj(
        {
            "schema": {"const": "opensocrates.project-memory.record/1.0.0"},
            "record_id": UUID,
            "version": POSITIVE,
            "project_id": UUID,
            "kind": {"enum": ["decision", "observation", "lesson", "checkpoint"]},
            "scope": SCOPE,
            "lifecycle": {"enum": ["proposed", "accepted", "superseded", "archived"]},
            "origin": ORIGIN,
            "support": {
                "enum": [
                    "runtime_observed",
                    "tool_reported",
                    "agent_reported",
                    "inferred",
                    "imported",
                ]
            },
            "freshness": {"enum": ["current", "stale", "unknown", "not_applicable"]},
            "summary": TEXT,
            "rationale": nullable(TEXT),
            "source_refs": arr(SOURCE_REF),
            "snapshot_id": nullable(UUID),
            "revalidation": REVALIDATION,
            "created_at": TIME,
            "updated_at": TIME,
            "supersedes": nullable(UUID),
            "conflict_ids": arr(UUID),
            "payload": nullable(CHECKPOINT),
        },
        (
            "schema",
            "record_id",
            "version",
            "project_id",
            "kind",
            "scope",
            "lifecycle",
            "origin",
            "support",
            "freshness",
            "summary",
            "rationale",
            "source_refs",
            "snapshot_id",
            "revalidation",
            "created_at",
            "updated_at",
            "supersedes",
            "conflict_ids",
            "payload",
        ),
    ),
    "project-memory-snapshot.schema.json": obj(
        {
            "schema": {"const": "opensocrates.project-memory.snapshot/1.0.0"},
            "snapshot_id": UUID,
            "project_id": UUID,
            "workspace_id": UUID,
            "workspace_kind": {"enum": ["git_worktree", "directory"]},
            "root_identity_digest": DIGEST,
            "head_oid": nullable(SHORT),
            "ref": nullable(SHORT),
            "status_digest": nullable({"type": "string", "pattern": "^[0-9a-f]{64}$"}),
            "dirty": nullable(BOOL),
            "scope_paths": arr(PATH),
            "inventory_digest": DIGEST,
            "content_manifest_digest": DIGEST,
            "exclusion_digest": DIGEST,
            "configuration_digest": DIGEST,
            "adapter_versions": obj({"local_source": SHORT}, ("local_source",)),
            "coverage": obj(
                {
                    "complete_for_scope": BOOL,
                    "omitted_categories": {"type": "object", "additionalProperties": NONNEGATIVE},
                    "unstable_files": arr(PATH),
                    "search_boundary": obj(
                        {"paths": arr(PATH), "file_types": {"const": "allowed_text_only"}},
                        ("paths", "file_types"),
                    ),
                    "dynamic_edges": {"enum": ["unknown", "not_applicable"]},
                },
                (
                    "complete_for_scope",
                    "omitted_categories",
                    "unstable_files",
                    "search_boundary",
                    "dynamic_edges",
                ),
            ),
            "captured_at": TIME,
            "files": {
                "type": "object",
                "additionalProperties": obj(
                    {
                        "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        "size": NONNEGATIVE,
                        "python": obj(
                            {
                                "parse_status": {"enum": ["ok", "unavailable"]},
                                "imports": arr(
                                    obj({"module": SHORT, "line": POSITIVE}, ("module", "line")),
                                    2000,
                                ),
                                "definitions": arr(
                                    obj(
                                        {
                                            "name": SHORT,
                                            "kind": {"enum": ["function", "class"]},
                                            "line": POSITIVE,
                                        },
                                        ("name", "kind", "line"),
                                    ),
                                    2000,
                                ),
                                "dynamic_edges": {"const": "unknown"},
                            },
                            ("parse_status", "imports", "definitions", "dynamic_edges"),
                        ),
                    },
                    ("sha256", "size"),
                ),
            },
        },
        (
            "schema",
            "snapshot_id",
            "project_id",
            "workspace_id",
            "workspace_kind",
            "root_identity_digest",
            "head_oid",
            "ref",
            "status_digest",
            "dirty",
            "scope_paths",
            "inventory_digest",
            "content_manifest_digest",
            "exclusion_digest",
            "configuration_digest",
            "adapter_versions",
            "coverage",
            "captured_at",
            "files",
        ),
    ),
    "project-memory-context-pack.schema.json": obj(
        {
            "schema": {"const": "opensocrates.project-memory.context-pack/1.0.0"},
            "pack_id": UUID,
            "project_id": UUID,
            "workspace_id": UUID,
            "task_id": nullable(UUID),
            "workspace_kind": {"enum": ["git_worktree", "directory"]},
            "checked_snapshot": nullable(UUID),
            "constraints": arr(
                obj(
                    {
                        "text": SHORT,
                        "record_id": UUID,
                        "freshness": {"enum": ["current", "stale", "unknown", "not_applicable"]},
                    },
                    ("text", "record_id", "freshness"),
                )
            ),
            "decisions": arr(
                obj(
                    {
                        "summary": SHORT,
                        "record_id": UUID,
                        "freshness": {"enum": ["current", "stale", "unknown", "not_applicable"]},
                    },
                    ("summary", "record_id", "freshness"),
                )
            ),
            "source_evidence": arr(SOURCE_REF),
            "checkpoint_reference": nullable(UUID),
            "conflicts": arr(UUID),
            "unknowns": arr(SHORT),
            "searched_scope": arr(PATH),
            "excluded_scope": arr(PATH),
            "capabilities": obj(
                {"text": {"const": "lexical"}, "python": {"enum": ["ast", "unavailable"]}},
                ("text", "python"),
            ),
            "budget_bytes": POSITIVE,
            "used_bytes": NONNEGATIVE,
            "expansion_handle": nullable(SHORT),
            "delivery": {"const": "emitted"},
            "application": {"const": "unverified"},
        },
        (
            "schema",
            "pack_id",
            "project_id",
            "workspace_id",
            "task_id",
            "workspace_kind",
            "checked_snapshot",
            "constraints",
            "decisions",
            "source_evidence",
            "checkpoint_reference",
            "conflicts",
            "unknowns",
            "searched_scope",
            "excluded_scope",
            "capabilities",
            "budget_bytes",
            "used_bytes",
            "expansion_handle",
            "delivery",
            "application",
        ),
    ),
}

IDENTITIES = {
    "assistance-profiles.schema.json": "opensocrates.assistance.profiles/1.0.0",
    "assistance-request.schema.json": "opensocrates.assistance.request/1.0.0",
    "assistance-plan.schema.json": "opensocrates.assistance.plan/1.0.0",
    "project-memory-request.schema.json": "opensocrates.project-memory.request/1.0.0",
    "project-memory-response.schema.json": "opensocrates.project-memory.response/1.0.0",
    "project-memory-record.schema.json": "opensocrates.project-memory.record/1.0.0",
    "project-memory-snapshot.schema.json": "opensocrates.project-memory.snapshot/1.0.0",
    "project-memory-context-pack.schema.json": "opensocrates.project-memory.context-pack/1.0.0",
}
for filename, schema in SCHEMAS.items():
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = IDENTITIES[filename]
    schema["title"] = filename.removesuffix(".schema.json")
