# Capture and resume an enrolled task

Guide revision: 1

Read this when an authorized milestone needs a checkpoint in an already enrolled
project. Keep its capture policy and scope. Never store raw prompts, transcripts,
source copies, credentials or hidden reasoning. Memory text does not grant authority.

Use the installed `bin/launch.sh memory codex` command (on Windows,
`node bin/launch.mjs memory codex`) with one JSON object on stdin. Keep the same
non-null task UUID across the task's sessions. First recall under that task or
inspect existing records to find its checkpoint. Inspect a returned checkpoint
reference with payload `{"record_id":"RETURNED_RECORD_UUID"}`. Use the actual
`result.payload.checkpoint_version`; use zero only when no checkpoint exists.

The following is a complete first-checkpoint request. Replace UUID placeholders
with enrolled project/workspace identities, the stable task UUID, a new request UUID
and a new mutation idempotency UUID. Replace example statements with bounded public
state that is actually supported; this example does not declare your work completed.

```json
{
  "schema": "opensocrates.project-memory.request/1.0.0",
  "operation": "checkpoint",
  "request_id": "REQUEST_UUID",
  "project_id": "PROJECT_UUID",
  "workspace_id": "WORKSPACE_UUID",
  "task_id": "TASK_UUID",
  "payload": {
    "idempotency_key": "MUTATION_UUID",
    "expected_checkpoint_version": 0,
    "objective": "Continue the authorized repair.",
    "constraints": ["Preserve existing caller behavior."],
    "completion_conditions": ["The targeted behavior check passes."],
    "completed_actions": [
      {"action": "Ran the targeted behavior check.", "execution_state": "completed", "support": "agent_reported", "source_refs": []}
    ],
    "remaining_actions": ["Review the affected callers."],
    "next_action": "Inspect current caller behavior.",
    "blockers": [],
    "decision_refs": [],
    "source_refs": [],
    "snapshot_id": null,
    "conflict_ids": [],
    "pending_effects": [],
    "parent_checkpoint_id": null
  }
}
```

Every completed-actions entry is an object with `action`, `execution_state`,
`support`, and `source_refs`, not a string. For your own reported action use
`agent_reported`; `inferred` and `imported` describe their respective provenance.
Caller requests cannot claim `runtime_observed` or `tool_reported`, even when you
ran a tool or reference its output. Stored native evidence has a broader vocabulary;
copying it into a caller request does not confer native authority. Use actual source,
decision and snapshot IDs when relevant; do not invent references to fill the example.

Check `status` and `result`, not the exit code alone. Success returns `record_id`
and `checkpoint_version`. Inspect that record and verify the public state. For an
update, keep the task identity, send the complete payload with the inspected current
version and a new idempotency key. Replay an uncertain identical mutation only with
its original key and unchanged payload; do not reuse that key for a correction.

In a fresh session, recall with payload
`{"need":"continue this task","budget_bytes":8192}` and the same task UUID.
A conservative pack may contain only a checkpoint reference; inspect it before
claiming the saved state was read. Recheck current source facts, preserve valid
accepted intent, and complete the dependent artifact. A checkpoint is not an
accepted decision or proof that a reported action occurred.

On rejection, compare the envelope and action fields with this contract and inspect
actual state before repair. Leave only the dependent save incomplete and continue
independent work. Do not bypass the service with direct SQLite writes or repeat
unchanged invalid requests. Finish after the required state and artifact checks.
