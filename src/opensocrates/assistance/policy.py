"""Pure assistance rules. Caller features and profile authorization are assertions, not proof."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping
from uuid import UUID

REQUEST_SCHEMA = "opensocrates.assistance.request/1.0.0"
PLAN_SCHEMA = "opensocrates.assistance.plan/1.0.0"
MAX_BYTES = 16 * 1024
REQUEST_SCHEMA_V2 = "opensocrates.assistance.request/1.1.0"
PLAN_SCHEMA_V2 = "opensocrates.assistance.plan/1.1.0"

COMPONENT_ORDER = (
    "goal",
    "constraints",
    "evidence_need",
    "bounded_subgoal",
    "verification_target",
    "completion_cue",
)
OPTIONAL_COMPONENTS = frozenset(("evidence_need", "bounded_subgoal", "verification_target"))
REASON_ORDER = (
    "mechanical",
    "completed_unchanged",
    "bounded_judgment",
    "coupled_task",
    "consequential_stakes",
    "material_uncertainty",
    "matched_support_rule",
    "profile_fallback",
    "dependency_missing",
    "obligation_gap",
)
TASK_ENUMS = {
    "task_kind": frozenset(("mechanical", "judgment")),
    "task_family": frozenset(("coding", "planning", "research", "writing", "other")),
    "complexity": frozenset(("bounded", "coupled")),
    "stakes": frozenset(("ordinary", "consequential")),
    "uncertainty": frozenset(("resolved", "bounded", "material")),
    "context_need": frozenset(("none", "current_evidence", "continuity")),
    "completion": frozenset(("in_progress", "checks_satisfied", "dependent_input_missing")),
}


class InvalidAssistanceRequest(ValueError):
    """A closed request failed validation; the original value is never included."""


@dataclass(frozen=True)
class AssistanceProfile:
    """Trusted, prevalidated package configuration injected by the caller."""

    profile_id: str
    revision: int
    state: Literal["candidate", "validated", "withdrawn"]
    model: str
    effort: str
    client: str
    task_families: frozenset[str]
    raise_to_structured: bool = False
    optional_components: tuple[str, ...] = ()
    validation_reference: str | None = None


def _object(value: Any, keys: frozenset[str], required: frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or value.keys() - keys or required - value.keys():
        raise InvalidAssistanceRequest("invalid_request")
    return value


def _string(value: Any) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise InvalidAssistanceRequest("invalid_request")
    return value


def validate_request(request: Any) -> dict[str, Any]:  # noqa: C901  # Closed field validation.
    """Validate closed fields and the encoded request bound before policy action."""

    try:
        if (
            len(json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
            > MAX_BYTES
        ):
            raise InvalidAssistanceRequest("invalid_request")
    except (TypeError, UnicodeError, ValueError) as exc:
        raise InvalidAssistanceRequest("invalid_request") from exc
    if isinstance(request, dict) and request.get("schema") == REQUEST_SCHEMA_V2:
        from ..project_memory.contracts import load_schema, validate
        from .obligations import summarize_obligations

        try:
            schema = load_schema("assistance-request-v2.schema.json")
        except (ValueError, OSError) as exc:
            raise RuntimeError("installed_assistance_schema_unavailable") from exc
        try:
            validate(request, schema)
            summarize_obligations(request["obligations"])
            legacy = {key: value for key, value in request.items() if key != "obligations"}
            legacy["schema"] = REQUEST_SCHEMA
            validate_request(legacy)
        except ValueError as exc:
            raise InvalidAssistanceRequest("invalid_request") from exc
        return request
    envelope = _object(
        request,
        frozenset(("schema", "request_id", "locale", "task", "model_context", "profile_override")),
        frozenset(("schema", "request_id", "locale", "task", "model_context")),
    )
    if envelope["schema"] != REQUEST_SCHEMA or envelope["locale"] not in ("en", "ko"):
        raise InvalidAssistanceRequest("invalid_request")
    request_id = _string(envelope["request_id"])
    try:
        if str(UUID(request_id)) != request_id.lower():
            raise ValueError
    except (ValueError, AttributeError) as exc:
        raise InvalidAssistanceRequest("invalid_request") from exc

    task = _object(
        envelope["task"],
        frozenset((*TASK_ENUMS, "material_change")),
        frozenset((*TASK_ENUMS, "material_change")),
    )
    for key, allowed in TASK_ENUMS.items():
        if not isinstance(task[key], str) or task[key] not in allowed:
            raise InvalidAssistanceRequest("invalid_request")
    if type(task["material_change"]) is not bool:
        raise InvalidAssistanceRequest("invalid_request")

    context = _object(
        envelope["model_context"],
        frozenset(("model", "effort", "client", "attribution")),
        frozenset(("model", "effort", "client", "attribution")),
    )
    for key in ("model", "effort", "client"):
        if context[key] is not None:
            _string(context[key])
    if context["attribution"] not in (
        "host_reported",
        "operator_declared",
        "agent_reported",
        "unknown",
    ):
        raise InvalidAssistanceRequest("invalid_request")

    override = envelope.get("profile_override")
    if override is not None:
        override = _object(
            override,
            frozenset(("profile_id", "revision", "authorization_basis")),
            frozenset(("profile_id", "revision", "authorization_basis")),
        )
        _string(override["profile_id"])
        _string(override["authorization_basis"])
        if type(override["revision"]) is not int or override["revision"] < 1:
            raise InvalidAssistanceRequest("invalid_request")
    return envelope


def _matched_profile(
    request: Mapping[str, Any], profiles: tuple[AssistanceProfile, ...], *, candidate_enabled: bool
) -> AssistanceProfile | None:
    context = request["model_context"]
    if any(context[key] is None for key in ("model", "effort", "client")):
        return None
    override = request.get("profile_override")
    for profile in profiles:
        if (
            profile.state == "withdrawn"
            or (profile.state == "candidate" and not candidate_enabled)
            or profile.state not in ("candidate", "validated")
            or (profile.model, profile.effort, profile.client)
            != (context["model"], context["effort"], context["client"])
            or request["task"]["task_family"] not in profile.task_families
        ):
            continue
        if override is None:
            if profile.state == "validated":
                return profile
        elif (profile.profile_id, profile.revision) == (
            override["profile_id"],
            override["revision"],
        ):
            return profile
    return None


def plan_assistance(  # noqa: C901  # Ordered policy precedence is intentionally explicit.
    request: Mapping[str, Any],
    *,
    profiles: tuple[AssistanceProfile, ...] = (),
    candidate_enabled: bool = False,
) -> dict[str, Any]:
    """Return bounded guidance from closed features; perform no I/O or model calls."""

    data = validate_request(request)
    task = dict(data["task"])
    obligation_summary = None
    if data["schema"] == REQUEST_SCHEMA_V2:
        from .obligations import summarize_obligations

        obligation_summary = summarize_obligations(data["obligations"])
        if not obligation_summary["finish_eligible"]:
            task["completion"] = (
                "dependent_input_missing"
                if (
                    obligation_summary["required_input_ids"]
                    or task["completion"] == "dependent_input_missing"
                )
                and not obligation_summary["ready_ids"]
                else "in_progress"
            )
        elif not task["material_change"] and task["completion"] != "dependent_input_missing":
            task["completion"] = "checks_satisfied"
    profile = _matched_profile(data, profiles, candidate_enabled=candidate_enabled)
    reasons: set[str] = set()
    if profile is None:
        reasons.add("profile_fallback")
    if obligation_summary is not None and not obligation_summary["finish_eligible"]:
        reasons.add("obligation_gap")

    dependency = task["completion"] == "dependent_input_missing"
    if dependency:
        reasons.add("dependency_missing")
        action = "resolve_dependency"
    elif task["completion"] == "checks_satisfied" and not task["material_change"]:
        reasons.add("completed_unchanged")
        action = "finish"
    else:
        action = "continue"

    if action == "finish" or task["task_kind"] == "mechanical":
        level = "none"
        components: list[str] = []
        if task["task_kind"] == "mechanical":
            reasons.add("mechanical")
    else:
        if task["complexity"] == "coupled":
            reasons.add("coupled_task")
        if task["stakes"] == "consequential":
            reasons.add("consequential_stakes")
        if task["uncertainty"] == "material":
            reasons.add("material_uncertainty")
        level = (
            "structured"
            if reasons.intersection(
                ("coupled_task", "consequential_stakes", "material_uncertainty")
            )
            else "light"
        )
        if level == "light":
            reasons.add("bounded_judgment")
        if profile is not None and profile.raise_to_structured and level == "light":
            level = "structured"
            reasons.add("matched_support_rule")
        optional = (
            set(profile.optional_components)
            if profile is not None
            else (
                set(OPTIONAL_COMPONENTS)
                if level == "structured"
                else ({"evidence_need"} if task["context_need"] != "none" else set())
            )
        )
        if not optional <= OPTIONAL_COMPONENTS or len(optional) != (
            len(profile.optional_components) if profile else len(optional)
        ):
            raise ValueError("invalid trusted profile configuration")
        if profile is not None and optional:
            reasons.add("matched_support_rule")
        components = [
            name
            for name in COMPONENT_ORDER
            if name in optional or name in ("goal", "constraints", "completion_cue")
        ]

    budget = (
        0
        if task["context_need"] != "continuity"
        else {"none": 0, "light": 8192, "structured": 24576}[level]
    )
    return {
        "schema": PLAN_SCHEMA_V2 if obligation_summary is not None else PLAN_SCHEMA,
        "request_id": data["request_id"],
        "status": "ok",
        "assistance_level": level,
        "profile_id": profile.profile_id if profile else None,
        "profile_revision": profile.revision if profile else None,
        "profile_evidence": "candidate_evaluation"
        if profile and profile.state == "candidate"
        else "validated_run"
        if profile
        else "task_default",
        "validation_reference": profile.validation_reference
        if profile and profile.state == "validated"
        else None,
        "context_pack_budget_bytes": budget,
        "guidance_components": components,
        "reason_codes": [reason for reason in REASON_ORDER if reason in reasons],
        "next_action": action,
        "application": "unverified",
        "limitations": ["caller_features_unverified", "permissions_and_required_checks_external"],
        **({"obligation_summary": obligation_summary} if obligation_summary is not None else {}),
    }
