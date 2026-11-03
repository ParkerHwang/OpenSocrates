"""Shared constants for the public synthetic bench."""

from __future__ import annotations

CASE_SCHEMA = "opensocrates.v2-bench-case/1"
FIXTURE_SCHEMA = "opensocrates.v2-bench-fixture/1"
REGRESSION_SCHEMA = "opensocrates.v2-bench-regression/1"
ENVELOPE_SCHEMA = "opensocrates.v2-bench-envelope/1"
REPORT_SCHEMA = "opensocrates.v2-bench-report/1"
CONDITIONS_SCHEMA = "opensocrates.v2-bench-conditions/1"
REQUEST_SCHEMA = "opensocrates.v2-bench-request/1"
ATTESTATION_SCHEMA = "opensocrates.v2-bench-model-attestation/1"

# A parsed envelope is not evidence that a model ran.
MODEL_CALL_VERIFIED = "verified"
MODEL_CALL_UNVERIFIED = "unverified"
MODEL_CALL_NOT_APPLICABLE = "not_applicable"
MODEL_CALLS = (
    MODEL_CALL_VERIFIED,
    MODEL_CALL_UNVERIFIED,
    MODEL_CALL_NOT_APPLICABLE,
)

REASON_CODES = (
    "input_error",
    "model_unavailable",
    "model_error",
    "condition_fail",
    "needs_human_review",
    "scorer_error",
    "pass",
)

# Product skills under test must not be rewritten to demand these headings.
# The harness envelope carries section identity outside the user's artifact.
FIXED_ENGLISH_HEADERS = ("Recipient body", "Requester memo")

CONDITION_IDS = ("baseline", "output_brief", "reader_1x", "opensocrates_v2")

TRANSPORT_INSTRUCTION = (
    "Return only a JSON object with the keys schema, body, and requester_notes. "
    'Set schema to "opensocrates.v2-bench-envelope/1". '
    "body is the artifact in the language and format the user requested. "
    'Do not add the English headings "Recipient body" or "Requester memo" '
    "unless the user asked for those words. "
    "requester_notes is text for the requester only, or an empty string. "
    "This JSON envelope is a bench transport. It is not part of the skill."
)
