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

## Mac과 Windows에서 쓰는 v1.5.0

v1.5.0은 Codex를 유지하면서 Apple Silicon Mac의 Claude Code 네이티브 연동,
휴대 가능한 Claude 계정 스킬, Mac·Windows x64의 Antigravity 작업공간·전역
규칙과 스킬을 추가합니다. 배포 파일과 SHA-256 파일은
[v1.5.0 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.0)에서
받거나 [npm 설치기](https://www.npmjs.com/package/opensocrates/v/1.5.0)를 사용하세요.

| 호스트 | 전달 방식 | 플랫폼과 활성화 |
| --- | --- | --- |
| Codex | 기존 훅·컨트롤러·네이티브 판단 런타임 | Apple Silicon Mac·Windows x64; 대화형 세션에서 훅 7개 검토 |
| Claude Code CLI / Desktop의 로컬 Code | 상태를 저장하지 않는 네이티브 진입과 설치된 전체 참조 | Apple Silicon Mac; Claude CLI·호스트 로그인·플러그인과 훅 권한 필요 |
| Claude 웹 / Desktop Chat / Cowork | 실행 코드가 없는 독립 계정 스킬 ZIP | Mac·Windows에서 내보낸 뒤 계정의 Skills 화면에서 업로드·활성화 |
| Antigravity 대화 애플리케이션 | 소유 범위가 명확한 모듈형 규칙과 스킬 | Apple Silicon Mac·Windows x64; 작업공간 또는 전역 선택 |

Windows 터미널이나 Desktop Code의 Claude Code 네이티브 연동은 이번 릴리스
범위에서 제외합니다. 계정 콘텐츠는 네이티브 Claude 연동을 설치하지 않습니다.
[Mac 안내](docs/macos-v1.5.ko.md)와 [Windows 안내](docs/windows-v1.5.ko.md)를 참고하세요.

매번 OpenSocrates 명령을 입력할 필요는 없습니다. 신뢰된 네이티브 훅과
Antigravity 상시 규칙은 진입 안내를 제공합니다. 계정 스킬은 호스트 모델이
선택하므로 호출되지 않을 수 있습니다. 설치·불러오기·전체 읽기·실제 적용·
결과의 유용성은 서로 다른 증거이며, 일반적인 품질·토큰 비용·속도 향상을
주장하지 않습니다.

## 설치 또는 업데이트

Node.js 20 이상과 사용할 호스트를 설치하고 그 호스트에 로그인하세요.
네이티브 런타임은 포함되어 있으므로 설치에 Python이 필요하지 않습니다.
지원하는 두 플랫폼에서 Codex를 설치하는 예입니다.

```sh
npx --yes opensocrates@1.5.0 install --host codex
npx --yes opensocrates@1.5.0 status --host codex
```

기존 v1.4 Codex 설치는 다음 명령으로 업데이트합니다.

```sh
npx --yes opensocrates@1.5.0 update --host codex
```

대화형 세션에서 Codex 훅 7개를 검토하고 새 대화를 시작하세요. 비대화형 실행은
신뢰되지 않은 훅을 건너뛸 수 있습니다. `status`는 설치와 무결성을 보고하며
자동 전달을 증명하지 않습니다.

Apple Silicon Mac에서는 Claude 네이티브 연동을 설치할 수 있습니다.

```sh
npx --yes opensocrates@1.5.0 install --host claude
npx --yes opensocrates@1.5.0 status --host claude
```

Antigravity는 이미 존재하는 작업공간의 절대 경로를 선택합니다.

```sh
npx --yes opensocrates@1.5.0 install --host antigravity --workspace /absolute/path/to/workspace
```

Windows에서는 `C:\Work\Reading Workshop`처럼 로컬 드라이브의 절대 경로로
바꾸고 따옴표로 감싸세요. `--workspace`를 생략하면 전역 범위를 선택합니다.
Claude 계정 콘텐츠는 이미 존재하는 폴더의 절대 ZIP 경로로 내보낸 뒤,
Claude의 Customize > Skills 화면에서 업로드하고 활성화합니다.

```sh
npx --yes opensocrates@1.5.0 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.0-account.zip
```

플랫폼별 안내에는 Windows 경로, 계정 스킬 교체, 업데이트·비활성화·제거와
검증한 로컬 파일 사용법을 설명합니다. 로컬 파일 옵션을 생략하면 설치기는
GitHub Releases에서 버전을 고정한 v1.5.0 ZIP과 체크섬을 받습니다.

새 연동에는 `--host claude`, `--host antigravity`, `--host claude-chat`를
명시해야 합니다. 기본값과 `--host all`은 계속 Codex를 선택하며 새 호스트를
전부 설치하지 않습니다. 새 연동에는 purge, 신뢰 초기화, 자동 업데이트가 없습니다.

과거 여러 호스트 연동을 자동으로 인수하거나 삭제하지 않습니다. 새 설치 전에
정확한 출처와 소유 범위를 확인하세요. 기존 OpenSocrates 계정 스킬은 교체 전에
백업하고 활성화 상태를 보존합니다.

## 사용 표기가 나오는 조건

적격한 사고 방법의 정본 전체를 읽고 현재 답변에 실제로 적용했을 때만 답변
마지막에 `Powered by OpenSocrates`를 한 줄로 그대로 표시합니다. 영어·한국어에서
같은 문구를 사용합니다. 독자 안내만 사용하거나 기계적인 작업만 했다면 표시하지
않습니다. 이 문구는 출처 표기이며 네이티브 적용이나 더 나은 결과의 증명은 아닙니다.

## 개인정보와 개발

기본 판단 경로는 별도의 선택 모델을 호출하거나 원시 프롬프트·대화·스크린샷·
숨겨진 추론을 저장하지 않습니다. Claude 네이티브 진입은 대화를 읽거나
데이터베이스를 초기화하지 않습니다. 계정 스킬에는 실행 코드가 없습니다.
일반 대화와 모델 요청은 호스트 자체의 인증·권한·보관 설정·약관을 따릅니다.
[보안 정책](SECURITY.md)에 정확한 경계를 설명합니다.

- [Mac 설치와 증거의 범위](docs/macos-v1.5.ko.md)
- [Windows 설치와 증거의 범위](docs/windows-v1.5.ko.md)
- [사고 방법 원문](content/methods/) · [판단 지점 계약](docs/decision-points.ko.md)
- [구현 범위](docs/v1.5.0/IMPLEMENTATION_PLAN.md)
- [변경 이력](CHANGELOG.md) · [기여 안내](CONTRIBUTING.md) · [행동 강령](CODE_OF_CONDUCT.md)

OpenSocrates는 [MIT 라이선스](LICENSE)를 따르는 독립 프로젝트이며
OpenAI·Anthropic·Google의 공식 제품이나 보증을 받은 제품이 아닙니다.
