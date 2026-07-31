"""Deterministic source and locator safety rules.

Source handling is intentionally conservative.  The runtime never fetches a
URL and never stores a private path.  A credential-looking query removes only
the URI (the safe human display remains available); userinfo, unsupported
schemes, malformed URLs, and unsafe locators are rejected.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import parse_qsl, urlsplit

from ..domain.enums import ViolationSeverity
from ..domain.models import SourceReference, Violation
from ..domain.validation import validate_safe_text
from ..errors import ValidationError

MAX_SOURCE_DISPLAY = 200
MAX_SOURCE_URI = 2048
MAX_SAFE_LOCATOR = 200

_CREDENTIAL_QUERY_KEYS = frozenset(
    {"token", "key", "secret", "signature", "sig", "auth", "code", "session"}
)
_LOCALHOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:")
_UNIT_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class SourceFailureCode(StrEnum):
    INVALID_DISPLAY = "invalid_display"
    DISPLAY_TOO_LONG = "display_too_long"
    INVALID_LOCATOR = "invalid_locator"
    LOCATOR_PATH = "locator_path"
    INVALID_URI = "invalid_uri"
    URI_TOO_LONG = "uri_too_long"
    URI_WHITESPACE = "uri_whitespace"
    URL_USERINFO = "url_userinfo"
    UNSUPPORTED_SCHEME = "unsupported_scheme"
    HTTP_NON_LOCALHOST = "http_non_localhost"
    CREDENTIAL_QUERY = "credential_query"
    CONTENT_HASH_FORBIDDEN = "content_hash_forbidden"
    INVALID_SOURCE = "invalid_source"


@dataclass(frozen=True, slots=True)
class SourceUriSanitization:
    """The safe storage decision for one source URI."""

    stored_uri: str | None
    removed_credentials: bool = False
    rejected: bool = False
    failure_code: SourceFailureCode | None = None


class SourceRuleError(ValidationError):
    """Raised when a source URI/locator must not be persisted."""

    def __init__(self, code: SourceFailureCode, message: str) -> None:
        super().__init__(message)
        self.failure_code = code


def _violation(rule_id: str, field: str | None, message_key: str) -> Violation:
    return Violation(
        rule_id=rule_id,
        severity=ViolationSeverity.ERROR,
        message_key=message_key,
        field=field,
        repair_hint_key=None,
    )


def _normalized_query_keys(query: str) -> tuple[str, ...]:
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=False)
    except ValueError as exc:
        raise SourceRuleError(
            SourceFailureCode.INVALID_URI, "source URI query is malformed"
        ) from exc
    return tuple(key.casefold() for key, _ in pairs)


def inspect_source_uri(uri: str | None) -> SourceUriSanitization:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Inspect a URI without fetching or rewriting its safe public spelling.

    ``stored_uri`` is ``None`` for a missing URI or a credential-like query.
    Unsafe URI classes are marked ``rejected`` and raise from the stricter
    :func:`sanitize_source_uri` façade.
    """

    if uri is None:
        return SourceUriSanitization(stored_uri=None)
    if not isinstance(uri, str):
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.INVALID_URI,
        )
    if len(uri) > MAX_SOURCE_URI:
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.URI_TOO_LONG,
        )
    if _UNIT_CONTROL_RE.search(uri) or any(char.isspace() for char in uri):
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.URI_WHITESPACE,
        )
    try:
        parsed = urlsplit(uri)
        # Accessing hostname/port forces validation for malformed bracketed
        # addresses and invalid ports in urllib's parser.
        hostname = parsed.hostname
        _ = parsed.port
        username = parsed.username
        password = parsed.password
    except (TypeError, ValueError):
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.INVALID_URI,
        )
    if username is not None or password is not None:
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.URL_USERINFO,
        )
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https"} or not parsed.netloc or not hostname:
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.UNSUPPORTED_SCHEME,
        )
    if scheme == "http" and hostname.casefold().strip("[]") not in _LOCALHOSTS:
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=SourceFailureCode.HTTP_NON_LOCALHOST,
        )
    try:
        query_keys = _normalized_query_keys(parsed.query)
    except SourceRuleError as exc:
        return SourceUriSanitization(
            stored_uri=None,
            rejected=True,
            failure_code=exc.failure_code,
        )
    if any(key in _CREDENTIAL_QUERY_KEYS for key in query_keys):
        # Keep the safe display name and discard the whole URI.  Retaining a
        # redacted query would still risk leaking a credential-shaped value.
        return SourceUriSanitization(stored_uri=None, removed_credentials=True)
    return SourceUriSanitization(stored_uri=uri)


def sanitize_source_uri(uri: str | None) -> str | None:
    """Return the URI safe for persistence, or raise for unsafe URL classes."""

    decision = inspect_source_uri(uri)
    if decision.rejected:
        code = decision.failure_code or SourceFailureCode.INVALID_URI
        raise SourceRuleError(code, f"source URI rejected: {code.value}")
    return decision.stored_uri


def sanitize_persistable_source_uri(uri: str | None) -> str | None:
    """Compatibility alias for :func:`sanitize_source_uri`."""

    return sanitize_source_uri(uri)


def _locator_violation(locator: object) -> SourceFailureCode | None:
    if not isinstance(locator, str) or not locator.strip():
        return SourceFailureCode.INVALID_LOCATOR
    if len(locator) > MAX_SAFE_LOCATOR or unicodedata.normalize("NFC", locator) != locator:
        return SourceFailureCode.INVALID_LOCATOR
    if _UNIT_CONTROL_RE.search(locator):
        return SourceFailureCode.INVALID_LOCATOR
    if "/" in locator or "\\" in locator:
        return SourceFailureCode.LOCATOR_PATH
    if locator.startswith(("~", "//", "\\\\")) or _DRIVE_PATH_RE.match(locator):
        return SourceFailureCode.LOCATOR_PATH
    if locator in {".", ".."} or locator.startswith("../") or locator.startswith("..\\"):
        return SourceFailureCode.LOCATOR_PATH
    return None


def collect_source_violations(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    source: SourceReference,
    *,
    allow_public_fixture_hash: bool = False,
) -> tuple[Violation, ...]:
    """Return bounded, stable violations for one typed source reference."""

    if not isinstance(source, SourceReference):
        return (_violation("OSV-SOURCE-000", None, "source.invalid"),)
    violations: list[Violation] = []
    try:
        display = str(source.display_name)
        validate_safe_text(
            display,
            field_name="display_name",
            max_length=MAX_SOURCE_DISPLAY,
            allow_newline=False,
            allow_tab=False,
        )
        if not display.strip():
            raise ValidationError("display name is blank")
    except (ValidationError, TypeError, ValueError):
        violations.append(_violation("OSV-SOURCE-001", "display_name", "source.display_invalid"))
    if len(str(source.display_name)) > MAX_SOURCE_DISPLAY:
        violations.append(_violation("OSV-SOURCE-002", "display_name", "source.display_too_long"))

    if source.safe_locator is not None:
        locator_code = _locator_violation(source.safe_locator)
        if locator_code is SourceFailureCode.LOCATOR_PATH:
            violations.append(_violation("OSV-SOURCE-003", "safe_locator", "source.locator_path"))
        elif locator_code is not None:
            violations.append(
                _violation("OSV-SOURCE-004", "safe_locator", "source.locator_invalid")
            )

    if source.uri is not None:
        decision = inspect_source_uri(source.uri)
        if decision.rejected:
            code = decision.failure_code
            rule_id = {
                SourceFailureCode.URL_USERINFO: "OSV-SOURCE-006",
                SourceFailureCode.HTTP_NON_LOCALHOST: "OSV-SOURCE-007",
                SourceFailureCode.UNSUPPORTED_SCHEME: "OSV-SOURCE-008",
                SourceFailureCode.URI_TOO_LONG: "OSV-SOURCE-009",
                SourceFailureCode.URI_WHITESPACE: "OSV-SOURCE-010",
            }.get(code, "OSV-SOURCE-005")  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            message = {
                SourceFailureCode.URL_USERINFO: "source.url_userinfo",
                SourceFailureCode.HTTP_NON_LOCALHOST: "source.http_localhost_only",
                SourceFailureCode.UNSUPPORTED_SCHEME: "source.scheme_unsupported",
                SourceFailureCode.URI_TOO_LONG: "source.uri_too_long",
                SourceFailureCode.URI_WHITESPACE: "source.uri_whitespace",
            }.get(code, "source.uri_invalid")  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            violations.append(_violation(rule_id, "uri", message))
    if source.content_hash is not None and not allow_public_fixture_hash:
        violations.append(
            _violation("OSV-SOURCE-011", "content_hash", "source.content_hash_forbidden")
        )
    return tuple(violations)


def validate_source_reference(
    source: SourceReference,
    *,
    allow_public_fixture_hash: bool = False,
) -> tuple[Violation, ...]:
    """Alias emphasizing validation rather than collection."""

    return collect_source_violations(source, allow_public_fixture_hash=allow_public_fixture_hash)


def enforce_source_rules(
    source: SourceReference,
    *,
    allow_public_fixture_hash: bool = False,
) -> SourceReference:
    """Raise if a source would violate persistence safety rules."""

    violations = collect_source_violations(
        source, allow_public_fixture_hash=allow_public_fixture_hash
    )
    if violations:
        details = ", ".join(item.rule_id for item in violations)
        raise ValidationError(f"source verification failed: {details}")
    return source


def is_safe_source(source: SourceReference, *, allow_public_fixture_hash: bool = False) -> bool:
    """Return the source safety bit; malformed input is never treated as safe."""

    return not collect_source_violations(
        source, allow_public_fixture_hash=allow_public_fixture_hash
    )


# Common names used by callers and walkthroughs.
check_source = collect_source_violations
verify_source = enforce_source_rules
safe_uri = sanitize_source_uri
validate_source = collect_source_violations
source_violations = collect_source_violations
sanitize_uri = sanitize_source_uri


__all__ = [
    "MAX_SAFE_LOCATOR",
    "MAX_SOURCE_DISPLAY",
    "MAX_SOURCE_URI",
    "SourceFailureCode",
    "SourceRuleError",
    "SourceUriSanitization",
    "check_source",
    "collect_source_violations",
    "enforce_source_rules",
    "inspect_source_uri",
    "is_safe_source",
    "safe_uri",
    "sanitize_uri",
    "sanitize_persistable_source_uri",
    "sanitize_source_uri",
    "validate_source_reference",
    "validate_source",
    "verify_source",
    "source_violations",
]
