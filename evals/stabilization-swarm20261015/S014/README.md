# Large-input boundary recipes / 큰 입력 경계 recipe

State: **AUTHORED_NOT_RUN**. Runtime: **NO_CHANGE**. No new defect is alleged.
Source baseline: `227a528996d93c423851db1d663f9572be534e59` (merged [#128](https://github.com/ParkerHwang/OpenSocrates/pull/128)).

상태: **작성됨·실행 안 함**. 런타임: **NO_CHANGE**. 새 결함을 주장하지 않는다.
기준은 위 SHA이며 [#130](https://github.com/ParkerHwang/OpenSocrates/pull/130)의
결정 요청 복구 변경을 다시 구현하지 않는다.

## Scope / 범위

[`large-input-recipes.json`](large-input-recipes.json) specifies deterministic,
synthetic raw UTF-8 JSON envelopes for default Codex `UserPromptSubmit` discovery.
It adds only the two exact boundary sizes absent from the existing hook tests.
The other four requested sizes remain coverage references, not duplicate cases.

JSON 파일은 기본 Codex `UserPromptSubmit` 발견 경로를 위한 결정론적 합성
UTF-8 JSON 봉투 명세다. 기존 훅 검사에 없는 정확한 크기 두 개만 새 사례로
둔다. 나머지 네 크기는 기존 검사 참조이며 중복 생성 대상이 아니다.

| Raw envelope bytes / 원시 봉투 바이트 | Disposition / 처리 | Expected kind / 예상 종류 |
| ---: | --- | --- |
| 32,767 | New recipe / 새 recipe | Discovery entry / 진입 안내 |
| 32,768 | Existing exact-entry assertion / 기존 정확한 안내 비교 | Discovery entry / 진입 안내 |
| 32,769 | Existing exact-entry assertion / 기존 정확한 안내 비교 | Discovery entry / 진입 안내 |
| 4,194,303 | New recipe / 새 recipe | Discovery entry / 진입 안내 |
| 4,194,304 | Existing nonempty-output assertion / 기존 비어 있지 않은 출력 검사 | Discovery entry / 진입 안내 |
| 4,194,305 | Existing ingress rejection / 기존 입구 거부 검사 | Empty fail-open / 빈 출력·계속 진행 |

The coverage map identifies each existing test and its actual assertion strength.
At 4 MiB the existing test checks nonempty output, not exact guidance equality;
that narrower assertion is not described as stronger evidence. Large Unicode,
escaped text, malformed input, privacy projection and strict legacy rejection
already have checks in the same file and are not duplicated here.

커버리지 표에는 기존 검사와 실제 단언 수준을 연결했다. 4 MiB 검사는
정확한 안내 일치가 아니라 비어 있지 않은 출력을 확인하므로 근거를
부풀리지 않는다. 같은 파일의 큰 유니코드·이스케이프 텍스트·잘못된 입력·
개인정보 투영·엄격한 레거시 거부 검사도 중복 작성하지 않는다.

## Generation / 생성

The compact empty envelope is 73 ASCII bytes, including all field names, quotes
and braces. Fill its `prompt` with `x` repeated `target - 73` times. No BOM,
whitespace, newline or reserialization may be added. Thus `73 + 32,694 = 32,767`
and `73 + 4,194,230 = 4,194,303`. These are envelope lengths, not prompt lengths.
The JSON specifies literal prefix/suffix bytes and the equivalent compact JSON
serialization, so a verifier need not guess the wire format.

빈 압축 봉투는 필드명·따옴표·괄호를 포함한 ASCII 73바이트다. `prompt`를
`target - 73`개의 `x`로 채운다. BOM·공백·개행·재직렬화를 추가하지 않는다.
따라서 `73 + 32,694 = 32,767`, `73 + 4,194,230 = 4,194,303`이다.
프롬프트 길이가 아니라 봉투 길이다. JSON에는 접두·접미 문자열과 동등한
압축 직렬화 식이 있어 전송 형식을 추측할 필요가 없다.

Generate one buffer at a time, in memory, only after the integration candidate
is frozen. The largest new buffer is under 4 MiB. Do not check in expanded raw
payloads or create a 100 MB file. If the source limits change, reconcile the
recipe before execution rather than silently shifting its boundary meaning.

통합 후보 동결 이후 메모리에 한 사례씩 생성하고 사용 후 버린다. 가장 큰
새 버퍼도 4 MiB 미만이다. 펼친 원시 입력을 체크인하거나 100 MB 파일을
만들지 않는다. 소스 한도가 바뀌면 실행 전에 recipe를 조정한다.

## Deferred verification / 통합 후 검증

No generator, hook, tests, lint, build, host or actor calls were run for these
recipes. `NOT_RUN` and null observations are intentional. The authoring session
does not own final validation or expand any model-call budget.

이 recipe의 생성기·훅·검사·린트·빌드·호스트·모델 호출은 실행하지 않았다.
`NOT_RUN`과 null 관찰값은 의도된 상태다. 작성 세션은 최종 검증이나 모델
호출 예산을 소유하지 않는다.

After S001 publishes the frozen integration SHA, the assigned verifier should:

1. Confirm the two constants and recipe arithmetic in a disposable checkout.
2. Reuse `SubmissionEntryChecks.setUp/invoke` with injected memory-only services
   for the two new cases. Compare exact stdout with a small synthetic control
   and `ENTRY_GUIDANCE` from the same frozen source. Check exit zero, no selector
   call, the expected cleanup call and content-free projection.
3. Run the existing `tools/check_decision_hook_runtime.py` once if the final
   verification plan has not already covered it through `make smoke` or the
   release gate. Use the repository's Python 3.12 environment. A focused form is
   `PYTHONPATH=src uv run --locked --no-sync python tools/check_decision_hook_runtime.py`.
4. Record the exact tested SHA, actual command, exit code and unmet assertions;
   leave unexecuted cases `NOT_RUN`. Do not copy generated payloads or results
   back into the frozen candidate.

S001이 통합 동결 SHA를 게시한 뒤 지정 검증자가 disposable checkout에서
수행할 최소 절차는 다음과 같다.

1. 상수 두 개와 recipe 길이 계산을 확인한다.
2. `SubmissionEntryChecks.setUp/invoke`의 주입형 메모리 서비스를 사용해
   새 두 사례만 실행한다. 같은 동결 소스의 작은 합성 대조 입력 및
   `ENTRY_GUIDANCE`와 정확한 표준 출력을 비교하고 정상 종료·선택기 미호출·
   예상 정리 호출·내용 없는 투영을 확인한다.
3. 최종 계획의 `make smoke`나 release gate에서 이미 포함하지 않았다면
   위 Python 3.12 명령으로 기존 훅 검사 파일을 한 번 실행한다.
4. 실제 검증 SHA·명령·종료 코드·미충족 단언을 기록한다. 미실행은
   `NOT_RUN`으로 남기고 펼친 입력이나 결과를 동결 후보에 복사하지 않는다.

## Evidence boundary / 근거 경계

Expected responses are source-derived specifications, not observations. A later
in-memory pass can establish local parsing and entry emission only. Exit zero
alone does not establish emission. Neither entry emission nor delivery proves
method selection, complete reading, application, useful answers, live host
qualification or the historical cause of [#124](https://github.com/ParkerHwang/OpenSocrates/issues/124).
No native application receipt is created. Actual host invocation and model
context delivery remain unknown here.

예상 응답은 소스에 근거한 명세이며 관찰 결과가 아니다. 후속 메모리 검사가
통과하더라도 로컬 파싱·진입 안내 출력만 확인한다. 종료 코드 0만으로 출력이
입증되지 않는다. 안내 출력·전달은 방법 선택·전체 읽기·적용·유용성·실제
호스트 적격성·#124의 과거 원인을 입증하지 않는다. 네이티브 적용 영수증을
만들지 않으며 실제 훅 호출과 모델 문맥 전달은 여기서 미확인이다.
