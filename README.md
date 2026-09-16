<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**A method for the judgment your Codex agent is making.**

OpenSocrates brings 48 authored reasoning methods to Codex. Examine assumptions,
compare options, and weigh evidence within the task you are already doing.

**English** | [한국어](README.ko.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Get started

Version **1.4.0 supports Codex only**, on **Apple-silicon macOS and Windows x64**.
Install Node.js 20 or later, make the Codex CLI available, and sign in to Codex.
The native runtime is bundled; users do not need Python.

```sh
npx --yes opensocrates@1.4.0 install
```

Start a new interactive Codex session and review the seven OpenSocrates command
hooks. Approve those hooks before relying on native discovery. Non-interactive
`codex exec` skips untrusted hooks; installation alone does not establish hook
approval or actual delivery. You can explicitly ask Codex to use the
`opensocrates` controller skill.

```sh
npx --yes opensocrates@1.4.0 status
npx --yes opensocrates@1.4.0 update
```

`--host codex` is optional. The compatibility alias `--host all` now means Codex
only. Other host names are rejected before installation or removal.

## Upgrading from a multi-host release

Claude Code, Cowork, Claude Chat, Antigravity, Cursor, Grok Build, and OpenCode
integrations and archives are removed in 1.4.0. Existing non-Codex installations
are not silently erased. If your previous desired state includes another host,
first use the version that installed it to remove that host, then update Codex:

```sh
# Example for an installation managed by 1.3.1:
npx --yes opensocrates@1.3.1 remove --host claude --purge
npx --yes opensocrates@1.4.0 update --host codex
```

Use the corresponding old host name for each retired integration. Review any
pending cleanup reported by the old installer. User conversation history and
unrelated files must be preserved. See [installation and removal](docs/advanced-usage.md).

## What it does

- Choose a method for a judgment: compare alternatives, check a causal claim,
  examine assumptions, or identify evidence that could change a recommendation.
- Revisit a decision when the facts change, including multiple decision points
  within one request. Mechanical steps need no method.
- Read complete instructions, examples, applicability limits, and required public
  results. All 48 methods retain their English and Korean procedure bodies.
- Keep conclusions connected to evidence, uncertainty, and reopening conditions
  while preserving the user's requested format.

Codex hooks provide lightweight discovery guidance. The active agent retrieves
eligible methods through the packaged native decision command. A constrained
complete-reference fallback remains when the runtime is unavailable. This path
makes no separate selector-model call and adds no prompt or transcript storage.
The integration fails open so ordinary work can continue when it is unavailable.
See [decision-point retrieval](docs/decision-points.md) for the exact contract.

## Platforms and limits

| Platform | Package | Updates |
| --- | --- | --- |
| Apple-silicon macOS | Native runtime and `bin/launch.sh` | Manual; optional macOS LaunchAgent |
| Windows x64 | Native `.exe` and `node bin/launch.mjs` | Manual only |

Windows does not require WSL or a Unix shell. Windows automatic updates,
Windows ARM64, Windows 10, macOS Intel, and Linux native packages are not claimed
as validated. Signing and SmartScreen reputation are unvalidated.
See the [Windows guide](docs/windows-support.md).

## Privacy and evidence

OpenSocrates runs locally, adds no product telemetry, and has no hosted backend or
separate account. Your ordinary Codex model requests use Codex authentication and
its service terms. Read [SECURITY.md](SECURITY.md) for integrity, rollback,
permissions, and the retained legacy selector boundary.

Package verification, hook delivery, complete reference reads, and actual method
application are distinct evidence levels. No general quality, token-cost, or
response-time improvement is claimed. Current release validation is tracked in
[PR #93](https://github.com/ParkerHwang/OpenSocrates/pull/93) and the
[release plan](docs/v1.4.0-release-plan.md); older evidence describes older versions.

- [Installation, updates, removal, and runtime reference](docs/advanced-usage.md)
- [Authored method catalog](content/methods/)
- [Changelog](CHANGELOG.md)
- [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md)

OpenSocrates is [MIT licensed](LICENSE), independent of OpenAI, and not endorsed
by OpenAI.
