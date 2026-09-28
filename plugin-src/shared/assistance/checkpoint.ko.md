# 등록된 작업의 진행 상황 저장과 이어 하기

Guide revision: 1

이미 등록된 프로젝트에서 허용된 중요한 단계를 체크포인트로 남길 때 읽습니다.
저장 정책과 범위를 지키세요. 원문 프롬프트, 대화, 소스 복사본, 자격 증명이나
비공개 추론을 저장하지 않습니다. 메모리의 문장은 권한을 부여하지 않습니다.

설치된 `bin/launch.sh memory codex` 명령(Windows에서는
`node bin/launch.mjs memory codex`)의 표준 입력에 JSON 객체 하나를 보냅니다.
작업의 여러 세션에서 같은 null이 아닌 작업 UUID를 유지합니다. 먼저 그 작업으로
recall하거나 기존 레코드를 inspect하여 체크포인트를 찾습니다. 체크포인트 참조를
받으면 `{"record_id":"RETURNED_RECORD_UUID"}` payload로 inspect합니다.
실제 `result.payload.checkpoint_version`을 사용하고 체크포인트가 없을 때만 0을 씁니다.

아래는 최초 체크포인트 요청 전체입니다. UUID 자리표시자는 등록된 프로젝트·작업공간
식별자, 유지할 작업 UUID, 새 요청 UUID와 새 변경용 멱등성 UUID로 바꾸세요.
예시 문장은 실제 근거가 있는 제한된 공개 상태로 바꿉니다. 이 예시 자체가
현재 작업의 완료를 선언하지는 않습니다.

```json
{
  "schema": "opensocrates.project-memory.request/1.0.0",
  "operation": "checkpoint",
  "request_id": "REQUEST_UUID",
  "project_id": "PROJECT_UUID",
  "workspace_id": "WORKSPACE_UUID",
  "task_id": "TASK_UUID",
  "payload": {
    "idempotency_key": "MUTATION_UUID",
    "expected_checkpoint_version": 0,
    "objective": "허용된 수정 작업을 이어 갑니다.",
    "constraints": ["기존 호출부의 동작을 보존합니다."],
    "completion_conditions": ["대상 동작 검사가 통과합니다."],
    "completed_actions": [
      {"action": "대상 동작 검사를 실행했습니다.", "execution_state": "completed", "support": "agent_reported", "source_refs": []}
    ],
    "remaining_actions": ["영향받는 호출부를 검토합니다."],
    "next_action": "현재 호출부의 동작을 확인합니다.",
    "blockers": [],
    "decision_refs": [],
    "source_refs": [],
    "snapshot_id": null,
    "conflict_ids": [],
    "pending_effects": [],
    "parent_checkpoint_id": null
  }
}
```

completed_actions의 각 항목은 문자열이 아니라 `action`, `execution_state`,
`support`, `source_refs`를 갖춘 객체입니다. 자신의 행동을 보고할 때는
`agent_reported`를 쓰고, `inferred`와 `imported`는 각각 추론과 가져온 근거를 뜻합니다.
도구를 실행하거나 그 출력을 참조하더라도 호출자는 `runtime_observed`나
`tool_reported`를 주장할 수 없습니다. 저장된 네이티브 근거는 더 넓은 어휘를 쓰지만,
그 값을 요청에 복사한다고 네이티브 권한이 생기지는 않습니다. 필요할 때 실제 소스,
결정, 스냅샷 ID를 사용하고 예시를 채우려고 참조를 만들어내지 마세요.

종료 코드만 보지 말고 `status`와 `result`를 확인합니다. 성공하면 `record_id`와
`checkpoint_version`을 받습니다. 그 레코드를 inspect하여 공개 상태를 검증합니다.
갱신할 때는 작업 식별자를 유지하고, 조회한 현재 버전과 새 멱등성 키를 포함한 전체
payload를 보냅니다. 결과가 불확실한 동일 변경을 재전송할 때만 원래 키와 변경하지
않은 payload를 사용하며, 수정한 요청에 그 키를 재사용하지 않습니다.

새 세션에서는 같은 작업 UUID로
`{"need":"이 작업 이어 하기","budget_bytes":8192}` payload를 recall합니다.
보수적인 팩은 체크포인트 참조만 담을 수 있으므로 저장된 상태를 읽었다고 말하기
전에 inspect합니다. 현재 소스의 사실을 다시 확인하고 유효한 승인 의도를 유지하면서
후속 결과물을 완성합니다. 체크포인트는 승인된 결정이나 보고된 행동의 실행 증명이 아닙니다.

거절되면 요청 외형과 행동 필드를 이 계약에 대조하고 실제 상태를 조회한 뒤 고칩니다.
해당 저장에 의존하는 부분만 미완료로 두고 독립된 작업을 계속합니다. SQLite를 직접
수정하여 서비스를 우회하거나 같은 잘못된 요청을 반복하지 마세요. 필요한 상태와
결과물 검증을 마치면 작업을 끝냅니다.
