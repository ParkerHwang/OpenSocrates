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

Other CLI operations are `catalog`, `availability`, `reservations`, `maintenance`, and `batch`. Availability takes `{"start":"2026-11-06","end":"2026-11-09"}`. HTTP equivalents are `GET /api/catalog`, `POST /api/quote`, `POST /api/availability`, `POST /api/command`, `POST /api/batch`, `GET /api/reservations`, `GET /api/maintenance`, and `GET /api/report`. `GET /api/health` checks the listener.

Every domain response includes `ok` and `revision`; successful responses include `data`, and failures include an error code and message. A new command needs an idempotency key and the revision last observed. Replay the same command with the same key to receive its original result without a new audit event. Reserve IDs are unique. `cancel` and `checkout` require a reserved booking; `return` and `return.partial` require a checked out booking.

`return.partial` takes `id`, `returnedOn`, and `lines` of `{itemId,quantity}` plus the normal mutation fields. Quantities must be positive whole units from that booking and cannot exceed the units still out. `return` takes `id` and optionally `returnedOn` and returns every remaining unit; omission uses the scheduled end. Dates use real UTC calendar days and cannot precede the booking start. Both commands report `refund`, `lateFee`, and `returnedQuantity`. The fee is the lesser of the returned units' frozen deposit and `returnedQuantity × days after scheduled end × frozen lateFeePerUnitDay`. Availability releases returned units in the scheduled interval. `report` includes cumulative `refunded` and `lateFees`, while `depositHeld` counts only unreturned units in reserved or checked out bookings. Cancelling a reserved booking releases its deposit without a refund entry.

`batch` takes `{"expectedRevision":0,"idempotencyKey":"batch-1","commands":[{"type":"reserve","id":"r1","memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}]},{"type":"checkout","id":"r1"}]}`. It accepts 1 to 20 commands without inner `expectedRevision` or `idempotencyKey`. Commands run in order against the results of earlier commands. Any failure leaves the stored file, audit, and replay records unchanged. A successful batch returns an array of command results and adds one revision and audit event per inner command. The batch key has its own replay namespace; replay returns the original array without changing revision. Reusing a key for different content within its operation namespace fails.

Errors use `VALIDATION` for malformed input, invalid dates, unsupported or malformed store data, and duplicate IDs; `NOT_FOUND` for absent members, items, bookings, or maintenance; `CAPACITY` for overbooking; `INVALID_TRANSITION` for a disallowed status change; `REVISION_CONFLICT` for a stale new mutation; `IDEMPOTENCY_CONFLICT` for a reused key with different content in its namespace; and `BUSY` if the writer lock cannot be acquired. HTTP maps validation to 400, not found to 404, and conflicts or busy state to 409. A replay is checked before the expected revision, so it can succeed with its original revision value.

`maintenance.add` accepts `id`, `itemId`, `start`, `end`, and `quantity` plus the normal mutation fields. `maintenance.remove` accepts `id` plus those mutation fields. Maintenance IDs are unique among maintenance records. A maintenance interval occupies equipment on each included day; the maintenance read operation lists active records. Both maintenance commands use the same revision, replay, and audit rules as reservations.

## Code and storage

`src/domain.mjs` exports `emptyStore`, `quote`, `availability`, `command`, `batch`, `reservations`, `maintenance`, and `report`. Pass a catalog object and store object directly to exercise rental logic without starting a server or accessing disk. Both mutation functions return a new store and result; the caller chooses when to persist it. Batch reuses the same internal command rules as single commands. Dates are UTC calendar days in a half open range, up to 30 days. Pricing uses integer KRW and the supplied `src/shared` helpers. Saturday and Sunday rates are rounded per unit per day using `pricing.weekendBps`; absent pricing defaults to 10000 basis points. Member discounts apply to the aggregate rental subtotal and are limited by `pricing.discountCap` when present. Deposits are unchanged. A new reservation stores `lateFeePerUnitDay` with its accepted quote; a missing catalog rate is zero.

`src/service.mjs` reads the catalog for each operation and owns persistence. It uses `store.json` in the requested data directory, a directory lock for writers, and a temporary file plus rename for atomic replacement. CLI and HTTP call that same service. No file outside that data directory is used for store state. New writes use schema version 2. Version 1 stores migrate in memory, preserving bookings, frozen quotes, maintenance, audit, and individual replay records. Historical bookings get a zero fee rate; fully returned bookings retain their full refund, and cancelled bookings remain cancelled. Failed writes never persist the migration. Invalid or unsupported data is rejected without replacement. Accepted quotes are stored on reservations, so changing the catalog affects future quotes only. A lock left behind by an interrupted process causes `BUSY` until it is removed manually after checking that no writer is active.
