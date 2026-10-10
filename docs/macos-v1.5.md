# OpenSocrates v1.5.0 on Mac

[한국어](macos-v1.5.ko.md) · [README](../README.md)

After installation, follow the [visual setup guide](setup-guide.md) for the remaining host steps or an agent-assisted setup request.

Version 1.5.0 preserves the original 48 authored reasoning methods and complete
English/Korean procedures. It adds reader guidance, native Claude Code entry,
a standalone Claude account skill, and Antigravity modular content. Codex
remains available. Windows x64 Codex, account export and Antigravity have their
own [Windows guide](windows-v1.5.md); Windows native Claude Code is outside scope.

## Install from the release

Use Node.js 20+, the chosen host, and its supported login flow. Native
Codex/Claude archives target Apple-silicon Mac and bundle their runtime;
installation needs no Python. The pinned npm installer downloads the v1.5.0
archive and SHA-256 companion from
[GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.0).
Local archive alternatives are described below.

For Codex, install or update the existing v1.4 installation:

```sh
npx --yes opensocrates@1.5.0 install --host codex
npx --yes opensocrates@1.5.0 status --host codex
# For an existing installation:
npx --yes opensocrates@1.5.0 update --host codex
```

Review the seven Codex hooks in an interactive session and start a fresh
conversation. Non-interactive sessions may skip untrusted hooks. `status`
reports installation and integrity, not host trust or automatic delivery.

## Native Claude Code

Make the Claude Code CLI available and sign in with its supported login flow.
Desktop local Code and terminal authentication/delivery are separate checks.
Install the native companion:

```sh
npx --yes opensocrates@1.5.0 verify --host claude
npx --yes opensocrates@1.5.0 install --host claude
npx --yes opensocrates@1.5.0 status --host claude
npx --yes opensocrates@1.5.0 diagnose --host claude
```

The driver owns the `opensocrates-macos` marketplace in user scope and confirms
the exact plugin version/enabled state. It preserves unrelated plugins/settings
and refuses an unowned collision. Review host permissions, then start a fresh
local Code session. Describe the task normally; repeated slash commands are not
required. Cloud/SSH/WSL Code sessions are outside this Mac native claim.

SessionStart and UserPromptSubmit emit bounded entry guidance and installed
controller/guide locations. The active agent reads complete eligible procedures
at materially changed judgments. The stateless entry reads no transcript,
initializes no database, and calls no extra selector model. Stop and SessionEnd
do not force a read-repair or assert native application evidence.

To update, run `npx --yes opensocrates@1.5.0 update --host claude`.
Update preserves disabled state. Lifecycle controls need no asset flags:

```sh
npx --yes opensocrates@1.5.0 disable --host claude
npx --yes opensocrates@1.5.0 enable --host claude
npx --yes opensocrates@1.5.0 remove --host claude
```

Reload/restart the host and verify the effective plugin origin/version. Removal
touches the owned registration/files, not the Claude application, account skill,
conversation history, or unrelated permissions. New profiles do not support
`--purge`, `--reset-trust`, or automatic updates.

## Antigravity conversation application

Choose one scope. For a workspace, pass an existing absolute directory every
time; use the same scope for status, update, disable, enable, and remove:

```sh
npx --yes opensocrates@1.5.0 install --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 update --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 status --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 disable --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 enable --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 remove --host antigravity \
  --workspace /absolute/path/to/workspace
```

Omitting `--workspace` chooses the global owned rule/skill under
`~/.gemini/config/rules/opensocrates.md` and
`~/.gemini/config/skills/opensocrates/`. Those global locations may affect both
the application and IDE; do not duplicate global and workspace entry.
`ANTIGRAVITY_CONFIG_DIR`, when set, overrides the default global base.
`diagnose` accepts the same scope as `status`. Update preserves disabled state.

The driver preserves `GEMINI.md`, `AGENTS.md`, unrelated rules, and modified or
unowned collisions. It moves disabled owned content out of active rule/skill
locations and records ownership for reversible lifecycle operations. Start a
fresh conversation in the **conversation application**, then ask normally.
Loaded context remains in an existing conversation after file disable/removal,
so a fresh conversation is needed to test those actions. File integrity or an
IDE observation does not prove conversation-app loading.

## Claude account skill: web Chat, Desktop Chat, Cowork

Export a verified standalone ZIP to a new absolute filename in an existing
owner-controlled directory. The exporter does not create its parent:

```sh
npx --yes opensocrates@1.5.0 verify --host claude-chat
npx --yes opensocrates@1.5.0 export --host claude-chat \
  --output /absolute/path/to/opensocrates-1.5.0-account.zip
```

An existing output with different bytes is preserved and reported as a conflict.
`verify --host claude-chat` validates the downloaded ZIP without uploading it. `install`, `update`, `status`, `diagnose`, `enable`, `disable`, and `remove`
are not account CLI actions; use the account's Customize > Skills interface.
`--output` is valid only for account export, and `--workspace` only for Antigravity.

Ensure the account's Skills/code-execution capability is available, upload the
standalone skill ZIP, review its contents, and enable it. If the name already
exists, first back up **only the existing OpenSocrates skill**, preserve its
enabled state, and qualify the replacement before deleting the original. Avoid
simultaneous duplicate controller origins in Code when account content syncs.
Upload acceptance is not activation or result proof.

Describe ordinary synthesis/decision/message tasks. Account matching is chosen
by the host model; a missed selection can be retried with an explicit request to
use OpenSocrates. Chat, Desktop Chat, and current cloud Cowork need separate
observations. The account ZIP does not provide native hooks or every-message
enforcement, and the native companion ZIP must not be uploaded in its place.

## Attribution and evidence boundaries

A final answer ends with the exact line `Powered by OpenSocrates` only after an
eligible authored method has been read in full and actually applied to that
answer. Use the same English wording in every locale. Reader guidance alone,
mechanical work, availability or emitted entry guidance do not qualify.
The footer is not a native application receipt or proof of improved results.

Source checks, archive integrity, installation, host loading, complete procedure
reads and useful outcomes remain distinct. CLI and Desktop local Code delivery,
web Chat, Desktop Chat, Cowork, and Antigravity workspace/global loading depend
on the actual host/account and are not interchangeable. This guide does not
claim universal answer-quality, token-cost or latency improvements. The
[Mac observation record](../evals/v1.5-macos/REPORT.md) preserves dated results
and limitations; it does not describe the current state of every installation.

The default and `--host all` continue to select Codex. The additional profiles
require an explicit host. Product and host retention boundaries are in
[SECURITY.md](../SECURITY.md); contributor verification and release gates are in
[CONTRIBUTING.md](../CONTRIBUTING.md).

## Contributor alternative: local archives

Contributors can build the same profiles from source on Apple-silicon Mac.
Use Python 3.12 and the locked uv environment in addition to Node.js 20+:

```sh
uv sync --locked --all-groups
make bootstrap
make generate
make release-check
```

The native gate assembles the existing Codex archive and then the additional Mac
profiles. Each archive in `dist/` has a same-name `.sha256` companion:

| Archive | Use |
| --- | --- |
| `opensocrates-1.5.0-codex-plugin.zip` | Existing native Codex Mac lane |
| `opensocrates-1.5.0-claude-plugin.zip` | Native local Claude Code companion |
| `opensocrates-1.5.0-claude-chat-skills.zip` | One content-only account skill folder |
| `opensocrates-1.5.0-antigravity-plugin.zip` | Modular workspace/global rule and skill |

The Antigravity filename does not mean a CLI-registered plugin: it contains
`.agents/rules/opensocrates.md` and `.agents/skills/opensocrates/`. The account
ZIP has an `opensocrates/` root, with no executable `bin/`, hooks, or runtime.
Inspect layouts without activating anything:

```sh
/usr/bin/zipinfo -1 dist/opensocrates-1.5.0-claude-plugin.zip
/usr/bin/zipinfo -1 dist/opensocrates-1.5.0-claude-chat-skills.zip
```

When using an archive from `dist/` or the release page, pass its paired
`--asset` and `--checksum` on install/update/verify/export. For example:

```sh
node installer/opensocrates.mjs verify --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs install --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
```

The source installer runs from this checkout. If using the standalone
`opensocrates.mjs` release asset, keep the verified `managed-hosts.mjs` dependency
beside it; the npm package includes that dependency. Local verification and
export do not activate an account skill or change host trust.
