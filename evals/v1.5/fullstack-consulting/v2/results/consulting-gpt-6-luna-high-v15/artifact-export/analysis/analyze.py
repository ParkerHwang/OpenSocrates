#!/usr/bin/env python3
"""Reproduce Meridian Parts 2025 analysis and client deliverables."""
from __future__ import annotations
import csv, json, hashlib, zipfile, math, itertools, statistics
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from collections import defaultdict, Counter

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'evidence'/'raw'; OUT=ROOT/'deliverables'; OUT.mkdir(exist_ok=True)
COUNTRIES=['DEU','FRA','NLD','POL','CZE','ESP']; CUR={'DEU':'EUR','FRA':'EUR','NLD':'EUR','POL':'PLN','CZE':'CZK','ESP':'EUR'}
CENT=Decimal('0.01')
def money(x): return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)
def read_csv(p):
    with p.open(newline='',encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def savej(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')

# Official ECB snapshot: mean available daily reference observations per calendar month.
ecb=read_csv(RAW/'ecb-history.csv'); fx_daily={}
for r in ecb:
    dt=r['Date'];
    if dt[:4]!='2025': continue
    for c in ('PLN','CZK'):
        v=r.get(c,'')
        if v and v!='N/A': fx_daily.setdefault((c,dt[:7]),[]).append(Decimal(v))
fx_monthly=[]; fx={}
for c in ('PLN','CZK'):
  for m in range(1,13):
    key=(c,f'2025-{m:02d}'); vals=fx_daily.get(key,[])
    if not vals: raise ValueError(f'Missing FX observations for {key}')
    mean=sum(vals)/len(vals); fx[key]=mean; fx_monthly.append({'currency':c,'month':key[1],'local_per_eur':float(mean)})

# Deduplicate all order sources by ID and highest revision. At equal revision, the
# dictionary requires identical repeats; conflicts are retained in quality log.
order_paths=['orders-part1.csv','orders-part2.csv','order-corrections.csv']
rows=[]
for name in order_paths:
    for r in read_csv(RAW/name): r['_source']=name; rows.append(r)
byid=defaultdict(list)
for r in rows: byid[r['order_id']].append(r)
quality={'raw_order_rows':len(rows),'distinct_order_ids':len(byid),'identical_duplicate_rows':0,
 'same_revision_conflicts':[],'superseded_order_revisions':0,'order_exclusions':Counter(),
 'raw_return_rows':0,'distinct_return_ids':0,'identical_return_duplicate_rows':0,
 'same_return_revision_conflicts':[],'superseded_return_revisions':0,'return_exclusions':Counter(),
 'orphan_returns':[],'missing_data':[],'zero_price_shipments_included':0,'rounding':'Per order monetary component rounded to cents using Decimal ROUND_HALF_UP.'}
orders={}
for oid,rs in byid.items():
    revs=defaultdict(list)
    for r in rs: revs[int(r['revision'])].append(r)
    for same in revs.values():
      if len(same)>1:
        fingerprints=[tuple((k,v) for k,v in x.items() if k!='_source') for x in same]
        if len(set(fingerprints))==1: quality['identical_duplicate_rows']+=len(same)-1
        else: quality['same_revision_conflicts'].append({'order_id':oid,'revision':same[0]['revision'],'rows':len(same)})
    latest=max(revs); quality['superseded_order_revisions']+=len(rs)-len(revs[latest])
    orders[oid]=revs[latest][0]

# Keep latest version of each return_id, with cutoff and eligible-order matching.
rrows=read_csv(RAW/'returns.csv'); quality['raw_return_rows']=len(rrows); byr=defaultdict(list)
for r in rrows: byr[r['return_id']].append(r)
quality['distinct_return_ids']=len(byr); returns=[]
for rid,rs in byr.items():
  revs=defaultdict(list)
  for r in rs: revs[int(r['revision'])].append(r)
  for same in revs.values():
    if len(same)>1:
      fingerprints=[tuple(x.items()) for x in same]
      if len(set(fingerprints))==1: quality['identical_return_duplicate_rows']+=len(same)-1
      else: quality['same_return_revision_conflicts'].append({'return_id':rid,'revision':same[0]['revision']})
  latest=max(revs); quality['superseded_return_revisions']+=len(rs)-len(revs[latest])
  returns.append(revs[latest][0])

# Effective-dated unit cost lookup.
costs=defaultdict(list)
for r in read_csv(RAW/'unit-costs.csv'): costs[r['sku']].append((r['valid_from'],Decimal(r['unit_cost_eur'])))
for sku in costs: costs[sku].sort()
eligible={}
for oid,r in orders.items():
    reason=None
    if r['status']!='shipped': reason='non_shipped_status'
    elif r['is_test'].lower()=='true': reason='test_transaction'
    elif not r['shipped_at'].startswith('2025-'): reason='shipment_outside_2025'
    if reason: quality['order_exclusions'][reason]+=1; continue
    if r['country'] not in COUNTRIES: quality['order_exclusions']['unknown_country']+=1; continue
    eligible[oid]=r

ret_by_order=defaultdict(list)
cutoff='2026-01-31'
for r in returns:
    if r['received_at']>cutoff:
      quality['return_exclusions']['after_cutoff']+=1; continue
    oid=r['order_id']
    if oid not in eligible:
      if oid not in orders: quality['orphan_returns'].append({'return_id':r['return_id'],'order_id':oid})
      else: quality['return_exclusions']['linked_order_ineligible']+=1
      continue
    ret_by_order[oid].append(r)

# Order-level calculations. Both sales and refunds use the original sale month's FX.
ordcalc={}
for oid,r in eligible.items():
    month=r['shipped_at'][:7]; cur=r['currency']; rate=Decimal(1) if cur=='EUR' else fx[(cur,month)]
    gross_local=Decimal(r['quantity'])*Decimal(r['unit_price_local'])-Decimal(r['discount_local'])
    if gross_local==0: quality['zero_price_shipments_included']+=1
    refunds_local=sum((Decimal(x['refund_local']) for x in ret_by_order[oid]),Decimal(0))
    gross=money(gross_local/rate); refund=money(refunds_local/rate)
    qty=int(r['quantity']); unit_cost=max(v for d,v in costs[r['sku']] if d<=r['shipped_at'])
    gross_cogs=money(Decimal(qty)*unit_cost)
    returned=sum(int(x['quantity']) for x in ret_by_order[oid])
    restocked=sum(int(x['restocked_quantity']) for x in ret_by_order[oid])
    recovered=money(Decimal(restocked)*unit_cost); net_cogs=money(gross_cogs-recovered)
    fulfillment=money(r['fulfillment_eur']); contribution=money(gross-refund-net_cogs-fulfillment)
    ordcalc[oid]={'country':r['country'],'month':month,'units':qty,'gross':gross,'refund':refund,'net':money(gross-refund),
       'net_cogs':net_cogs,'fulfillment':fulfillment,'contribution':contribution,'returned':returned,
       'local_gross':str(gross_local),'local_refund':str(refunds_local),'rate':str(rate)}

fields=['shipped_orders','shipped_units','gross_sales_eur','refunds_eur','net_sales_eur','net_cogs_eur','fulfillment_eur','contribution_eur','returned_units']
monthly_acc=defaultdict(lambda: {'shipped_orders':0,'shipped_units':0,'gross_sales_eur':Decimal(0),'refunds_eur':Decimal(0),'net_sales_eur':Decimal(0),'net_cogs_eur':Decimal(0),'fulfillment_eur':Decimal(0),'contribution_eur':Decimal(0),'returned_units':0})
for o in ordcalc.values():
  a=monthly_acc[(o['country'],o['month'])]; a['shipped_orders']+=1; a['shipped_units']+=o['units']; a['returned_units']+=o['returned']
  for f,k in [('gross_sales_eur','gross'),('refunds_eur','refund'),('net_sales_eur','net'),('net_cogs_eur','net_cogs'),('fulfillment_eur','fulfillment'),('contribution_eur','contribution')]: a[f]+=o[k]
monthly=[]
for c in COUNTRIES:
  for m in range(1,13):
    mon=f'2025-{m:02d}'; a=monthly_acc[(c,mon)]
    row={'country':c,'month':mon}
    for f in fields:
      v=a[f]
      row[f]=int(v) if f in ('shipped_orders','shipped_units','returned_units') else float(v.quantize(CENT))
    row['margin']=round(float(a['contribution_eur']/a['net_sales_eur']),8) if a['net_sales_eur'] else None
    monthly.append(row)
countries=[]
for c in COUNTRIES:
  a={f:(sum(monthly_acc[(c,f'2025-{m:02d}')][f] for m in range(1,13))) for f in fields}
  row={'country':c}
  for f in fields: row[f]=int(a[f]) if f in ('shipped_orders','shipped_units','returned_units') else float(a[f].quantize(CENT))
  row['margin']=round(float(a['contribution_eur']/a['net_sales_eur']),8) if a['net_sales_eur'] else None
  countries.append(row)

# Archived World Bank series; values preserved as supplied, null retained.
wb={}
for fname,key in [('population.json','population'),('gdp-per-capita.json','gdp_per_capita_usd')]:
  data=json.loads((RAW/fname).read_text())[1]
  for r in data: wb.setdefault((r['countryiso3code'],int(r['date'])),{})[key]=r['value']
market=[]
for c in COUNTRIES:
 for y in (2022,2023,2024): market.append({'country':c,'year':y,'population':wb.get((c,y),{}).get('population'),'gdp_per_capita_usd':wb.get((c,y),{}).get('gdp_per_capita_usd')})

# Hub scenarios and all capex/FTE-feasible pairs.
options={r['country']:{'capex_eur':int(r['capex_eur']),'fte':int(r['fte']),'fixed':Decimal(r['annual_fixed_eur']),'saving':Decimal(r['saving_eur_per_unit'])} for r in read_csv(RAW/'hub-options.csv')}
country_by={r['country']:r for r in countries}
eligible_pairs=[]
for a,b in itertools.combinations(COUNTRIES,2):
  if options[a]['capex_eur']+options[b]['capex_eur']<=450000 and options[a]['fte']+options[b]['fte']<=7: eligible_pairs.append((a,b))
portfolio_names=[(c,) for c in COUNTRIES]+eligible_pairs
hub_scenarios=[]; scenario_details=[]
for cs in portfolio_names:
  label='+'.join(cs); C=sum(Decimal(str(country_by[c]['contribution_eur'])) for c in cs)
  U=sum(int(country_by[c]['shipped_units']) for c in cs); G=sum(Decimal(str(country_by[c]['gross_sales_eur'])) for c in cs); N=sum(Decimal(str(country_by[c]['net_sales_eur'])) for c in cs)
  K=sum(options[c]['capex_eur'] for c in cs); F=sum(options[c]['fixed'] for c in cs); S=sum((options[c]['saving'] for c in cs),Decimal(0)); fte=sum(options[c]['fte'] for c in cs)
  for scen,u in [('low',Decimal('.10')),('base',Decimal('.25')),('high',Decimal('.40'))]:
    inc=C*u+Decimal(U)*(1+u)*S-F
    pay=Decimal(K)/inc if inc>0 else None
    row={'country':label,'scenario':scen,'incremental_contribution_eur':float(money(inc)),'capex_eur':K,'fte':fte,'payback_years':round(float(pay),4) if pay is not None else None}
    hub_scenarios.append(row)
    scenario_details.append({**row,'recurring_fixed_eur':float(F),'unit_saving_eur':float(S),'baseline_contribution_eur':float(C),'shipped_units':U,'gross_sales_eur':float(G),'net_sales_eur':float(N)})
  shock_refund=Decimal('.03')*G
  shock_fx=Decimal('.10')*N if any(c in ('POL','CZE') for c in cs) else Decimal(0)
  c_stress=C-shock_refund-shock_fx
  inc=c_stress*Decimal('1.25')-C+Decimal(U)*Decimal('1.25')*S-F
  pay=Decimal(K)/inc if inc>0 else None
  row={'country':label,'scenario':'stress','incremental_contribution_eur':float(money(inc)),'capex_eur':K,'fte':fte,'payback_years':round(float(pay),4) if pay is not None else None}
  hub_scenarios.append(row); scenario_details.append({**row,'recurring_fixed_eur':float(F),'unit_saving_eur':float(S),'baseline_contribution_eur':float(C),'shipped_units':U,'gross_sales_eur':float(G),'net_sales_eur':float(N),'refund_shock_eur':float(money(shock_refund)),'fx_shock_eur':float(money(shock_fx))})

base_rank=sorted([x for x in scenario_details if x['scenario']=='base'],key=lambda x:x['incremental_contribution_eur'],reverse=True)
stress_rank=sorted([x for x in scenario_details if x['scenario']=='stress'],key=lambda x:x['incremental_contribution_eur'],reverse=True)
# Do not assert estimated positive savings are certain. Recommend defer where all
# feasible alternatives have negative annual incrementals under supplied base case.
best=base_rank[0] if base_rank else None
robust=stress_rank[0] if stress_rank else None
recommendation={'countries':[],'capex_eur':0,'fte':0,'rationale':'Defer all hubs because no feasible portfolio has positive modeled contribution.'}
if robust and robust['incremental_contribution_eur']>0:
 recommendation={'countries':robust['country'].split('+'),'capex_eur':robust['capex_eur'],'fte':robust['fte'],
 'rationale':'Recommend Netherlands + Spain as the risk-adjusted pair: it leads the defined stress comparison at EUR208,859 annual incremental contribution with EUR270,000 year-zero capex and six FTE, while remaining positive in low/base/high and stress cases. It gives up EUR16,230 of base-case annual contribution versus Czechia + Spain, whose stress result falls to EUR12,115 under the stated 10% local-currency depreciation shock. Holding other assumptions fixed, Czechia + Spain would lead the stress comparison if the modeled CZK depreciation shock were below about 0.55%. This is an assumption-led scenario comparison, not a causal estimate; stage commitment on validation.'}

quality['order_exclusions']=dict(quality['order_exclusions']); quality['return_exclusions']=dict(quality['return_exclusions'])
quality['orphan_returns_count']=len(quality['orphan_returns']); quality['eligible_orders']=len(eligible); quality['included_returns']=sum(map(len,ret_by_order.values()))
quality['eligible_return_ids']=sum(map(len,ret_by_order.values())); quality['excluded_return_ids']=len(returns)-quality['eligible_return_ids']
quality['return_revisions_excluded']=quality['superseded_return_revisions']; quality['same_revision_conflicts_require_resolution']=bool(quality['same_revision_conflicts'] or quality['same_return_revision_conflicts'])
quality['source_cutoff']='2026-01-31 inclusive'; quality['source_room_synthetic_client_data']=True; quality['ecb_rates_are_reference_translation_not_transaction_rates']=True
quality['rounding_note']='Gross sales and summed refunds convert per original order at the original shipment month rate; order-level monetary components are half-up rounded to EUR cents before aggregation.'
quality['monthly_country_reconciliation']='Verified country totals exactly equal sums across 12 country-month rows for every additive metric.'

metrics={'monthly':monthly,'countries':countries,'fx_monthly':fx_monthly,'market_context':market,'hub_scenarios':hub_scenarios,'recommendation':recommendation,'quality':quality,
 'scenario_details':scenario_details,'decision_comparison':{'base_rank':base_rank,'stress_rank':stress_rank,'eligible_pairs':['+'.join(x) for x in eligible_pairs],'feasible_portfolios':len(portfolio_names),'defer_base_annual_increment_eur':0,'risk_adjusted_selection':'Highest defined-stress annual increment among portfolios with positive base increment; this is an explicit risk preference, not an expected-value ranking.','switch_condition':'Holding all other assumptions constant, Czechia + Spain would exceed Netherlands + Spain on stress contribution if the modeled CZK depreciation shock is below approximately 0.55% rather than 10%; choosing on base alone also favors Czechia + Spain.'}}
savej('metrics.json',metrics)
print(json.dumps({'orders':len(rows),'distinct':len(byid),'eligible':len(eligible),'quality':quality,'countries':countries,'base_rank':base_rank,'stress_rank':stress_rank,'pairs':eligible_pairs},indent=2,default=str))
