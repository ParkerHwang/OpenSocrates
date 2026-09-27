# Architecture and invariants

DepotFlow is one Python standard-library HTTP process with request threads, a SQLite file under `DATA_DIR`, and static JavaScript/CSS served from the same origin. Each request opens its own SQLite connection. The schema is initialized on startup. Demo seeding runs inside a write transaction only when the seeded store is empty. Static assets are allowlisted.

## Authoritative state

`inventory` is the authority for `on_hand`, `reserved`, catalog price, and inventory version. `available` is derived as `on_hand - reserved`, never stored. Database checks enforce `0 <= reserved <= on_hand`, nonnegative price, and positive version. An order has a tenant-local unique `client_ref`, status, version, snapshot total, and lines with snapshot unit prices and returned quantities. The server ignores client-supplied prices, tenant, status, and role. `dashboard` aggregates committed current rows; audit is an append-only record of successful mutations. No UI calculation is authoritative.

Quantity and version inputs must be JSON integers, not booleans or fractions. Signed SQLite integer limits are checked before writes; zero-price orders remain valid when they contain a positive-quantity line. Invalid payloads are 400. Stale versions, invalid transitions, insufficient stock, and key/ref conflicts are 409. Missing or invalid bearer tokens are 401; disallowed role mutations are 403; cross-tenant order IDs are 404. Every error has a structured code and a useful message.

## Transaction and retry boundary

Every mutation starts `BEGIN IMMEDIATE`. Within that one SQLite transaction the server looks up a tenant-scoped idempotency key, validates the current order/inventory and expected version, applies every stock/line/order update, inserts exactly one audit event, and stores the successful status/body for replay. It commits only after all these operations succeed. Any exception rolls back all effects, including the key. Repeated identical method, path, and canonical JSON payload returns the stored status/body, even after restart. The key is scoped across mutation endpoints within a tenant; a different payload or path returns 409. Authentication and route authorization happen before replay. SQLite's single-writer transaction serializes concurrent reservations and repeated requests, so the later writer observes the committed stock and key.

Transitions:

| From | Action | To | Stock effect |
| --- | --- | --- | --- |
| draft | reserve | reserved | add each line quantity to reserved if all lines fit |
| draft | cancel | cancelled | none |
| reserved | ship | shipped | subtract each line quantity from on_hand and reserved |
| reserved | cancel | cancelled | release each reserved quantity |
| shipped | return some | shipped | add returned units to on_hand and line returned_quantity |
| shipped | return all remaining | returned | same stock effect; no further returns allowed |

Each successful transition increments order version exactly once. Every touched inventory row increments its version once for that mutation. A failed multi-line reservation checks all availability before updating any line, and rollback also covers any later failure. Audit creation shares the transaction, so a rejected request or replay cannot add an event. Cancellation after shipment and over-return are conflicts.

## Isolation, authentication, and pagination

A session token is generated with `secrets.token_urlsafe`, returned only to the login caller, and stored as a SHA-256 digest. Password verification uses salted PBKDF2-HMAC-SHA256 and constant-time comparison. The user row associated with the bearer token supplies tenant and role; request headers/body cannot override them. All order, inventory, audit, dashboard, and idempotency queries use that tenant. Order reads and transitions include tenant in lookup so another tenant's ID looks absent. The browser keeps its token in session storage and clears it on logout.

Orders and audit page oldest-first by monotonically increasing IDs. A signed opaque cursor contains tenant, filter values, last ID, and the maximum ID visible when page one was requested. This prevents newly inserted rows from duplicating or entering the rest of that traversal; signature and filter/tenant checks reject mismatched or malformed cursors. A filter's result can change if existing orders change status during traversal. `q` uses case-insensitive substring matching on `client_ref`.

## UI and reuse

The UI's small DOM helper writes arbitrary order references and server strings as text nodes rather than HTML. A shared API function handles bearer authentication and structured errors. A shared action wrapper disables buttons during mutations, presents pending/success/error messages, and refreshes the appropriate view on success. On a 409 it leaves the create/return form values in place so the user can review them and reselect the order to refresh its version. Server role checks remain authoritative even though viewer controls are hidden. Native forms, labels, buttons, selects, tables, and responsive CSS support keyboard use and narrow screens.
