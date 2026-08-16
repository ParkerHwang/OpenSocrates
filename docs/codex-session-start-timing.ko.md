# Codex `SessionStart` 시간 게이트

[English](codex-session-start-timing.md)

네이티브 `darwin-arm64` 릴리스 게이트는 합성 실행 파일이나 `version --json`
대리 지표가 아니라 사용자가 받는 다음 명령을 측정합니다.

```text
${PLUGIN_ROOT}/bin/launch.sh hook codex session_started
```

게이트는 생성된 `hooks/hooks.json`에서 이 명령과 2초 제한을 읽고, 생성된 onedir
패키지에서 명령을 실행합니다. `startup`과 `compact` 두 source를 모두 표본으로
삼으며, 각 source마다 생성된 유효한 `SessionStart` envelope와 서로 다른 격리
HOME, 임시 디렉터리, Codex home, workspace를 사용하는 새 프로세스 20개를
시작합니다. 빈 소유자 전용 OAuth 메타데이터 표식은 어느 source든 전체 런타임
구성으로 회귀할 때 selector-available 분기를 거치게 하지만 selector 요청은
시작하지 않습니다.

Codex 런타임 빌드에서는 warm-up이 비용을 숨기지 못하도록 첫 configured hook을 모든
`version --json` smoke보다 먼저 실행합니다. 최종 릴리스 조립도 최종 패키지 버전
smoke 전에 `dist/codex`에서 게이트를 다시 실행합니다. 통과 조건은 다음과 같습니다.

- 모든 프로세스가 종료 코드 0과 완전히 빈 stdout/stderr로 끝나야 합니다.
- 각 source 집합의 첫 configured hook과 모든 표본이 설정된 2,000 ms 제한보다
  짧게 끝나야 합니다.
- 각 source의 nearest-rank p95가 1,000 ms 이하여야 하며 50% 예산 여유를 유지해야
  합니다.
- 각 source마다 새 프로세스 표본을 최소 20개 측정해야 합니다(도구의 상한은
  source마다 100개입니다).

닫힌 JSON 증거에는 target, release-manifest identity, process model, configured timeout,
그리고 `startup`·`compact` source별 결과만 기록합니다. 각 source 결과에는 sample
count, first/p50/p95/max latency, pass/fail이 있고, 두 source 결과가 모두 통과해야
전체 pass가 됩니다. callback 입력·출력, 사용자 prompt, credential, 환경 값, 로컬
경로는 기록하지 않습니다. 네이티브 패키지를 조립한 뒤 다음 명령으로 게이트를 실행할
수 있습니다.

```bash
make codex-hook-timing
```

게이트는 `source: "startup"`과 `source: "compact"` payload를 모두 전달합니다.
일반 `startup`, `resume`, `clear` callback은 런타임 구성 전의 fail-open no-op입니다.
고정 launcher는 callback 입력을 최대 4 MiB까지만 프로세스 메모리에 보관하고 macOS
시스템 parser로 최상위 `source: "compact"`가 정확히 일치할 때만 통과시킵니다. 이
입력을 disk, argument, environment 또는 diagnostic에 기록하지 않습니다. 크기 초과,
malformed, source 누락 및 일반 시작 callback은 완전히 빈 출력으로 끝납니다.
`compact`만 경계 안의 정확한 입력을 런타임에 다시 전달하며, 런타임은 전체 native-event
검증을 수행하고 기존 instruction reference 복원에 필요한 최소 artifact store를 엽니다.
24시간 crash-residue sweep은 `UserPromptSubmit`과 compact 복원 전에 실행되므로 일반
시작을 전체 경로에서 분리해도 privacy cleanup은 사라지지 않습니다.

이 게이트는 실행한 Apple Silicon Mac에서 해당 빌드 artifact만 뒷받침합니다. 실제
Codex hook 전달, 서명/notarization, quarantine 동작, clean-machine 설치를 입증하지는
않습니다.
