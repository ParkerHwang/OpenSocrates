"""Projection of the bundle-authored cross-examination fragment."""

from __future__ import annotations

from ..domain.models import CompiledContentBundle
from .framing_prompt import get_prompt_fragment


def cross_exam_fragment(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Return the reviewed strongest-objection/weakest-link guidance."""

    return get_prompt_fragment(bundle, locale, "cross_exam")


def build_cross_exam_prompt(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Compatibility builder alias for :func:`cross_exam_fragment`."""

    return cross_exam_fragment(bundle, locale)


project_cross_exam = cross_exam_fragment
build_cross_exam_fragment = cross_exam_fragment


__all__ = [
    "build_cross_exam_fragment",
    "build_cross_exam_prompt",
    "cross_exam_fragment",
    "project_cross_exam",
]
