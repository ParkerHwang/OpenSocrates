# DepotFlow architecture

## Runtime boundary

`run.sh` starts one Python process and binds `ThreadingHTTPServer` to `127.0.0.1`. Static UI files and `/api` share that origin. `PORT` and `DATA_DIR` configure the listener and SQLite file. SQLite uses WAL mode, foreign keys, a 30-second busy timeout, and a local embedded file; there is no service dependency.

Each HTTP request opens its own SQLite connection. Reads that assemble multiple query results use one read transaction so returned projections share a committed snapshot. The server can handle concurrent requests, while SQLite's write lock is the serialization point for state changes.

## Authoritative state and invariants

- `tenants` and `users` own tenant membership and roles. Each user belongs to one tenant; the server derives the request tenant from the authenticated user row.
- `inventory` is authoritative for current stock. For each tenant/SKU, `on_hand >= 0`, `reserved >= 0`, and `reserved <= on_hand`. `available` is always computed as `on_hand - reserved`.
- `orders.status`, `orders.version`, `orders.total_cents`, and `order_lines` own the order lifecycle and its historical price/quantity snapshot. A tenant-local unique constraint protects `client_ref`; line primary keys reject duplicate SKUs.
- `audit_events` is the committed history of successful stock adjustments, order creation, and transitions. One request changing several SKU rows still creates one event.
- `idempotency` owns the successful response associated with a tenant key. It stores method, URL path, canonical JSON request, HTTP status, response JSON, and creation time.
- Dashboard counts and unit totals are projections of the same tenant-scoped order and inventory state, not independent mutable counters.

Inventory versions increment once per SKU update caused by a reservation, shipment, cancellation release, return, or stock adjustment. An order starts at version 1; reserve, ship, cancel, and each accepted return request increment it exactly once. Rejected requests leave these versions unchanged.

## Mutation transaction boundary

The handler authenticates and applies the endpoint's role rule before looking up an idempotency replay. It validates the key, then `run_mutation` begins `BEGIN IMMEDIATE` and performs the following in one transaction:

1. Look up `(tenant_id, idempotency_key)`.
2. If found, compare method, path, and canonical JSON. Return the stored status/body for an exact match; return 409 for a mismatch.
3. Otherwise validate current state and expected version, update order/inventory rows, append one audit event, and store the success response under the key.
4. Commit once. Any exception rolls back all writes, including the audit and key record.

SQLite serializes concurrent writers before the read/check/write sequence, so two reservations cannot both observe the same unreserved units. A multi-line reservation checks all requested SKUs before applying stock changes; the enclosing transaction also protects against later errors. Idempotency rows are in the same database transaction as the effect, so a committed effect cannot lack its replay response. Concurrent duplicate requests serialize at the same write boundary.

Create orders, stock adjustments, transitions, audit, and idempotency all use this common boundary. Reads do not take the write lock. The implementation relies on SQLite's local transactional durability and does not attempt external side effects.

## Lifecycle rules

| Operation | Required source state | Order result | Inventory result |
| --- | --- | --- | --- |
| Create | — | `draft`, version 1 | unchanged |
| Reserve | `draft` | `reserved` | add line quantities to `reserved` after checking every SKU |
| Ship | `reserved` | `shipped` | subtract shipped quantities from both `on_hand` and `reserved` |
| Cancel | `draft` or `reserved` | `cancelled` | release reserved quantities when reserved |
| Return | `shipped`, valid unreturned line quantities | `shipped` until all lines returned, then `returned` | add accepted return quantities to `on_hand` |

All transitions compare `expected_version` under the write transaction. Missing/invalid fields and quantities return 400. Stale versions, illegal transitions, insufficient inventory, return overages, and idempotency mismatches return 409. Tenant-scoped reads hide foreign object IDs as 404. Role denial returns 403; missing or invalid bearer tokens return 401.

## Authentication and authorization

Demo user passwords are stored as salted PBKDF2-HMAC-SHA256 hashes. Session tokens are random URL-safe values; the database stores only their SHA-256 hashes. `/api/me` returns the user associated with that token. No request header, query parameter, or body field can change the tenant or role.

Role rules are enforced on the server, before replay: viewers may read only; operators and admins may create and transition orders; only admins may adjust stock. The UI also hides write controls for viewers, but API authorization remains authoritative. The local logout clears the browser's stored token; the API has no token-revocation endpoint, expiry, or account management.

## UI and error behavior

The UI uses browser `fetch` with same-origin routes. It creates an idempotency key for each logical request and retains that key after a network/HTTP failure so a retry of the same body can replay safely. A changed form body gets a different key. The server decides whether the operation succeeded.

Server-provided text is assigned with DOM `textContent`; no client text is inserted as HTML. The UI has explicit loading, empty, success, and error states. A failed form mutation does not re-render the page, preserving the user's current inputs. A 409 stale-version response is shown with a refresh instruction while those inputs remain in place. Successful mutations reload inventory/dashboard, order list/detail, and audit data.

## Persistence and seed behavior

Schema creation is idempotent. With `SEED_DEMO=1`, the two tenants, six users, and three catalog rows per tenant are inserted together only when the database has no tenant rows. Existing stores are never re-seeded. SQLite commits survive normal process restart; the tests exercise session, stock, audit, and replay persistence across an actual server restart. Power-loss behavior and backup/restore procedures are not separately tested.

## Limits

The app is designed for a small local operator workload. SQLite permits concurrent readers but serializes writes; the benchmark measures one local process and a small temporary database, not a remote or multi-region deployment. There is no token expiry/revocation, login rate limit, encrypted network transport, schema migration framework, retention policy, or backup tooling. Order/audit/idempotency history has no automatic expiry.
