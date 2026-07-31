"""Closed, public-only judgment record events.

The event union is deliberately explicit.  There is no generic event or raw
dictionary append surface: persistence receives a :class:`RecordEvent` whose
payload class fixes the allowed fields for its discriminator.
"""

from __future__ import annotations

import dataclasses
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Protocol, TypeVar

from opensocrates.constants import MAX_RECORD_EVENT_BYTES
from opensocrates.domain.enums import (
    ConflictResolution,
    HostId,
    InterventionClass,
    MethodActivationSource,
    RecordEventType,
    Rigor,
    TaskTerminalReason,
    ToolCategory,
)
from opensocrates.domain.models import (
    Alternative,
    ClaimVersion,
    CompletionResult,
    Conflict,
    Framing,
    JudgmentEvent,
    JudgmentVersion,
    SourceReference,
)
from opensocrates.domain.validation import model_from_dict, validate_model
from opensocrates.errors import OpenSocratesError
from opensocrates.ids import (
    new_event_id,
    validate_event_id,
    validate_local_id,
    validate_method_id,
    validate_semver,
    validate_sha256,
    validate_task_id,
    validate_timestamp,
)

SCHEMA = "opensocrates.judgment-event/1.0.0"
_EVENT_KEYS = frozenset(
    {
        "schema",
        "event_id",
        "task_id",
        "sequence",
        "event_type",
        "occurred_at",
        "host",
        "host_version",
        "adapter_version",
        "locale",
        "payload",
    }
)


class RecordEventError(ValueError):
    """Raised when a record event is malformed or violates its closed union."""


class RecordPayload(Protocol):
    """Protocol implemented by every closed payload class."""

    event_type: ClassVar[RecordEventType]
    allowed_fields: ClassVar[frozenset[str]]

    def public_fields(self) -> Mapping[str, object]:
        """Return only the payload fields allowed for this event type."""


def _enum_value(value: object, enum_type: type[Enum], name: str) -> str:
    try:
        member = value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as error:
        raise RecordEventError(f"invalid {name}") from error
    return str(member.value)


def _text(value: object, name: str, *, max_length: int = 2200) -> str:
    if not isinstance(value, str):
        raise RecordEventError(f"invalid {name}")
    if len(value) > max_length or "\x00" in value:
        raise RecordEventError(f"invalid {name}")
    if unicodedata.normalize("NFC", value) != value:
        raise RecordEventError(f"invalid {name}")
    if any(ord(character) < 0x20 and character not in "\n\t" for character in value):
        raise RecordEventError(f"invalid {name}")
    return value


def _tuple_text(
    values: object, name: str, *, max_items: int = 8, max_length: int = 2200
) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)) or len(values) > max_items:
        raise RecordEventError(f"invalid {name}")
    return tuple(_text(item, name, max_length=max_length) for item in values)


def _model_value(value: object, *, depth: int = 0) -> object:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    """Convert a typed public model to a JSON-compatible value."""

    if depth > 12:
        raise RecordEventError("public model is too deeply nested")
    if isinstance(value, Enum):
        return value.value
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RecordEventError("public model contains a non-finite number")
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _model_value(getattr(value, item.name), depth=depth + 1)
            for item in dataclasses.fields(value)
        }
    if isinstance(value, Mapping):
        converted: dict[str, object] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise RecordEventError("public model contains a non-string key")
            converted[key] = _model_value(child, depth=depth + 1)
        return converted
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_model_value(child, depth=depth + 1) for child in value]
    raise RecordEventError("unsupported public model value")


def _model_field(name: str, value: object) -> Mapping[str, object]:
    return {name: _model_value(value)}


@dataclass(frozen=True, slots=True)
class TaskStartedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.TASK_STARTED
    allowed_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "requested_rigor",
            "effective_rigor",
            "capability_gaps",
            "participation_reason",
            "host_session_key",
        }
    )
    requested_rigor: Rigor | str
    effective_rigor: Rigor | str
    capability_gaps: tuple[str, ...] = ()
    participation_reason: str = ""
    host_session_key: str = "sha256:" + ("0" * 64)

    def __post_init__(self) -> None:
        _enum_value(self.requested_rigor, Rigor, "requested_rigor")
        _enum_value(self.effective_rigor, Rigor, "effective_rigor")
        gaps = _tuple_text(self.capability_gaps, "capability_gaps", max_items=8, max_length=128)
        if tuple(sorted(set(gaps))) != gaps:
            raise RecordEventError("capability_gaps must be sorted and unique")
        _text(self.participation_reason, "participation_reason", max_length=128)
        try:
            validate_sha256(self.host_session_key)
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid host_session_key") from error

    def public_fields(self) -> Mapping[str, object]:
        return {
            "requested_rigor": _enum_value(self.requested_rigor, Rigor, "requested_rigor"),
            "effective_rigor": _enum_value(self.effective_rigor, Rigor, "effective_rigor"),
            "capability_gaps": list(self.capability_gaps),
            "participation_reason": self.participation_reason,
            "host_session_key": self.host_session_key,
        }


@dataclass(frozen=True, slots=True)
class ModelRecordPayload:
    """Payload for one allowlisted public domain model field."""

    event_type: ClassVar[RecordEventType]
    allowed_fields: ClassVar[frozenset[str]]
    field_name: ClassVar[str]
    model_type: ClassVar[type[Any] | None] = None
    value: object

    def __post_init__(self) -> None:
        if self.model_type is None or not isinstance(self.value, self.model_type):
            raise RecordEventError(f"{self.field_name} payload is not its closed domain model")
        try:
            validate_model(self.value)
        except (OpenSocratesError, TypeError, ValueError) as error:
            raise RecordEventError(f"{self.field_name} payload is invalid") from error

    def public_fields(self) -> Mapping[str, object]:
        return _model_field(self.field_name, self.value)


@dataclass(frozen=True, slots=True)
class FramingPublishedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.FRAMING_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"framing"})
    field_name: ClassVar[str] = "framing"
    model_type: ClassVar[type[Any]] = Framing


@dataclass(frozen=True, slots=True)
class ClaimPublishedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.CLAIM_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"claim_version"})
    field_name: ClassVar[str] = "claim_version"
    model_type: ClassVar[type[Any]] = ClaimVersion


@dataclass(frozen=True, slots=True)
class SourcePublishedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.SOURCE_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"source_reference"})
    field_name: ClassVar[str] = "source_reference"
    model_type: ClassVar[type[Any]] = SourceReference


@dataclass(frozen=True, slots=True)
class ConflictPublishedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.CONFLICT_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"conflict", "affected_claim_ids"})
    field_name: ClassVar[str] = "conflict"
    model_type: ClassVar[type[Any]] = Conflict
    affected_claim_ids: tuple[str, ...] = ()

    def public_fields(self) -> Mapping[str, object]:
        fields = dict(_model_field(self.field_name, self.value))
        claim_ids = _tuple_text(
            self.affected_claim_ids, "affected_claim_ids", max_items=5, max_length=32
        )
        for claim_id in claim_ids:
            try:
                validate_local_id(claim_id, "C")
            except (OpenSocratesError, ValueError) as error:
                raise RecordEventError("invalid affected claim id") from error
        fields["affected_claim_ids"] = list(claim_ids)
        return fields


@dataclass(frozen=True, slots=True)
class AlternativePublishedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.ALTERNATIVE_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"alternative"})
    field_name: ClassVar[str] = "alternative"
    model_type: ClassVar[type[Any]] = Alternative


@dataclass(frozen=True, slots=True)
class ConclusionPublishedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.CONCLUSION_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"judgment_version"})
    field_name: ClassVar[str] = "judgment_version"
    model_type: ClassVar[type[Any]] = JudgmentVersion


@dataclass(frozen=True, slots=True)
class CompletionCheckedPayload(ModelRecordPayload):
    event_type: ClassVar[RecordEventType] = RecordEventType.COMPLETION_CHECKED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"completion_result"})
    field_name: ClassVar[str] = "completion_result"
    model_type: ClassVar[type[Any]] = CompletionResult


@dataclass(frozen=True, slots=True)
class MethodSelectedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.METHOD_SELECTED
    allowed_fields: ClassVar[frozenset[str]] = frozenset(
        {"primary_method", "secondary_method", "selection_source"}
    )
    primary_method: str
    secondary_method: str | None
    selection_source: str

    def __post_init__(self) -> None:
        try:
            validate_method_id(self.primary_method)
            if self.secondary_method is not None:
                validate_method_id(self.secondary_method)
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid selected method") from error
        if self.secondary_method == self.primary_method:
            raise RecordEventError("primary and secondary method must differ")
        _text(self.selection_source, "selection_source", max_length=64)

    def public_fields(self) -> Mapping[str, object]:
        return {
            "primary_method": self.primary_method,
            "secondary_method": self.secondary_method,
            "selection_source": self.selection_source,
        }


@dataclass(frozen=True, slots=True)
class MethodActivatedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.METHOD_ACTIVATED
    allowed_fields: ClassVar[frozenset[str]] = frozenset(
        {"method_id", "activation_source", "turn_tag"}
    )
    method_id: str
    activation_source: MethodActivationSource | str
    turn_tag: str

    def __post_init__(self) -> None:
        try:
            validate_method_id(self.method_id)
            validate_sha256(self.turn_tag)
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid method activation") from error
        _enum_value(self.activation_source, MethodActivationSource, "activation_source")

    def public_fields(self) -> Mapping[str, object]:
        return {
            "method_id": self.method_id,
            "activation_source": _enum_value(
                self.activation_source, MethodActivationSource, "activation_source"
            ),
            "turn_tag": self.turn_tag,
        }


@dataclass(frozen=True, slots=True)
class JudgmentStartedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.JUDGMENT_STARTED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"judgment_id", "version"})
    judgment_id: str
    version: int = 1

    def __post_init__(self) -> None:
        try:
            validate_local_id(self.judgment_id, "J")
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid judgment id") from error
        if self.version < 1:
            raise RecordEventError("judgment version must be positive")

    def public_fields(self) -> Mapping[str, object]:
        return {"judgment_id": self.judgment_id, "version": self.version}


@dataclass(frozen=True, slots=True)
class ObservationCheckRequestedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.OBSERVATION_CHECK_REQUESTED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"tool_category", "dedupe_fingerprint"})
    tool_category: ToolCategory | str
    dedupe_fingerprint: str

    def __post_init__(self) -> None:
        _enum_value(self.tool_category, ToolCategory, "tool_category")
        try:
            validate_sha256(self.dedupe_fingerprint)
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid observation fingerprint") from error

    def public_fields(self) -> Mapping[str, object]:
        return {
            "tool_category": _enum_value(self.tool_category, ToolCategory, "tool_category"),
            "dedupe_fingerprint": self.dedupe_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class InterventionPublishedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.INTERVENTION_PUBLISHED
    allowed_fields: ClassVar[frozenset[str]] = frozenset(
        {"class", "summary", "action", "fingerprint"}
    )
    intervention_class: InterventionClass | str
    summary: str
    action: str
    fingerprint: str

    def __post_init__(self) -> None:
        _enum_value(self.intervention_class, InterventionClass, "intervention class")
        _text(self.summary, "summary", max_length=500)
        _text(self.action, "action", max_length=128)
        try:
            validate_sha256(self.fingerprint)
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid intervention fingerprint") from error

    def public_fields(self) -> Mapping[str, object]:
        return {
            "class": _enum_value(self.intervention_class, InterventionClass, "intervention class"),
            "summary": self.summary,
            "action": self.action,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class ConflictResolvedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.CONFLICT_RESOLVED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"resolution", "public_reason"})
    resolution: ConflictResolution | str
    public_reason: str

    def __post_init__(self) -> None:
        _enum_value(self.resolution, ConflictResolution, "resolution")
        _text(self.public_reason, "public_reason", max_length=500)

    def public_fields(self) -> Mapping[str, object]:
        return {
            "resolution": _enum_value(self.resolution, ConflictResolution, "resolution"),
            "public_reason": self.public_reason,
        }


@dataclass(frozen=True, slots=True)
class CrossExamCompletedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.CROSS_EXAM_COMPLETED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"findings_summary", "affected_ids"})
    findings_summary: str
    affected_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.findings_summary, "findings_summary", max_length=1000)
        _tuple_text(self.affected_ids, "affected_ids", max_items=12, max_length=32)

    def public_fields(self) -> Mapping[str, object]:
        return {"findings_summary": self.findings_summary, "affected_ids": list(self.affected_ids)}


@dataclass(frozen=True, slots=True)
class RepairRequestedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.REPAIR_REQUESTED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"rule_ids", "repair_count"})
    rule_ids: tuple[str, ...]
    repair_count: int = 1

    def __post_init__(self) -> None:
        rules = _tuple_text(self.rule_ids, "rule_ids", max_items=16, max_length=64)
        if not rules or tuple(sorted(set(rules))) != rules:
            raise RecordEventError("rule_ids must be sorted and non-empty")
        if self.repair_count != 1:
            raise RecordEventError("v1 permits exactly one repair")

    def public_fields(self) -> Mapping[str, object]:
        return {"rule_ids": list(self.rule_ids), "repair_count": self.repair_count}


@dataclass(frozen=True, slots=True)
class VerificationFailedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.VERIFICATION_FAILED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"rule_ids", "reason"})
    rule_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _tuple_text(self.rule_ids, "rule_ids", max_items=16, max_length=64)
        _text(self.reason, "reason", max_length=500)

    def public_fields(self) -> Mapping[str, object]:
        return {"rule_ids": list(self.rule_ids), "reason": self.reason}


@dataclass(frozen=True, slots=True)
class CapabilityDegradedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.CAPABILITY_DEGRADED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"capability_key", "limitation_key"})
    capability_key: str
    limitation_key: str

    def __post_init__(self) -> None:
        _text(self.capability_key, "capability_key", max_length=128)
        _text(self.limitation_key, "limitation_key", max_length=128)

    def public_fields(self) -> Mapping[str, object]:
        return {"capability_key": self.capability_key, "limitation_key": self.limitation_key}


@dataclass(frozen=True, slots=True)
class TaskConcludedPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.TASK_CONCLUDED
    allowed_fields: ClassVar[frozenset[str]] = frozenset(
        {"terminal_reason", "current_judgment_version"}
    )
    terminal_reason: TaskTerminalReason | str
    current_judgment_version: int | None = None

    def __post_init__(self) -> None:
        _enum_value(self.terminal_reason, TaskTerminalReason, "terminal_reason")
        if self.current_judgment_version is not None and self.current_judgment_version < 1:
            raise RecordEventError("current judgment version must be positive")

    def public_fields(self) -> Mapping[str, object]:
        return {
            "terminal_reason": _enum_value(
                self.terminal_reason, TaskTerminalReason, "terminal_reason"
            ),
            "current_judgment_version": self.current_judgment_version,
        }


@dataclass(frozen=True, slots=True)
class TaskInsufficientPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.TASK_INSUFFICIENT
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"terminal_reason", "missing_items"})
    terminal_reason: TaskTerminalReason | str
    missing_items: tuple[str, ...]

    def __post_init__(self) -> None:
        _enum_value(self.terminal_reason, TaskTerminalReason, "terminal_reason")
        if not self.missing_items:
            raise RecordEventError("missing_items must not be empty")
        _tuple_text(self.missing_items, "missing_items", max_items=5, max_length=500)

    def public_fields(self) -> Mapping[str, object]:
        return {
            "terminal_reason": _enum_value(
                self.terminal_reason, TaskTerminalReason, "terminal_reason"
            ),
            "missing_items": list(self.missing_items),
        }


@dataclass(frozen=True, slots=True)
class TaskCancelledPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.TASK_CANCELLED
    allowed_fields: ClassVar[frozenset[str]] = frozenset({"reason"})
    reason: str = "user_cancelled"

    def __post_init__(self) -> None:
        if self.reason != "user_cancelled":
            raise RecordEventError("task cancellation reason is closed")

    def public_fields(self) -> Mapping[str, object]:
        return {"reason": self.reason}


@dataclass(frozen=True, slots=True)
class RecoveredFromTornTailPayload:
    event_type: ClassVar[RecordEventType] = RecordEventType.RECOVERED_FROM_TORN_TAIL
    allowed_fields: ClassVar[frozenset[str]] = frozenset(
        {"source_record_safe_identifier", "complete_line_count"}
    )
    source_record_safe_identifier: str
    complete_line_count: int

    def __post_init__(self) -> None:
        _text(self.source_record_safe_identifier, "source_record_safe_identifier", max_length=128)
        if self.complete_line_count < 0:
            raise RecordEventError("complete_line_count must be non-negative")

    def public_fields(self) -> Mapping[str, object]:
        return {
            "source_record_safe_identifier": self.source_record_safe_identifier,
            "complete_line_count": self.complete_line_count,
        }


_PAYLOAD_TYPES: dict[RecordEventType, type[RecordPayload]] = {
    payload.event_type: payload
    for payload in (
        TaskStartedPayload,
        FramingPublishedPayload,
        MethodSelectedPayload,
        MethodActivatedPayload,
        JudgmentStartedPayload,
        ObservationCheckRequestedPayload,
        InterventionPublishedPayload,
        ClaimPublishedPayload,
        SourcePublishedPayload,
        ConflictPublishedPayload,
        ConflictResolvedPayload,
        AlternativePublishedPayload,
        ConclusionPublishedPayload,
        CrossExamCompletedPayload,
        CompletionCheckedPayload,
        RepairRequestedPayload,
        VerificationFailedPayload,
        CapabilityDegradedPayload,
        TaskConcludedPayload,
        TaskInsufficientPayload,
        TaskCancelledPayload,
        RecoveredFromTornTailPayload,
    )
}


def _payload_value(payload: RecordPayload) -> Mapping[str, object]:
    fields = payload.public_fields()
    if not isinstance(fields, Mapping):
        raise RecordEventError("payload did not expose public fields")
    if frozenset(fields) != payload.allowed_fields:
        raise RecordEventError("payload fields do not match its closed allowlist")
    return fields


@dataclass(frozen=True, slots=True)
class RecordEvent:
    """One immutable, typed, append-only public judgment event."""

    event_id: str
    task_id: str
    sequence: int
    event_type: RecordEventType
    occurred_at: str
    host: HostId | str
    host_version: str
    adapter_version: str
    locale: str
    payload: RecordPayload
    schema: str = SCHEMA

    def __post_init__(self) -> None:
        if self.schema != SCHEMA:
            raise RecordEventError("unknown record event schema")
        if not isinstance(self.event_type, RecordEventType):
            raise RecordEventError("record event type is closed")
        try:
            validate_event_id(self.event_id)
            validate_task_id(self.task_id)
            validate_timestamp(self.occurred_at)
            validate_semver(self.adapter_version)
        except (OpenSocratesError, ValueError) as error:
            raise RecordEventError("invalid record event envelope") from error
        if (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 1
        ):
            raise RecordEventError("record event sequence must start at one")
        try:
            normalized_host = HostId(self.host)
        except (TypeError, ValueError) as error:
            raise RecordEventError("invalid record host") from error
        object.__setattr__(self, "host", normalized_host)
        if not isinstance(self.locale, str) or self.locale not in {"en", "ko"}:
            raise RecordEventError("record locale is closed")
        _text(self.host_version, "host_version", max_length=64)
        if not isinstance(self.payload, tuple(_PAYLOAD_TYPES.values())):
            raise RecordEventError("payload class does not belong to the closed event union")
        if self.payload.event_type is not self.event_type:
            raise RecordEventError("event discriminator and payload type differ")
        _payload_value(self.payload)

    @classmethod
    def new(
        cls,
        *,
        task_id: str,
        sequence: int,
        event_type: RecordEventType,
        payload: RecordPayload,
        occurred_at: str,
        host: HostId | str,
        host_version: str,
        adapter_version: str = "1.0.0",
        locale: str = "en",
    ) -> "RecordEvent":
        return cls(
            event_id=new_event_id(),
            task_id=task_id,
            sequence=sequence,
            event_type=event_type,
            occurred_at=occurred_at,
            host=host,
            host_version=host_version,
            adapter_version=adapter_version,
            locale=locale,
            payload=payload,
        )

    def to_judgment_event(self) -> JudgmentEvent:
        """Adapt this closed event to S01's generic, domain-owned envelope.

        The adapter deliberately keeps the generic ``payload`` shape at the
        S01 boundary.  Callers must still pass this typed event through the
        persistence serializer, where forbidden-key and secret filtering is
        applied before bytes are written.
        """

        return JudgmentEvent(
            schema=self.schema,
            event_id=self.event_id,
            task_id=self.task_id,
            sequence=self.sequence,
            event_type=self.event_type,
            occurred_at=self.occurred_at,
            host=HostId(self.host),
            host_version=self.host_version,
            adapter_version=self.adapter_version,
            locale=self.locale,
            payload=dict(_payload_value(self.payload)),
        )

    @classmethod
    def from_judgment_event(cls, event: JudgmentEvent) -> "RecordEvent":
        """Validate and close an S01 envelope before persistence."""

        if not isinstance(event, JudgmentEvent):
            raise RecordEventError("expected a JudgmentEvent")
        try:
            payload = _decode_payload(event.event_type, event.payload)
            return cls(
                schema=event.schema,
                event_id=event.event_id,
                task_id=event.task_id,
                sequence=event.sequence,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                host=event.host,
                host_version=event.host_version,
                adapter_version=event.adapter_version,
                locale=event.locale,
                payload=payload,
            )
        except RecordEventError:
            raise
        except (OpenSocratesError, TypeError, ValueError, KeyError) as error:
            raise RecordEventError("invalid JudgmentEvent envelope") from error

    def to_json_value(self) -> Mapping[str, object]:
        """Return the canonical event object for the JSON serializer."""

        return {
            "schema": self.schema,
            "event_id": self.event_id,
            "task_id": self.task_id,
            "sequence": self.sequence,
            "event_type": self.event_type.value,
            "occurred_at": self.occurred_at,
            "host": HostId(self.host).value,
            "host_version": self.host_version,
            "adapter_version": self.adapter_version,
            "locale": self.locale,
            "payload": dict(_payload_value(self.payload)),
        }

    @classmethod
    def from_json_bytes(cls, data: bytes) -> "RecordEvent":
        if len(data) > MAX_RECORD_EVENT_BYTES:
            raise RecordEventError("record event exceeds 64 KiB")
        if not data.endswith(b"\n"):
            raise RecordEventError("record event must end with LF")
        try:
            raw = json.loads(data[:-1].decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RecordEventError("record event is not valid JSON") from error
        return cls._from_json_value(raw)

    @classmethod
    def _from_json_value(cls, raw: object) -> "RecordEvent":
        if not isinstance(raw, Mapping):
            raise RecordEventError("record event must be a JSON object")
        if frozenset(raw) != _EVENT_KEYS:
            raise RecordEventError("record event envelope fields are not closed")
        try:
            event_type = RecordEventType(raw["event_type"])
            payload_raw = raw["payload"]
        except (OpenSocratesError, KeyError, TypeError, ValueError) as error:
            raise RecordEventError("record event discriminator is invalid") from error
        if not isinstance(payload_raw, Mapping):
            raise RecordEventError("record event payload must be an object")
        payload = _decode_payload(event_type, payload_raw)
        try:
            return cls(
                event_id=raw["event_id"],
                task_id=raw["task_id"],
                sequence=raw["sequence"],
                event_type=event_type,
                occurred_at=raw["occurred_at"],
                host=raw["host"],
                host_version=raw["host_version"],
                adapter_version=raw["adapter_version"],
                locale=raw["locale"],
                payload=payload,
                schema=raw["schema"],
            )
        except KeyError as error:
            raise RecordEventError("record event envelope is incomplete") from error


def _decode_payload(event_type: RecordEventType, raw: Mapping[str, object]) -> RecordPayload:  # noqa: C901  # Branch-explicit contract; reviewed for v1.0.
    payload_type = _PAYLOAD_TYPES.get(event_type)
    if payload_type is None or frozenset(raw) != payload_type.allowed_fields:
        raise RecordEventError("payload fields are not closed for this event type")
    try:
        if payload_type is TaskStartedPayload:
            if not isinstance(raw["capability_gaps"], (list, tuple)):
                raise RecordEventError("capability_gaps must be an array")
            return TaskStartedPayload(
                requested_rigor=raw["requested_rigor"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                effective_rigor=raw["effective_rigor"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                capability_gaps=tuple(raw["capability_gaps"]),
                participation_reason=raw["participation_reason"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                host_session_key=raw["host_session_key"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            )
        if issubclass(payload_type, ModelRecordPayload):
            field_name = payload_type.field_name
            extras = {key: value for key, value in raw.items() if key != field_name}
            if extras:
                if payload_type is ConflictPublishedPayload and set(extras) == {
                    "affected_claim_ids"
                }:
                    return ConflictPublishedPayload(
                        value=_decode_model_value(payload_type, raw[field_name]),
                        affected_claim_ids=tuple(raw["affected_claim_ids"]),  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                    )
                raise RecordEventError("model payload has unknown fields")
            return payload_type(value=_decode_model_value(payload_type, raw[field_name]))
        if payload_type is MethodSelectedPayload:
            return MethodSelectedPayload(
                raw["primary_method"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["secondary_method"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["selection_source"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            )
        if payload_type is MethodActivatedPayload:
            return MethodActivatedPayload(
                raw["method_id"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["activation_source"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["turn_tag"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            )
        if payload_type is JudgmentStartedPayload:
            return JudgmentStartedPayload(raw["judgment_id"], raw["version"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is ObservationCheckRequestedPayload:
            return ObservationCheckRequestedPayload(raw["tool_category"], raw["dedupe_fingerprint"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is InterventionPublishedPayload:
            return InterventionPublishedPayload(
                raw["class"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["summary"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["action"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["fingerprint"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            )
        if payload_type is ConflictResolvedPayload:
            return ConflictResolvedPayload(raw["resolution"], raw["public_reason"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is CrossExamCompletedPayload:
            if not isinstance(raw["affected_ids"], (list, tuple)):
                raise RecordEventError("affected_ids must be an array")
            return CrossExamCompletedPayload(raw["findings_summary"], tuple(raw["affected_ids"]))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is RepairRequestedPayload:
            if not isinstance(raw["rule_ids"], (list, tuple)):
                raise RecordEventError("rule_ids must be an array")
            return RepairRequestedPayload(tuple(raw["rule_ids"]), raw["repair_count"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is VerificationFailedPayload:
            if not isinstance(raw["rule_ids"], (list, tuple)):
                raise RecordEventError("rule_ids must be an array")
            return VerificationFailedPayload(tuple(raw["rule_ids"]), raw["reason"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is CapabilityDegradedPayload:
            return CapabilityDegradedPayload(raw["capability_key"], raw["limitation_key"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is TaskConcludedPayload:
            return TaskConcludedPayload(raw["terminal_reason"], raw["current_judgment_version"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is TaskInsufficientPayload:
            if not isinstance(raw["missing_items"], (list, tuple)):
                raise RecordEventError("missing_items must be an array")
            return TaskInsufficientPayload(raw["terminal_reason"], tuple(raw["missing_items"]))  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is TaskCancelledPayload:
            return TaskCancelledPayload(raw["reason"])  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
        if payload_type is RecoveredFromTornTailPayload:
            return RecoveredFromTornTailPayload(
                raw["source_record_safe_identifier"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
                raw["complete_line_count"],  # type: ignore[arg-type]  # Closed runtime boundary validates this value.
            )
    except (OpenSocratesError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, RecordEventError):
            raise
        raise RecordEventError("invalid record payload") from error
    raise RecordEventError("unsupported record payload")


def _decode_model_value(payload_type: type[ModelRecordPayload], raw: object) -> object:
    model_type = payload_type.model_type
    if model_type is None or not isinstance(raw, Mapping):
        raise RecordEventError("model payload value is not a closed object")
    try:
        return model_from_dict(model_type, raw)
    except (OpenSocratesError, TypeError, ValueError) as error:
        raise RecordEventError("model payload value is invalid") from error


RecordPayloadType = TypeVar("RecordPayloadType", bound=RecordPayload)

__all__ = [
    "SCHEMA",
    "RecordEventError",
    "RecordPayload",
    "RecordEvent",
    "TaskStartedPayload",
    "FramingPublishedPayload",
    "MethodSelectedPayload",
    "MethodActivatedPayload",
    "JudgmentStartedPayload",
    "ObservationCheckRequestedPayload",
    "InterventionPublishedPayload",
    "ClaimPublishedPayload",
    "SourcePublishedPayload",
    "ConflictPublishedPayload",
    "ConflictResolvedPayload",
    "AlternativePublishedPayload",
    "ConclusionPublishedPayload",
    "CrossExamCompletedPayload",
    "CompletionCheckedPayload",
    "RepairRequestedPayload",
    "VerificationFailedPayload",
    "CapabilityDegradedPayload",
    "TaskConcludedPayload",
    "TaskInsufficientPayload",
    "TaskCancelledPayload",
    "RecoveredFromTornTailPayload",
]
