"""Host-neutral protocols used by the runtime registry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..domain.models import CapabilityProfile, NormalizedEvent
from .common import HostAction


class HostAdapter(Protocol):
    """Minimum adapter surface required by the packaged hook boundary."""

    def capabilities(self) -> CapabilityProfile: ...

    def handle(
        self,
        native_input: Mapping[str, Any] | str | bytes | bytearray,
        *,
        event_name: str | None = None,
    ) -> Any: ...


class PromptOnlyAdapterProtocol(Protocol):
    """Prompt-only surface: context can be supplied, lifecycle cannot."""

    def capabilities(self) -> CapabilityProfile: ...

    def context_for(self, event: NormalizedEvent | None = None) -> HostAction: ...


__all__ = ["HostAdapter", "PromptOnlyAdapterProtocol"]
