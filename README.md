<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Reasoning help for results you can understand, judge, and use.**

OpenSocrates brings 48 authored reasoning methods into the task you are already
doing: synthesize evidence, understand stakeholder perspectives, compare choices,
and write useful messages. English, Korean, Simplified Chinese (`zh`) and Japanese (`ja`) procedures,
teacher questions, response policies and shared reader guides retain the released
v1.5.1 baseline: content revision 4, 192 complete procedures and 576 teacher
questions. The original English/Korean method bodies remain unchanged.
The separate method-body upgrades are excluded from v1.6.0 and belong to v1.6.1
or later. Dedicated coding-specialist features remain outside this scope.

**English** | [한국어](README.ko.md) | [简体中文](README.zh.md) | [日本語](README.ja.md)

**For agents finding tools:** [Assess task fit, choose a released package and verify setup](docs/agent-discovery.md).

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## v1.6.0 native migration

This branch is the **unreleased v1.6.0 implementation candidate**. Its Go runtime,
management CLI, installer, updater and development tools replace the active
Python/JavaScript/npm path. End users do not install Go, Python, Node.js or npm.
Native release assets come from
[GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases).
Remaining production signing/trusted-root and native release conditions must be
completed before publishing or recommending this candidate as a stable release.
The current released baseline remains
[v1.5.1](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1).
The separate v1.5.2 language expansion is in progress; its proposed French,
German, Italian, Spanish, Portuguese and Thai additions are not this candidate
's current baseline. Reconcile that work before the v1.6.0 release.

| Host | Delivery | Platform and activation |
| --- | --- | --- |
| Codex CLI / Desktop | Native hooks, controller and Go decision runtime | macOS ARM64 and Windows x64/ARM64 (default PowerShell); review seven hooks and start a fresh session |
| Claude Code CLI / Desktop local Code | Stateless native entry and complete installed references | macOS ARM64; requires Claude CLI, login and plugin/hook permissions |
| Claude web / Desktop Chat / Cowork | Standalone content-only account ZIP | Verify/export on all supported targets; upload and enable separately in the account |
| Antigravity conversation application | Owned modular rule and skill | macOS ARM64 and Windows x64/ARM64; explicitly choose workspace or global scope |

Windows ARM64 was added by explicit user direction during implementation. It
uses its own native `.exe`/bundle/helper and the same per-user update policy.
Exact native ARM64 runtime/install/recovery/scheduler results belong in the
implementation handoff. Production and actual host activation evidence remain
separate gates; x64 execution under emulation is supplementary evidence only.

The default and `--host all` select **Codex only**. Other profiles require an
explicit host. Windows native Claude Code, Linux, macOS Intel,
WSL and remote-host qualification are outside this release scope.

Installation, loading, complete reads, application and useful outcomes are
separate evidence levels. Local tests and archive installation do not establish
live host delivery or general quality, token-cost or latency improvements.
See [the native guide](docs/native-v1.6.md) for exact commands, migration,
automatic updates, recovery and missing release evidence, and
[post-installation setup](docs/setup-guide.md) for host approval screens.

## Install, adopt or update

Download the native executable and matching platform bundle from the approved
GitHub Release. Check the release's authenticity/signing instructions before
running the installer. Candidate bundles are locally built until a release is
published. On macOS, run the downloaded native executable:

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
```

On Windows x64 or ARM64, use `opensocrates.exe` and a quoted absolute local-drive path:

```text
.\opensocrates.exe install --host codex --package "C:\Downloads\bundle.zip"
.\opensocrates.exe status --host codex
```

For a verified existing v1.5 npm-managed installation, use the explicit one-time
`adopt` command with the native bundle. It preserves owned state, settings, host
registrations, trust and disabled integrations while coordinating the old
updater. It does not broadly uninstall npm packages or erase user data.

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

Use `update` with a local verified bundle for subsequent manual installation
updates. `verify`, `manage diagnose` and `remove` select the same explicit
host/scope. Claude and Antigravity support `enable`/`disable`; Codex enabled state
belongs to the host controls. Unknown or modified files are preserved and reported.
Native Claude uses `--host claude` on Mac; Antigravity uses `--host antigravity`
and optional `--workspace /absolute/path/to/existing/workspace`. Omit workspace
for global scope. Account content uses:

```text
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

For ARM64 choose `opensocrates-v1.6.0-windows-arm64.exe` and
`opensocrates-v1.6.0-windows-arm64.zip`; do not substitute x64-emulated candidate
results for native evidence. See the native guide for external host availability.

Review Codex's seven hooks in an interactive session. Non-interactive execution
may skip untrusted hooks. Existing disabled integrations stay disabled after
adoption/update; enable them explicitly when desired. `status` checks local
installation/integrity, not automatic delivery or a running conversation's
loaded version.

## Automatic updates

Codex has opt-in `stable` checks outside hooks, every 24 hours with delayed login
checks: a per-user LaunchAgent on Mac and Task Scheduler task on Windows.
Use `auto-update enable`, `status`, `run` and `disable` through the native
management CLI. Signed metadata, expiry, rollback protection, platform integrity
and compatibility are checked before activation. Major or breaking-schema
updates are not applied automatically. Offline checks preserve the current
version. Processes retain their started bundle; host reload/fresh sessions may
be needed. Local updates never upload Claude account content or modify already
running conversations.

The candidate's production update root/signing service is not provisioned;
production checks remain unavailable until that release gate is satisfied.
Additional integrations retain manual lifecycle and are excluded from scheduled
updates until their individual activation/recovery qualification is complete.

### Claude Chat and Cowork: one-time account instructions

Enable the account skill, then append the instruction below in
**Settings → General → Instructions for Claude**, preserving existing
instructions. Older Cowork interfaces use **Settings → Cowork → Global
instructions**. Configure each account you use when Web and Desktop differ.

```text
For requests that require interpretation or judgment, such as synthesizing
sources, comparing options, making decisions or drafting messages, load the
enabled OpenSocrates skill and follow its instructions even when I do not
mention it. Read the complete procedure and check applicability before applying
a reasoning method. Do not add unnecessary procedures to mechanical work such
as formatting.
```

Save once and start a fresh conversation. This guides model-selected skill use;
it does not add native hooks or guaranteed every-turn enforcement. Follow the
[setup guide](docs/setup-guide.md#claude-standing-instructions) for the separate
upload, capability and enabled-state checks.

## Reasoning instruction language

The current content supports `en`, `ko`, `zh` and `ja`. The optional legacy
selector resolves explicit preference, stored preference, then current-input
script detection. Kana chooses Japanese; otherwise dominant Hangul chooses
Korean and dominant Han chooses Chinese. Han-only Japanese needs an explicit
Japanese preference. Empty, Latin-only and tied inputs fall back to English.

```text
./opensocrates locale get
./opensocrates locale set en
./opensocrates locale set ko
./opensocrates locale set zh
./opensocrates locale set ja
./opensocrates locale set follow
./opensocrates locale reset
```

These commands have no host argument. On Windows use `.\opensocrates.exe`.
`follow` and `reset` clear only this preference. It affects the optional legacy
selector, not stateless decision requests or account skills. Stateless decision
JSON requires an explicit `locale`; native Claude entry reads no stored
preference. Account skills and Antigravity use their language guides and complete
references. Instruction language is separate from answer language, host UI and
management CLI output; not every CLI message is translated. Method IDs, JSON
keys and the attribution line stay unchanged across all four languages.

## Attribution, privacy and development

An answer ends with the exact line `Powered by OpenSocrates` only when an
eligible authored method was read in full and actually applied. Reader guidance
alone and mechanical work do not qualify. Attribution does not prove application
or improved results.

The normal decision path makes no extra selector-model or authentication call
and stores no raw prompts, transcripts, screenshots or hidden reasoning. Native
Claude entry reads no transcripts and initializes no database. Account content
has no executable surface. Host conversation/authentication/retention policies
remain the host's responsibility. See [SECURITY.md](SECURITY.md).

- [Native installation and evidence boundaries](docs/native-v1.6.md)
- [Runtime reference](docs/advanced-usage.md) · [Windows scope](docs/windows-support.md)
- [Methods](content/methods/) · [Decision contract](docs/decision-points.md)
- [v1.6 implementation plan](docs/v1.6.0/IMPLEMENTATION_PLAN.md) · [Decisions](docs/v1.6.0/DECISIONS.md)
- [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

OpenSocrates is [MIT licensed](LICENSE), independent of OpenAI, Anthropic and
Google, and not endorsed by them.
