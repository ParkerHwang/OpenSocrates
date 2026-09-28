# DepotFlow

DepotFlow is a local two-tenant warehouse fulfillment app. It supports login,
inventory and dashboard inspection, order intake, atomic reservation, shipping,
cancellation, returns, and tenant-scoped audit history.

## Setup and run

Requirements: Python 3.10+ with SQLite support. No package install, container,
account, network service, or external database is needed.

```sh
./setup.sh
DATA_DIR="$PWD/.depot-data" SEED_DEMO=1 PORT=8000 ./run.sh
```

The service binds to `127.0.0.1` and serves the UI at
[`http://127.0.0.1:8000`](http://127.0.0.1:8000). `PORT` sets the HTTP port;
`DATA_DIR` sets the SQLite state directory. `SEED_DEMO=1` inserts initial users
and stock only when the user table is empty. On later restarts, existing stock
and changes are preserved. Keep the same `DATA_DIR` to keep the same database.

Demo password for all accounts: `DepotDemo!2026`

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | admin@north.example | operator@north.example | viewer@north.example |
| south | admin@south.example | operator@south.example | viewer@south.example |

Each tenant starts with 100 BOLT, 60 CABLE, and 20 SAMPLE units. The prices are
$12.50, $24.99, and $0.00 respectively.

## Stack and design

The backend is Python's standard-library threaded HTTP server and SQLite. The
frontend is semantic HTML, CSS, and vanilla JavaScript. SQLite write operations
use `BEGIN IMMEDIATE`; order updates, stock changes, audit events, and
idempotency responses commit together. Tenant and role are resolved from the
bearer session on the server. See [architecture.md](architecture.md) for schema
invariants, transaction boundaries, authentication, cursor rules, and error
handling.

Main routes include `POST /api/session`, `GET /api/me`, `/api/inventory`,
`/api/dashboard`, `/api/orders`, `/api/orders/<id>`, order transition routes,
`/api/stock/adjustments`, and `/api/audit`. Mutations require an
`Idempotency-Key`. Errors use `{error:{code,message}}`.

## Tests

Run route-level tests with:

```sh
python3 -m unittest discover -s tests -v
```

The tests start isolated HTTP servers and temporary SQLite files. They cover
role and tenant isolation, validation and integer checks, zero-price orders,
atomic failed multi-line reservations, concurrent stock reservations, stale
versions, full and partial returns, pagination, idempotent replay and conflict,
and persisted replay after process restart.

## Load exercise

Start a seeded server, sign in as an operator, and pass the returned token:

```sh
DATA_DIR="$PWD/.load-data" SEED_DEMO=1 PORT=8000 ./run.sh
# In another terminal, set TOKEN to a token from POST /api/session:
python3 load_test.py --base http://127.0.0.1:8000 --token "$TOKEN" --count 500 --workers 16
```

The script issues concurrent reads against inventory, dashboard, orders, and
audit, followed by unique SAMPLE-order writes. It reports successful request
throughput, errors, mean latency, and p50/p95/p99 latency. It mutates the local
database by creating zero-price orders; use a disposable `DATA_DIR` for each
run. It does not compare against a production target.

## Browser workflow

The local environment used for this deliverable provides Chromium over
`EVAL_BROWSER_WS` and Playwright. With the app running on port 8127, run:

```sh
node tests/browser_workflow.js
```

The script signs in as an operator, creates a multi-line order, reserves, ships,
records partial and complete returns, checks audit history, then signs in as a
viewer and confirms writable controls are absent.

## Verification record

Verified on 2026-09-27 on macOS 27.0 arm64, 10 logical CPUs, Python 3.12.14,
SQLite 3.53.1:

- `./setup.sh`: passed.
- `python3 -m unittest discover -s tests -v`: 6 route-level test groups passed,
  including concurrency, isolation, validation, cancellation, retries, returns,
  and durable state across restart.
- `python3 -m py_compile server.py load_test.py tests/test_routes.py`,
  `node --check static/app.js`, and `node --check tests/browser_workflow.js`:
  passed.
- `node tests/browser_workflow.js`: passed. It completed order creation,
  reservation, shipping, partial and full returns, audit inspection, and viewer
  read-only checks; no browser page errors were recorded.
- `python3 load_test.py --base http://127.0.0.1:8128 --token "$TOKEN" --count 500 --workers 16`
  against a freshly seeded local DB: reads were 500/500 HTTP
  200, 2,934.5 requests/s wall-clock throughput, mean 5.36 ms, p50 4.82 ms,
  p95 7.07 ms, p99 20.42 ms. Writes were 500/500 HTTP 201, 2,149.5 requests/s,
  mean 3.42 ms, p50 0.51 ms, p95 10.30 ms, p99 72.30 ms. The harness used 16
  concurrent workers for reads and up to 8 for writes; write operations each
  created a distinct SAMPLE order. Latencies are local urllib request durations;
  throughput uses each phase's wall time.

These are one local synthetic run, not a production capacity estimate. SQLite
serializes writes, the workload uses a small database and a single host, and
latency/throughput will vary with host load, filesystem, request mix, and worker
count. The seeded password and token model are for local demonstration only.
