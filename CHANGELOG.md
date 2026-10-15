# Changelog

## [1.6.0] - Unreleased

- Migrate active first-party runtime, CLI, lifecycle, updater, generation,
  validation, governance and release tooling to Go; native users require no
  Python, Node.js, npm or Go toolchain. Preserve the released v1.5.2 revision-5 content
  baseline: 48 methods, 480 complete procedures, 3,840 canonical cases and 1,440 teacher
  questions across ten languages, retaining the four earlier languages' authored bodies.
  Separate method-body upgrades are excluded and belong to v1.6.1 or later.
- Refactor typed services/contracts, distribution profiles versus runtime
  adapters, package transport, shared transaction/recovery, host registration
  and OS protection while preserving wire/state/serialization/hook boundaries.
  Port legacy SDK compatibility to a separate external Codex app-server adapter.
- Add native GitHub Release bundle distribution, explicit one-time npm adoption,
  durable recovery and versioned bundles separated from user state. Preserve
  owned settings, registrations, hook trust and disabled integrations; maintain
  one update owner and do not broadly uninstall npm packages/user data.
- Add opt-in stable Codex scheduled updates for macOS ARM64 and Windows x64/ARM64,
  signed metadata verification, expiry/rollback/compatibility guards and Go
  helper support for executable self-replacement. Major/breaking-schema updates
  are not automatic; reload/fresh-session and account-upload boundaries remain.
- Intentionally reject duplicate JSON keys/unpaired Unicode surrogates and
  validate complete decision requests before changing context/scope, so malformed
  routing cannot erase previous availability. Preserve unsafe/newer settings
  instead of overwriting them with defaults. Purge preflights every removable
  payload before mutation; explicit trust reset stays limited to seven entries. Preserve --host all as Codex only;
  native Windows Claude Code/additional platforms remain excluded.
- Candidate only: exact final checks belong in the implementation handoff.
  Native/clean-machine/live host qualification, production trusted root/signing,
  platform signatures and published asset verification remain release gates.
  No merge, tag, publication or active-installation replacement is implied.
- 활성 실행·설치·갱신·생성·검증·릴리스 도구를 Go로 전환합니다. 사용자는
  Python·Node.js·npm·Go를 설치하지 않습니다. 출시된 v1.5.2 콘텐츠 리비전 5와 방법
  48개·열 언어의 전체 절차 480개·정본 사례 3,840개·교사 질문 1,440개,
  기존 네 언어 본문을
  유지하고 본문 개선은 후속 릴리스로 분리합니다.
- 공통 작업·복구와 명확한 서비스·프로필·OS 보호를 정리하고 네이티브 배포·
  일회성 npm 인수·Mac ARM64·Windows x64/ARM64의 선택적 Codex 서명 안정 갱신을 추가합니다.
  기존 설정·신뢰·비활성 상태와 단일 업데이트 소유자를 보존합니다.
- 중복 JSON 키·짝 없는 surrogate와 잘못된 판단 요청을 문맥·scope 변경 전에
  거부하고 안전하지 않거나 새 설정은 덮어쓰지 않습니다. purge는 모든 제거
  대상을 먼저 확인하며 신뢰 초기화는 정확한 항목 7개만 다룹니다. --host all은 Codex만
  선택하며 계정 업로드·진행 중 대화 적용·새 플랫폼을 자동 지원하지 않습니다.
  운영 서명·네이티브·새 기기·실제 호스트 증거가 필요한 미출시 후보입니다.

- Clarify substantive-thinking support at the first need and later material
  changes across the four host profiles and ten instruction locales. Distinguish
  prescribed mechanical execution from reasoning with a fixed answer, and
  consideration/reader guidance from eligible canonical-method application.
  Preserve the 48 authored procedures, method revision 5, routing contracts,
  privacy, required stops and fail-open ordinary work. Controller edits change
  bundle/package hashes; no published release, incident #124 fix, live application
  or quality improvement is established by this source change.
- 네 호스트 프로필과 열 언어에서 실질적인 사고가 처음 필요할 때와 이후 중요한
  변화가 있을 때의 지원 범위를 명료하게 합니다. 정해진 수행 절차와 정답이 있는
  추론을 구분하고, 지원 검토·독자 안내·적격한 정본 방법 적용을 나눕니다. 사고 방법
  48개의 본문과 리비전 5, 라우팅 계약, 개인정보 보호, 필수 중단 조건과 일반 작업의
  fail-open 처리는 유지합니다. 컨트롤러 변경으로 번들·패키지 해시는 달라지며,
  이 소스 변경만으로 출시, #124 해결, 실사용 적용이나 품질 향상을 주장하지 않습니다.

## [1.5.2] - 2026-10-13

- Add French (`fr`), German (`de`), Italian (`it`), Spanish (`es`), Portuguese
  (`pt`) and Thai (`th`) to the existing English, Korean, Simplified Chinese and
  Japanese content across all four host profiles. Provide 480 complete procedure
  files, 3,840 canonical cases and 1,440 teacher questions for 48 methods in ten
  languages. Portuguese uses Brazilian orthography under the generic `pt` code;
  separate regional variants are not claimed.
- Advance bundle, overlay and individual method identity to content revision 5.
  Preserve the existing four languages' authored procedure/case body bytes and
  metadata/question values; prior revision 4 read evidence does not become
  revision 5 evidence merely because body text is unchanged.
- Extend closed runtime preferences, decision JSON locales and package inventories
  to all ten languages. Preserve explicit preference over stored preference,
  then script detection; add dominant Thai-script detection and retain Kana
  priority. Latin-script European languages require an explicit or stored choice;
  ties, empty input and unknown scripts use English. Keep complete historical
  two-/four-language runtime content compatibility without silently upgrading it.
- Add six native-language READMEs, current settings/language guides and a separate
  language-review record. Preserve the four existing profiles, Mac ARM64 and
  Windows x64 qualification, privacy, attribution, ownership, rollback and
  fail-open boundaries. Go migration and Windows ARM64 remain v1.6.0 work.
- 기존 영어·한국어·간체 중국어·일본어에 프랑스어·독일어·이탈리아어·스페인어·
  포르투갈어·태국어를 추가합니다. 열 언어·사고 방법 48개의 전체 절차 480개,
  정본 사례 3,840개, 교사 질문 1,440개를 네 호스트 프로필에 제공합니다.
  포르투갈어는 일반 `pt` 코드와 브라질식 철자를 사용하며 지역별 지원을
  별도로 주장하지 않습니다.
- 번들·오버레이·개별 방법의 콘텐츠 리비전은 5로 바뀝니다. 기존 네 언어의
  절차·사례 본문 바이트와 메타데이터·질문 값은 유지합니다. 본문이 같다는
  이유로 리비전 4의 읽기 증거를 리비전 5의 증거로 간주하지 않습니다.
- 폐쇄된 언어 선호·판단 JSON·패키지 목록을 열 언어로 확장합니다. 명시적
  선호 → 저장 선호 → 문자 판별 순서를 유지하고 태국 문자 우세 판별을
  추가합니다. 가나 우선순위를 유지하며 라틴 문자 언어에는 명시적·저장
  선택이 필요합니다. 동률·빈 입력·알 수 없는 문자는 영어입니다. 완전한
  과거 두 언어·네 언어 콘텐츠의 런타임 호환성을 유지하되 새 언어로 자동
  변경하지 않습니다.
- 여섯 언어 README와 현재 설정·언어 안내, 별도 언어 검토 기록을 추가합니다.
  기존 네 프로필·Mac ARM64·Windows x64 검증 범위와 개인정보·사용 표기·
  소유권·롤백·fail-open 경계를 유지합니다. Go·Windows ARM64는 v1.6.0입니다.

## [1.5.1] - 2026-10-13

- Add Simplified Chinese (`zh`) and Japanese (`ja`) alongside English and Korean
  across the 48 authored reasoning methods, canonical examples, teacher-question
  overlay, locale messages and four host instruction packages. Ship 192 complete
  procedure files and 576 teacher questions; content revision 4 preserves the
  original English/Korean authored method text.
- Resolve reasoning locale through explicit preference, stored preference and
  current-input script detection. Kana identifies Japanese; Han-only text
  defaults to Chinese and needs an explicit Japanese preference when ambiguous.
  Empty, Latin-only and tied inputs fall back to English.
- Add Chinese/Japanese READMEs and version-pinned installation commands. Preserve
  v1.5.0 host/platform boundaries, conditional attribution, privacy, fail-open
  behavior and lifecycle ownership. Windows ARM64 remains separate v1.6.0 work.
- 사고 방법 48개, 정본 사례·교사 질문·언어 메시지·네 호스트 지시문에 간체
  중국어(`zh`)와 일본어(`ja`)를 추가합니다. 전체 절차 192개와 교사 질문
  576개를 제공하며 콘텐츠 리비전 4에서 기존 영어·한국어 방법 본문을 유지합니다.
- 명시적 선호 → 저장된 선호 → 현재 입력의 문자 순으로 언어를 선택합니다.
  가나가 있으면 일본어, 한자만 있으면 기본 중국어이며 일본어를 명시할 수
  있습니다. 빈 입력·라틴 문자만 있는 입력·동률은 영어로 돌아갑니다.
- 중국어·일본어 README와 버전 고정 설치 안내를 추가합니다. v1.5.0의 호스트·
  플랫폼·조건부 사용 표기·개인정보·fail-open·설치 소유권 경계를 유지합니다.
  Windows ARM64는 별도 v1.6.0 범위입니다.

## [1.5.0] - 2026-10-10

- Preserve the v1.4 Codex baseline and all 48 authored reasoning methods with
  complete English/Korean procedures. Add reader guidance for source
  reconciliation, stakeholder context, decisions and useful messages.
- Add bounded, stateless native Claude Code entry on Apple-silicon Mac, a separate
  executable-free Claude account skill ZIP, and modular Antigravity conversation
  application rules/skills on Apple-silicon Mac and Windows x64.
- Support Claude web Chat, Desktop Chat and Cowork through account ZIP
  verification/export on Mac and Windows. Upload and activation remain separate
  account UI operations. Native Windows Claude Code is outside the release scope.
- Add owned native Claude/Antigravity install, update, status, diagnose, disable,
  enable and remove; preserve disabled state on update. Add Windows owner/DACL,
  ancestor protection, reparse refusal, safe ZIP extraction and recoverable rollback,
  native filesystem regressions, portable 0644 archive modes and Windows SBOM/CI.
- Unify conditional attribution across profiles as the exact final line
  `Powered by OpenSocrates`. Require an eligible authored method to be read in
  full and actually applied; reader guidance alone and mechanical work do not
  qualify. Keep structured method identities/revisions, read receipts and repair
  behavior unchanged. Attribution does not prove native application or better results.
- Publish version-pinned installation/update guides for Mac and Windows.
  The default and `--host all` still select Codex; new profiles require an explicit
  host and have no purge, trust-reset or automatic-update route.
- Tighten EN/KO reader guidance for absent source mentions, settled follow-up
  facts, persistent unknowns and unauthorized draft commitments. Preserve dated
  observations; source checks do not regrade historical outcomes or establish
  universal quality, token-cost or latency gains.
- v1.4 Codex와 정본 사고 방법 48개·영어·한국어 전체 절차를 유지하고, 자료·
  이해관계자 맥락·판단·메시지를 위한 독자 안내를 추가합니다. Apple Silicon
  Mac의 Claude Code 네이티브 연동, Mac·Windows의 계정 ZIP 검증·내보내기,
  Mac·Windows x64의 Antigravity 작업공간·전역 설치 상태 관리를 제공합니다.
- Windows Claude Code 네이티브 연동은 이번 범위에서 제외합니다. 계정 업로드·
  활성화는 계정 화면에서 별도로 진행합니다. 업데이트는 비활성화 상태를
  유지하며 기본값과 `--host all`은 계속 Codex를 선택합니다.
- 정본 전체를 읽은 적격한 방법을 실제로 적용했을 때만 마지막에
  `Powered by OpenSocrates`를 그대로 표시합니다. 독자 안내만 사용하거나
  기계적인 작업만 했다면 표시하지 않으며, 문구 자체는 적용 증명이 아닙니다.
  과거 관찰은 당시 결과로 보존하고 일반적인 품질·비용·속도 향상은 주장하지 않습니다.

## [1.4.0] - 2026-09-16

- Focus OpenSocrates on Codex only. Remove Claude Code/Cowork/Chat,
  Antigravity, Cursor, Grok Build and OpenCode runtime adapters, selectors,
  templates, install choices and release archives. `--host all` now means Codex.
- Preserve the 48 authored methods, all English/Korean procedures, native Codex
  hooks, integrity checks, safe lifecycle rollback and explicit trust reset.
- Reject retired-host desired state without changing it. Use the previous
  installer version to remove retired integrations before updating Codex.
- Codex 전용으로 전환하며 다른 호스트 연동과 배포 파일을 제거합니다. 48개 사고
  방법과 영어·한국어 절차, 무결성·롤백·훅 신뢰 경계는 유지합니다. 이전 버전의
  다른 호스트 설치는 해당 버전으로 제거한 다음 Codex를 업데이트해야 합니다.

- Add native Windows x64 runtime archives, Node launcher and Windows CI builds.
- Preserve SHA-256 inventories; reject Windows ZIP aliases, traversal and links before extraction.
- Validate Windows owner ACLs, binary I/O, file locks and explicit manual-update behavior.
- Keep macOS release gates; distinguish native package tests from authenticated host and Desktop delivery.
- Windows x64 네이티브 배포·런처·CI, ACL·바이너리 입출력·잠금·ZIP 검사를 추가합니다. 자동 업데이트는 수동 실행 안내로 명시하며 실제 호스트와 Desktop 검증 범위를 구분합니다.

See [Windows support](docs/windows-support.md) / [Windows 안내](docs/windows-support.ko.md).

## [1.3.0] - 2026-09-08

- Add agent-directed method retrieval at decision points within an existing turn,
  reusing canonical content and the deterministic router. Mechanical work can
  pass through without loading a method. Delivery, reported availability and
  application evidence remain distinct.
- Generate separate English/Korean canonical references for all 48 methods and
  six hosts. Codex discovery now exposes the controller, rigor and trace; previous
  per-method invocations migrate through the controller with unchanged Method IDs.
- Prevent weighted-primary and fallback routing from bypassing contraindications;
  reject malformed feature lists without silently choosing a fallback.
- Preserve authored procedure bodies and prior rejected experimental baselines.
  No Compact, method-variant or language rewrite is promoted.
- Add conservative presentation-only EN/KO Guided rules and full visible-output
  measurements while preserving required cards, evidence, stop conditions and user formats.
- Avoid first-use hook storage initialization, retain safe existing artifact cleanup,
  and provide a persistent packaged decision stream.
- Separate Chat export validation from cloud activation and postpublication provenance.
  Release evidence and remaining host limits are recorded in
  [the release record](docs/v1.3.0-recovery/PROGRESS.md).


All notable changes to OpenSocrates are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [1.3.1] - 2026-09-09

### Fixed

- Read one bounded JSON document through EOF in one-shot `decision` mode, so the
  documented pretty-printed packaged request reaches the native selector once.
  `--stream` remains newline-delimited JSON, and malformed or oversized input
  retains the fail-open unavailable result.
- Require GitHub's platform immutable-release setting before future release
  publication and verify the published release's `immutable` API field before
  npm publishing. This is distinct from the existing workflow rule that refuses
  to overwrite an existing tag or asset set.
- Reconcile the v1.3.0 Codex evidence table with P11: an in-request native call
  and complete references were observed, while submit-hook delivery, feature
  classification, actual application, Desktop GUI, and cloud activation remain
  separate or unverified.
- Converge concurrent same-machine lifecycle inspectors on one atomically
  published `blocked_unverifiable` receipt instead of letting the losing
  inspector fail on an exclusive-create race.

## [1.2.1] - 2026-08-16

### Added

- A committed v1.2 adjudication snapshot records 51 EN/KO semantic pairs,
  49 resolved disagreements, strict Draft 2020-12 schemas, aggregate counts,
  and hashes. Its clean-clone validator and mutation suite check only public
  repository artifacts; maintainer-held packet, reviewer, and raw-result
  evidence remains explicitly unavailable in public mode.
- `remove --host <host|all> --purge` provides an explicit, idempotent
  complete-uninstall attempt for exact OpenSocrates registrations, verified
  host cache payloads, empty Claude plugin-data directories, OpenCode-owned
  files, the updater, transaction residue, and final installer state.
- `remove --host <codex|all> --purge --reset-trust` explicitly resets only the
  seven canonical OpenSocrates Codex hook approvals after validating a narrow,
  transactional config update.
- A same-machine reinstall acceptance workflow binds the candidate commit,
  native artifacts, packed npm installer, purge and reinstall lifecycle,
  manual observations, privacy-safe result bundle, and guarded cleanup without
  presenting the machine as clean-machine evidence.

### Changed

- All six generated host packages now carry the same bilingual, three-question
  teacher overlay while preserving their real delivery models: hidden trusted
  hook context for Claude/Codex, explicit content reads for Antigravity/Cursor,
  native skill content for Grok Build, and one question-led compiled procedure
  with the same native fallback for OpenCode.
- Hook budget fallback now drops teacher questions before binding guardrails,
  instruction artifact schema `/3` reads in-flight `/2` headers with an empty
  question default, and empty or malformed question data no longer refers to
  absent questions.
- The teacher-question source now has a generated canonical schema and explicit
  overlay identity checks without changing authored per-method content revision
  `1`.
- Ordinary `remove` now states its narrower registration/managed-root contract,
  reports known remaining OpenSocrates paths, and points to the purge command
  instead of implying that every installed payload was removed.
- Installer help and English/Korean removal docs now distinguish plugin
  registration, owned payloads, host security trust, and preserved user history.
- Claude Code, Desktop Local, and Cowork plugin documentation now uses the
  canonical `/opensocrates:opensocrates` namespace, while the separately
  rendered Claude Chat standalone skill keeps `/opensocrates`. Release checks
  reject either command when it appears in the wrong artifact.
- Claude evidence now keeps the installer-managed local plugin, a manually
  uploaded standalone Chat ZIP, and the pre-existing synced/custom skill as
  separate provenance states. The historical v1.1.2 live receipt remains
  historical, while current-version checks require a version-bound receipt.
- Codex SessionStart timing evidence now measures `startup` and `compact`
  independently and requires both source sets to pass before release or
  reinstall acceptance can report the timing budget as verified.
- The exact public v1.2.1 Chat ZIP, checksum, and release commit were unavailable
  at the 2026-08-15 provenance audit. The current Chat receipt and EN/KO
  documentation therefore keep live upload pending instead of inheriting the
  v1.1.2 validation claim.

### Security and privacy

- Release-package checks reject evaluation or adjudication paths in every host
  and Claude Chat ZIP. The npm package remains restricted to the installer and
  its public release documents, so source evaluation artifacts do not ship.
- Purge verifies canonical non-symlink paths, exact package identity,
  manifests, checksums, and ownership markers; live `.in_use` payloads,
  unverified registration, unknown data, and cleanup failures remain pending.
  Unrelated host configuration and user history are preserved. Codex hook trust
  remains preserved unless the explicit reset flag is supplied.
- The trust reset refuses symlinks, hard links, noncanonical or unexpected
  matching sections, invalid configs, concurrent changes, and failed Codex
  consumption checks. It preserves non-target bytes and restores the exact
  original when rollback remains safe; a later external edit is never
  overwritten.
- Chat evidence stores only release/archive identity, counts, versions,
  pass/fail booleans, and categorical provenance/routing states. The missing
  exact release artifact at audit time prevented a UI upload attempt, so no
  authentication, 2FA, user-confirmation, prompt, conversation, account, path,
  raw UI, upload content, or credential boundary was crossed.

## [1.2.0] - 2026-08-13

### Added

- Experimental Google Antigravity integration as a content-only global plugin
  with one explicit `opensocrates` skill, 48 internal authored procedures,
  isolated lifecycle ownership, and an `agy 1.0.6` package-validation receipt.
  It deliberately ships no hooks, runtime, background process, or automatic
  selector.
- Experimental Cursor Agent Plugin integration with one `/opensocrates` skill,
  48 internal authored procedures, isolated lifecycle ownership, and
  release-gate package validation. It adds no OpenSocrates selector or hook,
  and no live Cursor invocation receipt is claimed.
- Grok Build is a first-class `grok` installer host with one native,
  auto-selectable `/opensocrates` skill, 48 internal authored procedures,
  deterministic content-only packaging, capability reporting, isolated
  lifecycle ownership, release-gate coverage, and English/Korean support
  documentation. Live Grok Build 1.0.3 evidence bounds automatic activation,
  explicit invocation, hook behavior, and remaining TUI/subagent limitations.
- First-class OpenCode 1.18.18+ integration using the stable `chat.message`
  hook for live-validated same-turn local activation and a native
  `opensocrates` Agent Skill fallback.
- Provider-neutral, dependency-free OpenCode bridge with bounded input,
  duplicate prevention, and exception fail-open behavior. A live
  DeepSeek V4 Flash smoke test is recorded without embedding provider settings.
- OpenCode install, status, verify, update, remove, rollback, automatic-update,
  and `--host all` lifecycle support with exact-path ownership and complete
  installed inventory verification.
- Deterministic OpenCode package generation, release-gate validation,
  capability reporting, privacy-safe compatibility evidence, and English and
  Korean support documentation.

### Fixed

- Pre-release and offline `--host all` transactions now treat supplied
  host-qualified asset pairs as the exact host set. Candidate packages are no
  longer mixed with public-release downloads merely because another supported
  host CLI is available on the machine.

### Security and privacy

- The OpenCode installer never rewrites `opencode.json`; it refuses unowned,
  partial, symbolic-link, and unsafe exact paths while preserving unrelated
  plugins, skills, and configuration.
- The OpenCode bridge makes no network, subprocess, recursive OpenCode, extra
  model, telemetry, or credential access and preserves the complete-procedure
  grounding requirement.

## [1.1.5] - 2026-08-12

### Added

- Packaged `diagnose` now verifies the complete installed file inventory
  against `checksums.sha256` and validates the release manifest's runtime
  version, host, and content revision. Explicit `mismatch`, `unavailable`, and
  `unverified` states replace presence-based claims
  ([#64](https://github.com/ParkerHwang/OpenSocrates/issues/64)).
- Release tests execute the packaged runtime against both intact packages and
  a staged tampered Claude package so integrity reporting is exercised outside
  the source process ([#64](https://github.com/ParkerHwang/OpenSocrates/issues/64)).

### Changed

- Claude grounding artifacts now prefer an owner-only, self-ignored
  `.opensocrates` area inside the active workspace, while retaining the OS
  temporary directory as a fail-open fallback. Lookup, receipts, expiry, and
  cleanup handle both roots during upgrades and fallback runs
  ([#62](https://github.com/ParkerHwang/OpenSocrates/issues/62)).
- Codex package and installation documentation now requires one interactive
  hook approval before automatic selection is expected and distinguishes
  release-validated packaging from unvalidated live hook delivery
  ([#63](https://github.com/ParkerHwang/OpenSocrates/issues/63)).

### Fixed

- Default-permission `claude -p` sessions can read selected grounding content
  without `--add-dir`, avoiding the denied-read repair loop caused by placing
  artifacts only in the system temporary directory
  ([#62](https://github.com/ParkerHwang/OpenSocrates/issues/62)).
- `diagnose` no longer reports manifest and checksum verification merely
  because package files exist ([#64](https://github.com/ParkerHwang/OpenSocrates/issues/64)).

## [1.1.4] - 2026-08-12

### Added

- A privacy-safe Claude selector aggregate records only bounded counts under a
  closed outcome vocabulary. `diagnose` exposes those counts without prompts,
  transcripts, session identifiers, paths, model output, credentials, or
  selector reasoning ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- A sanitized Cowork receipt validates local plugin upload and the native
  `UserPromptSubmit` → `PostToolUse(Read)` → `Stop` lifecycle, including the
  authenticated grounding receipt and final cleanup
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).

### Changed

- Native runtime builds are split by host profile. The Claude package excludes
  the Codex SDK and CLI while the Codex package preserves its existing runtime
  surface ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- Release tooling derives artifact paths from the detected native target,
  defaults plugin generation to `dist/runtime/<host>`, and interprets Cowork's
  50 MB and 200 MB limits conservatively as decimal bytes
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).

### Fixed

- The Claude runtime now uses PyInstaller's no-archive mode, and release checks
  reject nested ZIP entries before a Cowork package can be published
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- Unreadable selector aggregates report `unavailable` instead of zero attempts.
  Malformed current-schema documents self-heal on the next valid outcome while
  unknown future schemas are preserved
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).

## [1.1.3] - 2026-08-11

### Added

- Bounded semantic packaged-README checks now reject novel universal-support,
  vendor-endorsement, and managed-environment safety overclaims, with mutation
  coverage that also protects accurate limitation wording from false positives
  ([#27](https://github.com/ParkerHwang/OpenSocrates/issues/27)).
- Native plugin packages now expose one honest `darwin-arm64` boundary: the
  unvalidated PowerShell launcher is removed, the POSIX launcher rejects every
  other target, and package manifests and docs distinguish unshipped build
  candidates from the released platform
  ([#12](https://github.com/ParkerHwang/OpenSocrates/issues/12)).
- A Claude Chat upload probe records the exact verified v1.1.2 skills ZIP
  shape and hash, live uploader acceptance, single visible skill entry,
  catalog routing, representative method loading, and grounding audit without
  retaining prompt or conversation content
  ([#5](https://github.com/ParkerHwang/OpenSocrates/issues/5)).
- A privacy-safe Cowork probe validates the separately uploaded
  `/opensocrates` skill and corrects the installation boundary: Claude Code CLI
  marketplace registration is not a Cowork-native plugin install. The exact
  published v1.1.2 plugin archive is rejected by Cowork's upload-size limits,
  and repository sync is unavailable without a marketplace manifest, so native
  hooks remain blocked
  ([#4](https://github.com/ParkerHwang/OpenSocrates/issues/4)).
- A privacy-safe Claude Code desktop live probe now validates a complete
  authenticated UserPromptSubmit → PostToolUse(Read) → Stop lifecycle. It
  observes the owner-only instruction artifact, authenticated grounding
  receipt, and final cleanup without retaining prompts, transcripts, paths,
  credentials, payloads, or selector reasoning
  ([#3](https://github.com/ParkerHwang/OpenSocrates/issues/3)).
- A reproducible packaged `darwin-arm64` timing harness verifies PostToolUse
  receipt creation and Stop cleanup across fresh-path and warm runs. All 80
  measured operations completed, the worst p95 was 1,333.067 ms against the
  3-second budget, and no timeout change is recommended
  ([#6](https://github.com/ParkerHwang/OpenSocrates/issues/6)).
- An opt-in Claude structured-output matrix runs 20–50 bounded attempts per
  explicitly requested model, requires 95% valid envelopes, and stores only
  aggregate fixed outcome counts. The authenticated Claude Code 2.1.226
  `host-default` row passed 20/20 attempts with every failure outcome at zero;
  no unobserved named model is claimed
  ([#8](https://github.com/ParkerHwang/OpenSocrates/issues/8)).
- An opt-in, privacy-safe real Claude selector contract verifies the exact
  isolation command, environment allowlist, temporary workspace, and real
  subprocess failure categories. An authenticated, non-sensitive live call on
  Claude Code 2.1.226 returned `selected`, removed its temporary workspace, and
  retained no prompt, raw output, credential, or selector reasoning
  ([#7](https://github.com/ParkerHwang/OpenSocrates/issues/7)).
- Sanitized Claude Code payload receipts for the complete v1.1.2 hook
  lifecycle — `SessionStart`, `UserPromptSubmit`, `PostToolUse`, `Stop`, and
  `SessionEnd` — captured from a supported runtime and compared field by field
  with the shared adapter mapping. The checks assert that `prompt_id` is
  projected into turn identity, that `last_assistant_message` reaches the Stop
  decision, that two consecutive turns of one session stay artifact-isolated,
  and that Stop and `SessionEnd` clean up
  ([#9](https://github.com/ParkerHwang/OpenSocrates/issues/9)).

### Fixed

- The Claude Chat skills ZIP now uses the uploader's required single top-level
  `opensocrates/` folder with `SKILL.md` directly inside; the prior plugin-shaped
  archive was rejected by the real Customize → Skills upload UI
  ([#5](https://github.com/ParkerHwang/OpenSocrates/issues/5)).
- The installer now accepts only explicit Claude list JSON variants, rejects
  malformed, duplicate, or conflicting managed entries, surfaces disabled
  plugins as drift, re-enables them on install/update, preserves their state on
  rollback, and emits executable recovery commands after a secondary root
  removal failure ([#11](https://github.com/ParkerHwang/OpenSocrates/issues/11)).
- POSIX and PowerShell launchers now enforce the single generated `bin/`
  package layout and never probe a competing `bin/runtime/` tree
  ([#26](https://github.com/ParkerHwang/OpenSocrates/issues/26)).
- Packaged-launcher checks now derive each host's runtime root from canonical
  `generator.json` metadata and include a mismatch probe that remains
  discriminating when no native runtime targets were built
  ([#25](https://github.com/ParkerHwang/OpenSocrates/issues/25)).
- Claude sessions now supersede private instruction artifacts by `prompt_id`.
  When `Stop` is absent, the next `UserPromptSubmit` removes prior turn trees in
  that session while preserving the new active turn; `SessionEnd` and the
  24-hour `SessionStart` sweep remain backstops
  ([#13](https://github.com/ParkerHwang/OpenSocrates/issues/13)).
- The Claude selector now enforces its 512 KiB stdout ceiling while reading the
  child process stream. Output that crosses the limit terminates and reaps the
  process immediately, fails open with a content-free diagnostic, and is never
  retained or logged ([#10](https://github.com/ParkerHwang/OpenSocrates/issues/10)).
- An ordinary Claude payload no longer reports an unknown field. `effort` was
  present in the captured `PostToolUse` and `Stop` receipts, while
  `background_tasks` and `session_crons` were present in the captured `Stop`
  receipt. They were missing from the parser's known-field sets, so the
  `native_unknown_field_ignored` diagnostic fired on healthy turns. The parser
  still never reads those fields, and no parsing, projection, or gating
  behavior changed.

### Security and privacy

- The committed receipts contain no prompt, transcript, path, credential, or
  user-identifying content. Field names, value types, and container shapes are
  preserved as captured; every sensitive value is a fixed synthetic marker, and
  a check refuses every native-payload string outside a closed vocabulary so a
  future re-capture cannot commit real payload content by accident.

## [1.1.2] - 2026-08-11

### Added

- A Claude `PostToolUse` grounding receipt that is created only after a
  successful `Read` starts at the first line, reaches the instruction
  artifact's terminal marker, and targets the current turn's exact file.
- One bounded `Stop` repair pass when Claude attempts to finish without a
  verified read receipt or the exact public method/revision audit line.

### Fixed

- Selected reasoning methods can no longer silently pass the Claude completion
  gate when the model skips their required reference read and substitutes
  prior knowledge. Each selected method is identified as
  `method-id@content-revision`, and its authored `Do not use when` and
  `Stop conditions` are inlined when they fit the trusted context budget
  ([#32](https://github.com/ParkerHwang/OpenSocrates/issues/32)).
- A grounding read is recognized whatever shape the host uses to deliver the
  `Read` response. The terminator search no longer depends on envelope key
  names, which are not a stable host contract, so a host that wraps the body
  differently no longer looks like an incomplete read and no longer costs a
  compliant turn a repair pass. The search is bounded by an explicit depth limit
  and the existing collection limits.

### Security and privacy

- Grounding receipts are owner-only and authenticated. They contain only the
  instruction artifact digest, content revision, selected method IDs, and
  keyed tags; they never contain prompts, transcripts, tool output, credentials,
  or workspace and artifact paths, and they are removed with the turn artifact.
- The complete `Read` response is inspected transiently for the terminal marker
  and is neither retained nor projected into OpenSocrates records.
- The gate's scope is documented rather than implied. A receipt establishes that
  a successful `Read` callback for the exact current-turn artifact returned
  content reaching the terminal marker; it does not cryptographically prove that
  every artifact byte was returned. A synthetic marker-only payload would
  satisfy the marker test, which the model cannot produce because it does not
  author `tool_response`.

## [1.1.1] - 2026-08-10

### Added

- One-command `--host all` support for install, status, update, remove, and
  verification, backed by one desired-state manifest for the selected channel,
  installed hosts, and active version.
- Cross-host preflight, package verification, staging, activation, and reverse
  rollback so a partial Claude/Codex activation cannot leave a newly selected
  version on only one host.
- Opt-in macOS LaunchAgent updates through `auto-update enable`, `status`,
  `disable`, and the internal scheduled reconciliation command. Checks use a
  bounded interval with jitter, a single-instance lock, compatible-version
  policy, concise local receipts, and an update-target set kept separate from
  the complete installed-host set.

### Changed

- Claude now exposes one `/opensocrates` skill. The 48 method procedures,
  rigor, evidence audit, trace, and status behavior are internal supporting
  references or subcommands instead of separate top-level skills and commands.
- Updating a managed v1.1.0 Claude installation replaces the old multi-skill
  package tree, removing stale top-level method and helper entries.
- `status --host all` reports the desired and available version, last check,
  last successful update, and per-host drift.

### Security and privacy

- Automatic updates remain disabled until explicitly enabled, verify both the
  outer release checksum and complete package manifest before activation, and
  preserve the previous registrations on preflight, verification, staging, or
  activation failure.
- Desired state, locks, and receipts use owner-only permissions. Receipts keep
  only version, time, per-host result, and error category; no prompts,
  transcripts, credentials, or workspace paths are stored.

## [1.1.0] - 2026-08-06

### Added

- Claude Code CLI integration through native Claude plugin hooks and generated
  reasoning skills. Claude Code desktop and Cowork use the same implemented
  mechanism, but live delivery on those surfaces remains unvalidated.
- A bounded `claude --safe-mode -p` selector that uses the existing Claude login,
  disables tools and project/plugin context, accepts only structured output,
  and fails open after the existing 30-second deadline.
- Host-specific `npx` lifecycle support through `--host claude` while keeping
  Codex as the backward-compatible default.
- A separate Claude release package, checksum verification, security boundary
  checks, and offline integration contracts.
- A compact, runtime-free Claude Chat ZIP containing 48 method skills and
  three shared skills for custom-plugin upload.
- A support matrix that distinguishes automatic local hooks from skills-only
  Claude web and Desktop Chat use.

### Fixed

- The packaged POSIX and PowerShell launchers now resolve the native runtime
  from the plugin root (`runtime/<target>/...`) instead of from their own
  `bin/` directory. Previously every packaged Claude and Codex hook took the
  fail-open `missing_runtime` path, so `UserPromptSubmit` selection and
  `Stop`/`SessionEnd` cleanup were silent no-ops in the generated packages
  ([#16](https://github.com/ParkerHwang/OpenSocrates/issues/16)).

### Changed

- The release gate now executes the generated packages' own launchers against
  the packaged runtime layout for Claude and Codex, covering hook dispatch,
  control mode, and the fail-open paths, and it inspects the generated Claude
  package README for its trust-boundary and validation limitations
  ([#16](https://github.com/ParkerHwang/OpenSocrates/issues/16),
  [#22](https://github.com/ParkerHwang/OpenSocrates/issues/22)).
- The Claude package README now states that safe mode leaves managed settings
  policy in force, that policy-configured hooks can still observe the selector
  prompt and influence selection, and it grades Claude Code Desktop, Cowork,
  and Claude Chat validation the same way the repository README does
  ([#22](https://github.com/ParkerHwang/OpenSocrates/issues/22)).
- Release assembly, SBOM input, security scans, and GitHub Release publishing
  now cover both Claude and Codex packages.
- The installer detects case-sensitive pre-1.0 Claude marketplace
  registrations and requires an explicit migration instead of deleting them.

### Security and privacy

- Claude selection receives only the current prompt and authored catalog; it
  cannot read the transcript, workspace, MCP servers, or tools.
- Claude CLI stdout is parsed in memory, stderr is discarded, prompt history
  is disabled, and the process group is terminated on timeout or shutdown.

## [1.0.0] - 2026-07-31

### Added

- Local Codex selector and runtime with a 30-second, no-retry, fail-open
  execution contract.
- An authored catalog of 48 reasoning systems with English and Korean
  user-facing messages.
- Evidence, completion, routing, privacy, trace, and host-contract validation.
- Reproducible Python 3.12 builds, native `darwin-arm64` packaging, checksums,
  SBOM generation, security scanning, and release gates.
- GitHub Release and dependency-free Node.js installation paths, including
  `npx github:ParkerHwang/OpenSocrates#v1.0.0 install`.
- The public `opensocrates` npm package for the shorter
  `npx opensocrates@1.0.0 install` path.
- English and Korean README files and standard open-source community health
  documents.

### Security and privacy

- The selector uses the existing local Codex OAuth session; no API key or
  hosted OpenSocrates backend is required.
- Temporary instruction artifacts contain authored OpenSocrates material only.
- Installer downloads are checked against release and package-level SHA-256
  manifests before installation.

### Known limitations

- The packaged runtime is validated only for Apple-silicon macOS.
- Signing, notarization, clean-machine installation, and live host hook
  delivery remain explicitly unvalidated.

[1.0.0]: https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.0.0
[1.1.0]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.0.0...v1.1.0
[1.1.1]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.0...v1.1.1
[1.1.2]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.1...v1.1.2
[1.1.3]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.2...v1.1.3
[1.1.4]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.3...v1.1.4
[1.1.5]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.4...v1.1.5
[1.2.0]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.1.5...v1.2.0
[1.2.1]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.2.0...v1.2.1

[1.3.0]: https://github.com/ParkerHwang/OpenSocrates/compare/v1.2.1...v1.3.0
