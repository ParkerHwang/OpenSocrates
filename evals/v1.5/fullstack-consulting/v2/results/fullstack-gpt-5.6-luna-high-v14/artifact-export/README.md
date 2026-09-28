# DepotFlow

DepotFlow is a locally runnable, two-tenant fulfillment application. It supports receiving orders, reserving stock atomically, shipping, returns, stock adjustments, audit history, and a browser UI for the same JSON API.

## Run it

Requirements: Python 3.11+ with the standard library. No package install, container, account, or external database is required.

```sh
PORT=8080 DATA_DIR="$PWD/.data" SEED_DEMO=1 ./run.sh
```

Open <http://127.0.0.1:8080/>. `run.sh` always binds to `127.0.0.1`. `PORT` defaults to `8080`, `DATA_DIR` defaults to `./data`, and `SEED_DEMO=1` seeds only a completely empty database. Stop with Ctrl-C and start with the same `DATA_DIR` to preserve all changes; the seed is not applied to a populated store.

Demo users for each tenant are:

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | admin@north.example | operator@north.example | viewer@north.example |
| south | admin@south.example | operator@south.example | viewer@south.example |

All demo users use `DepotDemo!2026`. Passwords are stored as PBKDF2-SHA256 hashes. Session tokens are intentionally in memory, so log in again after restarting the process; business data and idempotency records are durable.

## Stack and design

- `server.py`: Python `ThreadingHTTPServer` and SQLite in WAL mode.
- `index.html`, `app.js`, `styles.css`: a dependency-free same-origin browser UI.
- SQLite is the only persistent service. Each mutation opens a connection, uses `BEGIN IMMEDIATE`, validates all state, applies stock/order/audit changes, stores the idempotency response, and commits once.
- Tenants are derived only from the authenticated bearer token. Every business query includes the authenticated tenant.
- The UI uses DOM APIs and `textContent` for server/client text; it does not inject arbitrary client text as HTML.

The application intentionally favors a small auditable local deployment over a distributed architecture. SQLite is appropriate for this exercise and serializes the write path safely, but a single-process service and local file are not intended for a high-availability production deployment. SQLite busy waits and the Python request-per-connection model are useful local defaults, not a capacity guarantee.

## Tests and verification

Run the route-level integration suite:

```sh
python3 -m py_compile server.py tests/test_app.py load_test.py
python3 -m unittest -v tests/test_app.py
```

The suite starts a real server against a temporary SQLite directory and exercises health/authentication, tenant and viewer isolation, zero-price nonempty orders, duplicate/idempotent creates, atomic multi-line reservation failure, concurrent reservations, stale versions, partial/full returns, stock validation, pagination validation, and restart durability. The verified run on 2026-09-27 completed 6 tests successfully.

The browser workflow was exercised with the installed headless Chromium connection: operator login, Orders navigation, creation of a zero-price SAMPLE order, order detail rendering, audit navigation, logout, and viewer login. The resulting detail showed the client reference, `draft` status, version 1, and `$0.00`; no page errors occurred. A viewer saw no new-order form or order mutation controls.

## Performance exercise

Start a seeded instance, log in as an operator, and pass the returned token to:

```sh
python3 load_test.py --base http://127.0.0.1:8080 \
  --token YOUR_TOKEN --requests 200 --concurrency 4
```

The driver makes 100 inventory reads and 100 idempotent SAMPLE order creates using unique keys, measures each HTTP request, and reports status counts, throughput, and p50/p95/max latency. A clean local run against a fresh database in this workspace produced:

```json
{"requests": 200, "concurrency": 4, "elapsed_seconds": 0.1074, "throughput_rps": 1862.23, "errors": 0, "status_counts": {"200": 100, "201": 100}, "latency_ms": {"p50": 0.78, "p95": 5.15, "max": 69.3}}
```

This is a local macOS sandbox measurement using fresh HTTP connections from Python, one DepotFlow process, SQLite on local storage, and four client workers. It is a reproducible indicative measurement, not a production capacity claim. An exploratory run at concurrency 8 recorded 2 connection-reset samples out of 200; the clean documented run uses concurrency 4 and reports errors rather than hiding transport failures.

## API notes

The API is same-origin under `/api`. Use `POST /api/session` with `{email,password}`, then send `Authorization: Bearer TOKEN`. Every mutation other than session creation requires a nonempty `Idempotency-Key`; successful responses are replayable after a restart, while changed requests with an existing key return a conflict. Error responses use `{ "error": { "code": "...", "message": "..." } }`.

The complete route contract is specified in `TASK.md`; `architecture.md` records the invariants and transaction boundaries implemented here.
