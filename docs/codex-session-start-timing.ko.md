# Codex SessionStart 시간 검사

[English](codex-session-start-timing.md)

Go 네이티브 시간 검사는 생성한 `hooks/hooks.json`의 정확한 SessionStart 명령과
2초 제한을 읽습니다. 명령은 패키지 `runtime/<target>/opensocrates[.exe]`를 직접
실행하며 자체 셸·PowerShell·JavaScript·Python 런처가 없습니다. 전체 패키지를
조립한 뒤 버전 smoke로 예열하기 전에 실행합니다.

```text
go run ./src/opensocrates/cmd/opensocrates-dev acceptance timing --package /absolute/path/to/codex-package --runs 20 --report build/evidence/codex-hook-timing.json
```

실행하는 macOS ARM64·Windows x64와 패키지 대상이 같아야 합니다. 실행 전
전체 목록·릴리스 식별을 검증합니다. `startup`·`compact` 각각 20–100개 새
프로세스를 독립 home/temp/Codex-home/작업공간과 합성 입력으로 실행합니다.
실제 대화·인증 증거가 아닌 합성 시간 검사입니다.

각 프로세스는 exit 0·빈 stderr, startup은 빈 출력, compact는 정확한 제한된
판단 안내를 반환해야 합니다. 모든 표본은 2,000ms 미만, nearest-rank p95는
1,000ms 이하여야 하며 50% 여유를 유지합니다. 첫 프로세스는 smoke 전에
기록합니다. 결과에는 대상·자산 식별·제한·프로세스 모델·source별 표본 수와
first/p50/p95/max·통과 여부만 넣습니다. callback 원문·프롬프트·인증·환경값·
로컬 경로는 저장하지 않습니다.

일반 startup/resume/clear는 안전한 no-op이며 compact는 방법 선택·저장소 초기화
없이 탐색 안내를 복원합니다. 입력은 제한해 메모리에서 처리합니다. 이전 정리는
명시적 호환 lifecycle이 맡고 기본 탐색은 저장소·인증을 만들지 않습니다.
없거나 안전하지 않거나 읽기 전용 정리 상태는 고치지 않고 건너뜁니다.

주장하는 대상마다 실제로 실행합니다. Mac 통과가 Windows 시간·실제 전달·
신뢰·서명·quarantine·SmartScreen·새 기기 증거는 아닙니다. 과거 시간 관찰을
Go 실행파일 검증으로 승격하지 않습니다.
