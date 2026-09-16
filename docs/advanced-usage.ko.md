# 설치와 런타임 참고

[English](advanced-usage.md)

OpenSocrates 1.4.0은 Codex만 지원합니다. Apple silicon macOS와 Windows x64용
네이티브 패키지를 제공합니다. Node.js 20 이상과 로그인된 Codex CLI가 필요하며,
사용자는 Python을 따로 설치하지 않아도 됩니다.

## 설치와 업데이트

```sh
npx --yes opensocrates@1.4.0 install
npx --yes opensocrates@1.4.0 status
npx --yes opensocrates@1.4.0 update
```

`--host codex`는 생략할 수 있습니다. 호환 별칭 `--host all`도 Codex만 가리킵니다.
다른 호스트 이름은 설치 상태를 변경하기 전에 거부합니다. 설치 후 새 대화형 Codex
세션에서 OpenSocrates 훅 7개를 검토하고 승인하세요. 승인하지 않은 훅은
비대화형 `codex exec`에서 실행되지 않습니다.

설치기는 압축 파일, 전체 체크섬 목록, 릴리스 식별 정보, 네이티브 대상과 런타임
구조를 검증한 뒤 설치를 준비합니다. 등록 실패 시 이전 설치를 복구합니다.
복구가 안전하게 끝나지 않으면 복구 파일과 안내를 남깁니다. 안내를 검토하기 전에
백업을 임의로 지우지 마세요.

## 1.3.1에서 전환

Codex만 설치했다면 `update`를 사용합니다. 여러 호스트가 설치되어 있다면
기존 버전으로 지원 종료된 통합을 각각 제거합니다.

```sh
npx --yes opensocrates@1.3.1 remove --host claude --purge
npx --yes opensocrates@1.4.0 update --host codex
```

`claude`를 실제 설치한 지원 종료 호스트 이름으로 바꿔 반복합니다. 1.4.0은 여러
호스트가 기록된 기존 상태를 거부하며 다른 통합을 임의로 삭제하거나 상태를
덮어쓰지 않습니다. 이전 설치기의 미완료 정리 결과를 먼저 확인하세요.
지원 종료 호스트의 1.4.0 패키지, 런타임, 업로드 압축 파일은 제공하지 않습니다.

## 제거와 훅 신뢰

```sh
npx --yes opensocrates@1.4.0 remove
npx --yes opensocrates@1.4.0 remove --purge
npx --yes opensocrates@1.4.0 remove --purge --reset-trust
```

일반 제거는 플러그인 등록을 해제합니다. `--purge`는 소유권이 검증된
OpenSocrates 설치 파일, 캐시, 설치 상태, 자동 업데이트 파일도 제거합니다.
알 수 없는 파일, 바뀐 파일 식별 정보, 사용 중인 캐시가 있으면 성공으로 처리하지
않습니다. 사용 중인 캐시만 남았다면 안내된 Codex 프로세스를 닫은 뒤 다시 실행합니다.
대화 기록, 인증 정보, 다른 플러그인과 파일은 보존합니다. 삭제한 캐시를 복원하지는 않습니다.

훅 신뢰는 별도 상태입니다. `--reset-trust`를 지정해야 OpenSocrates의 정확한
7개 신뢰 항목만 제거합니다. 다른 Codex 설정은 유지합니다. 변경할 설정은 격리된
app-server에서 검증하고 원자적으로 교체하며, 안전한 복구가 불가능하면 복구 파일을 보존합니다.

## macOS 자동 업데이트

```sh
npx --yes opensocrates@1.4.0 auto-update enable
npx --yes opensocrates@1.4.0 auto-update status
npx --yes opensocrates@1.4.0 auto-update run --force
npx --yes opensocrates@1.4.0 auto-update disable
```

선택적으로 사용자 LaunchAgent가 안정 버전을 확인합니다. 패키지 검증과 복구를
유지하며 주 버전 변경은 별도 정책 동의가 필요합니다. 설치 상태와 간단한 결과만
기록하고 실행 중인 작업은 종료하지 않습니다. Windows는 수동 `update`만 지원합니다.

## 내려받은 패키지 검증

GitHub Release에서 정확한 버전의 Codex ZIP, 체크섬 파일, 설치기를 받습니다.
Windows에서는 이름 끝이 `-windows-x64.zip`인 파일을 사용합니다.

```sh
node opensocrates.mjs verify --host codex \
  --asset opensocrates-1.4.0-codex-plugin.zip \
  --checksum opensocrates-1.4.0-codex-plugin.zip.sha256
node opensocrates.mjs install --host codex \
  --asset opensocrates-1.4.0-codex-plugin.zip \
  --checksum opensocrates-1.4.0-codex-plugin.zip.sha256
```

`--checksum`에는 해시 문자열이 아닌 파일 경로를 지정합니다. 체크섬은 파일 변조를
찾지만 코드 서명이나 독립적인 출처 인증을 대신하지 않습니다.

## 런타임 동작

Codex 네이티브 훅은 가벼운 탐색 안내를 전달합니다. 활성 에이전트가 판단에 필요한
방법을 고르고 완전한 절차를 읽으며 사용자의 목표, 권한, 출력 요구를 유지합니다.
일반 판단 지점 경로에는 별도 선택 모델 호출이 없습니다.
`decision codex --stream` 프로세스는 조회 상태를 메모리에 유지하지만 새 프로세스나
문맥이 이전의 전체 읽기 상태를 물려받을 수는 없습니다.

호환용 선택 경로는 고정된 OpenAI Codex SDK와 제한 시간, 재시도 없는 요청을 사용합니다.
일반 훅과 구분되는 이전 호환 경로입니다. 시간 초과, 호스트 부재, 잘못된 출력이나
안전하지 않은 문맥에서는 사용자 작업을 막지 않습니다. `diagnose codex`는 패키지
식별 정보와 파일 목록을 확인하며 실제 훅 전달, 전체 읽기, 방법 적용을 증명하지 않습니다.

OpenSocrates 텔레메트리나 원문 프롬프트·대화 저장은 추가하지 않습니다.
임시 저작 콘텐츠와 범주형 증거는 비공개 저장소와 제한된 정리를 사용합니다.
정확한 범위는 [보안 정책](../SECURITY.md)과 [판단 지점 조회](decision-points.ko.md)를 참고하세요.

## 개발과 인수검증

런타임은 `src/opensocrates/`, 방법은 `content/`, 스키마는 `schemas/source/`,
템플릿은 `plugin-src/codex/`가 원본입니다. 생성된 결과를 직접 고치지 마세요.

[CONTRIBUTING.md](../CONTRIBUTING.md)의 소스·네이티브 검사를 실행합니다.
[새 기기 검증](clean-machine-acceptance.ko.md)과
[동일 기기 제거·재설치](reinstall-cycle-acceptance.ko.md)는 서로 다른 증거입니다.
후자는 별도 새 기기 설치를 증명하지 않습니다. [Windows 검증](windows-support.ko.md)은
실제 Windows에서 수행합니다. 공개 후에는 npm과 GitHub 배포물도 검증해야 합니다.
