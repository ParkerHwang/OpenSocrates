# Verification record

Checks below were run in this workspace on the current project files. The test database and browser-run database were temporary; benchmark output is preserved as JSON in this directory.

## Automated HTTP integration

Command:

```sh
python3 -m unittest discover -s tests -v
```

Eight integration test methods passed in the final run (0.454 seconds reported by `unittest`). They start `run.sh` with `SEED_DEMO=1`, use an isolated `DATA_DIR`, and exercise HTTP routes. The suite verifies both tenant inventories and data boundaries; invalid/missing auth; viewer and operator authorization; trusted catalog pricing and extra-field ignoring; zero-price SAMPLE orders; malformed/duplicate/unknown lines; key collision, replay, failed-key retry, tenant-scoped keys, concurrent identical creates and reservations; atomic multi-line reservation failure; two different orders racing for limited stock; stale versions; reserved-stock floors; ship/cancel/return behavior; partial and full returns; audit uniqueness and pagination; and persistence across a process restart including idempotency replay. No test failures remained.

## Browser workflow

`PORT=8765 node scripts/browser_smoke.js` connected through the supplied isolated Playwright WebSocket. It logged in as the north operator, created a two-line BOLT/CABLE order in the UI, reserved it, shipped it, submitted a partial return and the remaining return, checked the audit table, logged out, and confirmed the viewer sees no order-creation or reserve control. At 390 CSS pixels, document width was 390 pixels. The run reported no uncaught page errors. The captured desktop order-detail state is [browser-order-workflow.png](browser-order-workflow.png).

The smoke script needs `EVAL_BROWSER_WS`, which is supplied by the local evaluation/browser environment; it does not launch its own Chromium process.

## Performance exercise

Command:

```sh
python3 scripts/benchmark.py --reads 600 --writes 100 --concurrency 8
```

This starts a fresh seeded service and temporary SQLite database, logs in once, then runs a shuffled mix of authenticated inventory/dashboard/order-list reads and unique zero-price SAMPLE order creates using 8 client threads. Result: 700 requests in 0.3443 s; 600 GETs returned 200, 100 order creates returned 201, and there were 0 errors. The measured mixed-run rates were 1,742.75 reads/s and 290.46 writes/s; the combined rate was 2,033.21 requests/s. Read latencies: p50 2.273 ms, p95 7.757 ms, p99 10.760 ms. Write latencies: p50 4.778 ms, p95 32.788 ms, p99 106.603 ms. Full output, including the host runtime description and methodology, is in [benchmark.json](benchmark.json).

Environment reported by Python: macOS 27 arm64, 10 logical CPUs, Python 3.12.14, SQLite 3.53.1. The timed run used loopback HTTP and local temporary SQLite WAL storage. It is one short synthetic run against a tiny seeded catalog, not a sustained or production capacity test.

## Setup check

`./setup.sh` succeeded and reported Python 3.12.14 and SQLite 3.53.1. It also compiled `app.py`; no dependency installation was needed.
