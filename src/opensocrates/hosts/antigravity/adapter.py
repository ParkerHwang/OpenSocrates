"""Antigravity explicit-skill adapter.

The v1.2 Antigravity integration deliberately has no native hook parser or
selector subprocess.  The generated plugin exposes authored OpenSocrates
content as one Agent Skill; this adapter exists for capability and diagnostic
composition without pretending that a host callback was observed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.models import CapabilityProfile
from ..prompt_only.adapter import PromptOnlyAdapter
from .capability import default_capability_profile


class AntigravityAdapter(PromptOnlyAdapter):
    """Return bounded authored context for an explicit Antigravity skill."""

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


__all__ = ["AntigravityAdapter"]
