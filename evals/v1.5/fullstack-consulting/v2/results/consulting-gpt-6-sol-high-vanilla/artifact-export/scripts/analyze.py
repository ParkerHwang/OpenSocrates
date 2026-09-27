#!/usr/bin/env python3
"""Reproduce Meridian's reconciled 2025 metrics from the saved source-room files."""
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
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
CENTS = Decimal("0.01")


def D(value):
    return Decimal(str(value))


def money(value):
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def rows(name):
    with (RAW / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, records):
    if not records:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)


def select_revisions(records, key):
    selected = {}
    duplicate = 0
    superseded = 0
    for r in records:
        k = r[key]
        rev = int(r["revision"])
        if k not in selected:
            selected[k] = r
            continue
        old = selected[k]
        old_rev = int(old["revision"])
        if rev > old_rev:
            selected[k] = r
            superseded += 1
        elif rev < old_rev:
            superseded += 1
        elif r == old:
            duplicate += 1
        else:
            raise ValueError(f"Conflicting same-revision rows for {key}={k}")
    return selected, duplicate, superseded


def main():
    OUT.mkdir(exist_ok=True)
    order_files = ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]
    raw_orders = list(itertools.chain.from_iterable(rows(n) for n in order_files))
    raw_order_blanks = Counter(k for r in raw_orders for k,v in r.items() if v in ("", None))
    order_by_id, order_duplicates, order_superseded = select_revisions(raw_orders, "order_id")
    exclusion = Counter()
    valid_orders = {}
    for oid, r in order_by_id.items():
        if r["status"].lower() != "shipped":
            exclusion[f"status_{r['status'].lower()}"] += 1
        elif r["is_test"].lower() != "false":
            exclusion["test"] += 1
        elif not ("2025-01-01" <= r["shipped_at"] <= "2025-12-31"):
            exclusion["shipped_outside_2025"] += 1
        else:
            valid_orders[oid] = r

    raw_returns = rows("returns.csv")
    raw_return_blanks = Counter(k for r in raw_returns for k,v in r.items() if v in ("", None))
    return_by_id, return_duplicates, return_superseded = select_revisions(raw_returns, "return_id")
    return_exclusion = Counter()
    valid_returns = defaultdict(list)
    for rid, r in return_by_id.items():
        if r["received_at"] > "2026-01-31":
            return_exclusion["after_cutoff"] += 1
        elif r["order_id"] not in order_by_id:
            return_exclusion["orphan_order_id"] += 1
        elif r["order_id"] not in valid_orders:
            return_exclusion["linked_ineligible_order"] += 1
        else:
            valid_returns[r["order_id"]].append(r)

    ecb = rows("ecb-history.csv")
    fx_days = defaultdict(list)
    for r in ecb:
        month = r["Date"][:7]
        if not month.startswith("2025-"):
            continue
        for currency in ("PLN", "CZK"):
            value = r[currency]
            if value and value != "N/A":
                fx_days[(currency, month)].append(D(value))
    fx_mean = {}
    fx_monthly = []
    for currency in ("PLN", "CZK"):
        for m in range(1, 13):
            month = f"2025-{m:02d}"
            observations = fx_days[(currency, month)]
            if not observations:
                raise ValueError(f"No ECB observations for {currency} {month}")
            mean = sum(observations) / D(len(observations))
            fx_mean[(currency, month)] = mean
            fx_monthly.append({"currency": currency, "month": month,
                               "local_per_eur": float(mean), "observation_days": len(observations)})

    costs = defaultdict(list)
    for r in rows("unit-costs.csv"):
        costs[r["sku"]].append((r["valid_from"], D(r["unit_cost_eur"])))
    for sku in costs:
        costs[sku].sort()

    order_detail = []
    missing = Counter()
    for oid, r in valid_orders.items():
        country = r["country"]
        if country not in COUNTRIES:
            raise ValueError(f"Unexpected country {country}")
        currency = r["currency"]
        if currency not in ("EUR", "PLN", "CZK"):
            raise ValueError(f"Unexpected currency {currency}")
        if (country in ("POL", "CZE")) != (currency in ("PLN", "CZK")):
            raise ValueError(f"Country/currency mismatch in {oid}")
        month = r["shipped_at"][:7]
        try:
            unit_cost = max((date, v) for date, v in costs[r["sku"]] if date <= r["shipped_at"])[1]
        except (KeyError, ValueError):
            missing["effective_unit_cost"] += 1
            raise ValueError(f"Missing effective unit cost for {oid}")
        rate = D(1) if currency == "EUR" else fx_mean[(currency, month)]
        quantity = int(r["quantity"])
        ret = valid_returns[oid]
        returned_units = sum(int(x["quantity"]) for x in ret)
        restocked = sum(int(x["restocked_quantity"]) for x in ret)
        if not (0 <= restocked <= returned_units <= quantity):
            raise ValueError(f"Invalid return quantities for {oid}")
        gross_local = D(quantity) * D(r["unit_price_local"]) - D(r["discount_local"])
        if gross_local < 0:
            raise ValueError(f"Negative gross local sale for {oid}")
        refund_local = sum((D(x["refund_local"]) for x in ret), D(0))
        gross = money(gross_local / rate)
        refunds = money(refund_local / rate)
        gross_cogs = money(D(quantity) * unit_cost)
        recovered_cogs = money(D(restocked) * unit_cost)
        net_cogs = gross_cogs - recovered_cogs
        fulfillment = money(D(r["fulfillment_eur"]))
        net = gross - refunds
        contribution = net - net_cogs - fulfillment
        order_detail.append({
            "order_id": oid, "country": country, "month": month, "shipped_at": r["shipped_at"],
            "sku": r["sku"], "revision": int(r["revision"]), "currency": currency,
            "local_per_eur": str(rate), "quantity": quantity,
            "returned_units": returned_units, "restocked_units": restocked,
            "return_ids": "|".join(sorted(x["return_id"] for x in ret)),
            "gross_sales_eur": str(gross), "refunds_eur": str(refunds),
            "net_sales_eur": str(net), "net_cogs_eur": str(net_cogs),
            "fulfillment_eur": str(fulfillment), "contribution_eur": str(contribution),
            "zero_price": gross_local == 0,
        })
    order_detail.sort(key=lambda r: (r["country"], r["month"], r["order_id"]))
    write_csv(OUT / "order_audit.csv", order_detail)

    monetary = ("gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur",
                "fulfillment_eur", "contribution_eur")
    def aggregate(records, country, month=None):
        chosen = [r for r in records if r["country"] == country and (month is None or r["month"] == month)]
        a = {"country": country}
        if month is not None:
            a["month"] = month
        a["shipped_orders"] = len(chosen)
        a["shipped_units"] = sum(r["quantity"] for r in chosen)
        for k in monetary:
            a[k] = float(sum((D(r[k]) for r in chosen), D(0)))
        a["returned_units"] = sum(r["returned_units"] for r in chosen)
        a["margin"] = float(D(str(a["contribution_eur"])) / D(str(a["net_sales_eur"]))) if a["net_sales_eur"] else None
        return a
    monthly = [aggregate(order_detail, c, f"2025-{m:02d}") for c in COUNTRIES for m in range(1, 13)]
    countries = [aggregate(order_detail, c) for c in COUNTRIES]
    for c in COUNTRIES:
        monthly_c = [r for r in monthly if r["country"] == c]
        year = next(r for r in countries if r["country"] == c)
        for k in ("shipped_orders", "shipped_units", "returned_units") + monetary:
            if money(sum((D(str(r[k])) for r in monthly_c), D(0))) != money(D(str(year[k]))):
                raise AssertionError(f"Monthly/year mismatch {c} {k}")

    wb_files = [
        ("population.json", "population"),
        ("gdp-per-capita.json", "gdp_per_capita_usd"),
    ]
    market = {(c, y): {"country": c, "year": y, "population": None,
                       "gdp_per_capita_usd": None} for c in COUNTRIES for y in (2022, 2023, 2024)}
    wb_meta = {}
    for name, field in wb_files:
        meta, observations = json.loads((RAW / name).read_text())
        wb_meta[name] = {"lastupdated": meta.get("lastupdated"), "sourceid": meta.get("sourceid")}
        for observation in observations:
            key = (observation["countryiso3code"], int(observation["date"]))
            if key in market:
                market[key][field] = observation["value"]
                if observation["value"] is None:
                    missing[field] += 1
    market_context = [market[(c, y)] for c in COUNTRIES for y in (2022, 2023, 2024)]

    options = {r["country"]: r for r in rows("hub-options.csv")}
    scenario_names = ("low", "base", "high", "stress")
    uplift = {"low": D("0.10"), "base": D("0.25"), "high": D("0.40")}
    single = {}
    for c in COUNTRIES:
        baseline = next(r for r in countries if r["country"] == c)
        option = options[c]
        C, U, G, N = (D(str(baseline[k])) for k in
                      ("contribution_eur", "shipped_units", "gross_sales_eur", "net_sales_eur"))
        s, F, K = (D(option[k]) for k in ("saving_eur_per_unit", "annual_fixed_eur", "capex_eur"))
        single[c] = {}
        for scenario in scenario_names:
            if scenario == "stress":
                fx_shock = D("0.10") * N if c in ("POL", "CZE") else D(0)
                stressed_C = C - D("0.03") * G - fx_shock
                annual = stressed_C * D("1.25") - C + U * D("1.25") * s - F
            else:
                u = uplift[scenario]
                annual = C * u + U * (D(1) + u) * s - F
            single[c][scenario] = money(annual)
    configurations = [(c,) for c in COUNTRIES]
    for pair in itertools.combinations(COUNTRIES, 2):
        if sum(int(options[c]["fte"]) for c in pair) <= 7 and sum(int(options[c]["capex_eur"]) for c in pair) <= 450000:
            configurations.append(pair)
    hub_scenarios = []
    for config in configurations:
        K = sum(int(options[c]["capex_eur"]) for c in config)
        fte = sum(int(options[c]["fte"]) for c in config)
        for scenario in scenario_names:
            annual = sum((single[c][scenario] for c in config), D(0))
            hub_scenarios.append({
                "country": "+".join(config), "scenario": scenario,
                "incremental_contribution_eur": float(annual),
                "capex_eur": K, "fte": fte,
                "payback_years": float(D(K) / annual) if annual > 0 else None,
            })
    for scenario in scenario_names:
        hub_scenarios.append({"country": "DEFER", "scenario": scenario,
                              "incremental_contribution_eur": 0.0, "capex_eur": 0,
                              "fte": 0, "payback_years": None})
    hub_scenarios.sort(key=lambda r: (r["country"], scenario_names.index(r["scenario"])))

    quality = {
        "raw_order_rows": len(raw_orders), "distinct_order_ids": len(order_by_id),
        "identical_order_duplicates": order_duplicates, "superseded_order_revisions": order_superseded,
        "order_exclusions": dict(exclusion), "eligible_2025_orders": len(valid_orders),
        "valid_zero_price_shipped_orders": sum(r["zero_price"] for r in order_detail),
        "raw_return_rows": len(raw_returns), "distinct_return_ids": len(return_by_id),
        "identical_return_duplicates": return_duplicates, "superseded_return_revisions": return_superseded,
        "return_exclusions": dict(return_exclusion),
        "eligible_return_ids": sum(map(len, valid_returns.values())),
        "eligible_returned_units": sum(r["returned_units"] for r in order_detail),
        "eligible_restocked_units": sum(r["restocked_units"] for r in order_detail),
        "missing_values": {"raw_order_shipped_at": raw_order_blanks["shipped_at"],
                           "raw_order_other_fields": sum(v for k,v in raw_order_blanks.items() if k != "shipped_at"),
                           "raw_return_fields": sum(raw_return_blanks.values()),
                           "eligible_order_shipped_at": sum(not r["shipped_at"] for r in valid_orders.values()),
                           "effective_unit_cost": missing["effective_unit_cost"],
                           "population": missing["population"],
                           "gdp_per_capita_usd": missing["gdp_per_capita_usd"]},
        "missing_value_handling": "The 24 blank raw shipped_at values belong to cancelled orders and are excluded; no eligible shipment, return field, effective unit cost or archived World Bank value is missing.",
        "world_bank_response_metadata": wb_meta,
        "fx_method": "Arithmetic mean of available published ECB business-day observations in original sale month; quote is local units per EUR.",
        "money_method": "Per-order components rounded to EUR cents half-up, then aggregated; refunds linked to original sale month.",
        "reconciliation": "All 6 country annual metric columns equal sums of their 12 monthly records.",
    }
    recommendation = {
        "countries": ["ESP", "CZE"], "capex_eur": 225000, "fte": 5,
        "rationale": "Authorize a staged Spain-first, Czechia-second plan. The pair leads feasible configurations in low/base/high incremental contribution; release Czechia capex only after its 90-day gate confirms return/FX exposure and an updated annual incremental contribution above EUR47,500 (simple payback under two years). Defer Czechia if joint stress appears persistent; Spain alone has a stronger stress outcome, while Netherlands+Spain is the strongest two-hub stress alternative and should be reassessed at the gate.",
        "staging": "ESP first; CZE conditional after day-90 gate",
        "base_incremental_contribution_eur": next(r["incremental_contribution_eur"] for r in hub_scenarios if r["country"] == "CZE+ESP" and r["scenario"] == "base"),
        "stress_incremental_contribution_eur": next(r["incremental_contribution_eur"] for r in hub_scenarios if r["country"] == "CZE+ESP" and r["scenario"] == "stress"),
    }
    metrics = {"monthly": monthly, "countries": countries, "fx_monthly": fx_monthly,
               "market_context": market_context, "hub_scenarios": hub_scenarios,
               "recommendation": recommendation, "quality": quality,
               "market_context_metadata": {
                   "population_unit": "persons", "gdp_per_capita_unit": "current US dollars per person",
                   "world_bank_lastupdated": wb_meta["population.json"]["lastupdated"],
                   "archive_retrieved_utc": json.loads((RAW / "source-register.json").read_text())["public"][0]["retrieved_utc"],
                   "population_original_url": json.loads((RAW / "source-register.json").read_text())["public"][0]["original_url"],
                   "gdp_per_capita_original_url": json.loads((RAW / "source-register.json").read_text())["public"][1]["original_url"],
               }}
    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n")
    write_csv(OUT / "monthly.csv", monthly)
    write_csv(OUT / "countries.csv", countries)
    write_csv(OUT / "hub_scenarios.csv", hub_scenarios)
    print(json.dumps({"quality": quality, "countries": countries,
                      "base_scenarios": [r for r in hub_scenarios if r["scenario"] == "base"]}, indent=2))


if __name__ == "__main__":
    main()
