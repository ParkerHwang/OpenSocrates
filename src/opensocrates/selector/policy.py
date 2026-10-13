"""Small pure policy seams for the Codex-only selector prototype."""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from ..domain.locales import detect_prompt_locale
from .models import SelectorLocale, SelectorModelError, SelectorRequest


class PromptLocalePolicy(Protocol):
    """Choose the requested authored-content locale from the current prompt."""

    def locale_for(self, request: SelectorRequest) -> SelectorLocale:
        """Return a supported locale without retaining the prompt."""


class ReasoningEffortPolicy(Protocol):
    """Keep selector effort separate from model selection and SDK wiring."""

    def effort_for(self, request: SelectorRequest) -> str:
        """Return the approved selector reasoning effort."""


class CurrentPromptLocalePolicy:
    """Prefer trusted locale settings; otherwise detect Kana, Hangul, Han, or English."""

    def locale_for(self, request: SelectorRequest) -> SelectorLocale:
        if not isinstance(request, SelectorRequest):
            raise SelectorModelError("locale policy requires a selector request")
        try:
            return detect_prompt_locale(
                request.prompt,
                explicit_locale=request.locale_preference,
                settings_locale=request.settings_locale_preference,
                count_ascii_digits=False,
            )
        except ValueError as error:
            raise SelectorModelError(str(error)) from error


class MediumReasoningEffortPolicy:
    """The approved policy seam: selector effort is always medium, never a model name."""

    def effort_for(self, request: SelectorRequest) -> str:
        if not isinstance(request, SelectorRequest):
            raise SelectorModelError("effort policy requires a selector request")
        return "medium"


def locale_with_english_fallback(
    requested: SelectorLocale, available_locales: Collection[str]
) -> SelectorLocale:
    """Return the requested locale when complete, otherwise English when complete."""

    if requested not in {"en", "ko", "zh", "ja"}:
        raise SelectorModelError("requested locale is unsupported")
    available = frozenset(available_locales)
    if requested in available:
        return requested
    if "en" in available:
        return "en"
    raise SelectorModelError("canonical content has no complete English fallback")


__all__ = [
    "CurrentPromptLocalePolicy",
    "MediumReasoningEffortPolicy",
    "PromptLocalePolicy",
    "ReasoningEffortPolicy",
    "locale_with_english_fallback",
]
