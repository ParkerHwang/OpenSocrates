# First use: Claude Code and Antigravity / 첫 사용: Claude Code와 Antigravity

**Draft for review / 검토용 초안 — 2026-10-15 (Asia/Seoul)**

This guide explains the documented OpenSocrates **1.5.2** paths. It is based on
source and documentation only. No installation command, host session, account
upload, model experiment, build or release check was run for this draft.

이 안내는 OpenSocrates **1.5.2**의 문서화된 경로를 설명합니다. 근거는 소스와
문서뿐입니다. 이 초안을 위해 설치 명령·호스트 세션·계정 업로드·모델 실험·
빌드·배포 검사를 실행하지 않았습니다.

Source baseline / 소스 기준: `227a528996d93c423851db1d663f9572be534e59`.
The remote `main` matched this assigned SHA in the 2026-10-15 source-reading
window, 05:27–05:32 UTC (14:27–14:32 Asia/Seoul). The separate published v1.5.2 tag resolves to
`9838db16910c5f22d9dcc3c7180350cb406fd236`; it is not the source baseline for a
future integrated candidate. / 원격 `main`은 위 시각에 배정 SHA와 일치했습니다.
공개 v1.5.2 태그의 커밋은 별개이며 앞으로 통합할 후보의 근거로 바꿔 쓰지 않습니다.

## English

### Choose the surface first

| Where you work | What OpenSocrates installs or exports | What starts the documented path |
| --- | --- | --- |
| Claude Code CLI or Desktop **local Code**, Apple-silicon Mac | Native local plugin with a bundled runtime | Enabled hooks emit entry guidance on `SessionStart` and `UserPromptSubmit`; host trust and policy still apply |
| Antigravity **conversation application**, supported Mac or Windows x64 | One rule and skill in workspace **or** global scope | An `always_on` rule points to the controller; the agent reads content progressively |
| Claude web Chat, Desktop **Chat**, or Cowork | Separate executable-free account skill ZIP | The correct account must allow Skills/code execution and enable the skill; selection remains model-selected |

These paths provide different ways to find the guidance. They do not establish
that a method is applied to every message. The agent considers support when
substantive thinking first arises or materially changes; reader guidance or no
method can be appropriate. A method needs a complete canonical read and an
applicability check before use. Ordinary requests can be used without repeating
an OpenSocrates command. See the [Claude template][S3], [Antigravity template][S4],
[standing rule][S5] and [setup guide][S6].

### Claude Code: install, check, then start a fresh local session

Use an Apple-silicon Mac, Node.js 20+, and the Claude Code CLI with its normal
login flow. The following commands are reader instructions, not results from
this task. Choose `install` for a first installation; use `update` for an
existing one. `--host all` selects Codex only, so name Claude explicitly.
([Scope][S1], [Mac lifecycle][S7])

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 status --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

For an existing installation, replace the first line with
`npx --yes opensocrates@1.5.2 update --host claude`.

In `diagnose`, check `version: 1.5.2`, `enabled: true`,
`integrity: verified` and `registration: confirmed`. Preserve an intentionally
disabled installation. Review the actual plugin origin and host permissions;
do not grant unrestricted app permissions just to complete setup.
([Setup guide][S6])

In terminal Claude Code, `/plugin` lists plugins and `/hooks` lists hook origins
and contents. Claude Code's `/hooks` is read-only; Codex's seven-hook approval
procedure does not apply here. In Desktop, the dated setup guide shows
**Code → Local → + → Plugins → Manage plugins**; menu names may differ. Check
the effective local OpenSocrates plugin and version. If hooks are blocked, check
`/status`, `disableAllHooks` and organization policy. Start a fresh **local Code**
session after lifecycle changes. ([Setup guide][S6])

The documented native entry is stateless: it emits guidance and installed
controller/decision-guide locations, reads no private transcript and makes no
extra selector-model call. `Stop` and `SessionEnd` are no-ops; they do not repair
reads or produce application receipts. CLI and Desktop local Code are separate
observation cells. Cloud, SSH and WSL Code are outside this Mac native claim.
([Claude template][S3])

**Setup criterion:** the correct local plugin is enabled and a fresh local
session can start. Package status alone does not establish live hook delivery,
complete reads, method application or a useful answer. An extra model-answer
test is not a universal installation requirement. ([Setup guide][S6], [Mac guide][S7])

### Antigravity: choose one scope and check both entries

Use Node.js 20+ and the host's normal login flow. For a workspace installation,
replace the example with an **existing absolute directory** and keep that same
scope for every lifecycle command. On a supported Mac:

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 status --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 diagnose --host antigravity --workspace /absolute/path/to/workspace
```

On Windows 11 x64, use an existing local-drive directory in PowerShell:

```powershell
$workspaceDirectory = (Resolve-Path -LiteralPath 'C:\Work\Reading Workshop').Path
npx --yes opensocrates@1.5.2 install --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.2 status --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.2 diagnose --host antigravity --workspace $workspaceDirectory
```

For an existing installation, use `update` with the same scope instead of a new
install; update preserves disabled state. For a global installation, omit
`--workspace` consistently. The default global base is `~/.gemini/config` on
Mac and `%USERPROFILE%\.gemini\config` on Windows;
`ANTIGRAVITY_CONFIG_DIR`, when set, selects another global base. Avoid duplicate
global and workspace entry for the same work. Global files can also affect the
IDE. Preserve user `GEMINI.md`, `AGENTS.md` and unrelated rules.
([Mac lifecycle][S7], [Windows lifecycle][S8])

Check `version: 1.5.2`, `enabled: true`, `integrity: verified` and the intended
`scope` in `diagnose`. Then check both entries in the **conversation app**, in
the selected scope. The dated setup guide shows **Customizations → Installed →
Skills & Rules**:

- `/opensocrates`: the skill, stored at `.agents/skills/opensocrates/` for a workspace.
- `opensocrates.md`: the `always_on` rule at `.agents/rules/opensocrates.md`.

Global equivalents are `rules/opensocrates.md` and `skills/opensocrates/` under
the global base. The rule points to `../skills/opensocrates/SKILL.md`.
There is no OpenSocrates hook approval step and no requirement to appear in a
Plugins card. Normal task permissions still apply. The archive name ending in
`antigravity-plugin.zip` does not make this a CLI-registered plugin: the content
has no hooks, runtime or launcher. ([Setup guide][S6], [Antigravity template][S4])

**Setup criterion:** the skill and rule are recognized in the chosen scope and a
fresh conversation can start. Use the **conversation application** for first
use; an IDE observation does not establish app loading. Workspace and global
loading need separate observations. Restart the conversation after an update,
disable or removal: removing files cannot erase already loaded context.
([Setup guide][S6], [Mac lifecycle][S7], [Windows lifecycle][S8])

### A first task for either host

After setup, try an ordinary task in a fresh conversation. This is an authored
public synthetic example, not a recorded user prompt or an observed result:

> Our four-person team has one launch slot next week. A login bug affects
> 8 of 100 test users; fixing it takes two days. Adding CSV export takes four days;
> three prospective customers requested it, but we do not know whether it is a
> buying condition. Compare the options, state the missing evidence, recommend
> a next step and explain one condition that would change the recommendation.

Assess the practical answer against the supplied facts and uncertainty. Did it
avoid treating requests as purchases? Is the next action usable? These are
questions for trying the product, not reported outcomes or a quality guarantee.
No method name or attribution is required by this example. For Korean reasoning
instructions, state that preference; instruction language, answer language and
host UI language are separate. ([Language scope][S1])

### How the Claude account skill differs

For web Chat, Desktop Chat and Cowork, export the **account** ZIP to a new
absolute filename in an existing folder, or obtain
`opensocrates-1.5.2-claude-chat-skills.zip` from the [v1.5.2 release][S13].
For example on Mac:

```sh
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

Use the [Windows account export instructions][S8] for Windows path handling.
Before replacement, back up only the existing OpenSocrates skill and record its
enabled state. In the **actual account** used on each surface, check required
Skills/code-execution capability, upload the account ZIP and enable it. For use
without a name cue, append the [setup guide's standing instruction][S6] to
**Instructions for Claude**, preserving existing instructions, then start a
fresh conversation. Organization policy and menu names can differ.

The account ZIP has no native hooks, runtime or launcher. Uploading the Mac
native Code ZIP is not a substitute. `install`, `status` and `diagnose` are not
account-skill CLI actions; manage that skill in Claude's Skills interface.
Export success is not upload, activation or selection. Explicitly asking for
the skill can help investigate missed selection, but does not establish
automatic selection. Web Chat, Desktop Chat and Cowork remain separate cells;
different accounts need separate setup. ([Setup guide][S6], [Mac guide][S7], [Windows guide][S8])

## 한국어

### 먼저 사용하는 화면을 구분하세요

| 작업하는 곳 | 설치하거나 내보내는 구성 | 문서상 진입 경로 |
| --- | --- | --- |
| Apple Silicon Mac의 Claude Code CLI 또는 Desktop **로컬 Code** | 런타임을 포함한 로컬 네이티브 플러그인 | 켜진 훅이 `SessionStart`·`UserPromptSubmit`에서 진입 안내를 전달하며 호스트 신뢰·정책이 적용됨 |
| 지원 Mac·Windows x64의 Antigravity **대화 앱** | 작업공간 **또는** 전역 규칙·스킬 한 쌍 | `always_on` 규칙이 컨트롤러를 가리키며 에이전트가 필요한 콘텐츠를 순차적으로 읽음 |
| Claude 웹 Chat·Desktop **Chat**·Cowork | 실행 코드 없는 별도 계정 스킬 ZIP | 실제 계정에서 Skills·코드 실행 기능을 허용하고 스킬을 켜야 하며 선택은 모델이 수행함 |

세 경로는 안내를 발견하는 방식이 다릅니다. 모든 메시지에 방법을 적용한다는
뜻은 아닙니다. 에이전트는 실질적인 사고가 처음 필요하거나 맥락이 크게
바뀔 때 지원을 고려하며, 독자 안내나 방법을 쓰지 않는 선택도 가능합니다.
방법을 적용하려면 적격 여부를 확인하고 정본 절차 전체를 읽어야 합니다.
OpenSocrates 명령을 매번 반복하지 않고 일반 과제로 시작할 수 있습니다.
([Claude 템플릿][S3], [Antigravity 템플릿][S4], [상시 규칙][S5], [설정 안내][S6K])

### Claude Code: 설치·상태 확인 후 새 로컬 세션 시작

Apple Silicon Mac, Node.js 20 이상, 정상 로그인한 Claude Code CLI를
준비합니다. 아래 명령은 독자를 위한 절차이며 이번 작업의 실행 결과가
아닙니다. 처음 설치에는 `install`, 기존 설치에는 `update`를 선택하세요.
`--host all`은 Codex만 선택하므로 Claude를 명시해야 합니다.
([지원 범위][S2], [Mac 관리 경로][S7])

```sh
npx --yes opensocrates@1.5.2 install --host claude
npx --yes opensocrates@1.5.2 status --host claude
npx --yes opensocrates@1.5.2 diagnose --host claude
```

기존 설치라면 첫 줄 대신 `npx --yes opensocrates@1.5.2 update --host claude`를
사용합니다.

`diagnose`에서 `version: 1.5.2`, `enabled: true`,
`integrity: verified`, `registration: confirmed`를 확인하세요.
의도적으로 꺼둔 설치는 보존합니다. 실제 플러그인 출처와 호스트 권한을
검토하며 설치를 마치기 위해 앱 전체에 무제한 권한을 줄 필요는 없습니다.
([설정 안내][S6K])

터미널 Claude Code에서는 `/plugin`으로 플러그인, `/hooks`로 훅의 출처와
내용을 봅니다. Claude Code의 `/hooks`는 읽기 전용 목록이며 Codex의 훅 7개
승인 절차를 적용하지 않습니다. 날짜가 명시된 설정 안내의 Desktop 경로는
**Code → Local → + → Plugins → Manage plugins**입니다. 메뉴 이름은 달라질
수 있으므로 실제 로컬 OpenSocrates 플러그인과 버전을 확인하세요. 훅이
차단되면 `/status`, `disableAllHooks`, 조직 정책을 확인합니다. 설치 상태를
바꾼 뒤에는 새 **로컬 Code** 세션을 시작하세요. ([설정 안내][S6K])

문서상 네이티브 진입은 상태를 저장하지 않습니다. 진입 안내와 설치된
컨트롤러·판단 안내 위치를 전달하며 사적인 대화를 읽거나 별도 선택 모델을
호출하지 않습니다. `Stop`·`SessionEnd`는 아무 작업도 하지 않으며 읽기 보정이나
적용 영수증을 만들지 않습니다. CLI와 Desktop 로컬 Code 관찰은 별개입니다.
Cloud·SSH·WSL Code는 이 Mac 네이티브 지원 주장의 범위 밖입니다.
([Claude 템플릿][S3])

**설정 완료 기준:** 올바른 로컬 플러그인이 켜져 있고 새 로컬 세션을 시작할
수 있습니다. 패키지 상태만으로 실제 훅 전달·전체 읽기·방법 적용·유용한
답변을 확인할 수는 없습니다. 별도 모델 답변 시험을 모든 설치의 추가 필수
조건으로 요구하지 않습니다. ([설정 안내][S6K], [Mac 안내][S7])

### Antigravity: 범위 하나를 선택하고 규칙·스킬 모두 확인

Node.js 20 이상과 호스트의 정상 로그인 흐름을 사용하세요. 작업공간 설치에는
**이미 존재하는 절대 경로**를 넣고 모든 관리 명령에서 같은 범위를 유지합니다.
지원 Mac의 예시는 다음과 같습니다.

```sh
npx --yes opensocrates@1.5.2 install --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 status --host antigravity --workspace /absolute/path/to/workspace
npx --yes opensocrates@1.5.2 diagnose --host antigravity --workspace /absolute/path/to/workspace
```

Windows 11 x64에서는 PowerShell에서 기존 로컬 드라이브 경로를 사용합니다.

```powershell
$workspaceDirectory = (Resolve-Path -LiteralPath 'C:\Work\Reading Workshop').Path
npx --yes opensocrates@1.5.2 install --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.2 status --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.2 diagnose --host antigravity --workspace $workspaceDirectory
```

기존 설치에는 같은 범위로 `update`를 사용하며 꺼진 상태는 유지됩니다.
전역 설치를 선택했다면 모든 명령에서 `--workspace`를 생략하세요. 기본 전역
기준 경로는 Mac의 `~/.gemini/config`, Windows의
`%USERPROFILE%\.gemini\config`입니다. `ANTIGRAVITY_CONFIG_DIR`이 설정되어
있으면 그 전역 경로를 사용합니다. 같은 작업에 전역·작업공간 진입을 중복하지
마세요. 전역 파일은 IDE에도 영향을 줄 수 있습니다. 사용자의 `GEMINI.md`·
`AGENTS.md`와 무관한 규칙을 보존합니다. ([Mac 관리 경로][S7], [Windows 관리 경로][S8])

`diagnose`에서 `version: 1.5.2`, `enabled: true`, `integrity: verified`와
원하는 `scope`를 확인합니다. 이어 **대화 앱**의 선택한 범위에서 두 항목을
확인하세요. 날짜가 명시된 설정 안내의 경로는 **Customizations → Installed →
Skills & Rules**입니다.

- `/opensocrates`: 작업공간의 `.agents/skills/opensocrates/`에 있는 스킬.
- `opensocrates.md`: `.agents/rules/opensocrates.md`의 `always_on` 규칙.

전역 설치에서는 전역 기준 경로 아래 `rules/opensocrates.md`와
`skills/opensocrates/`를 사용합니다. 규칙은
`../skills/opensocrates/SKILL.md`를 가리킵니다. OpenSocrates 전용 훅 승인
단계나 Plugins 카드 표시가 필요하지 않습니다. 일반 과제 권한은 별도로
적용됩니다. 배포 파일명이 `antigravity-plugin.zip`으로 끝나도 CLI에 등록하는
플러그인이라는 뜻은 아닙니다. 이 콘텐츠에는 훅·런타임·실행기가 없습니다.
([설정 안내][S6K], [Antigravity 템플릿][S4])

**설정 완료 기준:** 선택한 범위에서 스킬·규칙이 인식되고 새 대화를 시작할 수
있습니다. 첫 사용은 **대화 앱**에서 진행합니다. IDE 관찰만으로 대화 앱 로딩을
확인하지 않으며 작업공간·전역 로딩도 따로 관찰해야 합니다. 업데이트·비활성화·
제거 후 새 대화를 시작하세요. 파일을 지워도 기존 대화에 이미 들어간 맥락은
지워지지 않습니다. ([설정 안내][S6K], [Mac 관리 경로][S7], [Windows 관리 경로][S8])

### 두 호스트에서 처음 시도할 과제

설정 후 새 대화에 일반 과제를 입력해 보세요. 다음은 새로 작성한 공개 합성
예시이며 실제 사용자 요청이나 관찰된 결과가 아닙니다.

> 우리 4인 팀은 다음 주에 한 가지 작업만 출시할 수 있어. 로그인 오류가
> 테스트 사용자 100명 중 8명에게 영향을 주며 수정에는 이틀이 걸려. CSV 내보내기 추가는
> 나흘이 걸리며 잠재 고객 3명이 요청했지만 구매 조건인지는 몰라. 두 선택지를
> 비교하고 부족한 근거를 밝힌 다음, 다음 행동과 추천이 바뀔 조건 하나를 설명해 줘.

주어진 사실·불확실성에 맞는 실용적인 답변인지 살펴보세요. 요청을 구매로
간주하지 않았는지, 다음 행동을 실행할 수 있는지 확인할 수 있습니다. 이는
제품을 시도할 때 볼 질문이며 관찰 결과나 품질 보장이 아닙니다. 예시 자체는
방법 이름이나 사용 표기를 요구하지 않습니다. 한국어 사고 지시문을 원하면
그 선호를 명시하세요. 지시문 언어·답변 언어·호스트 화면 언어는 별개입니다.
([언어 범위][S2])

### Claude 계정 스킬은 어떻게 다른가요

웹 Chat·Desktop Chat·Cowork에는 기존 폴더 안의 새 ZIP 절대 경로로 **계정용**
패키지를 내보내거나 [v1.5.2 배포][S13]에서
`opensocrates-1.5.2-claude-chat-skills.zip`을 받습니다. Mac 예시는 다음과 같습니다.

```sh
npx --yes opensocrates@1.5.2 export --host claude-chat --output /absolute/path/to/opensocrates-1.5.2-account.zip
```

Windows 경로 처리는 [Windows 계정 내보내기 안내][S8]를 따르세요. 교체 전 기존
OpenSocrates 스킬만 백업하고 활성화 상태를 기록합니다. 각 화면에서 **실제로
사용하는 계정**의 Skills·코드 실행 기능을 확인하고 계정 ZIP을 업로드한 뒤
스킬을 켭니다. 이름을 매번 부르지 않고 쓰려면 [설정 안내의 상시 지침][S6K]을
기존 **Instructions for Claude**에 덧붙이고 새 대화를 시작하세요. 기존 지침을
보존하며 조직 정책·메뉴 이름이 다를 수 있다는 점을 확인합니다.

계정 ZIP에는 네이티브 훅·런타임·실행기가 없습니다. Mac 네이티브 Code ZIP을
대신 올리면 안 됩니다. `install`·`status`·`diagnose`는 계정 스킬 CLI 관리
명령이 아니며 Claude의 Skills 화면에서 관리합니다. 내보내기 성공은 업로드·
활성화·선택이 아닙니다. 스킬을 명시한 요청은 선택 누락을 조사하는 데 쓸 수
있지만 자동 선택의 증거가 되지는 않습니다. 웹 Chat·Desktop Chat·Cowork의
관찰은 별개이며 계정이 다르면 각각 설정해야 합니다.
([설정 안내][S6K], [Mac 안내][S7], [Windows 안내][S8])

## OS and evidence reference / OS·증거 근거표

This table states the documented scope, not newly observed qualification.
이 표는 문서의 지원 범위이며 이번 후보의 새 지원 검증 결과가 아닙니다.

| Surface / 대상 | Documented OS or environment / 문서상 환경 | Evidence boundary / 근거 한계 | Source / 근거 |
| --- | --- | --- | --- |
| Claude native / Claude 네이티브 | Apple-silicon macOS; CLI and Desktop local Code / Apple Silicon macOS의 CLI·Desktop 로컬 Code | Separate live cells; no current-candidate execution here / 실제 관찰은 각각 별개이며 이번 후보 실행 없음 | [v1.5.2 EN][S1], [KO][S2], [native template][S3] |
| Windows Claude Code | Native terminal and Desktop Code excluded / 네이티브 터미널·Desktop Code 범위 제외 | Account skill support does not add native Code support / 계정 스킬 지원이 Code 지원을 추가하지 않음 | [v1.5.2][S1], [Windows guide][S8] |
| Antigravity Mac | Apple-silicon Mac; conversation app / Apple Silicon Mac의 대화 앱 | Workspace/global and app/IDE observations are separate / 작업공간·전역과 앱·IDE 관찰은 별개 | [v1.5.2][S1], [Mac guide][S7] |
| Antigravity Windows | Existing Windows x64 scope; Windows guide specifies Windows 11 x64 / 기존 Windows x64 범위이며 안내는 Windows 11 x64 명시 | v1.5.2 adds no new host qualification; current candidate not tested / v1.5.2의 새 호스트 검증 없음, 이번 후보 미실행 | [v1.5.2][S1], [Windows guide][S8] |
| Claude account skill / Claude 계정 스킬 | Export on Mac or Windows; web Chat, Desktop Chat, Cowork / Mac·Windows에서 내보내고 각 계정 화면에서 사용 | Capability, activation and selection depend on account/surface / 기능 허용·활성화·선택은 실제 계정·화면별 | [v1.5.2][S1], [setup][S6], [Windows guide][S8] |
| Other native targets / 그 밖의 네이티브 대상 | No added Windows ARM64, Intel Mac or Linux qualification / Windows ARM64·Intel Mac·Linux의 새 네이티브 검증 없음 | v1.6/Windows ARM64 is separate; do not extrapolate from portable content / v1.6·Windows ARM64는 별개이며 콘텐츠 이식성으로 확대하지 않음 | [v1.5.2 EN][S1], [KO][S2] |
| Cloud / SSH / WSL Code | Outside the Mac native claim / Mac 네이티브 주장 범위 밖 | A local Code observation cannot qualify them / 로컬 Code 관찰을 이 환경의 검증으로 전용하지 않음 | [Claude template][S3], [setup][S6] |
| Signing and packaging / 서명·패키징 | No new claim in this draft / 이 초안의 새 주장 없음 | Historical signing, notarization, package checks and clean-machine results apply to their exact revision/bytes; no transfer to a later candidate / 과거 서명·공증·패키지 검사·클린 머신 결과는 해당 리비전·바이트에 한정하며 후속 후보로 전용하지 않음 | [Contributor gates][S12], [security policy][S11] |

The current setup guide retains Mac screenshots dated 2026-10-10, with steps
updated 2026-10-12. Those images are not v1.5.2 execution evidence or Windows
screenshots. / 현재 설정 안내의 Mac 화면은 2026-10-10 촬영 기록이며 절차는
2026-10-12에 갱신됐습니다. 이를 v1.5.2 실행 증거나 Windows 화면으로 쓰지 않습니다.
([Setup guide][S6])

## What this draft does not establish / 미확인 경계

| Observation / 관찰 | What it can support / 설명할 수 있는 범위 | What remains separate / 별개인 범위 |
| --- | --- | --- |
| Source/document read / 소스·문서 읽기 | Documented design and commands / 문서상 설계·명령 | Installed state, delivered entry, complete read, application, useful outcome / 설치 상태·진입 전달·전체 읽기·적용·유용성 |
| `status` / `diagnose` | Reported package integrity, registration or scope as applicable / 해당 프로필의 패키지 무결성·등록·범위 보고 | Actual host delivery and result quality / 실제 호스트 전달·결과 품질 |
| Account ZIP export / 계정 ZIP 내보내기 | Verified/exported content bytes / 검증·내보낸 콘텐츠 바이트 | Upload, enabled account state and model selection / 업로드·계정 활성화·모델 선택 |
| `Powered by OpenSocrates` | Conditional attribution after a full eligible canonical read and actual application / 적격 정본 전체 읽기·실제 적용 후의 조건부 표기 | Native application proof or answer-quality improvement / 네이티브 적용 증명·답변 품질 향상 |

Reader guidance alone and mechanical work do not qualify for the attribution
line. A missing footer alone does not establish installation failure. Do not
ask for hidden reasoning, raw host logs, private conversations or screenshots
to establish use. No native application receipt is fabricated or made a new
completion gate. / 독자 안내만 사용하거나 기계적인 작업만 했다면 사용 표기를
붙이지 않습니다. 문구가 없다는 이유만으로 설치 실패를 판단하지 않습니다.
사용 확인을 위해 숨은 추론·원시 호스트 로그·사적 대화·스크린샷을 요구하지
않으며 네이티브 적용 영수증을 만들거나 새 완료 조건으로 추가하지 않습니다.
([v1.5.2 EN][S1], [KO][S2], [security policy][S11], [setup][S6])

### Historical documents excluded from current instructions / 현재 절차에서 제외한 과거 문서

- [Legacy Antigravity support][S9] starts with a historical/unsupported notice.
  Its old `config/plugins` path, `agy plugin validate` observation and explicit
  skill profile do not describe the current modular rule/skill route. /
  과거 문서의 `config/plugins` 경로·`agy plugin validate` 관찰·명시적 스킬
  프로필을 현재 모듈형 규칙·스킬의 설치·자동 동작 근거로 쓰지 않았습니다.
- [Legacy Claude hook timing][S10] records v1.1.2 `PostToolUse` read receipts and
  `Stop` cleanup. It supplies no latency, receipt or cleanup claim for the current
  stateless Claude profile. / v1.1.2의 `PostToolUse` 읽기 영수증·`Stop` 정리 수치를
  현재 상태 없는 Claude 프로필의 속도·영수증·정리 보장으로 쓰지 않았습니다.

## Source register / 근거 목록

Repository files below are pinned to assigned source
`227a528996d93c423851db1d663f9572be534e59` and were read locally during
2026-10-15 05:27–05:32 UTC (14:27–14:32 Asia/Seoul). Public issue/release metadata
was read through `gh` in the same window. Sources describe their own evidence
level; a link does not promote a historical observation to this draft or a
later integrated candidate. / 아래 저장소 파일은 배정 SHA에 고정되어 있으며
위 시각에 로컬에서 읽었습니다. 공개 이슈·배포 메타데이터는 같은 시간대에
`gh`로 읽었습니다. 각 문서의 근거 수준을 유지하며 링크만으로 과거 관찰을
이 초안이나 이후 통합 후보의 증거로 올리지 않습니다.

| ID | Source / 자료 | Use / 용도 |
| --- | --- | --- |
| S1 / S2 | [v1.5.2 EN][S1] · [KO][S2] | Current documented host/OS/language scope / 현재 문서상 호스트·OS·언어 범위 |
| S3 | [Claude README template][S3] | Current native entry, hook events and limits / 현재 네이티브 진입·훅·한계 |
| S4 / S5 | [Antigravity README template][S4] · [rule template][S5] | Modular content, paths, trigger and scope / 모듈형 콘텐츠·경로·트리거·범위 |
| S6 / S6K | [Setup EN][S6] · [KO][S6K] | Post-install checks and account standing instruction / 설치 후 확인·계정 상시 지침 |
| S7 / S8 | [Mac v1.5 guide][S7] · [Windows v1.5 guide][S8] | Lifecycle semantics; historical versioned records / 상태 관리 의미·과거 버전 기록 |
| S9 / S10 | [Legacy Antigravity][S9] · [legacy Claude timing][S10] | Historical exclusions only / 과거 자료의 제외 근거만 사용 |
| S11 / S12 | [Security policy][S11] · [Contributing][S12] | Privacy and exact-revision release evidence / 개인정보·정확한 리비전의 배포 증거 |
| S13 | [v1.5.2 release][S13] | Pinned distribution route; published 2026-10-13T10:31:42Z / 고정 버전 배포 경로·게시 시각 |
| S14 | [Issue #113][S14] | First-use versus discovery/adoption boundary; observed OPEN, updated 2026-10-15T02:08:10Z / 첫 사용과 노출·채택의 구분, 조회 당시 OPEN |

[S1]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/v1.5.2.md
[S2]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/v1.5.2.ko.md
[S3]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/claude/README.md.tmpl
[S4]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/antigravity/README.md.tmpl
[S5]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/antigravity/rule.md.tmpl
[S6]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/setup-guide.md
[S6K]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/setup-guide.ko.md
[S7]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/macos-v1.5.md
[S8]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/windows-v1.5.md
[S9]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/antigravity-support.md
[S10]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/claude-hook-timing.md
[S11]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/SECURITY.md
[S12]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/CONTRIBUTING.md
[S13]: https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2
[S14]: https://github.com/ParkerHwang/OpenSocrates/issues/113
