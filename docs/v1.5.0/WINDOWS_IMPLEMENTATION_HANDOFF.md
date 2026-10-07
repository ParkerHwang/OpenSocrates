# Windows v1.5 implementation handoff

Current branch: `feat/v1.5-windows`. Base: verified Mac commit
`9eb2d2f90c9a17a7eee6db41a1c7f7c234ad761b` on `feat/v1.5-macos`, PR
[#104](https://github.com/ParkerHwang/OpenSocrates/pull/104), still open when
work began. No newer Mac head was present. The Windows Draft PR is stacked on
that branch. Use its latest head SHA and exact CI links for current verification;
this document's own Git blob belongs to that head. No PR #95 code/guidance was used.

## Current scope and ownership

The user narrowed Windows Claude to **Web Chat, Desktop Chat and Cowork account
skills only**. Do not restore terminal or Desktop local Code requirements from
the historical preparation handoff. Existing Mac native Claude remains unchanged.
No Windows native Claude launcher/runtime is added. `--host all` remains Codex.
No addon purge, trust reset, automatic update, coding expert, project memory or
broad orchestration is added. Main merge, tag, Release and npm publication need
a separate request.

The integrator owns common installer, build and CI changes. Independent agents
used the requested `gpt-6.1-sol` / `xhigh` settings for Windows test fixtures,
reader guidance, EN/KO documentation and public host research. No private prompts,
conversations, screenshots, credentials or hidden reasoning were retained here.

## Implemented

- Windows x64 Antigravity workspace/global install, update, status, diagnose,
  disable, disabled-state update, enable and remove; unrelated settings preserved.
- Portable Claude account ZIP build, manifest/canonical closure verification and
  exact-byte export, independent of Claude CLI/authentication.
- Windows .NET ZIP handling, captured checksum-verified archive, local absolute
  drive boundaries, explicit user owner/protected DACL creation, inherited foreign
  writer refusal, junction/reparse checks, operation lock and ancestor lease.
- Transactional recovery preserves changed replacement files and old backups.
  Interrupted operations leave a lock/recovery directory for explicit inspection;
  no automatic stale-lock deletion or force permission rewrite.
- Portable content ZIP regular modes fixed to 0644 on Mac and Windows; Windows
  SBOM covers Codex native archive and both content archives. Existing public
  v1.5 asset list stays 17; no nonexistent Windows Claude asset is listed.
- EN/KO reader fixes preserve absent-vs-unknown distinctions, settled facts,
  unresolved follow-up items and limits on draft promises. All 48 methods and
  96 canonical EN/KO procedure bodies remain unchanged.

## Commands and evidence

Use Python 3.12, Node >=20, locked uv and LF checkout. This machine ran Windows
11 Pro build 26300 x64, Python 3.12.15, Node 24.15.0. Full commands, pass counts,
failed attempts and live boundaries belong to the
[Windows report](../../evals/v1.5-windows/REPORT.md). User instructions and
PowerShell commands are in [English](../windows-v1.5.md) /
[한국어](../windows-v1.5.ko.md). Host paths/formats are supported by
[official documentation and installed bundle research](WINDOWS_HOST_RESEARCH.md).
The [original Mac handoff](WINDOWS_HANDOFF.md) and
[Mac observations](../../evals/v1.5-macos/REPORT.md) remain historical evidence.

The native Windows test found an ancestor lease bug: access=0 allowed rename.
The fixed handle requests FILE_LIST_DIRECTORY, excludes FILE_SHARE_DELETE, and
the real rename regression passes. The original failure is not discarded.
The old POSIX fixture installer tests are exercised on Linux/Mac CI; their
Windows run is not a native pass. Mac native build/release gates run in Mac CI.
Generated directories are ignored and rebuilt by their canonical generators.

## Live qualification and next actions

Consult the report before repeating a cell. Installation, entry, complete
canonical reads, actual application and artifact usefulness remain separate.
Web and Desktop use different accounts; no credentials are copied between them.
Account skill recovery must preserve original bytes or keep the original skill
intact with its enabled state restored. Native app input tooling could not target
the Antigravity window reliably; do not infer loading from managed files.

1. Review exact final CI head in the Windows Draft PR, including Linux source,
   installer and Mac native package jobs. Fix material failures before release.
2. With working native capture/input, qualify Antigravity workspace and global
   loading in fresh conversations using only the fixed synthetic sources.
3. Qualify Desktop Chat and Cowork with their own account origin and fixture
   results. Record Web observations independently; missing native grounding
   receipts do not invalidate an otherwise observed artifact.
4. Re-run affected R1/R2/R4/R5 cases after any reader repair; preserve earlier
   failures. A source contract pass does not regrade historical Mac outcomes.
5. After Mac #104 merges, explicitly rebase/retarget the stacked Windows PR.
   Run the exact new head gates. Publish only after separate release authorization.

## Recovery and limitations

Managed paths reject foreign ownership/writers rather than normalizing existing
settings. Export requires an existing owner-controlled parent; no parent is
created by export. Network shares and Windows ARM64 are unqualified. Existing
conversations may retain prior context after disable/remove; restart/reload and
use a fresh conversation. Restore backups only after confirming inventories,
ownership, inactive processes and the exact paths reported by the error.
Do not recursively delete a guessed path or a recovery tree containing unknown
files. Account skill matching remains model-selected, without every-turn hooks.

한국어 인계: 이번 범위는 Claude 계정 스킬과 Antigravity Windows x64입니다.
실제 앱 미검증 항목은 보고서에 남기며, 다른 계정·Mac 결과로 대체하지 않습니다.
다음 담당자는 이 문서와 PR의 최신 커밋·CI·검증 기록만으로 이어갈 수 있습니다.
