"""Canonical, zero-model Conclusion Card Markdown renderer.

The renderer accepts only an already typed :class:`ConclusionCard` and a
trusted locale catalog projection.  It never reads locale files, calls a
model, performs network I/O, or looks up source URLs.  Locale-key absence is a
hard error so English text cannot silently leak into a Korean card (or vice
versa).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..domain.enums import EvidenceState, FlipDirection, JudgmentStrength
from ..domain.models import CardSourceReference, ConclusionCard, ConclusionGround, FlipCondition
from ..errors import ValidationError
from .markdown import (
    escape_inline,
    inline_code,
    render_link,
    validate_card_markdown,
    validate_scalar_text,
)

CARD_LOCALE_KEYS: tuple[str, ...] = (
    "card.heading.conclusion",
    "card.heading.why",
    "card.heading.still_uncertain",
    "card.heading.this_flips_if",
    "card.heading.alternatives_considered",
    "card.state.verified",
    "card.state.computed",
    "card.state.inferred",
    "card.state.assumed",
    "card.state.unverified",
    "card.state.conflicted",
    "card.uncertainty.none",
    "card.source.user_provided",
    "card.strength.held",
    "card.strength.provisional",
    "card.strength.supported",
    "card.strength.strongly_supported",
    "card.flip.direction.strengthen",
    "card.flip.direction.weaken",
    "card.flip.direction.reverse",
    "card.flip.direction.hold",
    "card.flip.check",
    "card.flip.affected_conclusion",
)

_STATE_KEY = {state: f"card.state.{state.value}" for state in EvidenceState}
_STRENGTH_KEY = {strength: f"card.strength.{strength.value}" for strength in JudgmentStrength}
_DIRECTION_KEY = {
    direction: f"card.flip.direction.{direction.value}" for direction in FlipDirection
}


def _messages_from_catalog(locale_catalog: Mapping[str, Any], locale: str) -> dict[str, str]:
    """Extract one locale's flat message map and enforce the card key set."""

    if locale not in {"en", "ko"}:
        raise ValidationError("card.locale: locale must be en or ko")
    if not isinstance(locale_catalog, Mapping):
        raise ValidationError("card.locale: a locale catalog is required")

    candidate: Any = locale_catalog
    declared_locale = locale_catalog.get("locale")
    if "messages" in locale_catalog:
        if declared_locale is not None and declared_locale != locale:
            raise ValidationError("card.locale: catalog locale does not match card locale")
        candidate = locale_catalog["messages"]
    elif locale in locale_catalog and isinstance(locale_catalog[locale], Mapping):
        candidate = locale_catalog[locale]

    if not isinstance(candidate, Mapping):
        raise ValidationError("card.locale: catalog messages must be a mapping")
    messages: dict[str, str] = {}
    for key in CARD_LOCALE_KEYS:
        value = candidate.get(key)
        if not isinstance(value, str):
            raise ValidationError(f"card.locale: missing required key {key}")
        messages[key] = validate_scalar_text(value, field_name=f"locale.{key}", max_scalars=4000)
    return messages


def card_locale_messages(locale_catalog: Mapping[str, Any], locale: str) -> dict[str, str]:
    """Public fail-closed locale projection used by renderer and parser."""

    return _messages_from_catalog(locale_catalog, locale)


def required_card_locale_keys() -> tuple[str, ...]:
    """Return the exact locale keys consumed by the canonical card surface."""

    return CARD_LOCALE_KEYS


def _source_token(source: CardSourceReference, messages: Mapping[str, str]) -> str:
    if source.uri is not None:
        return render_link(source.display_name, source.uri)
    label = messages["card.source.user_provided"]
    return f"{label}: {escape_inline(source.display_name, field_name='source.display_name', max_scalars=200, escape_semicolons=True)}"


def _ground_line(ground: ConclusionGround, messages: Mapping[str, str]) -> str:
    state_label = messages[_STATE_KEY[ground.state]]
    support: list[str] = []
    if ground.calculation_summary is not None:
        support.append(
            inline_code(ground.calculation_summary, field_name="ground.calculation_summary")
        )
    support.extend(_source_token(source, messages) for source in ground.source_refs)
    suffix = f" ({'; '.join(support)})" if support else ""
    return (
        f"- {escape_inline(ground.text, field_name='ground.text', max_scalars=600)}"
        f" — **{escape_inline(state_label, field_name='locale.state', max_scalars=4000)}**{suffix}"
    )


def _flip_line(condition: FlipCondition, messages: Mapping[str, str]) -> str:
    direction_label = messages[_DIRECTION_KEY[condition.direction]]
    support = [
        f"{messages['card.flip.check']}: "
        f"{escape_inline(condition.check, field_name='flip.check', max_scalars=240, escape_semicolons=True)}"
    ]
    if condition.affected_conclusion is not None:
        support.append(
            f"{messages['card.flip.affected_conclusion']}: "
            f"{escape_inline(condition.affected_conclusion, field_name='flip.affected_conclusion', max_scalars=240, escape_semicolons=True)}"
        )
    return (
        f"- {escape_inline(condition.condition, field_name='flip.condition', max_scalars=300)}"
        f" — **{escape_inline(direction_label, field_name='locale.direction', max_scalars=4000)}**"
        f" ({'; '.join(support)})"
    )


def _render_card(card: ConclusionCard, messages: Mapping[str, str], *, heading_level: int) -> str:
    heading = "#" * heading_level
    subheading = "#" * (heading_level + 1)
    lines = [
        f"{heading} {messages['card.heading.conclusion']}",
        f"{escape_inline(card.conclusion, field_name='card.conclusion', max_scalars=500)}"
        f" — **{escape_inline(messages[_STRENGTH_KEY[card.strength]], field_name='locale.strength', max_scalars=4000)}**",
        f"{subheading} {messages['card.heading.why']}",
    ]
    lines.extend(_ground_line(ground, messages) for ground in card.grounds)
    lines.append(f"{subheading} {messages['card.heading.still_uncertain']}")
    if card.uncertainties:
        lines.extend(
            f"- {escape_inline(item, field_name='card.uncertainty', max_scalars=220)}"
            for item in card.uncertainties
        )
    else:
        lines.append(
            f"- {escape_inline(messages['card.uncertainty.none'], field_name='locale.uncertainty.none', max_scalars=220)}"
        )
    lines.append(f"{subheading} {messages['card.heading.this_flips_if']}")
    lines.extend(_flip_line(condition, messages) for condition in card.flip_conditions)
    lines.extend(
        (
            f"{subheading} {messages['card.heading.alternatives_considered']}",
            escape_inline(
                card.alternatives_summary, field_name="card.alternatives_summary", max_scalars=800
            ),
        )
    )
    return "\n".join(lines)


def render_card(
    card: ConclusionCard,
    locale_catalog: Mapping[str, Any] | None = None,
    *,
    locale_messages: Mapping[str, Any] | None = None,
    heading_level: int = 2,
) -> str:
    """Render a typed card into canonical Markdown.

    ``locale_catalog`` may be either the content loader's ``{locale,
    messages}`` object or the compiled bundle's ``{en: ..., ko: ...}``
    projection.  A flat message map is also accepted when it is already the
    card's locale.  No default catalog exists by design.
    """

    if not isinstance(card, ConclusionCard):
        raise ValidationError("card: expected ConclusionCard")
    if locale_catalog is not None and locale_messages is not None:
        raise ValidationError("card: provide one locale catalog")
    catalog = locale_messages if locale_messages is not None else locale_catalog
    if catalog is None:
        raise ValidationError("card: locale catalog is required")
    if (
        not isinstance(heading_level, int)
        or isinstance(heading_level, bool)
        or not 1 <= heading_level <= 5
    ):
        raise ValidationError("card: heading level must be between one and five")
    messages = card_locale_messages(catalog, str(card.locale))

    # Import lazily to keep verification independent of the renderer module at
    # import time and to make the production import boundary obvious.
    from ..verification.card_rules import enforce_card_rules

    enforce_card_rules(card)
    rendered = _render_card(card, messages, heading_level=heading_level)
    rendered = validate_card_markdown(rendered)
    enforce_card_rules(card, markdown=rendered)
    return rendered


def render_conclusion_card(
    card: ConclusionCard,
    locale_catalog: Mapping[str, Any] | None = None,
    *,
    locale_messages: Mapping[str, Any] | None = None,
    heading_level: int = 2,
) -> str:
    """Explicit alias for callers that prefer the domain object name."""

    return render_card(
        card,
        locale_catalog,
        locale_messages=locale_messages,
        heading_level=heading_level,
    )


render = render_card


__all__ = [
    "CARD_LOCALE_KEYS",
    "card_locale_messages",
    "render",
    "render_card",
    "render_conclusion_card",
    "required_card_locale_keys",
]
