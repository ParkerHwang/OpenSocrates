# Windows x64 네이티브 지원 — v1.6.0 후보

[English](windows-support.md) · [네이티브 안내](native-v1.6.ko.md)

후보는 Codex CLI/Desktop과 Antigravity 작업공간·전역 경로를 Go로 전환하고
Claude 계정 검증·내보내기를 유지합니다. Windows 네이티브 Claude Code,
Windows ARM64, WSL, 네트워크 공유와 추가 플랫폼은 지원 범위 밖입니다.
사용자는 네이티브 `.exe`와 x64 묶음만 필요하며 Python·Node.js·npm·Go가
필요하지 않습니다.

```text
.\opensocrates.exe verify --host codex --package "C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"
.\opensocrates.exe install --host codex --package "C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"
.\opensocrates.exe status --host codex
```

검증한 v1.5 npm 소유 설치를 인수할 때는 `install` 대신 명시적 `adopt`를
사용합니다. 설정·등록·신뢰·비활성·단일 업데이트 소유자를 보존합니다.
`--host all`은 Codex만 선택합니다. 작업공간·출력은 따옴표로 감싼 로컬 드라이브
절대 경로를 사용하세요. 위 명령은 Go 바이너리를 직접 실행하며 자체 셸·
PowerShell 런타임·설치 래퍼를 사용하지 않습니다.

Codex는 사용자 opt-in 후 훅 밖의 작업 스케줄러에서 안정 버전을 24시간마다
확인하고 로그인 후 지연 확인합니다. 서명·호환성·만료·롤백 방지를 검증합니다.
메이저·비호환 스키마는 자동 적용하지 않습니다. 운영 루트·서명과 실제 예약
검증은 남은 릴리스 조건입니다. Antigravity는 별도 수동 관리하며 계정 ZIP
내보내기는 계정 업로드·활성화가 아닙니다.

실제 Windows 검증은 보호된 DACL·현재 소유자, 열린 부모 핸들, reparse/junction
거부, 배타 잠금, 긴 Unicode 경로, 바이너리 입출력, 압축 alias/stream/대소문자
충돌, 수정된 다른 소유 파일, 동시 작업, Go 보조 프로그램의 사용 중 실행파일
교체를 확인해야 합니다. 크로스 컴파일로 증명할 수 없습니다. 이전 인증 복사·
POSIX 문맥은 사용 불가를 유지합니다. 훅은 안전하게 통과하며 신뢰는 대화형
검토와 새 세션이 필요합니다.

개발자는 고정된 Go 1.27.2와 [기여 안내](../CONTRIBUTING.md)의 Go 소스·패키지·
lifecycle 검사를 실제 Windows x64에서 실행합니다. 별도 Mac 검사도 필요합니다.
네이티브 fixture·인증된 CLI·Desktop GUI·새 기기·플랫폼 서명·SmartScreen은 다른
증거이며 정확한 커밋·명령·결과·누락 항목을 구현 인계에 기록합니다.

[v1.5 안내](windows-v1.5.ko.md)와 [v1.4 작업 기록](windows-v1.4.0-worklog.md)은
과거 증거이며 Go 후보 검증이 아닙니다.

Codex CLI/Desktop 훅은 정상 상속한 기본 PowerShell 문맥만 검증 대상입니다.
설정 명령 `& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe"`는
OS·호스트 설정이며 자체 PowerShell 래퍼가 아닙니다. 사용자 지정·cmd fallback
셸은 지원하지 않고 명시적으로 안전하게 통과합니다. 설치 진단은
`opensocrates.exe manage diagnose --host HOST`이며 런타임 진단과 구분합니다.
