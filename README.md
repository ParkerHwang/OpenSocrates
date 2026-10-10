<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Reasoning help for results you can understand, judge, and use.**

OpenSocrates brings 48 authored reasoning methods into the task you are already
doing: synthesize evidence, understand stakeholder perspectives, compare choices,
and write useful messages. The original English/Korean procedures remain intact.
The v1.5 reader guides connect conclusions to context and next actions;
dedicated coding-specialist features are outside this version.

**English** | [한국어](README.ko.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## v1.5.0 on Mac and Windows

Version 1.5.0 preserves Codex and adds native Claude Code on Apple-silicon Mac,
a portable Claude account skill, and Antigravity workspace/global rules and
skills on Mac and Windows x64. Download archives and SHA-256 files from the
[v1.5.0 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.0),
or use the [npm installer](https://www.npmjs.com/package/opensocrates/v/1.5.0).

| Host | Delivery | Platform and activation |
| --- | --- | --- |
| Codex | Existing hooks, controller and native decision runtime | Apple-silicon Mac and Windows x64; review the seven hooks in an interactive session |
| Claude Code CLI / Desktop local Code | Stateless native entry and complete installed references | Apple-silicon Mac; requires the Claude CLI, host login and plugin/hook permissions |
| Claude web / Desktop Chat / Cowork | Standalone content-only account skill ZIP | Export on Mac or Windows; upload and enable through the account's Skills interface |
| Antigravity conversation application | Owned modular rule and skill | Apple-silicon Mac and Windows x64; choose workspace or global scope |

Windows native Claude Code in a terminal or Desktop Code is outside this
release's scope. Account content does not install a native Claude integration.
See the [Mac guide](docs/macos-v1.5.md) and [Windows guide](docs/windows-v1.5.md).

Normal requests need no repeated OpenSocrates command. Trusted native hooks and
Antigravity's standing rule provide entry; account skills are selected by the
host model and may be missed. Installation, loading, complete reads, application,
and useful outcomes are separate evidence levels. No general quality, token-cost,
or latency improvement is claimed.

**After installation:** follow the [visual setup guide](docs/setup-guide.md) for hook review, account skill switches, and host readiness. It also includes a request you can paste into an agent.

## Install or update

Install Node.js 20+, make the chosen host available, and sign in to that host.
Native runtimes are bundled; installation does not require Python. Start with
Codex on either supported platform:

```sh
npx --yes opensocrates@1.5.0 install --host codex
npx --yes opensocrates@1.5.0 status --host codex
```

For an existing v1.4 Codex installation, use:

```sh
npx --yes opensocrates@1.5.0 update --host codex
```

Review the seven Codex hooks in an interactive session and start a fresh
conversation. Non-interactive execution may skip untrusted hooks. `status`
reports installation and integrity; it does not prove automatic delivery.

On Apple-silicon Mac, install the native Claude companion with:

```sh
npx --yes opensocrates@1.5.0 install --host claude
npx --yes opensocrates@1.5.0 status --host claude
```

For Antigravity, choose an existing absolute workspace directory:

```sh
npx --yes opensocrates@1.5.0 install --host antigravity --workspace /absolute/path/to/workspace
```

On Windows, replace the directory with an absolute local-drive path such as
`C:\Work\Reading Workshop` and quote it. Omit `--workspace` for the global scope.
For Claude account content, export to an absolute ZIP filename in an existing
folder, then upload and enable the ZIP in Claude's Customize > Skills interface:

```sh
npx --yes opensocrates@1.5.0 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.0-account.zip
```

The platform guides cover Windows paths, account replacement, updates, disabling,
removal, and verified local-archive alternatives. With no local asset flags,
the installer downloads the pinned v1.5.0 archive and checksum from GitHub Releases.

New profiles require explicit `--host claude`, `--host antigravity`, or
`--host claude-chat`. The default and `--host all` continue to select Codex;
they do not install every new host. New profiles have no purge, trust-reset,
or automatic-update route.

Old multi-host installations are not silently adopted or erased. Reconcile their
exact origin and ownership before installing a new profile. Back up an existing
OpenSocrates account skill and its enabled state before replacing it.

## When attribution appears

A final answer ends with the exact line `Powered by OpenSocrates` only when an
eligible authored method was read in full and actually applied to that answer.
The wording is the same in English and Korean. Reader guidance alone and
mechanical work do not qualify. The line is attribution, not proof of native
application or a better result.

## Privacy and development

The default decision path makes no extra selector-model call and stores no raw
prompts, transcripts, screenshots, or hidden reasoning. The native Claude entry
does not read transcripts or initialize a database. The account skill has no
executable surface; normal host conversations and model requests follow the
host's own authentication, permissions, retention settings, and terms.
See [SECURITY.md](SECURITY.md).

- [Mac installation and evidence boundaries](docs/macos-v1.5.md)
- [Windows installation and evidence boundaries](docs/windows-v1.5.md)
- [Authored methods](content/methods/) · [Decision-point contract](docs/decision-points.md)
- [Implementation scope](docs/v1.5.0/IMPLEMENTATION_PLAN.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

OpenSocrates is [MIT licensed](LICENSE), independent of OpenAI, Anthropic, and
Google, and not endorsed by them.
