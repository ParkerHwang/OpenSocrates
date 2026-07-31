"""Localized, bounded rendering for one completion repair instruction.

The repair surface is deliberately smaller than the card surface.  All prose
comes from the supplied compiled locale catalog; this module never embeds an
English/Korean fallback and never serializes an exception, private value, or
raw user content.  Violation fields are only used as bounded structural
locations inside the catalog-authored group template.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from ..domain.models import Violation

MAX_REPAIR_BYTES = 2 * 1024
REPAIR_LOCALE_KEYS: tuple[str, ...] = (
    "repair.title",
    "repair.group",
    "repair.footer",
    "repair.area.card",
    "repair.area.source",
    "repair.area.evidence",
    "repair.area.calculation",
    "repair.area.conflict",
    "repair.area.completion",
    "repair.area.privacy",
    "repair.area.vocab",
    "repair.area.locale",
    "repair.area.capability",
)

_AREA_KEYS = {
    "CARD": "repair.area.card",
    "SOURCE": "repair.area.source",
    "CALC": "repair.area.calculation",
    "EVIDENCE": "repair.area.evidence",
    "STRENGTH": "repair.area.evidence",
    "CONFLICT": "repair.area.conflict",
    "COMPLETION": "repair.area.completion",
    "PRIVACY": "repair.area.privacy",
    "VOCAB": "repair.area.vocab",
    "LOCALE": "repair.area.locale",
    "CAPABILITY": "repair.area.capability",
}
_FIELD_RE = re.compile(r"^[A-Za-z0-9_./\[\]-]{1,128}$")
_FIELD_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_PUBLIC_ID_RE = re.compile(r"^[A-Z][0-9]{6}$")
_SAFE_FIELD_TOKENS = frozenset(
    {
        "active",
        "affected_conclusion",
        "alternatives",
        "alternatives_summary",
        "answer_shape",
        "basis_claim_ids",
        "candidate",
        "capability_profile",
        "card",
        "card_rules",
        "calculation",
        "calculation_rules",
        "calculation_summary",
        "claims",
        "claim_history",
        "claim_id",
        "completion_criteria",
        "completion_result",
        "condition",
        "conflict",
        "conflicts",
        "conclusion",
        "current_judgment",
        "current_projection",
        "current_state",
        "display_name",
        "evidence_rules",
        "evidence_state",
        "field",
        "flip_conditions",
        "grounds",
        "judgment_id",
        "judgment_version",
        "last_assistant_message",
        "locale",
        "materiality",
        "parser",
        "repair_count",
        "required",
        "safe_locator",
        "source",
        "source_id",
        "source_ids",
        "source_rules",
        "source_refs",
        "sources",
        "state",
        "status",
        "strength",
        "task_id",
        "task_projection",
        "text",
        "turn_state",
        "uncertainties",
        "uri",
        "version",
        "content_hash",
    }
)


class RepairRenderError(ValueError):
    """Raised when a complete localized repair instruction cannot be rendered."""


def _area(rule_id: str) -> str:
    parts = rule_id.split("-")
    if len(parts) < 3 or parts[0] != "OSV":
        raise RepairRenderError("repair violation area is unavailable")
    value = parts[1].upper()
    if value not in _AREA_KEYS:
        raise RepairRenderError("repair violation area is unsupported")
    return value


def _message_map(catalog: Any, locale: str) -> Mapping[str, str] | None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Extract one locale's messages from supported compiled-catalog shapes."""

    if not isinstance(locale, str) or locale not in {"en", "ko"}:
        raise RepairRenderError("repair locale is unsupported")
    if isinstance(catalog, Mapping):
        if "locale_messages" in catalog and isinstance(catalog["locale_messages"], Mapping):
            nested = catalog["locale_messages"]
            value = nested.get(locale)
            if isinstance(value, Mapping):
                return value
        if "messages" in catalog:
            declared = catalog.get("locale")
            if declared is not None and declared != locale:
                raise RepairRenderError("repair catalog locale does not match")
            value = catalog.get("messages")
            if isinstance(value, Mapping):
                return value
        value = catalog.get(locale)
        if isinstance(value, Mapping):
            return value
        # A flat map is accepted only when it explicitly contains the repair
        # keys.  It is already a caller-selected locale projection.
        if any(key in catalog for key in REPAIR_LOCALE_KEYS):
            return catalog  # type: ignore[return-value, unused-ignore]  # Closed runtime boundary validates this value.
    candidate = getattr(catalog, "locale_messages", None)
    if isinstance(candidate, Mapping):
        value = candidate.get(locale)
        if isinstance(value, Mapping):
            return value
    return None


def _lookup(catalog: Any, locale: str, key: str, **values: object) -> str:
    """Lookup and format one catalog key without exposing catalog exceptions."""

    lookup = getattr(catalog, "lookup", None)
    if callable(lookup):
        try:
            value = lookup(locale, key, **values)
        except Exception as exc:  # catalog implementations are external ports
            raise RepairRenderError("repair locale key is unavailable") from exc
        if not isinstance(value, str) or not value.strip():
            raise RepairRenderError("repair locale message is empty")
        return value
    messages = _message_map(catalog, locale)
    if messages is None or key not in messages or not isinstance(messages[key], str):
        raise RepairRenderError("repair locale key is unavailable")
    template = messages[key]
    # Match the strict placeholder behavior of LocaleCatalog without importing
    # the rendering catalog (which would make the boundary less reusable).
    names = set(re.findall(r"\{([A-Za-z][A-Za-z0-9_.-]*)\}", template))
    if names != set(values):
        raise RepairRenderError("repair locale placeholders do not match")
    try:
        rendered = template.format_map({name: str(value) for name, value in values.items()})
    except (KeyError, ValueError) as exc:
        raise RepairRenderError("repair locale formatting failed") from exc
    if not rendered.strip():
        raise RepairRenderError("repair locale message is empty")
    return rendered


def _safe_field(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    if _FIELD_RE.fullmatch(text) is None:
        return ""
    tokens = tuple(token for token in re.split(r"[./\[\]]+", text) if token)
    if not tokens:
        return ""
    for token in tokens:
        if token.isdigit() or _PUBLIC_ID_RE.fullmatch(token):
            continue
        if _FIELD_TOKEN_RE.fullmatch(token) is None or token not in _SAFE_FIELD_TOKENS:
            return ""
    return text[:128]


def _violation_key(item: Violation) -> tuple[str, str, str]:
    return (str(item.rule_id), str(item.field or ""), str(item.message_key))


def render_repair_instruction(
    violations: Sequence[Violation] | Any,
    locale_catalog: Any,
    locale: str = "en",
    *,
    max_bytes: int = MAX_REPAIR_BYTES,
) -> str:
    """Render stable grouped repair locations using only catalog-authored prose.

    ``violations`` may contain only typed :class:`Violation` values.  The
    structural field names are bounded and treated as injected locations, not
    as prose or exception details.  Missing catalog keys fail closed.
    """

    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
        raise RepairRenderError("repair byte limit is invalid")
    items = tuple(violations or ())
    if any(not isinstance(item, Violation) for item in items):
        raise RepairRenderError("repair violations are not typed")
    if not items:
        raise RepairRenderError("repair requires at least one violation")

    # Stable grouping is by closed OSV area, then by rule and field.  Duplicate
    # reports from parser/evidence adapters collapse to one visible location.
    grouped: dict[str, set[str]] = defaultdict(set)
    for item in sorted(items, key=_violation_key):
        area = _area(str(item.rule_id))
        field = _safe_field(item.field)
        if field:
            grouped[area].add(field)

    title = _lookup(locale_catalog, locale, "repair.title")
    footer = _lookup(locale_catalog, locale, "repair.footer")
    lines = [title]
    for area in sorted(grouped, key=lambda value: _AREA_KEYS[value]):
        label = _lookup(locale_catalog, locale, _AREA_KEYS[area])
        details = ", ".join(sorted(grouped[area]))
        lines.append(_lookup(locale_catalog, locale, "repair.group", area=label, details=details))
    lines.append(footer)
    rendered = "\n".join(lines).strip()
    if len(rendered.encode("utf-8")) > max_bytes:
        raise RepairRenderError("repair instruction exceeds the bounded byte limit")
    return rendered


render_repair = render_repair_instruction
render_completion_repair = render_repair_instruction


__all__ = [
    "MAX_REPAIR_BYTES",
    "REPAIR_LOCALE_KEYS",
    "RepairRenderError",
    "render_completion_repair",
    "render_repair",
    "render_repair_instruction",
]
