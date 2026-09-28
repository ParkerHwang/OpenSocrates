#!/usr/bin/env python3
"""Deterministically regenerate this wholly synthetic input corpus."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUT = ROOT / 'inputs'

def write(name, fields, rows):
    with (INPUT / name).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

def main():
    INPUT.mkdir(exist_ok=True)
    roster = []
    avail = []
    for i in range(1, 73):
        p = f'P{i:03}'
        group = (i - 1) // 15 if i <= 60 else (i - 61) // 3
        region = ['서울', '대전', '부산', '광주'][group]
        roster.append(dict(row_id=f'R{i:03}', person_id=p, name=f'교육대상{i:03}', region=region,
                           tier='mandatory' if i <= 60 else 'optional', active='false' if i == 72 else 'true',
                           access_required='true' if i <= 12 and i != 5 else 'false', source_id='HR-BASE-0920'))
        allowed = ['S2;S5', 'S3;S6', 'S2;S5', 'S3;S6'][group]
        # Broad published availability includes S1, which costs more than the minimum plan.
        if i % 5 == 0:
            allowed += ';S1'
        avail.append(dict(row_id=f'A{i:03}', person_id=p, allowed_sessions=allowed, source_id='AVAIL-0924'))
    # A real predecessor note's working roster, corrected by the latest approved HR change log.
    roster[9]['tier'] = 'optional'
    roster[60]['tier'] = 'mandatory'
    changes = [
        ('P005', 'access_required', 'true', 'approved'),
        ('P010', 'tier', 'mandatory', 'approved'),
        ('P061', 'tier', 'optional', 'approved'),
        ('P072', 'active', 'true', 'approved'),
        ('P064', 'access_required', 'true', 'approved'),
        ('P020', 'allowed_sessions', 'S5', 'approved'),
        ('P025', 'allowed_sessions', 'S3', 'approved'),
        ('P045', 'allowed_sessions', 'S2;S5', 'approved'),
        ('P060', 'allowed_sessions', 'S6', 'approved'),
        ('P070', 'allowed_sessions', 'S3;S6', 'approved'),
        ('P063', 'tier', 'mandatory', 'pending'),
        ('P005', 'access_required', 'false', 'pending'),
    ]
    write('01_roster.csv', list(roster[0]), roster)
    write('02_availability.csv', list(avail[0]), avail)
    write('03_hr_changes.csv', ['row_id','person_id','field','value','approval','source_id'],
          [dict(row_id=f'H{i:02}', person_id=p, field=f, value=v, approval=a, source_id='HR-APPROVED-0926' if a == 'approved' else 'HR-PROPOSAL-0927') for i,(p,f,v,a) in enumerate(changes,1)])
    invoices = []
    for i in range(1,37):
        invoices.append(dict(row_id=f'I-B{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=13000+i*900, source_id='AP-EXPORT-0923'))
    for i in range(1,11):
        invoices.append(dict(row_id=f'I-R{i:02}', invoice_id=f'INV{i:02}', revision=2, status='posted', amount_krw=12000+i*900, source_id='AP-CORRECTION-0926'))
    for i in range(11,17):
        invoices.append(dict(row_id=f'I-D{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=13000+i*900, source_id='AP-EXPORT-0923-REPEAT'))
    for i in range(33,37):
        invoices.append(dict(row_id=f'I-V{i:02}', invoice_id=f'INV{i:02}', revision=2, status='void', amount_krw=0, source_id='AP-CORRECTION-0926'))
    invoices.append(dict(row_id='I-P01', invoice_id='INV01', revision=3, status='draft', amount_krw=999999, source_id='AP-PREVIEW-0927'))
    credits=[]
    for i in range(1,11):
        credits.append(dict(row_id=f'C-B{i:02}', credit_id=f'CR{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=0 if i==10 else 500+i*50, source_id='CREDIT-0924'))
    for i in range(1,5):
        credits.append(dict(row_id=f'C-R{i:02}', credit_id=f'CR{i:02}', invoice_id=f'INV{i:02}', revision=2, status='posted', amount_krw=700+i*50, source_id='CREDIT-CORRECTION-0926'))
    for i in range(5,7):
        credits.append(dict(row_id=f'C-D{i:02}', credit_id=f'CR{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=500+i*50, source_id='CREDIT-0924-REPEAT'))
    credits.append(dict(row_id='C-V09', credit_id='CR09', invoice_id='INV09', revision=2, status='void', amount_krw=0, source_id='CREDIT-CORRECTION-0926'))
    payments=[]
    for i in range(1,19):
        payments.append(dict(row_id=f'P-B{i:02}', payment_id=f'PAY{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=5000+i*100, source_id='BANK-0925'))
    for i in range(1,5):
        payments.append(dict(row_id=f'P-D{i:02}', payment_id=f'PAY{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=5000+i*100, source_id='BANK-0925-REPEAT'))
    for i in range(16,19):
        payments.append(dict(row_id=f'P-R{i:02}', payment_id=f'PAY{i:02}', invoice_id=f'INV{i:02}', revision=2, status='reversed', amount_krw=0, source_id='BANK-REVERSAL-0926'))
    for i in range(19,21):
        payments.append(dict(row_id=f'P-Z{i:02}', payment_id=f'PAY{i:02}', invoice_id=f'INV{i:02}', revision=1, status='posted', amount_krw=0, source_id='BANK-0925'))
    write('04_invoices.csv',list(invoices[0]),invoices)
    write('05_credits.csv',list(credits[0]),credits)
    write('06_payments.csv',list(payments[0]),payments)
    sessions=[
        ('S1','2026-10-05',18,True,90000,'approved'),
        ('S2','2026-10-06',18,True,80000,'approved'),
        ('S3','2026-10-08',16,False,60000,'approved'),
        ('S4','2026-10-09',18,True,40000,'proposed'),
        ('S5','2026-10-12',18,True,70000,'approved'),
        ('S6','2026-10-13',18,False,50000,'approved'),
    ]
    write('07_session_options.csv',['session_id','date','capacity','accessible','room_cost_krw','approval','source_id'],
          [dict(session_id=s,date=d,capacity=c,accessible=str(a).lower(),room_cost_krw=r,approval=p,source_id='FACILITY-0926') for s,d,c,a,r,p in sessions])
    terms=dict(source_id='SUPPLIER-TERMS-FINAL-0926', currency='KRW', vendors=[
        dict(vendor_id='CEDAR',fixed_krw=240000,per_person_krw=7000,allowed_sessions=['S1','S2','S3','S5','S6'],approval='approved',capacity_per_session=18),
        dict(vendor_id='LYRA',fixed_krw=200000,per_person_krw=8000,allowed_sessions=['S1','S2','S3','S5','S6'],approval='approved',capacity_per_session=18),
        dict(vendor_id='ORCHID',fixed_krw=285000,per_person_krw=6500,allowed_sessions=['S1','S2','S3','S5','S6'],approval='approved',capacity_per_session=18),
        dict(vendor_id='CEDAR-PILOT',fixed_krw=180000,per_person_krw=5000,allowed_sessions=['S1','S2','S3','S4','S5','S6'],approval='pending',capacity_per_session=20),
    ], note='These final terms supersede all price estimates in the predecessor note. A single vendor supplies exactly four sessions. Fixed charge is paid once; per-person charge applies once per assigned attendee. No taxes, discounts, travel or deposits apply.')
    (INPUT/'08_supplier_terms.json').write_text(json.dumps(terms,ensure_ascii=False,indent=2)+'\n')
    # This number is frozen, not discovered by candidates through a generated output oracle.
    constraints=dict(source_id='OPS-APPROVAL-0926',total_cash_cap_krw=1752600,pending_extra_budget_krw=70000,
                     sessions_required=4,window_start='2026-10-05',window_end='2026-10-13',
                     company_holidays=['2026-10-09'],coordinators_available_per_day=1,
                     preparation_workdays=3,approval_status='supplier_selection_pending',
                     preparation_rule='Three company working days strictly before the earliest selected session, latest feasible contiguous working-day sequence; preparation can proceed before supplier signoff.',
                     objective=['cover every final active mandatory attendee','maximize assigned final active optional attendees','minimize incremental launch cost'],
                     cash_rule='Reserve all historical positive invoice balances in addition to incremental launch cost. Do not count pending budget. No negative balances arise in these data.')
    (INPUT/'09_approved_constraints.json').write_text(json.dumps(constraints,ensure_ascii=False,indent=2)+'\n')
    (INPUT/'10_prior_maintained_note.md').write_text('''# 지역 직원 교육 운영 메모 — 유지본 v3\n\n작성: 운영기획팀, 2026-09-21. Source ID: OPS-NOTE-V3.\n이 문서는 기존에 관리해 온 인수인계 메모다. 현황·담당 역할의 출발점으로 쓰고, 이후 승인된 변경에 맞춰 갱신하라.\n\n- 9/20 인사본에서는 필수 60명, 선택 12명 중 P072가 철회 상태였다. P010은 선택, P061은 필수로 등록되어 있다. 담당자는 최신 인사 승인 로그로 다시 확인해야 한다.\n- Cedar 견적 추정: 기본 210,000원 + 1인 6,500원. 아직 계약 전 가격이며 최종 공급사 문서가 우선한다.\n- 시설 검토안은 10/9 S4를 저렴한 옵션으로 제시했다. 근무일 승인과 시설 승인 확인 전에는 일정에 넣을 수 없다.\n- 은행 전표 재전송을 합산하는 실수가 있었으므로 거래 ID를 보존하고 중복·취소를 확인한다. 송금 취소분은 새 예산이 아니라 미지급 잔액으로 돌아온다.\n- 운영 담당: 명단/안내문 박운영; 장소·장비 최시설; 공급사 결재 요청 윤구매; 전표·예산 대사 정회계.\n- 최종 공급사 선택은 운영책임자 결재 대기다. 명단 대사, 일정 초안, 접근성 점검, 자료 준비는 독립적으로 진행 가능하다. 결재 전 예약·발주·송금·외부 발송은 하지 않는다.\n- 교육은 전원 1회 참석한다. 세션 이동/재수강은 계획에 포함하지 않는다. 아직 준비일은 확정하지 않았다.\n''',encoding='utf-8')
    (INPUT/'11_supplier_correction_email.md').write_text('''# Final quotation clarification (English source)\nSource ID: SUPPLIER-EMAIL-0926. Procurement received 2026-09-26.\n\nThe attached final JSON quotation is authoritative, replacing the budgetary prices quoted in OPS-NOTE-V3. The CEDAR-PILOT entry is only a proposal pending procurement approval; it must not be selected using the existing authorization. Supplier staff and room capacity are separate limits; use the smaller limit for each session. Our rate covers all four sessions and one attendance per person. There is no extra daily trainer fee. The calendar contains a company shutdown on October 9, even though it falls on a weekday.\n\nThe quotation is approved for planning. The purchase itself still requires the operations lead's final selection signature. Preparing materials and reconciling the roster do not depend on that signature.\n''',encoding='utf-8')

if __name__ == '__main__': main()
