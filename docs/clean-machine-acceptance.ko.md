# 새 Apple silicon Mac 인수검증

[English](clean-machine-acceptance.md)

실제로 새로 설정한 Mac의 기본 Codex 홈과 실제 계정으로 검증합니다. 격리된 테스트
데이터나 동일 기기 재설치와 다릅니다. 기존 OpenSocrates 설치 상태, 등록, 관리 루트,
자동 업데이트 파일이 있으면 새 기기 기준에 맞지 않아 중단합니다.

Node.js 20 이상, Codex CLI, Git, GitHub CLI를 설치하고 Codex와 GitHub에 로그인합니다.
현재 PR을 체크아웃하고 정확한 최신 커밋의 macOS 네이티브 CI 성공을 기다립니다.
작업 트리는 변경 없이 깨끗해야 합니다.

```sh
gh repo clone ParkerHwang/OpenSocrates
cd OpenSocrates
gh pr checkout YOUR_PR_NUMBER
node tools/clean_machine_acceptance.mjs
```

도구는 아키텍처, 인증, 미사용 기준 상태를 확인합니다. PR·CI 실행·네이티브 배포물을
동일 커밋에 연결하고 Codex 압축 파일을 통합 매니페스트와 대조한 뒤 9개 파일의
npm 설치기를 만듭니다. 해당 후보 파일로 Codex를 설치하고 설치 상태, 등록, 관리 루트,
상태 명령을 확인해 개인정보를 배제한 결과를 저장합니다. 자동 업데이트는 켜지 않으며
공개 npm·GitHub 다운로드 경로는 배포 후 따로 검증해야 합니다.

안내된 `manual-observations.md`의 Codex 플러그인 인식과 호스트 런타임 로딩 두 항목을
완료합니다. 새 대화형 Codex 작업에서 OpenSocrates 훅을 검토하고 실제 관찰만 기록합니다.
`PENDING`을 `PASS` 또는 `FAIL`로 바꾸며 자유 형식 메모, 원문 출력·프롬프트·대화,
계정 정보, 인증 정보, 로컬 경로를 추가하지 않습니다. 안내된 `--pack` 명령을 실행하면
`result.json`, `result.md`, `manual-observations.md`만 포함한 ZIP을 만듭니다.

체크섬이나 기준 상태 검사 실패는 설치를 차단합니다. 등록 실패는 복구를 시도하고,
설치 후 검증 실패는 진단할 수 있도록 상태를 남깁니다. 실패 결과는 자동으로 묶습니다.
패키지 검사만으로 실제 훅 실행이나 방법 적용을 입증할 수는 없습니다.

결과를 보관한 뒤 테스트 설치를 제거하려면 Codex를 닫고 실행합니다.

```sh
node installer/opensocrates.mjs remove --host codex --purge
# OpenSocrates의 정확한 7개 훅 승인을 초기화하려는 경우에만:
node installer/opensocrates.mjs remove --host codex --purge --reset-trust
```

사용 중인 캐시가 있으면 정리가 미완료로 남습니다. 안내된 프로세스를 닫고 명령이
완료되기 전에는 성공으로 기록하지 않습니다. 인증, 대화 기록, 다른 설정은 보존하며
삭제한 캐시는 복원하지 않습니다.
