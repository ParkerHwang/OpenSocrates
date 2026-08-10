"""Codex native adapter: bounded parse, safe projection, injected dispatch."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable

from ...clock import Clock
from ...domain.enums import EventType, HostActionKind, HostId
from ...domain.models import CapabilityProfile, HostControlResult, NormalizedEvent
from ...selector import SelectorApplication, SelectorConfig, SelectorDecision, SelectorRequest
from ...version import PRODUCT_VERSION
from ..common import (
    ControlApplicationPort,
    EventApplicationPort,
    HostAction,
    StopDecision,
    StopDecisionPort,
)
from .capability import (
    capability_profile_for_availability,
    default_capability_profile,
)
from .events import normalize_codex_event, project_codex_payload
from .native import CodexNativeEvent, NativeParseResult, try_parse_codex_event
from .responses import (
    NativeResponseError,
    response_object,
    selector_context_response,
    serialize_codex_response,
    serialize_response_object,
)

DEFAULT_BUNDLE_PATH = Path("content/compiled-content.bundle.json")


@dataclass(frozen=True, slots=True)
class CodexAdapterConfig:
    """Explicit dependencies and trust state for one Codex adapter."""

    host: HostId = HostId.CODEX_CLI
    installation_key: bytes | None = None
    capability_profile: CapabilityProfile | None = None
    clock: Clock | None = None
    host_version: str = "unknown"
    adapter_version: str = PRODUCT_VERSION
    locale: str = "en"
    bundle_path: str | Path = DEFAULT_BUNDLE_PATH
    content_repository: Any | None = None
    control_application: ControlApplicationPort | None = None
    stop_decision_port: StopDecisionPort | None = None
    event_application: EventApplicationPort | None = None
    prompt_application: Any | None = None
    observation_application: Any | None = None
    context_factory: Callable[[NormalizedEvent], object] | None = None
    repair_count_provider: Callable[[NormalizedEvent], int] | None = None
    turn_repository: Any | None = None
    settings_repository: Any | None = None
    dispatcher: Any | None = None
    features_hooks: bool | None = None
    features: Mapping[str, object] | None = None
    trust_state: str = "unknown"
    allow_managed_hooks_only: bool = False
    plugin_hooks_loaded: bool | None = None
    managed_hooks_loaded: bool | None = None
    # ``selector_mode`` is set by packaged OpenSocrates composition even if one of
    # its dependencies is unavailable.  That distinction prevents an
    # unavailable selector from silently falling back to legacy injection.
    selector_mode: bool = False
    selector_application: SelectorApplication | None = field(default=None, repr=False)
    selector_config: SelectorConfig | None = field(default=None, repr=False)
    instruction_file_store: Any | None = field(default=None, repr=False)
    require_instruction_read_receipt: bool = False


@dataclass(frozen=True, slots=True)
class CodexHandleResult:
    """Transient adapter result; no native mapping or raw content is kept."""

    native_event_name: str | None
    normalized_event: NormalizedEvent | None
    action: HostAction
    response: dict[str, Any] = field(repr=False)
    projection: dict[str, Any]
    status: str = "accepted"
    diagnostics: tuple[str, ...] = ()
    error_code: str | None = None
    capability_limitations: tuple[str, ...] = ()
    literal_empty: bool = False
    selector_response: bool = False

    @property
    def accepted(self) -> bool:
        return self.error_code is None and self.status not in {
            "pass_through",
            "reject_before_domain_parse",
            "unsupported",
        }

    @property
    def pass_through(self) -> bool:
        return (
            self.status in {"pass_through", "reject_before_domain_parse"}
            or self.error_code is not None
        )

    @property
    def stdout(self) -> str:
        if self.literal_empty:
            return ""
        if self.selector_response:
            return serialize_response_object(self.response)
        if self.native_event_name is None:
            return "{}\n"
        return serialize_codex_response(self.action, self.native_event_name)

    @property
    def response_json(self) -> str:
        return self.stdout


class CodexAdapter:
    """One-way native boundary around shared application protocols."""

    def __init__(
        self,
        config: CodexAdapterConfig | None = None,
        *,
        control_application: ControlApplicationPort | None = None,
        stop_decision_port: StopDecisionPort | None = None,
        event_application: EventApplicationPort | None = None,
        capability_profile: CapabilityProfile | None = None,
        clock: Clock | None = None,
        installation_key: bytes | None = None,
        **kwargs: Any,
    ) -> None:
        base = config or CodexAdapterConfig()
        updates: dict[str, Any] = {}
        for name, value in (
            ("control_application", control_application),
            ("stop_decision_port", stop_decision_port),
            ("event_application", event_application),
            ("capability_profile", capability_profile),
            ("clock", clock),
            ("installation_key", installation_key),
        ):
            if value is not None:
                updates[name] = value
        for name, value in kwargs.items():
            if not hasattr(base, name):
                raise TypeError(f"unknown CodexAdapterConfig field: {name}")
            updates[name] = value
        self.config = replace(base, **updates)
        self._bundle: Any | None = None
        self._bundle_error = False

    @property
    def capability_profile(self) -> CapabilityProfile:
        if self.config.capability_profile is not None:
            return self.config.capability_profile
        if (
            any(
                value is not None
                for value in (
                    self.config.features_hooks,
                    self.config.plugin_hooks_loaded,
                    self.config.managed_hooks_loaded,
                    self.config.features,
                )
            )
            or self.config.trust_state.casefold() != "unknown"
            or self.config.allow_managed_hooks_only
        ):
            return capability_profile_for_availability(
                hooks_enabled=self.config.features_hooks,
                trust_state=self.config.trust_state,
                allow_managed_hooks_only=self.config.allow_managed_hooks_only,
                plugin_hooks_loaded=self.config.plugin_hooks_loaded,
                managed_hooks_loaded=self.config.managed_hooks_loaded,
                features=self.config.features,
                host=self.config.host,
                clock=self.config.clock,
                adapter_version=self.config.adapter_version,
                host_version_range=self.config.host_version,
            )
        return default_capability_profile(
            self.config.host,
            clock=self.config.clock,
            host_version_range=self.config.host_version,
            adapter_version=self.config.adapter_version,
        )

    def capabilities(self) -> CapabilityProfile:
        return self.capability_profile

    def _load_bundle(self) -> Any | None:
        if self._bundle is not None or self._bundle_error:
            return self._bundle
        try:
            if self.config.content_repository is not None:
                self._bundle = self.config.content_repository.load()
            else:
                from ...content.loader import load_compiled_bundle

                self._bundle = load_compiled_bundle(self.config.bundle_path)
        except Exception:
            self._bundle_error = True
            return None
        return self._bundle

    def _bundle_context(self) -> str | None:
        bundle = self._load_bundle()
        if bundle is None:
            return None
        fragments = getattr(bundle, "prompt_fragments", {})
        if not isinstance(fragments, Mapping):
            return None
        controller = fragments.get("controller", {})
        if not isinstance(controller, Mapping):
            return None
        text = controller.get(self.config.locale) or controller.get("en")
        return text if isinstance(text, str) and text else None

    @staticmethod
    def _action_from_callback(value: object) -> HostAction | None:
        if isinstance(value, HostAction):
            return value
        if isinstance(value, str) and value:
            return HostAction.add_context(value)
        return None

    def _invoke_callback(
        self,
        callback: object,
        event: NormalizedEvent,
    ) -> tuple[bool, HostAction | None, str | None]:
        if callback is None:
            return False, None, None
        handler = getattr(callback, "handle", None)
        if not callable(handler):
            handler = callback if callable(callback) else None
        if handler is None:
            return False, None, "application_callback_invalid"
        try:
            return True, self._action_from_callback(handler(event)), None
        except Exception:
            return True, None, "application_callback_failed"

    def _dispatch_shared(self, event: NormalizedEvent) -> tuple[HostAction | None, tuple[str, ...]]:
        """Call an injected normalized dispatcher without importing host code."""

        dispatcher = self.config.dispatcher
        if dispatcher is None:
            return None, ()
        try:
            from ...hooks.dispatcher import DispatchRequest

            request = DispatchRequest(
                event=event,
                capability_profile=self.capability_profile,
            )
            dispatch = getattr(dispatcher, "dispatch", None)
            if not callable(dispatch):
                return None, ("dispatcher_unavailable",)
            result = dispatch(request)
            action_value = getattr(result, "action", HostActionKind.NO_OP)
            if action_value is HostActionKind.ADD_CONTEXT:
                context = getattr(result, "context", {})
                if isinstance(context, Mapping):
                    rendered = json.dumps(
                        context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                    )
                    return HostAction.add_context(rendered), ()
            return HostAction.no_op(), ()
        except Exception:
            return None, ("dispatcher_failed",)

    def _start_turn_context(self, event: NormalizedEvent) -> tuple[str | None, tuple[str, ...]]:
        repository = self.config.turn_repository
        settings_repository = self.config.settings_repository
        if repository is None or settings_repository is None:
            return None, ()
        try:
            from ...application.start_task import issue_turn_state

            settings = settings_repository.load()
            result = issue_turn_state(
                event,
                settings,
                repository,
                capability_profile=self.capability_profile,
                clock=self.config.clock,
                installation_key=self.config.installation_key,
            )
            if result.issued:
                context = json.dumps(
                    result.controller_context(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                return context, ()
            return None, ("start_task_unavailable",)
        except Exception:
            return None, ("start_task_unavailable",)

    def _context_action(self, event: NormalizedEvent) -> tuple[HostAction, tuple[str, ...]]:
        callback = self.config.context_factory
        called, callback_action, callback_diagnostic = self._invoke_callback(callback, event)
        if called:
            return callback_action or HostAction.no_op(), (
                callback_diagnostic,
            ) if callback_diagnostic else ()
        shared_action, shared_diagnostics = self._dispatch_shared(event)
        if shared_action is not None:
            return shared_action, shared_diagnostics
        if event.event_type is EventType.USER_PROMPT_SUBMITTED:
            turn_context, turn_diagnostics = self._start_turn_context(event)
            if turn_context is not None:
                base = self._bundle_context()
                context = f"{base}\n\n{turn_context}" if base else turn_context
                return HostAction.add_context(context), turn_diagnostics
            diagnostics = list(turn_diagnostics)
        else:
            diagnostics = []
        context = self._bundle_context()  # type: ignore[assignment]  # Closed runtime boundary validates this value.
        if context is None:
            diagnostics.append("compiled_bundle_unavailable")
            return HostAction.no_op(), tuple(diagnostics)
        return HostAction.add_context(context), tuple(diagnostics)

    def _event_action(self, event: NormalizedEvent) -> tuple[HostAction, tuple[str, ...]]:
        if self.config.event_application is not None:
            called, action, diagnostic = self._invoke_callback(self.config.event_application, event)
            if called:
                return action or HostAction.no_op(), (diagnostic,) if diagnostic else ()
        prompt_events = {
            EventType.SESSION_STARTED,
            EventType.USER_PROMPT_SUBMITTED,
            EventType.PRE_COMPACTION,
            EventType.POST_COMPACTION,
        }
        callback = (
            self.config.prompt_application
            if event.event_type in prompt_events
            else self.config.observation_application
        )
        called, action, diagnostic = self._invoke_callback(callback, event)
        if called:
            return action or HostAction.no_op(), (diagnostic,) if diagnostic else ()
        if event.event_type in prompt_events:
            return self._context_action(event)
        return HostAction.no_op(), ()

    def _repair_count_before(self, event: NormalizedEvent, native: CodexNativeEvent) -> int:
        if self.config.repair_count_provider is not None:
            try:
                return 1 if self.config.repair_count_provider(event) else 0
            except Exception:
                return 0
        return 1 if native.stop_hook_active else 0

    def _stop_action(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self,
        native: CodexNativeEvent,
        event: NormalizedEvent,
        *,
        repair_count_before: int | None = None,
    ) -> tuple[HostAction, tuple[str, ...]]:
        port = self.config.stop_decision_port
        before = (
            self._repair_count_before(event, native)
            if repair_count_before is None
            else repair_count_before
        )
        try:
            if port is not None:
                decide = getattr(port, "decide", None)
                if callable(decide):
                    result = decide(
                        event,
                        native.final_message,
                        repair_count_before=before,
                        stop_hook_active=native.stop_hook_active,
                        capability_profile=self.capability_profile,
                    )
                else:
                    handle = getattr(port, "handle_stop", None)
                    if not callable(handle) and callable(port):
                        handle = port
                    if not callable(handle):
                        return HostAction.no_op(), ("stop_decision_port_unavailable",)
                    result = handle(self._make_s18_request(native, before))
            else:
                from ...application.handle_stop import handle_stop

                result = handle_stop(self._make_s18_request(native, before))
        except Exception:
            return HostAction.no_op(), ("stop_decision_failed",)
        if isinstance(result, StopDecision):
            action = result.action
        elif isinstance(result, HostAction):
            action = result
        else:
            decision_value = getattr(
                getattr(result, "decision", None), "value", getattr(result, "decision", None)
            )
            limitation = getattr(result, "limitation_key", None)
            diagnostics = (limitation,) if isinstance(limitation, str) and limitation else ()
            if decision_value == "continue_once":
                instruction = getattr(result, "repair_instruction", None)
                if isinstance(instruction, str) and instruction.strip():
                    action = HostAction.continue_turn(instruction)
                else:
                    return HostAction.no_op(), (*diagnostics, "stop_repair_instruction_unavailable")
            else:
                return HostAction.no_op(), diagnostics
        if native.stop_hook_active and action.kind is HostActionKind.CONTINUE_TURN:
            return HostAction.no_op(), ("stop_repeat_no_continuation",)
        if before >= 1 and action.kind is HostActionKind.CONTINUE_TURN:
            return HostAction.no_op(), ("stop_repeat_no_continuation",)
        return action, ()

    def _make_s18_request(self, native: CodexNativeEvent, before: int) -> Any:
        from ...application.handle_stop import StopInput

        continuation_entry = self.capability_profile.capabilities.get(
            "bounded_completion_continuation"
        )
        continuation_supported = None
        if continuation_entry is not None and continuation_entry.status.value == "unavailable":
            continuation_supported = False
        return StopInput(
            last_assistant_message=native.final_message,
            locale=self.config.locale,
            capability_profile=self.capability_profile,
            repair_count_before=before,
            native_stop_hook_active=native.stop_hook_active,
            continuation_supported=continuation_supported,
        )

    def _selector_enabled(self) -> bool:
        """Return whether this adapter is on the OpenSocrates selector-only path."""

        return self.config.selector_mode or self.config.selector_application is not None

    @staticmethod
    def _selector_user_prompt_request(native: CodexNativeEvent) -> SelectorRequest | None:
        """Project only approved transient native values into one selector request."""

        if not isinstance(native.prompt, str) or not native.prompt:
            return None
        try:
            # ``model`` remains a bounded transient host fact for diagnostics
            # isolation only.  The selector SDK request intentionally has no
            # model field and never receives this value.
            return SelectorRequest(
                prompt=native.prompt,
                transcript_path=native.transcript_path,
                cwd=native.cwd,
                session_id=native.session_id,
                # Claude Code does not expose a turn_id in its hook contract.
                # Reuse the bounded session identifier as a turn-directory key;
                # Stop deletes that directory before the next user prompt.
                turn_id=native.turn_id or native.session_id,
                model=native.model,
            )
        except Exception:
            return None

    @staticmethod
    def _selector_empty_result(
        native: CodexNativeEvent | None,
        *,
        status: str = "no_op",
        diagnostics: tuple[str, ...] = (),
        error_code: str | None = None,
    ) -> CodexHandleResult:
        """Build the literal-empty selector result without a normalized projection."""

        return CodexHandleResult(
            native_event_name=native.native_event if native is not None else None,
            normalized_event=None,
            action=HostAction.no_op(),
            response={},
            projection={},
            status=status,
            diagnostics=diagnostics,
            error_code=error_code,
            literal_empty=True,
        )

    def _selector_response_result(
        self,
        native: CodexNativeEvent,
        decision: object,
        *,
        diagnostics: tuple[str, ...] = (),
    ) -> CodexHandleResult:
        """Map one validated selector decision to the single allowed response."""

        if (
            not isinstance(decision, SelectorDecision)
            or not decision.intervene
            or not decision.selected_reasoning_systems
            or not decision.instructions
        ):
            return self._selector_empty_result(native, diagnostics=diagnostics)
        try:
            response = selector_context_response(decision.instructions, native.native_event)
        except Exception:
            return self._selector_empty_result(native, diagnostics=diagnostics)
        # The response contains only a bounded temporary-file reference.  The
        # complete canonical content stays in the owner-only artifact until
        # Stop, SessionEnd, or the 24-hour crash-recovery sweep removes it.
        return CodexHandleResult(
            native_event_name=native.native_event,
            normalized_event=None,
            action=HostAction.no_op(),
            response=response,
            projection={},
            status="selector_injected",
            diagnostics=diagnostics,
            selector_response=True,
        )

    def _record_selector_grounding_read(self, native: CodexNativeEvent) -> None:
        """Record only a successful complete Read of the current instruction artifact."""

        if (
            not self.config.require_instruction_read_receipt
            or native.native_event != "PostToolUse"
            or native.tool_name != "Read"
            or not native.result_present
        ):
            return
        recorder = getattr(self.config.instruction_file_store, "record_complete_read", None)
        if not callable(recorder):
            return
        try:
            recorder(
                native.session_id,
                native.turn_id or native.session_id,
                file_path=native.tool_file_path,
                tool_use_id=native.tool_use_id,
                offset=native.tool_read_offset,
                limit=native.tool_read_limit,
                end_marker_seen=native.tool_read_end_marker_seen,
            )
        except Exception:
            # Receipt capture is a fail-open host backstop.  The trusted inline
            # guardrails and skill contract remain available when storage fails.
            return

    def _selector_grounding_repair_result(
        self,
        native: CodexNativeEvent,
        *,
        diagnostics: tuple[str, ...],
    ) -> CodexHandleResult | None:
        """Return one Stop continuation when grounding or its public audit is absent."""

        if not self.config.require_instruction_read_receipt or native.stop_hook_active:
            return None
        store = self.config.instruction_file_store
        latest = getattr(store, "latest_for_session", None)
        checker = getattr(store, "has_complete_read_receipt", None)
        if not callable(latest) or not callable(checker):
            return None
        try:
            artifact = latest(native.session_id)
            if artifact is None:
                return None
            read_confirmed = bool(checker(artifact))
            footer = artifact.grounding_footer()
            final_lines = (native.final_message or "").rstrip().splitlines()
            footer_confirmed = bool(final_lines and final_lines[-1].strip() == footer)
            if read_confirmed and footer_confirmed:
                return None
            reason = artifact.grounding_repair_message(
                missing_read=not read_confirmed,
                missing_footer=not footer_confirmed,
            )
            action = HostAction.continue_turn(reason)
            response = response_object(action, "Stop")
        except Exception:
            return None
        return CodexHandleResult(
            native_event_name=native.native_event,
            normalized_event=None,
            action=action,
            response=response,
            projection={},
            status="grounding_repair",
            diagnostics=diagnostics,
            selector_response=True,
        )

    def _handle_selector_event(  # noqa: C901  # Closed native lifecycle dispatch.
        self, native: CodexNativeEvent, *, diagnostics: tuple[str, ...]
    ) -> CodexHandleResult:
        """Handle the closed selector lifecycle before legacy normalization."""

        application = self.config.selector_application
        artifact_store = self.config.instruction_file_store
        if native.native_event == "SessionStart":
            if artifact_store is not None:
                try:
                    artifact_store.sweep_expired()
                except Exception:
                    pass
            if native.source == "compact" and artifact_store is not None:
                try:
                    artifact = artifact_store.latest_for_session(native.session_id)
                except Exception:
                    artifact = None
                if artifact is not None:
                    try:
                        decision = SelectorDecision(
                            intervene=True,
                            selected_reasoning_systems=artifact.selected_reasoning_systems,
                            instructions=artifact.reference_message(),
                        )
                    except Exception:
                        decision = None
                    return self._selector_response_result(native, decision, diagnostics=diagnostics)
            return self._selector_empty_result(native, diagnostics=diagnostics)

        if native.native_event == "UserPromptSubmit":
            if application is None:
                return self._selector_empty_result(native, diagnostics=diagnostics)
            request = self._selector_user_prompt_request(native)
            if request is None:
                return self._selector_empty_result(native, diagnostics=diagnostics)
            try:
                decision = application.select_for_user_prompt_submit(request)
            except Exception:
                decision = None
            result = self._selector_response_result(native, decision, diagnostics=diagnostics)
            if result.literal_empty and artifact_store is not None:
                try:
                    artifact_store.delete_turn(
                        native.session_id, native.turn_id or native.session_id
                    )
                except Exception:
                    pass
            return result

        if native.native_event == "PostToolUse":
            self._record_selector_grounding_read(native)
            return self._selector_empty_result(native, diagnostics=diagnostics)

        if native.native_event == "Stop" and artifact_store is not None:
            repair = self._selector_grounding_repair_result(
                native,
                diagnostics=diagnostics,
            )
            if repair is not None:
                return repair
            try:
                artifact_store.delete_turn(native.session_id, native.turn_id or native.session_id)
            except Exception:
                pass
        if native.native_event == "SessionEnd" and artifact_store is not None:
            try:
                artifact_store.delete_session(native.session_id)
            except Exception:
                pass
        # Tool events, compaction events, Stop, and SessionEnd deliberately
        # produce a literal blank result and never reach the shared dispatcher.
        return self._selector_empty_result(native, diagnostics=diagnostics)

    def _result_for_parse_failure(
        self,
        parsed: NativeParseResult,
        *,
        event_name: str | None,
    ) -> CodexHandleResult:
        if self._selector_enabled():
            return self._selector_empty_result(
                None,
                status=(
                    "reject_before_domain_parse"
                    if parsed.error_code == "input_too_large"
                    else "pass_through"
                ),
                diagnostics=parsed.diagnostics,
                error_code=parsed.error_code,
            )
        name = event_name if isinstance(event_name, str) else None
        response: dict[str, Any] = {}
        if name is not None:
            try:
                response = response_object(HostAction.no_op(), name)
            except NativeResponseError:
                name = None
        status = (
            "reject_before_domain_parse"
            if parsed.error_code == "input_too_large"
            else "pass_through"
        )
        return CodexHandleResult(
            native_event_name=name,
            normalized_event=None,
            action=HostAction.no_op(),
            response=response,
            projection={},
            status=status,
            diagnostics=parsed.diagnostics,
            error_code=parsed.error_code,
        )

    def handle(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
        self,
        native_input: Mapping[str, Any] | str | bytes | bytearray,
        *,
        event_name: str | None = None,
    ) -> CodexHandleResult:
        """Process one Codex callback and return a safe legal response."""

        parsed = try_parse_codex_event(
            native_input,
            event_name=event_name,
            host=self.config.host,
        )
        if parsed.event is None:
            return self._result_for_parse_failure(parsed, event_name=event_name)
        native = parsed.event
        if self._selector_enabled():
            # The selector path consumes transient native data directly and
            # must never project prompt/path/model data into the legacy
            # normalized-event, diagnostics, or dispatcher path.
            result = self._handle_selector_event(native, diagnostics=parsed.diagnostics)
            del native
            return result
        projection = project_codex_payload(native)
        if native.native_event in {"PreToolUse", "PermissionRequest"}:
            return CodexHandleResult(
                native_event_name=native.native_event,
                normalized_event=None,
                action=HostAction.no_op(),
                response=response_object(HostAction.no_op(), native.native_event),
                projection=projection,
                status="no_op",
                diagnostics=parsed.diagnostics,
            )
        try:
            normalized = normalize_codex_event(
                native,
                installation_key=self.config.installation_key,
                clock=self.config.clock,
                adapter_version=self.config.adapter_version,
            )
        except Exception:
            action = HostAction.no_op()
            return CodexHandleResult(
                native_event_name=native.native_event,
                normalized_event=None,
                action=action,
                response=response_object(action, native.native_event),
                projection=projection,
                status="pass_through",
                diagnostics=(*parsed.diagnostics, "normalized_event_rejected"),
                error_code="normalized_event_rejected",
            )
        if normalized is None:
            return CodexHandleResult(
                native_event_name=native.native_event,
                normalized_event=None,
                action=HostAction.no_op(),
                response=response_object(HostAction.no_op(), native.native_event),
                projection=projection,
                status="no_op",
                diagnostics=parsed.diagnostics,
            )
        repair_count_before: int | None = None
        if native.native_event == "Stop":
            repair_count_before = self._repair_count_before(normalized, native)
            action, action_diagnostics = self._stop_action(
                native,
                normalized,
                repair_count_before=repair_count_before,
            )
            if action.kind is HostActionKind.CONTINUE_TURN or native.stop_hook_active:
                projection = dict(projection)
                projection["repair_count"] = 1
            elif repair_count_before >= 1:
                projection = dict(projection)
                projection["repair_count"] = 1
        else:
            action, action_diagnostics = self._event_action(normalized)
        try:
            response = response_object(action, native.native_event)
        except NativeResponseError:
            action = HostAction.no_op()
            response = response_object(action, native.native_event)
            action_diagnostics = (*action_diagnostics, "response_not_legal_pass_through")
        diagnostics = (*parsed.diagnostics, *action_diagnostics)
        if native.final_message is None and native.native_event == "Stop":
            diagnostics = (*diagnostics, "missing_final_message")
        status = "accepted"
        if native.native_event == "Stop":
            if action.kind is HostActionKind.CONTINUE_TURN:
                status = "continue_once"
            elif native.stop_hook_active or (repair_count_before or 0) >= 1:
                status = "accepted_without_continuation"
            elif native.final_message is None or any(
                item.startswith("capability.") for item in diagnostics
            ):
                status = "degraded"
        elif not diagnostics and action.kind is HostActionKind.NO_OP:
            status = "accepted"
        elif any(item == "native_unknown_field_ignored" for item in diagnostics):
            status = "accepted_with_diagnostic"
        limitations = tuple(
            sorted(
                {
                    entry.limitation_key
                    for entry in self.capability_profile.capabilities.values()
                    if entry.limitation_key is not None and entry.status.value != "supported"
                }
            )
        )
        return CodexHandleResult(
            native_event_name=native.native_event,
            normalized_event=normalized,
            action=action,
            response=response,
            projection=projection,
            status=status,
            diagnostics=diagnostics,
            capability_limitations=limitations,
        )

    def handle_bytes(
        self, native_input: bytes, *, event_name: str | None = None
    ) -> CodexHandleResult:
        return self.handle(native_input, event_name=event_name)

    def apply_control(
        self, request: Any, *, current_event: NormalizedEvent | None = None
    ) -> HostControlResult:
        """Delegate a typed control request to S14; native JSON stays outside."""

        application = self.config.control_application
        if application is None:
            raise RuntimeError("control application port is unavailable")
        from ...application.apply_control import ApplyControlRequest

        normalized_request = request
        if not isinstance(request, ApplyControlRequest):
            normalized_request = ApplyControlRequest(
                control=request,
                current_event=current_event,
                capability_profile=self.capability_profile,
            )
        return application.apply(normalized_request)

    apply_host_control = apply_control
    dispatch = handle
    process = handle
    handle_event = handle


__all__ = [
    "CodexAdapter",
    "CodexAdapterConfig",
    "CodexHandleResult",
    "DEFAULT_BUNDLE_PATH",
]
