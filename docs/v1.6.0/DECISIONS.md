# v1.6.0 implementation decisions / 구현 결정

These decisions apply to the unreleased Go candidate. The four preparation
documents remain planning references; actual command results and release gates
belong in the exact-commit implementation handoff. / 아래는 미출시 Go 후보의
구현 결정입니다. 준비 문서와 실제 실행·릴리스 증거를 구분합니다.

## Baseline / 기준

The original preparation main was `9572db2c71a455d4ada24c78402d0f874002cec9`.
The current reconciled release is v1.5.2 source
`9838db16910c5f22d9dcc3c7180350cb406fd236`, content revision `5`, all 48 methods
and ten languages (`en`, `ko`, `zh`, `ja`, `fr`, `de`, `it`, `es`, `pt`, `th`).
The annotated tag object `4c27d59da54eb1591ba24c0ebae62d6ab3168b60` is distinct
from its source commit. Main merge `8f08b9a90d711fa3fc60cc7db6f962e3dda43c42` has the same tree as the tagged
source, but its commit identity is not the release source. Released source and
normalized semantic hashes and full inputs belong to [CONTENT_BASELINE.json](CONTENT_BASELINE.json).

- Released `source_tree_hash`: `sha256:e1e11f7a772cb2a3f6c8dc0e3b22b0787cdc903de69842de957577a177cee7be`
- Released `normalized_semantic_hash`: `sha256:b5fc82f5ce8725bd23b7d270014f90853e39474e7b00ae4f20553a484524c659`

V1.5.2 provides 480 procedures, 3,840 canonical cases and 1,440 teacher questions.
The previous four languages' procedure/case body bytes and metadata/question
values remain unchanged; individual method revision identity advances to 5.
Portuguese uses Brazilian orthography under generic `pt`, without separate
regional claims. Latin-script European languages require explicit/stored choice;
Kana retains priority, then dominant Thai/Hangul/Han detection, with English on
ties, empty or unknown script. Default decision and native Claude entry stay stateless.
Separate method-body upgrades remain v1.6.1+; host/platform boundaries are unchanged.
/ 출시된 v1.5.2·리비전 5·열 언어를 현재 기준으로 반영합니다. 기존 네 언어의
본문과 값은 그대로지만 개별 방법 리비전 식별은 5입니다. 이전 검증·공증 결과를
새 리비전의 증거로 바꾸지 않으며 본문 업그레이드·호스트 확대를 섞지 않습니다.

The previous v1.5.1 reconciliation remains historical source
`5a6a7fa2897dd42772c4503a1301770e48bd1f29`, revision 4, EN/KO/ZH/JA:

- historical `source_tree_hash`: `sha256:993c30191b0d2b67af88a25c2631d9e8fddeeaf9dadfd0ff4fb07dd62539dcab`
- historical `normalized_semantic_hash`: `sha256:835a1e32695e863b3696c3bf5dcf1acb7faa580d889129e617524fbc0d9908e6`

The original v1.5.0 preparation/source and revision-3 evidence remain unchanged.
PR #110 is the planning reference; issue #109 tracks preparation only. Reconcile
any later published maintenance release before final v1.6.0 qualification and
publication, without importing unverified drafts or regrading old receipts.

## Maintenance reconciliation proposal / 유지보수 재통합 제안

The following sources define a proposed maintenance delta from Go candidate
`1dbccad464c83b21704416937d1b5ccc187522fe`. This record does not assert that the
delta is integrated, generated or verified. Main was
`227a528996d93c423851db1d663f9572be534e59` when the sources were reconciled.

| Source | Exact source identity | Proposed Go boundary |
| --- | --- | --- |
| [#126](https://github.com/ParkerHwang/OpenSocrates/pull/126), merged | `62e499475cc90483d7c87364e0a0142526775e26` (merge) | Substantive-thinking controller wording and host/shared reader and decision guidance; ordinary work or reader guidance can suffice. |
| [#128](https://github.com/ParkerHwang/OpenSocrates/pull/128), merged | `227a528996d93c423851db1d663f9572be534e59` (merge) | Bounded Codex discovery delivery for large submissions; no method-body change. |
| [#130](https://github.com/ParkerHwang/OpenSocrates/pull/130), open/unmerged at reconciliation | `197b317b4aeca4928fabe515dbfef6a98803e568` (head) | Repairable closed request diagnostics, distinct failure/empty/retired outcomes, and matching request guidance if selected for integration. |

Keep v1.5.2/revision 5, 48 methods and ten locales as the method-content
contract. Preserve authored methods/cases, teacher questions, response policies,
eligibility/scoring and required outputs/dependencies/stops. Controller and
reader/request guidance are explicitly recorded maintenance differences, not a
48-method rewrite or a new release. Port runtime behavior to Go without
restoring the Python runtime/tooling. Native entry delivery, complete reading,
application and usefulness remain distinct evidence levels.
/ 위 표는 정확한 출처에 따른 재통합 제안이며 적용·생성·검증 완료를 뜻하지
않습니다. #130은 조회 시 미병합인 별도 후보입니다. 출시된 리비전 5·48개 방법·
열 언어와 방법 본문·사례·교사 질문·응답 정책·적합성/점수·필수 출력·의존·중단
조건은 유지합니다. 컨트롤러와 독자/요청 안내의 유지보수 차이만 별도로 기록하고
Python 실행·개발 경로를 되살리지 않습니다. 진입 전달·전체 읽기·적용·유용성을
같은 증거로 취급하지 않습니다.

Method-body parity does not establish unchanged artifact hashes. #126 changes
`content/locales/*.yaml` controller text as well as templates and guides.
`SourceTreeHash(content)` includes those YAML sources; `SemanticHash` includes
both `locale_messages` and `prompt_fragments`. Its full semantic hash therefore
cannot be declared unchanged merely because method bodies are preserved.
Shared guide/request files under `plugin-src/shared/` are separate package
inputs, not part of this content-only source-tree hash. #128 runtime changes
and #130 shared request guidance do not by themselves require a method revision
or a replacement content hash; their package/source identities still need the
actual integrated inputs.
/ 방법 본문이 같아도 산출물 해시가 같다는 뜻은 아닙니다. #126의 로케일
컨트롤러는 콘텐츠 소스 해시와 의미 투영에 포함됩니다. 반면 shared 안내·요청
파일은 별도 패키지 입력이며 콘텐츠 전용 소스 해시에는 포함되지 않습니다.
#128의 실행 경로와 #130의 shared 안내만으로 방법 리비전이나 콘텐츠 해시를
바꾸지 말고, 실제 통합 입력에 따른 파일·패키지 식별을 따로 계산합니다.

`CONTENT_BASELINE.json` is deliberately unchanged by this proposal. Its existing
release identities, hashes and superseded baselines remain the pre-maintenance
record; no pending value replaces a machine-consumed hash. The integrated
candidate commit, content source hash, normalized semantic hash and generated
package identities are **pending integration**, not copied from either main or
the released bundle. Before admitting a maintenance candidate, the integration
owner must preserve the original release record, reconcile the exact allowed
canonical delta, and update the baseline and every affected generation/package
identity guard together with the actually computed candidate values. Do not
remove a guard, narrow its hash projection or reclassify old evidence to make
the new candidate pass. Regenerate canonical outputs through the Go tooling;
never hand-edit compiled bundles, embedded assets, schemas or package manifests.
/ 이 제안에서는 baseline JSON을 변경하지 않습니다. 기존 출시·과거 기준의
식별과 해시는 보존하며 기계가 읽는 해시 자리에 pending을 넣지 않습니다.
통합 커밋·콘텐츠 소스/의미 해시·생성 패키지 식별은 통합 후 실제 계산 전까지
미확정입니다. 통합 담당자는 원래 출시 기록을 보존하고 허용한 정본 차이만
확인한 뒤 실제 값으로 기준과 관련 생성·패키지 검사 고정값을 함께 갱신합니다.
검사를 없애거나 해시 범위를 줄이거나 과거 증거를 새 후보로 바꾸지 않습니다.
컴파일 묶음·내장 자산·스키마·패키지 명세는 Go 생성 경로로 갱신합니다.

## Go boundaries and toolchain / Go 경계와 도구체인

Use one Go module, runtime/application/domain/persistence boundaries and active
first-party tools below `src/opensocrates/`. Pin Go 1.27.2 with module directive
`go 1.27.0`; dependencies are fixed in `go.mod`/`go.sum`. End users run native
binaries and never require the Go toolchain, Python, Node.js or npm.
[Official Go module layout](https://go.dev/doc/modules/layout) supports multiple
commands with internal packages. / Go 모듈 하나와 기존 유용한 계층을 유지하며
활성 자체 구현을 Go로 통일합니다. Go는 개발 의존성이며 사용자 요구가 아닙니다.

Separate transport, lifecycle transaction/recovery, host registration and OS
filesystem/process services. Use typed contracts/capabilities/error categories;
distribution profiles are distinct from runtime adapters. Preserve stored/wire
formats and deterministic artifacts explicitly, including Unicode, numeric
precision, omitted/null/empty and unknown-field semantics. Do not equate Go's
JSON defaults with compatibility. / 전달·작업/복구·등록·OS와 배포 프로필·런타임
어댑터를 분리하며 직렬화·저장·검증 계약을 명시적으로 보존합니다.

### Released Windows payload size / 기존 Windows 패키지 크기

The authentic v1.5.0 Windows x64 archive contains a **341,142,832-byte**
`runtime/windows-x64/opensocrates-runtime/_internal/codex_cli_bin/bin/codex.exe`.
The initial Go lifecycle's 256 MiB per-file bound rejected that valid baseline
before adoption. Raise the per-file bound to **512 MiB**, retaining the 2 GiB
aggregate and 10,000-entry bounds. Stream owned-file hashing and verified
recovery copies rather than allocating the full legacy executable. Existing
owner, ACL, reparse, exclusive-create and durable-write checks still apply.
Files above the bound remain rejected. This corrects migration compatibility;
it does not expand platform or host support. / 실제 v1.5 Windows 패키지의
341,142,832바이트 실행파일이 초기 256 MiB 제한에 거부되는 호환성 문제를
수정합니다. 파일당 512 MiB, 전체 2 GiB, 10,000개 항목으로 제한하고 해시·복구
복사를 스트리밍 처리합니다. 소유권·ACL·reparse·배타 생성·내구성 검사를
유지하며 제한 초과 파일은 계속 거부합니다.

## Distribution candidate: GoReleaser / 배포 후보 평가

GoReleaser supports [Go build matrices](https://goreleaser.com/customization/builds/builders/go/),
[archives](https://goreleaser.com/customization/package/archives/),
[external signing](https://goreleaser.com/customization/sign/sign/) and separate
[notarization](https://goreleaser.com/customization/sign/notarize/). These APIs do
not by themselves provide our canonical content identities, closed manifests,
trusted update root or native/live qualification.

Choose the repository's Go `opensocrates-dev` build/package/release orchestration
for v1.6.0. It keeps the pinned toolchain, exact supported targets, canonical
inventories/provenance and signature-before-final-inventory gates together.
GoReleaser could orchestrate the matrix but would add a dependency while still
requiring the custom gates; it is not adopted. / 공식 기능을 확인했으며 자동으로
신뢰·콘텐츠·네이티브 검증을 제공하지 않습니다. 이번에는 자체 Go 도구를 선택하고
후보 기능을 검증 없이 보안 보장으로 해석하지 않습니다.

The supported matrix is macOS ARM64 and Windows x64/ARM64. Release bundles use
`opensocrates-v1.6.0-<target>.zip`, a `native-bundle/1.0.0` manifest, native manager
and update helper, version/content/schema identities and explicit host packages.
Native Claude is Mac-only. `--host all` remains Codex only. Account exports have
no executable, upload or activation. / 명시적으로 추가한 Windows ARM64와 기존
프로필을 지원하며 계정 활성화·Windows Claude·다른 플랫폼을 확대하지 않습니다.

GitHub's [immutable release workflow](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
permits preparing Draft assets before publishing to lock the release. Source
identity, native evidence, signing, production metadata and published transport
checks remain separate gates. No production publication occurs in this task. /
Draft 준비와 실제 게시를 구분하며 별도 승인 없이 게시하지 않습니다.

## Update candidate: TUF and go-tuf / 업데이트 후보 평가

Choose `github.com/theupdateframework/go-tuf/v2` v2.4.2 after inspecting its
[official client documentation](https://pkg.go.dev/github.com/theupdateframework/go-tuf/v2/metadata/updater)
and [source](https://github.com/theupdateframework/go-tuf/tree/v2.4.2).
[TUF's specification](https://theupdateframework.github.io/specification/latest/)
defines root authorization, role thresholds, expiry, consistent snapshots and
rollback/freeze protection. The library does not supply operational key custody,
platform signatures, host activation or filesystem transaction safety.

Use protected durable trust state, isolated candidate/cache transport and
persist accepted metadata versions before activation. Keep trust rollback floors
when rolling back a local runtime. Bootstrap an independently trusted compiled
production root generated from canonical `config/update/root.json` and
`config/update/identities.json` under `internal/update/trustconfig`; do not adopt an update-server root as initial trust. Root
rotation requires old/new authorization. Separate offline root and online release
roles, expiry and key recovery procedures. / 라이브러리의 보장을 운영 키 관리·
플랫폼 서명·작업 복구와 구분합니다. 독립 신뢰 루트와 내구성 롤백 기준을 유지하고
로컬 실행파일 롤백으로 네트워크 과거 메타데이터를 다시 허용하지 않습니다.

The production root is unprovisioned in this candidate and production signing
credentials are unavailable. Tests may use explicitly isolated development
trust. Production update checks must report unavailable until the approved
root/key/metadata service is provisioned; unsigned/checksum-only fallback is
forbidden. / 운영 루트·서명 미제공은 릴리스 차단 조건이며 검사 자료로 대신하지
않습니다. 신뢰를 우회하는 체크섬 경로로 자동 갱신하지 않습니다.

## Scheduling and activation / 예약과 적용

Codex only: opt-in stable checks every 24 hours with a five-minute delayed login
check, through per-user macOS LaunchAgent and Windows Task Scheduler. The
[Apple job documentation](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)
and [Windows executable-task documentation](https://learn.microsoft.com/en-us/windows/win32/taskschd/starting-an-executable-when-a-user-logs-on)
are scheduling references, not proof of native operation. No network/install runs
inside hooks. Major/breaking-schema updates do not auto-activate. / 두 플랫폼의
실제 예약 실행 증거가 필요하며 문서·크로스 컴파일로 대신하지 않습니다.

Versioned bundles are separate from settings/state. Started processes retain the
bundle; Windows replacement uses a Go helper where required. Journaled recovery
and verified rollback cover manager/updater self-replacement. Changed files can
require new hook review/fresh session/reload. Existing conversations are never
read/terminated for updates. Other integrations retain manual lifecycle until
scope-specific registration, disabled-state, integrity, reload and recovery
qualification. / 사용자 상태·버전 묶음을 분리하고 파일 변경과 실제 대화 적용을
구분합니다. 계정 업로드·활성화는 계속 별도 작업입니다.

## npm adoption / npm 인수

Use explicit `adopt`, exact ownership/inventory/registration checks and a durable
prior-state/scheduler backup. Coordinate exclusive ownership before retiring the
previous updater; preserve prior opt-in, trust, settings and disabled state.
Rollback restores the previous scheduler or reports incomplete recovery with
bytes retained. Do not indiscriminately remove npm packages/user data or
reinterpret retired profiles. / 검증한 기존 v1.5 설치를 한 번 명시적으로 인수하고
업데이트 소유자는 하나로 유지합니다. 기존 패키지의 무차별 삭제를 하지 않습니다.

The released v1.5.0 updater supports macOS ARM64 only. Windows automatic-update
commands report unavailable, so Windows adoption must preserve the absence of
an old supported scheduler rather than invent one. Enabled legacy-scheduler
takeover is a macOS qualification requirement. / v1.5.0 자동 업데이트는 macOS
ARM64 전용이므로 Windows에서는 이전 예약 작업이 없던 상태를 보존합니다.
켜진 이전 업데이트 작업의 인수 검증은 macOS에서 수행합니다.

## Compatibility versus intentional changes / 호환과 의도한 변경

Compatibility-preserving: all frozen content semantics; supported host/profile
matrix; wire/state/canonical identities; fail-open/content-free hooks; existing
trust and disabled-state boundaries; bounded legacy selector with external
version-matched Codex app-server, isolation/deadlines/cancellation/cleanup.

Intentional changes: Go-native direct distribution/adoption, signed scheduled
Codex updates including Windows, durable self-update/recovery, and validating
complete decision requests before changing scope so malformed routing preserves
existing availability. / 호환 포팅과 새 배포·예약·복구·검증 순서 개선을 분리합니다.
기본 판단은 추가 모델·인증이 없고 본문 변경은 포함하지 않습니다.

## Verification boundary / 검증 경계

Implement/integrate first; final checks run against stable files. Exact commit,
commands/results, native platforms, clean-machine/live observations and missing
production resources belong in the implementation handoff. Cross-compilation
is not Windows correctness; fixtures are not live delivery; historical evidence
is not v1.6 qualification. No claim of general answer, latency or token-cost
improvement follows from this migration. / 구현·통합 후 최종 검사하며 구현·로컬·
릴리스·실제 호스트 증거를 분리합니다. 병합·태그·게시·활성 설치 교체는 별도
승인입니다.

## Integration clarifications / 통합 확정

Intentional input hardening rejects duplicate JSON keys/unpaired Unicode
surrogates and validates complete requests before context/scope reset. Unsafe or
newer settings never receive destructive fallback defaults. Before the proposed
maintenance reconciliation above, the released v1.5.2 compiled bundle changes
only release metadata `product_version` to `1.6.0`; method/projection/policy
identity remains revision `5`. The proposal's controller/guidance differences
must be recorded separately from that release-metadata-only comparison.
/ 입력 보강과 릴리스 메타데이터 변경을 본문 포팅과 구분하며 이전 상태·설정을
파괴하지 않습니다. 위 유지보수 제안 전의 출시 기준 비교는 제품 버전만 1.6.0으로
바꾸고 리비전 5를 유지합니다. 제안의 컨트롤러·안내 차이는 별도로 기록합니다.

Legacy selector use is opt-in through external Codex app-server pinned to
`0.144.4`; protocol availability is not authenticated proof. Installation
diagnostics use `manage diagnose --host HOST`, preserving runtime `diagnose`
wire behavior. / 이전 선택기는 명시적 호환 경로이고 설치 진단과 런타임 계약은
분리합니다.

Windows native Codex hooks require the normal inherited default PowerShell
context; the configured command directly invokes the native binary using
`$env:PLUGIN_ROOT`. Custom/cmd fallback shells are unsupported and fail open.
This external OS/host one-command configuration is not a first-party wrapper.
Mac commands use quoted `$PLUGIN_ROOT`/`$CLAUDE_PLUGIN_ROOT` environment references
rather than textual macros. / 셸·경로 경계를 유지하며 사용자 요청의 ARM64 외 추가 플랫폼·자체 셸 구현을
추가하지 않습니다.

Production release orchestration is manual exact-tag execution through protected
signing/publication environments and ephemeral native macOS ARM64/Windows x64/ARM64
signing runners. Online metadata keys are separate from platform signing;
approved root/identities remain canonical data. Monotonic role versions require
previous signed metadata, except explicit initial repository version 1. Native
CI fixtures are not live Codex evidence. Unprovisioned roots/credentials block
production publication safely. / 운영 서명·메타데이터·게시 권한과 실제 검증을 분리하며
운영 자원 미제공을 우회하지 않습니다.

Explicit Codex purge/trust reset retains its existing bounded purpose. The
intentional safer ordering preflights every removable payload before mutation.
Reset only seven exact managed hook-state entries after isolated pinned
app-server strict-configuration capability validation; preserve unrelated TOML bytes and do not
auto-approve trust. Shared manager bundles, npm packages and conversation data
remain. / purge 대상 전체를 사전 확인하는 순서 개선이며 신뢰 초기화는 기존의
정확한 7개 항목에 한정합니다. 실제 네이티브 증거는 별도입니다.

Trust-reset configuration validation is a separate bounded management capability
probe requiring advertised stdio transport and `--strict-config`, not the legacy
selector version pin. Unknown support is unavailable. Reset completes its own
verified transaction under the lifecycle lock before purge; later purge failure
does not undo that explicit reset. / 관리 설정 검증과 이전 선택기의 버전 고정을
구분하며 신뢰 초기화·purge의 별도 완료 상태를 정확히 보고합니다.

GitHub's repository
[immutable-release status API](https://docs.github.com/en/rest/repos/repos#check-if-immutable-releases-are-enabled-for-a-repository)
requires Administration:read. The protected publication environment therefore
requires `OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN` scoped to this repository/read
permission, used only for the exact `/immutable-releases` GET; release mutations
continue using the contents:write workflow token. Missing permission blocks
before publication, with no immutability fallback. / 해당 조회는 별도 저장소 범위
Administration:read secret이 필요합니다. 값은 문서·로그에 기록하지 않으며
권한 부재를 검사 우회나 릴리스 검증 완료로 해석하지 않습니다.

## Material plan adjustment: Windows ARM64 / 명시적 범위 조정

The user explicitly added Windows ARM64 after implementation started, overriding
the original x64-only preparation scope. Include native ARM64 Codex CLI/Desktop
and Antigravity global/workspace lifecycle, installation/adoption/removal,
helper self-replacement and per-user opt-in stable updates. Preserve the same
reconciled v1.5.2 48-method/content revision-5 ten-language baseline. Native Windows Claude Code
and account upload remain excluded; `--host all` remains Codex. / 구현 중 사용자의
명시적 요청으로 ARM64를 추가했으며 본문·프로필 의미·계정 경계는 유지합니다.

ARM64 assets are `opensocrates-v1.6.0-windows-arm64.exe` and
`opensocrates-v1.6.0-windows-arm64.zip`, containing native manager/helper binaries
with the existing `bin/` names. Platform-qualified TUF target and Windows
Task Scheduler ownership/rollback policy remain architecture-specific. The
[official Codex 0.144.4 release](https://github.com/openai/codex/releases/tag/rust-v0.144.4)
contains aarch64 Windows CLI/app-server assets; GitHub's
[official runner matrix](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
provides `windows-11-arm`. Neither proves live host delivery. Antigravity native
architecture/actual ARM64 loading remains separately unverified. / 공식 배포·CI
가용성과 실제 실행·호스트 적용을 구분합니다.

The previous Windows VM is ARM64; x64-emulated observations are supplementary
and not native ARM64 acceptance. The [implementation handoff](IMPLEMENTATION_HANDOFF.md)
now records exact-commit native ARM64 runtime/lifecycle/ACL/reparse/scheduler/
helper/interruption/rollback evidence. Production signing/root/credentials,
original-installer adoption, clean-machine and actual host gates remain
unsatisfied until evidenced. / 에뮬레이션 결과를 네이티브 통과로 승격하지 않습니다.
인계에 실제 ARM64 네이티브 검사 커밋·결과를 기록하며 운영 서명·루트·자격,
원본 설치기부터의 이전, 새 기기·실제 호스트 검증은 별도 조건으로 남깁니다.

ARM64 production signing uses protected environment
`opensocrates-release-signing-windows-arm64` and an architecture-enforced native
`[Windows, ARM64, opensocrates-release]` runner. Windows CI separates
`windows-2025` x64 and `windows-11-arm` ARM64 lifecycle/timing/scheduler gates.
Metadata signing requires both `--windows-archive` and
`--windows-arm64-archive`; all three targets require native provenance, signing,
SBOM and platform-neutral content/export parity. These are configured gates,
not observed passes. / ARM64 서명·CI·메타데이터를 x64와 별도로 지정하며 설정만으로
실제 네이티브 통과나 운영 서명 완료를 주장하지 않습니다.
