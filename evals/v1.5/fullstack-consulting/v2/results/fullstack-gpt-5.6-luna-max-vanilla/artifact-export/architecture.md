# DepotFlow architecture

## Components

DepotFlow is intentionally a single local process:

```text
browser ── same-origin HTTP ──> Python ThreadingHTTPServer ──> SQLite (DATA_DIR/depotflow.sqlite3)
                                      ├── static/index.html, app.js, styles.css
                                      └── sessions / idempotency / audit / tenant data
```

The server uses Python's `http.server`, `sqlite3`, and standard-library helpers only. The browser client is a small vanilla SPA. `run.sh` passes the environment-selected data directory and port through to `server.py`; no network database, container, package manager, or account is required.

## Persistent model

- `tenants` contains `north` and `south` when the optional demo seed runs.
- `users` stores an explicit tenant and role. Passwords are PBKDF2-SHA256 records with random salts; the synthetic seed password is never stored as plaintext.
- `inventory` is keyed by `(tenant_id, sku)` and stores `on_hand`, `reserved`, server catalog price, and a positive version.
- `orders` has a tenant-local unique `client_ref`, stable creation sequence, status, version, total, and timestamp.
- `order_lines` snapshots the catalog unit price and tracks returned units. A line belongs to one tenant/order and is unique by SKU.
- `audit` is append-only and includes tenant, action, entity, actor email, and UTC timestamp.
- `sessions` stores random bearer tokens and their authenticated identity so a local restart does not invalidate a user unexpectedly.
- `idempotency` is keyed by `(tenant_id, key)` and stores method, path, canonical JSON payload hash, successful status, and response body.

Foreign-key relationships and SQL tenant predicates are used where the relation is relevant. UUID-like order IDs are globally difficult to guess, but the security boundary is still the tenant predicate rather than the ID format.

## Invariants

1. `on_hand >= 0`, `reserved >= 0`, and `available = on_hand - reserved >= 0` for every inventory row.
2. A reservation only changes `reserved` after every requested line has enough `available` stock. There is no partial reservation.
3. Shipping a reserved order subtracts the same quantity from `on_hand` and `reserved`, so available units are unchanged at the shipping instant.
4. Cancelling a reserved order releases exactly its order quantities. A draft cancellation has no stock effect; a shipped/returned order cannot be cancelled.
5. A return only applies to a shipped order, only names its own lines, and only adds units through the remaining shipped quantity. The order becomes `returned` when all line quantities have been returned.
6. Every successful order creation, order transition, and admin stock adjustment writes exactly one audit row. The audit insert is in the same transaction as the state change.
7. Order `version` starts at 1 and increments exactly once per successful lifecycle/return transition. Inventory `version` increments for each affected stock row, including reservation/release/shipping/return changes and adjustments.
8. A tenant-local `client_ref` is unique. Catalog prices are read from `inventory` while creating an order and are copied into its lines; request-supplied prices, tenant, and role fields are ignored.

SQLite `CHECK` constraints enforce the non-negative stored counters and positive versions/line quantities. Application validation rejects JSON booleans and fractions before arithmetic, because Python considers booleans a subclass of `int`.

## Transaction boundaries

Every state-changing route follows the same sequence:

1. Authenticate the bearer token and authorize its role before considering an idempotency replay.
2. Parse the JSON object and require a non-empty `Idempotency-Key`.
3. Open a request connection and issue `BEGIN IMMEDIATE`. This serializes SQLite writers while allowing ordinary reads through WAL.
4. Look up the tenant-scoped idempotency row. A matching method, path, and canonical payload hash commits the read transaction and replays the saved successful status/body. A mismatch returns 409.
5. Validate the current version/state and perform all affected inventory/order updates. A failed validation raises before commit and rolls back every update.
6. Insert the one audit event and the successful response into `idempotency`, then commit once.

The create-order transaction inserts the order, all lines, its audit event, and its replay body together. Reserve validates all lines before any reserved counter update. Ship, cancel, and return keep their stock mutations, order version/status change, and audit event in the same transaction. A concurrent identical request waits for the first writer, then receives its committed replay; a concurrent different request with the same key receives an idempotency conflict.

The read endpoints use a fresh connection and tenant-scoped queries. Order cursors contain the last immutable creation sequence plus the exact status/search filters; audit cursors contain the last immutable audit ID. Both streams are oldest-first and append-only for the supported workflow, so pre-existing matches do not duplicate or disappear across pages.

## Authentication and authorization

`POST /api/session` finds the user by email and verifies its password hash, then persists a random token. Subsequent requests accept only `Authorization: Bearer <token>` and derive tenant/email/role solely from the `sessions` row. Client headers and payload fields cannot override identity. The `/api/health` route is the only unauthenticated API read.

Admins and operators can create and transition orders. Only admins can adjust stock. Viewers can use all read routes but receive 403 for mutations, including a replay attempt. Every object lookup includes the authenticated tenant, so an ID belonging to another tenant returns 404 rather than confirming its existence. Bad/missing credentials return 401.

## Error handling

Expected application errors are JSON with a stable shape:

```json
{"error":{"code":"stale_version","message":"order version is stale"}}
```

Malformed payloads, unknown SKUs, invalid filters, and bad cursors are 400. Authentication is 401, viewer/role denial is 403, and cross-tenant/missing objects are 404. State conflicts, insufficient stock, stale versions, duplicate client references, excessive returns, and changed idempotency requests are 409. Failed mutations roll back and do not consume idempotency keys or write audit events.

## Reuse and frontend contract

`Handler.mutation` centralizes authentication ordering, idempotency lookup/replay, transaction setup, commit/rollback, and response persistence. `transition_order` centralizes reserve/ship/cancel state checks and stock logic; order serialization is shared by list/detail/mutation responses. The client uses one `api` helper for bearer/error handling and one mutation-key generator per submission.

The UI exposes the required `data-testid` markers, uses native select/input controls, labels all form fields, and sets arbitrary values through `textContent` or input values. It keeps return quantities in local state after a stale-version failure, displays the server error, and refreshes the current order so the operator can reconcile without silently discarding their input. Viewer rendering omits create, stock-adjustment, lifecycle, and return controls.

## Scope tradeoffs

This architecture favors reproducibility and inspectable local transactions over production-scale concerns. It does not provide token expiry, password reset, HTTPS, rate limiting, background jobs, distributed locks, multi-process migrations, or horizontal scaling. SQLite and the local bearer tokens are appropriate for the requested disposable local exercise; public deployment would require those operational and security layers.
