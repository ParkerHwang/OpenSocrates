"""Canonical closed v1.5 JSON contracts, generated into schemas/v1.

Operation-specific rules that JSON Schema cannot express without a discriminator
are also checked by the runtime. No schema in this module permits unknown keys.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

UUID = {
    "type": "string",
    "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
}
TEXT = {"type": "string", "maxLength": 8192}
SHORT = {"type": "string", "maxLength": 1024}
BASIS_REFERENCE = {
    "type": "string",
    "maxLength": 1024,
    "pattern": "^(?!(?:api_key|password|secret|token|prompt|transcript|credential|cookie|reasoning):)[a-z][a-z0-9_-]*:[A-Za-z0-9._/#-]{1,120}$",
    "description": "Bounded attribution reference such as user:current-request; never instruction prose, prompts, or credentials. The reference does not itself prove authorization.",
}
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
CALLER_ACTION = obj(
    {
        **ACTION["properties"],
        "support": {"enum": ["agent_reported", "inferred", "imported"]},
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
        "authorization_basis": BASIS_REFERENCE,
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
        "acceptance_basis": BASIS_REFERENCE,
        "acceptance_attribution": {
            "enum": ["operator_declared", "agent_reported_user_instruction"]
        },
        "new_record_id": UUID,
        "reason": SHORT,
        "objective": TEXT,
        "constraints": arr(SHORT),
        "completion_conditions": arr(SHORT),
        "completed_actions": arr(CALLER_ACTION),
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

# Separate closed revisions leave every v1.0 schema byte and stored record intact.
ID = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,127}$"}
ATTRIBUTION = {"enum": ["host_reported", "operator_declared", "agent_reported", "unknown"]}
OBLIGATION = obj(
    {
        "obligation_id": ID,
        "question_id": ID,
        "kind": {"enum": ["work", "input"]},
        "required": BOOL,
        "status": {"enum": ["met", "unmet", "unverified", "not_recorded", "not_applicable"]},
        "evidence_refs": arr(ID, 8),
        "attribution": ATTRIBUTION,
        "depends_on": arr(ID, 8),
    },
    (
        "obligation_id",
        "question_id",
        "kind",
        "required",
        "status",
        "evidence_refs",
        "attribution",
        "depends_on",
    ),
)
OBLIGATION_SUMMARY = obj(
    {
        "finish_eligible": BOOL,
        "blocking_ids": arr(ID, 8),
        "ready_ids": arr(ID, 8),
        "input_ids": arr(ID, 8),
        "required_input_ids": arr(ID, 8),
        "waiting_ids": arr(ID, 8),
        "questions": arr(
            obj(
                {"question_id": ID, "required_complete": BOOL, "blocking_ids": arr(ID, 8)},
                ("question_id", "required_complete", "blocking_ids"),
            ),
            8,
        ),
    },
    (
        "finish_eligible",
        "blocking_ids",
        "ready_ids",
        "input_ids",
        "required_input_ids",
        "waiting_ids",
        "questions",
    ),
)
for stem in (
    "assistance-request",
    "assistance-plan",
    "project-memory-request",
    "project-memory-context-pack",
):
    filename = stem + "-v2.schema.json"
    revised = deepcopy(SCHEMAS[stem + ".schema.json"])
    identity = IDENTITIES[stem + ".schema.json"].replace("/1.0.0", "/1.1.0")
    revised["properties"]["schema"] = {"const": identity}
    SCHEMAS[filename] = revised
    IDENTITIES[filename] = identity

request_v2 = SCHEMAS["assistance-request-v2.schema.json"]
request_v2["properties"]["obligations"] = arr(OBLIGATION, 8)
request_v2["required"].append("obligations")
plan_v2 = SCHEMAS["assistance-plan-v2.schema.json"]
plan_v2["properties"]["request_id"] = nullable(UUID)
plan_v2["properties"]["obligation_summary"] = OBLIGATION_SUMMARY
plan_v2["properties"]["reason_codes"]["items"]["enum"].append("obligation_gap")
plan_v2["properties"]["reason_codes"]["maxItems"] = 10
memory_v2 = SCHEMAS["project-memory-request-v2.schema.json"]
memory_v2["properties"]["operation"]["enum"].append("prepare")
memory_v2["properties"]["payload"]["properties"]["target_operation"] = {"const": "checkpoint"}

pack_v2 = SCHEMAS["project-memory-context-pack-v2.schema.json"]
for field in ("constraints", "decisions"):
    entry = pack_v2["properties"][field]["items"]
    for key in ("kind", "lifecycle", "support", "origin"):
        entry["properties"][key] = deepcopy(
            SCHEMAS["project-memory-record.schema.json"]["properties"][key]
        )
        entry["required"].append(key)
pack_v2["properties"]["checkpoint"] = {
    "anyOf": [
        {"type": "null"},
        obj(
            {
                "record_id": UUID,
                "checkpoint_version": POSITIVE,
                "lifecycle": {"enum": ["proposed", "accepted", "superseded", "archived"]},
                "support": {"const": "agent_reported"},
                "objective": SHORT,
                "next_action": SHORT,
                "summary_truncated": BOOL,
                "snapshot_id": nullable(UUID),
                "freshness": {"enum": ["current", "stale", "unknown", "not_applicable"]},
                "inspection_required_for_full_state": {"const": True},
            },
            (
                "record_id",
                "checkpoint_version",
                "lifecycle",
                "support",
                "objective",
                "next_action",
                "summary_truncated",
                "snapshot_id",
                "freshness",
                "inspection_required_for_full_state",
            ),
        ),
    ]
}
pack_v2["properties"]["revalidation_scopes"] = arr(arr(PATH))
pack_v2["required"].extend(("checkpoint", "revalidation_scopes"))

DOC_VERSION = {"type": "string", "pattern": "^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$"}
DOC_REFERENCE = obj(
    {
        "url": {"type": "string", "minLength": 1, "maxLength": 2048},
        "document_version": nullable(DOC_VERSION),
        "read_state": {"enum": ["not_read", "reported_read"]},
        "attribution": ATTRIBUTION,
    },
    ("url", "document_version", "read_state", "attribution"),
)
SCHEMAS["documentation-request.schema.json"] = obj(
    {
        "schema": {"const": "opensocrates.documentation.request/1.0.0"},
        "request_id": UUID,
        "locale": {"enum": ["en", "ko"]},
        "task_kind": {"enum": ["mechanical", "judgment"]},
        "need": {
            "enum": [
                "none",
                "api_contract",
                "version_change",
                "source_conflict",
                "official_request",
            ]
        },
        "publisher_id": nullable(ID),
        "target_version": nullable(DOC_VERSION),
        "references": arr(DOC_REFERENCE, 4),
    },
    (
        "schema",
        "request_id",
        "locale",
        "task_kind",
        "need",
        "publisher_id",
        "target_version",
        "references",
    ),
)
doc_result_reference = deepcopy(DOC_REFERENCE)
doc_result_reference["properties"].update(
    {
        "publisher_match": {"enum": ["catalog_match", "unverified"]},
        "version_match": {"enum": ["exact_declared", "mismatch", "unknown"]},
    }
)
doc_result_reference["required"].extend(("publisher_match", "version_match"))
SCHEMAS["documentation-pack.schema.json"] = obj(
    {
        "schema": {"const": "opensocrates.documentation.pack/1.0.0"},
        "request_id": nullable(UUID),
        "status": {"enum": ["ok", "not_needed", "invalid_request", "unavailable"]},
        "instructions": TEXT,
        "instruction_sha256": nullable(DIGEST),
        "publisher_id": nullable(ID),
        "catalog_revision": POSITIVE,
        "official_roots": arr({"type": "string", "maxLength": 2048}, 8),
        "references": arr(doc_result_reference, 4),
        "next_action": {
            "enum": [
                "continue",
                "find_official_source",
                "read_reference",
                "resolve_version",
                "apply_with_citations",
            ]
        },
        "delivery": {"enum": ["emitted", "not_emitted"]},
        "application": {"const": "unverified"},
        "limitations": arr(SHORT),
    },
    ("schema", "request_id", "status", "application", "limitations"),
)
IDENTITIES["documentation-request.schema.json"] = "opensocrates.documentation.request/1.0.0"
IDENTITIES["documentation-pack.schema.json"] = "opensocrates.documentation.pack/1.0.0"
for filename, schema in SCHEMAS.items():
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = IDENTITIES[filename]
    schema["title"] = filename.removesuffix(".schema.json")


# Optional orchestration is an independent closed schema family. It does not
# change any existing decision, memory, or assistance representation.
def orchestration_object(properties: dict[str, Any]) -> dict[str, Any]:
    return obj(properties, tuple(properties))


OC_ID = {"type": "string", "pattern": "^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$"}
OC_TEXT = {"type": "string", "minLength": 1, "maxLength": 8192}
OC_NOTE = {"type": "string", "minLength": 1, "maxLength": 2048}
OC_PATH = {"type": "string", "minLength": 1, "maxLength": 256}
OC_MODEL = orchestration_object(
    {
        "name": {"type": "string", "pattern": "^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$"},
        "effort": {"enum": ["low", "medium", "high", "xhigh", "max", "ultra"]},
    }
)
OC_CONSTRAINT = orchestration_object({"id": OC_ID, "text": OC_TEXT})
OC_SOURCE = orchestration_object({"id": OC_ID, "path": OC_PATH, "sha256": DIGEST})
OC_FILE = orchestration_object({"path": OC_PATH, "content": {"type": "string", "maxLength": 65536}})
OC_MANIFEST = orchestration_object(
    {
        "path": OC_PATH,
        "sha256": DIGEST,
        "bytes": {"type": "integer", "minimum": 0, "maximum": 262144},
    }
)
OC_OBLIGATION = orchestration_object(
    {"id": OC_ID, "requirement_id": OC_ID, "description": OC_NOTE, "required": BOOL}
)
OC_CHECK = orchestration_object(
    {
        "check_id": OC_ID,
        "argv": {**arr({"type": "string", "minLength": 1, "maxLength": 16384}, 32), "minItems": 1},
        "obligation_ids": {**arr(OC_ID, 16), "minItems": 1},
        "authorization_reference": BASIS_REFERENCE,
        "expected_exit_code": {"type": "integer", "const": 0},
    }
)
OC_SEED = {
    "anyOf": [
        {"type": "null"},
        orchestration_object(
            {
                "author": {"enum": ["synthetic_fixture", "external_author"]},
                "files": {**arr(OC_FILE, 16), "minItems": 1},
            }
        ),
    ]
}
OC_UNIT = orchestration_object(
    {
        "unit_id": OC_ID,
        "domain": {"enum": ["software", "data", "document", "research", "unknown"]},
        "task_kind": {"enum": ["judgment", "mechanical"]},
        "role": {"enum": ["design", "production"]},
        "objective": OC_TEXT,
        "owned_paths": {**arr(OC_PATH, 16), "minItems": 1},
        "dependencies": arr(OC_ID, 8),
        "source_ids": arr(OC_ID, 32),
        "requirement_ids": {**arr(OC_ID, 32), "minItems": 1},
        "specialists": arr({"enum": ["contracts", "transitions", "ownership"]}, 2),
        "obligations": {**arr(OC_OBLIGATION, 16), "minItems": 1},
        "checks": arr(OC_CHECK, 16),
        "seed": OC_SEED,
    }
)
OC_MEMORY_BINDING = {
    "anyOf": [
        {"type": "null"},
        orchestration_object(
            {"project_id": UUID, "workspace_id": UUID, "record_ids": arr(UUID, 64)}
        ),
    ]
}
OC_REQUEST = orchestration_object(
    {
        "schema": {"const": "opensocrates.orchestration.request/1.0.0"},
        "operation": {"enum": ["prepare", "run"]},
        "run_id": UUID,
        "task_id": UUID,
        "revision": POSITIVE,
        "authorization": orchestration_object(
            {
                "reference": BASIS_REFERENCE,
                "attribution": {"enum": ["operator_declared", "agent_reported_user_instruction"]},
            }
        ),
        "model": OC_MODEL,
        "locale": {"enum": ["en", "ko"]},
        "objective": OC_TEXT,
        "required_artifacts": {**arr(OC_PATH, 128), "minItems": 1},
        "constraints": {**arr(OC_CONSTRAINT, 32), "minItems": 1},
        "permissions": arr(OC_NOTE, 16),
        "prohibitions": arr(OC_NOTE, 16),
        "source_root": PATH,
        "sources": arr(OC_SOURCE, 32),
        "candidate_root": PATH,
        "client_path": PATH,
        "repair_limit": {"type": "integer", "minimum": 0, "maximum": 2},
        "memory": OC_MEMORY_BINDING,
        "handoff": arr(OC_TEXT, 16),
        "units": {**arr(OC_UNIT, 8), "minItems": 1},
    }
)
OC_FINDING = orchestration_object(
    {
        "artifact_sha256": DIGEST,
        "requirement_id": OC_ID,
        "location": OC_PATH,
        "expected": OC_NOTE,
        "observed": OC_NOTE,
        "reproduction": OC_NOTE,
        "impact": OC_NOTE,
        "missing_evidence": arr(OC_NOTE, 8),
        "severity": {"type": "string", "enum": ["blocking", "advisory"]},
    }
)
OC_JUDGMENT = orchestration_object(
    {
        "id": OC_ID,
        "status": {"type": "string", "enum": ["passed", "failed", "unknown"]},
        "expected": OC_NOTE,
        "observed": OC_NOTE,
        "reproduction": OC_NOTE,
        "evidence_ids": {
            **arr({"type": "string", "minLength": 1, "maxLength": 128}, 32),
            "minItems": 1,
        },
    }
)
OC_ASSESSMENT = orchestration_object(
    {
        "schema": {"type": "string", "const": "opensocrates.orchestration.assessment/1.0.0"},
        "assignment_id": UUID,
        "candidate_sha256": DIGEST,
        "verdict": {"type": "string", "enum": ["pass", "repair_required", "blocked"]},
        "findings": arr(OC_FINDING, 32),
        "obligations": {**arr(OC_JUDGMENT, 16), "minItems": 1},
    }
)
OC_CANDIDATE = orchestration_object(
    {
        "schema": {"type": "string", "const": "opensocrates.orchestration.candidate/1.0.0"},
        "assignment_id": UUID,
        "files": arr(OC_FILE, 16),
        "blocked_reason": {
            "type": ["string", "null"],
            "enum": [None, "contract_change", "missing_input"],
        },
    }
)
# The model receives these two complete schemas. Keep their shared leaf nodes
# independent of the 47 older schemas and other canonical graphs; provider-only
# annotations must never mutate an existing contract through an alias.
OC_ASSESSMENT = deepcopy(OC_ASSESSMENT)
OC_CANDIDATE = deepcopy(OC_CANDIDATE)

OC_GUIDE = orchestration_object(
    {"id": OC_PATH, "sha256": DIGEST, "text": {"type": "string", "maxLength": 65536}}
)
OC_MEMORY_ITEM = orchestration_object(
    {
        "record_id": UUID,
        "version": POSITIVE,
        "kind": {"enum": ["decision", "observation", "lesson", "checkpoint"]},
        "lifecycle": {"enum": ["proposed", "accepted", "superseded", "archived"]},
        "support": {
            "enum": ["runtime_observed", "tool_reported", "agent_reported", "inferred", "imported"]
        },
        "freshness": {"enum": ["current", "stale", "unknown", "not_applicable"]},
        "review_state": {"const": "unknown"},
        "summary": TEXT,
        "rationale": nullable(TEXT),
        "constraints": arr(TEXT, 32),
        "source_refs": arr(SOURCE_REF, 32),
        "conflict_ids": arr(UUID, 32),
        "origin": ORIGIN,
        "lesson": {
            "anyOf": [
                {"type": "null"},
                orchestration_object(
                    {
                        "conditions": OC_NOTE,
                        "mechanism": OC_NOTE,
                        "exceptions": arr(OC_NOTE, 8),
                        "provenance": OC_NOTE,
                        "evidence_refs": arr(SHORT, 32),
                    }
                ),
            ]
        },
    }
)
OC_MEMORY = orchestration_object(
    {
        "status": {"enum": ["not_requested", "available", "disabled", "unavailable", "changed"]},
        "records": arr(OC_MEMORY_ITEM, 64),
        "limitations": arr(SHORT, 32),
    }
)
OC_RECEIPT = orchestration_object(
    {
        "check_id": OC_ID,
        "candidate_sha256": DIGEST,
        "argv_sha256": DIGEST,
        "status": {"enum": ["passed", "failed", "unknown"]},
        "exit_code": {"type": ["integer", "null"]},
        "stdout_sha256": nullable(DIGEST),
        "stderr_sha256": nullable(DIGEST),
        "obligation_ids": arr(OC_ID, 16),
        "reason": {
            "enum": [
                "expected_exit",
                "unexpected_exit",
                "sandbox_unavailable",
                "inputs_changed",
                "output_limit",
                "cancelled",
            ]
        },
    }
)
OC_INPUT = orchestration_object(
    {
        "path": OC_PATH,
        "sha256": DIGEST,
        "bytes": NONNEGATIVE,
        "kind": {"enum": ["source", "dependency", "candidate"]},
        "source_id": nullable(OC_ID),
    }
)
OC_REPAIR_OBLIGATION = orchestration_object(
    {
        **OC_JUDGMENT["properties"],
        "assessment_role": {"enum": ["review", "execution_verification"]},
        "assessment_id": UUID,
        "candidate_sha256": DIGEST,
        "version": POSITIVE,
    }
)
OC_PUBLICATION = orchestration_object(
    {
        "status": {"enum": ["not_started", "incomplete", "complete"]},
        "location_verified": BOOL,
        "completed_files": arr(
            orchestration_object(
                {
                    "path": {"type": "string", "maxLength": 512},
                    "sha256": DIGEST,
                    "bytes": NONNEGATIVE,
                }
            ),
            512,
        ),
        "pending_path": nullable({"type": "string", "maxLength": 512}),
    }
)
OC_ASSIGNMENT = orchestration_object(
    {
        "schema": {"const": "opensocrates.orchestration.assignment/1.0.0"},
        "authorization": OC_REQUEST["properties"]["authorization"],
        "task_objective": OC_TEXT,
        "assignment_id": UUID,
        "run_id": UUID,
        "task_id": UUID,
        "revision": POSITIVE,
        "unit_id": OC_ID,
        "domain": OC_UNIT["properties"]["domain"],
        "task_kind": OC_UNIT["properties"]["task_kind"],
        "role": {"enum": ["design", "production", "review", "execution_verification"]},
        "model": OC_MODEL,
        "locale": {"enum": ["en", "ko"]},
        "objective": OC_TEXT,
        "constraints": arr(OC_CONSTRAINT, 32),
        "permissions": arr(OC_NOTE, 16),
        "prohibitions": arr(OC_NOTE, 32),
        "owned_paths": arr(OC_PATH, 16),
        "dependencies": arr(OC_ID, 8),
        "obligations": arr(OC_OBLIGATION, 16),
        "guides": arr(OC_GUIDE, 10),
        "inputs": arr(OC_INPUT, 160),
        "memory": OC_MEMORY,
        "handoff": arr(OC_TEXT, 16),
        "uncertainty": arr(SHORT, 32),
        "candidate_sha256": nullable(DIGEST),
        "checks": arr(OC_CHECK, 16),
        "check_receipts": arr(OC_RECEIPT, 16),
        "repair_findings": arr(OC_FINDING, 64),
        "repair_obligations": arr(OC_REPAIR_OBLIGATION, 32),
        "output_schema": {
            "enum": ["orchestration-candidate.schema.json", "orchestration-assessment.schema.json"]
        },
    }
)
OC_USAGE = orchestration_object(
    {
        key: {"type": ["integer", "null"], "minimum": 0}
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
        )
    }
)
OC_CALL = orchestration_object(
    {
        "assignment_id": UUID,
        "unit_id": OC_ID,
        "role": OC_ASSIGNMENT["properties"]["role"],
        "input_sha256": DIGEST,
        "output_sha256": nullable(DIGEST),
        "thread_sha256": nullable(DIGEST),
        "model": OC_MODEL,
        "status": {
            "enum": ["completed", "failed", "cancelled", "invalid_output", "inputs_changed"]
        },
        "usage": OC_USAGE,
        "guide_manifest": arr(orchestration_object({"id": OC_PATH, "sha256": DIGEST}), 10),
        "input_manifest": arr(OC_INPUT, 160),
        "memory_snapshot_sha256": DIGEST,
        "provider_error_events": NONNEGATIVE,
        "failed_turn_events": NONNEGATIVE,
        "process_exit_code": {"type": ["integer", "null"]},
        "backend_attempts": {"type": "null"},
        "reason": SHORT,
    }
)
OC_VERSION = orchestration_object(
    {
        "version": POSITIVE,
        "candidate_sha256": DIGEST,
        "artifacts": arr(OC_MANIFEST, 16),
        "producer_id": SHORT,
        "reviewer_id": nullable(UUID),
        "verifier_id": nullable(UUID),
        "review": {"anyOf": [{"type": "null"}, OC_ASSESSMENT]},
        "verification": {"anyOf": [{"type": "null"}, OC_ASSESSMENT]},
        "checks": arr(OC_RECEIPT, 16),
        "qualified": BOOL,
    }
)
OC_RESULT = orchestration_object(
    {
        "unit_id": OC_ID,
        "status": {
            "enum": [
                "ready",
                "classification_gap",
                "blocked_dependency",
                "unavailable",
                "repair_required",
                "source_conflict",
                "qualified_candidate",
                "cancelled",
            ]
        },
        "reason": SHORT,
        "versions": arr(OC_VERSION, 3),
        "required_open": arr(OC_ID, 16),
    }
)
OC_RESPONSE = orchestration_object(
    {
        "schema": {"const": "opensocrates.orchestration.response/1.0.0"},
        "run_id": nullable(UUID),
        "status": {
            "enum": [
                "prepared",
                "integration_pending",
                "partial",
                "blocked",
                "invalid_request",
                "unavailable",
                "cancelled",
            ]
        },
        "plan_sha256": nullable(DIGEST),
        "model": {"anyOf": [{"type": "null"}, OC_MODEL]},
        "client_version": nullable(SHORT),
        "client_sha256": nullable(DIGEST),
        "units": arr(OC_RESULT, 8),
        "calls": arr(OC_CALL, 72),
        "memory_status": OC_MEMORY["properties"]["status"],
        "memory_snapshot_sha256": nullable(DIGEST),
        "integration": {"const": "pending_primary_reconciliation"},
        "publication": OC_PUBLICATION,
        "limitations": arr(SHORT, 32),
    }
)
for _name, _schema in {
    "request": OC_REQUEST,
    "assignment": OC_ASSIGNMENT,
    "candidate": OC_CANDIDATE,
    "assessment": OC_ASSESSMENT,
    "response": OC_RESPONSE,
}.items():
    _filename = f"orchestration-{_name}.schema.json"
    _schema.update(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"opensocrates.orchestration.{_name}/1.0.0",
            "title": f"orchestration-{_name}",
        }
    )
    SCHEMAS[_filename] = _schema
    IDENTITIES[_filename] = _schema["$id"]
