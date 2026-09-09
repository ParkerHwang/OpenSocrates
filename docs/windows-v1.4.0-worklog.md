# Windows v1.4.0 implementation and validation record

## Resume point (2026-09-09)
- Base commit: `cce7f47ecab55b5d45e6d4844c793bc5306fa234` (origin/main, v1.3.1). No v1.4.0 existed at initial remote check.
- Branch: `codex/windows-v1.4.0`. No pre-existing changes were overwritten.
- User authorized branch push and a v1.4.0 PR on 2026-09-09 after local validation. Preparing a Draft PR because release evidence remains incomplete. Tags, merge, package publication and release publication remain unauthorized. Earlier entries below record the pre-authorization history.
- Candidate is NOT release-validated. Native package and explicit Codex live call passed; Claude paid-account testing, full CLI automatic hook coverage, remaining legacy checks and Mac release execution remain outstanding. Antigravity explicit-skill live delivery passed (see follow-up).

## Environment
Windows 11 Pro 10.0.26200, Intel Core Ultra 7 255H / x64, PowerShell 7.6.5, non-admin. Git 2.54.0 and Node 24.15.0 / npm 11.12.1 existed. Existing Python 3.14 was not used. Official Astral uv 0.12.11 and Python 3.12.14 installed under sibling `../toolchain/`; project `.venv` synchronized with locked all-groups dependencies. No machine PATH, developer-mode, administrator or unrelated settings changed.

Official Claude Code 2.1.266 installed at `$env:USERPROFILE\.local\bin\claude.exe`; authentication pending. Codex CLI 0.153.4 installed under `../toolchain/codex-host/node_modules`; existing ChatGPT login used without copying credentials. Bundled SDK and CLI remain pinned to the same 0.144.4. That older bundled CLI cannot use this account's configured newer model, and is not substituted for the host CLI. Codex Desktop, Claude Desktop and Antigravity were found installed; Desktop invocation is not inferred from CLI evidence.

## Completed implementation
- Windows x64 native Node launcher, PyInstaller runtimes for Claude/Codex and versioned ZIP/SHA-256 artifacts; no WSL.
- Platform-specific installer selection, PowerShell/.NET ZIP extraction, traversal/ADS/device/case-alias/symlink and resource bounds, full internal checksums, protected owner ACLs, existing transaction/ownership behavior.
- Python binary I/O, UTF-8 runtime streams, real owner/DACL/reparse checks, native file locks and key/artifact protection. Unix security scanning requirements retained.
- Windows auto-update explicitly unavailable, manual update instructions, no scheduled task silently created. macOS LaunchAgent paths retained.
- Legacy POSIX context/credential-copy SDK selector lane explicitly unavailable on Windows; primary decision lookup is independent of that lane.
- Windows CI/release artifact integration, source/platform identity validation, candidate release docs, English/Korean install/support boundaries.
- LF Git attributes and exact unchanged blob restoration fixed CRLF-sensitive canonical content checks. `git diff` shows substantive edits only; do not repeat the scratch restore script.

## Commands and results
Run from repository root in PowerShell, with `$env:PYTHONUTF8='1'`. Use `.venv/Scripts/python.exe` instead of global Python. If running uv, set `$env:UV_PYTHON_INSTALL_DIR=(Resolve-Path ../toolchain/python).Path` and use `../toolchain/uv/uv.exe`.

| Command / evidence | Actual native result |
| --- | --- |
| `python tools/build_windows.py` | PASS, two actual x64 PyInstaller ZIPs |
| `python tools/check_windows.py --packages` | PASS 7/7, final build; Korean/space and >260-character private artifact paths, no development Python PATH, PYTHONUTF8=0, catalog/selection/stream/hook, ACL, junction, lock, hostile ZIP |
| `npm run test:windows` | PASS 5/5, includes actual npm tarball extraction and helper |
| `npm pack --pack-destination ../../outputs` | PASS, final 1.4.0 candidate tgz |
| `ruff check src tools`; `ruff format --check src tools` | PASS |
| `mypy src`; `mypy --platform linux src` | PASS both, 153 source files |
| `python tools/security_scan.py` | PASS, original scanning rules unchanged |
| `python tools/build_sbom.py` | PASS, 22 locked packages |
| `python tools/check_links.py` | PASS 159 local links across 9 documents; external links not fetched by this check |
| `python tools/check_decision_points.py` | PASS 27 tests |
| `python tools/check_decision_hook_runtime.py` | PASS 7 tests, 4 explicit skips (POSIX/shell/UID/mode); Windows ACL equivalents run separately |
| `python tools/check_chat_archive_integrity.py` | PASS, 7 archive mutations; fixed native path separator assumption |
| `python tools/check_response_policy.py` | PASS 10 tests, 1 skip |
| `python tools/check_release_identity.py` | PASS 3 tests |
| `python tools/check_public_release_verification.py` | PASS 2 tests, preserves historical 1.3.1 inventory |
| `python ../check-release-merge.py` | PASS actual Windows ZIP merge, rejects changed checksum and source hash. Mac manifest fixture is synthetic, not Mac evidence |

Additional source runner `python ../source-checks.py` tested imports, generated contracts, adjudication (1854 checks), governance and mutation rules, Claude Chat evidence, product smoke and Antigravity/Cursor/Grok/OpenCode contracts: those passed. Logs and initial results are in `build/evidence/windows-source/`. Initial hook and Chat integrity failures in that JSON were subsequently fixed and rerun successfully as recorded above; retain initial results as history.

## Real distribution/host evidence
- Actual npm tarball unpacked at sibling `../distribution-cli`; installer from that directory installed, diagnosed and updated the real Codex registration from native ZIP.
- Standard removal and `remove --host codex --purge` succeeded; owned payload removed, unrelated user data and host trust preserved. Reinstalled afterwards.
- Holding installed runtime open with a native non-delete-sharing handle caused update rejection while preserving previous runtime and registration: `build/evidence/windows-locked-update.json`.
- Final rebuilt Codex ZIP updated successfully. `python ../live-codex.py` started a real authenticated Codex CLI 0.153.4 model session; it actually executed the installed launch.mjs/runtime and returned 48 Korean methods. Sanitized evidence: `build/evidence/windows-codex-live.json`. This proves explicit delivery, NOT automatic hooks.
- Both packaged runtimes execute without development Python/source in PATH. This is process-isolation evidence on this laptop, NOT a second clean-machine install.

## Remaining failures and unavailable evidence
- Original `npm test` baseline: 289 tests, 70 pass / 219 fail on Windows (POSIX host executable, mode and symlink fixtures); original suite retained for existing platforms. Native npm suite is separate, not a claim the original suite passed.
- `python tools/check_selector.py`: initial 6/23 failures were traced. Fixed synthetic POSIX paths and real >260-character artifact creation via extended Windows paths while preserving full HMAC tags. Focused rerun passes VSC-01D/01E/06B/06C; VSC-07 context and VSC-08 isolated SDK remain unavailable on Windows. Full rerun: FAIL 2/23 (only VSC-07 and VSC-08); see selector-final.log.
- `python tools/check_claude.py`: 7/26 fail: CLAUDE-02, 06, 06A, 06B, 08, 11, 17. CLI isolation/cancellation, legacy diagnostics/receipts and missing release evidence remain unresolved.
- `python tools/check_v12_adjudication_mutations.py` fails directory symlink fixture (WinError 1314, non-admin). Do not enable system developer mode to conceal this.
- Claude installer correctly rejected installation before authentication (real `auth status`: loggedIn false). Claude CLI login/live invocation, Codex automatic hook trust/live invocation, all Desktop UI and remaining hosts unvalidated.
- Mac native release gates, remote CI, Windows ARM64, Windows 10, second clean computer, code signing/SmartScreen reputation and public download/update were not validated. Local update tested same candidate replacement, not a published 1.3-to-1.4 server migration.

## Next actions
1. User runs Claude `auth login` directly (no credentials in chat), and opens Codex 0.153.4 interactively to approve the installed OpenSocrates hooks. See outputs authentication instructions. Do not alter trust files to bypass approval.
2. Validate Claude installation/removal/update and actual model/runtime response, and approved Codex automatic hook delivery. Record host version, event, runtime response and sanitized evidence.
3. Resolve remaining legacy regression failures or add rigorous platform-specific supported/unavailable assertions without weakening security checks.
4. Run Mac release gate and new Windows CI only after the user authorizes a remote workflow/push; record actual evidence. Validate other architectures separately.
5. Rebuild/retest when source changes, refresh artifact hashes and patch. Keep candidate unpublished until required evidence is complete.

## Final ZIP hashes
- `01351395861295c383244dab92f38476fd16f7f4d8f1a0f8264f095ca31633a9  opensocrates-1.4.0-claude-plugin-windows-x64.zip`
- `063aad4673be015c4bd6ddd6ac3111c0a95106f25709e107074bdbb313f1e0d3  opensocrates-1.4.0-codex-plugin-windows-x64.zip`

## Follow-up: authentication and hook approval (2026-09-09)
- User reports Codex hook approval completed and Claude login completed. User explicitly defers Claude Code/Cowork live validation until a paid account is available. Do not repeat Claude authentication or paid-service probes now; entitlement limitation is user-reported, not independently verified.
- Read-only native CLI feature check: hooks=true and plugins=true. OpenSocrates hook-specific trusted_hash records exist. No trust files changed.
- Current Codex Desktop task received the OpenSocrates decision-point developer entry after user approval. This is observed context delivery, not proof of every lifecycle event or method application.
- `python ../live-codex-hooks.py` ran a real CLI 0.153.4 ephemeral session without tool use or explicit launcher calls. Exit 0; model reported no decision-point entry. CLI JSON emitted no hook-specific events or errors. Automatic CLI hook delivery remains UNVERIFIED; do not infer it from trust config or Desktop context. Previous explicit runtime/catalog validation remains valid.
- No code, binaries, package hashes, trust or system settings changed in this follow-up. Existing legacy regression/Mac/CI limitations remain. Resume Claude only when the user supplies access; investigate CLI hook observability separately.

## Antigravity Windows live verification (2026-09-09)
- User requested Gemini/Antigravity validation. Existing Antigravity Desktop 2.12.2 was logged in, with Gemini 3.8 Flash High selected. Created an isolated `work/antigravity-live-test` project and synthetic prompt; no personal project files requested or modified.
- Installed official Antigravity CLI 1.1.28 from https://antigravity.google/cli/install.ps1 with `--skip-aliases --skip-path`, to LocalAppData/agy/bin/agy.exe. No PATH/profile edits. Set AGY_BIN only in task subprocesses.
- Built actual content-only candidate ZIP via `python ../build-antigravity-test.py`; SHA-256 ddf67480bd5a7a28f6e10ecddd7595e1d528911b6641bf160dc93f36e00137a8.
- Ran distribution installer `install/status/update/remove/status/install --host antigravity` using local ZIP and checksum; all succeeded. Removed status confirmed absence; final reinstall is present. Standard removal preserves shared installer state by design, not claimed complete purge.
- `agy plugin validate <home>/.gemini/config/plugins/opensocrates` passed: 1 skill, no agents/commands/MCP/hooks. `python tools/check_antigravity.py` passed (tier C, 48 methods, hooks=0/runtime=0).
- Actual Desktop tool history recorded SKILL.md L1-161, guide.ko.md L1-86, catalog.ko.json L1-2, value-of-information.md L1-72 and trade-off-analysis.md L1-72. Gemini returned a Korean answer and reported value-of-information@3. Full installed selected file has 71 lines; displayed read range covers it. Two methods were read although only one was requested/reported applied; reading is distinct from application.
- Confirmed scope: explicit installed content-skill discovery, complete selected method read and real Gemini response. No native runtime/hooks/automatic selection/application receipt or answer-quality improvement claimed. Gemini web/Gemini CLI are separate hosts, not tested here. Sanitized evidence: docs/evidence/antigravity-windows-live-2026-09-09.json. No screenshots/private sidebars/hidden reasoning saved.
- Claude remains deferred per user. Original Windows legacy regression, Mac and remote CI limits remain. No push, PR, tag or publication.
