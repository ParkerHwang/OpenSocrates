# Release environment review / 릴리스 환경 검토

This is preparation for Draft PR #112, not approval to merge, tag, publish or
transfer signing secrets. Exact live observations and execution results belong
in the implementation handoff. / PR #112의 릴리스 준비 문서입니다. 병합·태그·게시·
서명 비밀 전송 승인과 구분하며 실제 관찰·실행 결과는 구현 인계에 기록합니다.

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
bypass actors. Required check names still refer to the previous Python/npm
implementation. / main은 활성 ruleset으로 보호됩니다. 고전 branch-protection
API의 404를 보호 없음으로 해석하지 않습니다. PR 경유·최신 main 기준 검사·리뷰
대화 해결·삭제/강제 푸시 차단·우회 불가 조건을 유지합니다. 필수 검사 이름은
이전 Python/npm 구현 기준이어서 수정이 필요합니다.

## Required-check proposal / 필수 검사 수정안

Replace only the required status-check list with these observed Go workflow
check names; keep every other ruleset field, strict checking and GitHub Actions
integration binding unchanged. Application requires the user's approval because
this changes the repository's merge conditions. / 아래 실제 Go 검사 이름으로 필수
검사 목록만 교체하고 나머지 보호 조건·엄격한 검사·GitHub Actions 연결은 유지합니다.
저장소 병합 조건을 바꾸는 설정이므로 적용은 사용자 승인 후 진행합니다.

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

The current workflow requires an isolated ephemeral self-hosted Mac ARM64
runner. A normal development Mac or an `--ephemeral` registration alone does
not prove a fresh/discarded filesystem. / 현재 workflow는 격리된 일회성 Mac ARM64
runner를 요구합니다. 개발 Mac이나 일회성 runner 등록만으로 파일시스템 초기화·
폐기를 입증하지 않습니다.

A supported alternative is a fixed GitHub-hosted `macos-15` ARM64 job with a
protected signing environment and a temporary per-job keychain. Standard hosted
Mac jobs use fresh VMs. This alternative requires a reviewed workflow change;
the existing self-hosted configuration does not implement it. / 대안은 보호 환경과
작업별 임시 키체인을 사용하는 고정 `macos-15` ARM64 GitHub 실행 환경입니다.
표준 hosted Mac 작업은 새 VM을 사용합니다. 현재 self-hosted 설정에 바로 적용되는
값이 아니라 별도 구현·리뷰가 필요한 대안입니다.

Hosted signing needs explicit approval to place the purpose-specific Developer
ID private-key P12, P12 password and CI notarization credential in encrypted
GitHub environment secrets. Local `opensocrates-notary` registration does not
provision remote authentication. Create a separate CI credential and use only a
temporary owned keychain, with unconditional cleanup. No signing secret has
been transferred by this preparation. / hosted 서명은 개인키가 포함된 P12·P12 암호·
CI 전용 공증 자격 증명을 GitHub 암호화 비밀에 맡기는 승인이 필요합니다. 로컬
프로필 이름만으로 원격 인증은 준비되지 않습니다. CI 자격 증명을 분리하고 임시
키체인을 종료 때 정리해야 합니다. 이번 준비에서는 비밀값을 전송하지 않았습니다.

## Environment policy decisions / 승인 환경 결정

Signing/publication environments should require a designated reviewer, prohibit
administrator bypass, and allow only selected release tags. A tag rule such as
`v*` does not replace the exact merged-main/tag/source checks in the Go publisher.
An independent reviewer permits `prevent_self_review=true`; a sole maintainer
must explicitly choose a solo manual-review policy or add a real second reviewer.
Listing multiple reviewers requires one of them, not all of them, to approve.
/ 서명·게시 환경에는 지정 승인자·관리자 우회 금지·릴리스 태그 제한이 필요합니다.
태그 이름 제한은 Go 게시자의 정확한 태그·병합 main·소스 검사를 대신하지 않습니다.
본인 승인 금지를 쓰려면 실제 독립 승인자가 필요합니다. 단독 운영이라면 별도
승인 정책을 결정하거나 두 번째 승인자를 지정해야 하며, 여러 승인자 등록은 전원의
승인을 요구하는 설정이 아닙니다.

Final release qualification still needs the chosen runner's actual execution,
approved production trust/key custody, Windows signing, immutable publication
credentials, maintained metadata hosting, clean-machine quarantined download
and actual host activation. Candidate notarization does not satisfy these gates.
/ 선택한 환경에서의 실제 실행·운영 루트와 키 보관·Windows 서명·게시 자격·메타데이터
운영·새 기기의 다운로드·실제 호스트 적용은 별도 릴리스 조건으로 남습니다.

## Primary references / 공식 근거

- [GitHub hosted runner labels and environments](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
- [GitHub Apple signing certificates](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications)
- [GitHub environment policies](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)
- [GitHub deployment review and self-review](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments)
- [GitHub self-hosted runner security](https://docs.github.com/en/actions/reference/security/secure-use)
- [Apple CLI notarization verification](https://developer.apple.com/forums/thread/130560)
