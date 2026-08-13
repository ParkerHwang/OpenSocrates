#!/usr/bin/env python3
"""Small strict Draft 2020-12 validator for repository-owned schemas.

The adjudication gate must run in a clean clone without ambient packages. This
module implements every assertion keyword used by the checked schemas and
rejects schemas containing an unsupported assertion keyword. Format validation
is opt-in in JSON Schema; this implementation always asserts RFC 3339
``date-time`` when the schema requests it.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"

_ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "title", "description", "default"})
_ASSERTION_KEYWORDS = frozenset(
    {
        "type",
        "const",
        "enum",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
    }
)
_KNOWN_KEYWORDS = _ANNOTATION_KEYWORDS | _ASSERTION_KEYWORDS
_JSON_TYPES = frozenset({"null", "boolean", "object", "array", "number", "integer", "string"})
_DATE_TIME = re.compile(
    r"^(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})"
    r"[Tt](?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.[0-9]+)?(?:[Zz]|(?P<sign>[+-])(?P<offset_hour>[0-9]{2}):"
    r"(?P<offset_minute>[0-9]{2}))$"
)


@dataclass(frozen=True)
class ValidationIssue:
    """One schema or instance validation issue."""

    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _json_fingerprint(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError):
        return f"<non-json:{type(value).__name__}:{value!r}>"


def _json_equal(left: Any, right: Any) -> bool:
    return _json_fingerprint(left) == _json_fingerprint(right)


def _is_type(instance: Any, expected: str) -> bool:
    if expected == "null":
        return instance is None
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and math.isfinite(instance)
        )
    raise AssertionError(f"unknown JSON type {expected}")


def _valid_date_time(value: str) -> bool:
    match = _DATE_TIME.fullmatch(value)
    if match is None:
        return False
    values = {key: int(raw) for key, raw in match.groupdict().items() if raw and key != "sign"}
    try:
        date(values["year"], values["month"], values["day"])
    except ValueError:
        return False
    hour = values["hour"]
    minute = values["minute"]
    second = values["second"]
    if hour > 23 or minute > 59 or second > 60:
        return False
    # RFC 3339 permits a leap second only at the end of a UTC day. Historical
    # adjudication timestamps do not use leap seconds, but accepting the legal
    # representation keeps the format implementation standards-correct.
    if second == 60 and (hour, minute) != (23, 59):
        return False
    if match.group("offset_hour") is not None:
        if values["offset_hour"] > 23 or values["offset_minute"] > 59:
            return False
    return True


def check_schema(schema: Any) -> list[ValidationIssue]:  # noqa: C901
    """Check the repository schema and reject unsupported assertion keywords."""

    issues: list[ValidationIssue] = []
    if not isinstance(schema, dict):
        return [ValidationIssue("$", "schema must be an object")]
    if schema.get("$schema") != DRAFT_2020_12:
        issues.append(ValidationIssue("$.$schema", f"must equal {DRAFT_2020_12!r}"))

    def visit(node: Any, path: str) -> None:  # noqa: C901
        if not isinstance(node, dict):
            issues.append(ValidationIssue(path, "subschema must be an object"))
            return
        unknown = sorted(set(node) - _KNOWN_KEYWORDS)
        for keyword in unknown:
            issues.append(ValidationIssue(path, f"unsupported schema keyword {keyword!r}"))

        raw_types = node.get("type")
        if raw_types is not None:
            types = raw_types if isinstance(raw_types, list) else [raw_types]
            if not types or any(
                not isinstance(value, str) or value not in _JSON_TYPES for value in types
            ):
                issues.append(ValidationIssue(f"{path}.type", "contains an invalid JSON type"))
            if len(types) != len(set(types)):
                issues.append(ValidationIssue(f"{path}.type", "contains duplicate types"))

        required = node.get("required")
        if required is not None and (
            not isinstance(required, list)
            or any(not isinstance(value, str) for value in required)
            or len(required) != len(set(required))
        ):
            issues.append(ValidationIssue(f"{path}.required", "must be unique strings"))

        properties = node.get("properties")
        if properties is not None:
            if not isinstance(properties, dict):
                issues.append(ValidationIssue(f"{path}.properties", "must be an object"))
            else:
                for key, child in properties.items():
                    visit(child, f"{path}.properties.{key}")

        additional = node.get("additionalProperties")
        if additional is not None and not isinstance(additional, (bool, dict)):
            issues.append(
                ValidationIssue(f"{path}.additionalProperties", "must be boolean or schema")
            )
        elif isinstance(additional, dict):
            visit(additional, f"{path}.additionalProperties")

        items = node.get("items")
        if items is not None:
            visit(items, f"{path}.items")

        unique_items = node.get("uniqueItems")
        if unique_items is not None and not isinstance(unique_items, bool):
            issues.append(ValidationIssue(f"{path}.uniqueItems", "must be boolean"))

        enum = node.get("enum")
        if enum is not None and (
            not isinstance(enum, list)
            or not enum
            or len({_json_fingerprint(value) for value in enum}) != len(enum)
        ):
            issues.append(ValidationIssue(f"{path}.enum", "must be a non-empty unique array"))

        for keyword in ("minItems", "maxItems", "minLength", "maxLength"):
            value = node.get(keyword)
            if value is not None and (
                not isinstance(value, int) or isinstance(value, bool) or value < 0
            ):
                issues.append(
                    ValidationIssue(f"{path}.{keyword}", "must be a non-negative integer")
                )

        if (
            isinstance(node.get("minItems"), int)
            and isinstance(node.get("maxItems"), int)
            and node["minItems"] > node["maxItems"]
        ):
            issues.append(ValidationIssue(path, "minItems exceeds maxItems"))
        if (
            isinstance(node.get("minLength"), int)
            and isinstance(node.get("maxLength"), int)
            and node["minLength"] > node["maxLength"]
        ):
            issues.append(ValidationIssue(path, "minLength exceeds maxLength"))

        pattern = node.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                issues.append(ValidationIssue(f"{path}.pattern", "must be a string"))
            else:
                try:
                    re.compile(pattern)
                except re.error as exc:
                    issues.append(ValidationIssue(f"{path}.pattern", f"invalid regex: {exc}"))

        format_name = node.get("format")
        if format_name is not None and format_name != "date-time":
            issues.append(
                ValidationIssue(f"{path}.format", f"unsupported asserted format {format_name!r}")
            )

        for keyword in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"):
            value = node.get(keyword)
            if value is not None and not _is_type(value, "number"):
                issues.append(ValidationIssue(f"{path}.{keyword}", "must be a finite number"))

    visit(schema, "$")
    return issues


def validate(instance: Any, schema: dict[str, Any]) -> list[ValidationIssue]:  # noqa: C901
    """Validate an instance with the supported Draft 2020-12 assertions."""

    issues: list[ValidationIssue] = []

    def walk(value: Any, node: dict[str, Any], path: str) -> None:  # noqa: C901
        raw_types = node.get("type")
        if raw_types is not None:
            types = raw_types if isinstance(raw_types, list) else [raw_types]
            if not any(_is_type(value, expected) for expected in types):
                issues.append(
                    ValidationIssue(
                        path, f"expected type {raw_types!r}, got {type(value).__name__}"
                    )
                )
                return

        if "const" in node and not _json_equal(value, node["const"]):
            issues.append(ValidationIssue(path, f"must equal const {node['const']!r}"))
        if "enum" in node and not any(_json_equal(value, candidate) for candidate in node["enum"]):
            issues.append(ValidationIssue(path, f"is not one of {node['enum']!r}"))

        if isinstance(value, dict):
            required = node.get("required", [])
            for key in required:
                if key not in value:
                    issues.append(ValidationIssue(path, f"missing required property {key!r}"))
            properties = node.get("properties", {})
            for key, child in properties.items():
                if key in value:
                    walk(value[key], child, f"{path}.{key}")
            extras = sorted(set(value) - set(properties))
            additional = node.get("additionalProperties", True)
            if additional is False:
                for key in extras:
                    issues.append(
                        ValidationIssue(path, f"additional property {key!r} is forbidden")
                    )
            elif isinstance(additional, dict):
                for key in extras:
                    walk(value[key], additional, f"{path}.{key}")

        if isinstance(value, list):
            minimum = node.get("minItems")
            maximum = node.get("maxItems")
            if minimum is not None and len(value) < minimum:
                issues.append(
                    ValidationIssue(path, f"has {len(value)} items; minimum is {minimum}")
                )
            if maximum is not None and len(value) > maximum:
                issues.append(
                    ValidationIssue(path, f"has {len(value)} items; maximum is {maximum}")
                )
            if node.get("uniqueItems") is True:
                seen: set[str] = set()
                for index, item in enumerate(value):
                    fingerprint = _json_fingerprint(item)
                    if fingerprint in seen:
                        issues.append(
                            ValidationIssue(f"{path}[{index}]", "duplicates an earlier item")
                        )
                    seen.add(fingerprint)
            item_schema = node.get("items")
            if isinstance(item_schema, dict):
                for index, item in enumerate(value):
                    walk(item, item_schema, f"{path}[{index}]")

        if isinstance(value, str):
            minimum = node.get("minLength")
            maximum = node.get("maxLength")
            if minimum is not None and len(value) < minimum:
                issues.append(ValidationIssue(path, f"length is below {minimum}"))
            if maximum is not None and len(value) > maximum:
                issues.append(ValidationIssue(path, f"length exceeds {maximum}"))
            pattern = node.get("pattern")
            if isinstance(pattern, str) and re.search(pattern, value) is None:
                issues.append(ValidationIssue(path, f"does not match pattern {pattern!r}"))
            if node.get("format") == "date-time" and not _valid_date_time(value):
                issues.append(ValidationIssue(path, "is not an RFC 3339 date-time"))

        if _is_type(value, "number"):
            for keyword, operator, description in (
                ("minimum", lambda left, right: left >= right, "below minimum"),
                ("maximum", lambda left, right: left <= right, "above maximum"),
                (
                    "exclusiveMinimum",
                    lambda left, right: left > right,
                    "not above exclusiveMinimum",
                ),
                (
                    "exclusiveMaximum",
                    lambda left, right: left < right,
                    "not below exclusiveMaximum",
                ),
            ):
                boundary = node.get(keyword)
                if boundary is not None and not operator(value, boundary):
                    issues.append(ValidationIssue(path, f"{description} {boundary}"))

    walk(instance, schema, "$")
    return issues
