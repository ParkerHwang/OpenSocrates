<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Reasoning help for results you can understand, judge, and use.**

OpenSocrates brings 48 authored reasoning methods into the task you are already
doing: synthesize evidence, understand stakeholder perspectives, compare choices,
and write useful messages. The original English/Korean procedures remain intact.
The v1.5 reader guides connect their conclusions to context and next actions;
dedicated coding-specialist features are outside this version.

**English** | [한국어](README.ko.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## v1.5.0 implementation stages

The Windows continuation adds Claude Web/Desktop Chat/Cowork account ZIP
verification/export and Antigravity workspace/global lifecycle on Windows x64.
Windows Claude Code is outside the requested scope; the existing Mac native
implementation remains. See the [Windows guide](docs/windows-v1.5.md),
[observations](evals/v1.5-windows/REPORT.md) and
[implementation handoff](docs/v1.5.0/WINDOWS_IMPLEMENTATION_HANDOFF.md).
Filesystem validation and live host outcomes are recorded separately.

This checkout implements the Mac profiles below and builds their local archives.
**v1.5.0 has not been published to npm or GitHub Releases.** Use the source
installer with a verified local archive; do not assume `npx opensocrates@1.5.0`
or a release download exists. The npm badge describes published registry state.

| Host | Implemented delivery | Qualification boundary |
| --- | --- | --- |
| Codex, Apple-silicon Mac | Existing hooks, controller, native decision runtime | Existing Codex behavior and regression gates preserved |
| Claude Code CLI / Desktop local Code, Apple-silicon Mac | Stateless native entry plus complete installed references | CLI registration and Desktop local reader cases observed; authenticated terminal delivery pending; draft limitations recorded |
| Claude web / Desktop ordinary Chat / Cowork | Standalone content-only account skill ZIP | ZIP format accepted; temporary old-skill replacement and live treatment pending |
| Antigravity conversation application, Mac | Owned modular rule and skill, workspace or global scope | One ordinary-request workspace reader case observed; global/app lifecycle needs its own evidence |

Normal requests need no repeated OpenSocrates command. Trusted native hooks and
Antigravity's standing rule provide entry; account skills are selected by the
host model and may be missed. Installation, loading, complete reads, application,
and useful outcomes are separate evidence levels. No general quality, token-cost,
or latency improvement is claimed.

## Start from the local Mac candidate

Install Node.js 20+, make the chosen host available, and sign in to that host.
The native Mac runtime is bundled; installation does not require Python.
From this repository, verify a local Claude companion before installing it:

```sh
node installer/opensocrates.mjs verify --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs install --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs status --host claude
```

Review the host's plugin/hook permissions and start a fresh conversation.
`status` reports installation and integrity; it does not prove automatic entry.
For Antigravity workspace installation, account export, updates, disabling,
removal, and actual pending checks, use the [Mac guide](docs/macos-v1.5.md).

New profiles require explicit `--host claude`, `--host antigravity`, or
`--host claude-chat`. The default and `--host all` retain the existing Codex
desired-state lane; they do not install every new host. New profiles have no
purge, trust-reset, or automatic-update route.

## Existing released Codex and Windows

The published v1.4.0 package remains a Codex-only release for Apple-silicon Mac
and Windows x64:

```sh
npx --yes opensocrates@1.4.0 install --host codex
npx --yes opensocrates@1.4.0 status --host codex
```

Review the seven Codex hooks in an interactive session. Non-interactive execution
may skip untrusted hooks. Existing Codex Windows support is preserved; **new
v1.5 Claude/Antigravity Windows integration is the next stage**, not a completed
support claim. See [existing Windows support](docs/windows-support.md) and the
[Windows implementation handoff](docs/v1.5.0/WINDOWS_HANDOFF.md).

Old multi-host installations are not silently adopted or erased. Reconcile their
exact origin and ownership before installing a new profile. Preserve the existing
account skill until a backed-up replacement qualifies.

## Privacy and development

The default decision path makes no extra selector-model call and stores no raw
prompts, transcripts, screenshots, or hidden reasoning. The new Claude entry does
not read transcripts or initialize a database. The account skill has no executable
surface; normal host conversations and model requests follow the host's own
authentication, permissions, retention settings, and terms. See [SECURITY.md](SECURITY.md).

- [Mac installation and qualification](docs/macos-v1.5.md)
- [Authored methods](content/methods/) · [Decision-point contract](docs/decision-points.md)
- [Current implementation scope](docs/v1.5.0/IMPLEMENTATION_PLAN.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

OpenSocrates is [MIT licensed](LICENSE), independent of OpenAI, Anthropic, and
Google, and not endorsed by them.
