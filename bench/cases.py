"""Load and validate public synthetic bench cases and fixture envelopes."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from bench.contract import (
    CASE_SCHEMA,
    ENVELOPE_SCHEMA,
    FIXED_ENGLISH_HEADERS,
    FIXTURE_SCHEMA,
    REGRESSION_SCHEMA,
)
from bench.scoring import is_strict_int

_CASE_KEYS = {
    "schema",
    "id",
    "title",
    "inspired_by",
    "tags",
    "public_synthetic",
    "prompt",
    "materials",
    "checks",
    "arithmetic_policy",
}
_FIXTURE_KEYS = {
    "schema",
    "case_id",
    "condition",
    "origin",
    "model_called",
    "illustrates",
    "envelope",
}
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RULES = {
    "require_text",
    "require_any_text",
    "require_all_text",
    "forbid_text",
    "forbid_unlisted_dates",
    "script",
    "arithmetic_claim",
}


def forced_headers(text: str) -> list[str]:
    folded = text.casefold()
    return [header for header in FIXED_ENGLISH_HEADERS if header.casefold() in folded]


def load_case_files(root: Path) -> list[dict[str, Any]]:
    """Return one record per case file, with either a case or input errors."""

    directory = root / "bench" / "cases"
    paths = sorted(directory.glob("*.json")) if directory.is_dir() else []
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not paths:
        records.append(_input_error("(cases)", "no case files in bench/cases"))
        return records
    for path in paths:
        document, errors = _read_json(path)
        source = path.relative_to(root).as_posix()
        if errors:
            records.append(_input_error(source, "; ".join(errors)))
            continue
        case_errors = validate_case(document, source)
        case_id = document.get("id") if isinstance(document, Mapping) else None
        if isinstance(case_id, str) and case_id in seen:
            case_errors.append(f"duplicate case id {case_id}")
        if isinstance(case_id, str):
            seen.add(case_id)
        if case_errors:
            records.append(_input_error(source, "; ".join(case_errors), case_id=case_id))
            continue
        records.append({"source": source, "case": document, "errors": []})
    return records


def validate_case(document: object, source: str) -> list[str]:
    if not isinstance(document, Mapping):
        return [f"{source}: case is not a JSON object"]
    errors = _unknown_keys(document, _CASE_KEYS, source)
    if document.get("schema") != CASE_SCHEMA:
        errors.append(f"{source}: schema must be {CASE_SCHEMA}")
    case_id = document.get("id")
    if not isinstance(case_id, str) or _ID.fullmatch(case_id) is None:
        errors.append(f"{source}: id must be lowercase words separated by hyphens")
    elif not source.endswith(f"/{case_id}.json") and source != f"{case_id}.json":
        errors.append(f"{source}: file name must be {case_id}.json")
    errors.extend(_require_text_field(document, "title", source))
    errors.extend(_require_text_field(document, "prompt", source))
    errors.extend(_string_list(document.get("inspired_by"), f"{source}: inspired_by"))
    errors.extend(_string_list(document.get("tags"), f"{source}: tags"))
    if document.get("public_synthetic") is not True:
        errors.append(f"{source}: public_synthetic must be true")
    errors.extend(_string_list(document.get("materials"), f"{source}: materials"))
    errors.extend(_validate_checks(document.get("checks"), source))
    errors.extend(_validate_policy(document.get("arithmetic_policy"), source))
    prose = "\n".join(
        [
            str(document.get("prompt") or ""),
            *_strings(document.get("materials")),
        ]
    )
    headers = forced_headers(prose)
    if headers:
        errors.append(
            f"{source}: prompt and materials must not require fixed headings {headers}; "
            "the harness envelope labels body and requester_notes"
        )
    return errors


def load_fixture(
    path: Path,
    *,
    root: Path,
    case_id: str,
    condition: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    document, errors = _read_json(path)
    source = path.relative_to(root).as_posix()
    if errors:
        return None, [f"{source}: {item}" for item in errors]
    if not isinstance(document, Mapping):
        return None, [f"{source}: fixture is not a JSON object"]
    errors = _unknown_keys(document, _FIXTURE_KEYS, source)
    if document.get("schema") != FIXTURE_SCHEMA:
        errors.append(f"{source}: schema must be {FIXTURE_SCHEMA}")
    if document.get("case_id") != case_id:
        errors.append(f"{source}: case_id must be {case_id}")
    if document.get("condition") != condition:
        errors.append(f"{source}: condition must be {condition}")
    origin = document.get("origin")
    called = document.get("model_called")
    errors.extend(_fixture_origin(source, origin, called))
    illustrates = document.get("illustrates")
    if not isinstance(illustrates, str) or not illustrates.strip():
        errors.append(f"{source}: illustrates must explain the fixture")
    envelope, envelope_errors = _validate_envelope(document.get("envelope"), source)
    errors.extend(envelope_errors)
    if errors:
        return None, errors
    return {
        "source": source,
        "origin": origin,
        "model_called": called,
        "illustrates": illustrates.strip(),
        "envelope": envelope,
    }, []


def _fixture_origin(source: str, origin: object, called: object) -> list[str]:
    errors: list[str] = []
    if origin not in {"authored_example", "recorded_model_output"}:
        errors.append(f"{source}: origin is not recognized")
    if called is not False:
        errors.append(
            f"{source}: model_called must be false; a fixture file cannot verify a model call"
        )
    return errors


def expected_fixture_path(root: Path, case_id: str, condition: str) -> Path:
    return root / "bench" / "fixtures" / case_id / f"{condition}.json"


def load_regression_files(root: Path) -> list[dict[str, Any]]:
    """Load post-hoc regression envelopes. They are not condition-slot fixtures."""

    directory = root / "bench" / "regressions"
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in directory.rglob("*.json") if item.is_file()):
        rows.append(_read_regression(path, root))
    return rows


def unexpected_fixture_paths(root: Path, expected: set[Path]) -> list[Path]:
    directory = root / "bench" / "fixtures"
    if not directory.is_dir():
        return []
    found = {path.resolve() for path in directory.rglob("*.json") if path.is_file()}
    return sorted(found - {path.resolve() for path in expected})


def _read_regression(path: Path, root: Path) -> dict[str, Any]:
    source = path.relative_to(root).as_posix()
    document, errors = _read_json(path)
    if errors:
        return {"source": source, "errors": [f"{source}: {item}" for item in errors]}
    if not isinstance(document, Mapping):
        return {"source": source, "errors": [f"{source}: regression is not an object"]}
    allowed = {"schema", "case_id", "label", "framing", "expected_status", "envelope"}
    errors = _unknown_keys(document, allowed, source)
    if document.get("schema") != REGRESSION_SCHEMA:
        errors.append(f"{source}: schema must be {REGRESSION_SCHEMA}")
    case_id = document.get("case_id")
    label = document.get("label")
    framing = document.get("framing")
    expected = document.get("expected_status")
    if not isinstance(case_id, str) or _ID.fullmatch(case_id) is None:
        errors.append(f"{source}: case_id is invalid")
    if not isinstance(label, str) or _ID.fullmatch(label) is None:
        errors.append(f"{source}: label is invalid")
    if not isinstance(framing, str) or not _post_hoc_framing(framing):
        errors.append(f"{source}: framing must call this a post-hoc example and not a holdout")
    if expected not in {"pass", "condition_fail", "needs_human_review"}:
        errors.append(f"{source}: expected_status is not a scored outcome")
    envelope, envelope_errors = _validate_envelope(document.get("envelope"), source)
    errors.extend(envelope_errors)
    if errors or envelope is None:
        return {"source": source, "errors": errors}
    return {
        "source": source,
        "errors": [],
        "case_id": case_id,
        "label": label,
        "framing": framing.strip(),
        "expected_status": expected,
        "envelope": envelope,
    }


def _post_hoc_framing(value: str) -> bool:
    folded = value.casefold()
    return "post-hoc" in folded and "not an independent holdout" in folded


def _validate_envelope(value: object, source: str) -> tuple[dict[str, str] | None, list[str]]:
    if not isinstance(value, Mapping):
        return None, [f"{source}: envelope must be an object"]
    errors: list[str] = []
    if set(value) != {"schema", "body", "requester_notes"}:
        errors.append(f"{source}: envelope keys must be schema, body, requester_notes")
    if value.get("schema") != ENVELOPE_SCHEMA:
        errors.append(f"{source}: envelope schema must be {ENVELOPE_SCHEMA}")
    body = value.get("body")
    notes = value.get("requester_notes")
    if not isinstance(body, str):
        errors.append(f"{source}: envelope body must be a string")
    if not isinstance(notes, str):
        errors.append(f"{source}: envelope requester_notes must be a string")
    if errors or not isinstance(body, str) or not isinstance(notes, str):
        return None, errors
    return {"body": body, "requester_notes": notes}, []


def _validate_checks(value: object, source: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{source}: checks must be a non-empty list"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, check in enumerate(value):
        label = f"{source}: checks[{index}]"
        if not isinstance(check, Mapping):
            errors.append(f"{label} must be an object")
            continue
        check_id = check.get("id")
        if not isinstance(check_id, str) or _ID.fullmatch(check_id) is None:
            errors.append(f"{label} id is invalid")
        elif check_id in seen:
            errors.append(f"{label} duplicate id {check_id}")
        else:
            seen.add(check_id)
        rule = check.get("rule")
        if rule not in _RULES:
            errors.append(f"{label} rule is not supported")
            continue
        errors.extend(_validate_rule_shape(check, label))
    return errors


def _validate_rule_shape(check: Mapping[str, Any], label: str) -> list[str]:
    rule = check["rule"]
    section = check.get("section")
    errors: list[str] = []
    if rule == "require_text":
        errors.extend(_require_text_shape(check, section, label))
    elif rule == "require_any_text":
        errors.extend(_require_any_shape(check, section, label))
    elif rule == "require_all_text":
        errors.extend(_section(section, label, allow_combined=True))
        errors.extend(_pattern_list(check.get("patterns"), label))
    elif rule == "forbid_text":
        errors.extend(_section(section, label, allow_combined=True))
        errors.extend(_pattern_list(check.get("patterns"), label))
        errors.extend(_optional_string_list(check, "clear_exceptions", label))
        errors.extend(_optional_string_list(check, "ambiguous_cues", label))
    elif rule == "forbid_unlisted_dates":
        errors.extend(_section(section, label, allow_combined=True))
        allowed = check.get("allowed")
        if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
            errors.append(f"{label} allowed must be a list of strings")
    elif rule == "script":
        errors.extend(_section(section, label, allow_combined=False))
        if check.get("expect") not in {"latin_dominant", "hangul_present"}:
            errors.append(f"{label} expect must be latin_dominant or hangul_present")
    elif rule == "arithmetic_claim":
        errors.extend(_section(section, label, allow_combined=False))
        errors.extend(_arithmetic_shape(check, label))
    return errors


def _require_text_shape(check: Mapping[str, Any], section: object, label: str) -> list[str]:
    errors = _section(section, label, allow_combined=True)
    if not isinstance(check.get("text"), str) or not check.get("text"):
        errors.append(f"{label} text must be a non-empty string")
    return errors


def _require_any_shape(check: Mapping[str, Any], section: object, label: str) -> list[str]:
    errors = _section(section, label, allow_combined=True)
    errors.extend(_pattern_list(check.get("patterns"), label))
    errors.extend(_optional_string_list(check, "ambiguous_patterns", label))
    return errors


def _arithmetic_shape(check: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    numerator = check.get("numerator")
    denominator = check.get("denominator")
    if not is_strict_int(numerator) or not is_strict_int(denominator):
        errors.append(f"{label} numerator and denominator must be integers")
    elif denominator == 0:
        errors.append(f"{label} denominator must not be zero")
    phrases = check.get("pretended_verification")
    if (
        not isinstance(phrases, list)
        or not phrases
        or not all(isinstance(item, str) and item for item in phrases)
    ):
        errors.append(f"{label} pretended_verification must be a non-empty string list")
    tolerance = check.get("tolerance", 0.5)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
        errors.append(f"{label} tolerance must be a number")
    if check.get("policy") not in {None, "model_may_calculate"}:
        errors.append(f"{label} policy must be model_may_calculate when set")
    return errors


def _validate_policy(value: object, source: str) -> list[str]:
    if value is None:
        return []
    label = f"{source}: arithmetic_policy"
    if not isinstance(value, Mapping):
        return [f"{label} must be an object"]
    errors = _unknown_keys(
        value,
        {"model_may_calculate", "external_tools", "pretended_verification"},
        label,
    )
    if value.get("model_may_calculate") is not True:
        errors.append(f"{label} model_may_calculate must be true")
    tools = value.get("external_tools")
    if not isinstance(tools, str) or not tools.strip():
        errors.append(f"{label} external_tools must describe the available tools")
    if value.get("pretended_verification") != "fail":
        errors.append(f"{label} pretended_verification must be fail")
    return errors


def _section(value: object, label: str, *, allow_combined: bool) -> list[str]:
    allowed = {"body", "requester_notes"}
    if allow_combined:
        allowed |= {"either", "both"}
    if value not in allowed:
        return [f"{label} section must be one of {', '.join(sorted(allowed))}"]
    return []


def _optional_string_list(check: Mapping[str, Any], key: str, label: str) -> list[str]:
    if key not in check or check.get(key) is None:
        return []
    value = check.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        return [f"{label} {key} must be a list of non-empty strings"]
    return []


def _pattern_list(value: object, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        return [f"{label} patterns must be a non-empty string list"]
    return []


def _require_text_field(document: Mapping[str, Any], key: str, source: str) -> list[str]:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        return [f"{source}: {key} must be a non-empty string"]
    return []


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{label} must be a non-empty list of strings"]
    if not all(isinstance(item, str) and item.strip() for item in value):
        return [f"{label} must contain non-empty strings"]
    return []


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _unknown_keys(document: Mapping[str, Any], allowed: set[str], source: str) -> list[str]:
    extra = sorted(set(document) - allowed)
    if extra:
        return [f"{source}: unknown keys {', '.join(extra)}"]
    return []


def _read_json(path: Path) -> tuple[object, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [str(exc)]


def _input_error(source: str, reason: str, case_id: object = None) -> dict[str, Any]:
    return {
        "source": source,
        "case": None,
        "errors": [reason],
        "case_id": case_id if isinstance(case_id, str) else None,
    }
