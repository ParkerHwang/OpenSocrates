# S015 — UTF-8 byte and character boundary recipes / 인코딩 경계 recipe

**Authored, not executed / 작성만 완료, 실행하지 않음.**
`encoding-boundaries.json` contains public synthetic recipes and source-derived
expectations. It is neither a test runner nor an execution report. Runtime code:
**NO_CHANGE**. No new defect has been reproduced by S015.

공개 합성 recipe와 소스에서 도출한 기대치만 담았습니다. 테스트 실행기나 실행
보고서가 아니며, S015에서 새 결함을 재현하지 않았습니다. 런타임 변경은 없습니다.

## Separate contracts / 구분할 계약

| Surface / 경계 | Limit / 제한 | Measurement / 측정 |
| --- | --- | --- |
| Hook ingress / 훅 입력 | `MAX_HOOK_INPUT_BYTES = 4,194,304` inclusive / 이하 | Serialized envelope UTF-8 **bytes**, including JSON syntax and escapes / JSON 문법·이스케이프를 포함한 전체 UTF-8 바이트 |
| Decision CLI / decision 입력 | `MAX_REQUEST_CHARS = 16,384` inclusive / 이하 | Python `str` elements returned by `read` or `readline`, including returned whitespace and newline / 읽힌 문자열의 공백·줄바꿈을 포함한 문자 수 |
| Retained legacy native parser / 기존 native 파서 | `32,768` bytes for ordinary events / 일반 이벤트 | Separate existing boundary; do not substitute it for default submission discovery / 기본 제출 discovery 제한과 구분 |

The decision bound is not a prompt budget, grapheme count, UTF-16 unit count or
UTF-8 byte count. A literal `한` has one Python string element and three UTF-8
bytes; `🙂` has one element and four bytes. The serialized escapes `\ud55c` and
`\ud83d\ude42` occupy six and twelve ASCII characters respectively. Three Jamo
code points can render like one Hangul syllable and still count as three. Do not
normalize the input before measuring it.

decision 제한은 프롬프트 예산·화면상 글자·UTF-16 단위·UTF-8 바이트 제한이
아닙니다. 리터럴 `한`은 1자·3바이트, `🙂`는 1자·4바이트입니다. JSON 이스케이프는
각각 ASCII 6자·12자를 차지합니다. 한 음절처럼 보이는 자모 3개도 3자로 셉니다.
측정 전에 정규화하지 않습니다.

## Materialization / 입력 구성

Use the JSON file's named recipes as a declarative contract. Do not `eval` their
descriptions. Expand parameter arrays and stream types into separately named
variants; give every variant a fresh unread stream. Large bodies are generated
only in memory by the future verifier, not checked into Git or retained as logs.
All Korean text (`합성 경계 문장: ` and repeated `한`/Jamo) is authored synthetic
padding, with no user task or conversation content.

JSON의 이름 있는 recipe를 선언형 계약으로 해석하고 설명을 `eval`하지 않습니다.
매개변수·스트림 조합별로 새 스트림을 사용합니다. 큰 입력은 추후 검증자가 메모리에서
만들며 저장소나 로그에 보존하지 않습니다. 한국어 문구와 반복 문자는 모두 합성입니다.

For `hook_sized`, let `O` be the UTF-8 size of the complete serialized template
whose prompt is initially the synthetic prefix. Let `W` be the serialized-byte
increment per repeated unit. For target `H + delta`, compute
`n, r = divmod(H + delta - O, W)` and append `unit * n + 'x' * r` to the prompt.
The remainder makes every requested byte boundary exact, including when a unit
occupies three, four or nine bytes. Use the selected `ensure_ascii` consistently.

`hook_sized`는 합성 접두어가 들어 있는 전체 JSON의 바이트 수 `O`와 반복 단위의
직렬화 증가량 `W`를 기준으로 `n, r = divmod(H + delta - O, W)`를 계산합니다.
`unit * n + 'x' * r`를 붙여 3·4·9바이트 단위에서도 정확한 전체 바이트 경계를 만듭니다.

For `decision_padding` with `target_chars`, perform the same quotient/remainder
construction in **serialized Python string elements**, not bytes. Its deliberate
`synthetic_padding` field is not a valid request field. At or below `C`, the
expected result is a schema rejection after the size gate; above `C`, it is
`request_too_large`. This separates measurement from schema acceptance without
inventing Unicode operation names. `decision_valid_sized` instead uses a valid
catalog request padded with JSON whitespace, for an ordinary accepted control.

`decision_padding`의 `target_chars`는 직렬화 문자열의 문자 수로 계산합니다.
`synthetic_padding`은 의도적인 미지원 필드입니다. `C` 이하에서는 스키마 거절,
초과에서는 크기 거절을 기대합니다. 유효한 대조군은 catalog 요청 뒤에 JSON 공백을
붙이는 `decision_valid_sized`입니다.

`hook_octets` inserts the listed bytes inside the prompt string without trying
to decode or re-encode them. A future implementation can serialize the fixed
prefix and suffix separately, avoiding textual search and replacement. The
`truncate_after_octets` variant ends immediately after the incomplete sequence.
For raw surrogate strings, construct `chr(0xD800)` or `chr(0xDC00)` directly and
keep the result in `StringIO`; strict UTF-8 encoding has no value for that string.
For escaped variants use `ensure_ascii=True`, producing valid ASCII JSON bytes.

`hook_octets`는 지정 바이트를 디코딩하지 않고 prompt 따옴표 안에 넣습니다. 고정
접두·접미 JSON을 따로 구성하면 문자열 검색·치환이 필요 없습니다. 잘린 변형은 바이트
뒤에서 바로 끝냅니다. lone surrogate는 `chr`로 만들어 `StringIO`에 유지하고,
이스케이프 변형은 `ensure_ascii=True`로 ASCII JSON을 만듭니다.

## Stream and decoder boundaries / 스트림·디코더 경계

- Hooks accept `BinaryIO` and `TextIO`. An available `.buffer` takes precedence;
  a fresh `TextIOWrapper` configured with `utf-8-sig` therefore does **not** strip
  a BOM on the hook path. A bare `StringIO` is strictly UTF-8 encoded first.
- Decision input is a `TextIO` contract. `utf-8-sig` can strip a BOM in the
  caller's decoder before `run_decision` reads text. `utf-8` leaves U+FEFF in the
  string and JSON rejects a leading BOM. Do not give direct `BytesIO` results
  the status of a supported decision API contract.
- `newline=''` preserves CRLF as two characters. `newline=None` translates it
  to LF in the caller's decoder. A line with `C-1` characters before CRLF is
  oversize when preserved and exactly at `C` when translated. EOF adds nothing;
  an LF returned by `readline` counts toward `C`.
- Strict text decoding of invalid UTF-8 can fail at decision `read`/`readline`,
  before the JSON error handler. Such a category is separate from invalid JSON;
  its recipe predicts no JSON response or subprocess exit code. S015 has not
  executed it or proposed a runtime change.

`H17` additionally places a four-byte scalar across the binary `H+1` read
window. The complete source is valid UTF-8 but oversized; the hook rejects the
raw size before decoding the partial window. Keep this distinct from the
below-limit malformed UTF-8 recipes.

훅은 `.buffer`가 있으면 우선 사용하므로 text wrapper의 BOM 제거·디코딩 설정을
따르지 않습니다. decision은 `TextIO`에서 읽으므로 호출자가 지정한 codec과 줄바꿈
변환이 먼저 적용됩니다. 반환된 CRLF는 2자, 변환된 LF는 1자이며 EOF는 추가 문자가
없습니다. 잘못된 UTF-8의 엄격 디코딩 실패는 JSON 파싱 오류와 따로 기록합니다.
`H17`은 유효한 전체 입력의 4바이트 문자를 읽기 창에 걸쳐 배치하며, 디코딩 전에
초과 크기로 거절되는 경우를 제한 이하의 잘못된 UTF-8과 구분합니다.

## Frozen-candidate verification handoff / 동결 후보 검증 인계

S015 does not run these commands or materialize cases. After S091 integrates a
selected change and S001 publishes its exact frozen SHA, the assigned verifier
can use a disposable checkout of that SHA. Record the interpreter, platform,
source SHA and actual command/exit status. Never reuse #128 or #130's historical
validation as a result for this fixture or a new candidate.

S015는 아래 명령이나 fixture를 실행하지 않습니다. S091 통합·S001 SHA 동결 후
담당 검증자가 별도 disposable checkout에서 실행합니다. 인터프리터·플랫폼·SHA·실제
명령과 종료 코드를 기록하며, 과거 PR의 결과를 새 후보 결과로 재사용하지 않습니다.

Suggested minimum commands, **not run**:

```sh
python3 -m json.tool evals/stabilization-swarm20261015/S015/encoding-boundaries.json > /dev/null
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_decision_hook_runtime.py
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tools/check_decision_points.py
```

Use the repository's selected Python 3.12 interpreter if `.venv/bin/python` is
unavailable; record the actual invocation. JSON parsing only checks syntax, not
recipe correctness. The two existing suites do **not** automatically consume
this new JSON file. A future fixture consumer must implement the recipe contract
before claiming execution coverage; writing that consumer is outside S015's
owned files. Expected existing-suite results are no new regression. A root-only
read-only-directory baseline reported in #130 is historical, not a prediction
that permits ignoring a fresh failure.

JSON 문법 검사는 recipe 의미를 검증하지 않으며 기존 두 검사도 새 JSON을 자동으로
읽지 않습니다. 새 fixture 실행을 주장하려면 담당자가 recipe 소비자를 구현해야
합니다. 이 소비자 구현은 S015 소유 범위 밖입니다. 새 실패를 과거 환경 문제로
임의 제외하지 않습니다.

For future hook execution, reuse the memory-only services pattern in
`SubmissionEntryChecks.setUp`: `CodexAdapter` in `decision_point_mode`, mock
selector, mock instruction store and injected `adapter_for`. Do not construct
real installation services or access a real user's data root. Compare only the
current fixed `ENTRY_GUIDANCE`, literal empty output, safe error categories and
synthetic echo absence. Record installation, delivery, read, application and
usefulness as separate states; these recipes establish none of the latter.

추후 훅 실행은 기존 `SubmissionEntryChecks.setUp`의 메모리 전용 주입 방식을 사용해
실제 설치·사용자 데이터 루트를 피합니다. 고정 안내·빈 출력·안전한 오류 범주·합성
입력 미반향만 확인하며 설치·전달·읽기·적용·유용성을 구분합니다.

## Provenance and overlap / 근거·중복 범위

- Assigned base and read-only remote `main` matched
  `227a528996d93c423851db1d663f9572be534e59` when preparation began.
- Source: `src/opensocrates/constants.py` (hook bound),
  `hooks/entrypoint.py` (`_read_bounded`, `_input_metadata`, `run_hook`),
  `cli/decision.py` (`MAX_REQUEST_CHARS`, `run_decision`), and
  `hosts/codex/native.py` (`_text`, `try_parse_codex_entry_event`).
- Existing coverage: `tools/check_decision_hook_runtime.py` tests large Korean
  and escaped prompts, inclusive ingress, malformed bytes and an escaped
  surrogate; `tools/check_decision_points.py` covers oversized input and stream
  dispatch. These recipes add explicit encoding/reader matrices without editing
  those tests or runtime behavior.
- [Issue #127](https://github.com/ParkerHwang/OpenSocrates/issues/127) is closed;
  [PR #128](https://github.com/ParkerHwang/OpenSocrates/pull/128) merged the
  discovery/legacy size separation. Do not rewrite that correction.
- [PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130) was open/Draft at
  head `197b317b4aeca4928fabe515dbfef6a98803e568` when inspected. Its malformed
  JSON reclassification is versioned in this recipe file; its runtime repair
  contract is not reimplemented. Reconcile against the final integrated SHA.

배정 기준과 원격 main은 준비 시작 시 일치했습니다. #128의 기존 수정과 #130의
오류 응답 변경은 재작성하지 않습니다. JSON 파싱 실패의 기대치는 기준 main과 #130을
구분하며 최종 동결 SHA에서 다시 확정해야 합니다.

These are encoding boundary recipes, not whole-system language qualification,
memory-safety assurance, strict allocation limits, live host evidence, method
application receipts or answer-quality measurements. No prompt, transcript,
host log, screenshot, credential or hidden reasoning was collected.

이 자료는 시스템 전체 언어지원·메모리 안전·엄격한 할당량·실제 호스트 동작·방법 적용·
답변 품질의 검증이 아닙니다. 사용자 원문·대화·호스트 로그·스크린샷·인증정보·숨은
추론을 수집하지 않았습니다.
