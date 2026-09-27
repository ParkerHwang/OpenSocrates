# DepotFlow architecture

## Components

- `server.py` contains the HTTP routes, validation, authentication, SQLite schema/bootstrap, transactions, and static-file serving.
- `static/index.html`, `static/app.js`, and `static/style.css` form the same-origin browser client. Dynamic API text is assigned with `textContent` or DOM nodes rather than interpreted as HTML.
- `tests/test_api.py` starts the actual server against a temporary `DATA_DIR`; `load_test.py` runs concurrent localhost reads and writes against an already started instance.

There are no runtime dependencies outside Python 3's standard library. SQLite is the only persistence service and is created under `DATA_DIR`.

## Data model and invariants

`users` and `sessions` establish the authenticated tenant context. `inventory` has a `(tenant, sku)` primary key, `on_hand >= 0`, `reserved >= 0`, `reserved <= on_hand`, and a monotonically increasing version. `orders` has a tenant-local unique `client_ref`, immutable creation sequence, status, version, and total. `order_lines` stores positive quantities, server catalog price snapshots, and returned quantity. `audit` and `idempotency` are tenant-scoped.

The server never accepts tenant, role, price, or unit-price values from a client. Order creation reads the authenticated tenant's catalog and snapshots its prices. `available` is computed as `on_hand - reserved`; it is never stored separately, so it cannot drift.

## Transaction boundaries

All successful mutation requests use one SQLite `BEGIN IMMEDIATE` transaction:

1. Authenticate and authorize before looking for an idempotency replay.
2. Lock the database for the short mutation transaction.
3. Validate the current order/inventory versions and state.
4. Update all affected stock and order rows.
5. Add exactly one audit event for the stock adjustment, order creation, or order transition.
6. Store the successful status/body under the tenant-scoped idempotency key and commit.

Any exception rolls back the entire transaction. A reservation checks every line before changing any line, so multi-line insufficient stock cannot partially reserve. A second concurrent reservation waits for the first transaction and then observes its committed reserved quantity. Replay returns the stored status/body without creating another audit event. Failed requests are rolled back and do not consume the key. A changed method/path/payload under an existing key is a 409 conflict.

Inventory versions increment when stock state changes. Order versions start at 1 and increment exactly once per successful reserve, ship, cancel, or return operation. A stale expected version is rejected before mutation.

## Authentication, authorization, and isolation

`POST /api/session` compares the stored synthetic demo password hash and creates a random bearer token. All other protected routes resolve the token to a server-side user/session row. Viewer writes receive 403; stock adjustment additionally requires admin. Every protected query includes the authenticated tenant. Missing/invalid tokens return 401, and an object absent from that tenant returns 404 rather than revealing another tenant's existence.

## Error handling and frontend behavior

Route validation maps malformed JSON, missing fields, booleans/fractions where integers are required, invalid filters, and unknown SKUs to 400. Stale versions, illegal transitions, insufficient stock, over-returns, duplicate client references, and idempotency conflicts map to 409. The JSON shape is always `{error:{code,message}}` for API errors. Unexpected server faults are kept generic in the response.

The browser disables submit buttons during asynchronous mutation, refreshes order detail after transitions, shows server errors, preserves form fields on failures, and omits writable action controls for viewers. It provides semantic labels, native selects/inputs, keyboard-operable buttons, responsive tables, and mobile layout rules. The browser currently loads up to 100 orders for its client-side filter; API cursor pagination remains available to other clients.

## Operational boundaries

This is a local reference application, not a production security perimeter. It deliberately has no password reset, session expiry, TLS termination, rate limiting, backups, or multi-process deployment configuration. Those are material follow-up requirements before exposing it beyond localhost.
