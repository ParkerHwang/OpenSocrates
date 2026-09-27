# DepotFlow

DepotFlow is a locally runnable fulfillment desk for two isolated warehouse tenants. It includes a same-origin JSON API, a responsive browser UI, a persistent SQLite store, route-level integration tests, and a repeatable local HTTP workload.

## Start locally

Python 3.10 or newer is required. The app uses only Python standard-library modules and SQLite; there are no package downloads, containers, accounts, or external database services.

```sh
./setup.sh
SEED_DEMO=1 DATA_DIR="$PWD/data" PORT=8000 ./run.sh
```

Open `http://127.0.0.1:8000/`. `PORT` defaults to `8000`; the process always binds to `127.0.0.1`. `DATA_DIR` defaults to the project’s `data/` directory and contains `depotflow.sqlite3` plus SQLite WAL files while the service is running. Use the same directory after restart to keep orders, inventory changes, sessions, audit events, and idempotency responses.

`SEED_DEMO=1` inserts the demo tenants, users, and starting inventory only when the database has no tenant rows. Restarting with that setting does not reseed or reset an existing store. Omit it to start an empty store. `setup.sh` checks the Python and SQLite runtime and compiles the backend; it installs nothing.

## Demo users

All six synthetic users use `DepotDemo!2026`.

| Tenant | Administrator | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

Each tenant gets its own starting stock: BOLT (100 at 1,250 cents), CABLE (60 at 2,499 cents), and SAMPLE (20 at 0 cents). Inventory, orders, audit history, and idempotency keys are isolated by the authenticated tenant. Admins can adjust stock; admins and operators can create and fulfill orders; viewers can inspect but cannot mutate.

## API quick start

The API lives under `/api` on the same origin. `GET /api/health` is public. Create a session, then send its token as a bearer token:

```sh
curl -sS http://127.0.0.1:8000/api/session \
  -H 'Content-Type: application/json' \
  -d '{"email":"operator@north.example","password":"DepotDemo!2026"}'

curl -sS http://127.0.0.1:8000/api/inventory \
  -H 'Authorization: Bearer <token-from-session>'

curl -sS http://127.0.0.1:8000/api/orders \
  -H 'Authorization: Bearer <token-from-session>' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: order-demo-001' \
  -d '{"client_ref":"WEB-1042","lines":[{"sku":"BOLT","quantity":2},{"sku":"SAMPLE","quantity":1}]}'
```

Every mutation except `POST /api/session` requires a nonempty `Idempotency-Key`. Reusing a key for the same method, path, and JSON payload replays the original success. Reusing it for a different request returns 409. Failed calls do not consume keys. Error responses have `{ "error": { "code", "message" } }`.

## Frontend

The UI supports login/logout, the inventory dashboard, admin stock adjustment, order search/status filters, multi-line order creation, order details, reserve/ship/cancel/return actions, pagination, and a tenant audit view. Mutations refresh the related committed state. Inputs remain on stale or failed submissions, and the client reuses an idempotency key for an exact retry. Viewer sessions hide write controls. Dynamic API text is added with DOM text nodes rather than interpreted as HTML.

The stack-neutral browser workflow is in `scripts/browser_smoke.js`; it connects to the isolated Playwright browser supplied through `EVAL_BROWSER_WS` and expects the app at `PORT` (default 8000). A successful run from this workspace is captured in [evidence/browser-order-workflow.png](evidence/browser-order-workflow.png).

## Design and trade-offs

The hard constraints came from the task: one local start command, same-origin API and UI, durable restart state, and no external database service. For this delivery, setup simplicity and correct stock transactions matter more than multi-process write throughput.

| Option | Fit and trade-off |
| --- | --- |
| Python standard library + SQLite WAL (selected) | No package download or build step; includes an embedded transactional database. The local threaded server handles parallel requests, while SQLite serializes writes. The included benchmark measures this option only. |
| Node HTTP framework + SQLite driver | Could serve the same local interface; it adds a framework/database dependency choice and does not remove SQLite’s serialized write boundary. This is a qualitative alternative, not benchmarked here. |
| Go HTTP server + SQLite driver | Could produce a compact executable and handle concurrent requests; it needs a compile and driver setup and still shares SQLite’s write limit. This is a qualitative alternative, not benchmarked here. |

The selected stack satisfies the hard constraints and is reproducible with the local Python/SQLite runtime listed in `TOOLING.md`. The main concession is write scaling: the 8-client local workload is evidence for this implementation only, not a comparison or an Internet-facing capacity claim. If the requirement changes to multiple service processes or sustained concurrent writes, the storage choice should be revisited; the current no-external-service constraint would need to change to use a server database. The API reuses helpers for tenant-scoped reads, validation, audit insertion, and idempotency. See [architecture.md](architecture.md) for transaction and security details.

The demo deliberately uses local seeded credentials and persistent bearer sessions, binds only to loopback, and omits production concerns such as HTTPS termination, account provisioning, password reset, token expiry, and login rate limiting. Treat the synthetic users and local database as a development/demo environment, not an Internet-facing deployment.

## Tests and performance

Run route tests against a real child server and a temporary persisted store:

```sh
python3 -m unittest discover -s tests -v
```

The suite covers authentication, roles, tenant isolation, validation, server-side price snapshots, zero-price orders, atomic multi-line reservation failure, competing and identical concurrent requests, optimistic versions, adjustment floors, returns, cursor pagination, audit behavior, and restart persistence including idempotency replay.

Run a self-contained benchmark; it starts and stops a fresh seeded instance and writes only to a temporary directory:

```sh
python3 scripts/benchmark.py --reads 600 --writes 100 --concurrency 8
```

The workload mixes authenticated inventory/dashboard/order-list reads with unique SAMPLE order creations. The recorded run in [evidence/benchmark.json](evidence/benchmark.json) used Python 3.12.14, SQLite 3.53.1, macOS 27 on arm64 with 10 logical CPUs, a local loopback server, local temporary SQLite WAL storage, and 8 client workers. It completed 600 reads and 100 writes in 0.3443 seconds: 0 errors, 1,742.75 read requests/s and 290.46 writes/s when each category’s count is divided by the same mixed-run duration. Read latency was p50 2.273 ms, p95 7.757 ms, p99 10.760 ms; write latency was p50 4.778 ms, p95 32.788 ms, p99 106.603 ms. These are one local synthetic run, not a production capacity claim; the small catalog, temporary storage, host loopback, and concurrent mix limit how broadly they generalize.

See [evidence/verification.md](evidence/verification.md) for the actual check record and limits.
