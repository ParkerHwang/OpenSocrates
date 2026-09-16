<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**Codex 에이전트가 지금 내리는 판단에 맞는 사고 방법.**

OpenSocrates는 Codex에 직접 작성한 48개 사고 방법을 제공합니다. 진행 중인
작업에서 가정을 점검하고, 대안을 비교하고, 근거를 평가하도록 돕습니다.

[English](README.md) | **한국어**

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 시작하기

**1.4.0은 Codex만 지원**하며, **Apple Silicon macOS와 Windows x64**에서 사용합니다.
Node.js 20 이상을 설치하고 Codex CLI를 실행할 수 있게 한 뒤 Codex에 로그인하세요.
네이티브 런타임을 포함하므로 사용자가 Python을 설치할 필요는 없습니다.

```sh
npx --yes opensocrates@1.4.0 install
```

새 대화형 Codex 세션에서 OpenSocrates의 명령 훅 7개를 검토하세요. 네이티브
안내에 의존하기 전에 해당 훅을 승인해야 합니다. 비대화형 `codex exec`는
신뢰되지 않은 훅을 건너뜁니다. 설치만으로 승인이나 실제 전달이 입증되지는
않습니다. Codex에 `opensocrates` 컨트롤러 스킬 사용을 직접 요청할 수도 있습니다.

```sh
npx --yes opensocrates@1.4.0 status
npx --yes opensocrates@1.4.0 update
```

`--host codex`는 생략할 수 있습니다. 기존 명령과의 호환성을 위한 `--host all`도
이제 Codex만 뜻합니다. 다른 호스트 이름은 설치·제거 전에 거부합니다.

## 여러 호스트를 지원하던 버전에서 업데이트

1.4.0에서는 Claude Code, Cowork, Claude Chat, Antigravity, Cursor, Grok Build,
OpenCode 연동과 배포 파일을 제거했습니다. 이미 설치된 다른 호스트의 파일을
자동 삭제하지 않습니다. 기존 설치 상태에 다른 호스트가 포함되어 있다면,
설치했던 버전으로 해당 호스트를 먼저 제거한 다음 Codex를 업데이트하세요.

```sh
# 1.3.1로 관리하던 설치의 예:
npx --yes opensocrates@1.3.1 remove --host claude --purge
npx --yes opensocrates@1.4.0 update --host codex
```

제거할 연동마다 해당 이전 호스트 이름을 사용하세요. 이전 설치기가 보고하는
정리 보류 항목을 확인해야 합니다. 대화 기록과 무관한 파일은 보존합니다.
[설치·제거 안내](docs/advanced-usage.ko.md)를 참고하세요.

## 하는 일

- 대안 비교, 인과관계 검토, 가정 점검, 추천을 바꿀 근거 식별 등 판단에 맞는 방법을 찾습니다.
- 새로운 사실이 생기면 판단을 재검토합니다. 한 요청 안의 여러 판단 지점에서
  사용할 수 있으며, 기계적인 작업에는 방법을 불러올 필요가 없습니다.
- 지침, 예시, 적용 한계, 공개 결과 요건을 온전히 읽습니다. 48개 방법의
  영어·한국어 절차 본문을 모두 유지합니다.
- 사용자가 요구한 형식을 지키면서 결론을 근거·불확실성·재검토 조건과 연결합니다.

Codex 훅은 가벼운 탐색 안내를 제공합니다. 작업 중인 에이전트가 패키지의
네이티브 판단 명령으로 적용 가능한 방법을 가져옵니다. 런타임을 사용할 수
없으면 제약을 유지한 전체 참조 파일 경로를 사용합니다. 이 경로는 별도의
선택 모델을 호출하거나 프롬프트·대화를 저장하지 않습니다. 연동에 문제가
생겨도 일반 작업은 계속할 수 있습니다. 정확한 계약은
[판단 지점별 조회](docs/decision-points.ko.md)를 참고하세요.

## 운영체제와 한계

| 운영체제 | 패키지 | 업데이트 |
| --- | --- | --- |
| Apple Silicon macOS | 네이티브 런타임과 `bin/launch.sh` | 수동; macOS LaunchAgent 선택 가능 |
| Windows x64 | 네이티브 `.exe`와 `node bin/launch.mjs` | 수동만 지원 |

Windows에는 WSL이나 Unix 셸이 필요하지 않습니다. Windows 자동 업데이트,
Windows ARM64, Windows 10, Intel Mac, Linux 네이티브 패키지는 검증된 지원으로
주장하지 않습니다. 서명과 SmartScreen 평판도 미검증입니다.
[Windows 안내](docs/windows-support.ko.md)를 참고하세요.

## 개인정보와 검증 범위

OpenSocrates는 로컬에서 실행되며 제품 텔레메트리, 호스팅 서버, 별도 계정을
추가하지 않습니다. 일반 Codex 모델 요청은 Codex 인증과 서비스 약관을 따릅니다.
무결성·롤백·권한·기존 선택기의 경계는 [보안 정책](SECURITY.md)에 설명합니다.

패키지 검증, 훅 전달, 전체 참조 읽기, 실제 방법 적용은 서로 다른 증거입니다.
일반적인 품질·토큰 비용·응답 속도 개선을 주장하지 않습니다. 이번 버전의 검증은
[PR #93](https://github.com/ParkerHwang/OpenSocrates/pull/93)과
[릴리스 계획](docs/v1.4.0-release-plan.md)에 기록하며, 과거 증거는 과거 버전에만 해당합니다.

- [설치·업데이트·제거·런타임 안내](docs/advanced-usage.ko.md)
- [사고 방법 원문](content/methods/)
- [변경 이력](CHANGELOG.md)
- [기여 안내](CONTRIBUTING.md) · [행동 강령](CODE_OF_CONDUCT.md)

OpenSocrates는 [MIT 라이선스](LICENSE)를 따르는 독립 프로젝트이며 OpenAI의
공식 제품이나 보증을 받은 제품이 아닙니다.
