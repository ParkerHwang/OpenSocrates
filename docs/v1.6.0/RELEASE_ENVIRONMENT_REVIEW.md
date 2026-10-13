# Release environment review / 릴리스 환경 검토

This is preparation for Draft PR #112, not approval to merge, tag, publish or
transfer signing secrets. Exact live observations and execution results belong
in the implementation handoff. / PR #112의 릴리스 준비 문서입니다. 병합·태그·게시·
서명 비밀 전송 승인과 구분하며 실제 관찰·실행 결과는 구현 인계에 기록합니다.

Subsequent user approvals applied the Go required-check migration and selected
hosted Mac signing, encrypted GitHub custody and direct owner approval on every
release. [Hosted signing](HOSTED_MAC_SIGNING.md) records the implementation;
the observations below retain their initial source/date. / 이후 사용자 승인으로 Go
필수 검사 변경을 적용하고 GitHub Mac 서명·암호화 비밀 보관·매번 본인 승인 방식을
선택했습니다. 실제 구현은 별도 문서에 기록하며 아래 최초 관찰은 과거 상태입니다.

## Observed configuration / 확인한 설정

At source c9da20d, GitHub lists zero release environments, zero self-hosted
runners, and no repository Actions variables/secrets. Immutable releases are
enabled. The Pages API returned 404. No `v1.6.0` remote tag exists, and the
production TUF root is `{}`. Current source/native CI passed on macOS ARM64,
Windows x64 and Windows ARM64. These source jobs do not execute the signing or
publication workflow. / 릴리스 승인 환경·전용 runner·Actions 변수와 비밀 목록은
비어 있습니다. Immutable release는 켜져 있고 Pages 조회는 404입니다. 원격
v1.6.0 태그와 운영 TUF 루트는 아직 없으며, 소스·네이티브 CI 통과와 운영 서명·
게시 실행을 구분합니다.

Main is protected by active repository ruleset `20467374`, despite the classic
branch-protection API returning 404. Effective rules require a PR, current-main
checks, resolved review threads, and prohibit deletion/force pushes with no
bypass actors. Required check names referred to the previous Python/npm
implementation at that observation; the approved Go replacement is now applied.
/ main은 활성 ruleset으로 보호됩니다. 고전 branch-protection
API의 404를 보호 없음으로 해석하지 않습니다. PR 경유·최신 main 기준 검사·리뷰
대화 해결·삭제/강제 푸시 차단·우회 불가 조건을 유지합니다. 필수 검사 이름은
최초 관찰 당시에는 이전 Python/npm 기준이었고 이후 승인한 Go 목록으로 교체했습니다.

## Required-check proposal / 필수 검사 수정안

Replace only the required status-check list with these observed Go workflow
check names; every other ruleset field, strict checking and GitHub Actions
integration binding is unchanged. The user approved the change and effective
main rules/API readback were verified. / 아래 실제 Go 검사 이름으로 필수
검사 목록만 교체하고 나머지 보호 조건·엄격한 검사·GitHub Actions 연결은 유지합니다.
저장소 병합 조건 변경을 사용자 승인 후 적용했고 실제 main 규칙과 API를 확인했습니다.

| Required check / 필수 검사 |
| --- |
| `Go source and product contracts` |
| `Native macOS ARM64` |
| `Native Windows x64 and ARM64 / Native windows-x64` |
| `Native Windows x64 and ARM64 / Native windows-arm64` |
| `Repository governance` |

No admin bypass or obsolete-check bypass is proposed. The Draft and missing
release-evidence boundaries remain in force. / 관리자 우회나 누락 검사 무시는
제안하지 않습니다. Draft 상태와 미검증 릴리스 조건은 유지합니다.

## Mac signing execution options / Mac 서명 실행 환경

The initial workflow required an isolated ephemeral self-hosted Mac ARM64
runner. A normal development Mac or an `--ephemeral` registration alone does
not prove a fresh/discarded filesystem. / 현재 workflow는 격리된 일회성 Mac ARM64
runner를 요구합니다. 개발 Mac이나 일회성 runner 등록만으로 파일시스템 초기화·
폐기를 입증하지 않습니다.

A supported alternative is a fixed GitHub-hosted `macos-15` ARM64 job with a
protected signing environment and a temporary per-job keychain. Standard hosted
Mac jobs use fresh VMs. This alternative is implemented by the subsequent
workflow change; actual execution is recorded separately. / 대안은 보호 환경과
작업별 임시 키체인을 사용하는 고정 `macos-15` ARM64 GitHub 실행 환경입니다.
표준 hosted Mac 작업은 새 VM을 사용합니다. 이후 workflow 변경으로 구현했으며
실제 실행 증거는 별도로 기록합니다.

The user approved encrypted GitHub custody of the purpose-specific Developer
ID P12/password and separate CI notarization credential. They are registered in
the owner-protected Mac environment, with temporary copies for qualification.
Local temporary export/password files were removed. The CI credential validated
against Apple; actual hosted import/signing/notarization/cleanup is recorded
separately. / 개인키 P12·암호·별도 CI 공증 자격 증명의 GitHub 암호화 보관을 사용자
승인 후 Mac 보호 환경에 등록했습니다. 후보 검증용 사본은 임시이며 로컬 내보내기·
암호 파일은 삭제했습니다. CI 자격 증명은 Apple에서 확인했고 실제 GitHub 가져오기·
서명·공증·정리 실행 결과는 별도입니다.

## Environment policy decisions / 승인 환경 결정

Signing/publication environments require the sole designated user reviewer,
prohibit administrator bypass, and allow only selected release tags. A tag rule such as
`v*` does not replace the exact merged-main/tag/source checks in the Go publisher.
The selected solo policy uses `prevent_self_review=false`, permitting the owner
to approve their own initiated run without automatic approval. Listing multiple
reviewers would require one of them, not all of them, to approve.
/ 서명·게시 환경에는 사용자 한 명의 직접 승인·관리자 우회 금지·태그 제한을 적용했습니다.
태그 이름 제한은 Go 게시자의 정확한 태그·병합 main·소스 검사를 대신하지 않습니다.
선택한 단독 운영 정책은 직접 시작한 작업을 본인이 승인할 수 있고 자동 승인은
하지 않습니다. 여러 승인자 등록이 전원 승인을 요구하는 설정은 아닙니다.

The hosted Mac candidate's actual approved execution, signing/notarization and
credential cleanup passed at `9be0e5e`; see the exact receipts and subsequent
cleanup in [hosted signing](HOSTED_MAC_SIGNING.md). Final release qualification
still needs merged-tag execution, approved production trust/key custody,
Windows signing, immutable publication
credentials, maintained metadata hosting, clean-machine quarantined download
and actual host activation. Candidate notarization does not satisfy these gates.
/ GitHub Mac 후보는 9be0e5e에서 직접 승인 후 실제 실행·서명·공증·비밀 정리까지
통과했습니다. 최종 병합 태그·운영 루트와 키 보관·Windows 서명·게시 자격·메타데이터
운영·새 기기의 다운로드·실제 호스트 적용은 별도 조건으로 남습니다.

## Primary references / 공식 근거

- [GitHub hosted runner labels and environments](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Apple signing certificates](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications)
- [GitHub environment policies](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [GitHub deployment review and self-review](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments)
- [GitHub self-hosted runner security](https://docs.github.com/en/actions/reference/security/secure-use)
- [Apple CLI notarization verification](https://developer.apple.com/forums/thread/130560)
