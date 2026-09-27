# DepotFlow

DepotFlow is a locally runnable, multi-tenant fulfillment application for the two demo warehouse operators `north` and `south`. It includes a persistent backend, a same-origin responsive browser UI, route-level tests, and a repeatable local workload.

## Run it

This build uses only the Python 3 standard library and SQLite; no package install, container, account, or external service is required.

```sh
SEED_DEMO=1 DATA_DIR="$PWD/data" PORT=8000 ./run.sh
```

`run.sh` binds to `127.0.0.1`. `PORT` selects the HTTP port and `DATA_DIR` selects the SQLite state directory. `SEED_DEMO=1` creates the demo catalog only when the store is empty. Stop and restart with the same `DATA_DIR` to retain orders, stock, audit events, idempotency records, and sessions.

Demo users all use the synthetic password `DepotDemo!2026`:

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | admin@north.example | operator@north.example | viewer@north.example |
| south | admin@south.example | operator@south.example | viewer@south.example |

Open `http://127.0.0.1:8000/` after starting the server. The UI supports dashboard/inventory, searchable and status-filtered orders, multi-line order creation, reserve/ship/cancel/return actions, login/logout, and audit inspection. Viewers can inspect these screens but are not shown mutation controls.

## API and design

The API is under `/api`. Login is `POST /api/session` with `{email,password}`; subsequent requests use `Authorization: Bearer <token>`. Every mutation other than session creation requires a non-empty `Idempotency-Key`. Mutations return structured `{error:{code,message}}` failures. Inventory and order versions use strict JSON integers, and catalog prices are copied into order lines at creation time.

The application is a small Python `ThreadingHTTPServer` backed by SQLite in WAL mode. Every mutation opens one `BEGIN IMMEDIATE` transaction and commits its order change, all related inventory changes, audit event, and idempotency response together. This makes reservation competition safe and ensures a rejected multi-line reservation has no partial effect. Tenant is always derived from the authenticated session and is included in all data queries; cross-tenant object lookups therefore return 404. See [architecture.md](architecture.md) for the invariants and transaction details.

## Tests and workload

Run the route-level tests from the project root:

```sh
python3 -m unittest -v tests/test_api.py
```

They launch a real server and exercise authentication/role/tenant isolation, validation, zero-price orders, atomic failures, concurrent reservations, replay/conflict behavior, stale versions, returns, pagination, and a durable restart.

For a repeatable local workload, first start DepotFlow, obtain a token (for example with the command below), then run:

```sh
TOKEN=$(python3 -c 'import json,urllib.request; r=urllib.request.Request("http://127.0.0.1:8000/api/session",data=json.dumps({"email":"admin@north.example","password":"DepotDemo!2026"}).encode(),headers={"Content-Type":"application/json"}); print(json.load(urllib.request.urlopen(r))["token"])')
TOKEN="$TOKEN" READS=100 WRITES=40 CONCURRENCY=8 python3 load_test.py
```

One verification run on the supplied local environment (Python standard library server, SQLite WAL, localhost, 8 worker threads, 100 inventory reads and 40 unique one-unit SAMPLE order writes) produced:

```text
read: count=100 throughput=1858.69/s mean_ms=4.22 p95_ms=14.96 errors=0
write: count=40 throughput=1526.09/s mean_ms=4.08 p95_ms=12.15 errors=0
```

The exact timings are machine/load dependent; run `load_test.py` to record current values. The workload is intentionally a smoke/performance exercise, not a production capacity claim. It does not model large payloads, WAN latency, multiple processes, or customer data.

The browser check used Playwright against the running server and passed operator login, inventory table visibility, multi-line form navigation, SAMPLE order creation/detail, logout, viewer login, and confirmation that viewer order pages expose neither `new-order` nor transition controls.

## Tradeoffs and limits

SQLite keeps this exercise portable and durable, while `BEGIN IMMEDIATE` favors correctness and simple contention handling over maximum write concurrency. Sessions do not expire and are stored locally because this is a synthetic local demo; production deployment would need a stronger password/KMS/session policy, TLS, rate limiting, backups, and operational monitoring. The UI uses a short in-memory list page (up to 100 orders) even though the API itself provides cursor pagination.
