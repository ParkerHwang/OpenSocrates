"""Small pure policy seams for the Codex-only selector prototype."""

from __future__ import annotations

from collections.abc import Collection
from typing import Protocol

from .models import SelectorLocale, SelectorModelError, SelectorRequest


class PromptLocalePolicy(Protocol):
    """Choose the requested authored-content locale from the current prompt."""

    def locale_for(self, request: SelectorRequest) -> SelectorLocale:
        """Return ``en`` or ``ko`` without retaining the prompt."""


class ReasoningEffortPolicy(Protocol):
    """Keep selector effort separate from model selection and SDK wiring."""

    def effort_for(self, request: SelectorRequest) -> str:
        """Return the approved selector reasoning effort."""


class CurrentPromptLocalePolicy:
    """Use Korean/English character counts; ties and other scripts fall back to English."""

    def locale_for(self, request: SelectorRequest) -> SelectorLocale:
        if not isinstance(request, SelectorRequest):
            raise SelectorModelError("locale policy requires a selector request")
        korean = 0
        english = 0
        for character in request.prompt:
            codepoint = ord(character)
            if 0xAC00 <= codepoint <= 0xD7A3:
                korean += 1
            elif (0x41 <= codepoint <= 0x5A) or (0x61 <= codepoint <= 0x7A):
                english += 1
        return "ko" if korean > english else "en"


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

    if requested not in {"en", "ko"}:
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
