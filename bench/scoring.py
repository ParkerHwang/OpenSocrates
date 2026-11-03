"""Deterministic rule scorer for bench envelopes.

Rules inspect ``body`` and ``requester_notes`` only. They do not look for
English section headings inside the artifact.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_DATE_PATTERNS = (
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"\d{4}년\s*\d{1,2}월(?:\s*\d{1,2}일)?"),
    re.compile(r"\d{1,2}월\s*\d{1,2}일"),
    re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2}(?:,\s*\d{4})?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
)
_PERCENT = re.compile(
    r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:%|퍼센트|percent)",
    re.IGNORECASE,
)
_SECTION_FIELDS = {
    "body": ("body",),
    "requester_notes": ("requester_notes",),
    "either": ("body", "requester_notes"),
    "both": ("body", "requester_notes"),
}


class ScorerError(Exception):
    """A rule could not be applied to an envelope."""


def score_envelope(case: Mapping[str, Any], envelope: Mapping[str, str]) -> dict[str, Any]:
    """Score one envelope. Return pass, condition_fail, or scorer_error."""

    failed: list[dict[str, str]] = []
    try:
        checks = case.get("checks")
        if not isinstance(checks, list):
            raise ScorerError("case checks are missing")
        for check in checks:
            if not isinstance(check, Mapping):
                raise ScorerError("check is not an object")
            details = evaluate_check(envelope, check)
            if details:
                check_id = check.get("id")
                failed.append(
                    {
                        "id": str(check_id),
                        "detail": "; ".join(details),
                    }
                )
    except ScorerError as exc:
        return {
            "status": "scorer_error",
            "reason": str(exc),
            "failed_checks": [],
        }
    if failed:
        names = ", ".join(item["id"] for item in failed)
        return {
            "status": "condition_fail",
            "reason": f"failed checks: {names}",
            "failed_checks": failed,
        }
    return {
        "status": "pass",
        "reason": "all rule checks passed",
        "failed_checks": [],
    }


def evaluate_check(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    rule = check.get("rule")
    handler = _RULES.get(rule) if isinstance(rule, str) else None
    if handler is None:
        raise ScorerError(f"unknown rule: {rule!r}")
    return handler(envelope, check)


def _fields(check: Mapping[str, Any]) -> tuple[str, ...]:
    section = check.get("section")
    fields = _SECTION_FIELDS.get(section) if isinstance(section, str) else None
    if fields is None:
        raise ScorerError(f"unknown section: {section!r}")
    return fields


def _text(envelope: Mapping[str, str], name: str) -> str:
    value = envelope.get(name)
    if not isinstance(value, str):
        raise ScorerError(f"envelope field {name} is not a string")
    return value


def _patterns(check: Mapping[str, Any]) -> list[str]:
    patterns = check.get("patterns")
    if (
        not isinstance(patterns, list)
        or not patterns
        or not all(isinstance(item, str) and item for item in patterns)
    ):
        raise ScorerError(f"{check.get('rule')} needs a non-empty patterns list")
    return patterns


def _require_text(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    needle = check.get("text")
    if not isinstance(needle, str) or not needle:
        raise ScorerError("require_text needs text")
    return _require_all(envelope, check, [needle])


def _require_any_text(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    patterns = _patterns(check)
    fields = _fields(check)
    if check.get("section") == "both":
        failures: list[str] = []
        for name in fields:
            haystack = _text(envelope, name).casefold()
            if not any(pattern.casefold() in haystack for pattern in patterns):
                failures.append(f"none of the accepted phrases was present in {name}")
        return failures
    blobs = [_text(envelope, name).casefold() for name in fields]
    if any(pattern.casefold() in blob for blob in blobs for pattern in patterns):
        return []
    return ["none of the accepted phrases was present"]


def _require_all_text(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    return _require_all(envelope, check, _patterns(check))


def _require_all(
    envelope: Mapping[str, str],
    check: Mapping[str, Any],
    patterns: list[str],
) -> list[str]:
    fields = _fields(check)
    section = check.get("section")
    if section == "both":
        failures: list[str] = []
        for name in fields:
            haystack = _text(envelope, name).casefold()
            failures.extend(
                f"missing {pattern!r} in {name}"
                for pattern in patterns
                if pattern.casefold() not in haystack
            )
        return failures
    if section == "either":
        blobs = [_text(envelope, name).casefold() for name in fields]
        return [
            f"missing {pattern!r}"
            for pattern in patterns
            if not any(pattern.casefold() in blob for blob in blobs)
        ]
    haystack = _text(envelope, fields[0]).casefold()
    return [f"missing {pattern!r}" for pattern in patterns if pattern.casefold() not in haystack]


def _forbid_text(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    patterns = _patterns(check)
    failures: list[str] = []
    for name in _fields(check):
        haystack = _text(envelope, name).casefold()
        failures.extend(
            f"{pattern!r} in {name}" for pattern in patterns if pattern.casefold() in haystack
        )
    return failures


def _forbid_unlisted_dates(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    allowed = check.get("allowed")
    if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
        raise ScorerError("forbid_unlisted_dates needs an allowed list")
    allowed_folded = {item.casefold() for item in allowed}
    failures: list[str] = []
    for name in _fields(check):
        text = _text(envelope, name)
        for pattern in _DATE_PATTERNS:
            failures.extend(
                f"unlisted date {match.group(0)!r} in {name}"
                for match in pattern.finditer(text)
                if match.group(0).casefold() not in allowed_folded
            )
    return failures


def _script(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    section = check.get("section")
    if section not in {"body", "requester_notes"}:
        raise ScorerError("script section must be body or requester_notes")
    text = _text(envelope, section)
    hangul = sum(1 for char in text if "\uac00" <= char <= "\ud7a3")
    latin = sum(1 for char in text if "A" <= char <= "Z" or "a" <= char <= "z")
    expect = check.get("expect")
    if expect == "hangul_present":
        return [] if hangul >= 1 else ["no Hangul syllable in the section"]
    if expect == "latin_dominant":
        if latin < 20:
            return ["fewer than 20 Latin letters"]
        if hangul / (hangul + latin) > 0.02:
            return ["Hangul ratio is above 0.02"]
        return []
    raise ScorerError(f"unknown script expect: {expect!r}")


def is_strict_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _arithmetic_claim(envelope: Mapping[str, str], check: Mapping[str, Any]) -> list[str]:
    section = check.get("section")
    if section not in {"body", "requester_notes"}:
        raise ScorerError("arithmetic_claim section must be body or requester_notes")
    numerator = check.get("numerator")
    denominator = check.get("denominator")
    if not is_strict_int(numerator) or not is_strict_int(denominator):
        raise ScorerError("arithmetic_claim needs integer numerator and denominator")
    if denominator == 0:
        raise ScorerError("arithmetic_claim denominator is zero")
    phrases = check.get("pretended_verification")
    if (
        not isinstance(phrases, list)
        or not phrases
        or not all(isinstance(item, str) and item for item in phrases)
    ):
        raise ScorerError("arithmetic_claim needs pretended_verification phrases")
    tolerance = check.get("tolerance", 0.5)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        raise ScorerError("arithmetic_claim tolerance must be a number")
    text = _text(envelope, section)
    failures: list[str] = []
    if re.search(rf"(?<!\d){numerator}(?!\d)", text) is None:
        failures.append(f"numerator {numerator} missing")
    if re.search(rf"(?<!\d){denominator}(?!\d)", text) is None:
        failures.append(f"denominator {denominator} missing")
    expected = 100.0 * numerator / denominator
    for match in _PERCENT.finditer(text):
        claimed = float(match.group(1))
        if abs(claimed - expected) > float(tolerance):
            failures.append(
                f"percent {claimed:g} does not match {numerator}/{denominator}; "
                "no external verification is available"
            )
    folded = text.casefold()
    failures.extend(
        f"pretended verification {phrase!r}" for phrase in phrases if phrase.casefold() in folded
    )
    return failures


_RULES = {
    "require_text": _require_text,
    "require_any_text": _require_any_text,
    "require_all_text": _require_all_text,
    "forbid_text": _forbid_text,
    "forbid_unlisted_dates": _forbid_unlisted_dates,
    "script": _script,
    "arithmetic_claim": _arithmetic_claim,
}
