#!/usr/bin/env python3
"""Offline contract checks for the approved Codex-only selector prototype.

The runner uses only synthetic authored content, a deterministic clock, and a
fake selector. It does not start the SDK, read host data, or print content,
paths, credentials, or exception details.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from io import BytesIO, StringIO
from pathlib import Path
from typing import Literal
from unittest.mock import patch

from opensocrates.clock import FrozenClock
from opensocrates.content.injection import (
    ProjectionInstructionAssembler,
    assemble_canonical_instruction,
    resolve_injection_locale,
    resolve_prompt_locale,
    validate_candidate_instruction,
)
from opensocrates.content.loader import load_reasoning_content_projections
from opensocrates.domain.models import (
    InjectableReasoningContent,
    ReasoningContentProjections,
    SelectionCatalog,
    SelectionCatalogEntry,
    TemplateExample,
)
from opensocrates.hooks.entrypoint import run_hook
from opensocrates.hosts.codex.adapter import CodexAdapter, CodexAdapterConfig
from opensocrates.hosts.codex.commands import build_hooks
from opensocrates.selector.application import SelectorApplication
from opensocrates.selector.artifacts import (
    INSTRUCTION_FILE_TTL_SECONDS,
    InstructionFileStore,
)
from opensocrates.selector.context import (
    MAX_CONTEXT_CALLS,
    SelectorContextAccessor,
    SelectorContextHandles,
    handles_for_request,
)
from opensocrates.selector.models import (
    SelectorConfig,
    SelectorRequest,
    validate_raw_candidate,
)
from opensocrates.selector.sdk import CodexReasoningSelector
from opensocrates.selector.sdk_worker import (
    SELECTOR_RECURSION_ENV,
    SelectorWorkerRequest,
    _config_overrides,
    _context_tool_schema,
    _ContextToolHandler,
    _isolated_environment,
    _LiveSdkCall,
    _selector_turn_input,
    _thread_config,
    _thread_start_params,
    _watch_deadline,
)

_REVISION = 7
_METHODS = ("alpha-reasoning", "beta-reasoning", "gamma-reasoning")
_CHECKS: list[tuple[str, Callable[[], None]]] = []


class _ContractFailure(AssertionError):
    """A deliberately content-free contract-test failure."""


def _check(name: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
    def register(function: Callable[[], None]) -> Callable[[], None]:
        _CHECKS.append((name, function))
        return function

    return register


def _require(condition: bool) -> None:
    if not condition:
        raise _ContractFailure


def _expect_raises(function: Callable[[], object]) -> None:
    try:
        function()
    except Exception:
        return
    raise _ContractFailure


def _example(method_id: str, locale: Literal["en", "ko"]) -> TemplateExample:
    return TemplateExample(
        case_id=f"synthetic-{locale}-{method_id}",
        kind="synthetic",
        template_prompt=f"SYNTHETIC_TEMPLATE_{locale}_{method_id}",
        expected_route=method_id,
        expected_behavior="synthetic-behavior",
        decisive_features=("synthetic-feature",),
        rationale="synthetic-rationale",
    )


def _projections(
    *,
    korean_for_all: bool = False,
    theory_padding: int = 0,
) -> ReasoningContentProjections:
    entries: list[SelectionCatalogEntry] = []
    injectable: list[InjectableReasoningContent] = []
    for index, method_id in enumerate(_METHODS, start=1):
        english_name = f"Synthetic {index}"
        korean_name = f"합성 {index}"
        entries.append(
            SelectionCatalogEntry(
                method_id=method_id,
                family="synthetic-family",
                content_revision=_REVISION,
                display_name={"en": english_name, "ko": korean_name},
                core_purpose={"en": "synthetic-purpose", "ko": "합성-목적"},
                injectable_content_locator=f"synthetic/{method_id}",
            )
        )
        locales: tuple[tuple[Literal["en", "ko"], str], ...] = (
            ("en", english_name),
            ("ko", korean_name),
        )
        for locale, display_name in locales:
            if locale == "ko" and not (korean_for_all or method_id != _METHODS[-1]):
                continue
            padding = "x" * theory_padding
            injectable.append(
                InjectableReasoningContent(
                    method_id=method_id,
                    content_revision=_REVISION,
                    locale=locale,
                    display_name=display_name,
                    theory=f"SYNTHETIC_THEORY_{locale}_{method_id}{padding}",
                    template_examples=(_example(method_id, locale),),
                )
            )
    return ReasoningContentProjections(
        content_revision=_REVISION,
        selection_catalog=SelectionCatalog(content_revision=_REVISION, entries=tuple(entries)),
        injectable_content=tuple(injectable),
    )


def _request(
    *, prompt: str = "synthetic English prompt", turn_id: str = "turn-a"
) -> SelectorRequest:
    return SelectorRequest(
        prompt=prompt,
        transcript_path=Path("/synthetic/transcript.jsonl"),
        cwd=Path("/synthetic/workspace"),
        session_id="synthetic-session",
        turn_id=turn_id,
        transcript_referenced_file_paths=(Path("/synthetic/referenced.txt"),),
        tool_data_handle=object(),
    )


@dataclass
class _FakeSelector:
    candidate: Mapping[str, object] | None
    calls: list[tuple[SelectorRequest, object, int, str]] = field(default_factory=list)

    def select(
        self,
        request: SelectorRequest,
        context: object,
        *,
        deadline_seconds: int,
        reasoning_effort: str,
    ) -> Mapping[str, object] | None:
        self.calls.append((request, context, deadline_seconds, reasoning_effort))
        return self.candidate


@dataclass
class _SyntheticRuntime:
    adapter: CodexAdapter
    calls: int = 0

    def adapter_for(self, host: str) -> CodexAdapter | None:
        self.calls += 1
        return self.adapter if host == "codex" else None


@dataclass
class _FakeEvent:
    wait_result: bool = False
    set_count: int = 0

    def is_set(self) -> bool:
        return self.set_count > 0

    def set(self) -> None:
        self.set_count += 1

    def wait(self, timeout: float | None = None) -> bool:
        del timeout
        return self.wait_result


@dataclass
class _FakeTurn:
    interrupts: int = 0

    def interrupt(self) -> None:
        self.interrupts += 1


@dataclass
class _FakeSdkClient:
    closes: int = 0

    def close(self) -> None:
        self.closes += 1


def _candidate(*, selected: tuple[str, ...] = _METHODS) -> dict[str, object]:
    return {
        "intervene": True,
        "selected_reasoning_systems": list(selected),
        "instructions": "SYNTHETIC_RAW_CANDIDATE_MARKER",
    }


def _native_payload(event_name: str, **fields: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "hook_event_name": event_name,
        "session_id": "synthetic-session",
        "turn_id": "turn-a",
        "version": "synthetic-version",
    }
    if event_name == "UserPromptSubmit":
        payload["prompt"] = "synthetic English prompt"
    elif event_name == "SessionStart":
        payload["source"] = "startup"
    elif event_name in {"PreCompact", "PostCompact"}:
        payload["trigger"] = "auto"
    elif event_name == "SessionEnd":
        payload["reason"] = "other"
    elif event_name == "PreToolUse":
        payload.update({"tool_name": "Bash", "tool_input": {}})
    elif event_name == "PostToolUse":
        payload.update(
            {
                "tool_name": "Bash",
                "tool_input": {},
                "tool_response": {"synthetic": True},
            }
        )
    payload.update(fields)
    return payload


@_check("VSC-01-content-assembly-selected-only")
def _test_content_assembly() -> None:
    projections = _projections()
    assembled = assemble_canonical_instruction(
        projections,
        (_METHODS[2], _METHODS[0]),
        "synthetic English prompt",
        expected_content_revision=_REVISION,
    )
    _require(assembled.selected_reasoning_systems == (_METHODS[2], _METHODS[0]))
    _require(
        assembled.instructions.find("Synthetic 3") < assembled.instructions.find("Synthetic 1")
    )
    _require("SYNTHETIC_THEORY_en_gamma-reasoning" in assembled.instructions)
    _require("SYNTHETIC_TEMPLATE_en_gamma-reasoning" in assembled.instructions)
    _require("SYNTHETIC_THEORY_en_beta-reasoning" not in assembled.instructions)
    _require("untrusted template data" in assembled.instructions)
    _require(
        validate_candidate_instruction(
            projections,
            (_METHODS[2], _METHODS[0]),
            "synthetic English prompt",
            assembled.instructions,
            expected_content_revision=_REVISION,
        )
        == assembled
    )
    _expect_raises(
        lambda: validate_candidate_instruction(
            projections,
            (_METHODS[2], _METHODS[0]),
            "synthetic English prompt",
            "SYNTHETIC_INVENTED_PROSE",
            expected_content_revision=_REVISION,
        )
    )


@_check("VSC-02-locale-current-prompt-and-english-fallback")
def _test_locale_resolution() -> None:
    projections = _projections()
    _require(resolve_prompt_locale("가나다") == "ko")
    _require(resolve_prompt_locale("가ab") == "en")
    _require(
        resolve_injection_locale(
            projections,
            (_METHODS[0], _METHODS[1]),
            "가나다",
            expected_content_revision=_REVISION,
        )
        == "ko"
    )
    _require(
        resolve_injection_locale(
            projections,
            (_METHODS[0], _METHODS[2]),
            "가나다",
            expected_content_revision=_REVISION,
        )
        == "en"
    )
    fallback = assemble_canonical_instruction(
        projections,
        (_METHODS[0], _METHODS[2]),
        "가나다",
        expected_content_revision=_REVISION,
    )
    _require(fallback.locale == "en")
    _require("합성" not in fallback.instructions)


@_check("VSC-03-raw-candidate-three-field-and-no-cap")
def _test_raw_candidate_validation() -> None:
    accepted = validate_raw_candidate(_candidate(), known_method_ids=_METHODS)
    _require(accepted.selected_reasoning_systems == _METHODS)
    _require(len(accepted.selected_reasoning_systems) == 3)
    unbounded_ids = tuple(f"synthetic-method-{number:03d}" for number in range(49))
    no_cap = validate_raw_candidate(
        _candidate(selected=unbounded_ids), known_method_ids=unbounded_ids
    )
    _require(no_cap.selected_reasoning_systems == unbounded_ids)
    invalid_candidates: tuple[object, ...] = (
        {**_candidate(), "unexpected": True},
        {"intervene": False, "selected_reasoning_systems": [], "instructions": "not-empty"},
        {"intervene": True, "selected_reasoning_systems": [], "instructions": "x"},
        {
            "intervene": True,
            "selected_reasoning_systems": [_METHODS[0], _METHODS[0]],
            "instructions": "x",
        },
        {"intervene": True, "selected_reasoning_systems": ["unknown-method"], "instructions": "x"},
    )
    for candidate in invalid_candidates:
        try:
            validate_raw_candidate(candidate, known_method_ids=_METHODS)
        except Exception:
            continue
        raise _ContractFailure


@_check("VSC-04-prompt-first-opt-out-and-fresh-call")
def _test_application_opt_out_and_deadline() -> None:
    with tempfile.TemporaryDirectory(prefix="opensocrates-application-check-") as name:
        store = InstructionFileStore(
            installation_key=b"a" * 32,
            directory=Path(name) / "artifacts",
        )
        fake = _FakeSelector(_candidate(selected=(_METHODS[0], _METHODS[1])))
        application = SelectorApplication(
            selector=fake,
            assembler=ProjectionInstructionAssembler(_projections()),
            config=SelectorConfig(transcript_access_enabled=False),
            artifact_store=store,
        )
        request = _request(prompt="가나다")
        decision = application.select_for_user_prompt_submit(request)
        if decision is None:
            raise _ContractFailure
        _require(len(fake.calls) == 1)
        effective_request, context, deadline, effort = fake.calls[0]
        _require(effective_request.transcript_path is None)
        _require(effective_request.transcript_referenced_file_paths == ())
        _require(getattr(context, "transcript_access_enabled", None) is False)
        _require(getattr(context, "transcript_path", object()) is None)
        _require(deadline == 30 and effort == "medium")
        _require(decision.selected_reasoning_systems == (_METHODS[0], _METHODS[1]))
        _require("SYNTHETIC_RAW_CANDIDATE_MARKER" not in decision.instructions)
        _require("합성 1" in decision.instructions and "합성 2" in decision.instructions)
        artifact = store.latest_for_session(request.session_id)
        _require(artifact is not None and artifact.path.is_file())
        artifact_text = artifact.path.read_text(encoding="utf-8")
        _require("SYNTHETIC_THEORY_ko_alpha-reasoning" in artifact_text)
        _require("SYNTHETIC_RAW_CANDIDATE_MARKER" not in artifact_text)

    no_retry = _FakeSelector(None)
    rejected = SelectorApplication(
        selector=no_retry,
        assembler=ProjectionInstructionAssembler(_projections()),
        config=SelectorConfig(deadline_seconds=1),
    ).select_for_user_prompt_submit(_request(turn_id="turn-timeout"))
    _require(rejected is None and len(no_retry.calls) == 1)
    _require(no_retry.calls[0][2] == 1)
    _expect_raises(lambda: SelectorConfig(deadline_seconds=31))


@_check("VSC-05-large-canonical-content-moves-to-bounded-file-reference")
def _test_large_file_reference() -> None:
    projections = _projections(theory_padding=10_000)
    assembled = assemble_canonical_instruction(
        projections,
        (_METHODS[0], _METHODS[1]),
        "synthetic English prompt",
        expected_content_revision=_REVISION,
    )
    _require(assembled.estimated_tokens >= 2_500)
    with tempfile.TemporaryDirectory(prefix="opensocrates-large-file-check-") as name:
        store = InstructionFileStore(
            installation_key=b"l" * 32,
            directory=Path(name) / "artifacts",
        )
        fake = _FakeSelector(_candidate(selected=(_METHODS[0], _METHODS[1])))
        application = SelectorApplication(
            selector=fake,
            assembler=ProjectionInstructionAssembler(projections),
            artifact_store=store,
        )
        decision = application.select_for_user_prompt_submit(_request())
        _require(decision is not None and len(fake.calls) == 1)
        _require(len(decision.instructions.encode("utf-8")) < 2_500 * 4)
        artifact = store.latest_for_session("synthetic-session")
        _require(artifact is not None and artifact.path.stat().st_size > 2_500 * 4)


@_check("VSC-06-temporary-artifact-permissions-lifecycle-and-24h-cleanup")
def _test_instruction_artifacts() -> None:
    clock = FrozenClock(1_700_000_000_000_000_000)
    with tempfile.TemporaryDirectory(prefix="opensocrates-selector-check-") as temporary_name:
        directory = Path(temporary_name) / "artifacts"
        store = InstructionFileStore(
            installation_key=b"s" * 32,
            directory=directory,
            clock=clock,
        )
        fake = _FakeSelector(_candidate(selected=(_METHODS[0],)))
        application = SelectorApplication(
            selector=fake,
            assembler=ProjectionInstructionAssembler(_projections()),
            artifact_store=store,
        )
        request = _request()
        decision = application.select_for_user_prompt_submit(request)
        _require(decision is not None and len(fake.calls) == 1)
        artifact = store.latest_for_session(request.session_id)
        _require(artifact is not None and artifact.path.is_file())
        encoded = artifact.path.read_bytes()
        _require(b"synthetic/transcript" not in encoded)
        _require(b"SYNTHETIC_RAW_CANDIDATE_MARKER" not in encoded)
        _require(b"SYNTHETIC_THEORY_en_alpha-reasoning" in encoded)
        if os.name != "nt":
            _require(stat.S_IMODE(directory.stat().st_mode) == 0o700)
            _require(stat.S_IMODE(artifact.path.stat().st_mode) == 0o600)

        stale_seconds = clock.unix_time_ns() // 1_000_000_000 - INSTRUCTION_FILE_TTL_SECONDS - 1
        os.utime(artifact.path, (stale_seconds, stale_seconds))
        _require(store.sweep_expired() >= 1)
        _require(not artifact.path.exists())

        decision = application.select_for_user_prompt_submit(request)
        _require(decision is not None)
        current = store.latest_for_session(request.session_id)
        _require(current is not None)
        _require(store.delete_turn(request.session_id, request.turn_id) >= 1)
        _require(not current.path.exists())

        other_request = _request(turn_id="turn-b")
        _require(application.select_for_user_prompt_submit(other_request) is not None)
        session_artifact = store.latest_for_session(other_request.session_id)
        _require(session_artifact is not None)
        _require(store.delete_session(other_request.session_id) >= 1)
        _require(not session_artifact.path.exists())


@_check("VSC-06A-complete-48-method-catalog-fits-one-temporary-file")
def _test_complete_catalog_artifact() -> None:
    projections = load_reasoning_content_projections(
        Path("content/compiled-reasoning-content.bundle.json")
    )
    selected = tuple(entry.method_id for entry in projections.selection_catalog.entries)
    _require(len(selected) == 48)
    with tempfile.TemporaryDirectory(prefix="opensocrates-full-catalog-check-") as name:
        store = InstructionFileStore(
            installation_key=b"f" * 32,
            directory=Path(name) / "artifacts",
        )
        for locale in ("en", "ko"):
            assembled = ProjectionInstructionAssembler(projections).assemble(
                selected,
                requested_locale=locale,
            )
            artifact = store.create(
                "synthetic-full-catalog-session",
                f"synthetic-{locale}-turn",
                assembled,
            )
            _require(artifact.path.is_file())
            _require(artifact.path.stat().st_size < 1024 * 1024)
            reference = artifact.reference_message()
            _require(all(name in reference for name in assembled.selected_display_names))
        _require(store.delete_session("synthetic-full-catalog-session") >= 1)


@_check("VSC-06B-workspace-root-preferred-git-invisible-and-cleaned")
def _test_workspace_artifact_root() -> None:
    assembled = assemble_canonical_instruction(
        _projections(),
        (_METHODS[0],),
        "synthetic English prompt",
        expected_content_revision=_REVISION,
    )
    with tempfile.TemporaryDirectory(prefix="opensocrates-workspace-root-check-") as name:
        root = Path(name)
        workspace = root / "workspace"
        temporary_root = root / "temporary"
        workspace.mkdir()
        temporary_root.mkdir()
        subprocess.run(
            ("git", "init", "--quiet", str(workspace)),
            check=True,
            capture_output=True,
            text=True,
        )
        with patch(
            "opensocrates.selector.artifacts.tempfile.gettempdir", return_value=str(temporary_root)
        ):
            store = InstructionFileStore(
                installation_key=b"w" * 32,
                workspace=workspace,
            )
            artifact = store.create("workspace-session", "workspace-turn", assembled)
            _require(artifact.path.is_relative_to(workspace.resolve() / ".opensocrates"))
            ignore = workspace / ".opensocrates" / ".gitignore"
            _require(ignore.read_bytes() == b"*\n")
            if os.name != "nt":
                _require(stat.S_IMODE(ignore.stat().st_mode) == 0o600)
                _require(stat.S_IMODE(artifact.path.parent.stat().st_mode) == 0o700)
                _require(stat.S_IMODE(artifact.path.stat().st_mode) == 0o600)
            status = subprocess.run(
                ("git", "status", "--porcelain", "--untracked-files=all"),
                cwd=workspace,
                check=True,
                capture_output=True,
                text=True,
            )
            _require(status.stdout == "")
            _require(store.delete_session("workspace-session") >= 1)
            _require(not (workspace / ".opensocrates").exists())


@_check("VSC-06C-workspace-root-fallback-and-cross-root-receipts")
def _test_workspace_fallback_and_cross_root_receipts() -> None:
    assembled = assemble_canonical_instruction(
        _projections(),
        (_METHODS[0],),
        "synthetic English prompt",
        expected_content_revision=_REVISION,
    )
    with tempfile.TemporaryDirectory(prefix="opensocrates-cross-root-check-") as name:
        root = Path(name)
        temporary_root = root / "temporary"
        workspace = root / "workspace"
        temporary_root.mkdir()
        workspace.mkdir()
        installation_key = b"x" * 32
        with patch(
            "opensocrates.selector.artifacts.tempfile.gettempdir", return_value=str(temporary_root)
        ):
            legacy_store = InstructionFileStore(installation_key=installation_key)
            legacy = legacy_store.create("cross-session", "legacy-turn", assembled)
            _require(
                legacy_store.record_complete_read(
                    "cross-session",
                    "legacy-turn",
                    file_path=legacy.path,
                    tool_use_id="legacy-read",
                    offset=0,
                    limit=None,
                    end_marker_seen=True,
                )
            )

            workspace_store = InstructionFileStore(
                installation_key=installation_key,
                workspace=workspace,
            )
            _require(workspace_store.accepts_artifact_path(legacy.path))
            _require(workspace_store.has_complete_read_receipt(legacy))
            current = workspace_store.create("cross-session", "workspace-turn", assembled)
            _require(current.path.is_relative_to(workspace.resolve() / ".opensocrates"))
            _require(workspace_store.accepts_artifact_path(current.path))
            _require(workspace_store.latest_for_session("cross-session") == current)
            _require(
                workspace_store.record_complete_read(
                    "cross-session",
                    "workspace-turn",
                    file_path=current.path,
                    tool_use_id="workspace-read",
                    offset=0,
                    limit=None,
                    end_marker_seen=True,
                )
            )
            _require(workspace_store.has_complete_read_receipt(current))
            _require(workspace_store.delete_session("cross-session") >= 1)
            _require(not (workspace / ".opensocrates").exists())

            foreign_workspace = root / "foreign-workspace"
            foreign_workspace.mkdir()
            foreign_container = foreign_workspace / ".opensocrates"
            foreign_container.mkdir()
            (foreign_container / "foreign-data").write_text("synthetic", encoding="utf-8")
            fallback_store = InstructionFileStore(
                installation_key=b"y" * 32,
                workspace=foreign_workspace,
            )
            fallback = fallback_store.create("fallback-session", "fallback-turn", assembled)
            _require(fallback.path.is_relative_to(temporary_root.resolve()))
            _require(not fallback.path.is_relative_to(foreign_container.resolve()))
            _require(fallback_store.delete_session("fallback-session") >= 1)


@_check("VSC-07-context-on-demand-contained-and-bounded")
def _test_context_accessor_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="opensocrates-selector-context-check-") as name:
        root = Path(name)
        workspace = root / "workspace"
        nested = workspace / "nested"
        workspace.mkdir()
        nested.mkdir()
        transcript = root / "transcript.jsonl"
        referenced = root / "referenced.txt"
        outside = root / "outside.txt"
        workspace_file = nested / "context.txt"
        transcript.write_text("SYNTHETIC_TRANSCRIPT_DATA", encoding="utf-8")
        referenced.write_text("SYNTHETIC_REFERENCED_DATA", encoding="utf-8")
        outside.write_text("SYNTHETIC_OUTSIDE_DATA", encoding="utf-8")
        workspace_file.write_text("SYNTHETIC_WORKSPACE_DATA", encoding="utf-8")
        symlink = workspace / "escape.txt"
        if os.name == "posix":
            symlink.symlink_to(outside)

        handles = SelectorContextHandles(
            transcript_path=transcript,
            cwd=workspace,
            transcript_referenced_file_paths=(referenced,),
            tool_data_handle=object(),
        )
        accessor = SelectorContextAccessor(handles)
        _require(
            accessor.available_operations()
            == (
                "read_transcript",
                "list_workspace",
                "read_workspace_file",
                "read_referenced_file",
            )
        )

        worker_request = SelectorWorkerRequest(
            current_prompt="SYNTHETIC_CURRENT_PROMPT",
            selection_catalog='{"entries":[]}',
            reasoning_effort="medium",
            transcript_access_enabled=True,
            transcript_path=str(transcript),
            workspace_path=str(workspace),
            transcript_referenced_file_paths=(str(referenced),),
        )
        turn_input = _selector_turn_input(worker_request)
        _require(
            turn_input.index("SYNTHETIC_CURRENT_PROMPT")
            < turn_input.index("SELECTION_CATALOG_CANONICAL_DATA")
        )
        for raw_path in (transcript, workspace, referenced):
            _require(str(raw_path) not in turn_input)

        listed = accessor.list_workspace()
        transcript_value = accessor.read_transcript()
        workspace_value = accessor.read_workspace_file("nested/context.txt")
        referenced_value = accessor.read_referenced_file(0)
        _require(listed is not None)
        _require(transcript_value is not None)
        _require(workspace_value is not None)
        _require(referenced_value is not None)
        _require(accessor.bytes_read > 0)
        _require(accessor.read_workspace_file("../outside.txt") is None)
        _require(accessor.read_workspace_file(str(outside)) is None)
        if os.name == "posix":
            _require(accessor.read_workspace_file("escape.txt") is None)
            transcript_link = root / "transcript-link.jsonl"
            transcript_link.symlink_to(transcript)
            linked_accessor = SelectorContextAccessor(
                SelectorContextHandles(transcript_path=transcript_link)
            )
            _require(linked_accessor.read_transcript() is None)
        while accessor.calls < MAX_CONTEXT_CALLS:
            _require(accessor.read_workspace_file("nested/context.txt") is not None)
        _require(accessor.read_workspace_file("nested/context.txt") is None)

        callback_accessor = SelectorContextAccessor(handles)
        handler = _ContextToolHandler(callback_accessor)
        callback = handler(
            "item/tool/call",
            {
                "tool": "read_context",
                "namespace": None,
                "arguments": {"operation": "read_transcript", "offset": 0},
            },
        )
        _require(callback.get("success") is True)
        callback_text = json.dumps(callback, ensure_ascii=False)
        _require("SYNTHETIC_TRANSCRIPT_DATA" in callback_text)
        for raw_path in (transcript, workspace, referenced):
            _require(str(raw_path) not in callback_text)
        _require(handler("unexpected/request", {}) == {})

        schema = _context_tool_schema(callback_accessor)
        _require(schema.get("name") == "read_context")
        params = _thread_start_params(callback_accessor, workspace=root / "isolated")
        _require("model" not in params)
        _require(params.get("approvalPolicy") == "never")
        _require(params.get("environments") == [])
        _require(params.get("ephemeral") is True)
        _require(params.get("sandbox") == "read-only")
        dynamic_tools = params.get("dynamicTools")
        _require(isinstance(dynamic_tools, list) and len(dynamic_tools) == 1)

        disabled = SelectorContextAccessor(
            SelectorContextHandles(cwd=workspace, transcript_access_enabled=False)
        )
        _require("read_transcript" not in disabled.available_operations())


@_check("VSC-08-recursion-guard-and-sdk-policy-static-contract")
def _test_sdk_policy_contract() -> None:
    config = _thread_config()
    _require(SELECTOR_RECURSION_ENV == "OPENSOCRATES_SELECTOR_ACTIVE")
    original_environment = os.environ.copy()
    try:
        with tempfile.TemporaryDirectory(
            prefix="opensocrates-selector-sdk-check-"
        ) as temporary_name:
            root = Path(temporary_name)
            environment = _isolated_environment(root, root / "oauth")
            overrides = _config_overrides(environment)
            _require(not any(value.startswith("model=") for value in overrides))
            _require('web_search="disabled"' in overrides)
            _require("features.hooks=false" in overrides)
            _require("features.plugins=false" in overrides)
            _require("features.shell_tool=false" in overrides)
            _require("features.unified_exec=false" in overrides)
            _require("model_providers.opensocrates_selector.request_max_retries=0" in overrides)
            _require('shell_environment_policy.inherit="none"' in overrides)
            _require(f'shell_environment_policy.set.{SELECTOR_RECURSION_ENV}="1"' in overrides)
    finally:
        os.environ.clear()
        os.environ.update(original_environment)
    _require(config.get("web_search") == "disabled")
    features = config.get("features")
    if not isinstance(features, dict):
        raise _ContractFailure
    _require(features.get("hooks") is False and features.get("plugins") is False)
    _require(features.get("shell_tool") is False and features.get("unified_exec") is False)

    request = _request()
    _, context = handles_for_request(request, SelectorConfig())
    selector = CodexReasoningSelector(_projections().selection_catalog)
    worker_starts: list[object] = []

    def no_worker(worker_input: object, *, cancel_at: float) -> None:
        del cancel_at
        worker_starts.append(worker_input)
        return None

    with patch.object(selector, "_start_worker", no_worker):
        _require(
            selector.select(request, context, deadline_seconds=30, reasoning_effort="medium")
            is None
        )
        _require(
            selector.select(request, context, deadline_seconds=30, reasoning_effort="medium")
            is None
        )
    _require(len(worker_starts) == 2 and worker_starts[0] is not worker_starts[1])
    selector.close()

    cancellation = _FakeEvent()
    completed = _FakeEvent()
    wake = _FakeEvent()
    turn = _FakeTurn()
    client = _FakeSdkClient()
    live_call = _LiveSdkCall()
    live_call.retain_turn(turn)
    live_call.retain_codex(client)
    _watch_deadline(cancellation, completed, wake, live_call, cancel_at=0.0)
    _require(cancellation.is_set() and turn.interrupts == 1 and client.closes == 1)


@_check("VSC-09-codex-selector-host-lifecycle-and-hook-config")
def _test_codex_selector_host_contract() -> None:
    hooks = build_hooks()["hooks"]
    user_prompt_handler = hooks["UserPromptSubmit"][0]["hooks"][0]
    _require("timeout" not in user_prompt_handler)
    _require("PostCompact" not in hooks)
    _require(hooks["SessionEnd"][0]["hooks"][0]["timeout"] == 3)

    clock = FrozenClock(1_700_000_000_000_000_000)
    with tempfile.TemporaryDirectory(prefix="opensocrates-selector-host-check-") as temporary_name:
        store = InstructionFileStore(
            installation_key=b"h" * 32,
            directory=Path(temporary_name) / "artifacts",
            clock=clock,
        )
        fake = _FakeSelector(_candidate(selected=(_METHODS[0], _METHODS[1])))
        application = SelectorApplication(
            selector=fake,
            assembler=ProjectionInstructionAssembler(_projections()),
            config=SelectorConfig(transcript_access_enabled=False),
            artifact_store=store,
        )
        adapter = CodexAdapter(
            CodexAdapterConfig(
                selector_mode=True,
                selector_application=application,
                instruction_file_store=store,
            )
        )

        injected = adapter.handle(_native_payload("UserPromptSubmit"))
        _require(len(fake.calls) == 1)
        injected_response = injected.stdout
        parsed = json.loads(injected_response)
        _require(set(parsed) == {"hookSpecificOutput"})
        specific = parsed["hookSpecificOutput"]
        _require(set(specific) == {"hookEventName", "additionalContext"})
        _require(specific["hookEventName"] == "UserPromptSubmit")
        _require(isinstance(specific["additionalContext"], str))
        _require("SYNTHETIC_RAW_CANDIDATE_MARKER" not in specific["additionalContext"])
        artifact = store.latest_for_session("synthetic-session")
        _require(artifact is not None and artifact.path.is_file())

        for event_name in ("SessionStart", "PreToolUse", "PostToolUse", "PreCompact"):
            _require(adapter.handle(_native_payload(event_name)).stdout == "")
        _require(len(fake.calls) == 1)

        restored = adapter.handle(_native_payload("SessionStart", source="compact"))
        restored_response = json.loads(restored.stdout)
        _require(restored_response["hookSpecificOutput"]["hookEventName"] == "SessionStart")
        _require(len(fake.calls) == 1)
        _require(adapter.handle(_native_payload("PostCompact")).stdout == "")

        _require(adapter.handle(_native_payload("Stop")).stdout == "")
        _require(not artifact.path.exists())
        _require(len(fake.calls) == 1)

        second_prompt = _native_payload("UserPromptSubmit", turn_id="turn-b")
        _require(adapter.handle(second_prompt).stdout != "")
        session_artifact = store.latest_for_session("synthetic-session")
        _require(session_artifact is not None)
        _require(adapter.handle(_native_payload("SessionEnd")).stdout == "")
        _require(not session_artifact.path.exists())

        malformed = CodexAdapter(
            CodexAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=_FakeSelector({"unexpected": True}),
                    assembler=ProjectionInstructionAssembler(_projections()),
                    artifact_store=store,
                ),
                instruction_file_store=store,
            )
        )
        no_decision = CodexAdapter(
            CodexAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=_FakeSelector(None),
                    assembler=ProjectionInstructionAssembler(_projections()),
                    artifact_store=store,
                ),
                instruction_file_store=store,
            )
        )
        prompt = _native_payload("UserPromptSubmit")
        _require(malformed.handle(prompt).stdout == "")
        _require(no_decision.handle(prompt).stdout == "")


@_check("VSC-10-hook-entrypoint-empty-stdout-and-recursion-guard")
def _test_hook_entrypoint_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="opensocrates-entrypoint-check-") as name:
        store = InstructionFileStore(
            installation_key=b"e" * 32,
            directory=Path(name) / "artifacts",
        )
        fake = _FakeSelector(_candidate(selected=(_METHODS[0],)))
        adapter = CodexAdapter(
            CodexAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=fake,
                    assembler=ProjectionInstructionAssembler(_projections()),
                    artifact_store=store,
                ),
                instruction_file_store=store,
            )
        )
        runtime = _SyntheticRuntime(adapter)

        output = StringIO()
        exit_code = run_hook(
            ("codex", "user_prompt_submitted"),
            stdin=BytesIO(json.dumps(_native_payload("UserPromptSubmit")).encode("utf-8")),
            stdout=output,
            services=runtime,
        )
        _require(exit_code == 0)
        response = json.loads(output.getvalue())
        _require(set(response) == {"hookSpecificOutput"})
        _require(runtime.calls == 1 and len(fake.calls) == 1)

        for native_event, lane in (
            ("SessionStart", "session_started"),
            ("PreToolUse", "tool_succeeded"),
            ("PostToolUse", "tool_succeeded"),
            ("PreCompact", "pre_compaction"),
            ("Stop", "completion_candidate"),
            ("SessionEnd", "session_ended"),
        ):
            output = StringIO()
            exit_code = run_hook(
                ("codex", lane),
                stdin=BytesIO(json.dumps(_native_payload(native_event)).encode("utf-8")),
                stdout=output,
                services=runtime,
            )
            _require(exit_code == 0 and output.getvalue() == "")
        _require(len(fake.calls) == 1)

    no_decision = _SyntheticRuntime(
        CodexAdapter(
            CodexAdapterConfig(
                selector_mode=True,
                selector_application=SelectorApplication(
                    selector=_FakeSelector(None),
                    assembler=ProjectionInstructionAssembler(_projections()),
                ),
            )
        )
    )
    for raw in (
        json.dumps(_native_payload("UserPromptSubmit")).encode("utf-8"),
        b"not-json",
    ):
        output = StringIO()
        exit_code = run_hook(
            ("codex", "user_prompt_submitted"),
            stdin=BytesIO(raw),
            stdout=output,
            services=no_decision,
        )
        _require(exit_code == 0 and output.getvalue() == "")

    constructed = [False]

    def unexpected_runtime(*_args: object, **_kwargs: object) -> object:
        constructed[0] = True
        raise _ContractFailure

    original_marker = os.environ.get(SELECTOR_RECURSION_ENV)
    try:
        os.environ[SELECTOR_RECURSION_ENV] = "1"
        with patch("opensocrates.cli.runtime.build_runtime_services", unexpected_runtime):
            output = StringIO()
            exit_code = run_hook(
                ("codex", "user_prompt_submitted"),
                stdin=BytesIO(json.dumps(_native_payload("UserPromptSubmit")).encode("utf-8")),
                stdout=output,
            )
        _require(exit_code == 0 and output.getvalue() == "" and not constructed[0])
    finally:
        if original_marker is None:
            os.environ.pop(SELECTOR_RECURSION_ENV, None)
        else:
            os.environ[SELECTOR_RECURSION_ENV] = original_marker

    captured: list[dict[str, object]] = []

    def capture_runtime(**kwargs: object) -> _SyntheticRuntime:
        captured.append(dict(kwargs))
        return no_decision

    workspace = str(Path(tempfile.gettempdir()).resolve())
    payload = _native_payload("UserPromptSubmit", cwd=workspace)
    with patch("opensocrates.cli.runtime.build_runtime_services", capture_runtime):
        output = StringIO()
        exit_code = run_hook(
            ("claude", "user_prompt_submitted"),
            stdin=BytesIO(json.dumps(payload).encode("utf-8")),
            stdout=output,
        )
    _require(exit_code == 0 and output.getvalue() == "")
    _require(captured == [{"host": "claude", "workspace": workspace}])


def main() -> int:
    failures: list[str] = []
    for name, check in _CHECKS:
        try:
            check()
        except Exception:
            failures.append(name)
            print(f"FAIL {name}")
        else:
            print(f"PASS {name}")
    if failures:
        print(f"opensocrates-selector-contract: FAIL {len(failures)}/{len(_CHECKS)}")
        return 1
    print(f"opensocrates-selector-contract: PASS {len(_CHECKS)}/{len(_CHECKS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
