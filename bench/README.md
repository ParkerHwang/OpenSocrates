# Public synthetic bench

This harness is one slice of Peter's independent OpenSocrates 2.0 proposal:
a public, reproducible check for invented facts and hidden assumptions in
decision and outbound artifacts. It is not an agreed product direction.
The scope conflict between
[PR #161](https://github.com/ParkerHwang/OpenSocrates/pull/161) and
[PR #163](https://github.com/ParkerHwang/OpenSocrates/pull/163) is unresolved.
See [the design note](../docs/v2.0/proposals/grok-peter-bench.md).

`make bench` scores fixture envelopes with deterministic rules. It does not
call a model, does not read Codex `auth.json`, and does not compute an effect
size.

## Envelope, not fixed headings

Two ways to tell a recipient artifact from requester notes were compared:

| Approach | What the skill is told | What the scorer reads |
| --- | --- | --- |
| Fixed headings | The skill must emit English headings such as "Recipient body" and "Requester memo". | Text under those headings. |
| Bench envelope (used here) | The skill keeps the user's language and format. The harness does not rewrite it. | A harness-only JSON envelope with `body` and `requester_notes`. |

The envelope is the scoring surface. Those English headings are not required
in the case prompt, the skill bytes, or the artifact. A live command, when an
operator opts in, is asked for the same JSON transport. That transport is not
part of the skill.

```json
{
  "schema": "opensocrates.v2-bench-envelope/1",
  "body": "artifact in the user's language and format",
  "requester_notes": "notes for the requester, or an empty string"
}
```

## Condition slots

| Slot | Skill bytes | Default offline result |
| --- | --- | --- |
| `baseline` | none | Score a fixture when one exists, otherwise `model_unavailable`. |
| `output_brief` | Snapshot of the [PR #164](https://github.com/ParkerHwang/OpenSocrates/pull/164) skill in `bench/conditions/output_brief/SKILL.md`. | Same. The snapshot is not a live run of that skill. |
| `reader_1x` | `plugin-src/shared/reader/guide.en.md` in this checkout. | Same. The guide is fingerprinted, not executed. |
| `opensocrates_v2` | none; reserved | `model_unavailable` until a skill and an output exist. |

Missing fixtures are an honest skip. Shipping does not wait on a live call
for every slot.

## Run

From the repository root:

```bash
make bench
```

The command writes `build/bench/report.json` and `build/bench/summary.md`.
Both are generated local outputs. `build/` is gitignored.

Live mode is optional and still refuses to invent an answer:

```bash
OPENSOCRATES_BENCH_LIVE=1 \
OPENSOCRATES_BENCH_COMMAND='your-local-command' \
python3 -m bench.run --mode live \
  --report build/bench/live-report.json \
  --summary build/bench/live-summary.md
```

Per-slot overrides are `OPENSOCRATES_BENCH_COMMAND_BASELINE`,
`OPENSOCRATES_BENCH_COMMAND_OUTPUT_BRIEF`,
`OPENSOCRATES_BENCH_COMMAND_READER_1X`, and
`OPENSOCRATES_BENCH_COMMAND_OPENSOCRATES_V2`.
The command receives a JSON request on stdin and must print only the envelope
on stdout. Unset variables leave the row at `model_unavailable`. A non-zero
exit or a non-envelope stdout is `model_error`.

The packaged Codex selector is not this path. It selects a reasoning method
and returns selection JSON. This harness does not import it.

## Cases and rules

Cases live in `bench/cases/`. Each file carries an id, prompt, materials,
tags, and checks a rule scorer can apply without a model. Supported rules:

- `require_text`, `require_any_text`, `require_all_text`
- `forbid_text`
- `forbid_unlisted_dates`
- `script` (`latin_dominant` or `hangul_present`)
- `arithmetic_claim`

`arithmetic_claim` allows a percentage equal to the supplied numerator and
denominator. Any other percentage fails. Phrases that claim an external
verification also fail. The scorer does not invent a confirmation.

Authored fixtures under `bench/fixtures/<case-id>/<condition>.json` exist to
show pass and `condition_fail`. Their `illustrates` text says they are not
model outputs. Do not compare condition columns as a leaderboard.

## Reason codes

| Code | Meaning |
| --- | --- |
| `pass` | All checks passed. |
| `condition_fail` | The envelope was scored and a check failed. |
| `model_unavailable` | No output was available to score. |
| `model_error` | A command ran and did not yield an envelope. |
| `input_error` | A case, fixture, or condition file is invalid. |
| `scorer_error` | A rule could not be applied. |

`make bench` exits 0 when the report is written and the public cases and
classifier probes contain no `input_error` or `scorer_error`. A
`condition_fail` or `model_unavailable` row is a recorded outcome, not a
broken harness.

## Add a case

Follow [ADD_A_CASE.md](ADD_A_CASE.md).

## 한국어

이 하니스는 Peter의 독립 제안 중 공개 벤치 조각입니다. 팀의 합의된 2.0 범위가
아니고, #161과 #163의 범위 충돌은 여기서 정리하지 않습니다.

채점은 사용자 언어의 본문을 영어 제목으로 강제하지 않습니다. 하네스 전용
봉투의 `body`와 `requester_notes`만 규칙으로 봅니다. `make bench`는 모델을
호출하지 않고, 픽스처가 없으면 `model_unavailable`로 남깁니다. 픽스처의
통과와 실패는 채점기 예시이며 효과 크기가 아닙니다.

산술은 자료에 있는 분자와 분모로 계산할 수 있습니다. 도구가 없는데 검증했다고
말하면 실패입니다. 케이스를 하나 추가하는 절차는 [ADD_A_CASE.md](ADD_A_CASE.md)에
있습니다.
