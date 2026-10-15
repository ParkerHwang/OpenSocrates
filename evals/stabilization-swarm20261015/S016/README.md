# S016: hook early returns and service ownership

**Authored specification; NOT_RUN. Runtime: NO_CHANGE.**

This fixture adds source-derived lifecycle expectations at base
`227a528996d93c423851db1d663f9572be534e59`. No new runtime defect has
been established. It does not rewrite #130's already implemented decision-error
changes, the parser tests, or the existing compact restoration tests.

## Contract and boundary

[hook-lifecycle.json](hook-lifecycle.json) contains 28 scenario rows, expanding
to 34 cases using the declared variants. The expected values describe proposed
assertions, not observations or passing results. Only the two files in this
S016 directory are proposed repository additions.

The entrypoint has two distinct boundaries:

| Path | Runtime/seam work | Flush | Close |
| --- | --- | --- | --- |
| Invalid arguments, nonempty selector-active marker, or native/lane mismatch | No service access | Never | Never |
| No injected service, noncompact SessionStart | No service access | Never | Never |
| No injected service, compact SessionStart | Inert compact seam, `decision_point_mode=True` | Never | Never |
| Injected service, including either SessionStart source | Inert adapter lookup and dispatch | Once if callable | Never |
| Factory-created service | Inert factory, adapter lookup and dispatch | Once if callable | Once if callable, after flush |
| Factory raises before returning an object | Factory attempt only | Never | Never |

The first three rows return before the generic `try/finally`. The
adapter-unavailable return is inside it and therefore still cleans up. Flush is
best effort for both service ownership modes. Close is best effort only for a
runtime constructed by this invocation. An ordinary exception from flush must
not skip an available owned close; either cleanup exception must preserve the
already emitted response and zero exit status.

These statements are restricted to the inert, ordinary-method fakes defined in
the JSON. Attribute descriptors that raise during `getattr`, `BaseException`
subclasses, failing output streams, false-valued objects, import failures, and
an artificial compact helper that raises are outside this specification. They
are not claimed to be covered by the exception boundary.

## Additional assertions and retained coverage

| Scenario family | Additional assertion | Existing behavior retained elsewhere |
| --- | --- | --- |
| E01-E03 | Early returns never access injected adapter/flush/close; recursion marker also prevents input reads, including marker `"0"` | Argument/recursion behavior in `tools/check_selector.py` VSC-10; mismatched input in `SubmissionEntryChecks` |
| S01 | Missing, null, numeric, boolean, array and object `source` values never enter the lifecycle block | Startup/resume/clear/future-source string no-ops in VSC-10 |
| S02 | Injected startup and compact sources both dispatch and flush without closing; compact seam stays untouched | VSC-10 exercises injected callbacks but its `_SyntheticRuntime` has no cleanup methods |
| S03 | Default compact calls the minimal seam exactly once with `decision_point_mode=True`; both response and unavailable paths avoid generic cleanup | Real helper discovery and expiry checks in VSC-10A and `test_compact_default_restores_discovery_not_an_abandoned_method` |
| R01-R04 | Explicit flush/close order for success, absent adapter, adapter lookup exception and handle exception, under each ownership mode | Existing hook checks exercise composition and adapter output without lifecycle-call ordering |
| R05-R10 | Flush and close failures are independent; neither suppresses later cleanup or changes output/exit status; factory failure has no object to clean up | No equivalent entrypoint lifecycle matrix found in the read checks |
| R06/R11/R12 | Absent/noncallable optional members are ignored; absence of one does not skip the other | Current `RuntimeServices` has `close` but no `flush_selector_outcomes`; the fixture must not require a real flusher |

Basic marker/no-op/compact output expectations are supporting setup for the
additional assertions. They are not proposed replacements for their existing
checks. The JSON also records this assertion-level deduplication map.

Source anchors at the fixed base:

- `src/opensocrates/hooks/entrypoint.py:141-174`: early returns and compact seam.
- `src/opensocrates/hooks/entrypoint.py:175-212`: `owns_runtime`, dispatch and cleanup.
- `src/opensocrates/hooks/codex_session_start.py:42-67`: real compact helper, excluded from new scenarios.
- `tools/check_selector.py:229-235`: existing synthetic runtime lacks lifecycle methods.
- `tools/check_selector.py:1600-1818`: VSC-10/VSC-10A existing contracts.
- `tools/check_decision_hook_runtime.py:38-172`: retained ingress/privacy/parser checks.
- `tools/check_decision_points.py:497-512`: retained decision-point compact check.

## Future executor interface

No executor is added or run here. A later test owner can consume the JSON using
Python 3.12 standard library only, in a disposable checkout of the exact frozen
candidate:

1. Load the exact `entrypoint.py` file with `importlib` under a fixture-only
   package namespace. Create empty namespace parents, bypassing production
   `__init__.py` files. Load only the pure `constants.py` and
   `hosts/codex/commands.py` leaf modules needed by its relative imports.
2. Install inert module substitutes for that namespace's `cli.runtime` and
   `hooks.codex_session_start`. A forbidden seam must fail the check if touched.
   Never import or invoke the real runtime builder, compact helper, adapter,
   persistence, selector or SDK. This avoids package-initializer side effects.
3. Expand variants before invocation. `source_present=false` deletes `source`;
   otherwise replace its value. A variants row does not also run its template.
   Use in-memory streams and an in-memory trace. Remove or set the selector
   marker only inside the isolated process, restoring its prior environment.
4. Make fake calls append their fixed label before any declared `RuntimeError`.
   Fake lookup and handle verify the host/event/raw-byte arguments. The factory
   keeps the inherited kwargs `host="codex", hook_only=True, workspace=None`.
   The compact substitute checks `decision_point_mode=True`.
5. Compare exact traces, stdout, stderr, return code and exception flag. Even an
   empty `stdout.write("")` counts as a write; the recursion guard writes
   nothing. Thus the trace pins order and excludes all unexpected cleanup.

The generic adapter response is deliberately synthetic JSON, not a native-host
legality fixture. The compact seam response is also authored, not evidence from
the real helper. Streams and method-call labels exist only in memory during a
future run. Do not add a logger, raw callback capture, user inputs, transcript,
screenshot, credentials, active host calls or persistent trace output.

## Deferred verification and handoff

S016 ran no fixture, test, lint, build, browser QA or code/security review.
Structural parsing, unique-ID/variant checks and a future fake-seam executor
remain unverified. No native delivery, complete read, method application,
answer usefulness, latency or release claim follows from this artifact.

After S091 integrates selected files and S001 publishes an exact frozen SHA,
the final verification owner should first inspect/parse the JSON and its
variant expansion. The fixture has no current runner, so existing smoke checks
do **not** execute these new cases. If a fake-seam consumer is not adopted,
report lifecycle execution as `NOT_RUN`.

For regressions, reuse the assigned final source-suite results. Relevant
existing commands are `PYTHONPATH=src uv run --locked python
tools/check_decision_hook_runtime.py` and `PYTHONPATH=src uv run --locked python
tools/check_selector.py`; do not rerun the complete suite separately if the
central verifier already covers it. Those commands may import real source
components and require the central owner's permitted disposable environment;
they are distinct from the proposed dependency-free consumer. Expected outcome
is no regression, not a result observed by S016. Real helper coverage remains
with the existing checks.

Related durable sources: [#130](https://github.com/ParkerHwang/OpenSocrates/pull/130)
(open Draft, head `197b317b4aeca4928fabe515dbfef6a98803e568` when read),
[#80](https://github.com/ParkerHwang/OpenSocrates/pull/80) (merged SessionStart
fast path), [#76](https://github.com/ParkerHwang/OpenSocrates/issues/76)
(closed original requirement), and
[#128](https://github.com/ParkerHwang/OpenSocrates/pull/128) (merged ingress fix).
Their prior check results are not validation of this new fixture.

한국어 요약: 합성 서비스로 조기 반환과 서비스 소유권별 정리 순서를 명세한
자료이며 실행 결과가 아닙니다. 일반 정리 구간에 진입한 주입 서비스도 flush할
수 있지만 close는 이 호출이 생성한 런타임에만 적용합니다. 그 구간 전의 반환은
둘 다 호출하지 않습니다. 새로운 런타임 결함은 확인되지 않아 런타임 변경은
`NO_CHANGE`이며, 실제 호스트·로그·인증·전역 설정은 사용하지 않습니다. 기존
검사의 기본 동작은 다시 구현하지 않고 추가 수명주기 기대만 분리했습니다.
