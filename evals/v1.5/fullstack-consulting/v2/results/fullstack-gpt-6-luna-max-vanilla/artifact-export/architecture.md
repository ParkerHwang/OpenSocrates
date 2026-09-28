# DepotFlow architecture

## Components

`app.py` owns HTTP routing, authentication, validation, transactions, and SQLite access. The HTML/CSS/JavaScript under `static/` is served by the same origin. `run.sh` starts one local process and reads `PORT`, `DATA_DIR`, and `SEED_DEMO` from the environment. No network service or runtime package install is required.

SQLite is the source of truth. The schema separates tenants, users, sessions, inventory, orders, order lines, audit events, and idempotency records. Tenant identity is stored on every tenant-owned record. Composite uniqueness constraints protect client references and line identities within a tenant. Database checks enforce nonnegative on-hand/reserved stock, `reserved <= on_hand`, positive quantities, nonnegative prices, and valid returned quantities.

## Invariants

- **Tenant boundary:** the authenticated session resolves to one user, tenant, and role. Every domain query and mutation includes that tenant. Client-supplied tenant and role values are ignored. An order ID found only in another tenant is indistinguishable from an unknown ID (`404`).
- **Stock:** available is derived as `on_hand - reserved`; there is no separately mutable available counter. `reserved <= on_hand` and both counts are nonnegative. Reservation checks all lines before updating any line.
- **Order pricing:** catalog prices come from the tenant inventory catalog when the order is created and are copied into its lines. Order totals use those snapshots. Request fields such as `unit_price_cents` cannot set price.
- **Versioning:** new orders and seeded inventory rows start at version 1. Each successful order transition increments the order version once. Each inventory row changed by a transition increments its version once for that transition. Stale expected versions fail with `409` before a transition.
- **Returns:** return quantities accumulate per order line and cannot exceed shipped quantities. Returned stock increases on-hand; partial returns remain `shipped`, and the order becomes `returned` only when all lines are fully returned.
- **Audit:** one event is inserted for each successful order create, stock adjustment, and order transition. Validation failures, stale writes, insufficient stock, and idempotency replays add no events.

## Transaction boundaries

Every domain mutation starts `BEGIN IMMEDIATE`. SQLite obtains the writer reservation before reading mutable state, so two reservation requests cannot both validate against the same available counts. A reserve transaction performs all line availability checks, adjusts all line reservations and versions, updates the order/version, writes an audit row, records the idempotent response, then commits. If any validation or state check fails, the transaction rolls back with no partial stock, order, audit, or idempotency change.

Ship, cancel, returns, and admin stock adjustment follow the same boundary. The transaction also inserts the successful response body and status into `idempotency`; a retry using the same tenant key, method, path, and canonical JSON body returns that saved response without re-running the domain mutation. Reusing the key for a different request returns `409`. The per-tenant primary key on `(tenant_id, key)` plus the write transaction handles concurrent duplicate requests. Failed requests do not reserve the key.

Reads use independent SQLite connections. Order and audit cursors advance by stable insertion IDs, preserving oldest-first traversal for existing matches. Search uses Unicode case-folded substring matching. The dashboard is computed from committed order and inventory rows at request time.

## Authentication and authorization

`POST /api/session` verifies a salted PBKDF2-HMAC-SHA256 password hash and stores a random bearer token mapped to the user in SQLite. Protected routes look up that token and derive email, role, and tenant from the joined user record. No tenant or role request header is consulted.

Authentication and role checks run before idempotency replay. Viewers are read-only; only admins can adjust stock; admins and operators can create or transition orders. Demo sessions persist across process restarts. The local logout control removes the bearer token from browser storage. There is no session expiration/revocation UI in this compact demo.

## Validation and errors

The HTTP layer accepts and returns JSON for API calls. Payload validators reject booleans and fractional values where integers are required, enforce positive line quantities, reject duplicate line SKUs, and check required strings and enum filters. Unknown SKUs are `400`; malformed payloads/cursors are `400`; missing or invalid credentials are `401`; role failures are `403`; cross-tenant/missing objects are `404`; stale versions, invalid transitions, insufficient stock, key conflicts, duplicate client references, and return overruns are `409`.

Expected API failures return `{ "error": { "code": "…", "message": "…" } }`. Unexpected exceptions return a generic `500` body without database paths or stack details. The browser builds dynamic content with DOM nodes and `textContent`, so client references, actors, and errors are not interpreted as HTML. A failed form mutation leaves entered values in place; stale-version messages tell the user to refresh the order before retrying.

## Reuse and tradeoffs

Stock summaries, tenant filtering, order retrieval, integer/string validation, expected-version checking, audit insertion, and idempotency recording are shared helpers used by the route handlers. Python's standard library keeps setup reproducible and small. SQLite's single-writer model is appropriate for two local operators and gives atomic state transitions without an external service; it limits write concurrency and is not a horizontally scaled deployment design. Demo users share one synthetic password by task design, and the local token store has no expiration mechanism.
