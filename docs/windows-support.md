# Codex on Windows — OpenSocrates 1.4.0

For the v1.5.0 candidate, Windows x64 native source/package qualification is tied
to final-commit CI. No live Windows Codex host is connected, so that cell remains
unavailable. This limits the live-support statement, not completion of other RC
work. The 1.4.0 instructions below remain the published-release reference; see the
[unpublished candidate handoff](v1.5.0/RELEASE_CANDIDATE.md).

OpenSocrates 1.4.0 supports **Codex on Windows x64**, using native Windows
processes. Other host integrations are removed. Windows ARM64, Windows 10,
signing, SmartScreen reputation, and a separate clean PC remain unvalidated.

## Installation and updates

Install Node.js 20 or later and the Codex CLI, then sign in to Codex. Python,
WSL, and a Unix shell are not required for the distributed package.

```powershell
npx --yes opensocrates@1.4.0 install --host codex
npx --yes opensocrates@1.4.0 status --host codex
npx --yes opensocrates@1.4.0 update --host codex
```

If Codex is not on PATH, set `CODEX_BIN` to its executable. The installer chooses
`opensocrates-1.4.0-codex-plugin-windows-x64.zip` automatically. For a verified
local candidate, supply `--asset <ZIP>` and `--checksum <SHA256-file>` together.
Review the seven OpenSocrates hooks in an interactive Codex session.

Scheduled updates are unavailable on Windows. `auto-update status` reports that
boundary; `enable` and `run` require manual updates instead. No Windows scheduled
task is installed. To remove the integration:

```powershell
npx --yes opensocrates@1.4.0 remove --host codex --purge
```

Purge preserves conversation history and hook trust. Add `--reset-trust` only
when you also intend to reset the seven OpenSocrates hook approvals. Unknown,
unsafe, or in-use data is preserved and reported as pending.

## Runtime and evidence

The archive contains `bin/launch.mjs` and the native Windows `.exe` payload.
Decision-point retrieval is the supported runtime path. Legacy SDK
credential-copy and POSIX context access are unavailable on Windows. Real
owner/DACL checks, binary I/O, locks, and archive-path validation protect local
artifacts. Hooks fail open when their runtime is unavailable.

The embedded SDK and CLI stay version-matched at 0.144.4; this binary does not
replace the user's host CLI. Native package fixtures are distinct from
interactive hook approval, authenticated delivery, and Desktop GUI evidence.
The current exact-commit results belong in [PR #93](https://github.com/ParkerHwang/OpenSocrates/pull/93).
Earlier Windows evidence remains [historical](windows-v1.4.0-worklog.md).

## Native build and verification

Use Windows x64, Python 3.12, Node.js 20+, and uv:

```powershell
$env:PYTHONUTF8 = '1'
uv sync --locked --all-groups
uv run --locked python tools/build_windows.py
uv run --locked python tools/check_windows.py --packages
uv run --locked ruff check src tools
uv run --locked ruff format --check src tools
uv run --locked mypy src
npm run test:windows
npm pack --dry-run
```

Windows Actions builds on `windows-2025`. Publication also requires the macOS
release gate and verifies the Windows transport checksums and package source
identity before merging the release inventories.
