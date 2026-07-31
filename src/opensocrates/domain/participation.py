"""Pure participation-gate policy for the v1 judgment boundary.

The host model may supply semantic target categories, but the runtime owns the
closed decision and its invariants.  This module deliberately does not inspect
prompt text, host payloads, or method content.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import ValidationError
from .enums import (
    ConfidenceBasis,
    Participation,
    ParticipationReasonCode,
)
from .models import ParticipationDecision


@dataclass(frozen=True, slots=True)
class ParticipationSignals:
    """Closed semantic cues supplied by the host-model classifier.

    ``judgment_targets`` and ``mechanical_targets`` are already sanitized
    category descriptions.  The booleans make the gate usable before target
    text is available and are intentionally not inferred from prose here.
    """

    has_judgment_target: bool = False
    has_mechanical_target: bool = False
    judgment_targets: tuple[str, ...] = ()
    mechanical_targets: tuple[str, ...] = ()
    explicit_method: str | None = None
    reason_code: ParticipationReasonCode | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.has_judgment_target, bool) or not isinstance(
            self.has_mechanical_target, bool
        ):
            raise ValidationError("participation signals: target flags must be boolean")
        if not isinstance(self.judgment_targets, tuple) or not isinstance(
            self.mechanical_targets, tuple
        ):
            raise ValidationError("participation signals: targets must be tuples")
        if len(self.judgment_targets) > 3 or len(self.mechanical_targets) > 3:
            raise ValidationError("participation signals: at most three targets per kind")
        for target in (*self.judgment_targets, *self.mechanical_targets):
            if not isinstance(target, str) or not target.strip() or len(target) > 120:
                raise ValidationError(
                    "participation signals: target must be non-empty text of at most 120 characters"
                )
        if self.explicit_method is not None and (
            not isinstance(self.explicit_method, str) or not self.explicit_method.strip()
        ):
            raise ValidationError(
                "participation signals: explicit method must be a non-empty method ID"
            )
        if self.reason_code is not None and not isinstance(
            self.reason_code, ParticipationReasonCode
        ):
            raise ValidationError("participation signals: unknown reason code")


# The short alias is useful to application ports without creating a second
# contract type.
ParticipationInput = ParticipationSignals


_MECHANICAL_REASONS = frozenset(
    {
        ParticipationReasonCode.DIRECT_TRANSFORMATION,
        ParticipationReasonCode.DIRECT_ARTIFACT_ACTION,
        ParticipationReasonCode.DIRECT_RETRIEVAL,
        ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT,
    }
)
_JUDGMENT_REASONS = frozenset(
    {
        ParticipationReasonCode.JUDGMENT_CHOICE,
        ParticipationReasonCode.JUDGMENT_DIAGNOSIS,
        ParticipationReasonCode.JUDGMENT_EVIDENCE,
        ParticipationReasonCode.JUDGMENT_RISK,
        ParticipationReasonCode.JUDGMENT_COMPLETION,
        ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT,
    }
)
_MIXED_REASONS = frozenset(
    {
        ParticipationReasonCode.JUDGMENT_THEN_ARTIFACT,
        ParticipationReasonCode.ARTIFACT_WITH_JUDGMENT_SEGMENT,
        ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT,
    }
)


def _has_judgment(signals: ParticipationSignals) -> bool:
    return signals.has_judgment_target or bool(signals.judgment_targets)


def _has_mechanical(signals: ParticipationSignals) -> bool:
    return signals.has_mechanical_target or bool(signals.mechanical_targets)


def _default_reason(*, judgment: bool, mechanical: bool) -> ParticipationReasonCode:
    if judgment and mechanical:
        return ParticipationReasonCode.JUDGMENT_THEN_ARTIFACT
    if judgment:
        return ParticipationReasonCode.JUDGMENT_CHOICE
    return ParticipationReasonCode.DIRECT_TRANSFORMATION


def build_participation_decision(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    participation: Participation,
    reason_code: ParticipationReasonCode,
    *,
    judgment_targets: tuple[str, ...] = (),
    mechanical_targets: tuple[str, ...] = (),
    explicit_method: str | None = None,
    confidence_basis: ConfidenceBasis = ConfidenceBasis.RULE_PLUS_MODEL_POLICY,
) -> ParticipationDecision:
    """Construct and validate one closed participation decision.

    The mechanical gate is intentionally stricter than the model validator:
    an explicit method with no judgment target is represented as mechanical
    with ``explicit_method_without_judgment`` and can never be routed.
    """

    if not isinstance(participation, Participation):
        raise ValidationError("participation decision: unknown participation")
    if not isinstance(reason_code, ParticipationReasonCode):
        raise ValidationError("participation decision: unknown reason code")
    if not isinstance(confidence_basis, ConfidenceBasis):
        raise ValidationError("participation decision: unknown confidence basis")
    if not isinstance(judgment_targets, tuple) or not isinstance(mechanical_targets, tuple):
        raise ValidationError("participation decision: targets must be tuples")
    if explicit_method is not None and not isinstance(explicit_method, str):
        raise ValidationError("participation decision: explicit method must be text or null")

    if participation is Participation.MECHANICAL:
        if judgment_targets:
            raise ValidationError("mechanical participation cannot carry judgment targets")
        if reason_code not in _MECHANICAL_REASONS:
            raise ValidationError("mechanical participation has an incompatible reason code")
        if (
            reason_code is ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT
            and explicit_method is None
        ):
            raise ValidationError("explicit-method-without-judgment requires an explicit method")
        if (
            reason_code is not ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT
            and explicit_method is not None
        ):
            raise ValidationError(
                "an explicit method without judgment must use the explicit restraint reason"
            )
    elif participation is Participation.JUDGMENT:
        if not judgment_targets:
            raise ValidationError("judgment participation requires a judgment target")
        if reason_code not in _JUDGMENT_REASONS:
            raise ValidationError("judgment participation has an incompatible reason code")
        if (
            reason_code is ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
            and explicit_method is None
        ):
            raise ValidationError("explicit-method-with-judgment requires an explicit method")
        if (
            reason_code is not ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
            and explicit_method is not None
        ):
            raise ValidationError(
                "an explicit method with judgment must use the explicit invocation reason"
            )
    else:
        if not judgment_targets or not mechanical_targets:
            raise ValidationError(
                "mixed participation requires both judgment and mechanical targets"
            )
        if reason_code not in _MIXED_REASONS:
            raise ValidationError("mixed participation has an incompatible reason code")
        if (
            reason_code is ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
            and explicit_method is None
        ):
            raise ValidationError("explicit-method-with-judgment requires an explicit method")
        if (
            reason_code is not ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
            and explicit_method is not None
        ):
            raise ValidationError(
                "an explicit method with judgment must use the explicit invocation reason"
            )

    decision = ParticipationDecision(
        participation=participation,
        reason_code=reason_code,
        judgment_targets=judgment_targets,
        mechanical_targets=mechanical_targets,
        confidence_basis=confidence_basis,
        explicit_method=explicit_method,
    )
    return validate_participation_decision(decision)


def classify_participation(signals: ParticipationSignals) -> ParticipationDecision:
    """Derive a deterministic decision from closed semantic target cues."""

    if not isinstance(signals, ParticipationSignals):
        raise ValidationError("participation classifier requires ParticipationSignals")
    judgment = _has_judgment(signals)
    mechanical = _has_mechanical(signals)
    explicit = signals.explicit_method is not None

    if explicit and not judgment:
        # This is the hard restraint rule.  It applies even when the host did
        # not classify a mechanical target explicitly.
        participation = Participation.MECHANICAL
        reason = ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT
    elif judgment and mechanical:
        participation = Participation.MIXED
        reason = signals.reason_code or (
            ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
            if explicit
            else _default_reason(judgment=True, mechanical=True)
        )
    elif judgment:
        participation = Participation.JUDGMENT
        reason = signals.reason_code or (
            ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
            if explicit
            else _default_reason(judgment=True, mechanical=False)
        )
    else:
        participation = Participation.MECHANICAL
        reason = signals.reason_code or (
            ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT
            if explicit
            else _default_reason(judgment=False, mechanical=True)
        )

    # The classifier owns the canonical target segmentation.  A caller cannot
    # override the explicit-method restraint with an incompatible reason code.
    if (
        explicit
        and judgment
        and reason is not ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
    ):
        reason = ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
    if explicit and not judgment:
        reason = ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT

    # Preserve a useful closed target marker when a classifier only returned
    # the boolean cue.  The decision contract requires a target for judgment
    # and mixed outcomes, so the marker is deliberately not free prose from
    # the host model.
    judgment_targets = signals.judgment_targets or (
        ("judgment target",) if signals.has_judgment_target else ()
    )
    mechanical_targets = signals.mechanical_targets or (
        ("mechanical target",) if signals.has_mechanical_target else ()
    )

    return build_participation_decision(
        participation,
        reason,
        judgment_targets=judgment_targets,
        mechanical_targets=mechanical_targets,
        explicit_method=signals.explicit_method,
    )


def validate_participation_decision(decision: ParticipationDecision) -> ParticipationDecision:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Re-check policy invariants on an already constructed decision."""

    if not isinstance(decision, ParticipationDecision):
        raise ValidationError("participation decision: expected ParticipationDecision")
    participation = decision.participation
    reason = decision.reason_code
    has_judgment = bool(decision.judgment_targets)
    has_mechanical = bool(decision.mechanical_targets)
    explicit = decision.explicit_method is not None

    if participation is Participation.MECHANICAL and has_judgment:
        raise ValidationError("mechanical participation cannot carry judgment targets")
    if participation is Participation.JUDGMENT and not has_judgment:
        raise ValidationError("judgment participation requires a judgment target")
    if participation is Participation.MIXED and not (has_judgment and has_mechanical):
        raise ValidationError("mixed participation requires both target kinds")
    if participation is Participation.MECHANICAL and reason not in _MECHANICAL_REASONS:
        raise ValidationError("mechanical participation has an incompatible reason code")
    if participation is Participation.JUDGMENT and reason not in _JUDGMENT_REASONS:
        raise ValidationError("judgment participation has an incompatible reason code")
    if participation is Participation.MIXED and reason not in _MIXED_REASONS:
        raise ValidationError("mixed participation has an incompatible reason code")
    if (
        explicit
        and not has_judgment
        and reason is not ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT
    ):
        raise ValidationError("explicit method without judgment must be restrained")
    if (
        explicit
        and has_judgment
        and reason is not ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT
    ):
        raise ValidationError(
            "explicit method with judgment must use the explicit invocation reason"
        )
    if not explicit and reason in {
        ParticipationReasonCode.EXPLICIT_METHOD_WITH_JUDGMENT,
        ParticipationReasonCode.EXPLICIT_METHOD_WITHOUT_JUDGMENT,
    }:
        raise ValidationError("explicit reason code requires an explicit method")
    return decision


# Compatibility aliases for application code and early callers.
make_participation_decision = build_participation_decision
decide_participation = classify_participation
validate_participation = validate_participation_decision


__all__ = [
    "ParticipationInput",
    "ParticipationSignals",
    "build_participation_decision",
    "classify_participation",
    "decide_participation",
    "make_participation_decision",
    "validate_participation",
    "validate_participation_decision",
]
