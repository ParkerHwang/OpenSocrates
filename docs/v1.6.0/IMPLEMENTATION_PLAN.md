# OpenSocrates v1.6.0 구현 계획

출시된 v1.5.0의 콘텐츠를 기준으로 Go 제품을 완성한 뒤, 통합된 코드에서 최종 검증한다. 48개 본문 업그레이드는 v1.6.1 등 후속 릴리스로 분리하며 이 작업의 선행 조건이 아니다. 구조를 정리하는 변경과 사용자에게 새로운 동작을 제공하는 변경을 작업 기록에서 구분한다. 기본 범위와 호스트 목표는 [준비 개요](README.md), 업데이트의 세부 계약은 [배포와 자동업데이트](DISTRIBUTION_AND_UPDATE.md)를 따른다.

## 사용자 요청에 따른 범위 조정: Windows ARM64

구현 착수 후 사용자가 Windows ARM64를 v1.6.0 필수 지원 대상으로 명시적으로
추가했다. 이 결정은 준비 문서의 Windows x64 전용 플랫폼 제한을 변경한다.
현재 구현 범위는 macOS ARM64·Windows x64·Windows ARM64의 Codex CLI/Desktop,
두 Windows 아키텍처와 Mac의 Antigravity 전역/작업공간 관리이며, ARM64 설치·
이전 설치 인수·제거·Go 보조 프로그램·사용자 예약 갱신·복구도 포함한다.
Windows 네이티브 Claude Code는 계속 제외하며 `--host all`은 Codex만 선택한다.
계정 ZIP 검증·내보내기는 콘텐츠 경로로 유지하고 업로드·활성화는 별도다.

v1.5.0 콘텐츠 리비전 3과 48개 본문·양언어 의미·교사 질문·응답 정책·공통
안내는 그대로 고정한다. 본문 개선 세션에 영향을 주지 않는다. 준비 개요·배포
계약·준비 인계의 원래 플랫폼 표는 계획 당시 기록이며 이 명시적 조정이 현재
구현 플랫폼 범위를 정한다. 세부 결정은 [구현 결정](DECISIONS.md)을 따른다.

`opensocrates-v1.6.0-windows-arm64.exe`·`windows-arm64.zip`과 별도 플랫폼
식별·TUF 대상을 생성한다. per-user stable opt-in·24시간·로그인 지연·단일
업데이트 소유자·신뢰/비활성 보존 정책은 x64와 같다. V1 배포 프로필, V3 Windows
보호, V4 lifecycle, V5 배포/인수, V6 예약/자체 교체, V7 생성/CI, V8 실제 검증의
ARM64 대상을 함께 확장한다.

공식 [Codex 0.144.4 배포](https://github.com/openai/codex/releases/tag/rust-v0.144.4)의
aarch64 Windows CLI·app-server와 [GitHub runner 표](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)의
`windows-11-arm`을 확인했다. 이것은 자산·CI 가용성 증거이며 인증된 CLI/Desktop
전달 증거는 아니다. Antigravity의 외부 앱 네이티브 아키텍처·실제 ARM64 로딩은
별도 확인 대상이다.

기존 사용자 VM은 ARM64이며 이전 x64 실행은 에뮬레이션 보조 증거다.
네이티브 ARM64 런타임·권한/잠금/reparse·설치/인수/제거·사용 중 실행파일
교체·Task Scheduler·중단/롤백·호스트 적용은 아직 통과로 주장하지 않는다.
정확한 커밋에서 실제 ARM64 검증 후 인계에 기록한다. 운영 서명·루트·게시 자격,
새 기기·실제 호스트 증거는 플랫폼 확대만으로 충족되지 않는다.

## 릴리스 기준과 본문 작업 분리

현재 준비 작업은 `docs/v1.6.0/`만 소유한다. v1.6.0은 [준비 인계](PREPARATION_HANDOFF.md)에 지정한 v1.5.0 콘텐츠 기준과 기존 스키마·생성 계약을 사용한다. 본문 개선 세션의 새 본문·선택 메타데이터·교사 질문과 관련 의미 변경은 후속 릴리스의 입력으로 별도 관리한다.

구현은 당시의 최신 `main`과 콘텐츠 변경 범위를 재확인한 별도 브랜치에서 시작한다. 최신 소스에 후속 본문 변경이 포함됐다면 v1.6.0에 섞이지 않는 구현·릴리스 기준을 선택해 기록한다. 진행 중인 본문 브랜치에 런타임·설치 변경을 섞거나 그 작업의 원본을 덮어쓰지 않는다. 구현 착수 여부는 v1.6.0 준비와 사용자 지시를 따르며 본문 완료를 기다리지 않는다.

## 소스에서 확인한 작업 경계

| 영역 | 현재 입력 | 개선 방향 |
| --- | --- | --- |
| 설치 관리 | [주 설치 흐름](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/installer/opensocrates.mjs), [추가 호스트 흐름](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/installer/managed-hosts.mjs) | 공통 작업 계획·검증·적용·복구와 호스트별 등록 분리 |
| 서비스 구성 | [실행 구성](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/cli/runtime.py), [호스트 레지스트리](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/hosts/registry.py) | 훅, 선택, 관리, 이전 연결의 구체적 서비스 타입 |
| 선택과 전달 | [결정 세션](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/selector/decision.py), [선택 CLI](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/cli/decision.py) | 입력 검증, 순수 선택, 상태 반영, 응답 생성의 경계 |
| 데이터 계약 | [스키마 매니페스트](../../schemas/source/schema-manifest.yaml), [생성기](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/tools/generate_schemas.py) | Python 클래스명과 분리된 계약, 명시적 검증과 생성 |
| 콘텐츠 정체성 | [해시 규칙](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/content/hashes.py), [프로필 생성](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/tools/build_plugins.py) | 같은 콘텐츠 기준의 결정적 출력과 패키지 식별 |
| 파일 보호 | [Windows 보호](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/windows_security.py), [원자적 쓰기](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/persistence/atomic.py), [잠금](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/persistence/locks.py) | 공통 보호 계약과 OS별 구현, 설치·업데이트에서 재사용 |
| 이전 SDK 연결 | [SDK 경계](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/selector/sdk.py), [격리 worker](https://github.com/ParkerHwang/OpenSocrates/blob/v1.5.0/src/opensocrates/selector/sdk_worker.py) | 외부 app-server 프로토콜을 사용하는 별도 Go 어댑터 |
| 개발과 릴리스 | [Makefile](../../Makefile), [활성 도구](../../tools), [워크플로](../../.github/workflows) | Go 개발 명령과 플랫폼별 릴리스 검사로 치환 |

위 목록은 시작 위치다. 각 영역의 실제 호출자와 테스트, 준비 기준 이후의 소스 차이를 확인한 뒤 세부 파일 소유권을 확정한다.

## Go 모듈과 의존성

런타임 소스가 `src/opensocrates/` 아래에 있다는 현재 규칙을 유지하는 초기 구조는 다음과 같다. 여러 실행 프로그램과 공유 내부 패키지를 두는 방식은 [Go 모듈 구성 안내](https://go.dev/doc/modules/layout)를 참고한다.

```text
go.mod
src/opensocrates/
  cmd/
    opensocrates/
    opensocrates-update-helper/
    opensocrates-dev/
  internal/
    domain/            # 순수 규칙과 상태 전이
    decision/          # 선택과 휘발성 전달 상태
    contracts/         # 데이터 검증과 결정적 직렬화
    content/           # 고정 콘텐츠와 프로젝션
    hosts/             # 닫힌 호스트 어댑터와 배포 프로필
    lifecycle/         # 설치 계획, 적용, 저널, 복구
    update/            # 릴리스 신뢰, 정책, 예약 작업
    platform/          # macOS와 Windows 파일 및 프로세스 보호
    compat/            # 이전 Codex app-server 경로
    diagnostics/       # 내용 없는 상태와 오류 코드
    devtools/          # 생성, 패키지, 문서, 릴리스 검사
```

순수 규칙과 상태 전이는 호스트 CLI, 네트워크, 파일 저장소를 참조하지 않는다. 설치 엔진은 검증한 파일 보호와 호스트 등록 인터페이스를 통해 변경을 수행한다. CLI는 인수 해석과 출력, 서비스 생성만 담당한다. 인터페이스는 실제 외부 경계에 두고 모든 타입을 추상화하지 않는다.

`content/`, `schemas/source/`, `plugin-src/`는 정식 입력 위치로 유지한다. Go 런타임은 고정 패키지 또는 내장 콘텐츠를 사용하며 현재 작업 디렉터리의 임의 콘텐츠로 대체하지 않는다. 콘텐츠 전용 계정·Antigravity 배포물에 실행파일이나 인증 기능을 추가하지 않는다.

Go 도구체인, 모듈 버전, 외부 CLI 버전은 구현 시작 시 확인하고 고정한다. 기본 런타임과 콘텐츠 전용 배포물의 의존성에 이전 SDK 경로를 강제로 포함하지 않는다.

## 포팅과 함께 다룰 리팩토링

### 공통 설치 작업

수동 설치, 수동 업데이트, 예약 업데이트가 같은 사전 확인·스테이징·활성화·확인·복구 코드를 사용한다. 호스트마다 필요한 등록 명령과 파일 대상만 다르게 정의한다. 호스트의 외부 상태까지 포함해 여러 파일을 한 번에 원자적으로 바꿀 수 있다고 가정하지 않는다.

소유 마커, 사전·적용 후 목록과 해시, 비활성 상태, 관련 없는 등록 보존을 작업 계약에 넣는다. 기본 `--host all`의 기존 의미를 조용히 확대하지 않고, 등록된 설치 범위와 가능한 작업을 명시적으로 선택한다.

### 서비스 타입과 오류

기본 선택, 짧은 훅, 관리 명령, 이전 연결에 필요한 의존성을 각각 생성한다. 여러 `Any`와 선택적 필드를 가진 전체 서비스 객체를 Go의 `any`·`nil` 집합으로 그대로 번역하지 않는다. 초기화 결과에 사용할 수 없음과 이유를 명확하게 표현한다.

오류 발생 시 `verification`, `network`, `permission`, `locked`, `host_unavailable`, `protocol_incompatible`, `activation`, `rollback_incomplete` 등의 닫힌 코드와 작업 단계를 부여한다. 실제 분류 이름은 계약으로 고정하며 오류 메시지의 단어로 결정하지 않는다. 원문 오류·프롬프트·대화·인증값을 기록하지 않는다. 훅 실패는 현재처럼 호스트의 정상 작업을 계속 허용한다.

### 입력 검증과 상태 반영

현재 결정 세션의 `_select()`는 scope 갱신 뒤 참여 방식과 라우팅을 검증한다. 새 scope와 잘못된 라우팅이 함께 들어올 때 전달 상태가 먼저 초기화되는 순서를 검토한다. 전체 검증 후 상태를 반영하는 개선은 의도한 동작 변경으로 기록하고, 잘못된 요청·epoch 변경·반복 요청·acknowledgement 사례로 수락한다.

기존 순수 상태 전이와 선택 규칙은 Go에서 같은 의미로 유지한다. 전달, 에이전트의 읽었다는 주장, 실제 방법 적용과 결과 유용성을 같은 상태로 합치지 않는다.

### 데이터 계약과 직렬화

언어 중립 계약은 필드 이름, 필수·선택·null 구분, 열거형, 값 범위, 추가 필드 처리와 스키마 버전을 포함한다. 스키마로 표현할 수 없는 의미 규칙은 명시적인 검증기로 유지한다. Go 기본 JSON 처리만으로 기존 검증을 대체하지 않는다. [Go JSON 문서](https://pkg.go.dev/encoding/json)는 기본 필드 대응과 숫자 처리의 차이를 확인하는 기준이다.

UTF-8, 키 정렬, 이스케이프, 최종 LF, 정수·소수, Unicode 길이, 빈 배열·null·생략의 차이를 포팅 수락 사례에 넣는다. V0에서 고정한 v1.5.0 콘텐츠의 `source_tree_hash`와 `normalized_semantic_hash`를 같은 입력에서 재현한다. 의도한 형식 변경은 버전과 변환 규칙을 따로 지정하며 본문의 의미 변경을 포팅에 포함하지 않는다.

### 호스트와 운영체제 경계

배포 프로필에서 플랫폼, 설치 범위, 자산, 명령, 예약 업데이트 자격과 신뢰 요구를 관리한다. 런타임 훅 어댑터가 없는 콘텐츠 프로필도 표현할 수 있어야 한다. 지원하지 않는 동작은 닫힌 오류로 반환한다.

macOS와 Windows의 파일 API는 분리하되 소유권, 안전한 생성, 경로·링크 거부, 잠금, 쓰기 완료, 교체와 복구 계약을 공유한다. Windows DACL·reparse 방어·보호된 부모 핸들·긴 Unicode 경로·실행 중 파일 제약을 일반 권한 비트나 경로 검사로 치환하지 않는다.

## 작업 묶음과 의존관계

| 작업 | 선행 조건 | 소유 영역과 결과 | 수락 기준 |
| --- | --- | --- | --- |
| V0 릴리스 기준 고정 | v1.6.0 구현 착수 | 최신 소스와 v1.5.0 콘텐츠 기준, 리비전·해시, 기존 검증 기록을 고정 | 기존 콘텐츠 전체를 재현할 수 있고 후속 본문 변경과 분리됨 |
| V1 Go 골격과 데이터 계약 | V0 | Go 모듈, 구체적 타입, 검증·직렬화, 배포 프로필 | 기존 콘텐츠의 계약을 표현하고 형식 변경을 명시함 |
| V2 핵심 실행과 콘텐츠 | V1 | 순수 규칙, 선택·전달, CLI·훅·기존 관리 기능 | 기존 동작의 비교 사례와 의도한 상태 반영 개선 사례를 작성함 |
| V3 플랫폼 보호와 이전 연결 | V1 | 안전한 파일·잠금·프로세스 API, 별도 Go app-server 연결 | 기존 Windows 보호·격리·취소·읽기 제한을 표현하고 미지원 상태 유지 |
| V4 호스트 설치와 복구 | V2, V3 | 공통 작업 엔진, 등록 어댑터, 저널, scope별 상태 | 설치·업데이트·비활성화·제거·재실행·복구 경로를 통합함 |
| V5 직접 배포와 기존 설치 인수 | V4 | 플랫폼별 Go 설치물, 패키지 목록, 기존 상태 변환 | 기존 신뢰·설정·예약 작업을 복구 가능한 방식으로 인수함 |
| V6 자동업데이트 | V4, V5 | 신뢰 메타데이터, 예약 실행, 후보 검증, 적용, 자체 갱신 | Codex macOS ARM64·Windows x64/ARM64 필수 경로와 추가 프로필의 별도 수락 사례를 구현함 |
| V7 활성 도구와 개발 절차 전환 | V1 이후 진행, V2-V6과 통합 | 생성·검증·패키지·문서·보안·릴리스 도구, CI, 기여 지침 | 최종 활성 경로에 자체 Python/Node.js 의존성이 남지 않음 |
| V8 최종 통합 검증과 릴리스 준비 | V0-V7 전체 통합 | 비교 결과, 네이티브 결과, 정확한 리비전, EN/KO 안내 | 아래 검증과 실제 지원 주장에 필요한 증거가 완료됨 |

V3의 플랫폼 부분과 이전 연결은 파일 소유권을 분리하면 독립 구현이 가능하다. V7도 계약이 확정된 영역부터 작성할 수 있다. 공유 타입, 프로필, 저널 형식, 버전, 생성 입력과 CI는 통합 담당자가 소유한다. 여러 작성자가 같은 파일을 변경하지 않는다.

V2-V7의 수락 기준은 구현할 동작과 사례의 범위다. 각 묶음 직후에 테스트·린트·빌드를 실행하는 단계로 해석하지 않는다. 최종 실행 결과는 V8에 기록한다.

## 이전 SDK 경로

현재 Python SDK와 외부 CLI의 버전 일치, 격리 실행, 제한된 context 도구, 취소·프로세스 정리와 안전한 통과를 Go 프로토콜 어댑터에 옮긴다. Python SDK를 호출하는 작은 래퍼를 남기는 방식은 Go 통일의 완료로 인정하지 않는다.

기본 선택 경로는 이 어댑터 없이 동작한다. 외부 Codex app-server의 프로토콜과 재배포 조건은 V3에서 고정한 버전의 공식 자료와 실제 입력·응답으로 확인한다. 현재 Windows에서 사용할 수 없는 인증 복사·POSIX context 기능을 포팅만으로 지원했다고 주장하지 않는다. 보존할 기능의 동등성을 확인할 수 없다면 지원 축소 여부를 명시적으로 결정하고 기록한다.

## 최종 검증 순서

일반 구현 중에는 코드와 기존 테스트를 읽고 필요한 테스트를 작성한다. 전체 변경을 통합한 뒤 안정된 리비전에서 아래 검증을 실행한다. 명시적 디버깅, 구현을 막는 실제 오류, 사용자 요청이 있을 때만 최소한의 중간 진단을 수행한다.

1. 생성 결과·스키마·EN/KO 일치와 Go 형식·타입·정적 검사를 확인한다.
2. 기존 선택·전달·저장 상태·콘텐츠 출력과 Go 결과를 같은 합성 입력으로 비교한다. 같은 기준·입력·환경의 기존 검증 결과만 재사용하고 후속 본문 세션의 결과로 대체하지 않는다.
3. 불완전·과대·잘못된 입력, 시간 제한, 재귀 방지와 정리를 확인한다. 파서·ZIP 경계에는 필요한 [Go fuzzing](https://go.dev/doc/security/fuzz/) 사례를 사용한다.
4. 설치·이전 버전 인수·업데이트·제거·동시 실행·단계별 강제 종료·변경된 백업 보존·예약 작업 복원을 검사한다.
5. macOS ARM64·Windows x64·Windows ARM64에서 각각 실제 패키지, 권한·잠금, 긴 경로, 실행 중 파일, 업데이터 자체 교체를 각각 확인한다.
6. 실제 패키지의 훅 시작 시간을 측정한다. 현재 [Codex 훅 시간 기준](../codex-session-start-timing.md)의 2초 호스트 제한 안에서 p95 1초 이하 여유를 유지하고, 속도 향상은 측정 결과로만 보고한다.
7. 주장할 CLI·Desktop·account·workspace·global 적용을 각각 확인한다. 설치·내보내기·등록만으로 읽기·적용·결과 개선을 주장하지 않는다.
8. 통합 담당자가 최종 diff를 기준으로 코드 검토, 구체적 보안 경계 검토와 결과 확인을 맡긴다. 검토 중 파일을 수정하지 않고, 발견한 문제를 고친 뒤 영향받은 검사만 다시 수행한다.

기존 Python 구현과의 비교 실행은 최종 검증용 별도 기준 소스에서 할 수 있다. 그 비교용 환경을 새 제품의 실행·빌드 의존성으로 배포하지 않는다. 누락된 네이티브·실제 호스트 증거는 완료 보고와 지원 표에 그대로 남긴다.

## 릴리스 준비와 후속 작업

릴리스 준비 시 Go 설치법, 일회성 npm 설치 인수, 자동업데이트 설정·중지·복구, 호스트별 적용 시점과 지원 표를 EN/KO로 정리한다. 현재 생성 입력·지침·관련 검사 변경은 함께 반영하며 검사 삭제로 새 언어 전환을 통과시키지 않는다.

48개 본문 업그레이드는 v1.6.1 등 별도 릴리스에서 반영한다. 해당 릴리스는 새 콘텐츠 리비전·해시·필드 변경과 Go 생성 결과를 함께 검증하고, 본문이 달라지면 기존 결과 품질 증거를 자동 승계하지 않는다. v1.6.0 업데이터는 이러한 후속 콘텐츠 묶음을 버전·호환성 정책에 따라 전달할 수 있어야 한다.

Homebrew·WinGet, 추가 플랫폼, 계정 스킬 자동 업로드, 광범위한 GUI와 항상 실행되는 관리 서비스는 후속 후보로 둔다. 실제 기능 손실을 숨기는 이전 경로 삭제는 별도 범위 결정이 필요하다. 구현 완료, 로컬 검증, 릴리스 검증, 실제 호스트 증거, 병합·태그·게시를 각각 기록한다.
