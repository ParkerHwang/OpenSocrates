"""Transient contracts for the Codex-only reasoning selector prototype.

These models deliberately do not implement persistence serialization.  They
can contain prompt and host metadata while a selector request is in flight, so
their representations redact every content-bearing field.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Mapping

from ..errors import IdentifierError
from ..ids import validate_method_id

SelectorLocale = Literal["en", "ko"]
DEFAULT_SELECTOR_DEADLINE_SECONDS = 30
MAX_SELECTOR_DEADLINE_SECONDS = 30
MAX_TRANSIENT_PROMPT_BYTES = 256 * 1024
MAX_TRANSIENT_INSTRUCTIONS_BYTES = 256 * 1024


class SelectorModelError(ValueError):
    """Raised when a transient selector contract is malformed."""


def _require_bounded_text(value: object, name: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value:
        raise SelectorModelError(f"{name} must be non-empty text")
    if "\x00" in value or len(value.encode("utf-8")) > maximum:
        raise SelectorModelError(f"{name} is not within the transient bound")
    return value


def _optional_metadata(value: object, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or "\x00" in value or len(value.encode("utf-8")) > 512:
        raise SelectorModelError(f"{name} is invalid transient metadata")
    return value


def _optional_path(value: object, name: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, (str, Path)):
        raise SelectorModelError(f"{name} must be a path or null")
    path = Path(value)
    if "\x00" in str(path):
        raise SelectorModelError(f"{name} is invalid")
    return path


def _method_ids(
    value: object, *, known_method_ids: frozenset[str] | None = None
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise SelectorModelError("selected_reasoning_systems must be a JSON array")
    selected: list[str] = []
    for item in value:
        try:
            method_id = validate_method_id(item)
        except (IdentifierError, ValueError) as error:
            raise SelectorModelError(
                "selected_reasoning_systems contains an invalid method ID"
            ) from error
        if known_method_ids is not None and method_id not in known_method_ids:
            raise SelectorModelError("selected_reasoning_systems contains an unknown method ID")
        selected.append(method_id)
    if len(set(selected)) != len(selected):
        raise SelectorModelError("selected_reasoning_systems must not repeat an ID")
    return tuple(selected)


def _validated_known_ids(value: object) -> frozenset[str]:
    if not isinstance(value, Collection) or isinstance(value, (str, bytes)):
        raise SelectorModelError("canonical content returned invalid method IDs")
    checked: set[str] = set()
    for item in value:
        try:
            checked.add(validate_method_id(item))
        except (IdentifierError, ValueError) as error:
            raise SelectorModelError("canonical content returned an invalid method ID") from error
    return frozenset(checked)


def _immutable_method_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise SelectorModelError("selected_reasoning_systems must be an immutable tuple")
    selected: list[str] = []
    for item in value:
        try:
            selected.append(validate_method_id(item))
        except (IdentifierError, ValueError) as error:
            raise SelectorModelError(
                "selected_reasoning_systems contains an invalid method ID"
            ) from error
    if len(set(selected)) != len(selected):
        raise SelectorModelError("selected_reasoning_systems must not repeat an ID")
    return tuple(selected)


def _decision_instructions(value: object) -> str:
    if not isinstance(value, str) or "\x00" in value:
        raise SelectorModelError("instructions must be text without NUL")
    if len(value.encode("utf-8")) > MAX_TRANSIENT_INSTRUCTIONS_BYTES:
        raise SelectorModelError("instructions exceed the transient bound")
    return value


def _validate_decision_combination(
    intervene: bool, selected_reasoning_systems: tuple[str, ...], instructions: str
) -> None:
    if intervene and (not selected_reasoning_systems or not instructions.strip()):
        raise SelectorModelError(
            "intervention requires selected reasoning systems and instructions"
        )
    if not intervene and (selected_reasoning_systems or instructions):
        raise SelectorModelError("non-intervention must not carry methods or instructions")


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class SelectorConfig:
    """Bounded selector policy values that do not contain host content."""

    deadline_seconds: int = DEFAULT_SELECTOR_DEADLINE_SECONDS
    transcript_access_enabled: bool = True

    def __post_init__(self) -> None:
        if (
            type(self.deadline_seconds) is not int
            or not 1 <= self.deadline_seconds <= MAX_SELECTOR_DEADLINE_SECONDS
        ):
            raise SelectorModelError("selector deadline must be between 1 and 30 seconds")
        if not isinstance(self.transcript_access_enabled, bool):
            raise SelectorModelError("transcript_access_enabled must be boolean")


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class SelectorRequest:
    """One transient UserPromptSubmit request; never a persistence model."""

    prompt: str = field(repr=False)
    transcript_path: Path | None = field(default=None, repr=False)
    cwd: Path | None = field(default=None, repr=False)
    session_id: str | None = field(default=None, repr=False)
    turn_id: str | None = field(default=None, repr=False)
    model: str | None = field(default=None, repr=False)
    transcript_referenced_file_paths: tuple[Path, ...] = field(default=(), repr=False)
    tool_data_handle: object | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_bounded_text(self.prompt, "prompt", maximum=MAX_TRANSIENT_PROMPT_BYTES)
        object.__setattr__(
            self, "transcript_path", _optional_path(self.transcript_path, "transcript_path")
        )
        object.__setattr__(self, "cwd", _optional_path(self.cwd, "cwd"))
        object.__setattr__(self, "session_id", _optional_metadata(self.session_id, "session_id"))
        object.__setattr__(self, "turn_id", _optional_metadata(self.turn_id, "turn_id"))
        object.__setattr__(self, "model", _optional_metadata(self.model, "model"))
        if not isinstance(self.transcript_referenced_file_paths, tuple):
            raise SelectorModelError("referenced-file handles must be an immutable tuple")
        paths = tuple(
            _optional_path(path, "transcript-referenced file")
            for path in self.transcript_referenced_file_paths
        )
        if any(path is None for path in paths):
            raise SelectorModelError("referenced-file handles must not be null")
        object.__setattr__(self, "transcript_referenced_file_paths", paths)

    def without_transcript_context(self) -> "SelectorRequest":
        """Return an equivalent request with opt-out transcript handles removed."""

        return replace(self, transcript_path=None, transcript_referenced_file_paths=())

    def __repr__(self) -> str:
        return "SelectorRequest(<transient-redacted>)"


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class RawSelectorCandidate:
    """Validated SDK candidate whose raw instructions must never be injected."""

    intervene: bool
    selected_reasoning_systems: tuple[str, ...]
    instructions: str = field(repr=False)

    def __repr__(self) -> str:
        return "RawSelectorCandidate(<redacted>)"


@dataclass(frozen=True, slots=True, kw_only=True, repr=False)
class SelectorDecision:
    """Validated file-reference decision eligible for one host-context injection."""

    intervene: bool
    selected_reasoning_systems: tuple[str, ...]
    instructions: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.intervene, bool):
            raise SelectorModelError("intervene must be boolean")
        selected = _immutable_method_ids(self.selected_reasoning_systems)
        instructions = _decision_instructions(self.instructions)
        _validate_decision_combination(self.intervene, selected, instructions)

    def __repr__(self) -> str:
        return (
            "SelectorDecision("
            f"intervene={self.intervene}, selected_reasoning_systems=<"
            f"{len(self.selected_reasoning_systems)} IDs>, instructions=<redacted>)"
        )


def validate_raw_candidate(
    candidate: object, *, known_method_ids: Collection[str]
) -> RawSelectorCandidate:
    """Strictly validate untrusted SDK output without making it injectable."""

    if not isinstance(candidate, Mapping):
        raise SelectorModelError("selector candidate must be an object")
    expected = {"intervene", "selected_reasoning_systems", "instructions"}
    if set(candidate) != expected:
        raise SelectorModelError("selector candidate must contain exactly three fields")
    intervene = candidate["intervene"]
    if type(intervene) is not bool:
        raise SelectorModelError("intervene must be boolean")
    known = _validated_known_ids(known_method_ids)
    selected = _method_ids(candidate["selected_reasoning_systems"], known_method_ids=known)
    instructions = candidate["instructions"]
    if not isinstance(instructions, str) or "\x00" in instructions:
        raise SelectorModelError("instructions must be text without NUL")
    if len(instructions.encode("utf-8")) > MAX_TRANSIENT_INSTRUCTIONS_BYTES:
        raise SelectorModelError("instructions exceed the transient bound")
    if intervene:
        if not selected or not instructions.strip():
            raise SelectorModelError("intervention requires methods and instructions")
    elif selected or instructions:
        raise SelectorModelError("non-intervention must not carry methods or instructions")
    return RawSelectorCandidate(
        intervene=intervene,
        selected_reasoning_systems=selected,
        instructions=instructions,
    )


__all__ = [
    "DEFAULT_SELECTOR_DEADLINE_SECONDS",
    "MAX_SELECTOR_DEADLINE_SECONDS",
    "RawSelectorCandidate",
    "SelectorConfig",
    "SelectorDecision",
    "SelectorLocale",
    "SelectorModelError",
    "SelectorRequest",
    "validate_raw_candidate",
]
