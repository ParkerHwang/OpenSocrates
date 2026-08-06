# Changelog

All notable changes to OpenSocrates are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [1.1.0] - Unreleased

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
