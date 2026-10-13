# v1.6.0 implementation and release handoff

Tracking: [implementation issue #111](https://github.com/ParkerHwang/OpenSocrates/issues/111) and [Draft PR #112](https://github.com/ParkerHwang/OpenSocrates/pull/112). Preparation PR #110 and issue #109 remain separate. Reconciled main base: 9572db2c71a455d4ada24c78402d0f874002cec9. Branch: codex/v1.6-go-native.

## Completed implementation

| Package | Completed scope |
| --- | --- |
| V0 | Reconciled released v1.5.1 baseline, 48 methods, EN/KO/ZH/JA, revision 4 |
| V1–V2 | Typed Go contracts, services, content, domain, decision, runtime CLI and persistence |
| V3 | Native OS protection and pinned external Codex app-server compatibility |
| V4–V5 | Shared lifecycle journals, transport, host registration, native management and npm adoption |
| V6 | TUF trust, opt-in stable scheduling, versioned bundles and journaled self-update/recovery |
| V7 | Go generation, package/release tooling, governance/validation, CI and bilingual documentation |
| V8 | Source checks, compatibility comparison, native acceptance, specialist review and durable handoff |

The user subsequently added **Windows ARM64** to v1.6.0. It has separate native binaries, PE/build checks, signed target selection, helper/installer paths, publication assets and native CI. This is a material user-directed adjustment to the original two-platform plan. Codex and Antigravity retain their profile boundaries; native Windows Claude Code is excluded and --host all still means Codex. Claude account upload/activation remains separate.

Methods, teacher questions, response policies and shared guides now freeze released v1.5.1 tag source 5a6a7fa2897dd42772c4503a1301770e48bd1f29, revision 4 and EN/KO/ZH/JA. Original v1.5.0 EN/KO procedures and cases remain byte-identical. Compiled product metadata becomes 1.6.0. The separate method-body session and unreviewed v1.5.2 inputs were not modified or imported. Historical revision-3 evidence below retains its original source and does not qualify new revision-4 files. See [baseline](CONTENT_BASELINE.json) and [intentional changes](DECISIONS.md).

## Exact evidence

## Released v1.5.1 reconciliation

The original Go preparation and all revision-3 receipts retain their historical
source identity. After release v1.5.1, merge current main
`5a6a7fa2897dd42772c4503a1301770e48bd1f29` into the existing PR branch, retain
the native Go tooling/workflows and VERSION 1.6.0, and port released four-locale
runtime behavior. Canonical/schema generation now targets revision 4,
EN/KO/ZH/JA, 192 complete references and 576 teacher questions. Exact baseline
hashes are in [CONTENT_BASELINE.json](CONTENT_BASELINE.json). / 초기 준비와
리비전 3 기록은 그대로 보존하고 출시된 v1.5.1을 병합·포팅했습니다. Go 실행·개발
경로와 1.6.0 버전은 유지하며 네 언어의 전체 참조와 질문을 생성합니다.

Native locale get/set/reset, explicit/stored/text selector precedence,
four-language complete references and strict versioned package verification
address observed regressions. Legacy v1.5.0/96-reference and v1.5.1/192-reference
fixtures preserve preferences, disabled state, foreign data and rollback.
Default decision and Claude entry remain stateless. / 언어 명령·이전 선택기 우선순위·
완전한 참조·버전별 패키지 검사와 설정·꺼진 상태·다른 파일·복구 보존을 반영했으며
기본 판단과 Claude 진입에 설정·대화 읽기를 추가하지 않았습니다.

Source and platform qualification for this new merge must be recorded at its
own commit. Prior 9be0e5e hosted Mac notarization does not qualify these new
revision-4 bytes. Current main requires the maintenance pipeline's six legacy
checks; preserve that shared policy while the separate v1.5.2 work is active,
then coordinate the final Go check transition. v1.5.2's FR/DE/IT/ES/PT/TH are
pending, not this baseline; recheck publication before final v1.6.0 release.
/ 새 소스의 검증은 새 SHA에 기록하고 과거 공증을 재사용해 새 파일이 통과했다고
주장하지 않습니다. v1.5.2 진행 중 공용 보호 정책은 보존하고 최종 Go 전환을
조정합니다. 미출시 6개 언어는 포함했다고 주장하지 않습니다.

## Historical exact evidence

Historical native evidence for the resumed large-payload fix: **bc151afdb9a9d6845906b05ec2efb022961fd45f**. [CI 38239135183](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38239135183) passed source and actual macOS ARM64, Windows x64 and Windows ARM64 execution after the resumed large-payload fix. Git tree `29d6306880d0e09f42b59bdbc78cfbe816ad02c4` matches all three native provenance receipts. The documentation/evidence follow-up does not relabel these observations as a new execution.

Earlier [CI 38219463804](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38219463804) passed source and actual macOS ARM64, Windows x64 and Windows ARM64 execution. The first Windows x64 attempt reached the outer lifecycle acceptance deadline after 30.006 seconds during install, with empty output; the same commit passed when only that failed job was rerun, with unchanged deadlines. This observation does not establish the cause of the initial timeout. Earlier complete native runs [38218166860](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38218166860) at 6011249 and [38216709561](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38216709561) at d156c27 also passed. [Retained receipts](evidence/README.md) keep their original revisions; documentation does not relabel old results.

Commands/results:

- make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check security-scan smoke installer-check: all passed at bc151af on macOS ARM64 with Go 1.27.2. make release-check exited 2 (Make), failed closed with production platform signature required; this is not a release-check pass.
- The actual v1.5 Windows archive contains a 341,142,832-byte Codex executable, exceeding the initial Go 256 MiB lifecycle cap. bc151af corrects the per-file cap to 512 MiB while retaining 2 GiB/10,000-entry bounds, and streams guarded hashes/recovery copies. The exact-size synthetic copy regression, over-limit rejection and streaming security tests passed in all native source suites. Bounded final code/security reviews found no actionable findings; the evidence audit classified release acceptance PARTIAL.
- [Windows ARM64 actual-payload adoption](evidence/native-npm-adoption-windows-arm64-bc151af.json): Go adopt/status/recover exited 0 at bc151af using the authentic v1.5 Windows x64 ZIP and an integrity-matched actual npm TGZ installed under a private prefix. Disabled state, settings/trust/unknown JSON fields, npm bytes and exact payload/registration rollback passed. Overall qualification remains **PARTIAL** because the original unchanged v1.5 installer exited 1 with `Foreign owner refused` in this elevated VM's owner environment. The legacy layout was explicitly initialized from the verified release with its source-equivalent schema. The [frozen reproducer](evidence/qualification/windows-actual-payload/README.md) and [artifact receipt](evidence/native-npm-adoption-artifacts-windows-arm64-bc151af.json) bind source, native ARM64 PE identity and actual transferred bytes. Local cross-built and CI-built artifacts retain separate hashes.
- make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check package-check smoke installer-check: preparation/static/generated/content/docs/governance/package passed at 6498fd6. A new package test compared an in-memory typed array using JSON-only helpers; it was corrected to inspect serialized output. The affected runtimecli/devtools go test and make installer-check passed after correction. Complete source/behavioral CI passed at d156c27.
- make package TARGET=windows-arm64: artifacts assembled. Cross-build alone is not runtime evidence; native ARM64 CI subsequently executed the binaries.
- Native CI ran go test ./src/opensocrates/..., build, package, check package, acceptance lifecycle, acceptance timing and acceptance scheduler. Lifecycle covers install/status/update/disabled-state/removal/interruption/recovery/rollback and synthetic npm adoption. Windows runs actual packaged Go helpers for manager/helper replacement and interrupted activation.
- Exact generated hooks passed Unicode/space/dollar/backtick paths, 20 startup and 20 compact samples, each below two seconds and p95 at most one second. The development-test executable has separate checked Windows shell setup; packaged timing has no warmup, retry or excluded sample.
- Actual per-user Mac LaunchAgent and Windows Task Scheduler registration/Go execution/owned cleanup passed. Windows captured XML export/import restoration passed. Go encodes OS imports as UTF-16 while state remains UTF-8; defaults/durations/OS-resolved aliases do not authorize foreign changes.
- [Differential comparison](evidence/go-v1.5-compatibility.json): 1,055 synthetic decision responses, all 48 methods/locales, nine rigor commands, 21 control cases and ten affected control-root rechecks passed at c5a822c6. Unchanged runtime sources support reuse; four intentional differences remain documented.
- [Authentic npm payload adoption](evidence/native-npm-adoption-darwin-arm64.json) passed on Mac at c5a822c6 using the actual v1.5.0 ZIP and original entry installer with isolated HOME/Go host fixture. Exact bytes/modes/state/trust/disabled state were preserved and restored; the legacy scheduler was disabled.
- [Enabled legacy-updater takeover](evidence/native-npm-enabled-updater-darwin-arm64.json) passed on macOS ARM64 at 3724bf8. The original installer and actual release ZIP registered a real unique disposable LaunchAgent; Go adoption replaced its legacy arguments with the native updater and retained one update owner. Recovery restored the live legacy identity, original policy/plist/desired-state/payload bytes, settings, trust, key and disabled integration. The fixed label was mapped to a unique test label and RunAtLoad suppressed only in its OS copy; Codex/npx were Go fixtures. Actual updater execution, login/network triggers and the production fixed-label installation are outside this observation.
- Five-second Go fuzz runs passed for archive paths, trust reset and safe relative transport. Bounded final reviews found no remaining actionable findings after fixes.
- Read-only gh api repos/ParkerHwang/OpenSocrates/immutable-releases --jq '{enabled}' returned enabled:true. This does not provision the publication environment's separate Administration-read credential.

The user VM is Windows 11 ARM64. Its [native lifecycle](evidence/native-vm-windows-arm64-lifecycle.json) and [native scheduler](evidence/native-vm-windows-arm64-scheduler.json) passed with verified ARM64 artifacts, including packaged helper replacement/recovery. Earlier x64-emulation observations are supplemental. A contaminated disposable Mac transfer ZIP was rejected for 465 AppleDouble extras; the unchanged payload passed after metadata-free transfer into fresh staging. All temporary scheduler tasks were removed. Older diagnostic folders without a byte-identity sidecar were retained intentionally; modified/unverifiable files are never deleted indiscriminately. Existing installations, accounts, settings and trust decisions were preserved.

## Additional release preparation at 306b74c

[CI 38247473916](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38247473916)
passed source and native macOS ARM64/Windows x64/Windows ARM64 at
306b74cdf0efa4000dcee8a5656e287890d8a45d. The exact full local Make suite also
passed at that revision. New explicit Go acceptance commands are documented in
[release preparation](RELEASE_PREPARATION.md); ordinary tests do not call models.

- [Development HTTPS update](evidence/development-https-update-306b74c.json): real verified HTTPS through production transport/repository, authentic development metadata/archive, bounded synthetic extraction, shared lifecycle commit/rollback; tamper/expiry/metadata rollback/offline preserve payload. Production public delivery/native self-update remain separate.
- [Authenticated legacy selector](evidence/authenticated-legacy-selector-306b74c.json): actual official external Codex 0.144.4, existing protected login, one synthetic request with transcript off, completed valid catalog selection in 8.5 seconds. Post-success observation: zero matching processes/temporary selector directories. This qualifies authenticated adapter operation, not live host delivery/answer quality.
- [Real Codex private lifecycle](evidence/real-codex-registration-darwin-arm64-306b74c.json): installed actual CLI 0.162.0-alpha.17.2, private install/status/diagnose/same-version update/remove/final status PASS; active auth/config unchanged. Codex toggle state belongs to host controls; unsupported manager toggle examples are corrected in EN/KO. Host-disabled/different-version/live activation are not claimed by this probe.
- [Actual Mac Developer ID signature](evidence/macos-developer-id-signature-306b74c.json): user-authorized certificate issuance after direct agreement acceptance, public/private pair and Apple chain verified, dedicated owned keychain, manager/helper copies signed with verified hardened runtime, matching team and secure timestamp. Private signing material never entered source or left the Mac. Local signing does not establish notarization or protected release runner qualification.
- Canonical/embedded Mac Team ID now matches that approved account. Production TUF root remains `{}`; Windows publisher pin is empty. Existing protected-tag/publication guards were not bypassed. No release/active-installation replacement was performed.

Local notarization authentication was completed on 2026-10-12 at checkout
3b0ed4ec334f34549677af3c0baf72a703784c3d on macOS ARM64. After direct user
authentication, a dedicated app-specific password was registered as
`opensocrates-notary` in the local login keychain. `notarytool store-credentials`
with `--validate` exited 0; private account arguments and the secure password
input are intentionally omitted from this public handoff. The exact check
`xcrun notarytool history --keychain-profile opensocrates-notary --output-format json`
exited 0 with a valid history response. Temporary credential transfer was
removed and iCloud synchronization was not enabled. Actual archive notarization,
Gatekeeper and isolated release-runner qualification remain separate gates.

The actual native Mac ZIP and standalone installer at c9da20d each received
Apple `Accepted`, with zero issues, exact submitted ZIP hashes and code hashes
matching the returned tickets. The installer was submitted after payload
acceptance. [Candidate receipt](evidence/macos-candidate-notarization-c9da20d.json)
retains the source/file identities and the initial release-check failure:
all five distributed files pass notarized `codesign` requirements, but the
former `spctl` app assessor exits 3 for valid bare CLI code. The shared native
trust/release path now retains Apple Developer ID/team/notarized pinning, adds
online notarization checking, and removes that app-only assessor. Both manager
and helper authenticate before version execution. Changed bytes must be rebuilt,
re-signed and re-notarized; later evidence must retain its own source identity.

[Release environment observation](evidence/release-environment-c9da20d.json)
confirms source/native CI PASS at c9da20d (run 38265091598), active main ruleset
protection with obsolete required-check names, and absent release runners,
environments, Actions variables/secrets and final tag. The
[environment review](RELEASE_ENVIRONMENT_REVIEW.md) records the exact Go-check
migration proposal, runner choices and cloud-secret/reviewer decisions. No
production pipeline or cloud credential transfer was performed by these checks.

Final candidate platform qualification at
**8b677f58828b3e3d5dea0d4d53017f18d7caf809** is retained in the
[exact notarization receipt](evidence/macos-candidate-notarization-8b677f5.json).
The rebuilt native ZIP and standalone installer both received Apple `Accepted`
with zero issues and matching archive/code hashes. All four packaged Mach-O
files and the standalone installer pass the full pinned Developer ID/team/
notarized requirement. Wrong-team code is rejected. Native unsigned, ad-hoc,
modified-code and signed-but-unnotarized negatives retain their d5f55fc source
identity; that native trust code is unchanged by the relative-path follow-up.
`make release-check` now exits 0 and reports `RELEASE_PLATFORM_INTEGRITY_OK` using
its documented relative package path. The path adapter keeps lexical-alias,
symlink and ownership rejection rather than relaxing the platform guard.

The exact full Make suite passed at d5f55fc; incremental
`make format-check lint`, `go test ./src/opensocrates/internal/devtools`, native
build/package/provenance and final signed `make release-check` passed at
8b677f5. Code/security reviews found no actionable findings in either source
change. Apple acceptance briefly preceded local ticket availability at d5f55fc;
unchanged files later passed without OS/cache changes or resubmission. The
cause between cache and server propagation was not established. Clean-machine
quarantined download, offline ticket behavior, protected signing runners and
final merged-tag production trust/publication remain separate gates.

CI run 38271650284 passed source and native macOS ARM64/Windows x64/Windows
ARM64 at 8b677f5 after rerunning only its failed Windows x64 job at the same
commit. No source, deadline or check changed between attempts.
The Windows x64 native-install attempt hit its unchanged 30-second deadline
after 30.004 seconds with empty stdout/stderr. The
[original failure receipt](evidence/windows-x64-ci-timeout-8b677f5.json) is
retained. The initial timeout's cause remains unknown. The production
`release-identity` command on this untagged candidate exits 1 with
`release_exact_tag_required`, as required; no Actions/tag inputs were faked.

Additional original-Windows qualification at 001c75a used an isolated restricted
current-user primary token. The new file owner matched the user and original
owner/groups/privileges/default DACL remained unchanged. The original installer
still exited 1 at its Windows private-helper call; no fallback initialization
or adoption occurred. [Receipt](evidence/windows-original-installer-restricted-001c75a.json)
and [inactive reproducer](evidence/qualification/windows-restricted-owner/README.md)
retain this unavailable result. A compatible normal user environment is still
needed; do not weaken guards or change account/system/desktop policies.

## Hosted Mac signing follow-up

The complete local Make suite passed at `9be0e5e879364e7f259b4ad7815c122d0a7860e1`
on native macOS ARM64 / Go 1.27.2. Code and security reviews found no concrete
findings. [Hosted run 38331988614](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38331988614)
then passed after the owner's direct environment approval: actual ephemeral
keychain import, separate Accepted payload/installer notarizations with zero
issues, all five pinned code checks, native release check and credential cleanup.
The [qualification receipt](evidence/hosted-macos-signing-9be0e5e/macos-signing-candidate-qualification.json),
[notarization receipt](evidence/hosted-macos-signing-9be0e5e/macos-signing-candidate-notarization.json),
[cleanup receipt](evidence/hosted-macos-signing-9be0e5e/macos-keychain-cleanup.json)
and [environment observation](evidence/hosted-macos-signing-9be0e5e/environment-observation.json)
retain exact source identity. Production encrypted Mac secrets remain; the
qualification switch/SHA and temporary credential copies were disabled/removed.
See [custody and direct approval](HOSTED_MAC_SIGNING.md).

The same head's normal PR CI passed source and Mac jobs but exposed deterministic
Windows failures in new POSIX Mac-keychain fixtures. Those five lifecycle tests
now live in a Darwin-specific test file, preserving all assertions and production
guards. Portable certificate/secret-isolation/bounds tests remain, with explicit
Windows/Linux native-host rejection coverage added. This test/documentation
follow-up does not relabel the signed `9be0e5e` bytes as a new candidate execution.

GitHub 후보 환경의 본인 승인 뒤 실제 서명·공증·파일 5개·배포 검사·키체인 정리를
통과했습니다. 검증용 비밀 사본은 제거하고 운영 비밀과 직접 승인 정책을 유지합니다.
Windows에서는 Mac 전용 경로·권한을 가정한 테스트만 Mac 파일로 옮기고, 공통 보안
검사와 Windows/Linux 호스트 거부 검사를 보존했습니다. 기존 서명 산출물의 소스
9be0e5e를 후속 테스트·문서 커밋의 실행 결과로 바꾸지 않습니다.

At test/documentation revision `30877e7dec8fb053b760905ad18d68a869114de9`,
affected local format/lint/docs/governance and `go test
./src/opensocrates/internal/devtools -run TestMacSigning` passed.
[CI 38332733383](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38332733383)
then passed actual source/Mac ARM64/Windows x64/Windows ARM64 jobs without reruns.
Final inspection also found duplicate source/Mac required-check names emitted as
skipped by the qualification push run. The qualification job is now moved
unchanged into its own push-only workflow; normal CI triggers are restored and
the five protected-main rule names are unchanged. The ambiguity was observed;
an actual merge bypass was not established. / 30877e7의 후속 소스·3개 플랫폼 CI는
재실행 없이 통과했습니다. 후보 push가 일반 필수 검사와 같은 건너뜀 이름을 남겨
후보 작업을 그대로 별도 workflow로 옮겼습니다. 필수 규칙 이름은 유지하며 실제
병합 우회가 발생했다고 주장하지 않습니다.

The user then authorized using the running Windows VM. A new
[read-only boundary receipt](evidence/windows-vm-current-user-boundary-20261013.json)
directly observed native OS/process ARM64, an administrator-effective interactive
token with default owner different from the user, and QEMU-GA Running. Both
PowerShell and minimal cmd guest-agent RPC calls timed out; input automation
and shared-directory output worked. The diagnostic used process-only
ExecutionPolicy Bypass, with no persistent account/UAC/service/policy changes
or product execution. This VM boundary does not meet ordinary-user original
installer qualification. The prior restricted-token helper exit 1 has no
measured cause; a harness catch label alone does not establish owner refusal.
/ 사용자가 제공한 VM을 실제 진단했고 ARM64와 관리자 토큰·사용자와 다른 기본
소유자를 확인했습니다. 내부 명령 연결은 시간 초과였으나 입력과 공유 폴더로 결과를
받았습니다. 진단 프로세스에만 실행 정책 플래그를 사용했고 계정·UAC·서비스·영구
정책·제품 설치는 변경하지 않았습니다. 일반 사용자 환경 조건은 아직 충족하지
못하며 이전 제한 토큰 helper 실패의 구체 원인은 미측정입니다.

## Remaining release gates

Available implementation acceptance passes; this candidate is **not production-release validated**.

1. Provision an independently approved threshold-signed TUF root, Windows publisher identity/signing integration, metadata service/key custody and scoped Administration-read publication credential. Local and hosted Mac candidate signing/notarization/platform integrity now pass; final merged-tag bytes still require their own directly approved execution. Test trust cannot become production trust. The user-approved Go required-check migration and six protected release/qualification environment policies are applied.
2. Qualify public signed network updates and complete production installer/manager/updater self-update/rollback with production trust, security prompts and timestamps.
3. Complete Windows adoption beginning with a successfully executed original v1.5 installer in a compatible user environment. Actual-payload Go adoption/rollback now passes, but its source-equivalent initialization does not meet that original-installer gate. Also complete macOS production fixed-label/updater-execution qualification. Released v1.5.0 explicitly supported automatic updates only on macOS ARM64; its Windows installer reports them unavailable, so there is no supported enabled Windows legacy scheduler to adopt. Enabled macOS takeover and rollback now have integrated real-OS evidence under the disclosed unique-label and suppressed-execution fixture boundaries.
4. Obtain clean-machine and real host trust/activation, account/workspace/global and CLI/Desktop evidence. Authenticated macOS legacy adapter operation now has a synthetic live-account receipt; actual delivery/answer quality remain distinct. Local updates cannot modify account content or running conversations. External host ARM64 availability/loading remains host-specific qualification.

Next: complete these release gates, then protected review/release workflow. No merge/tag/production publication/active-installation replacement is authorized. PR remains Draft. SSH upload and workflow editing access are verified; production signing/trust is a separate requirement.
