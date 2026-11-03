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
| `baseline` | No skill. | Not run. |
| `output_brief` | Fixture copy of the PR #164 skill, pinned in [SKILL.md](../../../bench/conditions/output_brief/SKILL.md). | Not run. The copy is not a merge of `codex/v2-output-brief`. |
| `reader_1x` | [plugin-src/shared/reader/guide.en.md](../../../plugin-src/shared/reader/guide.en.md) from this checkout. The guide already covers audience, evidence, uncertainty, and commitments; PR #164 itself says much of that ground is already there. | Not run. The file is fingerprinted. |
| `opensocrates_v2` | None. The slot is reserved. | Not run. |

`make bench` finishes without a live result for every slot. A missing output
is `model_unavailable`.

The #164 snapshot recorded here is commit
`d6091b4d7c62086326e494ac724b7d1db7c48d00`, git blob
`06dfbc5ab41ea5f53952912087453caf8a0044a5`. Later commits on that branch are
not followed automatically.

## Arithmetic and pretended verification

A model may compute a percentage from operands that are in the case. The
`arithmetic_claim` rule accepts that quotient and rejects a different
percentage. If the case says no external tool or system is available, phrases
that claim the figure was verified there fail. The scorer does not add a
confirmation of its own.

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

자료에 있는 수로 비율을 계산하는 것은 허용됩니다. 확인할 수단이 없는데
검증했다고 말하면 실패입니다. 효과 크기는 계산하지 않습니다.
