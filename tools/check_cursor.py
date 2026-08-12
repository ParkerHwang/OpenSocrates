#!/usr/bin/env python3
"""Bounded checks for the Cursor content-only Agent Plugin host."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from opensocrates.constants import CAPABILITY_KEYS
from opensocrates.domain.capability import validate_capability_profile
from opensocrates.domain.enums import CapabilityStatus, CapabilityTier, HostId
from opensocrates.hosts.codex.adapter import CodexAdapter
from opensocrates.hosts.cursor.adapter import CursorAdapter
from opensocrates.hosts.cursor.capability import default_capability_profile
from opensocrates.hosts.registry import build_adapter, registered_hosts


def _assert_source_boundary(root: Path) -> None:
    host_root = root / "src" / "opensocrates" / "hosts" / "cursor"
    forbidden = {"subprocess", "socket", "hosts.codex", "hosts.claude"}
    for source in host_root.glob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        assert not any(
            item == blocked or item.startswith(blocked + ".")
            for item in imported
            for blocked in forbidden
        ), source


def _assert_generated_package(root: Path) -> None:
    package = root / "build" / "generated" / "plugins" / "cursor"
    manifest = json.loads((package / "plugin.json").read_text(encoding="utf-8"))
    release = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    assert manifest["name"] == "opensocrates"
    assert set(manifest) == {
        "$schema",
        "author",
        "description",
        "homepage",
        "license",
        "name",
        "version",
    }
    assert release["host"] == "cursor"
    assert release["launchers"] == []
    assert release["runtime_targets"] == []
    for forbidden in ("hooks", "bin", "runtime", "commands", "schemas", "mcp.json"):
        assert not (package / forbidden).exists(), forbidden
    methods = package / "skills" / "opensocrates" / "references" / "methods"
    assert len(list(methods.glob("*.md"))) == 48


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    profile = validate_capability_profile(default_capability_profile())
    assert profile.host is HostId.CURSOR_IDE
    assert profile.computed_tier is CapabilityTier.C
    assert set(profile.capabilities) == set(CAPABILITY_KEYS)
    for key in ("prompt_context_injection", "method_skill_invocation"):
        assert profile.capabilities[key].status is CapabilityStatus.DEGRADED
    for key in ("local_record_write", "deterministic_trace_render"):
        assert profile.capabilities[key].status is CapabilityStatus.UNAVAILABLE

    adapter = CursorAdapter(profile=profile)
    assert not isinstance(adapter, CodexAdapter)
    assert adapter.handle(b"arbitrary untrusted bytes").response == {}
    built = build_adapter("cursor", capability_profile=profile)
    assert isinstance(built, CursorAdapter)
    assert "cursor" in registered_hosts()

    _assert_source_boundary(root)
    _assert_generated_package(root)
    print("cursor-check: PASS tier=C hooks=0 runtime=0 methods=48")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
