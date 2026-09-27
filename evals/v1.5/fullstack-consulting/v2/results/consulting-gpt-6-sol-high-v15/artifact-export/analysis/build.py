"""Rebuild Meridian's audited 2025 model from the frozen source room.

Run from the project root: python analysis/build.py
No network access is needed after evidence/raw has been collected.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence" / "raw"
OUT = ROOT / "deliverables"
EVIDENCE = ROOT / "evidence"
OUT.mkdir(exist_ok=True)
CENT = Decimal("0.01")
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
MONEY = ["gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"]
ADDITIVE = ["shipped_orders", "shipped_units", *MONEY, "returned_units"]


def D(v):
    return Decimal(str(v))


def cents(v):
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def readcsv(name):
    with (RAW / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def writecsv(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def numeric(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def serialize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError(type(obj))


def read_fx():
    observations = defaultdict(list)
    for row in readcsv("ecb-history.csv"):
        date = row["Date"]
        if not date.startswith("2025-"):
            continue
        for c in ["PLN", "CZK"]:
            if row[c] not in ("", "N/A"):
                observations[(c, date[:7])].append(D(row[c]))
    fx = {}
    result = []
    for c in ["PLN", "CZK"]:
        for month in [f"2025-{m:02d}" for m in range(1, 13)]:
            values = observations[(c, month)]
            assert values, (c, month)
            mean = sum(values) / D(len(values))
            fx[(c, month)] = mean
            result.append({"currency": c, "month": month, "local_per_eur": round(float(mean), 10), "observations": len(values)})
    for month in [f"2025-{m:02d}" for m in range(1, 13)]:
        fx[("EUR", month)] = D(1)
    return fx, result


def read_context():
    maps = {}
    meta = {}
    for name in ["population.json", "gdp-per-capita.json"]:
        header, rows = json.loads((RAW / name).read_text())
        assert header["pages"] == 1 and header["total"] == 18 and len(rows) == 18
        maps[name] = {(r["countryiso3code"], int(r["date"])): r["value"] for r in rows}
        meta[name] = header
    result = []
    for c in COUNTRIES:
        for year in [2022, 2023, 2024]:
            result.append({"country": c, "year": year,
                           "population": maps["population.json"].get((c, year)),
                           "gdp_per_capita_usd": maps["gdp-per-capita.json"].get((c, year))})
    assert len(result) == 18
    return result, meta


def resolve(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    resolved = {}
    for k, group in groups.items():
        max_rev = max(int(x["revision"]) for x in group)
        winners = [x for x in group if int(x["revision"]) == max_rev]
        assert all(x == winners[0] for x in winners), f"Conflicting max-revision rows for {k}"
        resolved[k] = winners[0]
    return resolved


def empty_month(country, month):
    return {"country": country, "month": month, "shipped_orders": 0, "shipped_units": 0,
            **{field: D(0) for field in MONEY}, "returned_units": 0}


def ratio(row):
    return (float(row["contribution_eur"] / row["net_sales_eur"])
            if row["net_sales_eur"] != 0 else None)


def process_orders(fx):
    order_pages = readcsv("orders-part1.csv") + readcsv("orders-part2.csv")
    corrections = readcsv("order-corrections.csv")
    all_orders = order_pages + corrections
    orders = resolve(all_orders, "order_id")
    raw_returns = readcsv("returns.csv")
    returns = resolve(raw_returns, "return_id")
    cost = defaultdict(list)
    for r in readcsv("unit-costs.csv"):
        cost[r["sku"]].append((r["valid_from"], D(r["unit_cost_eur"])))
    for sku in cost:
        cost[sku].sort()

    qa = {
        "order_page_rows": len(order_pages), "correction_rows": len(corrections),
        "raw_order_rows": len(all_orders), "distinct_order_ids": len(orders),
        "exact_repeated_order_rows": len(all_orders) - len({tuple(sorted(x.items())) for x in all_orders}),
        "superseded_order_revision_rows": sum(int(x["revision"]) < int(orders[x["order_id"]]["revision"]) for x in all_orders),
        "missing_shipped_at_raw_rows": sum(not x["shipped_at"] for x in all_orders),
        "raw_return_rows": len(raw_returns), "distinct_return_ids": len(returns),
        "exact_repeated_return_rows": len(raw_returns) - len({tuple(sorted(x.items())) for x in raw_returns}),
        "superseded_return_revision_rows": sum(int(x["revision"]) < int(returns[x["return_id"]]["revision"]) for x in raw_returns),
    }
    audit = []
    eligible = {}
    for oid, row in sorted(orders.items()):
        if row["status"] != "shipped":
            reason = "cancelled_or_other_status"
        elif row["is_test"].lower() == "true":
            reason = "test"
        elif not row["shipped_at"] or row["shipped_at"][:4] != "2025":
            reason = "outside_2025_or_missing_ship_date"
        else:
            reason = "included"
            eligible[oid] = row
        audit.append({**row, "decision": reason})
    qa["order_decisions"] = dict(Counter(x["decision"] for x in audit))
    qa["included_zero_price_orders"] = sum(D(x["unit_price_local"]) == 0 for x in eligible.values())

    return_audit = []
    attached = defaultdict(list)
    for rid, r in sorted(returns.items()):
        if r["received_at"] > "2026-01-31":
            reason = "after_inclusive_cutoff"
        elif r["order_id"] not in orders:
            reason = "orphan_quarantined"
        elif r["order_id"] not in eligible:
            reason = "linked_order_ineligible"
        else:
            reason = "included"
            attached[r["order_id"]].append(r)
        return_audit.append({**r, "decision": reason})
    qa["return_decisions"] = dict(Counter(x["decision"] for x in return_audit))
    qa["multiple_return_ids_per_order"] = sum(len(v) > 1 for v in attached.values())

    monthly = {(country, f"2025-{m:02d}"): empty_month(country, f"2025-{m:02d}")
               for country in COUNTRIES for m in range(1, 13)}
    ledger = []
    for oid, row in sorted(eligible.items()):
        country = row["country"]
        month = row["shipped_at"][:7]
        currency = row["currency"]
        assert country in COUNTRIES and (currency, month) in fx
        unit_costs = [v for dt, v in cost[row["sku"]] if dt <= row["shipped_at"]]
        assert unit_costs, f"Missing effective cost: {oid}"
        unit_cost = unit_costs[-1]
        linked = attached.get(oid, [])
        quantity = int(row["quantity"])
        returned = sum(int(x["quantity"]) for x in linked)
        restocked = sum(int(x["restocked_quantity"]) for x in linked)
        assert 0 <= restocked <= returned <= quantity
        gross_local = D(row["unit_price_local"]) * quantity - D(row["discount_local"])
        refund_local = sum((D(x["refund_local"]) for x in linked), D(0))
        assert gross_local >= 0 and refund_local >= 0
        quote = fx[(currency, month)]
        gross = cents(gross_local / quote)
        refund = cents(refund_local / quote)
        gross_cogs = cents(unit_cost * quantity)
        recovered_cogs = cents(unit_cost * restocked)
        net_cogs = gross_cogs - recovered_cogs
        fulfillment = cents(D(row["fulfillment_eur"]))
        net = gross - refund
        contribution = net - net_cogs - fulfillment
        record = {"order_id": oid, "country": country, "month": month,
                  "currency": currency, "quote_local_per_eur": quote,
                  "sku": row["sku"], "quantity": quantity, "returned_units": returned,
                  "restocked_units": restocked, "unit_cost_eur": unit_cost,
                  "gross_local": gross_local, "refund_local": refund_local,
                  "gross_sales_eur": gross, "refunds_eur": refund, "net_sales_eur": net,
                  "gross_cogs_eur": gross_cogs, "recovered_cogs_eur": recovered_cogs,
                  "net_cogs_eur": net_cogs, "fulfillment_eur": fulfillment,
                  "contribution_eur": contribution}
        ledger.append(record)
        m = monthly[(country, month)]
        m["shipped_orders"] += 1
        m["shipped_units"] += quantity
        m["returned_units"] += returned
        for field in MONEY:
            m[field] += record[field]

    months = []
    for key in sorted(monthly):
        r = monthly[key]
        r["margin"] = ratio(r)
        months.append(r)
    countries = []
    for country in COUNTRIES:
        rows = [m for m in months if m["country"] == country]
        r = {"country": country}
        for field in ADDITIVE:
            r[field] = sum((x[field] for x in rows), D(0) if field in MONEY else 0)
        r["margin"] = ratio(r)
        countries.append(r)
    assert sum(x["shipped_orders"] for x in countries) == len(eligible)
    assert all(sum(m[field] for m in months if m["country"] == c["country"]) == c[field]
               for c in countries for field in ADDITIVE)
    qa["included_returned_units"] = sum(x["returned_units"] for x in countries)
    qa["included_restocked_units"] = sum(x["restocked_units"] for x in ledger)
    qa["eligible_orders_with_returns"] = len(attached)
    qa["monetary_reconciliation"] = "All 72 monthly rows reconcile exactly to six country totals at order-rounded cents."
    writecsv(EVIDENCE / "order_audit.csv", audit)
    writecsv(EVIDENCE / "return_audit.csv", return_audit)
    writecsv(EVIDENCE / "order_ledger.csv", ledger)
    return months, countries, qa


def scenarios(countries):
    options = {x["country"]: x for x in readcsv("hub-options.csv")}
    by_country = {x["country"]: x for x in countries}
    individual = []
    for country in COUNTRIES:
        b, o = by_country[country], options[country]
        C, U, G, N = (D(b["contribution_eur"]), D(b["shipped_units"]),
                      D(b["gross_sales_eur"]), D(b["net_sales_eur"]))
        K, F, s = (D(o["capex_eur"]), D(o["annual_fixed_eur"]), D(o["saving_eur_per_unit"]))
        for scenario, uplift in [("low", D("0.10")), ("base", D("0.25")), ("high", D("0.40")), ("stress", D("0.25"))]:
            if scenario == "stress":
                fx_shock = D("0.10") * N if country in ("POL", "CZE") else D(0)
                stressed_C = C - D("0.03") * G - fx_shock
                annual = stressed_C * (1 + uplift) - C + U * (1 + uplift) * s - F
            else:
                annual = C * uplift + U * (1 + uplift) * s - F
            annual = cents(annual)
            individual.append({"country": country, "scenario": scenario,
                               "incremental_contribution_eur": annual,
                               "capex_eur": K, "fte": int(o["fte"]),
                               "payback_years": round(float(K / annual), 3) if annual > 0 else None,
                               "annual_fixed_eur": F, "saving_eur_per_unit": s,
                               "volume_uplift": uplift})
    lookup = {(x["country"], x["scenario"]): x for x in individual}
    combinations = []
    sets = [()] + [(c,) for c in COUNTRIES] + list(itertools.combinations(COUNTRIES, 2))
    for selection in sets:
        capex = sum((D(options[c]["capex_eur"]) for c in selection), D(0))
        fte = sum(int(options[c]["fte"]) for c in selection)
        feasible = capex <= D(450000) and fte <= 7
        for scenario in ["low", "base", "high", "stress"]:
            annual = sum((D(lookup[(c, scenario)]["incremental_contribution_eur"]) for c in selection), D(0))
            combinations.append({"option": "+".join(selection) if selection else "DEFER",
                                 "countries": list(selection), "scenario": scenario,
                                 "incremental_contribution_eur": annual, "capex_eur": capex,
                                 "fte": fte, "feasible": feasible,
                                 "payback_years": round(float(capex / annual), 3) if annual > 0 and selection else None})
    return individual, combinations


def source_register(meta):
    upstream = json.loads((RAW / "source-register.json").read_text())
    official = {x["file"]: x for x in upstream["public"]}
    specs = {
        "orders-part1.csv": ("Synthetic client order extract, page 1", "orders/units/local currency/EUR", "2025-2026"),
        "orders-part2.csv": ("Synthetic client order extract, page 2", "orders/units/local currency/EUR", "2025-2026"),
        "order-corrections.csv": ("Synthetic client whole-row revisions", "orders/units/local currency/EUR", "2025"),
        "returns.csv": ("Synthetic client return extract", "units/local currency", "2025-2026-02-01"),
        "unit-costs.csv": ("Synthetic client effective unit costs", "EUR/unit", "2025"),
        "hub-options.csv": ("Synthetic client hub options", "EUR, EUR/unit, FTE", "annual planning assumption"),
        "scenario-policy.md": ("Synthetic client board scenario rules", "EUR, proportions", "annual planning assumption"),
        "data-dictionary.md": ("Synthetic client accounting rules", "definitions", "2025 base; 2026-01-31 cutoff"),
        "population.json": ("World Bank archived API response", "persons", "2022-2024"),
        "gdp-per-capita.json": ("World Bank archived API response", "current US$/person", "2022-2024"),
        "ecb-history.zip": ("ECB archived history ZIP", "local currency units/EUR", "through 2026-09-25"),
        "ecb-history.csv": ("Lossless extract of archived ECB ZIP", "local currency units/EUR", "through 2026-09-25"),
        "source-register.json": ("Source-room provenance metadata", "metadata", "2026-09-27 archive"),
    }
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for name, (description, units, period) in specs.items():
        path = RAW / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        o = official.get(name, {})
        if o:
            assert o["sha256"] == digest and o["bytes"] == path.stat().st_size, name
        status = ("source-room provenance metadata" if name == "source-register.json" else
                  "public official archive, extracted CSV" if name == "ecb-history.csv" else
                  "public archived official" if o else "synthetic client")
        rows.append({"file": str(path.relative_to(ROOT)), "source_room_url": f"http://127.0.0.1:65178/{name}",
                     "original_public_url": o.get("original_url", official.get("ecb-history.zip", {}).get("original_url", "") if name == "ecb-history.csv" else ""),
                     "archive_retrieved_utc": o.get("retrieved_utc", official.get("ecb-history.zip", {}).get("retrieved_utc", "") if name == "ecb-history.csv" else ""),
                     "local_downloaded_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                     "local_copy_checked_utc": now, "sha256": digest, "bytes": path.stat().st_size,
                     "units": units, "period": period, "status": status,
                     "description": description,
                     "source_revision": meta.get(name, {}).get("lastupdated", "")})
    writecsv(EVIDENCE / "source_register.csv", rows)
    return rows


def main():
    fx, fx_rows = read_fx()
    context, context_meta = read_context()
    months, countries, quality = process_orders(fx)
    singles, combos = scenarios(countries)
    source_register(context_meta)
    quality["archive_vintage_note"] = "Official series were collected by the source room on 2026-09-27; World Bank lastupdated is 2026-07-13. Historical observations may have been revised."
    quality["fx_note"] = "ECB means use all nonmissing published 2025 dates in the source-room archive; original sale-month quote used for returns. Actual settlement FX is unavailable."
    quality["excluded_return_values_note"] = "Orphan and after-cutoff returns remain in return_audit.csv and never enter the ledger."
    quality["missing_core_values"] = {"population": sum(x["population"] is None for x in context),
                                      "gdp_per_capita_usd": sum(x["gdp_per_capita_usd"] is None for x in context),
                                      "monthly_fx": 0, "eligible_order_cost": 0}
    feasible = [x for x in combos if x["feasible"] and x["scenario"] == "base"]
    ranked = sorted(feasible, key=lambda x: x["incremental_contribution_eur"], reverse=True)
    pair = {x["scenario"]: x for x in combos if x["option"] == "CZE+ESP"}
    risk_pair = {x["scenario"]: x for x in combos if x["option"] == "NLD+ESP"}
    base_edge = pair["base"]["incremental_contribution_eur"] - risk_pair["base"]["incremental_contribution_eur"]
    stress_edge = pair["stress"]["incremental_contribution_eur"] - risk_pair["stress"]["incremental_contribution_eur"]
    flip_fraction = float(base_edge / (base_edge - stress_edge))
    recommendation = {
        "countries": ["CZE", "ESP"], "capex_eur": 225000, "fte": 5,
        "decision": "Fund Spain first; reserve Czechia's capex subject to the day-60 operating and commercial gates.",
        "rationale": "CZE+ESP maximizes annual incremental contribution among feasible options in low/base/high client assumptions; the severe defined stress favors NLD+ESP, so stage the second commitment.",
        "base_incremental_contribution_eur": pair["base"]["incremental_contribution_eur"],
        "stress_incremental_contribution_eur": pair["stress"]["incremental_contribution_eur"],
        "strongest_stress_alternative": "NLD+ESP",
        "stress_alternative_incremental_contribution_eur": risk_pair["stress"]["incremental_contribution_eur"],
        "joint_stress_fraction_flipping_second_hub_vs_nld": round(flip_fraction, 4),
    }
    metrics = {"monthly": months, "countries": countries,
               "fx_monthly": [{k: v for k, v in x.items() if k in ("currency", "month", "local_per_eur")} for x in fx_rows],
               "market_context": context,
               "hub_scenarios": [{k: v for k, v in x.items() if k in ("country", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years")} for x in singles],
               "hub_combinations": combos, "recommendation": recommendation, "quality": quality,
               "fx_observation_counts": fx_rows,
               "units": {"monetary": "EUR", "population": "persons", "gdp_per_capita": "current US$", "fx": "local units per EUR"}}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, default=serialize, allow_nan=False) + "\n")
    print("COUNTRIES")
    for x in countries:
        print(x["country"], x["shipped_orders"], x["shipped_units"], x["contribution_eur"], x["margin"])
    print("BASE RANKING")
    for x in ranked:
        print(x["option"], x["incremental_contribution_eur"], x["capex_eur"], x["fte"], x["payback_years"])
    print("QUALITY", json.dumps(quality, default=serialize))
    # Selection is made after inspecting the audited ranking and stress comparison.
    (ROOT / "analysis" / "intermediate.json").write_text(json.dumps({
        "monthly": months, "countries": countries, "fx_monthly": fx_rows,
        "market_context": context, "hub_scenarios": singles, "hub_combinations": combos,
        "quality": quality}, indent=2, default=serialize) + "\n")


if __name__ == "__main__":
    main()
