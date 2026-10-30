# 일반 사무 업무를 돕는 AI 플러그인: 개발 착수 패키지

**상태:** 제품 기획 및 개발 준비. 구현·호스트 지원·사용자 효과·릴리스는 확인되지 않았다. 기준 main: `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`. 사용자 지정 첫 실제 사용 검증은 Claude이며, 일반 Chat·Cowork·Code를 별도 표면으로 기록한다.

목표 사용자는 **비개발직군의 일반 사무직 전반**이다. 업무 사실 라이브러리는
업무에 필요한 맥락을 사전에 전달하고 새로 확인된 내용을 자동 저장하기 위한
핵심 구성요소다. 제품은 회의, 문서, 조사, 분석, 기획, 운영, 소통 등 서로 다른
일을 돕는다. 이 예시 목록은 직군·업무의 허용 목록이 아니며, 모든 직군에서
이미 기능이나 효용이 검증됐다는 주장이 아니다. 새 업무로 관련 기록이 없거나
남길 내용이 없어도 가능한 작업과 필요한 사고 지원을 계속한다.

진행 기록: [기획 이슈 #146](https://github.com/ParkerHwang/OpenSocrates/issues/146) · [초안 PR #147](https://github.com/ParkerHwang/OpenSocrates/pull/147). 이 패키지와 실제 구현·호스트 시험은 별도 작업이다.

1. [제품 명세와 인수 조건](PRODUCT.md)
2. [사용자 경험과 화면 흐름](USER_EXPERIENCE.md)
3. [기술 설계와 데이터 계약](TECHNICAL_DESIGN.md)
4. [Claude 및 다른 호스트의 근거와 확인 범위](HOSTS.md)
5. [새 보관 기능을 위한 정책 변경 제안](PRIVACY_PROPOSAL.md)
6. [가상 사례와 Claude 실제 사용 평가 계획](EVALUATION.md)
7. [개발 순서와 작업별 완료 조건](BACKLOG.md)
8. [기존 자산과 이전 기획 대조](REUSE_AND_PRIOR_PLANS.md)

현재 루트 정책은 작업공간 내용 보관을 금지한다. 이 디렉터리는 새 정책을 승인하거나 기존 계약을 변경하지 않으며, 민감한 실제 정보를 수집하지 않는다. 가상 데이터 설계와 호스트 기능 확인은 진행할 수 있으나 실제 업무 사실의 지속 보관 기능은 정책 정합화 전 현재 저장소 규칙과 충돌한다. 개인/팀, 저장 장소, 제품명은 미결정이다. #137의 기존 기획을 자동으로 대체·수정하지 않는다.

## English orientation

This preparation packet proposes an AI work assistant for nontechnical office roles across a broad range of work, including one-off and continuing tasks. A work-fact library is a core component: deliver relevant, source- and time-qualified context before a task, then classify and save newly established facts after work without per-save approval. The assistant continues useful work and appropriate thinking support when no relevant record or saveable fact exists. Users can inspect, correct and delete records. The first live evaluation is Claude, with Chat, Cowork and Code treated as distinct surfaces. Host support, usefulness across roles, identity, storage location and personal-versus-team scope remain unverified or undecided. The current no-workspace-content-retention contract is not changed by this packet. The detailed planning documents are in Korean.
