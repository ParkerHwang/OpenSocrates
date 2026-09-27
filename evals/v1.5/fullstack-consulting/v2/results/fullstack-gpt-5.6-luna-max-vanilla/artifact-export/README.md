# DepotFlow

DepotFlow is a locally runnable, multi-tenant fulfillment application for two warehouse operators. It implements tenant-scoped authentication, inventory reservations, order lifecycles, returns, audit history, a browser UI, integration checks, and a repeatable loopback workload.

## Run it

The application has no third-party runtime dependencies. Python 3.10+ and a shell are enough; the supplied environment was verified with Python 3.12.14.

```sh
./setup.sh
PORT=8000 DATA_DIR="$PWD/data" SEED_DEMO=1 ./run.sh
```

`run.sh` binds only to `127.0.0.1`. `PORT` defaults to `8000`, and `DATA_DIR` defaults to `./data`. `SEED_DEMO=1` creates the demo tenants only when the SQLite store has no tenants. Stop and restart with the same `DATA_DIR` to preserve orders, stock, audit events, sessions, and idempotency records; starting again with `SEED_DEMO=1` does not reseed an existing store.

The UI is at `http://127.0.0.1:8000/`. The JSON API is under `/api` on the same origin. SQLite is the only persisted service and is created inside `DATA_DIR`.

## Demo users

Every user below uses the synthetic local password `DepotDemo!2026`.

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

Each tenant starts with the same independent catalog: BOLT / Steel bolt kit / 100 units / 1250 cents, CABLE / Cable assembly / 60 units / 2499 cents, and SAMPLE / Sample pack / 20 units / 0 cents.

## Design

The backend is a small Python standard-library HTTP server with one SQLite connection per request. SQLite runs in WAL mode; write paths use `BEGIN IMMEDIATE`, so the complete order transition, all affected inventory rows, audit event, and successful idempotency record commit together. The order and inventory versions are optimistic-concurrency tokens exposed to clients.

The frontend is a vanilla HTML/CSS/JavaScript single-page client. It uses DOM text nodes rather than interpolating client text as HTML, keeps mutation buttons out of viewer views, disables in-flight submissions, and refreshes inventory/dashboard/order/audit data after successful changes. It is responsive down to a narrow mobile viewport.

See [architecture.md](architecture.md) for the schema, invariants, transaction boundaries, authentication, error behavior, and tradeoffs.

## API behavior highlights

- `POST /api/session` accepts `{email,password}` and returns a bearer token plus `{email,role,tenant}`. `GET /api/me` returns the authenticated user directly. `GET /api/health` is unauthenticated.
- Every mutation except session creation requires a non-empty `Idempotency-Key`. Keys are tenant-scoped and durable. A matching method/path/canonical JSON payload replays the saved successful status/body after a restart; a changed request receives a 409 and rejected requests never consume a key.
- All inventory, order, audit, and dashboard reads are tenant-filtered in SQL. An object in another tenant therefore behaves as not found. Viewer mutations are rejected with 403, and missing/invalid credentials are 401.
- JSON validation rejects booleans and fractional quantities, versions, deltas, and cents. Errors use `{ "error": { "code": "...", "message": "..." } }`.

## Verification commands

The integration suite starts the actual server on a loopback port, uses real HTTP routes, runs concurrent requests, stops and restarts against the same data directory, and removes only its own temporary directory:

```sh
python3 tests/test_api.py
```

Observed result in this workspace:

```text
PASS: 13 integration areas
  - health and seeded startup
  - authentication, me, and tenant identity
  - viewer and operator authorization
  - validation, zero-price order, server pricing, and replay/conflict
  - atomic insufficient-stock reservation
  - concurrent identical idempotent create
  - serialized concurrent reservation without oversell
  - stale version, ship accounting, partial/full returns
  - reserved cancellation release
  - admin stock adjustment and durable idempotent replay preparation
  - tenant object and audit isolation
  - stable order/audit pagination and filter validation
  - restart durability for state, session, and idempotency
```

The browser check uses the Playwright Chromium WebSocket described in `TOOLING.md`; it exercises the login, inventory, multi-line order form, reserve/ship/full return, audit view, logout, viewer read-only controls, and a 390px viewport:

```sh
BASE_URL=http://127.0.0.1:8000 node tests/browser_check.js
```

Observed result against a freshly seeded local server: `{"title":"DepotFlow","inventory_rows":3,"audit_rows":4,"viewer_mutation_controls":0,"mobile_no_overflow":true,"console_errors":[]}`. The browser script expects `EVAL_BROWSER_WS` to be provided by the supplied tooling environment.

## Repeatable performance exercise

`load_test.py` starts a fresh local seeded server by default. It excludes startup, login, and one warmup request, then runs a read phase and a write phase with the requested concurrency. Reads are `GET /api/inventory`; writes are unique zero-price SAMPLE draft-order creates, each with its own idempotency key. Latency is client-observed wall time and errors include non-expected HTTP statuses and transport failures.

```sh
python3 load_test.py --duration 2 --concurrency 4
```

Observed run in this workspace (macOS 27 arm64, Python 3.12.14, 10 reported CPUs, loopback, one server process):

| Phase | Requests | Errors | Throughput | p50 | p95 | p99 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Read | 5,325 | 0 | 2,655.01 req/s | 1.16 ms | 3.03 ms | 5.82 ms | 42.38 ms |
| Write | 3,711 | 0 | 1,829.74 req/s | 0.59 ms | 2.91 ms | 25.00 ms | 382.29 ms |

This is a repeatable local smoke benchmark, not a capacity promise: it measures loopback client latency on one process and an in-memory request loop, with a growing SQLite database during the write phase. Production deployment would need HTTPS/token expiry, operational backups, rate limiting, observability, and a capacity test on representative hardware and data volumes.

## Deliberate tradeoffs and limits

- Standard-library HTTP and SQLite minimize setup and make the transaction semantics inspectable, but this is not a horizontally scaled deployment architecture.
- Bearer sessions are durable local random tokens without expiry or a password-reset flow because the task is a local synthetic demo. Do not reuse the demo password or expose this server publicly.
- There is no delete-order route; the workflow uses explicit cancellation and returns so audit history remains intact.
- Cursors are opaque base64 JSON positions bound to their filters. They are designed for stable append-only order/audit pagination, not as a general signed public token.
