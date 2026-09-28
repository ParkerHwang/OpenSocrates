# 운영기획 작업 메모

갱신일: 2026-09-27

## 현재 기준과 출처
- 기준 문서는 inputs/12_domain_rules.md (RULES-0927) 및 inputs/09_approved_constraints.json (OPS-APPROVAL-0926)이다. HR은 inputs/03_hr_changes.csv의 approved 행만 반영했고, 공급 조건은 inputs/08_supplier_terms.json 최종 조건을 inputs/11_supplier_correction_email.md (SUPPLIER-EMAIL-0926)와 대조했다.
- inputs/10_prior_maintained_note.md (OPS-NOTE-V3)는 역할 분장과 인수인계 출발점으로 유지하되, 공급가·인원 현황·S4 전제는 현행 사실로 사용하지 않는다. 원본 입력은 수정하지 않았다.
- 외부 회계·법률·휴일·공급사 가정을 추가하지 않았다. 실제 공급사 수락·일정 보유와 운영책임자 서명은 미확인이다.

## 대사 및 계획 요약
- INV01–INV36 잔액 합계: 787,600원. 총현금 한도 1,752,600원에서 차감한 신규 교육 한도: 965,000원. 제안 추가예산은 제외했다.
- 승인 HR 반영 후 활성 72명: 필수 60명, 선택 12명. 계획 배정은 필수 60명, 선택 6명이며 선택 6명은 대기한다. P064는 H05 접근성 변경과 A064 허용범위를 보면 승인된 접근 가능 회차가 없다.
- 기준안은 CEDAR, S2/S3/S5/S6이다. 네 회차 방 합계 260,000원, 신규 비용 962,000원, 한도 잔액 3,000원. 상태는 supplier_selection_pending.
- 준비일은 2026-10-01, 2026-10-02, 2026-10-05이다. 내부 자료·명단·접근성 준비는 독립 진행 가능하다. 서명 전 예약·발주·지급·외부 발송은 하지 않는다.

## 산출물 및 검사
- output/records.csv: 금융 물리행 101개. 처리 분포: active=58, draft=1, duplicate=12, reversed=3, superseded=22, void=5.
- output/balances.csv: 36개 송장, 잔액 등식 검사 통과.
- output/plan.json: 72명, 4회차, 12개 입력 근거행; 필수 전원·접근성·가능 회차·수용량 검사 통과.
- output/operations.xlsx: 6개 필수 시트 재개방, 헤더·행수·고정 헤더 확인 통과.
- output/decision_memo.md: 공급사 비교, 구 메모 변경, 미결 서명, 실행 한계와 다음 내부 조치 기재.
- 공급사별 동일 세션 계획에서 예산상 최대 참석은 CEDAR 66, LYRA 63, ORCHID 64명이다. 66명 CEDAR 비용은 962,000원이며 67명은 969,000원으로 한도 초과한다.
- 다음 운영자는 승인 입력이나 revision이 바뀌면 같은 우선순위로 잔액과 좌석을 다시 계산하고 파일 간 일치를 갱신한다.
