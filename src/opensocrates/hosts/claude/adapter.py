"""Claude host adapter over the shared selector-safe command-hook contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.enums import HostId
from ..codex.adapter import CodexAdapter, CodexAdapterConfig, CodexHandleResult


@dataclass(frozen=True, slots=True)
class ClaudeAdapterConfig(CodexAdapterConfig):
    """Claude-specific defaults for the shared bounded hook adapter."""

    host: HostId = HostId.CLAUDE_CODE


ClaudeHandleResult = CodexHandleResult


class ClaudeAdapter(CodexAdapter):
    """Selector-only Claude Code/Cowork adapter.

    Claude Code and Codex expose the same documented lifecycle envelope and
    ``additionalContext`` response shape for the events used by OpenSocrates.
    The shared parser remains host-tagged and this wrapper prevents callers
    from accidentally composing the Claude package with a Codex host ID.
    """

    def __init__(self, config: ClaudeAdapterConfig | None = None, **kwargs: Any) -> None:
        super().__init__(config or ClaudeAdapterConfig(), **kwargs)


__all__ = ["ClaudeAdapter", "ClaudeAdapterConfig", "ClaudeHandleResult"]
