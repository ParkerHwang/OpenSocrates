# Mac에서 OpenSocrates v1.5.0 사용하기

[English](macos-v1.5.md) · [README](../README.ko.md)

v1.5.0은 원래 직접 작성한 48개 사고 방법과 영어·한국어 전체 절차를
유지합니다. 독자 안내, Claude Code 네이티브 진입, 독립 계정 스킬과
Antigravity 모듈형 콘텐츠를 추가하며 Codex도 계속 제공합니다.
Windows x64의 Codex·계정 내보내기·Antigravity는
[Windows 안내](windows-v1.5.ko.md)를 따릅니다. Windows의 Claude Code
네이티브 연동은 이번 범위에서 제외합니다.

## 릴리스 설치하기

Node.js 20 이상과 사용할 호스트를 준비하고 호스트의 지원되는 로그인
절차를 따르세요. Codex·Claude 네이티브 파일은 Apple Silicon Mac용이며
런타임을 포함하므로 설치에 Python이 필요하지 않습니다. 버전을 고정한
npm 설치기는 [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.0)에서
v1.5.0 ZIP과 SHA-256 파일을 받습니다. 로컬 파일 사용법은 아래에 설명합니다.

Codex를 설치하거나 기존 v1.4 설치를 업데이트합니다.

```sh
npx --yes opensocrates@1.5.0 install --host codex
npx --yes opensocrates@1.5.0 status --host codex
# 기존 설치를 업데이트할 때:
npx --yes opensocrates@1.5.0 update --host codex
```

대화형 세션에서 Codex 훅 7개를 검토하고 새 대화를 시작하세요. 비대화형
세션은 신뢰되지 않은 훅을 건너뛸 수 있습니다. `status`는 설치·무결성을
보고하며 호스트 신뢰나 자동 전달을 증명하지 않습니다.

## Claude Code 네이티브 연동

Claude Code CLI를 실행할 수 있게 하고 지원되는 로그인 절차로 로그인하세요.
Desktop의 로컬 Code와 터미널 인증·전달은 별도 확인 항목입니다.

```sh
npx --yes opensocrates@1.5.0 verify --host claude
npx --yes opensocrates@1.5.0 install --host claude
npx --yes opensocrates@1.5.0 status --host claude
npx --yes opensocrates@1.5.0 diagnose --host claude
```

설치기는 사용자 범위의 `opensocrates-macos` 마켓플레이스를 소유하며 정확한
버전과 활성화 상태를 확인합니다. 무관한 플러그인·설정을 보존하고 소유하지
않은 충돌은 거부합니다. 호스트 권한을 검토한 뒤 새 로컬 Code 대화에서
평소처럼 작업을 요청하세요. 매번 슬래시 명령을 쓰지 않아도 됩니다.
클라우드·SSH·WSL Code 세션은 이 Mac 네이티브 확인 범위에 포함하지 않습니다.

SessionStart와 UserPromptSubmit은 짧은 진입 안내와 설치된 전체 컨트롤러·
안내 위치를 전달합니다. 에이전트는 판단이 실질적으로 달라질 때 적격한
전체 절차를 읽습니다. 이 진입은 대화를 읽거나 데이터베이스를 초기화하거나
별도 선택 모델을 호출하지 않습니다. Stop과 SessionEnd는 읽기 복구를
강제하거나 네이티브 적용 증명을 주장하지 않습니다.

업데이트는 `npx --yes opensocrates@1.5.0 update --host claude`로 실행합니다.
비활성화 상태는 유지됩니다. 아래 동작에는 파일 옵션이 필요 없습니다.

```sh
npx --yes opensocrates@1.5.0 disable --host claude
npx --yes opensocrates@1.5.0 enable --host claude
npx --yes opensocrates@1.5.0 remove --host claude
```

호스트를 다시 불러오거나 재시작하고 실제 출처·버전을 확인하세요. 제거는
소유한 등록·파일에만 적용되며 Claude 앱·계정 스킬·대화 기록·무관한 권한을
삭제하지 않습니다. 새 연동은 `--purge`, `--reset-trust`, 자동 업데이트를
지원하지 않습니다.

## Antigravity 대화 애플리케이션

한 범위를 선택합니다. 작업공간을 쓸 때는 기존 절대 경로를 매번 지정하고,
조회·업데이트·비활성화·활성화·제거에도 같은 범위를 사용합니다.

```sh
npx --yes opensocrates@1.5.0 install --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 update --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 status --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 disable --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 enable --host antigravity \
  --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.0 remove --host antigravity \
  --workspace /absolute/path/to/workspace
```

`--workspace`를 생략하면 `~/.gemini/config/rules/opensocrates.md`와
`~/.gemini/config/skills/opensocrates/`의 전역 소유 경로를 선택합니다.
전역 파일은 앱과 IDE 모두에 영향을 줄 수 있으므로 작업공간과 중복하지
않습니다. `ANTIGRAVITY_CONFIG_DIR`이 설정되어 있으면 기본 전역 위치 대신
그 경로를 사용합니다. `diagnose`도 `status`와 같은 범위를 받으며 업데이트는
비활성화 상태를 유지합니다.

설치기는 `GEMINI.md`, `AGENTS.md`, 무관한 규칙과 수정되었거나 소유하지 않은
파일을 보존합니다. 비활성화하면 소유한 콘텐츠를 활성 규칙·스킬 위치에서
옮겨 두고 되돌릴 수 있게 소유 정보를 기록합니다. **대화 애플리케이션**에서
새 대화를 시작하고 일반 요청으로 확인하세요. 기존 대화에 이미 들어간
문맥은 파일을 꺼도 남아 있으므로 비활성화·제거 시험에는 새 대화가 필요합니다.
파일 무결성이나 IDE 관찰만으로 대화 앱의 불러오기가 증명되지는 않습니다.

## Claude 계정 스킬: 웹 Chat·Desktop Chat·Cowork

이미 존재하고 본인이 소유한 폴더의 새 절대 ZIP 경로로 내보냅니다.
내보내기는 상위 폴더를 만들지 않습니다.

```sh
npx --yes opensocrates@1.5.0 verify --host claude-chat
npx --yes opensocrates@1.5.0 export --host claude-chat \
  --output /absolute/path/to/opensocrates-1.5.0-account.zip
```

같은 출력에 다른 내용이 있으면 보존하고 충돌을 보고합니다.
`verify --host claude-chat`는 받은 ZIP을 업로드 없이 검증합니다.
계정에는 CLI의 install·update·status·diagnose·enable·disable·remove가
적용되지 않습니다. 계정의 Customize > Skills 화면에서 관리합니다.
`--output`은 계정 내보내기에만, `--workspace`는 Antigravity에만 유효합니다.

계정의 스킬·코드 실행 기능이 사용 가능한지 확인하고 독립 스킬 ZIP을
업로드해 내용을 검토한 뒤 활성화합니다. 같은 이름이 있으면 **기존
OpenSocrates 스킬만** 먼저 백업하고 활성화 상태를 보존합니다. 교체본을
검증하기 전에 원본을 삭제하지 않습니다. 계정 콘텐츠가 Code로 동기화될
때 컨트롤러 출처가 중복되지 않게 확인합니다. 업로드 수용은 활성화나
유용한 결과의 증거가 아닙니다.

평소처럼 자료 종합·판단·메시지 작성을 요청하세요. 호스트 모델이 스킬을
선택하므로 누락되면 OpenSocrates를 사용해 달라고 직접 요청할 수 있습니다.
Chat·Desktop Chat·현재 클라우드 Cowork는 따로 확인합니다. 계정 ZIP에는
네이티브 훅이나 매 메시지 강제 진입이 없으며 네이티브 연동 ZIP을 대신
올려서는 안 됩니다.

## 사용 표기와 증거의 범위

적격한 사고 방법의 정본 전체를 읽고 현재 답변에 실제로 적용했을 때만
답변 마지막에 `Powered by OpenSocrates`를 한 줄로 그대로 표시합니다.
모든 언어에서 같은 영어 문구를 사용합니다. 독자 안내만 사용한 경우,
기계적인 작업, 사용 가능 상태나 진입 안내만으로는 표시하지 않습니다.
이 문구는 네이티브 적용 영수증이나 결과 개선의 증명이 아닙니다.

소스 검사, 파일 무결성, 설치, 호스트 불러오기, 전체 절차 읽기와 유용한
결과는 서로 다른 증거입니다. CLI·Desktop 로컬 Code 전달, 웹 Chat·Desktop
Chat·Cowork, Antigravity 작업공간·전역 불러오기는 실제 호스트·계정에 따라
확인해야 하며 서로 대체할 수 없습니다. 이 안내는 일반적인 답변 품질·토큰
비용·속도 향상을 주장하지 않습니다. [Mac 관찰 기록](../evals/v1.5-macos/REPORT.md)은
날짜가 있는 결과와 한계를 보존하며 모든 현재 설치 상태를 나타내지는 않습니다.

기본값과 `--host all`은 계속 Codex를 선택합니다. 새 연동은 호스트를 명시해야
합니다. 제품과 호스트의 보관 경계는 [SECURITY.md](../SECURITY.md), 기여자의
검증·릴리스 조건은 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고하세요.

## 기여자용 대안: 로컬 파일

기여자는 Apple Silicon Mac에서 같은 연동을 소스로 빌드할 수 있습니다.
Node.js 20 이상과 함께 Python 3.12·고정한 uv 환경을 사용합니다.

```sh
uv sync --locked --all-groups
make bootstrap
make generate
make release-check
```

기존 Codex 네이티브 검증 뒤 추가 Mac 파일을 만듭니다. `dist/`의 각 ZIP에는
같은 이름의 `.sha256` 파일이 함께 생깁니다.

| 파일 | 용도 |
| --- | --- |
| `opensocrates-1.5.0-codex-plugin.zip` | 기존 Codex Mac 네이티브 경로 |
| `opensocrates-1.5.0-claude-plugin.zip` | Claude Code 로컬 네이티브 연동 |
| `opensocrates-1.5.0-claude-chat-skills.zip` | 실행 코드가 없는 계정 스킬 폴더 1개 |
| `opensocrates-1.5.0-antigravity-plugin.zip` | 작업공간·전역의 모듈형 규칙과 스킬 |

Antigravity 파일 이름에 plugin이 들어가도 CLI에 등록하는 플러그인은 아닙니다.
`.agents/rules/opensocrates.md`와 `.agents/skills/opensocrates/`를 담습니다.
계정 ZIP의 최상위 폴더는 `opensocrates/`이며 실행용 `bin/`, 훅, 런타임이
없습니다. 활성화하지 않고 파일 구성을 살펴볼 수 있습니다.

```sh
/usr/bin/zipinfo -1 dist/opensocrates-1.5.0-claude-plugin.zip
/usr/bin/zipinfo -1 dist/opensocrates-1.5.0-claude-chat-skills.zip
```

`dist/`나 릴리스 페이지의 파일을 사용할 때는 설치·업데이트·검증·내보내기에
같은 파일의 `--asset`과 `--checksum`을 함께 지정합니다.

```sh
node installer/opensocrates.mjs verify --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs install --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
```

소스 설치기는 이 체크아웃에서 실행합니다. 단독 릴리스 파일
`opensocrates.mjs`를 쓸 때는 검증한 `managed-hosts.mjs`를 같은 폴더에 두세요.
npm 패키지는 이 의존 파일을 포함합니다. 로컬 검증·내보내기는 계정 스킬을
활성화하거나 호스트 신뢰를 바꾸지 않습니다.
