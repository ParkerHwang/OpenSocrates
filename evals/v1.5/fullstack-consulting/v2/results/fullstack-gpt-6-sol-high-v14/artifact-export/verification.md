# Verification record

All commands below were run in this disposable workspace on 2026-09-27. No external accounts, customer data, deployment, or paid service were used.

| Check | Command or method | Observed result |
| --- | --- | --- |
| Python syntax | `python3 -m py_compile server.py tests/load.py` | Passed |
| JavaScript syntax | `node --check static/app.js` | Passed |
| API and persisted state | `python3 -m unittest discover -s tests -v` | 1 integration test passed; it contains the workflow, validation, isolation, concurrency, retry, pagination, and restart assertions described in the README |
| Browser workflow | `node tests/browser.cjs` with supplied Chromium WebSocket and local server | Passed: two-line create, reserve, ship, partial/full return, audit, order search, admin stock adjustment, south viewer read-only state, 390×844 viewport; 0 page errors |
| Local load | `python3 tests/load.py --reads 300 --workflows 80 --concurrency 8` | Final run: 300 reads and 240 writes, 0 HTTP/transport errors; detailed JSON in `performance-results.json` |

The load tool runs a fresh local server and database, uses loopback HTTP, and measures each request with `time.perf_counter`. Eight Python client threads issue 300 round-robin reads; then eight threads perform 80 create → reserve → ship workflows. Workflow steps are sequential per thread and concurrent across threads. Reported throughput divides request count by the phase wall time. The measured host was macOS 27 arm64, 10 logical CPUs, Python 3.12.14. The final read phase lasted 0.086 seconds at 3,489.8 requests/s (p50 1.99 ms, p95 3.27 ms, max 25.91 ms); writes lasted 0.114 seconds at 2,110.5 requests/s (p50 0.52 ms, p95 11.42 ms, max 75.78 ms). The final dashboard showed 80 shipped orders, 180 on-hand units, and zero reserved units, consistent with the seeded 180 units plus 80 added and 80 shipped.

An initial browser script run failed because its status assertion was case-sensitive while CSS capitalized the displayed status. A later script run timed out because it tried the second return before the first return's refreshed detail appeared. The script now waits for the updated version, and the browser workflow passed. The API suite's first run found an incorrect expected audit count in the test (8 actual successful events versus 9 expected); the assertion was corrected and the suite passed. These were test issues, not observed domain-state failures.

An early 8-client load attempt hit a connection reset, and a measured pre-fix run counted 18 read transport errors while its 240 writes succeeded. The default Python HTTP accept backlog was five. After raising it to 128, two consecutive 8-client runs recorded zero errors; the final result file is from the last run. This local sample is deliberately short and does not establish sustained throughput, multi-process scaling, or performance on other hardware. The browser exercise used the supplied remote Chromium service; it is not a cross-browser compatibility test.
