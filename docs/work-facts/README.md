# 업무 사실 라이브러리: 개발 착수 패키지

**상태:** 제품 기획 및 개발 준비. 구현·호스트 지원·사용자 효과·릴리스는 확인되지 않았다. 기준 main: `d6b8ff1dc0dc7a51ebd5896a395ac39236e77d1c`. 사용자 지정 첫 실제 사용 검증은 Claude이며, 일반 Chat·Cowork·Code를 별도 표면으로 기록한다.

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

This preparation packet specifies a proposed work-fact library for nontechnical office work: deliver relevant, source- and time-qualified context before a task, then classify and save newly established facts after work without per-save approval. Users can inspect, correct and delete records. The first live evaluation is Claude, with Chat, Cowork and Code treated as distinct surfaces. Host support, usefulness, identity, storage location and personal-versus-team scope remain unverified or undecided. The current no-workspace-content-retention contract is not changed by this packet. The detailed planning documents are in Korean.
