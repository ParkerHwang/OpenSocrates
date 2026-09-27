# DepotFlow

DepotFlow is a locally runnable fulfillment app for two independent warehouse tenants. It serves a browser UI and JSON API from one Python process, with durable SQLite state. Python 3.10 or newer is required for the app; it has no runtime package dependencies.

## Start

```sh
SEED_DEMO=1 PORT=8000 DATA_DIR=./local-data ./run.sh
```

Open <http://127.0.0.1:8000/>. `PORT` defaults to `8000`, `DATA_DIR` defaults to `./data`, and the server binds only to `127.0.0.1`. `run.sh` is executable and uses the `python3` on `PATH`. The first start with `SEED_DEMO=1` creates both demo tenants when the database has no tenants. Later starts with the same `DATA_DIR` preserve stock, orders, sessions, audit and retry records; they do not seed again. To start with a new demo state, choose a new directory.

Demo users all use the synthetic password `DepotDemo!2026`:

| Tenant | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

Admins can adjust stock and work orders; operators can work orders; viewers can inspect only. Start in Inventory for dashboard totals and stock, open Orders to create a multi-line draft, reserve it, ship it, and record one or more returns. Audit shows the corresponding committed events. Log out to switch tenant or role.

API clients authenticate with `POST /api/session` and send `Authorization: Bearer <token>` on subsequent requests. Every non-session POST requires a nonempty `Idempotency-Key`. For example:

```sh
curl -s http://127.0.0.1:8000/api/health
curl -s -X POST http://127.0.0.1:8000/api/session \
  -H 'Content-Type: application/json' \
  -d '{"email":"operator@north.example","password":"DepotDemo!2026"}'
```

Use the returned token to call `/api/inventory`, `/api/dashboard`, `/api/orders`, and `/api/audit`. The API contract and transaction behavior are detailed in [architecture.md](architecture.md).

## Verification

The route tests start disposable servers and query actual HTTP endpoints and persisted SQLite state:

```sh
python3 -m unittest discover -s tests -v
```

They cover authentication and roles, tenant isolation, validation, zero-price orders, all order transitions, atomic failure, stale versions, concurrent reservation and identical retry, failed-key reuse, pagination, audit, and restart durability. The final run passed all four test methods.

The browser test runs a complete order lifecycle in Chromium, creates and cancels a separate multi-line order, checks audit and inventory, logs out, verifies a south viewer cannot access write controls, and checks a narrow viewport. Install its optional dependencies once with `npm ci` and `npx playwright install chromium`, then run `npm run test:browser`. In this workspace, Playwright was already available and the test connected to the supplied browser through `EVAL_BROWSER_WS`; when that variable is absent, it launches a local headless Chromium. The final run passed. [Browser screenshot](evidence-browser.png) is from the admin inventory view after those actions.

The repeatable workload starts a fresh seeded server and uses a fixed pool of eight clients. It issues 500 inventory reads, then creates 100 distinct draft orders. Each worker reuses an HTTP/1.1 connection. Results include client-side wall-clock throughput and latency (HTTP and JSON included), status/error counts, and a dashboard postcondition. Run `python3 tests/load.py`; override `LOAD_READS`, `LOAD_WRITES`, or `LOAD_CONCURRENCY` if desired. Each run writes [evidence-load.json](evidence-load.json).

On the supplied macOS 27 arm64 environment (Python 3.12.14, 10 logical CPUs), the recorded eight-client run measured **4,219 reads/s** (p50 **1.59 ms**, p95 **2.90 ms**, 0 errors) and **1,228 writes/s** (p50 **0.55 ms**, p95 **27.25 ms**, 0 errors). These are small local loopback samples, not capacity claims. An earlier benchmark that opened a new TCP connection for every request encountered intermittent loopback connection resets under the burst; the committed workload uses persistent connections and the recorded run had zero errors.

## Design and limits

The stack is Python standard-library `ThreadingHTTPServer`, SQLite in WAL mode, and plain HTML/CSS/JavaScript. SQLite `BEGIN IMMEDIATE` serializes mutations, so reservation and idempotency checks are atomic across request threads and process restarts. Browser text is inserted with text nodes rather than HTML interpolation. This keeps deployment simple and avoids a build step.

The app is intended for local demonstration and evaluation. Sessions are opaque random bearer tokens stored as hashes, but they do not expire or support remote revocation, and the UI keeps the token in browser local storage. The server has no TLS or account-management workflow. Cursor pages pin a high-water ID so newly inserted rows do not enter an existing traversal; a concurrent change to an order's status can change whether that order matches a later filtered page. SQLite permits one writer at a time, so write latency rises with contention. The load exercise measures order creation, not a full reserve/ship workload.
