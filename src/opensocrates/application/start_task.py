"""Issue one bounded ephemeral turn state at the normalized prompt boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..clock import Clock, SystemClock, utc_timestamp
from ..domain.enums import CapabilityStatus, HostControlReasonCode, Participation, TaskState
from ..domain.models import (
    CapabilityProfile,
    EphemeralTurnState,
    NormalizedEvent,
    ParticipationDecision,
    UserSettings,
)
from ..domain.turn_state import TurnStateError, expiry_for, token_tag_for, validate_turn_state
from ..domain.validation import validate_model
from ..errors import OpenSocratesError
from ..ids import new_turn_token
from .change_settings import CURRENT_ONBOARDING_VERSION
from .ports import TurnStateRepository


class StartTaskError(ValueError):
    """A normalized prompt cannot produce a safe ephemeral state."""


@dataclass(frozen=True, slots=True)
class StartTaskResult:
    """Transient result returned to a hook/controller; no raw input is kept."""

    raw_turn_token: str | None
    state: EphemeralTurnState | None
    recording_eligible: bool
    onboarding_disclosure_turn: bool
    reason_code: HostControlReasonCode | None = None
    capability_limitations: tuple[str, ...] = ()
    error_code: str | None = None

    @property
    def turn_token(self) -> str | None:
        """Compatibility alias used by hook callers."""

        return self.raw_turn_token

    @property
    def issued(self) -> bool:
        return self.state is not None and self.raw_turn_token is not None

    def controller_context(self) -> dict[str, str | bool]:
        """Return only the transient controller fields safe for host injection."""

        if self.state is None or self.raw_turn_token is None:
            return {}
        return {
            "turn_token": self.raw_turn_token,
            "recording_eligible": self.recording_eligible,
            "onboarding_disclosure_turn": self.onboarding_disclosure_turn,
        }


def _installation_key(repository: TurnStateRepository, supplied: bytes | None) -> bytes:
    key = supplied if supplied is not None else getattr(repository, "installation_key", None)
    if not isinstance(key, bytes) or len(key) != 32:
        raise StartTaskError("turn repository does not expose a 256-bit installation key")
    return key


def _capability_supported(profile: CapabilityProfile | None, key: str) -> bool:
    if profile is None:
        return True
    entry = profile.capabilities.get(key)
    return entry is not None and entry.status is CapabilityStatus.SUPPORTED


def _limitations(profile: CapabilityProfile | None) -> tuple[str, ...]:
    if profile is None:
        return ()
    values = []
    for key in ("local_record_write", "local_control_execution", "published_artifact_confirmation"):
        entry = profile.capabilities.get(key)
        if entry is not None and entry.status is not CapabilityStatus.SUPPORTED:
            values.append(entry.limitation_key or key)
    return tuple(sorted(set(values)))[:8]


def issue_turn_state(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    event: NormalizedEvent,
    settings: UserSettings,
    turn_repository: TurnStateRepository,
    *,
    capability_profile: CapabilityProfile | None = None,
    participation: ParticipationDecision | None = None,
    onboarding_disclosure_turn: bool | None = None,
    clock: Clock | None = None,
    installation_key: bytes | None = None,
    token_factory: Callable[[], str] = new_turn_token,
) -> StartTaskResult:
    """Issue an opaque token and closed state for one normalized user turn.

    No task/event record is created here.  A task receives an ID only after a
    valid ``begin_judgment`` control has been routed by ``apply_control``.
    """

    if not isinstance(event, NormalizedEvent):
        raise StartTaskError("start_task requires NormalizedEvent")
    if not isinstance(settings, UserSettings):
        raise StartTaskError("start_task requires UserSettings")
    if not hasattr(turn_repository, "issue"):
        raise StartTaskError("start_task requires a TurnStateRepository")
    try:
        validate_model(event)
        validate_model(settings)
        if capability_profile is not None:
            validate_model(capability_profile)
        if participation is not None:
            validate_model(participation)
    except (OpenSocratesError, TypeError, ValueError) as exc:
        raise StartTaskError("start_task received an invalid normalized contract") from exc

    decision_kind = participation.participation if participation is not None else None
    mechanical = decision_kind is Participation.MECHANICAL
    disclosed = settings.onboarding_version_seen == CURRENT_ONBOARDING_VERSION
    disclosure_turn = (
        bool(onboarding_disclosure_turn)
        if onboarding_disclosure_turn is not None
        else (not mechanical and not disclosed)
    )
    limitations = _limitations(capability_profile)
    can_record = (
        not mechanical
        and not disclosure_turn
        and settings.recording_mode.value == "local_public_artifacts"
        and _capability_supported(capability_profile, "local_record_write")
    )
    reason: HostControlReasonCode | None = None
    if mechanical:
        reason = HostControlReasonCode.RECORDING_OFF
    elif disclosure_turn:
        reason = HostControlReasonCode.ONBOARDING_DISCLOSURE_TURN
    elif not can_record:
        reason = HostControlReasonCode.RECORDING_OFF

    clock = clock or SystemClock()
    sweep = getattr(turn_repository, "sweep_expired", None)
    if callable(sweep):
        try:
            sweep(utc_timestamp(clock))
        except Exception:
            # Issuance must remain honest but should not block a fresh turn
            # merely because crash-residue cleanup is temporarily unavailable.
            pass
    raw_token = token_factory()
    try:
        key = _installation_key(turn_repository, installation_key)
        state = EphemeralTurnState(
            token_tag=token_tag_for(raw_token, key),
            host_session_key=event.host_session_key,
            host_turn_key=event.host_turn_key,
            host=event.host,
            issued_at=event.occurred_at,
            expires_at=expiry_for(event.occurred_at),
            recording_eligible=can_record,
            onboarding_disclosure_turn=disclosure_turn,
            task_id=None,
            judgment_id=None,
            task_state=TaskState.BYPASSED if mechanical else TaskState.NEW,
            participation=decision_kind,
            effective_rigor=settings.default_rigor,
            primary_method=None,
            secondary_method=None,
            repair_count=0,
            accepted_controls=(),
            observation_tags=(),
        )
        validate_turn_state(state)
        # ``clock`` is intentionally accepted as a dependency for callers that
        # want deterministic issuance; event.occurred_at remains authoritative
        # for the token's bounded lifetime.
        _ = clock
        turn_repository.issue(state)
    except (TurnStateError, OpenSocratesError, TypeError, ValueError, OSError):
        return StartTaskResult(
            raw_turn_token=None,
            state=None,
            recording_eligible=False,
            onboarding_disclosure_turn=disclosure_turn,
            reason_code=HostControlReasonCode.STORE_UNAVAILABLE,
            capability_limitations=tuple(sorted(set((*limitations, "local_control_execution"))))[
                :8
            ],
            error_code="store_unavailable",
        )
    return StartTaskResult(
        raw_turn_token=raw_token,
        state=state,
        recording_eligible=can_record,
        onboarding_disclosure_turn=disclosure_turn,
        reason_code=reason,
        capability_limitations=limitations,
    )


def start_task(*args: object, **kwargs: object) -> StartTaskResult:
    """Public function name used by hooks and focused walkthroughs."""

    return issue_turn_state(*args, **kwargs)  # type: ignore[arg-type]


__all__ = ["StartTaskError", "StartTaskResult", "issue_turn_state", "start_task"]
