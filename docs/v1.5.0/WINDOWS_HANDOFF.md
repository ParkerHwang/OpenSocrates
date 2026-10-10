# v1.5 Windows continuation after the Mac stage

The user requested Mac completion first, then Windows optimization. Continue
from the revised Mac implementation and its final Git commit/PR, not withdrawn
candidate #95. Original 48 methods and EN/KO canonical procedures remain intact.
Dedicated coding specialists, memory databases, credential-copy selection, and
broad orchestration are outside this release.

## Current boundary

Mac source includes native Claude hooks, content-only account/Antigravity
profiles, and an additive owned lifecycle driver. Existing Codex Windows x64
behavior is preserved. Its v1.4 CI/package evidence is **not proof of new host
Windows delivery**. New v1.5 native Claude Windows artifacts/launcher are absent;
`tools/build_plugins.py` rejects Claude `windows-x64`. The Claude POSIX launcher
and frozen root inference currently accept `darwin-arm64` only.

`installer/managed-hosts.mjs` deliberately rejects non-Darwin install/update/
status/diagnose/enable/disable/remove. Its offline verify/export model is portable,
but the main CLI's `prepareMacosProfilePackage()` still uses `/usr/bin/zipinfo`
and Mac archive tooling. Do not claim Windows CLI export merely because the
content bytes have no executable surface.

## First Windows work

The implementation branch is `feat/v1.5-macos`, not `main` or the withdrawn
`feat/v1.5.0-implementation`. On a fresh Windows machine:

```powershell
git clone https://github.com/ParkerHwang/OpenSocrates.git
cd OpenSocrates
git switch --track origin/feat/v1.5-macos
git rev-parse HEAD
```

Compare that commit with the implementation PR's latest verified head before
editing. This branch contains the preparation documents and Mac implementation
together, so no separate preparation cherry-pick is needed.

Use a focused checkout of the exact Mac integration commit, LF files, Windows
11 x64, Python 3.12, Node.js 20+, and the locked environment. Preserve the Codex
Windows baseline before extending any shared path:

```powershell
git config core.autocrlf false
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

These are baseline/build commands, not completed new-host acceptance. Check the
actual source's CLI help and report unsupported commands rather than inventing
Windows flags. Retain the Mac `make release-check` gate.

One integrator owns installer dispatch, package host lists, root preparation,
native build closure, version metadata, and CI. Host workers may own isolated
Claude normalization/launcher or Antigravity paths; do not let multiple writers
independently change those shared boundaries.

1. Split root preparation into a platform-safe archive seam. Validate outer
   SHA, every member, exact layout, regular files, no traversal/symlinks/reparse
   points, and bounded metadata before extraction. Keep native roots and the
   account ZIP's `opensocrates/` root distinct. Replace `/usr/bin/zipinfo -l`
   link detection with Windows-safe verification without broadening ownership.
2. Add an explicit native Claude Windows launcher/profile and `.exe` runtime
   closure. Reuse the host-neutral deterministic `decision` command and
   `claude-hook` contract; never route Claude to Codex `control`. Generalize
   installed-root inference only for verified layouts, never CWD or user payload.
3. Extend addon lifecycle after Windows owner/DACL, Unicode/spaces, binary I/O,
   locking, interruption, rollback, junction/race, and unrelated-settings tests.
   Keep purge/trust reset/automatic updates out of the new profiles.
4. Verify Antigravity conversation-app workspace/global paths and rule/skill
   loading on Windows separately from IDE and Mac observations. Portable account
   ZIP format, upload, automatic matching, complete reads, and result usefulness
   also remain distinct cells.

## Closure and handoff

Run ordinary synthesis, stakeholder-message, and decision cases with fixed source
notes. Check absence versus explicit refusal, keep known facts settled, and
preserve each question's missing input/reopening criteria. Record regressions
without regrading historical outcomes. Missing native application receipts do
not make a finished artifact incomplete.

For each claimed Windows host, record exact commit/artifact digest, host version,
capability state, entry observation, complete canonical reads, requested result,
and install/update/disable/remove/rollback preservation. CLI/Desktop, workspace/
global, and account/cloud surfaces require separate evidence. Attach unavailable
cells and their next action once; neither green Codex CI nor a Mac pilot closes
them. No npm/GitHub release publication is implied by Git push or local builds.
