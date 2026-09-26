# Expanded v1.5 engineering pilot

This directory is a new, versioned pilot condition. It does not replace or pool
the earlier prompt-proxy, installed, pre-repair, or revised-guide results. Package
metadata is still 1.4.0; the implementation is a Draft candidate.

- [Baseline audit](AUDIT.md) and [baseline consistency receipt](baseline-audit.v2.json)
- [Authorship and review independence](AUTHORSHIP.md)
- [Independent task manifest](fixtures.v2.json), [hidden checker](checks_v2.py),
  and [fixed judge procedure](JUDGE_PROCEDURE.v2.md)
- [Exact-client access freeze](access-freeze.v2.json) and
  [completed access probes](access-results/summary.json)
- [Outcome execution freeze](execution-freeze.v2.json) at `9dd94c6`, including
  every scheduled arm, two repetitions, client/package/guide/schema hashes,
  permissions, wall budget, missingness, and repair policy
- [Separate H02 fixture](host-fixture.v2.json), authored by the integrator for
  delivery acceptance rather than independent quality measurement
- [Completed v2 results](summary.v2.json), [blinded artifacts](blinded-v2/), and
  [separate guide-3 diagnostic freeze](diagnostic-freeze.v3.json)
- [Decision-ready results](RESULTS.md), [all diagnostic attempts](diagnostic-summary.json),
  and [guide-4 validation](validation-receipt.guide4.json)
- [Completed provisional Astra review](reviews/astra-xhigh-v4/REPORT.md): 60 packets,
  immutable first-pass and evidence-phase ratings, complete attempt/usage ledger,
  integrator disagreements and held-out readiness limits. Human scores remain null.

The nine independent tasks span coding, general planning, mechanical work,
authored fresh-session replay, and English/Korean developer/nondeveloper
collaboration. EVAL-01 is a paired C/D replay from the same author-written first
artifact. It is not an additional naturalistic four-arm study. EVAL-04 includes
disabled-memory, enrolled-memory, and maintained-note controls. Note preparation
and memory setup are counted separately from model time; human note-authoring
burden is unavailable. All memory effects are labelled confounded because local
profile controls do not prove account-side isolation.

The installed ablation and wrapper conditions share the same package, method
access, memory, source, tools, effort, and disabled hooks. Only the separately
declared optional wrapper varies. This does not validate the candidate model
profiles or turn the mechanical fixture into general efficiency evidence.
Luna-only cells disable subagents and receive no stronger-model answer or repair.

Run read-only checks without authentication:

```sh
python3 evals/v1.5/verify_pilot_results.py
python3 evals/v1.5/expanded/verify_baseline_v2.py
python3 evals/v1.5/expanded/harness_v3.py
python3 evals/v1.5/expanded/checks_v2.py
python3 evals/v1.5/expanded/report_v2.py
python3 evals/v1.5/expanded/report_diagnostics.py
```

Live execution requires the exact frozen client/package and the operator's
existing authenticated account. The executable runner verifies committed hashes
before calls and refuses to overwrite a started cell. It can resume **unstarted**
cells only. A failed outcome is never silently retried or replaced. A changed
task, scorer, guide, package, or harness requires a new versioned freeze before
new calls. The existing runs cannot be reproduced by silently substituting a
newer client, archive, or model.

`report_v2.py` verifies saved results offline without requiring the old client,
package archive, account, or a private transcript. Live execution retains its
strict current-client/package checks. `report_v2.py --write` finalizes every scheduled result, an immutable result
inventory, blinded artifact packets, separate post-first-read judge evidence, and
an unblinding map. Keep the unblinding map and result summaries away from assessors
until their scores are locked. Packets contain synthetic public artifacts and
messages only; they may retain non-blindable condition cues, which the judge must
record. No human review is implied by packet generation. Do not recruit or message
a reviewer without authorization. V2 retained only the final public message of
each turn, so earlier questions cannot be reconstructed from those packets. The
separate v3 dialogue diagnostic retains every public agent message and redacted
synthetic command templates; it does not include hidden reasoning. Keep its
condition and results separate from v2.
