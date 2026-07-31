# OpenSocrates

[English](README.md) | **한국어**

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![Release](https://img.shields.io/github/v/release/ParkerHwang/OpenSocrates)](https://github.com/ParkerHwang/OpenSocrates/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

OpenSocrates는 AI 에이전트 호스트를 위한 로컬 추론 프레임워크입니다. 의도적인
추론이 필요한 요청을 감지하고, 별도의 Codex 컨텍스트에서 적합한 추론 시스템을
선택한 뒤, 저작된 이론과 예제를 활성 작업에 추가합니다. 단순한 사실 확인과
기계적인 작업은 그대로 통과할 수 있습니다.

버전 `1.0.0`에는 48개의 추론 시스템이 들어 있으며 Apple Silicon macOS
(`darwin-arm64`)의 Codex Desktop과 Codex CLI를 지원합니다. 다른 플랫폼,
바이너리 서명, 공증, 클린 머신 설치는 아직 검증됐다고 주장하지 않습니다.

## 설치

설치 전에 OAuth로 Codex에 로그인하고 `codex` 명령을 사용할 수 있는지
확인하세요.

### 방법 1: npm에서 npx로 설치

Node.js 20 이상이 필요합니다. npm 패키지는 외부 의존성이 없는 작은 설치
프로그램이며, 일치하는 패키지를 GitHub Releases에서 내려받아 검증합니다.

```bash
npx --yes opensocrates@1.0.0 install
```

라이프사이클 명령:

```bash
npx --yes opensocrates@1.0.0 status
npx --yes opensocrates@1.0.0 update
npx --yes opensocrates@1.0.0 remove
```

### 방법 2: GitHub에서 npx로 설치

Node.js 20 이상이 필요합니다. npm 레지스트리에 별도 패키지를 게시하지 않아도
태그가 고정된 GitHub 저장소에서 직접 설치합니다.

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 install
```

라이프사이클 명령:

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 status
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 update
npx --yes github:ParkerHwang/OpenSocrates#v1.0.0 remove
```

설치 프로그램은 일치하는 GitHub Release 자산을 내려받고 릴리스 체크섬과
패키지 내부의 모든 체크섬을 검증한 다음, 현재 Codex 홈 아래의 비공개 관리형
마켓플레이스에 등록합니다.

### 방법 3: GitHub Releases에서 직접 다운로드

[v1.0.0 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.0.0)에서
`opensocrates.mjs`를 내려받은 뒤 실행합니다.

```bash
node opensocrates.mjs install
```

파일과 체크섬을 직접 내려받아 확인하려면:

```bash
curl -fLO https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.0.0/opensocrates-1.0.0-codex-plugin.zip
curl -fLO https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.0.0/opensocrates-1.0.0-codex-plugin.zip.sha256
shasum -a 256 -c opensocrates-1.0.0-codex-plugin.zip.sha256
node opensocrates.mjs install \
  --asset opensocrates-1.0.0-codex-plugin.zip \
  --checksum opensocrates-1.0.0-codex-plugin.zip.sha256
```

### 방법 4: 소스에서 빌드해 설치

[uv](https://docs.astral.sh/uv/)와 Python 3.12가 필요합니다.

```bash
git clone https://github.com/ParkerHwang/OpenSocrates.git
cd OpenSocrates
uv python install 3.12
uv sync --locked --all-groups
make release-check
uv run --locked --no-sync python tools/codex_plugin.py install
```

`make release-check`는 네이티브 런타임과 설치 가능한 패키지를 로컬에서
빌드합니다. 생성 파일은 Git에서 제외된 `build/`와 `dist/`에 기록됩니다.

## 사용법

Codex를 평소처럼 사용하세요. OpenSocrates는 제출된 각 프롬프트 전에 실행되며,
요청에 판단, 해석, 진단, 설명, 계획, 근거 조정 또는 다른 구조적 추론 과정이
필요할 때 개입할 수 있습니다. 개입 시 다음 순서로 동작합니다.

1. 매번 새로운 임시 셀렉터 스레드를 사용합니다.
2. 저작된 48개 시스템 카탈로그에서 적합한 시스템을 선택합니다.
3. 선택된 전체 콘텐츠를 소유자 전용 임시 Markdown 파일에 기록합니다.
4. 활성 작업에 해당 파일을 읽으라는 하나의 숨겨진 컨텍스트 메시지를
   추가합니다.

선택 수에는 고정 제한이 없습니다. 훅 메시지는 작게 유지하면서 선택된 이론과
예제 전체는 압축하거나 자르지 않고 참조 파일에 보존합니다.

셀렉터의 내부 제한 시간은 30초이며 재시도하지 않고 실패 시 통과합니다.
타임아웃, SDK 오류, 잘못된 출력, 미개입 결정, 안전하지 않은 컨텍스트 또는
사용할 수 없는 훅은 모두 주입 없이 끝나며 사용자의 작업을 차단하지 않습니다.

제한된 트랜스크립트 컨텍스트 요청도 막으려면:

```bash
export OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS=0
```

## 개인정보 보호와 보안

OpenSocrates는 Codex 앱 서버와 사용자의 기존 Codex OAuth 세션을 통해 로컬에서
실행됩니다. API 키가 필요 없고, 백엔드를 호스팅하지 않으며, 사용자가 요청한
작업을 대신 실행하지 않고, 텔레메트리를 추가하지 않습니다.

임시 instruction 파일에는 OpenSocrates가 저작한 콘텐츠만 들어갑니다. 원시
프롬프트, 대화 기록, 워크스페이스 파일, 도구 데이터, OAuth 자격 증명과 셀렉터
추론은 기록, 로그, 메트릭, 진단 또는 임시 instruction 파일에 저장되지
않습니다. `Stop`에서 현재 turn 파일을, `SessionEnd`에서 남은 세션 파일을,
`SessionStart`에서 24시간이 지난 비정상 종료 잔여 파일을 삭제합니다.

취약점 신고 방법과 현재 지원 경계는 [SECURITY.md](SECURITY.md)를 확인하세요.

## 개발

소스 저장소에는 네이티브 바이너리와 중간 빌드 결과를 넣지 않습니다. 잠긴 개발
환경을 설치하고 다음 검사를 실행합니다.

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

저장소 구조:

| 경로 | 용도 |
| --- | --- |
| `src/opensocrates/` | Python 3.12 런타임과 셀렉터 소스 |
| `content/` | 정책, 다국어 메시지, 추론 방법, 이론과 예제 |
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
