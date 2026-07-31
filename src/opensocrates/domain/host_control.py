"""Closed, host-neutral control-envelope validation.

Host adapters are responsible for turning native hook input into a
``NormalizedEvent``.  This module begins after that boundary: it accepts the
small model-to-runtime sideband union, rejects unknown/prohibited data, and
exposes pure lifecycle transition helpers.  It never writes a record or
serializes a host-native response.
"""

from __future__ import annotations

import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, TypeAlias

from ..constants import MAX_CONTROL_DEPTH, MAX_HOST_CONTROL_BYTES
from ..errors import ValidationError
from ..ids import validate_local_id, validate_method_id, validate_turn_token
from .enums import (
    AlternativeDisposition,
    ClaimMateriality,
    ConflictResolution,
    CriterionKind,
    EvidenceState,
    FeedbackOutcome,
    HostControlMessageType,
    HostControlStatus,
    InterventionClass,
    JudgmentStrength,
    Participation,
    RoundingMode,
    SourceKind,
    TaskState,
    TaskTerminalReason,
)
from .models import (
    HostControl,
    HostControlResult,
    ParticipationDecision,
    RigorDecision,
    RoutingFeatures,
)
from .validation import canonical_json, check_forbidden_keys, model_from_dict, validate_model

CONTROL_SCHEMA: Final[str] = HostControl.__schema_id__
CONTROL_RESULT_SCHEMA: Final[str] = HostControlResult.__schema_id__
CONTROL_KEYS: Final[frozenset[str]] = frozenset(
    {"schema", "message_id", "turn_token", "message_type", "published", "payload"}
)
FORBIDDEN_CONTROL_KEYS: Final[frozenset[str]] = frozenset(
    {
        "prompt",
        "prompts",
        "transcript",
        "transcript_path",
        "messages",
        "conversation",
        "reasoning",
        "rationale_internal",
        "thought",
        "thoughts",
        "chain_of_thought",
        "raw",
        "raw_input",
        "raw_output",
        "tool_input",
        "tool_output",
        "tool_response",
        "stdout",
        "stderr",
        "command",
        "environment",
        "env",
        "cookie",
        "authorization",
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "private_key",
        "credentials",
    }
)
_MAX_OBJECT_MEMBERS: Final[int] = 128
_MAX_COLLECTION_ITEMS: Final[int] = 256
_MAX_CATEGORY_TEXT: Final[int] = 120
_MAX_PUBLIC_TEXT: Final[int] = 2200


class HostControlError(ValidationError):
    """A control envelope or its closed payload is invalid."""


class ControlSizeError(HostControlError):
    """A control envelope exceeds the process-boundary limit."""


class ControlDepthError(HostControlError):
    """A control envelope exceeds the nesting limit."""


def _normal_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold().replace("-", "_").replace(" ", "_")


def _guard_tree(value: object, *, depth: int = 0, path: str = "") -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Reject forbidden keys, unsupported scalar forms, and excessive depth."""

    if depth > MAX_CONTROL_DEPTH:
        raise ControlDepthError(f"control JSON nesting exceeds {MAX_CONTROL_DEPTH}")
    if isinstance(value, Mapping):
        if len(value) > _MAX_OBJECT_MEMBERS:
            raise ControlSizeError("control object has too many members")
        for key, child in value.items():
            if not isinstance(key, str):
                raise HostControlError("control object keys must be strings")
            if _normal_key(key) in FORBIDDEN_CONTROL_KEYS:
                raise HostControlError("control contains a forbidden key")
            _guard_tree(child, depth=depth + 1, path=f"{path}.{key}".strip("."))
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) > _MAX_COLLECTION_ITEMS:
            raise ControlSizeError("control array has too many items")
        for index, child in enumerate(value):
            _guard_tree(child, depth=depth + 1, path=f"{path}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise HostControlError("control contains a non-finite number")
    if isinstance(value, str):
        if "\x00" in value or unicodedata.normalize("NFC", value) != value:
            raise HostControlError("control text is not canonical Unicode")
        if any(ord(char) < 0x20 and char not in "\n\t" for char in value):
            raise HostControlError("control text contains a forbidden control character")


def _closed_object(value: object, keys: set[str] | frozenset[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HostControlError(f"{name} must be an object")
    actual = set(value)
    if actual != set(keys):
        missing = sorted(set(keys) - actual)
        extra = sorted(actual - set(keys))
        detail = []
        if missing:
            detail.append(f"missing={','.join(missing)}")
        if extra:
            detail.append(f"unknown={','.join(extra)}")
        raise HostControlError(f"{name} keys are not closed ({'; '.join(detail)})")
    return value


def _text(value: object, name: str, maximum: int, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise HostControlError(f"{name} must be text")
    if len(value) > maximum or (nonempty and not value.strip()):
        raise HostControlError(f"{name} exceeds its bounded text contract")
    if unicodedata.normalize("NFC", value) != value or "\x00" in value:
        raise HostControlError(f"{name} is not canonical text")
    if any(ord(char) < 0x20 and char not in "\n\t" for char in value):
        raise HostControlError(f"{name} contains a forbidden control character")
    return value


def _bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise HostControlError(f"{name} must be boolean")
    return value


def _bounded_list(value: object, name: str, maximum: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise HostControlError(f"{name} must be a bounded array")
    return value


def _enum(value: object, enum_type: type[Enum], name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        raise HostControlError(f"{name} is not a closed enum value") from exc


def _id(value: object, prefix: str, name: str) -> str:
    if not isinstance(value, str):
        raise HostControlError(f"{name} must be a task-local ID")
    try:
        return validate_local_id(value, prefix)
    except Exception as exc:  # pragma: no cover - scalar validator detail
        raise HostControlError(f"{name} is not a valid {prefix} ID") from exc


def _method(value: object, name: str) -> str:
    if not isinstance(value, str):
        raise HostControlError(f"{name} must be a MethodId")
    try:
        return validate_method_id(value)
    except Exception as exc:  # pragma: no cover - scalar validator detail
        raise HostControlError(f"{name} is not a valid MethodId") from exc


def _schema(value: object, expected: str, name: str) -> None:
    if value != expected:
        raise HostControlError(f"{name}.schema must be {expected}")


def _parse_json_without_duplicates(data: bytes) -> Mapping[str, Any]:
    seen_error = False

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        nonlocal seen_error
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                seen_error = True
            result[key] = value
        return result

    try:
        decoded = json.loads(data.decode("utf-8"), object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HostControlError("control input is not strict UTF-8 JSON") from exc
    if seen_error:
        raise HostControlError("control input contains duplicate object keys")
    if not isinstance(decoded, Mapping):
        raise HostControlError("control input must be a JSON object")
    return decoded


@dataclass(frozen=True, slots=True)
class CriterionDraft:
    text: str
    required: bool
    kind: CriterionKind
    evidence_claim_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FramingDraft:
    decision_question: str
    assumptions: tuple[dict[str, Any], ...]
    decisive_evidence: tuple[str, ...]
    completion_criteria: tuple[CriterionDraft, ...]


@dataclass(frozen=True, slots=True)
class ReferenceDraft:
    existing_id: str | None = None
    new_index: int | None = None


@dataclass(frozen=True, slots=True)
class NewSourceDraft:
    kind: str
    display_name: str
    uri: str | None
    safe_locator: str | None
    published_at: str | None
    checked_at: str
    content_hash: str | None


@dataclass(frozen=True, slots=True)
class ClaimDraft:
    claim_ref: str | None
    expected_current_version: int | None
    text: str
    materiality: Any
    evidence_state: EvidenceState
    source_refs: tuple[ReferenceDraft, ...]
    new_sources: tuple[NewSourceDraft, ...]
    basis_claim_ids: tuple[str, ...]
    calculation: Mapping[str, Any] | None
    conflict: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class ConflictDraft:
    conflict: Mapping[str, Any]
    affected_claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AlternativeDraft:
    name: str
    disposition: AlternativeDisposition
    reason: str
    material_claim_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RevisionDraft:
    conclusion: str
    strength: JudgmentStrength
    change_reason: str
    ground_claim_ids: tuple[str, ...]
    uncertainty_claim_ids: tuple[str, ...]
    alternative_ids: tuple[str, ...]
    flip_conditions: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class CrossExamDraft:
    findings_summary: str
    affected_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class HoldDraft:
    missing_items: tuple[str, ...]
    reason_code: TaskTerminalReason


@dataclass(frozen=True, slots=True)
class BeginPayload:
    participation: ParticipationDecision
    rigor: RigorDecision
    routing_features: RoutingFeatures


@dataclass(frozen=True, slots=True)
class FeedbackPayload:
    feedback_class: InterventionClass
    outcome: FeedbackOutcome


ValidatedControlPayload: TypeAlias = (
    BeginPayload
    | FeedbackPayload
    | FramingDraft
    | ClaimDraft
    | ConflictDraft
    | AlternativeDraft
    | RevisionDraft
    | CrossExamDraft
    | HoldDraft
    | None
)


def _validate_assumptions(value: object) -> tuple[dict[str, Any], ...]:
    items = _bounded_list(value, "assumptions", 3)
    result: list[dict[str, Any]] = []
    for index, raw in enumerate(items):
        item = _closed_object(raw, {"text", "material"}, f"assumptions[{index}]")
        result.append(
            {
                "text": _text(item["text"], f"assumptions[{index}].text", 500),
                "material": _bool(item["material"], f"assumptions[{index}].material"),
            }
        )
    return tuple(result)


def _validate_claim_ids(
    value: object, name: str, prefix: str = "C", maximum: int = 5
) -> tuple[str, ...]:
    values = _bounded_list(value, name, maximum)
    result = tuple(_id(item, prefix, f"{name}[{index}]") for index, item in enumerate(values))
    if len(set(result)) != len(result):
        raise HostControlError(f"{name} must be unique")
    return result


def _validate_framing(payload: object) -> FramingDraft:
    raw = _closed_object(
        payload,
        {"decision_question", "assumptions", "decisive_evidence", "completion_criteria"},
        "framing",
    )
    evidence = tuple(
        _text(item, f"decisive_evidence[{index}]", 500)
        for index, item in enumerate(
            _bounded_list(raw["decisive_evidence"], "decisive_evidence", 3)
        )
    )
    criteria_raw = _bounded_list(raw["completion_criteria"], "completion_criteria", 8)
    if not criteria_raw:
        raise HostControlError("completion_criteria must not be empty")
    criteria: list[CriterionDraft] = []
    for index, value in enumerate(criteria_raw):
        item = _closed_object(
            value,
            {"text", "required", "kind", "evidence_claim_ids"},
            f"completion_criteria[{index}]",
        )
        criteria.append(
            CriterionDraft(
                text=_text(item["text"], f"completion_criteria[{index}].text", 400),
                required=_bool(item["required"], f"completion_criteria[{index}].required"),
                kind=_enum(item["kind"], CriterionKind, f"completion_criteria[{index}].kind"),
                evidence_claim_ids=_validate_claim_ids(
                    item["evidence_claim_ids"], f"completion_criteria[{index}].evidence_claim_ids"
                ),
            )
        )
    return FramingDraft(
        decision_question=_text(raw["decision_question"], "decision_question", 500),
        assumptions=_validate_assumptions(raw["assumptions"]),
        decisive_evidence=evidence,
        completion_criteria=tuple(criteria),
    )


def _validate_reference(value: object, name: str) -> ReferenceDraft:
    if not isinstance(value, Mapping):
        raise HostControlError(f"{name} must be a reference object")
    keys = set(value)
    if keys == {"existing_id"}:
        return ReferenceDraft(existing_id=_id(value["existing_id"], "E", f"{name}.existing_id"))
    if keys == {"new_index"}:
        index = value["new_index"]
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index <= 4:
            raise HostControlError(f"{name}.new_index must be in 0..4")
        return ReferenceDraft(new_index=index)
    raise HostControlError(f"{name} must contain exactly one reference variant")


def _validate_source(value: object, name: str) -> NewSourceDraft:
    item = _closed_object(
        value,
        {
            "kind",
            "display_name",
            "uri",
            "safe_locator",
            "published_at",
            "checked_at",
            "content_hash",
        },
        name,
    )
    kind = _enum(item["kind"], SourceKind, f"{name}.kind")
    return NewSourceDraft(
        kind=kind.value,
        display_name=_text(item["display_name"], f"{name}.display_name", 200),
        uri=None if item["uri"] is None else _text(item["uri"], f"{name}.uri", 2048),
        safe_locator=None
        if item["safe_locator"] is None
        else _text(item["safe_locator"], f"{name}.safe_locator", 200),
        published_at=None
        if item["published_at"] is None
        else _text(item["published_at"], f"{name}.published_at", 32),
        checked_at=_text(item["checked_at"], f"{name}.checked_at", 32),
        content_hash=None
        if item["content_hash"] is None
        else _text(item["content_hash"], f"{name}.content_hash", 80),
    )


def _validate_calculation(value: object) -> Mapping[str, Any] | None:
    if value is None:
        return None
    item = _closed_object(
        value, {"schema", "expression", "operands", "result", "unit", "rounding"}, "calculation"
    )
    _schema(item["schema"], "opensocrates.calculation/1.0.0", "calculation")
    _text(item["expression"], "calculation.expression", 1000)
    _text(item["result"], "calculation.result", 128)
    _text(item["unit"], "calculation.unit", 64)
    _enum(item["rounding"], RoundingMode, "calculation.rounding")
    operands = _bounded_list(item["operands"], "calculation.operands", 16)
    if not operands:
        raise HostControlError("calculation requires at least one operand")
    names: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(operands):
        operand = _closed_object(
            raw, {"name", "value", "unit", "source_ref"}, f"calculation.operands[{index}]"
        )
        name = _text(operand["name"], f"calculation.operands[{index}].name", 128)
        if name in names:
            raise HostControlError("calculation operand names must be unique")
        names.add(name)
        _text(operand["value"], f"calculation.operands[{index}].value", 128)
        _text(operand["unit"], f"calculation.operands[{index}].unit", 64)
        normalized.append(
            {
                **dict(operand),
                "source_ref": None
                if operand["source_ref"] is None
                else _validate_reference(
                    operand["source_ref"], f"calculation.operands[{index}].source_ref"
                ),
            }
        )
    return {**dict(item), "operands": tuple(normalized)}


def _validate_claim(payload: object) -> ClaimDraft:
    raw = _closed_object(
        payload,
        {
            "claim_ref",
            "expected_current_version",
            "text",
            "materiality",
            "evidence_state",
            "source_refs",
            "new_sources",
            "basis_claim_ids",
            "calculation",
            "conflict",
        },
        "claim",
    )
    claim_ref = None if raw["claim_ref"] is None else _id(raw["claim_ref"], "C", "claim.claim_ref")
    version = raw["expected_current_version"]
    if version is not None and (
        not isinstance(version, int) or isinstance(version, bool) or version < 1
    ):
        raise HostControlError("claim.expected_current_version must be a positive integer or null")
    if (claim_ref is None) != (version is None):
        raise HostControlError("claim_ref and expected_current_version are paired")
    refs = tuple(
        _validate_reference(value, f"claim.source_refs[{index}]")
        for index, value in enumerate(_bounded_list(raw["source_refs"], "claim.source_refs", 5))
    )
    sources = tuple(
        _validate_source(value, f"claim.new_sources[{index}]")
        for index, value in enumerate(_bounded_list(raw["new_sources"], "claim.new_sources", 5))
    )
    for ref in refs:
        if ref.new_index is not None and ref.new_index >= len(sources):
            raise HostControlError("claim source reference points outside new_sources")
    materiality = _enum(raw["materiality"], ClaimMateriality, "claim.materiality")
    evidence_state = _enum(raw["evidence_state"], EvidenceState, "claim.evidence_state")
    basis = _validate_claim_ids(raw["basis_claim_ids"], "claim.basis_claim_ids")
    calculation = _validate_calculation(raw["calculation"])
    conflict = raw["conflict"]
    if conflict is not None:
        if not isinstance(conflict, Mapping):
            raise HostControlError("claim.conflict must be an object or null")
        check_forbidden_keys(conflict)
    return ClaimDraft(
        claim_ref=claim_ref,
        expected_current_version=version,
        text=_text(raw["text"], "claim.text", 600),
        materiality=materiality,
        evidence_state=evidence_state,
        source_refs=refs,
        new_sources=sources,
        basis_claim_ids=basis,
        calculation=calculation,
        conflict=conflict,
    )


def _validate_conflict(payload: object) -> ConflictDraft:
    raw = _closed_object(payload, {"conflict", "affected_claim_ids"}, "conflict payload")
    conflict = _closed_object(
        raw["conflict"],
        {
            "schema",
            "summary",
            "subject",
            "source_ids",
            "affected_claim_ids",
            "material",
            "resolution",
            "resolution_reason",
        },
        "conflict",
    )
    _schema(conflict["schema"], "opensocrates.conflict/1.0.0", "conflict")
    _text(conflict["summary"], "conflict.summary", 600)
    _text(conflict["subject"], "conflict.subject", 300)
    _validate_claim_ids(conflict["affected_claim_ids"], "conflict.affected_claim_ids")
    sources = _bounded_list(conflict["source_ids"], "conflict.source_ids", 5)
    for index, value in enumerate(sources):
        _id(value, "E", f"conflict.source_ids[{index}]")
    _bool(conflict["material"], "conflict.material")
    _enum(conflict["resolution"], ConflictResolution, "conflict.resolution")
    if conflict["resolution_reason"] is not None:
        _text(conflict["resolution_reason"], "conflict.resolution_reason", 600)
    affected = _validate_claim_ids(raw["affected_claim_ids"], "affected_claim_ids")
    return ConflictDraft(conflict=dict(conflict), affected_claim_ids=affected)


def _validate_alternative(payload: object) -> AlternativeDraft:
    raw = _closed_object(
        payload, {"name", "disposition", "reason", "material_claim_ids"}, "alternative"
    )
    return AlternativeDraft(
        name=_text(raw["name"], "alternative.name", 160),
        disposition=_enum(raw["disposition"], AlternativeDisposition, "alternative.disposition"),
        reason=_text(raw["reason"], "alternative.reason", 400),
        material_claim_ids=_validate_claim_ids(
            raw["material_claim_ids"], "alternative.material_claim_ids"
        ),
    )


def _validate_revision(payload: object) -> RevisionDraft:
    raw = _closed_object(
        payload,
        {
            "conclusion",
            "strength",
            "change_reason",
            "ground_claim_ids",
            "uncertainty_claim_ids",
            "alternative_ids",
            "flip_conditions",
        },
        "revision",
    )
    flips = _bounded_list(raw["flip_conditions"], "revision.flip_conditions", 2)
    for index, item in enumerate(flips):
        check = _closed_object(
            item,
            {"schema", "condition", "affected_conclusion", "direction", "check"},
            f"revision.flip_conditions[{index}]",
        )
        _schema(
            check["schema"],
            "opensocrates.flip-condition/1.0.0",
            f"revision.flip_conditions[{index}]",
        )
        _text(check["condition"], f"revision.flip_conditions[{index}].condition", 300)
        if check["affected_conclusion"] is not None:
            _text(
                check["affected_conclusion"],
                f"revision.flip_conditions[{index}].affected_conclusion",
                240,
            )
        _text(check["check"], f"revision.flip_conditions[{index}].check", 240)
    return RevisionDraft(
        conclusion=_text(raw["conclusion"], "revision.conclusion", 500),
        strength=_enum(raw["strength"], JudgmentStrength, "revision.strength"),
        change_reason=_text(raw["change_reason"], "revision.change_reason", 500),
        ground_claim_ids=_validate_claim_ids(raw["ground_claim_ids"], "revision.ground_claim_ids"),
        uncertainty_claim_ids=_validate_claim_ids(
            raw["uncertainty_claim_ids"], "revision.uncertainty_claim_ids", maximum=2
        ),
        alternative_ids=_validate_claim_ids(
            raw["alternative_ids"], "revision.alternative_ids", prefix="A", maximum=3
        ),
        flip_conditions=tuple(dict(item) for item in flips),
    )


def _validate_cross_exam(payload: object) -> CrossExamDraft:
    raw = _closed_object(payload, {"findings_summary", "affected_ids"}, "cross_exam")
    affected = _bounded_list(raw["affected_ids"], "cross_exam.affected_ids", 12)
    for index, value in enumerate(affected):
        if not isinstance(value, str) or not value or len(value) > 32:
            raise HostControlError(f"cross_exam.affected_ids[{index}] is invalid")
    return CrossExamDraft(
        _text(raw["findings_summary"], "cross_exam.findings_summary", 1000), tuple(affected)
    )


def _validate_hold(payload: object) -> HoldDraft:
    raw = _closed_object(payload, {"missing_items", "reason_code"}, "hold")
    items = _bounded_list(raw["missing_items"], "hold.missing_items", 5)
    if not 1 <= len(items) <= 5:
        raise HostControlError("hold.missing_items must contain one through five items")
    reason_code = _enum(raw["reason_code"], TaskTerminalReason, "hold.reason_code")
    if reason_code in {
        TaskTerminalReason.MECHANICAL,
        TaskTerminalReason.CRITERIA_SATISFIED,
        TaskTerminalReason.USER_CANCELLED,
    }:
        raise HostControlError("hold.reason_code is not an insufficiency reason")
    return HoldDraft(
        missing_items=tuple(
            _text(item, f"hold.missing_items[{index}]", 500) for index, item in enumerate(items)
        ),
        reason_code=reason_code,
    )


def validate_control_payload(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    message_type: HostControlMessageType,
    payload: Mapping[str, Any],
    *,
    published: bool,
) -> ValidatedControlPayload:
    """Validate one exact message union member and return its typed draft."""

    if not isinstance(message_type, HostControlMessageType):
        raise HostControlError("message_type is not closed")
    if not isinstance(payload, Mapping):
        raise HostControlError("payload must be an object")
    check_forbidden_keys(payload)
    if message_type is HostControlMessageType.BEGIN_JUDGMENT:
        raw = _closed_object(
            payload, {"participation", "rigor", "routing_features"}, "begin_judgment"
        )
        try:
            participation = model_from_dict(ParticipationDecision, raw["participation"])
            rigor = model_from_dict(RigorDecision, raw["rigor"])
            features = model_from_dict(RoutingFeatures, raw["routing_features"])
            validate_model(participation)
            validate_model(rigor)
            validate_model(features)
        except Exception as exc:
            raise HostControlError("begin_judgment contains an invalid typed decision") from exc
        if not isinstance(participation.participation, (Participation,)):
            raise HostControlError("begin_judgment participation is not closed")
        return BeginPayload(participation=participation, rigor=rigor, routing_features=features)
    if message_type is HostControlMessageType.INTERVENTION_FEEDBACK:
        raw = _closed_object(payload, {"class", "outcome"}, "intervention_feedback")
        return FeedbackPayload(
            _enum(raw["class"], InterventionClass, "intervention_feedback.class"),
            _enum(raw["outcome"], FeedbackOutcome, "intervention_feedback.outcome"),
        )
    if message_type is HostControlMessageType.PUBLISH_FRAMING:
        if not published:
            raise HostControlError("publish_framing requires published=true")
        return _validate_framing(payload)
    if message_type is HostControlMessageType.PUBLISH_CLAIM:
        if not published:
            raise HostControlError("publish_claim requires published=true")
        return _validate_claim(payload)
    if message_type is HostControlMessageType.PUBLISH_CONFLICT:
        if not published:
            raise HostControlError("publish_conflict requires published=true")
        return _validate_conflict(payload)
    if message_type is HostControlMessageType.PUBLISH_ALTERNATIVE:
        if not published:
            raise HostControlError("publish_alternative requires published=true")
        return _validate_alternative(payload)
    if message_type is HostControlMessageType.REVISE_JUDGMENT:
        if not published:
            raise HostControlError("revise_judgment requires published=true")
        return _validate_revision(payload)
    if message_type is HostControlMessageType.COMPLETE_CROSS_EXAM:
        if not published:
            raise HostControlError("complete_cross_exam requires published=true")
        return _validate_cross_exam(payload)
    if message_type is HostControlMessageType.HOLD_JUDGMENT:
        if not published:
            raise HostControlError("hold_judgment requires published=true")
        return _validate_hold(payload)
    if message_type is HostControlMessageType.CANCEL_JUDGMENT:
        raw = _closed_object(payload, {"reason"}, "cancel_judgment")
        if raw["reason"] != "user_cancelled":
            raise HostControlError("cancel_judgment reason is closed")
        return None
    raise HostControlError("unknown message type")


def validate_host_control(value: HostControl | Mapping[str, Any] | bytes | str) -> HostControl:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Parse and validate a bounded control envelope plus its exact payload."""

    if isinstance(value, (bytes, bytearray)):
        if len(value) > MAX_HOST_CONTROL_BYTES:
            raise ControlSizeError("host control exceeds 32 KiB")
        raw = _parse_json_without_duplicates(bytes(value))
    elif isinstance(value, str):
        encoded = value.encode("utf-8")
        if len(encoded) > MAX_HOST_CONTROL_BYTES:
            raise ControlSizeError("host control exceeds 32 KiB")
        raw = _parse_json_without_duplicates(encoded)
    elif isinstance(value, HostControl):
        raw = value.to_dict()
    elif isinstance(value, Mapping):
        try:
            encoded = canonical_json(value).encode("utf-8")
        except Exception as exc:
            raise HostControlError("host control is not canonical JSON") from exc
        if len(encoded) > MAX_HOST_CONTROL_BYTES:
            raise ControlSizeError("host control exceeds 32 KiB")
        raw = value
    else:
        raise HostControlError("host control must be an object, JSON string, or UTF-8 bytes")
    _guard_tree(raw)
    if set(raw) != CONTROL_KEYS:
        raise HostControlError("host control envelope keys are not closed")
    if raw.get("schema") != CONTROL_SCHEMA:
        raise HostControlError("unknown schema")
    try:
        HostControlMessageType(raw.get("message_type"))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    except (TypeError, ValueError) as exc:
        raise HostControlError("unknown message type") from exc
    try:
        validate_turn_token(raw.get("turn_token"))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    except Exception as exc:
        raise HostControlError("invalid token") from exc
    try:
        control = HostControl.from_dict(raw)
    except Exception as exc:
        raise HostControlError("host control envelope is invalid") from exc
    validate_control_payload(control.message_type, control.payload, published=control.published)
    return control  # type: ignore[no-any-return]  # Closed runtime boundary validates this value.


def canonical_payload(control: HostControl) -> Mapping[str, Any]:
    """Return the exact payload projection used for idempotency tagging."""

    control = validate_host_control(control)
    return dict(control.payload)


def legal_control_transition(message_type: HostControlMessageType, state: TaskState) -> bool:
    """Return whether a control is legal from the current ephemeral state."""

    if not isinstance(message_type, HostControlMessageType) or not isinstance(state, TaskState):
        return False
    if message_type is HostControlMessageType.INTERVENTION_FEEDBACK:
        return True
    allowed: dict[HostControlMessageType, frozenset[TaskState]] = {
        HostControlMessageType.BEGIN_JUDGMENT: frozenset({TaskState.NEW}),
        HostControlMessageType.PUBLISH_FRAMING: frozenset({TaskState.FRAMING}),
        HostControlMessageType.PUBLISH_CLAIM: frozenset(
            {TaskState.FRAMING, TaskState.WORKING, TaskState.REJUDGING}
        ),
        HostControlMessageType.PUBLISH_CONFLICT: frozenset(
            {TaskState.WORKING, TaskState.REJUDGING}
        ),
        HostControlMessageType.PUBLISH_ALTERNATIVE: frozenset(
            {TaskState.FRAMING, TaskState.WORKING, TaskState.REJUDGING}
        ),
        HostControlMessageType.REVISE_JUDGMENT: frozenset({TaskState.WORKING, TaskState.REJUDGING}),
        HostControlMessageType.COMPLETE_CROSS_EXAM: frozenset({TaskState.CROSS_EXAMINING}),
        HostControlMessageType.HOLD_JUDGMENT: frozenset(
            {
                TaskState.FRAMING,
                TaskState.WORKING,
                TaskState.REJUDGING,
                TaskState.CROSS_EXAMINING,
                TaskState.VERIFYING,
                TaskState.DEGRADED,
            }
        ),
        HostControlMessageType.CANCEL_JUDGMENT: frozenset(
            {
                TaskState.FRAMING,
                TaskState.WORKING,
                TaskState.REJUDGING,
                TaskState.CROSS_EXAMINING,
                TaskState.VERIFYING,
                TaskState.DEGRADED,
            }
        ),
    }
    return state in allowed.get(message_type, frozenset())


def next_control_state(message_type: HostControlMessageType, state: TaskState) -> TaskState:
    """Return the immutable lifecycle transition or raise a stable error."""

    if not legal_control_transition(message_type, state):
        raise HostControlError(f"invalid {message_type.value} transition from {state.value}")
    if message_type is HostControlMessageType.PUBLISH_FRAMING:
        return TaskState.WORKING
    if message_type is HostControlMessageType.PUBLISH_CONFLICT:
        return TaskState.REJUDGING
    if message_type is HostControlMessageType.REVISE_JUDGMENT:
        return TaskState.CROSS_EXAMINING
    if message_type is HostControlMessageType.COMPLETE_CROSS_EXAM:
        return TaskState.VERIFYING
    if message_type is HostControlMessageType.HOLD_JUDGMENT:
        return TaskState.INSUFFICIENT
    if message_type is HostControlMessageType.CANCEL_JUDGMENT:
        return TaskState.CANCELLED
    return state


def result_is_durable(result: HostControlResult) -> bool:
    """Check the result status/mutation invariant used by adapters."""

    if not isinstance(result, HostControlResult):
        raise HostControlError("expected HostControlResult")
    if result.status is HostControlStatus.ACCEPTED and not result.durable_mutation:
        return False
    if result.status is HostControlStatus.ACCEPTED_NOT_RECORDED and result.durable_mutation:
        return False
    if result.status is HostControlStatus.REJECTED and (
        result.durable_mutation or result.assigned_ids.has_any()
    ):
        return False
    return True


__all__ = [
    "AlternativeDraft",
    "BeginPayload",
    "ClaimDraft",
    "ConflictDraft",
    "ControlDepthError",
    "ControlSizeError",
    "CrossExamDraft",
    "CriterionDraft",
    "FeedbackPayload",
    "FramingDraft",
    "HoldDraft",
    "HostControlError",
    "NewSourceDraft",
    "ReferenceDraft",
    "RevisionDraft",
    "ValidatedControlPayload",
    "canonical_payload",
    "legal_control_transition",
    "next_control_state",
    "result_is_durable",
    "validate_control_payload",
    "validate_host_control",
]
