# Swarm study privacy and public-artifact retention contract

**Status: authored contract, not execution or publication clearance.**
This file governs the proposed `swarm-20261015` study. It does not report a
completed experiment, a privacy review, a host installation or an efficacy result.
The English and Korean sections carry the same requirements.

## 1. Source, scope and freeze

The assigned source is main commit
`227a528996d93c423851db1d663f9572be534e59`. A read-only remote-main lookup on
2026-10-15 returned that exact commit. This is the authoring baseline, not the
eventual integrated study candidate. S001 must bind this contract, S031's
[PROTOCOL.md](PROTOCOL.md), the exact synthetic inputs, rubric, assignment order
and source identity to the pre-call freeze. A later source change needs an
explicit candidate identity and freeze decision; do not silently substitute it.

The launch v1 interface fixes three families (`email-agreement`,
`changed-recommendation`, `price-profit`), English/Korean, three conditions
(`plain`, `general-check`, `native-opensocrates`) and three repeats: **54
single-turn actor answers in one round**. Only S078 may execute that budget,
after S001 confirms the frozen inputs, shared quota and isolation approval.
S076's separately allocated recovery observations are not actor replacements.
S038 makes no model/API/experiment calls. The 100 authoring chats are not study
participants, control observations or additional model-answer evidence.

Freeze this contract before outcomes. Do not select favorable answers, change
thresholds after outcomes, make quality retries, replace failed cells or silently
remove failures, timeouts or interruptions from denominators. Report assigned,
attempted, completed, failed, timeout, blocked and not-run counts explicitly under
the frozen scoring rule. A privacy block does not erase an attempted call or
restore its quota. A changed protocol requires a separately identified future
study, not a repair of the current round's record.

## 2. Allowed data and retention units

Use an allowlist, not a list of fields to redact later. A field is retainable
only if its value also meets this contract. Unrecognized fields or opaque nested
payloads must not pass through to safe results or reports.

| Unit | Allowed contents | Boundary |
| --- | --- | --- |
| Authored fixture | Prewritten `case_id`, family, locale, `public_synthetic_input`, required outcome, critical-error labels and deterministic expected facts | Invented for public use before calls; no adaptation of private user work or hidden real identities. Use fictional roles and reserved example domains where needed. |
| Frozen provenance | Public repository URL, exact source SHA, product/content revision, repo-relative public input paths and SHA-256 digests | Hash only admissible public bytes. Do not hash prohibited material as a substitute for retaining it. |
| Assignment | Immutable cell/case ID, arm, repeat, order, assignment seed and v1 status | Arm mapping stays outside judge packets until scores are fixed. The seed describes order, not model determinism. |
| Result | Complete admissible `public_final_answer`, cell status, public rubric labels, `task_complete`, safe failure category | A final answer is eligible only when generated solely from the frozen public synthetic case and free of prohibited material. No host transcript or event stream is needed. |
| Delivery observation | `entry_emitted`, `canonical_full_read` as `true`, `false` or `null`; `application_evidence` | Preserve supported distinctions. Default application evidence is `unverified`; never create a native receipt. Unknown read evidence stays `null`, not `false`. |
| Public model identity | Host/platform and version where known; requested/observed public model label, effort and service tier | Record only non-account labels. Requested settings do not identify the actual backend or server processing tier. |
| Measurements | Safely observed start/end UTC, elapsed time, token counts, actual cost with declared currency/basis; aggregate scores/counts | Keep numbers, not provider payloads, invoices or billing-account details. Unavailable values are `null` with a safe reason; never zero-fill or estimate as observation. |
| Review/incident metadata | Synthetic cell or artifact ID, fixed rejection category, workflow role ID, UTC, action state and safe unresolved reason | No offending excerpt, local location, account identity, secret fingerprint or hash of forbidden bytes. |

The v1 case/result/source-identity fields remain the interoperability contract.
Review or publication decisions belong in a separate safe control record; they
must not be invented as extra native events or silently inserted into v1 result
objects. The public report may aggregate the allowed measurements and quote
reviewed public synthetic answers. It may not claim that a tool's acceptance
proves privacy, independence or answer quality.

## 3. Prohibited data and access

Do not intentionally collect, serialize, retain, publish or send to another model:

- Raw user prompts, real task notes, uploaded work files, private correspondence,
  work transcripts or unrelated workspace material. This prohibition does not
  include the separately authored, frozen public synthetic fixture itself.
- Credentials, tokens, cookies, OAuth/session material, keychain contents,
  authentication/configuration dumps, account IDs, handles, email addresses,
  subscription/billing identifiers or device identifiers. A fictional address
  in a declared synthetic case is not an account identifier.
- Absolute output/workspace/home paths, local usernames, machine names, private
  URLs, provider request/session/conversation IDs, or links that grant access.
  Public input manifests use repository-relative paths only.
- Raw host logs, raw event streams, complete interaction transcripts, tool-output
  dumps, screenshots, recordings, hidden reasoning or private scratch work.
  Do not request, reconstruct or log a native read/application receipt.
- Copies of logged-in environments, user homes, authentication stores or account
  skill backups. Never create isolation by copying existing login/configuration
  state. Use only S001-approved isolation; lack of approved access is `BLOCKED`.

Apply the allowlist before persistence: disable debug/trace captures, raw stdout
or stderr transcript files and request/response envelope dumps. An allowed
number may be taken from a supported usage field without saving its surrounding
payload. If a host cannot expose safe output separately from forbidden streams,
record that evidence as unavailable and block the affected collection route.
Do not add a collector to fill the gap.

Operational `status.json` is a separate coordination artifact whose v1 contract
requires an owned absolute worktree path. It is not a public study result. Do not
copy that file, resource requests, lease records, shell history or handoff paths
into judge packets or published evidence. Export an explicitly allowlisted
public subset instead.

## 4. Preserve the evidence boundary

Installation, discovery/entry emission, complete canonical-content retrieval,
method application and useful task completion are distinct claims. A command
name, success exit, attribution footer, agent assertion or complete read does
not establish application or benefit. Use only already supported, privacy-safe
observations; absence of an application receipt is not permission to collect one
or an extra condition for finishing an otherwise complete artifact.

Record native installed delivery separately from manual canonical-content
injection. A manual injection cannot become evidence for the native condition;
an unavailable native condition remains unavailable. Preserve actual host,
platform, model and treatment identity. If the backend cannot be identified,
`model_observed` is `null` with a safe reason even when the UI requested a model.
Likewise `service_tier_observed` remains `null` unless actually exposed.

An absent independent evaluator is `unavailable`; same-runner or same-model
review is not independent human validation. Historical v1.3 qualification and
v1.5 Mac smoke observations retain their original revisions, conditions, failed
attempts and limitations. They are design precedents, not current study cells or
evidence that the present candidate is installed, applied, effective or qualified.

## 5. Separate collection, judging and public release

| Role | Required handoff | Must not do |
| --- | --- | --- |
| S031 / S001 protocol and freeze | Bind the exact protocol, fixtures, privacy contract, identity and quota before any actor call; record actual state | Treat a draft or authoring-session output as frozen experimental evidence. |
| S078 actor runner | Submit only approved synthetic cases; hand off allowlisted results with all assigned/attempted statuses | Copy authentication, expand the model budget, retain raw streams or judge its own results as independent. |
| S044 safe-result ingestion | Enforce allowed fields and value boundaries; output only safe results and rejected field categories | Echo rejected values in exceptions/reports or treat a schema check as manual publication clearance. |
| S047 blind-packet preparation | Use blind IDs, public synthetic facts, fixed rubric and admitted final answers; hold arm mapping separately until scores are fixed | Include arm/installation hints, original cell IDs that encode arms, paths, host/model labels, timing, cost or other avoidable condition cues in judge metadata. Do not rewrite answer prose to hide a treatment; record residual unblinding risk. |
| S050 reporting | Consume admitted data, preserve denominator and unknowns, link exact public source/freeze identity and review status | Publish excluded bytes, operational paths, a fabricated reviewer sign-off or an efficacy claim beyond the actual design. |
| Prepublication privacy reviewer | S001 records an actual reviewer role distinct from S078's collection and S050's report authorship; inspect the exact proposed public bundle and record its public-byte digest and outcome | Certify a bundle from a tool summary alone, disclose prohibited content, or claim a human/independent review that did not occur. |

The separate privacy review is a publication condition, not permission to launch
another model run or another chat. Until an actual reviewer is assigned and the
exact bundle is cleared, publication remains `BLOCKED`. Role separation does not
by itself establish independent scientific judging. The reviewer checks content,
metadata, filenames, attachments and links, including identifiers echoed by an
actor. Automated screening supports that review; it cannot replace it.

Before public release, all of the following must be recorded as completed for
the exact bundle: allowed provenance and frozen inputs; safe complete answers
or explicitly withheld cells; rejected-field categories resolved without
disclosure; consistent total/attempt/failure counts; distinct native/manual
treatments and explicit unknowns; reviewer role/outcome; public-byte digest.
Public release still follows the owner's authorized publication workflow. This
contract and its source commit do not authorize posting or external messages.

## 6. Retention, deletion, stop and exposure response

Retain approved synthetic inputs, admitted final answers, safe assignments,
public source digests, outcome categories and aggregate measurements by study
and immutable cell ID. Retain full admissible answers rather than favorable
snippets. There is no separate user-work dataset. Frozen public files may remain
versioned for reproducibility; this contract promises no automatic deletion
deadline or removal from third-party caches, clones or host storage.

Delete unneeded safe temporary exports and blind mappings when scoring,
adjudication and audit needs are complete or the study is cancelled. Record
completion or inability using safe role/action metadata; do not claim cleanup
from a command's absence of errors. Do not delete another session's files or
rewrite shared Git history. Host-managed retention and conversation controls
remain the host's responsibility and are not overridden by package removal.

If prohibited material is detected or suspected:

1. Stop the affected collection/export/judging/publication route immediately.
   Keep the ordinary host task fail-open; do not change installation, trust or
   authentication state. Prevent further persistence/forwarding; do not make
   an evidence copy, archive, screenshot or quote, including in a private report.
2. Record only safe IDs, UTC, category (for example `PROHIBITED_FIELD`,
   `ACCOUNT_IDENTIFIER`, `LOCAL_PATH`, `PRIVATE_CONTENT`, `RAW_STREAM`), blocked
   action and unresolved state. Do not record matched text, nearby text, raw
   error messages, original locations or hashes of the forbidden data.
3. Before a call, use the existing v1 `BLOCKED` status. After an attempt, retain
   its actual lifecycle status and quota consumption. Withhold the answer and
   set dependent scoring/measurement to `null` where unavailable; report the
   privacy exclusion and its safe reason. Do not turn withheld content into a
   passing answer, a zero, a retry or a removed denominator entry. Publication
   clearance is separate from the v1 cell lifecycle; add no new cell enum.
4. Notify S001 through a safe state/handoff record. The owner of the affected
   artifact removes prohibited bytes from owned nonpublic material and records
   the action, without copying them into another folder. If deletion is outside
   its ownership or is unconfirmed, preserve `BLOCKED` and state the limit.
5. If already exposed, halt further distribution and follow the repository's
   [private security reporting route](../../SECURITY.md#report-a-vulnerability).
   Do not open a public issue with exploit or personal details. A maintainer
   handles access revocation, credential rotation, provider takedown or history
   remediation only within the appropriate authority; this task performs none
   of those actions. Mark third-party copies/removal as unknown when unverified.
6. Resume the route only after the cause is removed and the exact safe bundle is
   reviewed. Do not reuse exposed credentials, silently alter frozen inputs or
   rerun actor cells. A necessary changed experiment is a future, separately
   frozen protocol with separately authorized budget.

## 7. Unknowns and current handoff

Use `null` plus a safe reason for unavailable observations; never infer an
observed model/tier from configuration, an application from a read, or a
successful deletion from intention. Keep the v1 boolean/null fields and cell
statuses; state reasons in existing safe failure/limitations fields or the
separate safe control record. No free-form error text or raw event attachment is
needed to explain an unknown.

At authorship, the integrated freeze, approved runner isolation, actual backend
identity, actual server service tier, independent evaluator, prepublication
reviewer and final public bundle are **not established by this document**. S031's
protocol and S044/S047/S050 implementations must reconcile against this contract
and launch v1 during integration. No actor answers, empirical results, privacy
clearance, cleanup completion or publication are claimed here.

Policy sources at the authoring baseline:
[AGENTS.md](../../AGENTS.md), [CONTRIBUTING.md](../../CONTRIBUTING.md),
[SECURITY.md](../../SECURITY.md),
[content privacy](../../docs/content-privacy.md)
([한국어](../../docs/content-privacy.ko.md)),
[Mac observation report](../v1.5-macos/REPORT.md) and
[identities](../v1.5-macos/observations.json), and the historical
[v1.3 frozen protocol](../v1.3/release-guided-20260908/PROTOCOL.md).

---

# 실험 개인정보와 공개 산출물 보존 계약

**상태: 작성된 계약이며 실행·공개 승인이 아니다.** 제안된 `swarm-20261015`
실험에 적용한다. 실험 완료, 개인정보 검토 통과, 설치 또는 효과를 보고하지 않는다.
위 영어 본문과 아래 한국어 본문은 같은 요구사항을 담는다.

## 1. 소스·범위·동결

배정 기준은 main `227a528996d93c423851db1d663f9572be534e59`이며 2026-10-15
읽기 전용 원격 조회에서 일치했다. 이는 문서 작성 기준이며 최종 통합 후보는 아니다.
S001은 호출 전에 이 계약, S031의 `PROTOCOL.md`, 정확한 합성 입력·평가기준·배정
순서·소스 식별을 동결한다. 이후 소스가 바뀌면 후보와 동결 결정을 명시한다.

launch v1은 `email-agreement`, `changed-recommendation`, `price-profit` 세 과제,
영어·한국어, `plain`·`general-check`·`native-opensocrates` 세 조건, 세 반복으로
**단일 회차 54개 단일턴 actor 답변**을 고정한다. 동결 입력·공유 예산·격리 승인을
S001이 확인한 뒤 S078만 실행한다. S076의 별도 복구 관찰은 actor 대체 실행이 아니다.
S038은 모델/API/실험을 호출하지 않으며 100개 작성 채팅은 참가자·대조군·답변 증거가 아니다.

결과 전에 계약을 동결한다. 유리한 답변 선택, 결과 후 기준 변경, 품질 재시도, 실패
대체를 금지한다. 배정·시도·완료·실패·시간초과·차단·미실행 수를 동결된 집계 규칙에
따라 명시하며 실패·시간초과·중단을 분모에서 몰래 제외하지 않는다. 개인정보 차단도
시도와 사용 예산을 지우지 않는다. 변경된 실험은 별도 식별·동결한 후속 실험이다.

## 2. 허용 자료와 보존 단위

사후 삭제 목록이 아닌 허용 목록을 사용한다. 필드명과 값 모두 이 계약에 맞아야 하며,
알 수 없는 필드나 불투명한 중첩 객체를 안전 결과·보고서로 그대로 넘기지 않는다.

| 단위 | 허용 내용 | 한계 |
| --- | --- | --- |
| 사전 작성 fixture | `case_id`, 과제·언어, `public_synthetic_input`, 요구 결과, 치명 오류 라벨, 결정적 기대 수치 | 호출 전에 공개용으로 창작한다. 사적 업무를 변형하거나 실제 신원을 숨겨 넣지 않는다. 필요하면 가상 역할·예약 예시 도메인을 쓴다. |
| 동결 출처 | 공개 저장소 URL, 정확한 SHA, 제품·콘텐츠 개정, 공개 입력의 저장소 상대 경로와 SHA-256 | 허용된 공개 바이트만 해시한다. 금지 자료의 해시도 보존하지 않는다. |
| 배정 | 고정 cell/case ID, 조건·반복·순서·seed·v1 상태 | 조건 매핑은 점수 확정까지 평가 패킷과 분리한다. seed는 순서용이며 모델 결정성을 뜻하지 않는다. |
| 결과 | 허용된 `public_final_answer` 전체, cell 상태, 공개 rubric 라벨, `task_complete`, 안전 오류 범주 | 동결 공개 합성 과제로만 생성되고 금지 자료가 없는 최종 답변만 허용한다. 호스트 전사·이벤트 스트림을 수집하지 않는다. |
| 전달 관찰 | `entry_emitted`, `canonical_full_read`의 true/false/null, `application_evidence` | 지원되는 증거만 쓰고 적용은 기본 `unverified`다. 영수증을 만들지 않으며 미확인 조회를 false로 바꾸지 않는다. |
| 공개 모델 식별 | 확인된 host/platform·버전, 요청·관측 공개 모델명, effort·service tier | 계정과 무관한 라벨만 허용한다. 요청 설정으로 실제 backend·서버 tier를 추정하지 않는다. |
| 측정 | 안전하게 관측한 UTC 시작·종료, 경과시간, 토큰, 통화·산정 근거를 밝힌 실제 비용, 집계 점수·건수 | 숫자만 남기며 공급자 payload·청구서·결제 계정 자료는 금지한다. 미확인은 null과 안전 사유로 남기며 0·추정치를 관측으로 쓰지 않는다. |
| 검토·사고 메타데이터 | 합성 cell/artifact ID, 고정 거부 범주, 역할 ID, UTC, 조치 상태·안전한 미해결 사유 | 원문·로컬 위치·계정·비밀 fingerprint·금지 바이트 해시는 금지한다. |

v1의 case/result/source-identity가 호환 계약이다. 검토·공개 결정은 별도 안전 제어
기록에 두고 v1 결과에 몰래 필드를 넣거나 native 이벤트를 만들지 않는다. 보고서는
허용 지표를 집계하고 검토된 공개 합성 답변을 인용할 수 있다. 도구 수용은 개인정보
안전·독립성·품질의 증명이 아니다.

## 3. 금지 자료와 접근

다음 자료를 의도적으로 수집·직렬화·보관·공개하거나 다른 모델에 전송하지 않는다.

- 실제 사용자 프롬프트·업무 메모·업로드 업무 파일·비공개 연락·작업 전사·무관한
  작업공간 자료. 별도로 창작하고 동결한 공개 합성 fixture 자체는 이에 해당하지 않는다.
- 자격증명·토큰·쿠키·OAuth/session·keychain·인증/설정 dump, 계정 ID·handle·실제
  이메일·구독/결제/기기 식별자. 선언된 합성 과제의 가상 주소는 실제 계정 ID가 아니다.
- 절대 출력/작업공간/home 경로, 로컬 사용자명·기기명·사적 URL·공급자 요청/세션/대화
  ID·접근권한을 주는 링크. 공개 입력 목록은 저장소 상대 경로만 쓴다.
- raw host log·raw event stream·전체 상호작용 전사·도구 출력 dump·스크린샷·녹화·숨은
  추론·비공개 메모. native 조회/적용 영수증을 요구·재구성·기록하지 않는다.
- 기존 로그인 환경·사용자 home·인증 저장소·계정 스킬 backup 복제. 기존 인증/설정을
  복사해 격리하지 않는다. S001 승인 격리만 쓰며 승인 접근 부재는 `BLOCKED`다.

보존 전에 허용 목록을 적용한다. debug/trace, raw stdout/stderr 전사 파일과 요청/응답
envelope dump를 끈다. 지원되는 usage 필드의 숫자는 주변 payload 없이 취할 수 있다.
금지 스트림 없이 안전 출력을 얻을 수 없으면 증거를 unavailable로 남기고 해당 수집
경로를 막는다. 빈 증거를 채우기 위한 수집기를 추가하지 않는다.

v1상 절대 worktree 경로가 필요한 운영 `status.json`은 공개 실험 결과가 아니다.
이를 resource 요청·lease·셸 기록·인계 경로와 함께 평가 패킷이나 공개 증거에 복사하지
않는다. 공개 허용 목록으로 별도 내보낸 부분집합만 사용한다.

## 4. 증거 경계

설치, 발견/진입 방출, 정본 전체 조회, 방법 적용, 유용한 과제 완료는 각각 다르다.
명령명·종료 성공·출처 footer·에이전트 신고·전체 조회로 적용이나 효과를 증명하지
않는다. 이미 지원되는 안전 관찰만 사용한다. 적용 영수증 부재는 이를 새로 수집할
허가나 완성된 산출물에 추가할 완료 조건이 아니다.

네이티브 설치 전달과 수동 정본 주입을 구분한다. 수동 주입을 native 조건의 증거로
바꾸지 않으며 native 불가는 그대로 unavailable이다. 실제 호스트·플랫폼·모델·처리를
보존한다. backend가 식별되지 않으면 UI 선택과 무관하게 `model_observed=null`과 안전
사유를 남긴다. 실제 노출이 없으면 `service_tier_observed=null`도 유지한다.

독립 평가자 부재는 unavailable이며 실행자 자신의 검토·동일 모델 검토를 독립 인간
평가로 부르지 않는다. 과거 v1.3 검증·v1.5 Mac 관찰의 개정·조건·실패·한계를 유지한다.
이는 설계 참고이지 현재 cell, 설치·적용·효과·자격 증거가 아니다.

## 5. 수집·평가·공개 역할 분리

| 역할 | 인계 의무 | 금지 |
| --- | --- | --- |
| S031 / S001 | 호출 전 정확한 protocol·fixture·개인정보 계약·식별·예산을 동결하고 실제 상태를 기록한다. | 초안·작성 채팅을 동결된 실험 증거로 취급하지 않는다. |
| S078 실행 | 승인 합성 과제만 실행하고 모든 배정/시도 상태와 허용 결과를 인계한다. | 인증 복사·예산 확대·raw stream 보존·자기 평가의 독립성 주장을 금지한다. |
| S044 안전 결과 수집 | 필드·값 경계를 적용하고 안전 결과와 거부 필드 범주만 내보낸다. | 거부 값을 오류/보고서에 되풀이하거나 schema 통과를 수동 공개 승인으로 취급하지 않는다. |
| S047 블라인드 패킷 | blind ID·공개 합성 사실·고정 rubric·허용 최종 답변만 넣고 점수 확정까지 조건 매핑을 별도로 둔다. | metadata에 조건/설치 단서·조건이 드러나는 원 cell ID·경로·host/model·시간·비용을 넣지 않는다. 조건을 숨기려고 답변 본문을 고치지 않으며 잔여 노출 위험을 기록한다. |
| S050 보고 | 허용 결과, 분모·unknown, 정확한 공개 소스/동결 식별과 검토 상태를 사용한다. | 금지 바이트·운영 경로·가짜 승인·설계 범위를 넘는 효과 주장을 공개하지 않는다. |
| 공개 전 개인정보 검토자 | S001이 S078 수집 및 S050 보고서 작성과 다른 실제 역할을 기록한다. 정확한 공개 묶음과 공개 바이트 digest·결과를 점검·기록한다. | 도구 요약만으로 승인하거나 금지 내용을 공개하거나 수행하지 않은 인간/독립 검토를 주장하지 않는다. |

별도 검토는 공개 조건이며 다른 모델 실행·새 채팅을 허가하지 않는다. 실제 검토자
배정과 정확한 묶음 승인 전 공개는 `BLOCKED`다. 역할 분리만으로 과학적 평가의
독립성이 생기지 않는다. 검토자는 답변에 반복된 식별자까지 포함해 본문·metadata·
파일명·첨부·링크를 본다. 자동 검사는 보조 수단이며 이를 대신하지 않는다.

공개 전 같은 묶음에 대해 허용 출처·동결 입력, 안전한 전체 답변 또는 명시된 보류
cell, 노출 없이 처리한 거부 범주, 일치하는 배정/시도/실패 수, native/수동 구분과
unknown, 실제 검토 역할·결과, 공개 바이트 digest를 완료 상태로 기록한다. 외부 공개는
기존 소유자 승인 절차를 따른다. 이 문서·커밋은 게시나 외부 메시지를 허가하지 않는다.

## 6. 보존·삭제·중단·누출 대응

승인 합성 입력·허용 최종 답변 전체·안전 배정·공개 소스 digest·결과 범주·집계 측정을
study와 고정 cell ID 단위로 보존한다. 유리한 부분만 발췌해 원답을 대체하지 않는다.
별도 사용자 업무 dataset은 없다. 공개 동결 파일은 재현성을 위해 버전 관리될 수
있으며 자동 삭제 기한이나 제삼자 cache/clone/host 저장소 삭제를 약속하지 않는다.

채점·조정·감사 필요가 끝나거나 실험이 취소되면 불필요한 안전 임시 export와 blind
매핑을 삭제한다. 안전한 역할/조치 metadata로 완료·불가를 기록하며 오류가 없다는
이유만으로 완료를 주장하지 않는다. 타인 파일을 삭제하거나 공유 Git 이력을 바꾸지
않는다. host 보관·대화 제어는 해당 host의 책임이며 패키지 제거로 대체되지 않는다.

금지 자료가 감지되거나 의심되면 다음을 따른다.

1. 해당 수집·export·평가·공개 경로를 즉시 멈추고 추가 보존·전달을 막는다. 일반 host
   작업은 fail-open으로 유지하며 설치·신뢰·인증 상태를 바꾸지 않는다. 증거용 사본·
   archive·스크린샷·인용을 만들지 않으며 비공개 보고서에도 원문을 넣지 않는다.
2. 안전 ID·UTC·고정 범주(`PROHIBITED_FIELD`, `ACCOUNT_IDENTIFIER`, `LOCAL_PATH`,
   `PRIVATE_CONTENT`, `RAW_STREAM` 등), 차단 행동·미해결 상태만 남긴다. 일치 원문·주변
   문장·raw 오류·원 위치·금지 자료 해시는 기록하지 않는다.
3. 호출 전이면 기존 v1 `BLOCKED`를 사용한다. 호출 뒤면 실제 lifecycle 상태와 예산
   사용을 보존하고 답변을 보류한다. 의존 점수/측정이 불가하면 null과 개인정보 제외
   사유를 남긴다. 통과·0·재시도·분모 삭제로 바꾸지 않는다. 공개 승인은 v1 lifecycle과
   별개이며 새 cell enum을 만들지 않는다.
4. 안전 상태/인계 파일로 S001에 알린다. 해당 소유자가 소유한 비공개 자료에서 금지
   바이트를 제거하고 조치를 기록한다. 다른 폴더로 복사하지 않는다. 삭제가 소유권
   밖이거나 미확인이면 `BLOCKED`와 한계를 유지한다.
5. 이미 노출됐으면 배포를 멈추고 [비공개 보안 신고](../../SECURITY.md#report-a-vulnerability)
   절차를 따른다. 공개 이슈에 개인/악용 세부를 쓰지 않는다. 접근 취소·credential
   교체·공급자 삭제·이력 복구는 해당 권한이 있는 관리자가 처리한다. 이 작업은 이를
   실행하지 않는다. 외부 사본·삭제 미확인은 unknown으로 남긴다.
6. 원인을 제거하고 정확한 안전 묶음을 검토한 뒤 해당 경로만 재개한다. 노출 자격증명
   재사용·동결 입력 몰래 변경·actor 재실행을 금지한다. 실험 변경이 필요하면 별도
   protocol 동결과 별도 승인 예산을 가진 후속 실험으로 취급한다.

## 7. Unknown과 현재 인계

미확인은 null과 안전 사유로 남긴다. 설정으로 관측 모델/tier를, 조회로 적용을,
계획으로 삭제 성공을 추정하지 않는다. v1의 boolean/null·cell 상태를 유지하며 기존
안전 오류/한계 필드나 별도 안전 제어 기록에 사유를 쓴다. 자유 형식 raw 오류나
이벤트 첨부는 필요하지 않다.

이 문서 작성 시점에는 통합 동결·runner 격리 승인·실제 backend·실제 서버 tier·독립
평가자·공개 전 검토자·최종 공개 묶음이 이 문서로 입증되지 않는다. 통합 시 S031과
S044/S047/S050은 이 계약과 launch v1을 대조해야 한다. actor 답변·경험적 결과·개인정보
승인·삭제 완료·공개를 주장하지 않는다. 정책 근거는 위 영어 본문의 저장소 링크와 같으며
콘텐츠 개인정보 안내의 [한국어판](../../docs/content-privacy.ko.md)도 적용한다.
