"""Post-outcome semantic annotations; never edits first-pass scores or artifacts."""
from pathlib import Path
from itertools import combinations
from collections import Counter,defaultdict
from decimal import Decimal
import argparse,hashlib,json,re,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
parser=argparse.ArgumentParser();parser.add_argument('--storage',type=Path,required=True);STORAGE=parser.parse_args().storage.resolve()
sys.path.insert(0,str(ROOT/'v2'));import office_check as reference
ref=reference.expected();D=Decimal
single={(r['country'],r['scenario']):D(str(r['incremental_contribution_eur'])) for r in ref['hub_scenarios']}
options={r['country']:r for r in reference.rows(ROOT/'v2/source-room/hub-options.csv')}
scenarios=('low','base','high','stress');countries=set(options)
feasible={tuple(sorted(p)) for p in combinations(countries,2) if sum(int(options[c]['capex_eur']) for c in p)<=450000 and sum(int(options[c]['fte']) for c in p)<=7}

def identity(obj,inherited=None):
 for key in ('countries','country','option','portfolio','label','choice'):
  value=obj.get(key)
  if isinstance(value,list):
   if all(isinstance(c,str) and c in countries for c in value):return tuple(sorted(value))
  elif isinstance(value,str):
   tokens=re.findall(r'\b(?:DEU|FRA|NLD|POL|CZE|ESP)\b',value)
   if tokens and len(tokens)==len(set(tokens)) and len(tokens)<=2:return tuple(sorted(tokens))
 return inherited

def collect(value,path='$',pair=None,scenario=None):
 if isinstance(value,list):
  for i,item in enumerate(value):yield from collect(item,f'{path}[{i}]',pair,scenario)
 elif isinstance(value,dict):
  pair=identity(value,pair);current=value.get('scenario',scenario)
  if pair and len(pair)==2:
   if current in scenarios and isinstance(value.get('incremental_contribution_eur'),(int,float)):
    yield (path+'.incremental_contribution_eur',pair,current,value['incremental_contribution_eur'])
   for s in scenarios:
    for key in (s,s+'_eur',s+'_incremental_eur',s+'_incremental_contribution_eur',s+'_annual_incremental_contribution_eur','annual_incremental_'+s+'_eur'):
     if isinstance(value.get(key),(int,float)) and not isinstance(value.get(key),bool):yield(path+'.'+key,pair,s,value[key])
  for k,item in value.items():yield from collect(item,path+'.'+k,pair,k if k in scenarios else current)

records=[]
for cell in sorted((ROOT/'v2/results').glob('consulting-*')):
 source=STORAGE/cell.name/'locked-artifacts/deliverables/metrics.json';a=json.loads(source.read_text());strict=json.loads((ROOT/'qualification-v1/results'/cell.name/'office.json').read_text())
 own={(r['country'],r['scenario']):D(str(r['incremental_contribution_eur'])) for r in a['hub_scenarios'] if r['country'] in countries}
 pairs=[]
 for path,pair,scenario,got in collect(a):
  wanted=sum(single[c,scenario] for c in pair);own_sum=sum(own[c,scenario] for c in pair)
  pairs.append({'path':path,'countries':list(pair),'scenario':scenario,'actual_eur':got,'reference_country_sum_eur':float(wanted),'subject_country_sum_eur':float(own_sum),'matches_reference_within_5_cents':abs(D(str(got))-wanted)<=D('.05'),'matches_own_country_sum_within_5_cents':abs(D(str(got))-own_sum)<=D('.05')})
 covered={(tuple(p['countries']),p['scenario']) for p in pairs}
 required={(p,s) for p in feasible for s in scenarios}
 failed=[p for p in pairs if not p['matches_reference_within_5_cents']]
 r={'cell':cell.name,'metrics_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'strict_score_unchanged':{'passed':strict['passed'],'total':strict['total']},'shape_annotations':[],'numeric_annotations':[],'pair_checks':pairs,'required_feasible_pair_scenarios':len(required),'covered_pair_scenarios':len(required&covered),'missing_json_pair_coverage':[{'countries':list(p),'scenario':s} for p,s in sorted(required-covered)],'failed_pair_scenarios':len({(tuple(p['countries']),p['scenario']) for p in failed}),'recommendation':a['recommendation']}
 for g in strict['groups']:
  if g['pass_']:continue
  if g['name'].endswith('_shape'):
   r['shape_annotations'].append({'group':g['name'],'strict_detail':g['details'],'classification':'Exact array membership is stricter than the task; verify required rows, extra pairs/defer/EUR and their values separately.'})
  elif g['name'].endswith('_values'):
   failures=g['details'];rounding_only=all(x['field']=='payback_years' and isinstance(x['actual'],(int,float)) and abs(x['actual']-x['expected'])<=.0051 for x in failures)
   r['numeric_annotations'].append({'group':g['name'],'mismatch_count':len(failures),'fields':dict(Counter(x['field'] for x in failures)),'classification':'Payback rounded to two decimals; task did not specify 0.001-year accuracy.' if rounding_only else 'Substantive numerical mismatch; trace shared upstream defects rather than count correlated groups as independent failures.'})
 records.append(r)
 print(cell.name,'pair coverage',len(required&covered),'of',len(required),'bad unique pairs',r['failed_pair_scenarios'])
# Independent trace for effective-date counterexample: latest revision eligible SENSOR shipments.
orders=reference.latest([r for n in ('orders-part1.csv','orders-part2.csv','order-corrections.csv') for r in reference.rows(ROOT/'v2/source-room'/n)],'order_id')
returns=reference.latest(reference.rows(ROOT/'v2/source-room/returns.csv'),'return_id')
restocked=defaultdict(int)
for r in returns.values():
 if r['received_at']<='2026-01-31':restocked[r['order_id']]+=int(r['restocked_quantity'])
delta=defaultdict(lambda:D(0))
for oid,r in orders.items():
 if r['status']=='shipped' and r['is_test']=='false' and '2025-07-01'<=r['shipped_at']<='2025-12-31' and r['sku']=='SENSOR':delta[r['country']]+=D(int(r['quantity'])-restocked[oid])*D('1.5')
result={'scope':'Post-outcome semantic diagnostics from existing frozen artifacts; original scores unchanged; additional rows and two-decimal rounding do not imply correct substantive arithmetic. JSON coverage gaps need document/workbook follow-up.','pair_rule':'Sum per-country effects with no synergy. Apply FX only to PLN/CZK country revenue. Monetary comparison tolerance0.05EUR matches original checker; do not treat duplicate representations as independent failures.','effective_date_counterexample':{'source':'analysis/analyze.py:109 in consulting-gpt-6-luna-high-v15','correct_july_sensor_cost_eur':41.5,'chosen_maximum_historical_cost_eur':43,'reconstructed_cogs_overstatement_by_country':{c:float(v) for c,v in delta.items()},'total_cogs_overstatement_eur':float(sum(delta.values()))},'cells':records}
(HERE/'office-semantics.json').write_text(json.dumps(result,indent=2)+'\n')
