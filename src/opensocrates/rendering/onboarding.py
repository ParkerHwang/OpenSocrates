"""Deterministic first-judgment onboarding disclosure rendering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ..application.change_settings import CURRENT_ONBOARDING_VERSION
from .messages import LocaleCatalog, MessageCatalogError


class OnboardingRenderError(ValueError):
    """Raised when authored disclosure content is missing or over budget."""


EN_WORD_LIMIT: Final[int] = 90
KO_SPACING_LIMIT: Final[int] = 180
_EN_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*")


@dataclass(frozen=True, slots=True)
class OnboardingDisclosure:
    """Rendered native disclosure and its deterministic measurements.

    The ``*_word_count`` fields measure the final rendered text, including the
    prompt-only limitation when present.  The ``base_*`` fields measure only
    the rendered title/body disclosure, which is the budgeted surface under
    Plan §3.3.  Keeping both measurements makes the separately appended
    prompt-only sentence observable without weakening the base budget.
    """

    locale: str
    version: str
    text: str
    prompt_only: bool
    english_word_count: int
    korean_spacing_units: int
    base_english_word_count: int = 0
    base_korean_spacing_units: int = 0


def _count_english_words(text: str) -> int:
    return len(_EN_WORD_RE.findall(text))


def _count_korean_spacing_units(text: str) -> int:
    return len(text.split())


def _authored(catalog: LocaleCatalog, locale: str, key: str, **values: object) -> str:
    try:
        return catalog.lookup(locale, key, **values)
    except MessageCatalogError as error:
        raise OnboardingRenderError(str(error)) from error


def render_onboarding(
    catalog: LocaleCatalog,
    locale: str,
    *,
    version: str = CURRENT_ONBOARDING_VERSION,
    prompt_only: bool = False,
) -> OnboardingDisclosure:
    """Render exactly one authored disclosure screen in EN or KO.

    The body is authored once per locale and receives only the three authored
    rigor labels as placeholders.  The prompt-only sentence is a separate
    authored catalog value and is appended exactly once when requested.
    """

    if locale not in {"en", "ko"}:
        raise OnboardingRenderError("onboarding locale must be en or ko")
    if not isinstance(version, str) or not version:
        raise OnboardingRenderError("onboarding version is required")
    title = _authored(catalog, locale, "onboarding.title")
    body = _authored(
        catalog,
        locale,
        "onboarding.body",
        quiet=_authored(catalog, locale, "onboarding.rigor.quiet"),
        together=_authored(catalog, locale, "onboarding.rigor.together"),
        strict=_authored(catalog, locale, "onboarding.rigor.strict"),
    )
    base = f"**{title}**\n\n{body}".strip()
    text = base
    if prompt_only:
        limitation = _authored(catalog, locale, "onboarding.prompt_only_limitation")
        if limitation in base:
            raise OnboardingRenderError(
                "prompt-only limitation is already present in authored disclosure"
            )
        text = f"{base}\n\n{limitation}".strip()
        if text.count(limitation) != 1:
            raise OnboardingRenderError("prompt-only limitation must be appended exactly once")

    base_english_words = _count_english_words(base)
    base_korean_units = _count_korean_spacing_units(base)
    english_words = _count_english_words(text)
    korean_units = _count_korean_spacing_units(text)
    if locale == "en" and base_english_words > EN_WORD_LIMIT:
        raise OnboardingRenderError("base English onboarding disclosure exceeds 90 words")
    if locale == "ko" and base_korean_units > KO_SPACING_LIMIT:
        raise OnboardingRenderError("base Korean onboarding disclosure exceeds 180 spacing units")
    if not text or text != text.strip():
        raise OnboardingRenderError("onboarding disclosure must be nonblank and trimmed")
    return OnboardingDisclosure(
        locale=locale,
        version=version,
        text=text,
        prompt_only=prompt_only,
        english_word_count=english_words,
        korean_spacing_units=korean_units,
        base_english_word_count=base_english_words,
        base_korean_spacing_units=base_korean_units,
    )


render_disclosure = render_onboarding


__all__ = [
    "EN_WORD_LIMIT",
    "KO_SPACING_LIMIT",
    "OnboardingDisclosure",
    "OnboardingRenderError",
    "render_disclosure",
    "render_onboarding",
]
