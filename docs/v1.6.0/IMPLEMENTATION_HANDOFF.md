# v1.6.0 implementation and release handoff

Tracking: [implementation issue #111](https://github.com/ParkerHwang/OpenSocrates/issues/111) and [Draft PR #112](https://github.com/ParkerHwang/OpenSocrates/pull/112). Preparation PR #110 and issue #109 remain separate. Reconciled main base: 9572db2c71a455d4ada24c78402d0f874002cec9. Branch: codex/v1.6-go-native.

## Completed implementation

| Package | Completed scope |
| --- | --- |
| V0 | Reconciled released v1.5.2 baseline, 48 methods, ten languages, revision 5 |
| V1–V2 | Typed Go contracts, services, content, domain, decision, runtime CLI and persistence |
| V3 | Native OS protection and pinned external Codex app-server compatibility |
| V4–V5 | Shared lifecycle journals, transport, host registration, native management and npm adoption |
| V6 | TUF trust, opt-in stable scheduling, versioned bundles and journaled self-update/recovery |
| V7 | Go generation, package/release tooling, governance/validation, CI and bilingual documentation |
| V8 | Source checks, compatibility comparison, native acceptance, specialist review and durable handoff |

The user subsequently added **Windows ARM64** to v1.6.0. It has separate native binaries, PE/build checks, signed target selection, helper/installer paths, publication assets and native CI. This is a material user-directed adjustment to the original two-platform plan. Codex and Antigravity retain their profile boundaries; native Windows Claude Code is excluded and --host all still means Codex. Claude account upload/activation remains separate.

Methods, teacher questions, response policies and shared guides now freeze released
v1.5.2 source `9838db16910c5f22d9dcc3c7180350cb406fd236`, revision 5 and ten
languages. Compiled product metadata remains 1.6.0. All earlier evidence retains
its original source/revision and does not qualify these new revision-5 files.
See [baseline](CONTENT_BASELINE.json) and [intentional changes](DECISIONS.md).

## Released v1.5.2 reconciliation — locally verified, final CI pending

Current release source: `9838db16910c5f22d9dcc3c7180350cb406fd236`.
Annotated tag object: `4c27d59da54eb1591ba24c0ebae62d6ab3168b60`.
Reconciled main merge: `8f08b9a90d711fa3fc60cc7db6f962e3dda43c42`, same tree as the tagged source, distinct commit.

Completed: import the released revision-5, 48-method, ten-language content and
port its runtime/preference/script-detection/reference/package contracts to Go;
retain the native 1.6.0 commands, toolchain and macOS ARM64 / Windows x64/ARM64
scope. Canonical totals are 480 procedures, 3,840 cases and 1,440 teacher questions.
The existing four languages' authored procedure/case bytes and metadata/question
values remain unchanged; method identity advances from revision 4 to 5. Historical
v1.5.0/v1.5.1 package coverage remains versioned, without silently relabeling it.

Local source, generation, package and installer tests passed at
`76e67c7ce976fbf319191e460bac6db21f179ebe`, on macOS ARM64 / Go 1.27.2.
Exact commands and the independent source audit are recorded below. Final native
CI and the bounded test-only cost correction are still being verified.

Not verified at this documentation stage: new native CI, authentic v1.5.2 npm-installer adoption, new artifact
signing/notarization, production trust/public update transport, clean-machine or
actual-host delivery. Prior successful d297b76 CI and earlier hosted Mac Accepted
receipts remain historical and do not qualify the current revision-5 artifacts.
PR #112 records the final exact head, commands and CI results after completion.

Next: verify the bounded test-only correction and final native acceptance. Keep the protected-main required-check
transition and any release deployment under the user's existing approval rules.
No merge, tag, publication or active installation replacement follows from this
reconciliation. Method-body upgrades remain v1.6.1+ and native Windows Claude
Code remains excluded. / 출시된 v1.5.2를 현재 기준으로 포팅했습니다. 이 단계는
소스·생성·패키지·설치기 검사를 통과했으며, 새 CI·새 파일 서명/공증은 별도로 기록합니다.

## Exact evidence

At `76e67c7ce976fbf319191e460bac6db21f179ebe`, all commands below passed:

```text
make bootstrap format-check lint generated-check content-check adjudication-check docs-check governance-check
make package TARGET=darwin-arm64
make package TARGET=windows-x64
make package TARGET=windows-arm64
make package-check security-scan smoke installer-check
```

Local Windows package builds are cross-compilation. An independent audit verified
1,133 tagged canonical/shared/generated-schema files (only compiled product
version changes to 1.6.0), all 33 schema sources, 480 references/procedures,
3,840 cases, 1,440 teacher questions, exact source/semantic hashes, the 384
earlier-four-language procedure/case files and all 59 earlier evidence files.
Code and security reviews found no actionable defects at that source.

The initial CI source job stopped at missing PR handoff labels in its event
snapshot, before source tests. The labels were corrected without relaxing policy;
[governance run 38391577636](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38391577636)
passed at the same source. A subsequent documentation/test-only commit supplies a
fresh event with the corrected handoff. Current full results belong in PR #112.

The first local management suite took 595.258 seconds. The first test-only
reduction passed affected format/docs/governance/smoke/installer checks at
`ff0ee96118d8e70d10dfde2ac26587f49820e5e4`, with management reduced to
233.808 seconds. Its source CI job also passed. Windows source tests at the
original `76e67c7` had reached the Go package-level ten-minute limit during
physical fixture writes/copies, including old-version cases; individual
storage/ACL latency and a separate concurrent-lock failure cause are unmeasured.
See [bounded failure observation](evidence/v1.5.2-native-test-cost-76e67c7.json).

The final bounded test-only correction keeps one full physical lifecycle per
version: v1.5.0 KO, v1.5.1 JA and v1.5.2 TH. The v1.5.2 case inspects the entire
ten-language, 480-reference tree and every rollback/ownership/foreign-file
assertion. Transport creates one private physical fixture per host, retaining
all four version combinations, eight inventory attacks per host and four
canonical-row attacks per content host. Each case still invokes full package
verification and restores its changes; no validator results are cached.
All ten settings values, the inexpensive six-language opaque-state table and
all sixteen native legacy adoption/recovery fixtures remain covered.
No production deadline, Go timeout, OS guard or assertion was weakened.
/ Windows 기록에서 반복 파일 생성·복사 중 시험 시간이 만료된 것을 확인했습니다.
버전별 전체 수명주기와 모든 오류 사례를 유지하고 테스트 폴더를 재사용하도록
준비 비용을 줄였습니다. 열 언어 설정·전체 파일·원복·소유권과 제한 시간은 유지합니다.

At `bd8eb5d83c01f62d236a207dde15925abacec2f8`, affected
`make format-check lint docs-check governance-check smoke installer-check` passed
locally, with management 128.971 seconds and transport 45.361 seconds.
[CI 38394764452](https://github.com/ParkerHwang/OpenSocrates/actions/runs/38394764452)
passed source and complete native Mac acceptance; both Windows source/ACL suites
also passed. Windows initial install then reached the unchanged 30-second
deadline, at 30,003/30,004 milliseconds for x64/ARM64, respectively.
The owned fixture journal was `preparing`, registration had not started and
native/active state was absent. Original bounded receipts:
[x64](evidence/v1.5.2-native-install-bd8-windows-x64.json),
[ARM64](evidence/v1.5.2-native-install-bd8-windows-arm64.json).
Which candidate operation and individual delay caused the deadline are not yet
measured. This is separate from the package-level ten-minute test-cost failure.

The follow-up removes only `Inspect`'s redundant regular-leaf metadata guard:
`SHA256File` already validates ownership, ancestor/reparse/link protection and
the live regular-file handle it hashes. Root/directory guards, full snapshots,
file/hash/mode/size limits, copy-before/destination/copy-after checks, durable
writes and rollback remain intact. New Unix and Windows unsafe-leaf tests retain
the rejection boundary. A failure-only operation counter observes at most 64
known phases from the existing private journal, exporting counts and the next
planned ordinal without paths, IDs, role inference or contents. The existing
eight-MiB read guard, 30-second limit and pass criteria are unchanged.
This code-grounded duplication removal is not yet proof of the deadline cause
or a passing Windows install; current exact-head results are recorded in PR #112.
/ 등록 전 후보 준비까지 진행된 것을 확인했습니다. 실제 읽기 핸들의 소유권 검사를
유지하며 정규 파일의 중복 검사만 제거하고, 경로·원문 없는 준비 개수 관측을
보완했습니다. Windows 설치의 통과 여부는 현재 커밋에서 다시 확인합니다.

At `940ac715076a7d76bfa3fc920742382b73fa284a`, the complete local source suite,
three-target package generation and package/security checks passed. Current code
and security reviews confirmed live-handle guard equivalence. Source and native
Mac CI also passed, while both Windows source/ACL suites passed before initial
install again reached 30 seconds. The new counters showed exactly five
operations, one prepared and four planned, with next planned index 1. This binds
the interruption to the full immutable-bundle candidate operation after host
preparation: [x64](evidence/v1.5.2-native-install-940-windows-x64.json),
[ARM64](evidence/v1.5.2-native-install-940-windows-arm64.json).
Individual copy/hash/ACL/storage latency remains unmeasured.

The original verified bundle is already passed directly into that operation;
there is no duplicate full-bundle source copy to remove. The next bounded
follow-up overlaps independent regular-file copies with at most four workers.
All owned directories are created serially first; every file still uses the
unchanged owned, bounded and durable copy API. Assignment and first-error
recording share one mutex; new work stops after a recorded error and all
in-flight work is joined before returning. Partial owned output is preserved
for the engine. Directory modes apply after successful join, and source-before,
destination and source-after snapshots remain exact. There is no input-tree
consumption, cached validator result, timeout extension or trust/durability
reduction. Actual Windows timing is pending current-head CI in PR #112.
/ 호스트 준비 후 전체 불변 번들 후보에서 제한에 도달한 것을 확인했습니다.
독립 파일의 내구성 복사를 최대 네 개씩 처리하고 오류 뒤 추가 배정을 멈추며,
모든 작업 종료 후 기존 검증·복구로 넘어갑니다. 원본과 검사·저장·제한 시간은 유지합니다.

## Historical released v1.5.1 reconciliation

The original Go preparation and all revision-3 receipts retain their historical
source identity. After release v1.5.1, merge current main
`5a6a7fa2897dd42772c4503a1301770e48bd1f29` into the existing PR branch, retain
the native Go tooling/workflows and VERSION 1.6.0, and port released four-locale
runtime behavior. Canonical/schema generation now targets revision 4,
EN/KO/ZH/JA, 192 complete references and 576 teacher questions. Historical baseline
hashes remain in [the decisions](DECISIONS.md); the baseline JSON now tracks v1.5.2. / 초기 준비와
리비전 3 기록은 그대로 보존하고 출시된 v1.5.1을 병합·포팅했습니다. Go 실행·개발
경로와 1.6.0 버전은 유지하며 네 언어의 전체 참조와 질문을 생성합니다.

Native locale get/set/reset, explicit/stored/text selector precedence,
four-language complete references and strict versioned package verification
address observed regressions. Legacy v1.5.0/96-reference and v1.5.1/192-reference
fixtures preserve preferences, disabled state, foreign data and rollback.
Default decision and Claude entry remain stateless. / 언어 명령·이전 선택기 우선순위·
완전한 참조·버전별 패키지 검사와 설정·꺼진 상태·다른 파일·복구 보존을 반영했으며
기본 판단과 Claude 진입에 설정·대화 읽기를 추가하지 않았습니다.

At the historical v1.5.1 reconciliation, current main required the maintenance
pipeline's six legacy checks and v1.5.2 was still draft. That policy and pending
status were observed then, not a claim about the released current baseline.
Prior 9be0e5e hosted Mac notarization did not qualify the revision-4 merge.
The original results and limitations below retain their source and date.

## Historical exact evidence

Local reconciliation verification at `c9c8bd54d2f5c81556ddfd6b8888bb348341ab9c`
(native macOS ARM64 / Go 1.27.2): bootstrap, format-check, lint,
generated-check, content-check, adjudication-check, docs-check and
governance-check passed. Initial package-check included ten old revision-3
`dist/native` packages and correctly rejected their obsolete content. Those
generated artifacts were preserved outside the inspection path; regenerating
all three native targets with `make package TARGET=darwin-arm64`,
`TARGET=windows-x64`, and `TARGET=windows-arm64` made package-check and
security-scan pass. Windows local builds are cross-compilation, not native
Windows execution. / 처음에는 이전 리비전 3 산출물 10개를 거부했으며, 기존 파일을
보존하고 현재 소스로 재생성한 뒤 패키지·보안 검사를 통과했습니다. Windows
로컬 빌드는 실제 Windows 실행 증거가 아닙니다.

The first smoke run found an invalid cancellation-reason value in one new
test. The test-only correction at `66f757f435dd9cce205abe880705f08b110f22ea`
uses the existing closed `user_cancelled` reason and exposes validation errors.
`make format-check` and `make smoke installer-check` then passed. Production
code and canonical inputs are unchanged by that correction; successful earlier
checks and code/security audit are reused for those same inputs. This does not
claim that the aborted combined Make invocation passed. / 시험 데이터의 취소
사유만 고친 후 전체 런타임·설치기 검사를 통과했습니다. 런타임 검증 규칙은
완화하지 않았고 실패한 최초 통합 명령을 통과했다고 표시하지 않습니다.

Independent source audit verified exact v1.5.1 content/schema parity, all
192 original EN/KO procedure/case files, 192 references, 576 questions and
unchanged historical evidence. Code/security review found no actionable
defects. Current native CI results belong in PR #112 at the pushed head;
new-file notarization, actual v1.5.1 npm-installer adoption, production trust and
public/live delivery remain separate qualification. / 소스·의미·스키마·과거 기록을
독립 대조했고 코드·보안 검토에서 수정할 결함은 없었습니다. 새 파일 공증과
실제 npm 설치기부터의 인수·운영 신뢰·공개 전달은 별도입니다.

Native CI at documentation head `3ff8063` then passed source contracts but
found three new fixture setup issues: Windows settings/package roots lacked
explicit protected DACLs, and Mac legacy preparation applied private-file reads
to public package modes 0644/0755. The ordinary Mac lifecycle steps passed;
only six legacy fixture preparation cases failed before adoption commands.
Fix `fdb693c3fef1b7fc766e8876c19343c2f87f9481` creates new owned fixture
subdirectories through production protection APIs and uses `ReadOwnedFile` only
for public package payloads, retaining private settings/state reads. Runtime
ownership, ACL, reparse and unsupported-selector guards are unchanged. /
원격 검사는 새 시험 폴더의 Windows 권한과 Mac 공개 파일 읽기 준비 오류를
찾았습니다. 제품 검증을 완화하지 않고 전용 폴더와 적절한 읽기 경계를 사용했습니다.

At `fdb693c`, `make format-check lint`, `make package TARGET=darwin-arm64`,
`go build -o build/opensocrates-host-fixture
./src/opensocrates/cmd/opensocrates-host-fixture`, and native
`go run ./src/opensocrates/cmd/opensocrates-dev acceptance lifecycle --binary
dist/runtime/darwin-arm64/opensocrates --package dist/native/darwin-arm64
--host-binary build/opensocrates-host-fixture --report
build/evidence/native-lifecycle-darwin-arm64.json` all passed. The receipt now
passes all six v1.5.0/v1.5.1 synthetic adoption/recovery cases as well as ordinary
lifecycle. `go test ./src/opensocrates/internal/compat
./src/opensocrates/internal/transport ./src/opensocrates/internal/management
./src/opensocrates/internal/devtools` passed. Incremental code/security reviews
found no actionable findings. Native Windows re-execution is still recorded
through CI at the final pushed head. / 수정 후 실제 Mac 수락과 관련 Go 검사는
통과했습니다. Windows 실제 결과는 새 소스의 CI에서 기록합니다.

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
