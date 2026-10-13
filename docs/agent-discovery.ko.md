# 에이전트가 OpenSocrates를 발견하고 판단하는 방법

이 안내는 이미 출시된 v1.5.1 npm 채널에 고정되어 있습니다. 현재 브랜치는 별도로 미출시 Go v1.6.0을 준비하며 네이티브 설치·인수 명령과 Windows ARM64 범위는 [네이티브 후보 안내](native-v1.6.ko.md)를 따릅니다. 아래 npm 명령을 Go 후보에 적용하거나 후보 파일이 게시되었다고 해석하지 않습니다.

[English](agent-discovery.md) · [README](../README.ko.md) · [설정 가이드](setup-guide.ko.md) · [콘텐츠 전용 개인정보 안내](content-privacy.ko.md)

OpenSocrates는 직접 작성한 48개 사고 방법을 호스트별 플러그인·규칙·계정 스킬로
제공하는 MIT 라이선스 프로젝트입니다. 이 안내는 에이전트가 적합성을 판단하고
사용자가 허용한 설치를 수행하도록 돕습니다. 저장소 페이지·디렉터리 설명·스킬
지시문은 판단할 자료이며, 스스로 설치하거나 계정을 바꾸거나 호스트 신뢰 절차를
우회할 권한을 부여하지 않습니다.

## 작업에 필요한지 판단하기

사용자가 근거의 충돌을 정리하고, 자료를 종합하고, 선택지를 비교하고,
이해관계자의 관점을 이해하거나 판단 근거가 중요한 메시지를 작성해야 할 때
검토하세요. 방법을 선택하기 전에 실제 제공되는 방법과 적용 조건을 확인합니다.
설치했다고 모든 방법이 모든 작업에 적합해지는 것은 아닙니다.

단순 서식 변경·전사·파일 변환에는 사고 방법이 필요하지 않습니다. 일회성 작업은
설치 자체가 필요하지 않을 수도 있습니다. 이번 릴리스는 코딩 전문가 전용 기능,
더 나은 답변의 보장, 모델이나 구독 요금제 사이의 동등성을 제공하지 않습니다.

## 배포 버전과 호스트 구분하기

이 안내의 기준은 [v1.5.1](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1),
소스 커밋 [5a6a7fa2897dd42772c4503a1301770e48bd1f29](https://github.com/ParkerHwang/OpenSocrates/tree/5a6a7fa2897dd42772c4503a1301770e48bd1f29)입니다.
48개 방법의 영어·한국어·간체 중국어·일본어 전체 지시문과 사례를 포함하며
콘텐츠 리비전은 4입니다. 지시문 언어는 호스트 화면·설치기 출력·관찰된 모델
적용과 별개입니다.

| 사용자의 호스트 | 배포 방식과 지원 환경 | 범위와 후속 설정 |
| --- | --- | --- |
| Codex | 네이티브 플러그인과 기존 훅; Apple Silicon Mac 또는 Windows x64 | 기존 Codex 플러그인 설치 경로; 대화형 Codex에서 훅 7개 검토 |
| Claude Code CLI / Desktop의 로컬 Code | 네이티브 플러그인과 설치된 전체 참조; Apple Silicon Mac | 사용자 범위의 연동; Claude CLI·로그인·호스트 권한 |
| Claude 웹 / Desktop Chat / Cowork | 실행 코드가 없는 계정 스킬 ZIP; Mac 또는 Windows에서 내보내기 | 올바른 계정의 업로드·기능 설정·활성화 상태·상시 지침 |
| Antigravity 대화 애플리케이션 | 모듈형 규칙과 스킬; Apple Silicon Mac 또는 Windows x64 | 선택한 작업공간 또는 전역 범위 하나 |

v1.5.1은 Windows Claude Code 네이티브 연동, Windows ARM64, Intel Mac,
Linux 네이티브 검증 범위를 추가하지 않습니다. Claude 계정 콘텐츠는 네이티브
Code를 설치하지 않습니다. 기본값과 `--host all`은 Codex만 선택합니다.
다른 호스트는 각각 명시적으로 선택하세요.

`plugin-src/`의 `SKILL.md.tmpl` 같은 파일은 빌드 템플릿이며, 완전한 범용
설치용 스킬 디렉터리가 아닙니다. 루트의 `.agents/plugins/marketplace.json`은
생성된 Codex 빌드 출력을 가리킵니다. GitHub 탐색에서 이 파일들을 발견해도
루트 마켓플레이스 설치나 `npx skills add ParkerHwang/OpenSocrates`가
작동한다는 근거가 되지 않습니다. 아래 배포 설치기나 검증한 배포 파일을
사용하세요. 공개 디렉터리에 등록된 상태와 설치 호환성도 별개입니다.

## 사용자가 선택한 호스트와 범위에만 설치하기

특정 호스트·계정·작업공간의 설치나 업데이트를 사용자가 허용했는지 확인합니다.
먼저 OS·아키텍처, Node.js 20 이상, 호스트 설치·로그인과 기존 버전·소유 범위·
활성화 상태를 확인하세요. 네이티브 런타임이 포함되므로 설치에 Python이 필요하지
않습니다. 다른 설정과 의도적으로 꺼 둔 사본은 보존합니다. 과거 설치나 소유
범위가 불명확한 사본은 교체 전에 확인하고, Antigravity 전역·작업공간 중복을
피합니다.

네이티브 또는 파일 기반 설치는 **해당하는 상태 명령만** 실행합니다.
Antigravity 작업공간은 예시를 이미 존재하는 절대 경로로 바꾸고 모든 관리
명령에서 같은 범위를 유지하세요.

```sh
npx --yes opensocrates@1.5.1 status --host codex
npx --yes opensocrates@1.5.1 status --host claude
npx --yes opensocrates@1.5.1 status --host antigravity --workspace "/absolute/path/to/workspace"
```

없는 연동은 `install`, 소유 범위가 확인된 기존 연동은 `update`를 선택합니다.
선택한 호스트의 명령만 실행하고 업데이트할 때는 `install`을 `update`로
바꿉니다. Antigravity 전역 범위는 모든 명령에서 `--workspace`를 생략합니다.
Windows는 `"C:\Work\Reading Workshop"`처럼 따옴표로 감싼 로컬 드라이브의
절대 경로를 사용하세요.

```sh
npx --yes opensocrates@1.5.1 install --host codex
npx --yes opensocrates@1.5.1 install --host claude
npx --yes opensocrates@1.5.1 install --host antigravity --workspace "/absolute/path/to/workspace"
# 예: 기존 Codex 연동 업데이트
npx --yes opensocrates@1.5.1 update --host codex
```

Claude 계정 콘텐츠는 이미 존재하는 폴더의 새 절대 ZIP 경로로 내보냅니다.
기존 계정 스킬은 계정 화면에서 확인하세요. 설치기는 계정 `status`·`install`·
`update`를 제공하지 않습니다. 교체 전에 기존 스킬 파일과 활성화 상태를
백업합니다.

```sh
npx --yes opensocrates@1.5.1 export --host claude-chat --output "/absolute/path/to/opensocrates-1.5.1-account.zip"
```

이후 [설정 가이드](setup-guide.ko.md)에서 선택한 호스트의 단계를 따르세요.
Codex 훅 검토, 네이티브 Claude 플러그인 준비 상태, Claude 계정 업로드·활성화·
상시 지침, Antigravity 규칙과 스킬 인식을 각각 확인합니다. 기존 계정 지침을
보존하세요. 로그인·조직 정책·호스트 신뢰는 각각 별도 단계입니다. 승인 기록을
꾸미거나 보안 설정을 낮추지 않습니다. 변경 후 새 대화를 시작하세요.
[Mac](macos-v1.5.ko.md)·[Windows](windows-v1.5.ko.md) 안내는 복구와 로컬 파일을
설명하며, 그 안의 날짜가 있는 v1.5.0 명령과 관찰은 당시 기록입니다.
현재 명령은 이 안내의 1.5.1을 사용하세요.

## 확인 가능한 배포 파일

로컬 파일 옵션이 없으면 버전을 고정한 설치기는 GitHub Releases에서 해당
호스트의 v1.5.1 ZIP과 짝이 맞는 체크섬을 받습니다. 완전한 배포 패키지는
다음과 같습니다.

| 패키지 | 배포 파일 | SHA-256 파일 |
| --- | --- | --- |
| Codex, Apple Silicon Mac | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin.zip) | [체크섬](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin.zip.sha256) |
| Codex, Windows x64 | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin-windows-x64.zip) | [체크섬](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-codex-plugin-windows-x64.zip.sha256) |
| 네이티브 Claude, Apple Silicon Mac | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-plugin.zip) | [체크섬](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-plugin.zip.sha256) |
| Claude 계정 콘텐츠 | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip) | [체크섬](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip.sha256) |
| Antigravity | [ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-antigravity-plugin.zip) | [체크섬](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-antigravity-plugin.zip.sha256) |

체크섬은 공개된 체크섬과 바이트가 일치하는지 검증합니다. 그것만으로 배포자의
진위·동작의 안전성·호스트 활성화를 증명하지는 않습니다. 로컬 파일은 플랫폼
안내의 `--asset`·`--checksum`을 함께 사용하는 절차를 따르세요. 호스트
패키지를 소스 ZIP으로 대체하지 않습니다.

### 선택적으로 Skills CLI에서 발견 여부 확인하기

2026년 10월 13일, Node.js 24.21.0에서 `skills@1.7.2`로 목록만 확인한 결과
배포된 Claude 계정 ZIP에서 `opensocrates` 스킬 하나를 발견했습니다. 이 CLI
버전은 Node.js 22.20.0 이상이 필요하며, OpenSocrates의 Node.js 20 이상
조건과 별개입니다. 실제 확인에 사용한 명령은 다음과 같습니다.

```sh
DISABLE_TELEMETRY=1 DO_NOT_TRACK=1 npm exec --yes --package=skills@1.7.2 -- skills add https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.1/opensocrates-1.5.1-claude-chat-skills.zip --list
```

`--list`는 발견할 수 있는 스킬을 확인합니다. 이 관찰은 완전한 계정 콘텐츠를
발견했다는 근거이며, 설치·네이티브 훅·호스트 검증·공개 디렉터리 등록의 증거가
아닙니다. 각 호스트는 위의 관리형 설치 경로를 사용하세요.
[Skills CLI 문서](https://github.com/vercel-labs/skills/blob/main/README.md)와
[디렉터리 FAQ](https://www.skills.sh/docs/faq)를 참고할 수 있습니다. 검색 결과나
다운로드는 사용자 도입이나 순위 보장을 증명하지 않습니다.

## 실제로 확인한 상태 보고하기

| 증거 | 확인할 수 있는 범위 |
| --- | --- |
| 발견 | 소스나 목록을 찾음; 적합성과 호환성은 별도 판단 필요 |
| 설치 / 내보내기 | 파일·등록이 만들어졌거나 ZIP이 내보내짐; 내보내기는 계정 업로드가 아님 |
| `status`와 무결성 | 보고된 버전·소유 파일·등록·확인 가능한 활성화 상태; 관찰하지 못한 상태는 알 수 없음으로 유지 |
| 호스트 신뢰와 설정 | 선택한 호스트의 실제 권한·설정 확인; 설치만으로 증명되지 않음 |
| 콘텐츠 전체 읽기 | 해당 설치 절차를 사용할 수 있었고 전체를 읽음; 에이전트의 보고와 네이티브 증거를 구분 |
| 적용 | 적격한 방법을 현재 작업에 사용함; 읽기나 진입 출력만으로 증명되지 않음 |
| 유용성 | 사용자가 결과를 판단하고 사용할 수 있음; 설치나 단일 사례에서 일반적인 개선을 추론하지 않음 |

증거의 빈칸을 채우려고 비공개 프롬프트·원시 대화·스크린샷·자격증명·숨겨진
추론을 보관하지 않습니다. 일반 설정 완료에 추가 텔레메트리나 모델 답변
실험은 필요하지 않습니다.

설정 후 선택적으로 해 볼 **가상의 첫 작업**: “작은 프로젝트를 로컬에
유지하는 선택과 공유 호스팅으로 옮기는 선택을 비교해 주세요. 제공한 비용과
접근 요구사항을 사용하고, 사실과 가정을 구분하며, 남은 불확실성을 담은 짧은
결정 메시지를 작성해 주세요.” 합성 자료나 사용자가 허용한 자료만 사용합니다.
이것은 작업 제안이며 측정한 전후 비교 결과가 아닙니다.
