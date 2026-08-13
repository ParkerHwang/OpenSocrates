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
