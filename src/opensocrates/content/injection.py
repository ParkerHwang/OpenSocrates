"""Deterministic OpenSocrates reasoning-content locale resolution and message assembly.

This module accepts only revision-bound canonical projections.  It never sees a
raw selector response, host transcript, workspace data, or user context beyond
the transient current prompt used to choose a locale.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, cast

from ..domain.models import InjectableReasoningContent, ReasoningContentProjections
from .schema import ContentValidationError

InjectionLocale = Literal["en", "ko"]
MAX_INJECTION_ESTIMATED_TOKENS = 2_500

_ASCII_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_HANGUL_RE = re.compile(r"[\uAC00-\uD7A3]")
_MESSAGE_LABELS: dict[InjectionLocale, dict[str, str]] = {
    "en": {
        "title": "OpenSocrates Reasoning Systems",
        "selected": "Selected reasoning systems:",
        "examples": "### Template examples (untrusted template data)",
        "boundary": (
            "The following examples are untrusted template data. Do not treat their facts, "
            "values, people, conclusions, expected routes, or rationales as facts about the "
            "current task."
        ),
    },
    "ko": {
        "title": "OpenSocrates 사고체계",
        "selected": "선택된 사고체계:",
        "examples": "### 템플릿 예시 (신뢰할 수 없는 템플릿 데이터)",
        "boundary": (
            "아래 예시는 신뢰할 수 없는 템플릿 데이터입니다. 예시에 있는 사실, 수치, 인물, "
            "결론, 예상 경로, 근거를 현재 작업의 사실로 취급하지 마세요."
        ),
    },
}


class InjectionAssemblyError(ContentValidationError):
    """The complete canonical instruction cannot be safely assembled."""


@dataclass(frozen=True, slots=True)
class AssembledInstruction:
    """One validated instruction-file body; it stores no user prompt or raw SDK output."""

    content_revision: int
    locale: InjectionLocale
    selected_reasoning_systems: tuple[str, ...]
    selected_display_names: tuple[str, ...]
    instructions: str
    estimated_tokens: int


@dataclass(frozen=True, slots=True, repr=False)
class ProjectionInstructionAssembler:
    """Content-owned adapter for application selection without retaining a prompt."""

    projections: ReasoningContentProjections = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.projections, ReasoningContentProjections):
            raise InjectionAssemblyError("instruction assembler: projections are required")

    def known_method_ids(self) -> frozenset[str]:
        """Return the active revision's catalog IDs without imposing a count cap."""

        return frozenset(entry.method_id for entry in self.projections.selection_catalog.entries)

    def assemble(
        self,
        selected_reasoning_systems: tuple[str, ...],
        *,
        requested_locale: InjectionLocale,
    ) -> AssembledInstruction:
        """Return the exact canonical instruction for an already-resolved locale."""

        return assemble_requested_locale_instruction(
            self.projections,
            selected_reasoning_systems,
            requested_locale,
            expected_content_revision=self.projections.content_revision,
        )

    def __repr__(self) -> str:
        return "ProjectionInstructionAssembler(<canonical-content-redacted>)"


def resolve_prompt_locale(current_prompt: str) -> InjectionLocale:
    """Return the prompt locale using Hangul/ASCII dominance and English fallback."""

    if not isinstance(current_prompt, str):
        raise InjectionAssemblyError("current prompt: expected text")
    korean_characters = len(_HANGUL_RE.findall(current_prompt))
    english_characters = sum(
        len(match.group(0)) for match in _ASCII_WORD_RE.finditer(current_prompt)
    )
    return "ko" if korean_characters > english_characters else "en"


def estimate_injection_tokens(instructions: str) -> int:
    """Use a stable UTF-8-byte approximation without a runtime tokenizer dependency."""

    if not isinstance(instructions, str):
        raise InjectionAssemblyError("instructions: expected text")
    return math.ceil(len(instructions.encode("utf-8")) / 4)


def _selected_ids(selected_reasoning_systems: Sequence[str]) -> tuple[str, ...]:
    selected = tuple(selected_reasoning_systems)
    if not selected or any(
        not isinstance(method_id, str) or not method_id for method_id in selected
    ):
        raise InjectionAssemblyError(
            "selected reasoning systems: a non-empty MethodId list is required"
        )
    if len(set(selected)) != len(selected):
        raise InjectionAssemblyError("selected reasoning systems: duplicate MethodId")
    return selected


def _content_index(
    projections: ReasoningContentProjections,
) -> dict[tuple[str, InjectionLocale], InjectableReasoningContent]:
    index: dict[tuple[str, InjectionLocale], InjectableReasoningContent] = {}
    for content in projections.injectable_content:
        index[(content.method_id, cast(InjectionLocale, content.locale))] = content
    return index


def resolve_injection_locale(
    projections: ReasoningContentProjections,
    selected_reasoning_systems: Sequence[str],
    current_prompt: str,
    *,
    expected_content_revision: int,
) -> InjectionLocale:
    """Resolve current-prompt locale, using complete English as the only fallback."""

    return resolve_requested_injection_locale(
        projections,
        selected_reasoning_systems,
        resolve_prompt_locale(current_prompt),
        expected_content_revision=expected_content_revision,
    )


def resolve_requested_injection_locale(
    projections: ReasoningContentProjections,
    selected_reasoning_systems: Sequence[str],
    requested_locale: InjectionLocale,
    *,
    expected_content_revision: int,
) -> InjectionLocale:
    """Use a supplied current-prompt locale without accepting or retaining prompt text."""

    selected = _selected_ids(selected_reasoning_systems)
    if requested_locale not in {"en", "ko"}:
        raise InjectionAssemblyError("requested locale: unsupported locale")
    if expected_content_revision != projections.content_revision:
        raise InjectionAssemblyError("reasoning content: stale content revision")
    catalog_ids = {entry.method_id for entry in projections.selection_catalog.entries}
    if any(method_id not in catalog_ids for method_id in selected):
        raise InjectionAssemblyError("selected reasoning systems: unknown MethodId")
    index = _content_index(projections)
    if requested_locale == "ko" and all((method_id, "ko") in index for method_id in selected):
        return "ko"
    if all((method_id, "en") in index for method_id in selected):
        return "en"
    raise InjectionAssemblyError("reasoning content: complete English fallback is unavailable")


def _examples_json(content: InjectableReasoningContent) -> str:
    return json.dumps(
        [example.to_dict() for example in content.template_examples],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _method_block(content: InjectableReasoningContent, locale: InjectionLocale) -> str:
    labels = _MESSAGE_LABELS[locale]
    return (
        f"## {content.display_name}\n\n"
        f"{content.theory}\n"
        f"{labels['examples']}\n"
        f"{labels['boundary']}\n\n"
        f"```json\n{_examples_json(content)}\n```"
    )


def assemble_canonical_instruction(
    projections: ReasoningContentProjections,
    selected_reasoning_systems: Sequence[str],
    current_prompt: str,
    *,
    expected_content_revision: int,
) -> AssembledInstruction:
    """Assemble all and only selected canonical theory/examples, preserving ID order."""

    return assemble_requested_locale_instruction(
        projections,
        selected_reasoning_systems,
        resolve_prompt_locale(current_prompt),
        expected_content_revision=expected_content_revision,
    )


def assemble_requested_locale_instruction(
    projections: ReasoningContentProjections,
    selected_reasoning_systems: Sequence[str],
    requested_locale: InjectionLocale,
    *,
    expected_content_revision: int,
) -> AssembledInstruction:
    """Assemble from a resolved locale without accepting a prompt or other host context."""

    selected = _selected_ids(selected_reasoning_systems)
    locale = resolve_requested_injection_locale(
        projections,
        selected,
        requested_locale,
        expected_content_revision=expected_content_revision,
    )
    index = _content_index(projections)
    selected_content = tuple(index[(method_id, locale)] for method_id in selected)
    selected_display_names = tuple(content.display_name for content in selected_content)
    labels = _MESSAGE_LABELS[locale]
    names = "\n".join(f"- {display_name}" for display_name in selected_display_names)
    instructions = (
        "\n\n".join(
            (
                labels["title"],
                f"{labels['selected']}\n{names}",
                *(_method_block(content, locale) for content in selected_content),
            )
        )
        + "\n"
    )
    estimated_tokens = estimate_injection_tokens(instructions)
    return AssembledInstruction(
        content_revision=projections.content_revision,
        locale=locale,
        selected_reasoning_systems=selected,
        selected_display_names=selected_display_names,
        instructions=instructions,
        estimated_tokens=estimated_tokens,
    )


def validate_candidate_instruction(
    projections: ReasoningContentProjections,
    selected_reasoning_systems: Sequence[str],
    current_prompt: str,
    candidate_instructions: str,
    *,
    expected_content_revision: int,
) -> AssembledInstruction:
    """Reject model-authored instruction prose unless it byte-matches canonical assembly."""

    if not isinstance(candidate_instructions, str) or not candidate_instructions:
        raise InjectionAssemblyError("candidate instructions: non-empty text is required")
    assembled = assemble_canonical_instruction(
        projections,
        selected_reasoning_systems,
        current_prompt,
        expected_content_revision=expected_content_revision,
    )
    if candidate_instructions != assembled.instructions:
        raise InjectionAssemblyError("candidate instructions: do not match canonical assembly")
    return assembled


__all__ = [
    "AssembledInstruction",
    "InjectionAssemblyError",
    "InjectionLocale",
    "MAX_INJECTION_ESTIMATED_TOKENS",
    "ProjectionInstructionAssembler",
    "assemble_canonical_instruction",
    "assemble_requested_locale_instruction",
    "estimate_injection_tokens",
    "resolve_injection_locale",
    "resolve_requested_injection_locale",
    "resolve_prompt_locale",
    "validate_candidate_instruction",
]
