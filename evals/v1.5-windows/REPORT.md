# Windows v1.5 evidence report — 2026-10-07

Base: Mac `9eb2d2f90c9a17a7eee6db41a1c7f7c234ad761b`; Windows branch
`feat/v1.5-windows`. Exact final commit and CI are in the associated Draft PR.
Environment: Windows 11 Pro build 26300 x64, Python 3.12.15, Node 24.15.0,
locked uv environment, `PYTHONUTF8=1`, LF checkout.

## Scope and evidence levels

Windows native Claude Code is excluded by the user's revised scope, including
Desktop local Code. Existing Mac native Claude and Codex are retained. New
Windows profiles are Claude Web/Desktop Chat/Cowork account content and
Antigravity conversation-app modular workspace/global content.

Offline package/installer success does not prove host discovery. Entry delivery,
full canonical reads, application and useful final artifacts are measured
separately. No unavailable native application proof is made a completion gate.
Frozen [Mac failures](../v1.5-macos/REPORT.md) remain unchanged.

## Local validation

Initial existing Codex baseline passed: locked sync, native build,
`tools/check_windows.py --packages` (14 tests), `npm run test:windows` (5 tests)
and `npm pack --dry-run`. Completed checks and iteration boundaries are below.
The Draft PR records the final exact-head combined 18-case Windows run and CI.

| Check | Result |
| --- | --- |
| `uv sync --locked --all-groups` | Pass, Python 3.12 |
| `uv run --locked python tools/build_windows.py` | Pass: Codex runtime, two portable content archives, three-artifact SBOM |
| `uv run --locked python tools/check_windows.py --packages` | Pass: 16 tests, no skips |
| `node --test installer/managed-windows.test.mjs` | Earlier complete run: 11/11, no skips; final two parent guards: 2/2 focused pass |
| `npm run test:windows` | Earlier combined run: 16/16; final suite expanded to 18, exact-head result in PR/CI |
| `uv run --locked python tools/check_content_hosts.py` | Pass: 247 checks including canonical parity and portable ZIP modes |
| `uv run --locked python tools/check_claude_host.py` | Pass: 31 tests, 7 declared platform/privilege skips |
| `uv run --locked ruff check src tools` | Pass |
| `uv run --locked ruff format --check src tools` | Pass after final formatting repair |
| `uv run --locked mypy src` | Pass: 140 source files |
| `npm pack --dry-run` | Pass; no generated/private fixture content included |
| `tools/check_v12_adjudication_mutations.py` | Pass after portability repair: 83 validator scenarios + 30 coherent mutations; four real junction fixtures, zero skips |
| `tools/check_public_release_verification.py` | OK: 7 methods, 6 explicit skips (four privileged file-link cases, two Bash fixtures); 19 non-link addon byte/mutation subcases executed |
| `tools/security_scan.py` after source SBOM build | Pass; initial missing generic SBOM evidence repaired |

Canonical schema/content generators, Codex/Mac Claude generators and both
content-host generators ran. Git comparison shows no changes to compiled
canonical bundles, schemas, any of the 48 authored methods or frozen Mac evals.
Import boundaries, generated contract, committed adjudication, governance and
mutations, package documentation and mutations, response policy, release identity,
decision hook runtime, decision points and product smoke passed locally.
`check_packaged_launcher.py` could not run POSIX executable stubs on Windows
(WinError193). The retained legacy `check_selector.py` had two failures out of
23 cases in its POSIX context/credential-copy boundary, already unavailable on
Windows. Linux CI runs the full source suite; Mac CI runs native package/release
regressions. Neither is marked passed locally on Windows.

Native tests use new private synthetic directories, generated package clones
and existing-settings sentinels. They cover explicit current-user ownership,
protected DACL creation under an Everyone-writable parent, full lifecycle,
disabled-state update, Unicode/spaces/punctuation paths, unowned/changed files,
preserved operation locks, ancestor rename refusal, unprivileged junctions,
inherited foreign writer refusal without rewriting the DACL, a locked-leaf
rollback and mid-transaction replacement preservation with an old backup.
The account test verifies exact ZIP bytes, repeat export, conflicting output
preservation and no CLI/auth/settings access.

Retained iteration failures: the first native suite had 9/11 passes. One failure
exposed the access=0 ancestor lease; FILE_LIST_DIRECTORY fixes it and the 11/11
passes. The other was an old test assertion expecting `content-export`; the
existing contract is `export-only`, corrected and retested. Initial export to a
broadly writable parent was safely refused; export to a newly created protected
child succeeded. A Windows run of old POSIX fixtures failed due to POSIX mode/
executable assumptions and unsealed fixtures; it is not reported as a pass.
Additional hardening tests found that unsafe mutation parents were refused only
after staging. Parent checks now run before staging, and the unchanged-DACL/full
settings-inventory test passes with no residue. Separate held parents prevent
renaming rules, skills and metadata during activation. A directory-junction
fixture also exposed missing reparse checks in two historical adjudication
publishers; their unresolved-path validation now rejects junctions and all four
overwrite/ancestor fixtures pass. File-symlink privileges were not enabled to
manufacture coverage; privileged cases are explicit skips.

The first Draft PR CI run at `be125168a0b960c04dc5edf23a0c8e1c120c7b79`
failed two installer checks. The closed npm publishing contract still named only
the old Windows suite; it now includes the managed Windows suite exactly as
`package.json` does. A synthetic rejected-app-server fixture could be killed
before its EOF trace was written on a busy runner. Its test-only termination
grace is now 500 ms; production limits and the separate bounded-timeout test
are unchanged. The [initial failed run](https://github.com/ParkerHwang/OpenSocrates/actions/runs/37584772262)
is retained; the Draft PR records the corrected final-head run.

## Artifact identities

Portable final content ZIPs use fixed regular 0644 modes on both platforms:

| Artifact | SHA-256 |
| --- | --- |
| `opensocrates-1.5.0-claude-chat-skills.zip` | `a7fed8155dd209ee3b5ec4c4249a81dc68d66d36e715d23858f5075a9c68244f` |
| `opensocrates-1.5.0-antigravity-plugin.zip` | `327809e06876ca59efec879f3e18ff84203692ff0d49a17b73c2f0d4210f30c7` |

Earlier pre-normalization Antigravity UI staging used the digest retained in
[its observation](antigravity-observations.json); no model was invoked. Archive
normalization changes transport metadata only, not staged controller/procedures.

## Live host matrix

| Windows cell | Installation/export | Ordinary entry / reads / application / result |
| --- | --- | --- |
| Existing Codex | Native package regression verified | Authenticated Desktop/host outcome not newly measured here |
| Claude Web Chat | Account ZIP verified/exported; account signed in | Upload unavailable; no candidate model request |
| Claude Desktop Chat 2.26454.0 | App present | Native UI input unavailable; no candidate request |
| Claude Cowork | Separate account from Web | No candidate request; not inferred from Web |
| Antigravity 2.19.1 workspace | Managed files verified in separate synthetic folder | Native capture/input unavailable; zero model requests |
| Antigravity global | Native filesystem lifecycle verified in private settings fixture | App loading/results unavailable; no active global account settings touched |

The Antigravity helper's window capture showed another foreground app and
rejected geometry-dependent input. The bounded retry stopped before project
creation or any model request; all R1–R5 remain unavailable for that cell. This
is a measurement blocker, not a demonstrated OpenSocrates discovery failure.

## Reader regression coverage and recovery

[Fixed EN/KO cases](fixtures/cases.json) and [synthetic sources](fixtures/sources.md)
cover synthesis/stakeholder drafts, changed capacity, mechanical table, settled
private-draft decision and changed-date follow-up. Reader guidance now separates
source absence from real-world absence, carries prior unknowns across updates,
keeps supplied facts settled, and forbids unapproved duties/promises/deadlines.
These are source contract changes; live regrading requires a host result.

For account recovery, the original active OpenSocrates skill was kept intact.
Its Download action was attempted, but the browser download event timed out.
The browser policy refused internal downloads-manager navigation; no workaround
was used. A distinct `opensocrates-windows-synthetic-test` copy was then created
and immediately disabled. Replace was opened on that copy only, but selecting
the verified candidate ZIP failed because the Chrome ChatGPT extension lacks
"Allow access to file URLs". No ZIP was uploaded and no model request was made.
A native file-picker alternative stopped before input because the native helper
could not determine the browser URL sufficiently to enforce policy. No more
computer input was attempted in that turn. The original remained enabled;
the temporary copy remains disabled. No other account skill or conversation
was changed, and no old guide was adopted as an implementation baseline.

The user confirmed the Web account differs from the Desktop app account.
This Web attempt cannot qualify Desktop Chat or Cowork. A future authorized
operator can upload the candidate to the disabled test copy after allowing
file uploads in the browser extension, test fixed cases with the old origin
temporarily disabled, then restore the old enabled state. Remove the disposable
copy only with the required UI deletion confirmation.

The account recovery decision used the complete installed Korean
`premortem-analysis` revision 3 after the native decision lookup returned
unavailable. Single observer, same-day horizon; failure means an unrestorable
original or a false host claim. The observed unconfirmed backup threatened the
restore dependency. Assumed risks were ambiguous same-name origins, an upload
failure leaving the old skill off, and policy/input loss during cleanup. Their
early signals were duplicate origins, a refused upload and missing target state;
mitigation was retaining the original intact, disabling only the separate copy,
and stopping account mutation at the policy refusal. The integrator owns those
controls. Current decision: proceed with implementation/GitHub delivery while
holding live account qualification. Resume only with reliable upload/input and
an explicit restore path; no numerical failure probability is claimed.

## Resume

Use [implementation handoff](../../docs/v1.5.0/WINDOWS_IMPLEMENTATION_HANDOFF.md),
[Windows commands](../../docs/windows-v1.5.md) /
[한국어 안내](../../docs/windows-v1.5.ko.md), and
[public host research](../../docs/v1.5.0/WINDOWS_HOST_RESEARCH.md).
The next native operator needs reliable app targeting for Antigravity and
Desktop/Cowork. Use fresh conversations and the fixed synthetic sources; do not
copy credentials, read private history, replace an unbacked original skill, or
upload private traces. Main/Release/npm remain unpublished.
