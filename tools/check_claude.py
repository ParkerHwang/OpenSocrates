#!/usr/bin/env python3
"""Offline contract checks for the Claude Code and Cowork integration."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from opensocrates.constants import INSTRUCTION_ARTIFACT_END_MARKER
from opensocrates.content import ProjectionInstructionAssembler, load_reasoning_content_projections
from opensocrates.content.injection import _procedure_section
from opensocrates.domain.enums import HostId
from opensocrates.hooks.entrypoint import parse_hook_arguments
from opensocrates.hosts.claude.adapter import ClaudeAdapter, ClaudeAdapterConfig
from opensocrates.hosts.claude.commands import build_hooks
from opensocrates.hosts.codex.native import parse_codex_event, try_parse_codex_event
from opensocrates.selector import (
    InstructionFileStore,
    SelectorApplication,
    SelectorConfig,
    SelectorRequest,
    handles_for_request,
)
from opensocrates.selector.claude_cli import (
    _MAX_CLI_RESPONSE_BYTES,
    ClaudeCliReasoningSelector,
    SelectorOutcome,
    _candidate_from_cli_output,
    _close_pipes,
    _communicate_bounded,
    _selector_environment,
    _SelectorTimeout,
    _StdoutLimitExceeded,
    _terminate_process,
)
from opensocrates.selector.sdk_worker import SELECTOR_RECURSION_ENV

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
        # A faithful Popen double: real Popen objects always expose these.
        self.stdin = None
        self.stdout = None
        self.stderr = None
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


def _fake_communicate_bounded(process: FakeProcess, payload: bytes, *, timeout: int) -> bytes:
    try:
        stdout, _stderr = process.communicate(payload, timeout)
    except subprocess.TimeoutExpired as error:
        raise _SelectorTimeout from error
    return stdout


@check("CLAUDE-01-plugin-hook-contract")
def test_plugin_hook_contract() -> None:
    manifest = json.loads(
        (ROOT / "plugin-src" / "claude" / ".claude-plugin" / "plugin.json.tmpl").read_text(
            encoding="utf-8"
        )
    )
    require(
        "hooks" not in manifest,
        "Claude manifest redeclares the standard auto-loaded hooks/hooks.json file",
    )
    require(
        (ROOT / "plugin-src" / "claude" / "hooks" / "hooks.json.tmpl").is_file(),
        "standard Claude hooks file is missing",
    )
    hooks = build_hooks()
    require(
        set(hooks["hooks"])
        == {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "SessionEnd"},
        "unexpected Claude hook set",
    )
    handler = hooks["hooks"]["UserPromptSubmit"][0]["hooks"][0]
    require(handler["command"] == "${CLAUDE_PLUGIN_ROOT}/bin/launch.sh", "unsafe command")
    require(handler["args"] == ["hook", "claude", "user_prompt_submitted"], "unsafe args")
    require(handler["timeout"] == 35, "host hook deadline is not explicit")
    read_handler = hooks["hooks"]["PostToolUse"][0]
    require(read_handler["matcher"] == "Read", "grounding receipt hook is not Read-only")
    require(
        read_handler["hooks"][0]["args"] == ["hook", "claude", "tool_succeeded"],
        "grounding receipt hook uses the wrong lane",
    )
    require(
        read_handler["hooks"][0]["timeout"] == 3,
        "grounding receipt hook cannot cover the bounded cold-start path",
    )
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
    with (
        patch("opensocrates.selector.claude_cli.subprocess.Popen", FakeProcess),
        patch(
            "opensocrates.selector.claude_cli._communicate_bounded",
            side_effect=_fake_communicate_bounded,
        ),
    ):
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
    require(environment.get(SELECTOR_RECURSION_ENV) == "1", "recursion guard missing")
    # The exact allowlist contract is asserted in CLAUDE-05 against a populated
    # environment; a bare "key not present" check here would pass even if the
    # allowlist itself were widened.

    model_selector = ClaudeCliReasoningSelector(
        value.selection_catalog,
        executable="/usr/bin/true",
        model="claude-test-model-1",
    )
    model_command = model_selector._command()
    require(
        model_command is not None
        and model_command[model_command.index("--model") + 1] == "claude-test-model-1",
        "explicit reliability-matrix model was not passed as one argv value",
    )
    try:
        ClaudeCliReasoningSelector(
            value.selection_catalog,
            executable="/usr/bin/true",
            model="unsafe model value",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("unsafe model identifier was accepted")


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


def _structured_read_response(path: Path) -> dict[str, object]:
    """Mirror Claude Code's structured Read PostToolUse response."""

    content = path.read_text(encoding="utf-8")
    line_count = len(content.splitlines())
    return {
        "type": "text",
        "file": {
            "filePath": str(path),
            "content": content,
            "numLines": line_count,
            "totalLines": line_count,
        },
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
        require(
            "Blocking rules: Critical Thinking" in specific["additionalContext"]
            and "Do not use when" in specific["additionalContext"]
            and "critical-thinking@1" in specific["additionalContext"],
            "selected method guardrails or revision audit were not inlined",
        )
        require(any(store.directory.rglob("instruction-*.md")), "artifact was not created")
        artifact = store.latest_for_session("session-a")
        require(artifact is not None, "artifact metadata is unavailable")

        stop = adapter.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-a",
                "stop_hook_active": False,
                "last_assistant_message": "Done",
            },
            event_name="Stop",
        )
        blocked = json.loads(stop.stdout)
        require(blocked.get("decision") == "block", "ungrounded Stop was not continued")
        require(artifact.path.is_file(), "blocked Stop deleted the grounding artifact")

        partial = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-a",
                "tool_name": "Read",
                "tool_use_id": "tool-partial",
                "tool_input": {"file_path": str(artifact.path), "offset": 2},
                "tool_response": "partial",
            },
            event_name="PostToolUse",
        )
        require(partial.stdout == "", "PostToolUse emitted user-facing output")
        require(
            not store.has_complete_read_receipt(artifact),
            "partial Read produced a complete grounding receipt",
        )

        truncated = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-a",
                "tool_name": "Read",
                "tool_use_id": "tool-truncated",
                "tool_input": {"file_path": str(artifact.path)},
                "tool_response": "first lines only",
            },
            event_name="PostToolUse",
        )
        require(truncated.stdout == "", "truncated PostToolUse emitted user-facing output")
        require(
            not store.has_complete_read_receipt(artifact),
            "Read response without the terminal marker produced a complete receipt",
        )

        read = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-a",
                "tool_name": "Read",
                "tool_use_id": "tool-complete",
                "tool_input": {"file_path": str(artifact.path)},
                "tool_response": _structured_read_response(artifact.path),
            },
            event_name="PostToolUse",
        )
        require(read.stdout == "", "successful grounding Read emitted output")
        require(
            store.has_complete_read_receipt(artifact),
            "complete grounding Read did not produce a receipt",
        )

        receipt_path = artifact.path.parent / ".grounding-receipt.json"
        # A host that wraps the body under keys this boundary does not name must
        # still ground the turn end to end, not just pass the parser.
        receipt_path.unlink()
        require(
            not store.has_complete_read_receipt(artifact),
            "receipt survived its own deletion",
        )
        unfamiliar = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-a",
                "tool_name": "Read",
                "tool_use_id": "tool-unfamiliar-envelope",
                "tool_input": {"file_path": str(artifact.path)},
                "tool_response": {"result": [{"body": artifact.path.read_text(encoding="utf-8")}]},
            },
            event_name="PostToolUse",
        )
        require(unfamiliar.stdout == "", "unfamiliar Read envelope emitted user-facing output")
        require(
            store.has_complete_read_receipt(artifact),
            "an unfamiliar Read response envelope did not ground the turn",
        )

        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["artifact_sha256"] = "sha256:" + "0" * 64
        receipt_path.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        require(
            not store.has_complete_read_receipt(artifact),
            "tampered grounding receipt was accepted",
        )
        restored = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-a",
                "tool_name": "Read",
                "tool_use_id": "tool-complete-restored",
                "tool_input": {"file_path": str(artifact.path)},
                "tool_response": artifact.path.read_text(encoding="utf-8"),
            },
            event_name="PostToolUse",
        )
        require(restored.stdout == "", "receipt restoration emitted user-facing output")
        require(
            store.has_complete_read_receipt(artifact),
            "valid Read did not replace a tampered receipt",
        )

        grounded_stop = adapter.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-a",
                "stop_hook_active": False,
                "last_assistant_message": f"Done\n\n{artifact.grounding_footer()}",
            },
            event_name="Stop",
        )
        require(grounded_stop.stdout == "", "grounded Stop was not literal-empty")
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


@check("CLAUDE-04A-issue-32-grounding-specifics")
def test_issue_32_grounding_specifics() -> None:
    value = projections()
    assembler = ProjectionInstructionAssembler(value)
    assembled = assembler.assemble(("triangulation",), requested_locale="en")
    with tempfile.TemporaryDirectory(prefix="opensocrates-grounding-check-") as name:
        store = InstructionFileStore(installation_key=b"g" * 32, directory=Path(name) / "artifacts")
        artifact = store.create("session-grounding", "turn-grounding", assembled)
        context = artifact.reference_message()
        require(
            "all sources repeat one underlying dataset" in context,
            "triangulation's dependent-source exclusion was not in trusted context",
        )
        require(
            "all streams share one unverified source" in context,
            "triangulation's shared-source stop condition was not in trusted context",
        )
        require(
            artifact.grounding_footer() == "OpenSocrates grounding: triangulation@1",
            "triangulation method/revision audit line drifted",
        )

        require(
            store.record_complete_read(
                "session-grounding",
                "turn-grounding",
                file_path=artifact.path,
                tool_use_id="tool-first-artifact",
                offset=None,
                limit=None,
                end_marker_seen=True,
            ),
            "first artifact did not produce a complete-read receipt",
        )
        require(
            store.has_complete_read_receipt(artifact),
            "first artifact's receipt did not validate",
        )
        replay_target = store.create("session-grounding", "turn-grounding", assembled)
        require(replay_target.path != artifact.path, "artifact path was not randomized")
        require(
            replay_target.path.read_bytes() == artifact.path.read_bytes(),
            "same selection did not reproduce the replay precondition",
        )
        require(
            not store.has_complete_read_receipt(replay_target),
            "a prior artifact's receipt replayed against byte-identical content",
        )

    require(
        _procedure_section(
            "Prefix containing ### Do not use when\nlatent text\n\n## Stop conditions\nstop",
            "Do not use when",
        )
        is None,
        "a latent level-three heading was accepted as a canonical procedure section",
    )

    parsed = parse_codex_event(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "session-grounding",
            "tool_name": "Read",
            "tool_use_id": "tool-large-read",
            "tool_input": {"file_path": "/tmp/instruction-large.md"},
            "tool_response": "x" * (40 * 1024) + INSTRUCTION_ARTIFACT_END_MARKER,
        },
        event_name="PostToolUse",
        host=HostId.CLAUDE_CODE,
    )
    require(
        parsed.tool_read_end_marker_seen,
        "a complete Read response above the generic hook bound lost its terminal marker",
    )

    # Read envelope key names are not a stable host contract, so the terminator
    # search is shape-agnostic. Naming the expected keys would make a host that
    # wraps the body differently look like an incomplete read, costing a
    # compliant turn a repair pass.
    complete = "x" * 512 + INSTRUCTION_ARTIFACT_END_MARKER
    for label, response in (
        ("plain string", complete),
        ("file.content envelope", {"type": "text", "file": {"content": complete}}),
        ("flat content key", {"type": "text", "content": complete}),
        ("unfamiliar wrapper key", {"type": "text", "payload": {"blob": complete}}),
        ("list of content blocks", [{"type": "text", "text": complete}]),
        ("nested list envelope", {"result": [{"body": {"data": complete}}]}),
    ):
        shaped = parse_codex_event(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-grounding",
                "tool_name": "Read",
                "tool_use_id": "tool-shaped-read",
                "tool_input": {"file_path": "/tmp/instruction-large.md"},
                "tool_response": response,
            },
            event_name="PostToolUse",
            host=HostId.CLAUDE_CODE,
        )
        require(
            shaped.tool_read_end_marker_seen,
            f"a Read response delivered as a {label} lost its terminal marker",
        )

    # A body that never reaches the terminator is still refused, whatever shape
    # carries it, and the walk stays bounded rather than following one forever.
    too_deep: dict[str, object] = {"a": {"b": {"c": {"d": {"e": complete}}}}}
    for label, response in (
        ("truncated file envelope", {"type": "text", "file": {"content": "first lines only"}}),
        ("marker-free object", {"a": {"b": {"c": "no terminator here"}}}),
        ("marker-free list", [{"type": "text", "text": "no terminator here"}]),
        ("terminator past the depth bound", too_deep),
    ):
        refused = parse_codex_event(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-grounding",
                "tool_name": "Read",
                "tool_use_id": "tool-shaped-partial",
                "tool_input": {"file_path": "/tmp/instruction-large.md"},
                "tool_response": response,
            },
            event_name="PostToolUse",
            host=HostId.CLAUDE_CODE,
        )
        require(
            not refused.tool_read_end_marker_seen,
            f"a {label} was accepted as a complete grounding read",
        )

    oversized_stop = json.dumps(
        {
            "hook_event_name": "Stop",
            "session_id": "session-grounding",
            "last_assistant_message": "x" * (40 * 1024),
        }
    )
    with patch(
        "opensocrates.hosts.codex.native.json.loads",
        side_effect=AssertionError("oversized non-PostToolUse input was decoded"),
    ) as loads:
        rejected = try_parse_codex_event(
            oversized_stop,
            event_name="Stop",
            host=HostId.CLAUDE_CODE,
        )
    require(rejected.error_code == "input_too_large", "oversized Stop was not rejected")
    require(loads.call_count == 0, "oversized Stop reached json.loads")

    with patch("opensocrates.hosts.codex.native.json.loads", side_effect=RecursionError):
        recursive = try_parse_codex_event(
            '{"hook_event_name":"Stop"}',
            event_name="Stop",
            host=HostId.CLAUDE_CODE,
        )
    require(recursive.error_code == "native_invalid", "recursive JSON failure escaped the parser")

    with patch("opensocrates.hosts.codex.native.json.dumps", side_effect=RecursionError):
        recursive_mapping = try_parse_codex_event(
            {"hook_event_name": "Stop", "session_id": "session-grounding"},
            event_name="Stop",
            host=HostId.CLAUDE_CODE,
        )
    require(
        recursive_mapping.error_code == "input_too_large",
        "recursive Mapping serialization escaped the parser",
    )

    pre_tool = parse_codex_event(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "session-grounding",
            "tool_name": "Read",
            "tool_input": ["malformed", "but irrelevant"],
        },
        event_name="PreToolUse",
        host=HostId.CLAUDE_CODE,
    )
    require(pre_tool.tool_file_path is None, "PreToolUse consumed Read receipt metadata")
    permission = parse_codex_event(
        {
            "hook_event_name": "PermissionRequest",
            "session_id": "session-grounding",
            "tool_name": "Read",
            "tool_input": "malformed but irrelevant",
        },
        event_name="PermissionRequest",
        host=HostId.CLAUDE_CODE,
    )
    require(permission.tool_file_path is None, "PermissionRequest consumed Read receipt metadata")
    degraded_post = parse_codex_event(
        {
            "hook_event_name": "PostToolUse",
            "session_id": "session-grounding",
            "tool_name": "Read",
            "tool_input": {"file_path": "relative.md", "offset": "invalid"},
            "tool_response": {"type": "text", "file": {"content": "partial"}},
        },
        event_name="PostToolUse",
        host=HostId.CLAUDE_CODE,
    )
    require(
        degraded_post.tool_file_path is None,
        "malformed optional Read metadata invalidated PostToolUse",
    )


@check("CLAUDE-05-environment-allowlist-is-exact")
def test_environment_allowlist() -> None:
    """Assert the selector environment against a populated hostile environment.

    Checking only that one variable is absent is tautological: the code pops
    ANTHROPIC_API_KEY unconditionally, so such a check passes even if the
    allowlist were widened to include it.  This asserts the exact resulting key
    set instead.
    """

    sensitive = {
        "ANTHROPIC_API_KEY": "sk-ant-not-a-real-key",
        "ANTHROPIC_AUTH_TOKEN": "not-a-real-token",
        "ANTHROPIC_BASE_URL": "https://proxy.invalid",
        "ANTHROPIC_CUSTOM_HEADERS": "x-test: value",
        "ANTHROPIC_MODEL": "override",
        "CLAUDE_CODE_USE_BEDROCK": "1",
        "CLAUDE_CODE_USE_VERTEX": "1",
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE",
        "AWS_SECRET_ACCESS_KEY": "not-a-real-secret",
        "AWS_SESSION_TOKEN": "not-a-real-session",
        "AWS_PROFILE": "default",
        "AWS_REGION": "us-east-1",
        "GOOGLE_APPLICATION_CREDENTIALS": "/nonexistent/creds.json",
        "OPENAI_API_KEY": "sk-not-a-real-key",
        "GH_TOKEN": "not-a-real-token",
        "SSH_AUTH_SOCK": "/nonexistent/agent.sock",
    }
    approved = {
        "HOME": "/nonexistent/home",
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "CLAUDE_CONFIG_DIR": "/nonexistent/home/.claude",
        "TMPDIR": "/tmp",
    }
    with patch.dict(os.environ, {**sensitive, **approved}, clear=True):
        environment = _selector_environment()

    for key in sensitive:
        require(key not in environment, f"{key} crossed the selector boundary")
    expected = set(approved) | {SELECTOR_RECURSION_ENV, "CLAUDE_CODE_SKIP_PROMPT_HISTORY"}
    require(
        set(environment) == expected,
        f"selector environment key set drifted: {sorted(set(environment) ^ expected)}",
    )
    for key, value in approved.items():
        require(environment[key] == value, f"approved variable {key} was mutated")


class TimeoutProcess(FakeProcess):
    def communicate(self, payload: bytes, timeout: int) -> tuple[bytes, bytes]:
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)


class NonzeroProcess(FakeProcess):
    def communicate(self, payload: bytes, timeout: int) -> tuple[bytes, bytes]:
        self.returncode = 2
        return b"", b""


class GarbageProcess(FakeProcess):
    def communicate(self, payload: bytes, timeout: int) -> tuple[bytes, bytes]:
        self.returncode = 0
        return b"<<not json>>", b""


class NoInterventionProcess(FakeProcess):
    def communicate(self, payload: bytes, timeout: int) -> tuple[bytes, bytes]:
        self.returncode = 0
        candidate = {
            "intervene": False,
            "selected_reasoning_systems": [],
            "instructions": "",
        }
        return json.dumps({"structured_output": candidate}).encode("utf-8"), b""


def _fresh_selector(executable: str = "/usr/bin/true"):
    value = projections()
    selector = ClaudeCliReasoningSelector(value.selection_catalog, executable=executable)
    request = SelectorRequest(prompt="Critique this proposal", session_id="session-a")
    effective, context = handles_for_request(
        request, SelectorConfig(transcript_access_enabled=False)
    )
    return selector, effective, context


@check("CLAUDE-06-selector-failure-diagnostics")
def test_selector_failure_diagnostics() -> None:
    absent, effective, context = _fresh_selector(executable="opensocrates-absent-binary")
    require(absent.available is False, "absent executable reported as available")
    require(
        absent.select(effective, context, deadline_seconds=30, reasoning_effort="medium") is None,
        "absent executable did not fail open",
    )
    require(
        absent.outcome_counts().get(SelectorOutcome.EXECUTABLE_MISSING) == 1,
        "missing executable was not recorded",
    )

    rejected, effective, context = _fresh_selector()
    require(
        rejected.select(effective, context, deadline_seconds=999, reasoning_effort="medium")
        is None,
        "out-of-range deadline was accepted",
    )
    require(
        rejected.select(effective, context, deadline_seconds=30, reasoning_effort="high") is None,
        "unapproved effort was accepted",
    )
    require(
        rejected.outcome_counts().get(SelectorOutcome.REQUEST_REJECTED) == 2,
        "rejected requests were not recorded",
    )

    for process_class, outcome in (
        (TimeoutProcess, SelectorOutcome.TIMEOUT),
        (NonzeroProcess, SelectorOutcome.NONZERO_EXIT),
        (GarbageProcess, SelectorOutcome.INVALID_OUTPUT),
        (NoInterventionProcess, SelectorOutcome.NO_INTERVENTION),
    ):
        selector, effective, context = _fresh_selector()
        with (
            patch("opensocrates.selector.claude_cli.subprocess.Popen", process_class),
            patch(
                "opensocrates.selector.claude_cli._communicate_bounded",
                side_effect=_fake_communicate_bounded,
            ),
        ):
            result = selector.select(
                effective, context, deadline_seconds=30, reasoning_effort="medium"
            )
        if outcome == SelectorOutcome.NO_INTERVENTION:
            require(result is not None, "no-intervention candidate was discarded")
        else:
            require(result is None, f"{outcome} did not fail open")
        require(
            selector.outcome_counts().get(outcome) == 1,
            f"outcome {outcome} was not recorded",
        )

    overflow, effective, context = _fresh_selector()
    with (
        patch("opensocrates.selector.claude_cli.subprocess.Popen", FakeProcess),
        patch(
            "opensocrates.selector.claude_cli._communicate_bounded",
            side_effect=_StdoutLimitExceeded,
        ),
    ):
        require(
            overflow.select(
                effective,
                context,
                deadline_seconds=30,
                reasoning_effort="medium",
            )
            is None,
            "stdout overflow did not fail open",
        )
    require(
        overflow.outcome_counts().get(SelectorOutcome.INVALID_OUTPUT) == 1,
        "stdout overflow did not record the content-free invalid-output label",
    )

    # Repeated failures accumulate rather than overwrite.
    repeated, effective, context = _fresh_selector()
    with (
        patch("opensocrates.selector.claude_cli.subprocess.Popen", TimeoutProcess),
        patch(
            "opensocrates.selector.claude_cli._communicate_bounded",
            side_effect=_fake_communicate_bounded,
        ),
    ):
        for _ in range(3):
            repeated.select(effective, context, deadline_seconds=30, reasoning_effort="medium")
    require(
        repeated.outcome_counts().get(SelectorOutcome.TIMEOUT) == 3,
        "repeated failures were not counted",
    )
    # Privacy: only fixed labels are ever retained.
    require(
        set(repeated.outcome_counts()) <= set(SelectorOutcome.ALL),
        "selector recorded a label outside the fixed vocabulary",
    )


@check("CLAUDE-07-real-process-termination-and-reaping")
def test_real_process_reaping() -> None:
    """Terminate real children, including one that ignores SIGTERM."""

    if os.name != "posix":
        return
    for script, label in (
        ("sleep 30", "cooperative"),
        ('trap "" TERM; sleep 30', "sigterm-ignoring"),
    ):
        process = subprocess.Popen(
            ["/bin/sh", "-c", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _terminate_process(process)
        require(process.poll() is not None, f"{label} child was not reaped")
        require(
            process.stdin is None or process.stdin.closed,
            f"{label} stdin pipe was left open",
        )
        require(
            process.stdout is None or process.stdout.closed,
            f"{label} stdout pipe was left open",
        )
        # The whole process group must be gone, not just the direct child.
        try:
            os.killpg(process.pid, 0)
        except (ProcessLookupError, PermissionError):
            pass
        else:
            raise AssertionError(f"{label} process group survived termination")
    # Terminating an already-reaped process must stay a no-op.
    done = subprocess.Popen(["/bin/sh", "-c", "exit 0"], stdout=subprocess.PIPE)
    done.wait()
    _terminate_process(done)


@check("CLAUDE-07A-real-process-stdout-stream-limit")
def test_real_process_stdout_stream_limit() -> None:
    """Exceed the hard cap with a real child and prove prompt termination."""

    ordinary = subprocess.Popen(
        [sys.executable, "-c", 'import sys; sys.stdout.buffer.write(b"ok")'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    )
    require(
        _communicate_bounded(ordinary, b"", timeout=5) == b"ok",
        "bounded communication rejected ordinary real-process output",
    )
    _close_pipes(ordinary)

    early_exit = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.exit(7)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    )
    require(
        _communicate_bounded(early_exit, b"x" * (1024 * 1024), timeout=5) == b"",
        "early nonzero exit returned unexpected output",
    )
    require(early_exit.returncode == 7, "early nonzero exit lost its return code")
    _close_pipes(early_exit)

    sleeper = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    )
    try:
        _communicate_bounded(sleeper, b"", timeout=1)
    except _SelectorTimeout:
        pass
    else:
        raise AssertionError("bounded communication lost the selector timeout")
    require(sleeper.poll() is not None, "timed-out real child was not reaped")

    script = (
        "import sys,time; "
        f'sys.stdout.buffer.write(b"x" * ({_MAX_CLI_RESPONSE_BYTES} + 65536)); '
        "sys.stdout.buffer.flush(); time.sleep(30)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
    )
    started = time.monotonic()
    try:
        _communicate_bounded(process, b"", timeout=10)
    except _StdoutLimitExceeded:
        pass
    else:
        raise AssertionError("real subprocess output over the hard cap was accepted")
    require(time.monotonic() - started < 5, "stdout overflow did not stop the child promptly")
    require(process.poll() is not None, "stdout-overflow child was not reaped")
    require(process.stdin is None or process.stdin.closed, "overflow stdin pipe was left open")
    require(process.stdout is None or process.stdout.closed, "overflow stdout pipe was left open")


class BlockingProcess(FakeProcess):
    def communicate(self, payload: bytes, timeout: int) -> tuple[bytes, bytes]:
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)


@check("CLAUDE-08-cancel-and-close")
def test_cancel_and_close() -> None:
    selector, effective, context = _fresh_selector()
    selector.cancel()  # no active process; must not raise
    selector.close()
    with patch("opensocrates.selector.claude_cli.subprocess.Popen", BlockingProcess):
        result = selector.select(effective, context, deadline_seconds=30, reasoning_effort="medium")
    require(result is None, "closed selector produced a decision")
    require(
        selector.outcome_counts().get(SelectorOutcome.SELECTOR_CLOSED) == 1,
        "close was not recorded as a distinct outcome",
    )
    selector.close()  # idempotent


class SequencedSelector:
    """Return a different authored method on each successive turn."""

    def __init__(self, method_ids: tuple[str, ...]) -> None:
        self._method_ids = method_ids
        self.calls = 0

    def select(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        method_id = self._method_ids[min(self.calls, len(self._method_ids) - 1)]
        self.calls += 1
        return {
            "intervene": True,
            "selected_reasoning_systems": [method_id],
            "instructions": "canonical_assembly_required",
        }


def _referenced_path(additional_context: str) -> Path:
    for line in additional_context.splitlines():
        if line.startswith("File path:"):
            return Path(line.split("File path:", 1)[1].strip().strip('"'))
    raise AssertionError("no artifact reference in additionalContext")


@check("CLAUDE-09-two-turns-in-one-session")
def test_two_turns_in_one_session() -> None:
    """Claude prompt IDs isolate identical selections and their read receipts."""

    value = projections()
    assembler = ProjectionInstructionAssembler(value)
    with tempfile.TemporaryDirectory(prefix="opensocrates-claude-turns-") as name:
        store = InstructionFileStore(installation_key=b"d" * 32, directory=Path(name) / "artifacts")
        selector = SequencedSelector(("critical-thinking", "critical-thinking"))
        adapter = ClaudeAdapter(
            ClaudeAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=selector,
                    assembler=assembler,
                    config=SelectorConfig(transcript_access_enabled=False),
                    artifact_store=store,
                ),
                selector_config=SelectorConfig(transcript_access_enabled=False),
                instruction_file_store=store,
            )
        )

        def submit(prompt: str, prompt_id: str) -> Path:
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "session-shared",
                "prompt_id": prompt_id,
                "cwd": str(ROOT),
                "prompt": prompt,
            }
            result = adapter.handle(payload, event_name="UserPromptSubmit")
            body = json.loads(result.stdout)
            return _referenced_path(body["hookSpecificOutput"]["additionalContext"])

        first = submit("Critique this proposal", "prompt-1")
        first_artifact = store.latest_for_session("session-shared")
        require(first_artifact is not None, "first turn artifact metadata is unavailable")
        first_read = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-shared",
                "prompt_id": "prompt-1",
                "tool_name": "Read",
                "tool_use_id": "tool-prompt-1",
                "tool_input": {"file_path": str(first)},
                "tool_response": _structured_read_response(first),
            },
            event_name="PostToolUse",
        )
        require(first_read.stdout == "", "first complete Read emitted user-facing output")
        require(
            store.has_complete_read_receipt(first_artifact),
            "first prompt did not receive a valid receipt",
        )
        first_bytes = first.read_bytes()
        first_text = first_bytes.decode("utf-8")
        for private_value in (
            "Critique this proposal",
            "session-shared",
            "prompt-1",
            "tool-prompt-1",
            str(ROOT),
        ):
            require(
                private_value not in first_text,
                "instruction artifact retained prompt, identity, tool, or workspace content",
            )

        second = submit("Now critique the same proposal again", "prompt-2")
        second_artifact = store.latest_for_session("session-shared")
        require(second_artifact is not None, "second turn artifact metadata is unavailable")

        require(not first.exists(), "later UserPromptSubmit kept the superseded turn artifact")
        require(second.is_file(), "second turn artifact is missing")
        require(first != second, "second turn reused the first turn's artifact path")
        require(first.parent != second.parent, "Claude prompt IDs did not isolate turn directories")
        require(first_bytes == second.read_bytes(), "identical selection bytes drifted")
        require(selector.calls == 2, "second prompt did not reach the selector")
        require(
            store.delete_superseded_turns("session-shared", "prompt-2") == 0 and second.is_file(),
            "supersession cleanup deleted the active turn artifact",
        )

        second_text = second.read_text(encoding="utf-8")
        require(
            "critical-thinking" in second_text,
            "second turn artifact does not carry the second turn's selection",
        )
        stale_stop = adapter.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-shared",
                "prompt_id": "prompt-2",
                "stop_hook_active": False,
                "last_assistant_message": f"Done\n\n{second_artifact.grounding_footer()}",
            },
            event_name="Stop",
        )
        require(
            json.loads(stale_stop.stdout).get("decision") == "block",
            "the first prompt's receipt satisfied the second prompt's Stop gate",
        )

        second_read = adapter.handle(
            {
                "hook_event_name": "PostToolUse",
                "session_id": "session-shared",
                "prompt_id": "prompt-2",
                "tool_name": "Read",
                "tool_use_id": "tool-prompt-2",
                "tool_input": {"file_path": str(second)},
                "tool_response": _structured_read_response(second),
            },
            event_name="PostToolUse",
        )
        require(second_read.stdout == "", "second complete Read emitted user-facing output")
        grounded_stop = adapter.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-shared",
                "prompt_id": "prompt-2",
                "stop_hook_active": False,
                "last_assistant_message": f"Done\n\n{second_artifact.grounding_footer()}",
            },
            event_name="Stop",
        )
        require(grounded_stop.stdout == "", "grounded second Stop was not literal-empty")
        require(not first.exists(), "superseded first prompt artifact reappeared")
        require(not second.exists(), "second Stop did not delete its own artifact")

        ended = adapter.handle(
            {
                "hook_event_name": "SessionEnd",
                "session_id": "session-shared",
                "reason": "other",
            },
            event_name="SessionEnd",
        )
        require(ended.stdout == "", "SessionEnd emitted user-facing output")
        leftovers = sorted(store.directory.rglob("instruction-*.md"))
        require(
            not leftovers,
            f"SessionEnd left {len(leftovers)} artifact(s) from completed prompts",
        )


@check("CLAUDE-09A-supersession-cleanup-fails-open")
def test_supersession_cleanup_fails_open() -> None:
    """A cleanup failure must not block a later prompt or delete its active tree."""

    value = projections()
    assembler = ProjectionInstructionAssembler(value)
    with tempfile.TemporaryDirectory(prefix="opensocrates-claude-supersession-") as name:
        store = InstructionFileStore(installation_key=b"u" * 32, directory=Path(name) / "artifacts")
        adapter = ClaudeAdapter(
            ClaudeAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=FakeSelector(),
                    assembler=assembler,
                    config=SelectorConfig(transcript_access_enabled=False),
                    artifact_store=store,
                ),
                selector_config=SelectorConfig(transcript_access_enabled=False),
                instruction_file_store=store,
            )
        )

        def submit(prompt_id: str) -> Path:
            result = adapter.handle(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": "session-fail-open",
                    "prompt_id": prompt_id,
                    "prompt": "<transient-private-prompt>",
                },
                event_name="UserPromptSubmit",
            )
            require(result.stdout != "", "cleanup failure blocked UserPromptSubmit")
            body = json.loads(result.stdout)
            return _referenced_path(body["hookSpecificOutput"]["additionalContext"])

        first = submit("prompt-1")
        with patch.object(store, "delete_superseded_turns", side_effect=OSError):
            second = submit("prompt-2")
        require(first.is_file(), "failed cleanup unexpectedly removed the prior turn")
        require(second.is_file(), "failed cleanup removed or blocked the active turn")
        foreign = store.create(
            "other-session",
            "other-turn",
            assembler.assemble(("critical-thinking",), requested_locale="en"),
        )

        removed = store.delete_superseded_turns("session-fail-open", "prompt-2")
        require(removed > 0, "recovery cleanup removed no superseded content")
        require(not first.exists(), "recovery cleanup kept the superseded turn")
        require(second.is_file(), "recovery cleanup deleted the active turn")
        require(foreign.path.is_file(), "supersession cleanup crossed the session boundary")


FIXTURES = ROOT / "src" / "opensocrates" / "hosts" / "contracts" / "fixtures" / "claude"
# Every value a sanitized fixture is allowed to carry in a field that could
# otherwise hold prompt, transcript, path, credential, or identifying content.
ALLOWED_SANITIZED_VALUES = {
    "session_id": {"00000000-0000-4000-8000-00000000005e"},
    "prompt_id": {
        "00000000-0000-4000-8000-0000000000a1",
        "00000000-0000-4000-8000-0000000000a2",
    },
    "transcript_path": {"/synthetic/transcript.jsonl"},
    "cwd": {"/synthetic/workspace"},
    "prompt": {"<synthetic-prompt>"},
    "last_assistant_message": {"<synthetic-final-message>"},
    "tool_use_id": {"toolu-synthetic-1", "toolu-synthetic-2"},
    "file_path": {"/synthetic/workspace/instruction-artifact.md"},
    "filePath": {"/synthetic/workspace/instruction-artifact.md"},
    "content": {"<synthetic-read-body>"},
}
ALLOWED_NATIVE_INPUT_STRINGS = set().union(*ALLOWED_SANITIZED_VALUES.values()) | {
    "SessionEnd",
    "SessionStart",
    "PostToolUse",
    "Read",
    "Stop",
    "UserPromptSubmit",
    "acceptEdits",
    "low",
    "other",
    "resume",
    "startup",
    "text",
}


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def walk_sanitized(value: object, key: str | None, fixture_id: str) -> None:
    """Refuse any fixture value that escaped the sanitizer's marker vocabulary."""

    if key in ALLOWED_SANITIZED_VALUES:
        require(
            isinstance(value, str) and value in ALLOWED_SANITIZED_VALUES[key],
            f"{fixture_id}: unsanitized value in field {key}",
        )
        return
    if isinstance(value, str):
        require(
            value in ALLOWED_NATIVE_INPUT_STRINGS,
            f"{fixture_id}: native payload contains an unapproved string in field {key}",
        )
        return
    if isinstance(value, dict):
        for name, item in value.items():
            walk_sanitized(item, name, fixture_id)
    elif isinstance(value, list):
        for item in value:
            walk_sanitized(item, None, fixture_id)


@check("CLAUDE-11-runtime-payload-receipts")
def test_runtime_payload_receipts() -> None:
    """Compare captured Claude receipts field by field with the shared parser.

    The Claude adapter reuses the Codex parser deliberately.  Repository and
    schema documentation cannot show that the live envelope still agrees with
    that mapping, so these fixtures are runtime receipts rather than authored
    shapes.
    """

    names = sorted(path.stem for path in FIXTURES.glob("*.json"))
    require(
        names
        == [
            "post-tool-use-read",
            "session-end-other",
            "session-start-resume",
            "session-start-startup",
            "stop-turn-1",
            "user-prompt-submit-turn-1",
            "user-prompt-submit-turn-2",
        ],
        f"Claude receipt fixture set drifted: {names}",
    )
    covered = {load_fixture(name)["native_event"] for name in names}
    require(
        covered == {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "SessionEnd"},
        f"captured lifecycle coverage is incomplete: {sorted(covered)}",
    )

    for name in names:
        fixture = load_fixture(name)
        fixture_id = fixture["fixture_id"]
        native_input = fixture["native_input"]
        expectation = fixture["adapter_expectation"]

        walk_sanitized(native_input, None, fixture_id)
        require(
            sorted(native_input) == fixture["capture"]["observed_field_names"],
            f"{fixture_id}: fixture fields diverged from the captured field names",
        )

        parsed = try_parse_codex_event(
            native_input,
            event_name=fixture["native_event"],
            host=HostId.CLAUDE_CODE,
        )
        require(parsed.event is not None, f"{fixture_id}: real receipt failed to parse")
        require(
            parsed.error_code is None and expectation["parse_status"] == "accepted",
            f"{fixture_id}: real receipt was not accepted",
        )
        # A real payload must not look novel.  Anything the runtime always sends
        # belongs in the known-field set, so that the unknown-field diagnostic
        # keeps meaning "this host sent something we have never seen".
        require(
            list(parsed.ignored_fields) == expectation["ignored_fields"],
            f"{fixture_id}: unexpected ignored fields {list(parsed.ignored_fields)}",
        )
        event = parsed.event
        require(
            event.native_version == expectation["native_version"],
            f"{fixture_id}: native version marker drifted to {event.native_version!r}",
        )
        require(
            event.session_id == native_input["session_id"],
            f"{fixture_id}: session identity was not carried",
        )

        # prompt_id is the Claude-only turn identity.  Codex has no such field,
        # and the shared parser must keep projecting it into turn_id.
        require(
            event.turn_id == expectation["turn_id"],
            f"{fixture_id}: turn_id is {event.turn_id!r}, expected {expectation['turn_id']!r}",
        )
        if expectation["turn_id_source"] == "prompt_id":
            require(
                "turn_id" not in native_input and "prompt_id" in native_input,
                f"{fixture_id}: fixture does not exercise the prompt_id mapping",
            )
            require(
                event.turn_id == native_input["prompt_id"],
                f"{fixture_id}: prompt_id was not projected into turn_id",
            )

        if fixture["native_event"] == "Stop":
            require(
                event.final_message == native_input["last_assistant_message"],
                f"{fixture_id}: last_assistant_message was not carried into final_message",
            )
            require(
                event.stop_hook_active is native_input["stop_hook_active"],
                f"{fixture_id}: stop_hook_active was not carried",
            )
        if fixture["native_event"] == "SessionStart":
            require(
                event.source == native_input["source"],
                f"{fixture_id}: SessionStart source was not carried",
            )
        if fixture["native_event"] == "SessionEnd":
            require(
                event.reason == native_input["reason"],
                f"{fixture_id}: SessionEnd reason was not carried",
            )
        if fixture["native_event"] == "PostToolUse":
            require(
                event.tool_name == native_input["tool_name"],
                f"{fixture_id}: tool_name was not carried",
            )
            require(
                event.tool_file_path is not None
                and str(event.tool_file_path) == native_input["tool_input"]["file_path"],
                f"{fixture_id}: Read receipt metadata was not carried",
            )

    # Two consecutive turns of one captured session: identity is stable and the
    # turn identity is not.
    first = load_fixture("user-prompt-submit-turn-1")["native_input"]
    second = load_fixture("user-prompt-submit-turn-2")["native_input"]
    require(
        first["session_id"] == second["session_id"],
        "the captured second turn did not stay in one session",
    )
    require(
        first["prompt_id"] != second["prompt_id"],
        "the captured second turn reused the first turn's prompt_id",
    )
    resumed = load_fixture("session-start-resume")["native_input"]
    require(
        resumed["source"] == "resume" and resumed["session_id"] == first["session_id"],
        "the captured resume receipt did not continue the captured session",
    )


def _receipt_payload(fixture_name: str, **overrides: object) -> dict:
    payload = dict(load_fixture(fixture_name)["native_input"])
    payload.update(overrides)
    return payload


def _read_receipt_payload(fixture_name: str, artifact_path: Path, prompt_id: str) -> dict:
    """Rebuild the captured Read receipt around one live artifact."""

    payload = _receipt_payload(fixture_name, prompt_id=prompt_id)
    response = _structured_read_response(artifact_path)
    captured = payload["tool_response"]["file"]
    payload["tool_input"] = dict(payload["tool_input"], file_path=str(artifact_path))
    # Keep every runtime-authored key of the captured envelope, including the
    # ones this boundary never reads.
    payload["tool_response"] = {
        "type": payload["tool_response"]["type"],
        "file": {
            **captured,
            "filePath": str(artifact_path),
            "content": response["file"]["content"],
            "numLines": response["file"]["numLines"],
            "totalLines": response["file"]["totalLines"],
        },
    }
    payload["tool_use_id"] = f"toolu-{prompt_id}"
    return payload


@check("CLAUDE-12-runtime-receipt-lifecycle-isolation")
def test_runtime_receipt_lifecycle() -> None:
    """Drive two turns of one session with the captured envelopes end to end."""

    value = projections()
    assembler = ProjectionInstructionAssembler(value)
    turn_one = load_fixture("user-prompt-submit-turn-1")["native_input"]["prompt_id"]
    turn_two = load_fixture("user-prompt-submit-turn-2")["native_input"]["prompt_id"]
    session = load_fixture("user-prompt-submit-turn-1")["native_input"]["session_id"]

    with tempfile.TemporaryDirectory(prefix="opensocrates-claude-receipts-") as name:
        store = InstructionFileStore(installation_key=b"r" * 32, directory=Path(name) / "artifacts")
        adapter = ClaudeAdapter(
            ClaudeAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=FakeSelector(),
                    assembler=assembler,
                    config=SelectorConfig(transcript_access_enabled=False),
                    artifact_store=store,
                ),
                selector_config=SelectorConfig(transcript_access_enabled=False),
                instruction_file_store=store,
            )
        )

        started = adapter.handle(
            load_fixture("session-start-startup")["native_input"],
            event_name="SessionStart",
        )
        require(started.stdout == "", "captured SessionStart emitted user-facing output")

        def submit(prompt_id: str) -> Path:
            result = adapter.handle(
                _receipt_payload("user-prompt-submit-turn-1", prompt_id=prompt_id),
                event_name="UserPromptSubmit",
            )
            body = json.loads(result.stdout)
            require(
                body["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit",
                "captured UserPromptSubmit produced the wrong response event",
            )
            return _referenced_path(body["hookSpecificOutput"]["additionalContext"])

        first_path = submit(turn_one)
        first_artifact = store.latest_for_session(session)
        require(first_artifact is not None, "the first captured turn issued no artifact")

        read = adapter.handle(
            _read_receipt_payload("post-tool-use-read", first_path, turn_one),
            event_name="PostToolUse",
        )
        require(read.stdout == "", "captured PostToolUse emitted user-facing output")
        require(
            store.has_complete_read_receipt(first_artifact),
            "the captured Read envelope did not produce a grounding receipt",
        )

        stop_payload = _receipt_payload(
            "stop-turn-1",
            prompt_id=turn_one,
            last_assistant_message=f"Done\n\n{first_artifact.grounding_footer()}",
        )
        stopped = adapter.handle(stop_payload, event_name="Stop")
        require(stopped.stdout == "", "grounded captured Stop was not literal-empty")
        require(not first_path.exists(), "captured Stop did not clean its own turn")

        second_path = submit(turn_two)
        second_artifact = store.latest_for_session(session)
        require(second_artifact is not None, "the second captured turn issued no artifact")
        require(
            first_path.parent != second_path.parent,
            "the captured prompt_id pair did not isolate turn directories",
        )

        # The first turn's receipt must not satisfy the second turn's gate.
        ungrounded = adapter.handle(
            _receipt_payload(
                "stop-turn-1",
                prompt_id=turn_two,
                last_assistant_message=f"Done\n\n{second_artifact.grounding_footer()}",
            ),
            event_name="Stop",
        )
        require(
            json.loads(ungrounded.stdout).get("decision") == "block",
            "a completed turn's receipt satisfied the next captured turn's Stop gate",
        )

        ended = adapter.handle(
            _receipt_payload("session-end-other", prompt_id=turn_two),
            event_name="SessionEnd",
        )
        require(ended.stdout == "", "captured SessionEnd emitted user-facing output")
        leftovers = sorted(store.directory.rglob("instruction-*.md"))
        require(
            not leftovers,
            f"captured SessionEnd left {len(leftovers)} artifact(s) behind",
        )


@check("CLAUDE-10-single-user-facing-entry")
def test_single_user_facing_entry() -> None:
    source = ROOT / "plugin-src" / "claude"
    metadata = json.loads((source / "generator.json").read_text(encoding="utf-8"))
    require(
        metadata.get("public_skills") == ["opensocrates"],
        "Claude generator does not declare exactly one public skill",
    )
    require(
        metadata.get("method_output") == "skills/opensocrates/references/methods/{method_id}.md",
        "Claude methods are not routed to non-discoverable supporting references",
    )
    command_outputs = {
        str(item.get("output"))
        for item in metadata.get("command_templates", [])
        if isinstance(item, dict)
    }
    require(
        not any(output.startswith("commands/") for output in command_outputs),
        "Claude generator still publishes a duplicate command surface",
    )
    skill_entries = sorted(
        path.relative_to(source).as_posix() for path in (source / "skills").glob("*/SKILL.md.tmpl")
    )
    require(
        skill_entries == ["skills/opensocrates/SKILL.md.tmpl"],
        f"Claude source exposes unexpected top-level skills: {skill_entries}",
    )
    skill = (source / "skills" / "opensocrates" / "SKILL.md.tmpl").read_text(encoding="utf-8")
    require("$ARGUMENTS" in skill, "explicit /opensocrates arguments are not forwarded")
    require(
        "references/catalog.md" in skill,
        "the single Claude skill does not route to its internal catalog",
    )


@check("CLAUDE-13-real-selector-is-opt-in")
def test_real_selector_is_opt_in() -> None:
    environment = dict(os.environ)
    environment.pop("OPENSOCRATES_REAL_CLAUDE", None)
    with tempfile.TemporaryDirectory(prefix="opensocrates-real-claude-gate-") as name:
        report = Path(name) / "report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "check_real_claude.py"),
                "--report",
                str(report),
            ],
            cwd=ROOT,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        require(result.returncode == 0, "real Claude check did not skip without opt-in")
        evidence = json.loads(report.read_text(encoding="utf-8"))
        require(
            evidence.get("status") == "skipped" and evidence.get("blocker") == "opt_in_required",
            "real Claude check crossed its opt-in gate",
        )
        require(
            set(evidence) == {"schema", "status", "blocker", "privacy"},
            "skipped real Claude evidence contains unexpected data",
        )

        matrix_report = Path(name) / "matrix.json"
        matrix_environment = dict(environment)
        matrix_environment.pop("OPENSOCRATES_CLAUDE_RELIABILITY", None)
        matrix = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "check_claude_reliability.py"),
                "--report",
                str(matrix_report),
            ],
            cwd=ROOT,
            env=matrix_environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
        require(matrix.returncode == 0, "Claude reliability matrix did not skip without opt-in")
        matrix_evidence = json.loads(matrix_report.read_text(encoding="utf-8"))
        require(
            matrix_evidence.get("status") == "skipped"
            and matrix_evidence.get("blocker") == "opt_in_required"
            and matrix_evidence.get("rows") == [],
            "Claude reliability matrix crossed its opt-in gate or invented a row",
        )


@check("CLAUDE-14-packaged-hook-timing-evidence")
def test_packaged_hook_timing_evidence() -> None:
    report = json.loads(
        (ROOT / "docs" / "evidence" / "claude-hook-timing-v1.1.2-darwin-arm64.json").read_text(
            encoding="utf-8"
        )
    )
    require(report.get("status") == "pass", "packaged Claude timing evidence did not pass")
    require(
        report.get("product_version") == "1.1.2" and report.get("target") == "darwin-arm64",
        "packaged Claude timing evidence has the wrong release identity",
    )
    require(report.get("hook_budget_ms") == 3000, "timing evidence changed the host budget")
    for condition in ("cold", "warm"):
        sample = report.get(condition)
        require(isinstance(sample, dict), f"{condition} timing sample is missing")
        require(
            sample.get("runs") == 20
            and sample.get("verified_receipts") == 20
            and sample.get("verified_cleanups") == 20,
            f"{condition} timing sample did not verify every operation",
        )
        require(
            sample.get("sufficient_margin") is True and sample.get("p95_margin_ms", 0) >= 1500,
            f"{condition} timing sample lacks the required p95 margin",
        )
    privacy = report.get("privacy")
    require(
        isinstance(privacy, dict)
        and privacy.get("synthetic_content_only") is True
        and all(value is False for key, value in privacy.items() if key.endswith("_recorded")),
        "packaged timing evidence violates its privacy boundary",
    )


@check("CLAUDE-15-desktop-live-probe-is-honestly-blocked")
def test_desktop_live_probe_is_honestly_blocked() -> None:
    report = json.loads(
        (ROOT / "docs" / "evidence" / "claude-desktop-live-probe-v1.1.2.json").read_text(
            encoding="utf-8"
        )
    )
    require(
        report.get("status") == "blocked" and report.get("blocker") == "mac_locked",
        "desktop live probe does not preserve its exact blocker",
    )
    observations = report.get("observations")
    require(
        isinstance(observations, dict) and not any(observations.values()),
        "blocked desktop probe claims an observation",
    )
    privacy = report.get("privacy")
    require(
        isinstance(privacy, dict) and not any(privacy.values()),
        "blocked desktop probe contains private evidence",
    )


@check("CLAUDE-16-cowork-live-probe-separates-cli-registration")
def test_cowork_live_probe_separates_cli_registration() -> None:
    report = json.loads(
        (ROOT / "docs" / "evidence" / "claude-cowork-live-probe-v1.1.2.json").read_text(
            encoding="utf-8"
        )
    )
    require(
        report.get("status") == "blocked" and report.get("blocker") == "mac_locked",
        "Cowork probe does not preserve its exact blocker",
    )
    observations = report.get("observations")
    require(isinstance(observations, dict), "Cowork observations are missing")
    require(
        observations.get("cli_user_scope_marketplace_registered") is True,
        "Cowork probe lost the independently confirmed CLI registration",
    )
    require(
        not any(
            value
            for key, value in observations.items()
            if key != "cli_user_scope_marketplace_registered"
        ),
        "blocked Cowork probe claims a Cowork or hook observation",
    )
    privacy = report.get("privacy")
    require(
        isinstance(privacy, dict) and not any(privacy.values()),
        "blocked Cowork probe contains private evidence",
    )


@check("CLAUDE-17-chat-archive-evidence-does-not-claim-upload")
def test_chat_archive_evidence_does_not_claim_upload() -> None:
    report = json.loads(
        (ROOT / "docs" / "evidence" / "claude-chat-upload-probe-v1.1.2.json").read_text(
            encoding="utf-8"
        )
    )
    require(
        report.get("status") == "blocked" and report.get("blocker") == "mac_locked",
        "Chat upload probe does not preserve its exact blocker",
    )
    archive = report.get("archive")
    require(
        isinstance(archive, dict)
        and archive.get("file_count") == 52
        and archive.get("public_skill_count") == 1
        and archive.get("internal_method_count") == 48,
        "Chat archive evidence has the wrong package shape",
    )
    require(
        not any(value for key, value in archive.items() if key.endswith("_present")),
        "Chat archive evidence contains a forbidden surface",
    )
    observations = report.get("ui_observations")
    require(
        isinstance(observations, dict) and not any(observations.values()),
        "blocked Chat probe claims a UI observation",
    )
    privacy = report.get("privacy")
    require(
        isinstance(privacy, dict) and not any(privacy.values()),
        "blocked Chat probe contains private evidence",
    )


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
