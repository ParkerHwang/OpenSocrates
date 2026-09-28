# DepotFlow

A locally runnable fulfillment workspace for two independent warehouse organizations. It includes inventory control, multi-line orders, atomic reservations, shipping, cancellation, partial/full returns, role-aware screens, searchable order lists, and an auditable stock history.

## Run

Requires **Python 3.10+ with SQLite**. The application has no third-party Python dependencies and no frontend build step. Verified with Python 3.12.14 and SQLite 3.53.1.

```sh
./setup.sh
PORT=8000 DATA_DIR="$PWD/.data" SEED_DEMO=1 ./run.sh
```

Open **http://127.0.0.1:8000**. The server binds only to `127.0.0.1`, serves the UI at `/`, and serves JSON under `/api`. Stop with Ctrl-C. Use `PYTHON=/path/to/python3` if needed. `PORT` defaults to 8000 and `DATA_DIR` to `.data` in the project directory. Relative data paths are resolved from the project directory.

Restart the same command with the same `DATA_DIR` to retain changes. `SEED_DEMO=1` seeds only an empty domain store; it never resets existing stock. Without it, a fresh store has no users/catalog. Test runners create and remove their own isolated stores under `.test-data`.

## Demo accounts

All six synthetic users use **`DepotDemo!2026`**.

| Role | North | South | Access |
| --- | --- | --- | --- |
| Admin | `admin@north.example` | `admin@south.example` | Orders and stock adjustments |
| Operator | `operator@north.example` | `operator@south.example` | Create/reserve/ship/cancel/return orders |
| Viewer | `viewer@north.example` | `viewer@south.example` | Inspect inventory, orders, and activity |

Each tenant independently starts with BOLT (100 units, 1250 cents), CABLE (60 units, 2499 cents), and SAMPLE (20 units, zero cents). No real customer data is used.

## Use the workspace

1. Sign in and review **Inventory & overview**. Admins can record signed stock adjustments with a reason.
2. Open **Orders → New order**, enter a unique client reference, and add one or more SKU/quantity lines. Creating a draft does not consume stock.
3. **Reserve stock**, then **Ship order**. A failed multi-line reservation changes nothing. Draft/reserved orders can be cancelled.
4. For shipped orders, enter units physically received into each **Return now** input and choose **Receive return**. Leave other lines at zero. Partial returns remain shipped; the last return marks the order returned.
5. Inspect **Activity log**, including expandable reasons and line details. Order event IDs link back to order details.

The UI retains input after errors. A stale-version error offers **Refresh record · keep input** so the user can review against the current version. Submission controls are disabled while saving. Viewers see no writable controls. All user text is inserted as text, and mobile order details expose return inputs as stacked labeled fields. Wider inventory/audit tables can be scrolled by touch or keyboard.

## API contract and design

The implementation follows `TASK.md`. Login with `POST /api/session` and `{email,password}`; supply `Authorization: Bearer <token>` on subsequent requests. `GET /api/health` is public. Every domain POST additionally requires a nonempty `Idempotency-Key`. Store that key and the original request when retrying an uncertain result. Identical successful requests replay the original status/body; conflicting key reuse is 409. Authentication and role checks still run before replay.

Core routes: `/api/me`, `/api/inventory`, `/api/dashboard`, `/api/orders`, `/api/orders/<id>`, `/api/orders/<id>/{reserve,ship,cancel,returns}`, `/api/stock/adjustments`, and `/api/audit`. Creation returns 201; other successful domain operations return 200. Errors contain `{error:{code,message}}`. Audit entries include the required fields plus additive `details` for stock reasons and affected order lines.

Python's threaded HTTP server and SQLite WAL keep the installation small. One `BEGIN IMMEDIATE` transaction covers domain changes, versions, one audit event, status history, and the stored retry response. Database constraints reinforce integer/nonnegative stock and returned-quantity invariants. All lookups are scoped to the authenticated tenant. Passwords are independently salted PBKDF2 hashes; bearer tokens are opaque and hashed at rest.

Lists are oldest-first, default to 20 entries, accept limits 1–100, and return a signed cursor. Search is case-insensitive, literal substring matching. Pagination freezes the original membership and excludes later inserts, including when filtered orders transition while paging. Order bodies show current committed values, so an order on a historical filtered page may now have a different status; refresh the list to reapply current filters. Cursors survive restart.

See [architecture.md](architecture.md) for schema, invariants, transaction boundaries, reuse, security, error handling, and tradeoffs.

## Verification

Commands to reproduce the checks are below. This environment used the supplied isolated Chromium connection. Final evidence is stored in [evidence/](evidence/).

```sh
# Real HTTP route tests, isolated SQLite stores, concurrency, and restarts
python3 -m unittest discover -v

# Optional browser dependencies, pinned by package-lock.json (Node 20+)
./setup.sh --browser

# Normal local browser setup: downloads stay inside this project
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" python3 scripts/run_browser.py

# In the supplied environment with its isolated browser connection
python3 scripts/run_browser.py

# Independent fresh stores for each reproducible performance run
python3 scripts/load.py --concurrency 1 --output evidence/performance-c1.json
python3 scripts/load.py --concurrency 8 --output evidence/performance-c8.json
```

The browser runner uses `EVAL_BROWSER_WS` when supplied, otherwise it launches a local headless Chromium. `setup.sh --browser` installs Playwright locally; when a supplied browser exists it skips downloading a browser. No browser account/profile is used. The app itself does not require Node or Playwright.

The **15 route tests** cover authentication and roles, tenant/object isolation, untrusted fields, integer and JSON validation, zero-price orders, reservation/cancellation/shipping, partial/full returns, rollback of multi-line failures, stale versions, concurrent competing reservations/adjustments, simultaneous identical retries, conflicts, failed-key reuse, pagination under inserts/status changes, dashboard/audit agreement, graceful restart, process-kill recovery, and SQLite integrity. They compare persisted domain tables before and after rejected operations, not only response codes.

The **11 browser scenarios** cover login errors, admin adjustments, stale input preservation, multi-line fulfillment, returns, cancellation, stock failure, a deliberately lost successful response and safe retry, inert hostile-looking client text, filtering/empty states, audit details, viewer restrictions, tenant switching, 390px mobile use, page reload/logout, keyboard focus, load-more pagination, and rapid double submission. The final run had no uncaught browser exceptions or HTTP 5xx responses. See [browser-results.json](evidence/browser-results.json), [browser-tests.txt](evidence/browser-tests.txt), and [api-tests.txt](evidence/api-tests.txt).

Screenshots from the actual browser workflow:

- [Desktop inventory and stock adjustment](evidence/inventory-desktop.png)
- [Desktop order and returns](evidence/order-detail-desktop.png)
- [Mobile order and return inputs](evidence/order-mobile.png)
- [Mobile inventory](evidence/inventory-mobile.png)
- [Audit history](evidence/audit-desktop.png)
- [Login](evidence/login-desktop.png)

## Measured performance

Measurements on **2026-09-27**, macOS 27.0 arm64, **10 logical CPUs**, Python 3.12.14, SQLite 3.53.1. The sandbox did not expose the CPU model or RAM through `sysctl`; neither is guessed. Client and server ran on the same host. Each run used a fresh SQLite store and one authenticated synthetic north operator. Startup/login and 20 read warmups were excluded.

Each write phase ran **2,000 complete two-line workflows** (create → reserve → ship → full return), totaling **8,000 POSTs**. Each read phase then ran **10,000 GETs**, evenly distributed over inventory, dashboard, the first 20 orders, and the first 20 audit events. A fixed thread pool used one persistent HTTP/1.1 connection per worker. Each worker waited for a response before its next request. Latency includes request encoding, loopback HTTP, and JSON decoding; throughput uses phase wall time. Percentiles use nearest rank. Queue time before a worker starts is excluded. These are short closed-loop local measurements, not a saturation or long-duration test.

| Workers | Phase | Requests/sec | p50 ms | p95 ms | p99 ms | Max ms | Errors |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Writes | 1,103.71 | 0.882 | 1.037 | 1.197 | 31.248 | 0 / 8,000 |
| 1 | Reads | 2,092.90 | 0.454 | 0.623 | 0.762 | 22.979 | 0 / 10,000 |
| 8 | Writes | 2,330.14 | 0.406 | 5.087 | 49.877 | 1,416.101 | 0 / 8,000 |
| 8 | Reads | 845.59 | 4.395 | 27.200 | 29.543 | 42.110 | 0 / 10,000 |

Both runs finished with all 2,000 orders returned, exact initial stock restored, zero reservations, exactly 8,000 audit events and retry records, and passing SQLite integrity/foreign-key checks. Full timings and methodology are in [performance-c1.json](evidence/performance-c1.json) and [performance-c8.json](evidence/performance-c8.json).

Eight workers improved write throughput but increased its tail latency substantially. Read throughput decreased with concurrency; this implementation is not claimed to scale linearly. It opens a database connection per request and performs multiple queries when assembling order lists. Thread/query contention is a plausible contributor, but no profiler was run to attribute the slowdown. The measurements include the client, host, OS caches, and local filesystem behavior and should not be extrapolated to remote deployments.

## Limits and development findings

- The app is complete for the requested local workflow. There are no known failing final checks. Cross-browser behavior, assistive-technology testing, power-loss durability, and extended soak testing were not run.
- This is an embedded, single-writer local app. It has no deployment, TLS, multi-process scaling setup, user onboarding/password management, or server-side logout revocation. Local logout clears the tab token; a copied token expires after 12 hours. Login throttling is not implemented.
- Audit, retry responses, and status history grow indefinitely. There is no retention policy or schema upgrade framework. Stop the server before copying the whole data directory for backup.
- Unsaved forms survive validation/stale errors but are discarded on navigation; there is no offline queue. Server-side prices are authoritative. Monetary display assumes USD because the task supplies cents without a currency.
- A preliminary large load driver opened a new TCP connection per request and exhausted local ephemeral ports. The final driver and HTTP server use persistent connections; the reported reruns passed. A first browser filter assertion observed the previous table before the response; the test now waits for the filtered result. Screenshot review led to the stacked mobile return layout. See [evidence/verification.md](evidence/verification.md).
