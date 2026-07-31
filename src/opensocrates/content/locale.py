"""Locale catalog loading and build-time EN/KO parity checks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .schema import ContentValidationError

LOCALE_SCHEMA = "opensocrates.locale-catalog/1.0.0"
_PLACEHOLDER_RE = re.compile(r"\{([A-Za-z][A-Za-z0-9_.-]*)\}")


def flatten_messages(value: Mapping[str, Any], prefix: str = "") -> dict[str, str]:
    result: dict[str, str] = {}
    for key, item in value.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            result.update(flatten_messages(item, full_key))
        elif isinstance(item, str):
            result[full_key] = item
        else:
            raise ContentValidationError(f"locale.messages.{full_key}: expected a string")
    return result


def load_locale(value: Any, *, expected_locale: str | None = None) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ContentValidationError("locale: expected an object")
    if value.get("schema") != LOCALE_SCHEMA:
        raise ContentValidationError("locale.schema: unsupported schema")
    locale = value.get("locale")
    if locale not in {"en", "ko"} or (expected_locale is not None and locale != expected_locale):
        raise ContentValidationError("locale.locale: expected en or ko")
    messages = value.get("messages")
    if not isinstance(messages, Mapping):
        raise ContentValidationError("locale.messages: expected an object")
    flat = flatten_messages(messages)
    if not flat:
        raise ContentValidationError("locale.messages: cannot be empty")
    for key, text in flat.items():
        if len(text) > 4000:
            raise ContentValidationError(f"locale.messages.{key}: exceeds 4000 characters")
    return {"schema": LOCALE_SCHEMA, "locale": locale, "messages": flat}


def placeholders(text: str) -> frozenset[str]:
    return frozenset(_PLACEHOLDER_RE.findall(text))


def validate_locale_parity(en: Mapping[str, Any], ko: Mapping[str, Any]) -> None:
    en_messages = dict(en["messages"])
    ko_messages = dict(ko["messages"])
    if set(en_messages) != set(ko_messages):
        missing_en = sorted(set(ko_messages) - set(en_messages))
        missing_ko = sorted(set(en_messages) - set(ko_messages))
        raise ContentValidationError(
            f"locale parity: missing en={missing_en}, missing ko={missing_ko}"
        )
    mismatches = [
        key
        for key in en_messages
        if placeholders(en_messages[key]) != placeholders(ko_messages[key])
    ]
    if mismatches:
        raise ContentValidationError(
            f"locale parity: placeholder mismatch for {', '.join(sorted(mismatches))}"
        )


def prompt_fragments(en: Mapping[str, Any], ko: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    validate_locale_parity(en, ko)
    keys = {
        "controller": "prompt.controller",
        "participation_rigor": "prompt.participation_rigor",
        "routing_classifier": "prompt.routing_classifier",
        "framing": "prompt.framing",
        "evidence_card_completion": "prompt.evidence_card_completion",
        "cross_exam": "prompt.cross_exam",
        "strict_second_pass": "prompt.strict_second_pass",
        "capability_notice": "prompt.capability_notice",
    }
    result: dict[str, dict[str, str]] = {}
    for fragment, key in keys.items():
        if key not in en["messages"] or key not in ko["messages"]:
            raise ContentValidationError(f"locale: missing prompt fragment key {key}")
        result[fragment] = {"en": en["messages"][key], "ko": ko["messages"][key]}
    return result
