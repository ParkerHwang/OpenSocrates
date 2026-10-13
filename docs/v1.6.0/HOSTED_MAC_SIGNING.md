# Hosted Mac signing / GitHub Mac 서명 환경

The user approved hosted Mac ARM64 execution and encrypted GitHub environment
custody of the dedicated Developer ID P12/password and CI notarization credential.
Each release still requires the user's direct approval; merge, tagging and
publication of the current Draft remain separate. / 사용자가 GitHub 일회성 Mac과
서명 P12·암호·CI 공증 자격 증명의 암호화 비밀 보관을 승인했습니다. 릴리스마다
본인이 직접 승인하며 현재 Draft의 병합·태그·게시는 별도입니다.

## Execution and custody / 실행과 보관

The Mac job uses fixed `macos-15`, a fresh hosted ARM64 VM. The OS label does
not pin an image revision, so qualification records actual OS/tool versions.
Go tools/runtime are built and tested before credential injection. Only the
prepare step receives secrets. / Mac은 `macos-15`의 새 ARM64 VM을 사용합니다.
이미지 세부 버전은 고정되지 않아 실제 OS·도구 버전을 기록합니다. Go 도구·실행
파일을 먼저 빌드·검사하고 준비 단계만 비밀값을 받습니다.

| Encrypted environment secret / 암호화 환경 비밀 |
| --- |
| `OPENSOCRATES_MAC_CERTIFICATE_P12_BASE64` |
| `OPENSOCRATES_MAC_CERTIFICATE_PASSWORD` |
| `OPENSOCRATES_NOTARY_APPLE_ID` |
| `OPENSOCRATES_NOTARY_APP_PASSWORD` |

Public variables name the certificate SHA1, Team ID and `opensocrates-notary-ci`
profile. The Go prepare tool validates the exact Developer ID/private identity,
imports it into a new owned temporary keychain and validates that notary profile.
P12 bytes are removed after import; the random keychain password remains only
in memory. Source inspection excludes secret inputs, OS output is bounded and
private, and artifacts contain only closed public evidence. / 공개 변수는 인증서
SHA1·팀 ID·공증 프로필 이름입니다. Go 도구가 정확한 인증서·개인키와 공증 인증을
확인해 전용 임시 키체인에 등록합니다. P12는 가져오기 후 삭제하고 키체인 암호는
메모리에만 둡니다. 소스 검사에 비밀을 전달하지 않고 내부 출력은 제한하며 공개
산출물에는 안전한 증거만 포함합니다.

Preparation failures roll back. The `always()` cleanup removes only owned
marker-bound keys/files and restores the original search list. Existing keychains
and ACLs are preserved; unexpected foreign changes are reported. / 준비 실패는
롤백하고 항상 실행되는 정리는 자신이 만든 키체인·파일만 삭제하며 검색 목록을
복원합니다. 기존 키체인·접근 규칙과 다른 변경을 보존합니다.

## Direct approval / 직접 승인

The sole required reviewer is `ParkerHwang`. Administrator bypass is disabled.
`prevent_self_review=false` lets the owner approve a run they started; no run is
approved automatically. Production environments allow only `v*` tags, while
the Go publisher retains exact remote-tag/source/version/merged-main guards.
/ 필수 승인자는 사용자 한 명이며 관리자 우회는 금지합니다. 본인 승인 허용은 직접
시작한 작업을 본인이 승인할 수 있다는 뜻으로 자동 승인이 아닙니다. 운영 환경은
`v*` 태그만 허용하며 정확한 태그·소스·버전·main 병합 검사도 유지합니다.

| Environment / 환경 | Scope / 범위 |
| --- | --- |
| `opensocrates-release-signing-macos` | Hosted Mac signing / Mac 서명 |
| `opensocrates-release-signing` | Retained Windows x64 / Windows x64 |
| `opensocrates-release-signing-windows-arm64` | Retained Windows ARM64 / Windows ARM64 |
| `opensocrates-release-publication` | Release/metadata publication / 게시 |
| `github-pages` | Stable metadata activation / 메타데이터 적용 |

Windows signing and metadata resources remain independently unprovisioned;
approval policy creation is not execution evidence. / Windows 서명·메타데이터 자원은
별도 준비가 필요하며 승인 정책 생성만으로 실행 성공을 주장하지 않습니다.

## Pre-merge qualification / 병합 전 검증

The separate owner-reviewed `opensocrates-macos-signing-qualification` environment
allows only `codex/v1.6-go-native` pushes. Scheduling additionally requires
`OPENSOCRATES_MAC_SIGNING_QUALIFICATION_ENABLED=true` and a separate
`OPENSOCRATES_MAC_SIGNING_QUALIFICATION_SHA` equal to the push SHA. Other refs,
forks and later commits cannot schedule the enabled target. / 후보 환경은 지정
브랜치 push만 허용하고 같은 직접 승인·우회 금지 조건을 적용합니다. 실행 스위치와
별도 지정 SHA도 일치해야 하므로 fork·다른 ref·후속 커밋에는 적용되지 않습니다.

The Go gate checks native hosted execution, repository/branch, clean exact
source/build identity and owned prepared keychain. It signs/packages, notarizes
payload then standalone installer, binds both Accepted logs to final hashes and
code tickets, verifies all five distributed files and runs the documented release
check. Wait timeouts never resubmit. Ticket retries occur only after acceptance
of unchanged bytes. Candidate schemas cannot qualify production publication;
tag/Actions identities are not fabricated and production TUF/publication is not
activated. / Go 검증이 실제 환경·저장소·브랜치·소스·빌드·키체인을 확인합니다.
페이로드 뒤 설치기를 공증하고 로그·해시·티켓·파일 5개·배포 검사를 확인합니다.
대기 시간 초과로 중복 제출하지 않고 승인된 바이트에 대해서만 티켓 확인을 재시도합니다.
별도 후보 증거는 운영 게시를 허용하지 않으며 태그·실행 환경을 위조하거나 운영
루트·공개 릴리스를 적용하지 않습니다.

After success, disable qualification and remove its temporary credential copies.
Production secrets remain for the later reviewed merged tag. Actual approval,
hosted execution, notarization and cleanup results belong in the handoff.
Configuration/tests alone do not establish them. / 검증 후 스위치를 끄고 후보 환경의
비밀 사본을 제거합니다. 운영 비밀은 이후 검토한 병합 태그를 위해 보관하며 실제
승인·실행·공증·정리 결과를 인계에 기록합니다. 설정·소스 검사와 구분합니다.

Fresh-machine quarantined download/host activation, production trust/key custody,
Windows signing and metadata/publication remain separate gates. / 새 기기의 다운로드·
호스트 적용·운영 루트와 키 보관·Windows 서명·게시 검증은 별도 조건입니다.

## Primary references / 공식 근거

- [Hosted ARM64 runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [Apple certificate import](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications)
- [Environment reviewers and bypass](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [Deployment tag/branch policies](https://docs.github.com/en/rest/deployments/branch-policies)
- [Feature-branch push workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#push)
