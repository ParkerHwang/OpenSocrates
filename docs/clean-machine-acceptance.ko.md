# 새 Apple Silicon Mac 인수 테스트

현재 Pull Request를 병합하기 전에 실제 새 Mac에서 검증할 때 이 절차를 사용합니다.
인증된 사용자의 기본 Claude Code 및 Codex 홈에 실제로 설치하므로 샌드박스 테스트가
아닙니다.

이 절차는 출시 전 후보 검증입니다. 1.1.1은 아직 공개 npm 및 GitHub Release 경로에
없으므로, 도구가 현재 Pull Request의 정확한 커밋에서 성공한 macOS CI 패키지
산출물을 받고 실제 npm 설치 프로그램에 전달합니다. 패키지, 설치 프로그램, 두
호스트 트랜잭션, 등록, 관리형 파일 구조와 상태 계약을 검증합니다. 최종 공개
레지스트리 및 릴리스 다운로드 경로까지 증명하지는 않으므로, 출시 후에는 공개된
한 줄 설치 명령도 별도로 실행해야 합니다.

## 시작 전 준비

관리형 OpenSocrates를 설치한 적이 없는 Apple Silicon Mac을 사용하세요. 테스트
도구는 기존 OpenSocrates 상태 디렉터리, LaunchAgent, 관리형 마켓플레이스 또는
호스트 등록을 덮어쓰지 않고 중단합니다.

다음을 설치하고 로그인하세요.

- [Node.js](https://nodejs.org/en/download) 20 이상
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code/getting-started)
  2.1.205 이상 (`claude auth status` 성공 필요)
- [Codex CLI](https://help.openai.com/en/articles/11381614-api-codex-cli-and-sign-in-with-chatgpt)
  (`codex login status` 성공 필요)
- [GitHub CLI](https://cli.github.com/manual/index) (`gh auth login` 완료 필요)
- Git

Pull Request #33의 최신 커밋에 대한 `CI`가 성공할 때까지 기다리세요. 다른 실행의
산출물이나 이전 커밋은 테스트 도구가 거부합니다.

## 자동 인수 테스트 실행

터미널을 열고 다음을 실행하세요.

```bash
gh repo clone ParkerHwang/OpenSocrates
cd OpenSocrates
gh pr checkout 33
git pull --ff-only
node tools/clean_machine_acceptance.mjs
```

체크아웃은 변경 사항이 없는 상태여야 합니다. 테스트 도구는 다음을 수행합니다.

1. 기본 경로, Apple Silicon macOS, 도구 버전과 호스트 로그인을 확인합니다.
2. 이전 관리형 OpenSocrates 설치가 없음을 확인합니다.
3. 체크아웃, Pull Request, CI 실행, 네이티브 산출물을 한 커밋으로 고정합니다.
4. 통합 릴리스 매니페스트로 Claude 및 Codex ZIP 해시를 검증합니다.
5. 현재 체크아웃을 npm 패키지로 묶고 두 호스트를 하나의 실제 트랜잭션으로
   설치합니다.
6. 소유자 전용 desired state, 정확한 호스트 등록과 버전, Claude의 공개
   `/opensocrates` 스킬 하나, 전체 호스트의 버전 차이 없음을 확인합니다.
7. 홈 디렉터리 아래에 개인정보를 뺀 결과 디렉터리를 만듭니다.

자동 업데이트는 켜지 않습니다. 결과를 자동 업로드하지 않으며 원시 명령 출력,
프롬프트, 대화 기록, 로그인 사용자 정보, 자격 증명, 절대 로컬 경로도 결과에 넣지
않습니다. CI 및 npm 임시 파일은 실행이 끝날 때 삭제합니다.

## 수동 확인 완료 및 결과 전달

자동 검증이 성공하면 `manual-observations.md` 경로가 표시됩니다. 파일을 열고 새로운
Claude Code 및 Codex 작업에서 네 가지 확인을 수행하세요. 각:

```text
PENDING
```

값을 `PASS` 또는 `FAIL`로 바꾸세요. 메모를 추가하거나 프롬프트, 대화 기록, 계정
이름, 자격 증명, 로컬 경로를 붙여 넣지 마세요. 네 결과 필드 외의 변경이 있으면
묶기 명령이 거부합니다.

테스트 도구가 출력한 `--pack` 명령을 그대로 실행하면 결과 디렉터리 옆에 ZIP이
생깁니다. 그 ZIP을 Pull Request #33을 처리 중인 현재 Codex 작업에 첨부해 주세요.
커밋, CI, 무결성, 설치 및 상태 근거가 들어 있어 메인테이너가 결과를 판단할 수
있습니다.

자동 검증이 실패하면 개인정보를 뺀 ZIP을 즉시 만듭니다. 인증 출력은 복사하지 말고
ZIP만 첨부하세요. 체크섬 또는 깨끗한 시작 상태 검증이 실패하면 설치 전에
중단합니다. 호스트 활성화 중 실패하면 전체 호스트 설치 프로그램이 이미 변경한
호스트도 되돌립니다. 설치 후 검증 실패 시에는 진단할 수 있도록 관리 상태를
남깁니다.

## 테스트 설치 제거

결과를 확보한 뒤 두 관리형 호스트 설치를 제거하려면 다음을 실행하세요.

```bash
node installer/opensocrates.mjs remove --host all
```

설치 프로그램이 소유한 OpenSocrates 루트만 제거합니다. Claude Code, Codex 또는
GitHub CLI에서는 로그아웃하지 않습니다.
