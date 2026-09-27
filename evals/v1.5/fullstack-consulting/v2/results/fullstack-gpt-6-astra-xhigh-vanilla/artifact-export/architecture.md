# DepotFlow architecture

DepotFlow is a single local Python process serving JSON and static assets on `127.0.0.1`. It uses a persistent SQLite database and a JavaScript UI without a build step. Python's threaded HTTP/1.1 server is sufficient for this local application; it is not intended as an Internet-facing application server.

## Components and reuse

- `depotflow/server.py`: HTTP routing, strict JSON parsing, authentication boundary, security headers, and structured errors.
- `depotflow/service.py`: shared validation, tenant-scoped reads, stock/order operations, cursor signing, audit writing, and the idempotent mutation wrapper.
- `depotflow/db.py` and `schema.sql`: connections, database constraints, WAL initialization, and transactional empty-store seeding.
- `static/app.js`: one API client and mutation wrapper, DOM builders that insert text nodes, inventory/order/audit views, forms, and stale-input recovery. `styles.css` and `mobile.css` provide responsive layouts.
- `tests/support.py`: real server subprocess fixture reused by route tests, browser runner, and performance exercise. Test state lives under `.test-data`, separate from application state.

The application has no external runtime packages, services, or CDN assets. Playwright is an optional, pinned development dependency.

## Persistent model and invariants

| Table | Responsibility |
| --- | --- |
| `tenants`, `users` | Organization membership, role, salted password hash |
| `sessions` | Hash of an opaque bearer token, user, expiry |
| `inventory` | Per-tenant SKU, catalog price, on-hand/reserved counts, version |
| `orders`, `order_lines` | Tenant-local reference, immutable order ID and insertion sequence, status/version, price snapshots, cumulative returns |
| `audit` | Append-only event with actor, timestamp, entity, and structured change details |
| `order_status_history` | Status at each committed order event; freezes filtered pagination membership |
| `idempotency` | Tenant/key uniqueness, request fingerprint, successful HTTP status and serialized body |
| `meta` | Persistent cursor signing secret |

Foreign keys are enabled on every connection. Inventory and order lines have composite tenant keys. Lines reference both their tenant's order and its SKU. Domain queries include the authenticated tenant even though order IDs are globally random. SQLite checks enforce integer storage, nonnegative counts/prices, `reserved <= on_hand`, and `returned_quantity <= quantity`. Application checks also reject JSON booleans, fractions, zero/negative line quantities, repeated SKUs, and arithmetic outside the supported range. Money is calculated in integer cents, never binary floating point.

Order references are exact, case-sensitive, tenant-local unique strings. Search uses Unicode case folding and literal substring matching. Catalog prices are copied when an order is created; client-supplied price, tenant, role, ID, status, or total fields have no authority. A nonempty order with a zero total is valid.

## Transaction boundaries

Every domain mutation executes:

1. Authenticate and authorize using server-side membership. Parse and validate JSON and the idempotency header.
2. Acquire SQLite's writer lock using `BEGIN IMMEDIATE`.
3. Look up `(tenant, key)`. Replay a matching request's stored successful status/body; reject a different fingerprint.
4. Validate the object's tenant, version, transition, and every affected line. Perform domain writes.
5. Insert exactly one audit event; insert order status history for order events. Store the success response in `idempotency`.
6. Commit and then return the response.

All failures roll back the transaction, including tentative updates to earlier lines. Failed requests leave no retry record. A later request may reuse their key. SQLite serializes concurrent writers, so two reserve operations cannot both act on the same available stock. A busy writer waits for up to 30 seconds; a storage operational failure is surfaced as a structured 503, and the client can retry its original key. A response lost after commit is safe to replay, including after restarting the process.

Reservations increase reserved stock. Shipment decreases on-hand and reserved equally, preserving available stock at that instant. Reserved cancellation releases all held units; draft cancellation changes no inventory. Returns increase on-hand and cumulative returned quantity; the final complete return changes status to `returned`. Each successful order operation increments the order version once. Every SKU whose counts change increments its inventory version once. Order creation leaves stock unchanged.

Read routes use an explicit read transaction, so their multiple queries see one committed snapshot. Dashboard counts and inventory totals are computed, not cached. Separate concurrent API reads can naturally observe different commits; refresh brings each view current. WAL permits readers during writes; `synchronous=FULL` requests durable SQLite commits. Process crash recovery is tested. Power-loss and filesystem durability are not independently tested.

Seeding runs under a writer transaction only when no tenant exists and `SEED_DEMO=1`. It creates both tenants and their six users atomically, without audit events. Restart does not reset stock, users, events, tokens, retry records, or the cursor secret.

## Pagination

Orders use an immutable insertion sequence; audit uses an increasing event ID. Signed cursors contain the tenant, list kind, normalized filters, last position, initial upper bound, and initial audit position. Subsequent pages exclude newer records and move strictly after the last position. HMAC verification prevents clients changing boundaries or crossing tenants/list types/filters. Cursors survive restarts and allow a different valid page size.

Status-filter membership is evaluated against `order_status_history` at the first page's audit position. This prevents a not-yet-seen matching order from being omitted if it transitions while the user pages. Returned order bodies show current committed status, prices, quantities, and version. Thus a historical filtered page can contain an order whose current status differs from the filter; restarting the list applies current filters again. Client references are immutable, so search membership is stable. There are no delete routes.

## Authentication and browser state

Passwords use PBKDF2-HMAC-SHA256 with independent random 16-byte salts and 240,000 iterations. Login returns a random 256-bit bearer token. Only its SHA-256 hash is stored. Sessions expire after 12 hours and survive server restart; expired session rows are cleaned on login. Authorization resolves the user's current server-side role and tenant on each request. No tenant or role headers/body fields are trusted. Roles are admin (all domain operations), operator (orders), and viewer (reads). Authorization precedes idempotency replay.

The browser stores the token in tab-scoped `sessionStorage`. Logout removes local session/input/retry state. It does not revoke an already copied token; that token remains valid until expiry. Server-side token revocation, password changes, account provisioning, and login throttling are outside this local demo's scope. No authentication cookies or cross-origin API access are used. The server sends a restrictive Content Security Policy and does not log bearer tokens or request bodies.

Mutation buttons and inputs are disabled during an in-flight action, with a synchronous guard against double clicks. A pending request's key is retained per tenant/path/payload in tab storage until success, so a lost response can be retried safely. Validation and version errors retain form inputs. An explicit refresh reloads versions while preserving adjustment and return values for review. Navigating away from a form discards its unsaved values; there is no offline queue or durable draft editor.

## Errors and operational boundaries

API errors use `{error:{code,message}}`. 400 covers malformed JSON, invalid quantities/filters/cursors, missing keys, and unknown catalog SKUs. 401 covers missing/invalid sessions or bad credentials. 403 covers insufficient roles. An order outside the tenant is indistinguishable from a missing order (404). State, stock, stale-version, unique-reference, excess-return, and retry conflicts are 409. Unexpected faults return a generic 500 while recording a server-side stack trace; operational SQLite errors return 503. Errors also close the HTTP connection so unread invalid request bodies cannot contaminate subsequent requests.

Requests are capped at 128 KiB, orders/return requests at 100 unique lines, references/search at 200 characters, adjustment reasons at 1,000 characters, and keys at 200 characters. Quantities and individual money/count values are bounded by JavaScript's exact integer range. Limits are intentionally conservative for a small local warehouse.

This is a single-writer embedded design, with no background workers, replicated database, deployment configuration, TLS, inventory catalog editor, or schema upgrade framework. Audit/retry/status-history tables are retained indefinitely to preserve history and replay behavior. A long-lived installation would need a storage retention policy and versioned schema migrations. Substring search scans tenant references; broad lists currently fetch order lines per order. The measured concurrency and data sizes are small, and SQLite write-lock contention produces tail latency. `DATA_DIR` requires a writable local filesystem; do not run it on a network filesystem. To copy the store, stop the server first and copy the entire directory, including any WAL files.
