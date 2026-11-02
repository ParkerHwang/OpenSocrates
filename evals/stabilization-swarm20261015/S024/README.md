# S024 — Antigravity static delivery boundaries / 정적 전달 경계

This is an authored **static specification**, not an executed evaluation. Every
cell and case is `NOT_RUN`; no host result or application receipt is supplied.
Product/runtime changes: **NO_CHANGE**. Source inspection established no new
defect requiring a product fix. Only this README and
[`antigravity-boundaries.json`](antigravity-boundaries.json) are owned by S024.

이 자료는 작성된 **정적 명세**이며 실행 결과가 아닙니다. 모든 셀·사례는
`NOT_RUN`입니다. 새 제품 결함을 입증하지 않았으므로 제품·런타임 변경은
**NO_CHANGE**입니다. 설치·규칙 활성화·관리 addon 실행을 하지 않습니다.

## Source identity / 기준

- Assigned and remotely compared `main`:
  `227a528996d93c423851db1d663f9572be534e59`.
- Product `1.5.2`, content revision `5`, ten locales and 48 methods per locale.
- `source_references` pins public source paths, relevant line ranges and complete
  source-file SHA-256 values. These are provenance, not executed check results.
  Pins describe the assigned baseline, not a later integrated tree; reconcile
  intended source drift explicitly when integrating.
- Requested authoring service tier: `priority`; observed server tier: `null`.
  No experimental model call was made or budgeted here.

배정 SHA와 원격 `main`은 준비 시점에 일치했습니다. JSON의 소스 해시는 출처를
고정하며 검사 통과를 뜻하지 않습니다. 실제 서버 tier는 관측하지 않았습니다.

## Delivery chain / 전달 계층

| Layer / 계층 | Relative reference / 상대 참조 | Base / 기준 위치 |
| --- | --- | --- |
| `always_on` rule → controller | `@../skills/opensocrates/SKILL.md` | Installed rule directory / 설치 rule의 디렉터리 |
| Controller → reader | `references/reader/guide.{en,ko}.md` | Skill directory containing `SKILL.md` / 스킬 루트 |
| Controller → decision guide | `references/decision/guide.{en,ko}.md` | Skill directory / 스킬 루트 |
| Decision guide → metadata | `features.json`, `catalog.<locale>.json` | `references/decision/` |
| Catalog → complete procedure | `methods/<locale>/<id>.md` | `references/decision/` |

`@` marks the source reference; it is not a filesystem path component. The rule
reference is relative to the rule, never to a shell working directory. The
Antigravity builder deliberately renders the controller from
`plugin-src/claude-chat/SKILL.md.tmpl` and copies that profile's file-delivery
guides; it does not use the native decision-command guide.

Catalog entries contain `id`, `use_for`, `routing`, `sha256` and `path`.
`evidence: metadata_only` is explicit. Zero to two eligible methods may be
selected. Metadata, a name or a footer cannot replace a complete current
canonical read, exact method ID/revision, eligibility, stops and expressly
required dependency reads. Reader guidance or ordinary work may suffice.

rule의 상대 참조 기준은 rule 파일의 디렉터리입니다. controller는 계정 스킬과
공유하는 템플릿에서 생성되며 파일 전달용 안내를 사용합니다. 카탈로그는
메타데이터입니다. 0~2개의 적합한 방법을 선택할 수 있으나 이름·메타데이터·푸터를
정본 전체 읽기로 간주하지 않습니다. 일반 작업이나 독자 안내만으로 충분할 수
있습니다. EN/KO 경로와 접지 규칙을 함께 명세했습니다.

## Origins and collision assumptions / 범위와 충돌 가정

| Scope / 범위 | Rule | Controller |
| --- | --- | --- |
| Workspace | `<WORKSPACE>/.agents/rules/opensocrates.md` | `<WORKSPACE>/.agents/skills/opensocrates/SKILL.md` |
| Global | `<CONFIG>/rules/opensocrates.md` | `<CONFIG>/skills/opensocrates/SKILL.md` |

The global default is `~/.gemini/config` on Mac and
`%USERPROFILE%\.gemini\config` on Windows. The existing installer supports
`ANTIGRAVITY_CONFIG_DIR`; this fixture changes no environment setting. Both
origins preserve the same `../skills/opensocrates/SKILL.md` rule reference.
Global files may affect the conversation app and IDE. Choose one active origin.
Equal `opensocrates` names do not prove deduplication or host precedence.

Existing lifecycle source rejects unowned same-name targets, a legacy
`plugins/opensocrates` collision, changed inventory and replaced disabled
targets. These are source-defined expectations, not newly observed rejections.
User `GEMINI.md`, `AGENTS.md` and unrelated rules remain outside the owned
surface. Disabling/removing files cannot erase already loaded conversation
context; the guides require a fresh conversation for that observation.

workspace/global은 같은 상대 참조를 유지하지만 서로 다른 출처입니다. 같은
이름만으로 중복 제거·우선순위가 입증되지 않습니다. 한 출처를 선택하며 기존
사용자 지침과 소유권 없는 충돌 파일을 덮어쓰지 않습니다. 전역 파일은 앱과
IDE에 영향을 줄 수 있습니다. 비활성화·삭제 후 기존 대화의 문맥이 사라졌다고
간주하지 않습니다. 소유권·충돌 예상은 소스에 근거하며 실행 결과가 아닙니다.

## Payload and evidence limits / 콘텐츠와 근거의 한계

The no-runtime claim covers the distributed content payload. It does not deny
the separate build tools or lifecycle installer. The manifest declares one
public skill, no launchers and no runtime targets; the verifier has a closed
inventory and excludes hook/executable surfaces. The controller declares no
native runtime or extra selector-model request. No credentials, telemetry,
installation, global setting or native application receipt is introduced here.

Four cells remain separate: Mac workspace, Mac global, Windows x64 workspace,
and Windows x64 global. All use invented roots and all remain `NOT_RUN`.
Forward-slash paths are lexical display only; they do not simulate Windows
filesystem, DACL, reparse or host behavior. Discovery, full read, reported
application and useful output remain separate, unknown observations. No
historical Mac or Windows result is imported as a pass for these cells.

런타임 없음은 배포 콘텐츠의 범위입니다. 별도 생성 도구·설치 도구의 존재를
부정하지 않습니다. Mac/Windows × workspace/global 네 셀을 분리하고 모두
미실행으로 둡니다. 합성 경로는 실제 파일 시스템 검증이 아닙니다. 발견·전체
읽기·적용 보고·유용성은 각각 미확인입니다. 실제 작업공간 내용·스크린샷·로그·
인증정보·대화·숨은 추론은 수집하지 않습니다.

## Existing work and historical exclusion / 중복 작업·구형 문서 제외

Read-only searches covered open/closed Antigravity issues and PRs, including
issues #100/#102 and PRs #104/#105/#130. At preparation, #130 was an open Draft
at `197b317b4aeca4928fabe515dbfef6a98803e568`, based on the assigned `main`.
It adds native-envelope documentation to the shared `features.json` bytes that
Antigravity copies. That does not add a native runtime. This fixture accepts
that additive metadata, keeps file delivery, and duplicates no rejection/repair
implementation or #130 fixture.

`docs/antigravity-support.md` explicitly marks its old plugin integration
historical and removed/unsupported. Its `config/plugins/opensocrates` layout and
old receipts do not qualify current modular origins. Current scope references
are the Antigravity templates, builder, and `docs/macos-v1.5.md` /
`docs/windows-v1.5.md`.

#130의 이미 구현된 요청 오류·복구 변경은 다시 작성하지 않습니다. 공유 메타데이터가
추가되어도 Antigravity는 파일 전달형 콘텐츠입니다. 구형 Antigravity 문서와 그
관찰은 현재 모듈형 경로나 네 셀의 통과 근거로 사용하지 않습니다.

## Deferred integration checks / 통합 후 검사

S091/S001 should select the two files, record the integrated SHA and freeze the
candidate. A designated verifier may then inspect JSON syntax/source pins and
the lexical chain in its disposable checkout. The existing focused command is:

```sh
uv run --locked python tools/check_content_hosts.py
```

Expected existing-check coverage: deterministic content layouts, canonical
parity, the rule's installed relative reference, one public skill, and rejection
of extra/tampered/executable package members. It does **not** load this new JSON
fixture or execute a conversation-app cell. No new runner was requested or added.
Do not repeat an already successful identical candidate check unnecessarily.
Native installation, activation, browser QA, model calls and live receipts need
separate authorization/resources and are outside this static task.

위 명령은 실행하지 않았습니다. 동결된 통합 SHA에서 지정 검증 담당자가 기존
검사를 수행하고, 새 JSON은 정적 명세로 별도 확인합니다. 기존 검사 성공을
새 fixture 실행·실제 앱 적용·유용성 입증으로 바꾸지 않습니다. 작성 세션의
검사 결과를 만들지 않습니다.
