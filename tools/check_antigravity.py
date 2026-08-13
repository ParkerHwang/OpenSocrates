#!/usr/bin/env python3
"""Bounded checks for the Antigravity explicit-skill host."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from opensocrates.constants import CAPABILITY_KEYS
from opensocrates.domain.capability import validate_capability_profile
from opensocrates.domain.enums import CapabilityStatus, CapabilityTier, HostId
from opensocrates.hosts.antigravity.adapter import AntigravityAdapter
from opensocrates.hosts.antigravity.capability import default_capability_profile
from opensocrates.hosts.codex.adapter import CodexAdapter
from opensocrates.hosts.registry import build_adapter, registered_hosts


def _assert_source_boundary(root: Path) -> None:
    host_root = root / "src" / "opensocrates" / "hosts" / "antigravity"
    forbidden = {"subprocess", "socket", "hosts.codex", "hosts.claude"}
    for source in host_root.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        tree = ast.parse(text)
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
    package = root / "build" / "generated" / "plugins" / "antigravity"
    manifest = json.loads((package / "plugin.json").read_text(encoding="utf-8"))
    release = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "opensocrates"
    assert release["host"] == "antigravity"
    assert release["launchers"] == []
    assert release["runtime_targets"] == []
    for forbidden in ("hooks", "bin", "runtime", "commands", "schemas"):
        assert not (package / forbidden).exists(), forbidden
    methods = package / "skills" / "opensocrates" / "references" / "methods"
    assert len(list(methods.glob("*.md"))) == 48


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    profile = validate_capability_profile(default_capability_profile())
    assert profile.host is HostId.ANTIGRAVITY_CLI
    assert profile.computed_tier is CapabilityTier.C
    assert set(profile.capabilities) == set(CAPABILITY_KEYS)
    assert profile.capabilities["method_skill_invocation"].status is CapabilityStatus.DEGRADED
    assert profile.capabilities["local_record_write"].status is CapabilityStatus.UNAVAILABLE
    for key, entry in profile.capabilities.items():
        if key not in {
            "method_skill_invocation",
            "local_record_write",
            "deterministic_trace_render",
            "rich_card_widget",
        }:
            assert entry.status is CapabilityStatus.UNKNOWN, key

    adapter = AntigravityAdapter(profile=profile)
    assert not isinstance(adapter, CodexAdapter)
    assert adapter.handle(b"arbitrary untrusted bytes").response == {}
    built = build_adapter("antigravity", capability_profile=profile)
    assert isinstance(built, AntigravityAdapter)
    assert "antigravity" in registered_hosts()

    _assert_source_boundary(root)
    _assert_generated_package(root)
    print("antigravity-check: PASS tier=C hooks=0 runtime=0 methods=48")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
