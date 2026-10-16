# Claude account skill: first use / Claude 계정 스킬 첫 사용

Draft for maintainer review, prepared with AI assistance on 15 October 2026
(Asia/Seoul). This document has not been published or tried in a Claude account.
Product instructions are pinned to **OpenSocrates v1.5.2**, released source
`9838db16910c5f22d9dcc3c7180350cb406fd236`, content revision **5**.

This is a companion to the existing [first-use worksheet][worksheet]. It adds
account-specific file selection, setup checks and troubleshooting; the worksheet
remains the source for the three synthetic work tasks.

## English

### 1. Choose the account ZIP

Use this path for **Claude web Chat, ordinary Desktop Chat or Cowork** in the
account where you want the skill available. Start with the released
[opensocrates-1.5.2-claude-chat-skills.zip][account-zip]. You can download it in
your browser without Node.js or a terminal.

| What you found | What it is | What to do |
| --- | --- | --- |
| `opensocrates-1.5.2-claude-chat-skills.zip` | The complete account skill distribution | Select this ZIP in Claude's skill upload interface. |
| `opensocrates-1.5.2-claude-plugin.zip` | The separate native Claude Code package | Follow the [local Code setup guide][setup-en] if local Code is your target. It is not the account upload file. |
| `plugin-src/claude-chat/`, including `SKILL.md.tmpl` | Source templates used to assemble a distribution | Read these to inspect the design; do not upload the template folder or rename a template to make an account package. |
| GitHub's “Source code (zip)” or “Source code (tar.gz)” | A repository snapshot | Use the named account release asset instead. |

The assembled account ZIP has an `opensocrates/` skill folder with `SKILL.md`,
reader and decision guides, catalogs and complete method references. Source
templates contain placeholders and do not alone include that assembled content.
Keep the downloaded ZIP intact for upload. The package provides one public
skill with 48 internal methods in ten instruction languages. It contains no
hooks, runtime, launcher or credential client. [Tagged package sources][template-en]
and [assembler][assembler] describe this distinction.

If you already use the command-line exporter, the v1.5.2 `export --host
claude-chat` route is an alternative way to obtain the ZIP, as documented in
the [release guide][release-en]. **Export success means a local file was
produced; it does not mean Claude uploaded or enabled it.** `install --host
claude` and a native plugin's status do not establish account-skill setup.

### 2. Upload and enable it in the intended account

1. Check the account and organization you are actually using. Web and Desktop
   can use different accounts; check each surface you intend to use.
2. In `Settings → Capabilities`, check **Cloud code execution and file
   creation** (sometimes labelled **Code execution and file creation**). For a
   managed account, an administrator may need to allow Skills and code
   execution. Follow the [official Skills guide][claude-skills] if those controls
   are unavailable. All-domain network access is not an additional OpenSocrates
   installation requirement.
3. Go to `Customize → Skills → + → Create skill → Upload a skill` and select
   the account ZIP. Menu names may differ by app version and policy. Use the
   Skills upload control rather than attaching the ZIP to an ordinary chat.
4. If `opensocrates` already exists, download a backup through its `… →
   Download` menu and note whether it was enabled before using `… → Replace`.
   Preserve the backup until you have checked the replacement. Leave other
   skills and existing account instructions in place.
5. Open the uploaded skill. Check its enabled toggle and find
   `OpenSocrates 1.5.2` in `Contents → SKILL.md`. A label such as `v4` in the
   Claude skill list is the account's edit revision, not the product version.
   If the earlier skill was deliberately disabled, keep that choice until you
   decide to enable the replacement for this first-use task.

These steps follow the [version-pinned setup guide][setup-en]. They describe
what to check; this draft does not confirm your upload, capability or toggle.

### 3. Choose how to request it

For a first task, name OpenSocrates explicitly in your request. For ordinary
use without a name cue, append the standing instruction from the
[v1.5.2 English setup guide][standing-en] once in
`Settings → General → Instructions for Claude`, preserving existing text.
Some versions show this field directly in Settings; older Cowork versions may
show `Settings → Cowork → Global instructions → Edit`.

Account instructions and project instructions have different scope. A
project-only instruction does not configure other conversations. The
[official personalization guide][claude-instructions] explains that scope.
After saving your chosen setup, start a fresh conversation.

The instruction asks the model to load the enabled skill when appropriate.
It creates no native hook or every-message enforcement. The model can miss
selection, and mechanical formatting or transcription need not use a method.
An eligible method must be read in full before application; a skill name or
catalog entry is not the full procedure. [Released decision guide][decision-en]

### 4. Try one task and inspect the answer

Open the [English worksheet][worksheet-en] and use **“A client email: keep the
agreed promise”** in a fresh conversation. Use its initial request and follow-up
unchanged so the task and criteria remain in one public source. They are
synthetic examples, not observed model outputs or customer outcomes.

Check the answer itself: does it preserve Friday's draft review, avoid adding
a final-delivery promise, and keep the unresolved delivery date and approver
clear? If it fails one of those checks, record that failure. Do not infer an
improvement from fluency, a skill badge or a footer. This is a first-use task,
not a comparison study.

The exact line `Powered by OpenSocrates` is required only when an eligible
canonical method was fully read and actually applied. Reader guidance alone,
mechanical work or an empty eligible selection do not qualify. Its presence is
not native proof of application or better results; its absence alone does not
prove a loading failure. [Released account controller][controller]

### 5. Keep each observation separate

| Stage | What you can check | What it does not establish |
| --- | --- | --- |
| File obtained | The selected filename; product identity in its content; optional comparison with the release checksum | Account upload or activation |
| Uploaded | The skill appears in the intended account | Enabled state or model selection |
| Setup checked | Required capability and skill are enabled; standing instruction is saved if you chose use without a name cue | That this task loaded the skill |
| Reading/application | Any host-visible indication or agent report, with its limited scope stated | Independent verification of a complete read or application; this content-only package has no native application receipt |
| Useful result | The actual answer meets the worksheet's criteria and helps your task | Universal quality improvement or later reuse |

You can finish checking setup without demanding an unavailable application
receipt. Check web Chat, Desktop Chat and Cowork separately; an observation in
one surface does not settle another. A download or repository star is not a
first-use or repeat-use observation.

### 6. If something is missing

| Symptom | Next check |
| --- | --- |
| Skills or upload is missing/disabled | Confirm the account, required capability and organization policy with the official Skills guide or administrator. Record “unavailable” if blocked; do not broaden unrelated permissions. |
| Upload is rejected | Recheck the exact account asset filename. Avoid the native plugin ZIP, source archive, template folder or a ZIP you repacked. Note a safe error category and consult the official upload guidance. A cause is not established merely because upload failed. |
| Wrong version or unexpected content | Check `Contents → SKILL.md`, not the skill-list edit revision. Keep the previous backup; do not mix files from `main` into a release ZIP. |
| Skill is enabled but use is unclear | Check the intended account, start a fresh eligible task and name OpenSocrates explicitly if needed. For use without naming it, check the saved standing instruction and scope. Model selection can still be missed; do not claim a known cause without evidence. |
| An answer has no footer | Evaluate the task result and applicability first. The missing line alone cannot distinguish no eligible method, reader-only use or missed loading. |
| The answer changes an agreement or invents a fact | Treat that answer as failing the task's criterion even if the skill appears loaded. Use the worksheet's synthetic facts for a minimal report. |

If you choose to report a problem, share only the app/surface, product version,
a synthetic reproduction, safe error category and a short description of the
failed criterion through the [existing issue process][issues]. Leave out account
identifiers, company material, credentials, full conversations, screenshots and
hidden reasoning. OpenSocrates's content-only package adds no raw-prompt or
transcript collection; Claude's own retention and permissions still apply.

## 한국어

### 1. 계정용 ZIP 선택

이 안내는 실제 사용할 계정의 **Claude 웹 채팅·일반 Desktop Chat·Cowork**용입니다.
출시 파일인 [opensocrates-1.5.2-claude-chat-skills.zip][account-zip]을 내려받으세요.
브라우저로 받는 데 Node.js나 터미널은 필요 없습니다.

| 찾은 파일·폴더 | 용도 | 다음 행동 |
| --- | --- | --- |
| `opensocrates-1.5.2-claude-chat-skills.zip` | 완성된 계정 스킬 배포물 | Claude의 스킬 업로드 화면에서 이 ZIP을 선택합니다. |
| `opensocrates-1.5.2-claude-plugin.zip` | 별도의 Claude Code 네이티브 패키지 | 로컬 Code가 목적이면 [로컬 Code 설정 안내][setup-ko]를 따릅니다. 계정에 올리는 파일은 아닙니다. |
| `SKILL.md.tmpl` 등이 있는 `plugin-src/claude-chat/` | 배포물을 만드는 소스 템플릿 | 설계를 살펴볼 때 읽습니다. 폴더를 그대로 올리거나 템플릿 이름만 바꿔 계정 패키지로 쓰지 않습니다. |
| GitHub의 “Source code (zip)”·“Source code (tar.gz)” | 저장소 스냅샷 | 이름이 명시된 계정용 릴리스 파일을 선택합니다. |

완성된 계정 ZIP에는 `opensocrates/` 폴더 아래 `SKILL.md`, 독자·판단 안내,
카탈로그와 사고 방법의 전체 참조가 들어갑니다. 소스 템플릿에는 치환할 값이
남아 있고 그것만으로 완성된 콘텐츠가 갖춰지지 않습니다. 내려받은 ZIP을
그대로 업로드하세요. 공개 스킬 하나 안에 열 지시문 언어의 사고 방법 48개가
있으며 훅·런타임·실행기·인증 클라이언트는 포함하지 않습니다.
[출시 템플릿][template-en]과 [조립 코드][assembler]에서 이 구분을 확인할 수 있습니다.

명령줄 내보내기를 이미 사용한다면 v1.5.2의 `export --host claude-chat`도 ZIP을
얻는 별도 경로입니다. 명령은 [릴리스 안내][release-ko]를 따르세요.
**내보내기 성공은 로컬 파일을 만들었다는 뜻이며 계정 업로드·활성화 완료가 아닙니다.**
`install --host claude`나 네이티브 플러그인의 상태로 계정 스킬 설정을 확인할 수는 없습니다.

### 2. 실제 계정에 업로드하고 켜기

1. 실제 사용하는 계정과 조직부터 확인합니다. 웹과 Desktop이 다른 계정일 수
   있으므로 사용할 화면마다 확인합니다.
2. `Settings → Capabilities`의 **Cloud code execution and file creation**을
   확인합니다. 화면에 따라 **Code execution and file creation**으로 보일 수
   있습니다. 관리 계정은 관리자가 Skills와 코드 실행을 허용해야 할 수 있습니다.
   설정을 사용할 수 없다면 [Claude 공식 Skills 안내][claude-skills]를 따릅니다.
   모든 도메인의 네트워크 허용은 OpenSocrates의 추가 설치 조건이 아닙니다.
3. `Customize → Skills → + → Create skill → Upload a skill`에서 계정용 ZIP을
   선택합니다. 메뉴 이름은 앱 버전과 정책에 따라 다를 수 있습니다. 일반 대화의
   파일 첨부 대신 Skills의 업로드 기능을 사용합니다.
4. `opensocrates`가 이미 있다면 `… → Download`로 백업하고 켜짐 상태를
   기록한 뒤 `… → Replace`를 사용합니다. 새 파일을 확인할 때까지 백업을
   보관합니다. 다른 스킬과 기존 계정 지침은 보존합니다.
5. 업로드한 스킬에서 켜짐 스위치를 확인하고 `Contents → SKILL.md`의
   `OpenSocrates 1.5.2`를 찾습니다. 스킬 목록의 `v4` 같은 번호는 계정에서
   수정한 회차이며 제품 버전이 아닙니다. 기존 스킬을 의도적으로 꺼뒀다면,
   이번 첫 과제를 위해 켜기로 결정하기 전까지 그 선택을 유지합니다.

위 단계는 [버전을 고정한 설정 안내][setup-ko]를 따릅니다. 확인할 항목을
설명한 것이며 이 초안이 실제 계정의 업로드·기능·켜짐 상태를 확인한 것은 아닙니다.

### 3. 요청 방식 선택

첫 과제에서는 요청에 OpenSocrates 이름을 명시합니다. 이후 이름 없이 쓰려면
[v1.5.2 한국어 설정 안내][standing-ko]의 상시 지침을
`Settings → General → Instructions for Claude`에 한 번 추가하고 기존 문구는
보존합니다. 일부 버전은 Settings에서 이 항목을 바로 보여주고, 이전 Cowork는
`Settings → Cowork → Global instructions → Edit`를 보여줄 수 있습니다.

계정 지침과 프로젝트 지침은 적용 범위가 다릅니다. 프로젝트에만 넣은 지침은
다른 대화를 설정하지 않습니다. 범위는 [공식 개인화 안내][claude-instructions]에서
확인할 수 있습니다. 원하는 설정을 저장한 뒤 새 대화를 시작합니다.

상시 지침은 적절한 때 활성화된 스킬을 불러오도록 모델에 요청합니다.
네이티브 훅이나 매 메시지 강제 적용을 만들지는 않습니다. 모델의 선택에서
누락될 수 있고 단순 서식 변환·받아쓰기에는 방법이 필요하지 않을 수 있습니다.
적합한 방법도 전체 절차를 읽은 뒤 적용해야 합니다. 스킬 이름이나 카탈로그
항목은 전체 절차가 아닙니다. [출시 판단 안내][decision-ko]

### 4. 과제 하나를 시도하고 답변 확인

새 대화에서 [한국어 worksheet][worksheet-ko]의 **“회의 메일: 정해진 약속
유지하기”**를 시도합니다. 공개 원본 한곳에 과제와 기준을 유지하도록 첫 요청과
후속 요청을 그대로 사용합니다. 합성 예시이며 실제 모델 답변이나 사용자 성과가 아닙니다.

답변 자체를 봅니다. 금요일 초안 검토를 유지했는지, 최종 납품 약속을 새로
만들지 않았는지, 아직 정하지 않은 납품일·승인자를 분명히 남겼는지 확인합니다.
놓친 기준은 실패로 기록합니다. 매끄러운 문장·스킬 표시·마지막 사용 표기로
개선을 추정하지 않습니다. 첫 사용 과제이며 비교 실험이 아닙니다.

`Powered by OpenSocrates` 한 줄은 적합한 정본 방법을 전부 읽고 실제 답변에
적용했을 때만 필요합니다. 독자 안내만 사용했거나 기계적 작업이거나 적합한
방법이 없는 경우에는 해당하지 않습니다. 이 줄이 있어도 실제 적용이나 좋은
결과의 네이티브 증거가 아니며, 없다는 사실만으로 불러오기 실패를 증명하지도
않습니다. [출시 계정 컨트롤러][controller]

### 5. 관찰한 단계 구분

| 단계 | 확인할 수 있는 것 | 그 확인만으로 알 수 없는 것 |
| --- | --- | --- |
| 파일 확보 | 선택한 파일명, 콘텐츠의 제품 정보, 필요하면 릴리스 체크섬과 비교 | 계정 업로드·활성화 |
| 업로드 | 의도한 계정의 스킬 목록에 표시됨 | 켜짐 상태·모델 선택 |
| 설정 확인 | 필요한 기능과 스킬이 켜짐, 이름 없는 사용을 선택했다면 상시 지침이 저장됨 | 이번 과제에서 스킬을 불러왔는지 |
| 읽기·적용 | 호스트가 보여주는 표시나 에이전트의 보고가 있다면 그 한정된 범위 | 전체 읽기·적용의 독립적 검증. 콘텐츠 전용 패키지에는 네이티브 적용 영수증이 없음 |
| 유용한 결과 | 실제 답변이 worksheet 기준을 지키고 과제에 도움이 됨 | 보편적인 품질 향상·이후 재사용 |

제공되지 않는 적용 영수증을 요구하지 않고 설정 확인을 마칠 수 있습니다.
웹 채팅·Desktop Chat·Cowork는 각각 확인합니다. 한 화면의 관찰로 다른 화면까지
확정하지 않습니다. 다운로드나 저장소 스타는 첫 사용·재사용 관찰이 아닙니다.

### 6. 막혔을 때 확인

| 증상 | 다음 확인 |
| --- | --- |
| Skills나 업로드가 없거나 비활성화됨 | 공식 Skills 안내나 관리자를 통해 계정·필요한 기능·조직 정책을 확인합니다. 차단되면 ‘사용 불가’로 남기고 무관한 권한을 확대하지 않습니다. |
| 업로드가 거부됨 | 정확한 계정용 파일명을 다시 확인합니다. 네이티브 플러그인 ZIP·소스 압축·템플릿 폴더·직접 재압축한 ZIP과 구분합니다. 안전한 오류 범주만 적고 공식 업로드 안내를 봅니다. 실패했다는 사실만으로 원인이 확정되지는 않습니다. |
| 버전이나 콘텐츠가 예상과 다름 | 스킬 목록의 수정 회차 대신 `Contents → SKILL.md`를 확인합니다. 이전 백업을 보관하고 `main`의 파일을 릴리스 ZIP에 섞지 않습니다. |
| 켜져 있지만 사용 여부가 불분명함 | 실제 계정을 확인하고 새 판단 과제에서 필요하면 OpenSocrates 이름을 명시합니다. 이름 없이 쓰려면 상시 지침의 저장·범위를 확인합니다. 모델 선택에서 여전히 누락될 수 있으며 근거 없이 원인을 확정하지 않습니다. |
| 답변에 사용 표기가 없음 | 과제 결과와 적용 조건부터 봅니다. 표기 누락만으로 적합한 방법 없음·독자 안내만 사용·불러오기 누락을 구별할 수는 없습니다. |
| 답변이 약속을 바꾸거나 사실을 만듦 | 스킬이 불러와진 것처럼 보여도 해당 과제 기준에서 실패로 다룹니다. 최소 보고에는 worksheet의 합성 사실을 사용합니다. |

문제를 보고하기로 했다면 [기존 이슈 절차][issues]에 앱·화면, 제품 버전, 합성
재현 과제, 안전한 오류 범주와 놓친 기준의 짧은 설명만 공유합니다. 계정 식별자·
회사 자료·인증정보·전체 대화·스크린샷·숨은 추론은 제외합니다. OpenSocrates의
콘텐츠 전용 패키지는 원문 프롬프트·대화 수집을 추가하지 않지만 Claude 자체의
보존 정책과 권한은 계속 적용됩니다.

## Maintainer proposal / 유지관리자 제안

**EN — Keep the worksheet; add a companion link.** Its existing account section
already covers download, capability, upload/replace, enabled state and standing
instructions. Replacing the whole worksheet would duplicate three task designs
and the native-host guide. The new value here is the file-choice table,
stage-specific observations and symptom-specific checks. After approval, link
this companion from that account section; keep tasks and criteria in the gist
and standing-instruction text in the version-pinned setup guides. A shorter
replacement of the worksheet's account section is an alternative only if the
maintainer chooses one canonical setup home and checks existing incoming links.
No worksheet edit or publication has been made.

**KO — worksheet는 유지하고 보완 안내를 연결합니다.** 기존 계정 구역에는
다운로드·기능·업로드/교체·켜짐·상시 지침이 이미 있습니다. 전체를 바꾸면 세
과제 설계와 네이티브 안내까지 중복됩니다. 이 문서가 더하는 것은 파일 선택표,
단계별 관찰과 증상별 확인입니다. 승인 후 기존 계정 구역에서 이 안내를
연결하고 과제·기준은 gist, 상시 지침 원문은 버전을 고정한 설정 안내에 유지하는
방안을 제안합니다. worksheet의 계정 구역을 짧게 대체하는 대안은 유지관리자가
설정 원본의 위치와 기존 유입 링크를 확인한 경우에 선택할 수 있습니다.
worksheet 수정이나 게시를 실행하지 않았습니다.

## Source and evidence boundary / 출처와 근거 범위

Source reads: **15 October 2026 (Asia/Seoul)**. The initial remote-baseline
observation was at **05:27 UTC / 14:27 Asia/Seoul**. These are source
observations, not live account setup or method-use evidence; the handoff records
the completion time.

| Source | Identity and use |
| --- | --- |
| [v1.5.2 release][release] and [release notes EN][release-en] / [KO][release-ko] | Released 2026-10-13T10:31:42Z; tag resolves to `9838db16910c5f22d9dcc3c7180350cb406fd236`. Product/content identity and account/native scope. Asset names read through GitHub release metadata; ZIP bytes were not downloaded or checked in this task. |
| [Account README template][template-en], [SKILL template][controller], decision guides [EN][decision-en] / [KO][decision-ko], [assembler][assembler] | Tagged source for the assembled layout, complete-read requirement, content-only limitations and footer rule. Templates were inspected, not used as upload artifacts. |
| Setup guides [EN][setup-en] / [KO][setup-ko] | Version-pinned account setup, backup, product-version and standing-instruction steps. Historical screenshots in those guides do not establish today's UI or a new account observation. |
| [Worksheet snapshot][worksheet] | Gist revision `c06609a1278477055d1267041b08d1464124aebc`, committed 2026-10-14T11:31:32Z; EN/KO task and duplication baseline. Read through the public GitHub Gist API after the web reader could not open it. |
| [Issue #113][issue-113] | Open; body updated 2026-10-15T02:08:10Z when read. Distribution, first use, repeat use and independent recommendation remain separate. Related searches found existing setup work including merged PR #108; no new issue or PR created. |
| [Claude Skills guide][claude-skills] and [personalization guide][claude-instructions] | Current public guidance for menu labels and instruction scope; no signed-in account or organization policy was inspected. |
| Assigned working baseline | `227a528996d93c423851db1d663f9572be534e59`; remote `main` matched at preparation. Later main work including #126/#128, and pending #130, is not treated as released v1.5.2 behavior. |

**Remaining unknowns / 미확인:** actual account eligibility and policy, today's
menu layout in each client, upload acceptance, required capability and enabled
state, skill/method loading, complete read, application, useful result and later
reuse. Current Claude guidance also describes account-skill sync into newer
Claude Code versions; this draft does not qualify that host path or equate it
with installing the separate OpenSocrates native plugin. No automatic-use,
successful-installation or quality-improvement guarantee is made.

실제 계정의 사용 가능 여부·정책, 클라이언트별 현재 메뉴, 업로드 수락, 필요한
기능·켜짐 상태, 스킬·방법 불러오기, 전체 읽기, 적용, 유용한 결과와 이후
재사용은 미확인입니다. 현재 Claude 안내에는 새 Claude Code 버전의 계정 스킬
동기화도 나오지만 이 초안은 그 경로를 지원 검증하거나 별도 OpenSocrates
네이티브 플러그인 설치와 같은 것으로 취급하지 않습니다. 자동 사용·설치 성공·
품질 향상을 보장하지 않습니다.

[account-zip]: https://github.com/ParkerHwang/OpenSocrates/releases/download/v1.5.2/opensocrates-1.5.2-claude-chat-skills.zip
[release]: https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2
[release-en]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.md
[release-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.ko.md
[setup-en]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/setup-guide.md
[setup-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/setup-guide.ko.md
[standing-en]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/setup-guide.md#claude-standing-instructions
[standing-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/setup-guide.ko.md#claude-standing-instructions
[template-en]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/plugin-src/claude-chat/README.md.tmpl
[controller]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/plugin-src/claude-chat/SKILL.md.tmpl
[decision-en]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/plugin-src/claude-chat/guide.en.md
[decision-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/plugin-src/claude-chat/guide.ko.md
[assembler]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/tools/build_content_hosts.py
[worksheet]: https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5/c06609a1278477055d1267041b08d1464124aebc
[worksheet-en]: https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5/c06609a1278477055d1267041b08d1464124aebc#file-01-first-use-en-md
[worksheet-ko]: https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5/c06609a1278477055d1267041b08d1464124aebc#file-02-first-use-ko-md
[claude-skills]: https://support.claude.com/en/articles/12512180-use-skills-in-claude
[claude-instructions]: https://support.claude.com/en/articles/10185728-understanding-claude-s-personalization-features
[issue-113]: https://github.com/ParkerHwang/OpenSocrates/issues/113
[issues]: https://github.com/ParkerHwang/OpenSocrates/issues
