"""Bounded Claude Code CLI selector with no API-key dependency.

The selector starts one non-persistent ``claude -p`` process for each prompt.
Claude Code's safe mode prevents *user, project, and plugin* customizations --
project instructions, plugins, hooks, skills, and MCP configuration -- from
entering the selector context while retaining the user's existing OAuth login.
Built-in and MCP tools are disabled explicitly.

Managed settings policy is NOT disabled by safe mode and remains part of the
host trust boundary.  Anthropic documents that under ``--safe-mode`` "managed
settings policy still applies, including policy-configured hooks"
(https://code.claude.com/docs/en/cli-reference).  On an organization-managed
machine a managed ``UserPromptSubmit`` hook therefore runs inside this child
process, receives the current prompt on stdin, and may return
``additionalContext``.  Managed plugins, managed skills, managed CLAUDE.md, and
policy-configured MCP servers do not load.  Selection stays bounded regardless:
``SelectorApplication`` discards the model's instruction text and injects only
authored catalog content.

Raw prompt/catalog data travel over stdin and captured stdout is parsed in
memory; neither stream is logged or persisted by OpenSocrates.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from collections.abc import Mapping
from pathlib import Path

from ..domain.models import SelectionCatalog
from .context import SelectorContextHandles
from .models import MAX_SELECTOR_DEADLINE_SECONDS, SelectorRequest
from .policy import MediumReasoningEffortPolicy, ReasoningEffortPolicy
from .sdk_worker import (
    _BASE_INSTRUCTIONS,
    _DEVELOPER_INSTRUCTIONS,
    _OUTPUT_SCHEMA,
    SELECTOR_RECURSION_ENV,
    SelectorWorkerRequest,
    _selector_turn_input,
)

_EXPECTED_CANDIDATE_FIELDS = frozenset({"intervene", "selected_reasoning_systems", "instructions"})
_TERMINATE_GRACE_SECONDS = 0.25


class SelectorOutcome:
    """Content-free labels for one selector attempt.

    These are the only selector facts OpenSocrates records.  No prompt,
    catalog, stdout, stderr, argv, environment value, credential, transcript,
    or model reasoning is ever attached to an outcome.
    """

    EXECUTABLE_MISSING = "executable_missing"
    REQUEST_REJECTED = "request_rejected"
    SPAWN_FAILED = "spawn_failed"
    TIMEOUT = "timeout"
    NONZERO_EXIT = "nonzero_exit"
    INVALID_OUTPUT = "invalid_output"
    SELECTOR_CLOSED = "selector_closed"
    NO_INTERVENTION = "no_intervention"
    SELECTED = "selected"

    ALL = (
        EXECUTABLE_MISSING,
        REQUEST_REJECTED,
        SPAWN_FAILED,
        TIMEOUT,
        NONZERO_EXIT,
        INVALID_OUTPUT,
        SELECTOR_CLOSED,
        NO_INTERVENTION,
        SELECTED,
    )
_MAX_SELECTION_CATALOG_BYTES = 512 * 1024
_MAX_CLI_RESPONSE_BYTES = 512 * 1024
_ENVIRONMENT_ALLOWLIST = frozenset(
    {
        "CLAUDE_CONFIG_DIR",
        "HOME",
        "LANG",
        "LC_ALL",
        "PATH",
        "SHELL",
        "TEMP",
        "TMP",
        "TMPDIR",
        "USER",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
    }
)


def _serialized_catalog(catalog: SelectionCatalog) -> str:
    if not isinstance(catalog, SelectionCatalog):
        raise TypeError("catalog must be a SelectionCatalog")
    encoded = json.dumps(
        catalog.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    if len(encoded.encode("utf-8")) > _MAX_SELECTION_CATALOG_BYTES:
        raise ValueError("selection catalog exceeds the transient CLI bound")
    return encoded


def _context_matches_request(request: SelectorRequest, context: SelectorContextHandles) -> bool:
    if context.cwd != request.cwd or context.tool_data_handle is not request.tool_data_handle:
        return False
    if context.transcript_access_enabled:
        return (
            context.transcript_path == request.transcript_path
            and context.transcript_referenced_file_paths == request.transcript_referenced_file_paths
        )
    return context.transcript_path is None and not context.transcript_referenced_file_paths


def _worker_request(request: SelectorRequest, *, selection_catalog: str) -> SelectorWorkerRequest:
    # The Claude selector deliberately receives the current prompt and catalog
    # only.  It has no tools with which to read transcript or workspace data.
    return SelectorWorkerRequest(
        current_prompt=request.prompt,
        selection_catalog=selection_catalog,
        reasoning_effort="medium",
        transcript_access_enabled=False,
    )


def _selector_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in _ENVIRONMENT_ALLOWLIST and isinstance(value, str)
    }
    environment[SELECTOR_RECURSION_ENV] = "1"
    environment["CLAUDE_CODE_SKIP_PROMPT_HISTORY"] = "1"
    # OpenSocrates' Claude path uses the user's existing Claude login.  Do not
    # hand an ambient Console API key to the isolated selector process.
    environment.pop("ANTHROPIC_API_KEY", None)
    return environment


def _candidate_from_cli_output(raw: bytes) -> dict[str, object] | None:
    if not raw or len(raw) > _MAX_CLI_RESPONSE_BYTES:
        return None
    try:
        envelope = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return None
    if not isinstance(envelope, Mapping):
        return None
    candidate = envelope.get("structured_output")
    if not isinstance(candidate, Mapping) or set(candidate) != _EXPECTED_CANDIDATE_FIELDS:
        return None
    return dict(candidate)


def _close_pipes(process: subprocess.Popen[bytes]) -> None:
    """Close every pipe this process owns so no descriptor is leaked."""

    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except (OSError, ValueError):
            continue


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate and definitively reap one selector child process.

    SIGKILL cannot be blocked, so the post-kill wait is unbounded: a bounded
    wait that expires would leave a zombie behind in a long-lived host.
    """

    try:
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGTERM)
            else:
                process.terminate()
            try:
                process.wait(timeout=_TERMINATE_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
    except (OSError, ProcessLookupError, subprocess.SubprocessError):
        pass
    finally:
        # The child may have exited between poll() and the signal; reap it
        # unconditionally so no path leaves an unwaited process.
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except (OSError, subprocess.SubprocessError):
            pass
        _close_pipes(process)


class ClaudeCliReasoningSelector:
    """One-process-per-turn ``ReasoningSelector`` for Claude Code 2.1.205+."""

    def __init__(
        self,
        catalog: SelectionCatalog,
        *,
        executable: str | None = None,
        effort_policy: ReasoningEffortPolicy | None = None,
    ) -> None:
        requested = executable or os.environ.get("CLAUDE_BIN", "claude")
        self._executable = shutil.which(requested)
        self._selection_catalog = _serialized_catalog(catalog)
        self._effort_policy = effort_policy or MediumReasoningEffortPolicy()
        self._lock = threading.Lock()
        self._active: set[subprocess.Popen[bytes]] = set()
        self._closed = False
        self._outcomes: dict[str, int] = {}

    @property
    def available(self) -> bool:
        return self._executable is not None

    def _record(self, outcome: str) -> str:
        """Count one content-free selector outcome."""

        with self._lock:
            self._outcomes[outcome] = self._outcomes.get(outcome, 0) + 1
        return outcome

    def outcome_counts(self) -> dict[str, int]:
        """Return a copy of the content-free outcome counters."""

        with self._lock:
            return dict(self._outcomes)

    def _command(self) -> list[str] | None:
        if self._executable is None:
            return None
        instructions = f"{_BASE_INSTRUCTIONS}\n\n{_DEVELOPER_INSTRUCTIONS}"
        schema = json.dumps(_OUTPUT_SCHEMA, separators=(",", ":"), sort_keys=True)
        return [
            self._executable,
            "--safe-mode",
            "-p",
            "--no-session-persistence",
            "--output-format",
            "json",
            "--json-schema",
            schema,
            "--tools",
            "",
            "--disallowedTools",
            "mcp__*",
            "--strict-mcp-config",
            "--permission-mode",
            "dontAsk",
            "--max-turns",
            "1",
            "--effort",
            "medium",
            "--system-prompt",
            instructions,
        ]

    def select(  # noqa: C901  # Explicit fail-open process lifecycle.
        self,
        request: SelectorRequest,
        context: SelectorContextHandles,
        *,
        deadline_seconds: int,
        reasoning_effort: str,
    ) -> Mapping[str, object] | None:
        if not isinstance(request, SelectorRequest) or not isinstance(
            context, SelectorContextHandles
        ):
            self._record(SelectorOutcome.REQUEST_REJECTED)
            return None
        if (
            type(deadline_seconds) is not int
            or not 1 <= deadline_seconds <= MAX_SELECTOR_DEADLINE_SECONDS
        ):
            self._record(SelectorOutcome.REQUEST_REJECTED)
            return None
        try:
            approved_effort = self._effort_policy.effort_for(request)
        except Exception:
            self._record(SelectorOutcome.REQUEST_REJECTED)
            return None
        if approved_effort != "medium" or reasoning_effort != approved_effort:
            self._record(SelectorOutcome.REQUEST_REJECTED)
            return None
        if not _context_matches_request(request, context):
            self._record(SelectorOutcome.REQUEST_REJECTED)
            return None
        command = self._command()
        if command is None:
            self._record(SelectorOutcome.EXECUTABLE_MISSING)
            return None
        worker_input = _worker_request(request, selection_catalog=self._selection_catalog)
        payload = _selector_turn_input(worker_input).encode("utf-8")

        with tempfile.TemporaryDirectory(prefix="opensocrates-claude-selector-") as name:
            workspace = Path(name)
            try:
                os.chmod(workspace, 0o700)
                process = subprocess.Popen(
                    command,
                    cwd=workspace,
                    env=_selector_environment(),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    start_new_session=os.name == "posix",
                )
            except (OSError, subprocess.SubprocessError, ValueError):
                self._record(SelectorOutcome.SPAWN_FAILED)
                return None
            with self._lock:
                if self._closed:
                    closed = True
                else:
                    closed = False
                    self._active.add(process)
            if closed:
                _terminate_process(process)
                self._record(SelectorOutcome.SELECTOR_CLOSED)
                return None
            try:
                try:
                    stdout, _stderr = process.communicate(payload, timeout=deadline_seconds)
                except subprocess.TimeoutExpired:
                    _terminate_process(process)
                    self._record(SelectorOutcome.TIMEOUT)
                    return None
                if process.returncode != 0:
                    _close_pipes(process)
                    self._record(SelectorOutcome.NONZERO_EXIT)
                    return None
                candidate = _candidate_from_cli_output(stdout)
                _close_pipes(process)
                if candidate is None:
                    self._record(SelectorOutcome.INVALID_OUTPUT)
                    return None
                self._record(
                    SelectorOutcome.SELECTED
                    if candidate.get("intervene") is True
                    else SelectorOutcome.NO_INTERVENTION
                )
                return candidate
            except (OSError, subprocess.SubprocessError, ValueError):
                _terminate_process(process)
                self._record(SelectorOutcome.INVALID_OUTPUT)
                return None
            finally:
                with self._lock:
                    self._active.discard(process)

    def cancel(self) -> None:
        with self._lock:
            active = tuple(self._active)
        for process in active:
            _terminate_process(process)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            active = tuple(self._active)
        for process in active:
            _terminate_process(process)

    def __repr__(self) -> str:
        return "ClaudeCliReasoningSelector(<isolated>)"


__all__ = ["ClaudeCliReasoningSelector", "SelectorOutcome"]
