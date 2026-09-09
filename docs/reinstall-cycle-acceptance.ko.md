# 사용 이력이 있는 Mac의 purge 및 재설치 인수 테스트

[English](reinstall-cycle-acceptance.md)

이 절차는 OpenSocrates 설치 이력이 있고 정확한 지원 baseline을 갖춘 Apple Silicon
Mac에서 `purged_same_machine` 인수 테스트를 수행할 때만 사용합니다. clean-machine
테스트가 아니며 그렇게 보고해서도 안 됩니다.

도구는 실제 인증 계정 홈과 패키징된 `npx` 진입점을 사용합니다. 승인된 기존
OpenSocrates 설치를 제거하고 정확한 무잔여 상태를 검증한 뒤 같은 후보로 Claude와
Codex를 재설치합니다. OpenSocrates 소유 등록, payload, cache, data, state,
LaunchAgent와 OpenSocrates Codex 신뢰 항목 7개를 실제로 제거하는 파괴적 테스트입니다.
그 이전 내용은 복원하지 않습니다. 관계없는 호스트 설정, 기록, 플러그인, npm/npx
cache는 열람하거나 삭제하면 안 됩니다.

## 필수 시작 상태

focused Pull Request의 최신 커밋에 대한 Native package CI job이 성공한 뒤 그
체크아웃에서 실행합니다. 다음 조건을 모두 만족하지 않으면 lifecycle mutation 전에
중단합니다.

- macOS 하드웨어와 Node 프로세스가 모두 `arm64`이고, root 또는 `sudo` 실행이
  아니며, 계정 홈이 canonical 경로이고 현재 UID 소유입니다.
- hermetic installed `SessionStart` timing driver를 위한 Python 3.12를 사용할 수
  있습니다.
- 현재 POSIX username이 canonical이며, Claude와 Codex 인증이 일반 preflight와
  닫힌 lifecycle 환경에서 모두 성공합니다.
- Claude와 Codex의 canonical managed root에 OpenSocrates 1.3.1 등록이 각각 정확히
  하나 있습니다.
- Claude와 Codex managed root 및 cache version이 전체 checksum과 닫힌 파일 목록
  검사를 통과합니다.
- 자동 업데이트가 꺼져 있고 LaunchAgent가 unload 상태이며, exact desired state가
  Claude와 Codex만 지정합니다.
- Antigravity, Cursor, Grok, OpenCode의 OpenSocrates root 또는 bridge가 없습니다.
- 지원하지 않는 pre-1.0 Claude 대소문자 변형 등록, installer transaction residue,
  trust-reset residue, LaunchAgent temporary가 없습니다.
- 체크아웃이 clean 상태이고 열린 Pull Request head와 계속 일치합니다.

후보 gate는 정확한 9개 파일로 `npm pack` tarball을 만듭니다. 또한 성공한 CI의
repository, workflow, run ID, attempt, full head SHA, immutable artifact ID, artifact
name, raw ZIP digest와 size, 빌드 시점 commit/tree receipt, 두 호스트 payload
manifest와 canonical Python/Claude/Codex 실행 파일 및 각 SHA-256 digest를
고정합니다. private execution identity는 canonical POSIX username도 고정합니다.
파괴적 lifecycle capsule은 exact host binary와 해당 username을 명시적으로 전달하며
축소된 shell `PATH`에 의존하지 않고, 최종 timing은 고정한 Python을 직접 실행합니다.
harness는 Python이 observation byte를 쓰기 전에 private timing report를 배타적인
소유자 전용 파일로 만들고, 읽기 전에 해당 mode를 다시 검증합니다.
게시 전 후보 1.4.0은 packed installer와 정확한 PR CI artifact를 사용합니다. 공개 npm
또는 GitHub release 1.4.0 다운로드를 전제하지 않습니다. 공개된 1.3.1 release bytes는
시작 payload 출처 확인에만 사용하며 후보 검증을 대체하지 않습니다.

purge 직전 baseline 재검사는 exact managed root, stable cache payload, desired state,
OpenSocrates Codex trust 구문을 고정합니다. cache binding은 shape와 liveness를
별도로 검증한 non-live per-process `.in_use` transient만 제외합니다. 그 밖의 byte
또는 topology가 하나라도 바뀌면 첫 purge 명령 전에 중단합니다.

## 버전 전이와 baseline 출처

지원 전이는 **initialVersion 1.3.1 → candidateVersion 1.4.0**으로 한정합니다.
`purged_same_machine` 및 `transition: purge_then_reinstall`로 기록하며 clean-machine이나
in-place update/migration의 근거가 아닙니다. baseline을 맞추려고 1.4.0을 먼저 설치하지
마세요. 기존 이슈 #83 harness는 당시 같은 1.2.1 후보의 재설치를 검증하려고 양쪽에
`PRODUCT_VERSION`을 사용했습니다. upgrade 경로가 아니며 installer의 pre-1.0 대소문자
변형 등록 migration 안내도 별도의 명시적 수동 절차입니다.

두 host의 활성 등록, managed plugin/release manifest, marketplace metadata, desired
state는 모두 1.3.1이어야 합니다. source와 검증된 PR artifact는 1.4.0이어야 합니다.
public baseline, private checkpoint, resume, purge 직전 byte binding, sealed 최종 결과가
두 역할을 구분합니다. 새 계약이 없는 이전 checkpoint는 거부하며 source를 변경한 뒤
이전 checkpoint를 변환하거나 재실행하지 않습니다.

`tools/reinstall_baseline_provenance.json`은 공식 release archive를 다운로드해 GitHub
asset digest와 실제 bytes를 비교한 뒤 추출한 checksum inventory 및 manifest digest를
고정합니다. 1.3.1 release는 immutable입니다. 1.2.1 release는 immutable이 아니므로
나중의 mutable tag를 신뢰하지 않고 확인한 archive/inventory digest를 source에 고정합니다.
전체 checksum과 닫힌 파일 목록 검사는 그대로 수행합니다. 출처 불명·재해시 payload는
자체 checksum이 맞아도 거부합니다. 이는 저장소/release 출처 고정이며 code signing이 아닙니다.

고정된 1.3.1 cache와 선택적으로 남아 있는 **비활성 Claude 1.2.1 cache**만 허용합니다.
이전 cache는 initialVersion을 바꾸거나 활성 혼합 버전 설치를 뜻하지 않습니다. 알 수 없는
버전, host/version 불일치, manifest 변조, 추가 파일, 인식하지 못한 cache marker는 계속
차단합니다. 승인된 purge는 이 검증된 이전 cache도 제거하며 이를 파괴적 cycle에 기록합니다.

## Codex inventory 진단

OpenSocrates 경고, 모든 inventory error, 분류할 수 없는 경고는 계속 차단합니다.
정확히 진단된 외부 경고 하나만 별도 집계합니다. Codex Companion
`openai-codex/codex/1.0.6`의 SessionEnd 설정 5초를 Codex가 3초 제한으로 줄인다는
경고입니다. 다른 plugin의 설정 진단이며 OpenSocrates 실행 실패를 관찰한 것이 아닙니다.
정확한 문구와 canonical default-home 경로가 일치해야 하며 다른 문구/경로는 차단합니다.
관련 없는 설정은 변경하지 않습니다. baseline과 최종 첫 review 근거의
`otherPluginTimeoutWarningCount`에 개수만 남기고 원문 경로/메시지는 공개하지 않습니다.
일곱 hook, namespace, trust, 고정 SessionStart timeout 검사는 그대로 유지합니다.

CLI에는 `--preflight`나 `--dry-run`이 없습니다. 인자 없는 명령은 gate 이후 실제 변경까지
진행합니다. 읽기 전용 준비는 코드를 확인한 뒤 읽기 전용 inventory 함수만 사용해야 하며
cycle을 시작해서는 안 됩니다.

## 자동 cycle 시작

clean Pull Request 체크아웃에서 실행합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs
```

출력된 두 경로를 모두 보관하세요. public 디렉터리에는 정제된 근거만 있습니다.
소유자 전용 private 디렉터리에는 exact checkpoint, 후보 입력, lifecycle journal,
command ledger와 이후 녹화 파일이 있습니다. cycle이 진행 중일 때 private 디렉터리를
공개, 이동, 수정 또는 삭제하지 마세요.

모든 lifecycle 작업은 로컬에서 고정한 tarball을 operation별
`npx --package` 호출에 명시합니다. purge는
`remove --host all --purge --reset-trust`를 한 명령으로 실행하고, 재설치는 두 exact
host asset을 포함한 하나의 atomic `install --host all` 명령으로 실행합니다. 등록과
닫힌 exact residue inventory가 모두 비기 전에는 설치하지 않습니다.

## 재개와 단 한 번의 host-close retry

purge가 시작됐을 가능성이 있으면 새 initial run을 시작하지 마세요. 최초 baseline과
exact 후보를 계속 권위 있는 입력으로 사용하도록 출력된 private checkpoint만
재개합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY
```

정제된 결과가 `paused`이면 live `.in_use` marker만 유일한 blocker인 host app만
표시합니다. 정확히 그 앱만 닫고 실행 중이 아님을 확인한 뒤 단 한 번의 명시적
retry를 실행합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY \
  --confirm-host-apps-closed
```

이 확인은 도구가 앱을 종료하도록 허가하지 않습니다. retry 전에 checkpoint에 묶인
registration, root, data, state, trust, LaunchAgent, transaction, 후보와 desired-state가
변하지 않았고 표시된 live marker만 사라졌는지 검증합니다. 다른 purge 결함이 섞였거나
두 번째 live-cache 실패가 있으면 종료하며 추가 자동 retry를 하지 않습니다.

검증된 terminal receipt가 없는 claimed lifecycle은 `blocked_unverifiable`이며 다시
실행할 수 없습니다. 0이 아닌 atomic install terminal은 파일 구조가 설치처럼 보여도
성공으로 승격하지 않습니다. 일회성 Codex review 검증이 `finalizing`에 들어간 뒤에는
재실행하지 않으며, 완전하고 일치하는 sealed receipt가 있을 때만 결과 게시를
마무리합니다.

## 앱 관찰 녹화 및 검토

capture가 허가된 경우 첫 수동 Codex 또는 Claude 앱 상호작용 전에 Record & Replay를 시작하세요. 녹화기는
capture 시작 전 사용자 확인을 요청합니다. 확인 작업을 수행하고 녹화를 중지한 뒤
반환된 event stream을 private으로 검토하세요. raw accessibility event, prompt,
transcript, sidebar text, 계정 정보, credential 또는 local path를 public 결과에
복사하지 마세요.

다음 다섯 가지 categorical 확인을 순서대로 녹화합니다.

1. 첫 review에서 정확히 7개의 `opensocrates@opensocrates` Codex hook이 새 항목이며
   untrusted 상태로 표시됩니다.
2. 사용자가 정확히 그 7개를 승인한 뒤 모두 trusted 상태입니다. 관계없는 hook은
   승인하지 않습니다.
3. 새 Codex 작업에서 OpenSocrates `SessionStart`가 고정된 2초 host limit에 timeout
   되지 않습니다.
4. 새 Claude Code Local 작업에서 `/opensocrates:opensocrates status`를 실행해
   1.4.0을 보고합니다. bare `/opensocrates`는 Local plugin 근거가 아닙니다.
5. private Record & Replay event stream을 중지하고 검토했습니다.

독립형 Claude Chat의 canonical 명령은 `/opensocrates`이지만 exact public Chat 1.4.0
artifact는 계속 pending입니다. Claude Local plugin 관찰로 Chat 근거를 추론하지
마세요.

인증, 2FA, 승인 또는 안전한 앱 제어 문제로 확인할 수 없으면 그 상호작용을
중단합니다. 우회하거나 `PASS`로 표시하지 마세요. 각 manual field에는 `PASS`,
`FAIL`, `NOT_OBSERVED`, `BLOCKED` 중 하나만 사용합니다.

검토한 녹화 파일을 출력된 private evidence 디렉터리 안에 새로운 소유자 전용 `0600`
regular file로 둔 뒤 출력된 test ID에 결속합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs --bind-recording \
  PRIVATE_EVIDENCE_DIRECTORY RECORDING_FILE_INSIDE_PRIVATE_EVIDENCE TEST_ID
```

다섯 개의 `PENDING` manual line만 수정하세요. free-form note, 알 수 없는 enum, 변경된
자동 결과, link, extra file 또는 개인정보 값이 있으면 pack을 거부합니다. recording review를
`PASS`로 기록할 때만 verified same-test receipt가 필수입니다. recording 결속 부재가
미관찰 결과의 pack까지 무조건 금지하는 것은 아닙니다.

### 원문 수집이 금지된 경우

Record & Replay를 시작하거나 screenshot, prompt, transcript, accessibility event,
계정 정보, credential, hidden reasoning을 수집하지 마세요. 녹화나 대체 파일을 만들어
결속하지 마세요. 요건을 충족하는 녹화 관찰이 없는 manual field는 `NOT_OBSERVED`로,
로그인·승인·capture 권한·안전한 제어가 막은 field는 `BLOCKED`로 둡니다. 직접 보았더라도
녹화되지 않은 관찰이나 승인 영수증은 recorded `PASS` 요건을 충족하지 않습니다. 자동
hook 목록 조회는 수동 review, 자동 hook 전달, 정본 전체 읽기, native application receipt와
서로 다른 근거입니다.

자동 검사가 통과하면 기존 pack 계약은 다섯 field의 최종 enum에 미관찰/차단이 있어도
recording linkage pending 상태로 pack할 수 있습니다. `automatedResult: passed`는
유지하지만 `manualResult`와 `overallResult`는 `not_observed` 또는 `blocked`이며 하나라도
실패하면 `failed`입니다. 전체 acceptance PASS가 아닙니다. 자동 근거는 설치/topology
판단에 사용할 수 있으나 수동 acceptance 요건은 남습니다. 로그인과 trust 승인은 사용자
행동이며 추정해서는 안 됩니다.

## public handoff 생성 및 보존

다섯 field가 모두 최종 categorical 값을 가진 뒤 실행합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs --pack RESULT_DIRECTORY \
  --private-evidence PRIVATE_EVIDENCE_DIRECTORY
```

최종 ZIP에는 `result.json`, `result.md`, `manual-observations.md`만 정확히 들어갑니다.
자동 결과 bytes는 sealed result와 일치해야 하며, seal, final verification, installed
checkpoint, source commit, CI artifact, 존재하는 경우 recording receipt와 ZIP digest가 private
manifest에서 서로 결속됩니다.

paused 또는 failed run은 별도 이름의 `.diagnostic.zip`을 만들 수 있습니다. 이 bundle은
최종 `.zip` 이름을 차지하지 않으며 paused 결과를 automated pass로 봉인하지 않습니다.

public bundle과 SHA-256 digest를 안전하게 넘길 때까지 private evidence를 보관하세요.
cleanup은 소유권을 검증한 private run 디렉터리 하나를 영구 삭제합니다. bundle이 원래
경로에 있으면 다음을 실행합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs --cleanup-private \
  PRIVATE_EVIDENCE_DIRECTORY --test-id TEST_ID \
  --public-zip-sha256 BUNDLE_SHA256
```

exact bundle을 이동했다면 `--public-bundle MOVED_BUNDLE_FILE`을 추가합니다. digest를 다른
곳에 보존한 뒤 의도적으로 bundle을 삭제했다면 대신
`--allow-missing-public-bundle`을 추가합니다. cleanup은 먼저 durable authorization
tombstone을 쓰므로 삭제 중 중단되어도 같은 exact 명령을 안전하게 반복할 수 있습니다.
active run 또는 owner, mode, canonical path, link count, prefix, test ID, bundle digest가
다른 디렉터리에는 cleanup을 사용하지 마세요.

## 실패 경계와 최종 상태

- preflight 실패는 lifecycle 명령을 한 번도 실행하지 않고 승인된 설치를 그대로
  둡니다.
- partial purge 또는 비어 있지 않은 exact residue inventory 뒤에는 재설치하지
  않습니다.
- mutation 시작 뒤 실패하면 관찰한 categorical partial state 또는
  `unknown_unverified`를 기록하며 이전 cache, data, trust, content, version 복원을
  주장하지 않습니다.
- raw lifecycle output, 후보 경로, 녹화, accessibility snapshot, private evidence
  경로는 private으로 유지하며 issue 또는 Pull Request에 첨부하지 않습니다.
- 성공한 cycle은 exact 후보 commit의 Claude와 Codex를 설치한 상태, 자동 업데이트
  비활성 상태, 다른 지원 host가 없는 상태로 끝납니다. 이것이 의도한 최종 상태이므로
  이 acceptance의 일부로 다시 purge하지 않습니다.

유효한 성공 주장은 이 사용 이력이 있는 Mac의 categorical final topology와 exact
후보 설치로 제한됩니다.
