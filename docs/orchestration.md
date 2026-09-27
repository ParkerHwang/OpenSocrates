# Optional specialized orchestration

The unpublished v1.5 candidate adds an explicit `orchestrate` command for bounded
text, source-code, JSON calculation and Markdown artifacts. It runs a fresh maker,
a different independent reviewer, approved read-only executable checks, and a third
fresh execution verifier. The primary agent owns classification, accepted intent,
permissions and final integration. Ordinary hooks and the default `decision`
command do not launch this workflow. Binary office authoring and visual rendering
are outside this adapter.

`run` consumes the caller's authenticated Codex usage. Selected task constraints,
scoped source contents, dependency artifacts, selected memory projections and full
role/domain guidance are sent to that client. Each role uses the exact same
caller-authorized model and effort; there is no fallback or role-specific override.
Configured identities are not independent backend attestations. Fresh processes
and a read-only tool sandbox do not establish account isolation or prevent every
unrelated file read. The adapter disables native memories, hooks, apps, plugins,
child agents and host skill discovery without changing global settings.

## Invocation and closed plan

Source invocation is `python -m opensocrates orchestrate`. Installed launchers are
`bin/launch.sh orchestrate codex` and `node bin/launch.mjs orchestrate codex`.
Both accept one complete JSON document on stdin. `operation: prepare` validates
and reads the bounded source context without model calls or candidate writes;
`operation: run` invokes the explicitly selected client. The qualified adapter
currently requires macOS and `codex-cli 0.158.0-alpha.2`, including its
`sandbox -P :read-only` boundary. Other clients/platforms return unavailable;
packaging on a platform does not imply that its orchestration adapter is supported.

Use the [complete example](../plugin-src/shared/orchestration/request.example.json)
and the closed [request schema](../schemas/v1/orchestration-request.schema.json).
Replace its absolute source/client/candidate paths and verify actual source
SHA-256 digests before running. The example's source `requirements.txt` contains
exactly `Reviewed candidate.` followed by LF. Its new candidate
folder must be outside the source root and must not already exist. The example
uses a zero-exit exact-line check, not a model-generated command. Choose an actual
host executable for every check and authorize its complete argument array.

A plan separates these axes:

- `domain`: `software`, `data`, `document`, `research`, or `unknown`;
- `task_kind`: `judgment` or `mechanical`;
- producer `role`: `design` or `production`; the runtime assigns distinct
  `review` and `execution_verification` roles to each artifact version.

Every unit names one producer, exact owned paths, dependencies, relevant source
IDs, governing requirement IDs, and public completion obligations. Top-level
`required_artifacts` rejects a requested artifact without an owner. Duplicate or
case-overlapping paths, missing dependencies and cycles are invalid. Mechanical
work skips optional reasoning/domain procedures, while independent acceptance
still runs. Unknown domains produce a classification gap; unrelated ready units
continue. A document requiring a program needs an explicit software unit.

`constraints` contains the full current accepted contract. `permissions` and
`prohibitions` describe the caller's existing authorization; their presence does
not prove consent. `specialists` explicitly selects zero to two complete software
procedures (`contracts`, `transitions`, `ownership`) for judgment work. There is no
mandatory general-method pass. Complete EN/KO role/domain references, relevant
verification guidance and selected procedures are delivered without truncation.
Request, source and assignment bounds fail closed instead of dropping constraints.

Scoped source files appear in each fresh working directory at
`inputs/<source-id>/<original-basename>`. Dependency and candidate files use their
owned relative paths at that directory's root. Each fresh context includes exact
input/guide hashes and the closed output contract. Reviewers do not receive maker
self-assessments, earlier ratings, or repair findings; execution verifiers do not
receive the review verdict. Only a repairing maker receives public defect findings.

## Checks, repairs and result files

Checks are caller-approved `argv` arrays with an absolute executable,
`authorization_reference`, covered `obligation_ids`, and `expected_exit_code: 0`.
A negative test must assert the expected rejection and then exit zero. Nonzero
exits cannot be declared a success because sandbox failures could otherwise be
mistaken for an expected program failure. Only these arrays run, through the
supported read-only sandbox with a controlled environment and network disabled.
V1 permits no filesystem-writing tests, including writes to temporary scratch.
The runtime rehashes candidate/dependency/source inputs after each check and role.
It never falls back to unsandboxed execution. Shell policy limits and the client's
account/backend boundary are separate.

The distinct verifier interprets actual exit/input-integrity/output-hash receipts.
It must cite `check:<check_id>` for every covering passed required check. Review
and verification findings bind exact artifact digest, requirement, file location,
expected/observed outcome, independent reproduction, impact and missing evidence.
Unknown or failed required obligations block qualification even if another check
passes. Missing executable coverage is unknown. A process exit alone is not a
semantic acceptance decision.

Only the coordinator writes candidate artifacts. Reviewers cannot patch them.
The designated producer repairs within `repair_limit` (0–2); every new version gets
fresh review and execution verification. Dependencies are produced only from
qualified versions. Changed sources or previously qualified dependencies invalidate
affected units and leave their recheck obligations open.

The new `candidate_root` contains:

- `versions/<unit-id>/v<number>/<owned-path>`: each returned artifact version,
  including unsuccessful versions, with explicit producer lineage in the response;
- `artifacts/<owned-path>`: only qualified final candidate bytes.

The bounded [response](../schemas/v1/orchestration-response.schema.json) retains
manifests, structured public findings, process failures, error-event counts and all
five exposed usage fields. Missing usage and unobservable backend attempt counts
are null. Raw JSONL, prompts, reasoning, stderr and test-output dumps are discarded;
the product does not save them. Temporary scoped inputs are removed after the role
or check. Returned artifact files are intentional deliverables, not memory records.
Client behavior outside the adapter's output handling remains part of the Codex
host boundary.

`integration_pending` means every unit qualified as a candidate. The adapter never
writes an existing project or claims final integration. The primary must integrate
authorized bytes, identify affected dependents and rerun their relevant checks and
independent acceptance on the exact final bytes. Existing project edits cannot be
routed through `candidate_root`. After manual changes, a fresh explicitly authored
plan may use `seed.author: external_author` with current final bytes for independent
acceptance. A controlled defective fixture uses `synthetic_fixture`; it is never
attributed to a model maker. Seeded units skip only the first maker call and retain
review, execution verification and bounded maker repair.

Exit 0 means the response was handled, including `blocked`, `partial`, and
`integration_pending`; inspect semantic statuses. Invalid input exits 2 and
operational unavailability exits 3. No model wall-clock cutoff is imposed; caller
cancellation is preserved. If capabilities are unavailable, the same validated plan
can be handed to a supported host. `prepare` or a fake adapter is not live completion.

## Scoped memory and qualification

`memory: null` uses the explicit caller-owned `handoff` plus current constraints.
An optional binding names an already enrolled project/workspace and selected
record IDs; it never enrolls, migrates or captures data. An empty ID list recalls
applicable records. A nonempty list narrows optional knowledge but cannot remove
applicable accepted decision constraints. Task and module scope remain binding.
Full summaries/rationales and applicable checkpoint constraints are preserved.
Overflow rejects the context instead of truncating accepted intent.

Eligible record IDs/versions freeze before production. Review contexts exclude
same-attempt self-assessment, checkpoints and lessons without independent evidence.
The projection keeps lifecycle, support, source freshness and `review_state`
separate. Existing records have no exact-version independent review receipt, so
`review_state` remains `unknown`. A lesson can use a JSON public rationale containing
`conditions`, `mechanism`, `exceptions`, `provenance`, and `evidence_refs`; this adds
no SQLite field or migration. Source-dependent knowledge is revalidated against
its original snapshot scope. Deleted or changed frozen records invalidate reuse;
a later run cannot retrieve a deleted record from an orchestration cache.

Missing/disabled/unavailable memory creates no storage and explicitly reports lost
continuity. The current plan constraints and handoff remain intact. Use existing
memory enrollment, capture, CAS, acceptance and deletion APIs for any separately
authorized persistence. Accepted does not imply independently reviewed or true.

`make orchestration-check` exercises deterministic routing, contexts, ownership,
failures, repair, memory and privacy with clearly labeled fake model adapters.
Actual model behavior, host delivery, native packaging and quality benefit require
their own exact-version evidence. The implementation uses documented
[noninteractive Codex primitives](https://learn.chatgpt.com/docs/non-interactive-mode);
that documentation does not substitute for real host acceptance.
