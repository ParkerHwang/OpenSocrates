# Windows에서 OpenSocrates v1.5.0 사용하기

[English](windows-v1.5.md) · [기존 Codex Windows 기준](windows-support.md)

이번 Windows 단계는 기존 Codex Windows x64 지원을 보존하고, Claude 계정
스킬의 로컬 검증·내보내기와 Windows x64에서 소유한 Antigravity 규칙·스킬의
설치 상태 관리를 추가합니다. 요청된 Claude Windows 범위는 **계정 콘텐츠를
통한 웹 Chat·Desktop Chat·Cowork**입니다. 터미널이나 Desktop Code에서 쓰는
네이티브 Windows Claude Code는 이번 범위에 포함하지 않습니다. 기존 Mac
연동은 별도의 [Mac 안내](macos-v1.5.ko.md)를 따릅니다.

이 파일은 **게시되지 않은 로컬 v1.5.0 후보**이며 npm·GitHub 릴리스 파일이
아닙니다. 구현과 오프라인 검사만으로 계정 활성화, 대화 앱의 불러오기,
모델 결과 개선이 증명되지는 않습니다. 정확한 결과와 남은 실제 확인 항목은
[Windows 관찰 기록](../evals/v1.5-windows/REPORT.md)과
[구현 인계](v1.5.0/WINDOWS_IMPLEMENTATION_HANDOFF.md)에 기록합니다.

## 로컬 파일 빌드와 검증

네이티브 Windows 11 x64, Node.js 20 이상, Python 3.12, 고정한 uv 환경을
사용합니다. LF 파일을 쓰는 소스 저장소에서 다음 명령을 실행합니다.

```powershell
git config core.autocrlf false
$env:PYTHONUTF8 = '1'
uv sync --locked --all-groups
uv run --locked python tools/build_windows.py
uv run --locked python tools/check_windows.py --packages
uv run --locked python tools/check_content_hosts.py
uv run --locked ruff check src tools
uv run --locked ruff format --check src tools
uv run --locked mypy src
npm run test:windows
node --test installer/managed-windows.test.mjs
npm pack --dry-run
```

`core.autocrlf` 설정만으로 기존 파일이 변환되지는 않습니다. 고정한 소스
해시를 비교하기 전에 LF인지 확인합니다. 빌드는 아래 ZIP과 각 파일의 같은
이름 `.sha256` 파일, Windows SBOM 근거를 생성합니다.

| `dist/`의 파일 | 용도 |
| --- | --- |
| `opensocrates-1.5.0-codex-plugin-windows-x64.zip` | 기존 Codex Windows 네이티브 경로 |
| `opensocrates-1.5.0-claude-chat-skills.zip` | 휴대 가능한 콘텐츠 전용 `opensocrates/` 계정 스킬 1개 |
| `opensocrates-1.5.0-antigravity-plugin.zip` | 휴대 가능한 `.agents/` 규칙·스킬 콘텐츠 |

콘텐츠 전용 파일 이름에는 Windows 접미사가 없으며 런타임이나 훅을 담지
않습니다. Antigravity 파일 이름은 CLI 플러그인 등록을 뜻하지 않습니다.
네이티브 Windows Claude 파일은 만들지 않습니다. 별도 Mac 릴리스 검증도
유지하며 Windows 빌드로 대신하지 않습니다.

아래 설치·업데이트·검증·내보내기에는 로컬 `--asset`과 `--checksum`을 함께
지정합니다. 생략하면 아직 게시되지 않은 릴리스 파일을 요청합니다.
배포된 설치기에는 Node.js와 Windows PowerShell이 필요하며, Python은 소스
개발과 빌드에 사용합니다.

## Claude 계정 스킬: 웹 Chat·Desktop Chat·Cowork

이미 존재하고 본인이 소유한 로컬 내보내기 폴더를 선택합니다. 아래 예시
폴더를 실제 경로로 바꾼 뒤 실행합니다. 내보내기는 ZIP의 절대 경로를
요구하며 상위 폴더를 만들지 않습니다.

```powershell
$accountAsset = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-claude-chat-skills.zip').Path
$accountChecksum = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-claude-chat-skills.zip.sha256').Path
$accountExportDirectory = (Resolve-Path -LiteralPath 'C:\Work\OpenSocrates Exports').Path
$accountOutput = Join-Path $accountExportDirectory 'opensocrates-1.5.0-account.zip'
node installer/opensocrates.mjs verify --host claude-chat --asset $accountAsset --checksum $accountChecksum
node installer/opensocrates.mjs export --host claude-chat --asset $accountAsset --checksum $accountChecksum --output $accountOutput
```

검증은 업로드를 수행하지 않습니다. 내보내기는 검증한 ZIP의 바이트를
보존하며, 같은 출력에 다른 내용이나 안전하지 않은 파일 유형이 있으면
거부합니다. 상위 폴더는 Windows 소유자·접근 권한·재분석 지점 검사를
통과해야 합니다. CLI의 install·update·status·diagnose·enable·disable·remove는
계정 동작이 아닙니다. Claude의 Customize > Skills 화면에서 관리합니다.

계정에 필요한 스킬·코드 실행 기능이 제공되는지 확인하고, 독립 계정 ZIP을
업로드해 내용을 검토한 뒤 활성화합니다. OpenSocrates 스킬이 이미 있으면
교체 전에 해당 스킬과 활성화 상태를 백업합니다. 원본 백업을 보존한 채
교체본을 검증합니다. 승인받은 임시 시험 뒤에는 저장한 스킬과 활성화 상태를
복구합니다. 계정 ZIP 대신 네이티브 Mac 연동 ZIP을 업로드하지 않습니다.

평소처럼 자료 종합·판단·메시지 작성을 요청합니다. 호스트 모델이 계정
스킬을 선택하며 훅이나 매 턴 강제 적용은 없습니다. OpenSocrates를 사용해
달라는 명시적 요청으로 선택 누락을 확인할 수 있지만 자동 선택의 증거가
되지는 않습니다. 웹 Chat·Desktop Chat·현재 클라우드 Cowork는 각각
관찰해야 합니다. 내보내기나 업로드 성공만으로 선택, 전체 절차 읽기,
적용 또는 쓸 수 있는 결과가 증명되지는 않습니다.

## Antigravity 대화 애플리케이션

작업공간 또는 전역 범위를 선택합니다. 작업공간을 쓸 때는 예시를 이미
존재하는 로컬 드라이브의 절대 경로로 바꾸고 모든 동작에 같은 경로를 씁니다.

```powershell
$antigravityAsset = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-antigravity-plugin.zip').Path
$antigravityChecksum = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-antigravity-plugin.zip.sha256').Path
$workspaceDirectory = (Resolve-Path -LiteralPath 'C:\Work\Reading Workshop').Path
node installer/opensocrates.mjs verify --host antigravity --asset $antigravityAsset --checksum $antigravityChecksum
node installer/opensocrates.mjs install --host antigravity --workspace $workspaceDirectory --asset $antigravityAsset --checksum $antigravityChecksum
node installer/opensocrates.mjs status --host antigravity --workspace $workspaceDirectory
node installer/opensocrates.mjs diagnose --host antigravity --workspace $workspaceDirectory
node installer/opensocrates.mjs disable --host antigravity --workspace $workspaceDirectory
node installer/opensocrates.mjs update --host antigravity --workspace $workspaceDirectory --asset $antigravityAsset --checksum $antigravityChecksum
node installer/opensocrates.mjs enable --host antigravity --workspace $workspaceDirectory
node installer/opensocrates.mjs remove --host antigravity --workspace $workspaceDirectory
```

작업공간의 설치 위치는 `.agents/rules/opensocrates.md`와
`.agents/skills/opensocrates/`입니다. 설치 상태 관리 명령에서 `--workspace`를
생략하면 전역 기본 위치 `%USERPROFILE%\.gemini\config` 아래의
`rules\opensocrates.md`와 `skills\opensocrates\`를 선택합니다.
`ANTIGRAVITY_CONFIG_DIR`이 설정되어 있으면 그 명시적 설정 경로를 사용합니다.
활성 출처는 하나만 선택합니다. 전역 파일은 IDE에도 보일 수 있습니다.
`--workspace`는 Antigravity에만, `--output`은 계정 내보내기에만 유효합니다.

상시 `always_on` 규칙은 전체 컨트롤러와 선택해서 읽을 영어·한국어 절차를
가리킵니다. 스킬 명령을 매번 반복하지 않고 평소처럼 작업을 요청합니다.
실제 발견과 결과의 유용성은 아래의 호스트 관찰로 확인해야 합니다.

설치기는 없는 관리 폴더를 제한된 권한으로 만들고, 무관한 `GEMINI.md`,
`AGENTS.md`, 규칙과 스킬을 보존합니다. 소유하지 않거나 수정된 충돌은
거부합니다. 업데이트는 비활성화 상태를 유지합니다. 비활성화하면 소유한
콘텐츠를 활성 위치에서 옮겨 두고 활성화하면 복구합니다. 제거는 검증된
소유 콘텐츠에만 적용합니다. 새 연동은 추가 연동의 purge, 신뢰 초기화,
자동 업데이트를 지원하지 않습니다. `--host all`은 기존 Codex 경로를
계속 선택합니다.

Antigravity를 재시작하거나 다시 불러오고 **대화 애플리케이션**에서 새
대화를 시작한 뒤 평소처럼 요청합니다. 비활성화·제거는 기존 대화에 이미
들어간 문맥을 지울 수 없으므로 새 대화에서 시험합니다. 관리 파일이나
IDE 관찰만으로 대화 앱의 발견이 증명되지는 않습니다. 작업공간과 전역의
불러오기는 각각 검증해야 합니다.

## 안전성, 복구와 근거의 한계

Windows 보조 프로그램은 로컬 드라이브 경로를 정규화한 뒤 내부에서 확장
Win32 경로를 사용합니다. 운영체제의 긴 경로 설정을 바꾸지 않고 한글·공백과
260자를 넘는 경로, 더 깊어진 트랜잭션 백업을 처리합니다. 소유권, DACL,
정션·재분석 지점과 압축 파일의 경로 탈출 검사는 그대로 적용합니다.

Windows 경로는 예상한 소유자여야 하며 신뢰하지 않는 주체에게 쓰기 권한이
없어야 합니다. 관리 경로나 상위 경로의 정션, 심볼릭 링크와 기타 재분석
지점은 거부합니다. 동작은 배타적 잠금을 사용하고 상위 경로를 교체하지
못하도록 고정하며, 활성화가 실패하면 트랜잭션 롤백을 시도합니다. 기존의
소유하지 않은 폴더 권한을 다시 써서 안전한 것으로 취급하지 않습니다.

보존된 백업이나 남은 잠금을 보고하면 정확히 보고된 경로를 유지하고,
검증된 소유권·파일 목록과 동작 중인 프로세스가 없는 상태를 확인한 뒤
수동 복구를 판단합니다. 추정하거나 계산한 폴더를 재귀 삭제하거나 아직
동작이 진행 중일 수 있는 잠금을 지우지 않습니다. 안전 검사 실패는
거부 결과이며 강제 설치를 허용하는 뜻이 아닙니다.

소스에는 휴대 가능한 압축 검증, 계정 검증·내보내기와 Windows x64
Antigravity 설치 상태 관리가 구현되어 있습니다. 오프라인 검사는 실제로
측정한 계약만 다룹니다. 실제 계정 적용과 Windows 대화 앱의 불러오기·결과는
정확한 소스·파일에 대해 기록할 때까지 보류입니다. 과거 Mac의 회귀는
[Mac 기록](../evals/v1.5-macos/REPORT.md)에 남으며 소스 안내 변경으로
다시 평가하지 않습니다. 이번 단계는 새 프로젝트 메모리, 대화 수집,
코딩 전용 방법이나 광범위한 작업 조율을 추가하지 않습니다.

제품과 호스트의 개인정보 경계는 [SECURITY.md](../SECURITY.md), 전체 검증과
릴리스 조건은 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고합니다.
