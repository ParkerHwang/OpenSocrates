# Verification record

All verification was local, using synthetic data. TASK.md and TOOLING.md were preserved. No helpers, external models, accounts, customer data, deployments, or global settings were used.

## Executed checks

- `./setup.sh --browser`: runtime check and reproducible local `npm ci`; succeeded. The existing isolated browser connection was used and no browser was launched by the shell. See `setup.txt`.
- `python3 -m unittest discover -v`: 15 real-route tests, independent subprocess/data directory per test. See `api-tests.txt` for exact duration and outcome.
- `python3 scripts/run_browser.py`: Playwright against a fresh actual server, Chromium 148.0.7778.96, 1440×1100 and 390×844 viewports. See `browser-results.json` and `browser-tests.txt` for the 11 final scenario groups. Screenshots were produced by the same run; desktop inventory and mobile order screenshots were visually inspected during development.
- `node --check static/app.js` and `python3 -m compileall -q depotflow scripts tests`: passed.
- `python3 scripts/load.py --concurrency 1 --output evidence/performance-c1.json` and the equivalent concurrency-8 command: each 8,000 domain writes and 10,000 reads; zero HTTP errors and all post-workload persisted invariants passed. Full reports include hardware fields, percentile timings, method description, exact status counts, and file sizes.

## Corrections made during verification

The first browser pass exposed an assertion racing a filter response: the reference was already visible in the previous list. The assertion now waits for the filtered list to contain one row. No application filter defect was inferred from that early failure.

A preliminary 18,000-request load run used a fresh TCP connection for every request. The local client exhausted ephemeral ports (`Can't assign requested address`) before final validation. HTTP/1.1 keep-alive and one persistent connection per load worker eliminated that client bottleneck. Final reports come from fresh reruns after the correction, not from the failed run.

Review of the first mobile screenshot showed that return inputs required horizontal scrolling. Order detail now changes to labeled stacked rows at mobile widths. Inventory/audit tables remain horizontally scrollable with keyboard-focusable regions.

Filtered pagination was strengthened to retain membership even when later pages' orders change status. A persisted status history, committed with the corresponding event, supports that invariant without writing during reads. The route suite explicitly changes a matching order between pages and verifies that no original match disappears.

## Limits of this evidence

The final route/browser suites and workload checks pass. The load measurements are single runs of small local datasets (2,000 orders per run), with short phases rather than a long soak or steady-state capacity study. Read and write phases were measured separately; there is no measured mixed read/write saturation curve. Authentication hashing is excluded from throughput measurements. SQLite writer contention can cause long tails, as the reported 1.4-second maximum demonstrates. The client shares CPU and storage with the server. CPU model and RAM inspection were unavailable in the supplied sandbox.

Browser checks use only Chromium, and the keyboard checks are basic. No screen-reader audit, browser-engine matrix, real network partition test, disk-full simulation, power-loss test, or account administration workflow was run. One committed-response loss was deliberately simulated in Playwright, and durable recovery was verified after both graceful termination and process kill.
