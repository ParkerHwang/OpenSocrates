# Candidate project memory protocol

This document describes the v1.5 implementation branch. The released 1.4.0
installer does not provide these commands. Do not enroll a real project or
change the active plugin installation to run the source fixtures.

The explicit native command is `python -m opensocrates memory` from source,
`bin/launch.sh memory codex` in a macOS package, or
`node bin/launch.mjs memory codex` on Windows. Each invocation accepts one
strict UTF-8 JSON request of at most 256 KiB on stdin and emits one JSON
response. Exit 0 means a well-formed response, including `disabled`,
`partial`, or `conflict`; inspect `status`. Invalid requests exit 2 and
operational unavailability exits 3.

## Enrollment

`init` with `apply: false` previews the canonical root, workspace kind,
private storage policy, exclusions, retention, management operations, and
disclosure digest without creating a store. An authorized `init` with
`apply: true`, the matching digest, and attributed authorization creates an
opaque project/workspace identity. Apply also requires an idempotency key.
The digest binds the technical disclosure;
it does not prove consent. A project starts in the selected `read_only` or
`read_write` mode. Separate explicit policy updates use the current policy
version and a newly matching disclosure. `status` never creates storage.

Only enrolled `read_write` projects may save public proposals, attributed
acceptance, metadata observations, and task checkpoints. `recall` checks the
registered workspace and source footprint before returning a bounded pack.
The pack marks stale or unknown evidence, omitted scope, delivery, and
unverified application. A checkpoint does not prove that a planned side
effect happened. Current source governs implemented behavior; accepted intent
remains scoped and attributed.

The SQLite store lives in the private product data root under
`projects/<project UUID>/memory.sqlite3`. The private registry contains
absolute root bindings; public exports do not. No database goes into the
source directory. Metadata may include relative paths, hashes, inventory
coverage, and Python import/definition names. Source bytes are read
transiently but not retained. Raw prompts, transcripts, tool-output dumps,
source copies, credentials, screenshots, and hidden reasoning are forbidden.
The stateless `assistance` and existing `decision` commands do not initialize
this store.

Use `inspect` and paginated `export` to review stored public records. A
`disable` transition stops automatic recall/capture while preserving
management access. `delete` can remove an exact record or an exact project;
unknown owned-directory files block complete project deletion. `prune`
defaults to a dry-run request and preserves accepted decisions. Installer
`remove --purge` preserves enrolled memory by default; the explicit
`--delete-project-memory PROJECT_UUID --memory-policy-version VERSION`
choice delegates one project deletion to the installed memory command.

The source fixtures use disposable directories only:

```sh
PYTHONPATH=src uv run --locked --no-sync python tools/check_project_memory.py
PYTHONPATH=src uv run --locked --no-sync python tools/check_memory_sources.py
```

These tests verify specific contracts. Native Windows ownership/reparse
behavior, live Codex use, and task-quality improvement require separate
evidence under [the v1.5 evaluation plan](v1.5.0/06-verification-and-evaluation.md).
