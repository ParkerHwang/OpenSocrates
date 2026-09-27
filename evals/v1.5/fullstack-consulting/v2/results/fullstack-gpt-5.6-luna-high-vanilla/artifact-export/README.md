# DepotFlow

DepotFlow is a locally runnable, multi-tenant fulfillment control room for two small warehouse operators. It supports authenticated receiving, atomic reservation, shipping, cancellation, returns, stock adjustments, audit history and a responsive browser UI.

## Run it

The only runtime requirement is Python 3.8+; the service uses the standard library and SQLite. `setup.sh` is informational because there are no packages to install.

```sh
./setup.sh
SEED_DEMO=1 DATA_DIR="$PWD/data" PORT=8000 ./run.sh
```

The server binds to `127.0.0.1`. `DATA_DIR` contains the SQLite database and is durable across restarts. Seeding happens only when the database has no tenants. The UI is at <http://127.0.0.1:8000> and the API is same-origin under `/api`.

Demo accounts for both tenants use `DepotDemo!2026`:

```text
admin@north.example     operator@north.example     viewer@north.example
admin@south.example     operator@south.example     viewer@south.example
```

The `admin` role can adjust stock; `operator` can create and transition orders; `viewer` is read-only. Every mutation requires a tenant-scoped `Idempotency-Key`; the session endpoint is the exception.

## Implementation

`server.py` is a threaded `http.server` application with one SQLite connection per request. SQLite WAL mode is intentionally available to the local database; every mutation uses `BEGIN IMMEDIATE`, performs all order/stock/audit/idempotency writes together, and commits once. Sessions and idempotency responses are stored in the database, so retries and the demo login survive a process restart. The frontend is dependency-free HTML, CSS and JavaScript in `static/`.

Important choices and limitations are documented in [architecture.md](architecture.md). The application is deliberately a small local service rather than a production deployment: it has no TLS, external identity provider, background jobs, email, or horizontal-cluster coordination.

## Verification

The integration suite starts the real `run.sh` process against a temporary SQLite directory and exercises HTTP routes, persistence, tenant/role isolation, validation, zero-price orders, atomic failure, concurrent reservation, idempotent replay, stale versions, partial/full returns, audit pagination and restart durability:

```sh
python3 -m unittest -v tests/test_app.py
```

The browser check uses the supplied Playwright Chromium WebSocket. A small repeatable local read workload is:

```sh
python3 load_test.py http://127.0.0.1:8000 8 400
```

Results are machine- and workload-specific; the script splits its request count evenly between `GET /api/inventory` as a viewer and unique `POST /api/orders` draft creation as an admin, using 8 client threads. `load_test.py` reports p50/p95 latency, throughput and errors for both phases. The write phase intentionally leaves draft orders in the selected local store, so use a disposable `DATA_DIR`. It is not a capacity claim.

### Verification record

- Static syntax checks: `python3 -m py_compile server.py tests/test_app.py load_test.py` and `node --check static/app.js` passed.
- Route integration tests: `python3 -m unittest -v tests/test_app.py` passed, 5 tests in 0.18s. This included a real two-thread reservation race and a stop/start against the same `DATA_DIR`.
- Browser workflow: supplied headless Chromium connected over `EVAL_BROWSER_WS`; operator login, inventory, order creation/detail, audit navigation and viewer writable-control hiding passed.
- Load exercise: on Darwin 27.0.0 arm64, Python 3.12.14, `python3 load_test.py http://127.0.0.1:18767 8 400` reported 200 reads in 0.094s at 2,135.89 requests/s (p50 3.68ms, p95 5.21ms, 0 errors) and 200 writes in 0.164s at 1,218.72 requests/s (p50 0.71ms, p95 5.03ms, 0 errors). This was a local single-process smoke workload, not a production capacity result.
