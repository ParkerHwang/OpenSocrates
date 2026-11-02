<p align="center">
  <img src="https://raw.githubusercontent.com/ParkerHwang/OpenSocrates/main/docs/assets/opensocrates-banner.jpg" alt="OpenSocrates" width="320">
</p>

# OpenSocrates

**AI와의 대화에 48가지 사고 방법을 더하세요.**

OpenSocrates는 **Claude, Codex, Antigravity**에서 활용할 수 있는 사고 절차를
제공합니다. 선택지를 비교하고, 엇갈린 정보를 정리하고, 계획을 다른 관점에서
살펴보세요. 어떤 일인지 평소의 말로 설명하면 됩니다. 각 방법에는 활용할
질문과 점검 항목, 단계별 절차가 준비되어 있습니다.

[사용하는 앱에서 시작하기](#start-with-your-app) · [사용 예시](#see-it-in-a-task) · [사고 방법 둘러보기](#a-method-for-the-question)

**사고 방법 48개 · 지시문 언어 10개 · MIT 라이선스**

[English](README.md) · **한국어** · [简体中文](README.zh.md) · [日本語](README.ja.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Italiano](README.it.md) · [Español](README.es.md) · [Português](README.pt.md) · [ไทย](README.th.md)

## 지금 하는 일에 꺼내 쓰는 사고 도구

- **어떤 일인지부터 이야기하세요.** 각 방법에 질문과 점검 항목이 미리 작성되어 있어 여러 대화에서 재사용할 수 있습니다.
- **도움이 되는 관점을 찾아보세요.** 선택지 비교, 근거 평가, 가정 탐색, 계획 검토에 맞는 방법을 활용할 수 있습니다.
- **내 작업에 맞게 응용하세요.** 모든 절차와 사례가 공개되어 있어 직접 읽고, 살펴보고, 필요한 방식으로 바꿔 쓸 수 있습니다.

<a id="see-it-in-a-task"></a>

## 이렇게 요청해 보세요

설정을 마친 뒤, 평소처럼 질문해 보세요.

> 클라우드 도구를 사려던 참인데, 이제 작업이 오프라인에서 돌아가야 해요.
> 구매할지, 직접 만들지, 당분간 수작업으로 할지 같이 봐 주세요.

이런 결정에 활용할 수 있는
[트레이드오프 분석](content/methods/trade-off-analysis/procedure.ko.md)에는
필수 조건을 찾고, 실행 가능한 선택지를 비교하고, 확인된 사실과 가정을 나누고,
추천을 바꿀 근거를 설명하는 절차가 담겨 있습니다.
평소의 요청에 활용할 수 있는 사고의 틀이 미리 준비되어 있는 것입니다.

<a id="start-with-your-app"></a>

## 사용하는 앱에서 시작하기

OpenSocrates를 사용할 앱을 선택하세요.
[v1.5.3 다운로드](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.3)

<details>
<summary><strong>Claude Chat · Cowork</strong> — 스킬을 올리고 대화 시작하기</summary>

Claude 웹·Desktop Chat·Cowork에서:

1. **Settings → Capabilities**에서 **Code execution and file creation**을 켭니다. 조직에서 관리하는 계정이라면 Skills와 코드 실행이 조직 정책상 허용되는지 확인하세요.
2. [계정 스킬 ZIP](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip)과 [SHA-256 파일](https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.3/opensocrates-1.5.3-claude-chat-skills.zip.sha256)을 내려받습니다.
3. **Customize → Skills → + → Create skill → Upload a skill**에서 ZIP을 업로드하고 켭니다. 기존 OpenSocrates 스킬을 교체한다면 먼저 백업하세요.
4. 사용하는 Claude 계정마다 기존 지침을 유지하며 [계정 지침을 한 번 추가](docs/setup-guide.ko.md#claude-standing-instructions)합니다. 새 대화를 열고 하려는 일을 설명하세요.

전체 사고 방법과 사례가 하나의 계정 스킬 ZIP에 담겨 있습니다.
[화면으로 보는 설정 가이드](docs/setup-guide.ko.md) · [Claude 공식 Skills 안내](https://support.claude.com/en/articles/12512180-use-skills-in-claude)

</details>

<details>
<summary><strong>Claude Code</strong> — Apple Silicon Mac</summary>

[Node.js 20 이상](https://nodejs.org/en/download), Claude CLI와 로그인한 Claude 계정이
필요합니다. 터미널의 Claude Code와 Claude Desktop의 로컬 Code에서 사용할 수 있습니다.
**터미널**에서 실행하세요.

```sh
npx --yes opensocrates@1.5.3 install --host claude
npx --yes opensocrates@1.5.3 diagnose --host claude
```

`enabled: true`, `integrity: verified`, `registration: confirmed`를 확인하세요.
프로젝트 신뢰 안내가 표시되면 내용을 확인한 뒤 새 로컬 세션을 시작합니다.
[화면으로 보는 설정 가이드](docs/setup-guide.ko.md)

</details>

<details>
<summary><strong>Codex</strong> — Apple Silicon Mac 또는 Windows x64</summary>

[Node.js 20 이상](https://nodejs.org/en/download)과 Codex가 필요합니다.
네이티브 런타임은 패키지에 포함되어 있습니다.
**Mac은 터미널**, **Windows는 PowerShell**에서 실행하세요.

```sh
npx --yes opensocrates@1.5.3 install --host codex
npx --yes opensocrates@1.5.3 status --host codex
```

대화형 Codex의 입력창에 `/hooks`를 입력하세요. OpenSocrates 훅 7개의 내용을
검토하고 신뢰하는 정의를 승인한 뒤, 새 대화를 시작합니다.
[화면으로 보는 설정 가이드](docs/setup-guide.ko.md)

기존 Codex 설치를 업데이트하려면:

```sh
npx --yes opensocrates@1.5.3 update --host codex
```

</details>

<details>
<summary><strong>Antigravity</strong> — Apple Silicon Mac 또는 Windows x64</summary>

[Node.js 20 이상](https://nodejs.org/en/download)이 필요합니다. 사용할 작업공간을
정하고 아래 경로를 이미 존재하는 폴더의 절대 경로로 바꾸세요.
**Mac은 터미널**, **Windows는 PowerShell**에서 실행합니다.

```sh
npx --yes opensocrates@1.5.3 install --host antigravity --workspace "/absolute/path/to/workspace"
```

Windows에서는 `"C:\Work\Reading Workshop"`처럼 따옴표로 감싼 로컬 드라이브
경로를 사용하세요. 전역으로 설치하려면 `--workspace`를 생략합니다.
한 프로젝트에 사용할 범위를 전역 또는 작업공간 중 하나로 정하고 새 대화를 시작하세요.
[스킬과 규칙 확인](docs/setup-guide.ko.md)

</details>

**에이전트에게 설정을 맡기려면** [설정 요청문](docs/setup-guide.ko.md)이나
[현재 버전의 설치 안내](docs/agent-discovery.ko.md)를 사용하세요.
각 앱은 이름이 있는 `--host` 옵션으로 선택합니다. 기본값과 `--host all`은 Codex를 선택합니다.

<a id="a-method-for-the-question"></a>

## 질문에 맞는 사고 방법

| 지금 하는 일 | 살펴볼 사고 방법 |
| --- | --- |
| 서로 다른 우선순위에 따라 선택지 비교하기 | [트레이드오프 분석](content/methods/trade-off-analysis/procedure.ko.md) |
| 계획이 당연하게 여기는 가정 파악하기 | [가정 매핑](content/methods/assumption-mapping/procedure.ko.md) |
| 주장을 뒷받침하는 근거 살펴보기 | [비판적 사고](content/methods/critical-thinking/procedure.ko.md) |
| 계획에서 일어날 수 있는 문제에 대비하기 | [사전부검](content/methods/premortem-analysis/procedure.ko.md) |

각 방법에는 목적과 적용 조건, 전체 절차, 사례, AI가 확인할 질문이 담겨 있습니다.
내용을 읽고 사고의 흐름을 살펴보며 여러 작업에 재사용할 수 있습니다.

[사고 방법 48개 전체 보기](content/methods/)

## 사고 방법의 전체 내용을 10개 언어로

영어·한국어·간체 중국어·일본어·프랑스어·독일어·이탈리아어·스페인어·
포르투갈어·태국어로 제공합니다. 모든 언어에 사고 방법 48개의 전체 절차와
사례가 포함되어 있습니다.

AI가 읽는 사고 방법 본문을 이 언어들로 제공합니다.
[언어 안내](docs/v1.5.2.ko.md) · [Codex 지시문 언어 설정](docs/settings.ko.md)

## 읽고, 활용하고, 함께 발전시키는 오픈소스

사무업무 답변을 직접 비교하려면 [로컬 평가 도구](docs/evaluation-lab.ko.md)를
사용할 수 있습니다. Mac·Windows의 Work·Claude Cowork·Antigravity용 가상 과제를
준비하고, 먼저 업무에 쓸 결과를 고른 뒤 조건을 공개합니다. 도구 구현과 실제
앱에서의 작동 확인, 효과 검증은 구분합니다.

전체 사고 방법과 소스를 읽고, 내 작업에 맞게 응용하거나 새 사례를 더할 수 있습니다.
OpenSocrates는 [MIT 라이선스](LICENSE)로 공개된 독립 프로젝트입니다.

[릴리스](https://github.com/ParkerHwang/OpenSocrates/releases) · [설정 가이드](docs/setup-guide.ko.md) · [개인정보와 보안](SECURITY.md) · [기여 안내](CONTRIBUTING.md) · [문제 제보](https://github.com/ParkerHwang/OpenSocrates/issues/new/choose) · [변경 기록](CHANGELOG.md)
