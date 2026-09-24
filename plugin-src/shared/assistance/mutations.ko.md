# 허용된 메모리 정정과 삭제

Guide revision: 1

사용자의 기존 허용 범위에서 이미 등록된 프로젝트 메모리를 변경할 때만
읽으세요. 다른 루트를 등록하거나 범위를 넓히거나 SQLite를 직접 편집하지
마세요. 원문 프롬프트, 소스 복사본, 대화 기록, 숨겨진 사고 과정은 저장하지 않습니다.

설치된 `bin/launch.sh memory codex`에 JSON 객체 하나를 요청으로 보냅니다.
닫힌 최상위 형식은 `schema`: `opensocrates.project-memory.request/1.0.0`,
`operation`, 새 UUID인 `request_id`, 등록된 `project_id`와 `workspace_id`,
UUID 또는 null인 `task_id`, `payload`입니다. 연산별 필드는 `payload` 안에
넣으세요. 새로운 변경 의도마다 새 UUID `idempotency_key`를 사용합니다.
동일한 변경의 성공 여부가 불분명할 때만 원래 키와 동일한 요청으로 재시도합니다.

먼저 `inspect`에 `{}`를 보내 레코드를 나열하거나, 하나를 보려면
`{"record_id":"UUID"}`를 보냅니다. 반환된 레코드 ID와 **현재** 버전을
사용하세요. 이전 명령 수로 버전을 추측하지 마세요. 글로 제안했다고 해서
레코드가 실제로 생성된 것은 아닙니다.

이력을 남기는 일반 정정이라면 허용된 범위의 새 레코드를 만들고 명시적으로
승인한 뒤 `supersede`를 사용합니다. payload 필드는 `record_id`,
`new_record_id`, `expected_record_version`, `expected_new_record_version`,
`idempotency_key`, 짧은 공개 사유인 `reason`입니다. 두 레코드는 같은
프로젝트에서 이미 승인된 상태여야 합니다. 대체는 기존 요약과 이력을 남기므로
inspect/export에 기존 내용이 계속 나타날 수 있습니다.

사실을 **잊어 달라는** 명시적 요청에는 대체만으로 충분하지 않습니다.
삭제 단위는 레코드입니다. 철회된 사실과 유지할 의도가 한 레코드에 섞여
있다면, 유지할 공개 의도만 같은 범위의 새 레코드로 만들고 승인한 다음
기존 레코드만 정확히 삭제하세요. 철회된 사실을 새 요약, 사유, 체크포인트,
reason에 다시 쓰지 마세요. 한 사실을 지우려고 프로젝트나 무관한 레코드를
삭제하지 마세요.

자료에 의존하지 않는 공개 결정의 `record` payload 필드는 다음과 같습니다.

```json
{"idempotency_key":"UUID","expected_record_version":0,"kind":"decision","scope":{"level":"project"},"summary":"유지하도록 허용된 의도만 작성","origin":{"producer_kind":"agent","source_reference":null,"attestation":"agent_reported"},"support":"agent_reported","source_refs":[],"revalidation":{"dependency_paths":[],"negative_claim":false,"on_change":"not_applicable"}}
```

예시는 프로젝트 범위입니다. 원래 범위나 자료 의존 관계가 다르면 해당 내용을
유지하고 UUID 자리표시자를 바꾸세요. `accept`에는 반환된 `record_id`와
현재 `expected_record_version`, 새 `idempotency_key`, 실제 허용 근거를
가리키는 `acceptance_basis`를 사용합니다. 에이전트가 사용자 지시를 전달하는
경우 `acceptance_attribution`은 `"agent_reported_user_instruction"`입니다.
호스트가 증명했다고 주장하지 마세요.

레코드 하나를 지우는 `delete` payload는
`{"intent":"delete_record","record_id":"UUID","expected_record_version":2,"idempotency_key":"UUID"}`입니다.
버전 `2`는 예시이므로 조회한 현재 버전을 쓰세요. 모든 연산의 `status`와
`result`를 확인합니다. 거부되면 실제 상태와 계약을 확인한 뒤 요청을 고치세요.
추측을 반복하거나 데이터베이스 직접 편집으로 우회하지 마세요. 실패하면
그 메모리 변경만 미완료로 남깁니다.

`inspect`, 페이지 구분까지 확인한 `{"format":"json"}` export, 관련 recall로
철회된 요약이 사라지고 유지할 승인 의도는 남아 있는지 검증합니다.
삭제는 해당 레코드의 관리되는 이력과 백업도 제거합니다. 별도로 보관한 사용자
내보내기 사본과 포렌식 복구는 보장 범위 밖입니다. 확인할 수 없거나 미완료인
부분은 정확히 보고하고 독립적인 작업은 계속 진행하세요.
