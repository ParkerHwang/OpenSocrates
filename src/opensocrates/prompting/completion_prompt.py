"""Projection of bundle-authored completion guidance.

Evidence, card, and completion rules intentionally share one canonical bundle
fragment.  This helper exposes the completion-focused projection without
copying or creating a second authored source.
"""

from __future__ import annotations

from ..domain.models import CompiledContentBundle
from .framing_prompt import get_prompt_fragment


def completion_fragment(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Return the canonical evidence/card/completion fragment unchanged."""

    return get_prompt_fragment(bundle, locale, "evidence_card_completion")


def build_completion_prompt(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Compatibility builder alias for :func:`completion_fragment`."""

    return completion_fragment(bundle, locale)


project_completion = completion_fragment
build_completion_fragment = completion_fragment


__all__ = [
    "build_completion_fragment",
    "build_completion_prompt",
    "completion_fragment",
    "project_completion",
]
