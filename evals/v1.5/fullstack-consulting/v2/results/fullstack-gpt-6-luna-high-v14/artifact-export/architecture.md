# DepotFlow architecture

## Components

- `server.py` is a dependency-free Python 3 HTTP server built on
  `ThreadingHTTPServer`, `http.server`, and SQLite.
- `static/` contains the same-origin semantic HTML, responsive CSS, and plain
  JavaScript client. The browser stores only the bearer token in local storage;
  the server stores only its SHA-256 digest.
- `run.sh` starts the service. SQLite files live in `DATA_DIR`.

## Data and invariants

Every tenant-owned row carries `tenant`; reads and mutations select by the
authenticated user's tenant. Order IDs are random UUIDs. Inventory uses a
`(tenant, sku)` key. Orders have a tenant-local unique client reference. User
role and tenant come only from the user row resolved from the bearer token.

SQLite `CHECK` constraints prevent negative on-hand and reserved units and
prevent reserved from exceeding on-hand. API numeric validation rejects JSON
booleans and fractional values where integers are required. Catalog prices are
read from inventory at creation and copied into order lines. The totals are
computed server-side.

## Transaction boundaries

Each write request opens a connection and executes `BEGIN IMMEDIATE` before
checking/replaying its tenant-scoped idempotency key and before making changes.
This obtains SQLite's single-writer reservation before stock validation, so two
reservation requests cannot both use the same available units. A successful
operation commits order/inventory changes, one audit row, and the saved replay
response in one transaction. Any validation or business-rule error rolls back
all of them. A failed request does not insert an idempotency record.

Idempotency records use `(tenant, key)` and a SHA-256 fingerprint of the HTTP
method, URL path, and canonical JSON body. An exact match returns the saved
status and body; a changed request returns 409. Authentication and role checks
run before replay. SQLite persistence makes replay survive a process restart.

Order and audit collections use monotonically increasing internal IDs for
oldest-first pagination. Opaque URL-safe cursors hold the last ID. Order cursors
also bind to status and case-folded search filters. Cursor rows must exist in
the caller's tenant; malformed, foreign-tenant, or filter-mismatched cursors
return 400.

## Authentication and authorization

`POST /api/session` checks a per-user salted PBKDF2-HMAC-SHA256 password hash
(160,000 iterations) and creates a random bearer token. Only the token digest is
stored. The supplied demo password is synthetic and intended only for local
evaluation. Every other API route resolves its user from the bearer token;
client headers or request fields cannot set role or tenant. Viewer mutations
return 403. Other-tenant order IDs return 404 to avoid confirming their
existence. Admin-only inventory adjustments return 403 for operators.

## Error handling and reuse

Expected validation and business errors return `{ "error": { "code",
"message" } }` with 400, 401, 403, 404, or 409 as appropriate. Unexpected
server exceptions return a generic 500 without leaking tracebacks. Helpers for
integer/text validation, inventory response shaping, order shaping, auditing,
authentication, and idempotency are shared across routes.

The service intentionally uses SQLite's single-writer model rather than a
connection pool or external database. This keeps local setup simple and gives
clear transaction semantics for two small operators. It limits write
parallelism and is not a substitute for a production database deployment.
