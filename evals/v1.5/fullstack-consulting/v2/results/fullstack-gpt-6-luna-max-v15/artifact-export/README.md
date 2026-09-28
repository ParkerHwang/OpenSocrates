# DepotFlow

DepotFlow is a locally runnable, multi-tenant warehouse fulfillment app. It uses Python's standard library, SQLite, and plain HTML/CSS/JavaScript. It needs no container, account, network service, or third-party Python package.

## Run it

Python 3.10 or newer is required.

```sh
PORT=8000 DATA_DIR=./data SEED_DEMO=1 ./run.sh
```

Open <http://127.0.0.1:8000>. The server binds only to `127.0.0.1`. `PORT` selects the port and `DATA_DIR` selects the directory containing `depotflow.sqlite3`. The default data directory is `./data` beside the project. Set `SEED_DEMO=1` on the first run to create the demo tenants. Seeding occurs only when the database has no tenants; restarting with the same directory keeps all changes and does not reset stock.

There are no dependencies to install. `run.sh` starts `server.py` directly. For a clean second instance, choose a different port and data directory.

### Demo accounts

Each account uses the local synthetic password `DepotDemo!2026`.

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

## Stack and design

- `server.py` implements the same-origin JSON API and static UI with `ThreadingHTTPServer`.
- SQLite stores tenants, password hashes, hashed bearer tokens, inventory, order and line snapshots, audit events, and idempotency responses. Foreign keys and checks protect stored inventory and order-line invariants.
- Mutations use `BEGIN IMMEDIATE` and commit state, one audit event, and the replay record together. SQLite serializes competing writers, including requests from separate local processes. A stock reservation checks every line before changing any line.
- The tenant is obtained from the bearer token's database user record. Client headers and body fields cannot select a tenant or role. Orders, inventory, audit, dashboard, and idempotency keys are tenant scoped.
- Order line prices are copied from the server's tenant catalog when the order is created. `available` and dashboard values are derived from current inventory; order totals and unit prices remain the historical order snapshot.
- The interface is plain DOM code. It uses `textContent` for server-provided strings, semantic forms and labels, a native SKU select, narrow-screen styles, and role-based control visibility. Failed requests keep form input in place; stale-version errors explain that the order needs refreshing.

## API outline

`POST /api/session` accepts `{ "email", "password" }` and returns a bearer token with its user identity. Send it as `Authorization: Bearer <token>` for other API routes. `/api/health` is public. Authenticated routes include `/api/me`, `/api/inventory`, `/api/dashboard`, `/api/orders`, `/api/orders/<id>`, and `/api/audit`.

Every state-changing request other than session creation requires an `Idempotency-Key`. The tenant-scoped key replays a successful response for the same method, path, and JSON body, even after restart. A changed request with a used key returns 409. Failed requests roll back and do not consume a key. Operators and admins can manage orders; only admins can adjust stock; viewers can inspect data.

API errors use `{ "error": { "code", "message" } }`. A hidden object from another tenant returns 404. Inventory versions change when that SKU's on-hand or reserved quantity changes. Order versions start at 1 and increase once per successful transition.

## Verification

Route and persistence tests start the actual server process against a temporary database:

```sh
python3 -m unittest discover -s tests -v
```

The route suite covers authentication and tenant/role isolation, server-priced and zero-price orders, validation, atomic multi-line reservation failure, failed-key reuse, stale versions, stock adjustment, concurrent same-key replay, competing reservations, shipping, cancellation, partial/full returns, audit and dashboard consistency, cursor pagination, and replay after restarting with the same data directory.

The browser smoke test uses the supplied isolated Playwright browser WebSocket described in `TOOLING.md`:

```sh
node tests/browser_smoke.mjs
```

It exercises login, inventory, multi-line order creation, reserve, ship, partial and full return, audit, viewer read-only controls, the admin adjustment flow, and a 390×844 viewport. It asserts there are no API failures or uncaught page errors.

## Performance exercise

Run a repeatable temporary-database workload:

```sh
python3 scripts/benchmark.py --read-requests 300 --write-requests 120 --concurrency 8
```

The script starts a fresh seeded local server, mixes authenticated inventory/dashboard/order/audit reads, creates uniquely keyed one-line `SAMPLE` orders for writes, and reports throughput, p50/p95/max latency, HTTP status counts, and errors. The temporary store is removed at exit. It does not benchmark shipping/reservation contention or remote/network deployment.

### Recorded local results

Recorded in this workspace on 2026-09-27. The command and environment below are the actual run; small local runs are measurements, not a production capacity claim.

| Workload | Requests | Concurrency | Throughput | p50 | p95 | Max | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Authenticated reads | 300 | 8 | 1,953.29 req/s | 3.998 ms | 5.883 ms | 6.793 ms | 0 |
| Order-create writes | 120 | 8 | 1,179.16 req/s | 0.816 ms | 27.016 ms | 78.263 ms | 0 |

Environment reported by the script: macOS 27.0 arm64, processor string `arm`, 10 logical CPUs, Python 3.12.14. The script reports the operating system, processor string when available, logical CPU count, and Python version. Results vary with machine load, storage, and concurrency. Seven route/persistence tests passed in the same workspace; the Playwright smoke run completed the described desktop/mobile workflow with 0 API failures and 0 uncaught page errors.

## Tradeoffs and limits

This is a compact local app for small warehouse operators. SQLite WAL and a serialized writer make transaction boundaries easy to inspect and durable across restarts, while limiting write parallelism. The server has no external identity provider, HTTPS listener, token expiry, account recovery, or rate limiting. Demo credentials are synthetic and shared; use a production identity and deployment design before exposing this outside a trusted local environment. Audit and idempotency records are retained indefinitely in the local database.

## Files

- `server.py` — API, persistence, seed data, and local HTTP server
- `static/` — usable browser UI
- `tests/test_routes.py` — real-route and restart tests
- `tests/browser_smoke.mjs` — supplied-browser workflow
- `scripts/benchmark.py` — repeatable local load exercise
- `architecture.md` — data, transaction, authentication, and failure invariants
