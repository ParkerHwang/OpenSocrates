# OpenSocrates v1.5.0 on Mac

[한국어](macos-v1.5.ko.md) · [README](../README.md)

The Mac stage implements the original 48-method reasoning foundation, shared
EN/KO reader guidance, native Claude entry, a standalone Claude account skill,
and Antigravity modular content. Existing Codex support remains intact. These
are **local v1.5.0 candidates**, not published npm/GitHub release assets. The
new Windows profiles are the [next stage](v1.5.0/WINDOWS_HANDOFF.md).

## Obtain the local artifacts

Use Node.js 20+ for the installer. Native Codex/Claude archives target
Apple-silicon Mac and bundle their runtime. Building from source additionally
requires Python 3.12 and the locked uv environment:

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

Use the paired local `--asset` and `--checksum` on every install/update/verify
or export command below. Omitting them attempts a release download; v1.5.0 has
not been published. Run these commands from this source checkout.

## Native Claude Code

Make the Claude Code CLI available and sign in with its supported login flow.
Desktop local Code and terminal authentication/delivery are separate checks.
Install the companion through the source installer:

```sh
node installer/opensocrates.mjs verify --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs install --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs status --host claude
node installer/opensocrates.mjs diagnose --host claude
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

To update, replace `install` with `update` and supply the new local ZIP/checksum
pair. Update preserves disabled state. Lifecycle controls need no asset flags:

```sh
node installer/opensocrates.mjs disable --host claude
node installer/opensocrates.mjs enable --host claude
node installer/opensocrates.mjs remove --host claude
```

Reload/restart the host and verify the effective plugin origin/version. Removal
touches the owned registration/files, not the Claude application, account skill,
conversation history, or unrelated permissions. New profiles do not support
`--purge`, `--reset-trust`, or automatic updates.

## Antigravity conversation application

Choose one scope. For a workspace, pass an existing absolute directory every
time; use the same scope for status, update, disable, enable, and remove:

```sh
node installer/opensocrates.mjs install --host antigravity \
  --workspace /absolute/path/to/workspace \
  --asset dist/opensocrates-1.5.0-antigravity-plugin.zip \
  --checksum dist/opensocrates-1.5.0-antigravity-plugin.zip.sha256
node installer/opensocrates.mjs status --host antigravity \
  --workspace /absolute/path/to/workspace
node installer/opensocrates.mjs disable --host antigravity \
  --workspace /absolute/path/to/workspace
node installer/opensocrates.mjs enable --host antigravity \
  --workspace /absolute/path/to/workspace
node installer/opensocrates.mjs remove --host antigravity \
  --workspace /absolute/path/to/workspace
```

Omitting `--workspace` chooses the global owned rule/skill under
`~/.gemini/config/rules/opensocrates.md` and
`~/.gemini/config/skills/opensocrates/`. Those global locations may affect both
the application and IDE; do not duplicate global and workspace entry.
`diagnose` accepts the same scope as `status`. Update uses `update` with the
same archive/checksum flags as installation.

The driver preserves `GEMINI.md`, `AGENTS.md`, unrelated rules, and modified or
unowned collisions. It moves disabled owned content out of active rule/skill
locations and records ownership for reversible lifecycle operations. Start a
fresh conversation in the **conversation application**, then ask normally.
Loaded context remains in an existing conversation after file disable/removal,
so a fresh conversation is needed to test those actions. File integrity or an
IDE observation does not prove conversation-app loading.

## Claude account skill: web Chat, Desktop Chat, Cowork

Export a verified standalone ZIP to a new absolute filename:

```sh
node installer/opensocrates.mjs export --host claude-chat \
  --asset dist/opensocrates-1.5.0-claude-chat-skills.zip \
  --checksum dist/opensocrates-1.5.0-claude-chat-skills.zip.sha256 \
  --output /absolute/path/to/opensocrates-1.5.0-account.zip
```

An existing output with different bytes is preserved and reported as a conflict.
`verify --host claude-chat` with the asset/checksum validates locally without
upload. `install`, `update`, `status`, `diagnose`, `enable`, `disable`, and `remove`
are not account CLI actions; use the account's Customize > Skills interface.
`--output` is valid only for account export, and `--workspace` only for Antigravity.

Ensure the account's Skills/code-execution capability is available, upload the
standalone skill ZIP, review its contents, and enable it. If the name already
exists, first back up **only the existing OpenSocrates skill**, preserve its
enabled state, and qualify the replacement before deleting the original. Avoid
simultaneous duplicate controller origins in Code when account content syncs.
For a temporary test, agree on replacement/restoration first, then restore the
saved skill/state afterward. Upload acceptance is not activation or result proof.

Describe ordinary synthesis/decision/message tasks. Account matching is chosen
by the host model; a missed selection can be retried with an explicit request to
use OpenSocrates. Chat, Desktop Chat, and current cloud Cowork need separate
observations. The account ZIP does not provide native hooks or every-message
enforcement, and the native companion ZIP must not be uploaded in its place.

## Current practical evidence

Recorded during the 2026-10-07 Mac implementation; final exact-commit checks and
live cells must remain in the implementation handoff/PR.

| Cell | Observed result / next check |
| --- | --- |
| Local source/package | Claude contract checks 31/31; existing installer checks 245/245; new managed-host checks 17/17; Codex baseline/native gates passed. These are separate offline/package checks. |
| Claude CLI 2.1.285 | Actual user-scope companion registration confirmed. CLI authentication was unavailable and login requested; authenticated ordinary-task delivery remains pending. |
| Claude Desktop local Code, R1 | Read the reader guide. First output overstated a commitment and omitted the photography gap. Guidance was revised to keep absence unknown and avoid reopening known facts; retest pending. |
| Antigravity application, workspace R1 | Ordinary prompt led to controller/reader-guide reads and two usable stakeholder drafts. This bounded observation does not establish general improvement or global loading. |
| Account ZIP | Upload format accepted and replacement of the old skill requested. Existing skill's configured text names 1.1.2; its backup is complete. Temporary swap/restore authorization and live treatment remain pending. |

The R1 case combines five dated workshop notes, current capacity 24 versus old
35, a preference for 30 participants, tentative booking, and a check-in volunteer
without an agreed photography owner. A successful result preserves those
distinctions and gives each stakeholder relevant context and a specific next
request. No message sending or booking is part of the test. Pending practical
cells are not described as unimplemented source code.

`--host all` retains the Codex desired-state lane. Existing public v1.4 Codex
installation, trust, and Windows boundaries remain in the older version-specific
guides. See [SECURITY.md](../SECURITY.md) for product versus host retention and
[CONTRIBUTING.md](../CONTRIBUTING.md) for verification and publication gates.
