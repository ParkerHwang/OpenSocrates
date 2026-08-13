"""Cursor Agent Plugin adapter with no unproven hook or selector path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.models import CapabilityProfile
from ..prompt_only.adapter import PromptOnlyAdapter
from .capability import default_capability_profile


class CursorAdapter(PromptOnlyAdapter):
    """Return authored context for Cursor's native Agent Skill surface."""

    def __init__(
        self,
        *,
        bundle_path: str | Path | None = None,
        bundle: Any | None = None,
        profile: CapabilityProfile | None = None,
        locale: str = "en",
    ) -> None:
        super().__init__(
            bundle_path=bundle_path,
            bundle=bundle,
            profile=profile or default_capability_profile(),
            locale=locale,
        )


__all__ = ["CursorAdapter"]
