# Mac에서 OpenSocrates v1.5.0 사용하기

[English](macos-v1.5.md) · [README](../README.ko.md)

Mac 단계에는 원래 48개 사고 방법, 영어·한국어 독자 안내, Claude 네이티브
진입, 독립 계정 스킬, Antigravity 모듈형 콘텐츠가 구현되어 있습니다. 기존
Codex 지원도 유지합니다. **현재 파일은 로컬 v1.5.0 후보**이며 npm·GitHub에
게시된 릴리스가 아닙니다. 새 Windows 연동은 [다음 단계](v1.5.0/WINDOWS_HANDOFF.md)입니다.

## 로컬 파일 준비

설치기에는 Node.js 20 이상이 필요합니다. Codex·Claude 네이티브 파일은
Apple Silicon Mac용이며 런타임을 포함합니다. 직접 빌드할 때는 Python
3.12와 고정한 uv 환경도 필요합니다.

```sh
uv sync --locked --all-groups
make bootstrap
make generate
make release-check
```

기존 Codex 네이티브 검증 뒤 추가 Mac 파일을 만듭니다. `dist/`의 각 ZIP에는
같은 이름의 `.sha256` 파일이 함께 생깁니다.

| 파일 | 용도 |
| --- | --- |
| `opensocrates-1.5.0-codex-plugin.zip` | 기존 Codex Mac 네이티브 경로 |
| `opensocrates-1.5.0-claude-plugin.zip` | Claude Code 로컬 네이티브 연동 |
| `opensocrates-1.5.0-claude-chat-skills.zip` | 실행 코드가 없는 계정 스킬 폴더 1개 |
| `opensocrates-1.5.0-antigravity-plugin.zip` | 작업공간·전역의 모듈형 규칙과 스킬 |

Antigravity 파일 이름에 plugin이 들어가도 CLI에 등록하는 플러그인은 아닙니다.
`.agents/rules/opensocrates.md`와 `.agents/skills/opensocrates/`를 담습니다.
계정 ZIP의 최상위 폴더는 `opensocrates/`이며 실행용 `bin/`, 훅, 런타임이
없습니다. 활성화하지 않고 파일 구성을 살펴볼 수 있습니다.

```sh
/usr/bin/zipinfo -1 dist/opensocrates-1.5.0-claude-plugin.zip
/usr/bin/zipinfo -1 dist/opensocrates-1.5.0-claude-chat-skills.zip
```

아래 설치·업데이트·검증·내보내기에는 로컬 `--asset`과 `--checksum`을 함께
지정합니다. 생략하면 릴리스 다운로드를 시도하지만 v1.5.0은 게시되지
않았습니다. 이 저장소에서 명령을 실행하세요.

## Claude Code 네이티브 연동

Claude Code CLI를 실행할 수 있게 하고 지원되는 로그인 절차로 로그인하세요.
Desktop의 로컬 Code와 터미널 인증·전달은 별도 확인 항목입니다.

```sh
node installer/opensocrates.mjs verify --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs install --host claude \
  --asset dist/opensocrates-1.5.0-claude-plugin.zip \
  --checksum dist/opensocrates-1.5.0-claude-plugin.zip.sha256
node installer/opensocrates.mjs status --host claude
node installer/opensocrates.mjs diagnose --host claude
```

설치기는 사용자 범위의 `opensocrates-macos` 마켓플레이스를 소유하며 정확한
버전과 활성화 상태를 확인합니다. 무관한 플러그인·설정을 보존하고 소유하지
않은 충돌은 거부합니다. 호스트 권한을 검토한 뒤 새 로컬 Code 대화에서
평소처럼 작업을 요청하세요. 매번 슬래시 명령을 쓰지 않아도 됩니다.
클라우드·SSH·WSL Code 세션은 이 Mac 네이티브 확인 범위에 포함하지 않습니다.

SessionStart와 UserPromptSubmit은 짧은 진입 안내와 설치된 전체 컨트롤러·
안내 위치를 전달합니다. 에이전트는 판단이 실질적으로 달라질 때 적격한
전체 절차를 읽습니다. 이 진입은 대화를 읽거나 데이터베이스를 초기화하거나
별도 선택 모델을 호출하지 않습니다. Stop과 SessionEnd는 읽기 복구를
강제하거나 네이티브 적용 증명을 주장하지 않습니다.

업데이트는 `install`을 `update`로 바꾸고 새 ZIP·체크섬을 함께 지정합니다.
비활성화 상태는 유지됩니다. 아래 동작에는 파일 옵션이 필요 없습니다.

```sh
node installer/opensocrates.mjs disable --host claude
node installer/opensocrates.mjs enable --host claude
node installer/opensocrates.mjs remove --host claude
```

호스트를 다시 불러오거나 재시작하고 실제 출처·버전을 확인하세요. 제거는
소유한 등록·파일에만 적용되며 Claude 앱·계정 스킬·대화 기록·무관한 권한을
삭제하지 않습니다. 새 연동은 `--purge`, `--reset-trust`, 자동 업데이트를
지원하지 않습니다.

## Antigravity 대화 애플리케이션

한 범위를 선택합니다. 작업공간을 쓸 때는 기존 절대 경로를 매번 지정하고,
조회·업데이트·비활성화·활성화·제거에도 같은 범위를 사용합니다.

```sh
node installer/opensocrates.mjs install --host antigravity \
  --workspace /absolute/path/to/workspace \
  --asset dist/opensocrates-1.5.0-antigravity-plugin.zip \
  --checksum dist/opensocrates-1.5.0-antigravity-plugin.zip.sha256
node installer/opensocrates.mjs status --host antigravity \
  --workspace /absolute/path/to/workspace
node installer/opensocrates.mjs disable --host antigravity \
  --workspace /absolute/path/to/workspace
node installer/opensocrates.mjs enable --host antigravity \
  --workspace /absolute/path/to/workspace
node installer/opensocrates.mjs remove --host antigravity \
  --workspace /absolute/path/to/workspace
```

`--workspace`를 생략하면 `~/.gemini/config/rules/opensocrates.md`와
`~/.gemini/config/skills/opensocrates/`의 전역 소유 경로를 선택합니다.
전역 파일은 앱과 IDE 모두에 영향을 줄 수 있으므로 작업공간과 중복하지
않습니다. `diagnose`도 `status`와 같은 범위를 받으며, 업데이트는 설치와
같은 파일 옵션에 `update`를 사용합니다.

설치기는 `GEMINI.md`, `AGENTS.md`, 무관한 규칙과 수정되었거나 소유하지 않은
파일을 보존합니다. 비활성화하면 소유한 콘텐츠를 활성 규칙·스킬 위치에서
옮겨 두고 되돌릴 수 있게 소유 정보를 기록합니다. **대화 애플리케이션**에서
새 대화를 시작하고 일반 요청으로 확인하세요. 기존 대화에 이미 들어간
문맥은 파일을 꺼도 남아 있으므로 비활성화·제거 시험에는 새 대화가 필요합니다.
파일 무결성이나 IDE 관찰만으로 대화 앱의 불러오기가 증명되지는 않습니다.

## Claude 계정 스킬: 웹 Chat·Desktop Chat·Cowork

검증한 독립 ZIP을 새 절대 경로에 내보냅니다.

```sh
node installer/opensocrates.mjs export --host claude-chat \
  --asset dist/opensocrates-1.5.0-claude-chat-skills.zip \
  --checksum dist/opensocrates-1.5.0-claude-chat-skills.zip.sha256 \
  --output /absolute/path/to/opensocrates-1.5.0-account.zip
```

같은 출력에 다른 내용이 있으면 보존하고 충돌을 보고합니다. 파일 옵션을
붙인 `verify --host claude-chat`는 업로드 없이 로컬에서 검증합니다.
계정에는 CLI의 install·update·status·diagnose·enable·disable·remove가
적용되지 않습니다. 계정의 Customize > Skills 화면에서 관리합니다.
`--output`은 계정 내보내기에만, `--workspace`는 Antigravity에만 유효합니다.

계정의 스킬·코드 실행 기능이 사용 가능한지 확인하고 독립 스킬 ZIP을
업로드해 내용을 검토한 뒤 활성화합니다. 같은 이름이 있으면 **기존
OpenSocrates 스킬만** 먼저 백업하고 활성화 상태를 보존합니다. 교체본을
검증하기 전에 원본을 삭제하지 않습니다. 계정 콘텐츠가 Code로 동기화될
때 공개 컨트롤러 출처가 중복되지 않게 확인합니다. 임시 시험은 교체·복구
범위를 먼저 합의하고 저장한 스킬·상태를 복구합니다. 업로드 수용은 활성화나
유용한 결과의 증거가 아닙니다.

평소처럼 자료 종합·판단·메시지 작성을 요청하세요. 호스트 모델이 스킬을
선택하므로 누락되면 OpenSocrates를 사용해 달라고 직접 요청할 수 있습니다.
Chat·Desktop Chat·현재 클라우드 Cowork는 따로 확인합니다. 계정 ZIP에는
네이티브 훅이나 매 메시지 강제 진입이 없으며 네이티브 연동 ZIP을 대신
올려서는 안 됩니다.

## 현재 실제 확인 범위

2026-10-07 Mac 구현 중의 기록입니다. 최종 커밋 기준 확인과 실제 호스트
항목은 구현 인계·PR에 유지해야 합니다.

| 항목 | 관찰한 결과와 다음 확인 |
| --- | --- |
| 로컬 소스·패키지 | Claude 계약 31/31, 기존 설치기 245/245, 새 관리 호스트 17/17 및 Codex 기준·네이티브 검증 통과. 서로 다른 오프라인·패키지 확인입니다. |
| Claude CLI 2.1.285 | 실제 사용자 범위 등록 확인. CLI 인증이 없어 로그인 요청 중이며 인증된 일반 작업 전달은 보류입니다. |
| Claude Desktop 로컬 Code, R1 | 독자 안내 읽기 확인. 첫 결과는 약속을 과장하고 촬영 담당 공백을 빠뜨렸습니다. 부재는 미확인으로 유지하고 이미 아는 사실을 다시 묻지 않도록 안내를 수정했으며 재시험은 보류입니다. |
| Antigravity 앱, 작업공간 R1 | 일반 요청에서 컨트롤러·독자 안내를 읽고 이해관계자용으로 사용할 수 있는 초안 2개를 만들었습니다. 일반 개선이나 전역 불러오기를 증명하지 않습니다. |
| 계정 ZIP | 업로드 형식은 수용되었고 기존 스킬 교체를 요청했습니다. 기존 스킬의 설정 문구는 1.1.2이며 백업은 완료했습니다. 임시 교체·복구 승인과 실제 적용 시험은 보류입니다. |

R1은 워크숍 기록 5개를 종합하는 사례입니다. 현재 정원 24명과 과거 35명,
30명을 받고 싶은 선호, 가예약 상태, 접수 담당 자원봉사자와 합의되지 않은
촬영 담당을 구별해야 합니다. 각 이해관계자에게 필요한 맥락과 구체적인
다음 요청이 있어야 하며 메시지 전송이나 예약은 하지 않습니다. 보류된
실제 확인을 소스 미구현으로 표현하지 않습니다.

`--host all`은 기존 Codex 설치 상태 경로를 유지합니다. 공개 v1.4의 설치·
신뢰·Windows 경계는 해당 버전 안내를 따릅니다. 제품과 호스트의 보관 정책은
[SECURITY.md](../SECURITY.md), 검증·게시 조건은
[CONTRIBUTING.md](../CONTRIBUTING.md)를 참고하세요.
