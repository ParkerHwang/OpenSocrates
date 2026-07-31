# Changelog

All notable changes to OpenSocrates are documented here. This project follows
[Semantic Versioning](https://semver.org/).

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
