# DepotFlow architecture

## Boundary and runtime

DepotFlow is a single local Python process with a `ThreadingHTTPServer` bound
to `127.0.0.1`. The browser receives `static/index.html`, `static/app.js`, and
`static/styles.css` from the same origin as the JSON API. SQLite is the only
stateful dependency and lives at `DATA_DIR/depotflow.sqlite3`.

The database is initialized on startup. Demo seeding runs inside an immediate
transaction only when the tenants table is empty and `SEED_DEMO=1`, which
makes restarts idempotent. The schema uses foreign keys, integer fields, and
checks for non-negative on-hand/reserved quantities and valid order states.

## Data model

| Table | Purpose and scope |
| --- | --- |
| `tenants` | The `north` and `south` organizations. |
| `users` | Tenant, role, and PBKDF2 password verifier. |
| `sessions` | SHA-256 bearer-token hashes and their user. |
| `inventory` | Tenant/SKU catalog, on-hand, reserved, price, and version. |
| `orders` | Tenant-local client reference, status, order version, total, and stable `order_no`. |
| `order_lines` | Server-priced quantity snapshots and returned quantities. |
| `audit_events` | Tenant-scoped successful mutation events ordered by autoincrement ID. |
| `idempotency_keys` | Tenant-scoped method/path/payload fingerprint and replay response. |

Every query that can expose tenant-owned data includes the authenticated
tenant in its predicate. An order ID from another tenant therefore has the
same 404 response as an unknown order.

## Authentication and authorization

`POST /api/session` verifies the seeded email/password and stores only a
random-token hash. Subsequent requests authenticate from the `Authorization:
Bearer` header; tenant, email, and role are derived from the stored session,
never from a request header or body. `GET /api/me` exposes the derived user.

Viewers can use read routes only. Operators and admins can create and transition
orders; only admins can adjust stock. Authorization is checked before the
idempotency lookup, so a viewer cannot replay a mutation response by knowing a
key. Unauthenticated, missing, and invalid tokens return 401; a viewer or
insufficient role returns 403.

## Mutation transaction boundary

Each mutation opens a fresh connection and executes `BEGIN IMMEDIATE`. That
locks the SQLite write path before any inventory decision. The handler then
performs all validation and state changes on that connection. It inserts the
audit event and successful idempotency response before commit. Any 400/409
validation or business error rolls the transaction back, so it cannot consume
the key or leave a partial stock/order/audit update.

The `BEGIN IMMEDIATE` boundary is deliberately broader than an individual
SKU update. It makes a multi-line reservation all-or-none and prevents two
reservation requests from both observing the same available stock. The cost is
serialized writers, which is visible in the load-test limitation.

## Invariants and transitions

The central inventory invariant is:

```text
0 <= reserved <= on_hand
available = on_hand - reserved
```

Every inventory mutation increments its inventory version. An adjustment uses
`expected_version`, and a reduction cannot fall below reserved stock. A reserve
checks every line before changing any line, then increments reserved. Shipping
decrements both on-hand and reserved by the same quantity, preserving
available at that instant. Cancellation releases reserved units. Returns add
units to on-hand, increment per-line returned quantities, and change `shipped`
to `returned` only when every line is fully returned.

Orders begin at version 1 in `draft`. Each successful reserve, ship, cancel, or
return changes the state and increments the order version exactly once. A
stale expected version is a 409. Invalid transitions, insufficient stock,
return overages, and client-reference conflicts are also 409; malformed
payloads, quantities, unknown catalog SKUs, duplicate lines, and invalid
filters are 400.

Server catalog prices are read during order creation and copied into
`order_lines`; client-supplied price, tenant, role, or extra fields cannot
override those values. A non-empty SAMPLE line is still a valid order with a
zero total.

## Idempotency and retries

All mutation endpoints except session creation require `Idempotency-Key`. The
key is unique per tenant across mutation paths. Inside the same immediate
transaction, DepotFlow computes a SHA-256 fingerprint of canonical JSON,
compares the method/path/fingerprint with any existing record, and either:

1. replays the stored status/body with no handler effect or new audit event;
2. returns 409 for a changed request; or
3. runs the new handler and stores its successful response before commit.

Because the record is in SQLite, an exact retry after process restart also
replays. Concurrent identical requests serialize: the first stores the result,
and the second sees that result after the lock is released.

## Read consistency and reuse

Order list pagination uses an opaque cursor containing the last stable
`order_no` and a filter fingerprint. It filters by tenant, status, and
case-insensitive client-reference substring before ordering oldest-first. Audit
pagination uses the tenant-filtered autoincrement event ID. The dashboard,
inventory, order detail, and audit routes all read the same committed SQLite
state, so a refresh or restart does not require a separate cache invalidation
path.

Shared server helpers handle JSON parsing, integer validation, canonical
idempotency hashing, authentication, cursor validation, order serialization,
audit insertion, and error shaping. The UI uses one fetch wrapper for bearer
headers, JSON errors, idempotency keys, pending state, and replay-safe
mutations.

## Error handling and operational limits

Expected API errors are returned as `{error:{code,message}}`; unexpected
exceptions are reduced to a generic 500 response rather than exposing a
traceback. The service has no TLS termination, external identity provider,
rate limiter, token expiration/revocation UI, backup process, or migration
framework. It is intentionally self-contained for local use and testability.

The browser renders dynamic client references, actors, and identifiers through
DOM text nodes rather than HTML interpolation. It exposes pending, empty,
success, and error states; keeps a failed order form populated; and hides
mutation controls for viewers.

