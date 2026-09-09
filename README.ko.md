<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**에이전트가 지금 내리는 판단에 맞는 사고 방법.**

OpenSocrates는 Claude, Codex, OpenCode, Grok Build, Cursor, Google Antigravity에서
48개의 정본 사고 방법을 사용할 수 있게 합니다. 평소 쓰는 에이전트 안에서
가정을 점검하고, 대안을 비교하고, 근거를 평가할 때 활용할 수 있습니다.

[English](README.md) | **한국어**

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![Release](https://img.shields.io/github/v/release/ParkerHwang/OpenSocrates)](https://github.com/ParkerHwang/OpenSocrates/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[웹사이트](https://opensocrates.parker-j-hwang.chatgpt.site) ·
[v1.3.1 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.3.1) ·
[설치 상세 안내](docs/advanced-usage.ko.md)

## v1.4.0 Windows 후보

이 브랜치는 Windows x64 네이티브 패키지를 추가하며 아직 게시하지 않았습니다. 로컬 ZIP 설치·수동 업데이트·호스트별 검증 범위는 [Windows 안내](docs/windows-support.ko.md)를 확인하세요. 아래 v1.3.1 명령은 현재 공개된 릴리스를 설명합니다.

## 시작하기

먼저 호스트에 로그인하고 CLI를 사용할 수 있게 준비하세요. Node.js 20 이상이
필요합니다. 배포된 네이티브 런타임은 **Apple Silicon macOS**를 지원합니다.
다른 플랫폼에서 설치하려면 호스트별 지원 문서를 먼저 확인하세요.

```sh
# 지원되는 호스트 중 준비된 호스트에 모두 설치
npx --yes opensocrates@1.3.1 install --host all

# 또는 호스트 하나를 지정
npx --yes opensocrates@1.3.1 install --host codex
npx --yes opensocrates@1.3.1 install --host claude
```

설치 후 새 작업을 시작하세요. Codex에서는 대화형 세션에서 OpenSocrates 훅을
승인해야 네이티브 탐색 안내를 사용할 수 있습니다. 호스트의 기존 로그인과 모델
제공자 설정을 사용하며, 별도의 OpenSocrates 계정이나 API 키는 필요하지 않습니다.

이미 설치했다면 다음 명령으로 업데이트하고 상태를 확인할 수 있습니다.

```sh
npx --yes opensocrates@1.3.1 update --host all
npx --yes opensocrates@1.3.1 status --host all
```

## 하는 일

- **판단에 맞는 방법을 선택합니다.** 대안을 비교하거나, 인과관계 주장과 가정을
  점검하거나, 추천을 바꿀 근거가 무엇인지 검토합니다.
- **근거가 바뀌면 결정을 다시 검토합니다.** v1.3.1은 한 요청 안의 여러 결정
  지점에서 방법을 조회할 수 있습니다. 기계적인 단계에는 방법이 필요하지 않습니다.
- **절차 전체를 읽습니다.** 각 방법에는 영어·한국어 지침, 예시, 적용 한계와
  필수 공개 결과가 함께 있습니다.
- **결론과 근거를 연결합니다.** 작성 안내는 불확실성, 권한과 사용자 형식을
  보존하며, 서로 다른 질문의 결론과 재검토 조건을 구분하도록 합니다.

예를 들어 정해진 예산 안에서 두 공급업체를 비교하거나, 새 감사 결과를 반영해
추천을 다시 검토하거나, 소규모 파일럿으로 알 수 있는 것과 아직 모르는 것을
구분하도록 요청할 수 있습니다. 이는 사용 예시이며 측정된 성과를 보장하지 않습니다.

## v1.3.1의 동작 방식

Claude/Codex 훅은 가벼운 탐색 안내를 제공합니다. 이후 작업 중인 에이전트가
패키지의 네이티브 선택기로 적합한 방법 전체를 필요할 때 조회합니다. 런타임을
사용할 수 없으면 같은 제약을 유지하는 참조 파일 경로를 사용합니다. 다른 호스트의
전달 방식은 아래와 같습니다. 연동을 사용할 수 없으면 일반 작업을 계속할 수 있습니다.

이번 릴리스는 **48개 방법과 96개 영어·한국어 절차 본문**을 그대로 유지합니다.
작성 정책은 안내이며 자동으로 답변을 다시 쓰는 기능은 아닙니다. 선택·폴백·방법
가용성의 정확한 계약은 [결정 지점 조회와 이전 안내](docs/decision-points.ko.md)에 있습니다.

## 지원 호스트

| 호스트 | 전달 방식과 시작점 | 상세 안내 |
| --- | --- | --- |
| Claude Code / Cowork | 훅이 실행되는 환경에서 플러그인 탐색; `/opensocrates:opensocrates` | [Claude 지원](docs/decision-points.md) |
| Codex CLI / Desktop | 훅 승인 후 탐색; `opensocrates` 컨트롤러 | [전달 방식](docs/decision-points.ko.md) |
| OpenCode | 같은 턴의 로컬 브리지; 네이티브 스킬 폴백 | [OpenCode 지원](docs/opencode-support.md) |
| Grok Build | 네이티브 스킬 선택 또는 `/opensocrates` | [Grok 지원](docs/grok-support.md) |
| Cursor | Agent Plugin 스킬 탐색 또는 명시적 호출 | [Cursor 지원](docs/cursor-support.md) |
| Google Antigravity | 명시적 콘텐츠 스킬 호출 | [Antigravity 지원](docs/antigravity-support.md) |

Claude 웹과 Desktop Chat은 로컬 플러그인 훅 대신 **별도의 독립형 스킬 ZIP**을
사용합니다. [v1.3.1 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.3.1)에서
다운로드한 뒤 [Chat 설치 안내](docs/claude-chat-upload-probe.md)를 따르세요.

Chat 독립형 내보내기: **아카이브 계약 검증, 실제 활성화 미검증.**

## 개인정보와 지원 범위

연동은 로컬에서 실행되고 제품 텔레메트리나 OpenSocrates 서버를 추가하지 않습니다.
모델 요청에는 선택한 호스트 서비스의 약관이 적용되며, 별도의 OpenSocrates 계정은
필요하지 않습니다. 호스트의 신뢰 경계와 유지된 이전 어댑터의 동작은
[SECURITY.md](SECURITY.md)에서 확인할 수 있습니다.

v1.3.1은 여러 줄 decision 입력을 수정하고 출시 전에 패키지 예제를 검사합니다. 패키지 검증만으로
모든 호스트의 실사용 동작이나 모델의 실제 방법 적용까지 확인한 것은 아닙니다.
합성 시험에는 최종 응답 시간 초과와 반복적인 문장이 있었으며, 전반적인 품질·
자연스러움·토큰 비용·응답 시간 개선을 주장하지 않습니다. 전체 [릴리스 근거](docs/v1.3.1-release.md)와
[배포 검증 기록](https://github.com/ParkerHwang/OpenSocrates/pull/92)에 결과와 한계를 보존했습니다.

## 더 알아보기

- [설치·업데이트·삭제·런타임 상세 안내](docs/advanced-usage.ko.md)
- [정본 방법 카탈로그](content/methods/)
- [변경 기록](CHANGELOG.md)
- [기여와 개발 검사](CONTRIBUTING.md)
- [행동 강령](CODE_OF_CONDUCT.md)

OpenSocrates는 [MIT 라이선스](LICENSE)의 독립 오픈소스 프로젝트이며,
지원하는 호스트 제공자와 제휴하거나 그들의 보증을 받지 않습니다.
