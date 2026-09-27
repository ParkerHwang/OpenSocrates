"""Deterministic Decimal financial model from saved evidence. No network access."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP, getcontext
from collections import Counter, defaultdict
from itertools import combinations
import csv
import datetime as dt
import hashlib
import json
import zipfile

getcontext().prec = 40
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'evidence/raw'
OUT = ROOT / 'deliverables'
D = Decimal
COUNTRIES = ['DEU', 'FRA', 'NLD', 'POL', 'CZE', 'ESP']
MONTHS = [f'2025-{m:02d}' for m in range(1, 13)]
CURRENCY = dict(DEU='EUR', FRA='EUR', NLD='EUR', POL='PLN', CZE='CZK', ESP='EUR')
MONEY = ['gross_sales_eur', 'refunds_eur', 'net_sales_eur', 'net_cogs_eur', 'fulfillment_eur', 'contribution_eur']
SUM_FIELDS = ['shipped_orders', 'shipped_units'] + MONEY + ['returned_units']

def money(value):
    return D(value).quantize(D('.01'), rounding=ROUND_HALF_UP)

def serial(value):
    if isinstance(value, D):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(type(value))

def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, default=serial, allow_nan=False) + '\n')

def read_csv(name):
    with (RAW / name).open(newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def reconcile(files, key):
    all_rows, unique, by_id, audit = [], {}, defaultdict(list), []
    for name in files:
        for line, row in enumerate(read_csv(name), 2):
            all_rows.append((row, name, line))
            signature = tuple(row.items())
            if signature in unique:
                audit.append(dict(record_id=row[key], file=name, line=line, action='identical_duplicate', detail=f'Identical to {unique[signature]}'))
            else:
                unique[signature] = f'{name}:{line}'
                by_id[row[key]].append((row, name, line))
    winners = {}
    for record_id, versions in by_id.items():
        max_rev = max(int(x[0]['revision']) for x in versions)
        top = [x for x in versions if int(x[0]['revision']) == max_rev]
        if len(top) != 1:
            raise ValueError(f'Conflicting equal revisions: {record_id}')
        winner, name, line = top[0]
        winners[record_id] = dict(winner, source_file=name, source_line=line)
        for row, name, line in versions:
            if int(row['revision']) < max_rev:
                audit.append(dict(record_id=record_id, file=name, line=line, action='superseded_revision', detail=f'Replaced in full by revision {max_rev}'))
    stats = dict(raw_rows=len(all_rows), identical_duplicates=len(all_rows)-len(unique),
                 superseded_revisions=len(unique)-len(winners), retained_ids=len(winners))
    return winners, audit, stats, all_rows

def main():
    OUT.mkdir(exist_ok=True)
    (OUT / 'audit').mkdir(exist_ok=True)
    manifest = json.loads((ROOT / 'evidence/collection-manifest.json').read_text())
    public = json.loads((RAW / 'source-register.json').read_text())
    pubmap = {r['file']: r for r in public['public']}
    source_register = []
    for i, row in enumerate(manifest, 1):
        path = ROOT / row['file']
        name = path.name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], name
        p = pubmap.get(name, {})
        if p:
            assert p['sha256'] == row['sha256'], name
        parent = pubmap.get(p.get('derived_from'), {})
        unit = ('persons' if name == 'population.json' else 'current US$ per person' if name == 'gdp-per-capita.json'
                else 'local currency units per EUR' if name.startswith('ecb-') else
                'EUR capex / annual fixed cost / per-unit saving; FTE' if name == 'hub-options.csv' else
                'EUR per SKU unit, effective dated' if name == 'unit-costs.csv' else
                'order / units / original-currency amounts / EUR fulfillment' if name.startswith('order') else
                'return / physical units / restocked units / original-currency credit' if name == 'returns.csv' else 'metadata / definitions / assumptions')
        source_register.append(dict(source_id=f'S{i:02d}', **row,
            original_url=p.get('original_url', parent.get('original_url', row['collection_url'])),
            archive_retrieved_utc=p.get('retrieved_utc', parent.get('retrieved_utc')),
            source_kind='archived_official_public' if p else 'synthetic_client' if name not in ['index.html','source-register.json'] else 'archive_metadata',
            units=unit,
            period='2022–2024' if name in ['population.json','gdp-per-capita.json'] else 'full ECB history; model uses 2025' if name.startswith('ecb-') else '2025 shipments; returns through 2026-01-31' if name.startswith('order') or name=='returns.csv' else '2025 cost schedule' if name=='unit-costs.csv' else 'steady-state annual hub assumptions / archive metadata',
            revision_vintage=json.loads(path.read_text())[0]['lastupdated'] if name in ['population.json','gdp-per-capita.json'] else public['vintage_note'] if p else 'Client revision fields govern; scenario version as collected',
            transformation=p.get('transformation', 'none; saved original bytes')))
    with zipfile.ZipFile(RAW / 'ecb-history.zip') as z:
        zip_names = z.namelist()
        csv_names = [n for n in zip_names if n.endswith('.csv')]
        assert len(csv_names) == 1
        assert z.read(csv_names[0]) == (RAW / 'ecb-history.csv').read_bytes()
    write_json(ROOT / 'evidence/source-register.json', source_register)
    write_csv(ROOT / 'evidence/source-register.csv', source_register)

    fx_daily, observations = [], defaultdict(list)
    seen_dates = set()
    for row in read_csv('ecb-history.csv'):
        if row['Date'][:4] != '2025':
            continue
        assert row['Date'] not in seen_dates
        seen_dates.add(row['Date'])
        assert dt.date.fromisoformat(row['Date']).weekday() < 5
        for cur in ['PLN', 'CZK']:
            if row[cur] in ['', 'N/A']:
                continue
            v = D(row[cur]); assert v > 0
            observations[cur, row['Date'][:7]].append(v)
            fx_daily.append(dict(date=row['Date'], currency=cur, local_per_eur=v))
    fx = {(cur, mon): sum(values, D(0))/len(values) for (cur, mon), values in observations.items()}
    assert all((c, m) in fx for c in ['PLN','CZK'] for m in MONTHS)
    fx_rows = [dict(currency=c, month=m, local_per_eur=fx[c,m], observation_count=len(observations[c,m])) for c in ['PLN','CZK'] for m in MONTHS]
    write_csv(OUT / 'audit/fx_daily_2025.csv', sorted(fx_daily, key=lambda r:(r['currency'],r['date'])))

    wb = {}
    missing_wb = []
    for name, field, indicator in [('population.json','population','SP.POP.TOTL'),('gdp-per-capita.json','gdp_per_capita_usd','NY.GDP.PCAP.CD')]:
        meta, values = json.loads((RAW / name).read_text(), parse_float=D)
        assert meta['pages'] == 1 and len(values) == meta['total'] == 18
        seen = set()
        for row in values:
            key = row['countryiso3code'], int(row['date'])
            assert key not in seen and row['indicator']['id'] == indicator
            seen.add(key)
            wb.setdefault(key, dict(country=key[0], year=key[1]))[field] = row['value']
            if row['value'] is None:
                missing_wb.append(dict(country=key[0],year=key[1],field=field))
    market = [wb[c,y] for c in COUNTRIES for y in [2022,2023,2024]]

    orders, order_audit, order_stats, raw_orders = reconcile(['orders-part1.csv','orders-part2.csv','order-corrections.csv'], 'order_id')
    returns, return_audit, return_stats, raw_returns = reconcile(['returns.csv'], 'return_id')
    missing = Counter(f'{name}:{field}' for row,name,_ in raw_orders+raw_returns for field,value in row.items() if value == '')
    exclusions = []
    eligible = {}
    for oid,row in orders.items():
        reason = ('non_shipped_status' if row['status'] != 'shipped' else
                  'test_order' if row['is_test'] != 'false' else
                  'missing_shipped_at' if not row['shipped_at'] else
                  'outside_2025' if row['shipped_at'][:4] != '2025' else None)
        if reason:
            exclusions.append(dict(record_type='order', record_id=oid, linked_order=oid, reason=reason, quantity=row['quantity'], refund_local='', currency=row['currency']))
        else:
            assert all(v != '' for v in row.values()), oid
            assert row['country'] in COUNTRIES and row['currency'] == CURRENCY[row['country']]
            assert int(row['quantity']) > 0
            assert D(row['unit_price_local']) >= 0 and D(row['discount_local']) >= 0
            eligible[oid] = row
    included_returns = defaultdict(list)
    for rid,row in returns.items():
        reason = ('orphan_order' if row['order_id'] not in orders else
                  'after_cutoff' if row['received_at'] > '2026-01-31' else
                  'ineligible_order' if row['order_id'] not in eligible else None)
        if reason:
            exclusions.append(dict(record_type='return', record_id=rid, linked_order=row['order_id'], reason=reason, quantity=row['quantity'], refund_local=row['refund_local'], currency=orders.get(row['order_id'],{}).get('currency','unknown')))
        else:
            assert all(v != '' for v in row.values()), rid
            assert row['received_at'] >= eligible[row['order_id']]['shipped_at']
            assert 0 <= int(row['restocked_quantity']) <= int(row['quantity'])
            assert D(row['refund_local']) >= 0
            included_returns[row['order_id']].append(row)
    costs = read_csv('unit-costs.csv')
    for sku in {r['sku'] for r in costs}:
        dates = [r['valid_from'] for r in costs if r['sku']==sku]
        assert len(dates)==len(set(dates))
    ledger = []
    for oid,row in sorted(eligible.items()):
        c, cur, month, units = row['country'], row['currency'], row['shipped_at'][:7], int(row['quantity'])
        rate = D(1) if cur == 'EUR' else fx[cur,month]
        options = [r for r in costs if r['sku']==row['sku'] and r['valid_from'] <= row['shipped_at']]
        assert options, oid
        cost_row = max(options, key=lambda r:r['valid_from']); cost=D(cost_row['unit_cost_eur'])
        rr = included_returns[oid]
        returned = sum(int(r['quantity']) for r in rr)
        restocked = sum(int(r['restocked_quantity']) for r in rr)
        assert returned <= units, oid
        gross_local=D(units)*D(row['unit_price_local'])-D(row['discount_local'])
        refund_local=sum((D(r['refund_local']) for r in rr),D(0))
        assert gross_local>=0 and refund_local <= gross_local, oid
        gross=money(gross_local/rate); refund=money(refund_local/rate)
        gross_cogs=money(D(units)*cost); recovery=money(D(restocked)*cost)
        net_cogs=gross_cogs-recovery; fulfillment=money(row['fulfillment_eur'])
        net=gross-refund; contribution=net-net_cogs-fulfillment
        ledger.append(dict(order_id=oid, revision=int(row['revision']),country=c,month=month,
            shipped_at=row['shipped_at'],sku=row['sku'],currency=cur,shipped_orders=1,shipped_units=units,
            unit_price_local=D(row['unit_price_local']),discount_local=D(row['discount_local']),gross_local=gross_local,
            refund_local=refund_local,fx_local_per_eur=rate,unit_cost_eur=cost,cost_valid_from=cost_row['valid_from'],
            gross_sales_eur=gross,refunds_eur=refund,net_sales_eur=net,gross_cogs_eur=gross_cogs,
            restocked_units=restocked,recovered_cogs_eur=recovery,net_cogs_eur=net_cogs,fulfillment_eur=fulfillment,
            contribution_eur=contribution,returned_units=returned,return_count=len(rr),
            return_ids=';'.join(sorted(r['return_id'] for r in rr)),source_file=row['source_file'],source_line=row['source_line']))
    def aggregate(rows, c, month=None):
        result=dict(country=c)
        if month: result['month']=month
        for k in SUM_FIELDS: result[k]=sum((r[k] for r in rows),D(0) if k in MONEY else 0)
        result['margin']=result['contribution_eur']/result['net_sales_eur'] if result['net_sales_eur'] else None
        assert result['net_sales_eur']==result['gross_sales_eur']-result['refunds_eur']
        assert result['contribution_eur']==result['net_sales_eur']-result['net_cogs_eur']-result['fulfillment_eur']
        return result
    monthly=[aggregate([r for r in ledger if r['country']==c and r['month']==m],c,m) for c in COUNTRIES for m in MONTHS]
    countries=[aggregate([r for r in monthly if r['country']==c],c) for c in COUNTRIES]
    for cr in countries:
        direct=aggregate([r for r in ledger if r['country']==cr['country']],cr['country'])
        assert cr==direct
    totals=aggregate(ledger,'ALL')

    options=read_csv('hub-options.csv')
    scenarios=[]
    thresholds=[]
    for row in options:
        c=row['country']; b=next(r for r in countries if r['country']==c)
        C,U,G,N=b['contribution_eur'],D(b['shipped_units']),b['gross_sales_eur'],b['net_sales_eur']
        s,F,K=D(row['saving_eur_per_unit']),D(row['annual_fixed_eur']),D(row['capex_eur'])
        for scenario,u in [('low',D('.10')),('base',D('.25')),('high',D('.40')),('stress',D('.25'))]:
            shock=D('.03')*G+(D('.10')*N if CURRENCY[c] in ['PLN','CZK'] else D(0)) if scenario=='stress' else D(0)
            volume=C*u
            savings=U*(1+u)*s
            stress_penalty=shock*(1+u)
            incremental=money(volume+savings-F-stress_penalty)
            scenarios.append(dict(country=c,scenario=scenario,incremental_contribution_eur=incremental,
                capex_eur=K,fte=int(row['fte']),payback_years=K/incremental if incremental>0 else None,
                volume_uplift=u,volume_contribution_eur=money(volume),unit_savings_eur=money(savings),
                annual_fixed_eur=F,stress_penalty_eur=money(stress_penalty)))
        thresholds.append(dict(country=c,break_even_uplift=(F-U*s)/(C+U*s),
            break_even_saving_at_base=(F-C*D('.25'))/(U*D('1.25')),
            base_contribution=C,units=int(U),saving_eur_per_unit=s,annual_fixed_eur=F))
    scenario_map={(s['country'],s['scenario']):s for s in scenarios}
    portfolios=[]
    combos=[()] + [(c,) for c in COUNTRIES] + list(combinations(COUNTRIES,2))
    for combo in combos:
        K=sum((scenario_map[c,'base']['capex_eur'] for c in combo),D(0))
        fte=sum(scenario_map[c,'base']['fte'] for c in combo)
        feasible=K<=450000 and fte<=7
        reason='; '.join(x for x,fail in [('capex > EUR450,000',K>450000),('FTE > 7',fte>7)] if fail)
        for sc in ['low','base','high','stress']:
            inc=sum((scenario_map[c,sc]['incremental_contribution_eur'] for c in combo),D(0))
            portfolios.append(dict(portfolio='+'.join(combo) or 'DEFER',countries=list(combo),scenario=sc,
                incremental_contribution_eur=inc,capex_eur=K,fte=fte,feasible=feasible,infeasibility_reason=reason,
                payback_years=K/inc if inc>0 else None))
    for sc in ['low','base','high','stress']:
        ranked=sorted([r for r in portfolios if r['scenario']==sc and r['feasible']],key=lambda r:(-r['incremental_contribution_eur'],r['capex_eur']))
        for rank,row in enumerate(ranked,1): row['rank_within_scenario']=rank
    free=[r for r in ledger if r['gross_sales_eur']==0]
    quality=dict(order_reconciliation=order_stats,return_reconciliation=return_stats,
        eligible_orders=len(ledger),included_return_ids=sum(len(v) for v in included_returns.values()),
        exclusions_by_reason=dict(Counter(r['reason'] for r in exclusions)),
        missing_raw_values=dict(missing),missing_eligible_order_values=0,missing_world_bank_values=missing_wb,
        missing_fx_months=0,conflicting_equal_revisions=0,
        free_shipments=dict(count=len(free),units=sum(r['shipped_units'] for r in free),
            contribution_eur=sum((r['contribution_eur'] for r in free),D(0)),ids=[r['order_id'] for r in free]),
        returns_with_multiple_ids=[dict(order_id=oid,ids=sorted(r['return_id'] for r in rr)) for oid,rr in included_returns.items() if len(rr)>1],
        cutoff_return_ids=[rid for rid,r in returns.items() if r['received_at']=='2026-01-31' and r['order_id'] in eligible],
        january_2026_return_ids=[rid for rid,r in returns.items() if r['received_at'][:7]=='2026-01' and r['order_id'] in eligible],
        restocked_units=sum(r['restocked_units'] for r in ledger),
        recovered_cogs_eur=sum((r['recovered_cogs_eur'] for r in ledger),D(0)),
        archive_public_hash_matches=4,zip_csv_byte_match=True,
        controls='Highest numeric revision wins in full; identical rows collapse; distinct return IDs add; orphan quarantined; shipment-month FX for both gross and summed credits; no missing monetary values imputed.',
        limitations=['Synthetic transactions and hub assumptions are not observed client demand.',
            'No payment ledger: booked sales cannot be reconciled to cash.',
            'Returns are censored at 2026-01-31; later credits are outside the defined base.',
            'No measured hub volume uplift, service SLA, competitive demand, site quotes, working capital or implementation ramp supplied.',
            'Archive collected 2026-09-27; World Bank source lastupdated 2026-07-13 can revise historical years.',
            'Scenario results are steady-state annual arithmetic, not causal estimates or discounted cash flow.',
            'FX reference means translate sales analytically; they are not realized exchange rates.'])
    cm={r['country']:r for r in countries}
    tm={r['country']:r for r in thresholds}
    pm={(r['portfolio'],r['scenario']):r for r in portfolios}
    sensitivity=[]
    for c in COUNTRIES:
        b,t=cm[c],tm[c]
        # Supplemental conservative bound: all unit savings come only from historic fulfillment.
        capped=min(t['saving_eur_per_unit'],b['fulfillment_eur']/b['shipped_units'])
        for sc,u in [('zero_uplift',D(0)),('saving_capped_base',D('.25')),('saving_capped_low',D('.10')),('saving_capped_stress',D('.25'))]:
            saving=t['saving_eur_per_unit'] if sc=='zero_uplift' else capped
            shock=(D('.03')*b['gross_sales_eur']+(D('.10')*b['net_sales_eur'] if CURRENCY[c]!='EUR' else D(0))) if sc=='saving_capped_stress' else D(0)
            value=money(b['contribution_eur']*u+D(b['shipped_units'])*(1+u)*saving-t['annual_fixed_eur']-(1+u)*shock)
            sensitivity.append(dict(country=c,test=sc,volume_uplift=u,saving_eur_per_unit=saving,incremental_contribution_eur=value,
                provenance='Analyst boundary test, not a new client scenario or a probability; cap uses recorded 2025 fulfillment per shipped unit'))
    cze,nld,esp=cm['CZE'],cm['NLD'],cm['ESP']
    cze_base=scenario_map['CZE','base']['incremental_contribution_eur']
    nld_base=scenario_map['NLD','base']['incremental_contribution_eur']
    switches=dict(
        cze_uplift_to_match_nld_base=(nld_base+tm['CZE']['annual_fixed_eur']-D(cze['shipped_units'])*tm['CZE']['saving_eur_per_unit'])/(cze['contribution_eur']+D(cze['shipped_units'])*tm['CZE']['saving_eur_per_unit']),
        cze_fx_net_sales_haircut_to_match_nld_with_3pct_refund=(cze_base-nld_base-D('1.25')*D('.03')*(cze['gross_sales_eur']-nld['gross_sales_eur']))/(D('1.25')*cze['net_sales_eur']),
        cze_fx_net_sales_haircut_to_break_even_with_3pct_refund=(cze_base-D('1.25')*D('.03')*cze['gross_sales_eur'])/(D('1.25')*cze['net_sales_eur']),
        cze_esp_common_uplift_to_break_even=(tm['CZE']['annual_fixed_eur']+tm['ESP']['annual_fixed_eur']-D(cze['shipped_units'])*tm['CZE']['saving_eur_per_unit']-D(esp['shipped_units'])*tm['ESP']['saving_eur_per_unit'])/(cze['contribution_eur']+esp['contribution_eur']+D(cze['shipped_units'])*tm['CZE']['saving_eur_per_unit']+D(esp['shipped_units'])*tm['ESP']['saving_eur_per_unit']))
    recommendation=dict(countries=['CZE','ESP'],capex_eur=D(225000),fte=5,
        rationale='Reserve a staged Czechia + Spain envelope: highest base, low and high contribution among feasible portfolios; aggregate specified stress remains positive. Start with Spain; release Czechia only after savings, demand and FX validation. Netherlands + Spain is the stronger stress-resilient alternative.',
        status='Provisional consulting recommendation; conditional on unmeasured volume and saving assumptions',
        annual_incremental_base_eur=pm['CZE+ESP','base']['incremental_contribution_eur'],
        annual_incremental_low_eur=pm['CZE+ESP','low']['incremental_contribution_eur'],
        annual_incremental_high_eur=pm['CZE+ESP','high']['incremental_contribution_eur'],
        annual_incremental_stress_eur=pm['CZE+ESP','stress']['incremental_contribution_eur'],
        payback_years=pm['CZE+ESP','base']['payback_years'],
        recurring_fixed_eur=D(95000),capex_headroom_eur=D(225000),fte_headroom=2,
        strongest_alternative=['NLD','ESP'],
        decision_rule='Consultant default: maximize base annual incremental contribution within hard capex/FTE/hub limits, check low and joint stress, stage irreversible spend. No weights or scenario probabilities assumed. A maximin preference selects NLD+ESP.',
        switching_values=switches,
        release_conditions=['Validate net per-unit saving scope, since all supplied savings exceed historical fulfillment per shipped unit.',
            'With NLD at 25% uplift and normal FX/returns, reopen CZE selection if validated CZE uplift is below about 17.7%.',
            'At 25% volume and 3% gross-sales refund shock, NLD overtakes CZE above about a 2.6% Czech net-sales FX haircut.',
            'Confirm all-in capex, staffing and working-capital needs before binding commitments; remaining budget is headroom, not automatic spending authority.'])
    metrics=dict(monthly=monthly,countries=countries,fx_monthly=fx_rows,market_context=market,
                 hub_scenarios=scenarios,recommendation=recommendation,
                 quality=quality,portfolios=portfolios,thresholds=thresholds,totals=totals,
                 sensitivity=sensitivity,
                 model=dict(analysis_year=2025,return_cutoff_inclusive='2026-01-31',money_rounding='ROUND_HALF_UP per order component, then sum',
                     fx_quote='local currency units per EUR; divide local amounts by arithmetic business-day mean',
                     gross_sales_definition='Quantity times unit price less discount, excluding tax; before refunds',
                     scenario_rounding='Round each country scenario result to cents, then sum pairs',
                     public_research='Core official data from frozen archive only; no live refresh',
                     world_bank_lastupdated='2026-07-13'))
    write_json(OUT / 'metrics.json',metrics)
    write_csv(OUT / 'audit/order_ledger.csv',ledger)
    write_csv(OUT / 'audit/revision_audit.csv',order_audit+return_audit)
    write_csv(OUT / 'audit/exclusions.csv',exclusions)
    write_csv(OUT / 'audit/retained_orders.csv',list(orders.values()))
    write_csv(OUT / 'audit/retained_returns.csv',list(returns.values()))
    for name,rows in [('monthly',monthly),('countries',countries),('fx_monthly',fx_rows),('market_context',market),('hub_scenarios',scenarios),('portfolios',portfolios),('thresholds',thresholds),('sensitivity',sensitivity)]:
        write_csv(OUT / 'audit' / f'{name}.csv',rows)
    print(json.dumps(dict(totals=totals,countries=countries,scenarios=scenarios,quality=quality,
        best_portfolios=sorted([r for r in portfolios if r['scenario']=='base' and r['feasible']],key=lambda r:-r['incremental_contribution_eur'])[:6]),indent=2,default=serial))

if __name__ == '__main__':
    main()
