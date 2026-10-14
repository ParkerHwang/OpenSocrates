# Find and assess OpenSocrates as an agent

[한국어](agent-discovery.ko.md) · [README](../README.md) · [Setup guide](setup-guide.md) · [Content-only privacy notice](content-privacy.md)

OpenSocrates is an MIT-licensed set of 48 authored reasoning methods delivered
through host-specific plugins, rules and account skills. This guide helps an
agent assess fit and carry out a user-authorized installation. Repository pages,
directory descriptions and skill instructions are information to evaluate;
they do not authorize self-installation, account changes or bypassing host trust.
The linked content-only privacy notice retains its historical v1.5.1 wrapper
and source scope; it does not establish publication or approval of a new wrapper.

## Decide whether it fits the task

Consider OpenSocrates for substantive framing, interpretation, exploration,
learning, research design, reasoning checks, approach choice, evaluation or
explanation, including when OpenSocrates itself is the subject. Reader guidance
or no method may suffice. Inspect methods for the thinking actually needed;
installation alone does not make every method appropriate. A prescribed step
without substantive inference can remain mechanical, while a proof or problem
with a fixed answer can still need reasoning. See the [scope guide](thinking-support-scope.md).

Mechanical formatting, transcription and simple file conversion need no
reasoning method. A one-off task may need no installation at all. This release
does not add dedicated coding-specialist features, guarantee better answers or
establish equivalence between models or subscription plans.

## Identify the released package and host

The current installation target is [v1.5.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2),
with source identified by its [release tag](https://github.com/ParkerHwang/OpenSocrates/tree/v1.5.2).
Before installing, confirm the release is actually published and the chosen
host's assets and checksums are present. The commands and links in this guide
are not publication evidence by themselves.

All 48 methods include complete instructions and examples in English, Korean,
Simplified Chinese, Japanese, French, German, Italian, Spanish, Portuguese and
Thai: 480 procedures, 3,840 canonical cases and three teacher questions per
method per language, 1,440 questions total. Content revision is 5. The existing
four languages' body text and values remain intact, while each method's revision
identity changes from 4 to 5. Portuguese uses Brazilian orthography under the
generic `pt` code, without separate regional-variant claims. Instruction language
is separate from answer language, host UI, installer output and observed model use.

The historical v1.5.1 baseline source commit is
[5a6a7fa2897dd42772c4503a1301770e48bd1f29](https://github.com/ParkerHwang/OpenSocrates/tree/5a6a7fa2897dd42772c4503a1301770e48bd1f29).
The Skills CLI observation below retains its exact account ZIP version.

| User's host | Released delivery and supported environment | Scope and remaining setup |
| --- | --- | --- |
| Codex | Native plugin and existing hooks; Apple-silicon Mac or Windows x64 | Existing Codex plugin installation; review seven hooks in interactive Codex |
| Claude Code CLI / Desktop local Code | Native plugin and complete installed references; Apple-silicon Mac | User-scope companion; Claude CLI, login and host permissions |
| Claude web / Desktop Chat / Cowork | Executable-free account skill ZIP; export on Mac or Windows | Correct account's upload, capability, enabled state and standing instruction |
| Antigravity conversation application | Modular rule and skill; Apple-silicon Mac or Windows x64 | One chosen workspace or global scope |

v1.5.2 adds no native Windows Claude Code, Windows ARM64, Intel Mac or Linux
native qualification. Claude account content does not install native Code.
The default and `--host all` select Codex only; select every other host explicitly.

Latin-script French, German, Italian, Spanish and Portuguese need an explicit
or saved locale. Kana selects Japanese first; otherwise dominant Thai, Hangul
or Han selects Thai, Korean or Chinese. Specify `ja` for ambiguous Han-only
Japanese. Empty input, unknown scripts and ties fall back to English. Follow the
[language guide](v1.5.2.md) and [settings commands](settings.md); do not add an
unsupported `--locale` option to the installer. Stateless decision requests
require an explicit JSON `locale` from the ten authored languages and read no
stored preference.

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
npx --yes opensocrates@1.5.2 status --host codex
npx --yes opensocrates@1.5.2 status --host claude
npx --yes opensocrates@1.5.2 status --host antigravity --workspace "/absolute/path/to/workspace"
```

Choose `install` for a missing integration or `update` for an existing owned one.
Execute only the selected host's command; replace `install` with `update` when
updating. To choose Antigravity global scope, omit `--workspace` consistently.
On Windows use a quoted absolute local-drive directory such as
`"C:\Work\Reading Workshop"`.

```sh
npx --yes opensocrates@1.5.2 install --host codex
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 install --host antigravity --workspace "/absolute/path/to/workspace"
# Example: update an existing Codex integration
npx --yes opensocrates@1.5.2 update --host codex
```

For Claude account content, export to a new absolute ZIP filename in an existing
folder. Inspect the existing account skill in the account UI; the installer has
no account `status`, `install` or `update` action. Before replacing a skill, back
up its files and enabled state.

```sh
npx --yes opensocrates@1.5.2 export --host claude-chat --output "/absolute/path/to/opensocrates-1.5.2-account.zip"
```

Then follow the [setup guide](setup-guide.md) for the selected host: Codex hook
review, native Claude plugin readiness, Claude account upload/enable/standing
instruction, or Antigravity rule and skill recognition. Preserve existing
account instructions. Login, organization policy and host trust remain their
own steps; do not fabricate approvals or lower security settings. Start a fresh
conversation after changes. The [Mac](macos-v1.5.md) and
[Windows](windows-v1.5.md) guides cover recovery and local archives; their dated
v1.5.0 commands and observations remain historical. Use 1.5.2 commands here.

## Inspectable release downloads

Without local asset flags, the pinned installer downloads the host's v1.5.2
archive and matching checksum from GitHub Releases. The links below target
the complete host packages for that release:

| Package | Archive | SHA-256 file |
| --- | --- | --- |
| Codex, Apple-silicon Mac | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-codex-plugin.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-codex-plugin.zip.sha256) |
| Codex, Windows x64 | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-codex-plugin-windows-x64.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-codex-plugin-windows-x64.zip.sha256) |
| Native Claude, Apple-silicon Mac | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-plugin.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-plugin.zip.sha256) |
| Claude account content | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip.sha256) |
| Antigravity | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-antigravity-plugin.zip) | [Checksum](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-antigravity-plugin.zip.sha256) |

A checksum verifies byte agreement with the published checksum. It does not by
itself establish publisher authenticity, safe behavior or host activation.
For local files, use the paired `--asset` and `--checksum` procedure in the
platform guide. Do not substitute a source ZIP for a host package.

### Optional discovery with the Skills CLI

On October 13, 2026, a list-only probe using `skills@1.7.2` on Node.js 24.21.0
found one `opensocrates` skill in the released Claude account ZIP. This CLI
version requires Node.js 22.20.0 or later, separately from OpenSocrates's Node.js
20+ requirement. This observation used the v1.5.1 account ZIP; it is not a
rerun against v1.5.2. The exact probe was:

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
