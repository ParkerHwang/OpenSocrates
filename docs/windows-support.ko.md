# Windows 지원 — v1.4.0 후보

이 브랜치는 아직 공개하지 않은 릴리스 후보입니다. 게시 전에는 npm의 `opensocrates@1.4.0` 설치 명령을 사용하지 마세요. Windows 검증은 WSL 없이 네이티브 프로세스로 진행합니다.

## 요구사항과 설치

Windows x64와 Node.js 20 이상이 필요합니다. 검증 환경은 Windows 11 Pro 빌드 26200, Intel x64, PowerShell 7.6.5, 일반 사용자 권한입니다. Python은 네이티브 ZIP에 포함되어 사용자 PATH에 설치할 필요가 없습니다. Windows ARM64·Windows 10·별도 새 컴퓨터·코드 서명·SmartScreen 평판은 미검증입니다.

호스트에 먼저 로그인하세요. 공식 배포판 Claude Code 2.1.266과 Codex CLI 0.153.4를 준비했습니다. 최신 호스트 CLI와 별도로 번들 SDK와 CLI 바이너리는 모두 0.144.4로 일치합니다. 번들 CLI는 최신 호스트 CLI를 대신하지 않습니다.

저장소 또는 npm 패키지에서 PowerShell로 실행합니다.

```powershell
# 호스트 실행 파일이 PATH에 없을 때만 지정합니다.
$env:CODEX_BIN = 'C:\path\to\codex.exe'
$env:CLAUDE_BIN = "$env:USERPROFILE\.local\bin\claude.exe"
node installer/opensocrates.mjs install --host codex --asset dist/opensocrates-1.4.0-codex-plugin-windows-x64.zip --checksum dist/opensocrates-1.4.0-codex-plugin-windows-x64.zip.sha256
node installer/opensocrates.mjs status --host codex
# update에도 같은 --asset, --checksum 인자를 사용합니다.
node installer/opensocrates.mjs remove --host codex
```

Claude는 호스트와 ZIP 이름의 `codex`를 `claude`로 바꾸세요. 설치기는 외부 SHA-256, Windows ZIP 경로, 플랫폼 선언, 내부 전체 파일 체크섬을 검증하며 소유권 표식과 트랜잭션 롤백을 유지합니다. 업데이트·제거 전 활성 호스트 작업을 닫으세요. 실행 중인 파일이 잠겨 교체에 실패하면 표시된 백업을 보존하고 호스트를 닫은 뒤 재시도하세요. 다른 호스트 설정은 삭제하지 마세요.

게시 후에는 `npx --yes opensocrates@1.4.0 install --host codex`가 Windows ZIP을 자동 선택합니다. 같은 설치기의 `update`, `status`, `verify`, `remove`를 사용합니다. npm에는 Windows 도우미가 포함됩니다. 설치기를 단독 다운로드할 때는 `windows.ps1`을 `opensocrates.mjs`와 같은 폴더에 두세요.

## 호스트별 검증 범위

| 호스트 | 공식 Windows 조건 | 이 노트북 검증 |
| --- | --- | --- |
| Codex CLI | 네이티브 Windows, 훅은 대화형 신뢰 승인 필요 | 0.153.4 실제 모델 세션에서 설치된 런타임을 실행해 한국어 방법 48개 반환 확인; 자동 훅 승인 대기 |
| Codex Desktop | 설치됨; 로컬 스크립트와 신뢰 승인 필요 | Desktop 실호출 미검증; CLI 결과로 대체하지 않음 |
| Claude Code CLI | 네이티브 Windows, 호스트 로그인; Git for Windows 권장 | 2.1.266 설치, 로그인·실호출 대기 |
| Claude Desktop / Cowork | 로컬·원격 실행은 호스트가 결정 | Desktop 설치됨; 각 화면의 실호출 미검증 |
| Cursor | Windows x64/ARM64 배포판, 호환 Agent Plugin 버전 | 미설치; OpenSocrates 연동 미검증 |
| Antigravity | Windows 10 이상 x64/ARM64 배포판 | Desktop 2.12.2 / Gemini 3.8 Flash High: 실제 정본 읽기와 한국어 응답 확인; CLI 1.1.28 검증, ZIP 설치·업데이트·제거·재설치 통과 |
| Grok Build | 공식 PowerShell 설치 경로 | 미설치; 연동 미검증 |
| OpenCode | 네이티브 npm/릴리스 설치 지원, 공급자는 WSL 권장 | 미설치; 네이티브 브리지 미검증; WSL은 Windows 증거로 인정하지 않음 |

공식 자료와 확인 날짜(2026-09-09)는 [영문 안내](windows-support.md)에 링크로 정리했습니다.

Windows의 지원 경로는 결정 지점 조회(`node bin/launch.mjs decision codex` 또는 `claude`)와 호스트 승인 후 탐색 훅입니다. 유지된 이전 SDK의 자격 증명 복사·POSIX 파일 핸들 기반 컨텍스트 조회는 Windows에서 사용할 수 없으며 안전하게 실패합니다. 현재 결정 조회에는 이 경로가 필요하지 않습니다. 로컬 임시 상태는 실제 소유자·ACL 검사, 바이너리 입출력, Windows 파일 잠금을 사용합니다. 텔레메트리나 자격 증명 수집을 추가하지 않습니다.

**1.4.0의 Windows 예약 자동 업데이트는 미지원**입니다. `auto-update status`에 이를 표시하고 `enable`·`run`은 수동 업데이트 안내와 함께 실패합니다. Windows 예약 작업은 만들지 않습니다. 기존 macOS LaunchAgent 동작은 유지합니다. 훅의 런타임·런처 오류는 일반 작업이 계속되도록 처리합니다.

## 개발·빌드

Python 3.12, Node.js 20 이상, 공식 Astral uv를 사용합니다. 저장소 루트에서 다음을 실행하세요.

```powershell
$env:PYTHONUTF8 = '1'
uv sync --locked --all-groups
uv run --locked python tools/generate_schemas.py
uv run --locked python tools/validate_content.py --output content/compiled-content.bundle.json --reasoning-projections-output content/compiled-reasoning-content.bundle.json
uv run --locked python tools/build_windows.py
uv run --locked python tools/check_windows.py --packages
uv run --locked ruff check src tools
uv run --locked ruff format --check src tools
uv run --locked mypy src
npm pack
```

Windows CI는 `windows-2025`에서 빌드·검사를 수행하도록 추가했고 기존 Linux·Apple Silicon 검사를 유지합니다. 릴리스는 Windows 작업 성공과 전송된 ZIP 체크섬 확인 후 새 파일을 포함하도록 구성했습니다. 브랜치를 push하고 실제 실행하기 전에는 CI 통과를 주장하지 않습니다.

검증 결과, 기존 전체 테스트의 실패 및 재현 명령은 [작업 기록](windows-v1.4.0-worklog.md)을 확인하세요. POSIX 전용 픽스처 실패나 인증 대기 검사를 통과로 보고하지 않습니다. 이 노트북에서는 macOS를 실행해 검증하지 않았습니다.
