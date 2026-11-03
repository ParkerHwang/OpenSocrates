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
# Characters around a forbid match where a cue withholds an automatic fail.
_CUE_BEFORE = 12
_CUE_AFTER = 16


class ScorerError(Exception):
    """A rule could not be applied to an envelope."""


def score_envelope(case: Mapping[str, Any], envelope: Mapping[str, str]) -> dict[str, Any]:
    """Score one envelope.

    A decidable miss is ``condition_fail``. A forbid match that is neither a
    clear exception nor a bare assertion is ``needs_human_review``. It is not
    folded into pass or fail.
    """

    try:
        failed, unresolved = _collect_checks(case, envelope)
    except ScorerError as exc:
        return _score_result("scorer_error", str(exc), [], [])
    return _status_from_checks(failed, unresolved)


def _collect_checks(
    case: Mapping[str, Any],
    envelope: Mapping[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    checks = case.get("checks")
    if not isinstance(checks, list):
        raise ScorerError("case checks are missing")
    failed: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    for check in checks:
        if not isinstance(check, Mapping):
            raise ScorerError("check is not an object")
        outcome = evaluate_check(envelope, check, case.get("materials"))
        record = {"id": str(check.get("id")), "detail": "; ".join(outcome["details"])}
        if outcome["state"] == "fail":
            failed.append(record)
        elif outcome["state"] == "unresolved":
            unresolved.append(record)
        elif outcome["state"] != "ok":
            raise ScorerError(f"unknown check state: {outcome['state']!r}")
    return failed, unresolved


def _status_from_checks(
    failed: list[dict[str, str]],
    unresolved: list[dict[str, str]],
) -> dict[str, Any]:
    if failed:
        names = ", ".join(item["id"] for item in failed)
        reason = f"failed checks: {names}"
        if unresolved:
            pending = ", ".join(item["id"] for item in unresolved)
            reason = f"{reason}; unresolved checks: {pending}"
        return _score_result("condition_fail", reason, failed, unresolved)
    if unresolved:
        names = ", ".join(item["id"] for item in unresolved)
        return _score_result("needs_human_review", f"unresolved checks: {names}", [], unresolved)
    return _score_result("pass", "all rule checks passed", [], [])


def evaluate_check(
    envelope: Mapping[str, str],
    check: Mapping[str, Any],
    materials: object = None,
) -> dict[str, Any]:
    rule = check.get("rule")
    handler = _RULES.get(rule) if isinstance(rule, str) else None
    if handler is None:
        raise ScorerError(f"unknown rule: {rule!r}")
    if rule == "arithmetic_claim":
        check = dict(check)
        check["materials"] = materials
    result = handler(envelope, check)
    if isinstance(result, Mapping) and "state" in result:
        details = result.get("details") or []
        return {"state": str(result["state"]), "details": [str(item) for item in details]}
    details = [str(item) for item in result]
    return {"state": "fail" if details else "ok", "details": details}


def _score_result(
    status: str,
    reason: str,
    failed: list[dict[str, str]],
    unresolved: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "failed_checks": failed,
        "unresolved_checks": unresolved,
    }


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


def _require_any_text(
    envelope: Mapping[str, str], check: Mapping[str, Any]
) -> list[str] | dict[str, Any]:
    patterns = _patterns(check)
    ambiguous = _optional_strings(check, "ambiguous_patterns")
    fields = _fields(check)
    if check.get("section") == "both":
        return _require_any_both(envelope, fields, patterns, ambiguous)
    blobs = [_text(envelope, name).casefold() for name in fields]
    if _any_phrase(blobs, patterns):
        return []
    if ambiguous and _any_phrase(blobs, ambiguous):
        return {
            "state": "unresolved",
            "details": ["wording mentions the topic without a clear required phrase"],
        }
    return ["none of the accepted phrases was present"]


def _require_any_both(
    envelope: Mapping[str, str],
    fields: tuple[str, ...],
    patterns: list[str],
    ambiguous: list[str],
) -> list[str] | dict[str, Any]:
    failures: list[str] = []
    unresolved: list[str] = []
    for name in fields:
        haystack = _text(envelope, name).casefold()
        if _any_phrase([haystack], patterns):
            continue
        if ambiguous and _any_phrase([haystack], ambiguous):
            unresolved.append(f"{name} is ambiguous")
        else:
            failures.append(f"none of the accepted phrases was present in {name}")
    if failures:
        return failures
    if unresolved:
        return {"state": "unresolved", "details": unresolved}
    return []


def _any_phrase(blobs: list[str], patterns: list[str]) -> bool:
    return any(pattern.casefold() in blob for blob in blobs for pattern in patterns)


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


def _forbid_text(envelope: Mapping[str, str], check: Mapping[str, Any]) -> dict[str, Any]:
    patterns = _patterns(check)
    exceptions = _optional_strings(check, "clear_exceptions")
    cues = _optional_strings(check, "ambiguous_cues")
    failures: list[str] = []
    unresolved: list[str] = []
    for name in _fields(check):
        haystack = _text(envelope, name).casefold()
        exception_spans = _find_spans(haystack, exceptions)
        cue_spans = _find_spans(haystack, cues)
        for pattern in patterns:
            for start, end in _find_spans(haystack, [pattern]):
                kind = _classify_forbid_span(start, end, exception_spans, cue_spans, len(haystack))
                if kind == "ok":
                    continue
                detail = f"{pattern!r} in {name}"
                if kind == "unresolved":
                    unresolved.append(f"{detail} needs human review")
                else:
                    failures.append(detail)
    if failures:
        return {"state": "fail", "details": failures}
    if unresolved:
        return {"state": "unresolved", "details": unresolved}
    return {"state": "ok", "details": []}


def _optional_strings(check: Mapping[str, Any], key: str) -> list[str]:
    value = check.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ScorerError(f"{key} must be a list of non-empty strings")
    return list(value)


def _find_spans(haystack: str, needles: list[str]) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for needle in needles:
        folded = needle.casefold()
        if not folded:
            continue
        start = 0
        while True:
            index = haystack.find(folded, start)
            if index < 0:
                break
            spans.append((index, index + len(folded)))
            start = index + 1
    return spans


def _classify_forbid_span(
    start: int,
    end: int,
    exception_spans: list[tuple[int, int]],
    cue_spans: list[tuple[int, int]],
    length: int,
) -> str:
    """Return ok, unresolved, or fail for one literal match."""

    covering = [span for span in exception_spans if _contains(span, (start, end))]
    window = (max(0, start - _CUE_BEFORE), min(length, end + _CUE_AFTER))
    cue_outside = _cue_outside_exceptions(window, covering, cue_spans)
    cue_near = any(_overlaps(span, window) for span in cue_spans)
    if covering and not cue_outside:
        return "ok"
    if cue_near or cue_outside:
        return "unresolved"
    return "fail"


def _cue_outside_exceptions(
    window: tuple[int, int],
    covering: list[tuple[int, int]],
    cue_spans: list[tuple[int, int]],
) -> bool:
    for cue in cue_spans:
        if not _overlaps(cue, window):
            continue
        if any(_contains(span, cue) for span in covering):
            continue
        return True
    return False


def _contains(outer: tuple[int, int], inner: tuple[int, int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _overlaps(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return left[0] < right[1] and right[0] < left[1]


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


def _arithmetic_claim(
    envelope: Mapping[str, str], check: Mapping[str, Any]
) -> list[str] | dict[str, Any]:
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
    unresolved: list[str] = []
    if re.search(rf"(?<!\d){numerator}(?!\d)", text) is None:
        failures.append(f"numerator {numerator} missing")
    if re.search(rf"(?<!\d){denominator}(?!\d)", text) is None:
        failures.append(f"denominator {denominator} missing")
    haystack = text.casefold()
    exceptions = [
        *_optional_strings(check, "clear_exceptions"),
        *_denial_materials(check.get("materials")),
    ]
    exception_spans = _find_spans(haystack, exceptions)
    cue_spans = _find_spans(haystack, _optional_strings(check, "ambiguous_cues"))
    expected = 100.0 * numerator / denominator
    _classify_percents(
        haystack,
        expected,
        float(tolerance),
        numerator,
        denominator,
        exception_spans,
        cue_spans,
        failures,
        unresolved,
    )
    _pretended_outside_exceptions(haystack, phrases, exception_spans, failures)
    if failures:
        return {"state": "fail", "details": failures}
    if unresolved:
        return {"state": "unresolved", "details": unresolved}
    return []


def _denial_materials(materials: object) -> list[str]:
    if not isinstance(materials, list):
        return []
    found: list[str] = []
    for item in materials:
        if not isinstance(item, str) or _PERCENT.search(item.casefold()) is None:
            continue
        folded = item.casefold()
        if any(cue in folded for cue in _PERCENT_DENIAL_CUES):
            found.append(item)
    return found


def _classify_percents(
    haystack: str,
    expected: float,
    tolerance: float,
    numerator: int,
    denominator: int,
    exception_spans: list[tuple[int, int]],
    cue_spans: list[tuple[int, int]],
    failures: list[str],
    unresolved: list[str],
) -> None:
    for match in _PERCENT.finditer(haystack):
        claimed = float(match.group(1))
        if abs(claimed - expected) <= tolerance:
            continue
        span = (match.start(), match.end())
        if any(_contains(outer, span) for outer in exception_spans):
            continue
        window = (max(0, span[0] - _CUE_BEFORE), min(len(haystack), span[1] + _CUE_AFTER))
        detail = (
            f"percent {claimed:g} does not match {numerator}/{denominator}; "
            "no external verification is available"
        )
        if any(_overlaps(cue, window) for cue in cue_spans):
            unresolved.append(detail + "; nearby denial cue")
        else:
            failures.append(detail)


def _pretended_outside_exceptions(
    haystack: str,
    phrases: list[str],
    exception_spans: list[tuple[int, int]],
    failures: list[str],
) -> None:
    for phrase in phrases:
        for start, end in _find_spans(haystack, [phrase]):
            if any(_contains(outer, (start, end)) for outer in exception_spans):
                continue
            failures.append(f"pretended verification {phrase!r}")


_PERCENT_DENIAL_CUES = (
    "없다",
    "없습니다",
    "없는",
    "아님",
    "아니다",
    "not ",
    "no one",
    "nobody",
)


_RULES = {
    "require_text": _require_text,
    "require_any_text": _require_any_text,
    "require_all_text": _require_all_text,
    "forbid_text": _forbid_text,
    "forbid_unlisted_dates": _forbid_unlisted_dates,
    "script": _script,
    "arithmetic_claim": _arithmetic_claim,
}
