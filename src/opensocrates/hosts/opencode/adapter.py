"""OpenCode adapter for capability and explicit-content composition.

The generated dependency-free JavaScript bridge owns the live stable
``chat.message`` boundary.  This Python adapter deliberately does not pretend
to parse a callback it never receives; it exposes the same canonical content
seam for diagnostics and native-skill fallback composition.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.models import CapabilityProfile
from ..prompt_only.adapter import PromptOnlyAdapter
from .capability import default_capability_profile


class OpenCodeAdapter(PromptOnlyAdapter):
    """Return canonical fallback context and the evidence-bounded host profile."""

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


__all__ = ["OpenCodeAdapter"]
