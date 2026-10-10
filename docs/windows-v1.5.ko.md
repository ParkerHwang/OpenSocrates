# Windows에서 OpenSocrates v1.5.0 사용하기

[English](windows-v1.5.md) · [README](../README.ko.md)

설치 후에는 [설정 가이드](setup-guide.ko.md)를 참고하세요. 캡처는 Mac 화면이며, 본문에서 Windows 지원 범위와 계정·로컬 설치를 구분합니다.

v1.5.0은 기존 Codex Windows x64 지원을 보존하고, 휴대 가능한 Claude 계정
스킬의 검증·내보내기와 Antigravity 작업공간·전역 설치 상태 관리를 추가합니다.
Claude의 Windows 범위는 **계정 콘텐츠를 통한 웹 Chat·Desktop Chat·Cowork**입니다.
터미널이나 Desktop Code의 Claude Code 네이티브 연동은 이번 릴리스 범위에서
제외합니다. Apple Silicon 네이티브 Claude와 다른 Mac 연동은 별도의
[Mac 안내](macos-v1.5.ko.md)를 따릅니다.

## 릴리스 설치하기

Windows 11 x64, Node.js 20 이상, Windows PowerShell과 사용할 호스트를 준비하고
호스트의 지원되는 로그인 절차를 따르세요. Codex 네이티브 런타임은 포함되어
있으며 Python은 소스 개발·빌드에만 필요합니다. 로컬 파일 옵션을 생략하면
버전을 고정한 npm 설치기는 [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.5.0)에서
v1.5.0 ZIP과 SHA-256 파일을 받습니다.

Codex를 설치하거나 기존 v1.4 설치를 업데이트합니다.

```powershell
npx --yes opensocrates@1.5.0 install --host codex
npx --yes opensocrates@1.5.0 status --host codex
# 기존 설치를 업데이트할 때:
npx --yes opensocrates@1.5.0 update --host codex
```

대화형 세션에서 Codex 훅 7개를 검토하고 새 대화를 시작하세요. 비대화형 세션은
신뢰되지 않은 훅을 건너뛸 수 있습니다. `status`는 설치·무결성을 보고하며 호스트
신뢰나 자동 전달을 증명하지 않습니다. Codex의 기존 Windows 설치 상태 관리
동작은 [Windows 안내](windows-support.ko.md)를 참고하세요.

## Claude 계정 스킬: 웹 Chat·Desktop Chat·Cowork

이미 존재하고 본인이 소유한 로컬 내보내기 폴더를 선택합니다. 아래 예시
폴더를 실제 경로로 바꾼 뒤 실행합니다. 내보내기는 ZIP의 절대 경로를
요구하며 상위 폴더를 만들지 않습니다.

```powershell
$accountExportDirectory = (Resolve-Path -LiteralPath 'C:\Work\OpenSocrates Exports').Path
$accountOutput = Join-Path $accountExportDirectory 'opensocrates-1.5.0-account.zip'
npx --yes opensocrates@1.5.0 verify --host claude-chat
npx --yes opensocrates@1.5.0 export --host claude-chat --output $accountOutput
```

검증은 업로드를 수행하지 않습니다. 내보내기는 검증한 ZIP의 바이트를
보존하며, 같은 출력에 다른 내용이나 안전하지 않은 파일 유형이 있으면
거부합니다. 상위 폴더는 Windows 소유자·접근 권한·재분석 지점 검사를
통과해야 합니다. CLI의 install·update·status·diagnose·enable·disable·remove는
계정 동작이 아닙니다. Claude의 Customize > Skills 화면에서 관리합니다.

계정에 필요한 스킬·코드 실행 기능이 제공되는지 확인하고, 독립 계정 ZIP을
업로드해 내용을 검토한 뒤 활성화합니다. OpenSocrates 스킬이 이미 있으면
교체 전에 해당 스킬과 활성화 상태를 백업합니다. 원본 백업을 보존한 채
교체본을 검증합니다. 계정 ZIP 대신 네이티브 Mac 연동 ZIP을 업로드하지 않습니다.

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
$workspaceDirectory = (Resolve-Path -LiteralPath 'C:\Work\Reading Workshop').Path
npx --yes opensocrates@1.5.0 verify --host antigravity
npx --yes opensocrates@1.5.0 install --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 status --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 diagnose --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 disable --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 update --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 enable --host antigravity --workspace $workspaceDirectory
npx --yes opensocrates@1.5.0 remove --host antigravity --workspace $workspaceDirectory
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
파일 설치만으로 호스트의 발견이나 결과의 유용성이 증명되지는 않습니다.

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

소스 검사, 파일 무결성, 설치, 계정 활성화, 호스트 불러오기, 전체 절차 읽기와
유용한 결과는 서로 다른 증거입니다. 웹 Chat·Desktop Chat·Cowork와 Antigravity의
작업공간·전역 불러오기는 실제 호스트·계정에 따라 확인해야 하며 서로 대체할 수
없습니다. 일반적인 모델 품질·토큰 비용·속도 향상은 주장하지 않습니다.
[Windows 관찰 기록](../evals/v1.5-windows/REPORT.md)과 [Mac 기록](../evals/v1.5-macos/REPORT.md)은
날짜가 있는 결과와 한계를 보존하며 모든 현재 설치 상태를 나타내지는 않습니다.
이번 릴리스는 새 프로젝트 메모리, 대화 수집, 코딩 전용 방법이나 광범위한
작업 조율을 추가하지 않습니다.

제품과 호스트의 개인정보 경계는 [SECURITY.md](../SECURITY.md), 전체 검증과
릴리스 조건은 [CONTRIBUTING.md](../CONTRIBUTING.md)를 참고합니다.

## 사용 표기가 나오는 조건

적격한 사고 방법의 정본 전체를 읽고 현재 답변에 실제로 적용했을 때만 마지막에
`Powered by OpenSocrates`를 한 줄로 그대로 표시합니다. 모든 언어에서 같은 영어
문구를 사용합니다. 독자 안내만 사용하거나 기계적인 작업만 했다면 표시하지
않으며 네이티브 적용이나 더 나은 결과의 증명도 아닙니다.

## 기여자용 대안: 로컬 파일


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

`dist/`나 릴리스 페이지의 파일을 사용할 때는 설치·업데이트·검증·내보내기에
같은 파일의 `--asset`과 `--checksum`을 함께 지정합니다. 로컬 파일을 절대 경로로
확인한 뒤 소스 설치기를 실행합니다.

```powershell
$accountAsset = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-claude-chat-skills.zip').Path
$accountChecksum = (Resolve-Path -LiteralPath '.\dist\opensocrates-1.5.0-claude-chat-skills.zip.sha256').Path
node installer/opensocrates.mjs verify --host claude-chat --asset $accountAsset --checksum $accountChecksum
node installer/opensocrates.mjs export --host claude-chat --asset $accountAsset --checksum $accountChecksum --output $accountOutput
```

계정 안내의 기존 내보내기 폴더와 `$accountOutput`을 사용합니다. Antigravity는
`opensocrates-1.5.0-antigravity-plugin.zip`과 같은 이름의 체크섬을 선택하고
같은 설치 상태 관리 명령에 두 옵션을 붙입니다. 단독 릴리스 파일
`opensocrates.mjs`를 사용할 때는 검증한 `managed-hosts.mjs`·`windows.ps1`를
같은 폴더에 두세요. npm 패키지는 이 의존 파일들을 포함합니다.
로컬 검증·내보내기는 계정 스킬을 업로드하거나 활성화하지 않습니다.
