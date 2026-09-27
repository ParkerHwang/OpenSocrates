# DepotFlow

DepotFlow is a locally runnable, two-tenant order fulfillment app. It provides a same-origin JSON API and responsive browser UI for inventory, order entry, reservation, shipping, returns, and audit history.

## Run it

Requirements: Python 3.10 or later. The server, SQLite driver, UI, tests, and benchmark use the standard library; no package install or external service is needed.

```sh
PORT=8000 DATA_DIR="$PWD/depot-data" SEED_DEMO=1 ./run.sh
```

Open <http://127.0.0.1:8000>. `PORT` defaults to 8000, `DATA_DIR` defaults to `./data`, and the server binds only to `127.0.0.1`. Seeding occurs only when the store has no users, inventory, or orders. Restart with the same `DATA_DIR` to keep all changes. Seeding is optional; without it, the app starts empty and there is no login until users are provisioned (this deliverable only provisions demo users through seeding).

The synthetic demo password for each account is `DepotDemo!2026`:

| Tenant | Administrator | Operator | Viewer |
|---|---|---|---|
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

Seed inventory is independent per tenant: BOLT (100, $12.50), CABLE (60, $24.99), SAMPLE (20, $0.00). The UI supports signing in/out, dashboard and inventory, order search/status filtering, multi-line order creation, order details, reserve/ship/cancel/return, and audit review. Viewers can inspect these views but see no mutation controls.

## Stack and design

- Python `ThreadingHTTPServer` serves static HTML and `/api` from one origin.
- SQLite is the durable embedded store. Tenant ID is bound to the authenticated user and included in every tenant-owned read/write query.
- `BEGIN IMMEDIATE` serializes writes. Order transitions, inventory changes, audit events, and successful idempotency responses commit in one transaction.
- The browser is framework-free HTML/CSS/JavaScript; it uses `textContent` or escaped values for client/server text and native labeled controls.

See [architecture.md](architecture.md) for transaction boundaries, authorization, invariants, and known tradeoffs.

## Tests and browser workflow

Route tests launch a temporary seeded server and test HTTP routes against isolated persisted state:

```sh
python3 -m unittest discover -s tests -v
```

The tests cover credentials/roles/tenant isolation, validation, zero-price orders, tenant-local client references, failed multi-line reservation atomicity, simultaneous reservations, simultaneous same-key creates, stale versions, replay (including after restart), partial/full returns, audit consistency, and durability.

The UI was exercised with the supplied isolated headless Chromium connection. To repeat where `EVAL_BROWSER_WS` and Playwright are available, start the server as above, then run:

```sh
BASE_URL=http://127.0.0.1:8000 node browser_check.cjs
```

That workflow logs in as an operator, opens inventory and orders, creates a nonempty SAMPLE order, reserves and ships it, performs partial and full returns, checks audit, then logs in as a viewer and confirms order creation is absent.

## Performance exercise

Use a disposable seeded DATA_DIR because each write creates an order and audit record:

```sh
PORT=8000 DATA_DIR="$PWD/load-data" SEED_DEMO=1 ./run.sh
# In another shell:
python3 load.py --base http://127.0.0.1:8000 --requests 500 --concurrency 8
```

The benchmark alternates authenticated inventory reads with unique idempotent SAMPLE order creates. It prints combined and per-class throughput, success/error counts, and mean/p50/p95/p99 latency. One run in this environment (macOS 27.0 arm64, 10 reported CPUs, local SQLite file, 8 client workers) completed 500 requests in 0.347 s: combined 1,440.6 requests/s; 250/250 reads succeeded at 720.3/s (mean 2.20 ms, p50 0.43, p95 6.41, p99 12.47); 250/250 writes succeeded at 720.3/s (mean 8.31 ms, p50 0.93, p95 40.56, p99 151.98). This is a single short local run, not a capacity guarantee; the dataset was already populated, and latency includes client scheduling and Python HTTP handling.

## API surface

`POST /api/session` returns a bearer token; `/api/me`, `/api/inventory`, `/api/dashboard`, `/api/orders`, `/api/orders/<id>`, and `/api/audit` are reads. Mutations are `/api/stock/adjustments`, `POST /api/orders`, and per-order `/reserve`, `/ship`, `/cancel`, and `/returns`. Mutations require `Idempotency-Key`. The public health check is `/api/health`. API errors use `{ "error": { "code", "message" } }`.

## Results and limits

Verified on the disposable local workspace: Python bytecode compilation passed; all five route/integration tests passed; Chromium completed the operator and viewer flow described above; the 500-request mixed benchmark reported no errors. No external database, accounts, or services were used. SQLite serializes writes, so write-heavy multi-process deployments would need a database designed for higher concurrent write volume. The service intentionally has no password reset/account provisioning screen, token expiry/revocation, TLS, or network exposure; it binds to loopback for local use. Demo passwords are synthetic and identical across roles by design.
