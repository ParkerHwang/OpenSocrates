#!/usr/bin/env python3
"""Rebuild Meridian Parts analysis and board deliverables from saved source files."""
from __future__ import annotations
import csv, hashlib, itertools, json, math, os, zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from pptx import Presentation
from pptx.util import Inches as PInches, Pt as PPt
from pptx.dml.color import RGBColor as PRGB
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'sources' / 'raw'
OUT = ROOT / 'deliverables'
OUT.mkdir(exist_ok=True)
COUNTRIES = ['DEU','FRA','NLD','POL','CZE','ESP']
CN = {'DEU':'Germany','FRA':'France','NLD':'Netherlands','POL':'Poland','CZE':'Czechia','ESP':'Spain'}
CUR = {'DEU':'EUR','FRA':'EUR','NLD':'EUR','POL':'PLN','CZE':'CZK','ESP':'EUR'}
MONTHS = [f'2025-{m:02d}' for m in range(1,13)]
FIELDS = ['country','shipped_orders','shipped_units','gross_sales_eur','refunds_eur','net_sales_eur','net_cogs_eur','fulfillment_eur','contribution_eur','returned_units','margin']

def dec(x): return Decimal(str(x))
def cents(x): return dec(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
def num(x):
    if x is None or pd.isna(x): return None
    if isinstance(x, Decimal): return float(x)
    return float(x) if isinstance(x,(int,float)) else x
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(obj,p): p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def ssum(df,col): return round(float(df[col].sum()),2)

# ECB: source CSV is a lossless extraction of the archived official ZIP.
fxraw = pd.read_csv(RAW/'ecb-history.csv')
fxraw['Date'] = pd.to_datetime(fxraw['Date'],errors='coerce')
fx2025 = fxraw[(fxraw.Date >= '2025-01-01') & (fxraw.Date < '2026-01-01')].copy()
fx_month = {}
fx_rows=[]
for code,currency in [('PLN','PLN'),('CZK','CZK')]:
    for month,g in fx2025.groupby(fx2025.Date.dt.strftime('%Y-%m')):
        value=float(g[code].dropna().mean())
        fx_month[(currency,month)] = value
        fx_rows.append({'currency':currency,'month':month,'local_per_eur':value,'published_business_days':int(g[code].count())})
for m in MONTHS:
    fx_month[('EUR',m)] = 1.0

# Latest numeric revision wins across both page extracts and corrections.
srcs=[]
for fn in ['orders-part1.csv','orders-part2.csv','order-corrections.csv']:
    d=pd.read_csv(RAW/fn,dtype={'order_id':str,'currency':str,'sku':str})
    d['_source']=fn; srcs.append(d)
orders=pd.concat(srcs,ignore_index=True)
orders['revision']=pd.to_numeric(orders.revision,errors='coerce')
orders['is_test']=orders.is_test.astype(str).str.lower().map({'true':True,'false':False})
orders['shipped_at']=pd.to_datetime(orders.shipped_at,errors='coerce')
orders['_rowhash']=orders.drop(columns=['_source','_rowhash'],errors='ignore').astype(str).agg('|'.join,axis=1)
order_key_cols=orders.columns.difference(['_source','_rowhash'])
dup_rows=int(orders.duplicated(subset=order_key_cols,keep='first').sum())
orders=orders.drop_duplicates(subset=order_key_cols,keep='first').copy()
order_revisioned=int(orders.groupby('order_id').revision.nunique().gt(1).sum())
order_revision_conflicts=int(orders.groupby(['order_id','revision']).size().gt(1).sum())
orders=orders.sort_values(['order_id','revision','_source']).drop_duplicates(['order_id','revision'],keep='last')
orders=orders.sort_values(['order_id','revision']).drop_duplicates('order_id',keep='last').copy()
orders['_eligible']=(orders.status.eq('shipped') & orders.is_test.eq(False) & orders.shipped_at.ge('2025-01-01') & orders.shipped_at.lt('2026-01-01'))
eligible=orders[orders._eligible].copy()

# Returns are revisioned by return ID; only returns known by inclusive cutoff
# and linked to an eligible, unique selected order enter the calculation.
returns=pd.read_csv(RAW/'returns.csv',dtype={'return_id':str,'order_id':str})
returns['revision']=pd.to_numeric(returns.revision,errors='coerce')
returns['received_at']=pd.to_datetime(returns.received_at,errors='coerce')
ret_total=len(returns)
ret_dup=int(returns.duplicated(keep='first').sum())
returns=returns.drop_duplicates(keep='first').copy()
return_revisioned=int(returns.groupby('return_id').revision.nunique().gt(1).sum())
return_revision_conflicts=int(returns.groupby(['return_id','revision']).size().gt(1).sum())
returns=returns.sort_values(['return_id','revision']).drop_duplicates('return_id',keep='last').copy()
cutoff=pd.Timestamp('2026-01-31')
ret_cut=returns[returns.received_at.le(cutoff)].copy()
eligible_ids=set(eligible.order_id)
orphan=ret_cut[~ret_cut.order_id.isin(eligible_ids)].copy()
ret_valid=ret_cut[ret_cut.order_id.isin(eligible_ids)].copy()
eligible['sale_month']=eligible.shipped_at.dt.strftime('%Y-%m')
eligible['currency']=eligible.currency.fillna(eligible.country.map(CUR))
ret_valid=ret_valid.merge(eligible[['order_id','sale_month','currency','sku','quantity']],on='order_id',how='left',validate='many_to_one',suffixes=('','_order'))
return_units_by=ret_valid.groupby('order_id').quantity.sum()
return_excess_orders=int((return_units_by>eligible.set_index('order_id').quantity.reindex(return_units_by.index)).sum())
restock_excess_rows=int((ret_valid.restocked_quantity>ret_valid.quantity).sum())
local_gross=eligible.quantity*eligible.unit_price_local-eligible.discount_local
refund_local_by=ret_valid.groupby('order_id').refund_local.sum()
gross_local_by=pd.Series(local_gross.values,index=eligible.order_id)
refund_excess_orders=int((refund_local_by>gross_local_by.reindex(refund_local_by.index)).sum())

# Join source month FX; local EUR conversion quote is local currency per EUR.
fx_order={}
for (currency,month),rate in fx_month.items(): fx_order[(currency,month)]=rate
ret_by=ret_valid.groupby('order_id',as_index=True).agg(refund_local=('refund_local','sum'),returned_units=('quantity','sum'),restocked_quantity=('restocked_quantity','sum'),return_ids=('return_id','nunique'))
ret_by['returned_units']=ret_valid.groupby('order_id').quantity.sum()
ret_by['restocked_quantity']=ret_valid.groupby('order_id').restocked_quantity.sum()
eligible=eligible.merge(ret_by[['refund_local','returned_units','restocked_quantity']],left_on='order_id',right_index=True,how='left')
eligible[['refund_local','returned_units','restocked_quantity']]=eligible[['refund_local','returned_units','restocked_quantity']].fillna(0)

costs=pd.read_csv(RAW/'unit-costs.csv')
costs['valid_from']=pd.to_datetime(costs.valid_from)
cost_map={sku:g.sort_values('valid_from') for sku,g in costs.groupby('sku')}
missing_cost=[]; missing_fx=[]
gross=[]; refund=[]; netcogs=[]; fulfill=[]; contrib=[]; returned=[]; netsales=[]
for _,o in eligible.iterrows():
    m=o.sale_month; cur=o.currency; rate=fx_order.get((cur,m))
    if rate is None: missing_fx.append(o.order_id); rate=math.nan
    price=dec(o.quantity)*dec(o.unit_price_local)-dec(o.discount_local)
    gr=cents(price/dec(rate)) if math.isfinite(rate) else None
    rf=cents(dec(o.refund_local)/dec(rate)) if math.isfinite(rate) else None
    cg=cost_map.get(o.sku)
    cost_per=None if cg is None else cg[cg.valid_from.le(o.shipped_at)].iloc[-1].unit_cost_eur if not cg[cg.valid_from.le(o.shipped_at)].empty else None
    if cost_per is None: missing_cost.append(o.order_id); cost_per=0
    gc=cents(dec(o.quantity)*dec(cost_per))
    rc=cents(dec(o.restocked_quantity)*dec(cost_per))
    nc=gc-rc
    fl=cents(o.fulfillment_eur)
    co=gr-rf-nc-fl if gr is not None and rf is not None else None
    gross.append(float(gr) if gr is not None else math.nan); refund.append(float(rf) if rf is not None else math.nan)
    netcogs.append(float(nc)); fulfill.append(float(fl)); contrib.append(float(co) if co is not None else math.nan)
    netsales.append(float(gr-rf) if gr is not None and rf is not None else math.nan); returned.append(int(o.returned_units))
eligible['gross_sales_eur']=gross; eligible['refunds_eur']=refund; eligible['net_sales_eur']=netsales
eligible['net_cogs_eur']=netcogs; eligible['fulfillment_eur']=fulfill; eligible['contribution_eur']=contrib; eligible['returned_units']=returned

# Include explicit 72 country-month rows, even where the outcome is zero.
monthly=[]
for c in COUNTRIES:
  for m in MONTHS:
    d=eligible[(eligible.country==c)&(eligible.sale_month==m)]
    rec={'country':c,'month':m,'shipped_orders':int(d.order_id.nunique()),'shipped_units':int(d.quantity.sum())}
    for col in ['gross_sales_eur','refunds_eur','net_sales_eur','net_cogs_eur','fulfillment_eur','contribution_eur']:
        rec[col]=ssum(d,col)
    rec['returned_units']=int(d.returned_units.sum())
    rec['margin']=rec['contribution_eur']/rec['net_sales_eur'] if rec['net_sales_eur'] else None
    monthly.append(rec)
country_rows=[]
for c in COUNTRIES:
 d=eligible[eligible.country==c]
 rec={'country':c,'shipped_orders':int(d.order_id.nunique()),'shipped_units':int(d.quantity.sum())}
 for col in ['gross_sales_eur','refunds_eur','net_sales_eur','net_cogs_eur','fulfillment_eur','contribution_eur']: rec[col]=ssum(d,col)
 rec['returned_units']=int(d.returned_units.sum()); rec['margin']=rec['contribution_eur']/rec['net_sales_eur'] if rec['net_sales_eur'] else None
 country_rows.append(rec)

# Preserve archived World Bank observations and nulls exactly as published.
wbpop=json.loads((RAW/'population.json').read_text())
wbgdp=json.loads((RAW/'gdp-per-capita.json').read_text())
def wb_map(obj): return {(x.get('countryiso3code'),int(x['date'])): x.get('value') for x in obj[1]}
pop=wb_map(wbpop); gdp=wb_map(wbgdp)
market=[]
for c in COUNTRIES:
 for y in [2022,2023,2024]: market.append({'country':c,'year':y,'population':pop.get((c,y)),'gdp_per_capita_usd':gdp.get((c,y))})

opts=pd.read_csv(RAW/'hub-options.csv').set_index('country')
scenarios=[]
for c in COUNTRIES:
 b=next(r for r in country_rows if r['country']==c); o=opts.loc[c]
 C=b['contribution_eur']; U=b['shipped_units']; G=b['gross_sales_eur']; N=b['net_sales_eur']; s=float(o.saving_eur_per_unit); F=float(o.annual_fixed_eur); K=float(o.capex_eur)
 fxshock=0.10*N if c in ['POL','CZE'] else 0.0
 for scenario,u in [('low',.10),('base',.25),('high',.40)]:
  inc=C*u+U*(1+u)*s-F
  scenarios.append({'country':c,'scenario':scenario,'incremental_contribution_eur':round(inc,2),'capex_eur':K,'fte':int(o.fte),'payback_years':round(K/inc,4) if inc>0 else None,'annual_fixed_eur':F,'saving_eur_per_unit':s,'volume_uplift':u})
 Cstress=C-.03*G-fxshock; u=.25
 inc=Cstress*1.25-C+U*1.25*s-F
 scenarios.append({'country':c,'scenario':'stress','incremental_contribution_eur':round(inc,2),'capex_eur':K,'fte':int(o.fte),'payback_years':round(K/inc,4) if inc>0 else None,'annual_fixed_eur':F,'saving_eur_per_unit':s,'volume_uplift':u,'refund_shock_eur':round(.03*G,2),'fx_shock_eur':round(fxshock,2)})

# Every single option, every pair, and the defer case; only options meeting both
# board caps are feasible. Pair economics are additive with no assumed synergy.
alternatives=[{'countries':[],'label':'Defer','capex_eur':0,'fte':0,'annual_fixed_eur':0,'low':0,'base':0,'high':0,'stress':0}]
for n in [1,2]:
 for group in itertools.combinations(COUNTRIES,n):
  sc={s:round(sum(next(x['incremental_contribution_eur'] for x in scenarios if x['country']==c and x['scenario']==s) for c in group),2) for s in ['low','base','high','stress']}
  cap=sum(int(opts.loc[c].capex_eur) for c in group); fte=sum(int(opts.loc[c].fte) for c in group)
  alternatives.append({'countries':list(group),'label':' + '.join(group) if group else 'Defer','capex_eur':cap,'fte':fte,'annual_fixed_eur':sum(int(opts.loc[c].annual_fixed_eur) for c in group),**sc,'feasible':cap<=450000 and fte<=7})
for a in alternatives:
 if 'feasible' not in a:a['feasible']=True
feasible=sorted([a for a in alternatives if a['feasible']],key=lambda a:(a['base'],a['stress']),reverse=True)
for a in alternatives: a['minimum_scenario_eur']=min(a[s] for s in ['low','base','high','stress'])
for rank,a in enumerate(sorted([x for x in alternatives if x['feasible']],key=lambda x:(x['minimum_scenario_eur'],x['base']),reverse=True),1): a['rank_maximin']=rank
for rank,a in enumerate(sorted([x for x in alternatives if x['feasible']],key=lambda x:(x['base'],x['stress']),reverse=True),1): a['rank_base']=rank
for a in alternatives:
 a.setdefault('rank_maximin',None); a.setdefault('rank_base',None)
best=max((a for a in feasible),key=lambda a:(a['minimum_scenario_eur'],a['base']))
bestpairs=sorted([a for a in alternatives if a['feasible'] and len(a['countries'])==2],key=lambda x:x['base'],reverse=True)

quality={
 'source_status':'Client transaction and option files are synthetic. World Bank and ECB files are official public snapshots collected into the frozen source room; archive vintage is 2026-09-27 and may include subsequent historical revisions.',
 'orders':{'raw_rows':len(pd.concat(srcs)),'unique_order_ids':int(pd.concat(srcs).order_id.nunique()),'selected_after_revision':len(orders),'duplicate_rows_removed':dup_rows,'revisioned_ids':order_revisioned,'same_revision_conflicting_groups':order_revision_conflicts,'eligible_2025_shipped_orders':len(eligible),'excluded_status_or_test_or_date':int((~orders._eligible).sum()),'exclusion_counts_after_revision':{'not_shipped':int((orders.status!='shipped').sum()),'test_shipped':int(((orders.status=='shipped')&orders.is_test.fillna(False)).sum()),'shipped_date_outside_2025_or_missing':int(((orders.status=='shipped')&~orders.is_test.fillna(False)&(~orders.shipped_at.ge('2025-01-01')|~orders.shipped_at.lt('2026-01-01'))).sum())}},
 'returns':{'raw_rows':ret_total,'unique_return_ids':int(returns.return_id.nunique()),'revisioned_ids':return_revisioned,'exact_duplicate_rows_removed':ret_dup,'same_revision_conflicting_groups':return_revision_conflicts,'known_by_cutoff_unique_returns':len(ret_cut),'eligible_linked_returns':len(ret_valid),'quarantined_orphan_or_ineligible_returns':len(orphan),'after_cutoff_returns':int((returns.received_at>cutoff).sum()),'orphan_ids':orphan.return_id.tolist(),'return_units_exceeding_shipped_orders':return_excess_orders,'rows_restocking_more_than_returned':restock_excess_rows,'orders_with_refunds_above_gross_local_sales':refund_excess_orders,'missing_linked_order_is_quarantined':True},
 'sales_checks':{'valid_zero_price_shipments':int((local_gross==0).sum()),'negative_gross_local_sales_orders':int((local_gross<0).sum()),'currency_country_mismatches':int((eligible.currency!=eligible.country.map(CUR)).sum())},
 'missing':{'unknown_order_revisions':int(pd.concat(srcs).revision.isna().sum()),'missing_fx_orders':missing_fx,'missing_cost_orders':missing_cost,'missing_world_bank_population':sum(pop.get((c,y)) is None for c in COUNTRIES for y in [2022,2023,2024]),'missing_world_bank_gdp':sum(gdp.get((c,y)) is None for c in COUNTRIES for y in [2022,2023,2024])},
 'handling':{'orders':'Deduplicate identical full rows, choose highest numeric revision per order_id across both extracts and correction file; corrections replace the whole row. Include shipped, non-test 2025 shipment dates only. Keep zero-price shipments; exclude January 2026 orders.','returns':'Deduplicate identical full rows, choose highest numeric revision per return_id. Include received_at through 2026-01-31 inclusive only when linked to an eligible selected order. Quarantine orphan/ineligible returns; add distinct valid return IDs. COGS recovery follows restocked_quantity only.','fx':'Use original sale month ECB mean local-currency-units-per-EUR quote for gross sales and aggregate refunds; EUR=1. No inversion.','missing':'Do not impute source missingness; list missing FX/unit-cost orders and retain World Bank nulls. No missing values were detected in required calculation fields.'},
 'accounting':'Per selected eligible order: gross local price net of discount and refund credit summed in original sale currency, each translated at original sale-month ECB mean local units per EUR, rounded half-up to EUR cents. EUR quote=1. Net COGS = rounded gross unit cost less rounded recovered restocked unit cost. Fulfillment is nonrefundable. Contribution = net sales - net COGS - fulfillment. Returned units count received physical quantity.'}

metrics={'monthly':monthly,'countries':country_rows,'fx_monthly':fx_rows,'market_context':market,'hub_scenarios':[{'country':x['country'],'scenario':x['scenario'],'incremental_contribution_eur':x['incremental_contribution_eur'],'capex_eur':x['capex_eur'],'fte':x['fte'],'payback_years':x['payback_years']} for x in scenarios],
 'recommendation':{'countries':best['countries'],'capex_eur':best['capex_eur'],'fte':best['fte'],'rationale':f"Conservative maximin screen: {best['label']} has the highest minimum annual increment across the client-defined low/base/high/stress cases among alternatives within EUR450,000 capex and seven FTE. Low EUR{best['low']:,.2f}, base EUR{best['base']:,.2f}, high EUR{best['high']:,.2f}, stress EUR{best['stress']:,.2f}; minimum EUR{best['minimum_scenario_eur']:,.2f}. This is an explicit downside preference, not a probability forecast or causal estimate."},
 'ranking_basis':'Recommend the feasible alternative with the highest minimum annual incremental contribution across the client-defined low/base/high/stress cases; use base-case contribution to identify and compare the strongest different alternative. No scenario probabilities or board preference weights were supplied.',
 'quality':quality,'alternatives':alternatives,'source_files':[]}
dump(metrics,OUT/'metrics.json')

# Source register with archive links and local hashes. No client-system access occurred.
source_meta=json.loads((RAW/'source-register.json').read_text())
register=[]
for p in sorted(RAW.iterdir()):
 kind='synthetic_client_input'
 url='http://127.0.0.1:49789/'+p.name
 period='2025 transactions; returns cutoff 2026-01-31' if p.name in ['orders-part1.csv','orders-part2.csv','order-corrections.csv','returns.csv'] else 'scenario assumptions' if p.name in ['hub-options.csv','scenario-policy.md','unit-costs.csv'] else 'definition/metadata'
 units='as supplied; see data-dictionary.md'
 for sm in source_meta.get('public',[]):
  if sm['file']==p.name:
   kind='official_public_snapshot'; url=sm.get('original_url',url); period='2022-2024' if p.name.endswith('.json') else 'daily ECB reference rates; includes 2025'; units='population: persons' if p.name=='population.json' else 'GDP per capita: current US dollars' if p.name=='gdp-per-capita.json' else 'local currency units per EUR' if p.name.startswith('ecb-history') else units
 if p.name=='ecb-history.csv':
  zmeta=next(x for x in source_meta.get('public',[]) if x['file']=='ecb-history.zip')
  kind='official_public_snapshot'; url=zmeta['original_url']; period='daily ECB reference rates; includes 2025; lossless extraction of ecb-history.zip'; units='local currency units per EUR; full ECB table'
  retrieved=zmeta['retrieved_utc']
 else:
  retrieved=next((x.get('retrieved_utc') for x in source_meta.get('public',[]) if x['file']==p.name),None) or datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()
 register.append({'file':p.name,'source_url':url,'retrieved_utc':retrieved,'sha256':sha(p),'bytes':p.stat().st_size,'units':units,'period':period,'status':kind})
dump(register,ROOT/'sources'/'source-register.json')

def create_workbook():
 wb=Workbook(); wb.remove(wb.active)
 navy='17324D'; blue='246B8E'; teal='2A9D8F'; pale='E9F1F5'; white='FFFFFF'; gray='566573'
 def sheet(name,headers,rows,widths=None):
  ws=wb.create_sheet(name); ws.append(headers)
  for row in rows: ws.append(row)
  ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
  for cell in ws[1]: cell.fill=PatternFill('solid',fgColor=navy); cell.font=Font(color=white,bold=True); cell.alignment=Alignment(wrap_text=True,vertical='center')
  ws.row_dimensions[1].height=34
  for i,w in enumerate(widths or [],1): ws.column_dimensions[get_column_letter(i)].width=w
  for row in ws.iter_rows(min_row=2):
   for cell in row: cell.alignment=Alignment(vertical='top')
  return ws
 notes=[['Purpose','Decision-support workbook for the Meridian Parts synthetic case.'],['Client inputs','Entirely synthetic. No live client account or interviews accessed.'],['Public archive','World Bank responses and ECB daily reference rates preserved under sources/raw with original URLs, retrieval vintage and hashes.'],['Sales period','2025 shipped dates; returns with received_at through 2026-01-31 inclusive.'],['Revision logic','Highest numeric revision for each order_id across two exports plus corrections; returns highest revision by return_id.'],['FX','Monthly arithmetic mean of available ECB published business days, local units per EUR; used original shipment month for sale and refund; EUR=1.'],['Rounding','Each order gross sales, refunds, gross COGS, recovered COGS and fulfillment rounded half-up to cents before aggregation.'],['Contribution','Net sales less net COGS and nonrefundable fulfillment. Cash timing and FX settlement are not modeled.'],['Scenarios','Use scenario-policy.md; hub annual contribution excludes year-zero capex. Payback is simple K / positive annual increment.'],['Recommendation basis','Highest minimum across client-defined low/base/high/stress cases; strongest alternative compared by base case. No probabilities were supplied.'],['Limits','No hub causality, discounting, ramp-up, synergies, tax, lease breakage, working capital, service-level data or probability estimates.']]
 sheet('Read me',['Topic','Notes'],notes,[24,112])
 sheet('Monthly',['country','month']+FIELDS[1:],[[r['country'],r['month']]+[r[x] for x in FIELDS[1:]] for r in monthly],[12,12,16,14,14,17,14,16,17,16,15,12,12])
 sheet('Country totals',FIELDS,[[r[f] for f in FIELDS] for r in country_rows],[12,15,14,16,14,16,14,17,18,14,12])
 sheet('FX monthly',['currency','month','local_per_eur','published_business_days'],[[x['currency'],x['month'],x['local_per_eur'],x['published_business_days']] for x in fx_rows],[14,13,20,25])
 sheet('Market context',['country','year','population_persons','gdp_per_capita_current_usd'],[[r['country'],r['year'],r['population'],r['gdp_per_capita_usd']] for r in market],[14,12,25,34])
 scenrows=[]
 for x in scenarios:
  scenrows.append([x['country'],x['scenario'],x['incremental_contribution_eur'],x['annual_fixed_eur'],x['capex_eur'],x['fte'],x['payback_years'],x['volume_uplift'],x.get('refund_shock_eur',0),x.get('fx_shock_eur',0)])
 ws=sheet('Hub scenarios',['country','scenario','incremental contribution EUR / yr','recurring fixed EUR / yr','year-zero capex EUR','FTE','simple payback years','volume uplift','refund shock EUR','FX shock EUR'],scenrows,[13,13,30,25,22,10,23,16,17,17])
 # Scenario chart: base/stress by country.
 chart=BarChart(); chart.type='bar'; chart.style=10; chart.title='Annual incremental contribution by hub'; chart.y_axis.title='Country / scenario'; chart.x_axis.title='EUR per year'; chart.height=8; chart.width=15
 # chart helper grid
 cw=wb.create_sheet('Chart data'); cw.append(['country','base EUR/year','stress EUR/year'])
 for c in COUNTRIES:
  cw.append([c,next(x['incremental_contribution_eur'] for x in scenarios if x['country']==c and x['scenario']=='base'),next(x['incremental_contribution_eur'] for x in scenarios if x['country']==c and x['scenario']=='stress')])
 chart.add_data(Reference(cw,min_col=2,max_col=3,min_row=1,max_row=7),titles_from_data=True); chart.set_categories(Reference(cw,min_col=1,min_row=2,max_row=7)); chart.height=8; chart.width=15
 ws.add_chart(chart,'L2'); cw.sheet_state='hidden'
 ranked_alternatives=sorted(alternatives,key=lambda x:(x['feasible'],x['rank_maximin'] is not None,x['rank_maximin'] or 999))
 sheet('Alternatives',['maximin rank','base rank','label','countries','capex EUR','FTE','annual fixed EUR','low EUR/yr','base EUR/yr','high EUR/yr','stress EUR/yr','minimum across cases','feasible'],[[x['rank_maximin'],x['rank_base'],x.get('label','Defer'),', '.join(x['countries']),x['capex_eur'],x['fte'],x['annual_fixed_eur'],x['low'],x['base'],x['high'],x['stress'],x['minimum_scenario_eur'],x['feasible']] for x in ranked_alternatives],[15,13,24,18,16,10,21,16,16,16,17,23,13])
 anomalies=[['Issue','Detected','Handling'],['Duplicate/revisioned order IDs',f"{quality['orders']['duplicate_rows_removed']} exact duplicate rows removed; {quality['orders']['revisioned_ids']} IDs have distinct revisions; {quality['orders']['same_revision_conflicting_groups']} conflicting revision groups",'Deduplicate identical rows and keep highest numeric revision; corrections replace full row.'],['Excluded selected orders',f"{quality['orders']['excluded_status_or_test_or_date']} total: {quality['orders']['exclusion_counts_after_revision']}",'Exclude non-shipped, test, or shipment outside 2025; valid zero-price shipments are retained.'],['Valid zero-price orders',quality['sales_checks']['valid_zero_price_shipments'],'Included as shipped orders and units; revenue remains zero.'],['Returns',f"{quality['returns']['exact_duplicate_rows_removed']} exact duplicate rows; {quality['returns']['revisioned_ids']} revised IDs; {quality['returns']['quarantined_orphan_or_ineligible_returns']} quarantined; {quality['returns']['after_cutoff_returns']} after cutoff",'Keep highest revision per return ID; inclusive cutoff; quarantine unlinked/ineligible returns.'],['Return consistency',f"Units exceed shipped orders: {quality['returns']['return_units_exceeding_shipped_orders']}; restock > returned rows: {quality['returns']['rows_restocking_more_than_returned']}; refunds > gross orders: {quality['returns']['orders_with_refunds_above_gross_local_sales']}",'All returns additive; restocked quantity alone recovers product cost.'],['Missing FX / SKU cost',f"{len(missing_fx)} / {len(missing_cost)} orders",'Missing inputs would be listed; none expected in complete result.'],['World Bank nulls',f"Population {quality['missing']['missing_world_bank_population']}; GDP {quality['missing']['missing_world_bank_gdp']}",'Preserve nulls; do not impute.'],['Cash vs contribution','Accounting distinction','Gross booked shipment sales less credit refunds equals net sales; contribution additionally deducts net COGS and fulfillment. Cash timing/settlement is not modeled.']]
 sheet('Quality & sources',['Check','Result','Treatment'],anomalies,[30,54,100])
 # Numeric formats and table polish
 for ws in wb.worksheets:
  for row in ws.iter_rows(min_row=2):
   for c in row:
    if isinstance(c.value,float): c.number_format='#,##0.00;[Red](#,##0.00);-'
  ws.sheet_view.showGridLines=False
 wb.calculation.fullCalcOnLoad=True; wb.calculation.forceFullCalc=True
 wb.save(OUT/'meridian_analysis.xlsx')

create_workbook()

def euro(x): return '—' if x is None else f'€{x:,.0f}'
def pct(x): return '—' if x is None else f'{x:.1%}'
def build_docx():
 d=Document(); sec=d.sections[0]; sec.top_margin=Inches(.65); sec.bottom_margin=Inches(.62); sec.left_margin=Inches(.72); sec.right_margin=Inches(.72)
 styles=d.styles; styles['Normal'].font.name='Aptos'; styles['Normal'].font.size=Pt(9); styles['Normal'].font.color.rgb=RGBColor(39,55,67)
 for h,size,color in [('Title',31,'17324D'),('Heading 1',20,'17324D'),('Heading 2',13,'246B8E'),('Heading 3',10,'17324D')]:
  st=styles[h]; st.font.name='Aptos Display'; st.font.size=Pt(size); st.font.bold=True; st.font.color.rgb=RGBColor.from_string(color)
 def p(text='',style=None): return d.add_paragraph(text,style)
 def table(headers,rows,widths=None):
  t=d.add_table(rows=1,cols=len(headers)); t.style='Light Shading Accent 1'
  for i,x in enumerate(headers): t.rows[0].cells[i].text=str(x)
  for row in rows:
   cells=t.add_row().cells
   for i,x in enumerate(row): cells[i].text=str(x)
  for row in t.rows:
   for cell in row.cells:
    for para in cell.paragraphs:
     para.paragraph_format.space_after=Pt(1)
     for run in para.runs: run.font.size=Pt(8)
  return t
 p('MERIDIAN PARTS  /  BOARD DECISION NOTE','Subtitle'); p('European service-hub expansion','Title'); p('Decision brief • 27 September 2026 • Analysis of 2025 shipments and returns through 31 January 2026','Subtitle')
 b=next(x for x in alternatives if x is best); ss=next((x for x in alternatives if x['countries']==['NLD','POL']),None)
 p(f"Recommendation: stage an envelope for {b['label']}, pilot Spain first with country-specific reversible tests in the Netherlands, and release site capex only after the 90-day gates. This pair has the highest minimum annual increment across the supplied low/base/high/stress cases while staying under both caps: minimum {euro(b['minimum_scenario_eur'])}, base {euro(b['base'])}, stress {euro(b['stress'])}, on {euro(b['capex_eur'])} capex and {b['fte']} FTE. These are scenario calculations, not a causal hub forecast.",'Heading 1')
 p('Board choice. With no board probability weights, the recommendation uses the feasible combination with the highest minimum across the specified low/base/high/stress cases. This favors resilience across the published cases and is an explicit judgment, not a statistical result. CZE + ESP is the strongest alternative by base contribution and adds EUR31,168/year in the base case, but its stress increment is EUR75,450/year lower. Defer remains available. The hard caps—EUR450,000 capex, seven FTE and at most two hubs—are met; additive economics assume no pair synergy.')
 # executive table
 top=feasible[:6]
 table(['Alternative','Capex','FTE','Low / year','Base / year','High / year','Stress / year'],[[x.get('label','Defer'),euro(x['capex_eur']),str(x['fte']),euro(x['low']),euro(x['base']),euro(x['high']),euro(x['stress'])] for x in top])
 d.add_page_break(); p('1  /  What the operating record says','Heading 1')
 p('The 2025 shipment ledger is a strong baseline for where Meridian already sells and earns contribution, but it does not measure service-hub causality. The country values below use selected order revisions, eligible shipped orders, returned credits known by the cutoff, and month-matched ECB translation for PLN/CZK. The synthetic client data report actual booked shipment prices/cost fields; the option uplift and savings remain assumptions.')
 table(['Country','Orders','Units','Net sales','Contribution','Margin','Returned units'],[[CN[x['country']],f"{x['shipped_orders']:,}",f"{x['shipped_units']:,}",euro(x['net_sales_eur']),euro(x['contribution_eur']),pct(x['margin']),f"{x['returned_units']:,}"] for x in country_rows])
 p('Diagnosis. The hub thesis has two modeled levers: added volume at each market’s existing contribution economics and a per-unit fulfillment saving, less recurring fixed cost. Current sales by themselves establish only the baseline; neither the historical mix nor country size proves incremental demand from faster/local service. A hub can improve local service and may change conversion, but no service-level, lost-sales, lead-time, customer-interview or controlled rollout data were supplied.')
 p('Booked revenue, cash and contribution. Gross sales are order price times shipped quantity less discounts, translated and rounded per order; refunds reduce net sales. Net sales approximate booked revenue under the supplied credit ledger, not cash received: timing, settlement FX, payment fees and working capital are unavailable. Contribution further deducts net COGS after recoverable restocked units and nonrefundable fulfillment. It is not EBITDA or hub profit; annual option costs are then deducted separately in scenarios.')
 d.add_page_break(); p('2  /  Evidence base and quality controls','Heading 1')
 p('Client transaction, cost, and option files are synthetic (seed documented by the source room). They were collected from the frozen local source room; no live client account or customer was accessed. Population/GDP and ECB exchange rates are official public snapshots preserved in the room with original URLs and a 27 September 2026 collection vintage; this may include subsequent revisions to historical observations. Provenance, hashes and local inputs are in sources/source-register.json.')
 q=quality['orders']; rr=quality['returns']
 p(f"Across both extract pages and correction file, {q['raw_rows']:,} order rows represent {q['unique_order_ids']:,} order IDs. {q['revisioned_ids']} IDs have revision history and {q['duplicate_rows_removed']} exact duplicate rows were removed. The highest numeric revision was selected for each ID, then only shipped, non-test rows with shipment dates in 2025 entered the base ({q['eligible_2025_shipped_orders']:,} orders); {q['excluded_status_or_test_or_date']} selected rows were excluded by status, test flag or date. Valid zero-price shipments remain in the count. January 2026 orders are excluded.")
 p(f"Returns: {rr['raw_rows']} raw rows reduce to {rr['unique_return_ids']} return IDs after selecting highest revision. Returns received through 31 January 2026 were included only when linked to an eligible selected sale. {rr['quarantined_orphan_or_ineligible_returns']} orphan/ineligible returns were quarantined; {rr['after_cutoff_returns']} later-known returns were excluded. Distinct valid return IDs are additive. Returned units are physical return quantity; only restocked quantity recovers COGS.")
 p('For non-euro sales and refunds, the exchange rate is the arithmetic mean of published 2025 ECB business-day references in the original sale month, quoted local currency units per EUR. This quote is not inverted and is not transaction FX. Individual order monetary components are rounded half-up to cents before sums. EUR is 1. See the workbook FX monthly tab for all 24 PLN/CZK values and observations per mean.')
 p('Reconciliation: 72 country-month rows are generated, including zero-activity cells. Country totals equal the sum of their 12 monthly rows for orders, units, money and returned units; margins are recomputed on annual totals, not summed. Missing data and anomalies are recorded in metrics.json and the workbook Quality & sources tab. World Bank nulls are retained without imputation.')
 d.add_page_break(); p('3  /  Market context','Heading 1')
 p('The archived World Bank response reports population in persons and GDP per capita in current US dollars for 2022–2024. The 2022–2024 population change and 2024 income level below provide context for geographic scale and purchasing-power environment only. They do not establish Meridian product demand, fit, or addressable service pain.')
 popchg={}
 for c in COUNTRIES:
  p22=pop.get((c,2022)); p24=pop.get((c,2024)); popchg[c]=None if not p22 or not p24 else p24/p22-1
 table(['Country','Population 2022','Population 2024','Change 2022–24','GDP/capita 2024, current USD'],[[CN[c],f"{pop.get((c,2022)):,}" if pop.get((c,2022)) is not None else 'missing',f"{pop.get((c,2024)):,}" if pop.get((c,2024)) is not None else 'missing',pct(popchg[c]),f"${gdp.get((c,2024)):,.0f}" if gdp.get((c,2024)) is not None else 'missing'] for c in COUNTRIES])
 p('Source limits. Current-US-dollar GDP per capita is affected by prices and exchange rates; it is neither PPP-adjusted nor a real growth series. No market-size estimate, product category demand estimate, competitors, labor market or localized regulatory/real-estate evidence was added. Public evidence is limited to the archived official population, GDP/capita and ECB snapshots, as requested.')
 d.add_page_break(); p('4  /  Option economics and decision','Heading 1')
 p('For each country, annual incremental contribution is C×u + U×(1+u)×s − F, where C is 2025 contribution, U shipped units, u is an assumed volume uplift, s is assumed saving per unit, and F is recurring annual fixed cost. Capex K is kept separate; simple payback is K divided by positive annual incremental contribution. Stress applies the policy’s 3% gross-sales refund shock and 10% net-sales depreciation shock for PLN/CZK markets, then compares stressed 1.25× contribution with the unchanged base contribution and adds uplifted unit savings less F. Stress is a joint sensitivity, not a likely outcome.')
 strongest=next(x for x in feasible if x['countries']!=best['countries'])
 option_rows=[best,strongest]+[a for a in bestpairs if a['countries'] not in (best['countries'],strongest['countries'])][:2]
 table(['Option','Capex year 0','Fixed / yr','FTE','Low / yr','Base / yr','High / yr','Stress / yr','Base payback'],[[x['label'],euro(x['capex_eur']),euro(x['annual_fixed_eur']),str(x['fte']),euro(x['low']),euro(x['base']),euro(x['high']),euro(x['stress']),f"{x['capex_eur']/x['base']:.1f}y" if x['base']>0 else '—'] for x in option_rows])
 p(f"Strongest feasible alternative excluding the recommendation, ranked by base annual increment: {strongest['label']} at {euro(strongest['base'])}/year, {euro(strongest['capex_eur'])} capex and {strongest['fte']} FTE. It gives up {euro(best['base']-strongest['base'])}/year versus the selected combination under the same additive base arithmetic. In the stress case it produces {euro(strongest['stress'])}/year versus {euro(best['stress'])}/year for the recommendation; the comparison is sensitive to the stress assumptions and should be treated as a sequencing choice, not a proven ranking of real-world hub outcomes.")
 p(f"Decision-changing assumption. The recommendation rests on assumed volume uplifts of 10%–40% and recurring per-unit fulfillment savings. For each option, the break-even volume uplift solves u=(F−U×s)/(C+U×s) when denominator is positive. Use the pilot to verify actual avoidable fulfillment savings, incremental volume, repeat purchase effects and annual fixed costs before releasing full capex. If measured savings/volume fall below a selected option’s break-even, defer or compare a lower-cost pair.")
 p('Hard constraints are the board-set budget, staffing and maximum number of hubs. The scenario model is additive with no network synergy. Maximizing the minimum supplied-case increment is a conservative preference chosen for this recommendation, not a board-provided weight or probability. A base-only decision would choose CZE + ESP: EUR31,168 more annual base contribution, but EUR75,450 less in the defined stress case.')
 d.add_page_break(); p('5  /  90-day execution and gates','Heading 1')
 table(['Timing / owner','Work and dependency','Gate / evidence'],[
  ['Days 0–15 • COO + Finance','Authorize discovery and pilot design; validate option scope, actual avoidable freight/handling baseline, fixed-cost quote, FX treatment, service geography and KPI definitions. Finance reconciles shipment/return baseline.','Gate 1: approve only if auditable baseline and target cohort exist; set cash capex release schedule.'],
  ['Days 16–35 • Operations + Data','Select service zone and eligible SKUs; map lead-time promise, inventory/transfer design, labor plan, landlord/3PL quotes, returns/restock process, country tax/legal review. Establish holdout or matched comparison.','Gate 2: signed costed operating design, service SLA, owner, data completeness ≥98%, and capex within budget.'],
  ['Days 36–65 • Country lead + Supply Chain','Run reversible pilot using temporary space/3PL or reserved stock before lease/build; train staff; monitor order cohorts, promise-date performance, fill rate, incremental volume and unit handling cost.','Gate 3: no scale decision until ≥4 weeks usable pilot data; stop for safety/compliance breach, stock accuracy <98%, or negative contribution trend.'],
  ['Days 66–90 • CFO + COO + Board sponsor','Compare pilot to pre-registered baseline/holdout; update low/base/high and return/FX stress; validate capex, hiring and recurring cost quotes; document strongest alternative and defer case.','Gate 4: release full site capex only if annualized incremental contribution after recurring fixed cost is positive in base, capex/FTE caps hold, and downside is accepted. Otherwise defer/reconfigure.']])
 p('KPI plan (weekly pilot; monthly board view): incremental shipped orders and units against matched/control baseline; net sales and return rate by sale cohort; contribution after product cost and fulfillment; avoidable fulfillment EUR/unit; median and 90th-percentile order-to-delivery days; on-time-in-full; fill rate; stock accuracy; restocked share and return cycle time; annualized recurring hub cost; capex committed versus approved; staffed FTE. Report numerator, denominator, comparison period and confidence/coverage. Do not label seasonal or mix differences as hub lift without a credible comparison design.')
 p('Key risks and mitigations. Demand uplift may not materialize: use matched holdout and reversible pilot. Claimed unit savings may not be avoidable: validate invoice-level cost stack. Currency translation may differ from actual settlements: stress PLN/CZK and monitor booked-to-cash FX separately. Inventory fragmentation can lower availability or inflate working capital: pilot limited SKU set and enforce stock accuracy. Return behavior may erode margin: monitor cohort refunds and restocking, and gate scale on contribution after returns. Fixed-cost, labor, lease and legal assumptions are synthetic or absent: obtain local quotes and counsel before commitment.')
 d.add_page_break(); p('Appendix  /  Sources, reproducibility and limits','Heading 1')
 p('Evidence-linked source set (all original files saved in sources/raw):')
 for line in ['Synthetic order pages and corrections, return file, unit costs, hub options and scenario policy: source-room files; source register records local hash, file size and status.','ECB daily reference rates: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip (frozen public snapshot; retrieval timestamp in source-room source-register.json).','World Bank population: https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&format=json&per_page=1000','World Bank GDP/capita: https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&format=json&per_page=1000']:
  p(line, 'List Bullet')
 p('Rebuild from the project directory with: python3 analysis/build.py. Inputs are saved, so no network access is needed after collection. The script produces deliverables/metrics.json, deliverables/meridian_analysis.xlsx, deliverables/meridian_board_brief.docx and deliverables/meridian_board_deck.pptx, plus sources/source-register.json. A separate validation script checks reconciliation, deterministic JSON keys, decision constraints, and workbook integrity.')
 p('Limitations: inputs are synthetic; archived World Bank/ECB snapshots may include historical revisions after 2025. Reference FX is an analytical translation convention. 2025 is one year and has no seasonal adjustment; no causal lift data or confidence intervals exist. Scenario payback is undiscounted, assumes steady annual run rate and additive/no-synergy pair economics, and omits tax, depreciation, ramp, working capital, lease exit, labor-market dynamics and discounting. The recommendation is conditional and not statistically proven.')
 d.save(OUT/'meridian_board_brief.docx')
build_docx()

def build_pptx():
 prs=Presentation(); prs.slide_width=PInches(13.333); prs.slide_height=PInches(7.5)
 navy=PRGB(23,50,77); blue=PRGB(36,107,142); teal=PRGB(42,157,143); pale=PRGB(238,244,247); white=PRGB(255,255,255); ink=PRGB(39,55,67); gold=PRGB(235,179,76)
 def slide(title,kicker=None):
  s=prs.slides.add_slide(prs.slide_layouts[6]); bg=s.background.fill; bg.solid(); bg.fore_color.rgb=white
  sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,0,0,prs.slide_width,PInches(.13)); sh.fill.solid(); sh.fill.fore_color.rgb=teal; sh.line.fill.background()
  if kicker:
   tb=s.shapes.add_textbox(PInches(.6),PInches(.34),PInches(12),PInches(.3)); tf=tb.text_frame; tf.text=kicker.upper(); tf.paragraphs[0].font.size=PPt(10); tf.paragraphs[0].font.bold=True; tf.paragraphs[0].font.color.rgb=blue
  tb=s.shapes.add_textbox(PInches(.6),PInches(.7),PInches(12.1),PInches(.65)); tf=tb.text_frame; tf.text=title; tf.paragraphs[0].font.size=PPt(27); tf.paragraphs[0].font.bold=True; tf.paragraphs[0].font.color.rgb=navy
  return s
 def textbox(s,x,y,w,h,text,size=16,color=ink,bold=False):
  tb=s.shapes.add_textbox(PInches(x),PInches(y),PInches(w),PInches(h)); tf=tb.text_frame; tf.word_wrap=True; tf.text=text
  for para in tf.paragraphs: para.font.size=PPt(size); para.font.color.rgb=color; para.font.bold=bold
  return tb
 def footer(s,n): textbox(s,.6,7.13,12,.2,f'MERIDIAN PARTS  •  Synthetic case  •  Source vintage 27 Sep 2026                                           {n}',9,blue)
 s=slide('Stage Netherlands + Spain behind a 90-day pilot','Board decision • 27 September 2026')
 textbox(s,.8,1.65,7.1,1.55,f"{best['label']} has the strongest floor across the defined cases",27,navy,True)
 textbox(s,.8,3.4,6.8,1.1,f"Base {euro(best['base'])}/yr  |  Stress {euro(best['stress'])}/yr\nCapex {euro(best['capex_eur'])}  |  {best['fte']} FTE",19,blue,True)
 textbox(s,8.4,1.75,4.1,3.65,'Board action\n\nApprove a 90-day reversible pilot and staged capex envelope. Release full investment only after measured savings and incremental volume clear the operating gates. Defer remains a valid outcome.',18,ink)
 footer(s,1)
 s=slide('2025 contribution describes the baseline, not hub causality','Operating diagnosis')
 textbox(s,.8,1.4,11.8,.65,'Sales and margin vary materially by market; option economics depend on local volume response and avoidable fulfillment savings.',17,ink)
 # table drawn manually
 heads=['Country','Orders','Units','Net sales','Contribution','Margin']
 x0=.8;y0=2.35; widths=[2.0,1.35,1.35,2.0,2.15,1.3]
 for j,h in enumerate(heads): sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,PInches(x0+sum(widths[:j])),PInches(y0),PInches(widths[j]),PInches(.38)); sh.fill.solid();sh.fill.fore_color.rgb=navy;sh.line.fill.background();sh.text_frame.text=h;sh.text_frame.paragraphs[0].font.size=PPt(12);sh.text_frame.paragraphs[0].font.bold=True;sh.text_frame.paragraphs[0].font.color.rgb=white
 for i,r in enumerate(country_rows):
  vals=[CN[r['country']],f"{r['shipped_orders']:,}",f"{r['shipped_units']:,}",euro(r['net_sales_eur']),euro(r['contribution_eur']),pct(r['margin'])]; y=y0+.4+i*.5
  for j,v in enumerate(vals):
   sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,PInches(x0+sum(widths[:j])),PInches(y),PInches(widths[j]),PInches(.47)); sh.fill.solid();sh.fill.fore_color.rgb=pale if i%2==0 else white;sh.line.color.rgb=PRGB(220,229,234);sh.text_frame.text=v;sh.text_frame.margin_left=PInches(.06);sh.text_frame.paragraphs[0].font.size=PPt(13);sh.text_frame.paragraphs[0].font.color.rgb=ink
 textbox(s,.8,6.05,11.7,.65,'No lead-time, lost-sales, customer interview, or controlled service-hub evidence was supplied. The 2025 shipped mix is not proof of incremental demand.',14,blue)
 footer(s,2)
 s=slide('The strongest feasible alternatives trade modeled return for resilience','Scenario comparison')
 comps=[best]+[a for a in feasible if len(a['countries'])==2 and a['countries']!=best['countries']][:3]
 textbox(s,.8,1.35,11.8,.45,'Annual incremental contribution after recurring fixed cost; capex is separate year-zero investment.',15,ink)
 # table
 heads=['Option','Capex yr 0','Fixed / yr','FTE','Base / yr','Stress / yr','Base payback']
 widths=[2.8,1.5,1.5,.8,1.55,1.55,1.55]; y0=2.05
 for j,h in enumerate(heads):
  sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,PInches(.8+sum(widths[:j])),PInches(y0),PInches(widths[j]),PInches(.48));sh.fill.solid();sh.fill.fore_color.rgb=navy;sh.line.fill.background();sh.text_frame.text=h;sh.text_frame.paragraphs[0].font.bold=True;sh.text_frame.paragraphs[0].font.size=PPt(12);sh.text_frame.paragraphs[0].font.color.rgb=white
 for i,a in enumerate(comps):
  pay=f"{a['capex_eur']/a['base']:.1f}y" if a['base']>0 else '—'; vals=[a.get('label','Defer'),euro(a['capex_eur']),euro(a['annual_fixed_eur']),str(a['fte']),euro(a['base']),euro(a['stress']),pay]
  for j,v in enumerate(vals):
   sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,PInches(.8+sum(widths[:j])),PInches(y0+.5+i*.65),PInches(widths[j]),PInches(.6));sh.fill.solid();sh.fill.fore_color.rgb=pale if i==0 else white;sh.line.color.rgb=PRGB(220,229,234);sh.text_frame.text=v;sh.text_frame.paragraphs[0].font.size=PPt(14);sh.text_frame.paragraphs[0].font.color.rgb=ink
 textbox(s,.8,5.55,11.8,.9,'Stress is the client policy’s joint refund/FX shock, not a probability forecast. Recommendation uses the highest minimum across low/base/high/stress; the leading base-only alternative is CZE + ESP.',14,blue)
 footer(s,3)
 s=slide('Market context helps locate scale, not product demand','External evidence')
 textbox(s,.8,1.45,11.8,.55,'World Bank archived population and current-USD GDP/capita (2022–2024); official snapshot, vintage 27 Sep 2026.',15,ink)
 heads=['Country','Population change 22–24','GDP/capita 2024']; widths=[3.0,3.2,3.2]; y0=2.25
 for j,h in enumerate(heads):
  sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,PInches(.8+sum(widths[:j])),PInches(y0),PInches(widths[j]),PInches(.48));sh.fill.solid();sh.fill.fore_color.rgb=navy;sh.line.fill.background();sh.text_frame.text=h;sh.text_frame.paragraphs[0].font.color.rgb=white;sh.text_frame.paragraphs[0].font.bold=True;sh.text_frame.paragraphs[0].font.size=PPt(13)
 for i,c in enumerate(COUNTRIES):
  a=pop.get((c,2022));b=pop.get((c,2024));change=None if not a or not b else b/a-1; vals=[CN[c],pct(change),f"${gdp.get((c,2024)):,.0f}" if gdp.get((c,2024)) is not None else 'missing']
  for j,v in enumerate(vals):
   sh=s.shapes.add_shape(MSO_SHAPE.RECTANGLE,PInches(.8+sum(widths[:j])),PInches(y0+.5+i*.48),PInches(widths[j]),PInches(.45));sh.fill.solid();sh.fill.fore_color.rgb=pale if i%2==0 else white;sh.line.color.rgb=PRGB(220,229,234);sh.text_frame.text=v;sh.text_frame.paragraphs[0].font.size=PPt(13);sh.text_frame.paragraphs[0].font.color.rgb=ink
 textbox(s,.8,5.9,11.6,.65,'Current USD is not PPP or constant-price income. Population and GDP/capita do not establish Meridian demand.',14,blue)
 footer(s,4)
 s=slide('Use staged gates to turn assumptions into evidence','90-day plan')
 stages=[('0–15','Finance + COO','Reconcile baseline, avoidable cost, pilot cohort and KPI definitions','Gate: auditable baseline'),('16–35','Ops + Data','Costed design, service zone, SKU scope, staffing, legal and inventory dependencies','Gate: budget and controls'),('36–65','Country + Supply Chain','Reversible 3PL/temporary pilot; compare against matched baseline','Gate: ≥4 weeks valid data'),('66–90','CFO + COO + Board','Update scenarios, stress and quotes; release, reconfigure or defer','Gate: positive base contribution')]
 for i,(days,owner,work,gate) in enumerate(stages):
  y=1.55+i*1.25; sh=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,PInches(.8),PInches(y),PInches(11.8),PInches(1.05));sh.fill.solid();sh.fill.fore_color.rgb=pale;sh.line.color.rgb=PRGB(213,227,233)
  textbox(s,1.05,y+.12,1.2,.35,days+' days',15,teal,True);textbox(s,2.35,y+.12,2.25,.35,owner,14,navy,True);textbox(s,4.55,y+.08,5.6,.68,work,13,ink);textbox(s,10.25,y+.13,2.05,.65,gate,12,blue,True)
 textbox(s,.85,6.75,11.7,.28,'Weekly: incremental orders/units, return rate, contribution after returns, avoidable EUR/unit, OTIF, P90 delivery, fill rate, stock accuracy, capex and FTE.',11,ink)
 footer(s,5)
 s=slide('Decision is conditional; reopen it on measured unit economics','Risks and switch conditions')
 textbox(s,.9,1.5,5.5,4.8,'What changes the choice\n\n• Verified volume response below modeled 10–40% uplift\n• Savings prove not avoidable or fixed costs exceed quotes\n• Return shock reduces net contribution\n• Pilot fails delivery, fill-rate or stock-accuracy gates\n• Actual capex/FTE exceed board limits',17,ink)
 textbox(s,6.8,1.5,5.3,4.8,'Risk controls\n\n• Matched pilot/holdout before causal lift claims\n• Validate savings against actual invoices\n• Separate booked revenue, cash settlement FX and contribution\n• Limit initial SKUs; monitor restocked share and inventory accuracy\n• Defer or reconfigure if downside is not acceptable',17,ink)
 footer(s,6)
 s=slide('Appendix: model boundaries and reproducibility','Sources and limitations')
 textbox(s,.8,1.4,11.8,5.3,'Synthetic inputs: two order extracts, revisions/corrections, returns, unit costs, hub options and policy from the frozen source room.\n\nPublic inputs: archived World Bank population and GDP per capita; ECB daily reference rates, all with original URLs, timestamps and hashes in sources/source-register.json.\n\nReproduce: python3 analysis/build.py. Workbook contains 72 monthly rows, six country totals, 24 PLN/CZK monthly FX means, market context, all hub scenarios and all feasible alternatives.\n\nLimitations: one synthetic baseline year; monthly ECB reference translation is not transaction FX; no causal hub results, probability distributions, ramp, discounting, synergy, tax, working capital or site/legal quotes. Historical public series may reflect later revisions.',15,ink)
 footer(s,7)
 prs.save(OUT/'meridian_board_deck.pptx')
build_pptx()

# Embedded source rows in JSON are useful for reproducibility and reviewer audit.
metrics['source_files']=register
dump(metrics,OUT/'metrics.json')
print('Built deliverables')
print('selected',best)
print('country totals',[(x['country'],x['shipped_orders'],x['shipped_units'],x['net_sales_eur'],x['contribution_eur']) for x in country_rows])
print('quality',json.dumps(quality,ensure_ascii=False))
