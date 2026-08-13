# Claude Code instructions

<!-- make governance-check asserts distinctive policy strings in this file. -->

These instructions govern repository development only. OpenSocrates selector subprocesses use host safe mode and do not load project `CLAUDE.md`; this file does not change packaged selector behavior.

Read and follow [`AGENTS.md`](AGENTS.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md) before making changes. They are the shared cross-agent and human workflow contract.

Claude-specific requirements:

- Reconcile the active issue, pull request, branch, and latest commit on GitHub before resuming prior work.
- Do not rely on conversation history as project state; leave a durable handoff in the issue or PR.
- Use a focused branch and Draft PR. Never push directly to protected `main`.
- Never claim a check or host probe passed unless it was run against the reported commit.
- Keep evidence levels and privacy boundaries explicit. Do not infer live host delivery or answer-quality improvement from implementation or offline tests.
- Treat `content/methods/`, `schemas/source/`, and host templates as canonical sources; regenerate outputs rather than hand-editing generated files.
- Preserve English/Korean semantic alignment and the no-telemetry, no-raw-prompt-retention, fail-open, cleanup, and transactional rollback contracts.
