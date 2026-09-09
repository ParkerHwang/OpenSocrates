<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**A method for the judgment your agent is making.**

OpenSocrates brings 48 authored reasoning methods to Claude, Codex, OpenCode,
Grok Build, Cursor and Google Antigravity. Use it to examine assumptions, compare
options and weigh evidence while you work in your existing agent.

**English** | [한국어](README.ko.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![Release](https://img.shields.io/github/v/release/ParkerHwang/OpenSocrates)](https://github.com/ParkerHwang/OpenSocrates/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Website](https://opensocrates.parker-j-hwang.chatgpt.site) ·
[v1.3.1 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.3.1) ·
[Installation reference](docs/advanced-usage.md)

## Get started

Sign in to your host and make its CLI available. You need Node.js 20 or later.
The distributed native runtimes support **Apple-silicon macOS**; see each host's
support documentation before installing on another platform.

```sh
# Install for every supported, ready host
npx --yes opensocrates@1.3.1 install --host all

# Or choose one host
npx --yes opensocrates@1.3.1 install --host codex
npx --yes opensocrates@1.3.1 install --host claude
```

Start a new task after installation. In Codex, approve the OpenSocrates hooks in
an interactive session before relying on native discovery. OpenSocrates uses your
host's existing authentication and provider configuration; it needs no separate
OpenSocrates account or API key.

For an existing installation:

```sh
npx --yes opensocrates@1.3.1 update --host all
npx --yes opensocrates@1.3.1 status --host all
```

## What it does

- **Choose a method for a judgment.** Compare alternatives, check a causal claim,
  examine assumptions or decide which evidence would change a recommendation.
- **Revisit a decision when the facts change.** v1.3.1 supports method retrieval
  at multiple decision points within one request. Mechanical steps need no method.
- **Read the complete procedure.** Each method has authored instructions,
  examples, applicability limits and required public results, in English and Korean.
- **Keep the answer connected to its evidence.** Guided writing instructions
  preserve uncertainty, permissions and the user's format, with separate conclusions
  and reopening conditions for separate questions.

For example, ask your agent to compare two vendors under a fixed budget, reconsider
its choice after a new audit, or distinguish what a small pilot supports from what
it leaves unknown. These are use cases, not measured outcome guarantees.

## How v1.3.1 works

Claude/Codex hooks provide lightweight discovery guidance. The active agent then
uses the packaged native selector to retrieve eligible complete methods as needed.
If the runtime is unavailable, a constrained reference-file fallback remains.
Other hosts use the delivery paths below. OpenSocrates fails open when its
integration is unavailable so ordinary work can continue.

The release retains all **48 methods and 96 English/Korean procedure bodies**.
Its writing policy is guidance, not automatic rewriting. See
[decision-point retrieval and migration](docs/decision-points.md) for the exact
selection, fallback and method-availability contracts.

## Supported hosts

| Host | Delivery and entry point | Details |
| --- | --- | --- |
| Claude Code / Cowork | Plugin discovery where hooks run; `/opensocrates:opensocrates` | [Claude support](docs/decision-points.md) |
| Codex CLI / Desktop | Discovery after hook approval; `opensocrates` controller | [Delivery modes](docs/decision-points.md) |
| OpenCode | Local same-turn bridge; native skill fallback | [OpenCode support](docs/opencode-support.md) |
| Grok Build | Native skill selection or `/opensocrates` | [Grok support](docs/grok-support.md) |
| Cursor | Agent Plugin skill discovery or explicit invocation | [Cursor support](docs/cursor-support.md) |
| Google Antigravity | Explicit content skill | [Antigravity support](docs/antigravity-support.md) |

Claude web and Desktop Chat use a **separate standalone skill ZIP**, not the local
plugin hooks. Download it from the [v1.3.1 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.3.1)
and follow the [Chat installation guide](docs/claude-chat-upload-probe.md).

Chat standalone export: **archive contract validated; live activation unvalidated.**

## Privacy and support boundaries

The integration runs locally, adds no product telemetry and has no OpenSocrates
backend. Model requests still use your selected host service under its terms.
No separate OpenSocrates account is required. Read [SECURITY.md](SECURITY.md)
for the host trust boundaries and retained legacy adapter behavior.

v1.3.1 fixes multi-line decision input and checks packaged examples before release. Package verification
does not establish every host's live behavior or the model's actual application
of a method. Synthetic tests include final-delivery timeouts and repetitive output;
no general quality, naturalness, token-cost or response-time improvement is claimed.
The complete [release evidence](docs/v1.3.1-release.md) and
[publication verification](https://github.com/ParkerHwang/OpenSocrates/pull/92)
retain the measured results and limitations.

## More information

- [Detailed installation, updates, removal and runtime behavior](docs/advanced-usage.md)
- [Authored method catalog](content/methods/)
- [Changelog](CHANGELOG.md)
- [Contributing and development checks](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)

OpenSocrates is [MIT licensed](LICENSE). It is an independent open-source project,
not affiliated with or endorsed by its supported host providers.
