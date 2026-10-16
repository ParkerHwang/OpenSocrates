# S011: 선택 오류 뒤 연속 입력 상태 보존 / Session preservation after rejected selects

**Authored fixtures only — not executed or validated. / 합성 fixture 작성만 완료; 실행·검증 안 함.**

Runtime change: **NO_CHANGE**. This contribution adds only
`session-sequences.json` and this README. It does not rewrite PR #130 or change
runtime, canonical content, schemas, generated outputs, installation or trust.
런타임·정규 콘텐츠·스키마·생성물·설치·신뢰 상태를 변경하지 않습니다.

Base: [`197b317b4aeca4928fabe515dbfef6a98803e568`](https://github.com/ParkerHwang/OpenSocrates/commit/197b317b4aeca4928fabe515dbfef6a98803e568),
PR [#130](https://github.com/ParkerHwang/OpenSocrates/pull/130) head observed when
preparing S011. Remote `main` was `227a528996d93c423851db1d663f9572be534e59`.
The assigned recovery base is deliberately different from main; integration
selection belongs to S001/S091. Product version 1.5.2, content revision 5 are
source identities, not a claim that this candidate is released.
배정 recovery 기준과 main의 차이는 통합 담당자가 판단합니다. 이 기준 SHA는 출시 증거가 아닙니다.

## Six independent sequences / 독립 시퀀스 6개

Every sequence starts from a fresh `DecisionSession`, then runs `catalog`, a
successful synthetic explicit-method `select`, `acknowledge`, a rejected
`select`, correction, and requery. S011-05 and S011-06 add successful steps before
the error to make their initial cache/inventory distinction observable.
각 시퀀스는 새 세션을 시작하며, 성공·acknowledge 상태를 만든 뒤 오류·정정·재조회를 이어갑니다.
S011-05/06은 오류 전에 다른 성공 입력을 추가하여 마지막 선택과 누적 availability를 구분합니다.

| ID | New continuity assertion / 새 연속 상태 계약 | Fault trigger, not a standalone case / 오류 유발 입력 |
| --- | --- | --- |
| S011-01 | Same-request repair and an intervening catalog preserve routing reuse and acknowledged EN bytes. / 동일 요청 정정과 catalog 후 EN 캐시·ack 보존 | Boolean revision / revision에 boolean |
| S011-02 | Rejected higher epoch preserves old state; corrected accepted epoch clears assertions; repeats emit until newly acknowledged. / 거부된 epoch 증가는 보존, 정정된 승인 후에만 초기화 | Unsupported answer shape after valid epoch / 유효 epoch 뒤 잘못된 answer shape |
| S011-03 | Rejected foreign context preserves KO state; corrected handoff requires fresh emission and acknowledgment. / 거부된 새 context는 KO 상태 보존, 승인된 인계는 재전달 | Negative revision with valid different context / 새 context와 음수 revision |
| S011-04 | Rejected KO select preserves EN; corrected KO gets its own identity; EN remains reusable after KO acknowledgment. / KO 오류 뒤 EN 보존, KO 별도 ack 후 EN 재사용 | Features object instead of list / features에 객체 |
| S011-05 | Two acknowledged methods survive rejection; revisiting distinct decisions changes the last cache while preserving both deliveries. / 오류 후 두 방법의 availability 보존과 마지막 캐시 분리 | Missing routing features key / routing.features 누락 |
| S011-06 | Valid mechanical empty selection and later rejection preserve prior availability; repaired empty selection and substantive requery remain distinct. / 빈 선택·오류 뒤 이전 availability 보존 | Negative epoch / 음수 epoch |

All context handles, decision IDs, requests and fault values are newly authored
synthetic data. Explicit methods are stipulated synthetic requests so these
cases isolate state transitions rather than measure method classification.
모든 입력은 새 합성 데이터이며, 방법 선택 정확도나 실제 사용자의 요청을 나타내지 않습니다.

## Fixture interpretation / 해석

`session-sequences.json` is an S011-local **draft fixture format**, not an
existing supported runtime schema. No current check consumes it. Each step has a
full literal `request`, a named `pre_state`, expected response fields and a named
complete `post_state`. Named states describe the seven volatile fields:
`scope`, `last_key`, `last_selection`, `last_reason`, `delivered`, `available`,
and `busy`. They are expectations, never recorded observations.
현재 검사 도구는 이 파일을 읽지 않습니다. 각 상태와 응답은 관측값이 아니라 소스 계약에서 도출한 기대값입니다.

Keep all steps in one in-memory instance, using the same fixed canonical
bundle/projection pair and `response_policy=None`, as in the existing test setup.
Never seed snapshots directly. Each sequence begins empty and reaches its
prerequisites through the previous requests. Separate one-shot CLI calls cannot
share this state. The fixture does not require live hosts, credentials, a model,
hooks, installation changes, disk state or network calls.
한 시퀀스의 모든 요청은 동일 메모리 세션에 보내며 사전 상태를 직접 주입하지 않습니다.
실제 호스트·모델·인증·설치·hook 없이 source 세션만 대상으로 합니다.

The file's `notation` defines every operator. `$response` substitutes only a
sequence-local actual digest; request references must come from prior steps.
Post-state assertions may refer to the just-returned response. Instructions and
digests are compared with the full canonical assembly using
`$canonical_instructions` and `$canonical_sha256`; no hash or emitted body is
invented. `$request_sha256` follows the exact sorted-JSON hashing expression at
the pinned source. Arrays have exact lengths; `available` compares as a set.
Canonical content identity is fixed to revision 5. A changed candidate identity
requires an explicit rebase of expectations, not silently substituted values.
해시·본문은 가짜 관측값을 넣지 않고 정규 콘텐츠와 요청에서 계산할 관계식으로 남겼습니다.
기준 revision이 바뀌면 기대값을 명시적으로 재조정해야 합니다.

Response object comparisons are subsets; omitted object fields are unconstrained.
For every valid select, also compare `response.scope` to the literal request
context/epoch. Rejected responses must omit `selected` and `methods`. Snapshot
comparison is exact across all seven fields, and checks run only after `handle`
returns, when `busy` must be false.
응답은 지정된 필드와 배열 길이를 비교하고, 상태는 일곱 필드 전체를 비교합니다.

## Source basis and duplicate exclusions / 근거와 중복 제외

Every step lists source-reference keys. Their file paths, exact line ranges,
claims and SHA are in `source_references`. Core anchors at the pinned base:

- `selector/decision.py:125–154`: input faults return without reset.
- `selector/decision.py:189–230,240–268`: acknowledgment, validation before scope mutation.
- `selector/decision.py:269–329`: last-request cache versus identity/digest availability.
- `domain/routing.py:799–831,1047–1102`: selected fault guards and stipulated explicit/mechanical routes.
- `docs/decision-points.md:69–114`: process lifetime, repair and evidence boundaries.

위 근거는 JSON의 정확한 SHA·행 범위와 연결됩니다. 새 코드는 오류 경로를 재작성하지 않습니다.

The 20 standalone mutations in `evals/issue-124/select-faults.json` are not copied.
The existing 40 checks already cover successful reuse, compaction, locale changes,
multiple deliveries, standalone failures, one-error repair and stream shape.
Their individual cases are excluded here. The novel assertion in each sequence is
**the complete successful state surviving an intervening rejected select and
remaining distinguishable from a later accepted transition**. The
`duplicate_exclusions` list and each sequence's `overlap_exclusion` identify the
excluded neighboring checks. Their established behavior is a prerequisite,
not claimed as new test coverage.
기존 개별 오류 20종과 성공 경로 검사를 복제하지 않으며, 성공 상태가 오류를 거쳐 유지되는 연결만 추가합니다.
기존 성공 동작을 새 검증 결과로 세지 않습니다.

## Unresolved boundaries and integration / 미확인 범위와 통합

The file explicitly leaves runtime faults **after acceptance**, CLI malformed or
oversized input, process loss, host reading, method application and utility as
`unresolved` with null expected states. RequestFault preservation does not prove
rollback for accepted `_scope`/`_deliver` failures. Acknowledgment remains
`agent_reported`; `applied` stays `unverified` throughout.
승인 후 런타임 오류의 rollback과 실제 읽기·적용·유용성은 이 fixture로 추정하지 않습니다.

S011 executed no fixtures, tests, lint, builds, browser QA, or code/security
reviews. There is no new reproduced defect. Runtime disposition is NO_CHANGE.
The integration owner may accept these authored fixtures, then assign an adapter
outside S011's two owned files if executable coverage is wanted. After S001
freezes the exact integrated SHA, the final verifier can run the adapter in its
own disposable checkout and separately run the existing focused check:

```sh
PYTHONPATH=src .venv/bin/python tools/check_decision_points.py
```

This command is **proposed, not run**; it does not consume the new JSON file.
The expected legacy outcome is its existing checks passing on the selected
candidate; the new sequences have no result until an adapter executes them.
Repository-wide required checks belong to the integration/final-verification
owners. No generated inputs changed, so S011 does not run generation.
위 명령은 실행하지 않았으며 새 JSON을 검증하지도 않습니다. 동결 SHA 이후 최종 담당자가 담당 checkout에서 검사합니다.
