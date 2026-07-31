"""Projection of bundle-authored evidence/card/completion guidance."""

from __future__ import annotations

from ..domain.models import CompiledContentBundle
from .framing_prompt import get_prompt_fragment


def evidence_fragment(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Return the reviewed evidence/card/completion fragment for ``locale``."""

    return get_prompt_fragment(bundle, locale, "evidence_card_completion")


def build_evidence_prompt(bundle: CompiledContentBundle, locale: str = "en") -> str:
    """Compatibility builder alias for :func:`evidence_fragment`."""

    return evidence_fragment(bundle, locale)


project_evidence = evidence_fragment
build_evidence_fragment = evidence_fragment


__all__ = [
    "build_evidence_fragment",
    "build_evidence_prompt",
    "evidence_fragment",
    "project_evidence",
]
