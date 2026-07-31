"""Conclusion-blinded Strict second-pass contracts.

Strict is a second pass by the same host model, not a separate model, account,
agent, or principal.  ``StrictPacket`` has no current-conclusion field and
projects alternatives without their dispositions.  The comparison contract
keeps a select/hold disagreement visible until a public revise-or-hold
reconciliation is supplied.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, fields, is_dataclass
from enum import StrEnum
from typing import ClassVar, Iterable

from ..constants import MAX_CARD_GROUNDS
from ..errors import ValidationError
from .alternatives import observable_flip_conditions, validate_alternative_disposition
from .enums import EvidenceState, JudgmentStrength
from .models import Alternative, ClaimVersion, Criterion, FlipCondition


class StrictOutcome(StrEnum):
    """Closed second-pass outcome."""

    SELECT = "select"
    REVISE = "revise"
    HOLD = "hold"


class StrictNextAction(StrEnum):
    """Closed application action after comparison."""

    PUBLISH = "publish"
    RECONCILE = "reconcile"
    REVISE = "revise"
    HOLD = "hold"


class StrictFindingKind(StrEnum):
    """Public cross-exam finding labels allowed in a Strict result."""

    STRONGEST_OBJECTION = "strongest_objection"
    WEAKEST_LINK = "weakest_link"
    OMITTED_ALTERNATIVE = "omitted_alternative"
    STALE_RISK = "stale_risk"
    COMPLETION_CHECK = "completion_check"


class StrictReconciliationAction(StrEnum):
    """The only public actions that reconcile a disagreement."""

    REVISE = "revise"
    HOLD = "hold"


def _text(value: object, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValidationError(f"{name} must be bounded non-empty text")
    if "\x00" in value or any(ord(char) < 0x20 and char not in "\n\t" for char in value):
        raise ValidationError(f"{name} contains prohibited control characters")
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError(f"{name} must be NFC-normalized")
    return value


def _json_value(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _json_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    return value


def _canonical_json(value: object) -> str:
    return (
        json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictGround:
    """Neutral material claim projection; it has no conclusion relation."""

    claim_id: str
    text: str
    evidence_state: EvidenceState
    material: bool = True

    def __post_init__(self) -> None:
        _text(self.claim_id, "strict ground claim_id", 32)
        _text(self.text, "strict ground text", 600)
        if not isinstance(self.evidence_state, EvidenceState):
            raise ValidationError("strict ground evidence_state is not closed")
        if not isinstance(self.material, bool) or not self.material:
            raise ValidationError("strict packet grounds must be material")


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictAlternative:
    """Alternative projection deliberately omitting ``disposition``."""

    alternative_id: str
    name: str
    reason: str
    material_claim_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.alternative_id, "strict alternative id", 32)
        _text(self.name, "strict alternative name", 160)
        _text(self.reason, "strict alternative reason", 400)
        if not isinstance(self.material_claim_ids, tuple) or len(self.material_claim_ids) > 5:
            raise ValidationError("strict alternative claim references are bounded")
        for claim_id in self.material_claim_ids:
            _text(claim_id, "strict alternative claim id", 32)
        if len(set(self.material_claim_ids)) != len(self.material_claim_ids):
            raise ValidationError("strict alternative claim references must be unique")


_CONCLUSION_IDENTIFYING_PHRASES = (
    "current conclusion",
    "current recommendation",
    "the recommendation is",
    "our recommendation is",
    "we recommend",
    "recommended option",
    "selected disposition",
    "selected alternative",
    "final answer is",
    "final decision is",
    "therefore choose",
    "we chose",
    "we choose",
    "selected",
    "rejected",
    "deferred",
    "not comparable",
    "not_comparable",
)


def _contains_conclusion_language(value: str) -> bool:
    lowered = " ".join(value.casefold().split())
    return any(phrase in lowered for phrase in _CONCLUSION_IDENTIFYING_PHRASES)


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictPacket:
    """Public input for a same-host conclusion-blinded second pass.

    There is intentionally no ``conclusion``, ``recommendation``,
    ``selected_disposition``, model name, agent name, or hidden-reasoning
    field.  ``alternatives`` are neutral projections, so a selected/rejected
    disposition cannot leak through serialization.
    """

    schema: ClassVar[str] = "opensocrates.strict-packet/1.0.0"
    decision_question: str
    public_framing: str
    material_grounds: tuple[StrictGround, ...] = ()
    alternatives: tuple[StrictAlternative, ...] = ()
    completion_criteria: tuple[Criterion, ...] = ()
    same_host_second_pass: bool = True
    packet_tag: str | None = None

    def __post_init__(self) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        _text(self.decision_question, "strict decision question", 500)
        _text(self.public_framing, "strict public framing", 1200)
        if _contains_conclusion_language(self.public_framing):
            raise ValidationError("strict public framing contains conclusion-identifying phrasing")
        if not isinstance(self.same_host_second_pass, bool) or not self.same_host_second_pass:
            raise ValidationError("strict packet must identify a same-host second pass")
        if self.packet_tag is not None:
            if not isinstance(self.packet_tag, str) or not re.fullmatch(
                r"sha256:[0-9a-f]{64}", self.packet_tag
            ):
                raise ValidationError("strict packet tag must be a sha256 tag")
        if (
            not isinstance(self.material_grounds, tuple)
            or len(self.material_grounds) > MAX_CARD_GROUNDS
        ):
            raise ValidationError("strict packet has too many material grounds")
        for ground in self.material_grounds:
            if not isinstance(ground, StrictGround):
                raise ValidationError("strict packet grounds must be StrictGround values")
        if not isinstance(self.alternatives, tuple) or len(self.alternatives) > 3:
            raise ValidationError("strict packet has too many alternatives")
        names: set[str] = set()
        for alternative in self.alternatives:
            if not isinstance(alternative, StrictAlternative):
                raise ValidationError("strict packet alternatives must be neutral projections")
            key = alternative.name.casefold()
            if key in names:
                raise ValidationError("strict packet alternatives must be distinct")
            names.add(key)
            if _contains_conclusion_language(alternative.reason):
                raise ValidationError(
                    "strict alternative reason contains conclusion-identifying phrasing"
                )
        if not isinstance(self.completion_criteria, tuple) or len(self.completion_criteria) > 8:
            raise ValidationError("strict packet completion criteria are bounded")
        for criterion in self.completion_criteria:
            if not isinstance(criterion, Criterion):
                raise ValidationError("strict packet criteria must be Criterion values")

    def to_dict(self) -> dict[str, object]:
        """Return a schema-shaped packet without prohibited conclusion fields."""

        result: dict[str, object] = {
            "schema": self.schema,
            "decision_question": self.decision_question,
            "public_framing": self.public_framing,
            "material_grounds": _json_value(self.material_grounds),
            "alternatives": _json_value(self.alternatives),
            "completion_criteria": _json_value(self.completion_criteria),
            "same_host_second_pass": self.same_host_second_pass,
        }
        if self.packet_tag is not None:
            result["packet_tag"] = self.packet_tag
        return result

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())


def _ground(value: ClaimVersion | StrictGround) -> StrictGround:
    if isinstance(value, StrictGround):
        return value
    if isinstance(value, ClaimVersion):
        if value.materiality.value != "material":
            raise ValidationError("strict packet accepts material claim grounds only")
        return StrictGround(
            claim_id=value.claim_id,
            text=value.text,
            evidence_state=value.evidence_state,
            material=True,
        )
    raise ValidationError("strict packet ground must be ClaimVersion or StrictGround")


def _alternative(value: Alternative | StrictAlternative) -> StrictAlternative:
    if isinstance(value, StrictAlternative):
        return value
    if isinstance(value, Alternative):
        validate_alternative_disposition(value)
        # Deliberately do not copy ``value.disposition``.  The packet must not
        # tell the second pass which option was previously selected.
        return StrictAlternative(
            alternative_id=value.alternative_id,
            name=value.name,
            reason=value.reason,
            material_claim_ids=value.material_claim_ids,
        )
    raise ValidationError("strict packet alternative must be Alternative or StrictAlternative")


def _packet_tag(
    decision_question: str,
    public_framing: str,
    grounds: tuple[StrictGround, ...],
    alternatives: tuple[StrictAlternative, ...],
    criteria: tuple[Criterion, ...],
) -> str:
    value = "\x1f".join(
        (
            decision_question,
            public_framing,
            _canonical_json(grounds),
            _canonical_json(alternatives),
            _canonical_json(criteria),
        )
    )
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()}"


def build_strict_packet(
    decision_question: str,
    public_framing: str,
    material_grounds: Iterable[ClaimVersion | StrictGround],
    alternatives: Iterable[Alternative | StrictAlternative],
    completion_criteria: Iterable[Criterion],
    *,
    current_conclusion: str | None = None,
    selected_alternative_ids: Iterable[str] = (),
) -> StrictPacket:
    """Build a packet while using current conclusion only as an exclusion check.

    ``current_conclusion`` and ``selected_alternative_ids`` are never copied
    into the returned object.  They exist solely to make leakage checks
    explicit at the application boundary.
    """

    decision_question = _text(decision_question, "strict decision question", 500)
    public_framing = _text(public_framing, "strict public framing", 1200)
    raw_grounds = tuple(material_grounds)
    raw_alternatives = tuple(alternatives)
    raw_criteria = tuple(completion_criteria)
    if _contains_conclusion_language(public_framing):
        raise ValidationError("strict framing contains conclusion-identifying phrasing")
    if current_conclusion is not None:
        current_conclusion = _text(current_conclusion, "current conclusion exclusion value", 500)
        normalized_conclusion = " ".join(current_conclusion.casefold().split())
        if len(normalized_conclusion) >= 8:
            candidate_text = " ".join(
                (
                    decision_question,
                    public_framing,
                    *(getattr(item, "text", "") for item in raw_grounds),
                    *(getattr(item, "name", "") for item in raw_alternatives),
                    *(getattr(item, "reason", "") for item in raw_alternatives),
                    *(getattr(item, "text", "") for item in raw_criteria),
                )
            ).casefold()
            if normalized_conclusion in " ".join(candidate_text.split()):
                raise ValidationError("strict packet would reveal current conclusion")
    # Consume the selected IDs as a validation-only iterable; no selection
    # disposition or identifier is retained in the packet projection.
    for alternative_id in selected_alternative_ids:
        _text(alternative_id, "selected alternative exclusion id", 32)
    grounds = tuple(_ground(value) for value in raw_grounds)
    neutral_alternatives = tuple(_alternative(value) for value in raw_alternatives)
    criteria = raw_criteria
    packet = StrictPacket(
        decision_question=decision_question,
        public_framing=public_framing,
        material_grounds=grounds,
        alternatives=neutral_alternatives,
        completion_criteria=criteria,
        same_host_second_pass=True,
    )
    return StrictPacket(
        decision_question=packet.decision_question,
        public_framing=packet.public_framing,
        material_grounds=packet.material_grounds,
        alternatives=packet.alternatives,
        completion_criteria=packet.completion_criteria,
        same_host_second_pass=True,
        packet_tag=_packet_tag(
            packet.decision_question,
            packet.public_framing,
            packet.material_grounds,
            packet.alternatives,
            packet.completion_criteria,
        ),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictFinding:
    """One bounded public finding from the second pass."""

    kind: StrictFindingKind
    summary: str
    affected_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, StrictFindingKind):
            raise ValidationError("strict finding kind is not closed")
        _text(self.summary, "strict finding summary", 400)
        if not isinstance(self.affected_ids, tuple) or len(self.affected_ids) > 5:
            raise ValidationError("strict finding IDs are bounded")
        for value in self.affected_ids:
            _text(value, "strict finding affected ID", 32)


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictPassResult:
    """Public result of the same-host second pass; no private reasoning field."""

    outcome: StrictOutcome
    public_summary: str
    strength: JudgmentStrength = JudgmentStrength.SUPPORTED
    selected_alternative_id: str | None = None
    findings: tuple[StrictFinding, ...] = ()
    flip_conditions: tuple[FlipCondition, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, StrictOutcome):
            raise ValidationError("strict result outcome is not closed")
        _text(self.public_summary, "strict public summary", 1200)
        if not isinstance(self.strength, JudgmentStrength):
            raise ValidationError("strict result strength is not closed")
        if self.outcome is StrictOutcome.HOLD and self.strength is not JudgmentStrength.HELD:
            raise ValidationError("a Strict hold must use held strength")
        if self.outcome is not StrictOutcome.HOLD and self.strength is JudgmentStrength.HELD:
            raise ValidationError("non-hold Strict result cannot use held strength")
        if self.outcome is StrictOutcome.SELECT and self.selected_alternative_id is None:
            raise ValidationError("a Strict select result requires an alternative ID")
        if self.selected_alternative_id is not None:
            _text(self.selected_alternative_id, "strict selected alternative ID", 32)
        if not isinstance(self.findings, tuple) or len(self.findings) > 5:
            raise ValidationError("strict findings are bounded")
        for finding in self.findings:
            if not isinstance(finding, StrictFinding):
                raise ValidationError("strict findings must be StrictFinding values")
        object.__setattr__(
            self,
            "flip_conditions",
            observable_flip_conditions(self.flip_conditions),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "opensocrates.strict-result/1.0.0",
            "outcome": self.outcome.value,
            "public_summary": self.public_summary,
            "strength": self.strength.value,
            "selected_alternative_id": self.selected_alternative_id,
            "findings": _json_value(self.findings),
            "flip_conditions": _json_value(self.flip_conditions),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictReconciliation:
    """Public action required to resolve a pass disagreement."""

    action: StrictReconciliationAction
    public_summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.action, StrictReconciliationAction):
            raise ValidationError("Strict reconciliation action is not closed")
        _text(self.public_summary, "Strict reconciliation summary", 1200)


@dataclass(frozen=True, slots=True, kw_only=True)
class StrictComparison:
    """Comparison projection and visible completion gate."""

    first_outcome: StrictOutcome
    second_outcome: StrictOutcome
    agreement: bool
    reconciliation_required: bool
    reconciled: bool
    next_action: StrictNextAction
    public_summary: str
    reconciliation_summary: str | None = None

    @property
    def can_complete(self) -> bool:
        return not self.reconciliation_required or self.reconciled

    def __post_init__(self) -> None:
        if not isinstance(self.first_outcome, StrictOutcome) or not isinstance(
            self.second_outcome, StrictOutcome
        ):
            raise ValidationError("Strict comparison outcomes are not closed")
        if not isinstance(self.agreement, bool) or not isinstance(
            self.reconciliation_required, bool
        ):
            raise ValidationError("Strict comparison flags must be boolean")
        if not isinstance(self.reconciled, bool):
            raise ValidationError("Strict comparison reconciled must be boolean")
        if not isinstance(self.next_action, StrictNextAction):
            raise ValidationError("Strict comparison next action is not closed")
        _text(self.public_summary, "Strict comparison summary", 1200)
        if self.reconciliation_summary is not None:
            _text(self.reconciliation_summary, "Strict reconciliation summary", 1200)
        if (
            self.reconciliation_required
            and not self.reconciled
            and self.next_action is not StrictNextAction.RECONCILE
        ):
            raise ValidationError("unreconciled Strict disagreement must request reconciliation")


def _pass_agrees(
    first: StrictPassResult,
    second: StrictPassResult,
    first_selected_alternative_id: str | None,
) -> bool:
    if first.outcome is not second.outcome:
        return False
    if first.outcome in {StrictOutcome.SELECT, StrictOutcome.REVISE}:
        expected = (
            first.selected_alternative_id
            if first_selected_alternative_id is None
            else first_selected_alternative_id
        )
        return first.selected_alternative_id == second.selected_alternative_id == expected
    return True


def compare_strict_passes(
    first: StrictPassResult,
    second: StrictPassResult,
    *,
    first_selected_alternative_id: str | None = None,
    reconciliation: StrictReconciliation | None = None,
) -> StrictComparison:
    """Surface disagreement and require public revise/hold reconciliation."""

    if not isinstance(first, StrictPassResult) or not isinstance(second, StrictPassResult):
        raise ValidationError("Strict comparison requires two StrictPassResult values")
    if reconciliation is not None and not isinstance(reconciliation, StrictReconciliation):
        raise ValidationError("Strict reconciliation must be StrictReconciliation")
    agreement = _pass_agrees(first, second, first_selected_alternative_id)
    if agreement:
        next_action = (
            StrictNextAction.HOLD
            if second.outcome is StrictOutcome.HOLD
            else StrictNextAction.PUBLISH
        )
        return StrictComparison(
            first_outcome=first.outcome,
            second_outcome=second.outcome,
            agreement=True,
            reconciliation_required=False,
            reconciled=False,
            next_action=next_action,
            public_summary="the two same-host passes agree",
        )
    if reconciliation is None:
        return StrictComparison(
            first_outcome=first.outcome,
            second_outcome=second.outcome,
            agreement=False,
            reconciliation_required=True,
            reconciled=False,
            next_action=StrictNextAction.RECONCILE,
            public_summary="the two same-host passes disagree and require public reconciliation",
        )
    next_action = (
        StrictNextAction.REVISE
        if reconciliation.action is StrictReconciliationAction.REVISE
        else StrictNextAction.HOLD
    )
    return StrictComparison(
        first_outcome=first.outcome,
        second_outcome=second.outcome,
        agreement=False,
        reconciliation_required=True,
        reconciled=True,
        next_action=next_action,
        public_summary="the disagreement has a public reconciliation action",
        reconciliation_summary=reconciliation.public_summary,
    )


# Compatibility aliases used by application callers.
StrictBlindedPacket = StrictPacket
StrictResult = StrictPassResult
StrictPassComparison = StrictComparison
build_blinded_packet = build_strict_packet
compare_passes = compare_strict_passes


__all__ = [
    "StrictAlternative",
    "StrictBlindedPacket",
    "StrictComparison",
    "StrictFinding",
    "StrictFindingKind",
    "StrictNextAction",
    "StrictPacket",
    "StrictPassComparison",
    "StrictPassResult",
    "StrictReconciliation",
    "StrictReconciliationAction",
    "StrictResult",
    "StrictGround",
    "StrictOutcome",
    "build_blinded_packet",
    "build_strict_packet",
    "compare_passes",
    "compare_strict_passes",
]
