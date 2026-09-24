# Authorized memory correction and forgetting

Guide revision: 2

Read this only when changing already enrolled project memory under the user's
existing authorization. Do not enroll another root, broaden scope, edit SQLite
directly, or store raw prompts, source copies, transcripts, or hidden reasoning.

Send each request as one JSON object to installed `bin/launch.sh memory codex`.
Keep the closed envelope: `schema` is `opensocrates.project-memory.request/1.0.0`,
`operation`, a new UUID `request_id`, enrolled `project_id` and `workspace_id`,
`task_id` (UUID or null), and `payload`. Operation-specific fields belong inside
`payload`. Use a new UUID `idempotency_key` for each new mutation intent; retry an
uncertain identical mutation only with its original key and payload.

First `inspect` with payload `{}` to list records, or `{"record_id":"UUID"}`
for one record. Use returned record IDs and **current** versions. Do not guess a
version from the number of prior commands. No record exists merely because it
was proposed in prose.

For an ordinary correction that should retain history, create and explicitly
accept a replacement under the authorized scope, then `supersede` with payload
fields `record_id`, `new_record_id`, `expected_record_version`,
`expected_new_record_version`, `idempotency_key`, and a bounded public `reason`.
Both records must already be accepted in the same project. Supersession preserves
the old summary/history and can still expose it in inspect/export.

For an explicit request to **forget** a fact, supersession alone is insufficient.
Records are the deletion unit. If a record mixes the withdrawn fact with enduring
intent, first create and accept a replacement containing only the retained public
intent, using the same scope. Then delete the exact old record. Do not put the
withdrawn fact into a replacement summary, rationale, checkpoint, or reason.
Do not delete the project or unrelated records to remove one fact.

For a source-independent public decision, the `record` payload has these fields:

```json
{"idempotency_key":"UUID","expected_record_version":0,"kind":"decision","scope":{"level":"project"},"summary":"Only the retained authorized intent","origin":{"producer_kind":"agent","source_reference":null,"attestation":"agent_reported"},"support":"agent_reported","source_refs":[],"revalidation":{"dependency_paths":[],"negative_claim":false,"on_change":"not_applicable"}}
```

This example uses project scope; preserve the actual original scope and relevant
source dependencies instead when they differ. Replace UUID placeholders. To
`accept`, use the returned `record_id` and current `expected_record_version`, a
new `idempotency_key`, an `acceptance_basis` identifying the actual authorization,
and `acceptance_attribution: "agent_reported_user_instruction"` when only the
agent reports the user's instruction. Do not claim host attestation.
`acceptance_basis` (and enrollment's `authorization_basis`) must be a bounded
reference, **not the instruction sentence**. For the user's actual current scoped
instruction, `user:current-request` is a usable reference; it is not proof of
authorization by itself. The exact `accept` payload shape is:

```json
{"record_id":"UUID","expected_record_version":1,"idempotency_key":"UUID","acceptance_basis":"user:current-request","acceptance_attribution":"agent_reported_user_instruction"}
```

Use the actual returned version and UUIDs. Reference syntax is a lowercase prefix
matching `[a-z][a-z0-9_-]*`, then `:`, then 1–120 characters from
`A-Za-z0-9._/#-`. Prefixes `api_key`, `password`, `secret`, `token`, `prompt`,
`transcript`, `credential`, `cookie`, and `reasoning` are forbidden. Do not put
raw instructions or sensitive content into a reference to make it fit.

The exact-record `delete` payload is
`{"intent":"delete_record","record_id":"UUID","expected_record_version":2,"idempotency_key":"UUID"}`.
The version `2` is illustrative; use the inspected current version. Check `status`
and `result` for every operation. If rejected, inspect the contract and actual
state before repairing the request; do not repeat guesses or switch to direct
database writes. A failure keeps only the dependent memory change incomplete.

Verify `inspect`, `export` with `{"format":"json"}` (including pagination), and
a relevant `recall`: the withdrawn summary must be absent and retained accepted
intent must remain. Deletion also removes managed history/backups for that record;
independent user exports and forensic recovery are outside this guarantee. Report
an unavailable or incomplete check accurately while completing independent work.
