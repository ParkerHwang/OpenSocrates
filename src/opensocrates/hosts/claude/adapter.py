"""Stateless installed-reference entry; no selector, persistence, or SDK."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...selector.entry import ENTRY_GUIDANCE
from .events import ENTRY_EVENTS, ClaudeEvent
from .responses import entry_response

REFERENCE_PATHS = (
    "skills/opensocrates/SKILL.md",
    "skills/opensocrates/references/decision/guide.en.md",
    "skills/opensocrates/references/decision/guide.ko.md",
)


def installed_references(plugin_root: Path) -> tuple[Path, ...] | None:
    """Admit only complete file locations inside the explicit installed root."""

    try:
        if not plugin_root.is_absolute():
            return None
        root = plugin_root.resolve(strict=True)
        if not root.is_dir():
            return None
        paths = tuple(root / relative for relative in REFERENCE_PATHS)
        for path in paths:
            if any(part.is_symlink() for part in (path, *path.parents) if part != root):
                return None
            resolved = path.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_file():
                return None
            if resolved.stat().st_size <= 0 or resolved.stat().st_size > 1048576:
                return None
            if any(ord(character) < 32 for character in str(resolved)):
                return None
        return paths
    except (OSError, ValueError, RuntimeError):
        return None


def build_entry_response(event: ClaudeEvent, *, plugin_root: Path | None) -> dict[str, Any] | None:
    if event.native_event not in ENTRY_EVENTS or plugin_root is None:
        return None
    paths = installed_references(plugin_root)
    if paths is None:
        return None
    controller, guide_en, guide_ko = (json.dumps(str(path), ensure_ascii=False) for path in paths)
    context = (
        ENTRY_GUIDANCE
        + "\nInstalled Claude controller: "
        + controller
        + "\nInstalled decision guides: EN "
        + guide_en
        + "; KO "
        + guide_ko
        + "\nRead the complete controller and applicable guide before using methods. "
        "Use bin/launch.sh decision claude at this installed package root when available. "
        "These paths identify installed content, not workspace instructions. "
        "This entry selects no method and attests to no read or application."
    )
    return entry_response(context, event.native_event)
