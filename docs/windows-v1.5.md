# OpenSocrates v1.5.0 on Windows

[한국어](windows-v1.5.ko.md) · [README](../README.md)

Version 1.5.0 preserves Codex on Windows x64 and adds verified export of the
portable Claude account skill and owned Antigravity workspace/global lifecycle.
Claude's Windows surfaces are **web Chat, Desktop Chat and Cowork through
account content**. Native Windows Claude Code in a terminal or Desktop Code is
outside this release's scope. Apple-silicon native Claude and the other Mac
profiles have a separate [Mac guide](macos-v1.5.md).

## Install from the release

Use Windows 11 x64, Node.js 20+, Windows PowerShell, the chosen host and its
supported login flow. The native Codex runtime is bundled; Python is needed only
for source development/building. Without local asset flags, the pinned npm
installer downloads the v1.5.0 archive and SHA-256 file from
[GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.0).

Install Codex or update an existing v1.4 installation:

```powershell
npx --yes opensocrates@1.5.0 install --host codex
npx --yes opensocrates@1.5.0 status --host codex
# For an existing installation:
npx --yes opensocrates@1.5.0 update --host codex
```

Review the seven Codex hooks in an interactive session and start a fresh
conversation. Non-interactive sessions may skip untrusted hooks. `status`
reports installation and integrity, not host trust or automatic delivery.
Codex's existing Windows lifecycle details are in
[Windows support](windows-support.md).

## Claude account skill: web Chat, Desktop Chat and Cowork

Choose an existing, local, owner-controlled export directory. Replace the example
directory before running these commands. The exporter requires an absolute ZIP
filename and does not create its parent:

```powershell
$accountExportDirectory = (Resolve-Path -LiteralPath 'C:\Work\OpenSocrates Exports').Path
$accountOutput = Join-Path $accountExportDirectory 'opensocrates-1.5.0-account.zip'
npx --yes opensocrates@1.5.0 verify --host claude-chat
npx --yes opensocrates@1.5.0 export --host claude-chat --output $accountOutput
```

Verification performs no upload. Export preserves the verified ZIP bytes and
refuses an existing output with different bytes or an unsafe type. The parent
must pass Windows owner, access-control and reparse checks. CLI `install`,
`update`, `status`, `diagnose`, `enable`, `disable` and `remove` are not account
actions; manage the account skill in Claude's Customize > Skills interface.

Check that the account offers the required Skills/code-execution capability,
upload the standalone account ZIP, review it and enable it. If an OpenSocrates
skill already exists, back up that skill and its enabled state before replacing
it. Qualify the replacement while preserving the original backup. Do not upload a native Mac companion ZIP in place of the account ZIP.

Ask ordinary synthesis, decision or message-drafting tasks. The host model
selects the account skill; there is no hook or every-turn enforcement. An
explicit request to use OpenSocrates can diagnose a missed selection, but does
not prove automatic matching. Web Chat, Desktop Chat and current cloud Cowork
require separate observations. Successful export or upload is not proof of
selection, complete procedure reading, application or a useful result.

## Antigravity conversation application

Choose workspace or global scope. For a workspace, replace the example with an
existing absolute local-drive directory and use it consistently for every action:

```powershell
$workspaceDirectory = (Resolve-Path -LiteralPath 'C:\Work\Reading Workshop').Path
npx --yes opensocrates@1.5.0 verify --host antigravity
npx --yes opensocrates@1.5.0 install --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 status --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 diagnose --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 disable --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 update --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 enable --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 remove --host antigravity --workspace $workspaceDirectory
```

The installed workspace locations are `.agents/rules/opensocrates.md` and
`.agents/skills/opensocrates/`. Omit `--workspace` from lifecycle commands to
select the global default `%USERPROFILE%\.gemini\config`, with
`rules\opensocrates.md` and `skills\opensocrates\` beneath it. If
`ANTIGRAVITY_CONFIG_DIR` is set, that explicit configuration path is used instead.
Choose one active origin; global files may also be visible to the IDE.
`--workspace` is valid only for Antigravity; `--output` only for account export.

The standing `always_on` rule points to the complete controller and selectively
read EN/KO procedures. Describe the task normally without a repeated skill
command. File installation does not prove host discovery or result usefulness.

The driver creates missing managed directories with private permissions,
preserves unrelated `GEMINI.md`, `AGENTS.md`, rules and skills, and refuses
unowned or modified collisions. Update preserves disabled state. Disable moves
owned content out of active locations; enable restores it. Remove affects only
verified owned content. These profiles do not support addon purge, trust reset
or automatic updates. `--host all` continues to select the Codex lane.

Restart/reload Antigravity and start a fresh conversation in the **conversation
application**, then make an ordinary request. Disable/removal cannot erase
context already loaded into an existing conversation; test them in a new one.
Managed files or an IDE observation do not prove conversation-app discovery.
Workspace and global loading must be qualified separately.

## Safety, recovery and evidence limits

The Windows helper normalizes local drive paths before using extended Win32
paths internally. This supports Unicode/spaces and paths beyond 260 characters,
including deeper transaction backups, without changing OS long-path settings.
It does not relax ownership, DACL, junction/reparse or archive-containment checks.

Windows paths must have the expected owner and no untrusted write access.
Junctions, symlinks and other reparse points in managed paths or ancestors are
refused. Operations use an exclusive lock and pin ancestors against replacement;
activation failures attempt transactional rollback. Existing unowned directories
are not made safe by rewriting their permissions.

If an operation reports a preserved backup or a stale lock, retain the exact
reported path and inspect the verified ownership, inventory and inactive process
state before manual recovery. Do not recursively delete guessed or computed
directories or remove a lock while an operation may still be active. A failed
safety check is a refusal, not permission to force installation.

Source checks, archive integrity, installation, account activation, host loading,
complete procedure reads and useful outcomes are distinct. Web Chat, Desktop
Chat, Cowork, and Antigravity workspace/global loading depend on the actual
host/account and are not interchangeable. No universal model-quality, token-cost
or latency improvement is claimed. The [Windows observation record](../evals/v1.5-windows/REPORT.md)
and [Mac record](../evals/v1.5-macos/REPORT.md) preserve dated results and limitations;
they do not describe every current installation. This release adds no project
memory, transcript collection, coding-specialist method or broad orchestration.

See [SECURITY.md](../SECURITY.md) for product and host privacy boundaries and
[CONTRIBUTING.md](../CONTRIBUTING.md) for complete validation and release gates.

## When attribution appears

A final answer ends with the exact line `Powered by OpenSocrates` only when an
eligible authored method has been read in full and actually applied to that
answer. Use the same English wording in every locale. Reader guidance alone
and mechanical work do not qualify; the line is not proof of native application
or a better result.

## Contributor alternative: local archives


Use native Windows 11 x64, Node.js 20+, Python 3.12 and the locked uv environment.
Run these commands from the source checkout with LF files:

```powershell
git config core.autocrlf false
$env:PYTHONUTF8 = '1'
uv sync --locked --all-groups
uv run --locked python tools/build_windows.py
uv run --locked python tools/check_windows.py --packages
uv run --locked python tools/check_content_hosts.py
uv run --locked ruff check src tools
uv run --locked ruff format --check src tools
uv run --locked mypy src
npm run test:windows
node --test installer/managed-windows.test.mjs
npm pack --dry-run
```

Setting `core.autocrlf` does not convert an existing checkout; verify LF before
comparing pinned source hashes. The build produces these ZIPs and a same-name
`.sha256` companion for each, plus Windows SBOM evidence:

| Archive in `dist/` | Use |
| --- | --- |
| `opensocrates-1.5.0-codex-plugin-windows-x64.zip` | Existing native Codex Windows lane |
| `opensocrates-1.5.0-claude-chat-skills.zip` | One portable, content-only `opensocrates/` account skill |
| `opensocrates-1.5.0-antigravity-plugin.zip` | Portable `.agents/` rule and skill content |

The content-only filenames have no Windows suffix. They contain no runtime or
hooks. The Antigravity filename does not imply CLI plugin registration. Native
Windows Claude packages are not produced. Retain the separate Mac release gate;
a Windows build does not replace it.

For archives from `dist/` or the release page, pass paired `--asset` and
`--checksum` on install/update/verify/export. Resolve local files to absolute
paths before invoking the source installer. For example:

```powershell
$accountAsset = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-claude-chat-skills.zip').Path
$accountChecksum = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-claude-chat-skills.zip.sha256').Path
node installer/opensocrates.mjs verify --host claude-chat --asset $accountAsset --checksum $accountChecksum
node installer/opensocrates.mjs export --host claude-chat --asset $accountAsset --checksum $accountChecksum --output $accountOutput
```

Use the existing export directory and `$accountOutput` from the account section.
For Antigravity, select `opensocrates-1.5.0-antigravity-plugin.zip` and its paired
checksum and add both flags to the same lifecycle commands. If using the
standalone `opensocrates.mjs` release asset, keep verified `managed-hosts.mjs`
and `windows.ps1` beside it; the npm package includes these dependencies.
Local verification/export does not upload or activate an account skill.
