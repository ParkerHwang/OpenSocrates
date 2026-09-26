"""Mechanical decision envelopes and safe diagnostics, never semantic classification."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from ..domain.enums import (
    AnswerShape,
    ClassificationConfidence,
    FeatureBasis,
    FeatureKey,
    Participation,
)
from ..domain.models import RoutingFeatures

OPERATIONS = ("catalog", "prepare", "select", "acknowledge", "reset")
SELECT_FIELDS = (
    "operation",
    "context",
    "epoch",
    "decision",
    "revision",
    "locale",
    "participation",
    "routing",
)
ROUTING_FIELDS = (
    "schema",
    "answer_shape",
    "classification_confidence",
    "explicit_method",
    "features",
)


class DecisionRequestError(ValueError):
    """Only trusted paths, codes and vocabulary may be passed to this exception."""

    def __init__(self, code: str, path: str, allowed: tuple[str, ...] = ()) -> None:
        super().__init__(code)
        self.diagnostic: dict[str, Any] = {"code": code, "field_path": path}
        if allowed:
            self.diagnostic["allowed_values"] = list(allowed)


def closed_object(value: Any, path: str, fields: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionRequestError("expected_object", path)
    for field in fields:
        if field not in value:
            raise DecisionRequestError("required_field", f"{path}.{field}")
    if set(value) != set(fields):
        # Unknown names may themselves contain private input. Do not return them.
        raise DecisionRequestError("unexpected_field", path)
    return value


def enum_value(value: Any, path: str, vocabulary: type[StrEnum]) -> None:
    allowed = tuple(item.value for item in vocabulary)
    if not isinstance(value, str) or value not in allowed:
        raise DecisionRequestError("allowed_values", path, allowed)


def nonnegative_integer(value: Any, path: str) -> None:
    if type(value) is not int or value < 0:
        raise DecisionRequestError("nonnegative_integer", path)


def context_identity(value: dict[str, Any]) -> None:
    context = value["context"]
    if (
        not isinstance(context, str)
        or len(context) != 32
        or any(c not in "0123456789abcdef" for c in context)
    ):
        raise DecisionRequestError("opaque_32_lowercase_hex", "$.context")
    nonnegative_integer(value["epoch"], "$.epoch")


def validate_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionRequestError("expected_object", "$")
    operation = value.get("operation")
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise DecisionRequestError("allowed_values", "$.operation", OPERATIONS)
    fields = {
        "catalog": ("operation", "locale"),
        "prepare": ("operation", "locale"),
        "select": SELECT_FIELDS,
        "acknowledge": ("operation", "context", "epoch", "digests"),
        "reset": ("operation",),
    }[operation]
    closed_object(value, "$", fields)
    if "locale" in value and value["locale"] not in ("en", "ko"):
        raise DecisionRequestError("allowed_values", "$.locale", ("en", "ko"))
    if "context" in value:
        context_identity(value)
    if operation == "select":
        validate_select_identity(value)
    return value


def validate_select_identity(value: dict[str, Any]) -> None:
    nonnegative_integer(value["revision"], "$.revision")
    decision = value["decision"]
    if (
        not isinstance(decision, str)
        or not decision.isascii()
        or not decision.isalnum()
        or len(decision) > 64
    ):
        raise DecisionRequestError("ascii_alphanumeric_1_to_64", "$.decision")
    enum_value(value["participation"], "$.participation", Participation)


def diagnose_routing(value: Any) -> DecisionRequestError:
    """Explain a rejected payload. The canonical validator alone accepts routing."""
    try:
        _diagnose_routing(value)
    except DecisionRequestError as exc:
        return exc
    return DecisionRequestError("invalid_routing", "$.routing")


def _diagnose_routing(value: Any) -> None:
    routing = closed_object(value, "$.routing", ROUTING_FIELDS)
    if routing["schema"] != RoutingFeatures.__schema_id__:
        raise DecisionRequestError(
            "allowed_values", "$.routing.schema", (RoutingFeatures.__schema_id__,)
        )
    enum_value(routing["answer_shape"], "$.routing.answer_shape", AnswerShape)
    enum_value(
        routing["classification_confidence"],
        "$.routing.classification_confidence",
        ClassificationConfidence,
    )
    if routing["explicit_method"] is not None and not isinstance(routing["explicit_method"], str):
        raise DecisionRequestError("method_id_or_null", "$.routing.explicit_method")
    features = routing["features"]
    if not isinstance(features, list) or len(features) > 16:
        raise DecisionRequestError("array_max_16", "$.routing.features")
    seen: set[str] = set()
    for index, feature in enumerate(features):
        path = f"$.routing.features[{index}]"
        item = closed_object(feature, path, ("key", "strength", "basis"))
        enum_value(item["key"], path + ".key", FeatureKey)
        enum_value(item["basis"], path + ".basis", FeatureBasis)
        if type(item["strength"]) is not int or not 1 <= item["strength"] <= 3:
            raise DecisionRequestError("integer_1_to_3", path + ".strength")
        if item["key"] in seen:
            raise DecisionRequestError("duplicate_feature", path + ".key")
        seen.add(item["key"])


def prepare_request(locale: str) -> dict[str, Any]:
    """No selection, session mutation, persistence, or invented task semantics."""
    return {
        "status": "prepared",
        "request": {
            "operation": "select",
            "context": uuid4().hex,
            "epoch": 0,
            "decision": "d1",
            "revision": 0,
            "locale": locale,
            "participation": None,
            "routing": {
                "schema": RoutingFeatures.__schema_id__,
                "answer_shape": None,
                "classification_confidence": None,
                "explicit_method": None,
                "features": [],
            },
        },
        "requires_semantic_review": ["participation", "routing"],
        "allowed_values": {
            name: [item.value for item in vocabulary]
            for name, vocabulary in (
                ("participation", Participation),
                ("answer_shape", AnswerShape),
                ("classification_confidence", ClassificationConfidence),
                ("feature_key", FeatureKey),
                ("feature_basis", FeatureBasis),
            )
        },
        "limits": {"features_max": 16, "strength_min": 1, "strength_max": 3},
        "applied": "unverified",
        "selector_model_calls": 0,
        "context_eviction": False,
    }
