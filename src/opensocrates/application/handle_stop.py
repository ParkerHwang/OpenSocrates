"""Host-neutral Stop boundary for one bounded completion repair.

The boundary deliberately accepts ports instead of importing a host adapter or
the concrete turn store.  A repair continuation is reserved with one injected
atomic operation.  No retry is performed after that operation raises or loses
its compare-and-swap race, so a crash, re-entry, or concurrent Stop call cannot
create a second continuation.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from copy import copy
from dataclasses import dataclass, is_dataclass, replace
from enum import StrEnum
from typing import Protocol, runtime_checkable

from ..domain.enums import TaskState, VerificationOutcome, ViolationSeverity
from ..domain.models import (
    EphemeralTurnState,
    VerificationResult,
    Violation,
)
from ..domain.turn_state import replace_lifecycle
from ..rendering.repair import MAX_REPAIR_BYTES, render_repair_instruction
from ..verification.verifier import VerificationRequest, verify_completion


class StopDecision(StrEnum):
    """Closed action vocabulary exposed to host adapters."""

    PASS = "pass"
    CONTINUE_ONCE = "continue_once"
    HOLD = "hold"
    LIMITATION = "limitation"


StopDecisionKind = StopDecision
StopOutcome = StopDecision


@runtime_checkable
class StopVerifier(Protocol):
    def verify(self, request: VerificationRequest) -> VerificationResult: ...


@runtime_checkable
class RepairReservation(Protocol):
    def compare_and_swap(self, expected: object, replacement: object) -> object: ...


@dataclass(frozen=True, slots=True, kw_only=True)
class StopInput:
    """Typed inputs for the final public candidate and native Stop state."""

    last_assistant_message: str | None = None
    locale: str = "en"
    locale_catalog: object | None = None
    task_projection: object | None = None
    framing: object | None = None
    current_judgment: object | None = None
    claim_versions: object = ()
    sources: object = ()
    alternatives: object = ()
    conflicts: object = ()
    criterion_statuses: object | None = None
    capability_profile: object | None = None
    public_claim_changed: bool = False
    candidate_sequence: int = 1

    # ``turn_state`` is intentionally transient.  It contains no raw token or
    # transcript, and the repository remains an injected application port.
    turn_state: object | None = None
    turn_store: object | None = None
    turn_state_repository: object | None = None
    repair_reservation: object | None = None
    reservation: object | None = None
    cleanup: object | None = None

    repair_count_before: int | None = None
    repair_count: int | None = None
    native_stop_hook_active: bool = False
    native_stop_active: bool | None = None
    stop_hook_active: bool | None = None
    stop_active: bool | None = None
    continuation_supported: bool | None = None

    verifier: object | None = None
    verification_request: VerificationRequest | None = None
    verification_result: VerificationResult | None = None
    repair_renderer: object | None = None
    parser: object | None = None
    card_rules: object | None = None
    evidence_rules: object | None = None
    source_rules: object | None = None
    calculation_rules: object | None = None
    parser_kwargs: Mapping[str, object] | None = None


StopRequest = StopInput


@dataclass(frozen=True, slots=True, kw_only=True)
class StopOutput:
    """Typed Stop decision; user-visible limitation text stays host/catalog-owned."""

    decision: StopDecision
    verification: VerificationResult | None = None
    repair_instruction: str | None = None
    limitation_key: str | None = None
    repair_count_before: int = 0
    repair_count_after: int = 0
    reserved: bool = False
    cleanup_performed: bool = False
    terminal_cleanup_required: bool = True

    @property
    def should_continue(self) -> bool:
        return self.decision is StopDecision.CONTINUE_ONCE

    @property
    def continue_once(self) -> bool:
        return self.should_continue

    @property
    def pass_allowed(self) -> bool:
        return self.decision is StopDecision.PASS

    @property
    def terminal(self) -> bool:
        return self.decision is not StopDecision.CONTINUE_ONCE

    @property
    def limitation(self) -> str | None:
        return self.limitation_key

    @property
    def action(self) -> StopDecision:
        return self.decision

    @property
    def kind(self) -> StopDecision:
        return self.decision

    @property
    def may_continue(self) -> bool:
        return self.should_continue


StopDecisionResult = StopOutput
StopHandlingResult = StopOutput


def _get(value: object, name: str, default: object = None) -> object:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _safe_count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _repair_count(request: StopInput) -> tuple[int, bool]:
    explicit = request.repair_count_before
    if explicit is None:
        explicit = request.repair_count
    values: list[int] = []
    invalid = False
    for candidate in (
        explicit,
        _get(request.turn_state, "repair_count"),
        _get(request.task_projection, "repair_count"),
    ):
        if candidate is None:
            continue
        value = _safe_count(candidate)
        if value is None:
            invalid = True
        else:
            values.append(value)
    if not values:
        return 0, invalid
    selected = max(values)
    return selected, invalid or len(set(values)) > 1 or any(value > 1 for value in values)


def _native_stop_active(request: StopInput) -> bool:
    return any(
        value is True
        for value in (
            request.native_stop_hook_active,
            request.native_stop_active,
            request.stop_hook_active,
            request.stop_active,
        )
    )


def _task_state(request: StopInput) -> TaskState | None:
    value = _get(request.task_projection, "state")
    if value is None:
        value = _get(request.turn_state, "task_state")
    if isinstance(value, TaskState):
        return value
    try:
        return TaskState(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _has_candidate(request: StopInput) -> bool:
    if request.verification_result is not None or request.verification_request is not None:
        return True
    if isinstance(request.last_assistant_message, str) and request.last_assistant_message.strip():
        return True
    return False


def _no_candidate_is_safe_stop(request: StopInput) -> bool:
    if _has_candidate(request):
        return False
    state = _task_state(request)
    if state in {
        TaskState.BYPASSED,
        TaskState.CANCELLED,
        TaskState.CONCLUDED,
        TaskState.INSUFFICIENT,
        TaskState.DEGRADED,
    }:
        return True
    return (
        request.task_projection is None
        and request.framing is None
        and request.current_judgment is None
    )


def _request_for(request: StopInput) -> VerificationRequest:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    if request.verification_request is not None:
        value = request.verification_request
        changes: dict[str, object] = {}
        if value.locale == "en" and request.locale != "en":
            changes["locale"] = request.locale
        if value.locale_catalog is None and request.locale_catalog is not None:
            changes["locale_catalog"] = request.locale_catalog
        if value.markdown is None and request.last_assistant_message is not None:
            changes["markdown"] = request.last_assistant_message
        if value.task_projection is None and request.task_projection is not None:
            changes["task_projection"] = request.task_projection
        if value.framing is None and request.framing is not None:
            changes["framing"] = request.framing
        if value.current_judgment is None and request.current_judgment is not None:
            changes["current_judgment"] = request.current_judgment
        if value.repair_count_before == 0 and request.repair_count_before not in (None, 0):
            changes["repair_count_before"] = request.repair_count_before
        for field_name in (
            "parser",
            "card_rules",
            "evidence_rules",
            "source_rules",
            "calculation_rules",
            "parser_kwargs",
        ):
            if getattr(value, field_name) is None and getattr(request, field_name) is not None:
                changes[field_name] = getattr(request, field_name)
        return replace(value, **changes) if changes else value  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    return VerificationRequest(
        markdown=request.last_assistant_message,
        locale=request.locale,
        locale_catalog=request.locale_catalog,
        task_projection=request.task_projection,
        framing=request.framing,
        current_judgment=request.current_judgment,
        claim_versions=request.claim_versions,
        sources=request.sources,
        alternatives=request.alternatives,
        conflicts=request.conflicts,
        criterion_statuses=request.criterion_statuses,
        capability_profile=request.capability_profile,
        public_claim_changed=request.public_claim_changed,
        repair_count_before=request.repair_count_before or 0,
        candidate_sequence=request.candidate_sequence,
        parser=request.parser,
        card_rules=request.card_rules,
        evidence_rules=request.evidence_rules,
        source_rules=request.source_rules,
        calculation_rules=request.calculation_rules,
        parser_kwargs=request.parser_kwargs,
    )


def _violation(rule_id: str, message_key: str, field: str | None = None) -> Violation:
    return Violation(
        rule_id=rule_id,
        severity=ViolationSeverity.ERROR,
        message_key=message_key,
        field=field,
        repair_hint_key="repair.group",
    )


def _error_result(rule_id: str, message_key: str, field: str) -> VerificationResult:
    return VerificationResult(
        outcome=VerificationOutcome.ERROR,
        violations=(_violation(rule_id, message_key, field),),
        parsed_card=None,
        completion_result=None,
        duration_ms=0,
    )


def _call_verifier(verifier: object, request: VerificationRequest) -> VerificationResult:
    function = getattr(verifier, "verify", None)
    if not callable(function):
        function = verifier if callable(verifier) else None
    if function is None:
        raise TypeError("verifier unavailable")
    result = function(request)
    if not isinstance(result, VerificationResult):
        raise TypeError("verifier returned an invalid result")
    return result


def _verify(request: StopInput) -> VerificationResult:
    if request.verification_result is not None:
        if not isinstance(request.verification_result, VerificationResult):
            raise TypeError("verification result is invalid")
        return request.verification_result
    verifier = request.verifier or verify_completion
    return _call_verifier(verifier, _request_for(request))


def _call_render(renderer: object, violations: tuple[Violation, ...], request: StopInput) -> str:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    function = getattr(renderer, "render_repair_instruction", None)
    if not callable(function):
        function = getattr(renderer, "render", None)
    if not callable(function):
        function = renderer if callable(renderer) else None
    if function is None:
        raise TypeError("repair renderer unavailable")
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        result = function(violations, request.locale_catalog, request.locale)
    else:
        parameters = tuple(signature.parameters.values())
        accepts_kwargs = any(item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters)
        kwargs: dict[str, object] = {}
        if "locale_catalog" in signature.parameters or accepts_kwargs:
            kwargs["locale_catalog"] = request.locale_catalog
        if "locale" in signature.parameters or accepts_kwargs:
            kwargs["locale"] = request.locale
        if "max_bytes" in signature.parameters or accepts_kwargs:
            kwargs["max_bytes"] = MAX_REPAIR_BYTES
        positional = tuple(
            item
            for item in parameters
            if item.kind
            in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
        )
        # Support small injected render ports that name the catalog argument
        # differently while retaining one invocation and no retry semantics.
        if len(positional) >= 2 and "locale_catalog" not in signature.parameters:
            args: tuple[object, ...] = (violations, request.locale_catalog)
            if len(positional) >= 3 and "locale" not in signature.parameters:
                args = (*args, request.locale)
            result = function(*args, **kwargs)
        else:
            result = function(violations, **kwargs)
    if not isinstance(result, str) or not result.strip():
        raise TypeError("repair renderer returned an invalid instruction")
    if len(result.encode("utf-8")) > MAX_REPAIR_BYTES:
        raise ValueError("repair instruction exceeds the bounded limit")
    return result


def _replacement_state(state: object) -> object:
    if isinstance(state, EphemeralTurnState):
        return replace_lifecycle(state, repair_count=1)
    if isinstance(state, Mapping):
        result = dict(state)
        result["repair_count"] = 1
        return result
    if is_dataclass(state):
        return replace(state, repair_count=1)  # type: ignore[type-var]  # Closed runtime boundary validates this value.
    if state is None:
        return None
    try:
        result = copy(state)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        result.repair_count = 1  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.
        return result
    except Exception as exc:
        raise TypeError("turn state cannot be reserved") from exc


def _invoke_reservation(function: object, expected: object, replacement: object) -> object:
    if not callable(function):
        raise TypeError("repair reservation is unavailable")
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(expected, replacement)
    parameters = tuple(signature.parameters.values())
    if any(item.kind is inspect.Parameter.VAR_POSITIONAL for item in parameters):
        return function(expected, replacement)
    positional = tuple(
        item
        for item in parameters
        if item.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
    )
    required = sum(item.default is inspect.Parameter.empty for item in positional)
    if len(positional) >= 2 or required >= 2:
        return function(expected, replacement)
    if positional or required:
        return function(expected)
    return function()


def _reservation_provider(request: StopInput) -> object | None:
    return (
        request.repair_reservation
        or request.reservation
        or request.turn_state_repository
        or request.turn_store
    )


def _reserve(request: StopInput) -> tuple[bool, bool]:
    """Return ``(reserved, race_or_unknown_failure)`` after one attempt."""

    provider = _reservation_provider(request)
    if provider is None:
        return False, False
    expected = request.turn_state
    try:
        replacement = _replacement_state(expected)
    except Exception:
        return False, True
    if expected is None and callable(getattr(provider, "compare_and_swap", None)):
        return False, False
    function = getattr(provider, "compare_and_swap", None)
    if not callable(function):
        function = getattr(provider, "reserve_repair", None)
    if not callable(function):
        function = getattr(provider, "reserve", None)
    if not callable(function) and callable(provider):
        function = provider
    if not callable(function):
        return False, False
    try:
        result = _invoke_reservation(function, expected, replacement)
    except Exception:
        # A CAS conflict and an unknown write result are both terminal.  In
        # either case cleanup must not delete a state another caller may have
        # successfully reserved.
        return False, True
    if result is False:
        return False, True
    return True, False


def _invoke_cleanup(request: StopInput) -> bool:
    function = request.cleanup
    if function is None:
        provider = (
            request.turn_state_repository
            or request.turn_store
            or request.repair_reservation
            or request.reservation
        )
        if request.turn_state is None:
            return True
        function = getattr(provider, "delete", None) if provider is not None else None
    if function is None:
        return request.turn_state is None
    if not callable(function):
        return False
    try:
        _invoke_one(function, request.turn_state)
    except Exception:
        return False
    return True


def _invoke_one(function: object, value: object) -> object:
    if not callable(function):
        raise TypeError("cleanup is unavailable")
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(value)
    parameters = tuple(signature.parameters.values())
    positional = tuple(
        item
        for item in parameters
        if item.kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}
    )
    if positional or any(item.kind is inspect.Parameter.VAR_POSITIONAL for item in parameters):
        return function(value)
    return function()


def _terminal(
    request: StopInput,
    decision: StopDecision,
    verification: VerificationResult | None,
    *,
    limitation_key: str | None = None,
    count_before: int = 0,
    cleanup: bool = True,
    cleanup_required: bool = True,
) -> StopOutput:
    cleaned = _invoke_cleanup(request) if cleanup else False
    if cleanup and not cleaned:
        decision = StopDecision.LIMITATION
        limitation_key = "capability.turn_cleanup_failed"
    return StopOutput(
        decision=decision,
        verification=verification,
        limitation_key=limitation_key,
        repair_count_before=count_before,
        repair_count_after=count_before,
        cleanup_performed=cleaned,
        terminal_cleanup_required=cleanup_required,
    )


def handle_stop(request: StopInput | None = None, **kwargs: object) -> StopOutput:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Verify the final candidate and decide pass, one repair, hold, or limitation."""

    request = request if request is not None else StopInput(**kwargs)  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
    if not isinstance(request, StopInput):
        raise TypeError("handle_stop requires StopInput")
    count_before, count_invalid = _repair_count(request)
    if count_invalid:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            None,
            limitation_key="capability.repair_count_inconsistent",
            count_before=count_before,
        )

    if _no_candidate_is_safe_stop(request):
        return _terminal(request, StopDecision.PASS, None, count_before=count_before)
    if not _has_candidate(request):
        return _terminal(
            request,
            StopDecision.LIMITATION,
            None,
            limitation_key="capability.no_completion_candidate",
            count_before=count_before,
        )

    try:
        verification = _verify(request)
    except Exception:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            _error_result("OSV-CAPABILITY-005", "capability.stop_verifier_failed", "/verifier"),
            limitation_key="capability.stop_verifier_failed",
            count_before=count_before,
        )

    if verification.outcome is VerificationOutcome.PASS:
        return _terminal(request, StopDecision.PASS, verification, count_before=count_before)
    if verification.outcome is VerificationOutcome.INSUFFICIENT:
        return _terminal(
            request,
            StopDecision.HOLD,
            verification,
            limitation_key="completion.required_criteria_unmet",
            count_before=count_before,
        )
    if verification.outcome is not VerificationOutcome.REPAIR:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            verification,
            limitation_key="capability.completion_verification_unavailable",
            count_before=count_before,
        )

    if count_before >= 1:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            verification,
            limitation_key="capability.repair_already_used",
            count_before=count_before,
        )
    if _native_stop_active(request):
        return _terminal(
            request,
            StopDecision.LIMITATION,
            verification,
            limitation_key="capability.native_stop_hook_active",
            count_before=count_before,
        )
    if request.continuation_supported is False:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            verification,
            limitation_key="capability.continuation_unavailable",
            count_before=count_before,
        )

    try:
        renderer = request.repair_renderer or render_repair_instruction
        instruction = _call_render(renderer, tuple(verification.violations), request)
    except Exception:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            verification,
            limitation_key="capability.repair_renderer_failed",
            count_before=count_before,
        )

    reserved, unsafe_failure = _reserve(request)
    if not reserved:
        return _terminal(
            request,
            StopDecision.LIMITATION,
            verification,
            limitation_key=(
                "capability.repair_reservation_conflict"
                if unsafe_failure
                else "capability.repair_reservation_unavailable"
            ),
            count_before=count_before,
            cleanup=not unsafe_failure,
            cleanup_required=True,
        )

    return StopOutput(
        decision=StopDecision.CONTINUE_ONCE,
        verification=verification,
        repair_instruction=instruction,
        repair_count_before=count_before,
        repair_count_after=1,
        reserved=True,
        cleanup_performed=False,
        terminal_cleanup_required=False,
    )


process_stop = handle_stop
decide_stop = handle_stop
handle_completion_stop = handle_stop


__all__ = [
    "RepairReservation",
    "StopDecision",
    "StopDecisionKind",
    "StopDecisionResult",
    "StopHandlingResult",
    "StopInput",
    "StopOutcome",
    "StopOutput",
    "StopRequest",
    "StopVerifier",
    "decide_stop",
    "handle_completion_stop",
    "handle_stop",
    "process_stop",
]
