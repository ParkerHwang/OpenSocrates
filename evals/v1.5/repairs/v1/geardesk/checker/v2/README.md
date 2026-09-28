# Checker revision v2

Integrator-authored evaluation repair, not new unassisted model outcomes. Original
protocol, manifests, applications and historical scores remain untouched.

`checks.py` is the original public-adapter suite with explicit historical recursive
field equivalence, only additive `lateFeePerUnitDay: 0` allowed, retained audit-prefix
checks, and separate main/migration dependency groups. Main-store failure still
suppresses cumulative expected totals; separate migration failure does not.

`supplement.py` creates a fresh owned store for every date/batch/mixed scenario.
Absent/null/invalid partial dates must reject with byte-identical disk; full return
retains the omitted date default. Both adapters exercise invalid batch positions
first/middle/last. `domain-probes.mjs` tests exported APIs for direct dates, rejected
batch input ownership, detached new/replay results, and earlier batch snapshots.
Result aliasing concerns returned ownership, not a claim of impurity.

Historical ambiguous v1.4 stage2 mixed deposits must explicitly reject partial
refund and retain full aggregate return. Known v1.5 stage2 quote lines retain
5000/1000 facts. v1.4 native new bookings retain their accepted per-line values.
Both are checked against changed current catalog. No historical allocation is synthesized. v1.5 is not
required to import the foreign v1.4 aggregate-only schema, which is outside its
original storage format. Foreign v1.5 idempotency records are not imported into v1.4. The earlier v1
checker included that unsupported cross-format test; its source and outcomes are
preserved as superseded measurement evidence, not scored application defects.

Usage (paths may be absolute):

```sh
python3 repairs/v1/checker/v2/controls.py
python3 repairs/v1/checker/v2/checks.py --project apps/v1.4.0 --stage 3 --legacy-store evidence/v1.4.0/stage2/legacy-v1-store.json --output repairs/v1/checker-evidence/original-v1.4-main.json
python3 repairs/v1/checker/v2/supplement.py --project apps/v1.4.0 --arm v1.4.0 --baseline . --output repairs/v1/checker-evidence/original-v1.4-supplement.json
```

For derivatives change only `--project` and use distinct output files. Existing
outputs are refused. Source hashes are frozen before candidate derivative runs;
controls are predicate negative/positive tests, while original application runs
also demonstrate actual defect sensitivity. No provisional model judgments are
collected. The unawaited assertion is not graded as a demonstrated false-green;
the original Node observation remains separately in review evidence. Clone count
is outside correctness scoring and does not imply a throughput speedup.
