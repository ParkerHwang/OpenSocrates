# DepotFlow architecture

## Choice and boundaries

**Selected:** Python's standard-library HTTP server, SQLite, and browser-native JavaScript for a locally bound single-service application. The task explicitly permits an embedded database and leaves language/framework choices to the implementer. Python and SQLite availability were observed in the supplied environment. No external service, account, container, or paid resource is required.

Hard constraints come from `TASK.md`: tenant/role isolation, atomic stock transitions, durable retries/audit, restart persistence, same-origin UI/API, and the defined integration surface. They are not traded against convenience. Their implementation is supported by the route/database and browser checks recorded under `evidence/`.

The following is an **ordinal design comparison**, not a measured framework benchmark. Preference for a small reproducible local setup is an implementation judgment under the user's authorization; correctness and completeness are veto conditions. No numerical weights or unsupported speed rankings are used.

| Criterion / provenance | Python stdlib + SQLite + native UI | Python web framework + SQLite + native UI | Node web framework + SQLite + component UI |
| --- | --- | --- | --- |
| No external database/service; user requirement | Fits | Fits | Fits |
| Reproducible local startup; user requirement | No runtime package installation; verified locally | Requires pinned Python dependencies; not implemented/measured | Requires pinned JS/SQLite dependencies and usually a frontend build; not implemented/measured |
| Small implementation/dependency surface; implementer preference | Selected; explicit routing and DOM code | More routing conventions, additional dependency maintenance | More component tooling, additional setup/build maintenance |
| Rich routing/component ecosystem; inferred maintenance tradeoff | Concession: handcrafted validation and view composition | Framework support available; alternative untested here | Framework/component support available; alternative untested here |
| Sustained concurrent writes; workload-dependent | SQLite writer serialization; measured only for selected stack | Same SQLite constraint | Same SQLite constraint |
| Production internet service; outside user scope | Would require reconsidering HTTP/auth/operations layer | More natural migration route; still requires operational work | Also viable with operational work |

The alternatives remain viable and are not claimed to be dominated. The chosen design favors minimal startup dependencies over framework conventions. Accepted risks are serialized writes, handwritten request handling, and an in-memory browser view layer. The recommendation changes if the app must face untrusted network traffic, support many simultaneous writers beyond measured capacity, or grow a substantially larger UI/team. Those observations would justify a maintained application server/framework and possibly a service database. No missing user preference blocks this authorized local implementation. Capacity outside the measured workload remains unknown.

## Components and reuse

```text
Browser (static/index.html + app.js + styles.css)
              | same-origin HTTP + Bearer token
app.py        | parsing, security headers, auth, transaction envelope, routes
service.py    | validators, stock deltas, versions, state machine, audit, cursors
database.py   | connections, password hashing, initial schema and atomic seeding
              | per-request SQLite connection
SQLite WAL    | users/sessions, inventory, orders/lines, audit/status history,
              | idempotency responses, schema metadata/cursor secret
```

Every mutation reuses `mutate()` for permission enforcement and idempotency, `check_version()` for optimistic concurrency, `stock_change()` for stock invariants, and `audit()` for append-only event creation. `lines()` enforces consistent create/return rules. The frontend shares DOM construction, request/error handling, mutation locks, pagination, and notification behavior. Integration tests and the load generator share the real subprocess/HTTP fixture in `tests/support.py`.

## Persistent model and invariants

- Users belong to one tenant and hold one of `admin`, `operator`, or `viewer`. Email is the login identity.
- Every inventory row is keyed by `(tenant, sku)`. Composite foreign keys tie lines to inventory and orders within the same tenant.
- `0 <= reserved <= on_hand <= 1_000_000_000`; `available = on_hand - reserved` is computed. Quantities and cents use integers, not floating point. JSON booleans and integral-looking floats are rejected for integer fields.
- An order has an immutable UUID, creation sequence, client reference, price snapshots, original total, and ordered line positions. `(tenant, client_ref)` is unique. A zero total is valid when lines are nonempty.
- Order quantities are positive; returned quantities stay between zero and the original line quantity. Price and total changes are never accepted from client fields.
- For each tenant/SKU, `inventory.reserved` equals units on reserved orders, enforced by the shared transition operations. The database separately prevents negative/excess reservations.
- Inventory version starts at 1 and advances once per touched SKU in a successful stock-changing operation. A draft cancellation does not touch inventory. Order version starts at 1 and advances exactly once per successful transition, including a partial return.
- Audit events are append-only through application routes. One event is generated per successful business operation. No delete/update audit route exists.
- A durable `(tenant,key)` idempotency record stores the canonical request fingerprint and successful status/body. It does not expire. A successful replay returns the saved version/body even if the entity has changed since that operation.
- `order_states` stores the status at each order event; this is for stable filtered pagination, not an alternative source of current stock.
- Database constraints backstop ranges, integer storage, unique references/keys, valid states, and tenant relationships. Application transactions enforce cross-row invariants.

## Transaction boundaries

Reads use one explicit deferred transaction per API response. Thus dashboard counts and inventory sums in a dashboard response share a committed database snapshot. Each request has its own connection with foreign keys enabled, a 15-second lock timeout, and full SQLite synchronous mode.

Business POST processing is:

1. Authenticate and enforce the role before replay or business writes; parse/validate the JSON envelope.
2. Acquire `BEGIN IMMEDIATE`, serializing writers before reading an idempotency record, current stock, or expected version.
3. Authenticate again inside the transaction; compare the tenant-scoped request fingerprint. An identical saved operation returns its stored response with no extra event. A mismatch is 409.
4. Validate the business payload, ownership, current state, and version; update all affected lines/stock/order rows.
5. Insert exactly one audit event, its order-state history entry if applicable, and the saved successful retry response.
6. Commit before sending success. Any exception rolls back all writes, including stock versions, event rows, and the retry record.

This structure makes simultaneous identical requests wait and replay the first commit. Competing reservations serialize and recalculate availability. A multi-line failure can occur after a prior line was changed in the transaction, but rollback restores every line; the integration tests inspect that persisted state. An injected audit-insert failure also verifies the transaction envelope.

| Operation | Allowed starting state | Stock effect | Resulting state |
| --- | --- | --- | --- |
| Create | New unique reference | None | draft, version 1 |
| Reserve | draft | Add quantity to reserved for all lines | reserved |
| Ship | reserved | Subtract quantity from both on-hand and reserved | shipped |
| Cancel | draft or reserved | Release reserved units if present | cancelled |
| Return | shipped | Add returned units to on-hand; accumulate returned quantity | shipped until all units returned, then returned |
| Adjustment | Admin, current stock version | Add signed delta to on-hand, retaining reserved floor | Updated stock version |

Partial returns do not alter the original order total. Cancellation after shipment and returns after complete return fail with 409. SKU existence, unique positive lines, reason, and integer validation errors are 400. Unknown/foreign orders are 404. The same stock/update helpers serve every transition.

Session insertion is a separate single-row autocommit after password verification; it requires no idempotency key and creates no business audit event. Seeding is its own immediate transaction, guarded by the presence of any tenant. Restart creates missing schema objects but does not reset catalog, stock, sessions, history, or retry records. The schema version is recorded as 1; no upgrade migration is claimed.

## Authentication, tenancy, and browser safety

Passwords use PBKDF2-HMAC-SHA256 with an independent 16-byte random salt and 240,000 iterations. Unknown accounts perform comparable hash work. Tokens contain 32 random bytes; only a SHA-256 digest and expiry are stored. Every authenticated request joins the session to the current user row. Tokens expire after 24 hours. Browser storage is tab-scoped `sessionStorage`; logout removes the token locally. Server-side token revocation is outside the supplied surface.

Tenant and role come only from this database lookup. Query/header/body tenant overrides are ignored. Each lookup, mutation, audit query, and cursor is tenant scoped. Admin and operator can fulfill; only admin adjusts stock; viewer cannot run any business mutation, even a replay. Cross-tenant object lookups return 404 without revealing existence.

Authorization headers are required rather than cookies; there is no cookie-based ambient authority. JSON-only writes and no permissive CORS are used. CSP restricts scripts/styles/connects to the local origin, blocks framing, and forbids inline script. The frontend constructs nodes with `textContent` rather than interpolating client text as HTML. Stock reasons and references use the same safe rendering in audit and order views. Static paths are an explicit allowlist.

This local service does not claim production resistance to denial of service, brute-force attacks, malicious same-OS users, or arbitrary local database editing. It has request size/time limits, but no global thread/rate limit or credential administration UI. Local demo credentials are intentionally public. SQLite files are created with restrictive process permissions.

## Pagination and consistency

Order sequence and event IDs are monotonic, stable sort keys. A first page captures the tenant's maximum order/event sequence inside a read transaction. A signed cursor contains kind, tenant, normalized filters, high-water bounds, and last emitted sequence. Subsequent pages use `>` for the last key and `<=` for the high-water boundary. An extra row detects whether another page exists. Cursor signatures use an HMAC-SHA256 secret persisted in database metadata, so cursors survive restart.

For a status-filtered order list, membership is evaluated using the latest `order_states` row at or before the first page's event boundary. This prevents later status changes from dropping pre-existing matches. Reference search is an immutable, literal Unicode-casefolded substring (`instr`, not SQL wildcard matching). Details returned for members are current. There are no deletion routes. Reusing a cursor with a different tenant, list kind, or filter is 400; limits may change between pages.

Audit pagination uses the same bound/key approach. Newly committed events and orders appear on refresh, not mid-traversal. Separate browser requests may see different committed snapshots if another user mutates between them; the UI refreshes views after its own successful operations and offers explicit refresh controls for external changes. No distributed snapshot across separate HTTP responses is claimed.

## UI state and error handling

The UI provides pending messages, empty lists, success notices, and server error messages. Mutations disable their form/action group and main navigation. A request fingerprint retains its idempotency key after an uncertain network response. The browser test deliberately commits a create and drops its reply, then verifies a single resulting order on retry.

Version conflicts leave input nodes and values intact. Refreshing an order retains entered return quantities and loads the current version. Refreshing stock versions retains SKU/delta/reason; users review before submitting again. New-order validation failures retain all lines and reference. Navigation uses an epoch so a late read does not replace a newer view. Draft form state and retry keys are not saved across page reload.

Backend errors have stable codes and useful messages. Unknown exceptions roll back and produce a generic 500; details go only to local stderr. SQLite lock exhaustion becomes a retryable 503. Error responses close the HTTP connection so an unread invalid body cannot become another request. Duplicate JSON keys, nonfinite numbers, unpaired Unicode surrogates, and malformed root bodies are rejected.

## Evidence and remaining uncertainty

[evidence/verification.md](evidence/verification.md) maps actual integration/browser/load results to the requirements. Evidence supports this implementation on the observed host and supplied synthetic workflows; it does not establish production availability or scaling limits. Reopen the design if broader browsers, multi-worker deployment, internet exposure, significantly larger catalogs, or sustained mixed contention become requirements.

The installed OpenSocrates controller's decision selector returned the complete `trade-off-analysis` revision 3 procedure, which was read for the architecture comparison. Native method activation/public-artifact confirmation was not supplied; activation remains unconfirmed. This instrumentation limit does not change the recorded executable test results. No private reasoning trace is retained.
