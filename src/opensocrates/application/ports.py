"""Typed dependency ports for application services.

Only protocols are defined here so the application layer can depend on
domain contracts without importing filesystem, host, or persistence code.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import TYPE_CHECKING, Protocol, TypeVar

from ..clock import Clock
from ..domain.models import (
    CapabilityProfile,
    CompiledContentBundle,
    EphemeralTurnState,
    JudgmentEvent,
    LocalMetric,
    TaskProjection,
    UserSettings,
)

if TYPE_CHECKING:
    from ..content.injection import AssembledInstruction
    from ..selector.artifacts import InstructionArtifact
    from ..selector.context import ContextKind, SelectorContextHandles, UntrustedContext
    from ..selector.models import SelectorLocale, SelectorRequest

T = TypeVar("T")


class SettingsRepository(Protocol):
    def load(self) -> UserSettings: ...

    def save(self, settings: UserSettings) -> None: ...


class TaskRepository(Protocol):
    def load_projection(self, task_id: str) -> TaskProjection | None: ...


class RecordRepository(Protocol):
    def append(self, event: JudgmentEvent) -> None: ...


class TurnStateRepository(Protocol):
    def issue(self, state: EphemeralTurnState) -> None: ...

    def load_by_raw_token(self, raw_token: str) -> EphemeralTurnState | None: ...

    def compare_and_swap(
        self, expected: EphemeralTurnState, replacement: EphemeralTurnState
    ) -> None: ...

    def delete(self, state: EphemeralTurnState) -> None: ...

    def sweep_expired(self, now: str) -> int: ...


class MetricsRepository(Protocol):
    def append(self, metric: LocalMetric) -> None: ...


class ContentRepository(Protocol):
    def load(self) -> CompiledContentBundle: ...


class HostAdapter(Protocol):
    def capabilities(self) -> CapabilityProfile: ...


class PermissionManager(Protocol):
    def ensure_owner_only(self, path: str) -> None: ...


class ReasoningSelector(Protocol):
    """Fresh internal selector boundary; SDK implementations stay outside application code."""

    def select(
        self,
        request: "SelectorRequest",
        context: "SelectorContextHandles",
        *,
        deadline_seconds: int,
        reasoning_effort: str,
    ) -> Mapping[str, object] | None:
        """Return an untrusted structured candidate for this request only."""


class SelectorContextAccessor(Protocol):
    """Read-only, on-demand context seam used only inside a selector adapter."""

    def read(
        self, kind: "ContextKind", handles: "SelectorContextHandles"
    ) -> "UntrustedContext | None":
        """Return untrusted current-turn context, or no value when it is unavailable."""


class CanonicalInstructionAssembler(Protocol):
    """Content-owned deterministic assembly boundary with no host-context input."""

    def known_method_ids(self) -> Collection[str]:
        """Return the current canonical selection catalog IDs."""

    def assemble(
        self, selected_reasoning_systems: tuple[str, ...], *, requested_locale: "SelectorLocale"
    ) -> "AssembledInstruction":
        """Return exact canonical instructions, names, and locale for a temporary file."""


class InstructionArtifactStore(Protocol):
    """Private temporary-file boundary for canonical reasoning instructions."""

    def create(
        self,
        session_id: str | None,
        turn_id: str | None,
        assembled: "AssembledInstruction",
    ) -> "InstructionArtifact": ...

    def latest_for_session(self, session_id: str | None) -> "InstructionArtifact | None": ...

    def delete_turn(self, session_id: str | None, turn_id: str | None) -> int: ...

    def delete_session(self, session_id: str | None) -> int: ...

    def sweep_expired(self) -> int: ...


__all__ = [
    "Clock",
    "CanonicalInstructionAssembler",
    "ContentRepository",
    "HostAdapter",
    "InstructionArtifactStore",
    "MetricsRepository",
    "PermissionManager",
    "RecordRepository",
    "ReasoningSelector",
    "SelectorContextAccessor",
    "SettingsRepository",
    "TaskRepository",
    "TurnStateRepository",
]
