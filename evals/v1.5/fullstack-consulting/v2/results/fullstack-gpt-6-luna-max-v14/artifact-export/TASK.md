# Build DepotFlow

Build a complete, locally runnable multi-tenant fulfillment application for two
small warehouse operators. Deliver the backend, persistent data model, usable
frontend, tests, and a reproducible performance exercise. Choose the programming
language, framework and architecture yourself. Build actual working artifacts.
There is no imposed duration, token, tool-call or answer-length limit.

An operator receives orders, reserves stock atomically, ships them, handles
returns, and investigates inventory history. Two tenant organizations must never
see or mutate each other's data. A viewer may inspect but not mutate anything.
The UI must support this real workflow, not just show static demonstrations.

## Startup and integration surface

Provide executable `run.sh` at the project root. `PORT` supplies the HTTP port;
`DATA_DIR` supplies persistent state; `SEED_DEMO=1` seeds only an empty store.
Bind to 127.0.0.1. Serve the UI at `/` and JSON APIs under `/api` from the same
origin. Restarting with the same DATA_DIR must preserve changes and must not
reseed stock. Include reproducible dependency/build setup in `run.sh` or document
and provide `setup.sh`. No containers, accounts or external database service may
be required; any local embedded database or local process implementation works.

Provide `README.md` with setup, chosen stack, design, tradeoffs, test and load
commands, demo users, and actual results/limits. Provide `architecture.md`
describing invariants, transaction boundaries, reuse, authentication and error
handling. Keep evidence from your own verification, including a usable browser
workflow and performance measurements if available. Do not claim unrun checks.

Seed tenants `north` and `south`, each with users `admin@<tenant>.example`,
`operator@<tenant>.example`, `viewer@<tenant>.example`, all using the local synthetic
password `DepotDemo!2026`. Each tenant starts independently with:

| SKU | Name | On hand | Price in cents |
| --- | --- | ---: | ---: |
| BOLT | Steel bolt kit | 100 | 1250 |
| CABLE | Cable assembly | 60 | 2499 |
| SAMPLE | Sample pack | 20 | 0 |

`POST /api/session` takes `{email,password}` and returns `{token,user:{email,role,tenant}}`.
Use `Authorization: Bearer <token>` thereafter. `GET /api/me` returns that user.
No trusted tenant/role override from client headers or request body. Bad credentials
are 401; no/invalid token is 401; a viewer mutation is 403; another tenant's object
is 404. A health route `GET /api/health` returns `{status:"ok"}` without login.

## Stock and orders

`GET /api/inventory` returns `{items:[{sku,name,on_hand,reserved,available,price_cents,version}]}`.
Available is on_hand minus reserved. Values never go negative. All quantities,
versions and cents are JSON integers (booleans and fractions are not integers).
`POST /api/stock/adjustments`, admin only, takes
`{sku,delta,expected_version,reason}`. Nonzero signed delta, nonempty reason;
reject reductions below reserved with 409. Return the updated inventory item.

`POST /api/orders` takes `{client_ref,lines:[{sku,quantity}]}` and returns an order.
Each line quantity is positive, SKU exists, duplicate SKU lines are invalid, lines
are nonempty. Unknown SKU is 400. A nonempty zero-price SAMPLE order is valid.
Use server catalog prices; snapshot unit prices into the order. Order shape:
`{id,client_ref,status,version,total_cents,lines:[{sku,quantity,unit_price_cents,returned_quantity}]}`.
New orders are `draft` with version 1. Client references are tenant-local unique:
reusing a reference for a different create operation is 409. Extra client fields
must not override server prices, tenant or role.

`GET /api/orders/<id>` returns that order.
`GET /api/orders?status=<optional>&q=<optional>&limit=<1..100>&cursor=<optional>`
returns `{items:[orders],next_cursor:null|string}`. `q` is case-insensitive substring
of client_ref. Order results are stable oldest-first; cursor pagination must not
duplicate or omit pre-existing matches. Default limit is 20. Invalid filters or
cursors are 400; no matches return an empty list.

The following POSTs take `{expected_version}` except returns:

- `/api/orders/<id>/reserve`: draft → reserved. Reserve all requested lines in one
  transaction or none; insufficient available stock is 409. Never oversell when
  requests race.
- `/api/orders/<id>/ship`: reserved → shipped. Decrease on_hand and reserved by
  shipped quantities, keeping available unchanged at that moment.
- `/api/orders/<id>/cancel`: draft/reserved → cancelled. Release reserved stock
  if present; cancel after shipping is 409.
- `/api/orders/<id>/returns`: takes `{expected_version,lines:[{sku,quantity}]}`.
  Accept only shipped orders; positive integer quantities; SKUs must belong to
  that order and cannot repeat. Total returns per line cannot exceed shipped
  quantity. Add returned units to on_hand. Partial returns leave status `shipped`;
  a completely returned order becomes `returned`. Further returns are 409.

Each successful transition increments order version exactly once; stale version
is 409. State transitions, all stock updates and audit entries commit together.
Rejected requests must not partially change stock, order, version or audit.
Bad payload/quantity is 400. Invalid transition, insufficient stock, stale version
or idempotency conflict is 409. Errors have `{error:{code,message}}`, useful to a UI.

## Retry and audit integrity

Require nonempty `Idempotency-Key` on every mutation except session creation.
Scope keys per tenant across mutation endpoints. Same method, path and JSON payload
with the same key replay the original successful status/body without a second
effect or audit entry, including after process restart. A key reused with changed
payload/path is 409. Failed requests do not consume the key. Concurrent identical
requests must not create duplicate orders/stock changes/events. Authentication and
authorization still apply before replay.

`GET /api/audit?limit=<1..100>&cursor=<optional>` returns
`{items:[{id,action,entity_id,actor,created_at}],next_cursor:null|string}` oldest-first.
Every successful stock adjustment, order creation and order transition generates
one event. Idempotency replay and rejected requests generate none. Tenant scoped.
`GET /api/dashboard` returns `{orders_by_status:{...},inventory_units,reserved_units}`,
computed from current committed tenant state. Empty status counts may be zero or
omitted. Data must agree across UI/API/audit after mutations and restart.

## Frontend experience

Provide login/logout, an inventory/dashboard view, order list with filter/search
and detail, a form for multiple order lines, reserve/ship/cancel/return actions,
and an audit view. Show pending, empty, success and useful error states. Refresh
the appropriate data after mutations. Viewer UI must not offer writable controls.
Avoid double submissions; reflect stale-version errors without silently losing
user input. Use semantic labels and keyboard-operable controls. Make it usable at
desktop and narrow/mobile widths. Do not render arbitrary client text as HTML.

For stack-neutral browser automation, include these data-testid markers on the
corresponding controls: `login-email`, `login-password`, `login-submit`, `logout`,
`nav-inventory`, `inventory-table`, `nav-orders`, `new-order`, `order-client-ref`,
`line-sku` (native select), `line-quantity` (input), `add-line`, `submit-order`,
`order-detail`, `reserve-order`, `ship-order`, `cancel-order`, `return-quantity`
(one input per line), `submit-return`, `nav-audit`, `audit-table`.
Repeated line controls are matched in display order. Order details must show
client_ref and status as text. Other UI design choices are yours.

## Verification expected

Exercise normal use, role and tenant isolation, validation, zero-price nonempty
orders, atomic multi-line failure, concurrent reservation, retry/replay, stale
versions, partial/full returns and durable restart. Include tests that cover
actual routes and persisted state, not only internal helper functions. Exercise
your frontend. Measure read and write throughput/latency/error counts in a
repeatable local workload and explain hardware/concurrency/methodology; no target
RPS or time budget is imposed. Stop when the requested deliverable and your
appropriate verification are complete; report any genuine remaining failure.
