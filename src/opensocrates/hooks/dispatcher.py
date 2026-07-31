"""Adapter-neutral dispatch over already-normalized runtime requests.

Native hook envelopes are intentionally outside this module.  An adapter must
first construct a validated :class:`NormalizedEvent` and, for control calls, a
validated :class:`HostControl`; the dispatcher then selects the application
use case and returns typed data for the adapter to serialize.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..application.apply_control import ApplyControlRequest, ControlApplication
from ..application.ports import (
    ContentRepository,
    SettingsRepository,
    TaskRepository,
    TurnStateRepository,
)
from ..application.start_task import StartTaskResult, issue_turn_state
from ..clock import Clock, SystemClock
from ..domain.enums import EventType, HostActionKind
from ..domain.models import (
    CapabilityProfile,
    EphemeralTurnState,
    HostControl,
    HostControlResult,
    NormalizedEvent,
    ParticipationDecision,
    UserSettings,
)
from ..domain.validation import validate_model


class DispatchError(ValueError):
    """Raised when a caller crosses the normalized dispatcher boundary incorrectly."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchRequest:
    """One normalized lifecycle event or one typed control invocation."""

    event: NormalizedEvent
    settings: UserSettings | None = None
    capability_profile: CapabilityProfile | None = None
    participation: ParticipationDecision | None = None
    control: HostControl | None = None
    current_turn_state: EphemeralTurnState | None = None
    public_artifact_confirmed: bool = False
    direct_user_authority: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class DispatchResult:
    """Typed output which remains independent of Codex native JSON."""

    action: HostActionKind = HostActionKind.NO_OP
    turn: StartTaskResult | None = None
    control: HostControlResult | None = None
    context_fields: tuple[tuple[str, str | bool], ...] = ()
    limitation_key: str | None = None
    cleanup_performed: bool = False

    @property
    def context(self) -> dict[str, str | bool]:
        """Return a transient context projection for an adapter boundary."""

        return dict(self.context_fields)


class Dispatcher:
    """Route normalized events to start/control/cleanup application seams."""

    def __init__(
        self,
        turn_repository: TurnStateRepository,
        *,
        task_repository: TaskRepository | None = None,
        settings_repository: SettingsRepository | None = None,
        content_repository: ContentRepository | None = None,
        prompt_compiler: object | None = None,
        capability_profile: CapabilityProfile | None = None,
        clock: Clock | None = None,
        control_application: ControlApplication | None = None,
    ) -> None:
        self.turn_repository = turn_repository
        self.task_repository = task_repository
        self.settings_repository = settings_repository
        self.content_repository = content_repository
        self.prompt_compiler = prompt_compiler
        self.capability_profile = capability_profile
        self.clock = clock or SystemClock()
        self.control_application = control_application or ControlApplication(
            turn_repository,
            task_repository=task_repository,
            settings_repository=settings_repository,
            content_repository=content_repository,
            prompt_compiler=prompt_compiler,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            capability_profile=capability_profile,
            clock=self.clock,
        )

    def _validate(self, request: DispatchRequest) -> DispatchRequest:
        if not isinstance(request, DispatchRequest):
            raise DispatchError("dispatcher accepts DispatchRequest only")
        try:
            validate_model(request.event)
            if request.settings is not None:
                validate_model(request.settings)
            if request.capability_profile is not None:
                validate_model(request.capability_profile)
            if request.participation is not None:
                validate_model(request.participation)
            if request.control is not None:
                validate_model(request.control)
            if request.current_turn_state is not None:
                validate_model(request.current_turn_state)
        except Exception as exc:
            raise DispatchError("dispatcher received an invalid normalized contract") from exc
        if (
            request.control is not None
            and request.event.event_type is not EventType.USER_PROMPT_SUBMITTED
        ):
            # Controls are scoped to the current direct user turn.  The event
            # type remains normalized; no adapter-native event names are read.
            raise DispatchError("control dispatch requires the current user-prompt event")
        return request

    def _cleanup(self, state: EphemeralTurnState | None) -> bool:
        if state is None:
            return False
        try:
            self.turn_repository.delete(state)
        except Exception:
            return False
        return True

    def dispatch(self, request: DispatchRequest) -> DispatchResult:
        request = self._validate(request)
        event = request.event
        if request.control is not None:
            result = self.control_application.apply(
                ApplyControlRequest(
                    control=request.control,
                    current_event=event,
                    capability_profile=request.capability_profile or self.capability_profile,
                    public_artifact_confirmed=request.public_artifact_confirmed,
                    direct_user_authority=request.direct_user_authority,
                )
            )
            action = (
                HostActionKind.CONTINUE_TURN
                if result.next_action.value != "stop_control_calls"
                else HostActionKind.NO_OP
            )
            return DispatchResult(action=action, control=result)

        if event.event_type is EventType.USER_PROMPT_SUBMITTED:
            if request.settings is None:
                raise DispatchError("user-prompt dispatch requires UserSettings")
            turn = issue_turn_state(
                event,
                request.settings,
                self.turn_repository,
                capability_profile=request.capability_profile or self.capability_profile,
                participation=request.participation,
                clock=self.clock,
            )
            context = tuple(turn.controller_context().items())
            action = HostActionKind.ADD_CONTEXT if context else HostActionKind.NO_OP
            limitation = turn.error_code or (turn.reason_code.value if turn.reason_code else None)
            return DispatchResult(
                action=action, turn=turn, context_fields=context, limitation_key=limitation
            )

        if event.event_type is EventType.SESSION_ENDED:
            cleaned = self._cleanup(request.current_turn_state)
            return DispatchResult(cleanup_performed=cleaned)

        if event.event_type is EventType.PRE_COMPACTION:
            # Compaction injects only a higher-layer digest.  This seam never
            # reads transcript/prose and therefore has no context to add.
            return DispatchResult()

        return DispatchResult()


def dispatch(request: DispatchRequest, *, dispatcher: Dispatcher) -> DispatchResult:
    """Functional alias for adapters that keep their dispatcher injected."""

    if not isinstance(dispatcher, Dispatcher):
        raise DispatchError("dispatch requires a Dispatcher")
    return dispatcher.dispatch(request)


__all__ = ["DispatchError", "DispatchRequest", "DispatchResult", "Dispatcher", "dispatch"]
