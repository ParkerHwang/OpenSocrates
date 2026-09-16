"""Host-neutral protocols used by the runtime registry."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ..domain.models import CapabilityProfile


class HostAdapter(Protocol):
    """Minimum adapter surface required by the packaged hook boundary."""

    def capabilities(self) -> CapabilityProfile: ...

    def handle(
        self,
        native_input: Mapping[str, Any] | str | bytes | bytearray,
        *,
        event_name: str | None = None,
    ) -> Any: ...


__all__ = ["HostAdapter"]
