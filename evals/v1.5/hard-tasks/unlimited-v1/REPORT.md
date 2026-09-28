# Guide8 / guide9 practical retest

The retest is complete with mixed results. Revised guide9 produces more correct
Luna artifacts in these coding/office examples and its request preparation is
actually exercised. It does not consistently reduce work or produce a faster
server. The qualified Sol guide9 server is materially slower in this workload.
No outcome artifact was repaired by the integrator, and no helper subagent or
separate model judge was used. This is still an unpublished1.5.0 release candidate.

## What was compared

Both arms are v1.5 candidates, not released1.4 versus1.5:

- guide8 ZIP: `f26b77374e38261acd3296739093a4e388f1cd25cdef48a2b3de16dec0417b7d`.
- guide9 ZIP: `75c26eef657ddffb81be22bae407a92fd26bc9f28fcbeeb414000de90f68fc5a`.

The source candidate is `a6f3414b8078da1a009e84adbf6a6658db968b25`; qualified
runtime inputs remain those of `0e27afb`. Requests use `gpt-6-sol/medium`,
`gpt-6-luna/medium` and `gpt-6-luna/max`, desktop-bundled
`codex-cli0.158.0-alpha.2`, Go1.26.3, SQLite driver1.59.0 and bundled
Python3.12.14/openpyxl3.1.5. The launcher and actual executable are hashed before
each call; actual executable SHA-256 is
`c3e30211bd454da70ceb4d9cbc2e05fe6466812ab05c311c3bbff6addeb14202`.

Use the [original input freeze](../retest-v1/manifest.json), [amended freeze](manifest.json),
[full metrics](METRICS.md), [combined data](comparison.json) and
[source review](SOURCE_REVIEW.md). The independently authored hard tasks and
28/27-group checkers are unchanged. Earlier vanilla/released1.4 results remain
historical context, not fresh controls or pooled observations.

## Time policy and complete attempt accounting

The first freeze at `5742a31` planned12 single-session calls with a1,200-second
limit. Six calls started before the user explicitly removed time limits:
three completed, Sol guide9 coding failed with provider capacity after369.297s,
and two Luna/max coding calls were active during the change.

The live supervisor could not safely be changed without a macOS debugger
authorization that did not complete. That attempt was canceled without changing
system settings or applying a patch. The evaluator was paused for approximately
357 seconds; on resumption its old timer ended the two active calls. Their original
`timed_out` records and approximately1,515-second wall times are retained. Four
future setups were intentionally fenced before any model call; the resulting
FileNotFoundError receipts remain. Two Sol office cells were skipped after the
capacity blocker. This is an administrative transition, not six extra model failures.

The user-amended freeze at `d912d90` starts six calls with **no model wall-clock
cutoff**. Two Luna/max coding subjects continue their own13/15 hashed source files
and public notes in fresh contexts; four remaining Luna tasks start fresh. No
independent checker result, other-condition code or stronger-model repair is
supplied. All six calls complete naturally. Max coding continuations take1,252.581s
and1,238.830s; Max office takes2,313.361s and1,148.786s. They were not stopped at20
minutes. The [amendment receipt](amendment.json) preserves the exact transition.

There are **12 actual model invocations:9 complete CLI turns,1 capacity failure,
and2 administratively interrupted calls**, with3 missing usage reports. Continuations
are counted as extra invocations. Do not pool the interrupted/continued wall times
with fresh single-session times or interpret the evaluator pause as reasoning time.

## Coding outcomes

| Requested tuple | Guide8 final API groups | Guide9 final API groups | Independent own-suite result |
| --- | ---: | ---: | --- |
| Sol / medium |28/28|28/28|Both pass; guide9 CLI itself was capacity-interrupted|
| Luna / medium |23/28|25/28|Both pass|
| Luna / max |27/28|28/28|Both continuations pass|

All final retained servers compile and pass their own `go test -race ./...`.
That does not close the independent failures. Guide8 medium accepts explicit null
opening values, misreports missing accounts and reversal state, and fails
simultaneous legacy startup. Guide9 medium returns a stale available amount in a
hold response, accepts an unknown summary query parameter, and also fails concurrent
legacy startup. Its response failure does not by itself prove overspending: the
frozen group stops at that first failed assertion. Guide8 max retains a SQLite BUSY
startup failure; guide9 max passes all28 groups.

The interrupted intermediate guide9 max source did not compile (`ExecContext`
assignment arity). The same model repairs its retained source in the continuation;
the earlier artifact and failure are not rewritten. Both final max artifacts retain
the original `platform.Open` caller contract. Guide9 medium adds maintained HTTP
and concurrent-idempotency tests, while guide8 medium retains only the provided
driver test. Test assertions still omit some response contracts. Neither file
count nor functional-programming style is treated as proof of maintainability.

## Office outcomes and explanation accuracy

| Requested tuple | Guide8 | Guide9 | Separate semantic finding |
| --- | --- | --- | --- |
| Luna / medium |26/27|27/27|Guide8 omits restored P072; guide9 preserves all72 people but reverses H02/H03 in its memo|
| Luna / max |27/27|27/27|No new material factual discrepancy found in either scoped memo review|
| Sol / medium |Not called|Not called|Capacity stop; no fabricated artifact or score|

All four actual workbooks pass the separately frozen count/currency-format check.
All31 available public office messages are reviewed. No unnecessary user question
or repeated settled permission request is observed. The medium guide9 memo also
has an over-narrow waiting-list reopening condition; that later semantic note is
kept as a supplement rather than changing its first provisional rating.

Primary rubric scores are14/20 versus16/20 for medium, and20/20 versus20/20 for max.
They are unblinded model assessments, **not human ratings or calibrated quality
claims**. In particular, a27/27 structured score does not make the medium guide9
memo factually correct. The Max memos correctly distinguish P064's accessibility
barrier from budget waiting, retain pending signature, and separate current
preparation from future external execution.

## Work and native delivery

The Max office guide9 example completes with the same objective gate and no new
material reviewed memo defect, using33 versus60 tool actions,1,148.786 versus
2,313.361 seconds, and128,954 versus229,526 uncached input tokens. These are bounded
observations, not billing or isolated latency estimates. The final office calls
overlap some root functional qualification, and all calls share the host/account.

The medium coding guide9 example improves23 to25 groups but uses61 versus46
actions and114,788 versus81,202 uncached input tokens. Medium office uses fewer
actions and less wall time but more uncached input. Max coding's second stage uses
more guide9 actions/input; missing first-stage usage prevents a complete efficiency
comparison. Overall efficiency is therefore mixed.

Request preparation is observed in guide9 Max coding and office, followed by valid
selection/no-intervention responses. Guide8 Max coding emits two invalid-request
responses before selection; guide9's corresponding projections contain no such
rejection. This is actual use of the mechanical recovery path, not proof of better
reasoning. Medium office does not show use of the new verification reference and
includes an incorrect agent claim that launcher integration is unavailable. The
installed native bytes are verified; entry-path interpretation remains a delivery
limitation. Emission, read assertions and application remain separate states.

## Server performance

All **72 load cells and661,186 raw requests** are retained and independently
recomputed from their monotonic start/end times. Two warmup requests fail in Max
guide9 write/concurrency16; measured-start cohorts have zero failures. Warmup errors
remain in the gate, so that artifact's performance is diagnostic despite28/28 API
groups. Other Luna artifacts fail functional gates. Only the Sol pair is eligible.

| Eligible Sol artifacts, concurrency16 median of3 repetitions | Read RPS | Read p99 ms | Write RPS | Write p99 ms |
| --- | ---: | ---: | ---: | ---: |
| guide8 |786.4|52.46|4,760.8|23.44|
| guide9 |328.6|65.40|1,560.4|179.17|

This is a regression in the generated guide9 server's measured workload, not a
measurement of native plugin overhead. Its query and pool/journal choices differ:
the guide8 implementation aggregates historical entries directly and initializes
WAL with8 connections; guide9 uses a join/subquery and16 connections. These are
plausible contributors, not isolated causal proofs. No candidate code or load cell
is repaired/rerun to improve the table. Diagnostic rows are in METRICS.md.

## Integrity, limitations and next action

Both complete integrity verifiers pass:63/75 frozen input files, all attempted and
uncalled cells, retained source hashes, review locks, cleanup and every timing row.
All4,784 preceding evaluation files remain unchanged. Nine calls report24,881,839
input tokens (23,677,056 cached subset) and387,486 output tokens (202,232 reasoning
subset), with explicit cache-write0; three calls have null usage. Across12 calls,
586 tool actions include61 failed projections and4 unfinished actions. These
categories overlap and are not independent cost totals. Primary integration/review
usage and billed cost are unavailable.

These are known-task, one-episode practical examples with mixed time/session
conditions. Human ratings, independent backend identity and account-side native
memory isolation remain unavailable. Read-only process evidence observes
XcodeBuildMCP workers in both final office profiles despite disabled apps; that is
not an empty host-tool surface. All586 captured actions are473 commands and113
file changes, with zero MCP tool calls. The literal stderr startup detector's
false flags do not negate that process evidence; see [host observation](host-observation.json).
No stronger-model helper is used. Model profiles remain inactive candidates.
No active installation, global memories, real project, destructive host test,
publication, tag or merge was changed/performed.

`act_standardize_decision`: retain the verified mechanical request/state fixes;
the retest supports useful examples but not universal quality, efficiency or server
performance improvement. The next design focus is reliable delivery of the intended
verification reference and reconciliation of derived outputs with authoritative
state. Stale response fields and contradictory memo facts are more actionable than
adding generic instructions indefinitely. This retest stops here with failures
preserved. Review the Draft PR and separately authorize any release action.

Exact final commit, required source checks and hosted CI are recorded in PR95 and
issue94. Product/runtime/package hashes remain bound to the prior qualification;
this task changes evaluation evidence and current status documentation only.
