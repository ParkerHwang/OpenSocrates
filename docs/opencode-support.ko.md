# OpenCode 지원

OpenSocrates 1.2는 안정판 `chat.message` 플러그인 훅과 OpenCode의 네이티브
Agent Skill 탐색을 사용한다. 라이브 검증된 최소 OpenCode 버전은 1.18.18이다.

## 동작 방식

`~/.config/opencode/plugins/opensocrates.js` 브리지는 현재 사용자 요청을 로컬에서
제한적으로 분류한다. 판단이 필요한 요청에는 완전한 저작 절차 하나만 합성 텍스트
파트로 추가한다. 그 컴파일된 절차는 저작된 스승 질문 세 개로 시작한 뒤 전체 접지
절차로 이어진다. 이 변경은 같은 모델 턴의 메시지 저장과 모델 디스패치 전에
이뤄진다. 기계적 작업, 명시적 `/opensocrates` 요청, 비정상·과대 입력,
예외는 원래 요청을 바꾸지 않고 fail-open 처리된다.

`~/.config/opencode/skills/opensocrates/SKILL.md`는 항상 사용할 수 있는 명시적
폴백이다. 브리지는 네트워크·추가 모델 호출·서브프로세스·재귀 OpenCode 호출을
하지 않으며 자격 증명, 공급자, 모델 ID를 읽거나 내장하지 않는다. DeepSeek V4
Flash는 라이브 스모크 테스트 대상일 뿐 제품 의존성이 아니다. 베타 V2 플러그인
API도 사용하지 않는다.

네이티브 폴백은 브리지와 동일하게 생성된 질문 우선 절차를 읽는다. 명시적
`/opensocrates` 및 네이티브 스킬 요청은 브리지 활성화를 건너뛰므로 질문 머리말이
중복되지 않는다. 빠진 답이 작업을 바꾸지 않는다면 에이전트는 사용자를 인터뷰하지
않고 질문을 스스로 정리한다.

스승 질문이 `## Purpose`보다 앞에 있는 완전한 절차가 현재 대화에 로드되기 전에는
방법론을 사용했다고 주장할 수 없다는
OpenSocrates grounding 계약은 그대로 유지된다.

## 설치와 소유권

```sh
npx --yes opensocrates@1.2.1 install --host opencode
npx --yes opensocrates@1.2.1 status --host opencode
npx --yes opensocrates@1.2.1 verify --host opencode
npx --yes opensocrates@1.2.1 update --host opencode
npx --yes opensocrates@1.2.1 remove --host opencode
```

`--host all`에도 OpenCode가 포함된다. 설치 프로그램은 다음 경로만 소유한다.

- `~/.config/opencode/plugins/opensocrates.js`
- `~/.config/opencode/plugins/.opensocrates-managed.json`
- `~/.config/opencode/skills/opensocrates/`

`opencode.json`과 관계없는 플러그인·스킬·설정은 수정하지 않는다. 소유하지 않은
동일 경로, 부분 설치, 심볼릭 링크, 안전하지 않은 파일 항목은 거부한다. 설치와
업데이트는 원자적 스테이징 및 백업을 사용하며 이후 단계가 실패하면 이전 파일을
복원한다. 검증은 외부 체크섬, 전체 아카이브 인벤토리, 호스트/릴리스 매니페스트,
브리지, 스킬, 소유권 마커, 설치된 파일 체크섬을 포함한다.

## 검증 경계

- 패키지 결정성, 질문 순서·네이티브 절차 동일성·중복 방지를 포함한 브리지 단위
  동작, 격리된 전체 수명주기: 검증됨
- OpenCode 1.18.18 전역 플러그인/스킬 탐색: 라이브 검증됨
- 실제 생성 브리지의 같은 턴 자동 활성화, `opencode run`, 인터랙티브 TUI:
  라이브 검증됨
- 기존 OpenCode 공급자의 DeepSeek V4 Flash: 공급자별 라이브 스모크 완료
- 네이티브 스킬 호출 영수증: 미검증(스킬 탐색은 라이브 검증됨)
- 그 밖의 공급자/모델 매트릭스: 구현은 공급자 중립적이지만 라이브 영수증 없음

개인정보를 포함하지 않는 증거는
[`docs/evidence/opencode-compatibility-2026-08-13.json`](evidence/opencode-compatibility-2026-08-13.json)에
있다. 호스트 계약은 OpenCode의 공식
[플러그인 문서](https://opencode.ai/docs/plugins/),
[스킬 문서](https://opencode.ai/docs/skills/),
[v1.18.18 소스](https://github.com/anomalyco/opencode/tree/v1.18.18)를 기준으로
확인했다.
