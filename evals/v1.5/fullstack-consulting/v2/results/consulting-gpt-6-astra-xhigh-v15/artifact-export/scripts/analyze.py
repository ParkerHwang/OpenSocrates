"""Deterministic, offline Meridian analysis. Money uses Decimal ROUND_HALF_UP."""
import csv
import hashlib
import itertools
import json
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP, getcontext
from pathlib import Path

getcontext().prec = 36
ROOT = Path(__file__).resolve().parents[1]
RAW, OUT = ROOT / 'raw', ROOT / 'deliverables'
OUT.mkdir(exist_ok=True)
D = Decimal
ZERO = D('0')
CENT = D('0.01')
COUNTRIES = ['DEU', 'FRA', 'NLD', 'POL', 'CZE', 'ESP']
MONTHS = [f'2025-{m:02}' for m in range(1, 13)]
CURRENCY = {c: ('PLN' if c == 'POL' else 'CZK' if c == 'CZE' else 'EUR') for c in COUNTRIES}
MONEY = ['gross_sales_eur', 'refunds_eur', 'net_sales_eur', 'net_cogs_eur', 'fulfillment_eur', 'contribution_eur']
ADDITIVE = ['shipped_orders', 'shipped_units'] + MONEY + ['returned_units']

def money(x):
    return D(x).quantize(CENT, rounding=ROUND_HALF_UP)

def number(x):
    if isinstance(x, D):
        return float(x)
    raise TypeError(type(x).__name__)

def save_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, default=number, allow_nan=False) + '\n')

def save_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

def read_csv(name):
    with (RAW / name).open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def select_revisions(names, key):
    records, seen, duplicates = [], {}, 0
    groups = defaultdict(list)
    for name in names:
        for line, row in enumerate(read_csv(name), 2):
            fingerprint = tuple(sorted(row.items()))
            item = dict(source_file=name, source_line=line, **row)
            if fingerprint in seen:
                item['handling'] = 'exact_duplicate'
                duplicates += 1
            else:
                seen[fingerprint] = item
                groups[row[key]].append(item)
            records.append(item)
    selected = {}
    for identifier, items in groups.items():
        highest = max(int(i['revision']) for i in items)
        winners = [i for i in items if int(i['revision']) == highest]
        if len(winners) != 1:
            raise ValueError(f'Conflicting equal revisions: {key}={identifier}')
        selected[identifier] = winners[0]
        for item in items:
            item['handling'] = 'selected' if item is winners[0] else 'superseded_revision'
    return selected, records, dict(raw_rows=len(records), exact_duplicates=duplicates,
                                 superseded_revisions=sum(r['handling'] == 'superseded_revision' for r in records),
                                 unique_ids=len(selected), conflicting_equal_revisions=0)

def main():
    supplied = json.loads((RAW / 'source-register.json').read_text())
    collection = json.loads((OUT / 'collection-register.json').read_text())
    public = {r['file']: r for r in supplied['public']}
    for item in collection:
        p = ROOT / item['file']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == item['sha256'], p
    for name, r in public.items():
        assert hashlib.sha256((RAW / name).read_bytes()).hexdigest() == r['sha256'], name
    with zipfile.ZipFile(RAW / 'ecb-history.zip') as z:
        contents = [z.read(n) for n in z.namelist() if n.lower().endswith('.csv')]
        assert (RAW / 'ecb-history.csv').read_bytes() in contents

    # All published observations in the sale month, never a current quote.
    observations = read_csv('ecb-history.csv')
    days = defaultdict(list)
    fx_daily = []
    for row in observations:
        if row['Date'][:7] in MONTHS:
            for currency in ['PLN', 'CZK']:
                if row[currency] not in ('', 'N/A'):
                    value = D(row[currency])
                    assert value > 0
                    days[(currency, row['Date'][:7])].append((row['Date'], value))
                    fx_daily.append(dict(date=row['Date'], currency=currency, local_per_eur=value))
    fx, fx_monthly = {}, []
    for currency in ['PLN', 'CZK']:
        for month in MONTHS:
            rows = sorted(days[(currency, month)])
            assert rows and len(rows) == len({r[0] for r in rows})
            mean = sum(r[1] for r in rows) / len(rows)
            fx[(currency, month)] = mean
            fx_monthly.append(dict(currency=currency, month=month, local_per_eur=mean,
                                   business_day_observations=len(rows), first_date=rows[0][0], last_date=rows[-1][0]))
    fx.update({('EUR', m): D(1) for m in MONTHS})

    orders, order_audit, order_counts = select_revisions(
        ['orders-part1.csv', 'orders-part2.csv', 'order-corrections.csv'], 'order_id')
    eligible = {}
    for oid, row in orders.items():
        reasons = []
        if row['status'] != 'shipped': reasons.append('not_shipped')
        if row['is_test'] == 'true': reasons.append('test')
        if not row['shipped_at']: reasons.append('missing_shipped_at')
        elif not '2025-01-01' <= row['shipped_at'] <= '2025-12-31': reasons.append('outside_2025')
        if reasons:
            row['handling'] = 'exclude:' + '|'.join(reasons)
        else:
            assert row['country'] in COUNTRIES
            assert row['currency'] == CURRENCY[row['country']]
            assert row['is_test'] == 'false'
            assert all(row[k] != '' for k in ['quantity','unit_price_local','discount_local','fulfillment_eur','sku'])
            assert D(row['quantity']) > 0
            row['handling'] = 'include'
            eligible[oid] = row
    order_counts.update(eligible_orders=len(eligible), excluded_orders=len(orders)-len(eligible),
                        excluded_status=sum(r['status'] != 'shipped' for r in orders.values()),
                        excluded_test=sum(r['is_test'] == 'true' for r in orders.values()),
                        excluded_outside_2025=sum(bool(r['shipped_at']) and not '2025-01-01' <= r['shipped_at'] <= '2025-12-31' for r in orders.values()),
                        missing_shipped_at=sum(not r['shipped_at'] for r in orders.values()))

    returns, return_audit, return_counts = select_revisions(['returns.csv'], 'return_id')
    returns_by_order = defaultdict(list)
    for rid, row in returns.items():
        assert row['received_at']
        if row['order_id'] not in orders:
            row['handling'] = 'quarantine:orphan_order'
        elif row['received_at'] > '2026-01-31':
            row['handling'] = 'exclude:after_cutoff'
        elif row['order_id'] not in eligible:
            row['handling'] = 'exclude:ineligible_order'
        else:
            assert 0 <= int(row['restocked_quantity']) <= int(row['quantity'])
            assert D(row['refund_local']) >= 0
            row['handling'] = 'include'
            returns_by_order[row['order_id']].append(row)
    return_counts.update(Counter(r['handling'] for r in returns.values()))
    return_counts['orders_with_multiple_return_ids'] = sum(len(rs) > 1 for rs in returns_by_order.values())
    return_counts['inclusive_cutoff_return_ids'] = [r['return_id'] for r in returns.values() if r['handling'] == 'include' and r['received_at'] == '2026-01-31']

    costs = read_csv('unit-costs.csv')
    ledger = []
    for oid, row in sorted(eligible.items()):
        candidates = [r for r in costs if r['sku'] == row['sku'] and r['valid_from'] <= row['shipped_at']]
        assert candidates, f'Missing effective cost {oid}'
        costrow = max(candidates, key=lambda r:r['valid_from'])
        cost = D(costrow['unit_cost_eur'])
        month, country, units = row['shipped_at'][:7], row['country'], int(row['quantity'])
        rate = fx[(row['currency'], month)]
        rs = returns_by_order[oid]
        returned = sum(int(r['quantity']) for r in rs)
        restocked = sum(int(r['restocked_quantity']) for r in rs)
        assert restocked <= returned <= units, oid
        gross_local = units * D(row['unit_price_local']) - D(row['discount_local'])
        refund_local = sum((D(r['refund_local']) for r in rs), ZERO)
        gross = money(gross_local / rate)
        refund = money(refund_local / rate)
        gross_cogs, recovery = money(units * cost), money(restocked * cost)
        fulfill = money(row['fulfillment_eur'])
        net, net_cogs = gross - refund, gross_cogs - recovery
        ledger.append(dict(order_id=oid, revision=int(row['revision']), country=country, month=month,
                           shipped_at=row['shipped_at'], sku=row['sku'], currency=row['currency'],
                           fx_local_per_eur=rate, shipped_orders=1, shipped_units=units,
                           gross_local=gross_local, refunds_local=refund_local, gross_sales_eur=gross,
                           refunds_eur=refund, net_sales_eur=net, unit_cost_eur=cost,
                           cost_valid_from=costrow['valid_from'], gross_cogs_eur=gross_cogs,
                           recovered_cogs_eur=recovery, net_cogs_eur=net_cogs, fulfillment_eur=fulfill,
                           contribution_eur=net-net_cogs-fulfill, returned_units=returned,
                           restocked_units=restocked, return_ids='|'.join(r['return_id'] for r in rs),
                           source_file=row['source_file'], source_line=row['source_line']))
    order_counts['zero_price_orders_retained'] = sum(r['gross_local'] == 0 for r in ledger)
    order_counts['zero_price_units_retained'] = sum(r['shipped_units'] for r in ledger if r['gross_local'] == 0)
    order_counts['zero_price_contribution_eur'] = sum((r['contribution_eur'] for r in ledger if r['gross_local'] == 0), ZERO)
    order_counts['negative_contribution_orders'] = sum(r['contribution_eur'] < 0 for r in ledger)

    def aggregate(rows, **keys):
        result = dict(**keys)
        for k in ADDITIVE:
            result[k] = sum((r[k] for r in rows), ZERO if k in MONEY else 0)
        result['margin'] = result['contribution_eur']/result['net_sales_eur'] if result['net_sales_eur'] else None
        return result
    monthly = [aggregate([r for r in ledger if r['country']==c and r['month']==m], country=c, month=m)
               for c in COUNTRIES for m in MONTHS]
    countries = [aggregate([r for r in monthly if r['country']==c], country=c) for c in COUNTRIES]
    totals = aggregate(ledger, country='ALL')
    for c in countries:
        independently = aggregate([r for r in ledger if r['country']==c['country']], country=c['country'])
        assert c == independently
    assert aggregate(countries, country='ALL') == totals

    wb = {}
    for filename, field, units in [('population.json','population','persons'), ('gdp-per-capita.json','gdp_per_capita_usd','current USD per person')]:
        meta, rows = json.loads((RAW / filename).read_text())
        assert meta['pages'] == 1 and len(rows) == meta['total'] == 18
        vals = {(r['countryiso3code'], int(r['date'])): r['value'] for r in rows}
        assert len(vals) == 18
        wb[field] = vals
    market = [dict(country=c, year=y, population=wb['population'][(c,y)], gdp_per_capita_usd=wb['gdp_per_capita_usd'][(c,y)])
              for c in COUNTRIES for y in [2022,2023,2024]]
    market_changes = []
    for c in COUNTRIES:
        p22,p24 = wb['population'][(c,2022)], wb['population'][(c,2024)]
        g22,g24 = wb['gdp_per_capita_usd'][(c,2022)], wb['gdp_per_capita_usd'][(c,2024)]
        market_changes.append(dict(country=c, population_change_2022_2024=None if p22 is None or p24 is None else p24-p22,
                                   population_change_pct=None if not p22 or p24 is None else D(p24-p22)/D(p22),
                                   gdp_per_capita_change_pct=None if not g22 or g24 is None else (D(str(g24))/D(str(g22)))-1))

    options = read_csv('hub-options.csv')
    scenarios, thresholds = [], []
    country_map = {r['country']:r for r in countries}
    for o in options:
        c = o['country']; r = country_map[c]
        C,U,G,N = r['contribution_eur'],r['shipped_units'],r['gross_sales_eur'],r['net_sales_eur']
        F,K,s = D(o['annual_fixed_eur']),D(o['capex_eur']),D(o['saving_eur_per_unit'])
        for scenario,u in [('low',D('.10')),('base',D('.25')),('high',D('.40')),('stress',D('.25'))]:
            refund_shock = D('.03') * G if scenario=='stress' else ZERO
            fx_shock = D('.10') * N if scenario=='stress' and c in ['POL','CZE'] else ZERO
            cs = C - refund_shock - fx_shock
            inc = money(cs*(1+u)-C + U*(1+u)*s-F)
            scenarios.append(dict(country=c, scenario=scenario, incremental_contribution_eur=inc,
                                  capex_eur=K, fte=int(o['fte']), payback_years=K/inc if inc>0 else None,
                                  uplift=u, annual_fixed_eur=F, saving_eur_per_unit=s,
                                  refund_shock_eur=refund_shock, fx_shock_eur=fx_shock,
                                  contribution_after_shock_eur=cs,
                                  incremental_before_fixed_eur=money(inc+F),
                                  first_full_year_increment_less_capex_eur=inc-K))
        thresholds.append(dict(country=c, break_even_uplift=(F-U*s)/(C+U*s),
                               break_even_saving_at_base=(F-C*D('.25'))/(D('1.25')*U),
                               max_fixed_cost_at_base=C*D('.25')+D('1.25')*U*s,
                               contribution_per_shipped_unit=C/U,
                               return_rate=D(r['returned_units'])/U,
                               fulfillment_per_unit=r['fulfillment_eur']/U))
    smap = {(r['country'],r['scenario']):r for r in scenarios}
    combinations = [()] + [(c,) for c in COUNTRIES] + list(itertools.combinations(COUNTRIES, 2))
    portfolios = []
    for combo in combinations:
        K = sum((smap[c,'base']['capex_eur'] for c in combo), ZERO)
        staff = sum(smap[c,'base']['fte'] for c in combo)
        reasons=[]
        if K>D('450000'): reasons.append('capex above EUR450,000')
        if staff>7: reasons.append('FTE above seven')
        row = dict(option='+'.join(combo) or 'DEFER', countries=list(combo), capex_eur=K, fte=staff,
                   feasible=not reasons, constraint_failures='; '.join(reasons))
        for sc in ['low','base','high','stress']:
            inc = sum((smap[c,sc]['incremental_contribution_eur'] for c in combo), ZERO)
            row[f'{sc}_incremental_eur'] = inc
            row[f'{sc}_payback_years'] = K/inc if inc>0 else None
        portfolios.append(row)
    feasible = sorted([r for r in portfolios if r['feasible']], key=lambda r:r['base_incremental_eur'], reverse=True)
    for i, row in enumerate(feasible, 1): row['base_rank'] = i
    for row in portfolios: row.setdefault('base_rank', None)
    best = feasible[0]
    # Stated analyst preference: highest base annual increment inside hard limits;
    # expose downside and capital efficiency separately, without invented weights.
    recommendation = dict(countries=best['countries'], capex_eur=best['capex_eur'], fte=best['fte'],
                          rationale='Highest modeled base annual incremental contribution among feasible portfolios. Stage commitments and validate uplift, unit savings and recurring cost before release; no probabilities or causal proof are asserted.',
                          base_incremental_contribution_eur=best['base_incremental_eur'],
                          low_incremental_contribution_eur=best['low_incremental_eur'],
                          high_incremental_contribution_eur=best['high_incremental_eur'],
                          stress_incremental_contribution_eur=best['stress_incremental_eur'],
                          payback_years=best['base_payback_years'],
                          decision_basis='Analyst default: maximize base annual contribution subject to capex <=450000, FTE <=7, hubs <=2. Test low and joint stress, show concessions; no weighted score.',
                          status='conditional recommendation, not spending authorization')
    missing_values = {}
    for file in ['orders-part1.csv','orders-part2.csv','order-corrections.csv','returns.csv','unit-costs.csv','hub-options.csv']:
        rows = read_csv(file)
        missing_values[file] = {k:sum(r[k]=='' for r in rows) for k in rows[0] if any(r[k]=='' for r in rows)}
    quality = dict(order_reconciliation=order_counts, return_reconciliation=return_counts,
                   missing_values=missing_values, missing_eligible_required_fields=0,
                   missing_effective_costs=0, missing_fx_months=0,
                   missing_market_values=sum(r[k] is None for r in market for k in ['population','gdp_per_capita_usd']),
                   public_archive_hashes_match=True, ecb_zip_matches_csv=True,
                   monthly_country_order_reconciliation='PASS: all additive measures agree exactly using cents',
                   handling_notes=[
                       'Highest numeric revision wins across all pages; full-row replacement. Identical raw duplicates removed before revision selection.',
                       'Eligibility uses original shipped_at in 2025, shipped status, is_test false; zero-price shipments retained.',
                       'Refunds are summed in original currency per eligible order then divided by the sale-month mean quote and half-up rounded.',
                       'Only physically restocked units recover COGS, valued at original shipment unit cost. Fulfillment is nonrefundable.',
                       'Orphan returns quarantined with no guessed join or guessed currency; after-cutoff returns excluded.',
                       'Missing shipment dates occur on cancelled rows; no imputation. No missing core public values in this vintage.',
                       'Archive collection is separate from original official retrieval. World Bank lastupdated=2026-07-13; subsequent historical revisions may be included.',
                       'Reference-rate translation is analytical; cash settlement FX and receivables are absent.',
                       'Scenario inputs are synthetic planning assumptions; ramp-up, working capital, tax, financing, depreciation, closure cost and discounting are not modeled.'
                   ])
    metrics = dict(monthly=monthly, countries=countries, fx_monthly=fx_monthly,
                   market_context=market, hub_scenarios=scenarios, recommendation=recommendation,
                   quality=quality, totals=totals, portfolio_scenarios=portfolios,
                   market_changes=market_changes, decision_thresholds=thresholds,
                   accounting=dict(period='2025 shipments', returns_cutoff_inclusive='2026-01-31', currency='EUR',
                                   rounding='Individual order components: Decimal ROUND_HALF_UP to cents; scenario increments rounded at country level, pairs sum those figures.',
                                   scenario_payback='Capex divided by positive rounded annual increment; null otherwise. Full run-rate year, undiscounted.'),
                   evidence_state=dict(client='synthetic observations and assumptions', public='archived official observations', recommendation='inferred from computed scenarios', native_method_application='unverified'))
    save_json('metrics.json', metrics)
    for name,rows in [('monthly.csv',monthly),('countries.csv',countries),('order-ledger.csv',ledger),
                      ('order-audit.csv',order_audit),('return-audit.csv',return_audit),('fx-monthly.csv',fx_monthly),
                      ('fx-daily-2025.csv',sorted(fx_daily,key=lambda r:(r['date'],r['currency']))),
                      ('market-context.csv',market),('hub-scenarios.csv',scenarios),('portfolio-scenarios.csv',portfolios),
                      ('decision-thresholds.csv',thresholds)]:
        save_csv(name,rows)
    metadata = {
        'index.html': ('inventory', 'source-room index', 'collection date'),
        'data-dictionary.md': ('synthetic policy','grain, currency, EUR costs','2025 shipments / cutoff 2026-01-31'),
        'scenario-policy.md': ('synthetic assumptions','uplift fractions, EUR and FTE constraints','annual full-run-rate model'),
        'hub-options.csv': ('synthetic assumptions','EUR capex; EUR/year fixed; EUR/unit savings; FTE','annual full-run-rate model'),
        'unit-costs.csv': ('synthetic observations','EUR per unit','effective dates 2025-01-01 and 2025-07-01'),
        'returns.csv': ('synthetic observations','physical units, restocked units, refund in order currency','2025-2026 returns; cutoff applied'),
        'source-register.json': ('provenance supplied by source room','URLs, SHA256, timestamps','archive retrieved 2026-09-27'),
        'ecb-history.csv': ('public official archive','local currency units per EUR','1999-2026 archive; 2025 used'),
        'ecb-history.zip': ('public official archive','local currency units per EUR','1999-2026 archive; 2025 used'),
        'population.json': ('public official archive','persons','2022-2024'),
        'gdp-per-capita.json': ('public official archive','current USD per person','2022-2024'),
    }
    register=[]
    for i,item in enumerate(collection,1):
        name = Path(item['file']).name
        status,units,period = metadata.get(name,('synthetic observations','order units; local currency price/discount; EUR fulfillment','2025 plus one 2026 order; revised rows'))
        source = public.get(name,{})
        if source.get('derived_from'): source = {**public[source['derived_from']],**source}
        register.append(dict(source_id=f'S{i:02}', **item, original_url=source.get('original_url',''),
                             archive_retrieved_utc=source.get('retrieved_utc',''),
                             revision_vintage='World Bank lastupdated 2026-07-13' if name in ['population.json','gdp-per-capita.json'] else 'archive 2026-09-27' if name in public else 'frozen synthetic source room',
                             units=units, period=period, status=status,
                             supplied_hash_matches=(item['sha256']==public[name]['sha256']) if name in public else None))
    if (OUT/'live-source-register.json').exists():
        register += json.loads((OUT/'live-source-register.json').read_text())
    save_json('source-register.json',register)
    save_csv('source-register.csv',register)
    print(json.dumps(dict(totals=totals, quality=quality, ranked_feasible=feasible, thresholds=thresholds, market_changes=market_changes),indent=2,default=number))

if __name__ == '__main__':
    main()
