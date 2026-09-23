# Development-package validation

Status: document-package validation passed on 2026-09-23. This is not product
implementation, native package, live host, or model-quality validation.

Baseline: `5a2ff3c312e92aa8a44d0905465674d9a4e4f645` (`v1.4.0`).
Scope: English development specifications, source map, synthetic contract examples,
and an implementation kickoff prompt. No product behavior is implemented here.

Location: isolated branch `docs/v1.5.0-development-spec`, based on the baseline
above. Existing source worktrees and the active installed plugin were not edited.

## Checks performed

From the repository root:

```text
python3 tools/check_links.py --root . --path docs/v1.5.0 --report /tmp/opensocrates-v150-doc-links.json
python3 docs/v1.5.0/validate_documents.py
git diff --cached --check
```

The final local link pass covers 12 Markdown documents. The custom documentation
validator parses three JSON examples, checks UUID/digest shapes and shared IDs,
separates delivery/application and reported execution states, checks 37 acceptance
case IDs, verifies local link targets and the source dispatcher anchor, and scans
for unbalanced fences, trailing whitespace, and unintended Korean/CJK prose.
This script scan is not a substitute for editorial review; the documents were
also read and reviewed in English.

External links are cited research sources, not fetched by the local link check.
Official OpenAI, SQLite, release, and research pages were read during the design
discussion. No external service was used to publish this package.

## Review corrections

An independent read-only design review identified and prompted these repairs:

1. Enrollment records actual authorization attribution and binds preview/apply to
   the exact scope/policy. A model flag is not native consent proof.
2. Export remains inside the one-JSON-response protocol, with bounded pagination.
3. Record tombstones protect identified replay while enrollment exists; full
   project deletion removes registration/tombstones and does not promise eternal
   resurrection prevention.
4. Disabled, read-only, and read-write modes have explicit operation permissions
   and a management recovery path.
5. Fixed-state paired replay isolates memory retrieval from differing first-session
   code, separately from end-to-end naturalistic comparisons.
6. The checkpoint request no longer supplies the new server-assigned version.

A source-anchor assertion initially caught an incorrect dispatcher name in the
source map (`run_cli`); it was corrected to the actual `main` function and checked
again. Checkpoint action execution state and support provenance were separated,
and evidence-pack examples now include usable locators/digests.

## Not performed and why

- Product test suite, native builds, install/purge cycles: no product implementation
  or runtime/installer change is part of this documentation task.
- Production JSON Schema validation: schemas are a W0 implementation deliverable;
  the current examples are contract illustrations only.
- Live GPT-6 or memory-quality evaluations: protocols are specified; results do not
  exist yet and must not be inferred from the documentation checks.
- Enrollment of real projects, writes to Codex memories/global settings, or active
  plugin updates: outside this task's scope.
- Issue/PR publication, merge, release, and deployment: not performed.
- Implementation dispatch: the kickoff prompt is prepared, not submitted to a new task.

The actual implementation must create its own current-commit validation record.
