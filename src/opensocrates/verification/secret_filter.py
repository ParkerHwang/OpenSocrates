"""Positive-allowlist helpers for public record fields.

Unknown data is rejected before serialization.  The scanner reports only
field paths and stable reason codes; it never includes the suspected value in
an exception or diagnostic message.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlsplit


class FilterError(ValueError):
    """Base error for persistence-boundary validation."""


class ForbiddenKeyError(FilterError):
    """Raised when a prohibited key is present at any nesting depth."""

    def __init__(self, violations: tuple["FilterViolation", ...]) -> None:
        super().__init__("forbidden record key")
        self.violations = violations


class SecretDetectedError(FilterError):
    """Raised when a likely credential or unsafe URL is found."""

    def __init__(self, violations: tuple["FilterViolation", ...]) -> None:
        super().__init__("secret-like content is not allowed in public records")
        self.violations = violations


class AllowlistError(FilterError):
    """Raised when a typed payload exposes a field outside its allowlist."""


class ViolationKind(StrEnum):
    FORBIDDEN_KEY = "forbidden_key"
    SECRET = "secret"
    UNSAFE_URL = "unsafe_url"
    INVALID_TEXT = "invalid_text"
    UNKNOWN_FIELD = "unknown_field"
    DEPTH_LIMIT = "depth_limit"
    UNSUPPORTED_VALUE = "unsupported_value"


@dataclass(frozen=True, slots=True)
class FilterViolation:
    kind: ViolationKind
    path: tuple[str, ...]
    code: str


FORBIDDEN_KEYS = frozenset(
    {
        "prompt",
        "prompts",
        "transcript",
        "transcript_path",
        "messages",
        "conversation",
        "reasoning",
        "rationale_internal",
        "thought",
        "thoughts",
        "chain_of_thought",
        "raw",
        "raw_input",
        "raw_output",
        "tool_input",
        "tool_output",
        "tool_response",
        "stdout",
        "stderr",
        "command",
        "environment",
        "env",
        "cookie",
        "authorization",
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "private_key",
        "credentials",
    }
)

SECRET_QUERY_KEYS = frozenset(
    {
        "key",
        "api_key",
        "apikey",
        "access_token",
        "auth",
        "authorization",
        "credential",
        "password",
        "passwd",
        "secret",
        "token",
        "sig",
        "signature",
    }
)

_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pem_private_key", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    (
        "authorization_header",
        re.compile(r"(?i)\b(?:authorization|cookie)\s*[:=]\s*(?:bearer|basic)\s+\S+"),
    ),
    ("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    (
        "known_token_prefix",
        re.compile(
            r"(?i)\b(?:sk|rk|pk|ghp|github_pat|glpat|xox[baprs]-|npm|pypi)[_-][A-Za-z0-9._~+/=-]{12,}"
        ),
    ),
    ("cloud_access_key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    (
        "database_credentials",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mariadb|mongodb(?:\+srv)?|redis)://[^\s/:@]+:[^\s/@]+@"
        ),
    ),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(?:api[_ -]?key|access[_ -]?token|password|passwd|secret)\s*[:=]\s*[^\s]{12,}"
        ),
    ),
)
_BASE64_RUN = re.compile(r"[A-Za-z0-9+/=_-]{49,}")
_URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>]+")


class TypedPublicPayload(Protocol):
    """Protocol implemented by typed event payloads at the persistence edge."""

    def public_fields(self) -> Mapping[str, Any]:
        """Return the payload's closed, explicitly declared public fields."""


def _normal_key(key: str) -> str:
    normalized = unicodedata.normalize("NFKC", key).casefold().strip()
    return normalized.replace("-", "_").replace(" ", "_")


def _path_text(path: tuple[str, ...], index: int) -> tuple[str, ...]:
    return (*path, f"[{index}]")


def scan_forbidden_keys(value: object, *, max_depth: int = 12) -> tuple[FilterViolation, ...]:
    """Find forbidden keys recursively without retaining input values."""

    found: list[FilterViolation] = []

    def visit(item: object, path: tuple[str, ...], depth: int) -> None:
        if depth > max_depth:
            found.append(FilterViolation(ViolationKind.DEPTH_LIMIT, path, "json_depth"))
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    found.append(
                        FilterViolation(ViolationKind.UNSUPPORTED_VALUE, path, "non_string_key")
                    )
                    continue
                normalized = _normal_key(key)
                child_path = (*path, key)
                if normalized in FORBIDDEN_KEYS:
                    found.append(
                        FilterViolation(ViolationKind.FORBIDDEN_KEY, child_path, normalized)
                    )
                visit(child, child_path, depth + 1)
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)):
            for index, child in enumerate(item):
                visit(child, _path_text(path, index), depth + 1)
        elif isinstance(item, (bytes, bytearray)):
            found.append(FilterViolation(ViolationKind.UNSUPPORTED_VALUE, path, "binary_value"))

    visit(value, (), 0)
    return tuple(found)


def reject_forbidden_keys(value: object) -> None:
    violations = scan_forbidden_keys(value)
    if violations:
        raise ForbiddenKeyError(violations)


def _text_violations(text: str, path: tuple[str, ...]) -> tuple[FilterViolation, ...]:
    if "\x00" in text:
        return (FilterViolation(ViolationKind.INVALID_TEXT, path, "nul"),)
    if any(ord(char) < 0x20 and char not in "\n\t" for char in text):
        return (FilterViolation(ViolationKind.INVALID_TEXT, path, "control_character"),)
    return ()


def _url_violation(text: str, path: tuple[str, ...]) -> FilterViolation | None:
    match = _URL_RE.search(text)
    if match is None:
        return None
    candidate = match.group(0).rstrip(".,;:)]}")
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return FilterViolation(ViolationKind.UNSAFE_URL, path, "invalid_url")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return FilterViolation(ViolationKind.UNSAFE_URL, path, "unsupported_url")
    if parsed.username is not None or parsed.password is not None:
        return FilterViolation(ViolationKind.UNSAFE_URL, path, "url_userinfo")
    try:
        query = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=False)
    except ValueError:
        return FilterViolation(ViolationKind.UNSAFE_URL, path, "invalid_query")
    for key, _ in query:
        if _normal_key(key) in SECRET_QUERY_KEYS:
            return FilterViolation(ViolationKind.UNSAFE_URL, path, "credential_query")
    return None


def validate_public_url(url: str, *, path: tuple[str, ...] = ()) -> str:
    """Validate and return a source URL without rewriting it."""

    if not isinstance(url, str) or not url or len(url) > 2048:
        raise SecretDetectedError((FilterViolation(ViolationKind.UNSAFE_URL, path, "url_length"),))
    if any(ord(char) < 0x21 for char in url):
        raise SecretDetectedError(
            (FilterViolation(ViolationKind.UNSAFE_URL, path, "url_whitespace"),)
        )
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise SecretDetectedError(
            (FilterViolation(ViolationKind.UNSAFE_URL, path, "invalid_url"),)
        ) from error
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SecretDetectedError(
            (FilterViolation(ViolationKind.UNSAFE_URL, path, "unsupported_url"),)
        )
    if parsed.username is not None or parsed.password is not None:
        raise SecretDetectedError(
            (FilterViolation(ViolationKind.UNSAFE_URL, path, "url_userinfo"),)
        )
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=False):
        if _normal_key(key) in SECRET_QUERY_KEYS:
            raise SecretDetectedError(
                (FilterViolation(ViolationKind.UNSAFE_URL, path, "credential_query"),)
            )
    return url


def scan_secrets(value: object, *, max_depth: int = 12) -> tuple[FilterViolation, ...]:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Find secret-like strings and credential-bearing URLs recursively."""

    found: list[FilterViolation] = []

    def visit(item: object, path: tuple[str, ...], depth: int) -> None:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        if depth > max_depth:
            found.append(FilterViolation(ViolationKind.DEPTH_LIMIT, path, "json_depth"))
            return
        if isinstance(item, str):
            found.extend(_text_violations(item, path))
            for code, pattern in _SECRET_PATTERNS:
                if pattern.search(item):
                    found.append(FilterViolation(ViolationKind.SECRET, path, code))
            if _BASE64_RUN.search(item) and re.search(r"(?i)(?:secret|token|key|credential)", item):
                found.append(FilterViolation(ViolationKind.SECRET, path, "high_entropy_secret"))
            url_violation = _url_violation(item, path)
            if url_violation is not None:
                found.append(url_violation)
        elif isinstance(item, Mapping):
            for key, child in item.items():
                if isinstance(key, str):
                    visit(child, (*path, key), depth + 1)
                else:
                    found.append(
                        FilterViolation(ViolationKind.UNSUPPORTED_VALUE, path, "non_string_key")
                    )
        elif isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray)):
            for index, child in enumerate(item):
                visit(child, _path_text(path, index), depth + 1)
        elif item is not None and not isinstance(item, (bool, int, float)):
            found.append(
                FilterViolation(ViolationKind.UNSUPPORTED_VALUE, path, "unsupported_value")
            )

    visit(value, (), 0)
    return tuple(found)


def reject_secrets(value: object) -> None:
    violations = scan_secrets(value)
    if violations:
        raise SecretDetectedError(violations)


def validate_typed_allowlist(
    payload: TypedPublicPayload,
    allowed_fields: frozenset[str],
) -> Mapping[str, Any]:
    """Validate the public fields exposed by a typed payload.

    This is the only generic field-map adapter.  Record repositories call it
    with payload dataclasses; they do not expose a raw-dictionary append API.
    """

    fields = payload.public_fields()
    if not isinstance(fields, Mapping):
        raise AllowlistError("typed payload did not expose public fields")
    reject_forbidden_keys(fields)
    unknown = tuple(sorted(set(fields) - allowed_fields))
    if unknown:
        raise AllowlistError("payload contains an unknown public field")
    reject_secrets(fields)
    return fields


def safe_text(text: str, *, max_length: int = 2200, path: tuple[str, ...] = ()) -> str:
    """Validate a public SafeText field without exposing its content on error."""

    if not isinstance(text, str) or len(text) > max_length:
        raise FilterError("invalid public text")
    normalized = unicodedata.normalize("NFC", text)
    violations = _text_violations(normalized, path)
    if violations:
        raise FilterError("invalid public text")
    reject_secrets(normalized)
    return normalized
