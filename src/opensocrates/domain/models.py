"""Frozen Python projections of the normative Document-04 contracts.

These models are host-neutral.  They contain no filesystem, environment,
network, or host-adapter behavior; schemas are generated from this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, ClassVar

from ..errors import ValidationError
from ..version import CONTENT_REVISION, PRODUCT_VERSION, ROUTER_VERSION, VERIFIER_VERSION
from .enums import (
    AlternativeDisposition,
    AnswerShape,
    CapabilityEvidenceKind,
    CapabilityStatus,
    CapabilityTier,
    ClaimMateriality,
    ClassificationConfidence,
    ConfidenceBasis,
    ConflictResolution,
    CriterionKind,
    CriterionStatus,
    DurationBucket,
    EventType,
    EvidenceState,
    FeatureBasis,
    FeatureKey,
    FeedbackOutcome,
    FlipDirection,
    HostControlErrorCode,
    HostControlMessageType,
    HostControlNextAction,
    HostControlReasonCode,
    HostControlStatus,
    HostId,
    JudgmentState,
    JudgmentStrength,
    MetricEventName,
    MetricsConsent,
    Participation,
    ParticipationReasonCode,
    RecordEventType,
    RecordingMode,
    Rigor,
    RiskFloorReason,
    RoundingMode,
    RouterReasonCode,
    SourceKind,
    TaskState,
    TaskTerminalReason,
    VerificationOutcome,
    ViolationSeverity,
)
from .validation import (
    AlternativeId,
    ClaimId,
    CriterionId,
    DecimalString,
    DurationMs,
    EventId,
    EvidenceId,
    FamilyId,
    FrozenModel,
    JudgmentId,
    Locale,
    MethodId,
    ReviewedProcedureText,
    SafeText,
    SemVer,
    Sha256,
    TaskId,
    TurnToken,
    sanitize_persistable_uri,
)


def _schema(value: str) -> Any:
    return dc_field(default=value, metadata={"schema_const": value, "required": True})


def _text(max_length: int = 4096, *, nullable: bool = False) -> Any:
    return dc_field(
        metadata={"scalar": "safe_text", "max_length": max_length, "nullable": nullable}
    )


def _optional_text(max_length: int = 4096) -> Any:
    return dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": max_length, "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityEntry(FrozenModel):
    status: CapabilityStatus
    evidence_kind: CapabilityEvidenceKind
    source_url: str | None = dc_field(default=None, metadata={"nullable": True})
    source_checked_at: str = dc_field(metadata={"scalar": "date"})
    live_probe_id: str | None = dc_field(default=None, metadata={"nullable": True})
    limitation_key: str | None = dc_field(default=None, metadata={"nullable": True})


@dataclass(frozen=True, slots=True, kw_only=True)
class CapabilityProfile(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.capability-profile/1.0.0"
    schema: str = _schema(__schema_id__)
    host: HostId
    host_version_range: str = _text(128)
    checked_at: str = dc_field(metadata={"scalar": "timestamp"})
    adapter_version: SemVer = dc_field(metadata={"scalar": "semver"})
    computed_tier: CapabilityTier
    capabilities: dict[str, CapabilityEntry]


@dataclass(frozen=True, slots=True, kw_only=True)
class FeedbackEntry(FrozenModel):
    sequence: int
    day: str = dc_field(metadata={"scalar": "date"})
    outcome: FeedbackOutcome


@dataclass(frozen=True, slots=True, kw_only=True)
class InterventionPreference(FrozenModel):
    next_sequence: int = 1
    recent_feedback: tuple[FeedbackEntry, ...] = ()
    reduced_since_sequence: int | None = dc_field(default=None, metadata={"nullable": True})
    reduced_until: str | None = dc_field(
        default=None, metadata={"scalar": "date", "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class UserSettings(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.user-settings/1.0.0"
    schema: str = _schema(__schema_id__)
    revision: int = 1
    default_rigor: Rigor = Rigor.TOGETHER
    locale_preference: Locale | None = dc_field(default=None, metadata={"nullable": True})
    recording_mode: RecordingMode = RecordingMode.OFF
    record_retention_days: int = 90
    record_size_limit_bytes: int = 100 * 1024 * 1024
    onboarding_version_seen: SemVer | None = dc_field(
        default=None, metadata={"scalar": "semver", "nullable": True}
    )
    intervention_preferences: dict[str, InterventionPreference] = dc_field(default_factory=dict)
    metrics_consent: MetricsConsent = MetricsConsent.NONE


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedEvent(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.normalized-event/1.0.0"
    schema: str = _schema(__schema_id__)
    event_id: EventId = dc_field(metadata={"scalar": "event_id"})
    event_type: EventType
    occurred_at: str = dc_field(metadata={"scalar": "timestamp"})
    host: HostId
    host_version: SafeText = _text(64)
    adapter_version: SemVer = dc_field(metadata={"scalar": "semver"})
    host_session_key: Sha256 = dc_field(metadata={"scalar": "sha256"})
    host_turn_key: Sha256 | None = dc_field(
        default=None, metadata={"scalar": "sha256", "nullable": True}
    )
    cwd_hint: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 1024, "nullable": True}
    )
    payload: dict[str, Any] = dc_field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class ParticipationDecision(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.participation-decision/1.0.0"
    schema: str = _schema(__schema_id__)
    participation: Participation
    reason_code: ParticipationReasonCode
    judgment_targets: tuple[SafeText, ...] = ()
    mechanical_targets: tuple[SafeText, ...] = ()
    confidence_basis: ConfidenceBasis = ConfidenceBasis.RULE_PLUS_MODEL_POLICY
    explicit_method: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RigorDecision(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.rigor-decision/1.0.0"
    schema: str = _schema(__schema_id__)
    stored_rigor: Rigor
    task_override: Rigor | None = dc_field(default=None, metadata={"nullable": True})
    risk_floor: Rigor
    risk_reason: RiskFloorReason
    effective_rigor: Rigor
    show_raise_notice: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class RoutingFeature(FrozenModel):
    key: FeatureKey
    strength: int
    basis: FeatureBasis


@dataclass(frozen=True, slots=True, kw_only=True)
class RoutingFeatures(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.routing-features/1.0.0"
    schema: str = _schema(__schema_id__)
    answer_shape: AnswerShape
    features: tuple[RoutingFeature, ...] = ()
    classification_confidence: ClassificationConfidence
    explicit_method: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class RouterDecision(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.router-decision/1.0.0"
    schema: str = _schema(__schema_id__)
    router_version: SemVer = dc_field(default=ROUTER_VERSION, metadata={"scalar": "semver"})
    answer_shape: AnswerShape
    primary_family: FamilyId | None = dc_field(default=None, metadata={"nullable": True})
    secondary_family: FamilyId | None = dc_field(default=None, metadata={"nullable": True})
    primary_method: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )
    secondary_method: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )
    explicit_invocation: bool = False
    reason_code: RouterReasonCode = RouterReasonCode.NO_ELIGIBLE_METHOD
    prompt_bundle_hash: Sha256 | None = dc_field(
        default=None, metadata={"scalar": "sha256", "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class AssignedIds(FrozenModel):
    task_id: TaskId | None = dc_field(
        default=None, metadata={"scalar": "task_id", "nullable": True}
    )
    judgment_id: JudgmentId | None = dc_field(
        default=None, metadata={"scalar": "local_id:J", "nullable": True}
    )
    claim_ids: tuple[ClaimId, ...] = ()
    source_ids: tuple[EvidenceId, ...] = ()
    criterion_ids: tuple[CriterionId, ...] = ()
    alternative_ids: tuple[AlternativeId, ...] = ()

    def has_any(self) -> bool:
        return any(
            (
                self.task_id,
                self.judgment_id,
                self.claim_ids,
                self.source_ids,
                self.criterion_ids,
                self.alternative_ids,
            )
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class HostControl(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.host-control/1.0.0"
    schema: str = _schema(__schema_id__)
    message_id: EventId = dc_field(metadata={"scalar": "event_id"})
    turn_token: TurnToken = dc_field(metadata={"scalar": "turn_token"})
    message_type: HostControlMessageType
    published: bool
    payload: dict[str, Any] = dc_field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class HostControlResult(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.host-control-result/1.0.0"
    schema: str = _schema(__schema_id__)
    message_id: EventId = dc_field(metadata={"scalar": "event_id"})
    status: HostControlStatus
    reason_code: HostControlReasonCode | None = dc_field(default=None, metadata={"nullable": True})
    durable_mutation: bool = False
    assigned_ids: AssignedIds = dc_field(default_factory=AssignedIds)
    effective_rigor: Rigor | None = dc_field(default=None, metadata={"nullable": True})
    route: RouterDecision | None = dc_field(default=None, metadata={"nullable": True})
    capability_limitations: tuple[str, ...] = ()
    next_action: HostControlNextAction = HostControlNextAction.CONTINUE
    error_code: HostControlErrorCode | None = dc_field(default=None, metadata={"nullable": True})


@dataclass(frozen=True, slots=True, kw_only=True)
class AcceptedControl(FrozenModel):
    message_id: EventId = dc_field(metadata={"scalar": "event_id"})
    payload_tag: Sha256 = dc_field(metadata={"scalar": "sha256"})
    result: HostControlResult


@dataclass(frozen=True, slots=True, kw_only=True)
class EphemeralTurnState(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.ephemeral-turn-state/1.0.0"
    schema: str = _schema(__schema_id__)
    token_tag: Sha256 = dc_field(metadata={"scalar": "sha256"})
    host_session_key: Sha256 = dc_field(metadata={"scalar": "sha256"})
    host_turn_key: Sha256 | None = dc_field(
        default=None, metadata={"scalar": "sha256", "nullable": True}
    )
    host: HostId
    issued_at: str = dc_field(metadata={"scalar": "timestamp"})
    expires_at: str = dc_field(metadata={"scalar": "timestamp"})
    recording_eligible: bool
    onboarding_disclosure_turn: bool
    task_id: TaskId | None = dc_field(
        default=None, metadata={"scalar": "task_id", "nullable": True}
    )
    judgment_id: JudgmentId | None = dc_field(
        default=None, metadata={"scalar": "local_id:J", "nullable": True}
    )
    task_state: TaskState
    participation: Participation | None = dc_field(default=None, metadata={"nullable": True})
    effective_rigor: Rigor
    primary_method: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )
    secondary_method: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )
    repair_count: int = 0
    accepted_controls: tuple[AcceptedControl, ...] = ()
    observation_tags: tuple[Sha256, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class TaskProjection(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.task-projection/1.0.0"
    schema: str = _schema(__schema_id__)
    task_id: TaskId = dc_field(metadata={"scalar": "task_id"})
    state: TaskState
    terminal_reason: TaskTerminalReason | None = dc_field(default=None, metadata={"nullable": True})
    locale: Locale
    requested_rigor: Rigor
    effective_rigor: Rigor
    host: HostId
    host_session_key: Sha256 = dc_field(metadata={"scalar": "sha256"})
    current_judgment_id: JudgmentId | None = dc_field(
        default=None, metadata={"scalar": "local_id:J", "nullable": True}
    )
    repair_count: int = 0
    capability_gaps: tuple[str, ...] = ()
    latest_sequence: int = 0
    created_at: str = dc_field(metadata={"scalar": "timestamp"})
    updated_at: str = dc_field(metadata={"scalar": "timestamp"})


@dataclass(frozen=True, slots=True, kw_only=True)
class Assumption(FrozenModel):
    text: SafeText = _text(500)
    material: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Criterion(FrozenModel):
    criterion_id: CriterionId = dc_field(metadata={"scalar": "local_id:K"})
    text: SafeText = _text(400)
    required: bool
    kind: CriterionKind
    evidence_claim_ids: tuple[ClaimId, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Framing(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.framing/1.0.0"
    schema: str = _schema(__schema_id__)
    judgment_id: JudgmentId = dc_field(metadata={"scalar": "local_id:J"})
    decision_question: SafeText = _text(500)
    assumptions: tuple[Assumption, ...] = ()
    decisive_evidence: tuple[SafeText, ...] = ()
    completion_criteria: tuple[Criterion, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class FlipCondition(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.flip-condition/1.0.0"
    schema: str = _schema(__schema_id__)
    condition: SafeText = _text(300)
    affected_conclusion: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 240, "nullable": True}
    )
    direction: FlipDirection
    check: SafeText = _text(240)


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgmentVersion(FrozenModel):
    judgment_id: JudgmentId = dc_field(metadata={"scalar": "local_id:J"})
    version: int
    state: JudgmentState
    conclusion: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 500, "nullable": True}
    )
    strength: JudgmentStrength
    supersedes_version: int | None = dc_field(default=None, metadata={"nullable": True})
    change_reason: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 500, "nullable": True}
    )
    ground_claim_ids: tuple[ClaimId, ...] = ()
    uncertainty_claim_ids: tuple[ClaimId, ...] = ()
    flip_conditions: tuple[FlipCondition, ...] = ()
    alternative_ids: tuple[AlternativeId, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class SourceReference(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.source-reference/1.0.0"
    schema: str = _schema(__schema_id__)
    source_id: EvidenceId = dc_field(metadata={"scalar": "local_id:E"})
    kind: SourceKind
    display_name: SafeText = _text(200)
    uri: str | None = dc_field(default=None, metadata={"nullable": True})
    safe_locator: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 200, "nullable": True}
    )
    published_at: str | None = dc_field(default=None, metadata={"scalar": "date", "nullable": True})
    checked_at: str = dc_field(metadata={"scalar": "timestamp"})
    content_hash: Sha256 | None = dc_field(
        default=None, metadata={"scalar": "sha256", "nullable": True}
    )

    def __post_init__(self) -> None:
        # Credential-like query parameters are never persisted; keep the
        # human-readable source record while dropping only the unsafe URI.
        object.__setattr__(self, "uri", sanitize_persistable_uri(self.uri))
        FrozenModel.__post_init__(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationOperand(FrozenModel):
    name: SafeText = _text(128)
    value: DecimalString = dc_field(metadata={"scalar": "decimal"})
    unit: SafeText = _text(64)
    source_id: EvidenceId | None = dc_field(
        default=None, metadata={"scalar": "local_id:E", "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Calculation(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.calculation/1.0.0"
    schema: str = _schema(__schema_id__)
    expression: SafeText = _text(
        1000,
    )
    operands: tuple[CalculationOperand, ...] = ()
    result: DecimalString = dc_field(metadata={"scalar": "decimal"})
    unit: SafeText = _text(64)
    rounding: RoundingMode


@dataclass(frozen=True, slots=True, kw_only=True)
class Conflict(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.conflict/1.0.0"
    schema: str = _schema(__schema_id__)
    summary: SafeText = _text(600)
    subject: SafeText = _text(300)
    source_ids: tuple[EvidenceId, ...] = ()
    affected_claim_ids: tuple[ClaimId, ...] = ()
    material: bool
    resolution: ConflictResolution
    resolution_reason: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 600, "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ClaimVersion(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.claim-version/1.0.0"
    schema: str = _schema(__schema_id__)
    claim_id: ClaimId = dc_field(metadata={"scalar": "local_id:C"})
    version: int
    text: SafeText = _text(600)
    materiality: ClaimMateriality
    evidence_state: EvidenceState
    source_ids: tuple[EvidenceId, ...] = ()
    basis_claim_ids: tuple[ClaimId, ...] = ()
    calculation: Calculation | None = dc_field(default=None, metadata={"nullable": True})
    conflict: Conflict | None = dc_field(default=None, metadata={"nullable": True})
    active: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class Alternative(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.alternative/1.0.0"
    schema: str = _schema(__schema_id__)
    alternative_id: AlternativeId = dc_field(metadata={"scalar": "local_id:A"})
    name: SafeText = _text(160)
    disposition: AlternativeDisposition
    reason: SafeText = _text(400)
    material_claim_ids: tuple[ClaimId, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class CardSourceReference(FrozenModel):
    display_name: SafeText = _text(200)
    uri: str | None = dc_field(default=None, metadata={"nullable": True})


@dataclass(frozen=True, slots=True, kw_only=True)
class ConclusionGround(FrozenModel):
    claim_id: ClaimId = dc_field(metadata={"scalar": "local_id:C"})
    text: SafeText = _text(600)
    state: EvidenceState
    source_refs: tuple[CardSourceReference, ...] = ()
    calculation_summary: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 400, "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ConclusionCard(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.conclusion-card/1.0.0"
    schema: str = _schema(__schema_id__)
    locale: Locale
    task_id: TaskId = dc_field(metadata={"scalar": "task_id"})
    judgment_id: JudgmentId = dc_field(metadata={"scalar": "local_id:J"})
    judgment_version: int
    conclusion: SafeText = _text(500)
    strength: JudgmentStrength
    grounds: tuple[ConclusionGround, ...] = ()
    uncertainties: tuple[SafeText, ...] = ()
    flip_conditions: tuple[FlipCondition, ...] = ()
    alternatives_summary: SafeText = _text(800)
    rendered_at: str = dc_field(metadata={"scalar": "timestamp"})


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionCriterion(FrozenModel):
    criterion_id: CriterionId = dc_field(metadata={"scalar": "local_id:K"})
    status: CriterionStatus
    reason: SafeText = _text(400)
    required: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionResult(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.completion-result/1.0.0"
    schema: str = _schema(__schema_id__)
    judgment_id: JudgmentId = dc_field(metadata={"scalar": "local_id:J"})
    candidate_sequence: int
    outcome: VerificationOutcome
    criteria: tuple[CompletionCriterion, ...] = ()
    violations: tuple[str, ...] = ()
    repair_count_before: int = 0
    may_continue: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class Violation(FrozenModel):
    rule_id: SafeText = _text(32)
    severity: ViolationSeverity
    message_key: SafeText = _text(128)
    field: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 256, "nullable": True}
    )
    repair_hint_key: SafeText | None = dc_field(
        default=None, metadata={"scalar": "safe_text", "max_length": 128, "nullable": True}
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class VerificationResult(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.verification-result/1.0.0"
    schema: str = _schema(__schema_id__)
    outcome: VerificationOutcome
    verifier_version: SemVer = dc_field(default=VERIFIER_VERSION, metadata={"scalar": "semver"})
    ruleset_version: SemVer = dc_field(default=VERIFIER_VERSION, metadata={"scalar": "semver"})
    violations: tuple[Violation, ...] = ()
    parsed_card: ConclusionCard | None = dc_field(default=None, metadata={"nullable": True})
    completion_result: CompletionResult | None = dc_field(default=None, metadata={"nullable": True})
    duration_ms: DurationMs = dc_field(default=0, metadata={"scalar": "duration_ms"})


@dataclass(frozen=True, slots=True, kw_only=True)
class JudgmentEvent(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.judgment-event/1.0.0"
    schema: str = _schema(__schema_id__)
    event_id: EventId = dc_field(metadata={"scalar": "event_id"})
    task_id: TaskId = dc_field(metadata={"scalar": "task_id"})
    sequence: int
    event_type: RecordEventType
    occurred_at: str = dc_field(metadata={"scalar": "timestamp"})
    host: HostId
    host_version: SafeText = _text(64)
    adapter_version: SemVer = dc_field(metadata={"scalar": "semver"})
    locale: Locale
    payload: dict[str, Any] = dc_field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceView(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.trace-view/1.0.0"
    schema: str = _schema(__schema_id__)
    task_id: TaskId = dc_field(metadata={"scalar": "task_id"})
    public_short_id: SafeText = _text(8)
    status: TaskState
    terminal_reason: TaskTerminalReason | None = dc_field(default=None, metadata={"nullable": True})
    locale: Locale
    framing: Framing | None = dc_field(default=None, metadata={"nullable": True})
    chronology: tuple[dict[str, Any], ...] = ()
    methods: dict[str, Any] = dc_field(default_factory=dict)
    claim_history: tuple[ClaimVersion, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    alternatives: tuple[Alternative, ...] = ()
    completion: CompletionResult | None = dc_field(default=None, metadata={"nullable": True})
    current_card: ConclusionCard | None = dc_field(default=None, metadata={"nullable": True})
    capability_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalMetric(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.local-metric/1.0.0"
    schema: str = _schema(__schema_id__)
    event: MetricEventName
    occurred_at_day: str = dc_field(metadata={"scalar": "date"})
    product_version: SemVer = dc_field(default=PRODUCT_VERSION, metadata={"scalar": "semver"})
    host: HostId
    locale: Locale
    rigor: Rigor
    duration_bucket_ms: DurationBucket | None = dc_field(default=None, metadata={"nullable": True})
    attributes: dict[str, Any] = dc_field(default_factory=dict)


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodDisplayName(FrozenModel):
    """The explicit-use display label for a method."""

    en: SafeText = _text(200)
    ko: SafeText = _text(200)


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodPlainAction(FrozenModel):
    """The plain-language action injected for a method."""

    en: SafeText = _text(500)
    ko: SafeText = _text(500)


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodParticipation(FrozenModel):
    judgment_only: bool
    allowed_answer_shapes: tuple[AnswerShape, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodRouting(FrozenModel):
    positive_features: dict[FeatureKey, int]
    negative_features: dict[FeatureKey, int]
    minimum_score: int
    contraindications: tuple[FeatureKey, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodOutputContract(FrozenModel):
    required_sections: tuple[SafeText, ...]
    max_questions: int


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodComplements(FrozenModel):
    preferred: tuple[MethodId, ...]
    incompatible_secondary: tuple[MethodId, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodSourceProvenance(FrozenModel):
    predecessor_slug: MethodId = dc_field(metadata={"scalar": "method_id"})
    reviewed_by: SafeText = _text(128)


@dataclass(frozen=True, slots=True, kw_only=True)
class MethodAuthoring(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.method-authoring/1.0.0"
    schema: str = _schema(__schema_id__)
    id: MethodId = dc_field(metadata={"scalar": "method_id"})
    family: FamilyId
    content_revision: int
    display_name: MethodDisplayName
    plain_action: MethodPlainAction
    participation: MethodParticipation
    routing: MethodRouting
    output_contract: MethodOutputContract
    complements: MethodComplements
    locales: tuple[Locale, ...]
    source_provenance: MethodSourceProvenance


@dataclass(frozen=True, slots=True, kw_only=True)
class TeacherQuestionLocales(FrozenModel):
    """Exactly three authored prompts in each supported procedure locale."""

    en: tuple[SafeText, ...] = dc_field(
        metadata={
            "min_items": 3,
            "max_items": 3,
            "unique_items": True,
            "item_min_length": 20,
            "item_max_length": 220,
            "item_pattern": r"^(?!\s)(?!.*\s$)[^\r\n\u0000]+\?$",
        }
    )
    ko: tuple[SafeText, ...] = dc_field(
        metadata={
            "min_items": 3,
            "max_items": 3,
            "unique_items": True,
            "item_min_length": 20,
            "item_max_length": 220,
            "item_pattern": r"^(?!\s)(?!.*\s$)[^\r\n\u0000]+\?$",
        }
    )

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        for locale, questions in (("en", self.en), ("ko", self.ko)):
            if len(questions) != 3 or len(set(questions)) != len(questions):
                raise ValidationError(
                    f"teacher question locales: {locale} requires three unique questions"
                )
            if any(
                question != question.strip()
                or not 20 <= len(question) <= 220
                or not question.endswith("?")
                or "\n" in question
                or "\x00" in question
                for question in questions
            ):
                raise ValidationError(f"teacher question locales: {locale} question is invalid")


@dataclass(frozen=True, slots=True, kw_only=True)
class TeacherQuestionCatalog(FrozenModel):
    """Canonical bilingual overlay applied without changing authored method revisions."""

    __schema_id__: ClassVar[str] = "opensocrates.teacher-questions/1.0.0"
    schema: str = _schema(__schema_id__)
    content_revision: int = dc_field(default=CONTENT_REVISION, metadata={"const": CONTENT_REVISION})
    methods: dict[MethodId, TeacherQuestionLocales] = dc_field(
        metadata={
            "min_properties": 48,
            "max_properties": 48,
            "property_name_pattern": r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        }
    )

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        if self.content_revision != CONTENT_REVISION or len(self.methods) != 48:
            raise ValidationError(
                "teacher question catalog: overlay revision/count does not match canonical content"
            )
        seen: dict[str, set[str]] = {"en": set(), "ko": set()}
        for localized in self.methods.values():
            for locale, questions in (("en", localized.en), ("ko", localized.ko)):
                if seen[locale].intersection(questions):
                    raise ValidationError(
                        f"teacher question catalog: duplicate {locale} question across methods"
                    )
                seen[locale].update(questions)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompiledMethod(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.compiled-method/1.0.0"
    schema: str = _schema(__schema_id__)
    id: MethodId = dc_field(metadata={"scalar": "method_id"})
    family: FamilyId
    content_revision: int
    display_name: dict[str, SafeText]
    plain_action: dict[str, SafeText]
    participation: dict[str, Any]
    routing: dict[str, Any]
    output_contract: dict[str, Any]
    complements: dict[str, Any]
    procedure: dict[str, ReviewedProcedureText]
    complement_fragment: dict[str, ReviewedProcedureText]


@dataclass(frozen=True, slots=True, kw_only=True)
class TemplateExample(FrozenModel):
    """One authored routing case projected as untrusted injectable template data."""

    __schema_id__: ClassVar[str] = "opensocrates.template-example/1.0.0"
    schema: str = _schema(__schema_id__)
    case_id: SafeText = _text(160)
    kind: SafeText = _text(32)
    template_prompt: SafeText = _text(4000)
    expected_route: MethodId | None = dc_field(
        default=None, metadata={"scalar": "method_id", "nullable": True}
    )
    expected_behavior: SafeText = _text(64)
    decisive_features: tuple[SafeText, ...] = ()
    rationale: SafeText = _text(4000)

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        if not all(
            value.strip()
            for value in (
                self.case_id,
                self.kind,
                self.template_prompt,
                self.expected_behavior,
                self.rationale,
            )
        ):
            raise ValidationError("template example: required authored text cannot be blank")
        if any(not value.strip() for value in self.decisive_features):
            raise ValidationError("template example: decisive features cannot be blank")


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectionCatalogEntry(FrozenModel):
    """Compact comparison metadata for one reasoning system, never injected theory."""

    __schema_id__: ClassVar[str] = "opensocrates.selection-catalog-entry/1.0.0"
    schema: str = _schema(__schema_id__)
    method_id: MethodId = dc_field(metadata={"scalar": "method_id"})
    family: SafeText = _text(64)
    content_revision: int
    display_name: dict[Locale, SafeText]
    core_purpose: dict[Locale, SafeText]
    suitable_features: tuple[SafeText, ...] = ()
    unsuitable_features: tuple[SafeText, ...] = ()
    commonly_confused_features: tuple[SafeText, ...] = ()
    related_method_ids: tuple[MethodId, ...] = ()
    injectable_content_locator: SafeText = _text(200)

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        if not isinstance(self.content_revision, int) or isinstance(self.content_revision, bool):
            raise ValidationError("selection catalog entry: content revision must be an integer")
        if self.content_revision < 1:
            raise ValidationError("selection catalog entry: content revision must be positive")
        if not self.family.strip():
            raise ValidationError("selection catalog entry: family cannot be blank")
        locale_keys = set(self.display_name)
        if "en" not in locale_keys or locale_keys - {"en", "ko"}:
            raise ValidationError("selection catalog entry: English name is required")
        if set(self.core_purpose) != locale_keys or any(
            not value.strip()
            for value in (*self.display_name.values(), *self.core_purpose.values())
        ):
            raise ValidationError(
                "selection catalog entry: localized name/purpose must be complete"
            )
        for values, label in (
            (self.suitable_features, "suitable features"),
            (self.unsuitable_features, "unsuitable features"),
            (self.commonly_confused_features, "commonly confused features"),
            (self.related_method_ids, "related methods"),
        ):
            if len(set(values)) != len(values):
                raise ValidationError(f"selection catalog entry: duplicate {label}")
        if not self.injectable_content_locator.strip():
            raise ValidationError("selection catalog entry: injectable locator cannot be blank")


@dataclass(frozen=True, slots=True, kw_only=True)
class SelectionCatalog(FrozenModel):
    """Revision-bound selector comparison projection, distinct from injectable content."""

    __schema_id__: ClassVar[str] = "opensocrates.selection-catalog/1.0.0"
    schema: str = _schema(__schema_id__)
    content_revision: int
    entries: tuple[SelectionCatalogEntry, ...] = ()

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        if not isinstance(self.content_revision, int) or isinstance(self.content_revision, bool):
            raise ValidationError("selection catalog: content revision must be an integer")
        if self.content_revision < 1:
            raise ValidationError("selection catalog: content revision must be positive")
        method_ids = tuple(entry.method_id for entry in self.entries)
        if not method_ids or len(set(method_ids)) != len(method_ids):
            raise ValidationError("selection catalog: entries must have unique method IDs")
        if any(entry.content_revision != self.content_revision for entry in self.entries):
            raise ValidationError("selection catalog: entries must match the catalog revision")


@dataclass(frozen=True, slots=True, kw_only=True)
class InjectableReasoningContent(FrozenModel):
    """Complete authored theory and ordered template examples for one locale/method."""

    __schema_id__: ClassVar[str] = "opensocrates.injectable-reasoning-content/1.0.0"
    schema: str = _schema(__schema_id__)
    method_id: MethodId = dc_field(metadata={"scalar": "method_id"})
    content_revision: int
    locale: Locale
    display_name: SafeText = _text(200)
    theory: ReviewedProcedureText = _text(20_000)
    template_examples: tuple[TemplateExample, ...] = ()

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        if not isinstance(self.content_revision, int) or isinstance(self.content_revision, bool):
            raise ValidationError(
                "injectable reasoning content: content revision must be an integer"
            )
        if self.content_revision < 1:
            raise ValidationError("injectable reasoning content: content revision must be positive")
        if not self.display_name.strip() or not self.theory.strip():
            raise ValidationError("injectable reasoning content: name and theory are required")
        case_ids = tuple(example.case_id for example in self.template_examples)
        if not case_ids or len(set(case_ids)) != len(case_ids):
            raise ValidationError(
                "injectable reasoning content: ordered template examples are required"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ReasoningContentProjections(FrozenModel):
    """Canonical OpenSocrates selector catalog plus injectable content for one revision."""

    __schema_id__: ClassVar[str] = "opensocrates.reasoning-content-projections/1.0.0"
    schema: str = _schema(__schema_id__)
    content_revision: int
    selection_catalog: SelectionCatalog
    injectable_content: tuple[InjectableReasoningContent, ...] = ()

    def __post_init__(self) -> None:
        FrozenModel.__post_init__(self)
        if not isinstance(self.content_revision, int) or isinstance(self.content_revision, bool):
            raise ValidationError(
                "reasoning content projections: content revision must be an integer"
            )
        if (
            self.content_revision < 1
            or self.selection_catalog.content_revision != self.content_revision
        ):
            raise ValidationError("reasoning content projections: catalog revision mismatch")
        catalog_ids = {entry.method_id for entry in self.selection_catalog.entries}
        if not self.injectable_content:
            raise ValidationError("reasoning content projections: injectable content is required")
        seen: set[tuple[str, str]] = set()
        english_ids: set[str] = set()
        for content in self.injectable_content:
            if (
                content.content_revision != self.content_revision
                or content.method_id not in catalog_ids
            ):
                raise ValidationError(
                    "reasoning content projections: unknown or stale injectable content"
                )
            key = (content.method_id, content.locale)
            if key in seen:
                raise ValidationError("reasoning content projections: duplicate locale content")
            seen.add(key)
            if content.locale == "en":
                english_ids.add(content.method_id)
        if english_ids != catalog_ids:
            raise ValidationError(
                "reasoning content projections: English content is required for every method"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyVersion(FrozenModel):
    version: SemVer = dc_field(metadata={"scalar": "semver"})
    sha256: Sha256 = dc_field(metadata={"scalar": "sha256"})


@dataclass(frozen=True, slots=True, kw_only=True)
class CompiledContentBundle(FrozenModel):
    __schema_id__: ClassVar[str] = "opensocrates.compiled-content-bundle/1.0.0"
    schema: str = _schema(__schema_id__)
    product_version: SemVer = dc_field(default=PRODUCT_VERSION, metadata={"scalar": "semver"})
    content_revision: int = CONTENT_REVISION
    method_ids: tuple[MethodId, ...] = ()
    methods: tuple[CompiledMethod, ...] = ()
    locale_messages: dict[str, dict[str, SafeText]] = dc_field(default_factory=dict)
    prompt_fragments: dict[str, dict[str, SafeText]] = dc_field(default_factory=dict)
    policy_versions: dict[str, PolicyVersion] = dc_field(default_factory=dict)
    source_tree_hash: Sha256 | None = dc_field(
        default=None, metadata={"scalar": "sha256", "nullable": True}
    )
    normalized_semantic_hash: Sha256 | None = dc_field(
        default=None, metadata={"scalar": "sha256", "nullable": True}
    )


# Fields with defaults in Python still remain required in the persisted/public
# contract when Document 04 says the key must be present (often with null or an
# empty array as its value).  The strict adapter and schema generator share
# this table so they cannot drift.
_REQUIRED_FIELDS: dict[type[FrozenModel], tuple[str, ...]] = {
    CapabilityEntry: ("status", "evidence_kind", "source_checked_at"),
    CapabilityProfile: (
        "schema",
        "host",
        "host_version_range",
        "checked_at",
        "adapter_version",
        "computed_tier",
        "capabilities",
    ),
    FeedbackEntry: ("sequence", "day", "outcome"),
    InterventionPreference: (
        "next_sequence",
        "recent_feedback",
        "reduced_since_sequence",
        "reduced_until",
    ),
    UserSettings: (
        "schema",
        "revision",
        "default_rigor",
        "locale_preference",
        "recording_mode",
        "record_retention_days",
        "record_size_limit_bytes",
        "onboarding_version_seen",
        "intervention_preferences",
        "metrics_consent",
    ),
    NormalizedEvent: (
        "schema",
        "event_id",
        "event_type",
        "occurred_at",
        "host",
        "host_version",
        "adapter_version",
        "host_session_key",
        "host_turn_key",
        "payload",
    ),
    ParticipationDecision: (
        "schema",
        "participation",
        "reason_code",
        "judgment_targets",
        "mechanical_targets",
        "confidence_basis",
        "explicit_method",
    ),
    RigorDecision: (
        "schema",
        "stored_rigor",
        "task_override",
        "risk_floor",
        "risk_reason",
        "effective_rigor",
        "show_raise_notice",
    ),
    RoutingFeature: ("key", "strength", "basis"),
    RoutingFeatures: (
        "schema",
        "answer_shape",
        "features",
        "classification_confidence",
        "explicit_method",
    ),
    RouterDecision: (
        "schema",
        "router_version",
        "answer_shape",
        "primary_family",
        "secondary_family",
        "primary_method",
        "secondary_method",
        "explicit_invocation",
        "reason_code",
        "prompt_bundle_hash",
    ),
    AssignedIds: (
        "task_id",
        "judgment_id",
        "claim_ids",
        "source_ids",
        "criterion_ids",
        "alternative_ids",
    ),
    HostControl: ("schema", "message_id", "turn_token", "message_type", "published", "payload"),
    HostControlResult: (
        "schema",
        "message_id",
        "status",
        "reason_code",
        "durable_mutation",
        "assigned_ids",
        "effective_rigor",
        "route",
        "capability_limitations",
        "next_action",
        "error_code",
    ),
    AcceptedControl: ("message_id", "payload_tag", "result"),
    EphemeralTurnState: (
        "schema",
        "token_tag",
        "host_session_key",
        "host_turn_key",
        "host",
        "issued_at",
        "expires_at",
        "recording_eligible",
        "onboarding_disclosure_turn",
        "task_id",
        "judgment_id",
        "task_state",
        "participation",
        "effective_rigor",
        "primary_method",
        "secondary_method",
        "repair_count",
        "accepted_controls",
        "observation_tags",
    ),
    TaskProjection: (
        "schema",
        "task_id",
        "state",
        "terminal_reason",
        "locale",
        "requested_rigor",
        "effective_rigor",
        "host",
        "host_session_key",
        "current_judgment_id",
        "repair_count",
        "capability_gaps",
        "latest_sequence",
        "created_at",
        "updated_at",
    ),
    Assumption: ("text", "material"),
    Criterion: ("criterion_id", "text", "required", "kind", "evidence_claim_ids"),
    Framing: (
        "schema",
        "judgment_id",
        "decision_question",
        "assumptions",
        "decisive_evidence",
        "completion_criteria",
    ),
    FlipCondition: ("schema", "condition", "direction", "check"),
    JudgmentVersion: (
        "judgment_id",
        "version",
        "state",
        "conclusion",
        "strength",
        "supersedes_version",
        "change_reason",
        "ground_claim_ids",
        "uncertainty_claim_ids",
        "flip_conditions",
        "alternative_ids",
    ),
    SourceReference: (
        "schema",
        "source_id",
        "kind",
        "display_name",
        "uri",
        "safe_locator",
        "published_at",
        "checked_at",
        "content_hash",
    ),
    CalculationOperand: ("name", "value", "unit", "source_id"),
    Calculation: ("schema", "expression", "operands", "result", "unit", "rounding"),
    Conflict: (
        "schema",
        "summary",
        "subject",
        "source_ids",
        "affected_claim_ids",
        "material",
        "resolution",
        "resolution_reason",
    ),
    ClaimVersion: (
        "schema",
        "claim_id",
        "version",
        "text",
        "materiality",
        "evidence_state",
        "source_ids",
        "basis_claim_ids",
        "calculation",
        "conflict",
        "active",
    ),
    Alternative: (
        "schema",
        "alternative_id",
        "name",
        "disposition",
        "reason",
        "material_claim_ids",
    ),
    CardSourceReference: ("display_name", "uri"),
    ConclusionGround: ("claim_id", "text", "state", "source_refs", "calculation_summary"),
    ConclusionCard: (
        "schema",
        "locale",
        "task_id",
        "judgment_id",
        "judgment_version",
        "conclusion",
        "strength",
        "grounds",
        "uncertainties",
        "flip_conditions",
        "alternatives_summary",
        "rendered_at",
    ),
    CompletionCriterion: ("criterion_id", "status", "reason", "required"),
    CompletionResult: (
        "schema",
        "judgment_id",
        "candidate_sequence",
        "outcome",
        "criteria",
        "violations",
        "repair_count_before",
        "may_continue",
    ),
    Violation: ("rule_id", "severity", "message_key", "field", "repair_hint_key"),
    VerificationResult: (
        "schema",
        "outcome",
        "verifier_version",
        "ruleset_version",
        "violations",
        "parsed_card",
        "completion_result",
        "duration_ms",
    ),
    JudgmentEvent: (
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
    ),
    TraceView: (
        "schema",
        "task_id",
        "public_short_id",
        "status",
        "terminal_reason",
        "locale",
        "framing",
        "chronology",
        "methods",
        "claim_history",
        "conflicts",
        "alternatives",
        "completion",
        "current_card",
        "capability_notes",
    ),
    LocalMetric: (
        "schema",
        "event",
        "occurred_at_day",
        "product_version",
        "host",
        "locale",
        "rigor",
        "duration_bucket_ms",
        "attributes",
    ),
    MethodAuthoring: (
        "schema",
        "id",
        "family",
        "content_revision",
        "display_name",
        "plain_action",
        "participation",
        "routing",
        "output_contract",
        "complements",
        "locales",
        "source_provenance",
    ),
    TeacherQuestionLocales: ("en", "ko"),
    TeacherQuestionCatalog: ("schema", "content_revision", "methods"),
    CompiledMethod: (
        "schema",
        "id",
        "family",
        "content_revision",
        "display_name",
        "plain_action",
        "participation",
        "routing",
        "output_contract",
        "complements",
        "procedure",
        "complement_fragment",
    ),
    TemplateExample: (
        "schema",
        "case_id",
        "kind",
        "template_prompt",
        "expected_route",
        "expected_behavior",
        "decisive_features",
        "rationale",
    ),
    SelectionCatalogEntry: (
        "schema",
        "method_id",
        "family",
        "content_revision",
        "display_name",
        "core_purpose",
        "suitable_features",
        "unsuitable_features",
        "commonly_confused_features",
        "related_method_ids",
        "injectable_content_locator",
    ),
    SelectionCatalog: ("schema", "content_revision", "entries"),
    InjectableReasoningContent: (
        "schema",
        "method_id",
        "content_revision",
        "locale",
        "display_name",
        "theory",
        "template_examples",
    ),
    ReasoningContentProjections: (
        "schema",
        "content_revision",
        "selection_catalog",
        "injectable_content",
    ),
    PolicyVersion: ("version", "sha256"),
    CompiledContentBundle: (
        "schema",
        "product_version",
        "content_revision",
        "method_ids",
        "methods",
        "locale_messages",
        "prompt_fragments",
        "policy_versions",
        "source_tree_hash",
        "normalized_semantic_hash",
    ),
}
for _model_type, _required in _REQUIRED_FIELDS.items():
    _model_type.__required_fields__ = frozenset(_required)  # type: ignore[attr-defined]  # Closed runtime boundary validates this value.


SCHEMA_TYPES: dict[str, type[FrozenModel]] = {
    "normalized-event.schema.json": NormalizedEvent,
    "capability-profile.schema.json": CapabilityProfile,
    "user-settings.schema.json": UserSettings,
    "participation-decision.schema.json": ParticipationDecision,
    "rigor-decision.schema.json": RigorDecision,
    "routing-features.schema.json": RoutingFeatures,
    "router-decision.schema.json": RouterDecision,
    "host-control.schema.json": HostControl,
    "host-control-result.schema.json": HostControlResult,
    "ephemeral-turn-state.schema.json": EphemeralTurnState,
    "task-projection.schema.json": TaskProjection,
    "framing.schema.json": Framing,
    "source-reference.schema.json": SourceReference,
    "claim-version.schema.json": ClaimVersion,
    "calculation.schema.json": Calculation,
    "conflict.schema.json": Conflict,
    "alternative.schema.json": Alternative,
    "flip-condition.schema.json": FlipCondition,
    "conclusion-card.schema.json": ConclusionCard,
    "completion-result.schema.json": CompletionResult,
    "verification-result.schema.json": VerificationResult,
    "judgment-event.schema.json": JudgmentEvent,
    "trace-view.schema.json": TraceView,
    "local-metric.schema.json": LocalMetric,
    "method-authoring.schema.json": MethodAuthoring,
    "teacher-questions.schema.json": TeacherQuestionCatalog,
    "compiled-method.schema.json": CompiledMethod,
    "compiled-content-bundle.schema.json": CompiledContentBundle,
    "template-example.schema.json": TemplateExample,
    "selection-catalog-entry.schema.json": SelectionCatalogEntry,
    "selection-catalog.schema.json": SelectionCatalog,
    "injectable-reasoning-content.schema.json": InjectableReasoningContent,
    "reasoning-content-projections.schema.json": ReasoningContentProjections,
}

__all__ = [
    "SCHEMA_TYPES",
    "AcceptedControl",
    "Alternative",
    "Assumption",
    "AssignedIds",
    "Calculation",
    "CalculationOperand",
    "CapabilityEntry",
    "CapabilityProfile",
    "CardSourceReference",
    "ClaimVersion",
    "CompiledContentBundle",
    "CompiledMethod",
    "CompletionCriterion",
    "CompletionResult",
    "Conflict",
    "ConclusionCard",
    "ConclusionGround",
    "Criterion",
    "EphemeralTurnState",
    "FeedbackEntry",
    "FlipCondition",
    "Framing",
    "HostControl",
    "HostControlResult",
    "InterventionPreference",
    "InjectableReasoningContent",
    "JudgmentEvent",
    "JudgmentVersion",
    "LocalMetric",
    "MethodAuthoring",
    "MethodComplements",
    "MethodDisplayName",
    "MethodOutputContract",
    "MethodParticipation",
    "MethodPlainAction",
    "MethodRouting",
    "MethodSourceProvenance",
    "TeacherQuestionCatalog",
    "TeacherQuestionLocales",
    "NormalizedEvent",
    "ParticipationDecision",
    "PolicyVersion",
    "ReasoningContentProjections",
    "RigorDecision",
    "RouterDecision",
    "RoutingFeature",
    "RoutingFeatures",
    "SourceReference",
    "SelectionCatalog",
    "SelectionCatalogEntry",
    "TaskProjection",
    "TraceView",
    "TemplateExample",
    "UserSettings",
    "VerificationResult",
    "Violation",
]
