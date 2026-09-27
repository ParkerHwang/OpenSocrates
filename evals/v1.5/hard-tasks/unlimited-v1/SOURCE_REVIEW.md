# Source and artifact review notes

Status: independent coding qualification, office review and server performance
are complete. These notes distinguish source observations from
the measured checks.
No outcome artifact is edited. Human scores remain unavailable; semantic judgments
are provisional and unblinded.

## Completed Luna/medium office pair from the predecessor boundary

The predecessor's locked `review/office-batch1.assessments.json` records all public
messages, memo/source citations and separate deterministic checks.

- Guide9 passes27/27 original groups and preserves all72 active people, including
  the restored P072. Guide8 passes26/27: P01 correctly detects its71-row roster,
  which omits P072 despite approved change H04.
- Guide9's memo line15 reverses the meaning of H02/H03: P010 becomes mandatory
  and P061 optional in the source and JSON, while the memo says the opposite.
  Its earlier public61-mandatory count is corrected in the next message; this
  corrected transient statement is separate from the persistent memo error.
- Guide8's memo line18 retains the wrong11-optional count and claims P072's
  reinstatement/access update was applied despite its missing row. H04 restores
  active status; the access change H05 concerns P064.
- Both supplemental workbook checks find no currency format on inspected count
  fields. Both preserve the pending signature and continue authorized preparation;
  no unnecessary user question appears in the13/6 available public messages.
- A read of the revised assistance/verification reference is not observed. Guide9
  makes no observed native decision invocation; it incorrectly describes launcher
  integration as unavailable. Guide8 invokes the available decision launcher once
  without JSON input and receives no structured response. These are delivery/use
  limitations, not evidence that the native runtime is unavailable. The controller
  SKILL bytes are identical across packages; their decision guides differ.

The strict-score difference is a bounded artifact observation, not proof that
guide9's new verification reference caused it. Neither memo is fully factually
reliable. Provisional primary rubric totals16/20 and14/20 do not replace these
material findings or the objective scores.

## Luna/max coding continuations: observed source structure

The generated input locks precede this review. Both completed continuations pass
their own `go test -race ./...` command. Guide8 passes27/28 API groups and guide9
passes28/28. Guide8's alternate-legacy simultaneous start exits with SQLite BUSY;
the failure remains, with no retry to obtain a pass. Both performance results are
diagnostic: guide8 fails this functional gate, and guide9 has two write warmup
failures despite functional success. See [all measurements](METRICS.md).

- Guide8 uses `internal/ledger/http.go` and `store.go`; guide9 separates
  `internal/platform/http.go`, `writes.go`, `history.go`, `migrate.go` and types.
  File count is not a maintainability score: the latter package still owns
  transport, domain and persistence responsibilities together.
- Both preserve `platform.Open`, matching the original `driver_test.go` caller.
  This source observation requires the actual own-suite command before a pass.
- Guide8's `http.go:270` idempotent wrapper starts an immediate write transaction,
  checks cached replies before business mutation, and inserts the status/body in
  the same transaction. Guide9's `writes.go:20` mutate wrapper has the same atomic
  boundary using `sql.Tx` and a shared mutation callback. Reuse here is supported
  by actual effect boundaries, not similar names or a style label.
- Guide9's `history.go:193` explicitly begins a deferred transaction on one
  connection for historical reads, separately from its immediate write default.
  Merely seeing `_txlock=immediate` in the DSN is insufficient to claim that every
  read takes a writer lock.
- Guide8 configures WAL/full synchronization and16 pooled connections in
  `driver.go`; guide9 configures32 connections and explicit deferred read scope.
  Workload-specific performance must be measured before inferring a winner.
- Both retain only the provided Go driver smoke-test file in these snapshots.
  There are no retained additional Python integration-test files beyond the legacy
  producer and native adapter. Inline test commands exist in the public receipts;
  do not equate them with a maintained regression suite or claim no checking occurred.
- The guide9 continuation emits native `catalog`, `prepared`, then valid
  `no_intervention` projections. Guide8 emits catalog, two invalid-request
  rejections, then deduction selection. This observes use of request preparation
  and valid non-intervention; it does not establish a universal quality/efficiency
  effect or native proof of method application.

Driver-option judgments use the pinned `modernc.org/sqlite@v1.59.0` source.
Its `applyQueryParams` supports `_busy_timeout`, `_journal_mode`, `_foreign_keys`
and `_txlock` shorthands. The offline common cache passes `go mod verify`.
Claims that these options are necessarily ignored would be incorrect for this
version. This inspection did not modify the cache or supply feedback to subjects.

## Fresh Luna/medium coding pair

Both own-suite commands pass, but the independent checks find23/28 guide8 and
25/28 guide9. These are generated-program defects, not native OpenSocrates defects.

- Guide8 accepts an explicit null opening as zero, returns500 instead of404 for a
  missing/cross-tenant account, and returns the original transfer with
  `reversed:false` after reversal. These are explicit request/response contract
  failures. Its concurrent alternate-legacy startup also exits with SQLite BUSY.
  The source audit narrows the input defect to null: its generic required-field
  helper correctly rejects an absent field but unmarshals null into the integer
  zero value. Do not report the unobserved missing-field failure.
- Guide9's hold response has stale `available:100` after reserving80 from a100
  balance. In `internal/platform/api.go:323`, Reserved/Version change but Available
  is not recomputed before returning the existing Account value. `getAccount` at
  line349 derives Available when loading, so the observed group failure establishes
  a wrong response projection, not by itself successful overspending. The frozen
  group stops at that failed assertion; do not claim later assertions ran.
- Guide9 accepts `/summary?wat=1` with200. Its existing `checkQuery` helper is used
  by `readEntries` but not by `summary` at line548: a concrete reuse/coverage gap.
  Its concurrent alternate-legacy startup also exits with SQLite BUSY.
- Guide9 adds persistent HTTP-flow and concurrent-idempotency tests in
  `api_test.go`; guide8 retains only the provided driver test. The flow test takes
  the new hold ID but does not assert the returned available amount. Test presence
  is useful, but it does not close an omitted response-field contract.

## Sol coding pair and incomplete delivery

Both retained Sol artifacts pass28/28 independent groups and their own race-test
commands. The guide9 model turn ended with provider capacity failure; its complete
artifact checks must not relabel that call as a successful CLI completion.

Guide8 retains four Go tests for ledger/history, concurrent shared DB, replay/
tenant isolation and migration in `cmd/server/main_test.go`. Guide9 places the
main implementation in `internal/ledger/ledger.go` with a thin main, but retains
only the provided driver test. This is a source-structure and retained-test
observation; the service-interrupted guide9 call may not have reached its intended
final handoff. Do not score package-driven maintainability from module counts.

## Layer distinction

The implemented mechanical request preparation is exercised successfully in this
retest. API/roster correctness differences and persistent narrative errors are
separate observations. A recurring theme is failure to update a derived output
from its authoritative state: the stale hold Available field and the reversed HR
transition in a numerically correct office memo. This supports targeted data-to-
output reconciliation as a future design hypothesis, not a claim that more generic
instructions or more memory calls would fix every generated-program defect.
