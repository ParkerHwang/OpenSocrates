# DepotFlow

DepotFlow is a locally runnable multi-tenant fulfillment console for two small
warehouse operators. It includes a persistent SQLite backend, same-origin web
UI, route-level integration tests, browser smoke coverage, and a repeatable
local load exercise.

## Run it

Requirements: Python 3. The application uses only the standard library, so no
database service, container, account, or dependency download is needed.

```sh
./setup.sh
PORT=8000 DATA_DIR="$PWD/.depotflow-data" SEED_DEMO=1 ./run.sh
```

Open <http://127.0.0.1:8000/>. `run.sh` always binds to `127.0.0.1`. `PORT`
selects the HTTP port, `DATA_DIR` selects persistent state, and `SEED_DEMO=1`
seeds only a store whose tenant table is empty. Stop and restart with the same
`DATA_DIR` to preserve users, orders, stock, audit history, sessions, and
idempotency records; demo stock is not reseeded.

Demo users:

| Tenant | Admin | Operator | Viewer | Password |
| --- | --- | --- | --- | --- |
| north | `admin@north.example` | `operator@north.example` | `viewer@north.example` | `DepotDemo!2026` |
| south | `admin@south.example` | `operator@south.example` | `viewer@south.example` | `DepotDemo!2026` |

## Stack and design

The backend is `app.py`, using `ThreadingHTTPServer` and SQLite in WAL mode.
The frontend is `static/index.html`, `static/app.js`, and `static/styles.css`.
SQLite transactions use `BEGIN IMMEDIATE`, which serializes local writes and
makes reservation, shipment, cancellation, return, audit, and idempotency
updates commit together. Inventory is tenant-scoped and `available` is derived
from `on_hand - reserved`; order prices are server-side snapshots. See
[`architecture.md`](architecture.md) for ownership, authentication, error, and
transaction details.

Tradeoffs: the zero-dependency setup is easy to reproduce and durable on one
machine, while SQLite's single-writer behavior is not intended for a
multi-process production warehouse. Tokens are persistent local bearer tokens
without expiry, and there is no external identity service or recovery flow.

## API examples

```sh
BASE=http://127.0.0.1:8000
LOGIN=$(curl -sS -X POST "$BASE/api/session" -H 'Content-Type: application/json' \
  -d '{"email":"admin@north.example","password":"DepotDemo!2026"}')
TOKEN=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])' <<<"$LOGIN")
curl -sS "$BASE/api/inventory" -H "Authorization: Bearer $TOKEN"
```

Domain mutations require a nonempty `Idempotency-Key` header. The UI generates
one for each new mutation. A client that retries must reuse the same key and
payload; a changed request with that key gets a 409, while an exact successful
retry gets the original response without a second audit event.

## Verification commands

Run route and persistence tests:

```sh
PYTHONPATH=. python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Run the browser workflow against a running server. The supplied evaluation
environment exposes a Playwright WebSocket through `EVAL_BROWSER_WS`; the test
uses that existing headless Chromium connection and does not launch a browser
from the shell:

```sh
DEPOTFLOW_BASE=http://127.0.0.1:8000 node tests/browser_smoke.js
```

Run the reproducible workload in a separate seeded data directory:

```sh
PORT=8001 DATA_DIR="$PWD/.depotflow-load" SEED_DEMO=1 ./run.sh
DEPOTFLOW_BASE=http://127.0.0.1:8001 python3 tests/load_test.py --reads 240 --writes 120 --concurrency 12
```

The workload reports throughput, average/p95 latency, and error counts for
authenticated inventory reads and zero-price draft-order writes. It uses unique
references and idempotency keys, so it is repeatable without relying on
customer data.

## Verification evidence from this build

The following checks were run in the supplied workspace while completing the
project; exact command output is kept in the handoff response and can be
reproduced with the commands above.

- Python compile check for `app.py` and the integration test module.
- Route tests covering health/login, tenant and role isolation, strict integer
  validation, server-side pricing, zero-price SAMPLE orders, atomic reservation
  failure, concurrent reservation, idempotent replay/conflict, stale versions,
  partial/full returns, audit counts, cursor filters, and restart durability.
- Playwright browser smoke flow covering login, inventory, order creation with
  multiple lines, order detail, reserve, ship, return, audit, and logout; the
  viewer path checks writable controls are absent.
- A local load run records actual read/write metrics below after execution.

Latest recorded checks:

```text
Ran 4 tests in 0.674s
OK
{"ok":true,"workflow":"login -> inventory -> multi-line order -> reserve -> ship -> partial/full return -> audit","viewer_controls_hidden":true}
```

### Recorded local load result

This section is filled with the measured command output for the current build;
it is a local benchmark, not a capacity guarantee. The result depends on the
machine, Python runtime, SQLite filesystem, request mix, and concurrency.

Measured on Darwin 27.0 arm64 with Python 3.12.14 and SQLite 3.53.1, using one
DepotFlow process on loopback and a 12-worker client pool:

```text
base=http://127.0.0.1:8124 reads=240 writes=120
reads: requests=240 concurrency=12 throughput=2914.30 req/s elapsed=0.082s avg=4.00ms p95=6.13ms errors=0 error_types={}
writes: requests=120 concurrency=12 throughput=1071.03 req/s elapsed=0.112s avg=7.05ms p95=45.34ms errors=0 error_types={}
```

Reads were authenticated `GET /api/inventory` requests. Writes were unique
authenticated `POST /api/orders` requests for one-unit zero-price SAMPLE draft
orders, each with a unique idempotency key. The result is a short local sample;
it excludes browser rendering and should not be read as production capacity.

## Known limits

The tests exercise the real HTTP routes and a representative concurrent writer
race, but they do not constitute an exhaustive formal proof of all schedules or
a crash-at-every-instruction durability test. The application is deliberately
single-host and has no TLS, rate limiting, expiry policy, or external user
management; use it only as the requested local synthetic-data exercise.
