# Observation ledger and interpretation boundary

The active matrix is `v2/manifest.json`, frozen before actual calls at execution
commit `6fe19fe4b7450a2f68dd6fc4001b05ff2b832ae1`. The subject product candidate
remains `035fafcd208bf9577ca55ff5e42a93df4ca608ea`. `v1/` is immutable and retains
36 pre-call setup failures, zero model invocations and null usage. No failed model
outcome has been discarded or repaired.

The primary does not send follow-ups, choose subject stacks, repair artifacts,
reveal checks or terminate subjects for elapsed time/usage. All requested resource
budgets are null. Provider/client constraints remain possible and are recorded.
The initial three-process scheduler was superseded by the user's explicit request
for maximum simultaneous execution. The [concurrency amendment](parallel-v1/README.md)
atomically transferred all 16 never-started cells at 2026-09-27 10:10:37 UTC and
started them alongside the existing three subjects, reaching 19 live processes
with no queue, signal, restart or duplicate attempt. Original frozen manifests
are unchanged. New calls bind both the base protocol and amendment/dispatch hashes.
Final verification takes place only after the subject has
naturally ended and its artifacts have been hash-locked.

## Files to inspect

| Receipt | What it establishes |
| --- | --- |
| `call.started.json`, `process.json` | Intended tuple, actual CLI invocation, timestamp and manifest binding |
| `inputs.json` | Actual task/config/package identity, post-install config and source/tool environment |
| `sandbox-preflight.json`, `context-preflight.json` | Tested filesystem read denials and absence of known imported memory/history markers |
| `feature-preflight.json` | Native feature inspection: Fast, memory/import, hooks, apps and helper agents off |
| `browser-isolation.json` | Separate new browser tool with filesystem canary rejection and exact executable hash |
| `observation.jsonl` | Timestamped public messages/tool starts/completions/errors, numeric reported usage; no reasoning-text events |
| `resources.jsonl` | Time series of sampled process-tree CPU/RSS and host load, with the browser tool separate |
| `source-requests.jsonl` | Office source-room GET requests; not a complete internet/network trace |
| `call.json` | Terminal status, exact process duration, supplied token categories, errors and missing fields |
| `snapshot.json` | Final file hashes locked before independent checks; declared dependency exclusions |
| `cleanup.json` | Removal of this cell's copied auth file; no global auth/settings modification |
| `export-map.json`, `artifact-export/` | Privacy-safe derivative export with original/export hash pairs; qualification uses locked originals |
| `postflight-profile.json` | Post-call config comparison, auth-copy cleanup and original-artifact integrity |

`summarize_observations.py` produces a read-only derived view. Its totals state
usage coverage and never substitute zero for running/missing cells.
Live states now require a local PID, start-time and executable check. A missing,
zombie or reused PID with no terminal receipt is `awaiting_terminal_receipt`,
not an automatically failed outcome; unavailable probes are `unconfirmed`.
A public terminal event while its process is still present is `finalizing`.
These states request inspection, never interruption or an automatic rerun.
An explicit `transferred_to_parallel_v1` queue marker is administrative provenance,
not a skipped outcome. Its new call still requires the same process identity check.
Last resource-sample and public-event ages are reported separately: a quiet
public stream does not establish a stall. `attention_cells` exposes receipt and
harness problems. A post-call harness failure remains visible alongside the
original process outcome and reported usage. Process completion still does not
mean that independent artifact qualification has passed.
`export_observations.py --storage <declared outcome storage>` exports only finished,
hash-locked cells. Completed exports can be committed; do not stage a running
JSONL stream as a completed packet. The active same-thread heartbeat is
`opensocrates-36-cell-observer`, checking every ten minutes and continuing the
authorized verification/handoff when the matrix is terminal. `monitor-state.json`
is an explicitly mutable local coordination file, not frozen outcome evidence.

For Git handoff, follow [the portable publication procedure](PUBLICATION.md).
Some completed cells contain a large `.deps` installation cache. Its unchanged
distribution files remain in the full local export and hash inventory; the
publication manifest identifies the exact files to stage. Do not bulk-force-add
the whole export or silently remove a candidate-authored dependency modification.

## Interpretation

- A subject invocation is one fresh `codex exec` episode. It can make many backend
  requests internally. Public retry/error events are retained, but the CLI does
  not expose every private provider request. Do not equate 36 episodes with 36 HTTP
  inference requests or claim complete backend-attempt visibility.
- Before final usage arrives, usage is unknown, not zero. Cached-input and
  reasoning-output fields are subsets of input/output where reported; do not
  double count them. Missing categories stay null. Billing remains unavailable.
- Time is monotonic process elapsed time, with UTC start/end timestamps. No cutoff
  is applied. Setup duration is separate. Tool durations come from public start
  and completion events where both exist; missing starts remain unknown.
- `ps` CPU is a sampled process statistic; summed RSS can double count shared
  pages. Browser-tool resources are recorded separately. These are resource
  observations, not precise unique physical memory or energy measurements.
- Other subjects may be active while one generates artifacts. Host samples
  expose contention; generation elapsed times are descriptive, not clean
  single-tenant latency benchmarks. Independent backend performance qualification
  is separate and serial.
- Scheduling changed under explicit user authorization. Use the amendment's exact
  timestamp and per-call `scheduler_regime`; existing subjects can overlap the
  new regime. Do not pool their generation or self-load timings as if concurrency
  stayed unchanged. Observe both the original runner log and
  `/private/tmp/opensocrates-matrix-parallel-v1.log`; all 36 results remain under v2.
- Fast-off requested configuration and native feature output are available;
  independent backend service-tier/model echo is not. No fast configuration,
  alternate model, stronger helper or manual artifact repair is supplied.
- Fresh local memory/profile/process separation is tested. Account-side transfer,
  provider caching and backend isolation are not independently attested. No global
  memory is changed to manufacture proof.
- Package guidance retrieval, actual task artifacts, deterministic validation,
  primary qualitative review and claimed improvement are separate observations.
  One replicate per task/model/arm does not validate a profile or universal effect.

## Preparation failures retained

The first source downloader hit a local Python certificate-chain error; system
curl fetched the same official URLs with certificate verification enabled. The
bundled Playwright default browser revision was absent. Existing Chromium also
could not start inside the Codex shell's macOS IPC policy. A per-cell browser
tool with an independently tested filesystem sandbox solved this without opening
access to the user's profiles/history. The first batch's `/private/tmp` sibling
readability check rejected all 36 setups before a model call. `v2` uses the tested
per-user temporary layout, explicit `/tmp` read denial, complete effective-config
receipts and a stop condition for a shared setup defect. Original failed receipts
and the first freeze are unchanged. Git CSV normalization was caught and exact
frozen bytes are now preserved using scoped `.gitattributes`.

## Completed qualification and analysis

All36 episodes are terminal. The user resumed after travel. The [qualified analysis](analysis-v1/REPORT.md) and [per-cell tables](analysis-v1/TABLES.md) retain original scores, separately versioned evaluator diagnostics, actual artifact findings and usage/timing limits. No outcome model was rerun or candidate repaired. The observation phase is complete; see the report for the bounded review and remaining claim limitations.
