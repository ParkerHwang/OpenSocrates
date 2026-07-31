"""Small, deterministic Markdown primitives for public Conclusion Cards.

The renderer and parser deliberately implement only the inline Markdown they
own.  They do not invoke a Markdown package, read files, inspect the
environment, or fetch source URLs.  Text is validated before it is escaped so
that control characters, NULs, unpaired surrogates, and non-NFC public text do
not cross the card boundary.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from collections.abc import Iterator
from urllib.parse import parse_qsl, urlsplit

from ..errors import ValidationError

MAX_SOURCE_URI_SCALARS = 2048
_C0_CONTROL_MAX = 0x1F
_C1_CONTROL_MIN = 0x7F
_C1_CONTROL_MAX = 0x9F
_MARKDOWN_ESCAPABLE = frozenset("\\`*_[]<>;") | {"#"}
_URL_RE = re.compile(r"(?i)(?<![\w])(?:[a-z][a-z0-9+.-]*):\/\/[^\s<>]+")
_INVALID_URL_ESCAPE_RE = re.compile(r"%(?![0-9a-fA-F]{2})")
_CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "token",
        "key",
        "secret",
        "signature",
        "sig",
        "auth",
        "code",
        "session",
        "api_key",
        "apikey",
        "access_token",
        "authorization",
        "credential",
        "password",
        "passwd",
    }
)


def scalar_count(value: str) -> int:
    """Return the Unicode scalar count used by the card contract.

    Python's ``len`` counts Unicode code points.  Surrogate code points are
    rejected separately by :func:`validate_scalar_text`, so this is the
    contract's scalar count for accepted text.
    """

    if not isinstance(value, str):
        raise ValidationError("markdown: expected text")
    return len(value)


count_unicode_scalars = scalar_count


def _reject_text_hazards(
    value: str, *, field_name: str, allow_newline: bool, allow_tab: bool
) -> None:
    if unicodedata.normalize("NFC", value) != value:
        raise ValidationError(f"{field_name}: text must be Unicode NFC")
    for character in value:
        codepoint = ord(character)
        if unicodedata.category(character) == "Cs":
            raise ValidationError(f"{field_name}: contains an unpaired surrogate")
        if character == "\n" and allow_newline:
            continue
        if character == "\t" and allow_tab:
            continue
        if codepoint <= _C0_CONTROL_MAX or _C1_CONTROL_MIN <= codepoint <= _C1_CONTROL_MAX:
            raise ValidationError(f"{field_name}: contains a forbidden control character")


def validate_scalar_text(
    value: str,
    *,
    field_name: str = "text",
    max_scalars: int | None = None,
    allow_newline: bool = False,
    allow_tab: bool = False,
    require_nonblank: bool = True,
) -> str:
    """Validate safe public text and return it unchanged."""

    if not isinstance(value, str):
        raise ValidationError(f"{field_name}: expected text")
    _reject_text_hazards(
        value, field_name=field_name, allow_newline=allow_newline, allow_tab=allow_tab
    )
    if max_scalars is not None and scalar_count(value) > max_scalars:
        raise ValidationError(f"{field_name}: exceeds {max_scalars} Unicode scalar values")
    if require_nonblank and not value.strip():
        raise ValidationError(f"{field_name}: must not be blank")
    return value


safe_text = validate_scalar_text


def normalize_markdown(value: str) -> str:
    """Normalize accepted line endings while rejecting unsafe Markdown text."""

    if not isinstance(value, str):
        raise ValidationError("markdown: expected text")
    normalized = value.replace("\r\n", "\n")
    if "\r" in normalized:
        raise ValidationError("markdown: bare carriage return is not allowed")
    validate_scalar_text(
        normalized,
        field_name="markdown",
        max_scalars=None,
        allow_newline=True,
        allow_tab=False,
        require_nonblank=False,
    )
    return normalized


def nonblank_line_count(value: str) -> int:
    """Count nonblank LF-separated lines after safe line-ending handling."""

    normalized = normalize_markdown(value)
    return sum(bool(line.strip()) for line in normalized.split("\n"))


count_nonblank_lines = nonblank_line_count


def escape_inline(
    value: str,
    *,
    field_name: str = "text",
    max_scalars: int | None = None,
    escape_semicolons: bool = False,
) -> str:
    """Escape the small Markdown punctuation subset emitted by this package."""

    validate_scalar_text(value, field_name=field_name, max_scalars=max_scalars)
    result: list[str] = []
    for character in value:
        if character in _MARKDOWN_ESCAPABLE and (character != ";" or escape_semicolons):
            result.append("\\")
        result.append(character)
    return "".join(result)


def unescape_inline(value: str, *, field_name: str = "text") -> str:
    """Reverse :func:`escape_inline`; unknown escapes fail closed."""

    if not isinstance(value, str):
        raise ValidationError(f"{field_name}: expected text")
    result: list[str] = []
    index = 0
    while index < len(value):
        character = value[index]
        if character != "\\":
            result.append(character)
            index += 1
            continue
        if index + 1 >= len(value) or value[index + 1] not in _MARKDOWN_ESCAPABLE:
            raise ValidationError(f"{field_name}: unknown Markdown escape")
        result.append(value[index + 1])
        index += 2
    return validate_scalar_text("".join(result), field_name=field_name)


def inline_code(value: str, *, field_name: str = "code") -> str:
    """Render a safe inline code span with a minimal backtick fence."""

    validate_scalar_text(value, field_name=field_name)
    longest = 0
    current = 0
    for character in value:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    fence = "`" * (longest + 1)
    if value[:1].isspace() or value[-1:].isspace():
        return f"{fence} {value} {fence}"
    return f"{fence}{value}{fence}"


def parse_inline_code(value: str, *, field_name: str = "code") -> str:
    """Parse exactly one code span produced by :func:`inline_code`."""

    if not isinstance(value, str) or not value.startswith("`"):
        raise ValidationError(f"{field_name}: expected inline code")
    fence_length = 0
    while fence_length < len(value) and value[fence_length] == "`":
        fence_length += 1
    fence = "`" * fence_length
    if not value.endswith(fence) or len(value) <= 2 * fence_length:
        raise ValidationError(f"{field_name}: malformed inline code")
    body = value[fence_length:-fence_length]
    if body.startswith(" ") and body.endswith(" ") and len(body) >= 2:
        body = body[1:-1]
    if "\n" in body or "\r" in body:
        raise ValidationError(f"{field_name}: inline code must stay on one line")
    return validate_scalar_text(body, field_name=field_name)


def validate_public_url(value: str) -> str:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Validate a source URL without rewriting it or performing I/O."""

    if not isinstance(value, str) or not value or scalar_count(value) > MAX_SOURCE_URI_SCALARS:
        raise ValidationError("source.uri: URL length is outside the safe range")
    if any(character.isspace() for character in value):
        raise ValidationError("source.uri: whitespace is not allowed")
    if _INVALID_URL_ESCAPE_RE.search(value) or any(character in value for character in "\\<>"):
        raise ValidationError("source.uri: malformed URL escaping")
    validate_scalar_text(
        value,
        field_name="source.uri",
        max_scalars=MAX_SOURCE_URI_SCALARS,
        allow_newline=False,
        allow_tab=False,
    )
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise ValidationError("source.uri: malformed URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or not parsed.hostname:
        raise ValidationError("source.uri: only HTTP(S) URLs are allowed")
    if parsed.username is not None or parsed.password is not None:
        raise ValidationError("source.uri: URL userinfo is not allowed")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValidationError("source.uri: malformed URL") from exc
    if parsed.hostname.lower() == "localhost" and parsed.scheme != "http":
        raise ValidationError("source.uri: private or reserved host is not allowed")
    if parsed.scheme == "http" and parsed.hostname.lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise ValidationError("source.uri: HTTP is allowed only for localhost fixtures")
    try:
        host_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        host_ip = None
    if host_ip is not None and (host_ip.is_private or host_ip.is_link_local or host_ip.is_reserved):
        if not (parsed.scheme == "http" and host_ip.is_loopback):
            raise ValidationError("source.uri: private or reserved host is not allowed")
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=False):
        if key.casefold().replace("-", "_") in _CREDENTIAL_QUERY_KEYS:
            raise ValidationError("source.uri: credential-like query key is not allowed")
    return value


def render_link(display_name: str, uri: str) -> str:
    """Render a meaningful safe Markdown source link."""

    validate_scalar_text(display_name, field_name="source.display_name", max_scalars=200)
    if display_name.strip().casefold() in {"click here", "here", "link"}:
        raise ValidationError("source.display_name: generic link text is not allowed")
    validate_public_url(uri)
    escaped_name = escape_inline(display_name, field_name="source.display_name", max_scalars=200)
    if any(character in uri for character in ")\\"):
        return f"[{escaped_name}](<{uri}>)"
    return f"[{escaped_name}]({uri})"


def parse_link(value: str, *, field_name: str = "source") -> tuple[str, str]:
    """Parse one safe Markdown link produced by :func:`render_link`."""

    if not isinstance(value, str) or not value.startswith("["):
        raise ValidationError(f"{field_name}: expected Markdown link")
    close_label = value.find("](")
    if close_label <= 1 or not value.endswith(")"):
        raise ValidationError(f"{field_name}: malformed Markdown link")
    label_raw = value[1:close_label]
    destination = value[close_label + 2 : -1]
    if destination.startswith("<") and destination.endswith(">"):
        destination = destination[1:-1]
    if not destination or "(" in destination and not destination.startswith("http"):
        raise ValidationError(f"{field_name}: malformed Markdown destination")
    label = unescape_inline(label_raw, field_name=f"{field_name}.display_name")
    validate_scalar_text(label, field_name=f"{field_name}.display_name", max_scalars=200)
    validate_public_url(destination)
    return label, destination


def iter_urls(value: str) -> Iterator[str]:
    """Yield URL-looking substrings for deterministic caller-side checking."""

    if not isinstance(value, str):
        raise ValidationError("text: expected text")
    for match in _URL_RE.finditer(value):
        yield match.group(0).rstrip(".,;:)]}")


def validate_text_urls(value: str, *, field_name: str = "text") -> None:
    """Reject malformed, private, or credential-bearing URLs in public text."""

    for candidate in iter_urls(value):
        try:
            validate_public_url(candidate)
        except ValidationError as exc:
            raise ValidationError(f"{field_name}: unsafe URL") from exc


def validate_card_markdown(value: str, *, max_lines: int = 14, max_scalars: int = 2200) -> str:
    """Apply whole-card scalar and nonblank-line limits."""

    normalized = normalize_markdown(value)
    if nonblank_line_count(normalized) > max_lines:
        raise ValidationError(f"card: exceeds {max_lines} nonblank lines")
    if scalar_count(normalized) > max_scalars:
        raise ValidationError(f"card: exceeds {max_scalars} Unicode scalar values")
    return normalized


__all__ = [
    "MAX_SOURCE_URI_SCALARS",
    "count_nonblank_lines",
    "count_unicode_scalars",
    "escape_inline",
    "inline_code",
    "iter_urls",
    "normalize_markdown",
    "nonblank_line_count",
    "parse_inline_code",
    "parse_link",
    "render_link",
    "safe_text",
    "scalar_count",
    "unescape_inline",
    "validate_card_markdown",
    "validate_public_url",
    "validate_scalar_text",
    "validate_text_urls",
]
