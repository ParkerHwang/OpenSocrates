# Changelog

All notable changes to OpenSocrates are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.1] - 2026-08-16

### Added

- A committed v1.2 adjudication snapshot records 51 EN/KO semantic pairs,
  49 resolved disagreements, strict Draft 2020-12 schemas, aggregate counts,
  and hashes. Its clean-clone validator and mutation suite check only public
  repository artifacts; maintainer-held packet, reviewer, and raw-result
  evidence remains explicitly unavailable in public mode.
- `remove --host <host|all> --purge` provides an explicit, idempotent
  complete-uninstall attempt for exact OpenSocrates registrations, verified
  host cache payloads, empty Claude plugin-data directories, OpenCode-owned
  files, the updater, transaction residue, and final installer state.
- `remove --host <codex|all> --purge --reset-trust` explicitly resets only the
  seven canonical OpenSocrates Codex hook approvals after validating a narrow,
  transactional config update.
- A same-machine reinstall acceptance workflow binds the candidate commit,
  native artifacts, packed npm installer, purge and reinstall lifecycle,
  manual observations, privacy-safe result bundle, and guarded cleanup without
  presenting the machine as clean-machine evidence.

### Changed

- All six generated host packages now carry the same bilingual, three-question
  teacher overlay while preserving their real delivery models: hidden trusted
  hook context for Claude/Codex, explicit content reads for Antigravity/Cursor,
  native skill content for Grok Build, and one question-led compiled procedure
  with the same native fallback for OpenCode.
- Hook budget fallback now drops teacher questions before binding guardrails,
  instruction artifact schema `/3` reads in-flight `/2` headers with an empty
  question default, and empty or malformed question data no longer refers to
  absent questions.
- The teacher-question source now has a generated canonical schema and explicit
  overlay identity checks without changing authored per-method content revision
  `1`.
- Ordinary `remove` now states its narrower registration/managed-root contract,
  reports known remaining OpenSocrates paths, and points to the purge command
  instead of implying that every installed payload was removed.
- Installer help and English/Korean removal docs now distinguish plugin
  registration, owned payloads, host security trust, and preserved user history.
- Claude Code, Desktop Local, and Cowork plugin documentation now uses the
  canonical `/opensocrates:opensocrates` namespace, while the separately
  rendered Claude Chat standalone skill keeps `/opensocrates`. Release checks
  reject either command when it appears in the wrong artifact.
- Claude evidence now keeps the installer-managed local plugin, a manually
  uploaded standalone Chat ZIP, and the pre-existing synced/custom skill as
  separate provenance states. The historical v1.1.2 live receipt remains
  historical, while current-version checks require a version-bound receipt.
- Codex SessionStart timing evidence now measures `startup` and `compact`
  independently and requires both source sets to pass before release or
  reinstall acceptance can report the timing budget as verified.
- The exact public v1.2.1 Chat ZIP, checksum, and release commit were unavailable
  at the 2026-08-15 provenance audit. The current Chat receipt and EN/KO
  documentation therefore keep live upload pending instead of inheriting the
  v1.1.2 validation claim.

### Security and privacy

- Release-package checks reject evaluation or adjudication paths in every host
  and Claude Chat ZIP. The npm package remains restricted to the installer and
  its public release documents, so source evaluation artifacts do not ship.
- Purge verifies canonical non-symlink paths, exact package identity,
  manifests, checksums, and ownership markers; live `.in_use` payloads,
  unverified registration, unknown data, and cleanup failures remain pending.
  Unrelated host configuration and user history are preserved. Codex hook trust
  remains preserved unless the explicit reset flag is supplied.
- The trust reset refuses symlinks, hard links, noncanonical or unexpected
  matching sections, invalid configs, concurrent changes, and failed Codex
  consumption checks. It preserves non-target bytes and restores the exact
  original when rollback remains safe; a later external edit is never
  overwritten.
- Chat evidence stores only release/archive identity, counts, versions,
  pass/fail booleans, and categorical provenance/routing states. The missing
  exact release artifact at audit time prevented a UI upload attempt, so no
  authentication, 2FA, user-confirmation, prompt, conversation, account, path,
  raw UI, upload content, or credential boundary was crossed.

## [1.2.0] - 2026-08-13

### Added

- Experimental Google Antigravity integration as a content-only global plugin
  with one explicit `opensocrates` skill, 48 internal authored procedures,
  isolated lifecycle ownership, and an `agy 1.0.6` package-validation receipt.
  It deliberately ships no hooks, runtime, background process, or automatic
  selector.
- Experimental Cursor Agent Plugin integration with one `/opensocrates` skill,
  48 internal authored procedures, isolated lifecycle ownership, and
  release-gate package validation. It adds no OpenSocrates selector or hook,
  and no live Cursor invocation receipt is claimed.
- Grok Build is a first-class `grok` installer host with one native,
  auto-selectable `/opensocrates` skill, 48 internal authored procedures,
  deterministic content-only packaging, capability reporting, isolated
  lifecycle ownership, release-gate coverage, and English/Korean support
  documentation. Live Grok Build 1.0.3 evidence bounds automatic activation,
  explicit invocation, hook behavior, and remaining TUI/subagent limitations.
- First-class OpenCode 1.18.18+ integration using the stable `chat.message`
  hook for live-validated same-turn local activation and a native
  `opensocrates` Agent Skill fallback.
- Provider-neutral, dependency-free OpenCode bridge with bounded input,
  duplicate prevention, and exception fail-open behavior. A live
  DeepSeek V4 Flash smoke test is recorded without embedding provider settings.
- OpenCode install, status, verify, update, remove, rollback, automatic-update,
  and `--host all` lifecycle support with exact-path ownership and complete
  installed inventory verification.
- Deterministic OpenCode package generation, release-gate validation,
  capability reporting, privacy-safe compatibility evidence, and English and
  Korean support documentation.

### Fixed

- Pre-release and offline `--host all` transactions now treat supplied
  host-qualified asset pairs as the exact host set. Candidate packages are no
  longer mixed with public-release downloads merely because another supported
  host CLI is available on the machine.

### Security and privacy

- The OpenCode installer never rewrites `opencode.json`; it refuses unowned,
  partial, symbolic-link, and unsafe exact paths while preserving unrelated
  plugins, skills, and configuration.
- The OpenCode bridge makes no network, subprocess, recursive OpenCode, extra
  model, telemetry, or credential access and preserves the complete-procedure
  grounding requirement.

## [1.1.5] - 2026-08-12

### Added

- Packaged `diagnose` now verifies the complete installed file inventory
  against `checksums.sha256` and validates the release manifest's runtime
  version, host, and content revision. Explicit `mismatch`, `unavailable`, and
  `unverified` states replace presence-based claims
  ([#64](https://github.com/ParkerHwang/OpenSocrates/issues/64)).
- Release tests execute the packaged runtime against both intact packages and
  a staged tampered Claude package so integrity reporting is exercised outside
  the source process ([#64](https://github.com/ParkerHwang/OpenSocrates/issues/64)).

### Changed

- Claude grounding artifacts now prefer an owner-only, self-ignored
  `.opensocrates` area inside the active workspace, while retaining the OS
  temporary directory as a fail-open fallback. Lookup, receipts, expiry, and
  cleanup handle both roots during upgrades and fallback runs
  ([#62](https://github.com/ParkerHwang/OpenSocrates/issues/62)).
- Codex package and installation documentation now requires one interactive
  hook approval before automatic selection is expected and distinguishes
  release-validated packaging from unvalidated live hook delivery
  ([#63](https://github.com/ParkerHwang/OpenSocrates/issues/63)).

### Fixed

- Default-permission `claude -p` sessions can read selected grounding content
  without `--add-dir`, avoiding the denied-read repair loop caused by placing
  artifacts only in the system temporary directory
  ([#62](https://github.com/ParkerHwang/OpenSocrates/issues/62)).
- `diagnose` no longer reports manifest and checksum verification merely
  because package files exist ([#64](https://github.com/ParkerHwang/OpenSocrates/issues/64)).

## [1.1.4] - 2026-08-12

### Added

- A privacy-safe Claude selector aggregate records only bounded counts under a
  closed outcome vocabulary. `diagnose` exposes those counts without prompts,
  transcripts, session identifiers, paths, model output, credentials, or
  selector reasoning ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- A sanitized Cowork receipt validates local plugin upload and the native
  `UserPromptSubmit` → `PostToolUse(Read)` → `Stop` lifecycle, including the
  authenticated grounding receipt and final cleanup
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).

### Changed

- Native runtime builds are split by host profile. The Claude package excludes
  the Codex SDK and CLI while the Codex package preserves its existing runtime
  surface ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- Release tooling derives artifact paths from the detected native target,
  defaults plugin generation to `dist/runtime/<host>`, and interprets Cowork's
  50 MB and 200 MB limits conservatively as decimal bytes
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).

### Fixed

- The Claude runtime now uses PyInstaller's no-archive mode, and release checks
  reject nested ZIP entries before a Cowork package can be published
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- Unreadable selector aggregates report `unavailable` instead of zero attempts.
  Malformed current-schema documents self-heal on the next valid outcome while
  unknown future schemas are preserved
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).

## [1.1.3] - 2026-08-11

### Added

- Bounded semantic packaged-README checks now reject novel universal-support,
  vendor-endorsement, and managed-environment safety overclaims, with mutation
  coverage that also protects accurate limitation wording from false positives
  ([#27](https://github.com/ParkerHwang/OpenSocrates/issues/27)).
- Native plugin packages now expose one honest `darwin-arm64` boundary: the
  unvalidated PowerShell launcher is removed, the POSIX launcher rejects every
  other target, and package manifests and docs distinguish unshipped build
  candidates from the released platform
  ([#12](https://github.com/ParkerHwang/OpenSocrates/issues/12)).
- A Claude Chat upload probe records the exact verified v1.1.2 skills ZIP
  shape and hash, live uploader acceptance, single visible skill entry,
  catalog routing, representative method loading, and grounding audit without
  retaining prompt or conversation content
  ([#5](https://github.com/ParkerHwang/OpenSocrates/issues/5)).
- A privacy-safe Cowork probe validates the separately uploaded
  `/opensocrates` skill and corrects the installation boundary: Claude Code CLI
  marketplace registration is not a Cowork-native plugin install. The exact
  published v1.1.2 plugin archive is rejected by Cowork's upload-size limits,
  and repository sync is unavailable without a marketplace manifest, so native
  hooks remain blocked
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- A privacy-safe Claude Code desktop live probe now validates a complete
  authenticated UserPromptSubmit → PostToolUse(Read) → Stop lifecycle. It
  observes the owner-only instruction artifact, authenticated grounding
  receipt, and final cleanup without retaining prompts, transcripts, paths,
  credentials, payloads, or selector reasoning
  ([#3](https://github.com/ParkerHwang/OpenSocrates/issues/3)).
- A reproducible packaged `darwin-arm64` timing harness verifies PostToolUse
  receipt creation and Stop cleanup across fresh-path and warm runs. All 80
  measured operations completed, the worst p95 was 1,333.067 ms against the
  3-second budget, and no timeout change is recommended
  ([#6](https://github.com/ParkerHwang/OpenSocrates/issues/6)).
- An opt-in Claude structured-output matrix runs 20–50 bounded attempts per
  explicitly requested model, requires 95% valid envelopes, and stores only
  aggregate fixed outcome counts. The authenticated Claude Code 2.1.226
  `host-default` row passed 20/20 attempts with every failure outcome at zero;
  no unobserved named model is claimed
  ([#8](https://github.com/ParkerHwang/OpenSocrates/issues/8)).
- An opt-in, privacy-safe real Claude selector contract verifies the exact
  isolation command, environment allowlist, temporary workspace, and real
  subprocess failure categories. An authenticated, non-sensitive live call on
  Claude Code 2.1.226 returned `selected`, removed its temporary workspace, and
  retained no prompt, raw output, credential, or selector reasoning
  ([#7](https://github.com/ParkerHwang/OpenSocrates/issues/7)).
- Sanitized Claude Code payload receipts for the complete v1.1.2 hook
  lifecycle — `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `Stop`, and
  `SessionEnd` — captured from a supported runtime and compared field by field
  with the shared adapter mapping. The checks assert that `prompt_id` is
  projected into turn identity, that `last_assistant_message` reaches the Stop
  decision, that two consecutive turns of one session stay artifact-isolated,
  and that Stop and `SessionEnd` clean up
  ([#9](https://github.com/ParkerHwang/OpenSocrates/issues/9)).

### Fixed

- The Claude Chat skills ZIP now uses the uploader's required single top-level
  `opensocrates/` folder with `SKILL.md` directly inside; the prior plugin-shaped
  archive was rejected by the real Customize → Skills upload UI
  ([#5](https://github.com/ParkerHwang/OpenSocrates/issues/5)).
- The installer now accepts only explicit Claude list JSON variants, rejects
  malformed, duplicate, or conflicting managed entries, surfaces disabled
  plugins as drift, re-enables them on install/update, preserves their state on
  rollback, and emits executable recovery commands after a secondary root
  removal failure ([#11](https://github.com/ParkerHwang/OpenSocrates/issues/11)).
- POSIX and PowerShell launchers now enforce the single generated `bin/`
  package layout and never probe a competing `bin/runtime/` tree
  ([#26](https://github.com/ParkerHwang/OpenSocrates/issues/26)).
- Packaged-launcher checks now derive each host's runtime root from canonical
  `generator.json` metadata and include a mismatch probe that remains
  discriminating when no native runtime targets were built
  ([#25](https://github.com/ParkerHwang/OpenSocrates/issues/25)).
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
[1.1.3]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.2...v1.1.3
[1.1.4]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.3...v1.1.4
[1.1.5]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.4...v1.1.5
[1.2.0]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.5...v1.2.0
[1.2.1]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.2.0...v1.2.1
