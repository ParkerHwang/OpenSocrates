"""Pure eligibility and deduplication policy for tool observations.

The host adapter is responsible for converting a native hook event into
``ObservationMetadata``.  This module deliberately accepts no tool name,
command, path, source, input, output, error, or prompt field.  The only
correlation values it handles are already-normalized HMAC tags and bounded
closed metadata.  An eligible result is therefore safe to pass to the
application layer without creating a second raw-content retention boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Final, Iterable

from ..constants import MAX_OBSERVATION_TAGS
from ..errors import ValidationError
from ..ids import validate_sha256, validate_timestamp
from .enums import InterventionClass, TaskState, ToolCategory
from .models import TaskProjection

_ZERO_TAG: Final[str] = "sha256:" + ("0" * 64)
_ACTIVE_TASK_STATES: Final[frozenset[TaskState]] = frozenset(
    {
        TaskState.FRAMING,
        TaskState.WORKING,
        TaskState.REJUDGING,
        TaskState.CROSS_EXAMINING,
        TaskState.VERIFYING,
    }
)
_EVIDENCE_TOOL_CATEGORIES: Final[frozenset[ToolCategory]] = frozenset(
    {
        ToolCategory.RETRIEVAL,
        ToolCategory.READ,
        ToolCategory.SEARCH,
        ToolCategory.CALCULATION,
    }
)
_MECHANICAL_TOOL_CATEGORIES: Final[frozenset[ToolCategory]] = frozenset(
    {
        ToolCategory.WRITE,
        ToolCategory.FORMAT,
        ToolCategory.NAVIGATION,
    }
)


class ObservationStatus(StrEnum):
    """Closed result status retained for eligibility only."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


class ResultSizeBucket(StrEnum):
    """Closed, content-free result-size bucket."""

    EMPTY = "empty"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    OVERSIZE = "oversize"


class ObservationAction(StrEnum):
    """Whether the application may inject an observation obligation."""

    INJECT = "inject"
    EMPTY = "empty"


class ObservationReason(StrEnum):
    """Closed reasons for an observation decision."""

    ELIGIBLE = "eligible"
    NO_ACTIVE_TASK = "no_active_task"
    TASK_NOT_ACTIVE = "task_not_active"
    NO_CURRENT_JUDGMENT = "no_current_judgment"
    RECORDING_OFF = "recording_off"
    TASK_TAG_MISMATCH = "task_tag_mismatch"
    MECHANICAL_CATEGORY = "mechanical_category"
    INELIGIBLE_CATEGORY = "ineligible_category"
    EMPTY_RESULT = "empty_result"
    UNAVAILABLE_RESULT = "unavailable_result"
    DUPLICATE = "duplicate"
    BATCH_DUPLICATE = "batch_duplicate"
    DEDUPE_CAPACITY_EXHAUSTED = "dedupe_capacity_exhausted"


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationMetadata:
    """Normalized metadata for one bounded observation.

    Every correlation field is an already-derived ``sha256:`` tag.  There is
    intentionally no generic mapping field, raw payload field, or path-like
    field.  ``claim_version_tags`` is the active claim-version set used by the
    dedupe key; it is not a claim text or a model confidence value.
    """

    active_task_tag: str
    tool_category: ToolCategory | str
    result_size_bucket: ResultSizeBucket | str
    result_status: ObservationStatus | str
    tool_use_key: str
    occurred_at: str
    window_tag: str
    batch_tag: str | None = None
    subject_tag: str = _ZERO_TAG
    claim_version_tags: tuple[str, ...] = ()
    recording_eligible: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("active_task_tag", self.active_task_tag),
            ("tool_use_key", self.tool_use_key),
            ("window_tag", self.window_tag),
            ("subject_tag", self.subject_tag),
        ):
            _validate_tag(value, name)
        if self.batch_tag is not None:
            _validate_tag(self.batch_tag, "batch_tag")
        try:
            category = _coerce_enum(self.tool_category, ToolCategory, "tool_category")
            size = _coerce_enum(self.result_size_bucket, ResultSizeBucket, "result_size_bucket")
            status = _coerce_enum(self.result_status, ObservationStatus, "result_status")
        except ValueError as error:
            raise ValidationError(str(error)) from error
        object.__setattr__(self, "tool_category", category)
        object.__setattr__(self, "result_size_bucket", size)
        object.__setattr__(self, "result_status", status)
        if not isinstance(self.recording_eligible, bool):
            raise ValidationError("observation recording_eligible must be boolean")
        try:
            validate_timestamp(self.occurred_at)
        except (TypeError, ValueError) as error:
            raise ValidationError("observation occurred_at is invalid") from error
        if not isinstance(self.claim_version_tags, tuple):
            raise ValidationError("observation claim_version_tags must be a tuple")
        if len(self.claim_version_tags) > 5:
            raise ValidationError("observation claim_version_tags may contain at most five tags")
        for tag in self.claim_version_tags:
            _validate_tag(tag, "claim_version_tag")
        if tuple(sorted(set(self.claim_version_tags))) != self.claim_version_tags:
            raise ValidationError("observation claim_version_tags must be sorted and unique")

    @property
    def hmac_tool_key(self) -> str:
        """Compatibility name for the normalized HMAC tool-use key."""

        return self.tool_use_key

    @property
    def result_size(self) -> ResultSizeBucket:
        """Compatibility name for the closed result-size bucket."""

        return self.result_size_bucket  # type: ignore[return-value]  # Closed runtime boundary validates this value.

    @property
    def status(self) -> ObservationStatus:
        """Compatibility name for the closed result status."""

        return self.result_status  # type: ignore[return-value]  # Closed runtime boundary validates this value.


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationDedupeState:
    """Bounded content-free state supplied by the caller for one task/window."""

    fingerprints: tuple[str, ...] = ()
    batch_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.fingerprints, tuple) or not isinstance(self.batch_tags, tuple):
            raise ValidationError("observation dedupe state must use tuples")
        if len(self.fingerprints) > MAX_OBSERVATION_TAGS:
            raise ValidationError("observation fingerprint capacity exceeded")
        if len(self.batch_tags) > MAX_OBSERVATION_TAGS:
            raise ValidationError("observation batch capacity exceeded")
        for tag in (*self.fingerprints, *self.batch_tags):
            _validate_tag(tag, "observation dedupe tag")
        if len(set(self.fingerprints)) != len(self.fingerprints):
            raise ValidationError("observation fingerprints must be unique")
        if len(set(self.batch_tags)) != len(self.batch_tags):
            raise ValidationError("observation batch tags must be unique")


@dataclass(frozen=True, slots=True, kw_only=True)
class ObservationDecision:
    """Pure action and next bounded dedupe state for one metadata item."""

    action: ObservationAction
    reason: ObservationReason
    fingerprint: str | None = None
    next_fingerprints: tuple[str, ...] = ()
    next_batch_tags: tuple[str, ...] = ()
    tool_category: ToolCategory | None = None
    intervention_class: InterventionClass | None = None

    @property
    def eligible(self) -> bool:
        return self.action is ObservationAction.INJECT

    @property
    def should_record(self) -> bool:
        """An eligible decision records only the content-free check request."""

        return self.eligible

    @property
    def dedupe_fingerprint(self) -> str | None:
        """Compatibility name for the recordable safe fingerprint."""

        return self.fingerprint

    @property
    def is_empty(self) -> bool:
        return self.action is ObservationAction.EMPTY


def _coerce_enum(value: object, enum_type: type[StrEnum], name: str) -> StrEnum:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"observation {name} is not a closed value") from error


def _validate_tag(value: object, name: str) -> str:
    try:
        return validate_sha256(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{name} must be a sha256 HMAC tag") from error


def _coerce_metadata(metadata: ObservationMetadata) -> ObservationMetadata:
    if not isinstance(metadata, ObservationMetadata):
        raise ValidationError("observation policy requires ObservationMetadata")
    return metadata


def dedupe_fingerprint(
    metadata: ObservationMetadata,
    *,
    intervention_class: InterventionClass = InterventionClass.WEAK_EVIDENCE,
) -> str:
    """Derive a deterministic fingerprint from safe identifiers only.

    The digest never sees raw input/output, a tool name, command, path, source,
    or prompt.  A bounded window and batch tag make repeated mechanical hook
    delivery idempotent while the HMAC tool-use key keeps distinct tool uses
    distinguishable when the host exposes them.
    """

    metadata = _coerce_metadata(metadata)
    if not isinstance(intervention_class, InterventionClass):
        raise ValidationError("observation intervention class is not closed")
    components = (
        "opensocrates-observation/1",
        metadata.active_task_tag,
        metadata.window_tag,
        metadata.batch_tag or "-",
        metadata.subject_tag,
        intervention_class.value,
        metadata.tool_category.value,  # type: ignore[union-attr]  # Closed runtime boundary validates this value.
        metadata.tool_use_key,
        *metadata.claim_version_tags,
    )
    digest = sha256("\x1f".join(components).encode("ascii")).hexdigest()
    return f"sha256:{digest}"


def _empty(
    reason: ObservationReason,
    metadata: ObservationMetadata,
    *,
    intervention_class: InterventionClass,
    fingerprint: str | None = None,
) -> ObservationDecision:
    return ObservationDecision(
        action=ObservationAction.EMPTY,
        reason=reason,
        fingerprint=fingerprint,
        tool_category=metadata.tool_category,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        intervention_class=intervention_class,
    )


def assess_observation(  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    metadata: ObservationMetadata,
    task: TaskProjection | None,
    *,
    dedupe_state: ObservationDedupeState | None = None,
    seen_fingerprints: Iterable[str] = (),
    seen_batch_tags: Iterable[str] = (),
    active_task_tag: str | None = None,
    intervention_class: InterventionClass = InterventionClass.WEAK_EVIDENCE,
) -> ObservationDecision:
    """Return the closed eligibility/dedupe decision for one observation.

    The function is total for valid typed inputs and never mutates caller
    state.  All non-eligible paths return an empty action and no recordable
    content.  ``seen_fingerprints`` and ``seen_batch_tags`` are accepted as an
    integration convenience; ``ObservationDedupeState`` is preferred when the
    caller already has a typed projection.
    """

    metadata = _coerce_metadata(metadata)
    if not isinstance(intervention_class, InterventionClass):
        raise ValidationError("observation intervention class is not closed")
    if dedupe_state is not None:
        if not isinstance(dedupe_state, ObservationDedupeState):
            raise ValidationError("observation dedupe_state must be ObservationDedupeState")
        fingerprints = dedupe_state.fingerprints
        batch_tags = dedupe_state.batch_tags
    else:
        fingerprints = tuple(seen_fingerprints)
        batch_tags = tuple(seen_batch_tags)
        if len(fingerprints) > MAX_OBSERVATION_TAGS or len(batch_tags) > MAX_OBSERVATION_TAGS:
            return _empty(
                ObservationReason.DEDUPE_CAPACITY_EXHAUSTED,
                metadata,
                intervention_class=intervention_class,
            )
        for tag in (*fingerprints, *batch_tags):
            _validate_tag(tag, "observation dedupe tag")
        if len(set(fingerprints)) != len(fingerprints) or len(set(batch_tags)) != len(batch_tags):
            raise ValidationError("observation dedupe tags must be unique")

    if task is None:
        return _empty(
            ObservationReason.NO_ACTIVE_TASK,
            metadata,
            intervention_class=intervention_class,
        )
    if not isinstance(task, TaskProjection):
        raise ValidationError("observation task must be TaskProjection or null")
    if not metadata.recording_eligible:
        return _empty(
            ObservationReason.RECORDING_OFF,
            metadata,
            intervention_class=intervention_class,
        )
    if active_task_tag is not None:
        _validate_tag(active_task_tag, "active_task_tag")
        if metadata.active_task_tag != active_task_tag:
            return _empty(
                ObservationReason.TASK_TAG_MISMATCH,
                metadata,
                intervention_class=intervention_class,
            )
    if task.state not in _ACTIVE_TASK_STATES:
        return _empty(
            ObservationReason.TASK_NOT_ACTIVE,
            metadata,
            intervention_class=intervention_class,
        )
    if task.current_judgment_id is None:
        return _empty(
            ObservationReason.NO_CURRENT_JUDGMENT,
            metadata,
            intervention_class=intervention_class,
        )

    category = metadata.tool_category
    if category in _MECHANICAL_TOOL_CATEGORIES:
        return _empty(
            ObservationReason.MECHANICAL_CATEGORY,
            metadata,
            intervention_class=intervention_class,
        )
    failed_execution = (
        category is ToolCategory.EXECUTION and metadata.result_status is ObservationStatus.FAILED
    )
    if category not in _EVIDENCE_TOOL_CATEGORIES and not failed_execution:
        return _empty(
            ObservationReason.INELIGIBLE_CATEGORY,
            metadata,
            intervention_class=intervention_class,
        )
    if metadata.result_status is ObservationStatus.EMPTY:
        return _empty(
            ObservationReason.EMPTY_RESULT,
            metadata,
            intervention_class=intervention_class,
        )
    if metadata.result_status is ObservationStatus.UNAVAILABLE:
        return _empty(
            ObservationReason.UNAVAILABLE_RESULT,
            metadata,
            intervention_class=intervention_class,
        )
    # A failed evidence-bearing operation can itself invalidate a plan/source
    # set even when no result bytes were produced.  Successful empty results
    # remain ineligible; failure status is the explicit exception.
    if (
        metadata.result_size_bucket is ResultSizeBucket.EMPTY
        and metadata.result_status is not ObservationStatus.FAILED
    ):
        return _empty(
            ObservationReason.EMPTY_RESULT,
            metadata,
            intervention_class=intervention_class,
        )

    fingerprint = dedupe_fingerprint(metadata, intervention_class=intervention_class)
    if fingerprint in fingerprints:
        return _empty(
            ObservationReason.DUPLICATE,
            metadata,
            intervention_class=intervention_class,
            fingerprint=fingerprint,
        )
    if metadata.batch_tag is not None and metadata.batch_tag in batch_tags:
        return _empty(
            ObservationReason.BATCH_DUPLICATE,
            metadata,
            intervention_class=intervention_class,
            fingerprint=fingerprint,
        )
    if len(fingerprints) >= MAX_OBSERVATION_TAGS or (
        metadata.batch_tag is not None and len(batch_tags) >= MAX_OBSERVATION_TAGS
    ):
        return _empty(
            ObservationReason.DEDUPE_CAPACITY_EXHAUSTED,
            metadata,
            intervention_class=intervention_class,
            fingerprint=fingerprint,
        )

    next_fingerprints = (*fingerprints, fingerprint)
    next_batch_tags = batch_tags
    if metadata.batch_tag is not None:
        next_batch_tags = (*batch_tags, metadata.batch_tag)
    return ObservationDecision(
        action=ObservationAction.INJECT,
        reason=ObservationReason.ELIGIBLE,
        fingerprint=fingerprint,
        next_fingerprints=next_fingerprints,
        next_batch_tags=next_batch_tags,
        tool_category=category,  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        intervention_class=intervention_class,
    )


def is_observation_eligible(
    metadata: ObservationMetadata,
    task: TaskProjection | None,
    *,
    dedupe_state: ObservationDedupeState | None = None,
) -> bool:
    """Return only the eligibility bit for callers that do not need details."""

    return assess_observation(metadata, task, dedupe_state=dedupe_state).eligible


# Compatibility names used by application integrations and focused checks.
NormalizedObservation = ObservationMetadata
ObservationInput = ObservationMetadata
ObservationEligibility = ObservationDecision
evaluate_observation = assess_observation
decide_observation = assess_observation
observation_eligibility = assess_observation
validate_observation = _coerce_metadata


__all__ = [
    "NormalizedObservation",
    "ObservationAction",
    "ObservationDecision",
    "ObservationDedupeState",
    "ObservationEligibility",
    "ObservationInput",
    "ObservationMetadata",
    "ObservationReason",
    "ObservationStatus",
    "ResultSizeBucket",
    "assess_observation",
    "decide_observation",
    "dedupe_fingerprint",
    "evaluate_observation",
    "is_observation_eligible",
    "observation_eligibility",
    "validate_observation",
]
