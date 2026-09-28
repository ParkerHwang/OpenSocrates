# GearDesk

GearDesk is a local, fictional equipment rental desk. It uses Node ES modules and no installed dependencies. All amounts are integer KRW. The included Korean developer console calls the same HTTP operations as the CLI.

## Run

Use Node 20 or later. From this directory:

```sh
npm test
mkdir -p ./local-data
node server.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json --port 0
```

The server prints one JSON startup line with its actual port and binds `127.0.0.1`. Open `http://127.0.0.1:PORT/` for the console. The store is `local-data/store.json`. Use a caller chosen data directory for each independent desk.

CLI operations are `catalog`, `quote`, `availability`, `command`, `batch`, `reservations`, `maintenance`, and `report`. Provide one JSON request on stdin; an empty request means `{}`. The CLI emits one JSON response and exits nonzero for a business error.

```sh
printf '%s\n' '{"memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}]}' | node cli.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json quote
printf '%s\n' '{"type":"reserve","id":"demo-1","memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}],"idempotencyKey":"demo-key-1","expectedRevision":0}' | node cli.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json command
printf '%s\n' '{"type":"maintenance.add","id":"camera-service-1","itemId":"camera","start":"2026-11-10","end":"2026-11-12","quantity":1,"idempotencyKey":"demo-key-2","expectedRevision":1}' | node cli.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json command
```

Use the current response revision as `expectedRevision` for a new command. Repeating the same command with its original key and an older expected revision returns the original success. A key cannot be reused for different command content. Dates are UTC calendar days in `[start,end)` and span 1 to 30 days.

The HTTP routes are `GET /api/catalog`, `POST /api/quote`, `POST /api/availability`, `POST /api/command`, `POST /api/batch`, `GET /api/reservations`, `GET /api/maintenance`, `GET /api/report`, and `GET /api/health`. For example:

```sh
curl -s -H 'Content-Type: application/json' -d '{"start":"2026-11-06","end":"2026-11-09"}' http://127.0.0.1:PORT/api/availability
```

## Code and state

`src/domain.mjs` contains validation, availability, quoting, transitions, and reporting. Its exported functions take plain catalog and store objects and can be called in a Node test or REPL without opening a server or reading disk. For example, `quote(emptyStore(), validateCatalog(catalog), request)` returns a quote. `command(store, catalog, request, timestamp)` returns a new store and result; it does not mutate the input. `src/shared/` retains the supplied date and money helper APIs.

`src/service.mjs` reloads the catalog for each operation and owns store I/O. A lock directory in the data directory serializes mutations across processes, including revision checks. Writes use a temporary file and rename. A store that is malformed or has an unsupported schema is rejected and left intact. If a process dies while holding the lock, later commands return `BUSY` until the operator removes the stale `.store.lock` directory after checking that no writer is running. Reads use the last complete `store.json`; they do not wait for a writer.

The reservation quote is frozen when accepted. New quotes use current catalog prices and stock. An optional catalog `pricing` object sets `weekendBps`, `discountCap`, and `lateFeePerUnitDay` (default 0). Weekend rates round half up per unit per day before quantity is applied. The member discount uses the total rental subtotal, then the optional cap. New reservations snapshot each item's deposit and the late fee rate. `reserved` and `checked_out` reservations and active maintenance occupy their scheduled days. Returned units release scheduled capacity immediately; late possession does not extend the inventory horizon.

`return.partial` takes `id`, `returnedOn` (UTC `YYYY-MM-DD`), and nonempty `lines` with unique booked item IDs and positive quantities no greater than the unreturned balance. `return` returns every remaining unit and defaults `returnedOn` to the scheduled end. Both require `checked_out` status. Each result includes `refund`, `lateFee`, and `returnedQuantity`. Fees are whole late days times returned units times the frozen rate, capped at the deposits for those units. The report's `depositHeld` counts unreturned active units; `refunded` and `lateFees` accumulate across returns. Cancellation releases deposits without a refund entry.

`batch` and `POST /api/batch` take `{ "expectedRevision": 0, "idempotencyKey": "batch-1", "commands": [{ "type": "reserve", ... }] }`. Supply 1–20 commands without individual `expectedRevision` or `idempotencyKey` fields. The domain runs them in order against one working copy; the service writes only after all succeed. Each inner command advances revision and creates an audit entry. The batch has a separate idempotency namespace and no extra revision. Replaying the same batch key and content returns the original results even with a stale expected revision.

Stores written now use schema version 2. Version 1 loads in memory and is saved as version 2 after a successful mutation. Historical quote totals, IDs, audit and idempotency records remain; old reservations get a zero late fee rate. Version 1 only recorded aggregate deposits, so migration divides an old reservation's deposit evenly across its booked units, assigning any remainder to the first units in line order. This preserves its exact total, but historical per-item deposits cannot be reconstructed. Old fully returned reservations remain fully refunded, and cancelled reservations remain cancelled. Invalid or unsupported stores are rejected without rewriting them.

Operation errors use `VALIDATION` for malformed requests, dates, quantities, catalog or store; `NOT_FOUND` for unknown members, items or reservation IDs; `CAPACITY` for insufficient stock; `INVALID_TRANSITION` for a status that disallows the requested action; `REVISION_CONFLICT` for a stale expected revision; `IDEMPOTENCY_CONFLICT` for reusing a key with different content; and `BUSY` for lock or storage failure. HTTP maps validation to 400, missing records to 404, and conflicts or busy state to 409. CLI emits the same response shape and exits nonzero on failure. A failed mutation, including a failed batch suffix, leaves persisted store bytes unchanged.
