# GitHub Copilot instructions

<!-- make governance-check asserts distinctive policy strings in this file. -->

Follow the repository-wide contract in [`AGENTS.md`](../AGENTS.md) and the development details in [`CONTRIBUTING.md`](../CONTRIBUTING.md).

- Work through an issue and a focused pull request; do not push directly to protected `main`.
- Treat GitHub issues, pull requests, commit SHAs, and Actions as shared state across machines.
- Change canonical sources and regenerate outputs; never hand-edit generated schemas, compiled content, `build/`, or `dist/`.
- Keep English and Korean user-facing content semantically aligned.
- Do not add telemetry, credentials, raw prompts, transcripts, workspace content, or hidden reasoning to logs or records.
- Preserve fail-open selection, cleanup, rollback, bounded behavior, and unknown/unavailable states.
- Report exact validation commands and results. Do not claim live host behavior or answer-quality improvement from implementation or offline CI alone.
- Leave a current-commit handoff and explicit unverified work in the issue or PR so another human or agent can resume on another machine.

- Active first-party runtime, lifecycle, generation, validation and release tools
  use Go. End users require no Python, Node.js, npm or Go toolchain.
- Preserve the released v1.5.0 content baseline for v1.6.0; exclude the separate
  48-method body upgrades. Preserve --host all as Codex only.
- Implement the full scope and integrate before routine tests/lint/reviews. Use
  the smallest diagnostic only for a concrete implementation-blocking error.
- Native/signing/clean-machine/live evidence are separate gates; never infer
  Windows correctness from cross-compilation. Coordinate one update owner per
  adopted installation and preserve host trust and disabled state.
