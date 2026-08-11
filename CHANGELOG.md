# Changelog

All notable changes to OpenSocrates are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Sanitized Claude Code payload receipts for the complete v1.1.2 hook
  lifecycle — `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `Stop`, and
  `SessionEnd` — captured from a supported runtime and compared field by field
  with the shared adapter mapping. The checks assert that `prompt_id` is
  projected into turn identity, that `last_assistant_message` reaches the Stop
  decision, that two consecutive turns of one session stay artifact-isolated,
  and that Stop and `SessionEnd` clean up
  ([#9](https://github.com/ParkerHwang/OpenSocrates/issues/9)).

### Fixed

- Claude sessions now supersede private instruction artifacts by `prompt_id`.
  When `Stop` is absent, the next `UserPromptSubmit` removes prior turn trees in
  that session while preserving the new active turn; `SessionEnd` and the
  24-hour `SessionStart` sweep remain backstops
  ([#13](https://github.com/ParkerHwang/OpenSocrates/issues/13)).
- The Claude selector now enforces its 512 KiB stdout ceiling while reading the
  child process stream. Output that crosses the limit terminates and reaps the
  process immediately, fails open with a content-free diagnostic, and is never
  retained or logged ([#10](https://github.com/ParkerHwang/OpenSocrates/issues/10)).
- An ordinary Claude payload no longer reports an unknown field. `effort` was
  present in the captured `PostToolUse` and `Stop` receipts, while
  `background_tasks` and `session_crons` were present in the captured `Stop`
  receipt. They were missing from the parser's known-field sets, so the
  `native_unknown_field_ignored` diagnostic fired on healthy turns. The parser
  still never reads those fields, and no parsing, projection, or gating
  behavior changed.

### Security and privacy

- The committed receipts contain no prompt, transcript, path, credential, or
  user-identifying content. Field names, value types, and container shapes are
  preserved as captured; every sensitive value is a fixed synthetic marker, and
  a check refuses every native-payload string outside a closed vocabulary so a
  future re-capture cannot commit real payload content by accident.

## [1.1.2] - 2026-08-11

### Added

- A Claude `PostToolUse` grounding receipt that is created only after a
  successful `Read` starts at the first line, reaches the instruction
  artifact's terminal marker, and targets the current turn's exact file.
- One bounded `Stop` repair pass when Claude attempts to finish without a
  verified read receipt or the exact public method/revision audit line.

### Fixed

- Selected reasoning methods can no longer silently pass the Claude completion
  gate when the model skips their required reference read and substitutes
  prior knowledge. Each selected method is identified as
  `method-id@content-revision`, and its authored `Do not use when` and
  `Stop conditions` are inlined when they fit the trusted context budget
  ([#32](https://github.com/ParkerHwang/OpenSocrates/issues/32)).
- A grounding read is recognized whatever shape the host uses to deliver the
  `Read` response. The terminator search no longer depends on envelope key
  names, which are not a stable host contract, so a host that wraps the body
  differently no longer looks like an incomplete read and no longer costs a
  compliant turn a repair pass. The search is bounded by an explicit depth limit
  and the existing collection limits.

### Security and privacy

- Grounding receipts are owner-only and authenticated. They contain only the
  instruction artifact digest, content revision, selected method IDs, and
  keyed tags; they never contain prompts, transcripts, tool output, credentials,
  or workspace and artifact paths, and they are removed with the turn artifact.
- The complete `Read` response is inspected transiently for the terminal marker
  and is neither retained nor projected into OpenSocrates records.
- The gate's scope is documented rather than implied. A receipt establishes that
  a successful `Read` callback for the exact current-turn artifact returned
  content reaching the terminal marker; it does not cryptographically prove that
  every artifact byte was returned. A synthetic marker-only payload would
  satisfy the marker test, which the model cannot produce because it does not
  author `tool_response`.

## [1.1.1] - 2026-08-10

### Added

- One-command `--host all` support for install, status, update, remove, and
  verification, backed by one desired-state manifest for the selected channel,
  installed hosts, and active version.
- Cross-host preflight, package verification, staging, activation, and reverse
  rollback so a partial Claude/Codex activation cannot leave a newly selected
  version on only one host.
- Opt-in macOS LaunchAgent updates through `auto-update enable`, `status`,
  `disable`, and the internal scheduled reconciliation command. Checks use a
  bounded interval with jitter, a single-instance lock, compatible-version
  policy, concise local receipts, and an update-target set kept separate from
  the complete installed-host set.

### Changed

- Claude now exposes one `/opensocrates` skill. The 48 method procedures,
  rigor, evidence audit, trace, and status behavior are internal supporting
  references or subcommands instead of separate top-level skills and commands.
- Updating a managed v1.1.0 Claude installation replaces the old multi-skill
  package tree, removing stale top-level method and helper entries.
- `status --host all` reports the desired and available version, last check,
  last successful update, and per-host drift.

### Security and privacy

- Automatic updates remain disabled until explicitly enabled, verify both the
  outer release checksum and complete package manifest before activation, and
  preserve the previous registrations on preflight, verification, staging, or
  activation failure.
- Desired state, locks, and receipts use owner-only permissions. Receipts keep
  only version, time, per-host result, and error category; no prompts,
  transcripts, credentials, or workspace paths are stored.

## [1.1.0] - 2026-08-06

### Added

- Claude Code CLI integration through native Claude plugin hooks and generated
  reasoning skills. Claude Code desktop and Cowork use the same implemented
  mechanism, but live delivery on those surfaces remains unvalidated.
- A bounded `claude --safe-mode -p` selector that uses the existing Claude login,
  disables tools and project/plugin context, accepts only structured output,
  and fails open after the existing 30-second deadline.
- Host-specific `npx` lifecycle support through `--host claude` while keeping
  Codex as the backward-compatible default.
- A separate Claude release package, checksum verification, security boundary
  checks, and offline integration contracts.
- A compact, runtime-free Claude Chat ZIP containing 48 method skills and
  three shared skills for custom-plugin upload.
- A support matrix that distinguishes automatic local hooks from skills-only
  Claude web and Desktop Chat use.

### Fixed

- The packaged POSIX and PowerShell launchers now resolve the native runtime
  from the plugin root (`runtime/<target>/...`) instead of from their own
  `bin/` directory. Previously every packaged Claude and Codex hook took the
  fail-open `missing_runtime` path, so `UserPromptSubmit` selection and
  `Stop`/`SessionEnd` cleanup were silent no-ops in the generated packages
  ([#16](https://github.com/ParkerHwang/OpenSocrates/issues/16)).

### Changed

- The release gate now executes the generated packages' own launchers against
  the packaged runtime layout for Claude and Codex, covering hook dispatch,
  control mode, and the fail-open paths, and it inspects the generated Claude
  package README for its trust-boundary and validation limitations
  ([#16](https://github.com/ParkerHwang/OpenSocrates/issues/16),
  [#22](https://github.com/ParkerHwang/OpenSocrates/issues/22)).
- The Claude package README now states that safe mode leaves managed settings
  policy in force, that policy-configured hooks can still observe the selector
  prompt and influence selection, and it grades Claude Code Desktop, Cowork,
  and Claude Chat validation the same way the repository README does
  ([#22](https://github.com/ParkerHwang/OpenSocrates/issues/22)).
- Release assembly, SBOM input, security scans, and GitHub Release publishing
  now cover both Claude and Codex packages.
- The installer detects case-sensitive pre-1.0 Claude marketplace
  registrations and requires an explicit migration instead of deleting them.

### Security and privacy

- Claude selection receives only the current prompt and authored catalog; it
  cannot read the transcript, workspace, MCP servers, or tools.
- Claude CLI stdout is parsed in memory, stderr is discarded, prompt history
  is disabled, and the process group is terminated on timeout or shutdown.

## [1.0.0] - 2026-07-31

### Added

- Local Codex selector and runtime with a 30-second, no-retry, fail-open
  execution contract.
- An authored catalog of 48 reasoning systems with English and Korean
  user-facing messages.
- Evidence, completion, routing, privacy, trace, and host-contract validation.
- Reproducible Python 3.12 builds, native `darwin-arm64` packaging, checksums,
  SBOM generation, security scanning, and release gates.
- GitHub Release and dependency-free Node.js installation paths, including
  `npx github:ParkerHwang/OpenSocrates#v1.0.0 install`.
- The public `opensocrates` npm package for the shorter
  `npx opensocrates@1.0.0 install` path.
- English and Korean README files and standard open-source community health
  documents.

### Security and privacy

- The selector uses the existing local Codex OAuth session; no API key or
  hosted OpenSocrates backend is required.
- Temporary instruction artifacts contain authored OpenSocrates material only.
- Installer downloads are checked against release and package-level SHA-256
  manifests before installation.

### Known limitations

- The packaged runtime is validated only for Apple-silicon macOS.
- Signing, notarization, clean-machine installation, and live host hook
  delivery remain explicitly unvalidated.

[1.0.0]: https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.0.0
[1.1.0]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.0.0...v1.1.0
[1.1.1]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.0...v1.1.1
[1.1.2]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.1...v1.1.2
