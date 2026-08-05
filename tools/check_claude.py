#!/usr/bin/env python3
"""Offline contract checks for the Claude Code and Cowork integration."""

from __future__ import annotations

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from opensocrates.content import ProjectionInstructionAssembler, load_reasoning_content_projections
from opensocrates.hooks.entrypoint import parse_hook_arguments
from opensocrates.hosts.claude.adapter import ClaudeAdapter, ClaudeAdapterConfig
from opensocrates.hosts.claude.commands import build_hooks
from opensocrates.selector import (
    InstructionFileStore,
    SelectorApplication,
    SelectorConfig,
    SelectorRequest,
    handles_for_request,
)
from opensocrates.selector.claude_cli import (
    ClaudeCliReasoningSelector,
    _candidate_from_cli_output,
    _selector_environment,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[tuple[str, Callable[[], None]]] = []


def check(name: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def decorate(function: Callable[[], None]) -> Callable[[], None]:
        CHECKS.append((name, function))
        return function

    return decorate


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def projections():
    return load_reasoning_content_projections(
        ROOT / "content" / "compiled-reasoning-content.bundle.json"
    )


class FakeProcess:
    instances: list["FakeProcess"] = []

    def __init__(self, command: list[str], **kwargs: object) -> None:
        self.command = command
        self.kwargs = kwargs
        self.pid = 999_999_999
        self.returncode: int | None = None
        self.payload = b""
        self.__class__.instances.append(self)

    def communicate(self, payload: bytes, timeout: int) -> tuple[bytes, bytes]:
        require(timeout == 30, "selector timeout was not bounded")
        self.payload = payload
        self.returncode = 0
        candidate = {
            "intervene": True,
            "selected_reasoning_systems": ["critical-thinking"],
            "instructions": "canonical_assembly_required",
        }
        envelope = {"structured_output": candidate, "type": "result"}
        return json.dumps(envelope).encode("utf-8"), b""

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = -15
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


@check("CLAUDE-01-plugin-hook-contract")
def test_plugin_hook_contract() -> None:
    hooks = build_hooks()
    require(
        set(hooks["hooks"]) == {"SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"},
        "unexpected Claude hook set",
    )
    handler = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    require(handler["command"] == "${CLAUDE_PLUGIN_ROOT}/bin/launch.sh", "unsafe command")
    require(handler["args"] == ["hook", "claude", "user_prompt_submitted"], "unsafe args")
    require(handler["timeout"] == 35, "host hook deadline is not explicit")
    require(
        parse_hook_arguments(("claude", "user_prompt_submitted"))
        == ("claude", "user_prompt_submitted"),
        "Claude launcher form is not registered",
    )


@check("CLAUDE-02-cli-isolation-and-structured-output")
def test_cli_selector_contract() -> None:
    value = projections()
    selector = ClaudeCliReasoningSelector(value.selection_catalog, executable="/usr/bin/true")
    request = SelectorRequest(prompt="Critique this proposal", session_id="session-a")
    effective, context = handles_for_request(
        request, SelectorConfig(transcript_access_enabled=False)
    )
    FakeProcess.instances.clear()
    with patch("opensocrates.selector.claude_cli.subprocess.Popen", FakeProcess):
        candidate = selector.select(
            effective, context, deadline_seconds=30, reasoning_effort="medium"
        )
    require(candidate is not None and candidate.get("intervene") is True, "candidate missing")
    process = FakeProcess.instances[-1]
    command = process.command
    for required in (
        "--safe-mode",
        "--no-session-persistence",
        "--json-schema",
        "--tools",
        "--strict-mcp-config",
        "--max-turns",
        "--effort",
    ):
        require(required in command, f"missing CLI isolation flag {required}")
    require(b"Critique this proposal" in process.payload, "prompt did not travel on stdin")
    require(
        process.kwargs.get("stderr") is subprocess.DEVNULL,
        "selector stderr is not silenced",
    )
    environment = _selector_environment()
    require(environment.get("OPENSOCRATES_SELECTOR_ACTIVE") == "1", "recursion guard missing")
    require("ANTHROPIC_API_KEY" not in environment, "API key crossed selector boundary")


@check("CLAUDE-03-output-envelope-rejection")
def test_output_rejection() -> None:
    require(_candidate_from_cli_output(b"not-json") is None, "invalid JSON accepted")
    require(
        _candidate_from_cli_output(json.dumps({"structured_output": {"intervene": True}}).encode())
        is None,
        "partial candidate accepted",
    )


class FakeSelector:
    def select(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "intervene": True,
            "selected_reasoning_systems": ["critical-thinking"],
            "instructions": "canonical_assembly_required",
        }


@check("CLAUDE-04-adapter-injection-and-cleanup")
def test_adapter_injection_and_cleanup() -> None:
    value = projections()
    assembler = ProjectionInstructionAssembler(value)
    with tempfile.TemporaryDirectory(prefix="opensocrates-claude-check-") as name:
        store = InstructionFileStore(installation_key=b"c" * 32, directory=Path(name) / "artifacts")
        application = SelectorApplication(
            selector=FakeSelector(),
            assembler=assembler,
            config=SelectorConfig(transcript_access_enabled=False),
            artifact_store=store,
        )
        adapter = ClaudeAdapter(
            ClaudeAdapterConfig(
                selector_mode=True,
                selector_application=application,
                selector_config=SelectorConfig(transcript_access_enabled=False),
                instruction_file_store=store,
            )
        )
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "session-a",
            "cwd": str(ROOT),
            "prompt": "Critique this proposal",
        }
        result = adapter.handle(payload, event_name="UserPromptSubmit")
        response = json.loads(result.stdout)
        specific = response["hookSpecificOutput"]
        require(specific["hookEventName"] == "UserPromptSubmit", "wrong response event")
        require("File path:" in specific["additionalContext"], "artifact reference missing")
        require(any(store.directory.rglob("instruction-*.md")), "artifact was not created")

        stop = adapter.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-a",
                "stop_hook_active": False,
                "last_assistant_message": "Done",
            },
            event_name="Stop",
        )
        require(stop.stdout == "", "Stop was not literal-empty")
        require(not any(store.directory.rglob("instruction-*.md")), "Stop did not clean turn")

        forked = adapter.handle(
            {
                "hook_event_name": "SessionStart",
                "session_id": "session-b",
                "source": "fork",
            },
            event_name="SessionStart",
        )
        require(forked.stdout == "", "fork SessionStart was rejected")


def main() -> int:
    failures: list[tuple[str, str]] = []
    for name, function in CHECKS:
        try:
            function()
        except Exception as error:
            failures.append((name, type(error).__name__))
    if failures:
        print(f"opensocrates-claude-contract: FAIL {len(failures)}/{len(CHECKS)}")
        for name, error in failures:
            print(f"- {name}: {error}")
        return 1
    print(f"opensocrates-claude-contract: PASS {len(CHECKS)}/{len(CHECKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
