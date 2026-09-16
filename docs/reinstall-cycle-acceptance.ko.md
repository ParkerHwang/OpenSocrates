# 사용 중인 Mac 제거·재설치 인수검증

[English](reinstall-cycle-acceptance.md)

이 검증은 **Codex 1.3.1 → Codex 1.4.0**을 완전히 제거한 뒤 재설치합니다.
결과는 `purged_same_machine`, `purge_then_reinstall`로 기록하며 별도 새 기기
설치나 기존 상태를 유지하는 마이그레이션이 아닙니다. 실제 계정 홈에서 검증된
OpenSocrates 등록, 설치 파일, 캐시, 설치 상태, 업데이트 작업, 정확한 7개 Codex
훅 신뢰를 제거합니다. 삭제한 내용은 복원하지 않습니다. 다른 플러그인·설정·인증·
대화 기록·npm 캐시는 소유 범위 밖이며 다른 호스트 통합은 1.4.0 대상이 아닙니다.

## 시작 상태와 후보 식별

열린 PR의 정확한 최신 커밋에서 macOS CI가 성공한 뒤 깨끗한 체크아웃을 사용합니다.
Mac 하드웨어와 Node는 arm64여야 하며 실제 홈 소유자로 실행합니다. root나 sudo는
사용하지 않습니다. Python 3.12, 로그인된 Codex CLI와 GitHub CLI가 필요합니다.
기본 Codex 등록, 설치 파일, 설치 상태가 모두 1.3.1이어야 하며 자동 업데이트는
꺼져 있고 LaunchAgent는 내려가 있어야 합니다. 알 수 없는 파일, 잘못된 소유권,
설치 중간 잔여물은 변경 전에 차단합니다.

1.3.1 설치 상태에 지원 종료 호스트가 남아 있으면 먼저 1.3.1로 해당 통합을 제거합니다.
1.4.0 도구는 그 정리를 구현하지 않습니다. 기준 상태를 만들기 위해 1.4.0을 먼저
설치하지 마세요.

`tools/reinstall_baseline_provenance.json`은 변경 불가능한 공식 Codex 1.3.1
압축 파일·체크섬 목록·매니페스트 해시를 고정합니다. 전체 파일 목록과 체크섬도
검증하며 다시 해시한 파일이나 알 수 없는 파일은 거부합니다. Codex 1.3.1 캐시만
허용합니다. 이전 다중 호스트 체크포인트는 사용할 수 없습니다.

후보 검증은 9개 파일 npm 패키지, CI 실행·시도, 커밋, 배포물 ID·이름·해시·크기,
소스 커밋·트리 증거, Codex 파일 목록, Python·Codex 실행 파일 경로와 해시를 연결합니다.
제거 직전 기준 파일과 대상 신뢰 구문을 재검사합니다. 유효하고 사용 중이지 않은
`.in_use` 임시 표시만 캐시 바이트 연결에서 제외하며 다른 변화는 제거 전에 차단합니다.

OpenSocrates 훅 경고·오류와 알 수 없는 경고는 검증을 막습니다. Codex Companion
1.0.6의 알려진 SessionEnd 제한 경고는 메시지와 정규 출처가 정확히 맞을 때만
별도로 셉니다. 다른 플러그인 설정은 바꾸지 않습니다. 패키지 시간 측정만으로
실제 자동 전달을 증명할 수는 없습니다.

## 실행과 재개

인자 없는 명령은 실제 삭제까지 진행하며 dry-run이 없습니다. 제거 전에 Codex 호스트
세션을 닫고 독립된 Terminal에서 실행해 플러그인 제거 중에도 검증 제어가 유지되게 합니다.

```sh
node tools/reinstall_cycle_acceptance.mjs
```

안내된 공개 결과와 소유자 전용 비공개 경로를 보관합니다. 비공개 경로에는 후보 파일,
체크포인트, 명령 기록과 설치 작업 기록이 있습니다. 실행 중에는 옮기거나 편집하지 않습니다.
고정된 `npx` 패키지로 `remove --host all --purge --reset-trust`를 실행합니다.
`all`은 Codex만 뜻합니다. 정확한 잔여물이 없음을 확인한 뒤 후보 Codex 패키지를 설치합니다.

변경이 시작됐을 가능성이 있으면 새 초기 실행을 하지 말고 기존 체크포인트로 재개합니다.

```sh
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY
```

기록된 사용 중 캐시 일시 정지만 한 번의 재시도를 허용합니다. 안내된 호스트가
닫혔음을 확인한 뒤 실행합니다.

```sh
node tools/reinstall_cycle_acceptance.mjs --resume PRIVATE_EVIDENCE_DIRECTORY \
  --confirm-host-apps-closed
```

이 옵션은 앱을 종료하지 않습니다. 사용 중 표시 외 모든 연결 정보가 같아야 합니다.
다른 잔여물이나 두 번째 캐시 실패는 종료 상태입니다. 작업을 시작했으나 종료 증거가
없으면 `blocked_unverifiable`이며 재실행하지 않습니다. 설치가 실패했다면 파일이
있다는 이유로 성공으로 올리지 않습니다. 최종화가 시작되면 정확한 봉인 결과로만
저장을 끝내며 최초 훅 검사는 반복하지 않습니다.

## 관찰과 결과 묶기

원문 캡처가 승인된 경우 수동 조작 전에 Record & Replay를 시작하고 끝난 뒤 중지하여
비공개로 검토합니다. 접근성 이벤트, 프롬프트, 대화, 계정 정보, 경로를 공개하지 않습니다.
다음 네 항목을 범주로 기록합니다.

1. 최초 검토에서 OpenSocrates 훅 7개가 새 미승인 항목으로 나타남.
2. 해당 7개 훅의 승인이 끝나 신뢰 상태임.
3. 새 Codex 작업에서 고정 2초 제한의 OpenSocrates SessionStart 시간 초과가 없음.
4. 비공개 Record & Replay 캡처를 중지하고 검토함.

`PASS`, `FAIL`, `NOT_OBSERVED`, `BLOCKED`만 사용합니다. 승인 여부를 추측하거나
인증을 우회하지 않습니다. 관찰 기록이 있으면 소유자 전용 파일을 해당 검증에 연결합니다.

```sh
node tools/reinstall_cycle_acceptance.mjs --bind-recording \
  PRIVATE_EVIDENCE_DIRECTORY RECORDING_FILE_INSIDE_PRIVATE_EVIDENCE TEST_ID
```

원문 캡처가 금지되면 대체 기록을 만들지 않습니다. 정해진 기록이 없는 항목은
`NOT_OBSERVED` 또는 `BLOCKED`로 남깁니다. 기록 없는 직접 관찰은 기록 기반 PASS가
아닙니다. 자동 검사가 성공하면 미관찰 수동 항목을 포함해 결과를 묶을 수 있지만
전체 인수검증 성공으로 기록하지는 않습니다.

네 범주 항목만 수정한 뒤 실행합니다.

```sh
node tools/reinstall_cycle_acceptance.mjs --pack RESULT_DIRECTORY \
  --private-evidence PRIVATE_EVIDENCE_DIRECTORY
```

최종 ZIP에는 `result.json`, `result.md`, `manual-observations.md`만 들어갑니다.
자동 검사 원본, 최종 봉인, 설치 체크포인트, 소스·배포물 식별, 관찰 증거가 있는 경우
그 증거, ZIP 해시가 연결됩니다. 실패·일시 정지 진단 ZIP은 최종 ZIP을 대신하거나
성공을 뜻하지 않습니다.

## 보관과 최종 상태

공개 결과와 해시를 안전하게 전달하기 전까지 비공개 증거를 보관합니다. 아래 명령은
검증된 해당 비공개 실행 경로만 영구 삭제합니다.

```sh
node tools/reinstall_cycle_acceptance.mjs --cleanup-private \
  PRIVATE_EVIDENCE_DIRECTORY --test-id TEST_ID --public-zip-sha256 BUNDLE_SHA256
```

결과를 옮겼다면 `--public-bundle MOVED_BUNDLE_FILE`, 해시를 보관한 뒤 의도적으로
결과를 지웠다면 `--allow-missing-public-bundle`을 사용합니다. 영속 삭제 승인 기록으로
중단된 정리를 반복할 수 있습니다. 실행 중인 경로를 지우거나 소유자·모드·링크·식별·
해시 검사를 우회하지 마세요.

사전 검사 실패는 설치 상태를 바꾸지 않습니다. 일부 제거만 끝나면 재설치를 차단합니다.
변경 후 실패는 실제 부분 상태나 `unknown_unverified`로 남기며 삭제한 데이터·신뢰를
복원했다고 주장하지 않습니다. 성공 시 정확한 후보의 Codex 1.4.0이 설치되고 자동
업데이트는 꺼져 있습니다. 이 검증의 마지막 설치를 다시 지우지 마세요.
