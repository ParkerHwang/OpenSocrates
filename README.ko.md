<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="820">
</p>

# OpenSocrates

**이해하고 판단하고 사용할 수 있는 결과를 위한 사고 지원.**

OpenSocrates는 진행 중인 작업에 직접 작성한 48개 사고 방법을 제공합니다.
자료를 종합하고, 이해관계자의 관점을 파악하고, 선택지를 비교하고, 필요한
메시지를 쓰도록 돕습니다. 원래 영어·한국어 절차는 그대로 유지합니다.
v1.5의 독자 안내는 결론을 맥락과 다음 행동에 연결합니다. 코딩 전문가 전용
기능은 이번 버전에 포함하지 않습니다.

[English](README.md) | **한국어**

[![CI](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml/badge.svg)](https://github.com/ParkerHwang/OpenSocrates/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/opensocrates)](https://www.npmjs.com/package/opensocrates)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## v1.5.0 구현 단계

Windows 후속 구현은 Claude 웹·Desktop Chat·Cowork용 계정 ZIP 검증·내보내기와
Antigravity의 Windows x64 작업 폴더·전역 설치 수명 주기를 추가합니다.
이번 Windows 범위에서 Claude Code는 제외하며 기존 Mac 네이티브 구현은 유지합니다.
[Windows 안내](docs/windows-v1.5.ko.md),
[검증 기록](evals/v1.5-windows/REPORT.md),
[구현 인계](docs/v1.5.0/WINDOWS_IMPLEMENTATION_HANDOFF.md)를 참고하세요.
파일 시스템 검사와 실제 호스트 결과는 별도로 기록합니다.

이 체크아웃에는 아래 Mac 연동과 로컬 배포 파일을 만드는 기능이 구현되어
있습니다. **v1.5.0은 아직 npm이나 GitHub Releases에 게시되지 않았습니다.**
검증한 로컬 파일과 소스 설치기를 사용하세요. `npx opensocrates@1.5.0`이나
릴리스 다운로드가 있다고 가정하지 않습니다. npm 배지는 실제 게시 상태를
나타냅니다.

| 호스트 | 구현된 전달 방식 | 확인 범위 |
| --- | --- | --- |
| Codex, Apple Silicon Mac | 기존 훅·컨트롤러·네이티브 판단 런타임 | 기존 동작과 회귀 검증 유지 |
| Claude Code CLI / Desktop의 로컬 Code, Apple Silicon Mac | 상태를 저장하지 않는 네이티브 진입과 설치된 전체 참조 | CLI 등록과 Desktop 로컬 독자 사례 확인; 인증한 터미널 검증은 보류이며 초안 한계는 기록 |
| Claude 웹 / Desktop의 일반 Chat / Cowork | 실행 코드가 없는 독립 계정 스킬 ZIP | ZIP 형식 수용 확인; 기존 스킬의 임시 교체와 실제 적용 시험 보류 |
| Antigravity 대화 애플리케이션, Mac | 소유 범위가 명확한 모듈형 규칙·스킬; 작업공간 또는 전역 | 일반 요청의 작업공간 독자 사례 1건 확인; 전역·앱 생명주기는 별도 확인 필요 |

매번 OpenSocrates 명령을 입력할 필요는 없습니다. 신뢰된 네이티브 훅과
Antigravity 상시 규칙은 진입 안내를 제공합니다. 계정 스킬은 호스트 모델이
선택하므로 호출되지 않을 수 있습니다. 설치·불러오기·전체 읽기·실제 적용·
결과의 유용성은 서로 다른 증거이며, 일반적인 품질·토큰 비용·속도 향상을
주장하지 않습니다.

## 로컬 Mac 후보로 시작하기

Node.js 20 이상과 사용할 호스트를 설치하고 그 호스트에 로그인하세요.
Mac 네이티브 런타임은 포함되어 있으므로 설치에 Python이 필요하지 않습니다.
저장소에서 Claude 연동 파일을 검증한 뒤 설치하는 예입니다.

```sh
node installer/opensocrates.mjs verify --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs install --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs status --host claude
```

호스트의 플러그인·훅 권한을 검토하고 새 대화를 시작하세요. `status`는 설치와
무결성을 보고하며 자동 진입을 증명하지 않습니다. Antigravity 작업공간
설치, 계정 파일 내보내기, 업데이트·비활성화·제거와 보류 항목은
[Mac 안내](docs/macos-v1.5.ko.md)에 설명합니다.

새 연동에는 `--host claude`, `--host antigravity`, `--host claude-chat`를
명시해야 합니다. 기본값과 `--host all`은 기존 Codex 설치 상태를 관리하는
경로를 유지하며 새 호스트를 전부 설치하지 않습니다. 새 연동에는 purge,
신뢰 초기화, 자동 업데이트가 없습니다.

## 기존 Codex 릴리스와 Windows

게시된 v1.4.0은 Apple Silicon Mac과 Windows x64에서 Codex만 지원합니다.

```sh
npx --yes opensocrates@1.4.0 install --host codex
npx --yes opensocrates@1.4.0 status --host codex
```

대화형 세션에서 Codex 훅 7개를 검토하세요. 비대화형 실행은 신뢰되지 않은
훅을 건너뛸 수 있습니다. 기존 Codex Windows 지원은 유지하며, **v1.5의 새
Claude·Antigravity Windows 연동은 다음 단계**입니다. 완료된 지원으로
주장하지 않습니다. [기존 Windows 안내](docs/windows-support.ko.md)와
[Windows 구현 인계](docs/v1.5.0/WINDOWS_HANDOFF.md)를 참고하세요.

과거 여러 호스트 연동을 자동으로 인수하거나 삭제하지 않습니다. 새 설치
전에 정확한 출처와 소유 범위를 확인하고, 기존 계정 스킬은 백업한 교체본이
검증될 때까지 보존합니다.

## 개인정보와 개발

기본 판단 경로는 별도의 선택 모델을 호출하거나 원시 프롬프트·대화·스크린샷·
숨겨진 추론을 저장하지 않습니다. 새 Claude 진입은 대화를 읽거나 데이터베이스를
초기화하지 않습니다. 계정 스킬에는 실행 코드가 없습니다. 일반 대화와 모델
요청은 호스트 자체의 인증·권한·보관 설정·약관을 따릅니다.
[보안 정책](SECURITY.md)에 정확한 경계를 설명합니다.

- [Mac 설치와 확인 범위](docs/macos-v1.5.ko.md)
- [사고 방법 원문](content/methods/) · [판단 지점 계약](docs/decision-points.ko.md)
- [현재 구현 범위](docs/v1.5.0/IMPLEMENTATION_PLAN.md)
- [변경 이력](CHANGELOG.md) · [기여 안내](CONTRIBUTING.md) · [행동 강령](CODE_OF_CONDUCT.md)

OpenSocrates는 [MIT 라이선스](LICENSE)를 따르는 독립 프로젝트이며
OpenAI·Anthropic·Google의 공식 제품이나 보증을 받은 제품이 아닙니다.
