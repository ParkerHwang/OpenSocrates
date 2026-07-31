"""Pure settings commands and atomic application-level settings mutations.

The persistence layer owns locking and replacement of ``UserSettings``.  This
module owns the semantic transitions that are allowed to reach that layer.  A
transition is always built from a frozen model and is handed to the store as a
single read/transform/write operation; this keeps revisions and the
content-free intervention ring race-safe.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Final, Protocol, TypeVar

from ..clock import Clock, SystemClock, utc_date
from ..domain.enums import (
    FeedbackOutcome,
    InterventionClass,
    MetricsConsent,
    Participation,
    RecordingMode,
    Rigor,
)
from ..domain.models import (
    FeedbackEntry,
    InterventionPreference,
    RigorDecision,
    UserSettings,
)
from ..domain.risk import RiskSignals, build_rigor_from_risk
from ..domain.validation import validate_model
from ..version import PRODUCT_VERSION

CURRENT_ONBOARDING_VERSION: Final[str] = PRODUCT_VERSION
MIN_RETENTION_DAYS: Final[int] = 7
MAX_RETENTION_DAYS: Final[int] = 3650
MIN_SIZE_LIMIT_BYTES: Final[int] = 10 * 1024 * 1024
MAX_SIZE_LIMIT_BYTES: Final[int] = 10 * 1024 * 1024 * 1024

INTERVENTION_CLASSES: Final[tuple[InterventionClass, ...]] = (
    InterventionClass.REFRAME,
    InterventionClass.CONFLICT,
    InterventionClass.WEAK_EVIDENCE,
    InterventionClass.MISSING_ALTERNATIVE,
    InterventionClass.COMPLETION_GAP,
)
_INTERVENTION_CLASS_BY_VALUE: Final[dict[str, InterventionClass]] = {
    item.value: item for item in INTERVENTION_CLASSES
}
_MAX_FEEDBACK_ENTRIES: Final[int] = 20
_REDUCTION_DAYS: Final[int] = 30


class AtomicSettingsRepository(Protocol):
    """Minimal persistence contract required by this application module."""

    def load(self) -> UserSettings: ...

    def mutate(self, transform: Callable[[UserSettings], UserSettings]) -> UserSettings: ...


class SettingsMutationError(RuntimeError):
    """Raised when a repository cannot provide atomic settings mutation."""


@dataclass(frozen=True, slots=True)
class RigorRequest:
    """Closed result of parsing an explicit rigor request.

    ``ambiguous`` is deliberately separate from ``level is None`` so callers
    can distinguish an unrelated prompt from preference language that must not
    mutate stored settings.
    """

    level: Rigor | None = None
    persistent: bool = False
    one_task: bool = False
    ambiguous: bool = False


@dataclass(frozen=True, slots=True)
class RigorMutationResult:
    """Result of a parsed rigor request without exposing settings internals."""

    settings: UserSettings
    request: RigorRequest
    changed: bool
    persisted: bool
    effective_for_task: Rigor | None = None


@dataclass(frozen=True, slots=True)
class RecordingEligibility:
    """First-judgment and durable-recording decision for one host turn."""

    is_judgment: bool
    show_disclosure: bool
    disclosure_turn: bool
    recording_mode: RecordingMode
    recording_eligible: bool
    reason_code: str | None = None


@dataclass(frozen=True, slots=True)
class FeedbackSignal:
    """A closed, content-free feedback signal from one direct-user event."""

    intervention_class: InterventionClass
    outcome: FeedbackOutcome
    source: str | None = None
    explicit: bool = False
    current_event: bool = False


@dataclass(frozen=True, slots=True)
class FeedbackMutationResult:
    """Batch result with only closed class/outcome data."""

    settings: UserSettings
    applied: tuple[tuple[InterventionClass, FeedbackOutcome], ...] = ()


_T = TypeVar("_T")


def _all_preferences(settings: UserSettings) -> dict[str, InterventionPreference]:
    """Return a fresh map containing every closed class.

    Older or partially written settings may omit the five map entries.  Missing
    entries are filled in memory; unknown entries are retained so a read does
    not discard data owned by a future schema.
    """

    preferences = dict(settings.intervention_preferences)
    for intervention_class in INTERVENTION_CLASSES:
        preferences.setdefault(intervention_class.value, InterventionPreference())
    return preferences


def fresh_settings() -> UserSettings:
    """Return the complete fresh-install settings projection."""

    return UserSettings(intervention_preferences=_all_preferences(UserSettings()))


def normalize_settings(settings: UserSettings) -> UserSettings:
    """Fill missing current feedback classes without changing other settings."""

    if not isinstance(settings, UserSettings):
        raise TypeError("settings must be UserSettings")
    preferences = _all_preferences(settings)
    if preferences == settings.intervention_preferences:
        return settings
    return replace(settings, intervention_preferences=preferences)


def _next_revision(settings: UserSettings, **changes: Any) -> UserSettings:
    """Create a changed frozen settings model with exactly one revision step."""

    return replace(settings, revision=settings.revision + 1, **changes)


def _pure_change(settings: UserSettings, **changes: Any) -> UserSettings:
    """Apply a semantic change without changing the persistence revision."""

    if not isinstance(settings, UserSettings):
        raise TypeError("settings must be UserSettings")
    candidate = replace(settings, **changes)
    validate_model(candidate)
    return candidate


def _mutate(
    repository: AtomicSettingsRepository,
    transform: Callable[[UserSettings], UserSettings],
) -> UserSettings:
    """Run one atomic mutation and validate the returned frozen model.

    There is intentionally no ``load(); save()`` fallback.  That pair cannot
    guarantee a single revision under concurrent host processes.
    """

    mutate = getattr(repository, "mutate", None)
    if not callable(mutate):
        raise SettingsMutationError("settings repository lacks atomic mutate(transform)")
    result = mutate(transform)
    if not isinstance(result, UserSettings):
        raise SettingsMutationError("atomic settings mutation did not return UserSettings")
    validate_model(result)
    return result


def _mutating_transform(
    change: Callable[[UserSettings], UserSettings],
) -> Callable[[UserSettings], UserSettings]:
    """Wrap a revision-neutral pure command for the atomic store contract."""

    def transform(current: UserSettings) -> UserSettings:
        normalized = normalize_settings(current)
        candidate = change(normalized)
        if candidate == current:
            return current
        if candidate.revision != current.revision:
            candidate = replace(candidate, revision=current.revision)
        return _next_revision(candidate)

    return transform


def set_default_rigor(settings: UserSettings, level: Rigor) -> UserSettings:
    """Pure persistent-rigor command; storage revision is unchanged."""

    if not isinstance(level, Rigor):
        raise ValueError("rigor must be a closed Rigor value")
    return _pure_change(settings, default_rigor=level)


def set_locale(settings: UserSettings, locale: str | None) -> UserSettings:
    """Pure locale command accepting only follow-user, English, or Korean."""

    if locale not in {None, "en", "ko"}:
        raise ValueError("locale must be null, en, or ko")
    return _pure_change(settings, locale_preference=locale)


def set_recording_mode(
    settings: UserSettings,
    mode: RecordingMode,
    *,
    current_onboarding_version: str = CURRENT_ONBOARDING_VERSION,
) -> UserSettings:
    """Pure recording command with the disclosure-before-recording gate."""

    if not isinstance(mode, RecordingMode):
        raise ValueError("recording mode must be a closed RecordingMode value")
    if (
        mode is RecordingMode.LOCAL_PUBLIC_ARTIFACTS
        and settings.onboarding_version_seen != current_onboarding_version
    ):
        mode = RecordingMode.OFF
    return _pure_change(settings, recording_mode=mode)


def set_retention_days(settings: UserSettings, days: int) -> UserSettings:
    """Pure bounded record-retention command."""

    if isinstance(days, bool) or not MIN_RETENTION_DAYS <= days <= MAX_RETENTION_DAYS:
        raise ValueError("record retention must be between 7 and 3650 days")
    return _pure_change(settings, record_retention_days=days)


def set_size_limit_bytes(settings: UserSettings, size_bytes: int) -> UserSettings:
    """Pure bounded record-size command."""

    if (
        isinstance(size_bytes, bool)
        or not MIN_SIZE_LIMIT_BYTES <= size_bytes <= MAX_SIZE_LIMIT_BYTES
    ):
        raise ValueError("record size limit must be between 10 MiB and 10 GiB")
    return _pure_change(settings, record_size_limit_bytes=size_bytes)


def set_metrics_consent(settings: UserSettings, consent: MetricsConsent) -> UserSettings:
    """Keep the v1 metrics consent closed to ``none``."""

    if consent is not MetricsConsent.NONE:
        raise ValueError("v1 metrics consent is closed to none")
    return _pure_change(settings, metrics_consent=MetricsConsent.NONE)


def confirm_onboarding_disclosure(
    settings: UserSettings,
    version: str,
    *,
    trusted_host_confirmation: bool,
    recording_mode: RecordingMode = RecordingMode.LOCAL_PUBLIC_ARTIFACTS,
    current_onboarding_version: str = CURRENT_ONBOARDING_VERSION,
) -> UserSettings:
    """Pure post-disclosure transition.

    A host must prove that the current native surface rendered the disclosure.
    Without that proof, the version is not marked seen and recording stays off.
    The turn that performs this transition is separately non-recordable by
    :func:`recording_eligibility`.
    """

    if not isinstance(version, str) or not version:
        raise ValueError("onboarding version is required")
    if not isinstance(current_onboarding_version, str) or not current_onboarding_version:
        raise ValueError("current onboarding version is required")
    if not isinstance(recording_mode, RecordingMode):
        raise ValueError("recording mode must be a closed RecordingMode value")
    if not trusted_host_confirmation or version != current_onboarding_version:
        return _pure_change(settings, recording_mode=RecordingMode.OFF)
    selected = (
        RecordingMode.LOCAL_PUBLIC_ARTIFACTS
        if recording_mode is RecordingMode.LOCAL_PUBLIC_ARTIFACTS
        else RecordingMode.OFF
    )
    return _pure_change(
        settings,
        onboarding_version_seen=version,
        recording_mode=selected,
    )


def recording_eligibility(
    settings: UserSettings,
    participation: Participation,
    *,
    current_onboarding_version: str = CURRENT_ONBOARDING_VERSION,
    disclosure_turn: bool = False,
) -> RecordingEligibility:
    """Decide whether the current turn may create durable task artifacts."""

    if not isinstance(participation, Participation):
        raise ValueError("participation must be a closed Participation value")
    is_judgment = participation in {Participation.JUDGMENT, Participation.MIXED}
    show_disclosure = is_judgment and settings.onboarding_version_seen != current_onboarding_version
    if not is_judgment:
        return RecordingEligibility(
            is_judgment=False,
            show_disclosure=False,
            disclosure_turn=False,
            recording_mode=RecordingMode.OFF,
            recording_eligible=False,
            reason_code="mechanical",
        )
    if show_disclosure or disclosure_turn:
        return RecordingEligibility(
            is_judgment=True,
            show_disclosure=show_disclosure,
            disclosure_turn=True,
            recording_mode=RecordingMode.OFF,
            recording_eligible=False,
            reason_code="onboarding_disclosure_turn",
        )
    if settings.onboarding_version_seen != current_onboarding_version:
        return RecordingEligibility(
            is_judgment=True,
            show_disclosure=True,
            disclosure_turn=False,
            recording_mode=RecordingMode.OFF,
            recording_eligible=False,
            reason_code="onboarding_unconfirmed",
        )
    if settings.recording_mode is not RecordingMode.LOCAL_PUBLIC_ARTIFACTS:
        return RecordingEligibility(
            is_judgment=True,
            show_disclosure=False,
            disclosure_turn=False,
            recording_mode=RecordingMode.OFF,
            recording_eligible=False,
            reason_code="recording_off",
        )
    return RecordingEligibility(
        is_judgment=True,
        show_disclosure=False,
        disclosure_turn=False,
        recording_mode=RecordingMode.LOCAL_PUBLIC_ARTIFACTS,
        recording_eligible=True,
    )


def effective_recording_mode(
    settings: UserSettings,
    *,
    current_onboarding_version: str = CURRENT_ONBOARDING_VERSION,
) -> RecordingMode:
    """Return the durable mode that is actually safe for a later turn."""

    if settings.onboarding_version_seen != current_onboarding_version:
        return RecordingMode.OFF
    if settings.recording_mode is not RecordingMode.LOCAL_PUBLIC_ARTIFACTS:
        return RecordingMode.OFF
    return RecordingMode.LOCAL_PUBLIC_ARTIFACTS


def decide_rigor(
    settings: UserSettings,
    task_override: Rigor | None,
    participation: Participation,
    *,
    risk_signals: RiskSignals | None = None,
) -> RigorDecision:
    """Resolve a task's rigor without mutating stored settings."""

    return build_rigor_from_risk(
        settings.default_rigor,
        task_override,
        participation,
        signals=risk_signals,
    )


def _normalize_request_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("rigor request must be text")
    return " ".join(text.casefold().strip().split())


def parse_rigor_request(text: str) -> RigorRequest:
    """Parse only explicit closed rigor language; ambiguous language is inert."""

    normalized = _normalize_request_text(text)
    if not normalized:
        return RigorRequest(ambiguous=False)

    skill = re.fullmatch(
        r"/?opensocrates:rigor\s+(quiet|together|strict)(?:\s+--once)?", normalized
    )
    if skill:
        level = Rigor(skill.group(1))
        return RigorRequest(
            level=level,
            persistent="--once" not in normalized,
            one_task="--once" in normalized,
        )

    level_matches: set[Rigor] = set()
    level_phrases: tuple[tuple[Rigor, tuple[str, ...]], ...] = (
        (Rigor.QUIET, ("quiet", "just handle it", "조용히", "알아서 해줘")),
        (Rigor.TOGETHER, ("together", "check what matters", "중요한 건 확인해줘")),
        (
            Rigor.STRICT,
            ("strict", "this must not be wrong", "이건 틀리면 안 돼", "이건 틀리면 안돼"),
        ),
    )
    for level, phrases in level_phrases:
        if any(phrase in normalized for phrase in phrases):
            level_matches.add(level)
    if len(level_matches) != 1:
        return RigorRequest(
            ambiguous=bool(level_matches) or "rigor" in normalized or "엄격" in normalized
        )

    one_task_markers = ("for this", "this task", "이번만", "이번 작업", "이 작업만")
    persistent_markers = ("from now on", "default", "앞으로", "기본값", "계속")
    one_task = any(marker in normalized for marker in one_task_markers)
    persistent = any(marker in normalized for marker in persistent_markers)
    if one_task == persistent:
        return RigorRequest(ambiguous=True)
    return RigorRequest(level=next(iter(level_matches)), persistent=persistent, one_task=one_task)


def _set_and_commit(
    repository: AtomicSettingsRepository,
    pure_command: Callable[[UserSettings], UserSettings],
) -> UserSettings:
    return _mutate(repository, _mutating_transform(pure_command))


def persist_rigor(repository: AtomicSettingsRepository, level: Rigor) -> UserSettings:
    """Persist one explicit default-rigor change atomically."""

    return _set_and_commit(repository, lambda settings: set_default_rigor(settings, level))


def persist_locale(repository: AtomicSettingsRepository, locale: str | None) -> UserSettings:
    return _set_and_commit(repository, lambda settings: set_locale(settings, locale))


def persist_recording_mode(
    repository: AtomicSettingsRepository,
    mode: RecordingMode,
    *,
    current_onboarding_version: str = CURRENT_ONBOARDING_VERSION,
) -> UserSettings:
    return _set_and_commit(
        repository,
        lambda settings: set_recording_mode(
            settings,
            mode,
            current_onboarding_version=current_onboarding_version,
        ),
    )


def persist_retention_days(repository: AtomicSettingsRepository, days: int) -> UserSettings:
    return _set_and_commit(repository, lambda settings: set_retention_days(settings, days))


def persist_size_limit_bytes(repository: AtomicSettingsRepository, size_bytes: int) -> UserSettings:
    return _set_and_commit(repository, lambda settings: set_size_limit_bytes(settings, size_bytes))


def persist_onboarding_disclosure(
    repository: AtomicSettingsRepository,
    version: str,
    *,
    trusted_host_confirmation: bool,
    recording_mode: RecordingMode = RecordingMode.LOCAL_PUBLIC_ARTIFACTS,
    current_onboarding_version: str = CURRENT_ONBOARDING_VERSION,
) -> UserSettings:
    """Commit the disclosure transition only after trusted rendering proof."""

    return _set_and_commit(
        repository,
        lambda settings: confirm_onboarding_disclosure(
            settings,
            version,
            trusted_host_confirmation=trusted_host_confirmation,
            recording_mode=recording_mode,
            current_onboarding_version=current_onboarding_version,
        ),
    )


def apply_rigor_request(
    repository: AtomicSettingsRepository,
    text: str,
    *,
    participation: Participation = Participation.JUDGMENT,
    risk_signals: RiskSignals | None = None,
) -> RigorMutationResult:
    """Apply only an unambiguous explicit rigor request.

    One-task requests are resolved entirely in memory.  Persistent requests use
    one atomic settings revision.  Ambiguous preference language performs no
    mutation and returns the current settings.
    """

    request = parse_rigor_request(text)
    current = repository.load()
    if request.level is None or request.ambiguous:
        return RigorMutationResult(
            settings=current,
            request=request,
            changed=False,
            persisted=False,
        )
    if request.one_task:
        decision = decide_rigor(current, request.level, participation, risk_signals=risk_signals)
        return RigorMutationResult(
            settings=current,
            request=request,
            changed=False,
            persisted=False,
            effective_for_task=decision.effective_rigor,
        )
    committed = persist_rigor(repository, request.level)
    return RigorMutationResult(
        settings=committed,
        request=request,
        changed=committed != current,
        persisted=committed != current,
        effective_for_task=committed.default_rigor,
    )


def _parse_day(day_value: str | date) -> date:
    if isinstance(day_value, date):
        return day_value
    if not isinstance(day_value, str):
        raise ValueError("feedback day must be YYYY-MM-DD")
    try:
        return date.fromisoformat(day_value)
    except ValueError as error:
        raise ValueError("feedback day must be YYYY-MM-DD") from error


def _feedback_preference(
    settings: UserSettings,
    intervention_class: InterventionClass,
) -> InterventionPreference:
    if not isinstance(intervention_class, InterventionClass):
        raise ValueError("feedback class must be a closed InterventionClass value")
    return _all_preferences(settings)[intervention_class.value]


def append_feedback(
    settings: UserSettings,
    intervention_class: InterventionClass,
    outcome: FeedbackOutcome,
    *,
    day: str | date,
) -> UserSettings:
    """Purely append one already-authorized feedback signal.

    Authority checks belong to :func:`persist_feedback`; this function only
    transforms closed class/outcome data and never receives prose or IDs.
    """

    if not isinstance(outcome, FeedbackOutcome):
        raise ValueError("feedback outcome must be a closed FeedbackOutcome value")
    current_day = _parse_day(day)
    preferences = _all_preferences(settings)
    current = preferences[intervention_class.value]
    sequence = current.next_sequence
    entries = (
        *current.recent_feedback,
        FeedbackEntry(sequence=sequence, day=current_day.isoformat(), outcome=outcome),
    )
    entries = entries[-_MAX_FEEDBACK_ENTRIES:]
    reduced_since = current.reduced_since_sequence
    reduced_until = current.reduced_until
    if outcome is FeedbackOutcome.DISMISSED:
        dismissals = sum(item.outcome is FeedbackOutcome.DISMISSED for item in entries)
        if dismissals >= 2:
            reduced_since = sequence
            reduced_until = (current_day + timedelta(days=_REDUCTION_DAYS)).isoformat()
    elif reduced_since is not None:
        accepted_after = sum(
            item.outcome is FeedbackOutcome.ACCEPTED and item.sequence > reduced_since
            for item in entries
        )
        if accepted_after >= 3:
            entries = ()
            reduced_since = None
            reduced_until = None
    preferences[intervention_class.value] = InterventionPreference(
        next_sequence=sequence + 1,
        recent_feedback=tuple(entries),
        reduced_since_sequence=reduced_since,
        reduced_until=reduced_until,
    )
    return _pure_change(settings, intervention_preferences=preferences)


def _clear_preference(preference: InterventionPreference) -> InterventionPreference:
    return InterventionPreference(next_sequence=preference.next_sequence)


def expire_reduced_preferences(
    settings: UserSettings,
    *,
    current_day: str | date,
) -> UserSettings:
    """Pure read-time expiry for every reduction whose day has arrived."""

    today = _parse_day(current_day)
    preferences = _all_preferences(settings)
    changed = False
    for key, preference in tuple(preferences.items()):
        if preference.reduced_until is None:
            continue
        until = _parse_day(preference.reduced_until)
        if today >= until:
            preferences[key] = _clear_preference(preference)
            changed = True
    if not changed:
        return settings
    return _pure_change(settings, intervention_preferences=preferences)


def reset_preferences(settings: UserSettings) -> UserSettings:
    """Pure preference reset preserving each class's monotonic sequence."""

    preferences = _all_preferences(settings)
    cleared = {key: _clear_preference(value) for key, value in preferences.items()}
    if cleared == settings.intervention_preferences:
        return settings
    return _pure_change(settings, intervention_preferences=cleared)


def _authorized_signal(signal: FeedbackSignal) -> bool:
    return (
        isinstance(signal, FeedbackSignal)
        and signal.source == "direct_user"
        and signal.explicit
        and signal.current_event
        and isinstance(signal.intervention_class, InterventionClass)
        and isinstance(signal.outcome, FeedbackOutcome)
    )


def _deduplicate_signals(signals: Iterable[FeedbackSignal]) -> tuple[FeedbackSignal, ...]:
    """Keep at most one unambiguous signal per class in fixed contract order."""

    by_class: dict[InterventionClass, set[FeedbackOutcome]] = {}
    for signal in signals:
        if not _authorized_signal(signal):
            continue
        by_class.setdefault(signal.intervention_class, set()).add(signal.outcome)
    result: list[FeedbackSignal] = []
    for intervention_class in INTERVENTION_CLASSES:
        outcomes = by_class.get(intervention_class, set())
        if len(outcomes) == 1:
            result.append(
                FeedbackSignal(
                    intervention_class=intervention_class,
                    outcome=next(iter(outcomes)),
                    source="direct_user",
                    explicit=True,
                    current_event=True,
                )
            )
    return tuple(result)


def apply_feedback_batch(
    settings: UserSettings,
    signals: Iterable[FeedbackSignal],
    *,
    day: str | date,
) -> FeedbackMutationResult:
    """Purely apply each distinct authorized class at most once."""

    current = settings
    applied: list[tuple[InterventionClass, FeedbackOutcome]] = []
    for signal in _deduplicate_signals(signals):
        current = append_feedback(current, signal.intervention_class, signal.outcome, day=day)
        applied.append((signal.intervention_class, signal.outcome))
    return FeedbackMutationResult(settings=current, applied=tuple(applied))


def persist_feedback(
    repository: AtomicSettingsRepository,
    signal: FeedbackSignal,
    *,
    day: str | date,
) -> UserSettings:
    """Atomically append one direct-user explicit feedback signal, if allowed."""

    if not _authorized_signal(signal):
        return repository.load()
    return _set_and_commit(
        repository,
        lambda settings: append_feedback(
            settings,
            signal.intervention_class,
            signal.outcome,
            day=day,
        ),
    )


def persist_feedback_batch(
    repository: AtomicSettingsRepository,
    signals: Sequence[FeedbackSignal],
    *,
    day: str | date,
) -> FeedbackMutationResult:
    """Atomically process one direct-user event's distinct feedback classes."""

    authorized = _deduplicate_signals(signals)
    if not authorized:
        return FeedbackMutationResult(settings=repository.load())

    def transform(current: UserSettings) -> UserSettings:
        result = apply_feedback_batch(current, authorized, day=day)
        if result.settings == current:
            return current
        return _next_revision(result.settings)

    committed = _mutate(repository, transform)
    return FeedbackMutationResult(
        settings=committed,
        applied=tuple((s.intervention_class, s.outcome) for s in authorized),
    )


def read_settings(
    repository: AtomicSettingsRepository,
    *,
    clock: Clock | None = None,
) -> UserSettings:
    """Load settings and atomically clear reductions whose 30-day window ended."""

    current = repository.load()
    today = utc_date(clock or SystemClock())

    def transform(settings: UserSettings) -> UserSettings:
        expired = expire_reduced_preferences(settings, current_day=today)
        if expired == settings:
            return settings
        return _next_revision(expired)

    if not any(
        preference.reduced_until is not None for preference in _all_preferences(current).values()
    ):
        return current
    return _mutate(repository, transform)


def persist_expiry(
    repository: AtomicSettingsRepository,
    *,
    clock: Clock | None = None,
) -> UserSettings:
    """Explicit store-coordinated alias for read-time 30-day expiry."""

    return read_settings(repository, clock=clock)


def persist_preferences_reset(repository: AtomicSettingsRepository) -> UserSettings:
    """Reset only intervention feedback/reduction state atomically."""

    return _set_and_commit(repository, reset_preferences)


# Application-facing aliases kept intentionally boring for host adapters.
change_rigor = set_default_rigor
change_locale = set_locale
change_recording = set_recording_mode
change_retention = set_retention_days
change_size_limit = set_size_limit_bytes
update_rigor = persist_rigor
update_locale = persist_locale
update_recording = persist_recording_mode
update_retention = persist_retention_days
update_size_limit = persist_size_limit_bytes
complete_onboarding = persist_onboarding_disclosure
record_intervention_feedback = persist_feedback
intervention_feedback = persist_feedback
reset_intervention_preferences = persist_preferences_reset


__all__ = [
    "AtomicSettingsRepository",
    "CURRENT_ONBOARDING_VERSION",
    "FeedbackMutationResult",
    "FeedbackSignal",
    "INTERVENTION_CLASSES",
    "MAX_RETENTION_DAYS",
    "MAX_SIZE_LIMIT_BYTES",
    "MIN_RETENTION_DAYS",
    "MIN_SIZE_LIMIT_BYTES",
    "RecordingEligibility",
    "RigorMutationResult",
    "RigorRequest",
    "SettingsMutationError",
    "append_feedback",
    "apply_feedback_batch",
    "apply_rigor_request",
    "change_locale",
    "change_recording",
    "change_retention",
    "change_rigor",
    "change_size_limit",
    "complete_onboarding",
    "confirm_onboarding_disclosure",
    "decide_rigor",
    "effective_recording_mode",
    "expire_reduced_preferences",
    "fresh_settings",
    "normalize_settings",
    "parse_rigor_request",
    "persist_expiry",
    "persist_feedback",
    "persist_feedback_batch",
    "persist_locale",
    "persist_onboarding_disclosure",
    "persist_preferences_reset",
    "persist_recording_mode",
    "persist_retention_days",
    "persist_rigor",
    "persist_size_limit_bytes",
    "read_settings",
    "intervention_feedback",
    "record_intervention_feedback",
    "recording_eligibility",
    "reset_intervention_preferences",
    "reset_preferences",
    "set_default_rigor",
    "set_locale",
    "set_metrics_consent",
    "set_recording_mode",
    "set_retention_days",
    "set_size_limit_bytes",
    "update_locale",
    "update_recording",
    "update_retention",
    "update_rigor",
    "update_size_limit",
]
