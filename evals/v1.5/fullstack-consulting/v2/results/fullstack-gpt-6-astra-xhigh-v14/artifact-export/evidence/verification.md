# Verification record

All data in these checks was generated locally in isolated stores. No other evaluation cell, customer data, credentials, or external service was used. `TASK.md` and `TOOLING.md` were preserved.

## Recorded checks

| Check | Actual execution and outcome | Evidence |
| --- | --- | --- |
| Python syntax | `python3 -m py_compile app.py database.py service.py` exited 0 | Initial implementation check; final files also imported/executed by integration tests |
| Browser JavaScript syntax | `node --check static/app.js` exited 0 | Initial implementation check; final script executed in Chromium |
| HTTP/persistence suite | `python3 -m unittest -v tests.test_api` — 26 tests, 7.114 seconds, all passed | [api-tests.txt](api-tests.txt) |
| Browser workflow | `npm run test:browser` after local dependency installation — 12 recorded checks, all passed; zero uncaught page exceptions | [browser-results.json](browser-results.json), [browser-tests.txt](browser-tests.txt) |
| Optional dependency setup | Lockfile generated, then `npm ci --ignore-scripts --no-audit --no-fund --cache .npm-cache` exited 0 | Root `package-lock.json`, [dependency-setup.txt](dependency-setup.txt); application runtime requires no npm dependencies |
| Input preservation | Both supplied files compared byte-for-byte to the project's original Git versions | [preserved-inputs.json](preserved-inputs.json) |
| HTTP performance | 20,000 successful writes and 30,000 successful reads at concurrency 8 | [performance.json](performance.json), [performance-run.txt](performance-run.txt), [raw samples](performance-samples.json) |
| Persisted load postconditions | 5,000 returned orders; 20,000 events; 20,000 retry records; initial stock restored; integrity `ok`; no foreign-key violations | `postconditions` in performance.json |

API tests and browser tests use actual server subprocesses launched via the executable root `run.sh`. They request JSON APIs over loopback HTTP. Tests inspect whole persisted business tables when asserting rejection/rollback. They do not replace the backend with mocks. The browser network-interruption check deliberately intercepts one response only, after allowing the real server write to commit.

## Requirement coverage

| Behavior under test | Failure observation used by the checks | Result |
| --- | --- | --- |
| Seed independence, empty-store guard | Wrong seed values, tenant bleed, reseeded depletion, or inaccessible valid demo user | Passed for all six users and both seed modes |
| Auth and role isolation | Unauthenticated access, successful viewer/operator-only forbidden adjustment, client tenant/role override, or foreign-object visibility | Correct 401/403/404 responses; business state unchanged |
| Order validation and catalog prices | Accepted empty/repeated/unknown SKU lines, bool/fraction quantities, duplicate references, client prices, or zero-price rejection | Validation and immutable server price snapshot checks passed |
| Atomic multi-line reservation | First line remains reserved after a later line fails | Full persisted snapshot unchanged after failure; retry succeeds after replenishment |
| Concurrent stock reservation | Two orders reserve 60 BOLT each from a stock of 100 | One succeeds, one receives 409; no oversell or extra audit event |
| Concurrent idempotency | More than one create/adjustment/reserve/ship/return effect for identical concurrent requests | 12–16 simultaneous identical requests replay one result; one effect/event |
| Changed retry payload and stale version | Conflicting key or obsolete version changes persisted state | 409 and unchanged state; auth still checked before replay |
| Failed request key reuse | A failed request prevents a corrected/satisfied retry | Failed keys remain reusable |
| Shipment and cancellation | Ship changes available stock, cancellation leaks reservations, or shipped order can cancel | Correct transitions, stock effects, and 409 failures |
| Partial/full returns | Excess/invalid return accepted, partial return closes order, or duplicate return restores extra stock | Correct cumulative quantities, statuses, versions, and atomic failures |
| Audit/storage failure | A failed audit insertion leaves stock/order changes committed | Injected database trigger causes 500 and full rollback; same-key retry succeeds after removing injection |
| Stable pagination | Duplicated/omitted initial matches after insertion or status change; forged/cross-tenant cursor accepted | Original membership preserved, invalid cursors rejected, oldest-first traversal |
| Search and filters | SQL wildcards treated as user search syntax, broken case folding, invalid filters accepted | Literal `%`/`_` and Unicode casefold checks passed; invalid filters return 400 |
| Durable restart | Lost session/stock/order/audit/key/cursor or reintroduced seed stock after SIGKILL | Committed state and replay survive forced restart; SQLite integrity and foreign keys pass |
| Browser workflow | Inoperable form/actions, discarded stale input, duplicated uncertain write, rendered client HTML, or writable viewer controls | Passed desktop and mobile scenarios; snapshots saved |

## Browser evidence

Chromium **148.0.7778.96**, desktop viewport **1440 × 1000**, mobile viewport **390 × 844**. The final automation run used locally installed, lockfile-pinned Playwright 1.62.1 and connected to the provided isolated browser. It created its own browser context, synthetic database, and application process, then closed all three. Downloading/launching a separate local Chromium was not tested in this sandbox; the ordinary-install command is provided in the README.

The exercise signed in, showed bad-credential feedback, adjusted stock, created a two-line order, reserved/shipped it, performed partial/full returns, cancelled a zero-price order, recovered from stale return input, searched/filtered orders, checked an empty result, rendered hostile-looking client text safely, replayed a dropped successful response, inspected audit stock history, completed a narrow-screen order with a keyboard return, inspected as viewer, and operated within the south tenant. A page-width assertion checked for mobile horizontal overflow outside table scrolling.

Saved captures:

- [Login on desktop](login-desktop.png)
- [Inventory on desktop](inventory-desktop.png)
- [Partial return on desktop](order-desktop.png)
- [Expanded audit history](audit-desktop.png)
- [Inventory at mobile width](inventory-mobile.png)
- [Returned order at mobile width](order-mobile.png)

Desktop inventory and mobile order screenshots were also visually inspected. This is functional Chromium evidence, not a full assistive-technology audit or cross-browser certification.

## Performance methodology and result

Recorded on **2026-09-27**, using the following command after the functional implementation:

```sh
python3 scripts/benchmark.py --concurrency 8 --orders 5000 --reads 30000 \
  --output evidence/performance.json
```

Observed runtime: macOS 27.0 arm64, **10 logical CPUs** reported by Python, Python **3.12.14**, SQLite **3.53.1**. CPU model, physical CPU count, and memory capacity were unavailable because local `sysctl` access was denied. No escalation was attempted. Storage is the supplied local workspace; device model, physical flush behavior, and background host load were not measured.

One process serves the application while eight Python worker threads drive HTTP/1.1 over `127.0.0.1`, with one persistent connection per client. The workload is closed-loop: each client waits for its response, with no pacing or retry. There are 40 untimed warmup inventory reads. Startup, seeding, login, and postcondition checks are outside the timing window. Per-request latency includes client serialization, request/response processing, and JSON parsing. Phase throughput is completed request count divided by phase wall time. Percentiles use sorted samples and nearest rank.

Each write cycle creates an order for 2 BOLT, 1 CABLE, and 1 SAMPLE, reserves it, ships it, and returns all units. There are 5,000 cycles and 20,000 successful mutations. Read measurements follow the write phase against this accumulated history: 7,500 each of inventory, dashboard, 20-order first-page lists, and 20-event first-page audit lists. Reads are not a random deep-pagination benchmark. Full raw samples are provided so aggregate figures can be recomputed.

| Phase | Duration | Requests | Requests/s | p50 | p95 | p99 | Maximum | Errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Writes | 8.8823 s | 20,000 | 2,251.67 | 0.426 ms | 5.051 ms | 57.015 ms | 1,321.260 ms | 0 |
| Reads | 15.8660 s | 30,000 | 1,890.83 | 2.770 ms | 7.691 ms | 21.579 ms | 30.799 ms | 0 |

These are **computed** from this run, not forecast service-level guarantees. The substantially longer write tail is observed; SQLite writer serialization is a plausible contributing cause, but the run did not instrument lock waits separately. No causal breakdown is claimed. After the run, all 5,000 orders were returned, reservations were zero, stock was BOLT 100/CABLE 60/SAMPLE 20, and the two audit/retry counts were exactly 20,000. `PRAGMA integrity_check` was `ok`; `foreign_key_check` returned no rows. Database and WAL files totaled 48,234,496 bytes at inspection.

The first shorter measurement completed its requests with zero errors but failed report generation when the hardware probe was denied. That failure is retained in [performance-initial-attempt.txt](performance-initial-attempt.txt). The script was changed to record unavailable hardware metadata, and the longer full run above completed all postconditions. The failed attempt is not counted as a successful complete benchmark.

## Completion claim and disproof conditions

| Public field | Statement |
| --- | --- |
| claim | The delivered local implementation supports the supplied warehouse workflow with tenant/role isolation, transactional inventory, durable replay, and a usable UI. |
| scope | This artifact, seeded synthetic data, defined HTTP surface, tested concurrent operations, and observed local Python/SQLite/Chromium environment. |
| risky_prediction | Competing and repeated HTTP writes cannot oversell or duplicate effects; rejected/failed operations leave persisted business state unchanged; committed state and replay survive restart; the real browser can complete the workflow. |
| falsifier | Any test observing unauthorized tenant data, a negative/excess reservation, duplicate side effect/event, partial rollback, lost committed state/replay, or an unusable required browser action rejects completion for that behavior. |
| auxiliary_assumptions | Correct local Python/SQLite runtime, isolated test store, loopback reachability, and ordinary filesystem operation. No physical disk/power-failure model is assumed tested. |
| measurement_conditions | Real subprocess HTTP calls, synchronized concurrent requests, direct persisted snapshots, deliberate post-write audit fault, forced process restart, and actual Chromium DOM interaction. |
| observed_needed_test | The supplied route suite, browser suite, and load postconditions were executed. Production soak, multiple browsers, and hardware-failure testing remain unrun because no such capacity/availability claim is made. |
| test_and_provenance | Repository test scripts and the linked local logs/JSON/screenshots; results are from this implementation's own verification. Test assertions express task requirements before their corresponding final run. |
| observed_or_needed_result | Observed: 26 route tests pass; 12 browser checks pass; 50,000 measured HTTP requests produce no errors; persisted load postconditions pass. |
| status | **Supported-for-this-test**, not proof for all workloads. Executions/results are **verified** by saved outputs; aggregate performance is **computed**; wider production applicability remains **unverified**. |
| flip_condition | A reproducible violation of a stated invariant or required workflow reopens completion. New internet exposure, platform, scale, or availability requirements reopen the architecture/capacity decision. |

An input-parser review found that an exponent overflowing Python's float range could reach canonicalization as infinity. The JSON-envelope check was tightened to reject all nonfinite values, and `1e999` was added to the malformed-JSON route tests before the final successful run. The outcome was repaired in code rather than reclassified as acceptable input. The hardware-probe failure was a measurement/setup limitation, and remains documented separately from application correctness.

There is no known remaining required-workflow failure. Remaining limits are explicit: local standard-library server, serialized database writers, no production authentication/rate limiting/TLS stack, tab-memory form drafts/retry keys, no live push between users, no browser coverage beyond Chromium, no sustained mixed soak or physical crash/power-loss test, and incomplete hardware metadata. The next action for local use is the README startup command. Additional tests should be driven by changed requirements or a concrete failure rather than repeating unchanged passing checks.

## Controller evidence boundary

The installed OpenSocrates selector delivered complete canonical `trade-off-analysis@3` and `falsificationism@3` procedures. The former informed the public architecture comparison; the latter informed this requirement-based disproof/completion record. Both canonical procedures were read. Native activation and public-artifact confirmation remain **unconfirmed**; the selector reports application as unverified. That is an instrumentation limit, not a claim of an unperformed application test. No private reasoning narrative, raw prompt archive, or native receipt was fabricated.
