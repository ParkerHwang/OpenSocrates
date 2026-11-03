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
| `baseline` | No skill text. This is not a one-line general-instruction control. | Score a fixture when one exists, otherwise `model_unavailable`. |
| `output_brief` | Historical snapshot of the [PR #164](https://github.com/ParkerHwang/OpenSocrates/pull/164) skill in `bench/conditions/output_brief/SKILL.md`. | Same. The snapshot is not a live run of that skill. |
| `reader_1x` | Only `plugin-src/shared/reader/guide.en.md` in this checkout. | The file is fingerprinted and not executed. This is not a complete OpenSocrates 1.5.3 install or runtime. |
| `opensocrates_v2` | none; reserved | `model_unavailable` until a skill and an output exist. |

There is no shipped one-line instruction condition. Adding one later would be a new slot. This bench has no scores for it.

Missing fixtures are an honest skip. Shipping does not wait on a live call
for every slot.

## output_brief pin

`make bench` loads the committed file and checks its git blob:

- commit `d6091b4d7c62086326e494ac724b7d1db7c48d00`
- blob `06dfbc5ab41ea5f53952912087453caf8a0044a5`
- 2227 bytes

The PR #164 tip after Claude review is commit
`2775bf9beea5e802f94339ae7f8bd7c875c0ae25`, blob
`f5ed6cf9e0b7e2c70afb027c3d2069f7d3041a58`, 2495 bytes. That tip is recorded
in `PROVENANCE.json` and is not loaded. The comparison version has to be
agreed by Parker and Claude before this default changes. A refresh replaces
`SKILL.md`, `expected_git_blob` in the manifest, and `PROVENANCE.json` in one
change.

To preview another file without changing the default:

```bash
python3 -m bench.run --output-brief-pin /path/to/SKILL.md
```

The report then marks the pin as `override` and still records the documented
blob. `make bench` does not pass this flag.

## Model-call evidence

A command that prints a valid envelope proves two things: a process started,
and an envelope was parsed. It does not prove that a model ran. `model_called`
and `live_models_invoked` stay false unless harness code records a host
attestation (`opensocrates.v2-bench-model-attestation/1` with
`observed_by: harness`) after that code invoked the host. Stdout fields such
as `model_called` or `model_attestation` are ignored.

Failed commands record `execution_attempted` and whether `process_started`.
The failure status does not count as model use. No shipped adapter invokes a
host, so this harness does not report a verified model call.

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
on stdout. The request includes `public_synthetic`. That boolean is the case
author's claim. It is not proof that the prompt or materials are public or
synthetic. This harness still accepts only cases that set the claim to `true`.
If the field is missing or `false`, an experimental adapter may refuse the
run. A refusal has to be an explicit non-zero exit or an explicit error
status. It must not be a silent success or a fabricated envelope. Unset
command variables leave the row at `model_unavailable` with no process
started. A non-zero exit or a non-envelope stdout is `model_error`: the
process was attempted, and the model call stays unverified.

The packaged Codex selector is not this path. It selects a reasoning method
and returns selection JSON. This harness does not import it.

## Cases and rules

Cases live in `bench/cases/`. Each file carries an id, prompt, materials,
tags, and checks a rule scorer can apply without a model. Supported rules:

- `require_text`, `require_any_text`, `require_all_text`
- `forbid_text` (optional `clear_exceptions` and `ambiguous_cues`)
- `forbid_unlisted_dates`
- `script` (`latin_dominant` or `hangul_present`)
- `arithmetic_claim`

`arithmetic_claim` allows a percentage equal to the supplied numerator and
denominator. A percent inside a listed exception, or inside a material sentence
that denies a verified percent, is not a rate claim. A mismatched percent next
to a denial cue but outside those exceptions is `needs_human_review`. A bare
wrong rate still fails. Quoting “no one verified 100%” is not a pretended
verification. A post-hoc envelope under
`bench/regressions/calc-unverified-rate/` was added after this change. It is
not an independent holdout and is not a performance estimate.

Authored fixtures under `bench/fixtures/<case-id>/<condition>.json` exist to
show pass and `condition_fail`. Their `illustrates` text says they are not
model outputs. Do not compare condition columns as a leaderboard.

## Reason codes

| Code | Meaning |
| --- | --- |
| `pass` | All checks passed. |
| `condition_fail` | A check failed on a decidable literal match. |
| `needs_human_review` | A forbid match has a nearby cue and is not a listed exception. It is not pass or fail. |
| `model_unavailable` | No envelope was available. A missing executable was attempted and did not start. |
| `model_error` | A command failed before a usable envelope. This is not evidence of model use. |
| `input_error` | A case, fixture, or condition file is invalid. |
| `scorer_error` | A rule could not be applied. |

`make bench` exits 0 when the report is written and the public cases and
classifier probes contain no `input_error` or `scorer_error`. A
`condition_fail` or `model_unavailable` row is a recorded outcome, not a
broken harness.

## Adversarial check from Claude

Claude compared these fixed rules with a separate product checker on synthetic
sentences. Those sentences are not model outputs and are not a performance
estimate. The product checker is not the bench judge. A scanner flag is not a
bench pass or fail.

Reproduced on `e01-venue-messages` before the fix: `forbid_text` used raw
substring membership.

- `예약이 확정` matched the denial `예약이 확정되지 않았습니다`. The authored
  pass fixture had avoided that by writing `예약은 아직 확정되지 않았습니다`.
  That dodge did not make negation safe.
- `35명` matched a stale-value warning such as `예전 메모의 35명은 오래된 값`.

Listed `clear_exceptions` now cover those two shapes, so the denial and the
stale warning are not failures. A nearby cue that is not inside a listed
exception, such as `예약이 확정된 바 없습니다` or `35명은 오래된 값이 아닙니다`,
stays `needs_human_review`. A bare assertion, `예약이 확정되었습니다` or
`수용 인원은 35명입니다`, still fails. A denial that begins more than 16
characters after the match is outside this automatic window.

`unresolved-date-stated` accepts a clear unresolved-date phrase in the recipient
body or in `requester_notes`. Empty notes do not fail that check when the body
already says the date is unset. Wording that mentions a date or schedule
without saying whether it is set is `needs_human_review`. An unlisted calendar
date still fails `forbid_unlisted_dates`. Three post-hoc envelopes under
`bench/regressions/e01-venue-messages/` lock that behavior. They were added
after the rule change. They are not independent holdouts and are not a
performance estimate.

Paraphrases that never contain the literal pattern are still missed:
`잡아 두었습니다`, `삼십오 명`, and `채택되었습니다`. That is a blind spot.
The literal rule returning pass on those sentences is not a semantic clearance
and is not a solved checker.

## Add a case

Follow [ADD_A_CASE.md](ADD_A_CASE.md).

## 한국어

이 하니스는 Peter의 독립 제안 중 공개 벤치 조각입니다. 팀의 합의된 2.0 범위가
아니고, #161과 #163의 범위 충돌은 여기서 정리하지 않습니다.

채점은 사용자 언어의 본문을 영어 제목으로 강제하지 않습니다. 하네스 전용
봉투의 `body`와 `requester_notes`만 규칙으로 봅니다. 올바른 봉투가 돌아와도
모델 호출이 확인된 것은 아닙니다. 호스트를 하네스가 직접 봤다는 증명이
없으면 `model_called`는 거짓입니다. 픽스처의 통과와 실패는 채점기 예시이며
효과 크기가 아닙니다.

`output_brief` 기본 핀은 `d6091b4` blob `06dfbc5a`입니다. #164 팁 `2775bf9`
blob `f5ed6cf9`는 적기만 하고 불러오지 않습니다. 비교 버전은 Parker와 Claude가
맞춘 뒤에만 바꿉니다.

`public_synthetic: true`는 작성자의 주장입니다. 자료가 실제로 공개되었거나
가상이라는 증명이 아닙니다. 어댑터 요청 JSON에 그 값이 들어갑니다. 값이
없거나 `false`이면 실험용 어댑터는 실행을 거부할 수 있으며, 그때는 명시적
오류여야 하고 조용한 성공이어서는 안 됩니다.

`baseline`은 스킬이 없는 조건입니다. 한 줄 일반 지시 조건은 없습니다.
`reader_1x`는 `guide.en.md` 파일만 지문으로 읽으며, 1.5.3 전체 설치나 실행이
아닙니다.

날짜가 본문에 아직 정해지지 않았다고 분명히 있으면 요청자 메모가 비어 있어도
그 항목만으로 실패하지 않습니다. 날짜를 말하기만 하고 정해졌는지 드러나지
않으면 사람 검토입니다. 달력 날짜를 지어낸 경우는 계속 실패입니다.
`bench/regressions/`의 세 예는 규칙 수정 뒤에 더한 사후 예시이며, 독립
홀드아웃이나 성능 수치가 아닙니다.

Claude가 합성 문장으로 지적한 거짓 실패를 재현했습니다. `예약이 확정되지
않았습니다`와 `예전 메모의 35명은 오래된 값`은 이제 실패가 아닙니다. 예외
목록에 없는 주변 단서는 `needs_human_review`입니다. `잡아 두었습니다`,
`삼십오 명`, `채택되었습니다`처럼 글자 패턴을 피한 말은 여전히 놓칩니다.
그 통과는 의미 판정이 아닙니다. 제품 스캐너 표시는 벤치 합격이 아닙니다.

산술은 자료에 있는 분자와 분모로 계산할 수 있습니다. 자료가 100% 검증을
부인하는 문장을 본문이 인용하면 그 퍼센트는 비율 주장이 아닙니다. 예외 없이
부정 단서만 있는 다른 퍼센트는 사람 검토이고, 그냥 틀린 비율은 실패입니다.
이 사후 예시는 성능 수치가 아닙니다. 도구가 없는데 검증했다고 말하면
실패입니다. 케이스를 하나 추가하는 절차는 [ADD_A_CASE.md](ADD_A_CASE.md)에
있습니다.
