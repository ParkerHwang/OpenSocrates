# DepotFlow

A complete local fulfillment workspace for two independent warehouse organizations. It includes a persistent SQLite backend, a responsive same-origin UI, route-level integration tests, browser automation, and an HTTP performance exercise. Only synthetic demo data is used.

## Run

Requires **Python 3.10 or newer with SQLite support**. There are no application packages to install, no build step, and no external services.

```sh
SEED_DEMO=1 PORT=8000 DATA_DIR="$PWD/.data" ./run.sh
```

Open **http://127.0.0.1:8000**. The server always binds to `127.0.0.1`. `PORT` defaults to `8000`; `DATA_DIR` defaults to `.data` beside `run.sh`. Set `PYTHON` to a Python executable if necessary. Relative `DATA_DIR` paths resolve from the project root.

Stop with Ctrl-C and run the same command to resume. `SEED_DEMO=1` only seeds a store with no organizations. It never replenishes existing inventory. Starting a fresh store without this flag intentionally creates an empty database with no login accounts. To try another clean demo, choose another directory; do not delete a directory whose changes you want to keep.

| Organization | Admin | Operator | Viewer |
| --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` |

All six accounts use **`DepotDemo!2026`**. Each organization independently starts with BOLT 100 at 1,250 cents, CABLE 60 at 2,499 cents, and SAMPLE 20 at zero cents.

## Use the workspace

1. Sign in as an administrator or operator. Inventory shows dashboard totals and available stock.
2. Open **Orders → New order**, enter a unique client reference, and add one or more product lines. Catalog prices are displayed and copied by the server.
3. Open the created order and **Reserve stock**, then **Ship order**. A draft or reserved order can instead be cancelled.
4. For a shipped order, enter received return quantities. Zero leaves a line unchanged. Partial returns remain shipped; the final return closes the order as returned.
5. Administrators can expand **Adjust stock** in Inventory to record receipts or corrections with a reason.
6. **Activity log → Inspect change** shows the actor, order reference, reason, and stock before/after. Search and status filters are on the order list. Lists paginate oldest first.

Viewer accounts expose only inspection controls. Each request still enforces permissions on the server. Stale-version errors preserve typed inputs; use **Refresh order** or **Refresh stock versions**, review the retained values, and submit again. Buttons lock during writes. Network retries reuse the original operation key while the page remains open. Signing out removes the browser's session token.

## Stack and design

- Python standard-library threaded HTTP server and a small explicit route dispatcher.
- SQLite in WAL mode with foreign keys, database constraints, and `synchronous=FULL`.
- Browser-native JavaScript, semantic HTML, and responsive CSS; no CDN, framework runtime, or bundler.
- Server-owned tenant and role from hashed opaque session tokens. Salted PBKDF2 password hashes; sessions last 24 hours and survive restart.
- One `BEGIN IMMEDIATE` transaction covers each business mutation, its audit event, and its successful idempotency response. Failed mutations roll back everything.
- Signed cursor pagination uses an upper sequence boundary. Order status history preserves the first page's match membership even if an order changes status between pages. Returned details represent current state.

See [architecture.md](architecture.md) for invariants, transaction boundaries, reuse, authentication, pagination, and the design comparison.

## API

The complete required integration surface is implemented under `/api`. Login with `POST /api/session` using `{email,password}`; send the returned token as `Authorization: Bearer <token>` thereafter. `GET /api/health` needs no token. `GET /api/me` returns the authenticated user.

Every business mutation requires a nonempty **`Idempotency-Key`** header. A tenant shares its key namespace across endpoints. Identical method, path, and JSON content replay the saved status/body, including after restart. JSON object-key order is ignored; arrays and numeric types remain significant. Changes to ignored extra fields also change the request fingerprint. Failures do not consume keys. Always retry an uncertain response with the same key and payload.

| Method / route | Purpose |
| --- | --- |
| `GET /api/inventory` | Catalog, on-hand/reserved/available units, prices, versions |
| `GET /api/dashboard` | Committed tenant order counts and inventory totals |
| `POST /api/stock/adjustments` | Admin adjustment with `sku`, signed `delta`, `expected_version`, `reason` |
| `POST /api/orders` | Create with `client_ref` and `lines:[{sku,quantity}]` |
| `GET /api/orders` | Optional `status`, literal case-insensitive `q`, `limit`, `cursor` |
| `GET /api/orders/<id>` | Order with server price snapshots and returned quantities |
| `POST /api/orders/<id>/reserve` | Atomic stock reservation; `expected_version` |
| `POST /api/orders/<id>/ship` | Shipment; `expected_version` |
| `POST /api/orders/<id>/cancel` | Draft/reserved cancellation; `expected_version` |
| `POST /api/orders/<id>/returns` | Partial/full return; `expected_version`, `lines` |
| `GET /api/audit` | Audit events, optional `limit`, `cursor`; additional `details` supports investigation |

Business errors use `{error:{code,message}}`. Invalid input is 400, unauthenticated requests are 401, forbidden writes are 403, foreign/missing orders are 404, and stale versions, invalid transitions, stock shortages, and retry conflicts are 409. Create returns 201; other successful business writes return 200. An exhausted database-lock wait returns 503 with instructions to retry the same key. Unexpected faults return a generic 500 and roll back.

Pagination defaults to 20, permits 1–100, and ends with `next_cursor:null`. Preserve filters when reusing a cursor. Newly created records after the first page do not enter that traversal; refresh to start a new traversal. A status-filtered traversal can show an original member's newer status.

Payload limits: 1 MiB, 1–100 unique lines, quantities and on-hand stock at most 1 billion, client references at most 160 characters, reasons at most 1,000, and keys at most 200. Financial totals remain within JavaScript's safe integer range. Booleans, fractions, duplicate JSON keys, and nonfinite numbers are rejected where integer or valid JSON data is required. Client-supplied tenant, role, status, versions at creation, and prices cannot override server values.

## Verify

The API suite starts actual `run.sh` subprocesses, sends HTTP requests, and examines persisted database state. Every test gets a fresh directory under `.test-data`; it never uses the default store.

```sh
python3 -m unittest -v tests.test_api
```

The optional browser suite needs Node.js 20 or newer and Playwright. The application does not depend on Node.

```sh
npm ci
npx playwright install chromium
npm run test:browser
```

If your environment already supplies Playwright and `EVAL_BROWSER_WS`, use `node tests/browser.cjs`; it connects to that isolated browser. Otherwise it launches installed headless Chromium. The suite starts its own fresh application, exercises desktop and mobile workflows, saves screenshots/reports to `evidence/`, and cleans up. Its required UI markers are in `static/app.js`.

```sh
python3 scripts/benchmark.py --concurrency 8 --orders 5000 --reads 30000 \
  --output evidence/performance.json
```

The performance exercise uses a disposable store and real HTTP. Each of eight clients repeatedly creates, reserves, ships, and fully returns three-line orders. BOLT, CABLE, and zero-price SAMPLE are all exercised. Then it measures an equal mix of inventory, dashboard, order-list, and audit reads. Forty warmup reads, startup, and login are excluded. Connections are persistent; clients wait for each response with no pacing or retries. End-to-end timings include JSON encoding/parsing. Raw request samples and persisted-state postconditions are saved beside the aggregate report. Concurrency is limited to 20 to keep this workload within seeded stock.

## Recorded verification

On the recorded macOS arm64 host (10 logical CPUs reported, Python 3.12.14, SQLite 3.53.1), **26 API integration tests passed** and **12 Chromium workflow checks passed**, including a 390px mobile workflow and an interrupted-write retry. The benchmark at concurrency 8 recorded:

| Phase | Requests | Requests/s | p50 / p95 / p99 latency | Errors |
| --- | ---: | ---: | --- | ---: |
| Business writes | 20,000 | 2,251.67 | 0.426 / 5.051 / 57.015 ms | 0 |
| Mixed read endpoints | 30,000 | 1,890.83 | 2.770 / 7.691 / 21.579 ms | 0 |

The longest write took **1,321.260 ms** under writer contention. All 5,000 orders ended fully returned, stock returned to its initial values, and exactly 20,000 audit/retry records existed. Database integrity checks passed. Exact CPU model, physical CPU count, and memory capacity could not be queried within the sandbox. These short separate phases do not establish sustained mixed-workload capacity.

See [evidence/verification.md](evidence/verification.md) for actual results, commands, discovered issues, and remaining limits. Browser captures include [desktop inventory](evidence/inventory-desktop.png), [desktop order](evidence/order-desktop.png), and [mobile order](evidence/order-mobile.png). Reports are generated by the test scripts; these are not static demo screens.

## Scope and tradeoffs

This is a local application for the supplied workflow. SQLite serializes writers, and the standard-library HTTP server is intended here for a trusted local environment. The design minimizes installation and build dependencies; it accepts explicit handwritten routing/validation and limits horizontal scaling. There is no order editing, catalog-management UI, account administration, external shipping integration, tax/currency configuration, or multi-process load balancing.

Sessions expire after 24 hours. Logout clears the current browser token; it does not revoke copied tokens on the server. There is no rate limiter, TLS termination, recovery-email flow, or production observability stack. Use only synthetic local accounts as supplied. Idempotency records and audit history are retained without pruning. Browser form drafts and pending retry keys live in memory and are not retained after a tab reload. Other tabs are refreshed explicitly; this is not a live-push UI.

The forced-restart test checks completed committed requests, not process failure at every instruction or physical power loss. Browser evidence is Chromium only. Performance numbers are host-specific synthetic measurements, not a capacity guarantee.
