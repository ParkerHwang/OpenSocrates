# Data and interface contracts

All names in this document are proposed v1.5 contracts. Implement strict generated
schemas from canonical sources under `schemas/source/`; do not hand-edit generated
schemas. Do not extend the closed v1 judgment-event union with arbitrary memory
dictionaries. Version the memory schemas independently of canonical method content.

## Record envelope

Schema identifier: `opensocrates.project-memory.record/1.0.0`.

| Field | Type / values | Meaning |
| --- | --- | --- |
| `schema` | fixed versioned string | Exact record schema identity |
| `record_id` | UUID | Opaque, stable identity of the memory item |
| `version` | positive integer | Monotonic item version; compare-and-swap target |
| `project_id` | UUID | Registered project, never a remote URL |
| `kind` | `decision`, `observation`, `lesson`, `checkpoint` | Record category |
| `scope` | object | `level`: `project`, `workspace`, or `task`; optional bounded source paths; required workspace/task IDs where applicable |
| `lifecycle` | `proposed`, `accepted`, `superseded`, `archived` | Record lifecycle; not truth or freshness |
| `origin` | object | Producer, source reference, and attribution/attestation level |
| `support` | `runtime_observed`, `tool_reported`, `agent_reported`, `inferred`, `imported` | How supporting evidence was obtained |
| `freshness` | `current`, `stale`, `unknown`, `not_applicable` | Relation to a checked source footprint |
| `summary` | bounded text | Public decision/fact/lesson; no private reasoning narrative |
| `rationale` | bounded text or null | Concise public reason, tradeoff, or failure condition |
| `source_refs` | bounded array | Typed references defined below |
| `snapshot_id` | UUID or null | Source snapshot for source-dependent records |
| `revalidation` | object | Dependency footprint and invalidation conditions |
| `created_at`, `updated_at` | UTC timestamps | Record metadata; recency is not authority |
| `supersedes` | UUID or null | Explicit replaced record; preserve history until retention/delete |
| `conflict_ids` | UUID array | Unresolved contradictory intent/observations |
| `payload` | typed object, checkpoint only | Checkpoint-specific fields; forbidden for other kinds |

All objects reject unknown fields. `origin`, snapshot, support, and freshness
fields returned by runtime observation are runtime-owned. An agent submission
cannot claim runtime observation by setting a field. Imports cannot set accepted
human authority or native execution evidence without the matching acceptance or
adapter path.

Acceptance means the item was adopted for its stated use; it does not upgrade an
inference into an observation. A decision enters `accepted` only through explicit
acceptance with an attributed user/maintainer basis. An agent recommendation stays
`proposed` until then. If the host cannot attest to a user instruction, record
`agent_reported_user_instruction` as the acceptance attribution, not native proof.
The memory service cannot prove natural-language consent from a caller's assertion.
It must make that limitation inspectable and never silently auto-promote a record.

Current user instructions and applicable repository policy continue to govern the
task. Accepted memory is not an instruction-hierarchy escalation mechanism.

## Source references and snapshots

A source reference has `ref_id`, `type`, `locator`, `digest`, `collected_at`,
`collector`, and `coverage`. Types are `source_file`, `repository_document`,
`project_document`, `tool_result`, or `decision_reference`. File locators use project-relative paths,
optional qualified symbols, and optional line anchors. Line numbers are a display
aid; digests and symbol re-resolution detect changed source. Do not store absolute
private paths in exports or published evidence.

The runtime may observe source-file bytes and their identity. A saved tool-result
file proves only those bytes exist; it does not prove the described command ran.
`tool_reported` execution requires an available trusted host adapter. Otherwise
record test outcomes as `agent_reported`, with a bounded summary and references.
Never execute command text read from a memory item.

Snapshot schema: `opensocrates.project-memory.snapshot/1.0.0`.
Required fields: `snapshot_id`, `project_id`, `workspace_id`, `workspace_kind`, `head_oid` or null,
`scope_paths`, `inventory_digest`, `content_manifest_digest`, `exclusion_digest`,
`configuration_digest`, `adapter_versions`, `coverage`, `captured_at`.
Coverage contains `complete_for_scope`, omitted categories, unstable files, and
the allowed search boundary. A dirty/untracked manifest must be represented;
HEAD equality cannot stand in for it. Source content itself is not persisted.

`workspace_kind` is `git_worktree` or `directory`; non-Git snapshots require null
Git metadata and a complete declared file inventory/content footprint. Git fields
cannot be fabricated for a directory project. The registry owns the discriminator.
Snapshot checks bind to the current registered workspace. Native observations
collected while the worktree changes must be rejected or labeled unstable.
Revalidation of an incomplete scope cannot produce `complete_for_scope: true`.

## Checkpoint payload

A checkpoint is a record with `kind: checkpoint`, task scope, and a typed payload:

- `objective`, `constraints`, and `completion_conditions`;
- `completed_actions` with evidence references and status;
- `remaining_actions`, `next_action`, and material blockers;
- `decision_refs`, `source_refs`, `snapshot_id`, and unresolved conflicts;
- `pending_effects`, distinguishing planned, attempted, confirmed, and unknown;
- `parent_checkpoint_id` and `checkpoint_version`.

`checkpoint_version` belongs to the stored/returned checkpoint. Requests submit
only `expected_checkpoint_version` (zero for creation); the transaction assigns
the new version and returns it. Reject a caller-supplied new version rather than
letting the caller overwrite the concurrency contract.

Each action separates `execution_state` (`not_started`, `attempted`, `completed`,
`unknown`) from `support` (the record support vocabulary). A reported completed
test remains agent-reported unless an execution adapter supplies stronger evidence.
Collecting source bytes does not establish that an agent read or understood them.

Do not retain chat excerpts, raw tool responses, hidden reasoning, credentials,
or speculative execution claims. Checkpoints are operational state, not evidence
that a planned side effect happened. The latest committed checkpoint is loaded;
uncommitted partial writes are never served.

## Proposed command boundary

Source form: `python -m opensocrates memory` reads one JSON request through EOF and
writes one bounded JSON response. Installed equivalents are proposed extensions
`bin/launch.sh memory codex` and `node bin/launch.mjs memory codex`.
They are not existing v1.4 commands. Update each launcher's allowlist and native
tests explicitly. The npm installer remains a lifecycle surface, not the JSON
memory protocol. A separate MCP server is not required for v1.5.

Request schema: `opensocrates.project-memory.request/1.0.0`.
Envelope fields: `schema`, `operation`, `request_id`, `project_id`, `workspace_id`,
`task_id`, `payload`. Required identities depend on the operation. `init` is the
only operation accepting a new root binding. Other operations resolve approved
scope through registry identities, not arbitrary traversal paths.

Enrollment uses `init` with `apply: false` by default: return the resolved owned
root, policy disclosure, and a digest of that exact scope/policy without creating
state. `apply: true` requires the matching disclosure digest and an
`authorization_basis` identifying the explicit user/operator instruction reference.
This is a bounded reference such as `user:current-request` or `fixture:enrollment`,
not the instruction sentence. The same rule applies to `acceptance_basis`.
The syntax is `[a-z][a-z0-9_-]*:[A-Za-z0-9._/#-]{1,120}` with a 1024-character
overall bound; credential/content prefixes `api_key`, `password`, `secret`,
`token`, `prompt`, `transcript`, `credential`, `cookie`, and `reasoning` are
forbidden. The generated memory request schema now expresses the existing
runtime restriction. A pointer does not itself establish authorization.
The runtime recomputes the binding before applying. A digest proves disclosure
identity, not consent. Record `operator_declared`, `agent_reported_user_instruction`,
or `host_attested` provenance as actually available; callers cannot set the latter
without an attesting adapter. `status` exposes this distinction.
The caller must already have authorization; an `enable: true` flag is not proof.
This technical preview/apply sequence does not require asking again when the user
has already explicitly authorized enrollment. Existing enrollment policy/mode
changes require its current expected version and the new matching disclosure.

Responses include `schema`, `request_id`, `status`, `result`, `limitations`, and
`retryable`. Responses never report actual model understanding/application as
verified. A request ID correlates responses; mutations separately require an
`idempotency_key` and the relevant expected version.

| Operation | Inputs and behavior | Mutation |
| --- | --- | --- |
| `init` | Preview/apply, explicit root, policy/version, mode, exclusions, disclosure digest and attributed authorization; returns identities/disclosure | Creation or policy update only on authorized apply |
| `status` | Registered identity or explicit lookup root; returns enabled/capability/schema state | None; no creation |
| `observe` | Registered scope, typed file/symbol/search descriptor; collects bounded current references | Validated observation/index entries |
| `record` | Typed proposed decision/lesson or reported observation with source refs | New record/version; cannot forge acceptance/support |
| `accept` | Record ID/version and attributed explicit acceptance basis | Lifecycle transition, never evidence promotion |
| `checkpoint` | Typed task payload, expected version, idempotency key | Atomic checkpoint version |
| `recall` | Question or typed need, task/scope, budget, requested snapshot validation | No authoritative-record writes; see refresh rule below |
| `refresh` | Explicit stale scope/record/index generation | Replace derived index or append revalidated observation |
| `inspect` | Record/project/retention selector | None |
| `supersede` | Old/new record IDs, expected versions, public reason | Transactional replacement link |
| `export` | Scope/format/cursor; returns bounded export content inside JSON `result` | None inside store; destination write is caller-owned |
| `disable` | Project ID and current policy version | Disable automatic context use/capture; retain management access and data |
| `delete` | Exact record/task/project scope, expected identity/version, explicit delete intent | Logical removal plus managed-storage cleanup |
| `prune` | Explicit retention policy and dry-run/apply | Bounded cleanup; accepted decisions preserved by default |

`recall` may read current source to validate candidates. It does not persist a new
belief or initialize a cache. If a reusable derived refresh is needed, return
`needs_refresh` and a bounded follow-up operation. The active agent may perform
that operation under existing project policy; no new per-item interview is required.
Automatic observation/checkpoint writes are allowed only after enrollment and
within its declared capture policy. Semantic acceptance is separate.

Export always preserves the one-JSON-response wire contract. `result` contains
`format`, `content`, `next_cursor`, and a record-version snapshot identity. Markdown
is an escaped string; JSON is a structured value. Each page is bounded to 64 KiB
including its envelope. Pagination must preserve the same versions or fail with a
conflict; oversized single items return `budget_insufficient`. The caller chooses
whether and where to save the returned content under normal tool permissions.

### Modes and management operations

| Operation class | `disabled` | `read_only` | `read_write` |
| --- | --- | --- | --- |
| Status/capabilities | Allowed, no initialization | Allowed | Allowed |
| Automatic recall/context use | Forbidden | Allowed, no persisted refresh | Allowed |
| Record/observe/checkpoint/index refresh | Forbidden | Forbidden; transient source validation is allowed | Allowed within capture policy |
| Explicit inspect/export/delete | Allowed only as a directly requested management action | Same | Same |
| Explicit mode/policy changes and prune | Allowed management action with version/intent checks | Same | Same |

No automatic capture occurs in disabled/read-only modes. Management access does
not re-enable automatic memory use. A missing store remains missing after status,
recall, inspect, or export. Disablement is not deletion. Preserve a management path
for viewing/removing data even when automatic memory use is disabled.

## Evidence pack

Schema identifier: `opensocrates.project-memory.context-pack/1.0.0`.
Return `pack_id`, project/workspace/task identities, workspace kind, checked snapshot, applicable
constraints, decision summaries, source evidence, checkpoint reference, conflicts,
unknowns, searched/excluded scope, capability levels, budget accounting, and
expansion handles. Every substantive item has a record or source reference.
Evidence citations include their usable relative locator and digest in the pack;
an unexplained opaque ID alone is insufficient for a source-affecting conclusion.

`delivery: emitted` and `application: unverified` are separate from source
freshness. A source-correct pack can still be misused by the model. Optional
reported-read acknowledgment is not persisted as transferable proof of reading.
After a fresh context/compaction/handoff, load needed content again.

## Initial engineering limits

These are proposed defensive defaults, not measured performance claims. Freeze
them for an evaluation; tune only in a new versioned run.

| Boundary | Initial default |
| --- | --- |
| Request | 256 KiB UTF-8; one complete JSON document |
| Record public text | 8 KiB combined summary/rationale; 32 source references |
| Checkpoint payload | 16 KiB; bounded action/ref lists |
| Context pack | 64 KiB UTF-8 maximum; caller may request less |
| Single source file for indexing | 1 MiB; larger files require targeted bounded inspection |
| One refresh | 2,000 files / 32 MiB decoded text / 10 seconds, whichever first |
| Derived index per project | 256 MiB; eviction/rebuild does not remove authoritative records |
| One database lock wait | 2 seconds; return busy rather than block indefinitely |
| Transient artifacts | Delete on completion; crash-recovery cleanup on next explicit memory operation |

Limits apply before parsing/allocation where practical. Report omitted material.
Do not estimate true GPT-6 tokens using the legacy whitespace counter and label
them exact. Byte bounds are deterministic; optional token estimates state their
method, and model usage is measured separately.

## Error contract

Statuses include `ok`, `disabled`, `needs_refresh`, `partial`, `conflict`,
`budget_insufficient`, `busy`, `unavailable`, and `invalid_request`.
Reasons use a closed vocabulary such as `identity_mismatch`, `stale_snapshot`,
`scope_incomplete`, `unsupported_schema`, `unsafe_path`, `permission_denied`,
`store_corrupt`, `version_conflict`, and `source_changed_during_read`.

Native protocol exits: 0 for a well-formed response including disabled/partial;
2 for invalid requests; 3 for operational unavailability. Callers MUST inspect
status and requested semantic conditions, not just process exit. Human-readable
errors must not print raw prompts, content, credentials, or private root paths.

## Assistance interface separation

The stateless assistance request/response in 11 has its own closed schema family.
It reuses bounded JSON parsing/error conventions, not the memory envelope or a
new field in the existing closed `decision` envelope. It performs no memory writes
or source inspection. A memory pack budget is advisory to retrieval and remains
subject to the required-context/partial-result contract above.

## Illustrative examples

The files in [examples](examples/README.md) use synthetic IDs, locations, and
digests. They demonstrate record separation and pack evidence boundaries; they
are not runtime-validated schemas or observations from this repository.

## Additive structural revision

The [2026-09-27 revision](12-structural-revision-and-official-docs.md) adds separate
closed v1.1 assistance/memory requests and a v1.1 recall projection. Existing v1.0
schemas and stored records remain supported. The new assistance request carries
at most eight public obligations; its plan separates required blockers, pending
inputs and ready work without promoting caller reports into native evidence.
The memory `prepare` operation reads current schema/version without migration or
mutation. V1.1 recall returns lifecycle/support plus bounded checkpoint metadata.
Requested paths filter delivered source evidence; original snapshots retain their
full revalidation footprint. A source scope never deletes applicable accepted intent.
The separate documentation command is stateless and uses authorized host tools
for actual source reading. Frozen historical protocols are unchanged.
