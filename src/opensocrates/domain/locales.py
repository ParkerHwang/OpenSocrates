"""Closed locale choices and stateless script detection; no prompt retention."""

from __future__ import annotations

from typing import Literal

SupportedLocale = Literal["en", "ko", "zh", "ja"]
SUPPORTED_LOCALES = ("en", "ko", "zh", "ja")
LEGACY_LOCALES = frozenset({"en", "ko"})


def complete_locale_set(locales: object) -> bool:
    """Allow the complete legacy pair or complete current authored locale set."""
    return locales == LEGACY_LOCALES or locales == frozenset(SUPPORTED_LOCALES)


def _script_counts(prompt: str, count_ascii_digits: bool) -> tuple[bool, int, int, int]:
    korean = english = han = 0
    kana = False
    for character in prompt:
        codepoint = ord(character)
        if (
            0x3041 <= codepoint <= 0x3096
            or 0x30A1 <= codepoint <= 0x30FA
            or 0xFF66 <= codepoint <= 0xFF9D
        ):
            kana = True
        elif 0xAC00 <= codepoint <= 0xD7A3:
            korean += 1
        elif (
            0x3400 <= codepoint <= 0x4DBF
            or 0x4E00 <= codepoint <= 0x9FFF
            or 0x20000 <= codepoint <= 0x323AF
        ):
            han += 1
        elif character.isascii() and (
            character.isalpha() or (count_ascii_digits and character.isdigit())
        ):
            english += 1
    return kana, korean, english, han


def detect_prompt_locale(
    prompt: str,
    *,
    explicit_locale: SupportedLocale | None = None,
    settings_locale: SupportedLocale | None = None,
    count_ascii_digits: bool = True,
) -> SupportedLocale:
    """Prefer trusted choices, then Kana, dominant Hangul/Han, then English.

    Han-only text is ambiguous between Chinese and Japanese and defaults to zh;
    callers can supply ja explicitly. Unknown scripts and ties default to en.
    This recognizes scripts, not instructions to change locale inside a source.
    """
    if not isinstance(prompt, str):
        raise ValueError("current prompt must be text")
    for preference in (explicit_locale, settings_locale):
        if preference is not None:
            if preference not in SUPPORTED_LOCALES:
                raise ValueError("locale preference is unsupported")
            return preference
    kana, korean, english, han = _script_counts(prompt, count_ascii_digits)
    if kana:
        return "ja"
    if korean > max(english, han):
        return "ko"
    if han > max(english, korean):
        return "zh"
    return "en"
