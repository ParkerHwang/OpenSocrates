"""Closed locale choices and stateless script detection; no prompt retention."""

from __future__ import annotations

from typing import Literal

SupportedLocale = Literal["en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th"]
SUPPORTED_LOCALES = ("en", "ko", "zh", "ja", "fr", "de", "it", "es", "pt", "th")
LEGACY_LOCALES = frozenset({"en", "ko"})
V151_LOCALES = frozenset({"en", "ko", "zh", "ja"})


def complete_locale_set(locales: object) -> bool:
    """Allow the complete v1.5.0/v1.5.1 sets or complete current authored locale set."""
    return locales in (LEGACY_LOCALES, V151_LOCALES, frozenset(SUPPORTED_LOCALES))


def _script_counts(prompt: str, count_ascii_digits: bool) -> tuple[bool, int, int, int, int]:
    korean = english = han = thai = 0
    kana = False
    for character in prompt:
        codepoint = ord(character)
        if (
            0x3041 <= codepoint <= 0x3096
            or 0x30A1 <= codepoint <= 0x30FA
            or 0xFF66 <= codepoint <= 0xFF9D
        ):
            kana = True
        elif 0x0E01 <= codepoint <= 0x0E3A or 0x0E40 <= codepoint <= 0x0E4E:
            thai += 1
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
    return kana, korean, english, han, thai


def detect_prompt_locale(
    prompt: str,
    *,
    explicit_locale: SupportedLocale | None = None,
    settings_locale: SupportedLocale | None = None,
    count_ascii_digits: bool = True,
) -> SupportedLocale:
    """Prefer trusted choices, then Kana, dominant Thai/Hangul/Han, then English.

    Han-only text is ambiguous between Chinese and Japanese and defaults to zh;
    callers can supply ja explicitly. Unknown scripts and ties default to en.
    Latin-script European languages require a trusted explicit or saved preference.
    This recognizes scripts, not instructions to change locale inside a source.
    """
    if not isinstance(prompt, str):
        raise ValueError("current prompt must be text")
    for preference in (explicit_locale, settings_locale):
        if preference is not None:
            if preference not in SUPPORTED_LOCALES:
                raise ValueError("locale preference is unsupported")
            return preference
    kana, korean, english, han, thai = _script_counts(prompt, count_ascii_digits)
    if kana:
        return "ja"
    if thai > max(english, korean, han):
        return "th"
    if korean > max(english, han, thai):
        return "ko"
    if han > max(english, korean, thai):
        return "zh"
    return "en"
