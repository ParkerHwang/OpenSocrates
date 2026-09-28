# DepotFlow

DepotFlow is a locally runnable, two-tenant fulfillment workspace. Operators create orders, reserve stock, ship, cancel, and record returns. Admins can also adjust stock. Viewers can inspect inventory, orders, dashboard totals, and audit history. The browser UI and JSON API share one origin.

## Start

Python 3.9+ with its built-in `sqlite3` module is the only runtime dependency. No installation, container, account, or external database is needed.

```sh
PORT=8000 DATA_DIR="$PWD/data" SEED_DEMO=1 ./run.sh
```

Open <http://127.0.0.1:8000/>. The server binds only to `127.0.0.1`. `PORT` defaults to `8000`, and `DATA_DIR` defaults to `./data`. `SEED_DEMO=1` populates `north` and `south` only when the tenant store is empty. Restart with the same `DATA_DIR` to keep all orders, stock changes, sessions, audit events, and idempotency responses. The SQLite database is `DATA_DIR/depotflow.sqlite3`.

Demo accounts for each tenant are `admin@north.example`, `operator@north.example`, `viewer@north.example`, and the corresponding `@south.example` addresses. All use the synthetic password `DepotDemo!2026`. Each tenant begins with BOLT 100 at 1,250 cents, CABLE 60 at 2,499 cents, and SAMPLE 20 at 0 cents.

The API is rooted at `/api`. For example:

```sh
curl http://127.0.0.1:8000/api/health
curl -s -H 'Content-Type: application/json' \
  -d '{"email":"operator@north.example","password":"DepotDemo!2026"}' \
  http://127.0.0.1:8000/api/session
```

Pass the returned token as `Authorization: Bearer <token>`. Every state-changing request other than session creation also needs a nonempty `Idempotency-Key`. The UI generates and retains a key while retrying a pending action. The API contract and state rules are detailed in [architecture.md](architecture.md).

## Implementation

The backend uses Python's `ThreadingHTTPServer` and SQLite in WAL mode. Each request opens its own database connection. A `BEGIN IMMEDIATE` transaction serializes each mutation with its idempotency lookup, order and stock changes, and audit insert. SQLite constraints add protection for nonnegative stock and valid line quantities. Passwords are PBKDF2-HMAC-SHA256 hashes; sessions use random bearer tokens stored as SHA-256 hashes. The frontend is plain HTML, CSS, and JavaScript with semantic forms and DOM text nodes for untrusted values.

This small dependency-free stack makes the project easy to run and inspect. Its tradeoffs are a single SQLite writer at a time, one server process, and a demo-oriented session model. Tokens have no expiry or server-side logout endpoint; the UI removes its session token on logout. Add expiry, revocation, HTTPS, user management, and operational backup procedures before any production use. Order pagination persists match snapshots so status changes during paging cannot remove an item from an existing result set; those snapshot rows are retained without automatic cleanup in this local implementation.

The stack choice used the task's hard requirements—local startup, durable state, tenant isolation, and atomic stock operations—as veto conditions. Setup effort, implementation clarity, and UI usability were preferences inferred from the request, with no numeric weights. Python plus SQLite met the hard requirements with no packages (verified by the startup and tests). Node plus SQLite was also feasible but would add a package/build setup for this project (inferred), while a custom file store would require substantially more transaction and recovery code (inferred); neither alternative was measured as a speed comparison. The chosen stack gives up a larger frontend component ecosystem and parallel SQLite writes. A pre-existing Node codebase or a requirement for sustained multi-process writes would reopen the choice; neither is present here. The short local load run does not resolve production-scale performance.

## Verification

Run the route and persistence suite:

```sh
python3 -m unittest discover -s tests -v
```

The suite exercises login and token failures, roles, tenant isolation, payload validation, zero-price orders, full fulfillment and returns, stale versions, stock adjustments, atomic multi-line failure, simultaneous oversell contention, concurrent identical retries, cursor stability, audit/dashboard agreement, and restart persistence. It uses a temporary store and starts the actual HTTP server.

The browser exercise uses the Playwright installation and remote Chromium WebSocket described in `TOOLING.md`. With the server running at port 8765 and `EVAL_BROWSER_WS` set, run:

```sh
node tests/browser.cjs
```

It signs in as a north operator, creates a two-line order, reserves, ships, records a partial and a full return, reads audit history, and searches the order list. It then signs in as a north admin to adjust stock, and as a south viewer to check read-only isolation at a 390-pixel mobile viewport. `BASE_URL` can override the default `http://127.0.0.1:8765/`. Captures from the completed run are [desktop audit](browser-workflow.png) and [mobile inventory](browser-mobile.png).

Run the repeatable local load exercise:

```sh
python3 tests/load.py --reads 300 --workflows 80 --concurrency 8
```

It creates a fresh temporary database and server, adds enough BOLT stock, then runs 300 round-robin reads of inventory/orders/dashboard followed by 80 concurrent create → reserve → ship workflows (240 write requests). It reports throughput, p50/p95/max HTTP latency, and error counts to [performance-results.json](performance-results.json). On this macOS 27 arm64 host with 10 logical CPUs and Python 3.12.14, the final run measured **3,489.8 read requests/s** (p50 1.99 ms, p95 3.27 ms, 0 errors) and **2,110.5 write requests/s** (p50 0.52 ms, p95 11.42 ms, 0 errors). The phases lasted 0.086 and 0.114 seconds, respectively; these are short local-loopback samples, not sustained capacity claims. An earlier 8-client run showed 18 read transport errors with the default HTTP accept backlog. Raising it to 128 was followed by repeated zero-error runs. See [verification.md](verification.md) for the exact checks and limits.
