# Codex first use and safe recovery / Codex 첫 사용과 안전한 오류 복구

Draft prepared for the OpenSocrates maintainer with AI assistance. Public-source snapshot: **15 October 2026, 05:27–05:30 UTC / 14:27–14:30 Asia/Seoul**. This document is preparation for review, not a published setup change or a report of a new installation or test.

OpenSocrates 유지관리자를 위해 AI의 도움으로 준비한 검토용 초안입니다. 공개 자료 확인 시점은 **2026년 10월 15일 14:27–14:30 한국 시각 / 05:27–05:30 UTC**입니다. 새 설치·실험 결과나 공개된 설정 변경을 뜻하지 않습니다.

## English

### 1. Start with the released Codex package

Use the [v1.5.2 release](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2) and its [setup guide](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/setup-guide.md#1-codex-review-and-approve-opensocrates-hooks). The documented native Codex environments are Apple-silicon Mac and Windows x64. Node.js 20 or later is required; the native runtime is bundled. Intel Mac, native Linux and Windows ARM64 qualification are not added by this release. Follow the [Windows guide](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/windows-v1.5.md) for the Windows shell and platform limits.

For a **new installation**, run in your terminal:

```sh
npx --yes opensocrates@1.5.2 install --host codex
```

For an **existing installation**, use this instead:

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

Then inspect the installation state:

```sh
npx --yes opensocrates@1.5.2 status --host codex
```

Check the reported version and enabled state separately. Preserve a deliberately disabled installation. `status` does not approve hooks or establish that a particular message received guidance. These commands are instructions for the reader; none was executed while preparing this draft.

### 2. Review hook trust in Codex

Open **interactive Codex** in your usual project folder by running `codex`. Enter **`/hooks` in Codex's input field**, rather than in your shell.

Find the entries from `opensocrates@opensocrates`. Read their origin and exact commands, and use Codex's trust controls to approve only the definitions you trust. The package has seven hook events: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop` and `SessionEnd`. Already trusted, unchanged entries need no new approval. New or changed definitions require a fresh review; installation and enabling do not automatically grant trust. [OpenAI's hook documentation](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

After setup, start a fresh conversation. The setup completion check is: the intended plugin version is enabled, its current hook definitions are trusted, and a fresh conversation can start. It does not require proving that every answer uses a method. If policy prevents plugin hooks, leave that boundary in place and report the limitation; do not bypass trust or lower general permissions. The released setup guide uses `status` and interactive `/hooks`; `codex hooks` and `opensocrates diagnose --host codex` are not its supported verification paths.

### 3. Try one small judgment task

This is a newly authored **synthetic example**, not a model output, customer story or improvement result. Paste it into a fresh conversation:

```text
Use OpenSocrates where appropriate. For a fictional internal work queue,
compare buying a cloud tool, building a tool, and temporary manual work.
The limits are KRW 300,000 per month, one operator and 50 items per week.
No vendor specifications or development estimates have been supplied.
Give a provisional recommendation, explain its grounds and identify what
must be checked before committing. Do not invent feasibility or publish,
install, purchase or modify anything.
```

An optional follow-up changes one condition:

```text
The work must now function without an internet connection. Keep the same
budget, operator and workload. Revisit every alternative and the fallback.
Explain which assumption changed and what remains unknown.
```

Look at the answer: does it preserve the three original limits, revisit each alternative when the offline condition arrives, and distinguish missing evidence from impossibility? Naming OpenSocrates here is an explicit first-use aid. Success would not establish spontaneous selection, native delivery or a quality improvement over another answer. The maintainer's [earlier EN/KO first-use examples](https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5) are also synthetic task designs.

### 4. Keep the observations separate

| Observation | What it establishes | What it leaves open |
| --- | --- | --- |
| Package installed; plugin enabled | Installation and enabled state at the time checked | Current hook trust and delivery to a particular turn |
| Current definitions trusted in `/hooks` | Host permission for those definitions | Whether they ran or delivered guidance on the task |
| Entry guidance returned or delivered, if observable through supported host evidence | Only the observed transport stage | Selection, complete canonical reading, application and usefulness |
| A method was selected or its text returned | A candidate or content was made available | Complete reading and eligibility for this task |
| The agent reports a complete canonical read and use | An agent report; retain its limits | Independent native proof of application or benefit |
| The answer meets the task's concrete requirements | A useful outcome for that task | General quality, cost, speed or repeat-use improvement |

An exact-format conversion can legitimately need no method. Reader guidance alone may also suffice. A **valid** `no_intervention` response with an empty selection is normal; do not force a method or relabel substantive reasoning as mechanical to obtain it. A candidate found inapplicable after reading must remain unapplied. [Current source guidance](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/shared/decision/guide.en.md)

The line `Powered by OpenSocrates` is conditional: an eligible canonical method must have been completely read and actually applied. Reader guidance alone and mechanical work do not qualify. Its presence is not a native receipt; its absence alone does not diagnose installation failure. An unobservable stage stays **unknown**. Complete the user's task after its actual required checks; do not seek an unavailable application receipt as an extra completion gate. [Released evidence boundary](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.md#attribution-privacy-and-evidence)

### 5. Recover according to the installed version

**Release snapshot:** GitHub's latest release was v1.5.2, tagged source commit `9838db16910c5f22d9dcc3c7180350cb406fd236`. Public `main` matched `227a528996d93c423851db1d663f9572be534e59`. [PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130) was open and Draft at `197b317b4aeca4928fabe515dbfef6a98803e568`. A development package can still display 1.5.2 while containing later changes; its source SHA/package identity matters. Recheck this snapshot before publication.

| Symptom or state | Released v1.5.2 | `main` / Draft difference at this snapshot | Safe next step |
| --- | --- | --- | --- |
| Installed, but disabled or hook trust unknown | Installation alone does not establish either state | No fix changes the user's trust decision | Inspect enabled state and interactive `/hooks`; preserve intentional disabling and policy restrictions |
| No method or no attribution footer | Can be legitimate for mechanical work, reader guidance or a valid empty selection | Scope wording expanded in merged #126; it does not guarantee use | Judge the task and observable evidence; do not infer a broken install from the footer |
| Large message continues but entry is missing | A reproduced native parser defect rejects non-`PostToolUse` envelopes over 32,768 bytes; default submission discovery shares that path | [Merged #128](https://github.com/ParkerHwang/OpenSocrates/pull/128) fixes the bounded default submission-discovery path in `main`; it is not in the published v1.5.2 package | Record version and whether the task was small/large. A smaller synthetic example can help characterize the symptom, but is not a guaranteed workaround. Updating to the same published version does not add this fix |
| `invalid_decision_request` | Input was rejected; malformed `select` envelopes can produce the same generic reason without naming a field | [#129](https://github.com/ParkerHwang/OpenSocrates/issues/129) remains open. Draft #130 proposes `field`, `error`, `expected` and `repair: correct_field_once` plus an envelope guide | Ask the agent to consult the installed request example and allowed values and correct the input; do not resend it unchanged or treat rejection as normal empty selection. Do not expect Draft fields from the release |
| `decision_unavailable`, `canonical_content_unavailable` or launcher failure | Report the observed category. In this release malformed JSON can also appear as `decision_unavailable`, so that label alone does not establish an outage | Draft #130 separates malformed input from faults after acceptance; this contract is unreleased | Preserve task constraints and method eligibility. Let the agent follow its installed recovery guide; never invent a replacement procedure or claim an unread method was applied |
| `no_intervention` with a valid empty selection | Normal outcome, separate from invalid input or unavailability | Draft #130 makes these distinctions more explicit | Continue ordinary work with constraints intact; do not bypass the empty result through method-file lookup |
| Candidate is inapplicable, or only reader guidance is needed | Neither requires claiming method application | Draft #130 documents these as separate states | Retire the inapplicable candidate; keep any actual required stop/hold. Finish the requested artifact using sufficient support |
| Task is complete but application remains `unverified` | This can be a measurement limit | Neither merged transport work nor Draft diagnostics creates an application receipt | Deliver the completed artifact and state the evidence limit; do not repeat unchanged checks |

The large-input boundary is for the **JSON hook envelope**, not a promise about a user's prompt length or every event. The scoped correction retains the existing 4 MiB ingress limit; it is not an unlimited-input feature. The [EN investigation](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/codex-large-submission-entry.md) and [bounded live transport record](https://github.com/ParkerHwang/OpenSocrates/issues/124#issuecomment-6161617961) support that specific correction. They do not prove the historical cause, Desktop UI qualification, attention, application or usefulness. [#124 remains open](https://github.com/ParkerHwang/OpenSocrates/issues/124); Draft #130's input-error work does not close it.

Do not run the host's control launcher by hand, fabricate hook payloads, manufacture receipts, copy authentication or purge an installation to troubleshoot these states. Do not install a development build merely because this table describes it. Preserve ordinary task progress and use a separate authorized recovery process if a lifecycle change is actually needed.

### 6. Share a minimal, non-sensitive report

If you choose to report a problem, provide only:

- Date/time and timezone; Codex CLI or Desktop; OS/architecture; host build if known.
- OpenSocrates version; released package versus development build, with source SHA/package hash only if already available.
- Enabled state as **enabled / disabled / unknown** and current hook trust as **trusted / untrusted / unknown**, with how each was observed. Lack of observation is not a confirmed negative.
- A short task category or newly written synthetic example; expected versus observed behavior.
- The safe error category, or the stage that is unknown; small/large input category or a non-sensitive byte count if already known. Say when a size is prompt bytes rather than hook-envelope bytes.
- Whether the attempt explicitly named OpenSocrates. Keep spontaneous use, reminder-assisted use, first use and later reuse separate; report failures/timeouts without selecting only successful retries.

Do not attach the real prompt, full conversation, raw host logs, screenshots, credentials, company files, workspace paths or hidden reasoning. If a fact cannot be observed safely, write `unknown`. Ordinary feedback may use the [existing issue](https://github.com/ParkerHwang/OpenSocrates/issues/124) when it fits; avoid duplicate reports. Vulnerabilities belong in [private vulnerability reporting](https://github.com/ParkerHwang/OpenSocrates/security/advisories/new), without public exploit details. [Contribution and privacy rules](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/CONTRIBUTING.md)

## 한국어

### 1. 공개된 Codex 패키지에서 시작하기

[v1.5.2 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.2)와 해당 버전의 [설정 안내](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/setup-guide.ko.md#1-codex-opensocrates-훅을-검토하고-승인하기)를 사용하세요. 문서에 명시된 Codex 네이티브 환경은 Apple Silicon Mac과 Windows x64입니다. Node.js 20 이상이 필요하고 네이티브 런타임은 포함됩니다. 이번 릴리스는 Intel Mac·네이티브 Linux·Windows ARM64 검증을 추가하지 않습니다. Windows의 셸과 플랫폼 한계는 [Windows 안내](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/windows-v1.5.ko.md)를 따릅니다.

**처음 설치**한다면 터미널에서 실행합니다.

```sh
npx --yes opensocrates@1.5.2 install --host codex
```

**기존 설치**라면 대신 업데이트 명령을 사용합니다.

```sh
npx --yes opensocrates@1.5.2 update --host codex
```

이후 설치 상태를 확인합니다.

```sh
npx --yes opensocrates@1.5.2 status --host codex
```

표시된 버전과 켜짐 상태를 각각 확인하세요. 의도적으로 꺼둔 설치는 보존합니다. `status`가 훅을 승인하거나 특정 메시지에 안내가 전달됐음을 입증하지는 않습니다. 위 명령은 독자를 위한 안내이며, 이 초안을 준비하면서 실행하지 않았습니다.

### 2. Codex에서 훅 신뢰 확인하기

평소 프로젝트 폴더의 터미널에서 `codex`를 실행해 **대화형 Codex**를 엽니다. **Codex 입력칸에 `/hooks`**를 입력합니다. 일반 셸에 입력하는 명령이 아닙니다.

출처가 `opensocrates@opensocrates`인 항목을 찾습니다. 출처와 정확한 명령을 읽고 신뢰하는 정의만 Codex의 신뢰 기능으로 승인하세요. 패키지의 훅 이벤트는 `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`, `SessionEnd`의 일곱 개입니다. 이미 신뢰했고 바뀌지 않은 항목은 다시 승인할 필요가 없습니다. 새 정의나 변경된 정의는 다시 검토해야 하며, 설치·켜짐이 자동으로 훅 신뢰를 부여하지 않습니다. [OpenAI 공식 훅 안내](https://learn.chatgpt.com/docs/hooks#review-and-trust-hooks)

설정 후 새 대화를 시작합니다. 설치 설정의 완료 기준은 의도한 버전의 플러그인이 켜져 있고, 현재 훅 정의가 신뢰된 상태이며, 새 대화를 시작할 수 있는 것입니다. 모든 답변의 방법 사용을 입증해야 하는 것은 아닙니다. 정책이 플러그인 훅을 막으면 그 경계를 유지하고 한계를 기록하세요. 신뢰 승인을 우회하거나 전체 권한을 낮추지 않습니다. 공개 설정 안내의 확인 경로는 `status`와 대화형 `/hooks`입니다. `codex hooks`와 `opensocrates diagnose --host codex`는 이 버전에서 지원하는 확인 경로가 아닙니다.

### 3. 작은 판단 과제 하나 시도하기

다음은 새로 작성한 **합성 예시**입니다. 실제 모델 답변·사용자 경험·개선 결과가 아닙니다. 새 대화에 입력해 보세요.

```text
맞는 부분에 OpenSocrates를 사용해줘. 가상의 사내 업무 대기열을 위해
클라우드 도구 구매, 직접 제작, 당분간 수동 운영을 비교해줘.
월 예산은 30만원 이하, 운영자는 한 명, 처리량은 주 50건이야.
업체 사양과 개발 기간 추정은 제공되지 않았어.
잠정 추천과 그 근거, 결정 전에 확인할 사항을 정리해줘.
실행 가능성을 만들어내거나 게시·설치·구매·수정을 하지 마.
```

선택적으로 조건 하나를 바꿔 이어갑니다.

```text
이제 인터넷 연결 없이 작동해야 해. 예산·운영자·처리량은 유지해줘.
각 대안과 후속 대안을 다시 검토하고, 어떤 가정이 달라졌으며
무엇을 아직 모르는지 설명해줘.
```

답변에서 원래 세 조건이 유지되는지, 오프라인 조건을 각 대안에 반영했는지, 근거 부족을 불가능으로 단정하지 않는지 봅니다. 여기서 OpenSocrates 이름을 부르는 것은 첫 사용을 돕는 명시적 요청입니다. 성공해도 자발적 선택·네이티브 전달·다른 답변 대비 개선을 입증하지 않습니다. 유지관리자의 [기존 EN·KO 첫 사용 예시](https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5)도 합성 과제 설계입니다.

### 4. 확인한 상태를 구분하기

| 관찰 | 확인하는 것 | 여전히 모르는 것 |
| --- | --- | --- |
| 패키지 설치·플러그인 켜짐 | 확인 당시의 설치·활성화 상태 | 현재 훅 신뢰와 특정 턴의 안내 전달 |
| `/hooks`에서 현재 정의가 신뢰됨 | 해당 정의에 대한 호스트 권한 | 실제 과제에서 실행·전달됐는지 |
| 지원되는 호스트 증거로 안내 반환·전달을 관찰함 | 실제 관찰한 전달 단계 | 방법 선택·정본 전체 읽기·적용·유용성 |
| 방법이 선택되거나 본문이 반환됨 | 후보 또는 콘텐츠 제공 | 전체 읽기와 이번 과제의 적용 가능성 |
| 에이전트가 전체 읽기·사용을 보고함 | 한계가 있는 에이전트 보고 | 독립적인 네이티브 적용·효과 증거 |
| 답변이 과제의 구체적인 요구를 충족함 | 해당 과제에서 쓸 수 있는 결과 | 일반적인 품질·비용·속도·재사용 개선 |

정해진 형식 변환은 방법이 필요 없을 수 있습니다. 독자 안내만으로 충분할 수도 있습니다. **유효한** `no_intervention`과 빈 선택은 정상 결과입니다. 방법을 강제하거나 빈 선택을 얻기 위해 실질적인 추론을 기계적 작업으로 바꾸지 마세요. 읽은 뒤 부적합한 것으로 확인된 후보는 적용하지 않은 상태로 둡니다. [현재 소스 안내](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/shared/decision/guide.ko.md)

`Powered by OpenSocrates`는 적격한 정본 방법 전체를 읽고 실제 적용한 경우에만 붙이는 문구입니다. 독자 안내만 쓰거나 기계적 작업만 했다면 해당하지 않습니다. 이 문구 자체는 네이티브 영수증이 아니며, 없다는 사실만으로 설치 실패를 진단할 수 없습니다. 관찰할 수 없는 단계는 **미확인(unknown)**으로 남깁니다. 사용자가 요청한 일의 실제 필수 점검을 마치면 결과물을 전달하세요. 제공되지 않는 적용 영수증을 추가 완료 조건으로 만들지 않습니다. [공개 버전의 증거 경계](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.ko.md#사용-표기개인정보증거)

### 5. 설치 버전에 맞게 오류 복구하기

**릴리스 확인 시점:** GitHub 최신 릴리스는 v1.5.2였고, 태그의 소스 커밋은 `9838db16910c5f22d9dcc3c7180350cb406fd236`입니다. 공개 `main`은 `227a528996d93c423851db1d663f9572be534e59`와 일치했습니다. [PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130)은 `197b317b4aeca4928fabe515dbfef6a98803e568`에서 열린 Draft였습니다. 개발 패키지가 1.5.2라고 표시돼도 이후 변경을 포함할 수 있으므로 소스 SHA·패키지 식별값을 구분해야 합니다. 공개 전 이 상태를 다시 확인하세요.

| 증상·상태 | 공개 v1.5.2 | 확인 당시 `main`·Draft와의 차이 | 안전한 다음 행동 |
| --- | --- | --- | --- |
| 설치됐지만 꺼져 있거나 훅 신뢰가 미확인 | 설치만으로 두 상태를 알 수 없음 | 수정이 사용자의 신뢰 결정을 대신하지 않음 | 켜짐과 대화형 `/hooks` 확인. 의도적 비활성화·정책 제한 보존 |
| 방법이나 사용 표기가 없음 | 기계적 작업·독자 안내·정상 빈 선택에서는 가능 | 병합된 #126이 범위 문구를 넓혔지만 사용을 보장하지 않음 | 과제와 관찰 근거를 확인. 문구 유무만으로 설치 고장 단정 금지 |
| 큰 메시지에서 작업은 계속되지만 진입 안내가 없음 | 재현된 네이티브 파서 결함이 `PostToolUse` 이외의 32,768바이트 초과 봉투를 거부하며 기본 제출 안내도 이 경로를 사용 | [병합된 #128](https://github.com/ParkerHwang/OpenSocrates/pull/128)이 `main`의 기본 제출 안내 경로를 한정해 수정. 공개 v1.5.2 패키지에는 없음 | 버전과 입력의 소형·대형 여부 기록. 작은 합성 예시는 증상을 구분하는 데 도움이 될 수 있으나 보장된 우회책이 아님. 같은 공개 버전으로 업데이트해도 이 수정이 추가되지는 않음 |
| `invalid_decision_request` | 입력 거부. 잘못된 `select` 요청들이 필드 표시 없는 같은 일반 사유를 반환할 수 있음 | [#129](https://github.com/ParkerHwang/OpenSocrates/issues/129)는 열려 있음. Draft #130은 `field`, `error`, `expected`, `repair: correct_field_once`와 봉투 안내를 제안 | 에이전트가 설치된 요청 예시와 허용 값을 보고 입력을 수정하도록 함. 같은 입력을 반복하거나 정상 빈 선택으로 취급하지 않음. 출시판에 Draft 필드가 있으리라 기대하지 않음 |
| `decision_unavailable`·`canonical_content_unavailable`·런처 실패 | 관찰한 범주를 기록. 이 버전은 잘못된 JSON도 `decision_unavailable`로 보일 수 있어 이 값만으로 장애를 확정할 수 없음 | Draft #130이 잘못된 입력과 수락 후 실패를 구분하며 아직 미출시 | 과제 제약·방법 적격성 보존. 에이전트가 설치된 복구 안내를 따르게 함. 대체 절차를 만들어내거나 읽지 않은 방법을 적용했다고 주장하지 않음 |
| 유효한 빈 선택과 `no_intervention` | 입력 오류·사용 불가와 다른 정상 결과 | Draft #130은 이 구분을 더 명시적으로 설명 | 제약을 유지하며 일반 작업 계속. 방법 파일을 직접 읽어 빈 결과를 우회하지 않음 |
| 부적합한 후보 또는 독자 안내만으로 충분한 상태 | 방법을 적용했다고 주장할 필요 없음 | Draft #130은 각각의 상태로 설명 | 부적합한 후보 제외. 실제 필수 중단·보류는 유지. 충분한 지원으로 요청한 결과물 완성 |
| 결과물은 완성했지만 적용이 `unverified` | 측정의 한계일 수 있음 | 전달 수정의 병합이나 Draft 진단이 적용 영수증을 만들지 않음 | 완성한 결과물과 증거 한계 전달. 변하지 않은 검사 반복 금지 |

큰 입력 경계는 **훅의 JSON 봉투** 기준이며 사용자 프롬프트 길이나 모든 이벤트에 대한 보장이 아닙니다. 수정은 기존 4 MiB 입구 한도를 유지하며 무제한 입력 기능이 아닙니다. [한국어 조사 문서](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/docs/codex-large-submission-entry.ko.md)와 [범위를 제한한 실제 전달 기록](https://github.com/ParkerHwang/OpenSocrates/issues/124#issuecomment-6161617961)은 그 수정의 근거입니다. 과거 원인·Desktop UI 검증·주의·실제 적용·유용성을 입증하지 않습니다. [#124는 열려 있으며](https://github.com/ParkerHwang/OpenSocrates/issues/124), Draft #130의 입력 오류 수정이 이 이슈를 닫지는 않습니다.

이 상태를 확인하려고 호스트 전용 제어 런처를 직접 실행하거나 훅 입력·영수증을 만들어내거나 인증을 복사하거나 설치를 purge하지 마세요. 표에서 개발 변경을 설명한다고 개발 빌드를 설치하라는 뜻은 아닙니다. 일반 작업의 진행을 보존하고, 설치 상태 변경이 실제 필요하면 별도로 승인된 복구 절차를 사용합니다.

### 6. 민감정보 없는 최소 피드백

문제를 제보하려면 다음만 제공합니다.

- 날짜·시간·시간대, Codex CLI 또는 Desktop, 운영체제·아키텍처, 알고 있다면 호스트 빌드.
- OpenSocrates 버전, 공개 패키지인지 개발 빌드인지, 이미 확보했다면 소스 SHA·패키지 해시.
- 켜짐은 **켜짐 / 꺼짐 / unknown**, 현재 훅 신뢰는 **신뢰됨 / 신뢰되지 않음 / unknown**으로 표시하고 확인 방법 기재. 관찰하지 못했다는 사실을 확인된 부정 상태로 바꾸지 않음.
- 짧은 작업 종류나 새로 작성한 합성 예시, 기대한 동작과 관찰한 동작.
- 안전한 오류 범주 또는 모르는 단계, 입력의 소형·대형 구분이나 이미 아는 비민감 바이트 수. 크기가 프롬프트 기준이면 훅 봉투 크기와 구분.
- OpenSocrates를 명시적으로 불렀는지. 자발적 사용·명시 요청 후 사용·첫 사용·이후 재사용을 구분하고 성공한 재시도만 고르지 않으며 실패·시간 초과도 기록.

실제 프롬프트·전체 대화·원시 호스트 로그·스크린샷·인증정보·회사 파일·작업공간 경로·숨겨진 추론은 첨부하지 않습니다. 안전하게 관찰할 수 없으면 `unknown`이라고 씁니다. 일반 피드백은 내용이 맞는 [기존 이슈](https://github.com/ParkerHwang/OpenSocrates/issues/124)를 활용해 중복을 피할 수 있습니다. 취약점은 공개된 공격 상세 없이 [비공개 취약점 제보](https://github.com/ParkerHwang/OpenSocrates/security/advisories/new)를 사용합니다. [기여·개인정보 규칙](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/CONTRIBUTING.md)

## Source and integration notes / 근거와 통합 메모

- Released product/content: [v1.5.2 EN](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.md), [KO](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.ko.md); source `9838db16910c5f22d9dcc3c7180350cb406fd236`, content revision 5. The annotated tag object's SHA is a different identity.
- Source baseline: `227a528996d93c423851db1d663f9572be534e59`; [Codex README template](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/codex/README.md.tmpl), [controller template](https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/plugin-src/codex/skills/opensocrates/SKILL.md.tmpl), and the EN/KO large-input investigation were read. Templates describe source, not an installed release's proven behavior.
- Public state read: [#113](https://github.com/ParkerHwang/OpenSocrates/issues/113), [#124](https://github.com/ParkerHwang/OpenSocrates/issues/124), [#129](https://github.com/ParkerHwang/OpenSocrates/issues/129), [Draft #130](https://github.com/ParkerHwang/OpenSocrates/pull/130), and the linked EN/KO gist. Issue/PR reports are attributed evidence, not newly reproduced results. No adoption or uplift claim is derived from them.
- S083 changed only this draft. No product code, canonical input, generated output, installation, trust, account, automation or publication was changed. No new model experiment, host probe, browser session, test, build or final review was run. Canonical regeneration is unnecessary for this standalone draft.
- Before publication: the integrator should reconcile release/`main`/PR state, verify EN/KO meaning and links against the exact frozen candidate, and retain the separation of installation, trust, delivery, reading, application and usefulness. Final integrated-candidate verification belongs to the assigned verification owners; this draft does not claim their results.
