"""Deterministic localized Markdown rendering for a validated ``TraceView``.

This module never accepts JSONL events and never calls a model.  The current
card is rendered only by the injected card renderer so the card contract stays
owned by the conclusion-card slice.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Final, Protocol

from ..domain.enums import CriterionStatus
from ..domain.models import ConclusionCard, TraceView
from ..domain.validation import validate_model
from ..errors import OpenSocratesError
from .markdown import escape_inline
from .messages import LocaleCatalog, MessageCatalogError, placeholder_names


class TraceRenderError(ValueError):
    """Raised when a trace view or locale catalog cannot be rendered safely."""


class CardRenderer(Protocol):
    """The narrow card-renderer seam consumed by the trace renderer."""

    def __call__(
        self,
        card: ConclusionCard,
        locale_catalog: object,
        *,
        heading_level: int,
    ) -> str: ...


TRACE_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "trace.title",
    "trace.heading.framing",
    "trace.heading.what_changed",
    "trace.heading.methods_used",
    "trace.heading.evidence_changes",
    "trace.heading.conflicts_and_responses",
    "trace.heading.alternatives",
    "trace.heading.completion_check",
    "trace.heading.current_conclusion",
    "trace.label.decision_question",
    "trace.label.assumptions_published",
    "trace.label.completion_criteria",
    "trace.label.source",
    "trace.label.resolution",
    "trace.method.activation_confirmed",
    "trace.method.selected_not_confirmed",
    "trace.completion.met",
    "trace.completion.unmet",
    "trace.completion.unverified",
    "trace.completion.not_applicable",
    "trace.private_reasoning",
    "trace.record.partial",
    "trace.record.corrupt",
)
_EXISTING_TRACE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "trace.not_recorded",
        "trace.unavailable",
        "trace.none",
        "trace.primary",
        "trace.secondary",
    }
)
_REUSED_CARD_KEYS: Final[frozenset[str]] = frozenset(
    {
        "card.state.verified",
        "card.state.computed",
        "card.state.inferred",
        "card.state.assumed",
        "card.state.unverified",
        "card.state.conflicted",
    }
)
_ALL_TRACE_KEYS: Final[frozenset[str]] = frozenset(
    (*TRACE_LOCALE_KEYS, *_EXISTING_TRACE_KEYS, *_REUSED_CARD_KEYS)
)
_CRITERION_KEYS: Final[dict[CriterionStatus, str]] = {
    CriterionStatus.MET: "trace.completion.met",
    CriterionStatus.UNMET: "trace.completion.unmet",
    CriterionStatus.UNVERIFIED: "trace.completion.unverified",
    CriterionStatus.NOT_APPLICABLE: "trace.completion.not_applicable",
    CriterionStatus.NOT_RECORDED: "trace.not_recorded",
}


def _messages(catalog: object, locale: str) -> Mapping[str, str]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Read exactly one locale; never search another locale or inline text."""

    if isinstance(catalog, LocaleCatalog):
        return catalog.locale_messages[locale]
    if not isinstance(catalog, Mapping):
        raise TraceRenderError("trace renderer requires a LocaleCatalog or locale mapping")
    if "locale_messages" in catalog:
        candidate = catalog.get("locale_messages")
        if isinstance(candidate, Mapping):
            candidate = candidate.get(locale)
    elif "messages" in catalog:
        declared = catalog.get("locale")
        if declared is not None and declared != locale:
            raise TraceRenderError("trace locale catalog does not match the view locale")
        candidate = catalog.get("messages")
    elif locale in catalog and isinstance(catalog[locale], Mapping):
        candidate = catalog[locale]
    else:
        candidate = catalog
    if not isinstance(candidate, Mapping):
        raise TraceRenderError("trace locale messages must be a mapping")
    normalized: dict[str, str] = {}
    for key in _ALL_TRACE_KEYS:
        value = candidate.get(key)
        if not isinstance(value, str):
            raise TraceRenderError(f"missing locale key {locale}.{key}")
        normalized[key] = value
    return normalized


def _lookup(messages: Mapping[str, str], locale: str, key: str, **values: object) -> str:
    template = messages.get(key)
    if not isinstance(template, str):
        raise TraceRenderError(f"missing locale key {locale}.{key}")
    expected = placeholder_names(template)
    if expected != frozenset(values):
        raise TraceRenderError(
            f"{locale}.{key}: expected placeholders {sorted(expected)}, supplied {sorted(values)}"
        )
    if any(not isinstance(value, (str, int, bool)) for value in values.values()):
        raise TraceRenderError(f"{locale}.{key}: only scalar substitutions are allowed")
    try:
        rendered = template.format_map({name: str(value) for name, value in values.items()})
    except (KeyError, ValueError) as error:
        raise TraceRenderError(f"{locale}.{key}: invalid placeholder formatting") from error
    if not rendered.strip():
        raise TraceRenderError(f"{locale}.{key}: message is empty")
    return rendered


def _inline(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise TraceRenderError(f"trace {field} must be text")
    # Public SafeText normally has no line breaks.  Treat an unexpected line
    # break as one visible space rather than letting it create a new heading or
    # list item in a trace.
    try:
        return escape_inline(value.replace("\r\n", " ").replace("\n", " "), field_name=field)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceRenderError(f"trace {field} is not safe inline text") from error


def _empty_label(view: TraceView, messages: Mapping[str, str], locale: str) -> str:
    notes = set(view.capability_notes)
    for note in (
        "trace.record.corrupt",
        "trace.record.partial",
        "trace.unavailable",
        "trace.not_recorded",
    ):
        if note in notes:
            return _lookup(messages, locale, note)
    return _lookup(messages, locale, "trace.none")


def _section_heading(messages: Mapping[str, str], locale: str, key: str) -> str:
    return _lookup(messages, locale, key)


def _render_framing(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:
    framing = view.framing
    if framing is None:
        return [f"- {_empty_label(view, messages, locale)}"]
    lines = [
        f"- {_lookup(messages, locale, 'trace.label.decision_question')}: "
        f"{_inline(framing.decision_question, field='decision_question')}",
    ]
    assumptions = "; ".join(_inline(item.text, field="assumption") for item in framing.assumptions)
    criteria = "; ".join(
        _inline(item.text, field="criterion") for item in framing.completion_criteria
    )
    lines.append(
        f"- {_lookup(messages, locale, 'trace.label.assumptions_published')}: "
        f"{assumptions or _lookup(messages, locale, 'trace.none')}"
    )
    lines.append(
        f"- {_lookup(messages, locale, 'trace.label.completion_criteria')}: "
        f"{criteria or _lookup(messages, locale, 'trace.none')}"
    )
    return lines


def _render_chronology(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:
    if not view.chronology:
        return [f"- {_empty_label(view, messages, locale)}"]
    lines: list[str] = []
    expected_keys = {"sequence", "occurred_at", "kind", "summary", "effect"}
    for item in view.chronology:
        if not isinstance(item, Mapping) or set(item) != expected_keys:
            raise TraceRenderError("trace chronology contains an unknown field")
        sequence = item["sequence"]
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
            raise TraceRenderError("trace chronology sequence is invalid")
        _inline(item["kind"], field="kind")
        occurred_at = _inline(item["occurred_at"], field="occurred_at")
        raw_summary = item["summary"]
        raw_effect = item["effect"]
        if raw_summary == "" and raw_effect == "":
            continue
        summary = (
            _lookup(messages, locale, "trace.none")
            if raw_summary == ""
            else _inline(raw_summary, field="summary")
        )
        effect = "" if raw_effect == "" else _inline(raw_effect, field="effect")
        line = f"- {sequence} — {occurred_at} — {summary}"
        if effect:
            line += f" — {effect}"
        lines.append(line)
    return lines or [f"- {_empty_label(view, messages, locale)}"]


def _render_methods(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    methods = view.methods
    if not isinstance(methods, Mapping):
        raise TraceRenderError("trace methods must be a mapping")
    expected = {
        "status",
        "activation_status",
        "primary_method",
        "complement_method",
        "selection_source",
        "confirmed_activations",
        "complement_cue",
    }
    if set(methods) != expected:
        raise TraceRenderError("trace methods contain an unknown field")
    status = methods["status"]
    activation_status = methods["activation_status"]
    if status in {"none", "unavailable", "not_recorded"}:
        label = {
            "none": "trace.none",
            "unavailable": "trace.unavailable",
            "not_recorded": "trace.not_recorded",
        }[str(status)]
        return [f"- {_lookup(messages, locale, label)}"]
    if status not in {"selected", "confirmed"}:
        raise TraceRenderError("trace methods have an invalid status")
    confirmed = methods["confirmed_activations"]
    if not isinstance(confirmed, (tuple, list)) or any(
        not isinstance(item, str) or not item for item in confirmed
    ):
        raise TraceRenderError("trace confirmed activations are invalid")
    primary = methods["primary_method"]
    secondary = methods["complement_method"]
    if not isinstance(primary, str) or not primary:
        raise TraceRenderError("selected trace method has no primary ID")
    lines = [
        f"- {_lookup(messages, locale, 'trace.primary')}: {_inline(primary, field='primary_method')}"
    ]
    if secondary is not None:
        if not isinstance(secondary, str) or not secondary:
            raise TraceRenderError("trace complement method is invalid")
        # This line is intentionally a cue only; the projection never places
        # the complement in confirmed_activations.
        lines.append(
            f"- {_lookup(messages, locale, 'trace.secondary')}: "
            f"{_inline(secondary, field='complement_method')}"
        )
        if secondary in confirmed:
            raise TraceRenderError("trace complement cannot be a confirmed activation")
    if methods["complement_cue"] != secondary:
        raise TraceRenderError("trace complement cue does not match the complement method")
    if activation_status == "confirmed":
        lines.append(f"- {_lookup(messages, locale, 'trace.method.activation_confirmed')}")
    elif activation_status == "unavailable":
        lines.append(f"- {_lookup(messages, locale, 'trace.unavailable')}")
    elif activation_status == "not_recorded":
        lines.append(f"- {_lookup(messages, locale, 'trace.method.selected_not_confirmed')}")
    else:
        raise TraceRenderError("trace method activation status is invalid")
    return lines


def _render_claims(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:
    if not view.claim_history:
        return [f"- {_empty_label(view, messages, locale)}"]
    lines: list[str] = []
    for claim in view.claim_history:
        text = _inline(claim.text, field="claim.text")
        state_key = f"card.state.{claim.evidence_state.value}"
        state = _lookup(messages, locale, state_key)
        line = f"- {text} — {state}"
        if claim.source_ids:
            sources = ", ".join(_inline(item, field="claim.source_id") for item in claim.source_ids)
            line += f" — {_lookup(messages, locale, 'trace.label.source')}: {sources}"
        lines.append(line)
    return lines


def _render_conflicts(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:
    if not view.conflicts:
        return [f"- {_empty_label(view, messages, locale)}"]
    lines: list[str] = []
    for conflict in view.conflicts:
        reason = conflict.resolution_reason or _lookup(messages, locale, "trace.none")
        lines.append(
            f"- {_inline(conflict.summary, field='conflict.summary')} — "
            f"{_lookup(messages, locale, 'trace.label.resolution')}: {_inline(reason, field='conflict.resolution_reason')}"
        )
    return lines


def _render_alternatives(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:
    if not view.alternatives:
        return [f"- {_empty_label(view, messages, locale)}"]
    return [
        f"- {_inline(item.name, field='alternative.name')} — {_inline(item.reason, field='alternative.reason')}"
        for item in view.alternatives
    ]


def _render_completion(view: TraceView, messages: Mapping[str, str], locale: str) -> list[str]:
    completion = view.completion
    if completion is None or not completion.criteria:
        return [f"- {_empty_label(view, messages, locale)}"]
    lines: list[str] = []
    for criterion in completion.criteria:
        try:
            status_key = _CRITERION_KEYS[criterion.status]
        except KeyError as error:
            raise TraceRenderError("completion criterion has an unknown status") from error
        lines.append(
            f"- {_inline(criterion.reason, field='completion.reason')} — "
            f"{_lookup(messages, locale, status_key)}"
        )
    return lines


def _render_card(
    card: ConclusionCard,
    renderer: CardRenderer | Callable[..., str],
    locale_catalog: object,
) -> str:
    if not isinstance(card, ConclusionCard):
        raise TraceRenderError("current conclusion is not a typed ConclusionCard")
    callable_renderer: Any = getattr(renderer, "render", renderer)
    if not callable(callable_renderer):
        raise TraceRenderError("trace card renderer is not callable")
    try:
        card_catalog: object = locale_catalog
        if isinstance(locale_catalog, LocaleCatalog):
            card_catalog = locale_catalog.locale_messages
        elif isinstance(locale_catalog, Mapping) and "locale_messages" in locale_catalog:
            card_catalog = locale_catalog["locale_messages"]
        rendered = callable_renderer(card, card_catalog, heading_level=3)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceRenderError("injected card renderer rejected the typed card") from error
    if not isinstance(rendered, str) or not rendered.strip():
        raise TraceRenderError("injected card renderer returned empty output")
    return rendered


def render_trace(
    view: TraceView,
    locale_catalog: LocaleCatalog | Mapping[str, object],
    *,
    card_renderer: CardRenderer | Callable[..., str],
    private_reasoning_requested: bool = False,
) -> str:
    """Render exactly the public nine-section trace structure."""

    if not isinstance(view, TraceView):
        raise TraceRenderError("trace renderer accepts TraceView only")
    try:
        validate_model(view)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise TraceRenderError("trace view is invalid") from error
    if not isinstance(private_reasoning_requested, bool):
        raise TraceRenderError("private_reasoning_requested must be boolean")
    locale = str(view.locale)
    try:
        messages = _messages(locale_catalog, locale)
    except (MessageCatalogError, KeyError, TypeError, ValueError) as error:
        raise TraceRenderError("trace locale catalog is incomplete") from error

    lines = [f"# {_section_heading(messages, locale, 'trace.title')} "]
    # The trailing space is removed below; keeping the title construction here
    # makes the section order visually obvious while preserving exact output.
    lines[0] = lines[0].rstrip()
    if private_reasoning_requested:
        lines.append(f"- {_lookup(messages, locale, 'trace.private_reasoning')}")
    lines.extend(
        (
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.framing')}",
            *_render_framing(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.what_changed')}",
            *_render_chronology(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.methods_used')}",
            *_render_methods(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.evidence_changes')}",
            *_render_claims(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.conflicts_and_responses')}",
            *_render_conflicts(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.alternatives')}",
            *_render_alternatives(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.completion_check')}",
            *_render_completion(view, messages, locale),
            "",
            f"## {_section_heading(messages, locale, 'trace.heading.current_conclusion')}",
        )
    )
    if view.current_card is None:
        lines.append(f"- {_empty_label(view, messages, locale)}")
    else:
        lines.append(_render_card(view.current_card, card_renderer, locale_catalog))
    return "\n".join(lines)


render = render_trace


__all__ = ["CardRenderer", "TRACE_LOCALE_KEYS", "TraceRenderError", "render", "render_trace"]
