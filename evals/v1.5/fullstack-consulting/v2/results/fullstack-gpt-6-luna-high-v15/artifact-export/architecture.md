# DepotFlow architecture

## Components and authority

DepotFlow is a Python 3 standard-library HTTP server and a browser client built
from plain HTML, CSS, and JavaScript. The server binds only to `127.0.0.1` and
serves the UI and `/api` from the same origin. SQLite is the authoritative
store; no state is held only in process memory. Every tenant-owned query uses
the authenticated user's tenant from the session join. Request fields and
headers never select a tenant or role.

The schema separates tenant users, sessions, inventory, orders, order lines,
audit events, and idempotency responses. Orders retain catalog price snapshots.
Inventory `on_hand`, `reserved`, and version are stored values; available stock
is derived as `on_hand - reserved`. Dashboard totals are query-time projections
from the same committed state.

## Invariants

- Each inventory row is keyed by `(tenant, SKU)` and enforces nonnegative stock,
  nonnegative reservations, and `reserved <= on_hand` in SQLite.
- An order's client reference is unique inside its tenant. Order lines have one
  row per SKU, and their unit prices are copied from that tenant's catalog.
- Only a `draft` can be reserved, only a `reserved` order can ship, and only
  `draft` or `reserved` can be cancelled. Only a shipped order can receive
  returns. A fully returned order cannot receive another return.
- Order versions begin at one and increment exactly once for each successful
  transition. Inventory versions increase when a stock row is changed.
- A reservation verifies all lines before applying any line. Every stock change,
  order change, audit event, and successful idempotency record for a mutation
  commits together or rolls back together.
- Tenant identifiers and roles come only from the validated bearer token's
  stored session. Object lookup combines object ID and authenticated tenant.

## Transaction and retry boundary

The handler opens a SQLite connection per request. A mutation starts
`BEGIN IMMEDIATE`, checks the tenant-scoped idempotency key, checks the relevant
version/state/stock, applies changes, appends its audit record, stores the
successful HTTP status and response, and commits. SQLite's serialized writer
lock protects competing reservations across HTTP worker threads and across
server processes sharing this local file. Any exception before commit rolls
back the whole transaction. WAL mode is enabled to allow concurrent readers.

Idempotency fingerprints include method, path, and canonicalized JSON payload.
Same-key/same-fingerprint requests replay the saved status and body; a changed
fingerprint conflicts. Authentication and role checks occur before replay.
Failed requests are rolled back and do not occupy the key. Session creation is
the only mutation without a key. Idempotency, audit, and application data share
the same SQLite durability boundary, so process restart retains all three.

## Authentication, authorization, and errors

`POST /api/session` checks a seeded user's password hash and creates a random
opaque bearer token persisted in `sessions`. `GET /api/me` exposes the stored
identity. Every other API route except health validates that token. Viewers can
read but receive 403 for POST mutations; stock adjustment is admin-only. Unknown
or cross-tenant order IDs return the same 404 response.

API failures use `{ "error": { "code": "...", "message": "..." } }`.
Validation failures are 400, missing/bad authentication is 401, permission
failures are 403, tenant-invisible/missing objects are 404, and stale state,
stock conflicts, invalid transitions, duplicate references, or idempotency
conflicts are 409. Unexpected implementation errors return a generic 500;
details are emitted only when `DEBUG=1`.

## Reuse and limits

`mutate()` centralizes idempotency, transaction, and commit/rollback behavior;
`parse_lines()`, `serialize_order()`, and `audit()` keep shared data rules in a
single place. The frontend uses one same-origin fetch wrapper and refreshes the
inventory/dashboard after writes. It uses DOM text nodes for server-returned
text and does not inject client-entered values as HTML.

This is a single-host warehouse demo, not a hardened internet-facing service:
demo credentials are intentionally shared and session tokens have no expiry or
revocation UI. SQLite writer serialization prioritizes correctness over high
write concurrency. The local runner does not implement TLS, CSRF protection for
deployment behind a public origin, backup rotation, or multi-host coordination.
