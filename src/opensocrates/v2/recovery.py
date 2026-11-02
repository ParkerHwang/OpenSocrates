"""Pure recovery decisions for an interrupted delivery attempt.

Callers pass status values only. This module does not read a source, send,
cancel, inspect a host, or retain a body in a file, database, log, or queue.
A message identifier or hash is not accepted, because neither restores a body.
An internal retry identity is not accepted and does not reduce external
duplicate risk. Exactly-once external execution and successful cancellation are
not outcomes of this module. A cancellation observation blocks another send in
that decision; it does not prove an earlier effect was undone.

``payload_unrecoverable`` is the lost delivery body. It is distinct from a
learning input that cannot be read (``input_unavailable``), which this module
does not classify. ``effect_unknown`` is independent of that payload result:
a body may be gone and an external effect may already have happened.

Host acceptance, a later response, and an artifact check remain separate.
``receipt_confirmed`` records acceptance only. It does not confirm the external
effect and does not make another send safe. A missing receipt stays
``sent_unconfirmed`` or ``unknown``; this module does not promote a click,
a rejection, a timeout, or a cancellation report into acceptance or into proof
that nothing was sent.

Pending user confirmation and pending host permission are waits, not work
failure. Unknown authority is not permission and not a denial. The decision
covers the affected attempt only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, cast


class RecoveryInputError(ValueError):
    """Raised when a recovery status is missing or contradicts itself."""


class SourceReacquisition(StrEnum):
    """Whether an already permitted source can supply the body again."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class AuthorityState(StrEnum):
    """Current authority for the affected attempt. History is not authority."""

    PERMITTED = "permitted"
    DENIED = "denied"
    PENDING_USER = "pending_user"
    PENDING_HOST = "pending_host"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class ReceiptState(StrEnum):
    """Observed receipt. Absence of a receipt is not a confirmed non-send."""

    NOT_SENT = "not_sent"
    SEND_ATTEMPTED = "send_attempted"
    SENT_UNCONFIRMED = "sent_unconfirmed"
    RECEIPT_CONFIRMED = "receipt_confirmed"
    RECEIPT_REJECTED = "receipt_rejected"
    UNKNOWN = "unknown"


class CancellationObservation(StrEnum):
    """What was observed about cancellation. None of these is success."""

    NOT_OBSERVED = "not_observed"
    ATTEMPTED_UNCONFIRMED = "attempted_unconfirmed"
    REPORTED_STOPPED = "reported_stopped"


class PayloadDisposition(StrEnum):
    """Body recovery, independent of send and effect."""

    REACQUIRE_AND_REVALIDATE = "reacquire_and_revalidate"
    PAYLOAD_UNRECOVERABLE = "payload_unrecoverable"
    UNKNOWN = "unknown"


class EffectDisposition(StrEnum):
    """External effect of this attempt, independent of payload recovery."""

    NO_SEND = "no_send"
    EFFECT_UNKNOWN = "effect_unknown"


class RetryDisposition(StrEnum):
    """Whether another send is authorized. Inspection is not a send."""

    REVALIDATE_THEN_SEND = "revalidate_then_send"
    INSPECT_EXISTING_FIRST = "inspect_existing_first"
    HOLD_FOR_AUTHORITY = "hold_for_authority"
    HOLD_UNKNOWN_AUTHORITY = "hold_unknown_authority"
    HOLD_PAYLOAD_UNKNOWN = "hold_payload_unknown"
    DO_NOT_RETRY = "do_not_retry"


class DuplicateRisk(StrEnum):
    """Risk that another send repeats an external effect."""

    NONE = "none"
    POSSIBLE = "possible"
    RESEND_WOULD_DUPLICATE = "resend_would_duplicate"
    UNKNOWN = "unknown"


class AuthorityWait(StrEnum):
    """A named wait. It is not a delivery failure."""

    NONE = "none"
    USER_CONFIRMATION = "user_confirmation"
    HOST_PERMISSION = "host_permission"


_PENDING = frozenset({AuthorityState.PENDING_USER, AuthorityState.PENDING_HOST})


@dataclass(frozen=True, slots=True)
class RecoveryInput:
    """Closed statuses for one interrupted attempt. No body is accepted."""

    source_reacquisition: SourceReacquisition
    authority: AuthorityState
    receipt: ReceiptState
    cancellation: CancellationObservation = CancellationObservation.NOT_OBSERVED

    def __post_init__(self) -> None:
        _require(self.source_reacquisition, SourceReacquisition, "source_reacquisition")
        _require(self.authority, AuthorityState, "authority")
        _require(self.receipt, ReceiptState, "receipt")
        _require(self.cancellation, CancellationObservation, "cancellation")


@dataclass(frozen=True, slots=True)
class PayloadAssessment:
    """Whether the body can be reconstructed. Reacquisition is not a send."""

    disposition: PayloadDisposition

    def __post_init__(self) -> None:
        _require(self.disposition, PayloadDisposition, "payload disposition")


@dataclass(frozen=True, slots=True)
class EffectAssessment:
    """Receipt and effect stay side by side. Cancellation does not clear either."""

    disposition: EffectDisposition
    receipt: ReceiptState
    cancellation: CancellationObservation
    cancellation_succeeded: Literal[False] = False

    def __post_init__(self) -> None:
        _require(self.disposition, EffectDisposition, "effect disposition")
        _require(self.receipt, ReceiptState, "effect receipt")
        _require(self.cancellation, CancellationObservation, "effect cancellation")
        _reject_unless_false(
            self.cancellation_succeeded,
            "cancellation success is not a recovery outcome",
        )
        not_sent = self.receipt is ReceiptState.NOT_SENT
        if not_sent and self.disposition is not EffectDisposition.NO_SEND:
            raise RecoveryInputError("a confirmed non-send is the only no-send effect")
        if not not_sent and self.disposition is not EffectDisposition.EFFECT_UNKNOWN:
            raise RecoveryInputError("an unverified send remains effect_unknown")


@dataclass(frozen=True, slots=True)
class RetryAssessment:
    """Send gate for the same attempt. It does not rewrite payload or effect.

    ``inspect_before_any_send`` forbids another send until an existing session
    or result is checked. Only ``inspect_existing_first`` authorizes that
    check, and only when current authority is permitted. Denial is not
    permission to inspect. A confirmed receipt is not permission to send again.
    """

    disposition: RetryDisposition
    duplicate_risk: DuplicateRisk
    authority_wait: AuthorityWait
    another_send_allowed: bool
    inspect_before_any_send: bool
    blind_retry_allowed: Literal[False] = False
    assumes_exactly_once: Literal[False] = False

    def __post_init__(self) -> None:
        _require(self.disposition, RetryDisposition, "retry disposition")
        _require(self.duplicate_risk, DuplicateRisk, "duplicate risk")
        _require(self.authority_wait, AuthorityWait, "authority wait")
        _check_retry(self)


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """Three independent assessments. None retains the attempted body."""

    payload: PayloadAssessment
    effect: EffectAssessment
    retry: RetryAssessment
    scope: Literal["affected_attempt"] = "affected_attempt"
    exactly_once: Literal[False] = False
    retains_body: Literal[False] = False
    work_failure: Literal[False] = False

    def __post_init__(self) -> None:
        if type(self.payload) is not PayloadAssessment:
            raise RecoveryInputError("payload must be PayloadAssessment")
        if type(self.effect) is not EffectAssessment:
            raise RecoveryInputError("effect must be EffectAssessment")
        if type(self.retry) is not RetryAssessment:
            raise RecoveryInputError("retry must be RetryAssessment")
        if self.scope != "affected_attempt":
            raise RecoveryInputError("recovery scope stays on the affected attempt")
        _reject_unless_false(self.exactly_once, "exactly-once is not a recovery outcome")
        _reject_unless_false(self.retains_body, "recovery does not retain a body")
        _reject_unless_false(self.work_failure, "recovery does not classify work failure")


def decide_recovery(situation: RecoveryInput) -> RecoveryDecision:
    """Assess payload, effect, and retry without letting one replace another."""

    if type(situation) is not RecoveryInput:
        raise RecoveryInputError("situation must be RecoveryInput")
    return RecoveryDecision(
        payload=assess_payload(situation.source_reacquisition),
        effect=assess_effect(situation.receipt, situation.cancellation),
        retry=assess_retry(
            situation.source_reacquisition,
            situation.authority,
            situation.receipt,
            situation.cancellation,
        ),
    )


def assess_payload(source_reacquisition: SourceReacquisition) -> PayloadAssessment:
    """Classify the body. Storage, an outbox, an id, or a hash is not a source."""

    source = _require(source_reacquisition, SourceReacquisition, "source_reacquisition")
    if source is SourceReacquisition.AVAILABLE:
        return PayloadAssessment(PayloadDisposition.REACQUIRE_AND_REVALIDATE)
    if source is SourceReacquisition.UNAVAILABLE:
        return PayloadAssessment(PayloadDisposition.PAYLOAD_UNRECOVERABLE)
    if source is SourceReacquisition.UNKNOWN:
        return PayloadAssessment(PayloadDisposition.UNKNOWN)
    raise RecoveryInputError("source_reacquisition is not a known SourceReacquisition")


def assess_effect(
    receipt: ReceiptState,
    cancellation: CancellationObservation = CancellationObservation.NOT_OBSERVED,
) -> EffectAssessment:
    """Classify the external effect. Cancellation is recorded and is not success."""

    observed_receipt = _require(receipt, ReceiptState, "receipt")
    observed_cancellation = _require(cancellation, CancellationObservation, "cancellation")
    if observed_receipt is ReceiptState.NOT_SENT:
        disposition = EffectDisposition.NO_SEND
    else:
        disposition = EffectDisposition.EFFECT_UNKNOWN
    return EffectAssessment(
        disposition=disposition,
        receipt=observed_receipt,
        cancellation=observed_cancellation,
    )


def assess_retry(
    source_reacquisition: SourceReacquisition,
    authority: AuthorityState,
    receipt: ReceiptState,
    cancellation: CancellationObservation = CancellationObservation.NOT_OBSERVED,
) -> RetryAssessment:
    """Decide a later send. Unknown or possible external effect is not retried blindly.

    A cancellation observation never authorizes another send and never counts
    as proof that an earlier effect was undone.
    """

    source = _require(source_reacquisition, SourceReacquisition, "source_reacquisition")
    current = _require(authority, AuthorityState, "authority")
    observed = _require(receipt, ReceiptState, "receipt")
    observed_cancellation = _require(cancellation, CancellationObservation, "cancellation")
    if observed is ReceiptState.NOT_SENT:
        disposition = _pre_send_disposition(source, current, observed_cancellation)
        inspect = False
    else:
        disposition = _post_send_disposition(current)
        inspect = True
    return RetryAssessment(
        disposition=disposition,
        duplicate_risk=_duplicate_risk(observed),
        authority_wait=_authority_wait(current),
        another_send_allowed=disposition is RetryDisposition.REVALIDATE_THEN_SEND,
        inspect_before_any_send=inspect,
    )


def _pre_send_disposition(
    source: SourceReacquisition,
    authority: AuthorityState,
    cancellation: CancellationObservation,
) -> RetryDisposition:
    if authority in _PENDING:
        return RetryDisposition.HOLD_FOR_AUTHORITY
    if authority is AuthorityState.UNKNOWN:
        return RetryDisposition.HOLD_UNKNOWN_AUTHORITY
    if cancellation is not CancellationObservation.NOT_OBSERVED:
        return RetryDisposition.DO_NOT_RETRY
    if source is SourceReacquisition.UNAVAILABLE:
        return RetryDisposition.DO_NOT_RETRY
    if source is SourceReacquisition.UNKNOWN:
        if authority is AuthorityState.PERMITTED:
            return RetryDisposition.HOLD_PAYLOAD_UNKNOWN
        return RetryDisposition.DO_NOT_RETRY
    if authority is AuthorityState.PERMITTED:
        return RetryDisposition.REVALIDATE_THEN_SEND
    return RetryDisposition.DO_NOT_RETRY


def _post_send_disposition(authority: AuthorityState) -> RetryDisposition:
    if authority in _PENDING:
        return RetryDisposition.HOLD_FOR_AUTHORITY
    if authority is AuthorityState.UNKNOWN:
        return RetryDisposition.HOLD_UNKNOWN_AUTHORITY
    if authority is AuthorityState.PERMITTED:
        return RetryDisposition.INSPECT_EXISTING_FIRST
    return RetryDisposition.DO_NOT_RETRY


def _duplicate_risk(receipt: ReceiptState) -> DuplicateRisk:
    if receipt is ReceiptState.NOT_SENT:
        return DuplicateRisk.NONE
    if receipt is ReceiptState.SEND_ATTEMPTED:
        return DuplicateRisk.POSSIBLE
    if receipt is ReceiptState.SENT_UNCONFIRMED:
        return DuplicateRisk.POSSIBLE
    if receipt is ReceiptState.RECEIPT_CONFIRMED:
        return DuplicateRisk.RESEND_WOULD_DUPLICATE
    if receipt is ReceiptState.RECEIPT_REJECTED:
        return DuplicateRisk.UNKNOWN
    if receipt is ReceiptState.UNKNOWN:
        return DuplicateRisk.UNKNOWN
    raise RecoveryInputError("receipt is not a known ReceiptState")


def _authority_wait(authority: AuthorityState) -> AuthorityWait:
    if authority is AuthorityState.PENDING_USER:
        return AuthorityWait.USER_CONFIRMATION
    if authority is AuthorityState.PENDING_HOST:
        return AuthorityWait.HOST_PERMISSION
    return AuthorityWait.NONE


def _check_retry(assessment: RetryAssessment) -> None:
    _reject_unless_false(assessment.blind_retry_allowed, "blind retry is not a recovery outcome")
    _reject_unless_false(
        assessment.assumes_exactly_once,
        "exactly-once is not a recovery outcome",
    )
    send_allowed = assessment.disposition is RetryDisposition.REVALIDATE_THEN_SEND
    if assessment.another_send_allowed is not send_allowed:
        raise RecoveryInputError("another send does not match the retry disposition")
    if send_allowed and assessment.duplicate_risk is not DuplicateRisk.NONE:
        raise RecoveryInputError("a new send requires no prior duplicate risk")
    if assessment.inspect_before_any_send and send_allowed:
        raise RecoveryInputError("inspection and a new send cannot both be authorized")
    no_prior_send = assessment.duplicate_risk is DuplicateRisk.NONE
    if no_prior_send is assessment.inspect_before_any_send:
        raise RecoveryInputError("inspection does not match duplicate risk")
    holding = assessment.disposition is RetryDisposition.HOLD_FOR_AUTHORITY
    waiting = assessment.authority_wait is not AuthorityWait.NONE
    if holding is not waiting:
        raise RecoveryInputError("an authority hold requires a named wait")


def _require[T: StrEnum](value: object, kind: type[T], name: str) -> T:
    if type(value) is not kind:
        raise RecoveryInputError(f"{name} must be {kind.__name__}")
    return cast(T, value)


def _reject_unless_false(value: object, message: str) -> None:
    if value is not False:
        raise RecoveryInputError(message)


__all__ = [
    "AuthorityState",
    "AuthorityWait",
    "CancellationObservation",
    "DuplicateRisk",
    "EffectAssessment",
    "EffectDisposition",
    "PayloadAssessment",
    "PayloadDisposition",
    "ReceiptState",
    "RecoveryDecision",
    "RecoveryInput",
    "RecoveryInputError",
    "RetryAssessment",
    "RetryDisposition",
    "SourceReacquisition",
    "assess_effect",
    "assess_payload",
    "assess_retry",
    "decide_recovery",
]
