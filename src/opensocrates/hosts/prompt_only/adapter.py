"""Prompt-only adapter with explicit lifecycle limitations.

This adapter can return the compiled controller context for a prompt/skill
surface.  It has no persistence, no control-token handling, no method
activation observation, no Stop continuation, and no trace claim.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...content.loader import load_compiled_bundle
from ...domain.enums import EventType
from ...domain.models import CapabilityProfile, NormalizedEvent
from ..common import HostAction
from .capability import default_capability_profile


@dataclass(frozen=True, slots=True)
class PromptOnlyHandleResult:
    """Safe result for callers that want a uniform adapter-like object."""

    action: HostAction
    response: dict[str, object]
    diagnostics: tuple[str, ...] = ()
    status: str = "prompt_only"

    @property
    def stdout(self) -> str:
        return (
            json.dumps(self.response, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )


class PromptOnlyAdapter:
    """Return canonical context while making all lifecycle gaps explicit."""

    def __init__(
        self,
        *,
        bundle_path: str | Path | None = None,
        bundle: Any | None = None,
        profile: CapabilityProfile | None = None,
        locale: str = "en",
    ) -> None:
        self.bundle_path = Path(bundle_path) if bundle_path is not None else None
        self.bundle = bundle
        self.locale = locale if locale in {"en", "ko"} else "en"
        self._profile = profile or default_capability_profile()

    def capabilities(self) -> CapabilityProfile:
        return self._profile

    @property
    def capability_profile(self) -> CapabilityProfile:
        return self._profile

    def _context(self) -> str | None:
        bundle = self.bundle
        if bundle is None and self.bundle_path is not None:
            try:
                bundle = load_compiled_bundle(self.bundle_path)
            except Exception:
                bundle = None
        if bundle is None:
            return None
        fragments = getattr(bundle, "prompt_fragments", {})
        if not isinstance(fragments, Mapping):
            return None
        controller = fragments.get("controller")
        if not isinstance(controller, Mapping):
            return None
        value = controller.get(self.locale) or controller.get("en")
        return value if isinstance(value, str) and value.strip() else None

    def context_for(self, event: NormalizedEvent | None = None) -> HostAction:
        del event
        context = self._context()
        if context is None:
            return HostAction.no_op()
        try:
            return HostAction.add_context(context)
        except Exception:
            # Prompt-only context is best effort and must never turn a host
            # callback into a traceback or an oversized response.
            return HostAction.no_op()

    def handle(
        self,
        native_input: Mapping[str, Any] | str | bytes | bytearray,
        *,
        event_name: str | None = None,
    ) -> PromptOnlyHandleResult:
        del native_input, event_name
        return PromptOnlyHandleResult(action=self.context_for(), response={})

    def handle_event(self, event: NormalizedEvent) -> HostAction:
        if not isinstance(event, NormalizedEvent):
            return HostAction.no_op()
        if event.event_type in {
            EventType.SESSION_STARTED,
            EventType.USER_PROMPT_SUBMITTED,
            EventType.SKILL_INVOKED,
        }:
            return self.context_for(event)
        return HostAction.no_op()


__all__ = ["PromptOnlyAdapter", "PromptOnlyHandleResult"]
