# Windows의 Codex — OpenSocrates 1.4.0

OpenSocrates 1.4.0은 네이티브 Windows 프로세스로 **Windows x64의 Codex**를
지원합니다. 다른 호스트 연동은 제거했습니다. Windows ARM64, Windows 10,
서명, SmartScreen 평판, 별도의 깨끗한 PC는 미검증입니다.

## 설치와 업데이트

Node.js 20 이상과 Codex CLI를 설치하고 Codex에 로그인하세요. 배포 패키지를
사용하는 데 Python, WSL, Unix 셸은 필요하지 않습니다.

```powershell
npx --yes opensocrates@1.4.0 install --host codex
npx --yes opensocrates@1.4.0 status --host codex
npx --yes opensocrates@1.4.0 update --host codex
```

Codex가 PATH에 없으면 `CODEX_BIN`을 실행 파일 경로로 설정하세요. 설치기는
`opensocrates-1.4.0-codex-plugin-windows-x64.zip`을 자동 선택합니다. 검증된
로컬 후보에는 `--asset <ZIP>`과 `--checksum <SHA256-파일>`을 함께 지정하세요.
대화형 Codex 세션에서 OpenSocrates 훅 7개를 검토해야 합니다.

Windows 예약 업데이트는 지원하지 않습니다. `auto-update status`는 이 한계를
표시하며 `enable`과 `run`은 수동 업데이트를 안내합니다. Windows 예약 작업은
설치하지 않습니다. 연동을 제거하려면 다음 명령을 사용하세요.

```powershell
npx --yes opensocrates@1.4.0 remove --host codex --purge
```

Purge는 대화 기록과 훅 신뢰를 보존합니다. OpenSocrates 훅 승인 7개도 초기화할
때만 `--reset-trust`를 추가하세요. 알 수 없거나 안전하지 않거나 사용 중인
데이터는 보존하며 정리 보류로 보고합니다.

## 런타임과 증거

배포 파일에는 `bin/launch.mjs`와 Windows 네이티브 `.exe`가 들어 있습니다.
지원 런타임 경로는 판단 지점별 조회입니다. 기존 SDK의 자격 증명 복사와 POSIX
문맥 접근은 Windows에서 사용할 수 없습니다. 실제 소유자·DACL 검사, 바이너리
입출력, 잠금, 압축 경로 검증으로 로컬 산출물을 보호합니다. 런타임을 사용할
수 없어도 훅은 일반 작업을 막지 않습니다.

내장 SDK와 CLI는 0.144.4로 일치시키며 사용자의 Codex CLI를 대체하지 않습니다.
네이티브 패키지 테스트는 대화형 훅 승인·인증된 전달·Desktop GUI 증거와
구분합니다. 현재 커밋의 결과는 [PR #93](https://github.com/ParkerHwang/OpenSocrates/pull/93)에
기록합니다. 이전 Windows 결과는 [과거 기록](windows-v1.4.0-worklog.md)입니다.

## 네이티브 빌드와 검증

Windows x64, Python 3.12, Node.js 20 이상, uv를 사용하세요.

```powershell
$env:PYTHONUTF8 = '1'
uv sync --locked --all-groups
uv run --locked python tools/build_windows.py
uv run --locked python tools/check_windows.py --packages
uv run --locked ruff check src tools
uv run --locked ruff format --check src tools
uv run --locked mypy src
npm run test:windows
npm pack --dry-run
```

Windows Actions는 `windows-2025`에서 빌드합니다. 배포에는 macOS 릴리스 검사도
필요하며, Windows 전송 체크섬과 패키지 소스 신원을 검증한 뒤 배포 목록을 합칩니다.
