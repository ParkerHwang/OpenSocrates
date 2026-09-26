# Office hard fixture v1 — author/reviewer materials

Candidate-visible material is **only TASK.md and inputs/**. Keep oracle.json,
source generators, check.py, selfcheck.py, PROSE_RUBRIC.md and this README outside
the outcome sandbox. The oracle includes one example assignment for checker
selfchecks; it is not a candidate answer and must never be supplied to a model.
This directory is wholly synthetic and contains no credentials or real staff.

## Scope and oracle

263 tabular input rows: 72 roster + 72 availability + 12 HR changes + 57 invoice
records + 17 credit records + 27 payment records + 6 session options. Twelve
input files include the prior maintained operations note, later approved HR/
accounting changes, final supplier quotation and explicit domain rules. The
assignment involves record revisions, physical duplicates, valid zero amounts,
reversed transfers, authority distinctions, historical cash reserves, competing
vendor prices, access/availability/capacity and working-day preparation.

Exact accounting totals: gross 881,200, credits 6,600, paid 87,000, outstanding
787,600 KRW. Approved total cash cap 1,752,600 leaves 965,000 for the new launch.
A feasible optimum uses CEDAR and S2/S3/S5/S6, assigning all 60 mandatory and any
feasible 6 optional attendees at 962,000, leaving 3,000. Preparation days are
October 1, 2 and 5 before the first session on October 6. The task explicitly
accepts alternative valid allocations; it imposes no hidden optional priority.

The independent arithmetic lower bound is useful for review: every legal set of
four rooms costs at least 260,000. At 67 attendees, even the cheapest approved
vendor has a cost of 969,000, above the launch cap. The flow search demonstrates
66 feasible. oracle_generator.py enumerates every approved vendor/four-session
combination and calculates max attendance through augmenting paths, prioritizing
mandatory coverage before optional additions. No prose or model output enters
that computation.

## Validation

`python3 oracle_generator.py` regenerates oracle.json from inputs. The existing
12_domain_rules.md is an authored static rule source; generate_fixture.py
regenerates the other 11 synthetic inputs. Do not silently regenerate a frozen
fixture after outcome calls. Any deliberate data/rule revision requires renewed
selfchecks and a new freeze/hash.

Run selfchecks with the read-only bundled interpreter (openpyxl 3.1.5):

```sh
/Users/parkerhwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 selfcheck.py
```

check.py itself uses only Python stdlib including ZIP/XML, so it can run with an
ordinary Python 3 interpreter:

```sh
python3 check.py /absolute/path/to/outcome --report /absolute/path/to/report.json
```

There are 27 grouped checks: accounting 9, planning 9, lineage 4, artifact
consistency/presence 5. Each check has a stable ID and reports failures; score is
the percentage of passed checks, with group counts reported separately. Missing
mandatory files or unreadable XLSX/JSON/CSV means `unassessable`, null score and
no fabricated passed checks. An assessed run with incorrect values can score
partially, but `all_objective_checks_pass` is false. Unsupported uncached formulas
make the run unassessable with a null score and a specific formula error; correct static
values and the explicitly supported common formulas are accepted equally. Uncached
COUNTIF/SUMIF support literal equality only, without comparator/wildcard criteria;
ROUND uses decimal half-away-from-zero behavior for positive and negative ties.
Double-quoted Excel strings are lexically preserved before reference substitution.

Selfchecks include 15 lexical/rounding controls (A1-like quoted IDs, escaped
quotes, quoted and unquoted Korean sheet references, positive/negative ROUND
ties), explicit unsupported comparator/wildcard unassessable controls, correct
static and uncached formula workbooks, an equivalent
alternative allocation, duplicate accounting, removed active zero-value evidence,
wrong approval, missing evidence, arithmetic error, wrong preparation dates,
access failure, stale HR attributes, duplicate output identity, a workbook-only
mismatch, missing artifact and corrupt workbook. selfcheck_results.json records
the local run; it does not establish outcome-model success or actual operational
execution. The reference memo in selfchecks is structural filler and is not
prose quality evidence. Use the frozen PROSE_RUBRIC.md for the primary review
without a separate model judge panel.

Current author baseline: 8244c97, isolated author checkout. No outcome calls,
commits, pushes, external messages or operational actions were performed.
Fixture difficulty and comparative treatment performance remain unverified until
the primary integrates, freezes, executes and reviews the actual outcomes.
