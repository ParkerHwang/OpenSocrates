# v1.6.0 implementation decisions / 구현 결정

These decisions apply to the unreleased Go candidate. The four preparation
documents remain planning references; actual command results and release gates
belong in the exact-commit implementation handoff. / 아래는 미출시 Go 후보의
구현 결정입니다. 준비 문서와 실제 실행·릴리스 증거를 구분합니다.

## Baseline / 기준

The preparation main was `9572db2c71a455d4ada24c78402d0f874002cec9`; the released
v1.5.0 content tag is `cf6634310afcf5d5ce58484e67a73151bb4c5999`, revision `3`.
V0 records canonical baseline inputs and hashes:

- `source_tree_hash`: `sha256:b8824656fc53d588cc6a570de102531266ef2a7b39f04694d058c8da5c2418a6`
- `normalized_semantic_hash`: `sha256:e50af8296165a7c8e8a9a6e27d4881bbc816b7efe9e1c84ea798c80fb54efa48`

All 48 method bodies, bilingual semantics, teacher questions, response policies
and shared guides are frozen. Separate method-body upgrades belong to v1.6.1 or
later. Source baseline selection is reconciled against current GitHub state,
not inferred from the planning checkout. PR #110 is the planning reference;
issue #109 tracks preparation only. / 48개 본문·양언어 의미·교사 질문·응답 정책·
공통 안내를 고정합니다. 본문 개선은 후속 릴리스이며 최신 GitHub와 기준을 조정해
구현합니다. 준비 issue를 구현 추적으로 재사용하지 않습니다.

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

The supported matrix is macOS ARM64 and Windows x64. Release bundles use
`opensocrates-v1.6.0-<target>.zip`, a `native-bundle/1.0.0` manifest, native manager
and update helper, version/content/schema identities and explicit host packages.
Native Claude is Mac-only. `--host all` remains Codex only. Account exports have
no executable, upload or activation. / 두 플랫폼과 기존 프로필만 유지하며 계정
활성화·Windows Claude·추가 플랫폼을 확대하지 않습니다.

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
newer settings never receive destructive fallback defaults. The compiled bundle
changes only release metadata `product_version` to `1.6.0`; method/projection/
policy identity remains revision `3`. / 입력 보강과 릴리스 메타데이터 변경을 본문
포팅과 구분하며 이전 상태·설정을 파괴하지 않습니다.

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
rather than textual macros. / 셸·경로 경계를 명시하며 새로운 플랫폼·자체 셸 구현을
추가하지 않습니다.

Production release orchestration is manual exact-tag execution through protected
signing/publication environments and ephemeral native macOS ARM64/Windows x64
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
