# Exploratory pilot analysis and next-action plan / 탐색 파일럿 분석·후속 판단

Plan version: `1.0-draft`. Owner: S040. Evidence level: **design only; no actor
calls, scores, quality comparison, or verification performed by this session**.
This file becomes preregistered only when S001 freezes its exact bytes with the
protocol, cases, treatments, rubric, budget and assignment ledger **before any
actor response**. A commit alone is not that freeze.

문서 상태는 설계 초안이다. 결과를 보기 전에 정확한 입력·규칙 전체를 동결해야
사전등록이 된다. 작성·커밋은 실험 실행이나 효과 검증을 뜻하지 않는다.

## 1. Question, source and claim boundary / 질문·기준·주장 한계

The question is whether, on six newly authored synthetic EN/KO cases, the frozen
native OpenSocrates condition shows a useful descriptive signal relative to plain
answers and a general-check instruction, and which delivery, task or scoring
problem deserves the next bounded investigation. The decision is about the next
investigation, not efficacy certification, market adoption or release approval.

이번 질문은 여섯 합성 사례에서 관찰한 차이와 다음 조사 대상을 정하는 것이다.
효과 우월성, 시장 채택, 출시 승인을 입증하는 연구가 아니다.

- Assigned source: `main` at `227a528996d93c423851db1d663f9572be534e59`.
  A read-only remote `refs/heads/main` lookup during preparation on 2026-10-15
  returned this same SHA. This is a dated observation, not a promise about future
  main. S001/S091 must record any later difference rather than silently rebasing
  this study's evidence identity.
- The eventual freeze must identify its own exact candidate SHA, product/content
  revisions, package/treatment hashes, host/platform, requested model/effort/tier
  and actually observed identity. Use launch-v1 identity fields; unavailable
  observed values are `null` with a reason. Configured `priority` does not prove
  the server processing tier; a requested model name does not prove the backend.
- Three repeats per case and arm are exploratory observations, not three
  independent populations. They do not establish statistical significance,
  equivalence, non-inferiority, generalization or reliability for all 48 methods.
  These 100 authoring chats are not a control group or experimental responses.
- This plan adds no v1.6 release gate. A pilot finding may open a scoped issue;
  release decisions retain their separately documented requirements. No missing
  native application receipt becomes an added completion or release condition.

기준 SHA와 이후 동결 SHA를 구별한다. 요청 모델·Fast 설정을 관측 모델·서버 tier로
추정하지 않는다. 3반복은 유의성·동등성·일반화의 충분한 근거가 아니며, 100개 작성
채팅은 대조군이 아니다. 이 계획은 v1.6 출시 문턱을 추가하지 않는다.

Historical sources constrain interpretation, not the current outcome denominator:

| Source | Relevant limit carried into this plan |
| --- | --- |
| [Mac observations](../v1.5-macos/REPORT.md) | Seven historical requests, no same-model baseline or independent judge; retained regressions and installation observations do not prove efficacy. |
| [v1.3 protocol](../v1.3/release-guided-20260908/PROTOCOL.md) | Its upfront-content controls were transformed controls, distinct from installed delivery; preserve all attempts, exact identities and separately frozen repairs. Its former qualification rules are not imported as new release gates. |
| [Windows report](../v1.5-windows/REPORT.md) | No request on an unavailable UI surface is a measurement blocker, not a demonstrated discovery failure. Offline success cannot qualify live delivery. |
| [v1.2 adjudication](../../docs/v1.2-adjudication-report.md) | AI-assisted development labels are not independent human gold, held-out results or answer-quality evidence; unavailable historical packets stay unavailable. |
| [Issue #114](https://github.com/ParkerHwang/OpenSocrates/issues/114) | One manually injected-content numeric counterexample has unconfirmed mechanism/reproducibility and unobserved backend identity; it is not a current native regression estimate. |
| [Issue #124](https://github.com/ParkerHwang/OpenSocrates/issues/124) | An observed omission symptom does not identify its cause or frequency. Configuration is not execution evidence. |

과거 관찰은 이번 시도의 분모나 현재 버전의 검증 결과에 합치지 않는다. 과거 실패와
불확실성은 그대로 보존하며 비교 설계의 주의점으로만 사용한다.

## 2. Frozen design and authority / 동결 설계·권한

The launch-v1 contract fixes:

| Dimension | Values | Assigned cells |
| --- | --- | ---: |
| Family | `email-agreement`, `changed-recommendation`, `price-profit` | 18 per family |
| Locale | `en`, `ko` | 27 per locale |
| Arm | `plain`, `general-check`, `native-opensocrates` | 18 per arm |
| Repeat | `1`, `2`, `3` | 3 per family × locale × arm |
| Total | 3 families × 2 locales × 3 arms × 3 repeats | **54 single-turn actor responses** |

Only S078 may execute this base experiment after the required resource lease,
isolation approval, budget and freeze are established. S040 makes zero model/API
experiment calls. S076's separately bounded native-recovery observations are not
extra pilot repetitions and never enter these 54 cells. There is no quality
rerun or unbudgeted infrastructure retry. Dispatch uncertainty consumes a
reservation conservatively under S039's budget contract, not a free replacement.

기본 예산은 actor 단일턴 답변 54개 전체다. 실행 권한은 승인·격리·동결을 확인한
S078에만 있다. S076 진단이나 작성 채팅을 기본 실험에 편입하지 않는다. 실패와
불확실한 전송을 유리한 재시도로 대체하지 않는다.

Before outcomes, S031's `PROTOCOL.md`, S036's `scoring-rubric.json`/key binding,
S039's `BUDGET.json` and S043's assignment ledger must agree with this plan.
Freeze the randomized order
and seed, permitted tool access, timeout/measurement boundary, input hashes,
judging provenance and stop rules. Record the seed as ordering reproducibility,
not model determinism. No live drafting, threshold selection or rubric repair
after seeing answers. Unresolved inputs prevent actor dispatch; they do not
prevent this design draft from being delivered to the integrator.

`native-opensocrates` means the frozen native installed path. Manually supplying
canonical text is a different treatment; never relabel it as native or silently
substitute it for a blocked native arm. Any proposed manual-content study needs
its own protocol version, freeze and separately authorized finite budget.

정본을 수동 주입한 조건은 네이티브 설치 조건과 다르다. 네이티브가 막혔다고
수동 조건으로 교체하지 않는다. 순서·도구·시간제한·평가 기준도 결과 전에 동결한다.

## 3. Denominators and cell disposition / 분모·시도 상태

One immutable `cell_id` identifies one assigned response, not a conversation,
method or judge opinion. Keep a ledger row for all 54 cells. Preserve
`order_index`, actual dispatch order/time, status, safe failure reason and any
deviation. Never sort away a failure or replace a response with a later answer.

For every arm and family × locale × arm stratum report:

- `S`: assigned cells (18 per arm; 3 per stratum; 54 overall).
- `A`: attempted cells, including every confirmed dispatch and any dispatch that
  cannot safely be ruled out. A failed, timed-out, interrupted or blocked-after-
  dispatch cell remains attempted. Terminal status alone cannot erase dispatch.
- `Z = S - A`: not attempted, with `NOT_RUN` and pre-dispatch `BLOCKED` counts
  and reasons shown separately. Stop-time `STARTED` cells remain unresolved
  attempts, never disappear from the ledger.
- `P`: observed rubric passes on eligible `COMPLETED` final answers. Pass requires
  a completed required deliverable
  **and** adjudicated absence of every predeclared critical error. Unscored or
  unresolved answers are not passes. A pass does not certify method application.
- `F`: eligible `COMPLETED` answers with S036 verdict `fail`. An established
  decisive failure remains fail even when another dimension is unknown.
  `U`: other attempts, split into completed `unscorable`, completed score-pending,
  and execution-unavailable/not-final records whose quality verdict is `null`. Thus
  `A = P + F + U`; report disposition counts separately from scoring counts.
- `C`: attempts with at least one observed predeclared critical error; show each
  error label and overlaps. Multiple errors in one answer do not create multiple
  attempted cells. Unknown error status is reported separately from zero errors.

Display `P/A` (observed successful attempts), `P/S` (observed successes across
the fixed assignment) and coverage `A/S`, always with integer counts. When
`A=0`, `P/A` is unavailable, not zero. Unknown outcomes stay in the attempted
denominator but are not asserted to be incorrect answers. Report `C/A` with
error-assessment coverage; missing output does not prove absence of an error.
Completed-answer-only scores may be secondary, clearly marked as selected data.
Keep task-completion `true`/`false`/`null` counts separate from these verdicts.
For unresolved completed scores, additionally show logical adjudication bounds
`P/A` to `(P + U_score)/A`, where `U_score` is only the completed, potentially
passing, unresolved subset of `U`. A missing/non-final execution output is not a
potential observed pass under S036. These are missing-score bounds, not confidence
intervals or population reliability estimates; `A=0` remains unavailable.

모든 배정 셀과 실제 전송 순서를 남긴다. 실패·시간초과·중단·전송 후 차단은 시도
분모에서 빼지 않는다. 미실행·전송 전 차단은 별도 표시하고 54개 배정 대비 범위도
함께 보고한다. unknown을 정답·오답 또는 중대오류 없음으로 바꾸지 않는다.

An answer that violates the frozen task format, authority or numeric key can be
a rubric non-pass even when it sounds fluent. Apply only S036's frozen critical
labels; do not invent a new disqualifier after unblinding. Keep disputed scores,
original labels and adjudication amendments linked without overwriting history.

## 4. Comparisons and qualitative findings / 비교·정성 실패

Report the six case strata first, then family, locale and arm totals. Show all
three repetitions, including order/status, rather than only an average. Report
the two primary descriptive contrasts separately: native versus plain and native
versus general-check. General-check versus plain supplies context for whether a
generic reminder may explain a signal. Never combine both controls into one arm.

For strata with all three attempts adjudicated in both compared arms, show the
pass-count difference, critical-error counts and corresponding percentage-point
difference. For incomplete strata, show each denominator and unknown count;
do not present a complete-case difference as the assigned-stratum result.
Repeat numbers are scheduling identifiers, not matched random seeds or paired
independent subjects. Totals must not hide EN/KO or family reversals.

여섯 사례 층과 3반복을 먼저 제시한다. native 대 plain, native 대 general-check를
따로 비교한다. 반복 번호를 동일 난수·독립 피험자 쌍으로 해석하지 않으며, 총점으로
언어·과제별 반대 방향의 결과를 가리지 않는다.

This exploratory plan uses counts, fractions and observed ranges. It does not
run significance tests, attach confirmatory confidence claims, rank all methods
or choose a winner from post-hoc subgroups. Three repeats do not justify a
population error-rate estimate. Any sample-size/effect-size assumptions for a
later confirmation study must be specified in that new study, not claimed here.

Qualitative records must cover **every** observed critical error and disputed
case, plus examples of successful required outcomes and arm disagreements.
Use case/cell IDs, frozen rubric labels, bounded public-answer excerpts and
observable consequences. Describe symptoms before hypotheses: stale facts,
invented promises, arithmetic errors, unnecessary intervention, omitted output
or unknown treatment exposure. Fluent wording, attribution footers and model
self-reports do not establish delivery or application. No hidden-reasoning
explanation or invented causal diagnosis is allowed.

정성 기록에는 모든 관측 중대오류와 이견을 포함한다. 표현의 유창함·출처 표기·모델
자기보고를 전달·적용 증거로 삼지 않으며, 증상과 원인 가설을 구별한다.

## 5. Time, tokens and exposure / 시간·토큰·처치 노출

Use only observed `elapsed_ms`, `input_tokens` and `output_tokens` at the frozen
measurement boundary. State whether the reported usage includes the complete
actor interaction, native reads and treatment overhead. Partial usage is not
total cost. Do not estimate unreported tokens from characters or derive a guessed
bill. Monetary cost is reported only when actually attributed and observed under
S039's declared scope/currency contract. Missing usage is `null`
with a reason, not zero. Cache usage is unavailable unless separately supported
and frozen; launch v1 does not require an invented cache field.

Per arm and case stratum show known-value count / attempted count, total observed
usage, and individual elapsed values or median/min/max. Include measured time and
usage for failed/time-out attempts; label censoring and unequal boundaries. A
completed-answer-only time summary is secondary and may be biased by failure.
Never claim efficiency from shorter answers that miss required content. Where
available, juxtapose observed resource totals with `P`, `F`, `U` and `C` rather
than issuing a single cost-effectiveness score. No observed passes means cost
per observed pass is unavailable; no cross-backend efficiency claim is made.

시간·토큰은 실제 관측과 측정 범위를 함께 보고한다. 누락값을 0으로 대체하거나
문자 수로 토큰을 추정하지 않는다. 실패·시간초과의 관측 비용도 포함하고, 필수
내용을 빠뜨린 짧은 답변을 효율 개선으로 해석하지 않는다.

Report treatment assignment separately from exposure: installation/configuration,
`entry_emitted`, `canonical_full_read`, `application_evidence` and task result
are distinct. Preserve `true`, `false`, and `null` for supported observations.
Missing observation means unknown; only supported contrary evidence justifies
false. Keep `application_evidence=unverified` unless actual supported evidence
exists; no native application receipt is fabricated or required for task success.
Do not exclude exposure failures from the native assigned-arm summary. A
clearly labeled exposed-only exploratory view cannot replace it or prove cause.

설치·진입 전달·정본 전체 읽기·적용·유용한 답변을 별개로 유지한다. 전달을 못
관측한 경우 unknown이며 곧바로 전달 실패가 아니다. 노출이 확인된 답만 골라
네이티브 조건의 전체 결과를 대체하지 않는다.

## 6. Stop, hold and continue rules / 중단·보류·계속

| Trigger | Required action | Preserved reporting |
| --- | --- | --- |
| No exact freeze, valid lease, isolation or budget authority before dispatch | Do not start affected calls; S001 resolves the specific dependency. No manual-injection fallback. | All assigned cells, pre-dispatch blocked reason and missing evidence. |
| Credential/private-data exposure, unauthorized external side effect, cross-arm contamination, wrong source/treatment bytes, or lost isolation during execution | S078 stops the affected surface immediately; stop the whole run if scope cannot be bounded. S001 records safe category and disposition before any continuation. No unsafe evidence capture. | Consumed reservations and all prior safe results; invalid/uncertain exposure remains visible. |
| Dispatch/time-out/error or uncertain dispatch | Keep the attempt, actual observed usage/time and safe category; consume its reservation under the budget contract. Proceed to the next fixed cell only if safe and authorized. | No replacement response or denominator deletion. |
| Ordinary rubric critical error, including wrong arithmetic or an unsupported draft promise | Preserve and score it; investigate later. Continue remaining fixed safe calls without changing inputs, guidance or thresholds. | Critical error in its original arm; no favorable early stop or repair-rerun within the version. |
| Unknown backend, unavailable independent judge, unknown canonical read or usage | Hold only the dependent model-specific, independent-review, exposure or efficiency claim. Task outcomes may still be described with limits. | Explicit `unknown`/`unavailable`, provenance and coverage; no fabricated pass. |
| Rubric ambiguity/translation discrepancy after answers exist | Retain answer and original score; hold affected comparison pending documented adjudication. Do not edit case/rubric to improve a result. | Disagreement and unresolved count; any later rescoring is a linked separate version. |
| Budget exhausted or program deadline reached | Stop new calls and scope. Preserve partial ledger, in-flight disposition and safe outputs; report partial. | Full 54-cell assignment and attempted/not-attempted counts, not a complete-study claim. |

안전·격리·정체성 위반은 해당 실행을 중단한다. 일반적인 채점 실패는 기록하고
안전한 고정 순서를 계속한다. 유리하거나 불리한 점수 때문에 조기 종료하지 않으며,
부족한 근거는 그 근거에 의존하는 주장만 보류한다. 기한·예산 초과 호출은 없다.

## 7. Result-dependent next actions / 결과별 다음 행동

The rows below guide investigation; they are not inferential significance
thresholds. Apply the safety/identity rules above first. Overlapping outcomes
retain all applicable findings; mixed results never collapse into a forced win.

| Observed pattern | Permitted conclusion | Concrete next action and condition |
| --- | --- | --- |
| Same observed tallies as general-check | Use this label only when all six compared strata have 3 adjudicated attempts per arm, equal pass counts and equal critical-error counts, with no unresolved scoring. This is identical observed tallies, not equivalence or proof of no effect. | S049/S050 show the strata, exposure and resource coverage. If a benefit distinction matters, propose fresh held-out cases and a separately powered/design-justified study; do not claim native superiority over a general reminder. |
| Native signal better than plain with no observed advantage over general-check | A generic check instruction is a plausible explanation; native-specific added value remains unestablished. Incomplete or close tallies do not establish equivalence. | Retain both control contrasts. Specify what additional task/exposure evidence would distinguish a generic reminder from delivery-specific benefit in a new frozen study. |
| Supported native delivery omission | The observed missing stage is a delivery symptom on the measured surface, not proof that canonical content is ineffective. Unobserved delivery remains unknown. | Record the exact stage and safe source/package identity. S001 routes a narrow delivery/isolation diagnosis to its existing owner; any product repair and retest receive new source/plan version and freeze. No model calls are authorized by this row. |
| One or more critical errors in any arm | The named answer failed the frozen requirement; frequency, product-wide cause and all-method effect remain unknown. | Preserve every error. For arithmetic, compare against the frozen deterministic key; for source/authority errors, cite synthetic facts and the violated rubric label. Open a scoped follow-up proposal without rewriting canonical methods from this pilot alone. |
| Mixed family/locale/repetition directions, ties, or missing outcomes | No single overall winner is established. Local signals, uncertainty and delivery differences remain separate. | Report all strata and unknowns. Prioritize the observed failing case/stage for a new held-out design; freeze any changed case, rubric or treatment separately before calls. |
| Native better on all observed tallies with no critical error | A favorable signal only for these frozen cases, identities and attempts. Three repeats still do not prove superiority, adoption or generalization. | Preserve losses/ties if present elsewhere and cost coverage. Propose new tasks, independent output-blind evaluation where available, and an authorized sample design before any confirmation claim. |
| No usable native calls, unavailable judge, or identity/isolation invalidation | The affected comparative claim is unavailable, not negative efficacy and not a pass. | Deliver partial ledger and concrete blocker. Resume only under the original unchanged valid freeze where allowed; changed inputs/source/isolation design require a linked new version and freeze. |

동일한 관측 집계는 동등성 증명이 아니다. 전달 누락은 전달 단계의 조사로, 중대오류는
해당 사례의 재현·원인 조사로 연결한다. 혼합·미실행·정체성 불명 결과는 전체 우승
주장으로 합치지 않는다. 추가 실험은 새 허가·유한 예산·동결이 있어야 실행한다.

Any follow-up must state the changed hypothesis, source/treatment/case/rubric
version, retained original failure, new held-out material where needed, exact
identity/measurement limits, finite authorized budget and freeze time before
responses. A source correction is not evidence about the previous bytes.
Analysis-only corrections retain the original report and state their reason,
scope and changed conclusions; they cannot retroactively become preregistered.
No rerun erases a bad result, and this plan itself authorizes no additional calls.

후속 변경은 새 버전·새 동결로 구별하고 원래 실패를 보존한다. 수정 뒤 결과를
수정 전 바이트의 증거로 쓰지 않으며, 사후 분석 수정을 사전등록으로 부르지 않는다.

## 8. Required S049/S050 report contract / 최종 감사·보고 인계

S049's audit and S050's report must make these sections inspectable:

1. **Design and identity:** exact freeze/source/package/input hashes; assigned
   arms; actual host/platform/model/tier observations and missing values;
   native versus manual-content distinction; deviations and actual order.
2. **Full flow and denominators:** all 54 IDs; `S`, `A`, `Z`, dispositions,
   `P`, `F`, `U`, `C`, completion true/false/null and missing-score bounds;
   `P/A`, `P/S`, `A/S`; no omitted failures/timeouts;
   unequal or unavailable denominators explained.
3. **Stratified comparisons:** six case strata with all repeats, family and
   locale summaries, both native contrasts and general-check context; no pooled
   total that conceals reversal, unknowns or delivery omission.
4. **Quality and provenance:** frozen rubric/keys, blind-ID mapping kept outside
   judge packets, scores fixed before arm reveal, actual judge identities,
   disagreements and missing independent review. Show S036's correction-burden
   ordinal distribution and unknowns separately from measured editing time;
   do not average dimensions into a composite score. Self-review or another chat
   from this authoring swarm is not independent human validation. No extra
   model judge calls are allocated by this plan.
5. **Failures and exposure:** every critical error, non-pass and unresolved
   scoring category; configuration/entry/read/application/result separated;
   symptoms distinguished from untested causes, including historical limits.
6. **Resources:** observed time/input/output tokens with coverage, boundary,
   censoring and unavailable usage; no unsupported total-cost or efficiency claim.
7. **Decision and limits:** applicable next-action rows, held conclusions,
   remaining uncertainty, conditions that would change each conclusion, and
   whether follow-up needs a new version/freeze/budget. State explicitly that
   this small pilot does not establish all-method efficacy, adoption or a new
   v1.6 release gate.

보고서는 설계·정체성, 전체 분모, 층별 비교, 채점 출처·이견, 실패·전달, 비용 관측
범위, 결론 보류·후속 조건을 모두 포함한다. 독립 평가자가 없으면 unavailable로
남기며, 작성자 자기평가를 독립 인간 검증으로 포장하지 않는다.

Retain only newly authored public synthetic inputs, bounded public final
answers, hashes/IDs, safe statuses/error categories, rubric decisions and observed
usage/time under the frozen retention contract. Do not collect private prompts,
raw host logs/transcripts, screenshots, credentials/authentication copies,
unrelated workspace content or hidden reasoning. A safe summary is not permission
to retain the prohibited original. Host-owned storage follows its own policy;
this study makes no deletion claim about that storage.

보존 대상은 새 공개 합성 입력과 공개 최종 답변 및 제한된 안전 메타데이터다.
개인정보·인증자료·원시 로그/전사·스크린샷·숨은 추론을 수집하거나 인증을 복사하지
않는다. 호스트 자체 저장소까지 삭제했다고 주장하지 않는다.

## 9. Integration boundary / 통합 경계

This draft consumes launch `interfaces-v1.json` without changing sibling schemas.
Before freeze, bind the final S031 `PROTOCOL.md`, S036 `scoring-rubric.json`/key references and
S039 `BUDGET.json` hashes. Resolve any denominator, timeout, scoring-state or
budget mismatch explicitly through S001 and S091; never silently overwrite an
upstream contract. Only the integrator performs canonical generation, and only
the assigned final owners validate the integrated frozen candidate in disposable
checkouts. This file changes no canonical methods, historical experiments,
generated artifacts, runtime, host activation or authentication state.

One authoring-time reconciliation item is explicit: S039's draft
`accounting.study_totals.attempted_pass_rate` says "terminal attempted cells",
while its total-attempt rule, launch v1 and S036 include unresolved `STARTED`
attempts. This plan uses **all attempted cells** for `P/A`, with pending states
shown. S001/S091 must settle the wording before freeze; a terminal-only secondary
summary must never replace that denominator. S039's additional metering fields
may remain a `cell_id` sidecar under its v1 adapter; no sanitizer expansion is
authorized here. These are integration notes, not executed schema validation.

S031·S036·S039 최종 산출물과의 일치 여부는 통합 시 확정한다. 이 문서 작성 중에는
테스트·빌드·리뷰·실험을 실행하지 않는다. 최종 검증은 통합 동결 후보에서 담당자가
수행하며, 이 초안을 실행·검증 완료로 보고하지 않는다.
예산 초안의 "종료된 시도" 문구는 미종료 `STARTED`를 포함하는 전체 시도 원칙과
동결 전에 조정해야 한다. 비용 확장 필드는 v1의 안전한 별도 자료로 연결할 수 있으며,
이 문서가 수집 허용 범위를 넓히지는 않는다.
