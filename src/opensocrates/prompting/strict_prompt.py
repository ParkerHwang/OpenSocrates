"""Projection of the bundle-authored Strict second-pass fragment."""

from __future__ import annotations

from ..domain.models import CompiledContentBundle
from .framing_prompt import get_prompt_fragment


def strict_second_pass_fragment(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Return the conclusion-blinded Strict second-pass guidance."""

    return get_prompt_fragment(bundle, locale, "strict_second_pass")


def build_strict_prompt(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Compatibility builder alias for :func:`strict_second_pass_fragment`."""

    return strict_second_pass_fragment(bundle, locale)


project_strict_second_pass = strict_second_pass_fragment
build_strict_second_pass = strict_second_pass_fragment


__all__ = [
    "build_strict_prompt",
    "build_strict_second_pass",
    "project_strict_second_pass",
    "strict_second_pass_fragment",
]
