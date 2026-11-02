# Codex single-host pilot: preregistration draft / Codex 단일 호스트 파일럿 사전등록 초안

**State: DRAFT. No actor calls or results are reported here.** Writing, committing,
or integrating this document does not freeze the study. S001 selects the integrated
candidate and records protocol approval; S078 alone may execute actors after the
pre-outcome freeze and resource/isolation checks below. Unresolved values remain
`null` with a reason rather than being inferred from this authoring chat.

**상태: DRAFT. 이 문서는 actor 호출이나 결과를 보고하지 않는다.** 문서 작성·커밋·통합은
동결이 아니다. S001이 통합 후보와 프로토콜을 선택하고, 결과 전 동결 및 자원·격리 확인
이후 S078만 actor를 실행한다. 미확정 값은 이유와 함께 `null`로 유지한다.

## 1. Purpose, questions, and limits / 목적·질문·한계

This first pilot compares the current stabilization candidate on **one exact Codex
host surface** using public synthetic tasks. The predeclared questions are whether
task completion and critical-error patterns differ among `plain`, `general-check`,
and `native-opensocrates`, and what time/token costs and delivery observations
accompany those outcomes. The nondirectional working hypothesis is that outcomes
may differ; equality, ties, native omissions, and native regressions are admissible
results. No direction, minimum effect, success-rate target, statistical-power claim,
or release prerequisite is asserted.

The native-versus-plain contrast concerns the installed package workflow as a
whole. Native-versus-general-check asks whether that workflow differs from a
generic checking instruction. These contrasts do not isolate one method, prove a
mechanism, or establish benefits on other models, hosts, languages, or real work.
Three repetitions of the same case are stochastic observations, not three new task
families or proof of independent samples. No result exists at drafting time.

첫 파일럿은 공개 합성 과제로 **정확히 하나의 Codex 호스트 표면**에서 현재 안정화 후보를
비교한다. 세 조건의 과제 완수·중대 오류 양상 차이, 시간·토큰 비용과 전달 관찰을 묻는다.
차이의 방향은 가정하지 않으며 동률·차이 없음·native 누락·native 회귀도 결과로 보존한다.
최소 효과·성공률 목표·검정력·출시 전제조건을 추가하지 않는다. 비교 대상은 설치된 전체
워크플로이며 특정 방법의 기전이나 다른 모델·호스트·언어·실제 업무의 효과를 입증하지
않는다. 같은 사례의 반복을 새 과제나 독립 표본으로 부풀리지 않는다. 현재 결과는 없다.

## 2. Source identity and historical evidence / 소스 식별·과거 근거

The assigned source baseline is main
`227a528996d93c423851db1d663f9572be534e59`. A read-only
`git ls-remote origin refs/heads/main` returned that exact SHA on 2026-10-15 UTC
during preparation. This is a preparation-time observation, not a promise that
remote main or the final candidate will remain unchanged. The final integrated
candidate SHA and treatment package hashes are **unresolved**. S001/S091 must
reconcile any later source difference before freeze; never relabel baseline
observations as evidence for changed bytes.

Historical design references, not data in this study:

- [v1.5 Mac report](../v1.5-macos/REPORT.md) and
  [observations](../v1.5-macos/observations.json): bounded synthetic observations,
  seven requests, no same-model baseline or independent judge; package loading and
  public output quality were separate evidence states.
- [v1.3 protocol](../v1.3/release-guided-20260908/PROTOCOL.md) and
  [freeze](../v1.3/release-guided-20260908/freeze.json): examples of pre-outcome
  source/input identification and retaining failures. Their model, 24-call design,
  timing, upfront-content controls, hashes, and results are not this study's values.
- [Issue #114](https://github.com/ParkerHwang/OpenSocrates/issues/114): one historical
  numeric counterexample with manually supplied content, not native activation or
  a measured current failure rate. [Issue #124](https://github.com/ParkerHwang/OpenSocrates/issues/124)
  separates installation/trust from observed discovery and application.

배정 기준과 준비 시 읽은 원격 main은 위 SHA로 일치했다. 최종 통합 SHA·설치 패키지
해시는 미확정이며 이후 차이는 S001/S091이 동결 전에 조정한다. 과거 Mac 관찰, v1.3
동결 예시와 이슈는 설계 참고 자료다. 과거 호출·모델·제한·해시·결과를 이번 실험 값이나
현재 후보의 효과·실패율로 승격하지 않는다. 수동 정본 주입과 native 설치도 구분한다.

## 3. Fixed sample and single-turn unit / 고정 표본·단일 회차 단위

The entire basic actor budget is **3 families × 2 locales × 3 arms × 3 repeats =
54 single-turn actor responses**. There is one case per family and locale: six
case inputs, each used unchanged in nine cells. Each arm has 18 assigned cells;
each family has 18; each locale has 27. Repeats are `1`, `2`, and `3`.

| Family / 가족 | Locales / 언어 | Public task focus / 공개 과제 초점 |
| --- | --- | --- |
| `email-agreement` | `en`, `ko` | Preserve supported agreement and uncertainty without inventing the author's commitments / 합의·미확인을 보존하고 작성자 약속을 만들지 않음 |
| `changed-recommendation` | `en`, `ko` | Update a recommendation when supplied evidence changes, retaining still-valid constraints / 바뀐 근거를 반영하고 유효한 제약을 유지함 |
| `price-profit` | `en`, `ko` | Use the supplied quantities, units, profit equation and boundary correctly / 수량·단위·이익 식·경계를 정확히 다룸 |

Each cell is a fresh actor context with exactly one submitted task and at most one
actor final answer. All necessary synthetic initial facts and changed facts must
be included in that one input or its frozen public fixture files. A changed-fact
case must not become a conversation requiring an earlier actor answer. Tool steps
inside an actor turn do not authorize follow-up prompts, repair answers, hidden
selector-model calls, or extra actors. Asking a clarification that prevents the
required deliverable is scored against the frozen completion rule; no second user
turn is supplied. The 100 authoring chats are not actors or control observations.

Case content, required outcomes, critical-error labels, and deterministic numeric
facts must be finalized before freeze by their owners, not learned from actor
answers. EN/KO versions must preserve facts, difficulty, authority, and required
outputs; they need not have equal character/token counts. No task prompt may teach
a method ID, invocation command, package path, or instruction to use OpenSocrates.
Judges' rubrics and answer keys are never exposed to actors.

전체 기본 예산은 **3가족 × 영한 × 3조건 × 3반복 = 단일 회차 actor 답변 54개**다.
여섯 사례를 각 아홉 셀에서 그대로 쓴다. 셀마다 새 문맥에서 한 번 요청하고 최종 답변은
최대 하나다. 변경 전후 근거도 한 입력 또는 동결된 합성 파일 안에 제공하며 앞선 actor
답변이나 후속 질문을 전제로 하지 않는다. 내부 도구 사용은 추가 답변·수정 호출·모델
선택기 호출을 허가하지 않는다. 영한 사례는 사실·난도·권한·완료 조건을 맞춘다. 과제에
방법 ID·호출 명령·패키지 경로·OpenSocrates 사용 지시를 미리 넣지 않고 채점 기준도
노출하지 않는다. 100개 작성 채팅은 실험 표본이 아니다.

## 4. Arms and fair comparison / 조건·비교 공정성

| Arm / 조건 | Treatment contract / 처리 계약 |
| --- | --- |
| `plain` | Frozen common task and common host instructions, with no OpenSocrates installation/discovery content and no added checking instruction / 공통 과제·호스트 지시만 제공 |
| `general-check` | Same plugin-free setup plus the fixed locale-matched generic checking instruction in `arms.json`; no canonical method text / plain과 같은 환경에 사전 고정된 일반 점검 지시만 추가 |
| `native-opensocrates` | Same task with the exact candidate package installed and naturally discoverable through the selected host's supported path; no manual canonical/controller injection / 같은 과제에 정확한 후보를 설치하고 지원 경로의 자연스러운 발견을 관찰 |

Use the same requested model, effort, service tier, tool policy, permissions,
timeouts, token/step budgets, task facts, and permitted external effects across
arms. Only the frozen treatment and its necessary installed package access differ.
All tasks produce drafts or local synthetic outputs; sending, purchasing,
publishing, deployment, and unrelated workspace/network access are out of scope.
Tool availability is held constant; actual use may differ and must not be forced
to look identical. Native guide reading may consume extra input/context/time;
report observed full costs rather than equalizing away treatment overhead.

Never add compensating model calls, guided rescue messages, or full canonical
content to a missing native discovery. Such content would be a manual-injection
condition and is outside these three arms. A legitimate empty method selection
remains valid; do not force methods onto mechanical substeps or require an
application receipt as an answer-completion gate. Native nondiscovery is retained
in the assigned native arm, not recoded as plain or excluded after the fact.

모델·추론 강도·tier·도구 정책·권한·시간·토큰/단계 한도·과제 사실은 조건 간 같게 고정한다.
차이는 정해진 처리와 설치 패키지 접근이다. 실제 도구 사용은 달라도 되며 native의 추가
문맥·시간 비용도 보고한다. 외부 발송·구매·게시·배포는 하지 않는다. native 발견이 없다고
수동 주입·구제 메시지·추가 모델 호출로 보완하거나 plain으로 재분류하지 않는다. 빈 선택과
기계 작업 우회는 유효하며, 존재하지 않는 적용 영수증을 완료 문턱으로 만들지 않는다.

## 5. Identity, isolation, and execution order / 식별·격리·실행 순서

Freeze a `source_identity` record compatible with launch `interfaces-v1.json`:

| Field(s) / 필드 | Draft value and resolution rule / 초안 값·확정 규칙 |
| --- | --- |
| `repository` | `ParkerHwang/OpenSocrates` |
| `source_sha` | `null`: S001 has not selected the integrated candidate / 통합 후보 미선택 |
| `product_version`, `content_revision` | `null`: read from exact selected source/package / 선택된 소스·패키지에서 확인 |
| `host`, `platform` | `null`: choose one Codex surface, exact version, OS and architecture / 표면 하나·정확한 버전·OS·아키텍처 확정 |
| `model_requested`, `effort` | `null`: S078 records the common explicit request before freeze / 공통 요청값 미확정 |
| `model_observed` | `null`: independently reported backend identity unavailable at drafting / 백엔드 독립 식별 자료 없음 |
| `service_tier_requested` | `priority`: program Fast request; preserve across arms / 프로그램 Fast 요청 |
| `service_tier_observed` | `null`: configured/requested tier does not prove server processing / 서버 처리 tier 미관측 |

Unknown backend identity or observed tier remains `null` with a reason; it does not
permit quietly substituting another requested model or tier. Record any observable
change by affected cell and preserve the original assignment. Model/host drift,
unexpected context contamination, or an unplanned tool-policy change triggers the
pause rule below rather than a pooled same-model claim.

S078 must have a current S001 resource lease for the chosen authenticated host and
execution slot. Before actor calls, record privacy-safe isolation evidence:
fresh per-cell contexts; no prior answers; plugin-free plain/general-check surfaces;
exact candidate native installation; no inherited unrelated skills, instructions,
fixture answers, user history, or workspace content. Use only supported separation
that preserves existing host trust and permissions. Do not copy live authentication,
HOME contents, account configuration, or keychain material to fabricate isolation.
If separation cannot be established, mark isolation `BLOCKED` and do not substitute
an installed/shared authoring chat. Isolation evidence must not retain raw logs.

Freeze all 54 cell IDs and their order before outcomes. `case_id` is
`family-locale`; `cell_id` is `case_id-arm-r1` through `-r3`; `order_index` is 1–54.
Use a recorded assignment seed and deterministic ordering algorithm in the
assignment ledger to interleave conditions; freeze serial execution or an explicit
concurrency/resource schedule. The seed controls assignment order, not backend
determinism. Do not adapt order to early results or run favorable cells first.

실제 요청 모델·호스트·예산은 동결 전에 채우고 백엔드·서버 tier 미관측은 이유와 함께
`null`로 남긴다. S078은 유효한 자원 임대와 새 문맥·조건 분리·정확한 설치를 확인해야
한다. 활성 인증·HOME·계정 설정·keychain을 복사해 격리를 만들지 않는다. 분리할 수
없으면 `BLOCKED`다. 54개 셀·순서·seed·알고리즘·직렬/동시 실행 일정을 결과 전에 고정하고
초기 결과를 보고 순서를 바꾸지 않는다. seed는 백엔드 결정성을 보장하지 않는다.

## 6. Pre-outcome freeze contract / 결과 전 동결 계약

The launch v1 contract remains the baseline. S041's freeze manifest must enumerate
the exact protocol, six locale task payloads and source fixtures, arm instructions,
rubric/answer keys, analysis plan, privacy policy, budget, assignment ledger,
execution driver/configuration, and native package inventory/archive used. Include
repo-relative paths and SHA-256 values for immutable inputs; identify externally
stored safe artifacts by their immutable content hash as well. A filename or
author's `READY` status alone is not a frozen input. Do not include credentials or
raw host configuration in the manifest. Record final manifest hash in the safe run
record rather than trying to hash the manifest into itself.

Freeze states are `DRAFT`, `FROZEN`, and `INVALIDATED`. `FROZEN` requires the exact
candidate SHA, complete input inventory/hashes, `isolation_state: VERIFIED`,
`quota: 54`, frozen UTC timestamp, and S001's recorded selection in `approved_by`.
This is program selection, not a fabricated human signature. It also requires
resolved common requested model/host/policy/limits, the fixed order, safe capture
path, and a valid resource lease. Observed backend/model and tier unknowns may
remain explicit unknowns; required executable choices may not.

S078 records the frozen manifest identity before the first actor dispatch and
checks that the actor uses those bytes. If artifacts change before the first call,
invalidate and refreeze with a dated reason. After any dispatch, never overwrite
the original freeze, task, result, or assignment to rescue the study. Pause; retain
all consumed calls, statuses, and deviations under the original run identity.
Changed treatments/inputs require a separately declared follow-up and fresh
authorization/budget; this protocol grants no additional actor calls.

v1 계약에 따라 프로토콜·여섯 언어별 과제·원자료·조건 지시·채점 정답·분석·개인정보·예산·
배정표·실행 코드/설정·native 패키지의 정확한 경로·해시를 동결한다. `FROZEN`은 후보 SHA,
완전한 목록, 격리 `VERIFIED`, 예산 54, UTC 시각과 S001의 기록을 요구한다. 파일명이나
준비 완료 상태만으로 동결하지 않는다. 호출 전 변경은 사유와 함께 무효화 후 재동결한다.
호출 뒤 변경은 원본을 보존하고 중단하며 별도 후속 연구로 다룬다. 추가 예산은 없다.

## 7. Stops, attempts, and denominators / 중단·시도·분모

Freeze the per-cell wall timeout, token/output limit, tool/step limit, concurrency,
and study stop time before execution; their numeric values are **unresolved** in
this draft. The program's common deadline is 2026-10-15 07:16:58.780728 UTC
(16:16:58.780728 Asia/Seoul); later chat creation does not extend it. Do not dispatch
work whose frozen execution/cleanup allowance exceeds the remaining authorized
window. Deadline exhaustion yields an incomplete run, not a claim of 54 outcomes.

- `NOT_RUN`: assigned but not dispatched. `BLOCKED`: not dispatched because a
  documented prerequisite/resource is unavailable. Both remain visible in the
  fixed 54-cell ledger, with a safe reason.
- `STARTED`: dispatch initiated. A confirmed or ambiguous dispatch consumes that
  cell's one attempt. If acceptance by the service is unknown, retain that
  uncertainty and do not resend under the same cell or invent zero cost.
- `COMPLETED`: a final public answer was obtained; this status is not a quality
  pass. `FAILED`: dispatch/runtime/error or no usable final answer. `TIMEOUT`:
  frozen wall deadline expired. Preserve any permitted public partial output
  separately identified as partial, never as a replacement final answer.
- No quality reruns, infrastructure replacement calls, favorable reseeding,
  timeout retries, post-score prompt edits, or exclusion of errors. A native
  discovery omission with a final answer can be `COMPLETED` and still fail a task
  criterion. Service refusal after dispatch is an attempted outcome.
- Report planned coverage as all 54 assigned cells and attempted coverage as
  every dispatched cell, including failures/timeouts/interruptions. For the
  attempted pass fraction, failures/timeouts without a passing final answer are
  non-passes. Show `NOT_RUN` and `BLOCKED` separately; never silently shrink the
  denominator to successful answers. Do not silently convert unknown scores to
  successes; show missing adjudication and bounds if scores are unresolved.

Pause new dispatches for quota exhaustion, isolation/identity drift, changed frozen
inputs, lost resource lease, unsafe retention, host failure, or the common deadline.
Complete safe bounded cleanup without changing unrelated host state. Record safe
failure categories rather than raw error strings. Good or bad emerging quality is
not an early-stop rule. Report all already-attempted outcomes and remaining cells.
S076's separately governed finite observations are not this study's cells or
replacement budget. Other authoring sessions have zero experimental model calls.

셀별 시간·토큰/출력·도구/단계·동시성·중단 시각은 미확정이며 실행 전에 고정한다. 공통
기한은 한국 시각 2026-10-15 16:16:58.780728이다. 호출 수락 여부가 불명확해도 재전송하지
않는다. 호출된 실패·시간초과·중단은 시도 분모에 남기고 미실행·차단도 54셀 원장에 별도
표시한다. 좋은 결과만 남기는 재시도·분모 제외·조기 종료는 금지한다. 격리·식별·동결·자원·
개인정보 문제가 생기거나 기한/예산이 끝나면 새 호출을 멈추고 안전한 상태로 인계한다.
S076 관찰이나 다른 작성 채팅을 실험 셀 또는 대체 예산으로 쓰지 않는다.

## 8. Outcomes, scoring, and reporting / 결과·채점·보고

The primary public rule is **required deliverable complete AND no predeclared
critical error**, scored per cell against `scoring-rubric.json`. Report completion,
each critical-error label, and the joint pass separately, by arm, family, and
locale with exact numerators/denominators. The rubric must settle ambiguous and
unscorable cases before freeze. Numeric answer keys must include units, equations,
rounding/inequality boundaries, and permitted equivalences rather than matching a
preferred wording. No actor answer can redefine the key.

Use S040's frozen analysis plan for the three pairwise arm contrasts and case-level
tables. This pilot is descriptive: preserve all ties, harms, failures, and missing
data. No post-outcome endpoint selection, significance threshold, superiority
claim, success target, or language pooling that hides opposite results is allowed.
If the full 54 cells are not obtained, label the study incomplete and report the
observed subset alongside planned coverage; do not call it the completed design.

Prepare blinded judge packets containing the public task/facts, frozen rubric, and
public final answer with arm labels and package identifiers removed where safe.
Keep the blind-ID mapping separate; fix scores before revealing arm mapping. Never
alter substantive answer content to improve scores or disguise failure. Document
possible unblinding from wording/attribution, actual judge provenance, disagreements,
and the predeclared adjudication rule. No additional model-judge calls are
authorized. If independent human evaluation is unavailable, state `unavailable`;
author/self-review or deterministic rubric assistance is not independent judgment.

Secondary descriptions use observed elapsed time and full interaction token/cost
counts only when the host supplies them. Missing usage/cache/price information is
`null` plus a reason, not zero or a guessed bill. Count treatment/tool overhead and
failed attempts where observable. Report known measured subtotals separately from
unknown costs. Do not truncate answers or omit mandatory text to improve metrics.

Keep `entry_emitted`, `canonical_full_read`, `application_evidence`, and usefulness
separate. Installation/trust is configuration; emission is delivery; a supported
read observation concerns exact content; an actor assertion is not native proof.
Absent permitted observation is `null`, not `false`. `application_evidence` remains
`unverified` unless an actually supported evidence type warrants a narrower claim.
A footer, a read, or a passing answer does not certify method application or causal
improvement. Missing application proof does not block a completed user task.

셀별 기본 통과 규칙은 **요구 산출물 완성 AND 사전 정의된 중대 오류 없음**이다. 완수·오류·
통과를 조건·가족·언어별 정확한 분자/분모로 보고한다. 수치 정답의 단위·식·반올림·경계와
허용 동치도 결과 전에 고정한다. S040의 분석 계획으로 세 쌍 비교를 기술적으로 보고하고
사후 지표 선택·우월성 주장·반대 결과를 숨기는 합산을 하지 않는다. 블라인드 매핑은 점수
확정 후 공개하며 평가자 출처·불일치·눈가림 한계를 적는다. 독립 평가자 부재는
`unavailable`이며 자체 검토를 독립 평가로 부르지 않는다. 추가 모델 채점 예산은 없다.
비용·토큰·시간 미관측은 0이 아닌 `null`이다. 설치·전달·읽기·적용·유용성을 분리하고
native 적용 증명을 만들지 않는다. 관측 불가는 거짓을 뜻하지 않는다.

## 9. Public retention / 공개·보존 범위

Retain only newly authored public synthetic inputs/source facts, frozen public
instructions and rubrics, complete permitted public final answers, identities and
content hashes, cell statuses, safe failure categories, fixed scores, and actually
observed aggregate usage/timing. The frozen privacy policy must identify who may
publish these artifacts and the retention/deletion policy; drafting is not external
publication authorization. A safe result record follows launch v1 result fields.

Do not collect or preserve original user prompts/conversations, raw host event
streams/transcripts/logs, hidden reasoning, screenshots, credentials, account IDs,
authentication copies, or unrelated workspace content. A public synthetic task
input is authored test material, not permission to retain a host transcript. Use a
minimal supported safe capture path; if it cannot produce allowed fields without
prohibited retention, block that execution path. Do not fake read/application
receipts. Ordinary host storage remains governed by the host's policy and is not
claimed as erased by this protocol.

새 공개 합성 입력·공개 지시/채점표·허용된 최종 답변·해시·상태·안전한 오류 분류·점수·실제
관측 비용/시간만 제한적으로 보존한다. 공개 주체와 보존·삭제 정책은 동결 전에 확정하며
문서 작성은 외부 게시 허가가 아니다. 개인 원문·대화·raw host 로그/전사·숨은 추론·스크린샷·
인증·계정 식별·무관한 작업공간 자료는 수집·보존하지 않는다. 안전한 최소 수집을 지원하지
못하면 해당 실행 경로를 차단한다. 호스트 자체 보존 정책을 이 문서로 삭제했다고 주장하지 않는다.

## 10. Items S078 must resolve before dispatch / S078 실행 전 미확정 목록

These are study-execution requirements, not product-release gates. S078 consumes
the selected artifacts after S001/S091 integration; S031 changes only this protocol.
Resolve file/path/schema differences with a recorded v1-compatible adapter or a
new pre-outcome revision, never silent reinterpretation.

| Required item / 필요 항목 | Owner/input / 담당·입력 | Draft state / 초안 상태 |
| --- | --- | --- |
| Exact integrated source SHA; reconcile remote/base difference / 정확한 후보 SHA·기준 차이 조정 | S001, S091 | `null` |
| Product/content identity and exact native package hashes / 제품·콘텐츠·패키지 식별 | S001, S078 | `null` |
| Six finalized EN/KO payloads and public source facts / 확정된 영한 여섯 과제 | S032–S034, `fixtures/email-agreement.json`, `fixtures/changed-recommendation.json`, `fixtures/price-profit.json` | Not yet frozen / 미동결 |
| Common instructions and locale generic-check text; only permitted arm differences / 공통·조건별 지시 | S035, `arms.json` | Not yet frozen / 미동결 |
| Observable completion/error criteria, numeric keys, ambiguity and adjudication rules / 완료·오류·정답·이견 처리 | S036, `scoring-rubric.json` | Not yet frozen / 미동결 |
| Actual judge provenance or explicit unavailability; blind packet/mapping access / 평가자 출처·부재·블라인드 접근 | S078 with S047/S048 tooling | `null`; no model-judge budget / 모델 채점 예산 없음 |
| Safe capture, public scope, publication owner, retention/deletion policy / 안전한 수집·공개·보존 정책 | S038, `PRIVACY.md` | Not yet frozen / 미동결 |
| Fixed 54-cell allocation, per-cell limits and ledger accounting / 54셀·한도·집계 | S039, `BUDGET.json`; S043 ledger | Limits/order unresolved / 한도·순서 미확정 |
| Pairwise analysis, missing-score treatment and descriptive report / 쌍 비교·미채점 처리·보고 | S040, `ANALYSIS_PLAN.md` | Not yet frozen / 미동결 |
| Exact single Codex surface/version/platform and requested model/effort/tier / 단일 호스트·요청 모델 | S078 | `null`, except requested tier `priority` |
| Supported isolation, plugin-free controls, exact native install, current lease / 격리·조건 분리·설치·자원 | S078, S042 preflight, S001 lease | `UNVERIFIED` |
| Assignment seed/algorithm/order, concurrency and deadline-safe execution plan / seed·순서·동시성·실행 일정 | S078, S043 | `null` |
| Driver/config hashes, immutable input manifest, frozen timestamp, S001 selection / 실행 식별·목록·시각·선택 | S041, S001, S078 | `DRAFT`; no approval claimed / 승인 미주장 |

The execution decision may change only when these items are resolved against the
selected candidate and safe resources. The effect question remains untested until
the frozen actors are actually attempted and public outcomes are scored. An
unknown backend identity, absent independent judge, or incomplete run limits the
report; none may be concealed by declaring the document itself verified or frozen.

위 항목은 제품 출시 문턱이 아닌 이 연구의 실행 조건이다. 선택 후보·안전한 자원에 맞춰
해결해야 실행할 수 있다. 효과 질문은 실제 호출과 공개 결과 채점 전까지 미검증이다.
백엔드 미식별·독립 평가자 부재·미완료 표본은 한계로 남기며 문서 작성만으로 검증·동결을
선언하지 않는다.
