<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**이해하고 판단하고 사용할 수 있는 결과를 위한 사고 지원.**

OpenSocrates는 진행 중인 자료 종합, 이해관계자 관점 파악, 선택지 비교, 메시지
작성에 정본 사고 방법 48개를 제공합니다. 영어·한국어·간체 중국어(`zh`)·
일본어(`ja`) 절차, 교사 질문, 응답 정책, 공통 독자 안내는 출시된 v1.5.1
기준을 유지합니다. 콘텐츠 리비전 4, 전체 절차 192개와 교사 질문 576개를
제공하며 원래 영어·한국어 방법 본문은 그대로입니다. 별도 본문 업그레이드는
v1.6.0에서 제외하고 v1.6.1 이후로 분리합니다. 코딩 전문가 전용 기능도 이번
범위에 포함하지 않습니다.

[English](README.md) | **한국어** | [简体中文](README.zh.md) | [日本語](README.ja.md)

**도구를 찾는 에이전트에게:** [작업 적합성 판단·배포 패키지 선택·설정 확인 안내](docs/agent-discovery.ko.md).

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## v1.6.0 네이티브 전환

이 브랜치는 **아직 출시하지 않은 v1.6.0 구현 후보**입니다. Go 런타임, 관리 CLI,
설치기, 업데이터, 개발 도구가 기존의 활성 Python·JavaScript·npm 경로를
대체합니다. 사용자는 Go·Python·Node.js·npm을 설치하지 않습니다. 정식 자산은
[GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases)에서
배포합니다. 남은 운영 서명·신뢰 루트와 네이티브 릴리스 조건을 충족해야 게시하거나
안정 버전으로 권장할 수 있습니다. 현재 출시 기준은
[v1.5.1](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.1)입니다.
별도 v1.5.2 언어 확장은 진행 중이며 제안된 프랑스어·독일어·이탈리아어·
스페인어·포르투갈어·태국어는 이 후보의 현재 기준에 포함하지 않습니다.
v1.6.0 출시 전에 해당 작업과 다시 대조해야 합니다.

| 호스트 | 전달 방식 | 플랫폼과 활성화 |
| --- | --- | --- |
| Codex CLI / Desktop | 네이티브 훅·컨트롤러·Go 판단 런타임 | macOS ARM64·Windows x64/ARM64(기본 PowerShell); 훅 7개 검토 후 새 세션 |
| Claude Code CLI / Desktop의 로컬 Code | 상태 없는 네이티브 진입·설치된 전체 참조 | macOS ARM64; Claude CLI·로그인·플러그인과 훅 권한 필요 |
| Claude 웹 / Desktop Chat / Cowork | 실행 코드 없는 독립 계정 ZIP | 모든 지원 대상에서 검증·내보내기; 계정에서 별도 업로드·활성화 |
| Antigravity 대화 앱 | 소유 범위가 명확한 모듈형 규칙·스킬 | macOS ARM64·Windows x64/ARM64; 작업공간 또는 전역 명시 |

구현 중 사용자의 명시적 요청으로 Windows ARM64를 추가했습니다. 전용 네이티브
`.exe`·묶음·보조 프로그램과 같은 사용자 예약 정책을 사용합니다. 실제 ARM64
실행·설치/복구·예약 결과는 구현 인계에 기록합니다. 운영·실제 호스트 적용은
별도 조건이며 x64 에뮬레이션 관찰은 보조 증거입니다.

기본값과 `--host all`은 **Codex만** 선택합니다. 다른 프로필은 호스트를 명시해야
합니다. Windows 네이티브 Claude Code, Linux, macOS Intel,
WSL, 원격 호스트는 이번 범위 밖입니다.

설치·불러오기·전체 읽기·실제 적용·결과 유용성은 각각 다른 증거입니다.
로컬 검사와 파일 설치는 실제 호스트 전달이나 일반적인 품질·비용·속도 향상을
증명하지 않습니다. 명령·이전 설치 인수·자동업데이트·복구·누락 릴리스 증거는
[네이티브 안내](docs/native-v1.6.ko.md), 호스트 승인 화면은
[설치 후 설정](docs/setup-guide.ko.md)을 참고하세요.

## 설치·이전 설치 인수·업데이트

승인된 GitHub Release에서 네이티브 실행파일과 플랫폼에 맞는 묶음을 받습니다.
실행 전 해당 릴리스의 출처·서명 안내를 확인하세요. 릴리스 전 후보 묶음은 로컬
빌드 산출물입니다. Mac에서는 내려받은 실행파일을 사용합니다.

```text
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
```

Windows x64·ARM64에서는 `opensocrates.exe`와 따옴표로 감싼 로컬 드라이브 절대 경로를
사용합니다.

```text
.\opensocrates.exe install --host codex --package "C:\Downloads\bundle.zip"
.\opensocrates.exe status --host codex
```

소유권을 확인한 기존 v1.5 npm 설치는 네이티브 묶음과 함께 `adopt`를 한 번
실행합니다. 이전 업데이터를 조정하며 소유 상태·설정·등록·신뢰·비활성 상태를
보존합니다. npm 패키지나 사용자 데이터를 무차별 삭제하지 않습니다.

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
```

이후 수동 갱신은 검증한 로컬 묶음과 `update`를 사용합니다. `verify`,
`manage diagnose`, `remove`도 같은 호스트·범위를 명시합니다. Claude·Antigravity는
`enable`·`disable`을 지원하며 Codex 활성 상태는 호스트에서 관리합니다. 알 수 없거나
수정된 파일은 보존하고 충돌을 보고합니다. Mac Claude는 `--host claude`,
Antigravity는 `--host antigravity`와 선택적인
`--workspace /absolute/path/to/existing/workspace`를 사용합니다. 작업공간을
생략하면 전역 범위입니다. 계정 콘텐츠는 다음처럼 내보냅니다.

```text
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

ARM64에서는 `opensocrates-v1.6.0-windows-arm64.exe`와
`opensocrates-v1.6.0-windows-arm64.zip`을 선택하며 x64 에뮬레이션 결과로
네이티브 검증을 대신하지 않습니다. 외부 호스트 가용성은 네이티브 안내를 따릅니다.

대화형 Codex 세션에서 훅 7개를 검토하세요. 비대화형 실행에서는 승인되지 않은
훅을 건너뛸 수 있습니다. 꺼 둔 연동은 인수·갱신 후에도 꺼진 상태로 유지하며
원할 때 명시적으로 켭니다. `status`는 설치·무결성을 확인할 뿐 자동 전달이나
진행 중 대화가 불러온 버전을 증명하지 않습니다.

## 자동업데이트

Codex는 사용자 opt-in 후 훅 밖에서 `stable`을 24시간마다 확인하며 로그인 확인에
지연을 둡니다. Mac은 사용자 LaunchAgent, Windows는 작업 스케줄러를 사용합니다.
네이티브 관리 CLI의 `auto-update enable`, `status`, `run`, `disable`로 관리합니다.
적용 전 서명·만료·롤백 방지·플랫폼 무결성·호환성을 검증합니다. 메이저·호환성을
깨는 스키마 변경은 자동 적용하지 않습니다. 오프라인에서는 현재 버전을 유지합니다.
시작한 프로세스는 그 묶음을 유지하며 호스트 reload나 새 세션이 필요할 수 있습니다.
로컬 갱신은 계정 콘텐츠를 업로드하거나 이미 진행 중인 대화를 바꾸지 않습니다.

후보의 운영 업데이트 신뢰 루트·서명 서비스는 아직 제공하지 않았습니다. 이
릴리스 조건을 충족하기 전에는 운영 확인을 사용 불가로 보고합니다. 다른 연동은
수동 lifecycle을 유지하며 각 활성화·복구 검증을 마치기 전에는 예약 갱신에서
제외합니다.

### Claude Chat·Cowork: 계정 지침 한 번 추가

계정 스킬을 켜고 기존 지침을 보존하면서
**Settings → General → Instructions for Claude**에 아래를 추가하세요.
이전 Cowork 화면은 **Settings → Cowork → Global instructions**를 사용합니다.
웹과 Desktop 계정이 다르면 사용하는 계정마다 설정합니다.

```text
자료 종합, 선택지 비교, 판단, 메시지 작성처럼 해석이나 판단이 필요한
요청에서는 내가 이름을 언급하지 않아도 활성화된 OpenSocrates 스킬을 먼저
불러와 그 지침을 따르세요. 적용할 사고 방법의 전체 절차를 읽고 조건을
확인하세요. 단순 서식 변환 같은 기계적인 작업에는 불필요한 절차를
추가하지 마세요.
```

저장 후 새 대화를 시작하세요. 모델의 스킬 선택을 안내할 뿐 네이티브 훅이나
매 턴 강제 적용을 추가하지 않습니다. 업로드·필수 기능·활성 상태는
[설정 가이드](docs/setup-guide.ko.md#claude-standing-instructions)에서 별도로
확인합니다.

## 사고 지시문의 언어

현재 콘텐츠는 `en`, `ko`, `zh`, `ja`를 지원합니다. 선택적 이전 선택기는
명시적 선호 → 저장된 선호 → 현재 입력의 문자 순으로 언어를 정합니다.
가나가 있으면 일본어, 그 외에는 한글 우세 시 한국어, 한자 우세 시 중국어를
선택합니다. 한자만 있는 일본어는 일본어를 명시해야 합니다. 빈 입력·라틴
문자만 있는 입력·동률은 영어로 돌아갑니다.

```text
./opensocrates locale get
./opensocrates locale set en
./opensocrates locale set ko
./opensocrates locale set zh
./opensocrates locale set ja
./opensocrates locale set follow
./opensocrates locale reset
```

호스트 인수는 붙이지 않습니다. Windows에서는 `.\opensocrates.exe`를 씁니다.
`follow`와 `reset`은 이 선호만 지웁니다. 이 설정은 선택적 이전 선택기에만
적용하며 상태 없는 판단 요청이나 계정 스킬을 설정하지 않습니다. 상태 없는
판단 JSON에는 `locale`을 명시해야 하고 네이티브 Claude 진입은 저장된 선호를
읽지 않습니다. 계정 스킬과 Antigravity는 해당 언어 안내와 전체 참조를 사용합니다.
지시문 언어는 답변 언어·호스트 UI·관리 CLI 출력과 별도이며 모든 CLI 메시지의
번역을 약속하지 않습니다. 방법 ID·JSON 키·출처 표기는 네 언어에서 같습니다.

## 출처 표기·개인정보·개발

적격한 방법의 정본 전체를 읽고 실제로 적용했을 때만 답변 마지막에
`Powered by OpenSocrates`를 그대로 표시합니다. 독자 안내만 사용하거나 기계적인
작업만 했다면 표시하지 않으며 이 문구는 적용이나 결과 향상의 증명이 아닙니다.

일반 판단 경로에는 추가 선택 모델·인증 호출이 없고 원시 프롬프트·대화·
스크린샷·숨겨진 추론을 저장하지 않습니다. Claude 네이티브 진입은 대화를 읽거나
DB를 초기화하지 않습니다. 계정 콘텐츠에는 실행 코드가 없습니다. 호스트의
대화·인증·보관 정책은 호스트가 관리합니다. [보안 정책](SECURITY.md)을 참고하세요.

- [네이티브 설치와 증거 범위](docs/native-v1.6.ko.md)
- [런타임 참고](docs/advanced-usage.ko.md) · [Windows 범위](docs/windows-support.ko.md)
- [정본 방법](content/methods/) · [판단 계약](docs/decision-points.ko.md)
- [v1.6 구현 계획](docs/v1.6.0/IMPLEMENTATION_PLAN.md) · [결정 기록](docs/v1.6.0/DECISIONS.md)
- [변경 이력](CHANGELOG.md) · [기여 안내](CONTRIBUTING.md) · [행동 강령](CODE_OF_CONDUCT.md)

OpenSocrates는 [MIT 라이선스](LICENSE)를 따르는 독립 프로젝트이며
OpenAI·Anthropic·Google의 공식 제품이나 보증을 받은 제품이 아닙니다.
