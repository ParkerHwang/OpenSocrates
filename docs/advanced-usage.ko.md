# 설치 및 런타임 상세 안내

미공개 v1.4.0 Windows x64 후보는 [Windows 안내](windows-support.ko.md)를 따르세요. 아래 기존 공개 macOS 설치 안내와 구분합니다.

v1.3.1 시작 안내는 [README](../README.ko.md)에 있습니다. 소스 체크아웃이 필요한 명령은 저장소 루트에서 실행합니다. 기본 Claude/Codex 흐름은 탐색 안내와 에이전트의 방법 조회이며, 아래의 저장된 접지 파일과 별도 선택기 프로세스 설명은 유지된 이전 어댑터에 해당합니다. 과거 호스트 검증 기록을 v1.3.1의 새 실사용 검증으로 해석하지 않습니다. [현재 전달 방식](decision-points.ko.md)과 [릴리스 근거](v1.3.1-release.md)를 참고하세요.

## 설치

설치 전에 호스트에 로그인하고 명령을 사용할 수 있는지 확인하세요.

- Antigravity: `agy 1.0.0` 이상, 명시적 스킬 전용 지원
- Cursor: Cursor `2.5.0` 이상, 명시적 스킬 우선 지원
- Claude: Claude Code `2.1.205` 이상과 `claude` 명령
- Codex: OAuth 로그인이 완료된 `codex` 명령
- Grok Build: `grok 1.0.3` 이상과 기존 Grok 인증(API 키 추가 불필요)
- OpenCode: OpenCode `1.18.18` 이상, 설정된 공급자/모델 제한 없음

Node.js 20 이상이 필요합니다. npm에 게시된 `opensocrates` 패키지는 외부
의존성이 없는 작은 설치 프로그램입니다. GitHub Releases에서 호스트 패키지를
내려받고 릴리스 체크섬과 모든 파일 체크섬을 검증한 뒤, 소유권 표식이 있는 관리형
마켓플레이스를 등록합니다.

### 준비된 모든 호스트에 설치

```bash
npx --yes opensocrates@1.3.1 install --host all
```

모든 호스트 경로는 지원되는 인증 완료 CLI를 찾고, 어느 호스트도 바꾸기 전에
전체 사전점검을 끝냅니다. 선택된 패키지를 모두 검증·스테이징한 다음 한 릴리스를
트랜잭션으로 활성화합니다. 한 호스트의 활성화가 실패하면 이번 트랜잭션에서 이미
바뀐 호스트도 이전 관리형 등록으로 되돌립니다.

전체 라이프사이클에서 같은 호스트 값을 사용할 수 있습니다.

```bash
npx --yes opensocrates@1.3.1 status --host all
npx --yes opensocrates@1.3.1 update --host all
npx --yes opensocrates@1.3.1 remove --host all
```

### 등록 제거, 소유 payload purge, Codex 신뢰 초기화

일반 `remove`는 기존과 호환되는 좁은 계약을 유지합니다. 선택한 정확한 호스트 등록과
설치 프로그램 관리 루트를 제거하고 업데이터를 조정하지만, 호스트가 소유한
OpenSocrates 플러그인 캐시와 설치 프로그램 desired-state 파일은 남을 수 있습니다.
출력은 남은 것으로 확인된 OpenSocrates 경로와 다음 purge 명령을 표시하며, 이 결과를
완전 제거라고 설명하지 않습니다.

활성 호스트를 닫은 뒤 명시적인 소유 payload purge를 실행하세요.

```bash
npx --yes opensocrates@1.3.1 remove --host all --purge
# 호스트 하나: npx --yes opensocrates@1.3.1 remove --host claude --purge
# OpenSocrates Codex 훅 신뢰만 함께 초기화:
npx --yes opensocrates@1.3.1 remove --host all --purge --reset-trust
# Codex만: npx --yes opensocrates@1.3.1 remove --host codex --purge --reset-trust
```

Purge는 항목을 삭제하기 전에 canonical 경로, 정확한
`opensocrates@opensocrates` 패키지 ID, 매니페스트, 체크섬, 설치 프로그램 소유권
표식을 확인합니다. 관리 루트, 정확한 Claude/Codex 캐시 버전, 비어 있는 Claude
OpenSocrates 플러그인 data 디렉터리, OpenCode 소유 스킬·브리지·사이드카,
OpenSocrates LaunchAgent, 알려진 트랜잭션 잔여물, 그리고 lifecycle lock 해제 뒤의
알려진 최종 설치 프로그램 상태 파일과 빈 상태 디렉터리를 대상으로 합니다.
`~/.claude/plugins`, `~/.codex/plugins`, `~/.opensocrates` 같은 넓은 상위 경로를
재귀 삭제하지 않습니다.

살아 있는 `.in_use/<pid>`가 있는 Claude 캐시, 등록 확인을 막는 누락된 호스트 CLI,
symlink, 잘못된 소유권 표식이나 매니페스트, 비어 있지 않아 소유권을 증명할 수 없는
플러그인 data, 정리·권한 실패가 있으면 결과를 `pending` 또는 실패로 보고하고 명령도
실패 종료합니다. 호스트를 닫거나 보고된 경로를 해결한 뒤 같은 purge를 다시
실행하세요. 완료된 purge는 여러 번 실행해도 같은 결과를 냅니다. 다른 플러그인과
사용자 task·project·chat·plan·history 데이터는 byte-for-byte 보존합니다.

제거 대상 네 가지는 서로 분리됩니다.

- **플러그인 등록:** 일반 remove와 purge는 선택한 호스트에 정확한
  `opensocrates@opensocrates` 등록만 제거하도록 요청합니다.
- **Payload와 설치 프로그램 상태:** `--purge`는 소유권을 검증한 뒤 위에서 설명한
  정확한 cache/data/관리 상태 경로만 제거합니다.
- **호스트 보안 신뢰:** Codex 훅 승인은 payload가 아닙니다. 기본 purge는 신뢰를
  보존하고 그 사실을 보고합니다. `--host codex` 또는 `--host all`에서
  `--reset-trust`를 명시해야 정확한 OpenSocrates 훅 승인 7개만 초기화합니다.
- **사용자 기록:** task, project, chat, plan, session, history 내용은 제거 대상이
  아니며 항상 byte-for-byte 보존됩니다.

Codex CLI 0.145.0에는 범위가 좁은 공식 신뢰 제거 명령이 없습니다. 따라서 이 opt-in
fallback은 정확한 `CODEX_HOME/config.toml`만 대상으로 합니다. 해시를 하드코딩하거나
출력하지 않고 `pre_tool_use`, `post_tool_use`, `pre_compact`, `session_start`,
`session_end`, `user_prompt_submit`, `stop`에 해당하는 canonical OpenSocrates section만
제거합니다. 다른 설정과 플러그인, 주석, 순서, 공백, LF/CRLF 형식은 보존합니다.
symlink, canonical이 아닌 일치 section, 예상 밖 key, 잘못된 config, 지원되지 않는
Codex validator, 동시 변경, 쓰기·검증 실패가 있으면 purge는 partial입니다. 원본
config를 유지하거나 안전하게 rollback할 수 있을 때 트랜잭션으로 복원합니다. 뒤이은
외부 편집 때문에 자동 rollback이 안전하지 않으면 그 편집을 덮어쓰지 않고 소유자
전용 복구 사본을 보존합니다. 완료를 주장하지 않습니다. 재설치하면 이 7개 훅이 새
승인 대상으로 표시될 것으로 예상되지만, 실제 승인 흐름은 별도 host evidence가
필요합니다.

소유자 전용 `~/.opensocrates/desired-state.json`에는 선택 채널, 설치된 호스트,
원하는 활성 버전이 기록됩니다. `status --host all`은 원하는 버전과 사용 가능한
버전, 마지막 확인, 마지막 성공 자동 업데이트, 호스트별 버전 차이를 보여 줍니다.

### 호스트 하나를 명시적으로 설치

기존 사용자와의 호환성을 위해 기본 호스트는 계속 Codex입니다.

```bash
npx --yes opensocrates@1.3.1 install
# 같은 명령: npx --yes opensocrates@1.3.1 install --host codex
npx --yes opensocrates@1.3.1 install --host claude
npx --yes opensocrates@1.3.1 install --host antigravity
npx --yes opensocrates@1.3.1 install --host cursor
npx --yes opensocrates@1.3.1 install --host grok
npx --yes opensocrates@1.3.1 install --host opencode
```

Grok Build는 `~/.grok/plugins/opensocrates`에 네이티브 콘텐츠 전용 플러그인을
설치합니다. 자동 선택과 명시적 호출이 가능한 `/opensocrates` 스킬 하나와 내부
절차 48개만 포함하며, 훅·명령·에이전트·MCP 서버·런처·런타임·중첩 셀렉터 호출은
포함하지 않습니다. 설치 프로그램은 Grok의 기계 판독 상태를 확인하지만 이 정확한
디렉터리만 소유하며 Claude 설치를 변경하거나 삭제하지 않습니다. 자세한 내용은
[Grok Build 지원 경계](grok-support.md)를 참고하세요.

기존 `--host codex` 및 `--host claude` 라이프사이클은 그대로 지원합니다. 호스트별
업데이트는 의도적으로 버전 차이를 만들 수 있고, 이후 `update --host all` 또는
성공한 자동 조정이 desired state에 기록된 모든 호스트를 다시 한 버전으로 맞춥니다.

OpenCode 설치는 `~/.config/opencode` 아래의 `plugins/opensocrates.js`, 소유권
사이드카, `skills/opensocrates/`만 소유합니다. `opencode.json`이나 관계없는
플러그인·스킬은 수정하지 않습니다. 자세한 경계는
[OpenCode 지원 문서](opencode-support.ko.md)를 참고하세요.

Claude 상태는 활성 설치와 설치됐지만 비활성화된 플러그인을 구분합니다. 원하는
설치가 비활성 상태라면 drift로 보고합니다. `install` 또는 `update`를 실행하면 검증된
패키지를 의도적으로 다시 활성화하며, 활성화가 실패하면 롤백이 이전의 활성·비활성
상태를 복원합니다. 설치 프로그램은 Claude 목록 명령에서 실측한 직접 JSON 배열과
명시적인 `marketplaces`/`plugins` 래퍼만 허용합니다. 개인정보를 제거한 2.1.226
픽스처는 `installer/fixtures/claude-cli/`에 있습니다.

### 선택형 자동 업데이트

```bash
npx --yes opensocrates@1.3.1 auto-update enable --host all
npx --yes opensocrates@1.3.1 auto-update status
npx --yes opensocrates@1.3.1 auto-update disable
```

자동 업데이트는 명시적으로 켜기 전까지 비활성화되어 있습니다. macOS LaunchAgent는
한 시간마다 가벼운 확인을 시작하고, desired state는 기본 24시간 간격과 지터,
단일 실행 잠금을 적용합니다. 작업은 선택한 npm 채널을 호출하고 릴리스 및 패키지
체크섬을 검증하며 모든 관리 호스트를 스테이징한 뒤 한 트랜잭션으로 조정합니다.
메이저 버전 자동 업그레이드는 기본적으로 차단되며, 정책을 바꾸려면
`--allow-major`를 명시해야 합니다.

`auto-update enable`에 호스트 하나를 지정하면 자동 업데이트 대상만 좁아집니다.
다른 설치 호스트를 desired state에서 제거하지 않으므로 `status --host all`은 모든
설치를 계속 추적하고, 이후 `update --host all`도 전체 설치 집합을 다시 조정합니다.

업데이터 영수증에는 버전, 시간, 호스트별 결과, 오류 범주만 기록됩니다. 프롬프트,
대화 기록, 자격 증명, 작업공간 경로는 기록하지 않습니다. `auto-update disable`은
LaunchAgent를 언로드하고 삭제하며, `remove --host all`도 관리 호스트를 지우기 전에
같은 정리를 수행합니다.

### Claude 웹 및 Desktop Chat 스킬

이 화면들은 별도로 업로드한 독립형 스킬을 사용할 수 있지만 로컬 플러그인 훅은
실행하지 않습니다.

Chat 독립형 내보내기: **아카이브 계약 검증, 실제 활성화 미검증.**

v1.3.1 독립형 ZIP에는 정본 48개와 한영 참조가 모두 들어 있습니다. 파일 구조·참조
무결성 및 공개 배포 출처와 계정 수준의 업로드는 별도 근거입니다. 로컬 설치기는
기존 custom/synced 스킬을 자동 갱신하지 않습니다.
[버전별 지원 근거](claude-chat-upload-probe.md)를 확인하세요.

정확한 릴리스가 공개되면 checksum을 먼저 검증한 뒤 Claude의 **사용자 지정 → 스킬
→ 스킬 업로드** 화면을 사용하세요. ZIP은 업로더 요구사항에 맞춰 최상위
`opensocrates/` 폴더 바로 아래에 `SKILL.md`를 둬야 합니다. 이 파일은 Claude
Code/Cowork 플러그인 아카이브가 아닙니다. 독립형 패키지는 canonical
`/opensocrates` 스킬 하나만 노출하고, 48개 방법 절차와 엄격도·근거·추적 제어는
내부 참조로 둡니다. Chat은 패키지된 훅을 실행하지 않으므로 훅 기반 자동 선택은
없습니다. Anthropic의
[사용자 정의 스킬 안내](https://support.claude.com/en/articles/12512180-use-skills-in-claude)를
참고하세요.

### 태그가 고정된 GitHub 소스에서 설치

npm 레지스트리를 거치지 않을 때는 공개된 태그로 같은 호스트 옵션을 사용합니다.

```bash
npx --yes github:ParkerHwang/OpenSocrates#v1.3.1 install --host all
npx --yes github:ParkerHwang/OpenSocrates#v1.3.1 install --host claude
npx --yes github:ParkerHwang/OpenSocrates#v1.3.1 install --host codex
npx --yes github:ParkerHwang/OpenSocrates#v1.3.1 install --host opencode
```

### 릴리스 파일 직접 검증

공개 뒤에는
[v1.3.1 릴리스](https://github.com/ParkerHwang/OpenSocrates/releases/tag/v1.3.1)에서
`opensocrates.mjs`, 호스트 패키지, `.sha256` 파일을 내려받습니다. 아래 명령은 이름이 일치하는 공개 asset을 확인한 뒤에 사용하세요. Claude의 예:

```bash
shasum -a 256 -c opensocrates-1.3.1-claude-plugin.zip.sha256
node opensocrates.mjs install --host claude \
  --asset opensocrates-1.3.1-claude-plugin.zip \
  --checksum opensocrates-1.3.1-claude-plugin.zip.sha256
```

다른 호스트 패키지는 `claude`를 `antigravity`, `codex`, `cursor`, `opencode`로 바꾸면 됩니다.

### 1.0 이전 Claude 플러그인에서 이전하기

일부 개발 버전은 대소문자를 구분하는 `OpenSocrates` 마켓플레이스 이름을
사용했습니다. 새 이름은 `opensocrates`입니다. 설치 프로그램은 구형 등록을
감지하지만 자동으로 지우지 않습니다. 설치된 항목을 확인한 뒤 명시적으로
제거하세요.

```bash
claude plugin uninstall opensocrates@OpenSocrates --scope user
claude plugin marketplace remove OpenSocrates --scope user
npx --yes opensocrates@1.3.1 install --host claude
```

관리형 v1.1.0 Claude 설치를 업데이트하면 패키지 트리 전체가 교체됩니다. 따라서
예전의 최상위 방법 스킬 48개, `rigor`, `trace`, 중복 명령은 오래된 항목으로 남지
않고 함께 제거됩니다.

## 사용법

지원되는 호스트를 평소처럼 사용하세요. 요청에 판단, 해석, 진단, 설명, 계획,
근거 조정 또는 다른 구조적 추론이 필요하면 OpenSocrates가 참여할 수 있습니다.
Claude/Codex 네이티브 런타임 화면에서는 다음과 같이 동작합니다.

1. 초기 방법을 고르지 않고 짧은 네이티브 조회 안내를 전달합니다.
2. 판단이 달라질 때 활성 에이전트가 적합한 정본 전체를 조회합니다.
3. 목표·권한·근거·중단 조건과 요청한 출력 형식을 보존합니다.
4. 보호된 내용을 재작성하지 않는 언어별 작성 안내를 제공합니다.
5. 전달·에이전트의 가용성 신고·실제 적용을 구분합니다.

설치 런처의 `decision codex --stream`은 임시 조회 세션을 유지합니다.
새 프로세스나 문맥은 이전 읽기 신고를 이어받지 않습니다.

OpenCode에서는 의존성 없는 안정판 훅이 로컬에서 방법을 고르고 완전한 저작 절차
하나를 같은 메시지 턴에 직접 삽입합니다. 그 컴파일된 절차는 스승 질문 세 개로
시작하며, 네이티브 `/opensocrates` 폴백도 중복 머리말 없이 같은 절차를 읽습니다.
artifact나 추가 모델 호출은 만들지 않습니다.
[OpenCode 지원 경계](opencode-support.ko.md)를 참고하세요.

Antigravity와 Cursor는 명시적 콘텐츠 스킬을 사용하고, Grok Build는 네이티브 스킬
선택 또는 `/opensocrates`를 사용합니다. 세 패키지 모두 생성된 전체 절차가 활성
에이전트가 스스로 정리할 스승 질문으로 시작합니다. 이는 콘텐츠 전용 동작이며
OpenSocrates 훅 전달을 주장하지 않습니다.

Codex에 설치한 뒤에는 대화형 Codex 세션을 한 번 열어 OpenSocrates 훅을 승인해야
네이티브 조회 안내를 사용할 수 있습니다. 이 승인이 끝나기 전에는 `codex exec` 같은 비대화형
화면이 신뢰되지 않은 훅을 조용히 건너뛸 수 있습니다.

### 보존된 이전 영수증 어댑터

다음은 v1.3 기본 조회 안내 훅이 아닌 호환 셀렉터 경로의 설명입니다.
이전 경로의 Claude 훅 화면은 추가 디렉터리 권한 없이 선택 콘텐츠를 읽을 수 있도록 현재
워크스페이스 안의 소유자 전용 `.opensocrates` artifact 영역을 우선 사용합니다.
내부 `.gitignore`가 이 영역을 `git status`에서 숨기고 turn·세션 정리 시 파일을
삭제합니다. 워크스페이스를 사용할 수 없으면 소유자 전용 OS 임시 디렉터리로
대체합니다. 다만 `.gitignore`나 숨김 디렉터리를 무시하지 않는 별도 백업·동기화
도구는 artifact가 존재하는 동안 저작된 OpenSocrates 콘텐츠를 볼 수 있습니다.
artifact에는 원시 프롬프트, 대화 기록, 워크스페이스 콘텐츠, 자격 증명, 셀렉터
추론이 들어가지 않습니다.

Claude 훅 화면에서는 Read 전용 `PostToolUse` 훅이 현재 turn의 정확한 파일을 첫
줄부터 종료 표식까지 읽은 경우에만 인증된 영수증을 만듭니다. `Stop` 시 영수증이나
감사 줄이 없으면 한 번만 보정을 요청하고, `stop_hook_active`로 반복 보정을
막습니다. 일부만 읽었거나 출력이 잘렸거나 실패했거나 다른 파일을 읽은 경우는
인정하지 않습니다. Claude Chat은 이 훅을 실행하지 않으므로 접지 계약이 스킬
지침으로만 적용됩니다.

영수증은 해당 파일에 대한 성공한 `Read` 콜백이 종료 표식까지 도달한 내용을
반환했다는 사실만 기록합니다. 모든 바이트가 전달되었음을 증명하지는 않으며,
이 게이트는 실패 시 열린 상태로 통과합니다. 이 게이트가 방어하는 경계와 방어하지
않는 범위는 [SECURITY.md](../SECURITY.md)를 참고하세요.

선택 수에는 고정 제한이 없습니다. 셀렉터의 내부 제한 시간은 30초이고 재시도하지
않으며 실패 시 통과합니다. 타임아웃, 호스트 오류, 잘못된 출력, 미개입 결정,
안전하지 않은 컨텍스트 또는 사용할 수 없는 훅은 모두 주입 없이 끝납니다.

Claude에서는 필요할 때 같은 컨트롤러를 명시적으로 호출할 수 있습니다.

```text
/opensocrates:opensocrates <요청>
/opensocrates:opensocrates auto <요청>
/opensocrates:opensocrates trace
/opensocrates:opensocrates status
```

위 명령은 Claude Code/Cowork 플러그인용입니다. 독립형 Chat ZIP은 대신
`/opensocrates`를 사용합니다. 플러그인의 등록 명령 inventory에는
`/opensocrates:opensocrates`가 나타나며, bare alias를 source 증거로 사용하면 안
됩니다. 컨트롤러가 내부 방법 참조를 선택해 읽으므로 사용자가 48개 구현
카탈로그를 직접 탐색할 필요가 없습니다.

Claude 셀렉터는 세션을 저장하지 않는 단일 `claude --safe-mode -p` 프로세스를
사용합니다. 안전 모드는 사용자, 프로젝트, 플러그인 커스터마이즈를 끕니다.
`CLAUDE.md`, 스킬, 플러그인, 훅, MCP 서버, 사용자 정의 명령과 에이전트가 여기에
해당합니다. OpenSocrates는 여기에 더해 `--tools ""`, `--disallowedTools "mcp__*"`,
`--strict-mcp-config`를 전달해 기본 도구와 MCP 도구가 남지 않도록 합니다.
셀렉터에는 현재 프롬프트와 저작된 선택 카탈로그만 전달합니다.

관리형 정책(managed policy) 설정은 호스트 신뢰 경계의 일부이며 안전 모드로
비활성화되지 **않습니다**. Anthropic
[CLI 참조 문서](https://code.claude.com/docs/en/cli-reference)는 `--safe-mode`에서도
"관리형 설정 정책은 계속 적용되며 여기에는 정책으로 구성된 훅이 포함된다"고
명시합니다. 관리자가 관리형 `UserPromptSubmit` 훅을 구성한 장비에서는 그 훅이
셀렉터 프로세스 안에서 실행되고, 현재 프롬프트를 표준 입력으로 받으며,
`additionalContext`를 돌려주어 선택에 개입할 수 있습니다. 관리형 플러그인,
관리형 스킬, 관리형 `CLAUDE.md`, 정책으로 구성된 MCP 서버는 로드되지 않습니다.
조직이 관리형 훅을 구성한다면 셀렉터 프롬프트가 그 훅에 노출된다고 보고,
허용할 수 없다면 OpenSocrates 선택 기능을 끄세요.

Codex 셀렉터는 제한된 대화 기록 컨텍스트를 추가로 사용할 수 있으며 다음 설정으로
막을 수 있습니다.

```bash
export OPENSOCRATES_SELECTOR_TRANSCRIPT_ACCESS=0
```

## 개인정보 보호와 보안

OpenSocrates 연동은 로컬에서 실행되고 기존 Claude 또는 Codex 로그인을 사용합니다.
다만 호스트 모델 요청은 해당 호스트 서비스의 약관에 따라 처리됩니다.
OpenSocrates는 백엔드를 호스팅하거나 텔레메트리를 추가하거나 API 키를 저장하거나
사용자의 요청 작업을 대신 실행하지 않습니다.

임시 instruction 파일에는 OpenSocrates가 저작한 콘텐츠만 들어갑니다. 원시
프롬프트, 대화 기록, 워크스페이스 파일, 도구 데이터, 자격 증명과 셀렉터 추론은
OpenSocrates 기록, 로그, 메트릭, 진단 또는 instruction 파일에 쓰지 않습니다.
전체 Read 응답은 메모리에서 종료 표식만 확인하고 보관하지 않습니다. 소유자 전용
접지 영수증에는 artifact 해시, 콘텐츠 리비전, 선택한 방법 ID, 키 기반 인증 및
도구 사용 태그만 저장하며 프롬프트, 도구 출력, 워크스페이스 경로와 artifact 경로는
저장하지 않습니다. `Stop`에서 현재 turn 파일과 영수증을 삭제합니다. `Stop`이 오지
않으면 같은 세션의 다음 `UserPromptSubmit`이 새 turn을 선택하기 전에 이전
`prompt_id` 트리를 모두 삭제하되 새 활성 트리는 보존합니다. `SessionEnd`는 세션에
남은 파일을 삭제하고, 다음 `SessionStart`는 24시간이 지난 비정상 종료 잔여 파일을
삭제합니다.

Claude 셀렉터 시도는 `executable_missing`, `request_rejected`, `spawn_failed`,
`timeout`, `nonzero_exit`, `invalid_output`, `selector_closed`,
`no_intervention`, `selected`라는 고정 라벨만 사용해 소유자 전용 로컬 집계에
누적됩니다. `diagnose`는 이 누적 횟수를 표시합니다. 집계에는 시각, 프롬프트,
대화 기록, 세션·turn ID, 경로, 모델 출력, 자격 증명 또는 추론이 없으며 외부로
업로드되지 않습니다.
집계를 읽을 수 없으면 `diagnose`는 시도 0회라고 단정하지 않고 `unavailable`로
표시합니다. 다음 유효한 셀렉터 결과가 현재 스키마의 손상된 집계를 새로운 제한된
카운트 문서로 교체하며, 알 수 없는 미래 스키마는 해당 새 런타임을 위해 보존합니다.

패키지의 `diagnose` 명령은 설치 파일 목록을 `checksums.sha256`과 대조하고 릴리스
manifest가 실행 중인 버전·호스트·콘텐츠 리비전을 가리키는지도 확인합니다. 단순한
파일 존재 여부로 성공을 추정하지 않고 `verified`, `mismatch`, `unavailable`,
`unverified`를 표시합니다. 이 해시는 로컬 변경이나 손상을 찾지만 manifest와
checksum 파일 자체는 서명되지 않았으므로 패키지 전체를 바꿀 수 있는 공격자에 대한
진본성 증명은 아닙니다.

자동 업데이트를 켜면 앞서 설명한 desired state와 간결한 영수증만 소유자 전용
권한으로 저장합니다. 실행 중인 Claude나 Codex 세션을 검사하거나 종료하지 않습니다.
이미 실행 중인 작업은 로드한 플러그인을 계속 쓰고, 새 작업이 조정된 버전을 자연스럽게
불러옵니다.

취약점 신고와 측정된 지원 경계는 [SECURITY.md](../SECURITY.md)를 확인하세요.

## 개발

소스 저장소에는 네이티브 바이너리와 중간 빌드 결과를 넣지 않습니다.
[uv](https://docs.astral.sh/uv/), Python 3.12, Node.js 20 이상을 설치한 뒤 다음을
실행합니다.

릴리스 후보를 병합하기 전에는
[새 Apple Silicon Mac 인수 테스트 절차](clean-machine-acceptance.ko.md)를 따라
인증된 실제 Claude Code 및 Codex 홈에서 검증하고 개인정보를 뺀 근거 묶음을
확보하세요.

셀렉터의 인증된 Claude 하위 프로세스 계약은 별도의
[선택형 검사](real-claude-selector.md)로 검증합니다. 인증된 v1.1.2 영수증은 실제
하위 프로세스 격리 및 구조화 출력 계약을 통과했으며, 일반 오프라인 테스트는 이
실제 호출을 다시 실행하지 않습니다.

`--max-turns 1` 구조화 출력의 반복 동작은 별도의
[집계 신뢰성 매트릭스](claude-structured-output-reliability.md)로 검증합니다. 인증된
Claude Code 2.1.226의 `host-default` 행은 20/20회를 통과했으며, 관측하지 않은
명시적 모델은 지원된다고 주장하지 않습니다.

패키지 Claude PostToolUse 영수증과 Stop 정리 지연 시간에는 재현 가능한
[Apple Silicon 측정 영수증](claude-hook-timing.md)이 있습니다. v1.1.2에서 관측한
p95는 3초 훅 예산의 절반 이상을 여유로 남겨 타임아웃을 변경하지 않았습니다.

```bash
make bootstrap
make format-check
make lint
make generated-check
make content-check
make docs-check
make governance-check
make security-scan
make smoke
npm test
npm pack --dry-run
make release-check
```

| 경로 | 용도 |
| --- | --- |
| `src/opensocrates/` | 공유 Python 3.12 런타임과 호스트별 셀렉터 |
| `content/` | 정책, 다국어 메시지, 추론 방법, 이론과 예제 |
| `plugin-src/claude/` | Claude 플러그인 템플릿 |
| `plugin-src/codex/` | Codex 플러그인 템플릿 |
| `plugin-src/antigravity/` | 실험적 Antigravity 콘텐츠 전용 플러그인 템플릿 |
| `plugin-src/cursor/` | 실험적 Cursor Agent Plugin 템플릿 |
| `plugin-src/grok/` | Grok Build 네이티브 콘텐츠 전용 플러그인 템플릿 |
| `plugin-src/opencode/` | OpenCode 안정판 브리지 및 네이티브 스킬 템플릿 |
| `schemas/source/` | 정규 스키마 정의 |
| `schemas/v1/` | 생성된 버전 고정 공개 스키마 |
| `installer/` | 외부 의존성이 없는 Node.js GitHub/npx 설치 프로그램 |
| `tools/` | 빌드, 검증, 라이프사이클, 보안, 릴리스 도구 |
| `packaging/` | 네이티브 런처와 패키징 설정 |
| `build/`, `dist/` | 로컬에서 생성되어 릴리스 자산으로 게시되는 파일 |

생성된 스키마와 컴파일된 콘텐츠는 정규 소스와 생성기를 통해 변경해야 합니다.
릴리스 바이너리는 Git 이력이 아니라 GitHub Releases에 둡니다.

