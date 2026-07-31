"""Closed v1 enum vocabulary from Document 04 and the routing contract."""

from __future__ import annotations

from enum import StrEnum


class Participation(StrEnum):
    MECHANICAL = "mechanical"
    JUDGMENT = "judgment"
    MIXED = "mixed"


class Rigor(StrEnum):
    QUIET = "quiet"
    TOGETHER = "together"
    STRICT = "strict"


class RiskFloorReason(StrEnum):
    NONE = "none"
    ORDINARY_JUDGMENT = "ordinary_judgment"
    EXTERNALLY_CHECKABLE_MATERIAL_CLAIMS = "externally_checkable_material_claims"
    MATERIAL_CONSEQUENCE = "material_consequence"
    IRREVERSIBLE_COMMITMENT = "irreversible_commitment"
    EXPLICIT_USER_STRICT = "explicit_user_strict"


class TaskState(StrEnum):
    NEW = "new"
    FRAMING = "framing"
    WORKING = "working"
    REJUDGING = "rejudging"
    CROSS_EXAMINING = "cross_examining"
    VERIFYING = "verifying"
    BYPASSED = "bypassed"
    CONCLUDED = "concluded"
    CANCELLED = "cancelled"
    INSUFFICIENT = "insufficient"
    DEGRADED = "degraded"


class JudgmentState(StrEnum):
    IDENTIFIED = "identified"
    ACTIVE = "active"
    REVISED = "revised"
    CROSS_EXAMINED = "cross_examined"
    VERIFIED = "verified"
    PUBLISHED = "published"
    HELD = "held"
    SUPERSEDED = "superseded"
    ABANDONED = "abandoned"
    VERIFICATION_FAILED = "verification_failed"


class TaskTerminalReason(StrEnum):
    MECHANICAL = "mechanical"
    CRITERIA_SATISFIED = "criteria_satisfied"
    USER_CANCELLED = "user_cancelled"
    EVIDENCE_MISSING = "evidence_missing"
    EVIDENCE_CONFLICT = "evidence_conflict"
    COMPLETION_CRITERIA_UNMET = "completion_criteria_unmet"
    CAPABILITY_MISSING = "capability_missing"
    VERIFIER_UNAVAILABLE = "verifier_unavailable"
    VERIFIER_FAILED = "verifier_failed"
    METHOD_UNAVAILABLE = "method_unavailable"
    RECORD_UNAVAILABLE = "record_unavailable"
    RUNTIME_ERROR = "runtime_error"


class EvidenceState(StrEnum):
    VERIFIED = "verified"
    COMPUTED = "computed"
    INFERRED = "inferred"
    ASSUMED = "assumed"
    UNVERIFIED = "unverified"
    CONFLICTED = "conflicted"


class SourceKind(StrEnum):
    WEB = "web"
    USER_DOCUMENT = "user_document"
    HOST_CONNECTOR = "host_connector"
    DATASET = "dataset"
    CALCULATION_INPUT = "calculation_input"
    USER_STATEMENT = "user_statement"


class ClaimMateriality(StrEnum):
    MATERIAL = "material"
    NON_MATERIAL = "non_material"


class ConflictResolution(StrEnum):
    UNRESOLVED = "unresolved"
    SOURCE_PRECEDENCE = "source_precedence"
    RECENCY = "recency"
    MEASUREMENT_DEFINITION = "measurement_definition"
    CALCULATION_CORRECTION = "calculation_correction"
    SCOPE_SPLIT = "scope_split"
    USER_DECISION = "user_decision"


class CapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class HostId(StrEnum):
    CODEX_DESKTOP = "codex_desktop"
    CODEX_CLI = "codex_cli"
    PROMPT_ONLY = "prompt_only"


class VerificationOutcome(StrEnum):
    PASS = "pass"
    REPAIR = "repair"
    INSUFFICIENT = "insufficient"
    DEGRADED = "degraded"
    ERROR = "error"


class ViolationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class CriterionStatus(StrEnum):
    MET = "met"
    UNMET = "unmet"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"
    NOT_RECORDED = "not_recorded"


class CriterionKind(StrEnum):
    STRUCTURAL = "structural"
    EVIDENTIARY = "evidentiary"
    USER_CONSTRAINT = "user_constraint"
    SAFETY = "safety"
    CARD_CONTRACT = "card_contract"


class EventType(StrEnum):
    SESSION_STARTED = "session_started"
    USER_PROMPT_SUBMITTED = "user_prompt_submitted"
    SKILL_INVOKED = "skill_invoked"
    TOOL_SUCCEEDED = "tool_succeeded"
    TOOL_FAILED = "tool_failed"
    TOOL_BATCH_COMPLETED = "tool_batch_completed"
    COMPLETION_CANDIDATE = "completion_candidate"
    PRE_COMPACTION = "pre_compaction"
    POST_COMPACTION = "post_compaction"
    SESSION_ENDED = "session_ended"


class ToolCategory(StrEnum):
    RETRIEVAL = "retrieval"
    READ = "read"
    SEARCH = "search"
    CALCULATION = "calculation"
    WRITE = "write"
    FORMAT = "format"
    EXECUTION = "execution"
    NAVIGATION = "navigation"
    OTHER = "other"


class ParticipationReasonCode(StrEnum):
    DIRECT_TRANSFORMATION = "direct_transformation"
    DIRECT_ARTIFACT_ACTION = "direct_artifact_action"
    DIRECT_RETRIEVAL = "direct_retrieval"
    JUDGMENT_CHOICE = "judgment_choice"
    JUDGMENT_DIAGNOSIS = "judgment_diagnosis"
    JUDGMENT_EVIDENCE = "judgment_evidence"
    JUDGMENT_RISK = "judgment_risk"
    JUDGMENT_COMPLETION = "judgment_completion"
    JUDGMENT_THEN_ARTIFACT = "judgment_then_artifact"
    ARTIFACT_WITH_JUDGMENT_SEGMENT = "artifact_with_judgment_segment"
    EXPLICIT_METHOD_WITH_JUDGMENT = "explicit_method_with_judgment"
    EXPLICIT_METHOD_WITHOUT_JUDGMENT = "explicit_method_without_judgment"


class ConfidenceBasis(StrEnum):
    RULE_PLUS_MODEL_POLICY = "rule_plus_model_policy"


class AnswerShape(StrEnum):
    DIRECT_JUDGMENT = "direct_judgment"
    DECISION_MEMO = "decision_memo"
    DIAGNOSTIC = "diagnostic"
    CRITIQUE = "critique"
    RISK_ASSESSMENT = "risk_assessment"
    EVIDENCE_RECONCILIATION = "evidence_reconciliation"
    STRUCTURED_PLAN = "structured_plan"
    COMPLETION_REVIEW = "completion_review"


class FeatureBasis(StrEnum):
    TASK_SHAPE = "task_shape"
    EVIDENCE_NEED = "evidence_need"
    CAUSAL_NEED = "causal_need"
    DECISION_NEED = "decision_need"
    UNCERTAINTY_NEED = "uncertainty_need"
    CHALLENGE_NEED = "challenge_need"
    LEARNING_NEED = "learning_need"
    STRATEGY_NEED = "strategy_need"
    EXPLICIT_USER = "explicit_user"


class ClassificationConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RouterReasonCode(StrEnum):
    EXPLICIT_METHOD = "explicit_method"
    WEIGHTED_PRIMARY = "weighted_primary"
    WEIGHTED_PRIMARY_WITH_COMPLEMENT = "weighted_primary_with_complement"
    ANSWER_SHAPE_FALLBACK = "answer_shape_fallback"
    INVALID_FEATURES_FALLBACK = "invalid_features_fallback"
    NO_ELIGIBLE_METHOD = "no_eligible_method"
    CONTRAINDICATED_EXPLICIT_METHOD = "contraindicated_explicit_method"


class CapabilityEvidenceKind(StrEnum):
    HOST_CONTRACT = "host_contract"
    LOCAL_PROBE = "local_probe"
    PRODUCT_CONTRACT = "product_contract"


class CapabilityTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    UNSUPPORTED = "unsupported"


class JudgmentStrength(StrEnum):
    HELD = "held"
    PROVISIONAL = "provisional"
    SUPPORTED = "supported"
    STRONGLY_SUPPORTED = "strongly_supported"


class AlternativeDisposition(StrEnum):
    SELECTED = "selected"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    NOT_COMPARABLE = "not_comparable"


class FlipDirection(StrEnum):
    STRENGTHEN = "strengthen"
    WEAKEN = "weaken"
    REVERSE = "reverse"
    HOLD = "hold"


class RoundingMode(StrEnum):
    NONE = "none"
    HALF_EVEN_0 = "half_even_0"
    HALF_EVEN_1 = "half_even_1"
    HALF_EVEN_2 = "half_even_2"
    FLOOR = "floor"
    CEILING = "ceiling"


class RecordEventType(StrEnum):
    TASK_STARTED = "task_started"
    FRAMING_PUBLISHED = "framing_published"
    METHOD_SELECTED = "method_selected"
    METHOD_ACTIVATED = "method_activated"
    JUDGMENT_STARTED = "judgment_started"
    OBSERVATION_CHECK_REQUESTED = "observation_check_requested"
    INTERVENTION_PUBLISHED = "intervention_published"
    CLAIM_PUBLISHED = "claim_published"
    SOURCE_PUBLISHED = "source_published"
    CONFLICT_PUBLISHED = "conflict_published"
    CONFLICT_RESOLVED = "conflict_resolved"
    ALTERNATIVE_PUBLISHED = "alternative_published"
    CONCLUSION_PUBLISHED = "conclusion_published"
    CROSS_EXAM_COMPLETED = "cross_exam_completed"
    COMPLETION_CHECKED = "completion_checked"
    REPAIR_REQUESTED = "repair_requested"
    VERIFICATION_FAILED = "verification_failed"
    CAPABILITY_DEGRADED = "capability_degraded"
    TASK_CONCLUDED = "task_concluded"
    TASK_INSUFFICIENT = "task_insufficient"
    TASK_CANCELLED = "task_cancelled"
    RECOVERED_FROM_TORN_TAIL = "recovered_from_torn_tail"


class MethodActivationSource(StrEnum):
    AUTOMATIC = "automatic"
    EXPLICIT = "explicit"


class EventSource(StrEnum):
    MODEL = "model"
    USER = "user"
    UNKNOWN = "unknown"


class HostControlMessageType(StrEnum):
    BEGIN_JUDGMENT = "begin_judgment"
    INTERVENTION_FEEDBACK = "intervention_feedback"
    PUBLISH_FRAMING = "publish_framing"
    PUBLISH_CLAIM = "publish_claim"
    PUBLISH_CONFLICT = "publish_conflict"
    PUBLISH_ALTERNATIVE = "publish_alternative"
    REVISE_JUDGMENT = "revise_judgment"
    COMPLETE_CROSS_EXAM = "complete_cross_exam"
    HOLD_JUDGMENT = "hold_judgment"
    CANCEL_JUDGMENT = "cancel_judgment"


class HostControlStatus(StrEnum):
    ACCEPTED = "accepted"
    ACCEPTED_NOT_RECORDED = "accepted_not_recorded"
    REPLAYED = "replayed"
    REJECTED = "rejected"


class HostControlReasonCode(StrEnum):
    RECORDING_OFF = "recording_off"
    ONBOARDING_DISCLOSURE_TURN = "onboarding_disclosure_turn"
    PUBLIC_ARTIFACT_UNCONFIRMED = "public_artifact_unconfirmed"
    STORE_UNAVAILABLE = "store_unavailable"
    CAPACITY_EXHAUSTED = "capacity_exhausted"


class HostControlErrorCode(StrEnum):
    INVALID_JSON = "invalid_json"
    OVERSIZED = "oversized"
    UNKNOWN_SCHEMA = "unknown_schema"
    INVALID_TOKEN = "invalid_token"
    EXPIRED_TOKEN = "expired_token"
    REPLAYED_WITH_DIFFERENT_PAYLOAD = "replayed_with_different_payload"
    UNKNOWN_MESSAGE_TYPE = "unknown_message_type"
    INVALID_PAYLOAD = "invalid_payload"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    STALE_REFERENCE = "stale_reference"
    STORE_UNAVAILABLE = "store_unavailable"
    CAPACITY_EXHAUSTED = "capacity_exhausted"
    INTERNAL_ERROR = "internal_error"


class HostControlNextAction(StrEnum):
    CONTINUE = "continue"
    ACTIVATE_PRIMARY_SKILL = "activate_primary_skill"
    STOP_CONTROL_CALLS = "stop_control_calls"


class HostActionKind(StrEnum):
    NO_OP = "no_op"
    ADD_CONTEXT = "add_context"
    CONTINUE_TURN = "continue_turn"
    BLOCK_PROMPT = "block_prompt"
    WARN_USER = "warn_user"


class RecordingMode(StrEnum):
    LOCAL_PUBLIC_ARTIFACTS = "local_public_artifacts"
    OFF = "off"


class MetricsConsent(StrEnum):
    NONE = "none"


class InterventionClass(StrEnum):
    REFRAME = "reframe"
    CONFLICT = "conflict"
    WEAK_EVIDENCE = "weak_evidence"
    MISSING_ALTERNATIVE = "missing_alternative"
    COMPLETION_GAP = "completion_gap"


class FeedbackOutcome(StrEnum):
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"


class MetricEventName(StrEnum):
    JUDGMENT_STARTED = "judgment_started"
    CARD_RENDERED = "card_rendered"
    CARD_VALIDATED = "card_validated"
    RIGOR_CHANGED = "rigor_changed"
    INTERVENTION_EMITTED = "intervention_emitted"
    INTERVENTION_EXPLICITLY_ACCEPTED = "intervention_explicitly_accepted"
    INTERVENTION_EXPLICITLY_DISMISSED = "intervention_explicitly_dismissed"
    CONCLUSION_CHANGED = "conclusion_changed"
    TRACE_REQUESTED = "trace_requested"
    RUNTIME_DEGRADED = "runtime_degraded"


class DurationBucket(StrEnum):
    UNDER_50 = "under_50"
    MS_50_99 = "50_99"
    MS_100_249 = "100_249"
    MS_250_999 = "250_999"
    MS_1000_PLUS = "1000_plus"


class FeatureKey(StrEnum):
    # Participation and answer shape
    JUDGMENT = "judgment"
    MECHANICAL = "mechanical"
    MIXED = "mixed"
    EXPLICIT_METHOD = "explicit_method"
    CHOOSE = "choose"
    DIAGNOSE = "diagnose"
    EXPLAIN = "explain"
    CRITIQUE = "critique"
    FORECAST = "forecast"
    RECONCILE_EVIDENCE = "reconcile_evidence"
    PLAN = "plan"
    REVIEW_COMPLETION = "review_completion"
    # Structure and logical form
    AMBIGUOUS_TERMS = "ambiguous_terms"
    BOUNDARY_SENSITIVE = "boundary_sensitive"
    TANGLED_HIERARCHY = "tangled_hierarchy"
    CATEGORY_OVERLAP = "category_overlap"
    ARGUMENT_DISPUTE = "argument_dispute"
    COMPETING_EXPLANATIONS = "competing_explanations"
    EXPLICIT_RULES = "explicit_rules"
    EXCEPTION_PRONE_RULE = "exception_prone_rule"
    REPEATED_OBSERVATIONS = "repeated_observations"
    # Evidence and causality
    SOURCE_QUALITY = "source_quality"
    CONFLICTING_SOURCES = "conflicting_sources"
    NEW_EVIDENCE = "new_evidence"
    WEAK_SAMPLE = "weak_sample"
    TESTABLE_CLAIM = "testable_claim"
    CAUSAL_QUESTION = "causal_question"
    RECURRING_FAILURE = "recurring_failure"
    FEEDBACK_DELAY = "feedback_delay"
    CONFOUNDING = "confounding"
    # Decisions and uncertainty
    MULTIPLE_OPTIONS = "multiple_options"
    MULTIPLE_OBJECTIVES = "multiple_objectives"
    SINGLE_FEASIBLE_OPTION = "single_feasible_option"
    SEQUENTIAL_CHOICE = "sequential_choice"
    INFORMATION_PURCHASE = "information_purchase"
    IRREVERSIBLE_CHOICE = "irreversible_choice"
    DEEP_UNCERTAINTY = "deep_uncertainty"
    SENSITIVE_INPUTS = "sensitive_inputs"
    REFERENCE_CASES = "reference_cases"
    UNKNOWN_PROBABILITY = "unknown_probability"
    # Challenge, creation, and purpose
    CHOSEN_PLAN = "chosen_plan"
    FAILURE_RISK = "failure_risk"
    DISMISSED_OPPOSITION = "dismissed_opposition"
    HIDDEN_ASSUMPTIONS = "hidden_assumptions"
    STALE_OPTIONS = "stale_options"
    HUMAN_NEED = "human_need"
    TECHNICAL_CONTRADICTION = "technical_contradiction"
    COMBINABLE_DIMENSIONS = "combinable_dimensions"
    DUTIES_RIGHTS = "duties_rights"
    VALUE_CONFLICT = "value_conflict"
    PRACTICAL_CONSEQUENCE = "practical_consequence"
    USER_PROGRESS = "user_progress"
    # Learning and strategy
    TESTABLE_HYPOTHESIS = "testable_hypothesis"
    REPEAT_ITERATION = "repeat_iteration"
    GOVERNING_RULE = "governing_rule"
    PRIORITIZED_ASSUMPTIONS = "prioritized_assumptions"
    INTERACTING_ACTORS = "interacting_actors"
    MACRO_ENVIRONMENT = "macro_environment"
    STAKEHOLDER_CONFLICT = "stakeholder_conflict"
    CONTEXT_DISORDER = "context_disorder"
    # Contraindications
    BINDING_RULE_WITHOUT_DISCRETION = "binding_rule_without_discretion"
    NO_DEFENSIBLE_REFERENCE_CLASS = "no_defensible_reference_class"
    NO_TESTABLE_IMPLICATION = "no_testable_implication"
    NO_MEANINGFUL_INTERDEPENDENCE = "no_meaningful_interdependence"
    NO_COHERENT_DIMENSIONS = "no_coherent_dimensions"
    SAFETY_CRITICAL_VALIDATION = "safety_critical_validation"
    DECISIVE_INPUT_MISSING = "decisive_input_missing"


FAMILY_IDS = (
    "framing",
    "structuring",
    "logical_reasoning",
    "evidence_verification",
    "causal_systems",
    "critical_counterexample",
    "creative_reframing",
    "values_purpose",
    "decision_optimization",
    "future_uncertainty",
    "experiment_learning",
    "strategy_actors",
)
