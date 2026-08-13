#!/usr/bin/env python3
"""Bounded checks for the Grok Build content-first host."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

from opensocrates.constants import CAPABILITY_KEYS
from opensocrates.domain.capability import validate_capability_profile
from opensocrates.domain.enums import (
    CapabilityEvidenceKind,
    CapabilityStatus,
    CapabilityTier,
    HostId,
)
from opensocrates.domain.models import CapabilityProfile
from opensocrates.hosts.codex.adapter import CodexAdapter
from opensocrates.hosts.grok.adapter import GrokAdapter
from opensocrates.hosts.grok.capability import default_capability_profile
from opensocrates.hosts.grok.contracts import (
    MAX_GROK_HOOK_PAYLOAD_BYTES,
    GrokHookContractError,
    parse_sanitized_hook_envelope,
)
from opensocrates.hosts.registry import build_adapter, registered_hosts


def _assert_source_boundary(root: Path) -> None:
    host_root = root / "src" / "opensocrates" / "hosts" / "grok"
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
    package = root / "build" / "generated" / "plugins" / "grok"
    manifest = json.loads((package / "plugin.json").read_text(encoding="utf-8"))
    release = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "opensocrates"
    assert manifest["skills"] == "./skills"
    assert set(manifest) == {
        "author",
        "description",
        "homepage",
        "license",
        "name",
        "repository",
        "skills",
        "version",
    }
    assert release["host"] == "grok"
    assert release["capability_evidence"]["status"] == "verified"
    assert release["launchers"] == []
    assert release["runtime_targets"] == []
    for forbidden in ("hooks", "bin", "runtime", "commands", "agents", ".mcp.json"):
        assert not (package / forbidden).exists(), forbidden
    skill_root = package / "skills"
    assert [path.name for path in skill_root.iterdir() if path.is_dir()] == ["opensocrates"]
    skill = (skill_root / "opensocrates" / "SKILL.md").read_text(encoding="utf-8")
    assert "disable-model-invocation: false" in skill
    assert "/opensocrates" in skill
    methods = skill_root / "opensocrates" / "references" / "methods"
    assert len(list(methods.glob("*.md"))) == 48

    grok = shutil.which("grok")
    if grok is not None:
        completed = subprocess.run(
            [grok, "plugin", "validate", str(package)],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr


def _assert_evidence_alignment(root: Path, profile: CapabilityProfile) -> None:
    """Tie the shipped capability claim to the recorded compatibility probe.

    The release gate reads `capability_evidence` out of the package generator,
    so on its own that claim is self-asserted. These checks make the claim fail
    whenever it drifts from the privacy-safe evidence record, from the observed
    package inventory, or from the capability profile the product reports.
    """

    evidence = json.loads(
        (root / "docs" / "evidence" / "grok-build-1.0.3-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    package = root / "build" / "generated" / "plugins" / "grok"
    release = json.loads((package / "release-manifest.json").read_text(encoding="utf-8"))
    probe_id = evidence["probe_id"]
    assert release["capability_evidence"]["probe_id"] == probe_id
    for key, entry in profile.capabilities.items():
        expected = probe_id if entry.evidence_kind is CapabilityEvidenceKind.LOCAL_PROBE else None
        assert entry.live_probe_id == expected, key

    inventory = evidence["package"]
    skill_root = package / "skills"
    assert inventory["public_skills"] == len([p for p in skill_root.iterdir() if p.is_dir()])
    methods = skill_root / "opensocrates" / "references" / "methods"
    assert inventory["internal_methods"] == len(list(methods.glob("*.md")))
    for surface, recorded in (
        ("hooks", "hooks"),
        ("commands", "commands"),
        ("agents", "agents"),
        ("runtime", "native_runtimes"),
    ):
        assert inventory[recorded] == 0 and not (package / surface).exists(), surface
    assert inventory["mcp_servers"] == 0
    assert not any((package / name).exists() for name in ("mcp.json", ".mcp.json"))

    # Every supported claim must rest on a recorded live observation, and no
    # injection claim may outrun hook output that was never model-visible.
    observations = evidence["observations"]
    supported = {
        key
        for key, entry in profile.capabilities.items()
        if entry.status is CapabilityStatus.SUPPORTED
    }
    assert supported == {"method_skill_invocation", "model_initiated_method_skill_activation"}
    assert observations["headless_explicit_skill"] is True
    assert observations["headless_native_auto_skill_same_turn"] is True
    assert observations["passive_stdout_model_visible"] is False
    assert observations["structured_additional_context_model_visible"] is False
    assert observations["installed_plugin_hooks_activated"] is False


def _assert_probe_contracts(root: Path) -> None:
    fixtures = root / "src" / "opensocrates" / "hosts" / "contracts" / "fixtures" / "grok"
    events = {
        parse_sanitized_hook_envelope(path.read_bytes()).event
        for path in sorted(fixtures.glob("*.json"))
    }
    assert events == {
        "post_compact",
        "post_tool_use",
        "pre_compact",
        "pre_tool_use",
        "session_start",
        "stop",
        "subagent_start",
        "subagent_stop",
        "user_prompt_submit",
    }
    malformed = [
        b"not-json",
        b"[]",
        b'{"hookEventName":"future_event"}',
        json.dumps(
            {
                "hookEventName": "user_prompt_submit",
                "sessionId": "s",
                "cwd": "/workspace",
                "workspaceRoot": "/workspace",
                "timestamp": "t",
                "prompt": {"adversarial": True},
            }
        ).encode(),
        b"{" + b" " * MAX_GROK_HOOK_PAYLOAD_BYTES + b"}",
    ]
    for payload in malformed:
        try:
            parse_sanitized_hook_envelope(payload)
        except GrokHookContractError:
            continue
        raise AssertionError("malformed Grok probe payload was accepted")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    profile = validate_capability_profile(default_capability_profile())
    assert profile.host is HostId.GROK_BUILD
    assert profile.computed_tier is CapabilityTier.C
    assert set(profile.capabilities) == set(CAPABILITY_KEYS)
    assert profile.capabilities["prompt_context_injection"].status is CapabilityStatus.DEGRADED
    for key in ("method_skill_invocation", "model_initiated_method_skill_activation"):
        assert profile.capabilities[key].status is CapabilityStatus.SUPPORTED
    for key in (
        "post_tool_observation",
        "bounded_completion_continuation",
        "compaction_reinjection",
        "local_record_write",
        "deterministic_trace_render",
    ):
        assert profile.capabilities[key].status is CapabilityStatus.UNAVAILABLE

    adapter = GrokAdapter(profile=profile)
    assert not isinstance(adapter, CodexAdapter)
    assert adapter.handle(b"arbitrary untrusted bytes").response == {}
    built = build_adapter("grok", capability_profile=profile)
    assert isinstance(built, GrokAdapter)
    assert "grok" in registered_hosts()

    _assert_source_boundary(root)
    _assert_generated_package(root)
    _assert_evidence_alignment(root, profile)
    _assert_probe_contracts(root)
    validation = "pass" if shutil.which("grok") is not None else "unavailable"
    print(f"grok-check: PASS tier=C hooks=0 runtime=0 methods=48 native_validation={validation}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
