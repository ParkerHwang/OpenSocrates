# S012: one-shot and NDJSON framing fixtures

**Authored expectations only; NOT_RUN. Runtime: NO_CHANGE.**

These 31 public synthetic cases describe `run_decision` at recovery commit
`197b317b4aeca4928fabe515dbfef6a98803e568` (PR #130). They do not claim execution,
live delivery, method reading, application, or usefulness. No launcher, runner,
runtime change, generated input, installation, or active host setting is added.

## Input and expected-output representation

`framing.json` is a data manifest, not NDJSON to pipe directly into the command.
For each case, concatenate `input_segments` in order; a segment means its `text`
repeated `repeat` times. There is no interpolation, implicit newline, external
file reference, or dependence on the manifest file's own trailing newline. EOF
follows the final segment. Start a fresh invocation per case.

The `stream` boolean maps to `run_decision(..., stream=...)`. An
`expected.response_sequence` item names a parsed JSON response in
`response_expectations`; compare those objects in order. Each response is one
JSON object followed by a newline. JSON key order is not significant. The
`reset` operation keeps valid-frame responses small and deterministic; it does
not select a method or assert reading/application. Its explicit reset also
means these cases do not establish retention of prior method availability.

All `expected` values, including return codes, response counts, handler-call
counts and unread lengths, are source-derived predictions. The `execution`
object stays `NOT_RUN`, with observations null. There is no existing automatic
consumer of this new manifest; the current source suite does not replay it.

## Framing contract at the assigned SHA

| Boundary | One-shot | `--stream` |
| --- | --- | --- |
| Available content and immediate EOF | No response; return 0 | No response; return 0 |
| Blank physical line | One `invalid_json` response | One `invalid_json` response; continue |
| One valid object, with/without final newline | One response | One response; EOF ends the loop |
| A second newline after a valid line | Whitespace in the same document | A real empty frame; another `invalid_json` response |
| Two JSON objects on different lines | One `invalid_json` response for the document | One response for each line |
| Two adjacent objects on one line | One `invalid_json` response | One `invalid_json` response for that line |
| Pretty-printed object spanning three lines | One valid document | Three malformed frames in this fixture |
| Malformed line followed by a valid line | One document error; no per-line recovery | Error then valid response in the same session |
| Read payload exceeds 16,384 characters | One `request_too_large`; return 0 | One `request_too_large`; return 0; later frames are not processed |
| Canonical initialization fails, even at EOF | One `canonical_content_unavailable`; return 0 before reading | Same; response count is not proportional to supplied lines |

Both read paths request at most 16,385 **TextIO characters**, not bytes. In
stream mode `readline` includes the newline in its length check. Consequently,
a 16,384-character valid document without a newline is accepted at EOF, but
adding its newline produces `request_too_large`. A frame of 16,383 document
characters plus its newline remains within the limit and permits the next line.
The multibyte cases distinguish this character bound from UTF-8 byte length.

On oversize input, `run_decision` returns immediately: it does not drain to the
next newline, resynchronize, process the following valid line, or keep the
volatile session available for more requests in that invocation. For the
17,000-character oversized-line fixture, it reads 16,385 characters and leaves
615 characters of that line, its newline, and the following 22-character valid
line unread: 638 characters total. `stream-valid-oversize-valid` additionally
specifies the successful response emitted before the oversize failure.

Consumed/unread counts apply to a seekable TextIO such as `StringIO`. They do
not assert how far an OS pipe, decoder, or buffered reader has prefetched. A
valid stream frame without a newline requires EOF (or completion of the bounded
read); the finite cases do not promise an early response while the writer keeps
the pipe open. Controlled failure responses retain `continue_ordinary_work:
true` and `constraints_remain_binding: true`. These predictions do not cover
arbitrary read/write/encoding exceptions or a broken stdout. The canonical
initialization failure branch writes a newline but has no explicit flush.

## Source and overlap

All line references below are at the assigned recovery SHA, not mutable main:

- `src/opensocrates/cli/decision.py:19–39`: initialize canonical content and one
  `DecisionSession` before any read; unavailable content returns immediately.
- `src/opensocrates/cli/decision.py:40–63`: read/readline cap, EOF, oversize
  termination, JSON repair response, per-payload output and one-shot return.
- `src/opensocrates/selector/decision.py:46–83,125–172`: closed fault envelope,
  reset response, object-type rejection, failure flags and volatile-state reset.
- `tools/check_decision_points.py:366–378,499–532,711–726`: existing oversized,
  canonical-content, pretty-document, multi-document and stream checks. Their
  definitions were read; they were not run in S012.

[Closed issue #91](https://github.com/ParkerHwang/OpenSocrates/issues/91) already
defines bounded one-shot EOF input and NDJSON stream framing.
[Open PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130), for
[issue #129](https://github.com/ParkerHwang/OpenSocrates/issues/129), already
implements the repairable `invalid_decision_request` / `request` /
`invalid_json` contract used here. Its head matched the assigned SHA at
preparation; main was `227a528996d93c423851db1d663f9572be534e59`. S012 neither
rewrites that work nor claims it is merged/released. No new runtime defect was
established; runtime disposition is **NO_CHANGE**.

## Deferred integration verification

S091 may integrate only these two owned fixture files. After S001 publishes an
exact frozen candidate, the assigned final verifier may use its disposable
checkout to inspect/parse this manifest and compare cases with `run_decision`
using in-memory streams and the candidate's canonical content. For unavailable
content, use a scoped test patch to a guaranteed nonexistent synthetic root;
never remove an installation's files. Check ordered parsed output, return value,
handler-call count and TextIO position without retaining raw host output.

The existing focused command is:

```sh
PYTHONPATH=src uv run --locked --no-sync python tools/check_decision_points.py
```

This is a proposed future command, **not run here**, and it does not consume
`framing.json`. A future verifier must explicitly replay the manifest to claim
case coverage. Reuse the integrated suite's result if it already runs the same
check on the same candidate/environment. No additional launcher or automatic
consumer is part of S012. Package/host/release qualification remains separate.

## 한국어: 입력 표현과 현재 계약

**합성 fixture 작성만 완료했으며 실행하지 않았다(`NOT_RUN`). 런타임은
`NO_CHANGE`다.** 기준은 PR #130의
`197b317b4aeca4928fabe515dbfef6a98803e568`이며, main·출시판·실제 전달·읽기·적용·유용성
검증으로 확대하지 않는다. 새 런처·실행기·생성 원본·설치 변경은 없다.

31개 case는 각각 새 호출을 전제로 한다. `input_segments`의 `text`를 `repeat`만큼
반복해 순서대로 이어 붙이고 EOF를 준다. 암묵적 개행·보간·외부 파일 읽기는 없다.
`framing.json` 자체를 명령의 stdin으로 보내는 형식이 아니다. `stream`은 함수의
동명 인자이고, `expected.response_sequence`는 `response_expectations`의 JSON 객체를
순서대로 참조한다. 응답 하나마다 개행 하나가 있으며 JSON 키 순서는 비교하지 않는다.
`reset`은 작은 정상 응답을 만들기 위한 명시적 상태 초기화 요청이다. 방법을 선택하거나
읽기·적용 또는 기존 방법 가용성의 유지 여부를 입증하지 않는다.

정상 canonical content에서 즉시 EOF이면 응답 없이 0으로 끝난다. 빈 줄은 생략하지
않고 `invalid_json` 응답 하나를 만든다. 스트림은 다음 줄을 계속 처리한다. 정상 객체
뒤 개행 하나는 추가 빈 요청을 만들지 않지만 두 번째 개행은 별도 빈 줄이다. 서로 다른
줄의 객체 두 개는 스트림에서 응답 두 개, 단발에서 문서 전체 오류 하나가 된다. 한 줄에
객체 두 개를 이어 붙이면 양쪽 모두 해당 입력 단위의 오류 하나다. 여러 줄로 정렬한
정상 객체는 단발에서만 한 문서로 처리되며 이 fixture의 스트림 버전은 오류 세 개다.
잘못된 JSON 뒤 정상 줄은 스트림에서 같은 세션으로 계속 처리하고, 단발에서는 줄별
복구하지 않는다. 모든 기대값은 소스에서 도출한 예상이며 관측값은 null이다.

한도는 바이트가 아닌 `TextIO` 문자 16,384개이고 최대 16,385개를 읽는다. 스트림에서는
개행도 한도에 포함한다. 따라서 개행 없는 16,384문자 문서는 EOF에서 허용되지만 개행을
추가하면 초과다. 문서 16,383문자와 개행은 허용된다. 다중 바이트 합성 문자열 case는
문자 한도와 UTF-8 바이트 한도를 구분한다. 초과하면 `request_too_large` 응답 후 즉시
0으로 종료해 현재 세션을 계속하지 않으며 남은 줄 끝을 비우거나 다음 정상 줄을 처리하지
않는다. 17,000문자 case는 초과 줄의 남은 615문자·개행·다음 정상 줄 22문자, 합계
638문자가 `TextIO`에 남을 것으로 예상한다. 앞선 정상 응답이 있는 초과 case도 포함한다.

읽은/남은 문자 수는 `StringIO` 같은 seekable TextIO 기준이며 OS pipe·디코더·버퍼의
선행 읽기를 입증하지 않는다. 마지막 개행이 없는 정상 입력은 EOF가 필요하며, 쓰기 측이
열려 있는 동안의 조기 응답을 약속하지 않는다. 명시된 실패는 일반 작업 계속과 기존 제약
유지 플래그를 보존한다. 임의 I/O·인코딩 오류나 닫힌 stdout까지 처리한다고 주장하지
않는다. canonical 초기화 실패는 입력을 읽기 전에 응답 하나와 종료 0을 만들며 빈 입력도
예외가 아니다. 이 분기에는 명시적 flush가 없다.

근거 위치와 기존 검사 범위는 위 영문 목록과 같다. #91과 #130의 기존 구현을 재작성하지
않았고 새 런타임 결함을 확정하지 않았다. S091 통합 및 S001의 정확한 SHA 동결 후 최종
검증 담당자가 disposable checkout에서 manifest를 읽고 메모리 입력으로 비교할 수 있다.
위 focused command는 제안만 했으며 실행하지 않았다. 기존 검사기는 이 새 manifest를
읽지 않으므로 fixture 재생 여부는 별도로 명시해야 한다. 설치 파일을 제거하지 않고
일시적인 nonexistent-root patch로 unavailable 조건을 구성하며, 같은 후보·환경의 기존
검사 결과를 중복 실행하지 않는다. 호스트·패키지·출시 검증은 별도다.
