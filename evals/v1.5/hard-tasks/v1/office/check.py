#!/usr/bin/env python3
"""27 grouped deterministic artifact checks. No prose quality model or network.
Usage: python3 check.py OUTPUT_DIRECTORY [--report REPORT.json]
XLSX is read through ZIP/XML (stdlib), with basic uncached formula evaluation.
"""
import argparse
import ast
import csv
import json
import operator
import re
import zipfile
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from xml.etree import ElementTree as ET
from oracle_generator import ROOT, compute, csv_rows, preparation, working

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
SCHEMAS={
    'records':['row_id','kind','business_id','disposition','recognized_krw','source_id'],
    'balances':['invoice_id','gross_krw','credit_krw','paid_krw','balance_krw','invoice_row_id','credit_row_ids','payment_row_ids'],
    'assignments':['person_id','tier','access_required','allowed_sessions','session_id','state','source_row_ids'],
    'sessions':['session_id','date','attendees','capacity','accessible','room_cost_krw','source_id'],
    'evidence':['file','source_id','use'],
}
SHEETS={'대사기록':'records','송장잔액':'balances','배정':'assignments','일정':'sessions','근거':'evidence'}
REQUIRED=['records.csv','balances.csv','plan.json','decision_memo.md','operations.xlsx']
LIST_FIELDS={'credit_row_ids','payment_row_ids','source_row_ids','allowed_sessions','preparation_dates'}
NUM_FIELDS={'recognized_krw','gross_krw','credit_krw','paid_krw','balance_krw','attendees','capacity','room_cost_krw'}
BOOL_FIELDS={'access_required','accessible'}

def normalize(value, field):
    if field in LIST_FIELDS:
        if isinstance(value,list):return tuple(sorted(str(x) for x in value))
        return tuple(sorted(x.strip() for x in str(value or '').split(';') if x.strip()))
    if field in NUM_FIELDS:
        if isinstance(value,bool):raise ValueError('Boolean used as amount')
        if value is None or str(value).strip()=='':raise ValueError(f'Missing numeric {field}')
        n=float(value)
        if not n.is_integer():raise ValueError(f'Noninteger {field}')
        return int(n)
    if field in BOOL_FIELDS:
        if isinstance(value,bool):return value
        if str(value).lower()=='true':return True
        if str(value).lower()=='false':return False
        raise ValueError('Boolean must be true/false')
    return str(value or '')

def keyed(rows, field):
    ids=[r[field] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError(f'Duplicate {field}')
    return {r[field]:r for r in rows}

def equivalent(a,b,fields):
    return all(normalize(a.get(f),f)==normalize(b.get(f),f) for f in fields)

class UnsupportedFormula(ValueError):
    """Valid Excel expression whose uncached result this reader cannot establish."""


class Workbook:
    """Small inspectable reader; formulas may use arithmetic, SUM/COUNT/COUNTA,
    MIN/MAX/ROUND, equality-only COUNTIF/SUMIF and direct/range sheet references. Excel cached
    results are used for any other formula. The benchmark permits static values.
    """
    def __init__(self,path):
        self.cells={};self.cache={}
        with zipfile.ZipFile(path) as z:
            strings=[]
            if 'xl/sharedStrings.xml' in z.namelist():
                root=ET.fromstring(z.read('xl/sharedStrings.xml'))
                strings=[''.join(el.itertext()) for el in root.findall('m:si',NS)]
            rel=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
            targets={r.attrib['Id']:r.attrib['Target'] for r in rel}
            book=ET.fromstring(z.read('xl/workbook.xml'))
            for s in book.findall('m:sheets/m:sheet',NS):
                target=targets[s.attrib['{'+NS['r']+'}id']]
                target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
                cells={}
                for c in ET.fromstring(z.read(target)).findall('.//m:sheetData/m:row/m:c',NS):
                    value=c.find('m:v',NS);typ=c.attrib.get('t');f=c.find('m:f',NS)
                    v=value.text if value is not None else None
                    if typ=='inlineStr':
                        inline=c.find('m:is',NS);v=''.join(inline.itertext()) if inline is not None else ''
                    elif typ=='s' and v is not None:v=strings[int(v)]
                    elif typ=='b' and v is not None:v=v=='1'
                    elif typ not in ('str','e') and v is not None:
                        n=float(v);v=int(n) if n.is_integer() else n
                    cells[c.attrib['r']]=(v,f.text if f is not None else None)
                self.cells[s.attrib['name']]=cells
    def value(self,sheet,ref,trail=None):
        key=(sheet,ref.replace('$',''))
        if key in self.cache:return self.cache[key]
        v,f=self.cells.get(sheet,{}).get(key[1],(None,None))
        if v is not None or not f:return v
        trail=set(trail or ())
        if key in trail:raise ValueError('Circular formula')
        trail.add(key)
        value=self.formula(f,sheet,trail);self.cache[key]=value;return value
    def formula(self,f,sheet,trail):
        # References become safe Python literal values. No eval, imports or attribute calls.
        pattern=r"(?:(?:'([^']+)'|([\w\u0080-\uffff]+))!)?(\$?[A-Z]+\$?\d+)(?::(\$?[A-Z]+\$?\d+))?"
        def replacement(m):
            target=m.group(1) or m.group(2) or sheet
            first=m.group(3).replace('$','');last=m.group(4)
            if not last:return repr(self.value(target,first,trail) or 0)
            last=last.replace('$','')
            col1,row1=re.fullmatch(r'([A-Z]+)(\d+)',first).groups()
            col2,row2=re.fullmatch(r'([A-Z]+)(\d+)',last).groups()
            def ci(c):
                n=0
                for x in c:n=n*26+ord(x)-64
                return n
            def cs(n):
                out=''
                while n:n,r=divmod(n-1,26);out=chr(65+r)+out
                return out
            values=[self.value(target,cs(c)+str(r),trail) for r in range(int(row1),int(row2)+1) for c in range(ci(col1),ci(col2)+1)]
            return repr(values)
        # Excel double-quoted literals are lexed before references are substituted.
        # Doubled quotes inside a literal encode a quote, not a second token.
        parts=re.split(r'("(?:""|[^"])*")',f.lstrip('='))
        expression=''.join(repr(part[1:-1].replace('""','"')) if i%2 else re.sub(pattern,replacement,part)
                           for i,part in enumerate(parts))
        try:tree=ast.parse(expression,mode='eval')
        except SyntaxError as e:raise UnsupportedFormula(f'Unsupported uncached Excel syntax: {f}') from e
        def flat(args):
            return [x for a in args for x in (a if isinstance(a,list) else [a])]
        def visit(n):
            if isinstance(n,ast.Expression):return visit(n.body)
            if isinstance(n,ast.Constant):return n.value
            if isinstance(n,ast.List):return [visit(v) for v in n.elts]
            if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
                return visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
            if isinstance(n,ast.BinOp) and type(n.op) in {ast.Add,ast.Sub,ast.Mult,ast.Div}:
                return {ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}[type(n.op)](visit(n.left),visit(n.right))
            if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
                name=n.func.id.upper();args=[visit(a) for a in n.args];vals=flat(args)
                nums=[v for v in vals if isinstance(v,(int,float)) and not isinstance(v,bool)]
                if name=='SUM':return sum(nums)
                if name=='COUNT':return len(nums)
                if name=='COUNTA':return sum(v not in (None,'') for v in vals)
                if name=='MIN':return min(nums)
                if name=='MAX':return max(nums)
                if name=='ROUND':
                    if len(args)!=2 or not isinstance(args[1],(int,float)) or int(args[1])!=args[1]:
                        raise UnsupportedFormula(f'Unsupported ROUND arguments: {f}')
                    quantum=Decimal(1).scaleb(-int(args[1]))
                    try:return float(Decimal(str(args[0])).quantize(quantum,rounding=ROUND_HALF_UP))
                    except InvalidOperation as e:raise UnsupportedFormula(f'Unsupported ROUND value: {f}') from e
                if name in ('COUNTIF','SUMIF'):
                    if len(args)<2 or len(args)> (2 if name=='COUNTIF' else 3):
                        raise UnsupportedFormula(f'Unsupported {name} arguments: {f}')
                    criterion=args[1]
                    if isinstance(criterion,str) and (criterion.startswith(('>','<','=')) or any(c in criterion for c in '*?~')):
                        raise UnsupportedFormula(f'Uncached {name} supports literal equality criteria only: {f}')
                    def equal(value):
                        if value is None:return criterion in (None,'')
                        try:return Decimal(str(value))==Decimal(str(criterion))
                        except InvalidOperation:return str(value).casefold()==str(criterion).casefold()
                    if name=='COUNTIF':return sum(equal(v) for v in args[0])
                    summed=args[2] if len(args)==3 else args[0]
                    if len(summed)!=len(args[0]):raise UnsupportedFormula(f'Unsupported SUMIF range sizes: {f}')
                    return sum(v for k,v in zip(args[0],summed) if equal(k) and isinstance(v,(int,float)) and not isinstance(v,bool))
            raise UnsupportedFormula(f'Uncached unsupported formula: {f}')
        return visit(tree)
    def table(self,sheet):
        cells=self.cells[sheet]
        refs=[re.fullmatch(r'([A-Z]+)(\d+)',r).groups() for r in cells]
        maxrow=max((int(r) for _,r in refs),default=0)
        headers=[];c=1
        while True:
            # There are at most eight columns in required sheets.
            v=self.value(sheet,chr(64+c)+'1')
            if v is None:break
            headers.append(str(v));c+=1
        rows=[]
        for r in range(2,maxrow+1):
            values=[self.value(sheet,chr(65+i)+str(r)) for i in range(len(headers))]
            if any(v not in (None,'') for v in values):rows.append(dict(zip(headers,values)))
        return headers,rows

def check(output):
    missing=[f for f in REQUIRED if not (output/f).is_file()]
    if missing:return dict(status='unassessable',objective_score=None,missing_artifacts=missing,checks=[],prose_review='not_run')
    try:
        records=csv_rows(output/'records.csv');balances=csv_rows(output/'balances.csv')
        plan=json.loads((output/'plan.json').read_text(encoding='utf-8'))
        memo=(output/'decision_memo.md').read_text(encoding='utf-8')
        wb=Workbook(output/'operations.xlsx')
        oracle=compute();expected_records=keyed(oracle['records'],'row_id');expected_balances=keyed(oracle['balances'],'invoice_id')
        people=keyed(oracle['people'],'person_id')
        constraints=json.loads((ROOT/'inputs/09_approved_constraints.json').read_text())
        raw_sessions={r['session_id']:dict(r,capacity=int(r['capacity']),room_cost_krw=int(r['room_cost_krw']),accessible=r['accessible']=='true') for r in csv_rows(ROOT/'inputs/07_session_options.csv')}
        vendors={v['vendor_id']:v for v in json.loads((ROOT/'inputs/08_supplier_terms.json').read_text())['vendors']}
    except Exception as e:
        return dict(status='unassessable',objective_score=None,artifact_error=f'{type(e).__name__}: {e}',checks=[],prose_review='not_run')
    checks=[];evaluation_errors=[]
    def test(id,group,fn):
        try:
            result=fn();passed=bool(result);detail='ok' if passed else 'mismatch'
        except UnsupportedFormula as e:
            evaluation_errors.append(f'{id}: {e}');passed=False;detail=f'Unassessable formula: {e}'
        except Exception as e:passed=False;detail=f'{type(e).__name__}: {e}'
        checks.append(dict(id=id,group=group,passed=passed,detail=detail))
    def maps():return keyed(records,'row_id'),keyed(balances,'invoice_id')
    def data():
        return plan['summary'],keyed(plan['assignments'],'person_id'),keyed(plan['sessions'],'session_id'),vendors[plan['summary']['vendor_id']]
    def records_match(kind, fields):
        actual,_=maps()
        return all(equivalent(actual[rid],r,fields) for rid,r in expected_records.items() if r['kind']==kind)
    def balances_match(fields):
        _,actual=maps();return all(equivalent(actual[k],v,fields) for k,v in expected_balances.items())
    def artifact_contract():
        summary=plan['summary']; expected_summary=oracle['example_plan']['summary'] if 'example_plan' in oracle else oracle['plan']['summary']
        numeric=[key for key,value in expected_summary.items() if type(value) is int]
        return bool(records and balances) and list(records[0])==SCHEMAS['records'] and list(balances[0])==SCHEMAS['balances'] and set(summary)==set(expected_summary) and all(type(summary.get(key)) is int for key in numeric) and all(set(row)==set(SCHEMAS[name]) for name in ('assignments','sessions','evidence') for row in plan[name])
    test('A01','artifacts',artifact_contract)
    test('L01','lineage',lambda: set(maps()[0])==set(expected_records) and set(maps()[1])==set(expected_balances))
    test('C01','accounting',lambda: records_match('invoice',['kind','business_id','disposition']))
    test('C02','accounting',lambda: records_match('credit',['kind','business_id','disposition']))
    test('C03','accounting',lambda: records_match('payment',['kind','business_id','disposition']))
    test('C04','accounting',lambda: all(equivalent(maps()[0][k],v,['recognized_krw']) for k,v in expected_records.items()))
    test('L02','lineage',lambda: all(equivalent(maps()[0][k],v,['source_id']) for k,v in expected_records.items()))
    test('C05','accounting',lambda: balances_match(['gross_krw']))
    test('C06','accounting',lambda: balances_match(['credit_krw']))
    test('C07','accounting',lambda: balances_match(['paid_krw']))
    test('C08','accounting',lambda: balances_match(['balance_krw']) and all(int(b['gross_krw'])-int(b['credit_krw'])-int(b['paid_krw'])==int(b['balance_krw']) for b in balances))
    test('L03','lineage',lambda: balances_match(['invoice_row_id','credit_row_ids','payment_row_ids']))
    test('P01','planning',lambda: set(data()[1])==set(people) and all(equivalent(a,people[k],['tier','access_required','allowed_sessions','source_row_ids']) for k,a in data()[1].items()))
    def assignment_valid():
        _,assignments,sessions,_=data()
        for k,a in assignments.items():
            p=people[k];sid=a['session_id']
            if a['state']=='waitlist':
                if sid!='' or p['tier']!='optional':return False
            elif a['state']=='assigned':
                if sid not in sessions or sid not in p['allowed_sessions']:return False
                if p['access_required'] and not raw_sessions[sid]['accessible']:return False
            else:return False
        return True
    test('P02','planning',assignment_valid)
    test('P03','planning',lambda: all(data()[1][k]['state']=='assigned' for k,p in people.items() if p['tier']=='mandatory'))
    test('P04','planning',lambda: data()[3]['approval']=='approved' and data()[0]['approval_status']=='supplier_selection_pending')
    def legal_sessions():
        _,_,sessions,vendor=data()
        return len(sessions)==constraints['sessions_required'] and len({s['date'] for s in sessions.values()})==len(sessions) and all(
            sid in vendor['allowed_sessions'] and raw_sessions[sid]['approval']=='approved' and constraints['window_start']<=raw_sessions[sid]['date']<=constraints['window_end'] and working(date.fromisoformat(raw_sessions[sid]['date']),constraints)
            and equivalent(s,raw_sessions[sid],['date','accessible','room_cost_krw','source_id']) for sid,s in sessions.items())
    test('P05','planning',legal_sessions)
    def capacities():
        _,a,s,v=data()
        counts=Counter(r['session_id'] for r in a.values() if r['state']=='assigned')
        return all(int(r['attendees'])==counts[k] and 0<counts[k]<=min(raw_sessions[k]['capacity'],v['capacity_per_session']) and int(r['capacity'])==min(raw_sessions[k]['capacity'],v['capacity_per_session']) for k,r in s.items())
    test('P06','planning',capacities)
    def cost_valid():
        s,a,sessions,v=data();n=sum(x['state']=='assigned' for x in a.values());rooms=sum(raw_sessions[k]['room_cost_krw'] for k in sessions)
        expect=dict(vendor_fixed_krw=v['fixed_krw'],vendor_per_person_krw=v['per_person_krw'],room_cost_krw=rooms,
                    launch_cost_krw=v['fixed_krw']+n*v['per_person_krw']+rooms,assigned_count=n,
                    mandatory_count=sum(x['state']=='assigned' and people[k]['tier']=='mandatory' for k,x in a.items()),
                    optional_count=sum(x['state']=='assigned' and people[k]['tier']=='optional' for k,x in a.items()))
        return all(type(s.get(k)) is int and s[k]==value for k,value in expect.items())
    test('P07','planning',cost_valid)
    def budget_valid():
        s=data()[0];out=oracle['totals']['balance_krw'];budget=constraints['total_cash_cap_krw']-out
        return s['total_cash_cap_krw']==constraints['total_cash_cap_krw'] and s['historical_outstanding_krw']==out and s['launch_budget_krw']==budget and s['cash_remaining_krw']==budget-s['launch_cost_krw'] and 0<=s['launch_cost_krw']<=budget
    test('C09','accounting',budget_valid)
    def optimum():
        s,a,_,_=data();n=sum(x['state']=='assigned' for x in a.values())
        return n==oracle['optimum']['assigned_count'] and s['launch_cost_krw']==oracle['optimum']['launch_cost_krw']
    test('P08','planning',optimum)
    test('P09','planning',lambda: sorted(data()[0]['preparation_dates'])==preparation(min(s['date'] for s in data()[2].values()),constraints))
    test('L04','lineage',lambda: set(keyed(plan['evidence'],'file'))=={p.name for p in (ROOT/'inputs').iterdir() if p.is_file()} and all(str(e.get('source_id','')).strip() and str(e.get('use','')).strip() for e in plan['evidence']))
    def worksheet_consistency(sheet_names):
        sources=dict(records=records,balances=balances,assignments=plan['assignments'],sessions=plan['sessions'],evidence=plan['evidence'])
        keys=dict(records='row_id',balances='invoice_id',assignments='person_id',sessions='session_id',evidence='file')
        for sheet in sheet_names:
            name=SHEETS[sheet];headers,rows=wb.table(sheet)
            if headers!=SCHEMAS[name]:return False
            actual=keyed(rows,keys[name]);expected=keyed(sources[name],keys[name])
            if set(actual)!=set(expected) or not all(equivalent(actual[k],v,SCHEMAS[name]) for k,v in expected.items()):return False
        return True
    test('A02','artifacts',lambda: worksheet_consistency(['대사기록','송장잔액']))
    test('A03','artifacts',lambda: worksheet_consistency(['배정','일정','근거']))
    def summary_sheet():
        headers,rows=wb.table('예산');actual=keyed(rows,'key');summary=plan['summary']
        if headers!=['key','value'] or set(actual)!=set(summary):return False
        for key,value in summary.items():
            av=actual[key]['value']
            if isinstance(value,list):
                if normalize(av,key)!=normalize(value,key):return False
            elif isinstance(value,int):
                if av!=value:return False
            elif str(av)!=str(value):return False
        return True
    test('A04','artifacts',summary_sheet)
    # Structural prose check only: semantic quality is reserved for the frozen review rubric.
    test('A05','artifacts',lambda: len(memo.strip())>=400 and bool(re.search('[가-힣]',memo)))
    if evaluation_errors:
        return dict(status='unassessable',objective_score=None,artifact_error='; '.join(evaluation_errors),checks=[],prose_review='not_run')
    grouped={}
    for group in ('accounting','planning','lineage','artifacts'):
        subset=[c for c in checks if c['group']==group]
        grouped[group]=dict(passed=sum(c['passed'] for c in subset),total=len(subset))
    return dict(status='assessed',objective_score=round(100*sum(c['passed'] for c in checks)/len(checks),2),
                checks=checks,groups=grouped,prose_review='pending_human_semantic_rubric',
                all_objective_checks_pass=all(c['passed'] for c in checks))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('--report',type=Path);args=parser.parse_args()
    result=check(args.output);payload=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if args.report:args.report.write_text(payload,encoding='utf-8')
    print(payload,end='')
    raise SystemExit(0 if result.get('all_objective_checks_pass') else 2)
