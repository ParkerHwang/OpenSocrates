import csv, json, os, itertools, datetime, collections
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Border, Side
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter

ROOT=Path(__file__).resolve().parent
IN=ROOT/'inputs'; OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
def readcsv(name):
    with open(IN/name,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def writecsv(path,headers,rows):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(rows)

# Accounting: select one representative per business ID/revision and preserve every physical row.
acct_specs=[('04_invoices.csv','invoice','invoice_id',None),('05_credits.csv','credit','credit_id','invoice_id'),('06_payments.csv','payment','payment_id','invoice_id')]
records=[]; selected={}; allrows={}
for fn,kind,idcol,invcol in acct_specs:
    rows=readcsv(fn); allrows[kind]=rows
    groups=collections.defaultdict(list)
    for r in rows:groups[r[idcol]].append(r)
    for bid,rs in groups.items():
        non_draft=[r for r in rs if r['status']!='draft']
        hi=max((int(r['revision']) for r in non_draft),default=None)
        top=[r for r in non_draft if int(r['revision'])==hi] if hi is not None else []
        top.sort(key=lambda r:r['row_id']); rep=top[0] if top else None
        selected[(kind,bid)]=rep
        for r in rs:
            if r['status']=='draft':disp='draft'
            elif hi is None or int(r['revision'])<hi:disp='superseded'
            elif r not in top:disp='superseded'
            elif r is not rep:disp='duplicate'
            else:disp={'posted':'active','void':'void','reversed':'reversed'}[r['status']]
            amt=int(r['amount_krw']) if disp=='active' else 0
            records.append(dict(row_id=r['row_id'],kind=kind,business_id=bid,disposition=disp,recognized_krw=amt,source_id=r['source_id']))
writecsv(OUT/'records.csv',['row_id','kind','business_id','disposition','recognized_krw','source_id'],records)

invoices=collections.defaultdict(list)
for kind in ['credit','payment']:
    for (k,bid),r in selected.items():
        if k==kind and r:invoices[r['invoice_id']].append((kind,r))
balances=[]
for n in range(1,37):
    iid=f'INV{n:02d}'; inv=selected[('invoice',iid)]
    gross=int(inv['amount_krw']) if inv and inv['status']=='posted' else 0
    cr=[r for k,r in invoices[iid] if k=='credit']; pay=[r for k,r in invoices[iid] if k=='payment']
    credit=sum(int(r['amount_krw']) for r in cr if r['status']=='posted')
    paid=sum(int(r['amount_krw']) for r in pay if r['status']=='posted')
    bal=gross-credit-paid
    balances.append(dict(invoice_id=iid,gross_krw=gross,credit_krw=credit,paid_krw=paid,balance_krw=bal,invoice_row_id=inv['row_id'] if inv else '',credit_row_ids=';'.join(sorted(r['row_id'] for r in cr)),payment_row_ids=';'.join(sorted(r['row_id'] for r in pay))))
writecsv(OUT/'balances.csv',['invoice_id','gross_krw','credit_krw','paid_krw','balance_krw','invoice_row_id','credit_row_ids','payment_row_ids'],balances)
historical=sum(x['balance_krw'] for x in balances)

# Apply approved HR changes to active roster and availability.
roster=readcsv('01_roster.csv'); avail={r['person_id']:r for r in readcsv('02_availability.csv')}; hr=readcsv('03_hr_changes.csv')
byhr=collections.defaultdict(list)
for r in hr:
    if r['approval']=='approved':byhr[r['person_id']].append(r)
people=[]
for r in roster:
    fields={'tier':r['tier'],'active':r['active']=='true','access_required':r['access_required']=='true','allowed_sessions':avail[r['person_id']]['allowed_sessions'].split(';')}
    for h in byhr[r['person_id']]:
        v=h['value']
        fields[h['field']]= (v=='true') if h['field'] in ('active','access_required') else (v.split(';') if h['field']=='allowed_sessions' else v)
    if fields['active']:
        people.append(dict(person_id=r['person_id'],tier=fields['tier'],access_required=fields['access_required'],allowed_sessions=fields['allowed_sessions'],source_row_ids=[r['row_id'],avail[r['person_id']]['row_id']]+[x['row_id'] for x in byhr[r['person_id']]]))
byid={p['person_id']:p for p in people}

terms=json.load(open(IN/'08_supplier_terms.json',encoding='utf-8')); constraints=json.load(open(IN/'09_approved_constraints.json',encoding='utf-8'))
fac=readcsv('07_session_options.csv'); approved={r['session_id']:r for r in fac if r['approval']=='approved' and r['date'] not in constraints['company_holidays']}
vendors=[v for v in terms['vendors'] if v['approval']=='approved']

# Unit-capacity augmenting flow. Mandatory flow is found first and preserved while optional people augment.
def assign_subset(ss):
    sessions=[s for s in ss if s in approved and s in vendors[0]['allowed_sessions']]
    if len(sessions)!=4:return None
    caps={s:min(int(approved[s]['capacity']),min(int(v['capacity_per_session']) for v in vendors)) for s in sessions}
    # Residual bipartite flow, represented by person->session assignments with rerouting DFS.
    matched={s:[] for s in sessions}; person_session={}
    def place(pid,seen):
        p=byid[pid]
        for s in p['allowed_sessions']:
            if s not in caps or (p['access_required'] and approved[s]['accessible']!='true') or s in seen:continue
            seen.add(s)
            if len(matched[s])<caps[s]:matched[s].append(pid);person_session[pid]=s;return True
            for old in list(matched[s]):
                if place(old,seen):
                    matched[s].remove(old);matched[s].append(pid);person_session[pid]=s;return True
        return False
    byid={p['person_id']:p for p in people}
    mandatory=[p['person_id'] for p in people if p['tier']=='mandatory']
    optional=[p['person_id'] for p in people if p['tier']=='optional']
    for pid in mandatory:
        if not place(pid,set()):
            # debugging aid: caller can identify infeasible session sets
            return None
    mandmap=dict(person_session)
    for pid in optional:place(pid,set())
    if any(not matched[s] for s in sessions):return None
    return dict(person_session),caps

best=None; candidate_results=[]
feasible_combos=[]
for combo in itertools.combinations(sorted(approved),4):
    result=assign_subset(combo)
    if not result:continue
    feasible_combos.append(combo)
    alloc,caps=result
    n=len(alloc); m=sum(p['tier']=='mandatory' for p in people)
    room=sum(int(approved[s]['room_cost_krw']) for s in combo)
    for v in vendors:
        if not set(combo)<=set(v['allowed_sessions']):continue
        budget=int(constraints['total_cash_cap_krw'])-historical
        max_n=(budget-room-int(v['fixed_krw']))//int(v['per_person_krw'])
        target=min(n,max_n)
        trimmed=dict(alloc)
        if target<n:
            optional_ids=[pid for pid in trimmed if byid[pid]['tier']=='optional']
            # Keep optional seats distributed where possible; mandatory seats remain fixed.
            for pid in sorted(optional_ids,reverse=True)[:n-target]:del trimmed[pid]
        if target<m or any(not any(sid==s for sid in trimmed.values()) for s in combo):continue
        cost=room+int(v['fixed_krw'])+int(v['per_person_krw'])*target
        key=(target-m,-cost)
        candidate_results.append((key,combo,v,trimmed,caps,cost,room))
if not candidate_results:raise RuntimeError('No feasible 4-session plan covering mandatory staff; active=%s mandatory=%s approved=%s feasible=%s'%(len(people),sum(p['tier']=='mandatory' for p in people),sorted(approved),feasible_combos))
candidate_results.sort(key=lambda x:(x[0][0],x[0][1],x[2]['vendor_id'],x[1]),reverse=True)
_,ss,vendor,alloc,caps,cost,room=candidate_results[0]
mandatory_count=sum(p['tier']=='mandatory' for p in people); assigned_count=len(alloc); optional_count=assigned_count-mandatory_count

assignments=[]
for p in sorted(people,key=lambda p:p['person_id']):
    sid=alloc.get(p['person_id'],'')
    assignments.append(dict(person_id=p['person_id'],tier=p['tier'],access_required=p['access_required'],allowed_sessions=p['allowed_sessions'],session_id=sid,state='assigned' if sid else 'waitlist',source_row_ids=p['source_row_ids']))
sessions=[]
for s in ss:
    f=approved[s]
    sessions.append(dict(session_id=s,date=f['date'],attendees=sum(1 for x in alloc.values() if x==s),capacity=caps[s],accessible=f['accessible']=='true',room_cost_krw=int(f['room_cost_krw']),source_id=f['source_id']))

first=min(datetime.date.fromisoformat(approved[s]['date']) for s in ss)
holidays=set(map(datetime.date.fromisoformat,constraints['company_holidays']))
workdays=[]; d=first-datetime.timedelta(days=1)
while len(workdays)<3:
    if d.weekday()<5 and d not in holidays:workdays.append(d)
    d-=datetime.timedelta(days=1)
prep=sorted(x.isoformat() for x in workdays)
summary=dict(total_cash_cap_krw=int(constraints['total_cash_cap_krw']),historical_outstanding_krw=historical,launch_budget_krw=int(constraints['total_cash_cap_krw'])-historical,vendor_id=vendor['vendor_id'],vendor_fixed_krw=int(vendor['fixed_krw']),vendor_per_person_krw=int(vendor['per_person_krw']),room_cost_krw=room,launch_cost_krw=cost,cash_remaining_krw=int(constraints['total_cash_cap_krw'])-historical-cost,assigned_count=assigned_count,mandatory_count=mandatory_count,optional_count=optional_count,approval_status=constraints['approval_status'],preparation_dates=prep)

# Evidence inventory and provenance explanations.
evidence=[
 dict(file='01_roster.csv',source_id='MULTIPLE',use='기본 직원·활성 상태·초기 구분과 행 출처의 기준으로 사용.'),
 dict(file='02_availability.csv',source_id='MULTIPLE',use='개인별 원래 가능 세션을 HR 승인 변경과 결합.'),
 dict(file='03_hr_changes.csv',source_id='MULTIPLE',use='approved 변경만 적용하고 pending 제안은 제외.'),
 dict(file='04_invoices.csv',source_id='MULTIPLE',use='송장 ID·리비전별 유효 대표행과 총액 대사.'),
 dict(file='05_credits.csv',source_id='MULTIPLE',use='크레딧 ID별 승인 대표행을 잔액에 반영.'),
 dict(file='06_payments.csv',source_id='MULTIPLE',use='지급 ID별 유효 지급만 반영하고 취소·중복 행 보존.'),
 dict(file='07_session_options.csv',source_id='MULTIPLE',use='승인 시설·수용력·접근성·비용을 일정에 적용.'),
 dict(file='08_supplier_terms.json',source_id=terms['source_id'],use='최종 승인 공급사 요율·허용 세션·인당 상한 적용.'),
 dict(file='09_approved_constraints.json',source_id=constraints['source_id'],use='현금 한도·일정창·휴일·목표·서명 상태를 적용.'),
 dict(file='10_prior_maintained_note.md',source_id='OPS-NOTE-V3',use='수정 전 운영 가정과 담당 역할을 확인해 갱신.'),
 dict(file='11_supplier_correction_email.md',source_id='SUPPLIER-EMAIL-0926',use='최종 견적 우선, pilot 미승인, capacity 해석 및 서명 전 준비 범위 확인.'),
 dict(file='12_domain_rules.md',source_id='RULES-0927',use='ID·리비전·중복·취소·반올림·최적화 규칙 적용.'),
]
plan=dict(summary=summary,assignments=assignments,sessions=sessions,evidence=evidence)
with open(OUT/'plan.json','w',encoding='utf-8') as f:json.dump(plan,f,ensure_ascii=False,indent=2)

# Workbook mirrors the machine-readable deliverables, in required column order.
wb=Workbook(); wb.remove(wb.active)
sheet_defs=[('대사기록',['row_id','kind','business_id','disposition','recognized_krw','source_id'],records),('송장잔액',['invoice_id','gross_krw','credit_krw','paid_krw','balance_krw','invoice_row_id','credit_row_ids','payment_row_ids'],balances),('배정',['person_id','tier','access_required','allowed_sessions','session_id','state','source_row_ids'],assignments),('일정',['session_id','date','attendees','capacity','accessible','room_cost_krw','source_id'],sessions),('예산',['key','value'],[{'key':k,'value':';'.join(v) if isinstance(v,list) else v} for k,v in summary.items()]),('근거',['file','source_id','use'],evidence)]
moneycols={'recognized_krw','gross_krw','credit_krw','paid_krw','balance_krw','room_cost_krw','total_cash_cap_krw','historical_outstanding_krw','launch_budget_krw','vendor_fixed_krw','vendor_per_person_krw','launch_cost_krw','cash_remaining_krw'}
for name,headers,rows in sheet_defs:
    ws=wb.create_sheet(name); ws.append(headers)
    for r in rows:
        vals=[]
        for h in headers:
            val=r[h]
            if isinstance(val,list):val=';'.join(str(x) for x in val)
            vals.append(val)
        ws.append(vals)
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    for c in ws[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='24476B')
    for col_idx,h in enumerate(headers,1):
        width=max(len(str(h)),*(min(55,len(str(ws.cell(row, col_idx).value or ''))) for row in range(2,ws.max_row+1)))
        ws.column_dimensions[get_column_letter(col_idx)].width=min(55,max(12,width+2))
        for row in range(2,ws.max_row+1):
            is_money=(h in moneycols) or (name=='예산' and h=='value' and rows[row-2]['key'].endswith('_krw'))
            if is_money and isinstance(ws.cell(row,col_idx).value,(int,float)):ws.cell(row,col_idx).number_format='₩#,##0;[Red]-₩#,##0'
            ws.cell(row,col_idx).alignment=Alignment(vertical='top',wrap_text=(h=='use'))
    ws.sheet_view.showGridLines=False
wb.save(OUT/'operations.xlsx')

print(json.dumps({'historical':historical,'budget':summary['launch_budget_krw'],'summary':summary,'sessions':sessions,'active_people':len(people),'waitlist':[x['person_id'] for x in assignments if x['state']=='waitlist'],'top_options':[(x[2]['vendor_id'],x[1],x[0][0],x[5]) for x in candidate_results[:8]]},ensure_ascii=False,indent=2))
