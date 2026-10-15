# S030 — Host distribution source map / 호스트 배포 출처 대응표

This is a descriptive fixture specification for source commit
`227a528996d93c423851db1d663f9572be534e59` (product 1.5.2, content revision 5).
It records source selection and host boundaries. It contains no executed result,
package bytes, host receipt, or new checker.

이 자료는 위 기준 소스의 출처 선택과 호스트 경계를 기록하는 fixture 명세입니다.
실행 결과·패키지 바이트·호스트 영수증·새 검사 도구는 포함하지 않습니다.

## Contents / 구성

- [distribution-map.json](distribution-map.json): canonical inputs, generator and
  destination routes, included/excluded surfaces, write order, source evidence,
  seven authored synthetic provenance cases, explicit unknowns.
- `route_sets` are inherited by each host's `inherits_routes`; substitute the
  host's `skill_root` and `manifest_path`. Patterns describe sets, not commands.
- Every synthetic case is `NOT_RUN`. `expected_*` fields express intended source
  relationships, not observations or passing tests.

- JSON에는 canonical 입력→생성기→대상 경로, 포함/제외 표면, 쓰기 순서,
  근거 위치, 합성 출처 사례 7개와 명시적 미확인을 기록했습니다.
- 각 호스트는 `inherits_routes`의 공통 경로를 상속합니다. `skill_root`와
  `manifest_path`는 해당 호스트 값으로 읽습니다. 패턴은 명령이 아닙니다.
- 합성 사례는 모두 `NOT_RUN`입니다. `expected_*`는 출처 관계의 예상값이며
  관측값이나 검사 통과 결과가 아닙니다.

## Guide and envelope sources / guide와 요청 형식의 출처

| Host | Decision guide input | Shared features | Shared request | Reader guide input |
| --- | --- | --- | --- | --- |
| Codex | `plugin-src/shared/decision/guide.{locale}.md` | included | included | `plugin-src/shared/reader/guide.{locale}.md` |
| Claude native | `plugin-src/claude/references/decision/guide.{locale}.md.tmpl` | included | included | same shared reader |
| Claude account | `plugin-src/claude-chat/guide.{locale}.md` | included | excluded | same shared reader |
| Antigravity | `plugin-src/claude-chat/guide.{locale}.md` | included | excluded | same shared reader |

표의 included/excluded는 공유 `features.json`과 `request.json` 파일의 포함 여부입니다.
Claude account와 Antigravity는 실행 파일·hooks·runtime을 갖지 않는 닫힌 배포입니다.
Antigravity는 account controller와 notices도 재사용하며, 자체 README와 standing rule을
추가합니다. 두 content-only 호스트 모두 compiled bundle과 response policy를 입력으로
소비하지만 그 JSON/YAML 파일 자체를 패키지에 복사하지 않습니다.

The two content-only profiles have closed, non-executable layouts. Antigravity
also reuses the account controller and notices, with its own README and standing
rule. Both consume compiled bundles and response policy as inputs without copying
those JSON/YAML files into their payloads.

## Write order / 쓰기 순서

Native generation renders manifest/hooks, host `shared_templates`, method
references, canonical locale procedures/catalogs, then command templates. It next
copies `copy_files` in metadata order, serializes response policy and the legacy
bundle, copies a selected runtime if available, and applies the Codex Windows
guide rewrite before inventorying final bytes.

`shared_templates` is a metadata field: its paths resolve beneath the selected
host source directory. It does not mean `plugin-src/shared`. A later copy can
replace an earlier rendered path. Claude's guide survives because its metadata
copies only shared features/request, not the shared decision guide. Codex's shared
decision copy is later, and its Windows guides then replace `bin/launch.sh` with
`node bin/launch.mjs`; source origin does not imply identical final Windows bytes.
Content-only `_files` chooses its sources directly; it has no overlay algorithm.

native 생성 순서는 manifest/hooks → 호스트 `shared_templates` → 일반 method 참조 →
로케일별 canonical 절차/catalog → command 템플릿 → 순서대로 `copy_files` → 정책과
legacy bundle 직렬화 → 있는 경우 선택 runtime 복사 → Codex Windows guide 치환 →
최종 바이트 목록입니다. `shared_templates` 경로는 호스트 소스 안에서 해석합니다.
뒤의 복사는 앞의 같은 경로를 덮을 수 있습니다. Claude guide는 공유 guide를
복사하도록 설정하지 않았기 때문에 유지됩니다. 호스트 템플릿이 항상 이기는 규칙은
없습니다. Codex Windows guide는 복사 뒤 launcher 표기를 바꾸므로 원본과의 바이트
동일성을 주장하지 않습니다. content-only는 `_files`가 출처를 직접 선택합니다.

Native response-policy tokens come from `content/response-policy.yaml`.
Shared rigor activation guards prefix strict-second-pass tokens where a native
template consumes them. The content builder renders response-policy tokens but
does not perform that native guard-prefix loop. No current native metadata
configures `render_profiles`; supported profiles cannot replace core tokens.
Unknown future overlays and live host instruction priority remain `null`.

native의 response-policy 토큰은 canonical YAML에서 렌더링합니다. shared rigor
activation은 native 템플릿이 사용하는 strict-second-pass 토큰 앞에 붙습니다.
content-only는 정책 토큰을 렌더링하지만 native guard-prefix 반복은 수행하지 않습니다.
현재 native metadata는 `render_profiles`를 설정하지 않으며, 지원되는 profile도 핵심
토큰을 바꿀 수 없습니다. 미래 overlay와 실제 호스트 지침 우선순위는 `null`입니다.

## Scope and overlap / 범위와 중복 제외

**Runtime/generator change: NO_CHANGE.** No new defect is established by this
source inventory. The only repository additions are this README and its JSON.
[PR #130](https://github.com/ParkerHwang/OpenSocrates/pull/130) was OPEN at head
`197b317b4aeca4928fabe515dbfef6a98803e568`; it is not merged into this base.
It already implements request-repair errors and changes shared features/guides.
S030 neither reimplements nor cherry-picks that work. The source-path map must be
reconciled with the exact integrated candidate before consumption.

**runtime/생성기: NO_CHANGE.** 이번 출처 목록에서 새 결함을 확정하지 않았습니다.
저장소 추가는 이 README와 JSON뿐입니다. #130은 위 head의 열린 PR이며 기준 main에
아직 병합되지 않았습니다. 이미 구현한 요청 복구·공유 features/guide 변경을 재작성하거나
가져오지 않았습니다. 통합 후보를 소비할 때 정확한 SHA에서 경로를 다시 대조해야 합니다.

The existing content-host checker already owns byte parity of canonical
procedures/catalogs, reader/features, determinism, portable ZIP modes, closed
members and rejection cases. Native inventory, launcher/runtime and documentation
checks also already exist. See `existing_checks_delegated` and `evidence_index`.
This fixture adds only descriptive origin/host-boundary cases, not duplicate
checks. Equal canonical procedures do not establish equal host guides.

기존 검사는 canonical 절차/catalog·reader/features 바이트 일치, 결정적 생성,
portable ZIP mode, 닫힌 파일 목록과 거부 사례를 다룹니다. native 파일 목록,
launcher/runtime·문서 검사도 기존 담당을 유지합니다. 이번 fixture는 출처/호스트 경계만
설명합니다. canonical 절차가 같다는 사실로 호스트 guide까지 같다고 판단하지 않습니다.

## Deferred verification / 통합 후 검증

No tests, lint, generators, builds, package checks, release downloads, browser QA,
or live-host/model calls were run. The seven cases are synthetic labels only.
No integrated candidate has been supplied to S030. Runtime transitive contents,
final package hashes, installed priority, reading, application and usefulness
remain unknown.

검사·lint·생성·빌드·패키지 검사·릴리스 다운로드·브라우저 QA·호스트/모델 호출을 하지
않았습니다. 합성 사례는 라벨뿐입니다. 통합 동결 후보를 전달받지 않았으며 runtime의
전이적 내용, 최종 해시, 설치 지침 우선순위, 읽기·적용·유용성은 미확인입니다.

After S001 freezes an exact integration SHA, the assigned verifier can parse this
JSON, inspect the two-file scope, and resolve the relative README link. Expected
results are valid JSON, exactly the owned README/JSON in the S030 commit, and an
existing JSON target. These are proposed checks, not executed results. Reuse the
central final suite's evidence for unchanged package behavior; do not rerun its
checks solely for this descriptive fixture.

S001이 통합 SHA를 동결한 뒤 담당자가 JSON 구문, S030 커밋의 두 파일 범위와 README의
상대 링크를 확인합니다. 예상값은 유효한 JSON, 소유 README/JSON 두 파일만의 변경과
존재하는 링크 대상입니다. 아직 실행하지 않은 제안입니다. 패키지 동작은 중앙 최종 검사
근거를 재사용하며 이 명세만을 위해 중복 실행하지 않습니다.
