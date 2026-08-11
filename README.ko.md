<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

[English](README.md) | **한국어**

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![Release](https://img.shields.io/github/v/release/ParkerHwang/OpenSocrates)](https://github.com/ParkerHwang/OpenSocrates/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

OpenSocrates는 Claude와 Codex를 위한 로컬 연동 및 저작 추론 프레임워크입니다.
의도적인 추론이 필요한 요청을 감지하고, 현재 호스트의 새로운 셀렉터에서 적합한
추론 시스템을 고른 뒤, 이론과 예제 전체를 활성 작업에 추가합니다. 단순한 사실
확인과 기계적인 작업은 그대로 통과할 수 있습니다.

버전 `1.1.2`에는 48개의 추론 시스템, Claude의 단일 사용자 진입점, 선택된 절차를
실제로 읽었는지 확인하는 Claude 접지 게이트, Claude/Codex 통합 라이프사이클,
선택형 자동 업데이트가 들어 있습니다. 현재 릴리스 플랫폼은 Apple Silicon
macOS(`darwin-arm64`)입니다. 기존 호스트 로그인을 사용하므로 API 키나
OpenSocrates 백엔드가 필요하지 않습니다.

네이티브 플러그인 아카이브에는 의도적으로 `bin/launch.sh`만 포함됩니다. 이
런처는 `darwin-arm64`만 허용하며, Intel Mac·Linux·Windows용 런처와 런타임은
이번 릴리스에 포함되거나 지원되지 않습니다.

> **최신 릴리스: [OpenSocrates 1.1.2](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.1.2).**
> 인증된 Claude 접지 영수증, 한 번으로 제한된 보정, 아티팩트 인스턴스에 결합된
> 재사용 방지를 추가했습니다. `npx --yes opensocrates@1.1.2 update --host all`로
> 관리 중인 두 호스트를 함께 업데이트할 수 있습니다.

## 호스트 지원 범위

| 호스트 화면 | 자동 선택 | 사용자 진입점 | 검증 상태 |
| --- | --- | --- | --- |
| Codex CLI 및 Desktop | 지원 | OpenSocrates 플러그인 | `darwin-arm64` 릴리스 검증 완료 |
| Claude Code CLI | `UserPromptSubmit` 훅으로 지원 | `/opensocrates` | `darwin-arm64` 로컬 검증 완료 |
| Claude Code 데스크톱 앱 | Claude Code 플러그인이 실행되는 곳에서 구현됨 | `/opensocrates` | [실측 probe 차단](docs/claude-desktop-live-probe.md), 수신 기록 없음 |
| Claude Cowork | 로컬 플러그인 런타임을 사용할 수 있을 때 구현됨 | `/opensocrates` | [CLI 등록 확인, Cowork probe 차단](docs/claude-cowork-live-probe.md) |
| Claude 웹 및 Desktop Chat | 훅 미지원 | `/opensocrates` | [아카이브 검증, UI 업로드 차단](docs/claude-chat-upload-probe.md) |

상태 열은 서로 다른 네 단계를 뜻하며 같은 의미로 읽으면 안 됩니다.

- **구현 완료** — 코드에 존재하고 패키지에 포함됩니다.
- **로컬 검증 완료** — 관리자 장비에서 전 구간을 실행했지만 매 빌드마다
  검증하지는 않습니다.
- **릴리스 검증 완료** — 릴리스 게이트가 매 빌드마다 실행합니다.
- **실험적 / 실측 수신 기록 없음** — 구현은 되어 있지만 호스트가 실제로 훅을
  전달했다는 기록이 없습니다. `os capabilities show`는 이 항목들을 사용 가능이
  아니라 `unknown`으로 보고합니다.

Claude Chat 화면은 플러그인 훅을 실행하지 않습니다. 생성된 스킬은 사용할 수
있지만, 프롬프트마다 자동으로 선택하는 기능은 플러그인 런타임을 실행하는 Claude
Code와 Cowork 화면에서만 작동합니다. 훅이나 셀렉터를 사용할 수 없으면
OpenSocrates는 작업을 막지 않고 통과합니다.

Cowork에는 아직 확인되지 않은 전제가 하나 더 있습니다. OpenSocrates는
`claude plugin marketplace add --scope user`로 마켓플레이스를 등록하며 이는
Claude Code 사용자 설정에 기록됩니다. Anthropic 문서는 Cowork에서 플러그인 훅이
실행된다고 밝히지만, Claude Code CLI로 등록한 마켓플레이스가 Cowork에서 보인다는
내용은 없습니다. 실측 기록이 생기기 전까지 Cowork는 실험적 상태로 두세요.

## 설치

설치 전에 호스트에 로그인하고 명령을 사용할 수 있는지 확인하세요.

- Claude: Claude Code `2.1.205` 이상과 `claude` 명령
- Codex: OAuth 로그인이 완료된 `codex` 명령

Node.js 20 이상이 필요합니다. npm에 게시된 `opensocrates` 패키지는 외부
의존성이 없는 작은 설치 프로그램입니다. GitHub Releases에서 호스트 패키지를
내려받고 릴리스 체크섬과 모든 파일 체크섬을 검증한 뒤, 소유권 표식이 있는 관리형
마켓플레이스를 등록합니다.

### 준비된 모든 호스트에 설치

```bash
npx --yes opensocrates@1.1.2 install --host all
```

모든 호스트 경로는 지원되는 인증 완료 CLI를 찾고, 어느 호스트도 바꾸기 전에
전체 사전점검을 끝냅니다. 두 패키지를 모두 검증·스테이징한 다음 한 릴리스를
트랜잭션으로 활성화합니다. 한 호스트의 활성화가 실패하면 이번 트랜잭션에서 이미
바뀐 호스트도 이전 관리형 등록으로 되돌립니다.

전체 라이프사이클에서 같은 호스트 값을 사용할 수 있습니다.

```bash
npx --yes opensocrates@1.1.2 status --host all
npx --yes opensocrates@1.1.2 update --host all
npx --yes opensocrates@1.1.2 remove --host all
```

소유자 전용 `~/.opensocrates/desired-state.json`에는 선택 채널, 설치된 호스트,
원하는 활성 버전이 기록됩니다. `status --host all`은 원하는 버전과 사용 가능한
버전, 마지막 확인, 마지막 성공 자동 업데이트, 호스트별 버전 차이를 보여 줍니다.

### 호스트 하나를 명시적으로 설치

기존 사용자와의 호환성을 위해 기본 호스트는 계속 Codex입니다.

```bash
npx --yes opensocrates@1.1.2 install
# 같은 명령: npx --yes opensocrates@1.1.2 install --host codex
npx --yes opensocrates@1.1.2 install --host claude
```

기존 `--host codex` 및 `--host claude` 라이프사이클은 그대로 지원합니다. 호스트별
업데이트는 의도적으로 버전 차이를 만들 수 있고, 이후 `update --host all` 또는
성공한 자동 조정이 desired state에 기록된 모든 호스트를 다시 한 버전으로 맞춥니다.

Claude 상태는 활성 설치와 설치됐지만 비활성화된 플러그인을 구분합니다. 원하는
설치가 비활성 상태라면 drift로 보고합니다. `install` 또는 `update`를 실행하면 검증된
패키지를 의도적으로 다시 활성화하며, 활성화가 실패하면 롤백이 이전의 활성·비활성
상태를 복원합니다. 설치 프로그램은 Claude 목록 명령에서 실측한 직접 JSON 배열과
명시적인 `marketplaces`/`plugins` 래퍼만 허용합니다. 개인정보를 제거한 2.1.226
픽스처는 `installer/fixtures/claude-cli/`에 있습니다.

### 선택형 자동 업데이트

```bash
npx --yes opensocrates@1.1.2 auto-update enable --host all
npx --yes opensocrates@1.1.2 auto-update status
npx --yes opensocrates@1.1.2 auto-update disable
```

자동 업데이트는 명시적으로 켜기 전까지 비활성화되어 있습니다. macOS LaunchAgent는
한 시간마다 가벼운 확인을 시작하고, desired state는 기본 24시간 간격과 지터,
단일 실행 잠금을 적용합니다. 작업은 선택한 npm 채널을 호출하고 릴리스 및 패키지
체크섬을 검증하며 모든 관리 호스트를 스테이징한 뒤 한 트랜잭션으로 조정합니다.
메이저 버전 자동 업그레이드는 기본적으로 차단되며, 정책을 바꾸려면
`--allow-major`를 명시해야 합니다.

`auto-update enable`에 호스트 하나를 지정하면 자동 업데이트 대상만 좁아집니다.
다른 설치 호스트를 desired state에서 제거하지 않으므로 `status --host all`은 모든
설치를 계속 추적하고, 이후 `update --host all`도 전체 설치 집합을 다시 조정합니다.

업데이터 영수증에는 버전, 시간, 호스트별 결과, 오류 범주만 기록됩니다. 프롬프트,
대화 기록, 자격 증명, 작업공간 경로는 기록하지 않습니다. `auto-update disable`은
LaunchAgent를 언로드하고 삭제하며, `remove --host all`도 관리 호스트를 지우기 전에
같은 정리를 수행합니다.

### Claude 웹 및 Desktop Chat 스킬

이 화면들은 플러그인 스킬은 지원하지만 훅은 실행하지 않습니다. 릴리스에서
`opensocrates-1.1.2-claude-chat-skills.zip`을 내려받아 Claude의 플러그인 사용자
설정 화면에서 업로드하세요. 패키지는 `/opensocrates` 스킬 하나만 노출하고, 48개
방법 절차와 엄격도·근거·추적 제어는 내부 참조로 둡니다. Chat은 플러그인 훅을
실행하지 않으므로 자동 선택은 없습니다. Anthropic의
[플러그인 화면 안내](https://support.claude.com/en/articles/13837440-use-plugins-in-claude)를
참고하세요.

### 태그가 고정된 GitHub 소스에서 설치

npm 레지스트리를 거치지 않을 때도 같은 호스트 옵션을 사용합니다.

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.1.2 install --host all
npx --yes github:ParkerHwang/OpenSocrates#v1.1.2 install --host claude
npx --yes github:ParkerHwang/OpenSocrates#v1.1.2 install --host codex
```

### 릴리스 파일 직접 검증

[v1.1.2 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.1.2)에서
`opensocrates.mjs`, 호스트 패키지, `.sha256` 파일을 내려받습니다. Claude의 예:

```bash
shasum -a 256 -c opensocrates-1.1.2-claude-plugin.zip.sha256
node opensocrates.mjs install --host claude \
  --asset opensocrates-1.1.2-claude-plugin.zip \
  --checksum opensocrates-1.1.2-claude-plugin.zip.sha256
```

Codex 패키지는 `claude`를 `codex`로 바꾸면 됩니다.

### 1.0 이전 Claude 플러그인에서 이전하기

일부 개발 버전은 대소문자를 구분하는 `OpenSocrates` 마켓플레이스 이름을
사용했습니다. 새 이름은 `opensocrates`입니다. 설치 프로그램은 구형 등록을
감지하지만 자동으로 지우지 않습니다. 설치된 항목을 확인한 뒤 명시적으로
제거하세요.

```bash
claude plugin uninstall opensocrates@OpenSocrates --scope user
claude plugin marketplace remove OpenSocrates --scope user
npx --yes opensocrates@1.1.2 install --host claude
```

관리형 v1.1.0 Claude 설치를 업데이트하면 패키지 트리 전체가 교체됩니다. 따라서
예전의 최상위 방법 스킬 48개, `rigor`, `trace`, 중복 명령은 오래된 항목으로 남지
않고 함께 제거됩니다.

## 사용법

Claude나 Codex를 평소처럼 사용하세요. 요청에 판단, 해석, 진단, 설명, 계획,
근거 조정 또는 다른 구조적 추론이 필요하면 OpenSocrates가 개입할 수 있습니다.
개입할 때는 다음과 같이 동작합니다.

1. 현재 호스트에서 새로운 비영구 셀렉터를 시작합니다.
2. 저작된 48개 시스템 카탈로그에서 적합한 시스템을 선택합니다.
3. 선택된 전체 콘텐츠를 소유자 전용 임시 Markdown 파일에 씁니다.
4. 각 방법 ID와 콘텐츠 리비전, 크기 한도 안에 들면 정확한 `Do not use when` 및
   `Stop conditions`를 작은 숨김 컨텍스트에 추가합니다.
5. 활성 작업이 방법을 적용하기 전에 전체 파일을 읽고, 접지된 답변의 마지막에
   `OpenSocrates grounding: triangulation@1`과 같은 정확한 감사 줄을 남기게 합니다.

Claude 훅 화면에서는 Read 전용 `PostToolUse` 훅이 현재 turn의 정확한 파일을 첫
줄부터 종료 표식까지 읽은 경우에만 인증된 영수증을 만듭니다. `Stop` 시 영수증이나
감사 줄이 없으면 한 번만 보정을 요청하고, `stop_hook_active`로 반복 보정을
막습니다. 일부만 읽었거나 출력이 잘렸거나 실패했거나 다른 파일을 읽은 경우는
인정하지 않습니다. Claude Chat은 이 훅을 실행하지 않으므로 접지 계약이 스킬
지침으로만 적용됩니다.

영수증은 해당 파일에 대한 성공한 `Read` 콜백이 종료 표식까지 도달한 내용을
반환했다는 사실만 기록합니다. 모든 바이트가 전달되었음을 증명하지는 않으며,
이 게이트는 실패 시 열린 상태로 통과합니다. 이 게이트가 방어하는 경계와 방어하지
않는 범위는 [SECURITY.md](SECURITY.md)를 참고하세요.

선택 수에는 고정 제한이 없습니다. 셀렉터의 내부 제한 시간은 30초이고 재시도하지
않으며 실패 시 통과합니다. 타임아웃, 호스트 오류, 잘못된 출력, 미개입 결정,
안전하지 않은 컨텍스트 또는 사용할 수 없는 훅은 모두 주입 없이 끝납니다.

Claude에서는 필요할 때 같은 컨트롤러를 명시적으로 호출할 수 있습니다.

```text
/opensocrates <요청>
/opensocrates auto <요청>
/opensocrates trace
/opensocrates status
```

Claude의 스킬·명령 UI에는 `/opensocrates` 하나만 나타납니다. 컨트롤러가 내부 방법
참조를 선택해 읽으므로 사용자가 48개 구현 카탈로그를 직접 탐색할 필요가 없습니다.

Claude 셀렉터는 세션을 저장하지 않는 단일 `claude --safe-mode -p` 프로세스를
사용합니다. 안전 모드는 사용자, 프로젝트, 플러그인 커스터마이즈를 끕니다.
`CLAUDE.md`, 스킬, 플러그인, 훅, MCP 서버, 사용자 정의 명령과 에이전트가 여기에
해당합니다. OpenSocrates는 여기에 더해 `--tools ""`, `--disallowedTools "mcp__*"`,
`--strict-mcp-config`를 전달해 기본 도구와 MCP 도구가 남지 않도록 합니다.
셀렉터에는 현재 프롬프트와 저작된 선택 카탈로그만 전달합니다.

관리형 정책(managed policy) 설정은 호스트 신뢰 경계의 일부이며 안전 모드로
비활성화되지 **않습니다**. Anthropic
[CLI 참조 문서](https://code.claude.com/docs/en/cli-reference)는 `--safe-mode`에서도
"관리형 설정 정책은 계속 적용되며 여기에는 정책으로 구성된 훅이 포함된다"고
명시합니다. 관리자가 관리형 `UserPromptSubmit` 훅을 구성한 장비에서는 그 훅이
셀렉터 프로세스 안에서 실행되고, 현재 프롬프트를 표준 입력으로 받으며,
`additionalContext`를 돌려주어 선택에 개입할 수 있습니다. 관리형 플러그인,
관리형 스킬, 관리형 `CLAUDE.md`, 정책으로 구성된 MCP 서버는 로드되지 않습니다.
조직이 관리형 훅을 구성한다면 셀렉터 프롬프트가 그 훅에 노출된다고 보고,
허용할 수 없다면 OpenSocrates 선택 기능을 끄세요.

Codex 셀렉터는 제한된 대화 기록 컨텍스트를 추가로 사용할 수 있으며 다음 설정으로
막을 수 있습니다.

```bash
export OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS=0
```

## 개인정보 보호와 보안

OpenSocrates 연동은 로컬에서 실행되고 기존 Claude 또는 Codex 로그인을 사용합니다.
다만 호스트 모델 요청은 해당 호스트 서비스의 약관에 따라 처리됩니다.
OpenSocrates는 백엔드를 호스팅하거나 텔레메트리를 추가하거나 API 키를 저장하거나
사용자의 요청 작업을 대신 실행하지 않습니다.

임시 instruction 파일에는 OpenSocrates가 저작한 콘텐츠만 들어갑니다. 원시
프롬프트, 대화 기록, 워크스페이스 파일, 도구 데이터, 자격 증명과 셀렉터 추론은
OpenSocrates 기록, 로그, 메트릭, 진단 또는 instruction 파일에 쓰지 않습니다.
전체 Read 응답은 메모리에서 종료 표식만 확인하고 보관하지 않습니다. 소유자 전용
접지 영수증에는 artifact 해시, 콘텐츠 리비전, 선택한 방법 ID, 키 기반 인증 및
도구 사용 태그만 저장하며 프롬프트, 도구 출력, 워크스페이스 경로와 artifact 경로는
저장하지 않습니다. `Stop`에서 현재 turn 파일과 영수증을 삭제합니다. `Stop`이 오지
않으면 같은 세션의 다음 `UserPromptSubmit`이 새 turn을 선택하기 전에 이전
`prompt_id` 트리를 모두 삭제하되 새 활성 트리는 보존합니다. `SessionEnd`는 세션에
남은 파일을 삭제하고, 다음 `SessionStart`는 24시간이 지난 비정상 종료 잔여 파일을
삭제합니다.

자동 업데이트를 켜면 앞서 설명한 desired state와 간결한 영수증만 소유자 전용
권한으로 저장합니다. 실행 중인 Claude나 Codex 세션을 검사하거나 종료하지 않습니다.
이미 실행 중인 작업은 로드한 플러그인을 계속 쓰고, 새 작업이 조정된 버전을 자연스럽게
불러옵니다.

취약점 신고와 측정된 지원 경계는 [SECURITY.md](SECURITY.md)를 확인하세요.

## 개발

소스 저장소에는 네이티브 바이너리와 중간 빌드 결과를 넣지 않습니다.
[uv](https://docs.astral.sh/uv/), Python 3.12, Node.js 20 이상을 설치한 뒤 다음을
실행합니다.

릴리스 후보를 병합하기 전에는
[새 Apple Silicon Mac 인수 테스트 절차](docs/clean-machine-acceptance.ko.md)를 따라
인증된 실제 Claude Code 및 Codex 홈에서 검증하고 개인정보를 뺀 근거 묶음을
확보하세요.

셀렉터의 인증된 Claude 하위 프로세스 계약은 별도의
[선택형 검사](docs/real-claude-selector.md)로 검증합니다. 오프라인 테스트에는 포함되지
않으며, 로컬 Claude 프로필이 인증되지 않았으면 범주형 차단 사유만 보고합니다.

`--max-turns 1` 구조화 출력의 반복 동작은 별도의
[집계 신뢰성 매트릭스](docs/claude-structured-output-reliability.md)로 검증합니다. 인증된
실행이 문서의 임계값을 충족하기 전에는 어떤 CLI/모델 행도 지원된다고 주장하지
않습니다.

패키지 Claude PostToolUse 영수증과 Stop 정리 지연 시간에는 재현 가능한
[Apple Silicon 측정 영수증](docs/claude-hook-timing.md)이 있습니다. v1.1.2에서 관측한
p95는 3초 훅 예산의 절반 이상을 여유로 남겨 타임아웃을 변경하지 않았습니다.

```bash
make bootstrap
make format-check
make lint
make generated-check
make content-check
make docs-check
make security-scan
make smoke
npm test
npm pack --dry-run
make release-check
```

| 경로 | 용도 |
| --- | --- |
| `src/opensocrates/` | 공유 Python 3.12 런타임과 호스트별 셀렉터 |
| `content/` | 정책, 다국어 메시지, 추론 방법, 이론과 예제 |
| `plugin-src/claude/` | Claude 플러그인 템플릿 |
| `plugin-src/codex/` | Codex 플러그인 템플릿 |
| `schemas/source/` | 정규 스키마 정의 |
| `schemas/v1/` | 생성된 버전 고정 공개 스키마 |
| `installer/` | 외부 의존성이 없는 Node.js GitHub/npx 설치 프로그램 |
| `tools/` | 빌드, 검증, 라이프사이클, 보안, 릴리스 도구 |
| `packaging/` | 네이티브 런처와 패키징 설정 |
| `build/`, `dist/` | 로컬에서 생성되어 릴리스 자산으로 게시되는 파일 |

생성된 스키마와 컴파일된 콘텐츠는 정규 소스와 생성기를 통해 변경해야 합니다.
릴리스 바이너리는 Git 이력이 아니라 GitHub Releases에 둡니다.

## 기여

기여를 환영합니다. Pull Request를 열기 전에 [CONTRIBUTING.md](CONTRIBUTING.md)를
읽고, 버그와 기능 요청에는 이슈 템플릿을 사용하세요. 이 프로젝트는
[행동 강령](CODE_OF_CONDUCT.md)을 따릅니다.

## 라이선스

OpenSocrates는 [MIT 라이선스](LICENSE)로 배포됩니다. 저작권 및 라이선스 고지를
유지하면 사용, 수정, 배포, 재라이선스와 판매가 가능합니다.

OpenSocrates는 독립 오픈 소스 프로젝트이며 Anthropic 또는 OpenAI와 제휴하거나
그들의 보증을 받은 프로젝트가 아닙니다.
