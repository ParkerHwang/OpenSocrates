# S013: synthetic nonreflection specifications / 합성 비반사 명세

**Authored only; NOT_RUN.** These 15 negative cases supplement [PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130) at `197b317b4aeca4928fabe515dbfef6a98803e568`. They contain authored synthetic markers, inert path-shaped strings and in-memory exception descriptions. No private prompt, transcript, credential, actual workspace path or host log is used.

**명세 작성만 완료했으며 실행하지 않았다.** 15개 부정 사례는 #130의 기존 구현을 보완한다. 표식·경로형 문자열·예외 메시지는 모두 새 합성 자료이며 실제 파일을 열거나 설치된 호스트를 호출하지 않는다. 런타임 변경은 **NO_CHANGE**다. 새 결함을 재현했다는 주장이 아니다.

## Scope and incremental coverage / 범위와 추가 범위

`nonreflection.json` is an input specification, not a result file or an automatically discovered test suite. The existing `tools/check_decision_points.py` does **not** consume it. Its `expected_response` objects are independently authored, source-derived expectations, never captured responses.

기존 기본 검사를 그대로 복제하지 않았다. 기존 20개 fault matrix의 no-echo 검사는 문자열 대체 값에만 적용된다(`tools/check_decision_points.py:404-405`). 기존 예외 검사는 메시지 없는 `ValueError` 클래스를 주입한다(`:448-452`). 본 명세는 다음 추가 입력과 응답 전체의 닫힌 형태를 다룬다.

| Cases | Added input / 추가 입력 | Expected boundary / 기대 경계 |
| --- | --- | --- |
| NF01 | Nested object and POSIX-shaped path in strength / strength의 중첩 객체·경로 | `routing.features[0].strength` / `invalid_type` |
| NF02 | Marked unknown routing key / routing의 표식 포함 미지 키 | `routing` / `unknown_field` |
| NF03 | Unknown entry key imitating a schema path / schema 경로를 닮은 미지 키 | `routing.features[0]` / `unknown_field` |
| NF04 | Object-valued feature key / 객체형 feature key | `routing.features[0].key` / `unknown_feature` |
| NF05 | Array/object basis with NUL, CR, LF, TAB, ESC / 제어문자 포함 배열·객체 | `routing.features[0].basis` / `invalid_value` |
| NF06 | Object-valued answer shape / 객체형 answer shape | `routing.answer_shape` / `invalid_value` |
| NF07 | Object method with Windows-shaped path / Windows형 경로를 담은 객체 | `routing.explicit_method` / `invalid_type` |
| NF08 | Missing known field plus marked unknown key / 필수 키 누락과 미지 키 동시 존재 | `routing.classification_confidence` / `missing_field` |
| NF09 | Nested invalid key at the last permitted index / 마지막 허용 index의 잘못된 key | `routing.features[15].key` / `unknown_feature` |
| NF10 | Malformed JSON containing literal controls / 실제 제어문자를 담은 잘못된 JSON | `request` / `invalid_json` |
| NF11–13 | Assembly `ValueError`, `TypeError`, `KeyError` with marked messages / 표식 포함 예외 메시지 | `decision_unavailable`; no repair fields / 복구 필드 없음 |
| NF14 | Outer CLI `RuntimeError` / CLI 바깥 예외 | `decision_unavailable`; no repair fields / 복구 필드 없음 |
| NF15 | Loader `OSError` with marked path/message / 표식 경로·메시지 포함 로더 예외 | `canonical_content_unavailable`; no repair fields / 복구 필드 없음 |

## Why the allowed output is closed / 허용 출력을 닫는 근거

Locations below refer to the assigned source SHA, not to a later integrated revision.

- `selector/decision.py:28-63,77-83`: repair codes and expectation strings are constants. `fault_response` emits the five `_failure` keys plus `field`, `error`, `repair` and an optional static `expected` string. / 복구 응답의 코드와 설명은 상수이며, 정해진 키만 허용한다.
- `selector/decision.py:125-164,233-267`: request guards supply known schema locations. `_select` adds the literal `routing.` prefix to the routing validator's fault; caught runtime exceptions become the five-field failure object. / 알려진 schema 경로만 조합하며 일반 예외 메시지는 출력하지 않는다.
- `domain/routing.py:799-859`: unknown keys produce the enclosing location rather than the submitted key name. Missing names come from fixed required-key sets. Feature locations use the enumerated list position after the length limit of 16; `[0]` through `[15]` are bounded schema indexes. / 미지 키 이름 대신 상위 경로를 반환한다. index는 입력 속성명이 아닌, 길이 제한을 통과한 목록의 순번이다.
- `domain/routing.py:875-882`: model-level exceptions map to a known field/code without returning their messages. This is source evidence; these fixtures do not inject into that constructor. / 모델 생성 예외도 고정 필드·코드로 변환한다. 이 생성자 경로는 코드 근거만 읽었으며 별도 주입 사례는 아니다.
- `cli/decision.py:19-62`: loader, parser and outer runtime failures map to constants; caught exceptions are not formatted into stdout. / 로더·JSON 파서·CLI 예외는 고정 응답으로 변환한다.

This boundary depends on the trusted internal call sites. `fault_response(field, error)` itself accepts supplied strings; it is not a general sanitizer for arbitrary caller-provided paths. The fixture tests the public request/CLI route, not an invented direct call with an attacker-controlled `field` argument. Valid `selected` responses legitimately include a context handle and canonical content; the closed error oracle applies only to the listed rejection/failure cases.

이 근거는 신뢰된 내부 호출 경로에 한정한다. `fault_response` 자체를 임의 문자열용 정제 함수로 간주하지 않는다. 정상 선택 응답의 context·정본 본문에는 이 오류 응답 전용 allowlist를 적용하지 않는다. 응답 비반사만으로 모든 저장·전달·실사용 품질이 검증됐다고 주장하지 않는다.

## Construction and oracle / 입력 구성과 판정

1. Create a fresh `DecisionSession` per case from the frozen checkout's compiled bundles. Deep-copy `baseline_request`, then apply `edits` in order. A path is a list of literal dictionary keys or integer list indexes; do not split it on dots or interpret it as a filesystem path. / 사례마다 새 세션과 입력 복사본을 사용하고 경로 조각을 문자 그대로 취급한다.
2. For `run_decision`, use `raw_input` verbatim when present; otherwise serialize the edited request. All streams are in-memory `StringIO`, `stream=False`. / CLI의 raw 입력은 그대로 사용하되 실제 호스트·파일 접근은 추가하지 않는다.
3. Only the three fixed mock targets below are permitted. Map the five named exception types explicitly; do not evaluate or dynamically import fixture strings. Install each mock only for its case. / 고정된 대상·예외 표만 사용하며 문자열을 실행하지 않는다.
4. Require exact JSON keys, values **and types**, as fixed in `expected_response`; additional metadata is a failure even when it contains no marker. Recursively inspect keys/string leaves, plus captured stdout/stderr, for the marker prefix and each case's forbidden substrings. Reject NUL/ESC in either channel and decoded strings. / 키·값·타입 전체가 일치해야 하며 표식이 없는 추가 필드도 실패다.
5. A session call returns only a dictionary and emits no stdout/stderr. CLI must return exit code 0, one JSON object plus one terminal LF, and empty stderr. Keep only case IDs, safe failure labels, command/exit, SHA and runner identity in evidence; do not save raw exception or stream captures. / 메모리 캡처는 검사 후 버리고 사례 ID·안전한 오류 분류·실제 명령·SHA만 기록한다.

## Deferred integration checks / 통합 후 검사 계획

**Do not run during authoring.** S001 must first publish an exact integrated `FROZEN` candidate. The verifier uses its own disposable checkout, confirms that its HEAD and fixture files match that candidate, and obtains any required shared-resource lease. Setup follows the owning verification task; do not create another environment or use an active host profile for these cases.

**작성 단계에서는 실행하지 않는다.** 최종 담당자는 S001이 공지한 동결 SHA와 전용 disposable checkout이 일치하는지 확인한 후 실행한다. 이 README의 실행 예시도 현재 실행하지 않았다.

If the scheduled suite already runs the existing decision checker, reuse that result for the same candidate. Otherwise its focused baseline command is:

```sh
PYTHONPATH=src uv run --locked --no-sync python tools/check_decision_points.py DecisionChecks.test_select_faults_name_closed_location_without_values DecisionChecks.test_failure_states_remain_distinct DecisionChecks.test_single_document_cli_rejects_multiple_json_documents
```

That command covers existing checks only. It does **not** establish that the new 15 cases pass. The following reference runner exercises the new specification; save its exact text/hash as runner provenance if used. It reads only fixed canonical bundle paths and the fixture, uses no model, auth, network or installed-host calls, and prints safe case IDs only. It is provided for the later verifier and is **unexecuted**.

위 명령은 기존 검사만 다룬다. 새 15개 사례는 아래 참조 실행기를 별도로 실행해야 하며, 사용 시 실행기 본문·해시를 증거로 고정한다. 정본 콘텐츠는 동결 checkout 내부 파일에서만 읽으며 합성 경로는 열지 않는다. 아래 코드는 **미실행** 상태다.

```sh
PYTHONPATH=src uv run --locked --no-sync python - <<'PY'
import copy
import io
import json
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from opensocrates.cli.decision import run_decision
from opensocrates.content.injection import ProjectionInstructionAssembler
from opensocrates.content.loader import load_compiled_bundle, load_reasoning_content_projections
from opensocrates.selector.decision import DecisionSession

root = Path.cwd()
fixture = json.loads((root / 'evals/stabilization-swarm20261015/S013/nonreflection.json').read_text())
bundle = load_compiled_bundle(root / 'content/compiled-content.bundle.json')
projections = load_reasoning_content_projections(root / 'content/compiled-reasoning-content.bundle.json')
exception_types = {'ValueError': ValueError, 'TypeError': TypeError, 'KeyError': KeyError,
                   'RuntimeError': RuntimeError, 'OSError': OSError}
cli_targets = {'cli.DecisionSession.handle': 'opensocrates.cli.decision.DecisionSession.handle',
               'cli.load_compiled_bundle': 'opensocrates.cli.decision.load_compiled_bundle'}

def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)

for case in fixture['cases']:
    session = DecisionSession(bundle, ProjectionInstructionAssembler(projections))
    request = copy.deepcopy(fixture['baseline_request'])
    for edit in case['edits']:
        target = request
        for segment in edit['path'][:-1]:
            target = target[segment]
        key = edit['path'][-1]
        if edit['op'] == 'drop':
            del target[key]
        elif edit['op'] == 'set':
            target[key] = copy.deepcopy(edit['value'])
        else:
            raise AssertionError('unsupported edit')
    stdout, stderr = io.StringIO(), io.StringIO()
    with ExitStack() as stack:
        injection = case['failure_injection']
        if injection is not None:
            error = exception_types[injection['exception_type']](injection['message'])
            if injection['target'] == 'assembler.assemble':
                stack.enter_context(patch.object(type(session.assembler), 'assemble', side_effect=error))
            else:
                stack.enter_context(patch(cli_targets[injection['target']], side_effect=error))
        stack.enter_context(redirect_stdout(stdout))
        stack.enter_context(redirect_stderr(stderr))
        if case['entrypoint'] == 'DecisionSession.handle':
            actual = session.handle(request)
        elif case['entrypoint'] == 'run_decision':
            payload = case['raw_input'] if 'raw_input' in case else json.dumps(request)
            exit_code = run_decision(io.StringIO(payload), stdout, stream=False)
        else:
            raise AssertionError('unsupported entrypoint')
    captured = stdout.getvalue()
    if case['entrypoint'] == 'run_decision':
        assert exit_code == case['expected_exit_code'], case['id'] + ': exit'
        assert captured.endswith('\n') and captured.count('\n') == 1, case['id'] + ': framing'
        actual = json.loads(captured)
    else:
        assert captured == '', case['id'] + ': unexpected_stdout'
    assert stderr.getvalue() == '', case['id'] + ': unexpected_stderr'
    assert type(actual) is dict, case['id'] + ': response_type'
    assert json.dumps(actual, sort_keys=True, ensure_ascii=False) == json.dumps(
        case['expected_response'], sort_keys=True, ensure_ascii=False
    ), case['id'] + ': closed_response'
    tokens = [fixture['oracle']['forbidden_marker_prefix'], *case['forbidden_substrings']]
    for text in [*strings(actual), captured, stderr.getvalue()]:
        assert not any(token in text for token in tokens), case['id'] + ': reflected_marker'
        assert not any(chr(point) in text for point in fixture['oracle']['forbidden_control_codepoints']), case['id'] + ': reflected_control'
    print(case['id'] + ': PASS')
print('15 synthetic nonreflection cases: PASS')
PY
```

Expected later result: 15 PASS lines plus the final count, exit 0; no marker or exception content in the retained output. A failure, setup error or unavailable dependency remains a failure/blocker and must not be omitted or rerun selectively to improve the denominator. Do not change this file's `NOT_RUN` fields into fabricated evidence: store actual final-state evidence separately with the exact candidate SHA, environment, command, fixture hash and runner hash. A tracked-file difference after checks is FAIL; do not copy generated outputs back to the candidate.

예상 결과는 15개 PASS와 exit 0이지만 **관측 결과는 없다**. 실패·환경 오류를 제외하거나 유리한 사례만 재실행하지 않는다. 실제 증거는 동결 SHA·환경·명령·fixture 및 실행기 해시와 함께 별도로 기록한다. 검사로 추적 파일 차이가 생기면 FAIL로 보고하며 생성물을 후보에 복사하지 않는다.

No runtime, canonical schema/content, generated package, active installation or trust setting is changed here. Integration owners S091/S001 decide whether to include this fixture and where to retain the durable GitHub handoff. Successful later execution would establish only synthetic source-level error nonreflection, not live delivery, method application, release qualification or answer-quality improvement.

런타임·정본·생성 패키지·설치·신뢰 설정은 변경하지 않는다. 통합과 GitHub 영구 인계는 S091/S001이 담당한다. 이후 검사가 통과해도 합성 소스 수준의 오류 비반사 증거이며 실호스트 전달·방법 적용·릴리스 검증·답변 개선 증거가 아니다.
