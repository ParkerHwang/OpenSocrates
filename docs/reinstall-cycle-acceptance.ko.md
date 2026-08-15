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
- Claude와 Codex가 인증되어 있고, canonical managed root에 OpenSocrates 1.2.1
  등록이 각각 정확히 하나 있습니다.
- Claude와 Codex managed root 및 cache version이 전체 checksum과 닫힌 파일 목록
  검사를 통과합니다.
- 자동 업데이트가 꺼져 있고 LaunchAgent가 unload 상태이며, exact desired state가
  Claude와 Codex만 지정합니다.
- Antigravity, Cursor, Grok, OpenCode의 OpenSocrates root 또는 bridge가 없습니다.
- 지원하지 않는 pre-1.0 Claude 대소문자 변형 등록, installer transaction residue,
  trust-reset residue, LaunchAgent temporary가 없습니다.
- 체크아웃이 clean 상태이고 열린 Pull Request head와 계속 일치합니다.

후보 gate는 정확한 8개 파일로 `npm pack` tarball을 만듭니다. 또한 성공한 CI의
repository, workflow, run ID, attempt, full head SHA, immutable artifact ID, artifact
name, raw ZIP digest와 size, 빌드 시점 commit/tree receipt, 두 호스트 payload
manifest와 canonical Claude/Codex 실행 파일 및 각 SHA-256 digest를 고정합니다.
파괴적 lifecycle capsule은 그 exact host binary를 명시적으로 전달하며 축소된 shell
`PATH`에 의존하지 않습니다. 공개 npm 및 GitHub release의 1.2.1은 계속
unavailable이며 사용하거나 검증했다고 주장하지 않습니다.

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

첫 수동 Codex 또는 Claude 앱 상호작용 전에 Record & Replay를 시작하세요. 녹화기는
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
   1.2.1을 보고합니다. bare `/opensocrates`는 Local plugin 근거가 아닙니다.
5. private Record & Replay event stream을 중지하고 검토했습니다.

독립형 Claude Chat의 canonical 명령은 `/opensocrates`이지만 exact public Chat 1.2.1
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
자동 결과, 누락된 recording 결속, link, extra file 또는 개인정보 값이 있으면 pack을
거부합니다.

## public handoff 생성 및 보존

다섯 field가 모두 최종 categorical 값을 가진 뒤 실행합니다.

```bash
node tools/reinstall_cycle_acceptance.mjs --pack RESULT_DIRECTORY \
  --private-evidence PRIVATE_EVIDENCE_DIRECTORY
```

최종 ZIP에는 `result.json`, `result.md`, `manual-observations.md`만 정확히 들어갑니다.
자동 결과 bytes는 sealed result와 일치해야 하며, seal, final verification, installed
checkpoint, source commit, CI artifact, recording receipt와 ZIP digest가 private
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
