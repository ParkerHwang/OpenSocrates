"""Schemas, frozen content identifiers, and authoring validation.

This module is intentionally independent of host adapters and production I/O. YAML
parsing is exposed only for build tooling; runtime loading uses compiled JSON.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

AUTHORING_SCHEMA = "opensocrates.method-authoring/1.0.0"
COMPILED_METHOD_SCHEMA = "opensocrates.compiled-method/1.0.0"
BUNDLE_SCHEMA = "opensocrates.compiled-content-bundle/1.0.0"
CATALOG_SCHEMA = "opensocrates.method-catalog/1.0.0"
CASES_SCHEMA = "opensocrates.method-cases/1.0.0"
SELECTION_CATALOG_SCHEMA = "opensocrates.selection-catalog/1.0.0"
SELECTION_CATALOG_ENTRY_SCHEMA = "opensocrates.selection-catalog-entry/1.0.0"
INJECTABLE_REASONING_CONTENT_SCHEMA = "opensocrates.injectable-reasoning-content/1.0.0"
TEMPLATE_EXAMPLE_SCHEMA = "opensocrates.template-example/1.0.0"
REASONING_CONTENT_PROJECTIONS_SCHEMA = "opensocrates.reasoning-content-projections/1.0.0"

FROZEN_FAMILIES = (
    "framing",
    "structuring",
    "logical_reasoning",
    "evidence_verification",
    "causal_systems",
    "critical_counterexample",
    "creative_reframing",
    "values_purpose",
    "decision_optimization",
    "future_uncertainty",
    "experiment_learning",
    "strategy_actors",
)

# method_id | family | positive weights | negative weights | minimum | contraindication | complement
_FROZEN_ROWS = (
    (
        "boundary-critique",
        "framing",
        "boundary_sensitive:3,stakeholder_conflict:1",
        "",
        5,
        "",
        "stakeholder-analysis",
    ),
    (
        "conceptual-analysis",
        "framing",
        "ambiguous_terms:3,argument_dispute:2",
        "",
        5,
        "",
        "argument-mapping",
    ),
    (
        "first-principles",
        "framing",
        "hidden_assumptions:3,stale_options:2",
        "explicit_rules:1",
        5,
        "",
        "morphological-analysis",
    ),
    (
        "socratic-questioning",
        "framing",
        "decisive_input_missing:3,ambiguous_terms:2",
        "",
        5,
        "",
        "assumption-mapping",
    ),
    (
        "argument-mapping",
        "structuring",
        "argument_dispute:3,critique:2,tangled_hierarchy:1",
        "",
        5,
        "",
        "evidence-hierarchy",
    ),
    (
        "logic-tree",
        "structuring",
        "tangled_hierarchy:3,diagnose:2,plan:1",
        "feedback_delay:2",
        5,
        "",
        "root-cause-analysis",
    ),
    (
        "mece",
        "structuring",
        "category_overlap:3,tangled_hierarchy:2",
        "feedback_delay:2",
        5,
        "",
        "logic-tree",
    ),
    (
        "pyramid-principle",
        "structuring",
        "explain:3,tangled_hierarchy:2",
        "hidden_assumptions:1",
        5,
        "",
        "argument-mapping",
    ),
    (
        "abduction",
        "logical_reasoning",
        "competing_explanations:3,diagnose:2",
        "explicit_rules:2",
        5,
        "",
        "value-of-information",
    ),
    (
        "deduction",
        "logical_reasoning",
        "explicit_rules:3,explain:2",
        "unknown_probability:2",
        5,
        "",
        "conceptual-analysis",
    ),
    (
        "defeasible-reasoning",
        "logical_reasoning",
        "exception_prone_rule:3,explicit_rules:2",
        "",
        5,
        "",
        "premortem-analysis",
    ),
    (
        "induction",
        "logical_reasoning",
        "repeated_observations:3,weak_sample:2",
        "causal_question:2",
        5,
        "",
        "evidence-hierarchy",
    ),
    (
        "bayesian-updating",
        "evidence_verification",
        "new_evidence:3,unknown_probability:2,competing_explanations:1",
        "",
        5,
        "",
        "abduction",
    ),
    (
        "evidence-hierarchy",
        "evidence_verification",
        "source_quality:3,reconcile_evidence:2,conflicting_sources:1",
        "value_conflict:2",
        5,
        "",
        "triangulation",
    ),
    (
        "falsificationism",
        "evidence_verification",
        "testable_claim:3,critique:2",
        "",
        5,
        "no_testable_implication",
        "lean-startup",
    ),
    (
        "triangulation",
        "evidence_verification",
        "reconcile_evidence:3,conflicting_sources:2,source_quality:2",
        "",
        5,
        "",
        "evidence-hierarchy",
    ),
    (
        "causal-reasoning",
        "causal_systems",
        "causal_question:3,confounding:2",
        "",
        5,
        "",
        "falsificationism",
    ),
    (
        "root-cause-analysis",
        "causal_systems",
        "recurring_failure:3,diagnose:3",
        "macro_environment:1",
        5,
        "",
        "failure-mode-effects-analysis",
    ),
    (
        "systems-thinking",
        "causal_systems",
        "feedback_delay:3,causal_question:2,deep_uncertainty:1",
        "",
        5,
        "",
        "causal-loop-diagramming",
    ),
    (
        "causal-loop-diagramming",
        "causal_systems",
        "feedback_delay:3,recurring_failure:2",
        "",
        5,
        "",
        "systems-thinking",
    ),
    (
        "critical-thinking",
        "critical_counterexample",
        "critique:3,hidden_assumptions:2,argument_dispute:1",
        "",
        4,
        "",
        "argument-mapping",
    ),
    (
        "failure-mode-effects-analysis",
        "critical_counterexample",
        "failure_risk:3,plan:2,review_completion:1",
        "",
        5,
        "",
        "premortem-analysis",
    ),
    (
        "premortem-analysis",
        "critical_counterexample",
        "chosen_plan:3,failure_risk:3",
        "",
        5,
        "",
        "failure-mode-effects-analysis",
    ),
    (
        "steelman-reasoning",
        "critical_counterexample",
        "dismissed_opposition:3,argument_dispute:2,critique:1",
        "",
        5,
        "",
        "reflective-equilibrium",
    ),
    (
        "design-thinking",
        "creative_reframing",
        "human_need:3,user_progress:2",
        "",
        5,
        "",
        "jobs-to-be-done",
    ),
    (
        "lateral-thinking",
        "creative_reframing",
        "stale_options:3,choose:2",
        "",
        5,
        "safety_critical_validation",
        "trade-off-analysis",
    ),
    (
        "morphological-analysis",
        "creative_reframing",
        "combinable_dimensions:3,stale_options:2",
        "",
        5,
        "no_coherent_dimensions",
        "first-principles",
    ),
    (
        "triz",
        "creative_reframing",
        "technical_contradiction:3,plan:2",
        "value_conflict:1",
        5,
        "",
        "systems-thinking",
    ),
    (
        "deontic-reasoning",
        "values_purpose",
        "duties_rights:3,explicit_rules:2",
        "",
        5,
        "",
        "reflective-equilibrium",
    ),
    (
        "jobs-to-be-done",
        "values_purpose",
        "user_progress:3,human_need:2",
        "",
        5,
        "",
        "design-thinking",
    ),
    (
        "pragmatism",
        "values_purpose",
        "practical_consequence:3,choose:2,value_conflict:1",
        "duties_rights:2",
        5,
        "",
        "lean-startup",
    ),
    (
        "reflective-equilibrium",
        "values_purpose",
        "value_conflict:3,argument_dispute:2",
        "",
        5,
        "binding_rule_without_discretion",
        "steelman-reasoning",
    ),
    (
        "cost-benefit-analysis",
        "decision_optimization",
        "multiple_objectives:3,multiple_options:2,choose:1",
        "duties_rights:2",
        5,
        "",
        "sensitivity-analysis",
    ),
    (
        "decision-tree-analysis",
        "decision_optimization",
        "sequential_choice:3,unknown_probability:2,choose:1",
        "",
        5,
        "",
        "scenario-planning",
    ),
    (
        "trade-off-analysis",
        "decision_optimization",
        "multiple_options:3,multiple_objectives:3,choose:2",
        "single_feasible_option:2",
        4,
        "binding_rule_without_discretion",
        "sensitivity-analysis",
    ),
    (
        "value-of-information",
        "decision_optimization",
        "information_purchase:3,unknown_probability:2,choose:2",
        "irreversible_choice:1",
        5,
        "",
        "bayesian-updating",
    ),
    (
        "reference-class-forecasting",
        "future_uncertainty",
        "forecast:3,reference_cases:3",
        "",
        5,
        "no_defensible_reference_class",
        "sensitivity-analysis",
    ),
    (
        "robust-decision-making",
        "future_uncertainty",
        "deep_uncertainty:3,irreversible_choice:2,choose:1",
        "",
        5,
        "",
        "scenario-planning",
    ),
    (
        "scenario-planning",
        "future_uncertainty",
        "deep_uncertainty:3,macro_environment:2,forecast:1",
        "",
        5,
        "",
        "pestel-analysis",
    ),
    (
        "sensitivity-analysis",
        "future_uncertainty",
        "sensitive_inputs:3,unknown_probability:2,multiple_objectives:1",
        "deep_uncertainty:1",
        5,
        "",
        "trade-off-analysis",
    ),
    (
        "assumption-mapping",
        "experiment_learning",
        "hidden_assumptions:3,prioritized_assumptions:3",
        "",
        5,
        "",
        "lean-startup",
    ),
    (
        "double-loop-learning",
        "experiment_learning",
        "governing_rule:3,recurring_failure:2",
        "",
        5,
        "",
        "root-cause-analysis",
    ),
    (
        "lean-startup",
        "experiment_learning",
        "testable_hypothesis:3,prioritized_assumptions:2",
        "",
        5,
        "safety_critical_validation",
        "jobs-to-be-done",
    ),
    (
        "pdca-cycle",
        "experiment_learning",
        "repeat_iteration:3,plan:2",
        "diagnose:1",
        5,
        "",
        "root-cause-analysis",
    ),
    (
        "cynefin-framework",
        "strategy_actors",
        "context_disorder:3,diagnose:2,deep_uncertainty:1",
        "",
        5,
        "",
        "scenario-planning",
    ),
    (
        "game-theory",
        "strategy_actors",
        "interacting_actors:3,choose:2",
        "",
        5,
        "no_meaningful_interdependence",
        "stakeholder-analysis",
    ),
    (
        "pestel-analysis",
        "strategy_actors",
        "macro_environment:3,forecast:2",
        "recurring_failure:2",
        5,
        "",
        "scenario-planning",
    ),
    (
        "stakeholder-analysis",
        "strategy_actors",
        "stakeholder_conflict:3,interacting_actors:2",
        "",
        5,
        "",
        "game-theory",
    ),
)


def _parse_weight_spec(spec: str) -> dict[str, int]:
    if not spec:
        return {}
    return {part.split(":", 1)[0]: int(part.split(":", 1)[1]) for part in spec.split(",")}


FROZEN_METHOD_IDS = tuple(row[0] for row in _FROZEN_ROWS)
FROZEN_METHOD_FAMILIES = {row[0]: row[1] for row in _FROZEN_ROWS}
FROZEN_ROUTING = {
    row[0]: {
        "positive_features": _parse_weight_spec(row[2]),
        "negative_features": _parse_weight_spec(row[3]),
        "minimum_score": row[4],
        "contraindications": [row[5]] if row[5] else [],
        "preferred_complement": row[6],
    }
    for row in _FROZEN_ROWS
}
FROZEN_FEATURES = frozenset(
    {"mechanical", "judgment", "mixed", "explicit_method"}
    | {
        key
        for row in _FROZEN_ROWS
        for key in _parse_weight_spec(row[2]) | _parse_weight_spec(row[3])
    }
    | {row[5] for row in _FROZEN_ROWS if row[5]}
)
FROZEN_CONTRAINDICATIONS = frozenset({"mechanical"} | {row[5] for row in _FROZEN_ROWS if row[5]})
ALLOWED_ANSWER_SHAPES = frozenset(
    {
        "direct_judgment",
        "decision_memo",
        "diagnostic",
        "critique",
        "evidence_reconciliation",
        "structured_plan",
        "risk_assessment",
        "completion_review",
    }
)
METHOD_AUTHORING_KEYS = frozenset(
    {
        "schema",
        "id",
        "family",
        "content_revision",
        "display_name",
        "plain_action",
        "participation",
        "routing",
        "output_contract",
        "complements",
        "locales",
        "source_provenance",
    }
)
COMPILED_METHOD_KEYS = frozenset(
    {
        "schema",
        "id",
        "family",
        "content_revision",
        "display_name",
        "plain_action",
        "participation",
        "routing",
        "output_contract",
        "complements",
        "procedure",
        "complement_fragment",
    }
)
BUNDLE_KEYS = frozenset(
    {
        "schema",
        "product_version",
        "content_revision",
        "method_ids",
        "methods",
        "locale_messages",
        "prompt_fragments",
        "policy_versions",
        "source_tree_hash",
        "normalized_semantic_hash",
    }
)
SELECTION_CATALOG_KEYS = frozenset({"schema", "content_revision", "entries"})
SELECTION_CATALOG_ENTRY_KEYS = frozenset(
    {
        "schema",
        "method_id",
        "family",
        "content_revision",
        "display_name",
        "core_purpose",
        "suitable_features",
        "unsuitable_features",
        "commonly_confused_features",
        "related_method_ids",
        "injectable_content_locator",
    }
)
INJECTABLE_REASONING_CONTENT_KEYS = frozenset(
    {
        "schema",
        "method_id",
        "content_revision",
        "locale",
        "display_name",
        "theory",
        "template_examples",
    }
)
TEMPLATE_EXAMPLE_KEYS = frozenset(
    {
        "schema",
        "case_id",
        "kind",
        "template_prompt",
        "expected_route",
        "expected_behavior",
        "decisive_features",
        "rationale",
    }
)
REASONING_CONTENT_PROJECTIONS_KEYS = frozenset(
    {"schema", "content_revision", "selection_catalog", "injectable_content"}
)
PROMPT_FRAGMENT_IDS = (
    "controller",
    "participation_rigor",
    "routing_classifier",
    "framing",
    "evidence_card_completion",
    "cross_exam",
    "strict_second_pass",
    "capability_notice",
)
POLICY_IDS = ("participation", "risk", "routing", "card")
_CASE_KINDS = frozenset({"positive", "negative", "mechanical", "explicit", "insufficiency"})
_CASE_BEHAVIORS = frozenset({"route", "no_route", "explicit_primary", "hold", "refuse"})
_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_FAMILY_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ContentValidationError(ValueError):
    """Raised when canonical content violates a closed contract."""

    def __init__(self, message: str | Sequence[str]):
        self.errors = [message] if isinstance(message, str) else list(message)
        super().__init__("; ".join(self.errors))


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContentValidationError(f"{path}: expected an object")
    return value


def _keys(value: Mapping[str, Any], required: set[str], allowed: set[str], path: str) -> None:
    missing = sorted(required - set(value))
    extra = sorted(set(value) - allowed)
    errors = []
    if missing:
        errors.append(f"{path}: missing keys: {', '.join(missing)}")
    if extra:
        errors.append(f"{path}: unknown keys: {', '.join(extra)}")
    if errors:
        raise ContentValidationError(errors)


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise ContentValidationError(f"{path}: expected a non-empty string")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContentValidationError(f"{path}: expected a list")
    return value


def validate_method_authoring(value: Any, *, expected_id: str | None = None) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    raw = dict(_mapping(value, "method"))
    data = dict(raw)
    _keys(data, set(METHOD_AUTHORING_KEYS), set(METHOD_AUTHORING_KEYS), "method")
    if data["schema"] != AUTHORING_SCHEMA:
        raise ContentValidationError("method.schema: unsupported schema")
    method_id = _string(data["id"], "method.id")
    if not _ID_RE.fullmatch(method_id):
        raise ContentValidationError("method.id: invalid MethodId")
    if expected_id is not None and method_id != expected_id:
        raise ContentValidationError(f"method.id: expected {expected_id}, got {method_id}")
    if method_id not in FROZEN_METHOD_FAMILIES:
        raise ContentValidationError(f"method.id: not in the frozen 48: {method_id}")
    if data["family"] != FROZEN_METHOD_FAMILIES[method_id]:
        raise ContentValidationError(f"{method_id}.family: does not match frozen catalog")
    if data["content_revision"] != 1 or not isinstance(data["content_revision"], int):
        raise ContentValidationError(f"{method_id}.content_revision: expected positive revision 1")
    for field in ("display_name", "plain_action"):
        labels = _mapping(data[field], f"{method_id}.{field}")
        if set(labels) != {"en", "ko"}:
            raise ContentValidationError(f"{method_id}.{field}: locales must be exactly en and ko")
        _string(labels["en"], f"{method_id}.{field}.en")
        _string(labels["ko"], f"{method_id}.{field}.ko")
    participation = _mapping(data["participation"], f"{method_id}.participation")
    _keys(
        participation,
        {"judgment_only", "allowed_answer_shapes"},
        {"judgment_only", "allowed_answer_shapes"},
        f"{method_id}.participation",
    )
    if participation["judgment_only"] is not True:
        raise ContentValidationError(
            f"{method_id}.participation.judgment_only: v1 methods must be judgment-only"
        )
    shapes = _list(
        participation["allowed_answer_shapes"], f"{method_id}.participation.allowed_answer_shapes"
    )
    if not shapes or any(shape not in ALLOWED_ANSWER_SHAPES for shape in shapes):
        raise ContentValidationError(
            f"{method_id}.participation.allowed_answer_shapes: unknown or empty shape"
        )
    expected = FROZEN_ROUTING[method_id]
    routing = _mapping(data["routing"], f"{method_id}.routing")
    _keys(
        routing,
        {"positive_features", "negative_features", "minimum_score", "contraindications"},
        {"positive_features", "negative_features", "minimum_score", "contraindications"},
        f"{method_id}.routing",
    )
    for key in ("positive_features", "negative_features"):
        mapping = _mapping(routing[key], f"{method_id}.routing.{key}")
        if any(name not in FROZEN_FEATURES for name in mapping):
            raise ContentValidationError(f"{method_id}.routing.{key}: unknown feature")
        if any(
            not isinstance(weight, int) or isinstance(weight, bool) or weight not in (1, 2, 3)
            for weight in mapping.values()
        ):
            raise ContentValidationError(f"{method_id}.routing.{key}: weights must be integers 1-3")
    if (
        dict(routing["positive_features"]) != expected["positive_features"]
        or dict(routing["negative_features"]) != expected["negative_features"]
    ):
        raise ContentValidationError(f"{method_id}: frozen feature weights do not match")
    if routing["minimum_score"] != expected["minimum_score"]:
        raise ContentValidationError(
            f"{method_id}.routing.minimum_score: frozen threshold does not match"
        )
    if list(routing["contraindications"]) != expected["contraindications"]:
        raise ContentValidationError(
            f"{method_id}.routing.contraindications: frozen list does not match"
        )
    output_contract = _mapping(data["output_contract"], f"{method_id}.output_contract")
    _keys(
        output_contract,
        {"required_sections", "max_questions"},
        {"required_sections", "max_questions"},
        f"{method_id}.output_contract",
    )
    sections = _list(
        output_contract["required_sections"], f"{method_id}.output_contract.required_sections"
    )
    if not sections or any(
        not isinstance(section, str) or not section.strip() for section in sections
    ):
        raise ContentValidationError(
            f"{method_id}.output_contract.required_sections: non-empty strings required"
        )
    if (
        not isinstance(output_contract["max_questions"], int)
        or isinstance(output_contract["max_questions"], bool)
        or not 0 <= output_contract["max_questions"] <= 3
    ):
        raise ContentValidationError(
            f"{method_id}.output_contract.max_questions: expected integer 0-3"
        )
    complements = _mapping(data["complements"], f"{method_id}.complements")
    _keys(
        complements,
        {"preferred", "incompatible_secondary"},
        {"preferred", "incompatible_secondary"},
        f"{method_id}.complements",
    )
    preferred = _list(complements["preferred"], f"{method_id}.complements.preferred")
    if preferred != [expected["preferred_complement"]]:
        raise ContentValidationError(
            f"{method_id}.complements.preferred: frozen complement does not match"
        )
    if (
        _list(
            complements["incompatible_secondary"], f"{method_id}.complements.incompatible_secondary"
        )
        != []
    ):
        raise ContentValidationError(
            f"{method_id}.complements.incompatible_secondary: v1 must be empty"
        )
    if data["locales"] != ["en", "ko"]:
        raise ContentValidationError(f"{method_id}.locales: expected ['en', 'ko']")
    provenance = _mapping(data["source_provenance"], f"{method_id}.source_provenance")
    _keys(
        provenance,
        {"predecessor_slug", "reviewed_by"},
        {"predecessor_slug", "reviewed_by"},
        f"{method_id}.source_provenance",
    )
    if provenance["predecessor_slug"] != method_id:
        raise ContentValidationError(
            f"{method_id}.source_provenance.predecessor_slug: expected the frozen predecessor slug"
        )
    _string(provenance["reviewed_by"], f"{method_id}.source_provenance.reviewed_by")
    return data


def validate_catalog(value: Any) -> dict[str, Any]:
    data = dict(_mapping(value, "catalog"))
    _keys(
        data,
        {"schema", "content_revision", "families", "methods"},
        {"schema", "content_revision", "families", "methods"},
        "catalog",
    )
    if data["schema"] != CATALOG_SCHEMA or data["content_revision"] != 1:
        raise ContentValidationError("catalog: unsupported schema or content revision")
    families = _list(data["families"], "catalog.families")
    if [item.get("id") for item in families if isinstance(item, Mapping)] != list(FROZEN_FAMILIES):
        raise ContentValidationError("catalog.families: expected the frozen family order")
    methods = _list(data["methods"], "catalog.methods")
    ids = [item.get("id") for item in methods if isinstance(item, Mapping)]
    if len(methods) != 48 or len(set(ids)) != 48 or set(ids) != set(FROZEN_METHOD_IDS):
        raise ContentValidationError("catalog.methods: expected exactly the frozen 48 unique IDs")
    for family in families:
        item = _mapping(family, "catalog.family")
        if item["id"] not in FROZEN_FAMILIES:
            raise ContentValidationError(f"catalog.family: unknown family {item['id']}")
        declared = item.get("method_ids")
        expected = [
            method_id
            for method_id in FROZEN_METHOD_IDS
            if FROZEN_METHOD_FAMILIES[method_id] == item["id"]
        ]
        if declared != expected:
            raise ContentValidationError(
                f"catalog.family.{item['id']}: expected four frozen method IDs"
            )
    for item in methods:
        method = _mapping(item, "catalog.method")
        method_id = _string(method.get("id"), "catalog.method.id")
        if (
            method_id not in FROZEN_METHOD_FAMILIES
            or method.get("family") != FROZEN_METHOD_FAMILIES[method_id]
        ):
            raise ContentValidationError(f"catalog.method.{method_id}: family or ID does not match")
    return data


def validate_routing_policy(value: Any) -> dict[str, Any]:
    data = dict(_mapping(value, "routing-policy"))
    matrix = _mapping(data.get("matrix"), "routing-policy.matrix")
    if set(matrix) != set(FROZEN_METHOD_IDS):
        raise ContentValidationError(
            "routing-policy.matrix: expected all and only the frozen 48 IDs"
        )
    for method_id, expected in FROZEN_ROUTING.items():
        row = dict(_mapping(matrix[method_id], f"routing-policy.matrix.{method_id}"))
        actual = {
            key: row.get(key)
            for key in (
                "positive_features",
                "negative_features",
                "minimum_score",
                "contraindications",
                "preferred_complement",
            )
        }
        if actual != expected:
            raise ContentValidationError(f"routing-policy.matrix.{method_id}: frozen row mismatch")
    graph = _mapping(data.get("complement_graph"), "routing-policy.complement_graph")
    if dict(graph) != {
        method_id: row["preferred_complement"] for method_id, row in FROZEN_ROUTING.items()
    }:
        raise ContentValidationError("routing-policy.complement_graph: frozen graph mismatch")
    if data.get("global_negative_features") != {"mechanical": 3} or data.get(
        "global_contraindications"
    ) != ["mechanical"]:
        raise ContentValidationError("routing-policy: global mechanical guard mismatch")
    return data


def validate_compiled_bundle_shape(value: Any) -> dict[str, Any]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    data = dict(_mapping(value, "bundle"))
    if set(data) != set(BUNDLE_KEYS):
        raise ContentValidationError(f"bundle: expected exactly {sorted(BUNDLE_KEYS)}")
    if data["schema"] != BUNDLE_SCHEMA:
        raise ContentValidationError("bundle.schema: unsupported schema")
    method_ids = data["method_ids"]
    if (
        not isinstance(method_ids, list)
        or method_ids != sorted(method_ids)
        or method_ids != sorted(FROZEN_METHOD_IDS)
    ):
        raise ContentValidationError("bundle.method_ids: expected sorted frozen IDs")
    methods = data["methods"]
    if (
        not isinstance(methods, list)
        or [item.get("id") for item in methods if isinstance(item, Mapping)] != method_ids
    ):
        raise ContentValidationError("bundle.methods: order must equal method_ids")
    for item in methods:
        compiled = _mapping(item, "bundle.method")
        if set(compiled) != set(COMPILED_METHOD_KEYS):
            raise ContentValidationError(f"bundle.method.{compiled.get('id')}: unexpected fields")
        if compiled.get("schema") != COMPILED_METHOD_SCHEMA:
            raise ContentValidationError(f"bundle.method.{compiled.get('id')}: unsupported schema")
        if set(_mapping(compiled.get("procedure"), "bundle.method.procedure")) != {"en", "ko"}:
            raise ContentValidationError(
                f"bundle.method.{compiled.get('id')}.procedure: locale mismatch"
            )
        if set(
            _mapping(compiled.get("complement_fragment"), "bundle.method.complement_fragment")
        ) != {"en", "ko"}:
            raise ContentValidationError(
                f"bundle.method.{compiled.get('id')}.complement_fragment: locale mismatch"
            )
    if set(_mapping(data["locale_messages"], "bundle.locale_messages")) != {"en", "ko"}:
        raise ContentValidationError("bundle.locale_messages: expected exactly en and ko")
    if set(_mapping(data["prompt_fragments"], "bundle.prompt_fragments")) != set(
        PROMPT_FRAGMENT_IDS
    ):
        raise ContentValidationError("bundle.prompt_fragments: fixed fragment set mismatch")
    if set(_mapping(data["policy_versions"], "bundle.policy_versions")) != set(POLICY_IDS):
        raise ContentValidationError("bundle.policy_versions: fixed policy set mismatch")
    for field in ("source_tree_hash", "normalized_semantic_hash"):
        if not isinstance(data[field], str) or not _HASH_RE.fullmatch(data[field]):
            raise ContentValidationError(f"bundle.{field}: expected lowercase SHA-256")
    return data


def _positive_content_revision(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ContentValidationError(f"{path}: expected a positive integer")
    return value


def _unique_strings(value: Any, path: str) -> tuple[str, ...]:
    items = _list(value, path)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ContentValidationError(f"{path}: expected non-empty strings")
    if len(set(items)) != len(items):
        raise ContentValidationError(f"{path}: values must be unique")
    return tuple(items)


def _localized_text(value: Any, path: str) -> dict[str, str]:
    localized = dict(_mapping(value, path))
    locale_keys = set(localized)
    if "en" not in locale_keys or locale_keys - {"en", "ko"}:
        raise ContentValidationError(f"{path}: English is required; only en/ko are supported")
    if any(not isinstance(text, str) or not text.strip() for text in localized.values()):
        raise ContentValidationError(f"{path}: localized values must be non-empty strings")
    return localized


def validate_reasoning_content_projections_shape(value: Any) -> dict[str, Any]:  # noqa: C901
    """Validate the selector catalog/injectable projection without fixed cardinality rules."""

    data = dict(_mapping(value, "reasoning-content-projections"))
    _keys(
        data,
        set(REASONING_CONTENT_PROJECTIONS_KEYS),
        set(REASONING_CONTENT_PROJECTIONS_KEYS),
        "reasoning-content-projections",
    )
    if data["schema"] != REASONING_CONTENT_PROJECTIONS_SCHEMA:
        raise ContentValidationError("reasoning-content-projections.schema: unsupported schema")
    content_revision = _positive_content_revision(
        data["content_revision"], "reasoning-content-projections.content_revision"
    )

    catalog = dict(_mapping(data["selection_catalog"], "reasoning-content-projections.catalog"))
    _keys(
        catalog,
        set(SELECTION_CATALOG_KEYS),
        set(SELECTION_CATALOG_KEYS),
        "reasoning-content-projections.catalog",
    )
    if catalog["schema"] != SELECTION_CATALOG_SCHEMA:
        raise ContentValidationError(
            "reasoning-content-projections.catalog.schema: unsupported schema"
        )
    if (
        _positive_content_revision(
            catalog["content_revision"], "reasoning-content-projections.catalog.content_revision"
        )
        != content_revision
    ):
        raise ContentValidationError("reasoning-content-projections.catalog: revision mismatch")

    catalog_entries = _list(catalog["entries"], "reasoning-content-projections.catalog.entries")
    if not catalog_entries:
        raise ContentValidationError(
            "reasoning-content-projections.catalog.entries: cannot be empty"
        )
    catalog_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_entry in enumerate(catalog_entries):
        path = f"reasoning-content-projections.catalog.entries[{index}]"
        entry = dict(_mapping(raw_entry, path))
        _keys(entry, set(SELECTION_CATALOG_ENTRY_KEYS), set(SELECTION_CATALOG_ENTRY_KEYS), path)
        if entry["schema"] != SELECTION_CATALOG_ENTRY_SCHEMA:
            raise ContentValidationError(f"{path}.schema: unsupported schema")
        method_id = _string(entry["method_id"], f"{path}.method_id")
        if not _ID_RE.fullmatch(method_id) or method_id in catalog_by_id:
            raise ContentValidationError(f"{path}.method_id: expected a unique MethodId")
        if not isinstance(entry["family"], str) or not _FAMILY_ID_RE.fullmatch(entry["family"]):
            raise ContentValidationError(f"{path}.family: invalid family identifier")
        if (
            _positive_content_revision(entry["content_revision"], f"{path}.content_revision")
            != content_revision
        ):
            raise ContentValidationError(f"{path}.content_revision: revision mismatch")
        names = _localized_text(entry["display_name"], f"{path}.display_name")
        purpose = _localized_text(entry["core_purpose"], f"{path}.core_purpose")
        if set(names) != set(purpose):
            raise ContentValidationError(f"{path}: name and purpose locales must match")
        for field in (
            "suitable_features",
            "unsuitable_features",
            "commonly_confused_features",
            "related_method_ids",
        ):
            _unique_strings(entry[field], f"{path}.{field}")
        if any(not _ID_RE.fullmatch(related_id) for related_id in entry["related_method_ids"]):
            raise ContentValidationError(f"{path}.related_method_ids: invalid MethodId")
        expected_locator = f"injectable-content/{content_revision}/{method_id}"
        if entry["injectable_content_locator"] != expected_locator:
            raise ContentValidationError(f"{path}.injectable_content_locator: unexpected locator")
        catalog_by_id[method_id] = entry

    raw_injectable = _list(
        data["injectable_content"], "reasoning-content-projections.injectable_content"
    )
    if not raw_injectable:
        raise ContentValidationError(
            "reasoning-content-projections.injectable_content: cannot be empty"
        )
    injectable_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, raw_content in enumerate(raw_injectable):
        path = f"reasoning-content-projections.injectable_content[{index}]"
        content = dict(_mapping(raw_content, path))
        _keys(
            content,
            set(INJECTABLE_REASONING_CONTENT_KEYS),
            set(INJECTABLE_REASONING_CONTENT_KEYS),
            path,
        )
        if content["schema"] != INJECTABLE_REASONING_CONTENT_SCHEMA:
            raise ContentValidationError(f"{path}.schema: unsupported schema")
        method_id = _string(content["method_id"], f"{path}.method_id")
        locale = content["locale"]
        if method_id not in catalog_by_id or locale not in {"en", "ko"}:
            raise ContentValidationError(f"{path}: unknown method or locale")
        if (
            _positive_content_revision(content["content_revision"], f"{path}.content_revision")
            != content_revision
        ):
            raise ContentValidationError(f"{path}.content_revision: revision mismatch")
        key = (method_id, locale)
        if key in injectable_by_key:
            raise ContentValidationError(f"{path}: duplicate method/locale content")
        if content["display_name"] != catalog_by_id[method_id]["display_name"].get(locale):
            raise ContentValidationError(f"{path}.display_name: catalog name mismatch")
        if not isinstance(content["theory"], str) or not content["theory"].strip():
            raise ContentValidationError(f"{path}.theory: non-empty authored theory required")
        examples = _list(content["template_examples"], f"{path}.template_examples")
        case_ids: set[str] = set()
        if not examples:
            raise ContentValidationError(f"{path}.template_examples: cannot be empty")
        for example_index, raw_example in enumerate(examples):
            example_path = f"{path}.template_examples[{example_index}]"
            example = dict(_mapping(raw_example, example_path))
            _keys(example, set(TEMPLATE_EXAMPLE_KEYS), set(TEMPLATE_EXAMPLE_KEYS), example_path)
            if example["schema"] != TEMPLATE_EXAMPLE_SCHEMA:
                raise ContentValidationError(f"{example_path}.schema: unsupported schema")
            case_id = _string(example["case_id"], f"{example_path}.case_id")
            if case_id in case_ids:
                raise ContentValidationError(f"{example_path}.case_id: duplicate case ID")
            case_ids.add(case_id)
            for field in ("kind", "template_prompt", "expected_behavior", "rationale"):
                _string(example[field], f"{example_path}.{field}")
            expected_route = example["expected_route"]
            if expected_route is not None and expected_route not in catalog_by_id:
                raise ContentValidationError(f"{example_path}.expected_route: unknown MethodId")
            decisive_features = _list(
                example["decisive_features"], f"{example_path}.decisive_features"
            )
            if any(
                not isinstance(feature, str) or not feature.strip() for feature in decisive_features
            ):
                raise ContentValidationError(
                    f"{example_path}.decisive_features: expected non-empty strings"
                )
        injectable_by_key[key] = content

    for method_id, entry in catalog_by_id.items():
        available_locales = {
            locale for candidate_id, locale in injectable_by_key if candidate_id == method_id
        }
        if "en" not in available_locales or available_locales != set(entry["display_name"]):
            raise ContentValidationError(
                "reasoning-content-projections: catalog and injectable locale completeness mismatch"
            )
        for related_method_id in entry["related_method_ids"]:
            if related_method_id not in catalog_by_id:
                raise ContentValidationError(
                    "reasoning-content-projections: related method must resolve in catalog"
                )
    return data
