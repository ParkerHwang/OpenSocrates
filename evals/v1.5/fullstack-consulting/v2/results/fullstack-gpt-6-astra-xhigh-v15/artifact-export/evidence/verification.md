# Verification record

Performed on 2026-09-27 using only synthetic local data. No helper agents/models, deployment, external database, or paid service was used. `TASK.md` and `TOOLING.md` were preserved.

## Route and persistence checks

Command: `python3 -m unittest -v tests.test_api`

**26 tests passed in 5.944 seconds** in the retained final run. Full names and output are in [api-tests.txt](api-tests.txt). Tests launch the executable `run.sh` on an ephemeral loopback port, communicate over HTTP, and use isolated persistent databases under `.local/`.

The suite checks all six identities, absent/invalid tokens, viewer mutations, operator adjustment denial, tenant-scoped reads/writes/retry keys/references, forged identity fields, integer validation, zero-price orders, invalid lines, duplicate references, stock floors, stale versions, cancellation, shipping, partial/full/excess returns, and dashboard agreement. Rejected mutations are compared against persisted inventory/order/line/audit/idempotency snapshots.

Concurrency tests use a barrier to start competing HTTP requests: two reservations exceeding combined stock, twelve identical creates and then twelve identical reservations, and two returns with the same expected version but different keys. They check statuses, balances, versions, and event counts.

Failure injection installs an SQLite trigger that rejects audit insertion after the business writes have started. The HTTP operation returns 500; the entire persisted snapshot remains unchanged. Removing the trigger and reusing the same key succeeds. This verifies rollback through the real application/database boundary.

Restart verification kills the running server after acknowledged order and stock mutations, starts `run.sh` again with the same directory and `SEED_DEMO=1`, and checks exact persisted business state, sessions, order values, dashboard, signed cursors, and original replay bodies. Stock does not reset. It also tests starting without seeding, then enabling seed on that still-empty store.

Pagination tests mutate a previously matching order's status and insert new matching orders between pages. The traversal returns every original match once, excludes later inserts, binds tenant/filter/collection, and rejects invalid/tampered cursors. Audit pagination similarly excludes new events until a new traversal.

## Browser checks

Command: `node scripts/browser.cjs`

**14 workflow checks passed** in the final run, with no JavaScript page errors. See [browser-tests.txt](browser-tests.txt) and [browser-results.json](browser-results.json). Chromium **148.0.7778.96**, Playwright **1.62.1**, Node **24.19.0**. The test connects to the supplied fresh browser via `EVAL_BROWSER_WS`; it closes its context and connection afterward.

* Login validation, normal operator login, stock/dashboard display, and role controls.
* Multi-line order creation, catalog total, reserve, ship, partial/full return.
* An external API return makes the UI stale; the stale submission returns 409, reloads the version, and preserves the entered return quantity for review/resubmission.
* A zero-price order reserves and cancels normally.
* Two immediate button clicks generate one create request.
* The test forwards a create request to the server, receives its 201, then deliberately aborts delivery to the browser. After page reload, the retained intent replays with the original key, leaving exactly one order and audit event.
* Client text resembling an HTML image/event handler appears literally, creates no image element, and executes no script. Search, status filtering, and empty state work.
* Audit events and returned inventory agree with API state; a reload restores the local session.
* An admin adjustment persists. An unfinished North adjustment form is cleared on logout before a South admin opens the form.
* A viewer can open order details and sees no mutation controls.
* South retains its independent original stock. Its full create/reserve/ship/return workflow works at 390×844 with no document-level horizontal overflow.
* Keyboard Tab/Enter completes login.

Screenshots were inspected at desktop and mobile sizes: [inventory](desktop-inventory.png), [order](desktop-orders.png), [audit](desktop-audit.png), [mobile order](mobile-order.png), [mobile inventory](mobile-inventory.png). Wide tables scroll within panels. This verifies an actual usable browser flow; it is not a full screen-reader or cross-browser accessibility audit.

Two earlier harness-only failures are retained in `browser-first-attempt.txt` and `browser-second-attempt.txt`: one assertion ignored CSS capitalization, and a logout helper incorrectly waited for the authenticated shell after logout. Both assertions were corrected. The later review also found and fixed unsaved adjustment input persisting across logout; the final suite has a regression check. No known failing check remains.

## Performance exercise

Commands, run sequentially with fresh databases:

```sh
python3 scripts/load.py --concurrency 1 --output evidence/load-c1.json
python3 scripts/load.py --concurrency 8 --output evidence/load-c8.json
```

Environment: macOS **27.0**, **arm64**, **10 logical CPUs**, Python **3.12.14**, SQLite **3.53.1**. The sandbox did not expose the CPU model or physical RAM. Client and server share the host; this is not dedicated benchmark hardware. No browser/API suite ran concurrently with these measurements.

Each run seeds two tenants and 200 draft orders. Warmup is 100 reads plus 20 complete write workflows. The measured phases contain 30,000 reads and 6,000 five-request write workflows, respectively. Reads are evenly divided among inventory, dashboard, first-page orders, and first-page audit. Writes create BOLT quantity 2, reserve, ship, return one, then return the other. Authentication and startup are outside the timing window. All SQL writes use WAL and `synchronous=FULL`.

One persistent HTTP/1.1 loopback connection per worker issues closed-loop requests without think time. Throughput counts HTTP requests, not entire fulfillment workflows. Latency includes request transmission and reading the full response body. Percentiles use linear interpolation. The scripts record status counts and fail on unexpected HTTP/network errors or final-state mismatches.

| Workers | Phase | Requests | Seconds | Requests/s | p50 ms | p95 ms | p99 ms | Max ms | Errors |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Reads | 30,000 | 14.6746 | 2,044.35 | 0.476 | 0.589 | 0.644 | 1.495 | 0 |
| 1 | Writes | 30,000 | 38.2949 | 783.39 | 1.250 | 1.468 | 1.587 | 33.653 | 0 |
| 8 | Reads | 30,000 | 16.5415 | 1,813.62 | 2.967 | 8.034 | 20.097 | 28.782 | 0 |
| 8 | Writes | 30,000 | 12.1430 | 2,470.57 | 0.622 | 2.986 | 42.739 | 3,109.846 | 0 |

Both runs produced exactly **30,300 audit events**, **200 draft orders**, **6,020 returned orders**, restored both tenants' original stock, left zero reservations, passed `PRAGMA integrity_check`, and had no foreign-key violations. All warmup requests also succeeded. Raw measurements and full distributions are summarized in [load-c1.json](load-c1.json) and [load-c8.json](load-c8.json), with text copies alongside them.

Eight workers increased aggregate write throughput but exposed a **3.11-second maximum write latency**. Reads did not scale upward in this run. SQLite's single-writer model, Python/HTTP scheduling, connection setup/checkpoint behavior, and this finite local workload limit interpretation; no profiler isolated their individual contributions. These are observations, not an SLA, universal capacity claim, saturation test, or large-database benchmark. The read phase uses the pre-write dataset; the write phase grows to 6,220 orders. There was no sudden-power-loss, disk-failure, prolonged-soak, or remote-network test.

## Other checks and remaining scope

The following commands passed: `python3 -m compileall -q depotflow tests scripts`, `node --check depotflow/static/app.js`, `node --check scripts/browser.cjs`, and `sh -n run.sh setup-browser.sh`. `./setup-browser.sh` passed using the supplied installed-Playwright/remote-browser path; its external download/launch branch was not exercised in the restricted shell.

The runtime requires no dependency download or build. The recorded checks establish the requested local workflow and the exercised failure/interleaving cases. Finite tests are not a proof over every schedule. Internet deployment, TLS, account provisioning/reset, migrations, automated backups, external shipment/payment integrations, token-copy revocation on logout, disk corruption, and power-loss recovery remain outside the delivered local scope. See [architecture.md](../architecture.md) for these design limits and the actual authentication/transaction contracts.
