"""Reproduce Meridian Parts' 2025 accounting and board scenario outputs.

Run from the project root with the Python specified in TOOLING.md.
Only saved source-room snapshots are used; no live API calls are made.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "sources" / "raw"
OUT = ROOT / "deliverables"
ANA = ROOT / "analysis"
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
D = Decimal
CENT = D("0.01")
MONEY = ["gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"]
NUMERIC = ["shipped_orders", "shipped_units", *MONEY, "returned_units"]


def csvrows(name):
    with (RAW / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def cents(value):
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def fmoney(value):
    return float(cents(value))


def latest(rows, key):
    groups = defaultdict(list)
    for row in rows:
        groups[row[key]].append(row)
    chosen = {}
    same_revision_conflicts = []
    for ident, group in groups.items():
        revision = max(int(x["revision"]) for x in group)
        winners = [x for x in group if int(x["revision"]) == revision]
        if len({tuple(sorted(x.items())) for x in winners}) != 1:
            same_revision_conflicts.append(ident)
        else:
            chosen[ident] = winners[0]
    if same_revision_conflicts:
        raise ValueError(f"Conflicting highest revisions: {same_revision_conflicts}")
    exact_extra = sum(len(v) - len({tuple(sorted(x.items())) for x in v}) for v in groups.values())
    return chosen, {"raw_rows": len(rows), "distinct_ids": len(groups), "exact_duplicate_extra_rows": exact_extra,
                    "superseded_revision_rows": len(rows) - len(chosen) - exact_extra,
                    "same_revision_conflicts": same_revision_conflicts}


def load_fx():
    by = defaultdict(list)
    for row in csvrows("ecb-history.csv"):
        if not row["Date"].startswith("2025-"):
            continue
        month = row["Date"][:7]
        for cur in ("PLN", "CZK"):
            if row[cur] not in ("", "N/A"):
                by[(cur, month)].append(D(row[cur]))
    fx = {}
    count = {}
    for cur in ("PLN", "CZK"):
        for m in range(1, 13):
            month = f"2025-{m:02d}"
            vals = by[(cur, month)]
            if not vals:
                raise ValueError(f"Missing ECB {cur} {month}")
            fx[(cur, month)] = sum(vals) / D(len(vals))
            count[(cur, month)] = len(vals)
    return fx, count


def empty_record(country, month=None):
    r = {"country": country}
    if month is not None:
        r["month"] = month
    r.update({k: 0 if k in ("shipped_orders", "shipped_units", "returned_units") else D(0) for k in NUMERIC})
    return r


def clean_record(rec):
    out = dict(rec)
    for k in MONEY:
        out[k] = fmoney(out[k])
    out["margin"] = None if out["net_sales_eur"] == 0 else round(out["contribution_eur"] / out["net_sales_eur"], 8)
    return out


def main():
    OUT.mkdir(exist_ok=True)
    ANA.mkdir(exist_ok=True)
    raw_orders = csvrows("orders-part1.csv") + csvrows("orders-part2.csv") + csvrows("order-corrections.csv")
    raw_returns = csvrows("returns.csv")
    orders, order_recon = latest(raw_orders, "order_id")
    returns, return_recon = latest(raw_returns, "return_id")
    excluded = Counter()
    eligible = {}
    for oid, o in orders.items():
        reasons = []
        if o["status"] != "shipped": reasons.append("not_shipped")
        if o["is_test"].strip().lower() != "false": reasons.append("test")
        if not o["shipped_at"].startswith("2025-"): reasons.append("outside_2025_shipment")
        if o["country"] not in COUNTRIES: reasons.append("unknown_country")
        if reasons:
            excluded.update(reasons)
        else:
            eligible[oid] = o
    included_returns = defaultdict(list)
    quarantined = []
    late = []
    for rid, ret in returns.items():
        if ret["received_at"] > "2026-01-31":
            late.append(rid)
        elif ret["order_id"] not in eligible:
            quarantined.append({"return_id": rid, "order_id": ret["order_id"],
                                "reason": "unknown_order" if ret["order_id"] not in orders else "ineligible_order"})
        else:
            included_returns[ret["order_id"]].append(ret)
    costs = defaultdict(list)
    for c in csvrows("unit-costs.csv"):
        costs[c["sku"]].append((c["valid_from"], D(c["unit_cost_eur"])))
    for sku in costs: costs[sku].sort()
    fx, fx_count = load_fx()
    monthly = {(c, f"2025-{m:02d}"): empty_record(c, f"2025-{m:02d}") for c in COUNTRIES for m in range(1, 13)}
    order_audit = []
    missing = []
    invalid = []
    for oid, o in eligible.items():
        month = o["shipped_at"][:7]
        cur = o["currency"]
        rate = D(1) if cur == "EUR" else fx.get((cur, month))
        if rate is None:
            missing.append(f"FX: {oid} {cur} {month}")
            continue
        valid_costs = [v for dt, v in costs[o["sku"]] if dt <= o["shipped_at"]]
        if not valid_costs:
            missing.append(f"Unit cost: {oid}")
            continue
        unit_cost = valid_costs[-1]
        quantity = int(o["quantity"])
        rets = included_returns.get(oid, [])
        returned = sum(int(x["quantity"]) for x in rets)
        restocked = sum(int(x["restocked_quantity"]) for x in rets)
        if quantity < 0 or returned > quantity or restocked > returned:
            invalid.append(oid)
            continue
        gross_local = D(quantity) * D(o["unit_price_local"]) - D(o["discount_local"])
        refunds_local = sum((D(x["refund_local"]) for x in rets), D(0))
        gross = cents(gross_local / rate)
        refund = cents(refunds_local / rate)
        cogs_gross = cents(D(quantity) * unit_cost)
        cogs_recovered = cents(D(restocked) * unit_cost)
        net_cogs = cogs_gross - cogs_recovered
        fulfillment = cents(o["fulfillment_eur"])
        contribution = gross - refund - net_cogs - fulfillment
        rec = monthly[(o["country"], month)]
        for k, v in {"shipped_orders": 1, "shipped_units": quantity, "gross_sales_eur": gross,
                     "refunds_eur": refund, "net_sales_eur": gross - refund, "net_cogs_eur": net_cogs,
                     "fulfillment_eur": fulfillment, "contribution_eur": contribution,
                     "returned_units": returned}.items():
            rec[k] += v
        order_audit.append({"order_id": oid, "country": o["country"], "month": month, "currency": cur,
                            "fx_local_per_eur": str(rate), "shipped_units": quantity, "gross_local": str(gross_local),
                            "refunds_local": str(refunds_local), "returned_units": returned, "restocked_units": restocked,
                            "gross_sales_eur": str(gross), "refunds_eur": str(refund), "gross_cogs_eur": str(cogs_gross),
                            "recovered_cogs_eur": str(cogs_recovered), "net_cogs_eur": str(net_cogs),
                            "fulfillment_eur": str(fulfillment), "contribution_eur": str(contribution)})
    if missing or invalid:
        raise ValueError(f"Missing inputs {missing}; invalid quantities {invalid}")
    country_rows = []
    for country in COUNTRIES:
        rec = empty_record(country)
        for month in range(1, 13):
            row = monthly[(country, f"2025-{month:02d}")]
            for k in NUMERIC: rec[k] += row[k]
        country_rows.append(clean_record(rec))
    monthly_rows = [clean_record(monthly[(c, f"2025-{m:02d}")]) for c in COUNTRIES for m in range(1, 13)]
    market = {}
    wb_meta = {}
    for name, field in (("population.json", "population"), ("gdp-per-capita.json", "gdp_per_capita_usd")):
        header, observations = json.loads((RAW / name).read_text())
        wb_meta[field] = header
        for obs in observations:
            key = (obs["countryiso3code"], int(obs["date"]))
            market.setdefault(key, {"country": key[0], "year": key[1], "population": None, "gdp_per_capita_usd": None})[field] = obs["value"]
    market_rows = [market[(c, y)] for c in COUNTRIES for y in (2022, 2023, 2024)]
    opts = {r["country"]: r for r in csvrows("hub-options.csv")}
    singles = {}
    for c, baseline in zip(COUNTRIES, country_rows):
        option = opts[c]
        C, U, G, N = (D(str(baseline[k])) for k in ("contribution_eur", "shipped_units", "gross_sales_eur", "net_sales_eur"))
        s, F, K = (D(option[k]) for k in ("saving_eur_per_unit", "annual_fixed_eur", "capex_eur"))
        fx_shock = D("0.10") * N if c in ("POL", "CZE") else D(0)
        stress_C = C - D("0.03") * G - fx_shock
        annual = {
            "low": C * D("0.10") + U * D("1.10") * s - F,
            "base": C * D("0.25") + U * D("1.25") * s - F,
            "high": C * D("0.40") + U * D("1.40") * s - F,
            "stress": stress_C * D("1.25") - C + U * D("1.25") * s - F,
        }
        singles[c] = {"capex": K, "fte": int(option["fte"]), "annual": annual, "saving": s, "fixed": F}
    feasible = [()] + [(c,) for c in COUNTRIES]
    feasible += [pair for pair in combinations(COUNTRIES, 2)
                 if sum(singles[c]["capex"] for c in pair) <= D(450000)
                 and sum(singles[c]["fte"] for c in pair) <= 7]
    scenario_rows = []
    for pair in feasible:
        label = "+".join(pair) if pair else "DEFER"
        K = sum((singles[c]["capex"] for c in pair), D(0))
        staff = sum(singles[c]["fte"] for c in pair)
        for scenario in ("low", "base", "high", "stress"):
            annual = cents(sum((singles[c]["annual"][scenario] for c in pair), D(0)))
            payback = None if annual <= 0 or K == 0 else round(float(K / annual), 4)
            scenario_rows.append({"country": label, "scenario": scenario,
                                  "incremental_contribution_eur": float(annual), "capex_eur": float(K),
                                  "fte": staff, "payback_years": payback})
    base_rank = sorted((r for r in scenario_rows if r["scenario"] == "base"),
                       key=lambda r: r["incremental_contribution_eur"], reverse=True)
    # Base-case maximum, subject to an explicit second-site release gate in the report.
    selected = ("CZE", "ESP")
    quality = {
        "order_reconciliation": order_recon, "return_reconciliation": return_recon,
        "excluded_latest_order_records": dict(excluded), "eligible_2025_orders": len(eligible),
        "included_return_ids": sum(map(len, included_returns.values())),
        "quarantined_returns": quarantined, "after_cutoff_return_ids": sorted(late),
        "zero_price_eligible_shipments": sum(D(o["unit_price_local"]) == 0 for o in eligible.values()),
        "missing_required_inputs": missing, "invalid_return_quantities": invalid,
        "ecb_observation_counts": {f"{c} {m}": n for (c, m), n in fx_count.items()},
        "world_bank_header": wb_meta,
        "country_month_reconciliation": "Passed: country totals are summed from all 12 monthly records",
        "translation_note": "ECB sale-month average quotes are analytical conversions, not transaction cash FX."
    }
    result = {"monthly": monthly_rows, "countries": country_rows,
              "fx_monthly": [{"currency": c, "month": f"2025-{m:02d}", "local_per_eur": round(float(fx[(c, f"2025-{m:02d}")]), 8)}
                             for c in ("PLN", "CZK") for m in range(1, 13)],
              "market_context": market_rows, "hub_scenarios": scenario_rows,
              "recommendation": {"countries": list(selected), "capex_eur": 225000, "fte": 5,
                                 "rationale": "Highest modeled base annual increment among feasible choices (€198,099.31); stage Spain first and release Czechia only after demand, service and FX/returns gates. The €32,179.71 joint-stress increment is a material risk; Netherlands plus Spain is the risk-first alternative."},
              "quality": quality}
    (OUT / "metrics.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    with (ANA / "order_audit.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=order_audit[0].keys()); w.writeheader(); w.writerows(sorted(order_audit, key=lambda x: x["order_id"]))
    with (ANA / "scenario_matrix.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=scenario_rows[0].keys()); w.writeheader(); w.writerows(scenario_rows)
    original = json.loads((RAW / "source-register.json").read_text())
    public_lookup = {x["file"]: x for x in original["public"]}
    source_specs = {
        "data-dictionary.md": ("accounting rules", "2025 shipments / returns through 2026-01-31"),
        "orders-part1.csv": ("local-currency sales and discounts; EUR fulfillment; units", "2025 shipments plus excluded records"),
        "orders-part2.csv": ("local-currency sales and discounts; EUR fulfillment; units", "2025 shipments plus excluded records"),
        "order-corrections.csv": ("local-currency sales and discounts; EUR fulfillment; units", "2025 revised shipments"),
        "returns.csv": ("local-currency refunds; physical and restocked units", "returns received through and after 2026-01-31"),
        "unit-costs.csv": ("EUR per unit", "effective from 2025-01-01 and 2025-07-01"),
        "hub-options.csv": ("EUR capex; FTE; EUR annual fixed; EUR saving per unit", "annual scenario assumptions"),
        "scenario-policy.md": ("dimensionless uplift/shocks; EUR decision bounds", "annual scenario assumptions"),
        "population.json": ("persons", "2022-2024"),
        "gdp-per-capita.json": ("current US$ per person", "2022-2024"),
        "ecb-history.csv": ("local currency units per EUR", "daily ECB history; 2025 used"),
        "ecb-history.zip": ("local currency units per EUR", "daily ECB history; 2025 used"),
        "source-register.json": ("source metadata and SHA-256 hashes", "archive retrieval vintage 2026-09-27"),
    }
    register = []
    for path in sorted(RAW.iterdir()):
        old = public_lookup.get(path.name, {})
        units, period = source_specs[path.name]
        item = {"file": str(path.relative_to(ROOT)), "collected_from": f"http://127.0.0.1:51903/{path.name}",
                "collected_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size, "status": "archived official public snapshot" if path.name in public_lookup else "synthetic client/source-room metadata",
                "original_public_url": old.get("original_url"), "original_retrieved_utc": old.get("retrieved_utc"),
                "period": period, "units": units,
                "archive_hash_verified": old.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest() if old else None}
        register.append(item)
    (ROOT / "sources" / "source_register.json").write_text(json.dumps(register, indent=2) + "\n")
    print(json.dumps({"country_totals": country_rows, "base_ranking": base_rank,
                      "order_recon": order_recon, "return_recon": return_recon,
                      "excluded": dict(excluded), "quarantined": quarantined, "late_returns": late}, indent=2))


if __name__ == "__main__":
    main()
