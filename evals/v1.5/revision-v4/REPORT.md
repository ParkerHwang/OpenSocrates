# Decision recovery and verification revision

Unpublished v1.5.0 release candidate. This revision implements fixes derived from
the completed hard-task analysis, with no subagents or new model invocations.
Historical artifacts, judgments, scores, failure counts and limitations remain
unchanged. The earlier comparison used guide 8, not this revised candidate.

## Changes and measured boundary

- Decision `prepare` supplies an opaque context handle and a draft envelope with
  null semantic placeholders, allowed values and limits. It neither selects nor
  certifies a classification. A caller must fill observed task features.
- Field diagnostics explain invalid identifiers, feature key/basis confusion and
  transport errors without returning raw values or unknown keys. The canonical
  routing validator and existing valid requests remain authoritative.
- Full validation precedes context mutation. Invalid routing or unknown methods
  can no longer erase a valid current-session read acknowledgment.
- EN/KO assistance guide 9 links a targeted verification reference and complete
  existing-schema examples. Impact guide 4 and maintainability guide 3 connect
  shared-contract changes to actual application/test callers. Reuse remains guide 2.
  The reference also covers narrative/structured-result agreement, display units
  and requested performance qualification. It is loaded when relevant, not per edit.

The actual runtime defect is distinct from the historical generated servers'
HTTP, transaction, reversal and test-caller defects. This revision does not change
those servers or claim their scores improved. Office checker coverage and provisional
review limitations remain in their original reports. No schema or SQLite layout
changes, active profile promotion, model switching or memory enrollment are added.

## Acceptance and failures

The pre-check [plan](PLAN.md) and [baseline](baseline.json) bind the scope to
`08c123a3803d7bfd1ac5e8cfb33c61d02894c98c`. Run the portable preservation and
before/after state check with `python3 evals/v1.5/revision-v4/verify.py`.

Focused checks pass: seven decision-recovery tests, the existing 27 decision
tests (including all 48 methods in both languages), and 16 EN/KO assistance
transitions. A disposable executable fixture has a working entry point but a
broken legacy test import; the required caller/test obligations stay open. Restoring
compatibility passes the same unchanged test. A separate fixture has valid numbers
but wrong memo text and a currency unit on people; those required checks stay open.
Reported repairs, missing references and unknown attribution are tested separately.
These are runtime decisions over caller reports, not automatic semantic artifact
validation. Performance-state transitions do not constitute a load benchmark.

The first recovery test run had one incorrect expectation: an uppercase unknown
method violated the pre-existing method-ID syntax before catalog lookup. The fixture
now uses a syntactically valid lowercase unknown ID; production validation was not
relaxed. Ruff also found one native-check function above the complexity limit;
the new decision checks were extracted into a focused helper. Both repairs passed
their focused reruns. No model outcome was retried.

Full source and native qualification passed at
`0e27afb048f77a1f3f521d2b13e311607f639df3` on macOS 27.0 / arm64:

- `make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check`
  — pass, including 251 installer/lifecycle tests and npx packaging.
- `make release-check` — pass on its first attempt, including frozen SQLite
  migration/backup/deletion, 130 external/embedded canonical member comparisons,
  EN/KO decision preparation/recovery and 16 native assistance transitions.
- `python3 evals/v1.5/hard-tasks/v1/verify.py --complete` — pass: 50 frozen inputs,
  all 18 attempts and 311 retained artifacts; the three timeouts remain failures.
- `.venv/bin/python evals/v1.5/revision-v4/verify.py` — pass: all 4,777 historical
  evaluation files and 47 schemas unchanged; the old-source state-loss reproducer
  changes from scope/acknowledgment loss and no diagnostic to preservation and
  an actionable diagnostic.
- `.venv/bin/python docs/v1.5.0/validate_documents.py` — pass.

The [validation receipt](validation.json) hashes runtime/package inputs and retains
both focused-check failures. The [native report](native-release.json) records the
actual gates and timing: packaged-hook p95 startup 16.083 ms and compaction
107.432 ms, both within the existing one-second margin. These are hook timings,
not model or generated-server performance measurements.

New candidate ZIP SHA-256:
`75c26eef657ddffb81be22bae407a92fd26bc9f28fcbeeb414000de90f68fc5a`.
Runtime executable SHA-256:
`6d0b1c05303eb7969a39668fed6055401f3cadf1b05510669eb20f930f6c2cd3`.
The compared guide-8 archive retains its original hash in [baseline.json](baseline.json).
Subsequent handoff edits change evidence only; the verifier binds them to qualified
runtime and check inputs. Exact pushed-commit CI is recorded in PR #95 and issue #94.

`act_standardize_decision`: adopt the verified request/state fixes and packaged
completion examples. Keep the guidance's model-quality and efficiency effects
unverified. Required checks passed, so no further unchanged testing or expanded
model study belongs to this revision.

## Claim boundary and next action

Deterministic recovery and completion checks can be verified without model calls.
Whether guide 9 improves Luna/Sol artifacts or reduces request/tool/token overhead
remains unmeasured. No shorter-text, quality, cost or performance benefit is claimed.
Model/effort/client: not invoked in this revision. Model usage and billing are null;
model calls and subagents are zero. Human scores remain unavailable.

Live Windows Codex remains unavailable; hosted native Windows tests are separate.
No destructive host test, account setting, global memory or active installation
was changed. Publication still requires separate authority. The next action is
review of the new candidate and its exact commit/CI handoff in Draft PR #95.
