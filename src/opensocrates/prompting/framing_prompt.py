"""Projection of the bundle-authored framing prompt fragment.

This module contains no authored prompt prose.  It only selects the reviewed
``framing`` text from a validated :class:`CompiledContentBundle` for the
requested locale and phase.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..domain.enums import TaskState
from ..domain.models import CompiledContentBundle


class PromptFragmentError(ValueError):
    """A requested bundle fragment is absent or malformed."""


def get_prompt_fragment(bundle: CompiledContentBundle, locale: str, fragment_id: str) -> str:
    """Read one locale-specific prompt fragment without fallback or rewriting."""

    if not isinstance(bundle, CompiledContentBundle):
        raise PromptFragmentError("prompt projection requires a validated CompiledContentBundle")
    if locale not in {"en", "ko"}:
        raise PromptFragmentError(f"unsupported prompt locale: {locale!r}")
    if not isinstance(fragment_id, str) or not fragment_id:
        raise PromptFragmentError("prompt fragment ID must be non-empty text")
    if (
        not isinstance(bundle.content_revision, int)
        or isinstance(bundle.content_revision, bool)
        or bundle.content_revision < 1
    ):
        raise PromptFragmentError("bundle content revision is missing or invalid")
    fragments: Mapping[str, Any] = bundle.prompt_fragments
    if fragment_id not in fragments:
        raise PromptFragmentError(f"missing prompt fragment ID: {fragment_id}")
    localized = fragments[fragment_id]
    if not isinstance(localized, Mapping):
        raise PromptFragmentError(f"prompt fragment {fragment_id} has no locale map")
    if locale not in localized:
        raise PromptFragmentError(f"prompt fragment {fragment_id} has no {locale} revision")
    text = localized[locale]
    if not isinstance(text, str) or not text.strip():
        raise PromptFragmentError(f"prompt fragment {fragment_id}.{locale} is empty")
    return text


def framing_fragment(
    bundle: CompiledContentBundle,
    locale: str,
    *,
    phase: TaskState | str | None = None,
) -> str | None:
    """Project framing guidance when the current phase establishes framing.

    ``None`` is returned for later phases because injecting framing guidance at
    every event would violate the event-relevance and observation budgets.
    """

    if phase is not None:
        phase_value = getattr(phase, "value", phase)
        if phase_value not in {TaskState.NEW.value, TaskState.FRAMING.value}:
            return None
    return get_prompt_fragment(bundle, locale, "framing")


def build_framing_prompt(
    bundle: CompiledContentBundle,
    locale: str = "en",
    *,
    phase: TaskState | str | None = None,
) -> str | None:
    """Compatibility builder alias for :func:`framing_fragment`."""

    return framing_fragment(bundle, locale, phase=phase)


project_framing = framing_fragment
frame_prompt = framing_fragment
build_framing_fragment = framing_fragment


__all__ = [
    "PromptFragmentError",
    "build_framing_prompt",
    "build_framing_fragment",
    "frame_prompt",
    "framing_fragment",
    "get_prompt_fragment",
    "project_framing",
]
