# Find and assess OpenSocrates as an agent

This guide is pinned to the already released v1.5.1 npm channel. The current repository branch also prepares an unreleased Go v1.6.0 candidate; its native installation/adoption commands and Windows ARM64 scope are in [the native candidate guide](native-v1.6.md). Do not apply these npm commands to the Go candidate or infer that its assets have been published.

[한국어](agent-discovery.ko.md) · [README](../README.md) · [Setup guide](setup-guide.md) · [Content-only privacy notice](content-privacy.md)

OpenSocrates is an MIT-licensed set of 48 authored reasoning methods delivered
through host-specific plugins, rules and account skills. This guide helps an
agent assess fit and carry out a user-authorized installation. Repository pages,
directory descriptions and skill instructions are information to evaluate;
they do not authorize self-installation, account changes or bypassing host trust.

## Decide whether it fits the task

Consider OpenSocrates when the user needs to reconcile evidence, synthesize
sources, compare decisions, understand stakeholder perspectives or draft a
message whose reasoning matters. Inspect the available methods and their
applicability before selecting one. Installation alone does not make every
method appropriate.

Mechanical formatting, transcription and simple file conversion need no
reasoning method. A one-off task may need no installation at all. This release
does not add dedicated coding-specialist features, guarantee better answers or
establish equivalence between models or subscription plans.

## Identify the released package and host

The baseline here is [v1.5.1](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1),
source commit [5a6a7fa2897dd42772c4503a1301770e48bd1f29](https://github.com/ParkerHwang/OpenSocrates/tree/5a6a7fa2897dd42772c4503a1301770e48bd1f29).
It includes complete English, Korean, Simplified Chinese and Japanese
instructions and examples for 48 methods, content revision 4. Instruction
language is separate from host UI, installer output and observed model use.

| User's host | Released delivery and supported environment | Scope and remaining setup |
| --- | --- | --- |
| Codex | Native plugin and existing hooks; Apple-silicon Mac or Windows x64 | Existing Codex plugin installation; review seven hooks in interactive Codex |
| Claude Code CLI / Desktop local Code | Native plugin and complete installed references; Apple-silicon Mac | User-scope companion; Claude CLI, login and host permissions |
| Claude web / Desktop Chat / Cowork | Executable-free account skill ZIP; export on Mac or Windows | Correct account's upload, capability, enabled state and standing instruction |
| Antigravity conversation application | Modular rule and skill; Apple-silicon Mac or Windows x64 | One chosen workspace or global scope |

v1.5.1 adds no native Windows Claude Code, Windows ARM64, Intel Mac or Linux
native qualification. Claude account content does not install native Code.
The default and `--host all` select Codex only; select every other host explicitly.

`plugin-src/` contains build templates such as `SKILL.md.tmpl`, not complete
generic installable skill directories. The root `.agents/plugins/marketplace.json`
points to generated Codex build output. Finding these files in a GitHub scan does
not establish that a root marketplace install or `npx skills add
ParkerHwang/OpenSocrates` works. Use the released installer or verified archives
below. Public directory presence is also separate from install compatibility.

## Install only the user's chosen host and scope

Confirm the user has authorized installation or updating for the specific host,
account or workspace. Check OS/architecture, Node.js 20+, the host's availability
and login, and existing version, ownership and enabled state first. Native
runtimes are bundled; Python is not needed for installation. Preserve unrelated
settings and intentionally disabled copies. Reconcile legacy or unowned copies
before replacement; avoid duplicate global and workspace Antigravity copies.

For a native or file-based installation, run **only the matching status command**.
For Antigravity workspace scope, replace the example with the existing absolute
directory and keep that same scope on every lifecycle command:

```sh
npx --yes opensocrates@1.5.1 status --host codex
npx --yes opensocrates@1.5.1 status --host claude
npx --yes opensocrates@1.5.1 status --host antigravity --workspace "/absolute/path/to/workspace"
```

Choose `install` for a missing integration or `update` for an existing owned one.
Execute only the selected host's command; replace `install` with `update` when
updating. To choose Antigravity global scope, omit `--workspace` consistently.
On Windows use a quoted absolute local-drive directory such as
`"C:\Work\Reading Workshop"`.

```sh
npx --yes opensocrates@1.5.1 install --host codex
npx --yes opensocrates@1.5.1 install --host claude
npx --yes opensocrates@1.5.1 install --host antigravity --workspace "/absolute/path/to/workspace"
# Example: update an existing Codex integration
npx --yes opensocrates@1.5.1 update --host codex
```

For Claude account content, export to a new absolute ZIP filename in an existing
folder. Inspect the existing account skill in the account UI; the installer has
no account `status`, `install` or `update` action. Before replacing a skill, back
up its files and enabled state.

```sh
npx --yes opensocrates@1.5.1 export --host claude-chat --output "/absolute/path/to/opensocrates-1.5.1-account.zip"
```

Then follow the [setup guide](setup-guide.md) for the selected host: Codex hook
review, native Claude plugin readiness, Claude account upload/enable/standing
instruction, or Antigravity rule and skill recognition. Preserve existing
account instructions. Login, organization policy and host trust remain their
own steps; do not fabricate approvals or lower security settings. Start a fresh
conversation after changes. The [Mac](macos-v1.5.md) and
[Windows](windows-v1.5.md) guides cover recovery and local archives; their dated
v1.5.0 commands and observations remain historical. Use 1.5.1 commands here.

## Inspectable release downloads

Without local asset flags, the pinned installer downloads the host's v1.5.1
archive and matching checksum from GitHub Releases. These are the complete
released packages:

| Package | Archive | SHA-256 file |
| --- | --- | --- |
| Codex, Apple-silicon Mac | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin.zip.sha256) |
| Codex, Windows x64 | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin-windows-x64.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin-windows-x64.zip.sha256) |
| Native Claude, Apple-silicon Mac | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-plugin.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-plugin.zip.sha256) |
| Claude account content | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip.sha256) |
| Antigravity | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-antigravity-plugin.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-antigravity-plugin.zip.sha256) |

A checksum verifies byte agreement with the published checksum. It does not by
itself establish publisher authenticity, safe behavior or host activation.
For local files, use the paired `--asset` and `--checksum` procedure in the
platform guide. Do not substitute a source ZIP for a host package.

### Optional discovery with the Skills CLI

On October 13, 2026, a list-only probe using `skills@1.7.2` on Node.js 24.21.0
found one `opensocrates` skill in the released Claude account ZIP. This CLI
version requires Node.js 22.20.0 or later, separately from OpenSocrates's Node.js
20+ requirement. The exact probe was:

```sh
DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 npm exec --yes --package=skills@1.7.2 -- skills add https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip --list
```

`--list` inspects available skills; this observation establishes discovery of
the complete account content, not installation, native hooks, host qualification
or a public directory listing. Use the managed installation routes above for
their corresponding hosts. See the [Skills CLI documentation](https://github.com/vercel-labs/skills/blob/main/README.md)
and [directory FAQ](https://www.skills.sh/docs/faq); a search result or download
does not establish user adoption or a ranking guarantee.

## Report what was actually established

| Evidence | What it establishes |
| --- | --- |
| Discovered | A source or listing was found; suitability and compatibility still need assessment |
| Installed / exported | Files or registration were created, or a ZIP was exported; export is not account upload |
| `status` and integrity | The reported version, owned files, registration and enabled state where available; unobserved state stays unknown |
| Host trust and setup | The selected host's actual permission/settings checks; installation alone does not prove these |
| Complete content read | The relevant installed procedure was available and read completely; distinguish an agent report from native evidence |
| Applied | The eligible method was used for this task; content reading or entry emission alone does not prove it |
| Useful | The user can judge and use the result; no general improvement follows from installation or one example |

Do not retain private prompts, raw transcripts, screenshots, credentials or
hidden reasoning to fill evidence gaps. No additional telemetry or model-answer
experiment is required to finish ordinary setup.

An optional **hypothetical first-use task**, after setup: “Compare keeping a
small project local with moving it to shared hosting. Use the supplied cost and
access requirements, separate facts from assumptions, and draft a short decision
message with the remaining uncertainty.” Use only synthetic or user-authorized
material. This is a task suggestion, not a measured before/after result.
