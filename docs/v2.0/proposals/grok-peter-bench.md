# Public synthetic bench (Peter, independent proposal)

Status: independent proposal slice, implemented as an offline harness on a
branch from `main`. This note is not team consensus and does not replace the
[2.0 preparation packet](../README.md).

Parker authorized the harness, then asked for three design changes. Those
changes are what this branch implements.

## What this slice is

Peter's proposal is a measurable open check layer that reduces fabricated
facts and hidden assumptions in decision and outbound artifacts. The growth
asset in that proposal is a public reproducible bench, not a new 48-method
catalog and not a desktop session mediator.

This repository slice contains:

- public synthetic cases inspired by the preparation cases in
  [EVALUATION_CASES.md](../EVALUATION_CASES.md) (E01, E02, E04, E05, E06) plus
  one arithmetic case;
- four condition slots;
- a rule scorer that does not call a model;
- a contributor path for adding one case.

It does not report an effect size. Authored fixtures show that a rule can
pass or fail. They are labeled as authored examples.

## Envelope rather than fixed headings

A skill that must print the English headings "Recipient body" and
"Requester memo" changes the user's language and format, and it mixes the
scorer's labels into the skill under test.

This harness keeps those labels in a bench-only envelope. `body` is the
artifact in the language and format the user requested. `requester_notes` is
for the requester, or empty. The case prompt does not demand those English
headings. The skill bytes are loaded as-is and audited for those headings.
The [bench README](../../../bench/README.md) records the comparison.

## Condition slots

| Slot | Bytes used here | Live execution in this PR |
| --- | --- | --- |
| `baseline` | No skill text. There is no one-line general-instruction control in this harness. | Not run. |
| `output_brief` | Fixture copy of the PR #164 skill, pinned in [SKILL.md](../../../bench/conditions/output_brief/SKILL.md). | Not run. The copy is not a merge of `codex/v2-output-brief`. |
| `reader_1x` | Only [plugin-src/shared/reader/guide.en.md](../../../plugin-src/shared/reader/guide.en.md). The file is fingerprinted and not executed. It is not a complete OpenSocrates 1.5.3 install or runtime. | Not run. |
| `opensocrates_v2` | None. The slot is reserved. | Not run. |

`make bench` finishes without a live result for every slot. A missing output
is `model_unavailable`.

The loaded #164 snapshot stays commit
`d6091b4d7c62086326e494ac724b7d1db7c48d00`, git blob
`06dfbc5ab41ea5f53952912087453caf8a0044a5` (2227 bytes). The branch tip after
Claude review, commit `2775bf9beea5e802f94339ae7f8bd7c875c0ae25`, blob
`f5ed6cf9e0b7e2c70afb027c3d2069f7d3041a58` (2495 bytes), is recorded in
`bench/conditions/output_brief/PROVENANCE.json` and is not loaded. Parker and
Claude need to agree before that comparison version replaces the pin. `make
bench` checks the documented blob and does not fetch the tip.

## Author claim on adapter requests

`build_request` puts the case's `public_synthetic` value on the JSON stdin
object. `true` is the author's claim. It does not prove the materials are
public or synthetic. The case loader in this harness still requires the claim
to be `true` before a case is scored. If the field is missing or `false`, an
experimental adapter may refuse the run. That refusal must be an explicit
non-zero exit or an explicit error status, not a silent success or a
fabricated envelope. This branch does not implement that adapter.

## Model-call evidence

`process_started` and `envelope_received` record that a command ran and that
its stdout parsed as a bench envelope. `model_called` and
`live_models_invoked` stay false unless this harness records a host
attestation after its own client call. A local script that prints an envelope,
or a command that exits non-zero, does not verify model use. No host client
is wired up here, so verified model calls stay at zero.

## Adversarial observation

Claude's comparison used synthetic sentences, not model outputs, and it is
not a general performance estimate. The bench rule scorer stays separate from
any product evidence scanner. Scanner flags are not bench pass or fail.

`forbid_text` was raw substring membership. That made `예약이 확정` fail the
honest denial `예약이 확정되지 않았습니다`, and made `35명` fail a warning
that the old figure is stale. The earlier pass fixture avoided the first
match by writing `예약은 아직 확정되지 않았습니다`. Listed exceptions now
accept those two clear shapes. A nearby cue outside a listed exception becomes
`needs_human_review` instead of pass or fail. Bare assertions still fail.
A denial that begins more than 16 characters after the matched span is outside
this window.

Paraphrases that do not contain the literal pattern, including `잡아
두었습니다`, `삼십오 명`, and `채택되었습니다`, are still missed. A literal
pass on those sentences is a blind spot, not a solved semantic check.

The unresolved-date check accepts a clear phrase in the recipient body or in
the requester notes. It does not fail only because the notes lack a canned
phrase. Ambiguous date wording is `needs_human_review`. An invented calendar
date still fails. The three envelopes in `bench/regressions/e01-venue-messages/`
were added after that change. They are not independent holdouts and are not a
performance estimate.

## Arithmetic and pretended verification

A model may compute a percentage from operands that are in the case. The
`arithmetic_claim` rule accepts that quotient. A different percentage fails
when it is a bare claim. A percentage inside a listed exception, or inside a
material sentence that denies a verified rate, is not treated as a rate claim.
A mismatched percentage near a denial cue but outside those exceptions is
`needs_human_review`. A denial prefix that continues as `없지 않습니다` is
also `needs_human_review`, not a clean pass. Quoting the material statement that nobody verified 100%
is not pretended verification. Each scored section is limited to 20000 characters. Longer text is
`input_error`. After intervals are merged, one start list is built and reused
for every percent in that section. No timing was measured, so this does not
establish the scan's asymptotic cost. `forbid_text` still compares each match
with each of its own exception spans inside that bound. The envelope in
`bench/regressions/calc-unverified-rate/` was added after this change. It is
not an independent holdout and is not a performance estimate. The scorer does
not add a confirmation of its own.

## Scope that stays unresolved

- [PR #161](https://github.com/ParkerHwang/OpenSocrates/pull/161) drafts a
  desktop-session plan on `codex/v2-adaptive-team-plan`.
- [PR #163](https://github.com/ParkerHwang/OpenSocrates/pull/163) sets a core
  slice on `cursor/v2-core-ideas-ee06`, aimed at `codex/v2-runtime-foundation`
  rather than `main`.
- Those branches disagree about host priority and about which documents are
  current. This harness does not merge, rebase, or edit them.
- [PR #162](https://github.com/ParkerHwang/OpenSocrates/pull/162) and
  [PR #164](https://github.com/ParkerHwang/OpenSocrates/pull/164) were not
  modified. #164 is cited only as the source of the copied skill bytes.

Out of scope here: desktop session mediation, the IPC runtime, learning rules
from user corrections, rewriting the 48 by 10 method catalogs, and any claim
about answer-quality improvement.

## How to run and extend

`make bench` writes `build/bench/report.json` and `build/bench/summary.md`.
Adding a case is documented in [bench/ADD_A_CASE.md](../../../bench/ADD_A_CASE.md).

## 한국어

이 문서는 Peter의 독립 제안 중 공개 벤치 조각입니다. 팀 합의가 아니며
[2.0 준비 패킷](../README.md)을 대체하지 않습니다. #161과 #163의 범위 충돌은
아직 정리되지 않았고, 이 브랜치는 그 브랜치들을 병합하거나 수정하지 않습니다.

Parker의 설계 수정을 반영했습니다. 채점은 스킬에 영어 제목 "Recipient body" /
"Requester memo"를 강제하지 않고, 하네스 전용 봉투의 `body`와
`requester_notes`를 봅니다. 조건 슬롯은 `baseline`, `output_brief`(#164 스킬
원문을 픽스처로 복사), `reader_1x`(저장소의 `guide.en.md`), `opensocrates_v2`
(미래 슬롯)입니다. 라이브 호출 없이 출고할 수 있습니다.

`output_brief` 기본값은 `d6091b4` / blob `06dfbc5a`입니다. 팁 `2775bf9` /
blob `f5ed6cf9`는 불러오지 않습니다. 프로세스 실행과 봉투 수신은 모델 호출
확인과 별개이며, 호스트 증거가 없으면 모델 호출은 미확인입니다.

`public_synthetic: true`는 작성자의 주장이지, 공개·가상 자료라는 인증이
아닙니다. 요청 JSON에 포함되며, 없거나 `false`이면 실험용 어댑터는 명시적
오류로 거부할 수 있습니다.

`baseline`은 스킬 없음이고, 한 줄 일반 지시 조건은 없습니다. `reader_1x`는
영어 독자 가이드 파일만이며 1.5.3 전체 설치가 아닙니다. `예약이 확정되지
않았습니다`와 오래된 `35명` 경고는 거짓 실패였고, 이제 예외로 통과합니다.
본문이 날짜가 정해지지 않았다고 말하면 요청자 메모가 비어도 그 이유만으로
실패하지 않습니다. 애매하면 사람 검토이고, 지어낸 달력 날짜는 실패입니다.
사후 회귀 예시는 성능 수치가 아닙니다.
주변 단서가 애매하면 사람 검토입니다. 다른 말로 바꾼 주장은 글자 규칙이
놓치며, 그 통과는 의미 판정이 아닙니다. 제품 스캐너는 벤치의 유일한 판정자가
아닙니다.

자료에 있는 수로 비율을 계산하는 것은 허용됩니다. 100% 검증이 없다는 자료
문장을 인용한 퍼센트는 틀린 비율이 아닙니다. 애매한 부정은 사람 검토이고,
그냥 틀린 비율과 검증했다고 한 말은 실패입니다. `없지 않습니다`로 부정이
뒤집히면 사람 검토입니다. 20000자를 넘는 본문은 입력 오류입니다. 그 길이
상한이 확인된 범위이고, 수행 시간은 재지 않았으며 제곱 비용이 사라졌다고
하지 않습니다. 사후 예시는 성능 수치가 아닙니다. 효과 크기는 계산하지 않습니다.
