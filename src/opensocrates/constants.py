"""Normative size, count, and timeout limits shared by v1 contracts."""

from __future__ import annotations

MAX_NORMALIZED_EVENT_BYTES = 4 * 1024 * 1024
MAX_HOST_CONTROL_BYTES = 32 * 1024
MAX_HOST_CONTROL_RESULT_BYTES = 1536
MAX_EPHEMERAL_TURN_STATE_BYTES = 64 * 1024
MAX_RECORD_EVENT_BYTES = 64 * 1024
MAX_CARD_LINES = 14
MAX_CARD_SCALARS = 2200
MAX_CARD_GROUNDS = 5
MAX_CARD_UNCERTAINTIES = 2
MAX_CARD_FLIP_CONDITIONS = 2
MAX_CONTROL_DEPTH = 12
MAX_CONTROL_ACCEPTED_CONTROLS = 16
MAX_OBSERVATION_TAGS = 384
MAX_DURATION_MS = 86_400_000
MAX_REPAIR_COUNT = 1
MAX_SCHEMA_NAME_LENGTH = 128
MAX_SAFE_TEXT = 4096
MAX_REVIEWED_PROCEDURE_TEXT = 16_384

# The current capability registry is intentionally closed.  Keep this list in
# one place so profiles, schemas, and downstream adapters cannot drift.
CAPABILITY_KEYS = (
    "prompt_context_injection",
    "local_control_execution",
    "method_skill_invocation",
    "model_initiated_method_skill_activation",
    "method_invocation_observation",
    "post_tool_observation",
    "post_tool_batch_observation",
    "completion_candidate_observation",
    "bounded_completion_continuation",
    "compaction_reinjection",
    "published_artifact_confirmation",
    "local_record_write",
    "deterministic_trace_render",
    "rich_card_widget",
)
