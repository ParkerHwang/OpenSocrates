"""Deterministic v1 routing policy.

The semantic classifier supplies only closed feature codes.  This module owns
the participation gate, the frozen 48-method matrix, scoring, tie-breaking,
fallbacks, and the optional complementary method.  It never parses YAML or
reads host data; a compiled typed bundle may be supplied by the content layer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError
from ..version import ROUTER_VERSION
from .enums import (
    AnswerShape,
    ClassificationConfidence,
    FeatureBasis,
    FeatureKey,
    Participation,
    RouterReasonCode,
)
from .models import (
    CompiledContentBundle,
    CompiledMethod,
    ParticipationDecision,
    RouterDecision,
    RoutingFeature,
    RoutingFeatures,
)
from .participation import validate_participation_decision


@dataclass(frozen=True, slots=True)
class RouteMethod:
    """Typed route metadata used by the deterministic scorer."""

    id: str
    family: str
    positive_features: tuple[tuple[FeatureKey, int], ...]
    negative_features: tuple[tuple[FeatureKey, int], ...]
    minimum_score: int
    contraindications: frozenset[FeatureKey]
    preferred_complement: str | None
    allowed_answer_shapes: frozenset[AnswerShape]
    prompt_token_cost: int = 0
    incompatible_secondary: frozenset[str] = frozenset()
    output_sections: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            raise ValidationError("route method: method ID must be non-empty text")
        if not isinstance(self.family, str) or not self.family:
            raise ValidationError("route method: family must be non-empty text")
        if (
            not isinstance(self.minimum_score, int)
            or isinstance(self.minimum_score, bool)
            or not 3 <= self.minimum_score <= 9
        ):
            raise ValidationError("route method: minimum score must be 3..9")
        if (
            not isinstance(self.prompt_token_cost, int)
            or isinstance(self.prompt_token_cost, bool)
            or self.prompt_token_cost < 0
        ):
            raise ValidationError("route method: prompt token cost cannot be negative")
        for key, weight in (*self.positive_features, *self.negative_features):
            if not isinstance(key, FeatureKey) or not 1 <= weight <= 3:
                raise ValidationError(
                    "route method: feature weights must use closed keys and range 1..3"
                )
        if any(not isinstance(key, FeatureKey) for key in self.contraindications):
            raise ValidationError("route method: contraindications must use closed feature keys")
        if any(not isinstance(shape, AnswerShape) for shape in self.allowed_answer_shapes):
            raise ValidationError("route method: answer shapes must be closed values")


@dataclass(frozen=True, slots=True)
class RoutingCatalog:
    """Immutable catalog protocol for compiled method metadata."""

    methods: tuple[RouteMethod, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.methods, tuple) or not self.methods:
            raise ValidationError("routing catalog: at least one typed method is required")
        if any(not isinstance(method, RouteMethod) for method in self.methods):
            raise ValidationError("routing catalog: methods must be typed RouteMethod values")
        ids = [method.id for method in self.methods]
        if len(ids) != len(set(ids)):
            raise ValidationError("routing catalog: method IDs must be unique")

    @classmethod
    def from_bundle(cls, bundle: CompiledContentBundle) -> "RoutingCatalog":
        """Project a validated compiled-content bundle into route metadata."""

        if not isinstance(bundle, CompiledContentBundle):
            raise ValidationError("routing catalog: expected CompiledContentBundle")
        if tuple(bundle.method_ids) != tuple(sorted(bundle.method_ids)):
            raise ValidationError("routing catalog: compiled method IDs must be sorted")
        methods = tuple(_route_method_from_compiled(method) for method in bundle.methods)
        if tuple(method.id for method in methods) != tuple(bundle.method_ids):
            raise ValidationError(
                "routing catalog: compiled method IDs do not match method objects"
            )
        return cls(methods)


@dataclass(frozen=True, slots=True)
class MethodScore:
    """Deterministic score details useful to callers and walkthroughs."""

    method: RouteMethod
    score: int
    active_contraindications: tuple[FeatureKey, ...]
    exact_answer_shape: bool


@dataclass(frozen=True, slots=True)
class RoutingPayloadValidation:
    """Result of a boundary validation that preserves whole-list semantics."""

    features: RoutingFeatures | None
    structurally_valid: bool
    invalid_feature_list: bool


def _shape_values(*values: str) -> frozenset[AnswerShape]:
    return frozenset(AnswerShape(value) for value in values)


_SHAPES: dict[str, frozenset[AnswerShape]] = {
    "abduction": _shape_values("direct_judgment", "diagnostic"),
    "argument-mapping": _shape_values("structured_plan", "direct_judgment"),
    "assumption-mapping": _shape_values("structured_plan", "completion_review"),
    "bayesian-updating": _shape_values("evidence_reconciliation", "direct_judgment"),
    "boundary-critique": _shape_values("direct_judgment"),
    "causal-loop-diagramming": _shape_values("diagnostic", "direct_judgment"),
    "causal-reasoning": _shape_values("diagnostic", "direct_judgment"),
    "conceptual-analysis": _shape_values("direct_judgment"),
    "cost-benefit-analysis": _shape_values("decision_memo"),
    "critical-thinking": _shape_values("critique", "risk_assessment"),
    "cynefin-framework": _shape_values("decision_memo", "structured_plan"),
    "decision-tree-analysis": _shape_values("decision_memo"),
    "deduction": _shape_values("direct_judgment", "diagnostic"),
    "defeasible-reasoning": _shape_values("direct_judgment", "diagnostic"),
    "deontic-reasoning": _shape_values("direct_judgment", "decision_memo"),
    "design-thinking": _shape_values("structured_plan", "decision_memo"),
    "double-loop-learning": _shape_values("structured_plan", "completion_review"),
    "evidence-hierarchy": _shape_values("evidence_reconciliation", "direct_judgment"),
    "failure-mode-effects-analysis": _shape_values("critique", "risk_assessment"),
    "falsificationism": _shape_values("evidence_reconciliation", "direct_judgment"),
    "first-principles": _shape_values("direct_judgment"),
    "game-theory": _shape_values("decision_memo", "structured_plan"),
    "induction": _shape_values("direct_judgment", "diagnostic"),
    "jobs-to-be-done": _shape_values("direct_judgment", "decision_memo"),
    "lateral-thinking": _shape_values("structured_plan", "decision_memo"),
    "lean-startup": _shape_values("structured_plan", "completion_review"),
    "logic-tree": _shape_values("structured_plan", "direct_judgment"),
    "mece": _shape_values("structured_plan", "direct_judgment"),
    "morphological-analysis": _shape_values("structured_plan", "decision_memo"),
    "pdca-cycle": _shape_values("structured_plan", "completion_review"),
    "pestel-analysis": _shape_values("decision_memo", "structured_plan"),
    "pragmatism": _shape_values("direct_judgment", "decision_memo"),
    "premortem-analysis": _shape_values("critique", "risk_assessment"),
    "pyramid-principle": _shape_values("structured_plan", "direct_judgment"),
    # Document 04's closed AnswerShape set has no ``forecast`` value; forecast
    # authoring metadata therefore participates in the decision-memo shape.
    "reference-class-forecasting": _shape_values("decision_memo"),
    "reflective-equilibrium": _shape_values("direct_judgment", "decision_memo"),
    "robust-decision-making": _shape_values("decision_memo"),
    "root-cause-analysis": _shape_values("diagnostic", "direct_judgment"),
    "scenario-planning": _shape_values("decision_memo"),
    "sensitivity-analysis": _shape_values("decision_memo"),
    "socratic-questioning": _shape_values("direct_judgment"),
    "stakeholder-analysis": _shape_values("decision_memo", "structured_plan"),
    "steelman-reasoning": _shape_values("critique", "risk_assessment"),
    "systems-thinking": _shape_values("diagnostic", "direct_judgment"),
    "trade-off-analysis": _shape_values("decision_memo", "direct_judgment"),
    "triangulation": _shape_values("evidence_reconciliation", "direct_judgment"),
    "triz": _shape_values("structured_plan", "decision_memo"),
    "value-of-information": _shape_values("decision_memo"),
}


# Method | family | positive additions | negative additions | minimum |
# additional contraindications | preferred complement.  The global mechanical
# negative/contraindication is added exactly once by _build_default_catalog.
_FROZEN_ROWS: tuple[
    tuple[str, str, dict[str, int], dict[str, int], int, tuple[str, ...], str], ...
] = (
    (
        "boundary-critique",
        "framing",
        {"boundary_sensitive": 3, "stakeholder_conflict": 1},
        {},
        5,
        (),
        "stakeholder-analysis",
    ),
    (
        "conceptual-analysis",
        "framing",
        {"ambiguous_terms": 3, "argument_dispute": 2},
        {},
        5,
        (),
        "argument-mapping",
    ),
    (
        "first-principles",
        "framing",
        {"hidden_assumptions": 3, "stale_options": 2},
        {"explicit_rules": 1},
        5,
        (),
        "morphological-analysis",
    ),
    (
        "socratic-questioning",
        "framing",
        {"decisive_input_missing": 3, "ambiguous_terms": 2},
        {},
        5,
        (),
        "assumption-mapping",
    ),
    (
        "argument-mapping",
        "structuring",
        {"argument_dispute": 3, "critique": 2, "tangled_hierarchy": 1},
        {},
        5,
        (),
        "evidence-hierarchy",
    ),
    (
        "logic-tree",
        "structuring",
        {"tangled_hierarchy": 3, "diagnose": 2, "plan": 1},
        {"feedback_delay": 2},
        5,
        (),
        "root-cause-analysis",
    ),
    (
        "mece",
        "structuring",
        {"category_overlap": 3, "tangled_hierarchy": 2},
        {"feedback_delay": 2},
        5,
        (),
        "logic-tree",
    ),
    (
        "pyramid-principle",
        "structuring",
        {"explain": 3, "tangled_hierarchy": 2},
        {"hidden_assumptions": 1},
        5,
        (),
        "argument-mapping",
    ),
    (
        "abduction",
        "logical_reasoning",
        {"competing_explanations": 3, "diagnose": 2},
        {"explicit_rules": 2},
        5,
        (),
        "value-of-information",
    ),
    (
        "deduction",
        "logical_reasoning",
        {"explicit_rules": 3, "explain": 2},
        {"unknown_probability": 2},
        5,
        (),
        "conceptual-analysis",
    ),
    (
        "defeasible-reasoning",
        "logical_reasoning",
        {"exception_prone_rule": 3, "explicit_rules": 2},
        {},
        5,
        (),
        "premortem-analysis",
    ),
    (
        "induction",
        "logical_reasoning",
        {"repeated_observations": 3, "weak_sample": 2},
        {"causal_question": 2},
        5,
        (),
        "evidence-hierarchy",
    ),
    (
        "bayesian-updating",
        "evidence_verification",
        {"new_evidence": 3, "unknown_probability": 2, "competing_explanations": 1},
        {},
        5,
        (),
        "abduction",
    ),
    (
        "evidence-hierarchy",
        "evidence_verification",
        {"source_quality": 3, "reconcile_evidence": 2, "conflicting_sources": 1},
        {"value_conflict": 2},
        5,
        (),
        "triangulation",
    ),
    (
        "falsificationism",
        "evidence_verification",
        {"testable_claim": 3, "critique": 2},
        {},
        5,
        ("no_testable_implication",),
        "lean-startup",
    ),
    (
        "triangulation",
        "evidence_verification",
        {"reconcile_evidence": 3, "conflicting_sources": 2, "source_quality": 2},
        {},
        5,
        (),
        "evidence-hierarchy",
    ),
    (
        "causal-reasoning",
        "causal_systems",
        {"causal_question": 3, "confounding": 2},
        {},
        5,
        (),
        "falsificationism",
    ),
    (
        "root-cause-analysis",
        "causal_systems",
        {"recurring_failure": 3, "diagnose": 3},
        {"macro_environment": 1},
        5,
        (),
        "failure-mode-effects-analysis",
    ),
    (
        "systems-thinking",
        "causal_systems",
        {"feedback_delay": 3, "causal_question": 2, "deep_uncertainty": 1},
        {},
        5,
        (),
        "causal-loop-diagramming",
    ),
    (
        "causal-loop-diagramming",
        "causal_systems",
        {"feedback_delay": 3, "recurring_failure": 2},
        {},
        5,
        (),
        "systems-thinking",
    ),
    (
        "critical-thinking",
        "critical_counterexample",
        {"critique": 3, "hidden_assumptions": 2, "argument_dispute": 1},
        {},
        4,
        (),
        "argument-mapping",
    ),
    (
        "failure-mode-effects-analysis",
        "critical_counterexample",
        {"failure_risk": 3, "plan": 2, "review_completion": 1},
        {},
        5,
        (),
        "premortem-analysis",
    ),
    (
        "premortem-analysis",
        "critical_counterexample",
        {"chosen_plan": 3, "failure_risk": 3},
        {},
        5,
        (),
        "failure-mode-effects-analysis",
    ),
    (
        "steelman-reasoning",
        "critical_counterexample",
        {"dismissed_opposition": 3, "argument_dispute": 2, "critique": 1},
        {},
        5,
        (),
        "reflective-equilibrium",
    ),
    (
        "design-thinking",
        "creative_reframing",
        {"human_need": 3, "user_progress": 2},
        {},
        5,
        (),
        "jobs-to-be-done",
    ),
    (
        "lateral-thinking",
        "creative_reframing",
        {"stale_options": 3, "choose": 2},
        {},
        5,
        ("safety_critical_validation",),
        "trade-off-analysis",
    ),
    (
        "morphological-analysis",
        "creative_reframing",
        {"combinable_dimensions": 3, "stale_options": 2},
        {},
        5,
        ("no_coherent_dimensions",),
        "first-principles",
    ),
    (
        "triz",
        "creative_reframing",
        {"technical_contradiction": 3, "plan": 2},
        {"value_conflict": 1},
        5,
        (),
        "systems-thinking",
    ),
    (
        "deontic-reasoning",
        "values_purpose",
        {"duties_rights": 3, "explicit_rules": 2},
        {},
        5,
        (),
        "reflective-equilibrium",
    ),
    (
        "jobs-to-be-done",
        "values_purpose",
        {"user_progress": 3, "human_need": 2},
        {},
        5,
        (),
        "design-thinking",
    ),
    (
        "pragmatism",
        "values_purpose",
        {"practical_consequence": 3, "choose": 2, "value_conflict": 1},
        {"duties_rights": 2},
        5,
        (),
        "lean-startup",
    ),
    (
        "reflective-equilibrium",
        "values_purpose",
        {"value_conflict": 3, "argument_dispute": 2},
        {},
        5,
        ("binding_rule_without_discretion",),
        "steelman-reasoning",
    ),
    (
        "cost-benefit-analysis",
        "decision_optimization",
        {"multiple_objectives": 3, "multiple_options": 2, "choose": 1},
        {"duties_rights": 2},
        5,
        (),
        "sensitivity-analysis",
    ),
    (
        "decision-tree-analysis",
        "decision_optimization",
        {"sequential_choice": 3, "unknown_probability": 2, "choose": 1},
        {},
        5,
        (),
        "scenario-planning",
    ),
    (
        "trade-off-analysis",
        "decision_optimization",
        {"multiple_options": 3, "multiple_objectives": 3, "choose": 2},
        {"single_feasible_option": 2},
        4,
        ("binding_rule_without_discretion",),
        "sensitivity-analysis",
    ),
    (
        "value-of-information",
        "decision_optimization",
        {"information_purchase": 3, "unknown_probability": 2, "choose": 2},
        {"irreversible_choice": 1},
        5,
        (),
        "bayesian-updating",
    ),
    (
        "reference-class-forecasting",
        "future_uncertainty",
        {"forecast": 3, "reference_cases": 3},
        {},
        5,
        ("no_defensible_reference_class",),
        "sensitivity-analysis",
    ),
    (
        "robust-decision-making",
        "future_uncertainty",
        {"deep_uncertainty": 3, "irreversible_choice": 2, "choose": 1},
        {},
        5,
        (),
        "scenario-planning",
    ),
    (
        "scenario-planning",
        "future_uncertainty",
        {"deep_uncertainty": 3, "macro_environment": 2, "forecast": 1},
        {},
        5,
        (),
        "pestel-analysis",
    ),
    (
        "sensitivity-analysis",
        "future_uncertainty",
        {"sensitive_inputs": 3, "unknown_probability": 2, "multiple_objectives": 1},
        {"deep_uncertainty": 1},
        5,
        (),
        "trade-off-analysis",
    ),
    (
        "assumption-mapping",
        "experiment_learning",
        {"hidden_assumptions": 3, "prioritized_assumptions": 3},
        {},
        5,
        (),
        "lean-startup",
    ),
    (
        "double-loop-learning",
        "experiment_learning",
        {"governing_rule": 3, "recurring_failure": 2},
        {},
        5,
        (),
        "root-cause-analysis",
    ),
    (
        "lean-startup",
        "experiment_learning",
        {"testable_hypothesis": 3, "prioritized_assumptions": 2},
        {},
        5,
        ("safety_critical_validation",),
        "jobs-to-be-done",
    ),
    (
        "pdca-cycle",
        "experiment_learning",
        {"repeat_iteration": 3, "plan": 2},
        {"diagnose": 1},
        5,
        (),
        "root-cause-analysis",
    ),
    (
        "cynefin-framework",
        "strategy_actors",
        {"context_disorder": 3, "diagnose": 2, "deep_uncertainty": 1},
        {},
        5,
        (),
        "scenario-planning",
    ),
    (
        "game-theory",
        "strategy_actors",
        {"interacting_actors": 3, "choose": 2},
        {},
        5,
        ("no_meaningful_interdependence",),
        "stakeholder-analysis",
    ),
    (
        "pestel-analysis",
        "strategy_actors",
        {"macro_environment": 3, "forecast": 2},
        {"recurring_failure": 2},
        5,
        (),
        "scenario-planning",
    ),
    (
        "stakeholder-analysis",
        "strategy_actors",
        {"stakeholder_conflict": 3, "interacting_actors": 2},
        {},
        5,
        (),
        "game-theory",
    ),
)


def _weights(values: Mapping[str | FeatureKey, int]) -> tuple[tuple[FeatureKey, int], ...]:
    return tuple(
        (key if isinstance(key, FeatureKey) else FeatureKey(key), weight)
        for key, weight in values.items()
    )


def _build_default_catalog() -> RoutingCatalog:
    return RoutingCatalog(
        tuple(
            RouteMethod(
                id=method_id,
                family=family,
                positive_features=_weights(positive),
                negative_features=(*_weights(negative), (FeatureKey.MECHANICAL, 3)),
                minimum_score=minimum,
                contraindications=frozenset(
                    {FeatureKey.MECHANICAL, *(FeatureKey(key) for key in contraindications)}
                ),
                preferred_complement=complement,
                allowed_answer_shapes=_SHAPES[method_id],
            )
            for method_id, family, positive, negative, minimum, contraindications, complement in _FROZEN_ROWS
        )
    )


DEFAULT_ROUTING_CATALOG = _build_default_catalog()
FROZEN_ROUTING_CATALOG = DEFAULT_ROUTING_CATALOG
METHOD_MATRIX = DEFAULT_ROUTING_CATALOG.methods


def _route_method_from_compiled(method: CompiledMethod) -> RouteMethod:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if not isinstance(method, CompiledMethod):
        raise ValidationError(
            "routing catalog: compiled methods must be typed CompiledMethod values"
        )
    routing = method.routing
    if not isinstance(routing, Mapping):
        raise ValidationError("routing catalog: compiled routing metadata must be an object")
    positive = routing.get("positive_features")
    negative = routing.get("negative_features")
    contraindications = routing.get("contraindications")
    minimum = routing.get("minimum_score")
    if (
        not isinstance(positive, Mapping)
        or not isinstance(negative, Mapping)
        or not isinstance(contraindications, (list, tuple))
    ):
        raise ValidationError("routing catalog: compiled routing metadata is incomplete")
    if not isinstance(minimum, int):
        raise ValidationError("routing catalog: compiled minimum score is invalid")
    participation = method.participation
    shapes = (
        participation.get("allowed_answer_shapes", ()) if isinstance(participation, Mapping) else ()
    )
    if not isinstance(shapes, (list, tuple)):
        raise ValidationError("routing catalog: compiled answer-shape metadata is invalid")
    complements = method.complements
    preferred: str | None = None
    if isinstance(complements, Mapping):
        raw_preferred = complements.get("preferred", ())
        if isinstance(raw_preferred, str):
            preferred = raw_preferred
        elif isinstance(raw_preferred, (list, tuple)) and raw_preferred:
            preferred = raw_preferred[0]
    procedure = method.procedure.get("en", "") if isinstance(method.procedure, Mapping) else ""
    token_cost = len(procedure.split()) if isinstance(procedure, str) else 0
    output_contract = method.output_contract
    sections = (
        output_contract.get("required_sections", ()) if isinstance(output_contract, Mapping) else ()
    )
    try:
        parsed_shapes = {
            shape if isinstance(shape, AnswerShape) else AnswerShape(shape) for shape in shapes
        }
    except (TypeError, ValueError) as exc:
        # Unknown answer shapes are a closed-contract failure.  Do not silently
        # map or drop a stale content value.
        raise ValidationError("routing catalog: compiled answer shape is unknown") from exc
    if not parsed_shapes:
        raise ValidationError("routing catalog: compiled method has no answer shapes")
    try:
        positive_weights = _weights(positive)
        negative_weights = _weights(negative)
        parsed_contraindications = frozenset(
            FeatureKey(value) if not isinstance(value, FeatureKey) else value
            for value in contraindications
        ) | {FeatureKey.MECHANICAL}
        return RouteMethod(
            id=method.id,
            family=method.family,
            positive_features=positive_weights,
            negative_features=negative_weights,
            minimum_score=minimum,
            contraindications=parsed_contraindications,
            preferred_complement=preferred,
            allowed_answer_shapes=frozenset(parsed_shapes),
            prompt_token_cost=token_cost,
            output_sections=tuple(sections) if isinstance(sections, (list, tuple)) else (),
        )
    except (TypeError, ValueError) as exc:
        raise ValidationError("routing catalog: compiled feature metadata is invalid") from exc


def catalog_from_bundle(bundle: CompiledContentBundle) -> RoutingCatalog:
    return RoutingCatalog.from_bundle(bundle)


def _no_route(
    answer_shape: AnswerShape,
    *,
    reason: RouterReasonCode,
    explicit: bool = False,
    prompt_bundle_hash: str | None = None,
) -> RouterDecision:
    return RouterDecision(
        router_version=ROUTER_VERSION,
        answer_shape=answer_shape,
        primary_family=None,
        secondary_family=None,
        primary_method=None,
        secondary_method=None,
        explicit_invocation=explicit,
        reason_code=reason,
        prompt_bundle_hash=prompt_bundle_hash,
    )


def _as_decision(
    participation: ParticipationDecision | Participation,
) -> ParticipationDecision | None:
    if isinstance(participation, ParticipationDecision):
        return validate_participation_decision(participation)
    if isinstance(participation, Participation):
        return None
    raise ValidationError("router: expected ParticipationDecision or Participation")


def validate_routing_features(features: RoutingFeatures) -> RoutingFeatures:
    """Validate the typed feature object without partially repairing it."""

    if not isinstance(features, RoutingFeatures):
        raise ValidationError("routing features: expected RoutingFeatures")
    if len(features.features) > 16:
        raise ValidationError("routing features: at most 16 features are allowed")
    keys = [feature.key for feature in features.features]
    if len(keys) != len(set(keys)):
        raise ValidationError("routing features: duplicate feature keys are invalid")
    for feature in features.features:
        if not isinstance(feature, RoutingFeature):
            raise ValidationError("routing features: feature entries must be typed")
        if not 1 <= feature.strength <= 3:
            raise ValidationError("routing features: strength must be 1..3")
        if not isinstance(feature.basis, FeatureBasis):
            raise ValidationError("routing features: unknown feature basis")
    return features


def validate_routing_payload(payload: Mapping[str, Any]) -> RoutingPayloadValidation:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Validate a raw boundary object while preserving whole-list fallback.

    This adapter is intentionally narrow and does not accept prompt text or
    free-form fields.  Unknown/duplicate feature keys make the complete list
    invalid; they never become a partially scored subset.
    """

    if not isinstance(payload, Mapping):
        return RoutingPayloadValidation(None, False, False)
    expected_keys = {
        "schema",
        "answer_shape",
        "features",
        "classification_confidence",
        "explicit_method",
    }
    if set(payload) != expected_keys:
        return RoutingPayloadValidation(None, False, False)
    try:
        if payload.get("schema") != RoutingFeatures.__schema_id__:
            return RoutingPayloadValidation(None, False, False)
        answer_shape = AnswerShape(payload["answer_shape"])
        confidence = ClassificationConfidence(payload["classification_confidence"])
    except (KeyError, ValueError, TypeError):
        return RoutingPayloadValidation(None, False, False)
    explicit_method = payload["explicit_method"]
    if explicit_method is not None and not isinstance(explicit_method, str):
        return RoutingPayloadValidation(None, False, False)
    raw_features = payload["features"]
    if not isinstance(raw_features, list) or len(raw_features) > 16:
        return RoutingPayloadValidation(None, False, False)
    parsed: list[RoutingFeature] = []
    seen: set[FeatureKey] = set()
    invalid_list = False
    for raw in raw_features:
        if not isinstance(raw, Mapping) or set(raw) != {"key", "strength", "basis"}:
            return RoutingPayloadValidation(None, False, False)
        try:
            key = FeatureKey(raw["key"])
        except (ValueError, TypeError):
            invalid_list = True
            continue
        try:
            basis = FeatureBasis(raw["basis"])
        except (ValueError, TypeError):
            return RoutingPayloadValidation(None, False, False)
        strength = raw["strength"]
        if not isinstance(strength, int) or isinstance(strength, bool) or not 1 <= strength <= 3:
            return RoutingPayloadValidation(None, False, False)
        if key in seen:
            invalid_list = True
            continue
        seen.add(key)
        parsed.append(RoutingFeature(key=key, strength=strength, basis=basis))
    if invalid_list:
        parsed = []
    try:
        normalized = RoutingFeatures(
            answer_shape=answer_shape,
            features=tuple(parsed),
            classification_confidence=confidence,
            explicit_method=explicit_method,
        )
    except Exception:
        return RoutingPayloadValidation(None, False, False)
    return RoutingPayloadValidation(normalized, True, invalid_list)


def _coerce_features(features: RoutingFeatures | Mapping[str, Any]) -> RoutingPayloadValidation:
    if isinstance(features, RoutingFeatures):
        try:
            return RoutingPayloadValidation(validate_routing_features(features), True, False)
        except ValidationError:
            return RoutingPayloadValidation(None, False, False)
    return validate_routing_payload(features)


def _feature_map(features: RoutingFeatures) -> dict[FeatureKey, int]:
    return {feature.key: feature.strength for feature in features.features}


def score_method(method: RouteMethod, features: RoutingFeatures) -> MethodScore:
    """Apply the exact weighted matrix equation to one method."""

    if not isinstance(method, RouteMethod):
        raise ValidationError("router scorer: expected RouteMethod")
    validate_routing_features(features)
    strengths = _feature_map(features)
    score = sum(weight * strengths.get(key, 0) for key, weight in method.positive_features)
    negatives = dict(method.negative_features)
    negatives.setdefault(FeatureKey.MECHANICAL, 3)
    score -= sum(weight * strengths.get(key, 0) for key, weight in negatives.items())
    active = tuple(
        sorted(
            (key for key in method.contraindications if key in strengths), key=lambda key: key.value
        )
    )
    score -= 12 * len(active)
    return MethodScore(
        method=method,
        score=score,
        active_contraindications=active,
        exact_answer_shape=features.answer_shape in method.allowed_answer_shapes,
    )


def _score_sort_key(item: MethodScore) -> tuple[int, int, int, int, str]:
    return (
        -item.score,
        -int(item.exact_answer_shape),
        len(item.active_contraindications),
        item.method.prompt_token_cost,
        item.method.id,
    )


def _nonredundant(primary: RouteMethod, secondary: RouteMethod) -> bool:
    if primary.output_sections and secondary.output_sections:
        return primary.output_sections != secondary.output_sections
    return primary.family != secondary.family


def _compatible(primary: RouteMethod, secondary: RouteMethod) -> bool:
    if primary.id == secondary.id or primary.family == secondary.family:
        return False
    if (
        secondary.id in primary.incompatible_secondary
        or primary.id in secondary.incompatible_secondary
    ):
        return False
    return (
        primary.preferred_complement == secondary.id or secondary.preferred_complement == primary.id
    )


def _select_secondary(primary: MethodScore, ranked: Sequence[MethodScore]) -> MethodScore | None:
    for candidate in ranked:
        if candidate.method.id == primary.method.id:
            continue
        if candidate.score * 5 < primary.score * 4:
            continue
        if candidate.active_contraindications:
            continue
        if not _compatible(primary.method, candidate.method):
            continue
        if not _nonredundant(primary.method, candidate.method):
            continue
        return candidate
    return None


_FALLBACKS: dict[AnswerShape, tuple[str, str | None]] = {
    AnswerShape.DIRECT_JUDGMENT: ("critical-thinking", None),
    AnswerShape.DECISION_MEMO: ("trade-off-analysis", "sensitivity-analysis"),
    AnswerShape.DIAGNOSTIC: ("root-cause-analysis", None),
    AnswerShape.CRITIQUE: ("argument-mapping", "critical-thinking"),
    AnswerShape.RISK_ASSESSMENT: ("premortem-analysis", "failure-mode-effects-analysis"),
    AnswerShape.EVIDENCE_RECONCILIATION: ("evidence-hierarchy", "triangulation"),
    AnswerShape.STRUCTURED_PLAN: ("logic-tree", "premortem-analysis"),
    AnswerShape.COMPLETION_REVIEW: ("critical-thinking", None),
}
_UNCERTAINTY_FEATURES = frozenset(
    {
        FeatureKey.DEEP_UNCERTAINTY,
        FeatureKey.UNKNOWN_PROBABILITY,
        FeatureKey.SENSITIVE_INPUTS,
        FeatureKey.REFERENCE_CASES,
    }
)


def _fallback_decision(
    features: RoutingFeatures,
    catalog: RoutingCatalog,
    *,
    reason: RouterReasonCode,
    uncertainty_explicit: bool,
    prompt_bundle_hash: str | None,
) -> RouterDecision:
    primary_id, secondary_id = _FALLBACKS[features.answer_shape]
    if features.answer_shape is AnswerShape.DECISION_MEMO and not uncertainty_explicit:
        secondary_id = None
    by_id = {method.id: method for method in catalog.methods}
    primary = by_id.get(primary_id)
    secondary = by_id.get(secondary_id) if secondary_id else None
    if primary is None:
        return _no_route(
            features.answer_shape,
            reason=RouterReasonCode.NO_ELIGIBLE_METHOD,
            prompt_bundle_hash=prompt_bundle_hash,
        )
    return RouterDecision(
        router_version=ROUTER_VERSION,
        answer_shape=features.answer_shape,
        primary_family=primary.family,
        secondary_family=secondary.family if secondary else None,
        primary_method=primary.id,
        secondary_method=secondary.id if secondary else None,
        explicit_invocation=False,
        reason_code=reason,
        prompt_bundle_hash=prompt_bundle_hash,
    )


def route_features(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    participation: ParticipationDecision | Participation,
    features: RoutingFeatures | Mapping[str, Any],
    *,
    catalog: RoutingCatalog = DEFAULT_ROUTING_CATALOG,
    prompt_bundle_hash: str | None = None,
) -> RouterDecision:
    """Return one deterministic RouterDecision for a validated target."""

    if not isinstance(catalog, RoutingCatalog):
        raise ValidationError("router: expected RoutingCatalog")
    decision = _as_decision(participation)
    participation_kind = decision.participation if decision is not None else participation
    payload = _coerce_features(features)
    if payload.features is None:
        # A structurally invalid answer shape/object is rejected before any
        # fallback.  There is no closed reason code for malformed payloads, so
        # the no-route result uses the safe no_eligible_method code.
        return _no_route(
            AnswerShape.DIRECT_JUDGMENT,
            reason=RouterReasonCode.NO_ELIGIBLE_METHOD,
            prompt_bundle_hash=prompt_bundle_hash,
        )
    normalized = payload.features
    explicit_id = normalized.explicit_method
    if participation_kind is Participation.MECHANICAL:
        return _no_route(
            normalized.answer_shape,
            reason=RouterReasonCode.NO_ELIGIBLE_METHOD,
            explicit=explicit_id is not None
            or (decision is not None and decision.explicit_method is not None),
            prompt_bundle_hash=prompt_bundle_hash,
        )
    if decision is not None:
        if decision.explicit_method is not None:
            if explicit_id is not None and explicit_id != decision.explicit_method:
                return _no_route(
                    normalized.answer_shape,
                    reason=RouterReasonCode.NO_ELIGIBLE_METHOD,
                    explicit=True,
                    prompt_bundle_hash=prompt_bundle_hash,
                )
            explicit_id = decision.explicit_method
    if payload.invalid_feature_list:
        return _fallback_decision(
            normalized,
            catalog,
            reason=RouterReasonCode.INVALID_FEATURES_FALLBACK,
            uncertainty_explicit=False,
            prompt_bundle_hash=prompt_bundle_hash,
        )

    by_id = {method.id: method for method in catalog.methods}
    if explicit_id is not None:
        explicit = by_id.get(explicit_id)
        if explicit is None:
            return _no_route(
                normalized.answer_shape,
                reason=RouterReasonCode.NO_ELIGIBLE_METHOD,
                explicit=True,
                prompt_bundle_hash=prompt_bundle_hash,
            )
        scored_explicit = score_method(explicit, normalized)
        if scored_explicit.active_contraindications:
            return _no_route(
                normalized.answer_shape,
                reason=RouterReasonCode.CONTRAINDICATED_EXPLICIT_METHOD,
                explicit=True,
                prompt_bundle_hash=prompt_bundle_hash,
            )
        return RouterDecision(
            router_version=ROUTER_VERSION,
            answer_shape=normalized.answer_shape,
            primary_family=explicit.family,
            secondary_family=None,
            primary_method=explicit.id,
            secondary_method=None,
            explicit_invocation=True,
            reason_code=RouterReasonCode.EXPLICIT_METHOD,
            prompt_bundle_hash=prompt_bundle_hash,
        )

    scored = [score_method(method, normalized) for method in catalog.methods]
    eligible = [item for item in scored if item.score >= item.method.minimum_score]
    if not eligible:
        return _fallback_decision(
            normalized,
            catalog,
            reason=RouterReasonCode.ANSWER_SHAPE_FALLBACK,
            uncertainty_explicit=bool(_UNCERTAINTY_FEATURES.intersection(_feature_map(normalized))),
            prompt_bundle_hash=prompt_bundle_hash,
        )
    ranked = sorted(eligible, key=_score_sort_key)
    primary = ranked[0]
    secondary = _select_secondary(primary, ranked)
    return RouterDecision(
        router_version=ROUTER_VERSION,
        answer_shape=normalized.answer_shape,
        primary_family=primary.method.family,
        secondary_family=secondary.method.family if secondary else None,
        primary_method=primary.method.id,
        secondary_method=secondary.method.id if secondary else None,
        explicit_invocation=False,
        reason_code=(
            RouterReasonCode.WEIGHTED_PRIMARY_WITH_COMPLEMENT
            if secondary
            else RouterReasonCode.WEIGHTED_PRIMARY
        ),
        prompt_bundle_hash=prompt_bundle_hash,
    )


def route(
    participation: ParticipationDecision | Participation,
    features: RoutingFeatures | Mapping[str, Any],
    *,
    catalog: RoutingCatalog = DEFAULT_ROUTING_CATALOG,
    prompt_bundle_hash: str | None = None,
) -> RouterDecision:
    return route_features(
        participation, features, catalog=catalog, prompt_bundle_hash=prompt_bundle_hash
    )


def route_from_bundle(
    participation: ParticipationDecision | Participation,
    features: RoutingFeatures | Mapping[str, Any],
    bundle: CompiledContentBundle,
    *,
    prompt_bundle_hash: str | None = None,
) -> RouterDecision:
    return route_features(
        participation,
        features,
        catalog=RoutingCatalog.from_bundle(bundle),
        prompt_bundle_hash=prompt_bundle_hash,
    )


# Application-facing aliases.
deterministic_route = route_features
route_routing_features = route_features
validate_features = validate_routing_features
DEFAULT_CATALOG = DEFAULT_ROUTING_CATALOG
ROUTING_MATRIX = METHOD_MATRIX
FROZEN_ROUTING_MATRIX = METHOD_MATRIX


__all__ = [
    "DEFAULT_ROUTING_CATALOG",
    "DEFAULT_CATALOG",
    "FROZEN_ROUTING_MATRIX",
    "FROZEN_ROUTING_CATALOG",
    "METHOD_MATRIX",
    "MethodScore",
    "RouteMethod",
    "RoutingCatalog",
    "RoutingPayloadValidation",
    "catalog_from_bundle",
    "deterministic_route",
    "route",
    "route_features",
    "route_from_bundle",
    "route_routing_features",
    "ROUTING_MATRIX",
    "score_method",
    "validate_features",
    "validate_routing_features",
    "validate_routing_payload",
]
