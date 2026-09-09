# Windows support — v1.4.0 candidate

This branch is an unpublished candidate. Do not use `opensocrates@1.4.0` from npm until publication. Windows support means native Windows processes, without WSL. Draft [PR #93](https://github.com/ParkerHwang/OpenSocrates/pull/93) tracks `codex/windows-v1.4.0`. The independent-review baseline and first CI run used `9e5ec5bd458e2d8c2b772b6074df25e0192d413e`; consult the PR for its current head.

## Requirements and installation

Windows x64 and Node.js 20+; the local test machine is Windows 11 Pro build 26200, Intel x64, PowerShell 7.6.5, non-administrator. Python is bundled in each native archive and is not required on the user's PATH. Windows ARM64, Windows 10, a separate clean computer, signing and SmartScreen reputation are unvalidated.

Authenticate in the host first. Claude Code was installed from its official installer (2.1.266); Codex CLI 0.153.4 supports the current configured model. The embedded SDK and its CLI remain version-matched at 0.144.4; this embedded binary is not a replacement for an up-to-date host CLI.

From a checkout or extracted npm package, use PowerShell:

```powershell
# Set these only when the host executable is not on PATH.
$env:CODEX_BIN = 'C:\path\to\codex.exe'
$env:CLAUDE_BIN = "$env:USERPROFILE\.local\bin\claude.exe"
node installer/opensocrates.mjs install --host codex --asset dist/opensocrates-1.4.0-codex-plugin-windows-x64.zip --checksum dist/opensocrates-1.4.0-codex-plugin-windows-x64.zip.sha256
node installer/opensocrates.mjs status --host codex
# Use the same local --asset and --checksum flags with update.
node installer/opensocrates.mjs remove --host codex
```

Replace `codex` with `claude` in the host and archive name for Claude. The installer checks the outer SHA-256, Windows ZIP path rules, target metadata and the complete inner file inventory. It preserves managed ownership markers and transactional rollback. Close active host tasks before update/removal: Windows can lock loaded executables. If replacement fails, preserve the reported backup, close the host, and retry; do not delete unrelated host configuration.

After publication, `npx --yes opensocrates@1.4.0 install --host codex` downloads the Windows archive automatically. Use `update`, `status`, `verify`, and `remove` through the same installer. The npm package includes the Windows helper; when downloading the standalone installer, keep `windows.ps1` beside `opensocrates.mjs`.

## Delivery and evidence

| Surface | Official Windows availability / conditions | This laptop |
| --- | --- | --- |
| Codex CLI | Native Windows; plugin hooks require interactive trust | CLI 0.153.4 returned 48 Korean methods through the installed native runtime in a real model session; hook approval is user-reported complete, while automatic CLI hook delivery remains unverified |
| Codex Desktop | Installed; local hook scripts and trust required | Desktop live delivery unvalidated; CLI evidence does not establish Desktop behavior |
| Claude Code CLI | Native Windows; authenticated host; Git for Windows recommended | 2.1.266 installed; login is user-reported complete, and paid-account live validation is deferred by the user |
| Claude Desktop / Cowork | Local versus remote execution is host-owned | Desktop installed; separate live delivery unvalidated |
| Cursor | Windows x64/ARM64 distributions; Agent Plugin requires compatible version | Not installed; OpenSocrates Windows integration unvalidated |
| Antigravity | Native Windows distribution | Desktop 2.12.2 / Gemini 3.8 Flash High: real installed skill and full Korean method read, response returned; CLI 1.1.28 validation and ZIP lifecycle passed |
| Grok Build | Official Windows PowerShell installer | Not installed; integration unvalidated |
| OpenCode | Native npm/release installation documented; vendor recommends WSL | Not installed; native bridge unvalidated; WSL is not accepted as Windows evidence |

Official references: [Codex Windows](https://developers.openai.com/codex/windows/), [plugins](https://developers.openai.com/codex/plugins/), [Claude setup](https://code.claude.com/docs/en/setup), [Claude hooks](https://code.claude.com/docs/en/hooks), [Cursor downloads](https://cursor.com/download), [Antigravity downloads](https://antigravity.google/download), [Grok Build](https://docs.x.ai/build/overview), [OpenCode installation](https://opencode.ai/docs/). Checked 2026-09-09.

The supported Windows runtime lane is decision-point retrieval (`node bin/launch.mjs decision codex` or `claude`) and discovery hooks after host trust. The retained legacy SDK credential-copy/on-demand POSIX context lane is unavailable on Windows and must fail closed; it is not needed for decision retrieval. Local transient state uses real owner/DACL validation, binary I/O and Windows file locks. The product adds no telemetry or credential collection.

Scheduled updates are **unavailable on Windows in 1.4.0**. `auto-update status` states this and `enable`/`run` fail with a manual-update instruction. No Windows scheduled task is installed. macOS LaunchAgent behavior is unchanged. A runtime/launcher failure remains fail-open for hooks.

## Native development and build

Use Python 3.12, Node 20+, and uv from [Astral's official distribution](https://docs.astral.sh/uv/getting-started/installation/). Run from the repository root:

```powershell
$env:PYTHONUTF8 = '1'
uv sync --locked --all-groups
uv run --locked python tools/generate_schemas.py
uv run --locked python tools/validate_content.py --output content/compiled-content.bundle.json --reasoning-projections-output content/compiled-reasoning-content.bundle.json
uv run --locked python tools/build_windows.py
uv run --locked python tools/check_windows.py --packages
uv run --locked ruff check src tools
uv run --locked ruff format --check src tools
uv run --locked mypy src
npm pack
```

The Windows workflow runs the native checks/build on `windows-2025`; existing Linux and Apple-silicon jobs remain. Release publication waits for the Windows job and verifies transported Windows checksums before including the new assets. The [first remote CI run](https://github.com/ParkerHwang/OpenSocrates/actions/runs/34316264162) did execute for commit `9e5ec5bd458e2d8c2b772b6074df25e0192d413e` and failed in Product contracts, GitHub and npx installer, and Native Windows x64. That hosted-runner result is separate from the earlier private Windows laptop evidence. The current remediation run, if any, and its exact head must be read from PR #93 rather than inferred from this historical baseline.

Evidence and outstanding full-suite failures are recorded in [the working record](windows-v1.4.0-worklog.md). POSIX fixture failures and unavailable authenticated checks must not be reported as passes. macOS has not been executed on this laptop.
