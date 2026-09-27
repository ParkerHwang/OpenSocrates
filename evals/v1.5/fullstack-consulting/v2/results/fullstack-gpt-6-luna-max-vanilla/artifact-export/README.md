# DepotFlow

DepotFlow is a locally runnable, two-tenant order and inventory workspace. It includes a JSON API, a responsive browser UI, a persistent SQLite store, an integration test suite, a browser workflow script, and a mixed read/write load generator.

## Run locally

Requirements: Python 3.10 or newer with SQLite support. The application uses only the Python standard library; no package install, container, account, or external database is needed.

```sh
./setup.sh
DATA_DIR="$PWD/.depotflow-data" PORT=8000 SEED_DEMO=1 ./run.sh
```

Open <http://127.0.0.1:8000>. `run.sh` binds only to `127.0.0.1`. Use the same `DATA_DIR` after stopping and restarting the process to preserve users, sessions, orders, inventory, audit entries, and idempotency responses. The demo seed is inserted only if the database has no tenants; setting `SEED_DEMO=1` again does not reset stock or orders. Choose another empty directory when a fresh demo store is needed.

The seeded synthetic users all use password `DepotDemo!2026`:

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

## Stack and design

- Python `http.server` and `sqlite3` provide a small, dependency-free backend.
- SQLite stores tenant data in one local database file with foreign keys, WAL journaling, checks, and a busy timeout.
- Vanilla JavaScript and CSS render the same-origin UI at `/`; JSON endpoints live under `/api`.
- Bearer tokens are created at login and mapped to server-side sessions. Tenant and role come from the authenticated database user. Client headers and body fields cannot select them.
- Each mutation uses a SQLite `BEGIN IMMEDIATE` transaction. Stock checks, order state changes, audit writes, and successful idempotency results commit together.
- SQLite serializes writers, so concurrent reservations cannot both spend the same available quantity. The tradeoff is that write throughput is limited by one local database writer and is intended for small warehouse teams.
- Passwords use salted PBKDF2-HMAC-SHA256 hashes. The synthetic demo password is intentionally shared across the seeded demo accounts; replace the seed/users for any non-demo use.

See [architecture.md](architecture.md) for transaction boundaries, invariants, authorization, and errors.

## Tests and browser workflow

The integration test starts the real server in a temporary data directory and exercises HTTP routes, persistence, and process restart:

```sh
python3 -m unittest discover -s tests -v
```

It covers login and roles, tenant isolation, stock/order validation, zero-price orders, pagination, concurrent reservation, atomic multi-line failure, idempotent replay, stale versions, stock adjustments, partial and full returns, audit consistency, and persisted state after restart.
Recorded result: 1 integration test passed; see [evidence/api-tests.txt](evidence/api-tests.txt).

The browser script uses Playwright and the isolated Chromium WebSocket supplied in this environment. With DepotFlow running and `EVAL_BROWSER_WS` configured:

```sh
DEPOTFLOW_URL=http://127.0.0.1:8000 node scripts/browser_smoke.cjs
```

It drives login, inventory, a two-line order, reserve, ship, partial and full return, order search, audit, logout, and viewer read-only behavior at 390px width. Captured screenshots and the run result are in [evidence](evidence/).

## Load exercise

Run against a seeded local instance. The script logs in once, then submits a fixed 80% read / 20% write mix: inventory, dashboard, order-list reads, and unique zero-price `SAMPLE` order creates. Writes are persistent, so use a disposable `DATA_DIR` for each run.

```sh
DATA_DIR="$PWD/.load-data" PORT=8001 SEED_DEMO=1 ./run.sh
python3 scripts/load_test.py --url http://127.0.0.1:8001 --requests 1000 --concurrency 16
```

Latency is measured per HTTP request with `time.perf_counter`; throughput covers all measured requests and failures count non-expected status codes or transport errors. Login and health setup are excluded. The workload has no warmup period and uses one local process/database.

Measured result from this workspace (Python 3.12.14, macOS 27.0 arm64, 10 logical CPUs, 16 client workers, 1,000 requests; 200 create writes):

| Measure | Result |
| --- | ---: |
| Total throughput | 2,536.96 requests/s |
| Read p50 / p95 | 0.79 / 4.13 ms |
| Write p50 / p95 | 1.75 / 126.02 ms |
| Read / write throughput | 2,029.57 / 507.39 requests/s |
| Errors | 0 / 1,000 |

The full output is [evidence/load-results.json](evidence/load-results.json). These are local synthetic-workload measurements, not a production capacity claim. The server is single-process and SQLite allows one writer at a time; results vary with the machine, store size, and contention.

## API behavior notes

- `POST /api/session` returns a bearer token; use it in `Authorization: Bearer …` for protected endpoints.
- Every successful mutation except login requires a nonempty `Idempotency-Key`. Replays are tenant-scoped and survive restart.
- `GET /api/health` is unauthenticated. Other read routes return `401` without a valid token.
- `viewer` can read but receives `403` for mutations; stock adjustments require `admin`; operators can create and fulfill orders.
- A cross-tenant order lookup returns `404` to avoid revealing the other tenant's objects.
- Errors use `{ "error": { "code": "…", "message": "…" } }`.

## Local limitations

DepotFlow is deliberately a compact local application. There is no TLS, public-network bind, account recovery, role-management UI, token expiry, or multi-process deployment configuration. Logout clears the browser's locally stored bearer token; server-side demo sessions remain in the local database. Keep the synthetic demo password and data local.
