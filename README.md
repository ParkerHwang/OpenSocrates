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

**English** | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Italiano](README.it.md) | [Español](README.es.md) | [Português](README.pt.md) | [ไทย](README.th.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## v1.5.2 on Mac and Windows

Version 1.5.2 adds French (`fr`), German (`de`), Italian (`it`), Spanish (`es`),
Portuguese (`pt`) and Thai (`th`) reasoning instructions to the existing English,
Korean, Simplified Chinese and Japanese, across all four host profiles. It preserves the v1.5.0 platform scope: Apple-silicon Mac and Windows
x64, with native Claude Code on Mac only. Download archives and SHA-256 files from the
[v1.5.2 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2),
or use the [npm installer](https://www.npmjs.com/package/opensocrates/v/1.5.2).

| Host | Delivery | Platform and activation |
| --- | --- | --- |
| Codex | Existing hooks, controller and native decision runtime | Apple-silicon Mac and Windows x64; review the seven hooks in an interactive session |
| Claude Code CLI / Desktop local Code | Stateless native entry and complete installed references | Apple-silicon Mac; requires the Claude CLI, host login and plugin/hook permissions |
| Claude web / Desktop Chat / Cowork | Standalone content-only account skill ZIP | Export on Mac or Windows; upload, enable and add the one-time account instructions below |
| Antigravity conversation application | Owned modular rule and skill | Apple-silicon Mac and Windows x64; choose workspace or global scope |

Windows native Claude Code in a terminal or Desktop Code is outside this
release's scope. Account content does not install a native Claude integration.
See the [Mac guide](docs/macos-v1.5.md) and [Windows guide](docs/windows-v1.5.md).

Trusted native hooks and Antigravity's standing rule provide entry during normal
requests. For Claude account skills, add the standing instruction below to use
OpenSocrates without repeating its name. Selection still depends on the host
model and can be missed. Installation, loading, complete reads, application,
and useful outcomes are separate evidence levels. No general quality, token-cost,
or latency improvement is claimed.

**After installation:** follow the [visual setup guide](docs/setup-guide.md) for hook review, account skill switches, and host readiness. It also includes a request you can paste into an agent.

## Install or update

Install Node.js 20+, make the chosen host available, and sign in to that host.
Native runtimes are bundled; installation does not require Python. Start with
Codex on either supported platform:

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 status --host codex
```

For an existing Codex installation, including v1.5.0, use:

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

Review the seven Codex hooks in an interactive session and start a fresh
conversation. Non-interactive execution may skip untrusted hooks. `status`
reports installation and integrity; it does not prove automatic delivery.

On Apple-silicon Mac, install the native Claude companion with:

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 status --host claude
```

For Antigravity, choose an existing absolute workspace directory:

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
```

On Windows, replace the directory with an absolute local-drive path such as
`C:\Work\Reading Workshop` and quote it. Omit `--workspace` for the global scope.
For Claude account content, export to an absolute ZIP filename in an existing
folder, then upload and enable the ZIP in Claude's Customize > Skills interface:

```sh
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

### Claude Chat and Cowork: one-time account instructions

For use without typing `/opensocrates` on each request, enable the account skill
and append this instruction in **Settings → General → Instructions for Claude**.
Preserve your existing instructions. In older Cowork interfaces, use
**Settings → Cowork → Global instructions**; if Web and Desktop use different
accounts, configure each account you use.

```text
For requests that require interpretation or judgment, such as synthesizing
sources, comparing options, making decisions or drafting messages, load the
enabled OpenSocrates skill and follow its instructions even when I do not
mention it. Read the complete procedure and check applicability before applying
a reasoning method. Do not add unnecessary procedures to mechanical work such
as formatting.
```

Save once, then start a fresh conversation and describe your task normally.
The instruction guides model-selected skill use; it adds no native hook or
guaranteed every-turn enforcement. See the [step-by-step setup guide](docs/setup-guide.md#claude-standing-instructions)
and [Claude's official instruction settings](https://support.claude.com/en/articles/10185728-understanding-claude-s-personalization-features).

The platform guides cover Windows paths, account replacement, updates, disabling,
removal, and verified local-archive alternatives. With no local asset flags,
the installer downloads the pinned v1.5.2 archive and checksum from GitHub Releases.

New profiles require explicit `--host claude`, `--host antigravity`, or
`--host claude-chat`. The default and `--host all` continue to select Codex;
they do not install every new host. New profiles have no purge, trust-reset,
or automatic-update route.

Old multi-host installations are not silently adopted or erased. Reconcile their
exact origin and ownership before installing a new profile. Back up an existing
OpenSocrates account skill and its enabled state before replacing it.

## Reasoning instruction languages

All 48 methods include complete procedures and examples in ten languages:
English, Korean, Simplified Chinese, Japanese, French, German, Italian, Spanish,
Portuguese and Thai. The release contains 480 procedure files, 3,840 canonical
cases and 1,440 teacher questions, three per method per language. Content
revision 5 preserves the existing four languages' body text and values while
updating each method's revision identity from 4 to 5.

An explicit trusted locale takes precedence over a stored preference, then
current-input script detection applies. Kana selects Japanese first; otherwise
dominant Thai, Hangul or Han selects Thai, Korean or Chinese. Latin-script
French, German, Italian, Spanish and Portuguese need an explicit or stored
choice; they are not reliably identified by script. Han-only Japanese also
needs an explicit choice. Empty, unknown-script and tied input falls back to
English. Portuguese uses Brazilian orthography under the generic `pt` code;
separate regional variants are not claimed.

See the [v1.5.2 language guide](docs/v1.5.2.md) and
[locale settings](docs/settings.md) for exact runtime commands and JSON requests.
Instruction language is separate from answer language, npm installer output and
host UI. Windows ARM64 and the Go migration remain separate v1.6.0 work.

## When attribution appears

A final answer ends with the exact line `Powered by OpenSocrates` only when an
eligible authored method was read in full and actually applied to that answer.
The wording is the same in all ten languages. Reader guidance alone and
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
- [v1.5.2 languages, selection and scope](docs/v1.5.2.md)
- [v1.5.0 implementation baseline](docs/v1.5.0/IMPLEMENTATION_PLAN.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

OpenSocrates is [MIT licensed](LICENSE), independent of OpenAI, Anthropic, and
Google, and not endorsed by them.
