# Source review of the nine AuditLedger artifacts

The primary integrator reviewed these immutable snapshots unblinded after their
generation and deterministic checks were locked in
[coding-inputs.lock.json](review/coding-inputs.lock.json), following
[the frozen procedure](CODING_REVIEW.md). No candidate was repaired or given
stronger-model assistance. These are generated application findings, not defects
in the OpenSocrates Python runtime or its own SQLite migration implementation.

## Findings with demonstrated consequences

**Luna medium, vanilla: transaction ownership is broken in several related paths.**
`ServeHTTP` calls `mutate`, which commits business changes, and only then starts
another transaction to save the idempotency result. Concurrent duplicates can
therefore apply effects before the winning response is recorded. Within mutation
helpers, `a.account` reads through the pool instead of the active transaction, so
responses and later batch operations see pre-transaction state. The traces show
stale transfer/hold responses, incorrect staged version behavior and concurrency
failures. These are shared causes, not sixteen unrelated architecture defects.
See [the split commit boundary](results/coding-luna-medium-vanilla/snapshot/internal/platform/api.go#L190),
[the committing mutation wrapper](results/coding-luna-medium-vanilla/snapshot/internal/platform/api.go#L306)
and [the transfer helper](results/coding-luna-medium-vanilla/snapshot/internal/platform/api.go#L475).

That artifact also stores inferred opening balances in current accounts during
migration without applying the imported movements to those accounts. Imported
history and current balances disagree (for example100 versus83 in the genuine
legacy fixture). Reversal routes are a terminal-error stub, including missing and
other-tenant objects that should return404. The failed tenant fixture does not
demonstrate a data leak; its recorded failure is that wrong error code. Input
validation accepts a null opening as zero, and negative entry cursors are accepted.
See [migration](results/coding-luna-medium-vanilla/snapshot/internal/platform/api.go#L100),
[reversal stub](results/coding-luna-medium-vanilla/snapshot/internal/platform/api.go#L469),
and the unchanged [16 failed groups](results/coding-luna-medium-vanilla/acceptance.json).
It passes12/28 groups and its supplied driver smoke test; that smoke is not a
domain correctness suite.

**Luna medium,1.4: reversal provenance is stored on the wrong side for the terminal
check.** The original transfer gains `reverse_id`, but the newly created reversal
has neither a reversal-origin marker nor its own `reverse_id`. The next request
can reverse that reversal: group18 observes HTTP200 where409 `terminal` is required.
The shared `mutate` boundary correctly keeps business changes and retry storage
atomic, which is a substantial improvement over the vanilla artifact's structure.
See [reverse](results/coding-luna-medium-v14/snapshot/internal/platform/api.go#L579)
and [mutate](results/coding-luna-medium-v14/snapshot/internal/platform/api.go#L268).
Its27/28 result is preserved; it adds no Go domain tests.

**Luna medium,1.5: method admission is missing before the write path.**
`ServeHTTP` sends GET to reads and sends every other method into mutation handling.
The actual group28 trace creates an account with `PUT /accounts` and returns201,
although the contract permits only404/405 for that method. This is an unintended
state-changing path, not merely a response wording issue. The transaction-scoped
retry/body/application flow and reversal-origin marker are correct in the tested
cases. See [dispatch](results/coding-luna-medium-v15/snapshot/internal/platform/driver.go#L205),
[shared transfer rules](results/coding-luna-medium-v15/snapshot/internal/platform/driver.go#L521)
and [reversal provenance](results/coding-luna-medium-v15/snapshot/internal/platform/driver.go#L690).
The artifact passes27/28 groups but keeps HTTP, schema migration, domain changes
and driver setup in the same platform file, with no new Go domain tests.

Its read path also calls `DB.Begin()` on a pool configured with
`_txlock=immediate`. Thus a historical read acquires a write reservation rather
than using the same deferred-read design seen in other artifacts. All three
concurrency16 read repetitions retain warmup timeouts (6,2 and6 requests), even
though their measured-window failure counts are zero. The source mechanism and
observed failures agree, but the benchmark does not isolate locking from every
other host/query factor. See [pool configuration](results/coding-luna-medium-v15/snapshot/internal/platform/driver.go#L81)
and [read transaction](results/coding-luna-medium-v15/snapshot/internal/platform/driver.go#L757).

**Luna max,1.5: the driver refactor leaves a real caller uncompilable.**
The new `OpenReader`/`OpenWriter` API removes `platform.Open`, while the original
`driver_test.go` still calls it. The normal server build passes28/28 external
groups, but `go test -race ./...` fails with `undefined: Open`. This is an incomplete
refactor/integration check in the generated project, not a faulty evaluator
assertion. See [the new driver API](results/coding-luna-max-v15/snapshot/internal/platform/driver.go#L14)
and [the preserved caller](results/coding-luna-max-v15/snapshot/internal/platform/driver_test.go#L9).
The20-minute cutoff remains a separate incomplete CLI outcome. Performance is
diagnostic even if the measured server behaves correctly.

## Ownership, reuse and tests across every artifact

| Artifact | Observed reusable boundary | Test and maintainability assessment |
| --- | --- | --- |
| Sol medium / vanilla | `writeConn` owns an immediate SQLite transaction; `transfer` is shared by single, batch and reversal operations; capture has its reservation-specific path. | Two new domain tests cover replay, staged rollback, history, tenant lookup and genuine legacy preservation/restart. Main is a small entry point; most logic shares one ledger file. |
| Sol medium /1.4 | `transaction` takes an operation callback; request preparation is separate from application; single/batch transfers share `transfer`. | One broad domain test exercises replay, null versions, batch rollback, historical reads and hold release. Ledger package gives a reusable boundary, although its HTTP/domain/persistence file remains large. |
| Sol medium /1.5 | `sqler`, `transferApply`, lookup/save and entry helpers share transaction-scoped work. | All28 API groups and own test command pass, but the own suite contains only the supplied driver smoke. HTTP, migration and domain logic live in `cmd/server/main.go`; another consumer cannot import that command package as a domain library. This is a reuse/test-seam limitation, not an observed API failure. |
| Luna medium / vanilla | A shared transfer function exists, but its pooled reads and split commit boundary defeat staged-state reuse. |12/28; no added domain suite. Several ignored SQL errors and the reversal stub make short successful smoke output misleading. |
| Luna medium /1.4 | `mutate` owns retry lookup, business operation and retry storage in one transaction; single/batch share `makeTransfer`. |27/28; no new domain tests; reversal-origin identity remains wrong. |
| Luna medium /1.5 | Transaction-scoped `doTransfer`, explicit field readers and `reverse_of` preserve shared invariants. |27/28; no new domain tests; an HTTP method guard is missing. Generic driver setup also owns all application behavior. |
| Luna max / vanilla | Generic `mutate[T]` combines typed validation and an operation callback inside `writeTx`; migration/storage are separate from the HTTP module. |28/28 and driver smoke pass, but no added domain suite. One warmup load timeout remains; generation did not finish its CLI turn before cutoff. |
| Luna max /1.4 | Shared `writeState`/entry writer, typed parsers, migration and read modules give explicit responsibilities; single/batch use `performTransfer`. |28/28 and driver smoke pass; no added domain suite; CLI cutoff preserved. History reads materialize every prefix entry and accumulate with Go `big.Int`. |
| Luna max /1.5 | Separate HTTP, operations, store and types; `OptionalInt` preserves missing versus null and a staged account map supports sequential batches. Read/write pools are separate. |28/28 API groups, but the supplied test caller no longer compiles. No new domain suite and no completed CLI turn. More modules did not establish a complete refactor. |

The Sol vanilla [domain tests](results/coding-sol-medium-vanilla/snapshot/internal/ledger/ledger_test.go#L42)
and Sol1.4 [domain test](results/coding-sol-medium-v14/snapshot/internal/ledger/ledger_test.go#L15)
are actual behavioral assertions, not only tests of helper construction. Other
episodes may have run ad hoc shell checks; their command attempts are retained,
but no additional reusable test file is present in their snapshots. Public command
stdout is not comprehensively retained, so an old internal repair cannot be
reconstructed solely from its exit-code receipt.

Relevant positive source seams include the Sol vanilla
[shared transfer/reversal helper](results/coding-sol-medium-vanilla/snapshot/internal/ledger/ledger.go#L371),
Sol1.4 [transaction callback](results/coding-sol-medium-v14/snapshot/internal/ledger/ledger.go#L205),
Sol1.5 [mutation boundary](results/coding-sol-medium-v15/snapshot/cmd/server/main.go#L478),
Luna max vanilla [generic mutation boundary](results/coding-luna-max-vanilla/snapshot/internal/ledger/http.go#L194),
Luna max1.4 [write-state wrapper](results/coding-luna-max-v14/snapshot/internal/ledger/server.go#L605),
and Luna max1.5 [staged transfer rule](results/coding-luna-max-v15/snapshot/internal/ledger/operations.go#L146).
These are concrete forms of function reuse. Most domain transitions still perform
SQL directly; a broad claim of functional-core architecture would overstate what
was delivered. File counts and function syntax are not scored as quality.

## History and performance interpretation

The passing migration implementations preserve final account balances while
reconstructing historical openings and importing movements under a transaction.
The failing vanilla Luna medium migration confuses those two states. All original
legacy tables remain part of the independent preservation checks; a generated
program's failure there says nothing about OpenSocrates' own separately qualified
project-memory migration.

Read implementations differ materially. Sol1.4/1.5 and Luna max vanilla use SQL
aggregation over the entry prefix; Luna max1.4 scans the prefix into Go and performs
per-row arbitrary-precision arithmetic. Some artifacts use one connection and
others larger pools; journal/synchronous settings also differ. These are plausible
contributors to observed throughput/latency, not isolated causal experiments.
See [Sol1.4 SQL summary](results/coding-sol-medium-v14/snapshot/internal/ledger/ledger.go#L1075),
[Luna max vanilla SQL summary](results/coding-luna-max-vanilla/snapshot/internal/ledger/http.go#L891)
and [Luna max1.4 row accumulation](results/coding-luna-max-v14/snapshot/internal/ledger/reads.go#L142).

A suspected driver-option problem was refuted by inspecting the actual pinned
modernc.org/sqlite1.59.0 source: it supports `_busy_timeout` and `_foreign_keys`
aliases. They must not be called invalid based on recollection of an older driver.
The actual `platform.Open` caller break is independently demonstrated by compilation.
No extra model or candidate-repair call was made to settle either point.

## Product implications, with limits

This fixture supports a bounded observation: the Luna medium plugin artifacts
have stronger transaction ownership than its vanilla artifact, while Sol already
passes the same external suite in all conditions. It does not establish universal
version superiority, a validated profile or an isolated method/memory effect.
The candidate does not consistently improve reusable tests or module ownership.

The practical improvement targets are specific: make valid native request
construction and repair easier; preserve callers/tests when changing an interface;
keep shared transaction invariants executable; and cross-check narrative claims
and displayed units against structured results. Expanding generic instructions
or shortening text is not evidence that internal reasoning improves. The current
comparison finishes with its failures intact; further product changes require
their own focused qualification, not rewriting these generated artifacts.
