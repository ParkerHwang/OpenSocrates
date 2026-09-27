# DepotFlow architecture

DepotFlow is a same-origin, single-process web application built with Python's
standard-library `http.server` and SQLite. The browser UI is dependency-free
HTML, CSS, and JavaScript. `run.sh` binds the server to `127.0.0.1`; `PORT`,
`DATA_DIR`, and `SEED_DEMO` are the only runtime inputs.

## Data ownership and tenant isolation

SQLite is the source of truth. Each tenant-owned root table carries
`tenant_id`; child order lines are reached only through an order already scoped
to that tenant. Every tenant-scoped read, update, audit query, and idempotency
lookup uses the authenticated tenant. Orders use a global integer primary key,
but an order is only returned when its ID and the caller's tenant match, so a
foreign ID is a 404 without revealing its contents. The server derives tenant
and role solely from the bearer token's session row; request bodies and headers
cannot override them.

Inventory rows own `on_hand`, `reserved`, `price_cents`, and `version`.
`available` is a response-only calculation (`on_hand - reserved`). Order lines
own the server-price snapshot and `returned_quantity`; later catalog changes do
not change historical order totals. The dashboard is derived directly from
committed order and inventory rows, rather than a cache.

## Transactions and invariants

Each mutation opens a SQLite `BEGIN IMMEDIATE` transaction. SQLite's write lock
serializes competing stock mutations in this local process and across server
restarts. A successful order transition updates the order, every affected stock
row, its audit event, and its idempotency record before commit. A validation or
business conflict rolls the transaction back, so it cannot leave a partial
reservation, shipment, return, version increment, or audit event.

The relevant invariants are:

- `on_hand >= reserved >= 0` and `available = on_hand - reserved`.
- A reserve is allowed only for a draft order and checks every line while the
  write transaction is held; all stock is reserved or none is.
- Shipping a reserved order decrements both `on_hand` and `reserved`, so
  available stock does not change at the shipment instant.
- Cancelling a reserved order releases its line quantities; cancelling a draft
  order changes no stock.
- A return is accepted only for a shipped order and cannot exceed each line's
  shipped-minus-already-returned quantity. A full return changes status to
  `returned`.
- Order versions begin at 1 and increment once per successful transition.
  Inventory versions increment for every stock mutation, including reservation,
  shipment, cancellation release, return, and manual adjustment.

## Authentication and authorization

`POST /api/session` verifies the seeded password using PBKDF2-HMAC-SHA256 and
creates a random bearer token whose SHA-256 digest is persisted in SQLite.
`GET /api/me` and all protected routes resolve that token to the persisted user.
Sessions and idempotency records survive a process restart. A viewer can read
inventory, dashboard, orders, and audit history, but every domain mutation is
rejected with 403. Stock adjustments require an admin; order creation and
transitions allow admin and operator roles.

Authentication and role checks run before idempotency replay. Missing or invalid
tokens are 401, forbidden roles are 403, and a tenant's attempt to access an
order owned by another tenant is 404.

## Idempotency and error handling

Every authenticated POST mutation except session creation requires a nonempty
`Idempotency-Key`. The key is unique per tenant across mutation paths. Inside the
same write transaction the server compares method, route path, and a canonical
JSON payload hash. An exact successful match returns the stored status/body
without another business write or audit event. A changed path or payload is a
409 conflict; rejected requests never insert a key. Because the idempotency row
commits with the business mutation, replay remains available after restart and
the lock prevents concurrent identical requests from duplicating effects.

Errors use `{ "error": { "code": "...", "message": "..." } }`. Payload shape,
integer, duplicate-SKU, filter, and cursor errors are 400. Authentication is
401, authorization is 403, unknown tenant-owned objects are 404, and stale
versions, invalid state transitions, insufficient stock, client-reference
conflicts, return conflicts, and idempotency conflicts are 409.

## API/UI reuse and limits

The server keeps pure validation/serialization helpers shared across routes and
one transaction wrapper for all idempotent mutations. The UI uses one fetch
client, one mutation helper for fresh idempotency keys, and DOM `textContent`
when displaying server data. It refreshes inventory/dashboard after stock or
order mutations and refreshes orders/detail after order changes.

This is intentionally a local operator tool, not a distributed service. SQLite
write serialization is appropriate for the requested disposable local setup but
limits write concurrency. Tokens do not expire, there is no password reset or
external identity provider, and there is no background job queue. The load
exercise documents observed local performance rather than a production capacity
claim.
