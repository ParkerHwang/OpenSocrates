"""Strict Markdown-to-typed Conclusion Card parser.

Only the bounded public card segment is accepted.  IDs and timestamps are
trusted boundary values: they are supplied explicitly by the native handler or
generated here from the standard-library ID/clock ports.  No identifier or
timestamp is ever read from Markdown prose.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..clock import Clock, utc_timestamp
from ..domain.enums import EvidenceState, FlipDirection, JudgmentStrength
from ..domain.models import CardSourceReference, ConclusionCard, ConclusionGround, FlipCondition
from ..errors import ValidationError
from ..ids import (
    new_local_id,
    new_task_id,
    validate_local_id,
    validate_task_id,
    validate_timestamp,
)
from ..rendering.card import card_locale_messages, render_card
from ..rendering.markdown import (
    nonblank_line_count,
    normalize_markdown,
    parse_inline_code,
    parse_link,
    scalar_count,
    unescape_inline,
    validate_card_markdown,
)
from .card_rules import enforce_card_rules

_HEADING_RE = re.compile(r"^(#{1,6}) (.+)$")
_MODEL_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])[JCEAKI][0-9]{6}(?![A-Za-z0-9])|(?<![A-Za-z0-9])[0-9A-HJKMNP-TV-Z]{26}(?![A-Za-z0-9])"
)
_GROUND_MARKER = " — **"


@dataclass(frozen=True, slots=True)
class TrustedCardContext:
    """Trusted native values used to bind a parsed public card."""

    task_id: str | None = None
    judgment_id: str | None = None
    claim_ids: tuple[str, ...] | None = None
    judgment_version: int = 1
    rendered_at: str | None = None
    clock: Clock | None = None


def _heading(line: str) -> tuple[int, str] | None:
    match = _HEADING_RE.fullmatch(line)
    if match is None:
        return None
    return len(match.group(1)), match.group(2)


def _clean_lines(markdown: str) -> tuple[str, list[str]]:
    normalized = normalize_markdown(markdown)
    validate_card_markdown(normalized)
    if _MODEL_ID_RE.search(normalized):
        raise ValidationError("card parser: model-provided identifier is not accepted")
    lines: list[str] = []
    for line in normalized.split("\n"):
        if not line.strip():
            continue
        if line != line.strip():
            raise ValidationError("card parser: leading/trailing line whitespace is not allowed")
        lines.append(line)
    if not lines:
        raise ValidationError("card parser: card is empty")
    if nonblank_line_count(normalized) > 14 or scalar_count(normalized) > 2200:
        raise ValidationError("card parser: card exceeds collapsed limits")
    return normalized, lines


def _reverse_labels(
    messages: Mapping[str, str], keys: Sequence[str], *, field: str
) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in keys:
        label = messages[key]
        if label in result:
            raise ValidationError(f"card parser: duplicate locale label for {field}")
        result[label] = key
    return result


def _split_support(value: str) -> list[str]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Split semicolon-delimited card metadata outside links/code spans."""

    pieces: list[str] = []
    start = 0
    index = 0
    code_fence = 0
    bracket_depth = 0
    paren_depth = 0
    while index < len(value):
        character = value[index]
        if character == "\\":
            index += 2
            continue
        if character == "`":
            fence = 1
            while index + fence < len(value) and value[index + fence] == "`":
                fence += 1
            if code_fence == 0:
                code_fence = fence
            elif fence == code_fence:
                code_fence = 0
            index += fence
            continue
        if code_fence:
            index += 1
            continue
        if character == "[":
            bracket_depth += 1
        elif character == "]" and bracket_depth:
            bracket_depth -= 1
        elif character == "(" and bracket_depth == 0:
            paren_depth += 1
        elif character == ")" and paren_depth:
            paren_depth -= 1
        elif character == ";" and bracket_depth == 0 and paren_depth == 0:
            piece = value[start:index].strip()
            if not piece:
                raise ValidationError("card parser: empty support field")
            pieces.append(piece)
            start = index + 1
        index += 1
    if code_fence or bracket_depth or paren_depth:
        raise ValidationError("card parser: malformed support metadata")
    piece = value[start:].strip()
    if not piece:
        raise ValidationError("card parser: empty support field")
    pieces.append(piece)
    return pieces


def _parse_support(
    value: str, messages: Mapping[str, str], *, field: str
) -> tuple[tuple[CardSourceReference, ...], str | None]:
    if not value:
        return (), None
    if not value.startswith(" (") or not value.endswith(")"):
        raise ValidationError(f"card parser: malformed {field} support")
    content = value[2:-1]
    sources: list[CardSourceReference] = []
    calculation: str | None = None
    user_prefix = f"{messages['card.source.user_provided']}: "
    for piece in _split_support(content):
        if piece.startswith("`"):
            if calculation is not None:
                raise ValidationError(f"card parser: duplicate {field} calculation")
            calculation = parse_inline_code(piece, field_name=f"{field}.calculation")
            continue
        source_value = piece
        if source_value.startswith("["):
            display_name, uri = parse_link(source_value, field_name=f"{field}.source")
        elif source_value.startswith(user_prefix):
            display_name = unescape_inline(
                source_value[len(user_prefix) :],
                field_name=f"{field}.source.display_name",
            )
            uri = None
        else:
            raise ValidationError(f"card parser: unsupported {field} support form")
        sources.append(CardSourceReference(display_name=display_name, uri=uri))
    return tuple(sources), calculation


def _parse_conclusion(
    line: str, strength_labels: Mapping[str, str]
) -> tuple[str, JudgmentStrength]:
    marker = line.rfind(_GROUND_MARKER)
    if marker <= 0 or not line.endswith("**"):
        raise ValidationError("card parser: conclusion must carry a strength label")
    conclusion_raw = line[:marker]
    strength_label = line[marker + len(_GROUND_MARKER) : -2]
    strength_key = strength_labels.get(strength_label)
    if strength_key is None:
        raise ValidationError("card parser: unknown conclusion strength label")
    conclusion = unescape_inline(conclusion_raw, field_name="conclusion")
    return conclusion, JudgmentStrength(strength_key.rsplit(".", 1)[1])


def _split_ground_line(line: str) -> tuple[str, str, str]:
    if not line.startswith("- "):
        raise ValidationError("card parser: ground must be a bullet")
    marker = line.rfind(_GROUND_MARKER)
    if marker <= 2:
        raise ValidationError("card parser: ground is missing evidence state")
    state_start = marker + len(_GROUND_MARKER)
    state_end = line.find("**", state_start)
    if state_end <= state_start:
        raise ValidationError("card parser: ground has malformed evidence label")
    return line[2:marker], line[state_start:state_end], line[state_end + 2 :]


def _parse_ground(
    line: str,
    state_labels: Mapping[str, str],
    messages: Mapping[str, str],
    claim_id: str,
) -> ConclusionGround:
    text_raw, state_label, support = _split_ground_line(line)
    state_key = state_labels.get(state_label)
    if state_key is None:
        raise ValidationError("card parser: unknown evidence state label")
    text = unescape_inline(text_raw, field_name="ground.text")
    sources, calculation = _parse_support(support, messages, field="ground")
    return ConclusionGround(
        claim_id=claim_id,
        text=text,
        state=EvidenceState(state_key.rsplit(".", 1)[1]),
        source_refs=sources,
        calculation_summary=calculation,
    )


def _parse_flip_line(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    line: str,
    direction_labels: Mapping[str, str],
    messages: Mapping[str, str],
) -> FlipCondition:
    if not line.startswith("- "):
        raise ValidationError("card parser: flip condition must be a bullet")
    marker = line.rfind(_GROUND_MARKER)
    if marker <= 2:
        raise ValidationError("card parser: flip condition is missing direction")
    direction_start = marker + len(_GROUND_MARKER)
    direction_end = line.find("**", direction_start)
    if direction_end <= direction_start:
        raise ValidationError("card parser: flip condition has malformed direction")
    direction_label = line[direction_start:direction_end]
    direction_key = direction_labels.get(direction_label)
    if direction_key is None:
        raise ValidationError("card parser: unknown flip direction label")
    support = line[direction_end + 2 :]
    if not support.startswith(" (") or not support.endswith(")"):
        raise ValidationError("card parser: flip condition requires check metadata")
    fields = _split_support(support[2:-1])
    check: str | None = None
    affected: str | None = None
    check_prefix = f"{messages['card.flip.check']}: "
    affected_prefix = f"{messages['card.flip.affected_conclusion']}: "
    for field_value in fields:
        if field_value.startswith(check_prefix):
            if check is not None:
                raise ValidationError("card parser: duplicate flip check")
            check = unescape_inline(field_value[len(check_prefix) :], field_name="flip.check")
        elif field_value.startswith(affected_prefix):
            if affected is not None:
                raise ValidationError("card parser: duplicate affected conclusion")
            affected = unescape_inline(
                field_value[len(affected_prefix) :],
                field_name="flip.affected_conclusion",
            )
        else:
            raise ValidationError("card parser: unknown flip metadata")
    if check is None:
        raise ValidationError("card parser: flip condition requires a check")
    condition = unescape_inline(line[2:marker], field_name="flip.condition")
    return FlipCondition(
        condition=condition,
        affected_conclusion=affected,
        direction=FlipDirection(direction_key.rsplit(".", 1)[1]),
        check=check,
    )


def _section_heading(line: str, depth: int, title: str) -> bool:
    parsed = _heading(line)
    return parsed == (depth, title)


def _next_heading(lines: Sequence[str], index: int) -> bool:
    return index < len(lines) and _heading(lines[index]) is not None


def _resolve_alias(primary: Any, alias: Any, *, field: str) -> Any:
    if primary is not None and alias is not None and primary != alias:
        raise ValidationError(f"card parser: conflicting trusted {field}")
    return primary if primary is not None else alias


def _normalize_claim_ids(value: Sequence[str] | None, *, field: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    try:
        return tuple(value)
    except TypeError as exc:
        raise ValidationError(f"card parser: trusted {field} must be a sequence") from exc


def _bind_ids(
    *,
    clock: Clock | None,
    task_id: str | None,
    judgment_id: str | None,
    claim_ids: Sequence[str] | None,
    judgment_version: int,
    rendered_at: str | None,
) -> tuple[str, str, tuple[str, ...] | None, int, str]:
    bound_task = task_id if task_id is not None else new_task_id(clock)
    try:
        validate_task_id(bound_task, clock=clock)
    except Exception as exc:
        raise ValidationError("card parser: trusted task_id is invalid") from exc
    bound_judgment = judgment_id if judgment_id is not None else new_local_id("J", 1)
    try:
        validate_local_id(bound_judgment, "J")
    except Exception as exc:
        raise ValidationError("card parser: trusted judgment_id is invalid") from exc
    if claim_ids is not None:
        bound_claims = tuple(claim_ids)
        try:
            for claim_id in bound_claims:
                validate_local_id(claim_id, "C")
        except Exception as exc:
            raise ValidationError("card parser: trusted claim_id is invalid") from exc
        if len(set(bound_claims)) != len(bound_claims):
            raise ValidationError("card parser: trusted claim_ids must be unique")
    else:
        bound_claims = None
    if (
        not isinstance(judgment_version, int)
        or isinstance(judgment_version, bool)
        or judgment_version < 1
    ):
        raise ValidationError("card parser: trusted judgment_version is invalid")
    bound_rendered_at = rendered_at if rendered_at is not None else utc_timestamp(clock)
    try:
        validate_timestamp(bound_rendered_at)
    except Exception as exc:
        raise ValidationError("card parser: trusted rendered_at is invalid") from exc
    return bound_task, bound_judgment, bound_claims, judgment_version, bound_rendered_at


def parse_card(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    markdown: str,
    locale: str = "en",
    locale_catalog: Mapping[str, Any] | None = None,
    *,
    locale_messages: Mapping[str, Any] | None = None,
    task_id: str | None = None,
    judgment_id: str | None = None,
    claim_ids: Sequence[str] | None = None,
    judgment_version: int = 1,
    rendered_at: str | None = None,
    clock: Clock | None = None,
    trusted_task_id: str | None = None,
    trusted_judgment_id: str | None = None,
    trusted_claim_ids: Sequence[str] | None = None,
    context: TrustedCardContext | None = None,
) -> ConclusionCard:
    """Parse a strict card and bind trusted/generated identity fields.

    ``task_id``, ``judgment_id``, ``claim_ids``, and ``rendered_at`` are
    boundary arguments only.  Markdown has no accepted syntax for any of
    them; identifier-like prose is rejected before construction.
    """

    if not isinstance(markdown, str):
        raise ValidationError("card parser: Markdown must be text")
    if locale_catalog is not None and locale_messages is not None:
        raise ValidationError("card parser: provide one locale catalog")
    catalog = locale_messages if locale_messages is not None else locale_catalog
    if catalog is None:
        raise ValidationError("card parser: locale catalog is required")
    if not isinstance(locale, str) or locale not in {"en", "ko"}:
        raise ValidationError("card parser: locale must be en or ko")
    messages = card_locale_messages(catalog, locale)
    normalized, lines = _clean_lines(markdown)
    heading_data = _heading(lines[0])
    if heading_data is None:
        raise ValidationError("card parser: card must begin with a heading")
    root_depth, root_title = heading_data
    if root_title != messages["card.heading.conclusion"]:
        raise ValidationError("card parser: unknown conclusion heading")
    if root_depth >= 6:
        raise ValidationError("card parser: heading depth leaves no section level")
    section_depth = root_depth + 1
    expected = (
        messages["card.heading.why"],
        messages["card.heading.still_uncertain"],
        messages["card.heading.this_flips_if"],
        messages["card.heading.alternatives_considered"],
    )
    if len(lines) < 3:
        raise ValidationError("card parser: card is incomplete")
    conclusion, strength = _parse_conclusion(
        lines[1],
        _reverse_labels(
            messages,
            tuple(f"card.strength.{item.value}" for item in JudgmentStrength),
            field="strength",
        ),
    )
    index = 2
    if not _section_heading(lines[index], section_depth, expected[0]):
        raise ValidationError("card parser: missing or unknown Why heading")
    index += 1
    ground_lines: list[str] = []
    while index < len(lines) and not _next_heading(lines, index):
        ground_lines.append(lines[index])
        index += 1
    if not 1 <= len(ground_lines) <= 5:
        raise ValidationError("card parser: grounds must contain one through five bullets")

    if index >= len(lines) or not _section_heading(lines[index], section_depth, expected[1]):
        raise ValidationError("card parser: missing or unknown uncertainty heading")
    index += 1
    uncertainty_lines: list[str] = []
    while index < len(lines) and not _next_heading(lines, index):
        uncertainty_lines.append(lines[index])
        index += 1
    if len(uncertainty_lines) > 2:
        raise ValidationError("card parser: at most two uncertainty bullets are allowed")
    for line in uncertainty_lines:
        if not line.startswith("- "):
            raise ValidationError("card parser: uncertainty must be a bullet")
    none_uncertainty = f"- {messages['card.uncertainty.none']}"
    if none_uncertainty in uncertainty_lines:
        if uncertainty_lines != [none_uncertainty]:
            raise ValidationError(
                "card parser: none-uncertainty marker cannot be combined with uncertainty"
            )
        uncertainty_lines = []

    if index >= len(lines) or not _section_heading(lines[index], section_depth, expected[2]):
        raise ValidationError("card parser: missing or unknown flip heading")
    index += 1
    flip_lines: list[str] = []
    while index < len(lines) and not _next_heading(lines, index):
        flip_lines.append(lines[index])
        index += 1
    if not 1 <= len(flip_lines) <= 2:
        raise ValidationError("card parser: flip conditions must contain one or two bullets")

    if index >= len(lines) or not _section_heading(lines[index], section_depth, expected[3]):
        raise ValidationError("card parser: missing or unknown alternatives heading")
    index += 1
    alternatives_lines = lines[index:]
    if (
        len(alternatives_lines) != 1
        or alternatives_lines[0].startswith("- ")
        or _heading(alternatives_lines[0])
    ):
        raise ValidationError("card parser: alternatives must be one compact paragraph")

    state_labels = _reverse_labels(
        messages,
        tuple(f"card.state.{item.value}" for item in EvidenceState),
        field="evidence state",
    )
    direction_labels = _reverse_labels(
        messages,
        tuple(f"card.flip.direction.{item.value}" for item in FlipDirection),
        field="flip direction",
    )
    if context is not None and not isinstance(context, TrustedCardContext):
        raise ValidationError("card parser: context must be TrustedCardContext")
    trusted_context = context or TrustedCardContext()
    bound_clock = trusted_context.clock if context is not None and clock is None else clock
    bound_task = _resolve_alias(task_id, trusted_context.task_id, field="task_id")
    bound_task = _resolve_alias(bound_task, trusted_task_id, field="task_id")
    bound_judgment = _resolve_alias(judgment_id, trusted_context.judgment_id, field="judgment_id")
    bound_judgment = _resolve_alias(bound_judgment, trusted_judgment_id, field="judgment_id")
    provided_claim_ids = _normalize_claim_ids(claim_ids, field="claim_ids")
    context_claim_ids = _normalize_claim_ids(trusted_context.claim_ids, field="claim_ids")
    alias_claim_ids = _normalize_claim_ids(trusted_claim_ids, field="claim_ids")
    bound_claims = _resolve_alias(provided_claim_ids, context_claim_ids, field="claim_ids")
    bound_claims = _resolve_alias(bound_claims, alias_claim_ids, field="claim_ids")
    bound_version = judgment_version
    if (
        context is not None
        and judgment_version != 1
        and judgment_version != context.judgment_version
    ):
        raise ValidationError("card parser: conflicting trusted judgment_version")
    if context is not None and judgment_version == 1:
        bound_version = context.judgment_version
    bound_rendered_at = _resolve_alias(
        rendered_at, trusted_context.rendered_at, field="rendered_at"
    )
    bound_task_id, bound_judgment_id, bound_claim_ids, bound_version, bound_time = _bind_ids(
        clock=bound_clock,
        task_id=bound_task,
        judgment_id=bound_judgment,
        claim_ids=bound_claims,
        judgment_version=bound_version,
        rendered_at=bound_rendered_at,
    )
    if bound_claim_ids is not None and len(bound_claim_ids) != len(ground_lines):
        raise ValidationError("card parser: trusted claim_ids must match ground count")
    effective_claim_ids = bound_claim_ids or tuple(
        new_local_id("C", item) for item in range(1, len(ground_lines) + 1)
    )

    grounds = tuple(
        _parse_ground(line, state_labels, messages, effective_claim_ids[item])
        for item, line in enumerate(ground_lines)
    )
    uncertainties = tuple(
        unescape_inline(line[2:], field_name=f"uncertainties[{item}]")
        for item, line in enumerate(uncertainty_lines)
    )
    flips = tuple(_parse_flip_line(line, direction_labels, messages) for line in flip_lines)
    alternatives_summary = unescape_inline(alternatives_lines[0], field_name="alternatives_summary")
    card = ConclusionCard(
        locale=locale,
        task_id=bound_task_id,
        judgment_id=bound_judgment_id,
        judgment_version=bound_version,
        conclusion=conclusion,
        strength=strength,
        grounds=grounds,
        uncertainties=uncertainties,
        flip_conditions=flips,
        alternatives_summary=alternatives_summary,
        rendered_at=bound_time,
    )
    enforce_card_rules(card, markdown=normalized)
    canonical = render_card(card, catalog, heading_level=root_depth)
    if canonical != "\n".join(lines):
        raise ValidationError("card parser: Markdown is not canonical")
    return card


parse_conclusion_card = parse_card
parse_markdown_card = parse_card


__all__ = [
    "TrustedCardContext",
    "parse_card",
    "parse_conclusion_card",
    "parse_markdown_card",
]
