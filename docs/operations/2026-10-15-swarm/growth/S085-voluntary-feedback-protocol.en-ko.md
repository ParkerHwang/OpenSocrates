# Voluntary first use and seven-day follow-up / 자발적 첫 사용과 7일 후속 확인

Draft for owner review, 15 October 2026 / 소유자 검토용 초안, 2026년 10월 15일.

This is a protocol and copy draft. It creates no survey service, form endpoint,
participant tracker, reminder or automation. No person has been contacted or
enrolled through this work. Actual first-use counts, follow-up eligibility and
reuse results are **unknown**. The fictional examples below are not observations.

이 문서는 절차와 문안의 초안입니다. 설문 서비스·폼 접수처·참여자 추적기·알림·
자동화를 만들지 않습니다. 이 작업으로 연락하거나 참여 등록한 사람은 없습니다.
실제 첫 사용 수·후속 확인 대상 수·재사용 결과는 **unknown(미확인)**입니다.
아래 가상 사례는 관찰 결과가 아닙니다.

## English

### 1. Keep the existing request and separate the observations

Keep the existing [first-use worksheet][worksheet] and [Claude skill showcase][showcase]
as the public entry points. They already ask for an app, product version,
non-sensitive task summary and a check that helped or failed. This draft adds
optional date and follow-up choices; it does not replace, repost or automatically
amend either public request. Any later use of the copy remains an owner-manual
action under the venue's rules. Do not turn an old comment into enrollment without
the contributor's new, explicit agreement to the notice below.

| Observation | What it can support | What it cannot establish |
| --- | --- | --- |
| Star, download or setup report | Discovery, a download event or reported setup, respectively | First task use, activation, usefulness or retention |
| Voluntary first-use report | A contributor says they chose to try a task and received an answer, including a failed or unhelpful answer | Independently verified use, method reading/application or improved quality |
| Intention to use again | A stated intention | Actual later use |
| Report of later use | Self-reported use on a later task/day within the stated window | Independent verification, a causal product effect or population retention |
| Independent recommendation | A separately evidenced, independent recommendation | Anything established merely by a maintainer's example or this worksheet |

“Voluntary” describes the contributor's choice to participate. A person can
voluntarily try a worksheet that explicitly names OpenSocrates. That does not
establish spontaneous model selection. Keep worksheet trials, contributor-chosen
work tasks and unknown task origins separate. If reported, also distinguish an
explicit skill request from use without mentioning it in that turn; a standing
instruction may still exist. Do not infer the trigger from a footer or from
silence. Hook delivery, full reading, application and usefulness remain separate.

An incomplete setup report is still useful feedback, but is not a completed
first-use report. A follow-up turn in the worksheet or a maintainer-requested
rerun is part of the initial trial, not evidence of voluntary later reuse.

### 2. Proposed notice and optional first-use reply

The owner must be able to honor these handling rules before using this notice.
The contributor can give ordinary feedback without joining follow-up, skip any
field, choose `unknown`, or stop. Positive feedback, a star, a recommendation or
a reason for declining is never required. There is no reward for a favorable report.

**Notice — proposed copy**

> I maintain OpenSocrates; this request was prepared with AI assistance. Feedback
> is optional. If you agree, I may use a short coded summary to improve setup and
> report aggregate first-use/follow-up counts. Please share only broad task
> categories and your own non-sensitive assessment. Do not send a real name,
> contact details, company/client names, original work, prompts, conversations,
> screenshots, credentials or hidden reasoning. A public reply is visible on the
> platform and may show your existing account; public does not mean anonymous.
> No new account or contact information is needed for this request.
>
> A later check is optional and separate. By default I will not contact you. You
> may return to the same thread yourself, or explicitly allow one public reply
> there after the observation window. No DM, email or repeated reminder. You can
> decline or withdraw by replying here; no explanation or further contact is needed.
> Any local coded note will be removed within 30 days of receipt, or earlier on
> withdrawal. Future summaries will omit withdrawn records; any still-linkable
> totals will be corrected. Already unlinked aggregate totals and third-party
> copies may not be retractable. The platform controls public-post retention;
> you can edit/delete your own reply using its controls, but I cannot promise
> removal from platform backups or archives.

**First-use reply — copy only the fields you want**

```text
Coded-summary permission: yes / no
App/profile and product version: [broad labels, or unknown]
Stage: setup only / tried a task and received an answer / unknown
Task origin: public worksheet / my own chosen task / unknown
Task/check: [e.g. client email — kept the draft-review promise / missed it / unclear]
First actual task-use day: [UTC YYYY-MM-DD, or unknown; no exact time needed]
Optional trigger: explicitly named OpenSocrates / did not name it that turn / unknown
Follow-up choice: I may return myself / one public reply here is okay / no follow-up
```

Do not require the optional trigger to establish first use. “Did not name it” is
a self-report, not proof of native activation or absence of standing instructions.
If only a local date is known, do not ask for location or precise activity times;
leave UTC eligibility unknown unless the contributor volunteers a UTC date.
Permission left blank is not permission to include a response-level record in
this cohort or to contact the contributor. Ordinary support can still proceed.

### 3. First-use date, eligibility and one manual check

Use a known **UTC first-use date**, not the download, installation, signup,
comment, publication or program-start date. Reconcile a corrected date openly;
do not move it earlier to make a record eligible. Existing comments and intentions
do not supply a first-use date by inference.

For date-only input, this draft uses a conservative full-calendar-day convention:

| Item | Definition |
| --- | --- |
| `D` | Contributor-reported UTC date of the first actual task use |
| Observation window | The next seven complete UTC dates: `D+1` through `D+7`, inclusive |
| `eligible_at` | `00:00 UTC` on `D+8`; the entire observation window has ended |
| Manual reply window | `eligible_at <= as_of < 00:00 UTC on D+15` |
| Contact permission | Explicit permission for one public reply, still in force; permission is separate from date eligibility |

This is a **seven-day follow-up about reported later use**, not exact day-seven
retention or an exact 168-hour event measure. Waiting until `D+8` avoids pretending
that a date-only record contains a clock time. If `D` is missing, impossible,
conflicting or future-dated, eligibility is `unknown`; do not replace it with
today's date. If `as_of < eligible_at`, the record is `pending`, not a negative
reuse result. A newly reported first use on 15 October 2026 UTC cannot be eligible
before 23 October 2026 00:00 UTC / 09:00 Asia/Seoul under this convention.

At a later, already-authorized manual review, the owner checks the date and
permission. A date-eligible record with no completed answer is `eligible`; it
does not oblige contact. If one reply is permitted, use it only in the original
thread and within the manual reply window. If permission is absent/withdrawn,
the contributor declines, the single reply was already used, or the window has
closed, do not send another invitation. Do not create a reminder or recurring
check. A contributor may return without an invitation; label a late report as
late and use it only if it clearly concerns the fixed observation window. A report
about use after that window is separate qualitative feedback, not a changed
seven-day numerator.

**Manual follow-up — proposed copy; never sent by this session**

> You allowed one follow-up here. For the seven UTC dates [start] through [end]
> after your first-use day, did you choose to use OpenSocrates again on another
> task/day? You can reply: used again / had a relevant task but did not use it /
> had no relevant opportunity / prefer not to answer / unsure. A new turn in the
> first worksheet or a requested rerun does not count as another task. If you
> want, add one broad check that helped or failed; no original work or screenshots.
> No reply is needed, and I will not send a reminder. You may also withdraw your
> coded summary here.

Do not ask people to perform another task so that a reuse count increases. A
positive answer must concern later use they chose before the check, not use done
in response to it. Failure, no opportunity and declining are legitimate responses.

### 4. Minimal handling and denominators

This draft creates no response log. If later adopted, use only an already-owned
manual workflow; do not put real response-level data in this repository, patches
or public operational handoffs. No raw reply exports, user-profile lookup,
cross-site matching, tracking links, fingerprinting or host-log collection.

For a consented report, the minimum temporary coded note is a neutral record code,
permission choices, app/profile/version (or unknown), broad task/check category,
first-use UTC day (or unknown), task origin, the fixed window, whether the one
allowed reply has been used, and the coded outcome. The optional trigger may be
omitted. A temporary reference to the contributor's original public reply may be
used only for permitted same-thread handling, linking a return and withdrawal;
it is linkable data, not anonymous data. Do not copy the username or build a
contact list. Never store these references in the public draft or repo. Delete
the reference together with the coded note within 30 days of receipt. Do not
retain an indefinite reference list under the label “aggregate.”

The contributor can reply to their original report to link a later response;
they do not need to provide a real name, contact address or new identifier. If a
return cannot be linked confidently, keep it as unlinked qualitative feedback;
do not guess or count it as a second first-use record. Merge only an explicitly
linked duplicate report. Unit: a voluntarily contributed report sequence, not a
verified unique person. Deduplication and self-selection limits must accompany
any summary. If local coded data cannot be handled under these rules, retain no
cohort data and do not offer follow-up.

At an explicitly dated cutoff, report counts first:

| Symbol | Meaning |
| --- | --- |
| `F` | Consented self-reported completed first-use records, including unknown first-use dates; exclude setup-only and maintainer/test examples |
| `E` | Records in `F` whose known observation window has ended by the cutoff, with summary permission still in force; lack of contact permission does not remove them |
| `R` | In `E`, reports of voluntary later task use inside the fixed observation window |
| `N` | In `E`, explicit reports of a relevant opportunity but no reuse in that window |
| `J` | In `E`, explicit reports of no relevant opportunity in that window |
| `Q` | In `E`, follow-up declined while permission for the coded summary remains |
| `U` | In `E`, no reply, unsure, incomplete/conflicting outcome or an answer only about a different period |
| `C` | Substantive follow-up outcomes: `R + N + J` |

Use one outcome per eligible record, so `E = R + N + J + Q + U`. Unknown dates
and not-yet-eligible records stay visible outside `E`. The same person can have
a completed first-use report while follow-up is pending. A workflow label such
as `completed` is not a reuse outcome by itself.

If needed, show `R/E` as the **fraction of eligible voluntary report records with
reported reuse**, alongside `C/E` and all five outcome counts. It is neither
population retention nor proof that every other record did not reuse. `J`, `Q`
and `U` remain in `E`; do not silently discard them. An optional opportunity-only
diagnostic `R/(R+N)` must show its exclusions and cannot replace `R/E`. A zero
denominator is `not estimable`, never 0% or 100%. Do not publish small cells,
quotations or combinations of details that could identify a contributor.

A withdrawal of summary permission removes the linked record from future
cohort summaries and any still-recomputable totals; it is not a “no reuse”
response. Disclose cohort-definition changes without preserving identifying
withdrawal details. Aggregate reporting needs no names, reply links or verbatim
text. Do not claim a retention result from this two-hour drafting program; real
cohort coverage, duplicates and seven-day results remain unknown.

## 한국어

### 1. 기존 요청을 유지하고 관찰을 구분하기

기존 [첫 사용 워크시트][worksheet]와 [Claude 스킬 소개 글][showcase]을 공개
진입점으로 유지합니다. 이미 앱·제품 버전·비민감 과제 요약·도움되거나 실패한
확인 사항을 묻고 있습니다. 이 초안은 선택적인 날짜·후속 확인 항목을 더하며,
기존 요청을 대체·재게시·자동 수정하지 않습니다. 이후 문안을 쓰는 일은 해당
공간의 규칙을 따르는 소유자의 수동 작업입니다. 아래 안내에 새로 명시적으로
동의하지 않은 과거 댓글을 참여 등록으로 바꾸지 않습니다.

| 관찰 | 뒷받침할 수 있는 내용 | 확인할 수 없는 내용 |
| --- | --- | --- |
| 스타·다운로드·설정 보고 | 각각 발견·다운로드 사건·설정 자기보고 | 첫 과제 사용·활성화·유용성·유지율 |
| 자발적 첫 사용 보고 | 참여자가 스스로 과제를 시도하고 답변을 받았다는 보고; 실패·도움 안 됨도 포함 | 독립 검증된 사용·방법 읽기/적용·품질 개선 |
| 다시 쓰겠다는 의향 | 의향 | 실제 나중 사용 |
| 이후 사용 보고 | 정해진 기간의 나중 과제/날짜에서 사용했다는 자기보고 | 독립 검증·제품의 인과적 효과·전체 사용자 유지율 |
| 독립 추천 | 별도 근거가 있는 독립 추천 | 제작자 예시나 이 워크시트만으로 확인한 사항 |

‘자발적’은 참여자가 참여를 선택했다는 뜻입니다. OpenSocrates를 명시하는
워크시트를 자발적으로 시도할 수 있지만, 그것이 모델의 자발적 선택을 확인하지는
않습니다. 워크시트 시도·참여자가 고른 업무·과제 출처 미확인을 구분합니다.
보고된 경우 그 턴에서 스킬 이름을 명시했는지도 별도로 구분하되, 상시 지침이
있을 수 있습니다. 사용 표기나 언급이 없다는 이유로 호출 경로를 추정하지
않습니다. 훅 전달·전체 읽기·적용·유용성은 각각 별개입니다.

설정을 끝내지 못한 보고도 유용하지만 완료한 첫 사용 보고는 아닙니다.
워크시트의 후속 턴이나 유지관리자가 요청한 재실행은 최초 시도의 일부이며,
자발적인 이후 재사용의 증거가 아닙니다.

### 2. 동의 안내와 선택적인 첫 사용 답변 초안

소유자는 안내를 쓰기 전에 아래 처리 원칙을 이행할 수 있어야 합니다.
참여자는 후속 확인에 참여하지 않고 일반 피드백만 줄 수 있으며, 항목을
건너뛰거나 `unknown`을 고르거나 중단할 수 있습니다. 긍정 평가·스타·추천·
거절 이유는 요구하지 않습니다. 유리한 보고에 대한 보상은 없습니다.

**안내 — 문안 초안**

> 저는 OpenSocrates 유지관리자이고, 이 요청은 AI의 도움으로 준비했습니다.
> 피드백은 선택입니다. 동의하면 짧은 분류 요약을 설정 개선과 첫 사용·후속
> 확인 집계에 사용할 수 있습니다. 넓은 과제 유형과 비민감한 본인 평가만
> 알려주세요. 실명·연락처·회사/고객 이름·원문 업무 자료·프롬프트·전체 대화·
> 스크린샷·자격증명·숨겨진 추론은 보내지 마세요. 공개 답변은 플랫폼에서
> 보이고 기존 계정이 표시될 수 있으므로 익명 답변이 아닙니다. 이 요청을
> 위해 새 계정이나 연락처를 제공할 필요는 없습니다.
>
> 후속 확인은 별도 선택입니다. 기본적으로 제가 먼저 연락하지 않습니다.
> 같은 글에 직접 돌아오거나, 관찰 기간 뒤 그곳에서 공개 답글 한 번을
> 받는 데 명시적으로 동의할 수 있습니다. DM·메일·반복 알림은 보내지 않습니다.
> 같은 곳에 답해 거절하거나 철회할 수 있고, 설명이나 추가 연락은 필요 없습니다.
> 로컬 분류 기록은 받은 날부터 30일 안에 지우며, 철회하면 더 일찍 지웁니다.
> 이후 집계에서 철회한 기록을 빼고, 아직 연결할 수 있는 집계도 고칩니다.
> 이미 연결을 끊은 총계나 제3자 사본은 회수하지 못할 수 있습니다. 공개 글의
> 보관은 플랫폼이 관리합니다. 본인 답변은 플랫폼 기능으로 수정·삭제할 수
> 있지만 플랫폼 백업이나 외부 보관본의 삭제까지 약속할 수는 없습니다.

**첫 사용 답변 — 원하는 항목만 복사하기**

```text
분류 요약 사용 동의: 예 / 아니요
앱·프로필과 제품 버전: [넓은 분류, 또는 unknown]
단계: 설정만 함 / 과제를 시도하고 답변을 받음 / unknown
과제 출처: 공개 워크시트 / 내가 직접 고른 과제 / unknown
과제·확인 사항: [예: 고객 메일 — 초안 검토 약속 유지 / 놓침 / 불분명]
처음 실제 과제에 쓴 날: [UTC YYYY-MM-DD, 또는 unknown; 정확한 시각 불필요]
선택적 호출 방식: OpenSocrates 이름을 명시함 / 그 턴에는 명시 안 함 / unknown
후속 확인 선택: 직접 돌아올 수 있음 / 여기서 공개 답글 한 번 허용 / 후속 확인 안 함
```

첫 사용 확인에 선택적 호출 항목을 필수로 요구하지 않습니다. ‘이름을 명시 안 함’은
자기보고이며 네이티브 활성화나 상시 지침의 부재를 증명하지 않습니다.
현지 날짜만 알면 위치나 정확한 활동 시각을 요구하지 않습니다. 참여자가 UTC
날짜를 자발적으로 제공하지 않으면 UTC 대상 여부를 미확인으로 둡니다.
동의가 비어 있으면 개별 기록을 이 집계에 포함하거나 연락해도 된다는 뜻이
아닙니다. 일반 지원은 계속할 수 있습니다.

### 3. 첫 사용일, 대상 계산과 수동 확인 한 번

다운로드·설치·가입·댓글·게시·프로그램 시작일 대신 **실제 첫 과제 사용의 UTC
날짜**를 씁니다. 정정 날짜는 드러내고 반영하며, 대상을 늘리려고 앞당기지
않습니다. 기존 댓글이나 사용 의향에서 첫 사용일을 추정하지 않습니다.

날짜만 받으므로 다음처럼 온전한 달력 날짜를 기준으로 보수적으로 계산합니다.

| 항목 | 정의 |
| --- | --- |
| `D` | 참여자가 보고한 첫 실제 과제 사용의 UTC 날짜 |
| 관찰 기간 | 그 다음 온전한 UTC 날짜 7개: `D+1`부터 `D+7`까지 포함 |
| `eligible_at` | `D+8`의 UTC 00:00; 관찰 기간 전체가 끝난 시점 |
| 수동 답글 가능 기간 | `eligible_at <= as_of < D+15의 UTC 00:00` |
| 연락 동의 | 여전히 유효한 공개 답글 한 번의 명시적 동의; 날짜상 대상 여부와 별개 |

이는 **이후 사용 자기보고를 묻는 7일 후속 확인**이며, 정확히 7일째의 유지율이나
168시간 사건 측정이 아닙니다. `D+8`까지 기다려 날짜만 있는 기록에 정확한 시각이
있는 것처럼 다루지 않습니다. `D`가 없거나 성립하지 않거나 충돌하거나 미래이면
대상 여부는 `unknown`이며 오늘로 대체하지 않습니다. `as_of < eligible_at`이면
`pending`으로 두고 재사용 안 함으로 처리하지 않습니다. 이 규칙에서 2026년
10월 15일 UTC의 신규 첫 사용은 10월 23일 UTC 00:00 / 서울 09:00 전에는
후속 확인 대상이 될 수 없습니다.

이후 이미 승인된 수동 검토에서 소유자가 날짜와 동의를 확인합니다. 날짜상
대상이지만 답변을 마치지 않은 기록은 `eligible`이며 연락 의무가 생기지는 않습니다.
답글 한 번에 동의했다면 원래 대화와 수동 답글 가능 기간 안에서만 사용합니다.
동의가 없거나 철회했거나 거절했거나 한 번을 이미 썼거나 기간이 끝났으면
추가 초대를 보내지 않습니다. 알림이나 정기 확인을 만들지 않습니다. 참여자는
초대 없이 돌아올 수 있습니다. 늦은 보고는 늦었다고 표시하고 고정 관찰 기간에
관한 내용이 분명할 때만 사용합니다. 기간 뒤의 사용은 별도 정성 피드백이며
7일 분자를 바꾸지 않습니다.

**수동 후속 확인 — 문안 초안; 이 세션에서는 보내지 않음**

> 여기서 후속 확인 한 번을 허용하셨습니다. 첫 사용일 다음의 UTC 날짜
> [시작일]부터 [종료일]까지 7일 동안, 다른 과제/날짜에서 OpenSocrates를
> 다시 쓰기로 직접 선택하셨나요? 다시 사용함 / 관련 과제는 있었지만 안 씀 /
> 관련 기회가 없었음 / 답하지 않겠음 / 잘 모르겠음 중 하나로 답할 수 있습니다.
> 첫 워크시트의 다음 턴이나 요청받은 재실행은 다른 과제로 세지 않습니다.
> 원하면 도움되거나 실패한 확인 사항을 넓은 분류로 하나만 더해 주세요.
> 원문 업무 자료나 스크린샷은 필요 없습니다. 답하지 않아도 되고 알림은
> 보내지 않습니다. 여기서 분류 요약 사용 동의도 철회할 수 있습니다.

재사용 수를 늘리려고 다른 과제를 시도해 달라고 요구하지 않습니다. 긍정 답변은
이 확인에 응해서 새로 한 사용이 아니라, 확인 전에 본인이 선택한 이후 사용에
관한 것이어야 합니다. 실패·기회 없음·거절도 유효한 응답입니다.

### 4. 최소 처리와 분모

이 초안은 응답 기록장을 만들지 않습니다. 나중에 채택하더라도 이미 소유한
수동 업무 흐름만 사용하며, 실제 개별 응답을 이 저장소·패치·공개 운영 인계에
넣지 않습니다. 원문 답변 내보내기·사용자 프로필 조회·사이트 간 매칭·추적 링크·
핑거프린팅·호스트 로그 수집은 하지 않습니다.

동의한 보고의 임시 분류 기록은 중립적인 기록 코드·동의 선택·앱/프로필/버전
(또는 미확인)·넓은 과제/확인 유형·첫 사용 UTC 날짜(또는 미확인)·과제 출처·
고정 기간·허용된 답글 한 번의 사용 여부·결과 분류만 둡니다. 선택적 호출 방식은
생략할 수 있습니다. 원래 공개 답변의 임시 참조는 허용된 같은 대화의 처리·
재방문 연결·철회에만 쓸 수 있습니다. 연결 가능한 정보이지 익명 정보는 아닙니다.
사용자 이름을 복사하거나 연락처 명단을 만들지 않습니다. 공개 초안이나 저장소에
참조를 저장하지 않습니다. 받은 날부터 30일 안에 분류 기록과 함께 지웁니다.
‘집계’라는 이름으로 참조 목록을 무기한 보관하지 않습니다.

참여자는 원래 답변에 이어 답해 후속 보고를 연결할 수 있습니다. 실명·연락처·
새 식별자는 필요 없습니다. 확실히 연결하지 못하면 연결 불가 정성 피드백으로
두고 추측하거나 두 번째 첫 사용으로 세지 않습니다. 명시적으로 연결된 중복
보고만 합칩니다. 단위는 자발적으로 제공된 보고 묶음이며 검증된 고유 인원이
아닙니다. 집계마다 중복 판별과 자발적 참여의 한계를 표시합니다. 이 원칙대로
로컬 분류 정보를 처리할 수 없으면 집계 정보를 보관하지 않고 후속 확인도
제안하지 않습니다.

집계 기준시점을 명시하고 우선 개수를 보고합니다.

| 기호 | 뜻 |
| --- | --- |
| `F` | 분류 요약에 동의한 완료 첫 사용 자기보고; 날짜 미확인 포함, 설정만 함·제작자/시험 예시는 제외 |
| `E` | `F` 중 알려진 관찰 기간이 기준시점까지 끝났고 요약 동의가 유효한 기록; 연락 미동의로는 제외하지 않음 |
| `R` | `E` 중 고정 관찰 기간에 자발적으로 나중 과제에 사용했다고 보고 |
| `N` | `E` 중 기간 안에 관련 기회가 있었지만 재사용하지 않았다고 명시적으로 보고 |
| `J` | `E` 중 기간 안에 관련 기회가 없었다고 명시적으로 보고 |
| `Q` | `E` 중 분류 요약 동의는 유지하면서 후속 응답을 거절 |
| `U` | `E` 중 미응답·불확실·불완전/충돌 결과·다른 기간만 답한 경우 |
| `C` | 실질적인 후속 결과 응답: `R + N + J` |

적격 기록마다 결과 하나를 두어 `E = R + N + J + Q + U`를 유지합니다.
날짜 미확인과 아직 대상이 아닌 기록은 `E` 밖에서 별도 표시합니다. 첫 사용은
완료했지만 후속 확인은 대기인 상태가 가능합니다. `completed` 같은 진행 상태
자체가 재사용 결과는 아닙니다.

필요하면 `R/E`를 **후속 확인 대상 자발적 보고 중 재사용을 보고한 비율**로
표시하고 `C/E`와 결과 다섯 범주의 개수를 함께 둡니다. 전체 사용자 유지율도,
나머지 모두가 재사용하지 않았다는 증거도 아닙니다. `J`·`Q`·`U`를 `E`에서
몰래 빼지 않습니다. 선택적 기회 한정 진단 `R/(R+N)`은 제외 범위를 밝히고
`R/E`를 대체하지 않습니다. 분모가 0이면 `not estimable(산출 불가)`이며 0%나
100%가 아닙니다. 참여자를 알아볼 수 있는 소수 집계·인용·세부 조합은 공개하지
않습니다.

요약 동의를 철회하면 연결된 기록을 이후 집계와 아직 재계산 가능한 총계에서
뺍니다. 재사용 안 함으로 세지 않습니다. 식별 가능한 철회 내역을 보존하지 않고
집계 대상 정의의 변경을 밝힙니다. 총계 보고에는 이름·답변 링크·원문이 필요
없습니다. 이 두 시간 초안 작업에서 유지율이 나왔다고 주장하지 않습니다.
실제 대상 범위·중복·7일 결과는 미확인입니다.

## Fictional cases / 가상 사례

**All rows and counts in this section are invented to explain the rules. No row
represents a participant. / 이 절의 모든 행과 수치는 규칙 설명용 가상 자료이며
참여자를 나타내지 않습니다.**

Hypothetical cutoff / 가상 기준시점: `2026-10-10T12:00:00Z`.
All examples retain coded-summary permission; contact permission differs.
모두 분류 요약 동의는 유지하며 연락 동의는 서로 다릅니다.

| Fictional code / 가상 코드 | Case label / 사례명 | `D` → `eligible_at` UTC | Meaning / 의미 | Count / 집계 |
| --- | --- | --- | --- | --- |
| EX-A | completed / 완료 | Oct 1 → Oct 9 00:00 | Reports a chosen later task on Oct 5; follow-up answer complete / 10월 5일 본인이 고른 나중 과제 사용을 보고, 후속 응답 완료 | `E`, `C`, `R` |
| EX-B | eligible / 대상 | Oct 2 → Oct 10 00:00 | Window ended; allowed one reply, none sent yet, no outcome / 기간 종료, 답글 한 번 허용, 아직 보내지 않음, 결과 미확인 | `E`, `U` |
| EX-C | pending / 대기 | Oct 8 → Oct 16 00:00 | First use complete, follow-up window not ended / 첫 사용 완료, 후속 관찰 기간 미종료 | In `F`, outside `E` / `F` 포함, `E` 제외 |
| EX-D | no opportunity / 기회 없음 | Oct 1 → Oct 9 00:00 | Completed answer: no relevant task during Oct 2–8 / 응답 완료: 10월 2–8일 관련 과제 없음 | `E`, `C`, `J`; not abandonment / 이탈 아님 |
| EX-E | declined / 거절 | Oct 1 → Oct 9 00:00 | Declines follow-up, retains summary permission; no contact / 후속 응답 거절, 요약 동의 유지, 연락 안 함 | `E`, `Q`; reuse unknown / 재사용 미확인 |
| EX-F | unknown / 미확인 | unknown → unknown | First use reported but date missing; no guessed eligibility / 첫 사용 보고는 있으나 날짜 없음, 대상 추정 안 함 | In `F`, eligibility unknown / `F` 포함, 대상 미확인 |
| EX-G | completed, no reuse / 완료, 재사용 안 함 | Oct 1 → Oct 9 00:00 | Relevant task existed; explicitly reports no reuse in Oct 2–8 / 관련 과제가 있었으며 10월 2–8일 재사용 안 했다고 명시 | `E`, `C`, `N` |

For these **fictional** report records only: `F=7`, `E=5`, `R=1`, `N=1`, `J=1`,
`Q=1`, `U=1`, `C=3`; one pending record and one unknown-date record remain outside
`E`. The illustrative reported-reuse fraction is `1/5` and coverage is `3/5`;
neither is a measured retention result. Even `EX-A` supports only self-reported
later use, not improved answer quality or native application.

이 **가상** 보고 기록에서만 `F=7`, `E=5`, `R=1`, `N=1`, `J=1`, `Q=1`,
`U=1`, `C=3`입니다. 대기 1개와 날짜 미확인 1개는 `E` 밖에 둡니다.
설명용 재사용 보고 비율은 `1/5`, 결과 응답 범위는 `3/5`이며 측정한 유지율은
아닙니다. `EX-A`도 이후 사용 자기보고만 뒷받침하며 답변 품질 개선이나
네이티브 적용을 증명하지 않습니다.

## Sources, evidence and handoff / 출처·근거·인계

Source reads completed by `2026-10-15T05:33:37Z` / 출처 읽기 완료 기준시각:
2026년 10월 15일 서울 14:33:37.
Remote `main` matched the assigned source baseline
`227a528996d93c423851db1d663f9572be534e59` at preparation. The current source is
distinct from the released v1.5.2 claim baseline. No product or installation
state was changed. / 준비 시 원격 `main`은 배정 SHA와 일치했습니다. 현재 소스와
v1.5.2 배포 주장 기준은 구분하며 제품·설치 상태는 바꾸지 않았습니다.

| Source / 출처 | Relevant evidence / 사용한 근거 | Limit / 한계 |
| --- | --- | --- |
| [Issue #113][program], body updated `2026-10-15T02:08:10Z` | Discovery, use and independent recommendations are separate; maintain existing channels / 발견·사용·독립 추천 구분, 기존 경로 유지 | A program record, not a participant dataset / 운영 기록이지 참여자 데이터 아님 |
| [EN/KO worksheet][worksheet], updated `2026-10-14T11:31:33Z` | Synthetic tasks, app-specific paths, voluntary non-sensitive feedback / 합성 과제·앱별 경로·자발적 비민감 피드백 | Authored examples, not observed use or improvement / 작성한 예시이지 사용·개선 관찰 아님 |
| [Claude showcase #2023][showcase], updated `2026-10-15T01:31:22Z` | Existing voluntary app/version/task/check request / 기존 앱·버전·과제·확인 사항 요청 | Body and returned first 30 top-level comment scope had zero nodes; no global absence of feedback inferred / 본문과 첫 30개 최상위 댓글 조회는 0개였으며 전체 피드백 부재를 추론하지 않음 |
| [v1.5.2 English][release-en] and [한국어][release-ko] | First-use/setup/read/application/usefulness boundaries / 첫 사용·설정·읽기·적용·유용성 경계 | Release documentation is not a new live observation / 배포 문서는 새 실사용 관찰 아님 |
| [SECURITY.md][security] and [contributor protocol][agents] at the assigned SHA | No private material, credentials, raw conversation retention or hidden reasoning capture / 사적 자료·자격증명·원문 대화 보관·숨겨진 추론 수집 금지 | Platform retention remains separate / 플랫폼 보관 정책은 별개 |

**Decision / 결정:** retain the existing public request and prepare optional,
manual follow-up copy. **Missing / 부족한 근거:** real consented first-use dates,
matured cohorts and later-use reports. **Revisit / 재검토 조건:** actual contributor
preferences, an actionable setup problem, unclear date interpretation or inability
to honor deletion/contact limits. No conversion, retention or improvement target
is set without a measured baseline.

**결정:** 기존 공개 요청을 유지하고 선택적 수동 후속 문안만 준비합니다.
**부족한 근거:** 실제 동의한 첫 사용일·관찰 기간이 끝난 집계 대상·이후 사용
보고입니다. **재검토 조건:** 실제 참여자의 선택·조치 가능한 설정 문제·날짜
해석의 모호함·삭제/연락 한계 이행 불가입니다. 측정 기준선 없이 전환율·유지율·
개선 목표를 정하지 않습니다.

Implementation status: document draft only. Integrated-candidate checks and an
actual consented longitudinal observation have not run. S091/S001 may select this
owned document for integration; source/release gates belong to the frozen
candidate workflow. Owner adoption, any public edit and any future permitted
manual reply remain outside this session's execution.

구현 상태는 문서 초안만입니다. 통합 후보 검사와 동의한 실제 사람의 시간 경과
관찰은 실행하지 않았습니다. S091/S001이 소유 문서를 통합 대상으로 선택할 수
있으며, 소스·배포 검사는 동결 후보 절차에서 수행합니다. 소유자의 채택·공개
수정·향후 허용된 수동 답글 실행은 이 세션의 실행 범위 밖입니다.

[worksheet]: https://gist.github.com/ParkerHwang/d814da73fb445f7123eb5d637e912cd5
[showcase]: https://github.com/anthropics/skills/discussions/2023
[program]: https://github.com/ParkerHwang/OpenSocrates/issues/113
[release-en]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.md
[release-ko]: https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.2/docs/v1.5.2.ko.md
[security]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/SECURITY.md
[agents]: https://github.com/ParkerHwang/OpenSocrates/blob/227a528996d93c423851db1d663f9572be534e59/AGENTS.md
