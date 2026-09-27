# DepotFlow architecture

## Components and persisted model

`app.py` owns the HTTP API, authentication, domain validation, and SQL operations. `index.html` is served from the same process and calls only same-origin JSON endpoints. `run.sh` uses the available Python interpreter and creates the configured state directory. SQLite stores:

- `users` and hashed bearer-token references (`tokens`)
- per-tenant SKU balances and versions (`inventory`)
- orders and price-snapshotted lines (`orders`, `order_lines`)
- append-only tenant audit events (`audit`)
- successful response snapshots keyed by tenant and idempotency key (`idempotency`)

Foreign keys, unique keys, and CHECK constraints provide persistence-level support for identity uniqueness and nonnegative/reserved inventory. IDs are monotonically increasing SQLite row IDs. The order list uses ascending ID order and an ID cursor, so additions after a page do not shift earlier pages.

## Invariants

1. A bearer token is opaque and randomly generated. Only its SHA-256 digest is stored. The server resolves its email, role, and tenant from its own tables; headers and body fields never set identity or role.
2. Every tenant-owned lookup and mutation includes the authenticated tenant in the SQL predicate. An order that exists only in another tenant therefore returns 404.
3. `0 <= reserved <= on_hand`. Available stock is derived as `on_hand - reserved`; reservations compare all requested lines before changing any inventory row.
4. Catalog price and tenant are taken server-side. Order lines retain the catalog price from creation. A client reference is unique within one tenant.
5. Every successful create, stock adjustment, or order transition has exactly one audit row. A failed transaction or successful idempotency replay adds no event.
6. A successful transition increments the order version once. Inventory versions increment once for each SKU row changed by a transition/adjustment.

## Transaction boundaries and retry behavior

Each authenticated mutation first starts `BEGIN IMMEDIATE`, which obtains SQLite's write reservation before checking idempotency or reading mutable domain state. This serializes competing local writers and avoids a check-then-update race during reservation.

Inside the same transaction the server:

1. Checks the tenant-wide idempotency key and canonical request fingerprint.
2. Validates current order/inventory state and expected versions.
3. Applies all inventory/order/return changes.
4. Adds the audit row and stores the successful HTTP status/body snapshot.
5. Commits once.

Any API or database error rolls back before the error is sent. Thus failed requests do not consume keys or retain partial multi-line updates. Identical simultaneous requests serialize: one makes the change and stores the response; later requests replay it. A different method/path/body under that tenant/key receives 409. Authentication, viewer rejection, and the admin-only adjustment check happen before replay.

The HTTP server uses one SQLite connection per request with a 30-second busy timeout. `BEGIN IMMEDIATE` intentionally favors correctness and a compact local setup over write parallelism. Read handlers use independent connections and no explicit write transaction.

## Authorization and errors

`POST /api/session` checks the stored password digest and creates a random token. Every other private API route resolves the bearer token on the server. Missing/unknown tokens return 401. A viewer mutation returns 403. Stock adjustments require admin; operators and admins may create and progress orders. Tenant scoping occurs on object lookup, returning 404 rather than revealing cross-tenant existence.

Request shape and quantity validation returns a 400 with a stable machine-readable error code and UI-usable message. Stale versions, invalid transitions, insufficient inventory, duplicate references, return overages, and idempotency conflicts return 409. Unexpected exceptions return a generic 500 without exposing SQL or tracebacks.

## Frontend reuse and interaction

The UI has one API wrapper for bearer handling and JSON error extraction; each screen function owns its loading, empty, and error presentation. After writes it reloads the order list, current order, inventory/dashboard, and audit when selected. A single `busy` guard and disabled submit/action button prevent duplicate clicks. A stale-version response is shown and the latest detail is refreshed; unsent form fields remain in place. The viewer role branches out all order-entry and action controls. Server/client text is inserted as escaped text or `textContent`, never interpreted as arbitrary HTML.

## Tradeoffs and boundaries

This is a single-process local application. SQLite durability is suitable for the requested two-operator deployment and restart behavior; its single-writer model caps write concurrency as data or request contention grows. Password hashing uses SHA-256 for the fixed synthetic demo password; real accounts should use a slow password KDF and proper credential lifecycle. Tokens do not expire or have a revocation UI. The service binds to loopback and does not provide TLS, remote hosting configuration, or production account management. Seed data is inserted only when users, inventory, and orders are all empty; setting `SEED_DEMO=1` after the app has acquired data does not overwrite that data.
