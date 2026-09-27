# Orchestration qualification record

Start with [REPORT.md](REPORT.md), [validation.json](validation.json),
[verification.json](verification.json), [usage.json](usage.json), and
[export-manifest.json](export-manifest.json). The design contract is
[document 15](../../../../docs/v1.5.0/15-specialized-orchestration.md).
These are new evidence records; preceding evaluations are unchanged.

From the repository root, verify public hashes, receipt consistency, exact
candidate/delivery bytes, role identities and usage accounting without model calls.
The artifact lock additionally covers the complete public file set:

```sh
python3 -B evals/v1.5/orchestration/v1/verify.py --tracked
```

Omit `--tracked` when verifying an exported directory without its Git repository.
The tracked check reads every locked file from HEAD; local presence alone is insufficient.

This offline command does not rerun generated Python or claim a new execution
result. Actual native check receipts and the independently attributed audits are
preserved. Source-level regression execution is `make orchestration-check`;
complete source/native gates and their exact commit are in validation.json.

`replay.py` prepares a new request from a selected frozen synthetic episode.
It requires an explicit supported package/client/Python executable and a new
output directory. It fails rather than overwrite any old result. The default
creates only the manifest/request and does not call a model:

```sh
python3 -B evals/v1.5/orchestration/v1/replay.py \
  --workflow software \
  --package /absolute/path/to/disposable/codex-package \
  --client /absolute/path/to/qualified/codex-client \
  --python /absolute/path/to/python3.12 \
  --output /absolute/path/to/new-replay-directory
```

Use `office`, `continuation` or `repair` for the other scoped episodes. Adding
`--run` with another new directory explicitly consumes the caller's Codex usage.
It keeps `gpt-6-astra` / `max`, repair limits and executable check arrays; it has no
model timeout, external retry or alternate model. Use an existing authenticated
supported client; do not provision credentials or reset account credits for this
record. A replay with a different source/package identity is a new observation,
not a replacement for the original results. Only the approved checker arrays run,
through the product's qualified read-only sandbox.

`fixture/` contains the independent fixed inputs/oracles and original freeze.
Some frozen builder/self-test script bytes are represented only by their original
hashes; the copied synthetic fixture/oracle bytes remain exact. `oracles/` retains
both the original and corrected documentation-only check. `audit-harnesses/`
contains path-normalized source used during this run for inspection; it is not a
portable command suite. Current source tests and the explicit replay entry point
are the maintained execution paths.

`independent/` preserves positive and unfavorable deterministic/native reports,
including their original source-version qualifications. Reports using fake role
adapters are not live model results. Full synthetic adapter assignments, temporary
memory databases, raw shell logs and model JSONL are not exported. Original SHA
fields inside path-normalized JSON refer to original bytes; public integrity uses
`exported_sha256` in the export manifest. Exact artifact bytes and failure statuses
are not normalized or repaired.

The source candidate is unpublished. Draft PR #95 is the durable final handoff for
its pushed commit and hosted CI. A maintainer can review it without this machine
or chat; release and active-install actions require separate authorization.
