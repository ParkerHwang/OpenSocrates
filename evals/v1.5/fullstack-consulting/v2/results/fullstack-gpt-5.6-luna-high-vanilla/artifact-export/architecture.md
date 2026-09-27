# DepotFlow architecture

## Data and tenant boundary

SQLite stores tenants, users, sessions, inventory, orders, order lines, audit events and idempotency records in one file below `DATA_DIR`. Every tenant-owned table has a `tenant_id` (or reaches it through an order), and every authenticated read/write query binds the tenant from the server-side session row. Client headers and payload fields are never used to choose tenant or role. An object that exists for another tenant therefore appears as `404` through the tenant-filtered lookup.

The seed catalog is copied independently into `north` and `south`: BOLT 100/$12.50, CABLE 60/$24.99 and SAMPLE 20/$0.00. Passwords are synthetic demo credentials and are stored as SHA-256 hashes for this disposable local exercise; a production deployment should use a slow password hash and external secret management.

## Invariants and transactions

- `on_hand >= 0`, `reserved >= 0`, and `available = on_hand - reserved >= 0`.
- Order quantities are positive integers; returned quantity never exceeds shipped quantity.
- Client references are unique per tenant, and order line SKUs are unique per order.
- Catalog price is read from inventory at creation and snapshotted into order lines.
- Reserve checks every line before changing any line, then increments all reservations in one `BEGIN IMMEDIATE` transaction.
- Ship decrements `on_hand` and `reserved` together, preserving available stock at that instant.
- Cancellation releases reservations; returns increase on-hand stock.
- Successful stock changes/order creation/order transitions insert exactly one audit event in the same transaction.
- Order and inventory versions change on committed changes. Expected versions are checked while the write transaction holds SQLite's writer lock.

SQLite's serialized writer transaction is the oversell protection: concurrent reservations cannot both pass the availability check against the same committed state. A failed validation, stale version, transition, insufficient-stock check or idempotency conflict rolls back all writes.

## Idempotency and authentication

The request authenticates first, then requires a nonempty idempotency key for mutations. The `(tenant_id, key)` primary key scopes a key across all mutation endpoints. The stored method, path and canonical JSON hash must match; a match replays the stored status/body without another audit event, while a mismatch returns `409`. The idempotency row is inserted in the same transaction as the business effect, which covers concurrent duplicates and restart replay. Failed requests do not insert one.

Bearer tokens are random opaque values; only their SHA-256 digest is stored in `sessions`. `/api/health` is public; all other API reads require a valid session. Viewers receive `403` on mutation attempts, and only admins may adjust stock.

## HTTP and UI

`server.py` uses the standard-library threaded HTTP server and emits JSON errors in `{error:{code,message}}`. Query cursors are URL-safe base64 JSON values: orders use `(created_at,id)` and audits use the monotonic audit id. This makes the oldest-first listings stable for the pre-existing matching set; the UI currently fetches its first page and exposes useful empty/loading/error states.

The browser app renders user-controlled values with `textContent`, hides all writable controls for viewers, uses native labels/selects and keyboard-operable buttons, and refreshes inventory, orders and the selected detail after mutations. UI requests create a fresh idempotency key per intent and leave form values present when a request fails.

## Tradeoffs and limits

The service is intentionally compact and dependency-free. SQLite is excellent for this local two-operator exercise and durable single-process writes, but a production multi-host deployment would need a managed database, stronger secret/password handling, TLS, token expiry/rotation, rate limiting, structured logging and operational backups. The load script measures one read endpoint; it is a reproducible smoke measurement, not a benchmark of every write path.

