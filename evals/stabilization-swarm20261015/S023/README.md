# S023 — Claude account skill static boundaries

This directory contains an assertion **specification**, not a test runner or an
account qualification result. `account-boundaries.json` is newly authored
synthetic fixture data. No assertion, package build, upload, activation or host
experiment was run for this assignment.

## Scope and baseline

The source baseline is `197b317b4aeca4928fabe515dbfef6a98803e568`, the inspected
HEAD of [Draft PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130).
Remote main was `227a528996d93c423851db1d663f9572be534e59`; that is the assigned
commit's parent. These are preparation observations, not final candidate identity.
The integration owner decides how to reconcile recovery work with main.

**Runtime/guidance implementation disposition: NO_CHANGE.** No new defect was
established. #130 already adds the shared `features.json` envelope and native
rejection contract. This assignment does not rewrite that implementation, change
its account guides, or replay its native request faults. The two files here add
future assertions and evidence boundaries only.

## Coverage without duplicate implementation

| Existing ownership | Keep in the existing checks |
| --- | --- |
| E01 | `features.json` byte parity in `tools/check_content_hosts.py`; envelope drift in `tools/check_decision_points.py` |
| E02 | Closed account layout, runtime/launcher absence, one skill, ZIP modes and rejection of hooks/scripts/tampering/links |
| E03 | Ten-locale catalog and complete canonical byte parity, deterministic output, locale fallback rejection |
| E04 | Attribution token presence and removal of the old footer |

Every existing-check record is `NOT_RUN` here. Source references are pinned to
the baseline above and are navigation hints, not claimed check results.

A01–A08 specify the remaining relationships: file selection without native
requests; locale-matched guide/catalog/procedure paths; eligible zero-to-two
selection and valid empty selection; catalogs versus complete procedures and
required dependencies; unavailable-content handling and reference restoration;
grounding versus receipt evidence; distributed envelope versus execution; and
separate live account surfaces. English and Korean guides are the semantic pair.
The package's ten-locale inventory remains with E03.

## Reading the evidence fields

`features_envelope_distribution` records what is expected to be shipped.
`native_runtime_presence` separately records the expected absence of native
runtime targets/launchers. Both have null observations because no ZIP was built
or inspected. `native_execution` is a third field and remains unobserved.
Shipping an envelope does not require the account model to submit it or prove
that anything executed. Host matching is model-selected.

Web Chat, Desktop Chat and current Cowork each retain null activation, selection,
complete-read, reported-application and usefulness observations. Static artifacts
and mocked cases cannot populate those fields. Native application receipts are
unavailable on this content-only surface; missing receipts do not create an
extra completion gate. A footer is also not such a receipt.

Each `synthetic_cases` entry has a `synthetic_input` and `expected_contract`.
Neither is an observed model response. `synthetic-method-a` is an invented label,
not an actual method. No new model call, conversation, credential, raw host log,
screenshot, hidden reasoning or unrelated workspace content is retained.

## Deferred final verification

After S001 publishes an integrated candidate SHA, the assigned verifier can use
its own disposable checkout to parse the fixture:

```sh
python3 -m json.tool evals/stabilization-swarm20261015/S023/account-boundaries.json > /dev/null
```

The existing package check, if not already covered on the same frozen candidate
by the assigned release/source verifier, is:

```sh
uv run --locked python tools/check_content_hosts.py
```

These commands have **not** been run by S023. There is no executable A01–A08
runner; inspect their relationships against the frozen controller/guides and
actual package identity. Expected results are parse success, existing check exit
0, aligned static instructions, and unchanged `NOT_OBSERVED` live cells. Passing
static checks cannot qualify live selection, reading, application or usefulness.
Any required generation belongs in the verifier's disposable checkout; tracked
generation drift is FAIL and must not be copied back. Reuse unchanged candidate
check evidence instead of adding a duplicate full-suite run.

## 한국어 요약

이 자료는 새 합성 fixture와 정적 assertion 명세입니다. 검사 도구나 실제 계정
관측 결과가 아닙니다. 기준은 Draft #130의 `197b317b4aeca4928fabe515dbfef6a98803e568`이며,
준비 시 원격 main은 그 부모 `227a528996d93c423851db1d663f9572be534e59`였습니다.
새 결함 근거가 없어 runtime·안내 구현은 **NO_CHANGE**입니다. #130의 기존 변경을
재작성하지 않습니다.

E01–E04의 바이트 일치·폐쇄 패키지·전체 정본·locale·기존 footer 검사를 중복 구현하지
않습니다. A01–A08은 파일 기반 모델 선택, 0~2개 적합 집합과 빈 선택, 전체 정본·필수
의존 읽기, 읽기 불가 시 일반 작업 계속, 압축·인계 뒤 참조 복원, 배포와 실행의 구분을
명세합니다. 영어·한국어 안내가 의미 기준이며 열 개 locale 패키지 검사는 E03이 맡습니다.

`features` envelope 배포, native runtime 부재, 실제 native 실행은 별도 필드입니다.
현재 모두 실측값이 null입니다. envelope를 배포했다고 실행 요청·실행·계정 활성화·전체
읽기가 증명되지 않습니다. 계정 선택은 모델이 하며 Web/Desktop/Cowork의 활성화·선택·
전체 읽기·적용 보고·유용성은 각각 **미관측**입니다. 모의 자료나 footer를 네이티브
증거로 쓰지 않으며 제공되지 않는 적용 영수증을 추가 완료 조건으로 만들지 않습니다.

실행 결과는 만들지 않았습니다. S001의 통합 SHA 동결 뒤 전용 disposable checkout에서
위 JSON 파싱과 기존 검사를 담당자가 수행하고 A01–A08을 정적으로 확인합니다. 같은
후보의 기존 검사 근거는 재사용합니다. 원문 대화·로그·화면·인증정보·숨은 추론은 보존하지
않습니다. 생성으로 추적 파일이 바뀌면 FAIL로 인계하고 후보에 복사하지 않습니다.
