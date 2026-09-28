# Guide8 / guide9 retest metrics

All12 actual calls are retained:9 complete CLI turns,1 provider-capacity failure,
and2 administratively interrupted calls. The6 later calls have no model wall-clock
deadline and all complete naturally. Six original slots were not called:2 Sol
office slots after capacity blockage and4 transferred before-call setups.

These are one-episode practical observations. Treat the two Max coding continuations
separately from fresh episodes. Earlier vanilla/released1.4 results are historical
references only. See [the combined report](REPORT.md) and [amendment](amendment.json).

## Every actual invocation

| Boundary / case | Package | CLI outcome | Wall seconds | Tools / failed / unfinished | Input / cached subset | Uncached input | Output / reasoning subset |
| --- | --- | --- | ---: | --- | --- | ---: | --- |
| retest-v1 / coding-sol-medium-a | guide8 | complete | 592.167 | 44 / 4 / 0 | 1,720,875 / 1,646,208 | 74,667 | 24,808 / 6,385 |
| retest-v1 / coding-sol-medium-b | guide9 | capacity failure | 369.297 | 30 / 2 / 0 | null / null | null | null / null |
| retest-v1 / office-luna-medium-a | guide9 | complete | 318.846 | 21 / 7 / 0 | 777,892 / 701,184 | 76,708 | 14,679 / 1,812 |
| retest-v1 / office-luna-medium-b | guide8 | complete | 416.270 | 27 / 5 / 0 | 492,374 / 426,240 | 66,134 | 14,529 / 3,900 |
| retest-v1 / coding-luna-max-a | guide8 | administrative interruption | 1514.755 | 70 / 3 / 4 | null / null | null | null / null |
| retest-v1 / coding-luna-max-b | guide9 | administrative interruption | 1514.764 | 42 / 2 / 0 | null / null | null | null / null |
| unlimited-v1 / coding-luna-max-a | guide8 | complete | 1252.581 | 59 / 3 / 0 | 3,117,380 / 2,957,824 | 159,556 | 64,823 / 40,363 |
| unlimited-v1 / coding-luna-max-b | guide9 | complete | 1238.830 | 93 / 7 / 0 | 6,679,648 / 6,406,400 | 273,248 | 53,367 / 32,089 |
| unlimited-v1 / coding-luna-medium-a | guide8 | complete | 383.155 | 46 / 6 / 0 | 1,263,922 / 1,182,720 | 81,202 | 16,647 / 2,356 |
| unlimited-v1 / coding-luna-medium-b | guide9 | complete | 600.977 | 61 / 8 / 0 | 2,562,916 / 2,448,128 | 114,788 | 26,393 / 5,892 |
| unlimited-v1 / office-luna-max-a | guide8 | complete | 2313.361 | 60 / 6 / 0 | 6,586,774 / 6,357,248 | 229,526 | 114,850 / 71,567 |
| unlimited-v1 / office-luna-max-b | guide9 | complete | 1148.786 | 33 / 8 / 0 | 1,680,058 / 1,551,104 | 128,954 | 57,390 / 37,868 |

Cache-write tokens are explicitly0 in9 complete reports and null in3 interrupted/failed
reports. Cached input is a subset of input; reasoning output is a subset of output.
Do not add subset categories again. Summed input24,881,839 includes23,677,056 cached;
output387,486 includes202,232 reasoning. Missing usage is not zero. Billing and primary
integration/review usage are unavailable. The interrupted wall times include the
357-second supervisor pause and are not model reasoning or comparable service time.

## Final retained coding artifacts

| Tuple | Guide8 API / own suite | Guide9 API / own suite | Episode limitation |
| --- | --- | --- | --- |
| Sol medium |28/28 / pass|28/28 / pass|Guide9 CLI ended with provider capacity failure|
| Luna medium |23/28 / pass|25/28 / pass|Fresh deadline-free episodes|
| Luna max |27/28 / pass|28/28 / pass|Own-source continuations after administrative interruption|

The interrupted intermediate Max guide9 source fails to build at `history.go:168`
(one assignment target for the two-value ExecContext return). Its continuation
repairs that issue independently. The old snapshot/score is retained, not replaced.

## Office artifacts and separate primary semantic review

| Tuple | Guide8 objective / provisional prose | Guide9 objective / provisional prose | Material findings |
| --- | --- | --- | --- |
| Luna medium |26/27 /14/20|27/27 /16/20|Guide8 omits P072; guide9 preserves the row but reverses H02/H03 in its memo|
| Luna max |27/27 /20/20|27/27 /20/20|No new material memo discrepancy found in the scoped source review|
| Sol medium |not called / null|not called / null|Capacity stop; no fabricated score|

All4 actual workbooks pass the separately frozen count/currency-format diagnostic.
Prose scores are unblinded primary-model assessments, not human scores. The medium
guide9 reopening-condition limitation was added in a separate semantic supplement
without rewriting its first rating. All public messages were reviewed.

## Serial server performance

Concurrency16 medians of3 repetitions; the full JSON retains concurrency1 and16,
ranges, sampled resources and every failure. Diagnostic rows cannot establish a
qualified performance win. All661,186 requests across72 cells are retained.

| Tuple / package | Eligibility | Read RPS | Read p99 ms | Write RPS | Write p99 ms | All-window failures |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| gpt-6-sol / medium / guide8 | eligible artifact | 786.4 | 52.46 | 4760.8 | 23.44 | 0 |
| gpt-6-sol / medium / guide9 | eligible artifact | 328.6 | 65.40 | 1560.4 | 179.17 | 0 |
| gpt-6-luna / max / guide8 | diagnostic | 617.4 | 61.50 | 2540.4 | 103.59 | 0 |
| gpt-6-luna / max / guide9 | diagnostic | 375.4 | 98.02 | 1326.6 | 229.24 | 2 |
| gpt-6-luna / medium / guide8 | diagnostic | 386.2 | 109.72 | 3948.2 | 34.63 | 0 |
| gpt-6-luna / medium / guide9 | diagnostic | 339.6 | 119.05 | 3938.6 | 35.45 | 0 |

The2 failures occur in the Max guide9 concurrency16 write warmup. Measured-start
cohorts have0 failures, but warmup failures remain in the gate, so this artifact’s
performance is diagnostic despite28/28 functional groups. All other diagnostic
artifacts fail a functional gate. Only the two Sol artifacts qualify.

Same Mac host, GOMAXPROCS4, fixed10,002-entry seed,1-second warmup and5-second
measurement. Root functional qualification overlapped part of the final office
generation; invocation times are descriptive. All model calls and builds ended
before the serial meter. Fixed sampling windows are not model wall-clock cutoffs.
