"""Reproduce Meridian's frozen-input model. Decimal arithmetic; no network required."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP, getcontext
from collections import defaultdict, Counter
from itertools import combinations
import csv, json, hashlib, zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'evidence/raw'
OUT = ROOT / 'deliverables'
DETAIL = OUT / 'data'
DETAIL.mkdir(parents=True, exist_ok=True)
getcontext().prec = 40
D = Decimal
ZERO = D(0)
COUNTRIES = ['DEU', 'FRA', 'NLD', 'POL', 'CZE', 'ESP']
MONTHS = [f'2025-{m:02}' for m in range(1, 13)]
MONEY = ['gross_sales_eur', 'refunds_eur', 'net_sales_eur', 'net_cogs_eur', 'fulfillment_eur', 'contribution_eur']
ADDITIVE = ['shipped_orders', 'shipped_units'] + MONEY + ['returned_units']
checks = []

def check(name, condition, detail=''):
    checks.append({'check': name, 'passed': bool(condition), 'detail': detail})
    if not condition:
        raise AssertionError(f'{name}: {detail}')

def money(x):
    return D(x).quantize(D('.01'), rounding=ROUND_HALF_UP)

def json_default(x):
    if isinstance(x, Decimal):
        return float(x)
    raise TypeError(type(x))

def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=json_default, allow_nan=False) + '\n')

def write_csv(name, records):
    if not records:
        return
    with (DETAIL / name).open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

def read_csv(name):
    with (RAW / name).open(newline='') as f:
        return list(csv.DictReader(f))

# Hash checks distinguish source-room archive vintage from our collection time.
manifest = json.loads((ROOT / 'evidence/collection_manifest.json').read_text())
archive = json.loads((RAW / 'source-register.json').read_text())
pub = {r['file']: r for r in archive['public']}
unit_map={
    'orders-part1.csv':'quantity: physical units; price/discount: original local currency; fulfillment: EUR/order; revision: integer',
    'orders-part2.csv':'quantity: physical units; price/discount: original local currency; fulfillment: EUR/order; revision: integer',
    'order-corrections.csv':'replacement whole orders; quantities: units; price/discount: local currency; fulfillment: EUR/order',
    'returns.csv':'quantity/restocked_quantity: physical units; refund_local: original order currency (unknown for orphan); revision: integer',
    'unit-costs.csv':'EUR per physical unit, effective-dated',
    'hub-options.csv':'capex EUR at year zero; annual fixed EUR/year; savings EUR/unit; staffing FTE',
    'scenario-policy.md':'volume/refund/FX fractions; capex EUR; fixed EUR/year; staff FTE; payback years',
    'data-dictionary.md':'definitions for physical units, order IDs, revisions, currencies and EUR accounting',
    'source-register.json':'provenance metadata; timestamps UTC; file bytes and SHA-256 hashes',
    'index.html':'not applicable: source-room file index'}
period_map={
    'orders-part1.csv':'2025 shipment cohort; cancelled/test records also present',
    'orders-part2.csv':'2025 shipment cohort plus one 2026-01 shipment; test records present',
    'order-corrections.csv':'revisions to 2025 orders; revision timestamps not supplied',
    'returns.csv':'returns for 2025 cohort, including 2026-01-31 and excluded 2026-02-01 records',
    'unit-costs.csv':'effective 2025-01-01 and 2025-07-01',
    'hub-options.csv':'forward annual steady-state planning; no launch year specified',
    'scenario-policy.md':'2025 baseline; forward annual steady-state planning',
    'data-dictionary.md':'2025 shipments; returns cutoff 2026-01-31 inclusive',
    'source-register.json':'archive retrieved 2026-09-27 UTC',
    'index.html':'frozen room collected at analyst timestamp'}
ecb_dates=[r['Date'] for r in read_csv('ecb-history.csv')]
register = []
for i, r in enumerate(manifest, 1):
    check('Collected file integrity: ' + r['file'], hashlib.sha256((RAW/r['file']).read_bytes()).hexdigest() == r['sha256'])
    a = pub.get(r['file'], {})
    if a:
        check('Archive hash: ' + r['file'], a['sha256'] == r['sha256'])
    parent = pub.get(a.get('derived_from'), {})
    wb = r['file'] in ['population.json', 'gdp-per-capita.json']
    register.append(dict(source_id=f'S{i:02}', **r,
        original_url=a.get('original_url', parent.get('original_url', r['collection_url'])),
        archive_retrieved_utc=a.get('retrieved_utc', parent.get('retrieved_utc')),
        revision_vintage=json.loads((RAW/r['file']).read_text())[0]['lastupdated'] if wb else ('archive retrieval vintage' if a else 'not supplied'),
        status='public official archive' if a else ('provenance metadata' if r['file'] in ['source-register.json', 'index.html'] else 'synthetic client input'),
        units=('persons' if r['file']=='population.json' else 'current US$ per person' if r['file']=='gdp-per-capita.json' else 'local currency units per EUR' if r['file'].startswith('ecb') else unit_map[r['file']]),
        period='2022–2024' if wb else f'{min(ecb_dates)} through {max(ecb_dates)} archived; 2025 selected for core calculations' if r['file'].startswith('ecb') else period_map[r['file']],
        transformation=a.get('transformation', 'none; original downloaded bytes')))
dump(ROOT/'evidence/source_register.json', register)
with (ROOT/'evidence/source_register.csv').open('w', newline='') as f:
    w=csv.DictWriter(f, fieldnames=list(register[0])); w.writeheader(); w.writerows(register)
with zipfile.ZipFile(RAW/'ecb-history.zip') as z:
    names = [n for n in z.namelist() if n.lower().endswith('.csv')]
    check('ECB ZIP extraction matches saved CSV', len(names)==1 and z.read(names[0])==(RAW/'ecb-history.csv').read_bytes())

def resolve(names, idcol):
    raw=[]
    for n in names:
        for line, r in enumerate(read_csv(n), 2):
            raw.append((r, n, line))
    groups=defaultdict(list)
    for r,n,l in raw:
        groups[r[idcol]].append((r,n,l))
    selected={}; audit=[]; exact=0; superseded=0
    for key, rows in groups.items():
        maxrev=max(int(r['revision']) for r,_,_ in rows)
        top=[r for r,_,_ in rows if int(r['revision'])==maxrev]
        check(f'No conflicting latest revision: {key}', all(r==top[0] for r in top))
        selected[key]=top[0]
        seen=set()
        for r,n,l in rows:
            sig=tuple(r.items())
            if sig in seen:
                disposition='identical_duplicate'; exact+=1
            elif int(r['revision'])<maxrev:
                disposition='superseded_revision'; superseded+=1
            else:
                disposition='selected'
            seen.add(sig)
            audit.append(dict(source_file=n, source_line=l, **r, resolution=disposition))
    check(f'{idcol} row reconciliation', len(raw)==len(selected)+exact+superseded)
    return selected,audit,dict(raw_rows=len(raw),unique_ids=len(selected),identical_duplicate_rows=exact,superseded_rows=superseded,
        revised_ids=sum(len({int(r['revision']) for r,_,_ in rows})>1 for rows in groups.values()))

orders, order_audit, oq = resolve(['orders-part1.csv','orders-part2.csv','order-corrections.csv'], 'order_id')
returns, return_audit, rq = resolve(['returns.csv'], 'return_id')
eligible={}; excluded=[]
def exclusion(r):
    if r['status']!='shipped': return 'not_shipped'
    if r['is_test']!='false': return 'test'
    if not r['shipped_at']: return 'missing_shipment_date'
    if not '2025-01-01' <= r['shipped_at'] <= '2025-12-31': return 'outside_2025'
    return 'included'
for k,r in orders.items():
    reason=exclusion(r)
    if reason=='included': eligible[k]=r
    else: excluded.append(dict(**r, exclusion=reason))
for r in order_audit:
    r['eligibility']=exclusion(orders[r['order_id']]) if r['resolution']=='selected' else 'not_applicable'
write_csv('order_resolution.csv', order_audit)
write_csv('excluded_orders.csv', excluded)

kept_returns=defaultdict(list); excluded_returns=[]
for rid,r in returns.items():
    if r['order_id'] not in orders: reason='orphan_order'
    elif r['received_at']>'2026-01-31': reason='after_cutoff'
    elif r['order_id'] not in eligible: reason='ineligible_order'
    else: reason='included'
    if reason=='included': kept_returns[r['order_id']].append(r)
    else: excluded_returns.append(dict(**r, exclusion=reason))
    for a in return_audit:
        if a['return_id']==rid and a['resolution']=='selected': a['eligibility']=reason
for a in return_audit: a.setdefault('eligibility','not_applicable')
write_csv('return_resolution.csv', return_audit)
write_csv('excluded_returns.csv', excluded_returns)

# Keep full-precision arithmetic means internally, with observation counts and date coverage.
fx_groups=defaultdict(list)
fx_daily=[]
for r in read_csv('ecb-history.csv'):
    if r['Date'].startswith('2025-'):
        for currency in ['PLN','CZK']:
            if r[currency].strip() not in ('','N/A'):
                rate=D(r[currency]); fx_groups[(currency,r['Date'][:7])].append((r['Date'],rate))
                fx_daily.append(dict(date=r['Date'],currency=currency,local_per_eur=rate))
fx=[]; rates={}
for currency in ['PLN','CZK']:
    for month in MONTHS:
        rows=sorted(fx_groups[(currency,month)])
        check(f'ECB observations: {currency} {month}', len(rows)>0 and len(rows)==len({d for d,_ in rows}))
        rate=sum((v for _,v in rows), ZERO)/len(rows)
        rates[(currency,month)]=rate
        fx.append(dict(currency=currency,month=month,local_per_eur=rate,observations=len(rows),first_date=rows[0][0],last_date=rows[-1][0]))
write_csv('fx_daily_2025.csv',sorted(fx_daily,key=lambda x:(x['currency'],x['date'])))
write_csv('fx_monthly.csv',fx)

costs=read_csv('unit-costs.csv')
ledger=[]; return_issues=[]
for oid,r in sorted(eligible.items()):
    check(f'Eligible order complete: {oid}', all(v!='' for v in r.values()))
    month=r['shipped_at'][:7]; currency=r['currency']
    check(f'Expected currency: {oid}', currency=={'POL':'PLN','CZE':'CZK'}.get(r['country'],'EUR'))
    candidates=[c for c in costs if c['sku']==r['sku'] and c['valid_from']<=r['shipped_at']]
    check(f'Effective unit cost: {oid}', bool(candidates))
    costrow=max(candidates,key=lambda c:c['valid_from']); cost=D(costrow['unit_cost_eur'])
    q=int(r['quantity']); rate=D(1) if currency=='EUR' else rates[currency,month]
    rr=kept_returns[oid]; ret=sum(int(t['quantity']) for t in rr); restock=sum(int(t['restocked_quantity']) for t in rr)
    check(f'Return/restock quantities: {oid}', 0<=restock<=ret<=q and all(0<=int(t['restocked_quantity'])<=int(t['quantity']) for t in rr))
    gross_local=q*D(r['unit_price_local'])-D(r['discount_local'])
    refund_local=sum((D(t['refund_local']) for t in rr), ZERO)
    gross=money(gross_local/rate); refund=money(refund_local/rate)
    gross_cogs=money(q*cost); recovered=money(restock*cost)
    net_cogs=gross_cogs-recovered; fulfill=money(r['fulfillment_eur']); net=gross-refund; contribution=net-net_cogs-fulfill
    ledger.append(dict(order_id=oid,revision=int(r['revision']),country=r['country'],month=month,shipped_at=r['shipped_at'],sku=r['sku'],currency=currency,
        shipped_orders=1,shipped_units=q,unit_price_local=D(r['unit_price_local']),discount_local=D(r['discount_local']),gross_local=gross_local,refund_local=refund_local,
        local_per_eur=rate,unit_cost_eur=cost,cost_valid_from=costrow['valid_from'],gross_sales_eur=gross,refunds_eur=refund,net_sales_eur=net,
        gross_cogs_eur=gross_cogs,recovered_cogs_eur=recovered,net_cogs_eur=net_cogs,fulfillment_eur=fulfill,contribution_eur=contribution,
        returned_units=ret,restocked_units=restock,return_ids=';'.join(t['return_id'] for t in rr),return_records=len(rr),margin=contribution/net if net else None))
write_csv('order_ledger.csv', ledger)

def aggregate(rows, **keys):
    a=dict(**keys)
    for f in ADDITIVE+['gross_cogs_eur','recovered_cogs_eur','restocked_units']:
        a[f]=sum((r[f] for r in rows), ZERO if f.endswith('_eur') else 0)
    a['margin']=a['contribution_eur']/a['net_sales_eur'] if a['net_sales_eur'] else None
    a['returned_unit_rate']=D(a['returned_units'])/a['shipped_units'] if a['shipped_units'] else None
    return a

monthly=[aggregate([r for r in ledger if r['country']==c and r['month']==m],country=c,month=m) for c in COUNTRIES for m in MONTHS]
countries=[aggregate([r for r in monthly if r['country']==c],country=c) for c in COUNTRIES]
total=aggregate(ledger,country='TOTAL')
for c in countries:
    direct=aggregate([r for r in ledger if r['country']==c['country']],country=c['country'])
    check('Monthly to annual: '+c['country'], c==direct)
for f in ADDITIVE:
    check('Group total: '+f,sum(r[f] for r in countries)==total[f])
for r in monthly+countries+[total]:
    check('Accounting bridge: '+r['country']+' '+r.get('month','annual'), r['gross_sales_eur']-r['refunds_eur']==r['net_sales_eur'] and r['net_sales_eur']-r['net_cogs_eur']-r['fulfillment_eur']==r['contribution_eur'])
write_csv('monthly.csv',monthly);write_csv('countries.csv',countries)

market_map=defaultdict(dict); wb_quality=[]
for filename,field in [('population.json','population'),('gdp-per-capita.json','gdp_per_capita_usd')]:
    metadata, observations=json.loads((RAW/filename).read_text(),parse_float=D)
    check('World Bank pagination: '+filename,metadata['pages']==1 and metadata['total']==len(observations)==18)
    for obs in observations:
        key=(obs['countryiso3code'],int(obs['date']))
        check('World Bank unique key: '+filename+str(key), field not in market_map[key])
        market_map[key][field]=obs['value']
        if obs['value'] is None: wb_quality.append(dict(country=key[0],year=key[1],field=field))
market=[dict(country=c,year=y,**market_map[c,y]) for c in COUNTRIES for y in [2022,2023,2024]]
market_changes=[]
for c in COUNTRIES:
    p0=market_map[c,2022]['population'];p1=market_map[c,2024]['population']
    g0=market_map[c,2022]['gdp_per_capita_usd'];g1=market_map[c,2024]['gdp_per_capita_usd']
    market_changes.append(dict(country=c,population_change=p1-p0 if p0 is not None and p1 is not None else None,
        population_change_pct=D(p1)/p0-1 if p0 and p1 is not None else None,
        nominal_usd_gdp_per_capita_change_pct=g1/g0-1 if g0 and g1 is not None else None))
write_csv('market_context.csv',market);write_csv('market_changes.csv',market_changes)

options=read_csv('hub-options.csv'); bycountry={c['country']:c for c in countries}
scenarios=[]; breakpoints=[]
for o in options:
    c=o['country']; b=bycountry[c]; C=b['contribution_eur']; U=b['shipped_units']; G=b['gross_sales_eur']; N=b['net_sales_eur']
    s=D(o['saving_eur_per_unit']); F=D(o['annual_fixed_eur']); K=D(o['capex_eur']); fte=int(o['fte'])
    for scenario,u in [('low',D('.10')),('base',D('.25')),('high',D('.40')),('stress',D('.25'))]:
        refund_shock=D('.03')*G if scenario=='stress' else ZERO
        fx_shock=D('.10')*N if scenario=='stress' and c in ['POL','CZE'] else ZERO
        stress_c=C-refund_shock-fx_shock
        volume=C*u
        savings=U*(1+u)*s
        shock=(refund_shock+fx_shock)*(1+u)
        annual=money(volume+savings-F-shock)
        scenarios.append(dict(country=c,scenario=scenario,incremental_contribution_eur=annual,capex_eur=K,fte=fte,
            payback_years=K/annual if annual>0 else None,volume_uplift=u,volume_contribution_eur=volume,
            savings_eur=savings,annual_fixed_eur=F,stress_penalty_eur=shock,year_zero_capex_eur=K,
            first_full_year_less_capex_eur=annual-K,baseline_contribution_eur=C,baseline_units=U,saving_eur_per_unit=s))
    breakpoints.append(dict(country=c,break_even_volume_uplift=(F-U*s)/(C+U*s),
        base_break_even_saving_eur_per_unit=(F-D('.25')*C)/(D('1.25')*U),
        base_break_even_fixed_eur=D('.25')*C+D('1.25')*U*s))
scmap={(s['country'],s['scenario']):s for s in scenarios}
portfolio=[]
for n in range(3):
    for combo in combinations(COUNTRIES,n):
        opts=[next(o for o in options if o['country']==c) for c in combo]
        capex=sum((D(o['capex_eur']) for o in opts),ZERO); fte=sum(int(o['fte']) for o in opts)
        feasible=capex<=450000 and fte<=7
        row=dict(option='+'.join(combo) if combo else 'DEFER',countries=list(combo),capex_eur=capex,fte=fte,feasible=feasible,
            constraint='; '.join(x for x in ['capex > EUR450,000' if capex>450000 else '', 'FTE > 7' if fte>7 else ''] if x))
        for scenario in ['low','base','high','stress']:
            v=sum((scmap[c,scenario]['incremental_contribution_eur'] for c in combo),ZERO)
            row[f'{scenario}_eur']=v
            row[f'{scenario}_payback_years']=capex/v if v>0 else None
        row['base_first_full_year_less_capex_eur']=row['base_eur']-capex
        portfolio.append(row)
ranked=sorted([p for p in portfolio if p['feasible']],key=lambda p:p['base_eur'],reverse=True)
for i,p in enumerate(ranked,1): p['base_rank']=i
for p in portfolio: p.setdefault('base_rank',None)
check('All portfolios enumerated',len(portfolio)==22)
write_csv('hub_scenarios.csv',scenarios);write_csv('breakpoints.csv',breakpoints)
write_csv('portfolios.csv',[dict(**p,country_codes=';'.join(p['countries'])) for p in sorted(portfolio,key=lambda p:(not p['feasible'],-p['base_eur']))])

quality=dict(order_reconciliation=oq,return_reconciliation=rq,
    eligible_orders=len(eligible),excluded_order_counts=dict(Counter(r['exclusion'] for r in excluded)),
    excluded_order_ids={reason:[r['order_id'] for r in excluded if r['exclusion']==reason] for reason in sorted({r['exclusion'] for r in excluded})},
    selected_returns=len(returns),included_return_records=sum(len(v) for v in kept_returns.values()),
    excluded_return_counts=dict(Counter(r['exclusion'] for r in excluded_returns)),excluded_returns=excluded_returns,
    zero_price_orders=sum(D(r['unit_price_local'])==0 for r in eligible.values()),
    zero_price_units=sum(int(r['quantity']) for r in eligible.values() if D(r['unit_price_local'])==0),
    free_order_contribution_eur=sum((r['contribution_eur'] for r in ledger if r['unit_price_local']==0),ZERO),
    multiple_return_id_orders=sum(len(v)>1 for v in kept_returns.values()),
    cutoff_day_returns=[r['return_id'] for rs in kept_returns.values() for r in rs if r['received_at']=='2026-01-31'],
    missing_shipment_dates=sum(r['shipped_at']=='' for r in orders.values()),missing_required_eligible_fields=0,
    missing_market_observations=wb_quality,missing_2025_fx_months=0,
    note='Revision selection precedes eligibility. Exact repeated rows removed; highest numeric revisions replace entire rows. Orphan not assigned currency or EUR value. Blank shipment dates occur only in excluded cancelled records. No imputation. All figures from frozen archive; no live official re-fetch.',
    limitations=['Synthetic client data and scenario inputs; no customer interviews or measured uplift.',
        'Returns after 2026-01-31 excluded; late-2025 shipments have shorter return observation windows.',
        'No collection/payment, VAT, working capital, lease quotes, detailed staffing costs, service levels, lead times, or site evidence.',
        'ECB translations are analytical rates, not realized cash FX. World Bank revision vintage is later than 2025.',
        'Revision timestamps are absent; highest supplied revision and received_at cutoff follow the dictionary, not a reconstructed historical system snapshot.',
        'Scenario savings apply to every shipped unit, including free shipments, and scale without capacity constraints per client policy.',
        'Pair model has no synergy, cannibalization, ramp-up, tax, financing, discounting or implementation delay.'])

recommendation=dict(countries=ranked[0]['countries'],capex_eur=ranked[0]['capex_eur'],fte=ranked[0]['fte'],
    rationale='Conditionally fund Czechia and Spain: highest annual incremental contribution in low, base and high cases, lower capex/FTE than runner-up Poland plus Spain, and positive combined stress. Launch Spain first; release Czechia only after demand, savings, cost coverage and FX gates. Netherlands plus Spain is the strongest downside alternative. This is a conditional choice under synthetic assumptions, not proven demand.',
    implementation='Reserve EUR225,000 / five FTE. Spain first: EUR130,000 / three FTE; Czechia second: EUR95,000 / two FTE. No capex release before validated economics and operational readiness. If Czechia gates fail, retain Spain-only or re-submit Netherlands plus Spain (EUR270,000 / six FTE).',
    annual_incremental_contribution_eur={s:ranked[0][s+'_eur'] for s in ['low','base','high','stress']},
    strongest_base_alternative=ranked[1]['option'])
sensitivities=[]
for u in [D('0'),D('.10'),D('.25'),D('.40')]:
    for sf in [D('0'),D('.5'),D('1')]:
        parts=[]
        for c in recommendation['countries']:
            o=next(o for o in options if o['country']==c); b=bycountry[c]
            parts.append(money(b['contribution_eur']*u+b['shipped_units']*(1+u)*D(o['saving_eur_per_unit'])*sf-D(o['annual_fixed_eur'])))
        sensitivities.append(dict(option='CZE+ESP',volume_uplift=u,savings_realization=sf,incremental_contribution_eur=sum(parts,ZERO)))
cze=bycountry['CZE']; nld=bycountry['NLD']; pol=bycountry['POL']; esp=bycountry['ESP']
base_gap=scmap['CZE','base']['incremental_contribution_eur']-scmap['NLD','base']['incremental_contribution_eur']
decision_thresholds=dict(
    cze_vs_nld_fx_haircut_crossover_no_refund_shock=base_gap/(D('1.25')*cze['net_sales_eur']),
    cze_vs_nld_fx_haircut_crossover_with_refund_shock=(base_gap-D('.0375')*(cze['gross_sales_eur']-nld['gross_sales_eur']))/(D('1.25')*cze['net_sales_eur']),
    cze_standalone_fx_haircut_break_even_with_refund_shock=(scmap['CZE','base']['incremental_contribution_eur']-D('.0375')*cze['gross_sales_eur'])/(D('1.25')*cze['net_sales_eur']),
    cze_volume_uplift_to_match_pol_at_base=(scmap['POL','base']['incremental_contribution_eur']+D(40000)-cze['shipped_units']*D('2.1'))/(cze['contribution_eur']+cze['shipped_units']*D('2.1')),
    recommended_no_savings_break_even_uplift=D(95000)/(cze['contribution_eur']+esp['contribution_eur']),
    recommended_base_with_savings_capped_at_recorded_fulfillment=sum((money(D('.25')*b['contribution_eur']+D('1.25')*b['fulfillment_eur']-f) for b,f in [(cze,D(40000)),(esp,D(55000))]),ZERO),
    caveat='Haircuts follow policy arithmetic: loss as a fraction of net sales, not exact exchange-rate percentage depreciation. One-way thresholds hold other inputs fixed; savings cap assumes all recorded fulfillment costs can be removed and is not a forecast.')
write_csv('sensitivity.csv',sensitivities)
metrics=dict(monthly=monthly,countries=countries,fx_monthly=fx,market_context=market,hub_scenarios=scenarios,
    recommendation=recommendation,quality=quality,portfolio_scenarios=sorted(portfolio,key=lambda p:(not p['feasible'],-p['base_eur'])),
    totals=total,market_changes=market_changes,breakpoints=breakpoints,sensitivities=sensitivities,decision_thresholds=decision_thresholds,
    methodology=dict(shipment_period='2025-01-01 through 2025-12-31',return_cutoff_inclusive='2026-01-31',
        rounding='Decimal ROUND_HALF_UP at order component level; scenario annual incremental outputs rounded half up to cents after unrounded intermediate terms; pairs sum displayed country scenario amounts.',
        fx='Arithmetic mean of published business-day quotes in shipment month; divide local amounts by local units per EUR; EUR=1.',
        market_vintage='World Bank lastupdated 2026-07-13; source archive retrieved 2026-09-27; revised history, not a point-in-time 2025 forecast.',
        scenario_timing='Full steady-state annual run-rate after launch. Capex at year zero; recurring fixed costs included annually. Simple undiscounted payback.'),
    source_register='../evidence/source_register.json')
dump(OUT/'metrics.json',metrics)
dump(ROOT/'verification/calculation_checks.json',{'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'checks':checks})
print(json.dumps({'totals':total,'quality':quality,'ranked_feasible':ranked,'breakpoints':breakpoints},indent=2,default=json_default))
