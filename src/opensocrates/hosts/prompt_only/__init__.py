"""Honest prompt-only host fallback."""

from .adapter import PromptOnlyAdapter, PromptOnlyHandleResult
from .capability import capability_profile, default_capability_profile

__all__ = [
    "PromptOnlyAdapter",
    "PromptOnlyHandleResult",
    "capability_profile",
    "default_capability_profile",
]
