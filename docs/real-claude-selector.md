# Opt-in real Claude selector contract

Issue #7 adds a deliberately separate integration check for the selector's
real Claude Code subprocess boundary. It is not part of the ordinary offline
suite and never falls back to an API key.

Run it only with a dedicated, authenticated Claude Code profile:

```bash
OPENSOCRATES_REAL_CLAUDE=1 make real-claude-check
```

The check requires Claude Code 2.1.205 or later and an existing successful
`claude auth status`. It validates the exact safe-mode, no-persistence,
structured-output, tool/MCP blocking, non-interactive permission, one-turn,
fixed-effort, environment allowlist, and temporary-workspace contract. One
non-sensitive prompt is sent only after authentication succeeds. Separate real
subprocess probes verify the fixed `nonzero_exit`, `timeout`, and
`invalid_output` diagnostics.

The report at `build/evidence/real-claude-selector.json` is owner-only and
contains only the CLI version, booleans, categorical outcomes, and an optional
blocker. It never contains the prompt, catalog, transcript, stdout, stderr,
credentials, environment values, or selector reasoning.

## Current evidence

On 2026-08-11 the installed Claude Code 2.1.226 executable passed the command,
environment, workspace, and real subprocess failure contracts. The live model
case was not run because `claude auth status` returned `loggedIn: false`. The
categorical blocker is `claude_not_authenticated`; this is not success evidence
and no structured-output reliability claim follows from it.

Claude Code documents the relevant safe-mode and non-interactive flags in its
[CLI reference](https://code.claude.com/docs/en/cli-reference). Managed policy
still belongs to the host trust boundary, as described in `SECURITY.md`.
