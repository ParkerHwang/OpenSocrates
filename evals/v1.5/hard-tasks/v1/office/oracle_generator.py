#!/usr/bin/env python3
"""Independent exact arithmetic and finite plan optimization; no model calls."""
import csv
import itertools
import json
from collections import deque
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def canonical(rows, kind):
    key = {'invoice':'invoice_id','credit':'credit_id','payment':'payment_id'}[kind]
    selected = {}
    for row in rows:
        if row['status'] == 'draft': continue
        bid = row[key]
        rank = (int(row['revision']), row['row_id'])
        old = selected.get(bid)
        if old is None or rank[0] > int(old['revision']) or (rank[0] == int(old['revision']) and rank[1] < old['row_id']):
            selected[bid] = row
    physical = []
    for row in rows:
        bid = row[key]
        winner = selected.get(bid)
        if row['status'] == 'draft': disposition = 'draft'
        elif int(row['revision']) < int(winner['revision']): disposition = 'superseded'
        elif row['row_id'] != winner['row_id']: disposition = 'duplicate'
        else: disposition = 'active' if row['status'] == 'posted' else row['status']
        physical.append(dict(row_id=row['row_id'],kind=kind,business_id=bid,disposition=disposition,
                             recognized_krw=int(row['amount_krw']) if disposition=='active' else 0,source_id=row['source_id']))
    return selected, physical

def roster(inputs):
    people = {r['person_id']:dict(r) for r in csv_rows(inputs/'01_roster.csv')}
    for r in csv_rows(inputs/'02_availability.csv'):
        people[r['person_id']]['allowed_sessions'] = r['allowed_sessions'].split(';')
        people[r['person_id']]['source_row_ids'] = [people[r['person_id']]['row_id'],r['row_id']]
    for r in csv_rows(inputs/'03_hr_changes.csv'):
        if r['approval'] != 'approved': continue
        p = people[r['person_id']]
        p[r['field']] = r['value'].split(';') if r['field']=='allowed_sessions' else r['value']
        p['source_row_ids'].append(r['row_id'])
    result=[]
    for p in people.values():
        if p['active'] != 'true': continue
        result.append(dict(person_id=p['person_id'],tier=p['tier'],access_required=p['access_required']=='true',
                           allowed_sessions=p['allowed_sessions'],source_row_ids=p['source_row_ids']))
    return result

class Flow:
    def __init__(self): self.edges={}
    def add(self,a,b,c):
        self.edges.setdefault(a,{})[b]=c
        self.edges.setdefault(b,{})[a]=0
    def run(self, source, sink, limit=10**9):
        total=0
        while total < limit:
            seen={source:None}; q=deque([source])
            while q and sink not in seen:
                a=q.popleft()
                for b,c in self.edges[a].items():
                    if c>0 and b not in seen: seen[b]=a;q.append(b)
            if sink not in seen: break
            n=sink
            while seen[n] is not None:
                a=seen[n];self.edges[a][n]-=1;self.edges[n][a]+=1;n=a
            total+=1
        return total

def allocate(people, sessions, vendor, max_count):
    flow=Flow(); source='@source';sink='@sink'
    for s in sessions: flow.add(s['session_id'],sink,min(s['capacity'],vendor['capacity_per_session']))
    mandatory=[p for p in people if p['tier']=='mandatory']
    optional=[p for p in people if p['tier']=='optional']
    if max_count < len(mandatory): return None
    for p in people:
        for s in sessions:
            if s['session_id'] in p['allowed_sessions'] and (not p['access_required'] or s['accessible']):
                flow.add(p['person_id'],s['session_id'],1)
    for p in mandatory: flow.add(source,p['person_id'],1)
    if flow.run(source,sink) != len(mandatory): return None
    for p in optional: flow.add(source,p['person_id'],1)
    count=len(mandatory)+flow.run(source,sink,max_count-len(mandatory))
    assignments=[]
    for p in people:
        assigned=next((s['session_id'] for s in sessions if flow.edges.get(s['session_id'],{}).get(p['person_id'],0)==1),'')
        assignments.append(dict(p,session_id=assigned,state='assigned' if assigned else 'waitlist'))
    if any(not any(a['session_id']==s['session_id'] for a in assignments) for s in sessions): return None
    return count, assignments

def working(d, constraints):
    return d.weekday()<5 and d.isoformat() not in constraints['company_holidays']

def preparation(first, constraints):
    d=date.fromisoformat(first); days=[]
    while len(days)<constraints['preparation_workdays']:
        d-=timedelta(days=1)
        if working(d,constraints): days.append(d.isoformat())
    return sorted(days)

def compute(inputs=None):
    inputs=inputs or ROOT/'inputs'
    all_records=[];selected={}
    for kind,file in [('invoice','04_invoices.csv'),('credit','05_credits.csv'),('payment','06_payments.csv')]:
        selected[kind], records=canonical(csv_rows(inputs/file),kind);all_records.extend(records)
    balances=[]
    for iid, inv in sorted(selected['invoice'].items()):
        cr=[r for r in selected['credit'].values() if r['invoice_id']==iid]
        pay=[r for r in selected['payment'].values() if r['invoice_id']==iid]
        gross=int(inv['amount_krw']) if inv['status']=='posted' else 0
        credit=sum(int(r['amount_krw']) for r in cr if r['status']=='posted')
        paid=sum(int(r['amount_krw']) for r in pay if r['status']=='posted')
        balances.append(dict(invoice_id=iid,gross_krw=gross,credit_krw=credit,paid_krw=paid,balance_krw=gross-credit-paid,
                             invoice_row_id=inv['row_id'],credit_row_ids=sorted(r['row_id'] for r in cr),payment_row_ids=sorted(r['row_id'] for r in pay)))
    constraints=json.loads((inputs/'09_approved_constraints.json').read_text())
    outstanding=sum(b['balance_krw'] for b in balances)
    budget=constraints['total_cash_cap_krw']-outstanding
    sessions=[]
    for r in csv_rows(inputs/'07_session_options.csv'):
        sessions.append(dict(r,capacity=int(r['capacity']),room_cost_krw=int(r['room_cost_krw']),accessible=r['accessible']=='true'))
    vendors=json.loads((inputs/'08_supplier_terms.json').read_text())['vendors']
    people=roster(inputs); candidates=[]
    for vendor in vendors:
        if vendor['approval']!='approved': continue
        legal=[s for s in sessions if s['approval']=='approved' and s['session_id'] in vendor['allowed_sessions']
               and constraints['window_start']<=s['date']<=constraints['window_end'] and working(date.fromisoformat(s['date']),constraints)]
        for choice in itertools.combinations(legal,constraints['sessions_required']):
            if len({s['date'] for s in choice})!=len(choice):continue
            rooms=sum(s['room_cost_krw'] for s in choice)
            max_count=(budget-vendor['fixed_krw']-rooms)//vendor['per_person_krw']
            result=allocate(people,choice,vendor,max_count)
            if result:
                count,assignment=result
                cost=vendor['fixed_krw']+vendor['per_person_krw']*count+rooms
                candidates.append((count,cost,vendor,choice,assignment))
    if not candidates: raise ValueError('Fixture has no approved feasible complete plan')
    candidates.sort(key=lambda c:(-c[0],c[1],c[2]['vendor_id'],[s['session_id'] for s in c[3]]))
    count,cost,vendor,choice,assignments=candidates[0]
    schedule=[dict(session_id=s['session_id'],date=s['date'],attendees=sum(a['session_id']==s['session_id'] for a in assignments),
                   capacity=min(s['capacity'],vendor['capacity_per_session']),accessible=s['accessible'],room_cost_krw=s['room_cost_krw'],source_id=s['source_id']) for s in choice]
    summary=dict(total_cash_cap_krw=constraints['total_cash_cap_krw'],historical_outstanding_krw=outstanding,
                 launch_budget_krw=budget,vendor_id=vendor['vendor_id'],vendor_fixed_krw=vendor['fixed_krw'],
                 vendor_per_person_krw=vendor['per_person_krw'],room_cost_krw=sum(s['room_cost_krw'] for s in choice),
                 launch_cost_krw=cost,cash_remaining_krw=budget-cost,assigned_count=count,
                 mandatory_count=sum(a['tier']=='mandatory' and a['state']=='assigned' for a in assignments),
                 optional_count=sum(a['tier']=='optional' and a['state']=='assigned' for a in assignments),
                 approval_status='supplier_selection_pending',preparation_dates=preparation(min(s['date'] for s in choice),constraints))
    evidence=[dict(file=p.name,source_id='MULTIPLE' if p.suffix=='.csv' else {'08_supplier_terms.json':'SUPPLIER-TERMS-FINAL-0926','09_approved_constraints.json':'OPS-APPROVAL-0926','10_prior_maintained_note.md':'OPS-NOTE-V3','11_supplier_correction_email.md':'SUPPLIER-EMAIL-0926','12_domain_rules.md':'RULES-0927'}[p.name],use='검토 및 대사 근거') for p in sorted(inputs.iterdir()) if p.is_file()]
    return dict(fixture_version='office-v1',records=all_records,balances=balances,people=people,
                optimum=dict(assigned_count=count,optional_count=summary['optional_count'],launch_cost_krw=cost,
                             all_optimal_choices=[dict(vendor_id=c[2]['vendor_id'],session_ids=[s['session_id'] for s in c[3]]) for c in candidates if c[0]==count and c[1]==cost]),
                totals=dict(gross_krw=sum(b['gross_krw'] for b in balances),credit_krw=sum(b['credit_krw'] for b in balances),paid_krw=sum(b['paid_krw'] for b in balances),balance_krw=outstanding),
                example_plan=dict(summary=summary,sessions=schedule,assignments=assignments,evidence=evidence),
                feasible_choices=[dict(vendor_id=c[2]['vendor_id'],session_ids=[s['session_id'] for s in c[3]],assigned_count=c[0],cost_krw=c[1]) for c in candidates])

if __name__=='__main__':
    (ROOT/'oracle.json').write_text(json.dumps(compute(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
