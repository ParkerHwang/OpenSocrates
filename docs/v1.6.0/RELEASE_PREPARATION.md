# Remaining v1.6.0 release preparation / 남은 릴리스 준비

This records independently actionable preparation for Draft PR #112. It does
not authorize merge, tagging, publication, production trust adoption or replacing
an active installation. / PR #112에서 진행 가능한 준비와 사용자 준비·승인 항목을
구분합니다. 병합·태그·게시·운영 신뢰 적용·기존 설치 교체 승인은 별도입니다.

## Available qualification commands / 추가 검증 명령

Run after complete integration, on the reported native platform:

```text
go run ./src/opensocrates/cmd/opensocrates-dev acceptance network-update --report build/evidence/development-https-update.json
go run ./src/opensocrates/cmd/opensocrates-dev acceptance legacy-selector --host-binary /absolute/path/to/codex-0.144.4 --codex-home /absolute/path/to/existing/.codex --report build/evidence/authenticated-legacy-selector.json
```

`network-update` uses real HTTPS and the production transport/repository code
with ephemeral development TUF/TLS keys and an explicitly trusted loopback
server. It verifies signed metadata/archive retrieval, bounded synthetic archive
parsing, shared lifecycle activation/rollback, tampering, expiry, rollback
protection and offline preservation. It does not modify the compiled production
root, contact public update servers, replace native executable bundles, or prove
production publisher/self-update qualification. / 실제 HTTPS·기존 전달/저장소 코드를
일회용 개발 키와 로컬 서버로 검사합니다. 운영 루트·공개 서버·네이티브 실행파일
자체 갱신 검증과 구분하며 기존 설치·예약 작업을 변경하지 않습니다.

`legacy-selector` is explicit, invokes exactly one fixed synthetic selection
using the existing protected OAuth file and external Codex **0.144.4**, and
removes its disposable environment through the production selector. It does not
start a login flow, inherit user workspace/transcript content, change model
settings or install hooks. It may consume existing host-account model quota.
Public receipts contain closed results and validity booleans, never prompts,
credentials, selected content or raw errors. Passing proves authenticated
adapter operation, not answer improvement or delivery into an existing session.
Prerequisite failures remain unavailable. / 명시적인 검증에서 기존 로그인과 고정
합성 입력으로 선택을 한 번 요청합니다. 추가 모델 사용량이 발생할 수 있으며
사용자 대화·작업공간을 읽지 않습니다. 인증된 어댑터 동작과 실제 호스트 적용·
답변 품질을 구분합니다. 일반 테스트 모음은 모델을 호출하지 않습니다.

## Observed prerequisites / 확인한 준비 상태

Initial read-only checks on 2026-10-12 found no valid code-signing identities in the
current Mac keychain, no repository release environments or self-hosted runners
listed by GitHub, and empty production publisher IDs/root inputs. The GitHub
Pages GET returned 404: the API did not establish a configured accessible site.
Immutable releases were verified enabled. / 최초 확인 시 Mac의 서명 identity는 0개,
GitHub 배포 환경·전용 runner 목록도 0개입니다. 운영 identity는 비어 있고 루트는
`{}`입니다. Pages 조회는 404로 설정·접근 가능 상태를 확인하지 못했습니다.
Immutable release 설정은 켜짐을 확인했습니다.

The user's Apple Developer membership is present, but the actual Certificates
page returned **Access Unavailable**, explicitly requiring acceptance of the
latest Program License Agreement. The existing certificate inventory is therefore
unknown; an empty local keychain does not prove that the account has no issued
certificates. The contract review was opened without acceptance. No account
identity/contact details or credentials are retained here. / Apple 유료 회원
화면은 확인했지만 인증서 목록은 최신 약관 미동의로 차단됐습니다. 계정의 기존
발급 목록은 미확인입니다. 계약 검토 화면만 열었으며 동의·인증서 변경은 하지
않았습니다. 개인정보·자격 증명은 이 문서에 기록하지 않습니다.

## Completed in this follow-up / 이번에 완료한 준비

The user accepted the account agreement, then authorized Developer ID
Application issuance for OpenSocrates. The public certificate was issued and
matched to the locally generated private key; the code-signing usage, account
team, validity and Apple certificate chain were verified. Only the public CSR
was uploaded. The private key and a dedicated signing keychain remain on this
Mac, outside the repository. Existing keychain item ACLs were not changed; a
new owned signing keychain avoids changing access rules for unrelated keys.
The public Mac Team ID is now bound in canonical/embedded publisher configuration.
The TUF root remains `{}` and the Windows identity remains unprovisioned.
/ 사용자가 계약에 동의했고 OpenSocrates용 인증서를 발급했습니다. 개인키 일치·
용도·팀·유효기간·Apple 인증 경로를 확인했습니다. 공개 CSR만 업로드했으며
개인키·전용 키체인은 Mac에만 있습니다. 기존 키의 접근 규칙은 변경하지 않았고,
공개 Mac Team ID만 정본·임베드 설정에 반영합니다. TUF 루트는 비어 있습니다.

Actual Developer ID signatures, hardened runtime, trusted team and secure
Apple timestamps passed for disposable copies of the manager and update helper
at source 306b74c. This does not qualify notarization, Gatekeeper activation,
protected CI signing runners or a production release. / 관리자·도우미 복사본의 실제
서명·강화 런타임·팀·타임스탬프가 통과했습니다. 공증·Gatekeeper·CI 서명 환경·
운영 릴리스 검증과 구분합니다.

The explicit authenticated 0.144.4 selector passed one synthetic selection
within 8.5 seconds. A post-run observation found zero matching selector
processes and zero selector temporary directories. Actual Codex
0.162.0-alpha.17.2 private install/status/diagnose/same-version-update/remove
also passed, with active auth/config bytes unchanged. Different-version update,
host-disabled preservation and user-approved live session activation are not
claimed by that private registration probe. The development HTTPS gate passed
signed retrieval, bounded archive/lifecycle rollback and rejection preservation.
/ 실제 인증된 선택은 8.5초에 통과했고 종료 뒤 해당 프로세스·임시 디렉터리가
남지 않았습니다. 실제 Codex의 격리 설치·진단·동일 버전 갱신·제거도 통과했습니다.
새 버전 적용·비활성 호스트 보존·신뢰 승인·실제 대화 적용을 과장하지 않습니다.

## User resources and approvals / 사용자 준비·승인

| Area / 구분 | Concrete prerequisite / 준비할 항목 | Boundary / 구분 |
| --- | --- | --- |
| Apple account / Apple 계정 | Completed: agreement accepted and certificate issued / 계약 동의·인증서 발급 완료 | Contract consent is a distinct account-owner decision / 계약 동의는 별도 결정 |
| Mac signing / Mac 서명 | Current Mac ready; separately provision the isolated CI signing runner / 현재 Mac 준비 완료, 격리 CI 서명 runner는 별도 준비 | `OPENSOCRATES_MAC_SIGN_IDENTITY`, `OPENSOCRATES_MAC_TEAM_ID`; verify public `darwin_team_id` |
| Mac notarization / Mac 공증 | An authenticated notarytool keychain profile / 공증용 키체인 프로필 | `OPENSOCRATES_NOTARY_KEYCHAIN_PROFILE` names the profile; passwords/API keys stay outside source/chat |
| Windows signing / Windows 서명 | SignPath Foundation application handled in the separate user chat; approved project/policy and hosted integration details / 별도 채팅의 무료 신청 승인·프로젝트/policy 정보 | Application and release signing approval are different; see hosted workflow constraints below |
| Update trust / 업데이트 신뢰 | Independently approved public threshold root, publisher certificate identity, offline root custody and online metadata key handling / 승인한 공개 루트·서명자·오프라인 키 보관·온라인 역할 키 운영 | Root threshold at least 2, consistent snapshots, expiry beyond 30 days; no test keys promoted |
| Release infrastructure / 배포 환경 | Isolated signing runners and protected environments / 격리 서명 runner·보호 환경 | `opensocrates-release-signing`, `opensocrates-release-signing-windows-arm64`, `opensocrates-release-publication`, `github-pages`; approvers/tag policy require user choice |
| Immutable publication / 변경 불가 게시 | Repository-scoped Administration:read credential / 이 저장소만의 Administration:read 자격 | Secret `OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN`; publication writes remain on normal workflow token |
| Metadata hosting / 메타데이터 서버 | Approved GitHub Actions Pages site and ongoing timestamp refresh / Actions Pages 설정과 timestamp 갱신 담당 | Current timestamp expires in 48 hours; one release run does not maintain the channel |
| Windows original adoption / 원본 Windows 이전 | Compatible unelevated user environment for unmodified v1.5 installer / 원본 v1.5 설치기가 통과하는 일반 사용자 환경 | New account/OS changes need separate authorization; source-equivalent payload success stays PARTIAL |
| Clean machines / 새 기기 | Fresh OS environments for claimed native targets / 지원 주장별 새 OS 환경 | New directories or a new account on this used machine are not clean-machine proof |
| Host activation / 실제 적용 | User-reviewed hook trust, fresh sessions/reload, account skill upload when selected / 훅 신뢰 승인·새 세션·계정 스킬 업로드 | Installing files/registration never auto-approves trust or updates running conversations |

The production release workflow already enforces approved Actions execution,
exact remote release tag and source merged into protected main. Do not fake
those environment inputs to qualify a candidate branch. / 기존 운영 workflow의
승인·원격 태그·보호 main 기준을 후보 브랜치 검증을 위해 위조하지 않습니다.

## SignPath Foundation integration boundary / SignPath 연동 경계

The separate chat **OpenSocrates용 신청 및 발급** is preparing the Foundation
application. It is not yet an observed approved signing configuration. Foundation
keeps private keys in its HSM; the supported hosted path needs API submitter
access, organization ID, project slug, signing-policy slug and GitHub artifact ID.
The public certificate can be downloaded; private-key PFX export is not assumed.
/ 별도 신청 채팅은 진행 중이며 승인·서명 연동 완료로 주장하지 않습니다.
개인키는 재단 HSM에 있고 hosted API 입력이 필요합니다.

Current `release.yml` uses self-hosted jobs and local `signtool /sha1` signing.
Foundation requires all jobs preceding its signing request to use GitHub-hosted
runners. Prepare a separate Windows hosted build/sign origin, then independently
qualify the returned signed binaries and package them for the approved release.
The existing local certificate-store path cannot consume the hosted approval
unchanged. Exact organization/project/policy inputs and approved certificate
must be obtained before activation. / 현재 self-hosted·로컬 인증서 저장소 방식은
재단 hosted 경로와 그대로 호환되지 않습니다. Windows hosted 빌드·서명 원본과
반환 서명본 검증·패키징을 분리하고 승인한 ID·인증서로 연동해야 합니다.

The existing Windows DER certificate SHA256 pin may use the approved public
leaf certificate, but certificate renewal needs an explicit trust transition.
It is not a perpetual publisher identity. Microsoft Artifact Signing has a
separate rotating-certificate integration and is not a substitute configuration
for this chosen SignPath application. / 현재 DER 인증서 pin은 승인한 공개 인증서에
연결할 수 있으나 갱신 시 신뢰 전환이 필요합니다. 선택한 SignPath 신청에 다른
서비스의 설정을 혼용하지 않습니다.

A restricted-current-user Windows probe kept original token/account/security
settings unchanged and created user-owned files, but the original v1.5 private
helper still failed. No fallback layout was used. This remains unavailable
original-installer qualification; see the exact receipt in the handoff.
/ 계정·보안 설정을 유지한 제한 권한 프로세스에서도 원본 Windows 설치기의
private helper가 통과하지 않았습니다. 호환되는 일반 사용자 환경은 여전히
필요하며 권한·소유권 검사를 완화하지 않습니다.

## Primary references / 공식 근거

- [Apple Developer ID certificates](https://developer.apple.com/help/account/certificates/create-developer-id-certificates/)
- [Apple CSR preparation](https://developer.apple.com/help/account/certificates/create-a-certificate-signing-request)
- [Apple notarization credentials](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool)
- [SignPath GitHub origins and hosted action](https://docs.signpath.io/trusted-build-systems/github)
- [SignPath Foundation terms](https://signpath.org/terms)
- [GitHub protected environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)
- [GitHub immutable release permission](https://docs.github.com/en/rest/repos/repos#check-if-immutable-releases-are-enabled-for-a-repository)
- [TUF trust and roles](https://theupdateframework.github.io/specification/latest/)
