#!/usr/bin/env python3
"""Bounded checks for the stable OpenCode bridge and native skill host."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from opensocrates.constants import CAPABILITY_KEYS
from opensocrates.domain.capability import validate_capability_profile
from opensocrates.domain.enums import CapabilityStatus, CapabilityTier, HostId
from opensocrates.hosts.opencode.adapter import OpenCodeAdapter
from opensocrates.hosts.opencode.capability import default_capability_profile
from opensocrates.hosts.registry import build_adapter, registered_hosts


def _assert_source_boundary(root: Path) -> None:
    host_root = root / "src" / "opensocrates" / "hosts" / "opencode"
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
    package = root / "build" / "generated" / "plugins" / "opencode"
    manifest = json.loads((package / "opencode-plugin.json").read_text(encoding="utf-8"))
    release = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["minimum_opencode_version"] == "1.18.18"
    assert manifest["stable_plugin_hook"] == "chat.message"
    assert manifest["beta_v2_api"] is False
    assert release["host"] == "opencode"
    assert release["launchers"] == []
    assert release["runtime_targets"] == []
    assert (package / "plugins" / "opensocrates.js").is_file()
    assert (package / "skills" / "opensocrates" / "SKILL.md").is_file()
    for forbidden in ("hooks", "bin", "runtime", "mcp.json"):
        assert not (package / forbidden).exists(), forbidden
    methods = package / "skills" / "opensocrates" / "references" / "methods"
    assert len(list(methods.glob("*.md"))) == 48


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    profile = validate_capability_profile(default_capability_profile())
    assert profile.host is HostId.OPENCODE_CLI
    assert profile.computed_tier is CapabilityTier.C
    assert set(profile.capabilities) == set(CAPABILITY_KEYS)
    assert profile.capabilities["prompt_context_injection"].status is CapabilityStatus.SUPPORTED
    assert profile.capabilities["method_skill_invocation"].status is CapabilityStatus.DEGRADED
    for key in ("local_record_write", "deterministic_trace_render"):
        assert profile.capabilities[key].status is CapabilityStatus.UNAVAILABLE

    assert isinstance(build_adapter("opencode", capability_profile=profile), OpenCodeAdapter)
    assert "opencode" in registered_hosts()
    _assert_source_boundary(root)
    _assert_generated_package(root)
    print("opencode-check: PASS tier=C stable-hook=chat.message runtime=0 methods=48")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
