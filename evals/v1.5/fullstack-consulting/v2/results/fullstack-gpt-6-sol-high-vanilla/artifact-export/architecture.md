# DepotFlow architecture

The process serves static files at `/` and JSON routes at `/api` over the same loopback origin. Each request opens a SQLite connection to `DATA_DIR/depotflow.sqlite3`; WAL mode and a busy timeout allow readers alongside a single serialized writer. Tables hold tenants, users, hashed session tokens, inventory, orders, order lines, audit events, and idempotency results. The seed step inserts both tenants, six users, and independent stock rows only when no tenant exists. A later start does not overwrite committed data.

## Invariants and transactions

Inventory rows belong to one tenant and SKU. Database checks enforce `on_hand >= reserved >= 0`; `available` is calculated as `on_hand - reserved`. Order lines hold server catalog price snapshots and returned quantities. A draft starts at version 1. A successful transition increments its version once. Inventory versions increment once per changed SKU per operation, and stock adjustments require the expected inventory version.

Every mutation enters `BEGIN IMMEDIATE` before looking up its idempotency key or reading stock and order state. This reserves SQLite's write lock and prevents two request threads from both seeing the same available stock or unused retry key. Reserve checks every line before changing any row; ship subtracts on-hand and reserved together; cancellation releases reservations; returns check every requested line before adding stock. Order change, stock change, audit event, and the saved successful response commit in one transaction. An exception rolls them all back. Database constraints add a second line of defense against negative stock.

The idempotency primary key is `(tenant, key)`. After authentication and role authorization, a mutation compares the stored method, exact URL path and canonical JSON body. An exact match replays the stored status and body; a mismatch returns 409. Failed mutations never save a key. This also handles identical concurrent calls and persists across restarts. Client references have a separate `(tenant, client_ref)` uniqueness constraint, so a different create key cannot reuse a reference.

Order and audit IDs increase monotonically. Pagination sorts by ID ascending and encodes the last ID, a first-page high-water ID, and filters in an opaque base64 cursor. Pages stay within that high-water mark, preventing later inserts from shifting them. Invalid limits, filters and cursors return 400. This is a high-water traversal rather than a historical snapshot of mutable order statuses.

## Reuse, identity and errors

The same tenant-qualified order and inventory helpers are used by reads and mutations. The server derives tenant and role only from the bearer token's user row; client headers and JSON fields cannot override them. Passwords are salted PBKDF2-SHA256 hashes, and only SHA-256 hashes of random session tokens are stored. Viewer mutations return 403 before idempotency replay; another tenant's order is looked up with the caller's tenant and returns 404. Admin-only stock adjustments are checked before transaction entry.

Validation helpers reject booleans and fractional numbers where JSON integers are required, enforce positive line quantities, and reject duplicate SKUs. Expected-version conflicts, invalid transitions, stock shortages and retry conflicts return 409. Invalid payloads and query parameters return 400; missing or invalid bearer tokens return 401. Errors use `{ "error": { "code": "...", "message": "..." } }` so the UI can show useful feedback. The frontend uses one API wrapper and refreshes relevant views after successful mutations. It disables controls during requests, retains order/return/stock form values after failures, and offers explicit refresh controls for stale data.
