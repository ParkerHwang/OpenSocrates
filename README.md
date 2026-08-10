<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**English** | [한국어](README.ko.md)

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![Release](https://img.shields.io/github/v/release/ParkerHwang/OpenSocrates)](https://github.com/ParkerHwang/OpenSocrates/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

OpenSocrates is a local integration and authored reasoning framework for
Claude and Codex. It detects requests that benefit from deliberate reasoning,
uses a fresh host-native selector to choose relevant systems, and adds their
complete theory and examples to the active task. Straightforward factual and
mechanical work can pass through unchanged.

Version `1.1.1` includes 48 reasoning systems, one user-facing Claude entry,
coordinated Claude/Codex lifecycle management, and opt-in automatic updates on
Apple-silicon macOS (`darwin-arm64`). It uses your existing host login and does
not require an API key or an OpenSocrates backend.

## Host support

| Host surface | Automatic selection | User-facing entry | Validation status |
| --- | --- | --- | --- |
| Codex CLI and Desktop | Yes | OpenSocrates plugin | Release-validated on `darwin-arm64` |
| Claude Code CLI | Yes, through `UserPromptSubmit` | `/opensocrates` | Locally validated on `darwin-arm64` |
| Claude Code desktop app | Implemented, where Claude Code plugins run | `/opensocrates` | Implemented; no live probe receipt |
| Claude Cowork | Implemented, when the local plugin runtime is available | `/opensocrates` | Experimental; no live probe receipt |
| Claude web and Desktop Chat | No hooks | `/opensocrates` | Skills-only; upload path unvalidated |

The status column uses four distinct levels. Do not read them as
interchangeable:

- **Implemented** — the integration exists in code and ships in the package.
- **Locally validated** — exercised end to end on a maintainer machine, but
  not on every build.
- **Release-validated** — exercised by the release gate on every build.
- **Experimental / no live probe receipt** — implemented, but no captured
  receipt shows the host actually delivering the hook. `os capabilities show`
  reports these capabilities as `unknown`, not as available.

Claude Chat surfaces do not run plugin hooks. They can use the generated
skills, but automatic per-prompt selection is available only on Claude Code
and Cowork surfaces that execute the plugin runtime. OpenSocrates fails open
if a hook or selector is unavailable.

Cowork carries one further unverified assumption. OpenSocrates registers its
marketplace with `claude plugin marketplace add --scope user`, which writes
Claude Code user settings. Anthropic documents that plugin hooks run in Cowork,
but does not document that a marketplace registered through the Claude Code CLI
is visible to Cowork. Until a receipt exists, treat Cowork as experimental.

## Install

Before installing, sign in to the host and make sure its command is available:

- Claude: Claude Code `2.1.205` or later and the `claude` command;
- Codex: an OAuth-authenticated `codex` command.

Node.js 20 or later is required. The published `opensocrates` npm package is a
small, dependency-free installer. It downloads the matching package from
GitHub Releases and verifies the release checksum and every file checksum
before registering an owner-marked managed marketplace.

### Install every ready host

```bash
npx --yes opensocrates@1.1.1 install --host all
```

The all-host path detects supported, authenticated host CLIs, completes every
preflight before changing either host, verifies and stages both packages, and
then activates one release transactionally. If one activation fails, every
host already changed in that transaction is restored to its previous managed
registration.

Use the same host value for the complete lifecycle:

```bash
npx --yes opensocrates@1.1.1 status --host all
npx --yes opensocrates@1.1.1 update --host all
npx --yes opensocrates@1.1.1 remove --host all
```

A private `~/.opensocrates/desired-state.json` manifest records the selected
channel, installed hosts, and desired active version. `status --host all`
reports the desired and available versions, last check, last successful
automatic update, and per-host drift.

### Install one host explicitly

Codex remains the default host for backward compatibility:

```bash
npx --yes opensocrates@1.1.1 install
# Equivalent: npx --yes opensocrates@1.1.1 install --host codex
npx --yes opensocrates@1.1.1 install --host claude
```

Existing `--host codex` and `--host claude` lifecycle commands remain
supported. A host-specific update can intentionally create drift; a later
`update --host all` or successful automatic reconciliation brings every host
recorded in desired state back to one version.

### Opt-in automatic updates

```bash
npx --yes opensocrates@1.1.1 auto-update enable --host all
npx --yes opensocrates@1.1.1 auto-update status
npx --yes opensocrates@1.1.1 auto-update disable
```

Automatic updates are disabled until explicitly enabled. The macOS LaunchAgent
starts a bounded hourly poll; desired state applies the configured interval
(24 hours by default) with jitter and a single-instance lock. The job invokes
the selected npm channel, verifies release and package checksums, stages every
managed host, and reconciles them as one transaction. Major-version upgrades
are blocked by default; use `--allow-major` only when that policy is intended.

Passing one host to `auto-update enable` narrows only the automatic-update
scope. It never removes another installed host from desired state;
`status --host all` continues to track every installation, and a later
`update --host all` still reconciles the complete installed set.

The updater keeps a private receipt with version, time, per-host result, and an
error category only. It never records prompts, transcripts, credentials, or
workspace paths. `auto-update disable` unloads and removes the LaunchAgent;
`remove --host all` does the same before removing the managed hosts.

### Claude web and Desktop Chat skills

These surfaces support plugin skills but not hooks. Download
`opensocrates-1.1.1-claude-chat-skills.zip` from the release and upload it from
Claude's plugin customization UI. The package exposes exactly one
`/opensocrates` skill; its 48 method procedures, rigor, evidence, and trace
controls are internal supporting references. Automatic selection is absent
because Chat does not execute plugin hooks. See Anthropic's
[plugin surface guide](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).

### Install from a tagged GitHub source

The same host option works without the npm registry:

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.1.1 install --host all
npx --yes github:ParkerHwang/OpenSocrates#v1.1.1 install --host claude
npx --yes github:ParkerHwang/OpenSocrates#v1.1.1 install --host codex
```

### Manual release verification

Download `opensocrates.mjs`, the host package, and its `.sha256` file from the
[v1.1.1 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.1.1).
For Claude, for example:

```bash
shasum -a 256 -c opensocrates-1.1.1-claude-plugin.zip.sha256
node opensocrates.mjs install --host claude \
  --asset opensocrates-1.1.1-claude-plugin.zip \
  --checksum opensocrates-1.1.1-claude-plugin.zip.sha256
```

Replace `claude` with `codex` for the Codex package.

### Migrating a pre-1.0 Claude plugin

Some development builds used a case-sensitive marketplace named
`OpenSocrates`. The new marketplace is `opensocrates`. The installer detects
the old registration and refuses to remove it automatically. After reviewing
what is installed, remove it explicitly:

```bash
claude plugin uninstall opensocrates@OpenSocrates --scope user
claude plugin marketplace remove OpenSocrates --scope user
npx --yes opensocrates@1.1.1 install --host claude
```

Updating a managed v1.1.0 Claude installation replaces the complete package
tree. Its old 48 top-level method skills, `rigor`, `trace`, and duplicate
commands are therefore removed rather than left visible as stale entries.

## Use

Use Claude or Codex normally. Before a submitted prompt, OpenSocrates may
intervene when the request needs judgment, interpretation, diagnosis,
explanation, planning, evidence reconciliation, or another structured
reasoning process. When it intervenes, it:

1. starts a fresh, non-persistent selector in the current host;
2. chooses from the authored 48-system catalog;
3. writes the complete selected content to an owner-only temporary Markdown
   file; and
4. adds a small hidden context message telling the active task to read it.

There is no fixed selection-count limit. The selector has a 30-second internal
deadline, does not retry, and fails open. A timeout, host error, invalid output,
non-intervention decision, unsafe context, or unavailable hook produces no
injection and does not block the user's task.

On Claude, explicitly invoke the same controller when desired:

```text
/opensocrates <request>
/opensocrates auto <request>
/opensocrates trace
/opensocrates status
```

Only `/opensocrates` appears in Claude's skill and command UI. The controller
selects and loads internal method references; users do not need to browse the
48-system implementation catalog.

The Claude selector uses one `claude --safe-mode -p` process with no session
persistence. Safe mode disables user, project, and plugin customizations:
`CLAUDE.md`, skills, plugins, hooks, MCP servers, custom commands, and agents.
OpenSocrates additionally passes `--tools ""`, `--disallowedTools "mcp__*"`,
and `--strict-mcp-config` so that no built-in or MCP tool remains available. It
receives only the current prompt and the authored selection catalog.

Managed policy settings are part of the host trust boundary and are **not**
disabled by safe mode. Anthropic's
[CLI reference](https://code.claude.com/docs/en/cli-reference) states that under
`--safe-mode` "managed settings policy still applies, including
policy-configured hooks". On a machine where an administrator configures a
managed `UserPromptSubmit` hook, that hook runs inside the selector process,
receives the current prompt on standard input, and can return
`additionalContext` that enters selection. Managed plugins, managed skills,
managed `CLAUDE.md`, and policy-configured MCP servers do not load. If your
organization configures managed hooks, treat the selector prompt as visible to
them and disable OpenSocrates selection if that is unacceptable.

The Codex selector can additionally use bounded transcript context unless
disabled:

```bash
export OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS=0
```

## Privacy and security

OpenSocrates runs its integration locally and uses the existing Claude or
Codex login. Host model requests are still processed by the selected host
service under that service's terms. OpenSocrates does not host a backend, add
telemetry, store an API key, or execute the user's requested task.

Temporary instruction files contain authored OpenSocrates content only. Raw
prompts, transcripts, workspace files, tool data, credentials, and selector
reasoning are not written to OpenSocrates records, logs, metrics, diagnostics,
or instruction files. Turn files are removed on `Stop`, remaining session
files on `SessionEnd`, and crash leftovers older than 24 hours on
`SessionStart`.

When enabled, the updater stores only desired lifecycle state and the concise
receipt described above, under owner-only permissions. It does not inspect or
terminate running Claude or Codex sessions; a running task keeps its loaded
plugin, and a new task naturally loads the reconciled version.

See [SECURITY.md](SECURITY.md) for vulnerability reporting and the measured
support boundary.

## Develop

The source repository intentionally excludes native binaries and intermediate
build output. Install [uv](https://docs.astral.sh/uv/), Python 3.12, and Node.js
20 or later, then run:

Before merging a release candidate, follow the
[clean Apple-silicon Mac acceptance procedure](docs/clean-machine-acceptance.md)
to exercise the real authenticated Claude Code and Codex homes and return a
privacy-safe evidence bundle.

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

| Path | Purpose |
| --- | --- |
| `src/opensocrates/` | Shared Python 3.12 runtime and host-native selectors |
| `content/` | Policies, localized messages, methods, theory, and examples |
| `plugin-src/claude/` | Claude plugin templates |
| `plugin-src/codex/` | Codex plugin templates |
| `schemas/source/` | Canonical schema definitions |
| `schemas/v1/` | Generated, versioned public schemas |
| `installer/` | Dependency-free Node.js GitHub/npx installer |
| `tools/` | Build, validation, lifecycle, security, and release tools |
| `packaging/` | Native launcher and packaging configuration |
| `build/`, `dist/` | Generated locally and published as release assets |

Generated schemas and compiled content must be changed through their canonical
sources and generators. Release binaries belong in GitHub Releases, not in Git
history.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before
opening a pull request, and use the issue templates for bugs and feature
requests. The project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

OpenSocrates is available under the [MIT License](LICENSE). You may use,
modify, distribute, sublicense, and sell copies, provided the copyright and
license notice are preserved.

OpenSocrates is an independent open-source project and is not affiliated with
or endorsed by Anthropic or OpenAI.
