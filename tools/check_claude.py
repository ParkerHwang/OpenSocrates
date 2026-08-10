#!/usr/bin/env python3
"""Offline contract checks for the Claude Code and Cowork integration."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from opensocrates.constants import INSTRUCTION_ARTIFACT_END_MARKER
from opensocrates.content import ProjectionInstructionAssembler, load_reasoning_content_projections
from opensocrates.domain.enums import HostId
from opensocrates.hooks.entrypoint import parse_hook_arguments
from opensocrates.hosts.claude.adapter import ClaudeAdapter, ClaudeAdapterConfig
from opensocrates.hosts.claude.commands import build_hooks
from opensocrates.hosts.codex.native import parse_codex_event
from opensocrates.selector import (
    InstructionFileStore,
    SelectorApplication,
    SelectorConfig,
    SelectorRequest,
    handles_for_request,
)
from opensocrates.selector.claude_cli import (
    ClaudeCliReasoningSelector,
    SelectorOutcome,
    _candidate_from_cli_output,
    _selector_environment,
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
    require(environment.get(SELECTOR_RECURSION_ENV) == "1", "recursion guard missing")
    # The exact allowlist contract is asserted in CLAUDE-05 against a populated
    # environment; a bare "key not present" check here would pass even if the
    # allowlist itself were widened.


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
                "tool_response": artifact.path.read_text(encoding="utf-8"),
            },
            event_name="PostToolUse",
        )
        require(read.stdout == "", "successful grounding Read emitted output")
        require(
            store.has_complete_read_receipt(artifact),
            "complete grounding Read did not produce a receipt",
        )

        receipt_path = artifact.path.parent / ".grounding-receipt.json"
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
        with patch("opensocrates.selector.claude_cli.subprocess.Popen", process_class):
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

    # Repeated failures accumulate rather than overwrite.
    repeated, effective, context = _fresh_selector()
    with patch("opensocrates.selector.claude_cli.subprocess.Popen", TimeoutProcess):
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
    """Two prompts in one session, with no intervening Stop.

    Claude Code exposes no turn_id, so the adapter reuses session_id as the
    turn key. This asserts that the second turn cannot be served the first
    turn's artifact, and that Stop remains the normal cleanup path with the
    24-hour TTL sweep as fallback rather than the mechanism.
    """

    value = projections()
    assembler = ProjectionInstructionAssembler(value)
    with tempfile.TemporaryDirectory(prefix="opensocrates-claude-turns-") as name:
        store = InstructionFileStore(installation_key=b"d" * 32, directory=Path(name) / "artifacts")
        selector = SequencedSelector(("critical-thinking", "first-principles"))
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

        def submit(prompt: str) -> Path:
            payload = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "session-shared",
                "cwd": str(ROOT),
                "prompt": prompt,
            }
            result = adapter.handle(payload, event_name="UserPromptSubmit")
            body = json.loads(result.stdout)
            return _referenced_path(body["hookSpecificOutput"]["additionalContext"])

        first = submit("Critique this proposal")
        second = submit("Now weigh the alternative")

        require(first.is_file(), "first turn artifact was not created")
        require(second.is_file(), "second turn artifact is missing")
        require(first != second, "second turn reused the first turn's artifact path")
        require(selector.calls == 2, "second prompt did not reach the selector")

        second_text = second.read_text(encoding="utf-8")
        require(
            "first-principles" in second_text,
            "second turn artifact does not carry the second turn's selection",
        )
        require(
            "critical-thinking" not in second_text,
            "second turn artifact leaked the first turn's selection",
        )

        adapter.handle(
            {
                "hook_event_name": "Stop",
                "session_id": "session-shared",
                "stop_hook_active": True,
                "last_assistant_message": "Done",
            },
            event_name="Stop",
        )
        leftovers = sorted(store.directory.rglob("instruction-*.md"))
        require(
            not leftovers,
            f"Stop left {len(leftovers)} artifact(s); TTL sweep must be the fallback, "
            "not the normal cleanup path",
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
