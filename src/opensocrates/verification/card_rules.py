"""Pure Conclusion Card structure, evidence, source, and vocabulary rules.

These rules inspect only a typed public card and (optionally) its Markdown
projection.  They do not fetch sources, execute calculations, inspect
transcripts, call a model, or read the filesystem.  A rule returns a bounded
tuple of typed ``Violation`` objects; :func:`enforce_card_rules` maps the same
result to the repository's ``ValidationError`` contract.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from typing import Any

from ..constants import (
    MAX_CARD_FLIP_CONDITIONS,
    MAX_CARD_GROUNDS,
    MAX_CARD_LINES,
    MAX_CARD_SCALARS,
    MAX_CARD_UNCERTAINTIES,
)
from ..domain.enums import EvidenceState, FlipDirection, JudgmentStrength, ViolationSeverity
from ..domain.models import (
    CardSourceReference,
    ConclusionCard,
    ConclusionGround,
    FlipCondition,
    Violation,
)
from ..errors import ValidationError
from ..rendering.markdown import (
    nonblank_line_count,
    validate_card_markdown,
    validate_public_url,
    validate_scalar_text,
    validate_text_urls,
)
from .secret_filter import scan_secrets

MAX_CONCLUSION_SCALARS = 240
MAX_GROUND_SCALARS = 240
MAX_UNCERTAINTY_SCALARS = 220
MAX_FLIP_SCALARS = 220
MAX_ALTERNATIVES_SCALARS = 300
MAX_RULE_VIOLATIONS = 32

_GENERIC_FLIPS = frozenset(
    {
        "if circumstances change",
        "if new information emerges",
        "if new information appears",
        "if the analysis is wrong",
        "if things change",
        "if more data arrives",
    }
)
_CALCULATION_RE = re.compile(
    r"^\s*(?=[^=\s])[A-Za-z0-9_().%+*/\-\s]+\s*=\s*[+-]?(?:\d+(?:\.\d+)?)\s+\S+\s*$"
)
_SENTENCE_END_RE = re.compile(r"[.!?。！？](?=\s|$)")
_INTERNAL_TERMS = (
    "run",
    "gate",
    "routing",
    "router",
    "reasoning_gate",
    "lens_mode",
    "evidence_mode",
    "phase",
    "state machine",
    "hook",
    "adapter",
    "event journal",
    "task/claim/evidence ids",
    "task_id",
    "judgment_id",
    "claim_id",
    "evidence_id",
    "source_id",
    "schema version",
    "schema_version",
    "repair counter",
    "repair_counter",
    "capability tier",
    "capability_tier",
    "implementation filename",
)
_GENERIC_SOURCE_LABELS = frozenset({"click here", "here", "link"})
_PRIVATE_DISPLAY_RE = re.compile(r"(?:^[/\\~])|(?:^[A-Za-z]:[/\\])|(?:^|[/\\])\.\.(?:[/\\]|$)")
_CONFLICT_MARKERS = (
    " vs ",
    " versus ",
    " but ",
    " while ",
    "although",
    "conflict",
    "disagree",
    "충돌",
    ";",
)


def _violation(rule_id: str, field: str | None, message_key: str) -> Violation:
    return Violation(
        rule_id=rule_id,
        severity=ViolationSeverity.ERROR,
        message_key=message_key,
        field=field,
        repair_hint_key=None,
    )


def _append(violations: list[Violation], rule_id: str, field: str | None, message_key: str) -> None:
    if len(violations) < MAX_RULE_VIOLATIONS:
        violations.append(_violation(rule_id, field, message_key))


def _iter_public_texts(card: ConclusionCard) -> Iterator[tuple[str, str]]:
    yield "conclusion", card.conclusion
    for index, ground in enumerate(card.grounds):
        yield f"grounds[{index}].text", ground.text
        for source_index, source in enumerate(ground.source_refs):
            yield f"grounds[{index}].source_refs[{source_index}].display_name", source.display_name
        if ground.calculation_summary is not None:
            yield f"grounds[{index}].calculation_summary", ground.calculation_summary
    for index, uncertainty in enumerate(card.uncertainties):
        yield f"uncertainties[{index}]", uncertainty
    for index, condition in enumerate(card.flip_conditions):
        yield f"flip_conditions[{index}].condition", condition.condition
        yield f"flip_conditions[{index}].check", condition.check
        if condition.affected_conclusion is not None:
            yield f"flip_conditions[{index}].affected_conclusion", condition.affected_conclusion
    yield "alternatives_summary", card.alternatives_summary


def _contains_internal_vocabulary(value: str) -> bool:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    for term in _INTERNAL_TERMS:
        if "_" in term:
            needle = term.casefold()
            if needle in normalized or needle.replace("_", "-") in normalized:
                return True
            continue
        escaped = re.escape(term.casefold())
        if re.search(rf"(?<![\w]){escaped}(?![\w])", normalized):
            return True
    return False


def contains_internal_vocabulary(value: str) -> bool:
    """Return whether public text contains a prohibited internal term."""

    if not isinstance(value, str):
        raise ValidationError("vocabulary: expected text")
    return _contains_internal_vocabulary(value)


def _check_text(
    violations: list[Violation],
    value: str,
    *,
    field: str,
    maximum: int,
    allow_blank: bool = False,
) -> None:
    try:
        validate_scalar_text(
            value,
            field_name=field,
            max_scalars=maximum,
            allow_newline=False,
            allow_tab=False,
            require_nonblank=not allow_blank,
        )
    except ValidationError:
        _append(violations, "OSV-CARD-001", field, "card.text_invalid")
        return
    try:
        validate_text_urls(value, field_name=field)
    except ValidationError:
        _append(violations, "OSV-SOURCE-003", field, "source.unsafe_url")


def _check_source(
    violations: list[Violation],
    source: CardSourceReference,
    *,
    field: str,
    state: EvidenceState,
) -> None:
    _check_text(violations, source.display_name, field=f"{field}.display_name", maximum=200)
    if source.display_name.strip().casefold() in _GENERIC_SOURCE_LABELS:
        _append(violations, "OSV-SOURCE-002", f"{field}.display_name", "source.generic_label")
    if _PRIVATE_DISPLAY_RE.search(source.display_name):
        _append(violations, "OSV-SOURCE-005", f"{field}.display_name", "source.private_display")
    if source.uri is not None:
        try:
            validate_public_url(source.uri)
        except ValidationError:
            _append(violations, "OSV-SOURCE-001", f"{field}.uri", "source.unsafe_url")
        if _contains_internal_vocabulary(source.uri):
            _append(violations, "OSV-VOCAB-001", f"{field}.uri", "vocabulary.internal_term")
    elif state is EvidenceState.VERIFIED:
        # The only linkless verified source allowed by the public contract is
        # an exact safe user-provided display exception.  The display itself
        # was checked above; there is no path or hidden locator to accept here.
        if not source.display_name.strip():
            _append(violations, "OSV-SOURCE-004", field, "source.user_display_required")


def _check_ground(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    violations: list[Violation], ground: ConclusionGround, index: int, strength: JudgmentStrength
) -> None:
    field = f"grounds[{index}]"
    _check_text(violations, ground.text, field=f"{field}.text", maximum=MAX_GROUND_SCALARS)
    if not isinstance(ground.state, EvidenceState):
        _append(violations, "OSV-EVIDENCE-001", f"{field}.state", "evidence.unknown_state")
        return
    if not ground.claim_id:
        _append(violations, "OSV-EVIDENCE-002", f"{field}.claim_id", "evidence.claim_id_required")
    for source_index, source in enumerate(ground.source_refs):
        _check_source(
            violations,
            source,
            field=f"{field}.source_refs[{source_index}]",
            state=ground.state,
        )
    if ground.calculation_summary is not None:
        _check_text(
            violations,
            ground.calculation_summary,
            field=f"{field}.calculation_summary",
            maximum=400,
        )

    if ground.state is EvidenceState.VERIFIED and not ground.source_refs:
        _append(violations, "OSV-EVIDENCE-003", field, "evidence.verified_source_required")
    elif ground.state is EvidenceState.COMPUTED:
        summary = ground.calculation_summary
        if summary is None or not _CALCULATION_RE.fullmatch(summary):
            _append(
                violations,
                "OSV-CALC-001",
                f"{field}.calculation_summary",
                "calculation.reproducible_required",
            )
        if summary is not None and any(
            token in summary.casefold() for token in ("eval", "exec", "import", "shell")
        ):
            _append(
                violations,
                "OSV-CALC-002",
                f"{field}.calculation_summary",
                "calculation.unsafe_expression",
            )
    elif ground.state is EvidenceState.INFERRED:
        if ground.calculation_summary is not None:
            _append(violations, "OSV-EVIDENCE-004", field, "evidence.inferred_no_calculation")
    elif ground.state is EvidenceState.ASSUMED:
        if ground.source_refs or ground.calculation_summary is not None:
            _append(violations, "OSV-EVIDENCE-005", field, "evidence.assumed_no_support")
    elif ground.state is EvidenceState.CONFLICTED:
        normalized = f" {ground.text.casefold()} "
        has_public_basis = len(ground.source_refs) >= 2 or ground.calculation_summary is not None
        has_conflict_language = any(marker in normalized for marker in _CONFLICT_MARKERS)
        if not has_public_basis and not has_conflict_language:
            _append(violations, "OSV-CONFLICT-001", field, "conflict.public_summary_required")
        if strength in {JudgmentStrength.SUPPORTED, JudgmentStrength.STRONGLY_SUPPORTED}:
            _append(violations, "OSV-CONFLICT-002", field, "conflict.must_lower_strength")


def _check_conclusion(violations: list[Violation], conclusion: str) -> None:
    _check_text(violations, conclusion, field="conclusion", maximum=MAX_CONCLUSION_SCALARS)
    if len(_SENTENCE_END_RE.findall(conclusion)) > 1:
        _append(violations, "OSV-CARD-002", "conclusion", "card.one_sentence_required")


def _check_flip(violations: list[Violation], condition: FlipCondition, index: int) -> None:
    field = f"flip_conditions[{index}]"
    _check_text(
        violations, condition.condition, field=f"{field}.condition", maximum=MAX_FLIP_SCALARS
    )
    _check_text(violations, condition.check, field=f"{field}.check", maximum=MAX_FLIP_SCALARS)
    if condition.affected_conclusion is not None:
        _check_text(
            violations,
            condition.affected_conclusion,
            field=f"{field}.affected_conclusion",
            maximum=MAX_FLIP_SCALARS,
        )
    if condition.condition.strip().casefold() in _GENERIC_FLIPS:
        _append(violations, "OSV-CARD-003", f"{field}.condition", "card.observable_flip_required")
    if not isinstance(condition.direction, FlipDirection):
        _append(violations, "OSV-CARD-004", f"{field}.direction", "card.unknown_flip_direction")


def _check_vocabulary(violations: list[Violation], card: ConclusionCard) -> None:
    for field, value in _iter_public_texts(card):
        if _contains_internal_vocabulary(value):
            _append(violations, "OSV-VOCAB-001", field, "vocabulary.internal_term")


def _check_secret_patterns(violations: list[Violation], card: ConclusionCard) -> None:
    values: dict[str, Any] = {field: value for field, value in _iter_public_texts(card)}
    for index, ground in enumerate(card.grounds):
        for source_index, source in enumerate(ground.source_refs):
            values[f"grounds[{index}].source_refs[{source_index}].uri"] = source.uri
    if scan_secrets(values):
        _append(violations, "OSV-PRIVACY-001", None, "privacy.secret_or_unsafe_text")


def collect_card_violations(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    card: ConclusionCard,
    *,
    markdown: str | None = None,
) -> tuple[Violation, ...]:
    """Return bounded deterministic violations for a typed public card."""

    if not isinstance(card, ConclusionCard):
        raise ValidationError("card rules: expected ConclusionCard")
    violations: list[Violation] = []
    if str(card.locale) not in {"en", "ko"}:
        _append(violations, "OSV-LOCALE-001", "locale", "locale.unsupported")
    if not 1 <= len(card.grounds) <= MAX_CARD_GROUNDS:
        _append(violations, "OSV-CARD-005", "grounds", "card.ground_count")
    if len(card.uncertainties) > MAX_CARD_UNCERTAINTIES:
        _append(violations, "OSV-CARD-006", "uncertainties", "card.uncertainty_count")
    if not 1 <= len(card.flip_conditions) <= MAX_CARD_FLIP_CONDITIONS:
        _append(violations, "OSV-CARD-007", "flip_conditions", "card.flip_count")
    if (
        not isinstance(card.judgment_version, int)
        or isinstance(card.judgment_version, bool)
        or card.judgment_version < 1
    ):
        _append(violations, "OSV-CARD-008", "judgment_version", "card.version_invalid")

    _check_conclusion(violations, card.conclusion)
    for index, ground in enumerate(card.grounds):
        _check_ground(violations, ground, index, card.strength)
    for index, uncertainty in enumerate(card.uncertainties):
        _check_text(
            violations,
            uncertainty,
            field=f"uncertainties[{index}]",
            maximum=MAX_UNCERTAINTY_SCALARS,
        )
    for index, condition in enumerate(card.flip_conditions):
        _check_flip(violations, condition, index)
    _check_text(
        violations,
        card.alternatives_summary,
        field="alternatives_summary",
        maximum=MAX_ALTERNATIVES_SCALARS,
    )

    states = {ground.state for ground in card.grounds}
    if card.strength is JudgmentStrength.STRONGLY_SUPPORTED and not states.issubset(
        {EvidenceState.VERIFIED, EvidenceState.COMPUTED}
    ):
        _append(
            violations, "OSV-EVIDENCE-006", "strength", "evidence.strong_strength_requires_support"
        )
    if card.strength is JudgmentStrength.PROVISIONAL and not states.intersection(
        {EvidenceState.ASSUMED, EvidenceState.UNVERIFIED, EvidenceState.CONFLICTED}
    ):
        _append(violations, "OSV-EVIDENCE-007", "strength", "evidence.provisional_basis_required")
    if card.strength is JudgmentStrength.SUPPORTED and states.intersection(
        {EvidenceState.ASSUMED, EvidenceState.UNVERIFIED, EvidenceState.CONFLICTED}
    ):
        _append(
            violations,
            "OSV-EVIDENCE-009",
            "strength",
            "evidence.uncertain_strength_requires_downgrade",
        )
    if not isinstance(card.strength, JudgmentStrength):
        _append(violations, "OSV-EVIDENCE-008", "strength", "evidence.unknown_strength")

    _check_vocabulary(violations, card)
    _check_secret_patterns(violations, card)
    if markdown is not None:
        try:
            normalized = validate_card_markdown(
                markdown, max_lines=MAX_CARD_LINES, max_scalars=MAX_CARD_SCALARS
            )
            if nonblank_line_count(normalized) == 0:
                _append(violations, "OSV-CARD-009", None, "card.empty")
        except ValidationError:
            _append(violations, "OSV-CARD-010", None, "card.collapsed_limits")
    return tuple(violations[:MAX_RULE_VIOLATIONS])


def validate_card_rules(
    card: ConclusionCard, *, markdown: str | None = None
) -> tuple[Violation, ...]:
    """Alias emphasizing that this function is a pure validator."""

    return collect_card_violations(card, markdown=markdown)


def enforce_card_rules(card: ConclusionCard, *, markdown: str | None = None) -> ConclusionCard:
    """Raise ``ValidationError`` when any card rule is violated."""

    violations = collect_card_violations(card, markdown=markdown)
    if violations:
        details = ", ".join(
            f"{item.rule_id}{f'@{item.field}' if item.field else ''}" for item in violations
        )
        raise ValidationError(f"card verification failed: {details}")
    return card


def is_valid_card(card: ConclusionCard, *, markdown: str | None = None) -> bool:
    """Return whether the typed card passes all bounded card rules."""

    return not collect_card_violations(card, markdown=markdown)


validate_card = validate_card_rules
verify_card = enforce_card_rules
check_card = validate_card_rules
collect_violations = collect_card_violations


__all__ = [
    "MAX_ALTERNATIVES_SCALARS",
    "MAX_CONCLUSION_SCALARS",
    "MAX_FLIP_SCALARS",
    "MAX_GROUND_SCALARS",
    "MAX_RULE_VIOLATIONS",
    "MAX_UNCERTAINTY_SCALARS",
    "check_card",
    "collect_card_violations",
    "collect_violations",
    "contains_internal_vocabulary",
    "enforce_card_rules",
    "is_valid_card",
    "validate_card",
    "validate_card_rules",
    "verify_card",
]
