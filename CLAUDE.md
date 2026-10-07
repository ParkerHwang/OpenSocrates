# Claude Code instructions

<!-- make governance-check asserts distinctive policy strings in this file. -->

These instructions govern repository development. The unpublished v1.5 Mac
stage implements a native Claude Code companion and a separate content-only
account skill while preserving the released Codex baseline. This contributor
file is not the installed product controller. See [the Mac guide](docs/macos-v1.5.md)
for current behavior, local installation, and pending live qualification.

Read and follow [`AGENTS.md`](AGENTS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) before making changes. They are the shared cross-agent and human workflow contract.

Claude-specific requirements:

- Reconcile the active issue, pull request, branch, and latest commit on GitHub before resuming prior work.
- Do not rely on conversation history as project state; leave a durable handoff in the issue or PR.
- Use a focused branch and Draft PR. Never push directly to protected `main`.
- Never claim a check or host probe passed unless it was run against the reported commit.
- Keep evidence levels and privacy boundaries explicit. Do not infer live host delivery or answer-quality improvement from implementation or offline tests.
- Treat `content/methods/`, `schemas/source/`, and host templates as canonical sources; regenerate outputs rather than hand-editing generated files.
- Preserve English/Korean semantic alignment and the no-telemetry, no-raw-prompt-retention, fail-open, cleanup, and transactional rollback contracts.
- Keep native Claude payload/response normalization separate from Codex. Entry
  must not copy credentials, read private transcripts, initialize a database,
  or demand an unavailable native application receipt.
- Treat account skill matching, native CLI/Desktop delivery, and Antigravity
  workspace/global loading as separate evidence cells. Preserve existing account
  skills and unrelated host settings during any authorized migration.
- Do not import the withdrawn v1.5 coding/memory/orchestration candidate. Original
  48-method contracts remain intact; dedicated coding specialists are excluded.
