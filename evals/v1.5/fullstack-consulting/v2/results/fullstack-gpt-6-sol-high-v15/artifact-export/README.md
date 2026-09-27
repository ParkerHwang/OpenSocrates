# DepotFlow

DepotFlow is a locally runnable, two-tenant fulfillment app. It serves a responsive browser UI and JSON API from one loopback HTTP server. The application uses Python 3.10+ standard-library HTTP handling, SQLite for durable state, and plain JavaScript/CSS. The runtime has no third-party packages, containers, accounts, or external database.

## Start

```sh
SEED_DEMO=1 DATA_DIR="$PWD/data" PORT=8000 ./run.sh
```

Open `http://127.0.0.1:8000/`. `run.sh` is executable and uses `python3`, or `PYTHON_BIN` if set. `PORT` defaults to 8000 and `DATA_DIR` defaults to `./data`. The server binds only to `127.0.0.1`. `SEED_DEMO=1` creates demo tenants only in an empty store. A restart with the same `DATA_DIR` retains inventory, orders, audit, idempotency responses, and sessions; seeding does not reset stock.

Each tenant (`north` and `south`) has `admin@<tenant>.example`, `operator@<tenant>.example`, and `viewer@<tenant>.example`. All use the synthetic local password `DepotDemo!2026`. Admins can adjust stock and work orders; operators can work orders; viewers can inspect only. Each tenant starts with BOLT 100 units at $12.50, CABLE 60 at $24.99, and SAMPLE 20 at $0.00. The two stores are independent.

The UI supports dashboard and inventory, admin stock adjustments, order creation with multiple lines, search/status filtering, detail, reserve/ship/cancel/return, audit history, and paging. It preserves form input when a mutation fails, including stale-version errors. An order's price is taken from the server catalog when created.

## API use

`POST /api/session` with `{"email":"operator@north.example","password":"DepotDemo!2026"}` returns a bearer token. Send it as `Authorization: Bearer <token>` to other `/api` routes except `/api/health`. Every mutation except session creation needs a unique nonempty `Idempotency-Key`; reuse the same key and JSON payload to retry after an uncertain response. Response errors use `{ "error": { "code": "...", "message": "..." } }`.

The contract for all routes, status codes, fields, and transitions is in [TASK.md](TASK.md). The implementation notes are in [architecture.md](architecture.md).

## Verification

Run route and persistence tests:

```sh
python3 -m unittest discover -s tests -v
```

The browser test uses Playwright. In an ordinary local environment, install the optional test dependency and its browser, start DepotFlow on port 8765, then run the workflow at both widths:

```sh
npm ci
npx playwright install chromium
SEED_DEMO=1 DATA_DIR="$PWD/browser-data" PORT=8765 ./run.sh
# In another terminal:
PORT=8765 npm run test:browser
PORT=8765 VIEWPORT_WIDTH=1366 VIEWPORT_HEIGHT=900 npm run test:browser
```

When `EVAL_BROWSER_WS` is set, the same script connects to that existing browser instead of launching one. It creates a unique order each run. Its flow signs in as an operator, creates a BOLT+SAMPLE order, reserves and ships, returns both lines, checks audit/inventory, logs out, then checks that a south viewer has no order creation control.

Run the repeatable load exercise:

```sh
python3 tests/load.py --reads 400 --writes 200 --concurrency 8
```

It starts an isolated temporary seeded server, signs in once, alternates inventory/dashboard reads, then creates unique one-line draft orders. It reports request count, status/error counts, wall-clock throughput, and client-observed p50/p95/max latency. The workload measures local loopback and SQLite, not a network deployment or long-running saturation.

## Results from this workspace

- `python3 -m unittest discover -s tests -v`: **4 tests passed**. They cover real HTTP routes and persisted state: role and tenant isolation, validation, zero-price orders, all main transitions, cancellation, partial/full returns, atomic multi-line reservation failure, concurrent reservation, concurrent identical retries, replay after restart, key conflicts, cursor pagination, stock version checks, and audit counts.
- `node tests/browser.js` at **390×844** and **1366×900**: both passed the full workflow described above with **0 page errors** using the provided Chromium WebSocket browser.
- `python3 tests/load.py --reads 400 --writes 200 --concurrency 8` on macOS 27 arm64, 10 logical CPUs, Python 3.12.14: **400 reads, 0 errors, 3,187.9 requests/s, p50 2.38 ms, p95 3.84 ms, max 6.26 ms**; **200 writes, 0 errors, 2,021.4 requests/s, p50 0.54 ms, p95 11.58 ms, max 98.33 ms**. The write phase creates orders without reserving or shipping them.

## Design and limits

SQLite WAL permits concurrent reads while `BEGIN IMMEDIATE` serializes writers. This favors correctness and simple local deployment over high write parallelism. Sessions are random bearer tokens stored as hashes; demo passwords are PBKDF2-hashed. The app is designed for a loopback demo: it has no TLS, password reset, token expiry, production account administration, or remote deployment configuration. Cursor pages pin an upper ID boundary so new inserts do not appear mid-pagination; updates to a status filter between pages can change which existing orders match. The included load run is a short local measurement, not a capacity promise.
