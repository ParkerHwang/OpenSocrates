# DepotFlow architecture

## Components

- `app.py` runs a `ThreadingHTTPServer` bound to `127.0.0.1`, serves the static browser files, and implements the JSON routes.
- `static/` contains a no-build HTML/CSS/JavaScript client. It uses same-origin `fetch`, native form controls, and DOM `textContent` for untrusted API strings.
- SQLite at `$DATA_DIR/depotflow.sqlite3` holds tenants, users, bearer sessions, inventory, orders and lines, audit events, and idempotency responses.
- `tests/test_api.py` starts the executable server and drives its actual HTTP routes. `scripts/benchmark.py` starts a separate seeded server and measures a repeatable mixed workload.

The implementation has no runtime dependencies beyond Python and SQLite. A single process is the supported deployment shape. The threaded HTTP server handles independent reads concurrently; SQLite permits many readers but serializes write transactions.

## Data and tenant boundaries

Tenant IDs are internal database IDs. A bearer token is generated at login and stored only as a SHA-256 hash in `sessions`; each protected request resolves the token through `sessions → users → tenants`. The resulting user context supplies `tenant_id`, role, email, and tenant slug. Request bodies and headers are never used to select a trusted tenant or role.

Every inventory, order, order-line, audit, and idempotency query includes the authenticated tenant. Order IDs are globally random, but lookups still require both tenant and ID; a foreign order therefore returns 404. Inventory is keyed by `(tenant_id, sku)`. Order client references are unique within a tenant. Audit and cursor results are tenant scoped, and cursors encode both tenant and resource type so they cannot be reused across tenant/resource boundaries.

Passwords use salted PBKDF2-HMAC-SHA256 hashes (180,000 iterations). Session tokens survive process restart because they are stored in SQLite. The demo does not expire or revoke tokens through a UI; signing out removes the browser’s token but does not delete the server-side session.

## Inventory and order invariants

SQLite checks enforce nonnegative `on_hand`, `reserved`, prices, versions, and return quantities, and ensure `reserved <= on_hand`. API validation rejects booleans and fractional values where JSON integers are required. `available` is derived as `on_hand - reserved` and is not independently stored.

Catalog prices are read from the tenant’s inventory catalog at order creation and snapshotted into immutable order lines. Order totals are computed from those server prices. A nonempty SAMPLE-only order has a zero total and remains a normal draft order.

Order version starts at 1. Every successful transition updates status and increments the order version once. Inventory versions increment once per affected SKU for adjustments, reservations, shipment, cancellation release, and returns. An `expected_version` mismatch returns 409 before the mutation commits.

## Transaction boundaries

Each business mutation and its idempotency record use a single `BEGIN IMMEDIATE` SQLite transaction. `BEGIN IMMEDIATE` obtains SQLite’s writer reservation before checking current stock or the idempotency key, so concurrent handlers cannot both reserve the same available units. The operation then validates every line, changes the necessary inventory/order rows, inserts exactly one audit event, stores the successful response, and commits. Any validation or transition error rolls the transaction back, including inventory changes and audit rows; failed requests do not reserve their idempotency key.

Order reservation first checks availability for every line and only then updates any SKU. Shipment reduces `on_hand` and `reserved` by equal amounts. Cancellation releases reservations only when the order was reserved. Return lines are all validated before any quantity is restored; partial returns retain `shipped`, and the order becomes `returned` when all line quantities have been returned.

Idempotency is keyed by `(tenant_id, key)` and fingerprints the HTTP method, decoded route path, and canonical JSON object. Matching requests replay their saved status and body from the same database transaction. A changed path, method, or payload under the same tenant/key produces 409. Authentication and role checks happen before key replay, including after restart.

Dashboard and inventory reads use a SQLite read transaction so related values come from one committed snapshot. Order/audit pagination is oldest-first and uses monotonically increasing database IDs as stable cursors; a new request includes only rows after the last returned ID.

## Reuse and error handling

Shared helpers centralize connection setup, strict integer/payload validation, inventory/order serialization, optimistic-version validation, audit creation, and cursor encoding. Route-specific mutations run through one idempotent transaction wrapper rather than duplicating transaction policy.

Expected request, authorization, isolation, conflict, and transition errors return `{ "error": { "code": "...", "message": "..." } }` with HTTP 400, 401, 403, 404, or 409 as appropriate. Stale versions, insufficient stock, invalid transitions, capacity constraints, and changed idempotency keys return 409. Unexpected server exceptions return a generic 500 body without exposing database details. SQLite constraints provide a final invariant check if application validation is bypassed.

## Deliberate limits

This is a compact local application, not a public multi-process service. SQLite serializes writes and the server does not implement TLS, session expiry/revocation, rate limits, account management, automated backups, or database migration tooling. The synthetic credentials are intentionally shared by role and tenant for local evaluation. The measured workload is a small loopback benchmark and does not represent a production capacity test.
