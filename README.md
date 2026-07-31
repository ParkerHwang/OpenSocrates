# OpenSocrates

**English** | [한국어](README.ko.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![Release](https://img.shields.io/github/v/release/ParkerHwang/OpenSocrates)](https://github.com/ParkerHwang/OpenSocrates/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

OpenSocrates is a local reasoning framework for AI-agent hosts. It detects
requests that benefit from deliberate reasoning, selects relevant reasoning
systems in a separate Codex context, and adds their authored theory and
examples to the active task. Straightforward factual and mechanical work can
pass through unchanged.

Version `1.0.0` includes 48 reasoning systems and supports Codex Desktop and
Codex CLI on Apple-silicon macOS (`darwin-arm64`). Other platforms, binary
signing, notarization, and clean-machine installation are not yet claimed as
validated.

## Install

Before installing, sign in to Codex with OAuth and make sure the `codex`
command is available.

### Option 1: npx from npm

Requires Node.js 20 or later. The npm package is a small, dependency-free
installer; it downloads and verifies the matching package from GitHub
Releases.

```bash
npx --yes opensocrates@1.0.0 install
```

Lifecycle commands:

```bash
npx --yes opensocrates@1.0.0 status
npx --yes opensocrates@1.0.0 update
npx --yes opensocrates@1.0.0 remove
```

### Option 2: npx from GitHub

Requires Node.js 20 or later. This command installs directly from the tagged
GitHub repository and remains available without the npm registry.

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 install
```

Lifecycle commands:

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 status
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 update
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 remove
```

The installer downloads the matching GitHub Release asset, verifies both the
release checksum and every checksum inside the package, and then registers a
private managed marketplace under the current Codex home.

### Option 3: download from GitHub Releases

Download `opensocrates.mjs` from the
[v1.0.0 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.0.0),
then run:

```bash
node opensocrates.mjs install
```

For a fully manual download and checksum check:

```bash
curl -fLO https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.0.0/opensocrates-1.0.0-codex-plugin.zip
curl -fLO https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.0.0/opensocrates-1.0.0-codex-plugin.zip.sha256
shasum -a 256 -c opensocrates-1.0.0-codex-plugin.zip.sha256
node opensocrates.mjs install \
  --asset opensocrates-1.0.0-codex-plugin.zip \
  --checksum opensocrates-1.0.0-codex-plugin.zip.sha256
```

### Option 4: build and install from source

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
git clone https://github.com/ParkerHwang/OpenSocrates.git
cd OpenSocrates
uv python install 3.12
uv sync --locked --all-groups
make release-check
uv run --locked --no-sync python tools/codex_plugin.py install
```

`make release-check` builds the native runtime and installable package locally.
Generated files are written to ignored `build/` and `dist/` directories.

## Use

Use Codex normally. Before each submitted prompt, OpenSocrates may intervene
when the request needs judgment, interpretation, diagnosis, explanation,
planning, evidence reconciliation, or another structured reasoning process.
When it intervenes, it:

1. uses a fresh, ephemeral selector thread;
2. chooses from the authored 48-system catalog;
3. writes the complete selected content to an owner-only temporary Markdown
   file; and
4. adds one hidden context message telling the active task to read that file.

There is no fixed selection-count limit. The hook message stays small while
the full selected theory and examples remain uncompressed in the referenced
file.

The selector has a 30-second internal deadline, does not retry, and fails open.
A timeout, SDK error, invalid output, non-intervention decision, unsafe
context, or unavailable hook produces no injection and does not block the
user's task.

To prevent the selector from requesting bounded transcript context:

```bash
export OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS=0
```

## Privacy and security

OpenSocrates runs locally through the Codex app-server and the user's existing
Codex OAuth session. It does not require an API key, host a backend, execute
the user's requested task, or add telemetry.

Temporary instruction files contain authored OpenSocrates content only. Raw
prompts, transcripts, workspace files, tool data, OAuth credentials, and
selector reasoning are not written to records, logs, metrics, diagnostics, or
temporary instruction files. Turn files are removed on `Stop`, remaining
session files on `SessionEnd`, and crash leftovers older than 24 hours on
`SessionStart`.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and the current
support boundary.

## Develop

The source repository intentionally excludes native binaries and intermediate
build output. Install the locked development environment and run:

```bash
make bootstrap
make format-check
make lint
make generated-check
make content-check
make docs-check
make security-scan
make smoke
npm test
npm pack --dry-run
make release-check
```

Repository layout:

| Path | Purpose |
| --- | --- |
| `src/opensocrates/` | Python 3.12 runtime and selector source |
| `content/` | Policies, localized messages, methods, theory, and examples |
| `plugin-src/codex/` | Codex plugin templates |
| `schemas/source/` | Canonical schema definitions |
| `schemas/v1/` | Generated, versioned public schemas |
| `installer/` | Dependency-free Node.js GitHub/npx installer |
| `tools/` | Build, validation, lifecycle, security, and release tools |
| `packaging/` | Native launcher and packaging configuration |
| `build/`, `dist/` | Generated locally and published as release assets |

Generated schemas and compiled content must be changed through their canonical
sources and generators. Release binaries belong in GitHub Releases, not in the
Git history.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request, and use the issue templates for bugs and feature
requests. The project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

OpenSocrates is available under the [MIT License](LICENSE). You may use,
modify, distribute, sublicense, and sell copies, provided the copyright and
license notice are preserved.
