# DepotFlow architecture

## Boundary and authentication

The server and UI share one origin. `GET /` serves the browser assets and `/api/*` serves JSON. `GET /api/health` is the only unauthenticated API route. `POST /api/session` looks up the email, verifies the PBKDF2-SHA256 password hash, and returns a random bearer token plus the server-owned `{email, role, tenant}` identity. The token map is process-local and deliberately expires on process restart; persistent business data never depends on a token surviving restart.

The request handler never accepts tenant or role from a header or request body. After authentication, all reads and writes use the tenant carried by the token. Object lookup is tenant-qualified, so an object belonging to another tenant is indistinguishable from a missing object and returns 404. Viewer mutation checks occur before mutation/idempotency replay and return 403.

## Persistent model

SQLite tables are:

- `users`: demo identities, roles, tenant, password hash.
- `inventory`: one catalog row per `(tenant, sku)` with on-hand, reserved, price, and optimistic version.
- `orders` and `order_lines`: tenant-local client references, lifecycle status, version, price snapshots, and returned quantities.
- `audit`: append-only tenant-scoped events with actor and timestamp.
- `idempotency`: tenant-scoped key, request identity/hash, original status, and original JSON response.

The order `seq` integer is the stable oldest-first ordering key. Cursors encode the last sequence position and, for orders, the active filters. Audit cursors encode the last audit ID. A cursor that is malformed or does not match the current order filters is rejected rather than silently skipping records.

## Invariants

1. `on_hand >= 0`, `reserved >= 0`, and `available = on_hand - reserved`.
2. A reservation checks every order line before changing any inventory row. The entire check and update is one `BEGIN IMMEDIATE` transaction, so concurrent reservations cannot oversell.
3. Shipping subtracts the shipped quantity from both `on_hand` and `reserved`, preserving available stock at that instant.
4. Cancellation of a reserved order releases every reservation; cancellation after shipping is rejected.
5. A return is accepted only for a shipped order, only for its own non-repeated SKUs, and only up to shipped quantity. Returned units are added back to on-hand. All-line return changes status to `returned`.
6. Every order mutation compares `expected_version` while holding the write transaction and increments the order version exactly once on success. Inventory rows touched by stock movement also advance their version.
7. A successful stock adjustment, order creation, or order transition writes exactly one audit event in the same transaction as the business update. A rejected request rolls back everything; an idempotency replay returns the stored response without a new event.
8. Client-supplied price, tenant, role, and extra fields cannot override server catalog data or authenticated identity. Order lines snapshot the catalog price at creation.

## Transaction boundaries and retries

`perform_mutation` is the shared write wrapper. It begins an immediate transaction, checks the `(tenant, Idempotency-Key)` record, rejects a changed method/path/canonical JSON payload, or returns the stored success response. If no record exists it calls the operation-specific mutation, inserts the response record, and commits. Failed validation and business conflicts roll back, so the key remains available for a corrected retry. SQLite's writer serialization also makes simultaneous identical keys converge on one effect: the second transaction sees the first committed record and replays it.

The order create, reservation, shipment, cancellation, return, and stock adjustment implementations reuse this wrapper and the shared order/inventory serializers. Reads use short-lived connections and do not hold a write transaction.

## Error handling

Malformed JSON, wrong types, nonpositive quantities, unknown SKUs, invalid filters, and invalid cursors return 400. Missing or invalid credentials return 401. Viewer or non-admin forbidden operations return 403. Missing tenant-scoped objects return 404. Stale versions, invalid lifecycle transitions, insufficient stock, duplicate client references, return overflow, and idempotency conflicts return 409. The UI displays the server message, disables buttons while a request is pending, refreshes committed views after success, and leaves API error responses visible instead of silently treating a conflict as success.

## Frontend workflow

The UI has login/logout, dashboard and inventory, searchable order queue, multi-line order creation, order detail actions, returns, and audit history. It renders only server-provided text through DOM properties. It hides all writable controls for viewers while leaving inventory/orders/audit reads available. Layout uses responsive CSS grids and horizontal table scrolling for narrow screens. Required `data-testid` markers are in the corresponding controls, including repeated native SKU selects, quantities, return inputs, and audit/inventory tables.

## Operational tradeoffs and limits

This project is intentionally dependency-free and local. It does not provide TLS, external identity, token revocation, background jobs, a migration framework, backups, multi-process session sharing, or horizontal scaling. In a production deployment those concerns should be supplied by the environment and the single-file SQLite database should be replaced or carefully replicated. The included tests and load driver verify the stated local behavior, not those production concerns.
