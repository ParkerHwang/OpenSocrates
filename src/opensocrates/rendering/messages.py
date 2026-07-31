"""Fail-closed locale-catalog lookup and safe status/settings messages.

The renderer consumes the compiled content bundle supplied by the caller.  It
never reads authoring files, translates at runtime, or falls back to another
locale.  Missing keys and placeholder mismatches are hard errors so a host
cannot silently display mixed-language or misleading status text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from ..domain.models import CompiledContentBundle


class MessageCatalogError(ValueError):
    """Base error for malformed or incomplete locale catalogs."""


class MissingLocaleKey(MessageCatalogError):
    """Raised when a requested locale/key pair is absent."""


class PlaceholderMismatch(MessageCatalogError):
    """Raised when a template's placeholders do not match its arguments."""


_PLACEHOLDER_RE: Final[re.Pattern[str]] = re.compile(r"\{([A-Za-z][A-Za-z0-9_.-]*)\}")
_LOCALES: Final[frozenset[str]] = frozenset({"en", "ko"})
_STATUS_STATES: Final[frozenset[str]] = frozenset(
    {"full", "degraded", "prompt_only", "unavailable", "unknown"}
)
_RECORDING_STATES: Final[frozenset[str]] = frozenset({"on", "off"})
_ONBOARDING_STATES: Final[frozenset[str]] = frozenset({"complete", "pending"})
_STORAGE_STATES: Final[frozenset[str]] = frozenset(
    {"supported", "degraded", "unavailable", "unknown"}
)
_RIGOR_STATES: Final[frozenset[str]] = frozenset({"quiet", "together", "strict"})
_LOCALE_STATES: Final[frozenset[str]] = frozenset({"follow", "en", "ko"})


def placeholder_names(template: str) -> frozenset[str]:
    """Return the closed placeholder names present in one template."""

    if not isinstance(template, str):
        raise MessageCatalogError("locale message must be a string")
    return frozenset(_PLACEHOLDER_RE.findall(template))


def validate_placeholder_parity(
    locale_messages: Mapping[str, Mapping[str, str]],
) -> None:
    """Require EN/KO key and placeholder parity for a complete catalog."""

    if set(locale_messages) != _LOCALES:
        raise MessageCatalogError("locale catalog must contain exactly en and ko")
    en = locale_messages["en"]
    ko = locale_messages["ko"]
    if set(en) != set(ko):
        missing_en = sorted(set(ko) - set(en))
        missing_ko = sorted(set(en) - set(ko))
        raise MessageCatalogError(f"locale key parity mismatch: en={missing_en}, ko={missing_ko}")
    mismatches = [key for key in en if placeholder_names(en[key]) != placeholder_names(ko[key])]
    if mismatches:
        raise PlaceholderMismatch("placeholder parity mismatch: " + ", ".join(sorted(mismatches)))


@dataclass(frozen=True, slots=True)
class LocaleCatalog:
    """Immutable view over the compiled bundle's EN/KO message maps."""

    locale_messages: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        copied: dict[str, Mapping[str, str]] = {}
        for locale, messages in self.locale_messages.items():
            if locale not in _LOCALES or not isinstance(messages, Mapping):
                raise MessageCatalogError("locale catalog contains an unsupported locale")
            normalized: dict[str, str] = {}
            for key, value in messages.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise MessageCatalogError("locale keys and messages must be strings")
                placeholder_names(value)
                normalized[key] = value
            copied[locale] = MappingProxyType(normalized)
        validate_placeholder_parity(copied)
        object.__setattr__(self, "locale_messages", MappingProxyType(copied))

    @classmethod
    def from_bundle(cls, bundle: CompiledContentBundle) -> "LocaleCatalog":
        """Create a catalog from a validated compiled content bundle."""

        if not isinstance(bundle, CompiledContentBundle):
            raise TypeError("locale catalog requires CompiledContentBundle")
        return cls(bundle.locale_messages)

    @classmethod
    def from_messages(
        cls,
        locale_messages: Mapping[str, Mapping[str, str]],
    ) -> "LocaleCatalog":
        """Construct a catalog for focused application/rendering walkthroughs."""

        return cls(locale_messages)

    def lookup(self, locale_code: str, key: str, **values: object) -> str:
        """Look up and format one message, rejecting missing/mismatched data."""

        if locale_code not in _LOCALES:
            raise MissingLocaleKey(f"unsupported locale: {locale_code!r}")
        messages = self.locale_messages.get(locale_code)
        if messages is None or key not in messages:
            raise MissingLocaleKey(f"missing locale key {locale_code}.{key}")
        template = messages[key]
        expected = placeholder_names(template)
        supplied = frozenset(values)
        if expected != supplied:
            raise PlaceholderMismatch(
                f"{locale_code}.{key}: expected placeholders {sorted(expected)}, supplied {sorted(supplied)}"
            )
        # Only scalar substitutions are accepted.  This prevents callers from
        # accidentally injecting structured settings or an internal object.
        if any(not isinstance(value, (str, int, bool)) for value in values.values()):
            raise MessageCatalogError(f"{locale_code}.{key}: substitutions must be scalar")
        try:
            rendered = template.format_map({name: str(value) for name, value in values.items()})
        except (KeyError, ValueError) as error:
            raise PlaceholderMismatch(
                f"{locale_code}.{key}: invalid placeholder formatting"
            ) from error
        if not rendered.strip():
            raise MessageCatalogError(f"{locale_code}.{key}: rendered message is empty")
        return rendered


def _state_key(prefix: str, state: str, allowed: frozenset[str]) -> str:
    if state not in allowed:
        raise MessageCatalogError(f"unsupported closed status value: {state!r}")
    return f"{prefix}.{state}"


def rigor_label(catalog: LocaleCatalog, locale: str, level: str) -> str:
    return catalog.lookup(locale, _state_key("onboarding.rigor", level, _RIGOR_STATES))


def render_rigor_confirmation(
    catalog: LocaleCatalog,
    locale: str,
    level: str,
) -> str:
    """Render one short localized settings confirmation without JSON/internal IDs."""

    return catalog.lookup(
        locale,
        "message.settings.rigor",
        level=rigor_label(catalog, locale, level),
    )


def render_settings_confirmation(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    catalog: LocaleCatalog,
    locale: str,
    *,
    kind: str,
    value: str | int | None = None,
) -> str:
    """Render a catalog-backed confirmation for one safe settings change."""

    if kind == "rigor":
        if not isinstance(value, str):
            raise MessageCatalogError("rigor confirmation requires a level")
        return render_rigor_confirmation(catalog, locale, value)
    if kind == "locale":
        state = value if isinstance(value, str) else "follow"
        locale_label = catalog.lookup(
            locale, _state_key("message.status.locale", state, _LOCALE_STATES)
        )
        return catalog.lookup(locale, "message.settings.locale", locale=locale_label)
    if kind == "recording":
        state = value if isinstance(value, str) else "off"
        recording_label = catalog.lookup(
            locale,
            _state_key("message.status.recording", state, _RECORDING_STATES),
        )
        return catalog.lookup(locale, "message.settings.recording", state=recording_label)
    if kind == "retention":
        if not isinstance(value, int) or isinstance(value, bool):
            raise MessageCatalogError("retention confirmation requires an integer")
        return catalog.lookup(locale, "message.settings.retention", days=value)
    if kind == "size":
        if not isinstance(value, int) or isinstance(value, bool):
            raise MessageCatalogError("size confirmation requires an integer")
        return catalog.lookup(locale, "message.settings.size", bytes=value)
    if kind == "reset":
        if value is not None:
            raise MessageCatalogError("reset confirmation accepts no value")
        return catalog.lookup(locale, "message.settings.reset")
    raise MessageCatalogError(f"unsupported settings confirmation kind: {kind!r}")


def render_status(
    catalog: LocaleCatalog,
    projection: Any,
) -> str:
    """Render a content-free localized status projection.

    ``projection`` is intentionally duck-typed to avoid a rendering↔application
    import cycle.  Only the closed scalar fields produced by ``status.py`` are
    read; settings JSON, capability IDs, paths, and secrets cannot enter this
    surface.
    """

    locale = getattr(projection, "locale", None)
    if locale not in _LOCALES:
        raise MessageCatalogError("status projection has unsupported locale")
    capability = getattr(projection, "capability_state", None)
    capability_value = getattr(capability, "value", capability)
    storage = getattr(projection, "storage_state", None)
    storage_value = getattr(storage, "value", storage)
    rigor = getattr(
        getattr(projection, "default_rigor", None),
        "value",
        getattr(projection, "default_rigor", None),
    )
    recording_on = bool(getattr(projection, "recording_effective", False))
    onboarding_complete = bool(getattr(projection, "onboarding_complete", False))
    locale_preference = getattr(projection, "locale_preference", None)
    locale_state = locale_preference if locale_preference in {"en", "ko"} else "follow"
    lines = [catalog.lookup(locale, "message.status.title")]
    lines.append(
        catalog.lookup(
            locale,
            _state_key("message.status.capability", capability_value, _STATUS_STATES),  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        )
    )
    recording_state = "on" if recording_on else "off"
    lines.append(
        catalog.lookup(
            locale,
            "message.settings.recording",
            state=catalog.lookup(
                locale,
                _state_key("message.status.recording", recording_state, _RECORDING_STATES),
            ),
        )
    )
    lines.append(
        catalog.lookup(
            locale,
            _state_key(
                "message.status.onboarding",
                "complete" if onboarding_complete else "pending",
                _ONBOARDING_STATES,
            ),
        )
    )
    lines.append(
        catalog.lookup(locale, _state_key("message.status.storage", storage_value, _STORAGE_STATES))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    )
    lines.append(
        catalog.lookup(locale, "message.settings.rigor", level=rigor_label(catalog, locale, rigor))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    )
    lines.append(
        catalog.lookup(
            locale,
            "message.settings.locale",
            locale=catalog.lookup(
                locale,
                _state_key("message.status.locale", locale_state, _LOCALE_STATES),
            ),
        )
    )
    lines.append(
        catalog.lookup(
            locale,
            "message.settings.retention",
            days=int(projection.record_retention_days),
        )
    )
    lines.append(
        catalog.lookup(
            locale,
            "message.settings.size",
            bytes=int(projection.record_size_limit_bytes),
        )
    )
    return "\n".join(lines)


__all__ = [
    "LocaleCatalog",
    "MessageCatalogError",
    "MissingLocaleKey",
    "PlaceholderMismatch",
    "placeholder_names",
    "render_rigor_confirmation",
    "render_settings_confirmation",
    "render_status",
    "rigor_label",
    "validate_placeholder_parity",
]
