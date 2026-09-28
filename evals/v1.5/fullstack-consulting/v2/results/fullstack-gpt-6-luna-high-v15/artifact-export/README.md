# DepotFlow

DepotFlow is a locally runnable two-tenant order and warehouse workflow. It
serves the browser UI and JSON API from one Python process and stores all state
in an embedded SQLite database.

## Run it

Requirements: Python 3.10+ with the standard library. No container, external
service, account, or package installation is needed.

```sh
PORT=8000 DATA_DIR="$PWD/data" SEED_DEMO=1 ./run.sh
```

Open `http://127.0.0.1:8000/`. `PORT` defaults to 8000; `DATA_DIR` defaults to
`./data`; `SEED_DEMO=1` initializes tenants and stock only when the database has
no tenants. Keep the same `DATA_DIR` to retain orders, stock, sessions, audit,
and idempotency records across restarts. The process binds to loopback only.

Demo accounts (all use `DepotDemo!2026`):

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

## Stack and design

- Python standard library HTTP server, SQLite, and plain HTML/CSS/JavaScript.
- SQLite is the source of truth. Tenant-scoped uniqueness and inventory checks
  are enforced in the database; the detailed invariants, transaction boundary,
  identity rules, and error behavior are in [architecture.md](architecture.md).
- Each state-changing request uses `BEGIN IMMEDIATE`. Order/stock changes,
  audit event, and idempotency response commit together. This keeps concurrent
  last-unit reservations safe and makes a retry replayable after restart.
- Static, same-origin UI with role-aware actions, order search/status filtering,
  multi-line creation, order transitions, returns, dashboard and audit history.
- Tradeoff: SQLite writer serialization is a simple reliable fit for a small
  local operator workflow; high-volume writes or multiple hosts would call for
  a different persistence tier. Demo credentials and non-expiring local bearer
  sessions are for this isolated synthetic deployment only.

## Verification

Run the actual-route suite from the project root:

```sh
python3 -m unittest discover -s tests -v
```

The suite starts and stops the real server using a fresh temporary SQLite file.
It covers authentication, tenant isolation, viewer authorization, integer and
SKU validation, zero-price orders, atomic multi-line reservation failure,
simultaneous reservation, stale versions, replay and payload conflicts,
partial/full returns, audit behavior, and restart durability/no reseed.

To exercise a real browser with the supplied local Playwright/Chromium setup:

```sh
node tests/browser_check.js
```

That check attaches to `EVAL_BROWSER_WS` (provided by the workspace tooling),
then logs in, creates/reserves/ships/returns an order, forces a stale-version
response and checks that its entered return quantity is retained, inspects
audit, checks a narrow viewport, and verifies the viewer has no create control.
No browser is launched by the shell. If running elsewhere, install Playwright locally and
provide a browser WebSocket endpoint, or adapt the small script to your local
browser runner.

The repeatable local read/write workload is:

```sh
python3 scripts/load.py --reads 800 --writes 200 --concurrency 8
```

It starts a fresh seeded server/database, concurrently performs inventory GETs
and uniquely keyed order POSTs, and reports throughput, latency percentiles,
and errors. The report includes OS, Python version, logical CPU count and
concurrency. Use the same command and machine for comparisons; this is an
in-process/local-loopback measurement, not a production capacity claim.

## Checks run for this delivery

- `python3 -m py_compile app.py tests/test_routes.py scripts/load.py` and
  `node --check static/app.js`: passed.
- `python3 -m unittest discover -s tests -v`: 1 end-to-end route test passed.
  It also restarts the server against the same DB to check persistence and that
  seeding does not overwrite stock.
- `node tests/browser_check.js`: passed with zero browser page errors; the
  workflow list is saved in [evidence/browser.json](evidence/browser.json), and
  route test output is saved in [evidence/routes.txt](evidence/routes.txt).
- Load run on macOS 27.0 arm64, Python 3.12.14, 10 logical CPUs, 8 workers:
  800 inventory reads plus 200 order writes completed in 0.4008 s, 2,495
  combined requests/s, 0 errors. Mixed-run read results: 2.134 ms p50,
  3.429 ms p95; writes: 0.517 ms p50, 5.982 ms p95. Type throughput (1,996
  reads/s and 499 writes/s) is each operation count divided by the common
  mixed-run elapsed time, not isolated saturation capacity. One write had a
  173.9 ms maximum latency outlier. Full raw output is in
  [evidence/load.json](evidence/load.json); rerun with the load command above.

The test and browser harnesses remove their temporary databases. The load
measurement is loopback-only, one host, and a small mixed workload; it does not
establish production or multi-host performance.
