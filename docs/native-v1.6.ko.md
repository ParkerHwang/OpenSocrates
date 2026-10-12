# 네이티브 설치·이전 설치 인수·업데이트 — v1.6.0 후보

[English](native-v1.6.md) · [설정](setup-guide.ko.md) · [보안](../SECURITY.md)

아직 출시하지 않은 Go 구현입니다. 아래 명령은 후보 동작을 설명하며 소스 검사
통과가 운영 릴리스 검증은 아닙니다. 실제 결과·커밋·환경·남은 조건은 구현 인계에
기록합니다. 현재 Mac의 Developer ID identity와 정본 Team ID는 확인했습니다.
공증·보호된 CI 서명 환경·Windows 서명·운영 업데이트 루트는 별도 조건입니다. 별도 승인
없이 사용 중인 설치를 후보로 교체하지 마세요.

## 다운로드와 최초 설치 신뢰

정식 배포는 [GitHub Releases](https://github.com/ParkerHwang/OpenSocrates/releases)의
네이티브 `opensocrates`/`opensocrates.exe`와 플랫폼 묶음입니다.

| 대상 | 묶음 |
| --- | --- |
| macOS ARM64 | `opensocrates-v1.6.0-darwin-arm64.zip` |
| Windows x64 | `opensocrates-v1.6.0-windows-x64.zip` |
| Windows ARM64 | `opensocrates-v1.6.0-windows-arm64.zip` |

묶음에는 `bundle-manifest.json`, 관리·런타임 실행파일, Go 교체 보조 프로그램,
스키마·콘텐츠 식별 정보, 호스트 패키지가 들어갑니다. Windows에는 네이티브
Claude Code가 없습니다. 사용자 기기에 Go·Python·Node.js·npm은 필요 없지만
네이티브 등록·사용을 위한 외부 호스트 실행파일과 로그인은 필요합니다.

실행 전에 공개한 플랫폼 서명·전달 정책과 독립적으로 신뢰한 업데이트 루트로
설치기 출처를 확인하세요. 다운로드 옆 체크섬은 손상만 찾고 출처 인증을
대신하지 않습니다. Mac 서명·notarization, Windows 서명 정책, 운영 루트·키 관리가
완료되기 전에는 최초 설치 신뢰를 주장할 수 없습니다. 개발 신뢰 자료는 격리
검사용입니다.

## 수동 설치 상태 관리

패키지는 절대 경로를 사용합니다. Mac 예제의 `./opensocrates`는 네이티브
실행파일입니다. Windows에서는 `.\opensocrates.exe`와
`"C:\Downloads\opensocrates-v1.6.0-windows-x64.zip"` 또는 `windows-arm64`
대응 파일 같은 로컬 드라이브 절대
경로를 사용하세요. 상태 확인·갱신·끄기·켜기·제거에서 동일한 전역/작업공간
범위를 선택합니다.

```text
./opensocrates verify --host codex --package /absolute/path/to/bundle.zip
./opensocrates install --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
./opensocrates manage diagnose --host codex
./opensocrates update --host codex --package /absolute/path/to/new-bundle.zip
./opensocrates remove --host codex
```

Codex 활성 상태는 호스트 자체 설정에서 관리합니다. Go 관리 도구는 설치·이전·
업데이트 때 그 상태를 보존합니다. `enable`·`disable` 관리 명령은 Claude와
Antigravity를 지원하며 Codex에서는 미지원 결과를 반환합니다.

기본값과 `--host all`은 Codex만 가리키며 모든 연동을 다루지 않습니다. 다른
프로필은 명시합니다.

```text
./opensocrates install --host claude --package /absolute/path/to/bundle.zip
./opensocrates install --host antigravity --package /absolute/path/to/bundle.zip --workspace /absolute/path/to/existing/workspace
./opensocrates status --host antigravity --workspace /absolute/path/to/existing/workspace
./opensocrates export --host claude-chat --package /absolute/path/to/account.zip --output /absolute/path/to/opensocrates-account.zip
```

네이티브 Claude는 Mac만 지원합니다. Antigravity에서 `--workspace`를 생략하면
전역입니다. 작업공간을 자동 탐색·등록하지 않습니다. 계정 `verify`·`export`는
로그인·훅·업로드 없이 콘텐츠를 확인합니다. 수동 교체·업로드 전 이전 계정 스킬과
활성 상태를 백업하세요. 로컬 작업은 계정 콘텐츠를 활성화하지 않습니다.

검증은 패키지 목록·식별·로컬 등록을 확인하며 에이전트 읽기·적용이나 실제
호스트 전달을 증명하지 않습니다. 모르는 파일·수정 파일·다른 소유자·링크/reparse·
안전하지 않은 대상은 지우지 않고 충돌로 남깁니다. 일반 제거는 선택한 소유 연동만
다룹니다. `remove`를 광범위한 purge·신뢰 초기화·npm 제거로 해석하지 마세요.

## npm 설치의 일회성 인수

출시된 v1.5.0 설치를 인수 기준으로 사용합니다. 소유권·버전·desired state·목록·
등록·비활성 상태·이전 예약 작업을 먼저 확인합니다. 명시한 소유 연동만 인수합니다.

```text
./opensocrates adopt --host codex --package /absolute/path/to/bundle.zip
./opensocrates status --host codex
```

네이티브 상태·묶음을 별도 준비하고 이전 상태·예약 작업 복구 자료를 검증해
보존합니다. 이전 업데이트 소유자를 조정하고 등록·무결성을 확인한 뒤 확정합니다.
배타권을 얻을 수 없으면 기존 설치를 유지합니다. 두 업데이터가 같은 설치를
변경하지 않도록 하세요. 기존 opt-in·설정·신뢰·비활성 상태를 보존하고 지원 종료
다중 호스트 상태를 재해석하지 않습니다. npm 패키지·캐시·사용자 내용을 무차별
삭제하지 않으며 이전 패키지는 업데이트 소유권을 내려놓은 뒤 남아 있을 수 있습니다.

실패 시 파일·상태·등록·예약 작업을 검증한 이전 상태로 복구하거나, 복구 파일을
보존하고 미완료를 보고해야 합니다. 실제 네이티브 기기에서 확인하기 전에는 운영
인수 지원을 주장하지 않습니다.

## 자동업데이트와 적용

```text
./opensocrates auto-update enable --host codex
./opensocrates auto-update status --host codex
./opensocrates auto-update run --host codex
./opensocrates auto-update disable --host codex
```

기본 정책은 opt-in·`stable`·24시간·로그인 후 5분 지연입니다. 로그인된 사용자의
Mac LaunchAgent 또는 Windows 작업 스케줄러를 사용하며 서비스·암호·토큰을
저장하지 않습니다. 훅은 네트워크 확인·설치를 하지 않습니다. 오프라인에서는
현재 버전을 유지합니다. 설정 정책·실제 OS 예약 상태·후보 무결성·적용 상태를
구분하며 작업 부재를 등록 성공으로 보고하지 않습니다.

TUF root/timestamp/snapshot/targets의 서명 임계값·만료·단조 버전·일관성,
제한된 허용 전송·플랫폼·목록·런타임/스키마 호환성을 확인합니다. 메이저와
비호환 스키마는 자동 적용을 차단합니다. 로컬 롤백이 네트워크 롤백 방지 기준을
낮추지 않습니다. 루트 교체는 이전·새 루트의 승인이 필요합니다. 없거나 만료·
불일치한 메타데이터와 미제공 운영 루트는 신뢰를 완화하지 않고 사용 불가로 남깁니다.

v1.6.0 예약 대상은 Codex macOS ARM64·Windows x64/ARM64입니다. Claude·Antigravity는
각 등록·reload·비활성·무결성·복구 검증을 마칠 때까지 수동 관리합니다. 계정 ZIP은
수동 내보내기·업로드이며 계정 자동화를 주장하지 않습니다.

사용자 설정·상태와 버전 묶음은 `~/.opensocrates/` 아래 `bundles`, `bin`,
`native-state.json`, `transactions`로 분리합니다. 시작한 프로세스는 자신의 묶음을
유지합니다. 관리 CLI·업데이터 교체도 동일한 검증된 작업이며 Windows 실행파일
사용 중에는 Go 보조 프로그램을 사용합니다. 실행 중·복구용 묶음은 보존합니다.
파일 적용 완료와 호스트 적용 대기는 다를 수 있습니다. 바뀐 훅은 호스트에서
검토하고 필요한 reload·새 세션을 사용하세요. 대화를 읽거나 종료해 강제 적용하지
않습니다.

## 복구

```text
./opensocrates recover --transaction TRANSACTION_ID
```

내구성 저널은 소유 대상의 이전/이후 목록·검증한 백업을 연결합니다. 저널만
믿지 않고 실제 파일·등록을 확인합니다. 잠금·저널·수정된 교체 파일·백업을 임의
삭제해 충돌을 우회하지 마세요. 준비 중 중단은 현재 버전을 유지하고 적용 중
중단은 안전한 완료 또는 검증한 이전 상태 복원을 요구합니다. 둘 다 안전하지
않으면 파일을 남기고 `rollback_incomplete`와 로컬 복구 안내를 보고합니다.
로컬 경로는 비공개 운영 정보이며 공개 결과에 작업공간 경로·원문 오류를 넣지
않습니다. 파일·등록·상태·예약 소유권이 일치해야 롤백 검증이 끝납니다.

## 호환성과 의도한 변경

패키지 전달·작업/복구·호스트 등록·OS 보호·배포 프로필·런타임 어댑터·명확한
서비스/오류 타입을 분리하는 것은 호환성을 유지하는 리팩토링입니다. wire·저장
상태·정본 바이트·Unicode·숫자 정밀도·unknown fields·생략/null/빈 값·안전한 통과
훅을 보존합니다. 이전 선택기는 opt-in·`0.144.4` 고정 Go Codex app-server 어댑터이며
가용성 확인은 인증된 동작 증거가 아닙니다. 일반 판단
경로에는 추가 모델·인증 호출이 없습니다.

의도한 변경은 네이티브 직접 배포·인수, Windows 예약 갱신, 서명된 호환 안정
갱신과 자체 교체 복구입니다. 중복 JSON 키와 짝 없는 Unicode surrogate는 거부합니다. 판단 요청은 문맥·scope
변경 전에 모두 검증하므로 잘못된 라우팅이 이전 가용 상태를 지우지 않습니다.
안전하지 않거나 지원하지 않는 새 설정은 기본값으로 덮어쓰지 않습니다. 방법 본문 업그레이드는 제외합니다.
기준 v1.5.0 태그는 `cf6634310afcf5d5ce58484e67a73151bb4c5999`, 콘텐츠 리비전은
`3`입니다. 전체 해시·목록은 V0 구현 기록에서 확인하며 전달 안내 변경이 방법
의미 변경을 허용하지 않습니다.

## 남은 릴리스 검증

정확한 최종 명령·결과는 구현 인계에 기록합니다. Mac·Windows의 실제 설치·인수·
제거·예약·자체 갱신·중단·롤백, ACL·reparse·동시성·수정 파일, 오프라인·서명
메타데이터 변조 사례는 관찰된 결과가 필요합니다. 크로스 컴파일은 Windows
통과가 아닙니다. 별도 새 기기·인증된 호스트 적용·운영 키 관리·플랫폼 서명·공개
자산 검증은 명시적 증거가 나올 때까지 남은 조건입니다. 과거 v1.5/v1.4 증거를
Go 릴리스로 승격하지 않습니다. 이 문서는 병합·태그·게시·사용 중 설치 교체를
승인하지 않습니다.

## 훅 명령과 신뢰 설정

설치 진단은 `opensocrates manage diagnose --host HOST`이며 기존 런타임
`diagnose codex` wire 동작과 구분합니다. macOS 명령은 경로 문자열 치환 대신
따옴표로 감싼 OS 환경 참조 `$PLUGIN_ROOT`·`$CLAUDE_PLUGIN_ROOT`를 사용합니다.
Windows Codex CLI/Desktop 훅은 정상적으로 상속한 기본 PowerShell 문맥만
검증 대상입니다.

```text
& "$env:PLUGIN_ROOT\runtime\windows-x64\opensocrates.exe" hook codex session_started
```

이는 외부 OS·호스트 설정의 명령 하나이며 자체 PowerShell 래퍼가 아닙니다.
사용자 지정·cmd fallback 셸은 지원하지 않고 명시적으로 안전하게 통과합니다.
ARM64는 같은 명령 형식의 `runtime/windows-arm64/` 경로를 사용하며
셸 경계를 변경하지 않습니다.

운영 신뢰 정본은 `config/update/root.json`·`config/update/identities.json`이며
Go 생성으로 `internal/update/trustconfig`에 내장합니다. 후보에는 승인된 운영
루트·Windows 게시자 식별이 없습니다. Mac Team ID는 사용자 요청으로 발급한
Developer ID 인증서에 연결되며 로컬 서명과 공증·운영 검증은 구분합니다.
업데이트 정책·범주형 결과·승인한 TUF 상태는
별도 비공개 설치 상태입니다.

컴파일 콘텐츠 묶음은 릴리스 메타데이터 `product_version`만 `1.6.0`으로 바꿉니다.
방법·projection·응답 정책 식별은 리비전 `3`이며 본문 개선이 아닙니다.

## 명시적 Codex purge·신뢰 초기화

```text
./opensocrates remove --host codex --purge
./opensocrates remove --host codex --purge --reset-trust
```

과거 순차 정리와 달리 purge는 제거할 모든 대상을 변경 전에 확인합니다. 검증한
소유 연동·이전 상태만 제거하고 소유 예약 작업을 끕니다. 공통 관리 도구·묶음,
npm 패키지, 대화·기록·다른 파일은 남깁니다. 미확인·수정·링크·사용 중
`.in_use` 캐시는 안전하게 완료를 차단·보류합니다.

`--reset-trust`는 OpenSocrates의 정확한 훅 상태 항목 7개만 명시적으로
제거합니다. 관련 없는 TOML 바이트·주석·BOM·개행·호스트 설정을 보존하고
격리·무인증 Codex app-server에서 제한된 버전·stdio 기능 확인과 필수
`--strict-config` 지원으로 이전·후보 설정을 검증한 뒤 저널 작업으로 교체합니다.
이 관리 기능 확인은 이전 선택기의 `0.144.4` 고정과 별도입니다. 모르는 기능은
사용 불가로 남기며 잘못된 설정을 기본값으로 대체하지 않습니다. 승인을 보존하려면 지정하지 마세요. 자동 승인은
하지 않으며 실제 네이티브 제거·복구·호스트 신뢰 증거는 별도로 필요합니다.

신뢰 초기화는 같은 lifecycle 잠금 아래 별도로 검증·완료한 작업이며 호스트 등록
해제도 설정을 바꿀 수 있으므로 purge snapshot·등록 변경보다 먼저 수행합니다.
후속 purge가 실패해도 명시적으로 완료한 신뢰 초기화는 되돌리지 않습니다.
`trust_transaction`을 별도로 보고합니다.

운영 게시에는 보호 환경 secret `OPENSOCRATES_RELEASE_ADMIN_READ_TOKEN`도
필요합니다. 이 저장소의 Administration:read만 부여하며 GitHub
`/immutable-releases`의 정확한 GET에만 사용합니다. 릴리스 변경은 기존
contents:write workflow 토큰으로 수행합니다. 읽기 권한이 없거나 부족하면
immutable 검사를 완화하지 않고 게시를 막습니다. 운영 루트·게시자·서명 자원과
함께 필요한 게시 자격이지 릴리스 검증 증거는 아닙니다.

## 사용자 요청에 따른 Windows ARM64 범위 조정

원래 준비는 Windows x64만 대상으로 했지만 사용자가 이후 명시적으로
Windows ARM64를 v1.6.0에 추가했습니다. Codex CLI/Desktop, Antigravity 전역/
작업공간 관리, 네이티브 설치·인수·제거, Go 보조 프로그램 자체 교체, 사용자
예약 갱신이 대상입니다. `--host all`의 의미, Windows 네이티브 Claude Code
제외, 수동 계정 업로드, v1.5.0의 48개 본문 기준은 바꾸지 않습니다. 계정
검증·내보내기는 모든 지원 대상에서 실행 코드 없는 콘텐츠 경로입니다.

단독 `opensocrates-v1.6.0-windows-arm64.exe`와
`opensocrates-v1.6.0-windows-arm64.zip`을 받습니다. 묶음 내부는
`bin/opensocrates.exe`·`bin/opensocrates-update-helper.exe`, 호스트 런타임은
`runtime/windows-arm64/opensocrates.exe`입니다. TUF 대상
`stable/windows-arm64/opensocrates.archive`는 별도 플랫폼 식별을 갖습니다.
단독 ARM64 실행파일로 처음 설치하는 예입니다.

```text
.\opensocrates-v1.6.0-windows-arm64.exe install --host codex --package "C:\Downloads\opensocrates-v1.6.0-windows-arm64.zip"
.\opensocrates-v1.6.0-windows-arm64.exe status --host codex
```

`.\opensocrates.exe` 예제는 묶음의 `bin/`에서 푼 네이티브 실행파일을 뜻합니다.
단독 다운로드 파일은 실제 내려받은 이름으로 실행하세요.

예약은 사용자 opt-in·stable·24시간·로그인 지연이며 신뢰·비활성·단일 소유자를
보존합니다. 실제 ARM64 네이티브 CI의 설치·ACL/reparse/잠금·보조 프로그램·
중단·롤백·예약 결과는 구현 인계에 기록합니다. 운영 서명·새 기기·실제 호스트
적용 증거는 별도이며 에뮬레이션 결과를 네이티브 통과로 승격하지 않습니다.

공식 [Codex 0.144.4 릴리스](https://github.com/openai/codex/releases/tag/rust-v0.144.4)에
`aarch64-pc-windows-msvc` CLI·app-server 실행파일이 있습니다. 배포 가용성
증거이지 인증된 CLI/Desktop 실제 전달 증거는 아닙니다. GitHub
[runner 안내](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)는
네이티브 CI용 `windows-11-arm`을 명시합니다. Antigravity의 네이티브 앱
아키텍처와 실제 ARM64 불러오기는 별도 미검증입니다. OpenSocrates 소유 규칙·
스킬 관리 지원이 외부 앱의 네이티브 가용성까지 증명하지 않습니다.

기존 Windows VM은 ARM64입니다. 그곳의 x64 실행은 에뮬레이션 보조 증거이며
Go ARM64 네이티브 검증을 대신하지 않습니다. 운영 서명·루트·게시 자격과
새 기기·실제 호스트 증거는 이 대상도 별도 릴리스 조건입니다.
