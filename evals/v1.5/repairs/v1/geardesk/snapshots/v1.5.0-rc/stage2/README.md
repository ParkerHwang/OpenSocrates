# GearDesk

A local, fictional equipment desk. Requires Node.js 20 or newer. No package installation or external service is needed.

## Run

From this directory:

```sh
npm test
mkdir -p /tmp/geardesk-data
node server.mjs --data-dir /tmp/geardesk-data --catalog fixtures/catalog.json --port 0
```

The server prints `{"port":<actual port>}`. Open `http://127.0.0.1:<port>/` for the developer console. The HTTP API binds only to `127.0.0.1`.

The CLI accepts one JSON object from stdin and writes one JSON response:

```sh
printf '%s' '{"memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}]}' | node cli.mjs --data-dir /tmp/geardesk-data --catalog fixtures/catalog.json quote
printf '%s' '{"type":"reserve","id":"r1","idempotencyKey":"request-1","expectedRevision":0,"memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}]}' | node cli.mjs --data-dir /tmp/geardesk-data --catalog fixtures/catalog.json command
node cli.mjs --data-dir /tmp/geardesk-data --catalog fixtures/catalog.json report </dev/null
```

Other CLI operations are `catalog`, `availability`, `reservations`, and `maintenance`. Availability takes `{"start":"2026-11-06","end":"2026-11-09"}`. HTTP equivalents are `GET /api/catalog`, `POST /api/quote`, `POST /api/availability`, `POST /api/command`, `GET /api/reservations`, `GET /api/maintenance`, and `GET /api/report`. `GET /api/health` checks the listener.

Every domain response includes `ok` and `revision`; successful responses include `data`, and failures include an error code and message. A new command needs an idempotency key and the revision last observed. Replay the same command with the same key to receive its original result without a new audit event. Reserve IDs are unique. `cancel` and `checkout` require a reserved booking; `return` requires a checked out booking and reports the frozen deposit refund.

`maintenance.add` accepts `id`, `itemId`, `start`, `end`, and `quantity` plus the normal mutation fields. `maintenance.remove` accepts `id` plus those mutation fields. Maintenance IDs are unique among maintenance records. A maintenance interval occupies equipment on each included day; the maintenance read operation lists active records. Both maintenance commands use the same revision, replay, and audit rules as reservations.

## Code and storage

`src/domain.mjs` exports `emptyStore`, `quote`, `availability`, `command`, `reservations`, `maintenance`, and `report`. Pass a catalog object and store object directly to exercise rental logic without starting a server or accessing disk. `command` returns a new store and result; the caller chooses when to persist it. Dates are UTC calendar days in a half open range, up to 30 days. Pricing uses integer KRW and the supplied `src/shared` helpers. Saturday and Sunday rates are rounded per unit per day using `pricing.weekendBps`; absent pricing defaults to 10000 basis points. Member discounts apply to the aggregate rental subtotal and are limited by `pricing.discountCap` when present. Deposits are unchanged.

`src/service.mjs` reads the catalog for each operation and owns persistence. It uses `store.json` in the requested data directory, a directory lock for writers, and a temporary file plus rename for atomic replacement. No file outside that data directory is used for store state. Existing invalid or unsupported store data causes failure and is left untouched. Stores created before maintenance existed are read with an empty maintenance list; their bookings, audit, and replay records are preserved. Accepted quotes are stored on reservations, so changing the catalog affects future quotes only. A lock left behind by an interrupted process causes `BUSY` until it is removed manually after checking that no writer is active.
