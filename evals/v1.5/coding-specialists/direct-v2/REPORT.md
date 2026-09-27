# Direct specialist prompt comparison

Eight gpt-6-luna/max calls completed naturally: six initial code-change episodes
and two same-arm follow-ups. This is complete prompt-delivered evidence, separate
from installed-package routing. One exact-tuple access probe is recorded separately
in revision-v1. No helper agents, stronger-model answers, generation deadlines or
integrator repairs were supplied to the subjects.

Inputs were committed before outcomes at `a014c57e0008d3618dfe30af89fb89c9e85fee6e`.
The manifest is `bac6bf212ae255d9eb5d8ab5042218ddd761cf0ce968b48ddb4daa492315d288`.
The unexecuted direct-v1 boundary is retained: its pre-call import-alias oracle
assumption was removed before this version's calls. Both arms receive the same
new tasks, source, facts, tools, permissions and decision point. Current support
uses the complete relevant existing coding guide and result-verification guide;
specialist support uses its complete v0.1.1 procedure. Length and content differences
are actual treatment costs, not normalized away. No published worked answers or
prior failed program repairs are outcome input.

## Observable outcomes

| Task | Current guide | Specialist | Own suite | Interpretation |
| --- | ---: | ---: | --- | --- |
| QuotaDesk contracts | 10/10 | 10/10 | Both pass | Correctness tie on the frozen checks |
| ParcelSeal transitions | 10/10 | 10/10 | Both pass | Correctness tie on the supplied synthetic transport |
| BatchFlow ownership | 10/10 | 9/10 | Both pass | Specialist trusts normalized producer output; faulty-producer injection is accepted |
| BatchFlow scaling follow-up | 13/14 | 13/14 | Both pass | Original check rejects an unspecified exception type; separate diagnostic below |

Protected existing tests/provider/old-producer bytes remain unchanged in all eight
artifacts. Frozen functional group counts are not weighted quality scores, and
own-suite passes do not close independent failures. No original score is rewritten.

The initial ownership specialist does not re-normalize the result of `describe`
inside `create`: the real producer already normalizes and returns an owned result.
The frozen negative check replaces that producer with malformed output containing
boolean workers. The specialist serializes it; the current-guide arm rejects it.
This establishes a scoped robustness difference under producer fault injection.
It does not establish that the normal public registry accepts invalid workers.

The two follow-up failures are more nuanced. The fixture omitted `options` and
the checker accepted only ValueError/TypeError, although the task did not prescribe
that exception class. Both programs reject with KeyError before writing. The
[separately frozen diagnostic](diagnostics/ownership-boundary-v1.manifest.json)
checks state after rejection without changing the original scores. Its
[observations](diagnostics/ownership-boundary-v1.results.json) show:

- Every initial/follow-up real public `put` rejects boolean workers and preserves
  persistent state.
- Both follow-ups reject the original missing-options producer fault atomically;
  the original exception-type scoring assumption is a rubric limitation.
- With an `options` field supplied, both follow-ups multiply True by factor before
  normalizing, making it integer 1 and accepting the faulty producer result. This
  is a separate observed defensive-boundary gap, not a reason to retrofit scores
  or claim general caller failure.
- Existing valid retained runs remain unchanged in every diagnostic probe.

## Source choices and work

Both contract artifacts keep the new strict edit semantics separate from the
legacy coercing importer, reuse the Store's public result/copy boundary and catch
only PolicyError in the API adapter. The current-guide arm additionally puts an
RLock around Store operations; concurrency was not required by this fixture. That
is a scope/complexity observation, not a universal maintainability ranking.

Both transition artifacts persist identity before sending and reconcile unknown
outcomes instead of treating timeout as rollback. The current-guide artifact uses
process-local per-identity locks with transport calls outside write transactions;
the specialist uses a shared database lock and a write transaction around the
lookup/send/outcome phase after separately committing pending state. Both pass the
declared thread-level cases. Their concurrency/performance tradeoffs are not measured
by this task; real provider and physical-crash guarantees remain unverified.

Both ownership artifacts retain live monitors, isolate nested JSON values, preserve
historical source revision as unknown when absent, and publish retained manifests
without overwriting IDs. The follow-ups keep the existing consumers and add scaling
coverage. Differences in defensive normalization are described above. No file count,
method name or self-reported use is used as a quality score.

| Episode | Current seconds / tools / uncached input | Specialist seconds / tools / uncached input |
| --- | --- | --- |
| Contracts | 304.889 / 15 / 50,001 | 372.440 / 12 / 47,179 |
| Transitions | 636.275 / 17 / 40,659 | 611.196 / 22 / 65,703 |
| Ownership initial | 414.590 / 21 / 58,874 | 313.639 / 9 / 49,700 |
| Ownership follow-up | 193.066 / 8 / 60,448 | 338.658 / 7 / 25,782 |

Efficiency is mixed. Fewer actions or input tokens do not necessarily mean less
wall time, preserved robustness or lower billing. These are single paired episodes
on a shared host with concurrent subject pairs and some independent preparation
work. They are not isolated latency or repeated model samples.

All 38 public messages and the eight final source artifacts were inspected. No
unnecessary user question or external execution was observed. Public final reports
generally preserve the tested versus unverified boundary. Four failed tool actions
are retained: one unsuccessful file search, two transition self-test failures, and
one follow-up self-test failure. The same outcome model repaired its own work/tests
within its original call; no outside evaluator feedback was supplied. Final own
suites pass. These actions are included in the 111 total tool actions.

## Usage and interpretation

All eight calls report usage: 2,314,250 input tokens including 1,915,904 cached;
130,514 output tokens including 88,015 reasoning-output tokens; cache-write is
explicitly zero. Cached input and reasoning output are subsets, not extra totals.
No direct call has missing usage, but human scores, independent backend echo,
billed cost and primary preparation/review usage remain null. Requested client:
`codex-cli 0.158.0-alpha.2`; launcher/actual executable and account fingerprints are
bound in the manifest and verified before calls. Account-side memory isolation
remains unproven. No program performance benchmark is claimed.

`act_standardize_decision`: this pilot does not establish a general coding-quality
or efficiency gain. Preserve the complete specialist files as a provisional,
optional route for unresolved decisions benefiting from additional structure;
retain ordinary work/current guides when sufficient and keep profiles unpromoted.
The product integration must independently demonstrate usable selection/delivery.
Do not expand this pilot or repair its generated programs to manufacture a win.

## Inspect and replay

[summary.json](summary.json) contains every row and usage category. `evidence/`
contains public messages, tool receipts, protected-input identities, original
snapshot locks, code and qualifications. [export-map.json](export-map.json) binds
124 public files to their immutable local originals. Only the interpreter path
inside each of eight TOOLING.md environment notes is redacted; business source
bytes are unchanged. Original local results remain in the authorized evaluation
boundary and are excluded from Git. Original snapshot hashes are not rewritten
to pretend the redacted environment note was the original.

The standalone frozen checker can replay the public source without account access:

```sh
python checker.py contracts evidence/contracts-current/snapshot
python checker.py transitions evidence/transitions-specialist/snapshot
python checker.py ownership evidence/ownership-specialist/snapshot
python checker.py ownership evidence/ownership-followup-current/snapshot --followup
```

Expected nonzero exits preserve the reported failures. Use Python 3.12 with its
standard library and inspect `qualification.json` for the actual historical runs.
This report is provisional primary-agent interpretation, not blinded human review.
