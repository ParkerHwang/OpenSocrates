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

CLI operations are `catalog`, `quote`, `availability`, `command`, `reservations`, `maintenance`, and `report`. Provide one JSON request on stdin; an empty request means `{}`. The CLI emits one JSON response and exits nonzero for a business error.

```sh
printf '%s\n' '{"memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}]}' | node cli.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json quote
printf '%s\n' '{"type":"reserve","id":"demo-1","memberId":"club","start":"2026-11-06","end":"2026-11-09","lines":[{"itemId":"camera","quantity":1}],"idempotencyKey":"demo-key-1","expectedRevision":0}' | node cli.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json command
printf '%s\n' '{"type":"maintenance.add","id":"camera-service-1","itemId":"camera","start":"2026-11-10","end":"2026-11-12","quantity":1,"idempotencyKey":"demo-key-2","expectedRevision":1}' | node cli.mjs --data-dir ./local-data --catalog ./fixtures/catalog.json command
```

Use the current response revision as `expectedRevision` for a new command. Repeating the same command with its original key and an older expected revision returns the original success. A key cannot be reused for different command content. Dates are UTC calendar days in `[start,end)` and span 1 to 30 days.

The HTTP routes are `GET /api/catalog`, `POST /api/quote`, `POST /api/availability`, `POST /api/command`, `GET /api/reservations`, `GET /api/maintenance`, `GET /api/report`, and `GET /api/health`. For example:

```sh
curl -s -H 'Content-Type: application/json' -d '{"start":"2026-11-06","end":"2026-11-09"}' http://127.0.0.1:PORT/api/availability
```

## Code and state

`src/domain.mjs` contains validation, availability, quoting, transitions, and reporting. Its exported functions take plain catalog and store objects and can be called in a Node test or REPL without opening a server or reading disk. For example, `quote(emptyStore(), validateCatalog(catalog), request)` returns a quote. `command(store, catalog, request, timestamp)` returns a new store and result; it does not mutate the input. `src/shared/` retains the supplied date and money helper APIs.

`src/service.mjs` reloads the catalog for each operation and owns store I/O. A lock directory in the data directory serializes mutations across processes, including revision checks. Writes use a temporary file and rename. A store that is malformed or has an unsupported schema is rejected and left intact. If a process dies while holding the lock, later commands return `BUSY` until the operator removes the stale `.store.lock` directory after checking that no writer is running. Reads use the last complete `store.json`; they do not wait for a writer.

The reservation quote is frozen when accepted. New quotes use current catalog prices and stock. An optional catalog `pricing` object sets `weekendBps` and `discountCap`; without it, weekends use the base rate and the discount has no cap. Weekend rates round half up per unit per day before quantity is applied. The member discount uses the total rental subtotal, then the optional cap. Deposits do not change. `reserved` and `checked_out` reservations and active maintenance occupy their scheduled days; cancellation, return, and `maintenance.remove` release those days. Maintenance mutations share revision, idempotency, and audit rules. Old stores without `maintenance` load with an empty list. This toy does not model possession beyond the scheduled end date or real payments.
