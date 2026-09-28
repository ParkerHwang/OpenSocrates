#!/usr/bin/env python3
"""Reproducible Meridian Parts data analysis from the saved source-room files."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evidence" / "source-room"
OUT = ROOT / "analysis"
OUT.mkdir(exist_ok=True)
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
COUNTRY_CURRENCY = {"DEU": "EUR", "FRA": "EUR", "NLD": "EUR", "POL": "PLN", "CZE": "CZK", "ESP": "EUR"}
COUNTRY_NAMES = {"DEU": "Germany", "FRA": "France", "NLD": "Netherlands", "POL": "Poland", "CZE": "Czechia", "ESP": "Spain"}
WB_ISO2 = {"DEU": "DE", "FRA": "FR", "NLD": "NL", "POL": "PL", "CZE": "CZ", "ESP": "ES"}
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
CUTOFF = date(2026, 1, 31)


def D(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def read_csv(name: str) -> list[dict[str, str]]:
    with (SRC / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def deduplicate_exact(rows: list[dict[str, str]], key: str) -> tuple[list[dict[str, str]], int]:
    seen = set()
    keep = []
    duplicates = 0
    fields = tuple(rows[0].keys()) if rows else ()
    for row in rows:
        signature = tuple(row.get(field, "") for field in fields)
        if signature in seen:
            duplicates += 1
            continue
        seen.add(signature)
        keep.append(row)
    return keep, duplicates


def resolve_revisions(rows: list[dict[str, str]], id_field: str) -> tuple[dict[str, dict[str, str]], int, list[str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[id_field]].append(row)
    chosen: dict[str, dict[str, str]] = {}
    ties = []
    superseded = 0
    for key, items in grouped.items():
        highest = max(int(x["revision"]) for x in items)
        winners = [x for x in items if int(x["revision"]) == highest]
        signatures = {tuple(sorted(x.items())) for x in winners}
        if len(signatures) > 1:
            ties.append(key)
            # A conflict at the winning revision cannot be resolved from source
            # truth. Retain a stable lexical choice and surface it as a blocker.
            winners = sorted(winners, key=lambda x: tuple(sorted(x.items())))
        chosen[key] = winners[0]
        superseded += len(items) - 1
    return chosen, superseded, ties


def json_num(value: Decimal | int | float | None, places: int = 2):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def dec_sum(values):
    return sum(values, Decimal(0))


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    # Resolve source records across extract pages and correction files.
    order_page_1 = read_csv("orders-part1.csv")
    order_page_2 = read_csv("orders-part2.csv")
    order_corrections = read_csv("order-corrections.csv")
    order_all = order_page_1 + order_page_2 + order_corrections
    order_dedup, order_exact_dups = deduplicate_exact(order_all, "order_id")
    orders, order_superseded, order_ties = resolve_revisions(order_dedup, "order_id")

    order_quality = Counter()
    eligibility_exclusions = Counter()
    eligible_orders = {}
    excluded_orders = []
    for oid, row in orders.items():
        status = row["status"].strip().lower()
        is_test = row["is_test"].strip().lower() == "true"
        if status != "shipped":
            reason = "status_not_shipped"
        elif is_test:
            reason = "test_transaction"
        elif not row.get("shipped_at", "").strip():
            reason = "missing_shipped_date"
        elif not (date(2025, 1, 1) <= date.fromisoformat(row["shipped_at"]) <= date(2025, 12, 31)):
            reason = "shipment_outside_2025"
        else:
            reason = None
        if reason:
            eligibility_exclusions[reason] += 1
            excluded_orders.append({"order_id": oid, "revision": int(row["revision"]), "country": row["country"],
                                    "reason": reason, "status": status, "is_test": is_test, "shipped_at": row["shipped_at"]})
        else:
            if row["country"] not in COUNTRIES:
                eligibility_exclusions["unknown_country"] += 1
                excluded_orders.append({"order_id": oid, "reason": "unknown_country", "country": row["country"]})
                continue
            eligible_orders[oid] = row

    # Choose latest valid effective-dated unit cost for each shipment.
    cost_rows = read_csv("unit-costs.csv")
    costs = defaultdict(list)
    for row in cost_rows:
        costs[row["sku"]].append((date.fromisoformat(row["valid_from"]), D(row["unit_cost_eur"])))
    for sku in costs:
        costs[sku].sort(key=lambda x: x[0])

    # Calculate arithmetic means of the archived official business-day ECB quotes.
    with (SRC / "ecb-history.csv").open(newline="", encoding="utf-8-sig") as f:
        fx_rows = list(csv.DictReader(f))
    fx_daily = defaultdict(list)
    for row in fx_rows:
        if not row.get("Date"):
            continue
        day = date.fromisoformat(row["Date"])
        if day.year != 2025:
            continue
        month = day.strftime("%Y-%m")
        for currency in ("PLN", "CZK"):
            val = row.get(currency, "").strip()
            if val and val != "N/A":
                fx_daily[(currency, month)].append(D(val))
    fx_monthly_decimal = {}
    for currency in ("PLN", "CZK"):
        for month in MONTHS:
            obs = fx_daily.get((currency, month), [])
            if not obs:
                raise ValueError(f"Missing ECB rate observations for {currency} {month}")
            fx_monthly_decimal[(currency, month)] = dec_sum(obs) / D(len(obs))

    # Resolve returns by return ID before applying date/order eligibility filters.
    raw_returns = read_csv("returns.csv")
    returns_dedup, return_exact_dups = deduplicate_exact(raw_returns, "return_id")
    returns, return_superseded, return_ties = resolve_revisions(returns_dedup, "return_id")
    order_return_components = defaultdict(lambda: {"refund_local": Decimal(0), "returned_units": 0, "restocked_units": 0, "return_ids": []})
    return_quality = Counter()
    included_return_rows = []
    orphan_return_rows = []
    linked_ineligible_rows = []
    outside_cutoff_rows = []
    for rid, row in returns.items():
        received = date.fromisoformat(row["received_at"])
        if received > CUTOFF:
            return_quality["received_after_cutoff"] += 1
            outside_cutoff_rows.append({"return_id": rid, "order_id": row["order_id"], "received_at": row["received_at"]})
            continue
        oid = row["order_id"]
        if oid not in orders:
            return_quality["orphan_quarantined"] += 1
            orphan_return_rows.append({"return_id": rid, "order_id": oid, "received_at": row["received_at"], "refund_local": row["refund_local"]})
            continue
        if oid not in eligible_orders:
            return_quality["linked_order_ineligible"] += 1
            linked_ineligible_rows.append({"return_id": rid, "order_id": oid, "received_at": row["received_at"]})
            continue
        q = int(row["quantity"])
        restocked = int(row["restocked_quantity"])
        if q < 0 or restocked < 0 or restocked > q:
            return_quality["invalid_return_quantity"] += 1
        comp = order_return_components[oid]
        comp["refund_local"] += D(row["refund_local"])
        comp["returned_units"] += q
        comp["restocked_units"] += restocked
        comp["return_ids"].append(rid)
        included_return_rows.append(row)
        return_quality["included"] += 1

    # Calculate rounded monetary components at order grain, then aggregate.
    ledger = []
    for oid, row in eligible_orders.items():
        country = row["country"]
        month = row["shipped_at"][:7]
        if month not in MONTHS:
            raise ValueError(f"Eligible shipment outside 2025 months: {oid}")
        currency = row["currency"].strip().upper()
        if currency != COUNTRY_CURRENCY[country]:
            order_quality["country_currency_mismatch"] += 1
        rate = Decimal(1) if currency == "EUR" else fx_monthly_decimal.get((currency, month))
        if rate is None:
            raise ValueError(f"No FX rate for {currency} {month}")
        qty = int(row["quantity"])
        if qty < 0:
            order_quality["negative_shipped_quantity"] += 1
        gross_local = D(qty) * D(row["unit_price_local"]) - D(row["discount_local"])
        refund_local = order_return_components[oid]["refund_local"]
        gross_eur = cents(gross_local / rate)
        refunds_eur = cents(refund_local / rate)
        ship_date = date.fromisoformat(row["shipped_at"])
        eligible_costs = [(valid_from, cost) for valid_from, cost in costs.get(row["sku"], []) if valid_from <= ship_date]
        if not eligible_costs:
            raise ValueError(f"No effective unit cost for {oid} ({row['sku']})")
        unit_cost = eligible_costs[-1][1]
        returned_qty = order_return_components[oid]["returned_units"]
        restocked_qty = order_return_components[oid]["restocked_units"]
        if returned_qty > qty:
            order_quality["returned_quantity_exceeds_shipped"] += 1
        if restocked_qty > returned_qty:
            return_quality["restocked_exceeds_returned"] += 1
        gross_cogs = cents(D(qty) * unit_cost)
        recovered_cogs = cents(D(restocked_qty) * unit_cost)
        net_cogs = cents(gross_cogs - recovered_cogs)
        fulfillment = cents(D(row["fulfillment_eur"]))
        contribution = gross_eur - refunds_eur - net_cogs - fulfillment
        if gross_local == 0:
            order_quality["zero_gross_orders"] += 1
        if gross_local < 0:
            order_quality["negative_gross_orders"] += 1
        if refunds_eur > gross_eur:
            order_quality["refunds_exceed_gross_orders"] += 1
        ledger.append({
            "order_id": oid, "revision": int(row["revision"]), "country": country, "month": month,
            "shipped_at": row["shipped_at"], "status": row["status"], "sku": row["sku"], "quantity": qty,
            "currency": currency, "fx_local_per_eur": rate, "gross_sales_local": gross_local,
            "refunds_local": refund_local, "unit_cost_eur": unit_cost, "returned_units": returned_qty,
            "restocked_units": restocked_qty, "gross_sales_eur": gross_eur, "refunds_eur": refunds_eur,
            "net_sales_eur": gross_eur - refunds_eur, "gross_cogs_eur": gross_cogs,
            "recovered_cogs_eur": recovered_cogs, "net_cogs_eur": net_cogs,
            "fulfillment_eur": fulfillment, "contribution_eur": contribution,
            "return_ids": ";".join(order_return_components[oid]["return_ids"]),
        })

    # Aggregate complete country x calendar-month grid, retaining true zero months.
    monthly_acc = {}
    numeric_fields = ["shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units"]
    for country in COUNTRIES:
        for month in MONTHS:
            monthly_acc[(country, month)] = {k: 0 if k in ("shipped_orders", "shipped_units", "returned_units") else Decimal(0) for k in numeric_fields}
    for row in ledger:
        a = monthly_acc[(row["country"], row["month"])]
        a["shipped_orders"] += 1
        a["shipped_units"] += row["quantity"]
        a["gross_sales_eur"] += row["gross_sales_eur"]
        a["refunds_eur"] += row["refunds_eur"]
        a["net_sales_eur"] += row["net_sales_eur"]
        a["net_cogs_eur"] += row["net_cogs_eur"]
        a["fulfillment_eur"] += row["fulfillment_eur"]
        a["contribution_eur"] += row["contribution_eur"]
        a["returned_units"] += row["returned_units"]
    monthly = []
    for country in COUNTRIES:
        for month in MONTHS:
            a = monthly_acc[(country, month)]
            rec = {"country": country, "month": month}
            for field in numeric_fields:
                rec[field] = a[field]
            rec["margin"] = (a["contribution_eur"] / a["net_sales_eur"]) if a["net_sales_eur"] != 0 else None
            monthly.append(rec)

    country_acc = {c: {k: 0 if k in ("shipped_orders", "shipped_units", "returned_units") else Decimal(0) for k in numeric_fields} for c in COUNTRIES}
    for rec in monthly:
        a = country_acc[rec["country"]]
        for field in numeric_fields:
            a[field] += rec[field]
    countries = []
    for country in COUNTRIES:
        a = country_acc[country]
        rec = {"country": country, **a}
        rec["margin"] = a["contribution_eur"] / a["net_sales_eur"] if a["net_sales_eur"] != 0 else None
        countries.append(rec)

    # Archived World Bank values: preserve every requested country-year record,
    # including nulls, along with source metadata elsewhere in the register.
    wb_pop = json.loads((SRC / "population.json").read_text(encoding="utf-8"))
    wb_gdp = json.loads((SRC / "gdp-per-capita.json").read_text(encoding="utf-8"))
    archive_register = json.loads((SRC / "source-register.json").read_text(encoding="utf-8"))
    archive_rows = {r["file"]: r for r in archive_register["public"]}
    pop_values = {(r.get("countryiso3code"), int(r["date"])): r.get("value") for r in wb_pop[1]}
    gdp_values = {(r.get("countryiso3code"), int(r["date"])): r.get("value") for r in wb_gdp[1]}
    market_context = []
    for country in COUNTRIES:
        for year in (2022, 2023, 2024):
            market_context.append({"country": country, "year": year,
                                   "population": pop_values.get((country, year)),
                                   "gdp_per_capita_usd": gdp_values.get((country, year))})

    # Option and pair scenarios, with exact client policy formula.
    options = {r["country"]: {"capex_eur": int(r["capex_eur"]), "fte": int(r["fte"]),
                               "annual_fixed_eur": D(r["annual_fixed_eur"]), "saving_eur_per_unit": D(r["saving_eur_per_unit"])}
               for r in read_csv("hub-options.csv")}
    policy = {"low": Decimal("0.10"), "base": Decimal("0.25"), "high": Decimal("0.40")}
    country_by_code = {r["country"]: r for r in countries}
    choices = [{"codes": (c,), "choice": c} for c in COUNTRIES]
    excluded_pairs = []
    for a, b in itertools.combinations(COUNTRIES, 2):
        capex = options[a]["capex_eur"] + options[b]["capex_eur"]
        fte = options[a]["fte"] + options[b]["fte"]
        if capex <= 450_000 and fte <= 7:
            choices.append({"codes": (a, b), "choice": f"{a}+{b}"})
        else:
            excluded_pairs.append({"choice": f"{a}+{b}", "capex_eur": capex, "fte": fte,
                                   "capex_over_budget": capex > 450_000, "fte_over_budget": fte > 7})

    def scenario_for(codes, name):
        capex = sum(options[c]["capex_eur"] for c in codes)
        fte = sum(options[c]["fte"] for c in codes)
        C = dec_sum(D(country_by_code[c]["contribution_eur"]) for c in codes)
        U = sum(int(country_by_code[c]["shipped_units"]) for c in codes)
        G = dec_sum(D(country_by_code[c]["gross_sales_eur"]) for c in codes)
        N = dec_sum(D(country_by_code[c]["net_sales_eur"]) for c in codes)
        F = dec_sum(options[c]["annual_fixed_eur"] for c in codes)
        saving = dec_sum(D(country_by_code[c]["shipped_units"]) * options[c]["saving_eur_per_unit"] for c in codes)
        if name == "stress":
            fx_shock = Decimal(0)
            for c in codes:
                if c in ("POL", "CZE"):
                    fx_shock += D(country_by_code[c]["net_sales_eur"]) * Decimal("0.10")
            C_stress = C - G * Decimal("0.03") - fx_shock
            annual = C_stress * Decimal("1.25") - C + saving * Decimal("1.25") - F
            uplift = Decimal("0.25")
        else:
            uplift = policy[name]
            annual = C * uplift + saving * (Decimal(1) + uplift) - F
        annual_rounded = cents(annual)
        payback = D(capex) / annual_rounded if annual_rounded > 0 else None
        return {"country": "+".join(codes), "choice": " + ".join(codes), "scenario": name,
                "incremental_contribution_eur": annual_rounded, "capex_eur": capex, "fte": fte,
                "payback_years": payback, "feasible": True, "baseline_contribution_eur": C,
                "baseline_units": U, "baseline_gross_sales_eur": G, "baseline_net_sales_eur": N,
                "annual_fixed_eur": F, "saving_eur_per_unit_total": saving,
                "volume_uplift": uplift, "fx_shock_eur": fx_shock if name == "stress" else Decimal(0),
                "return_shock_eur": G * Decimal("0.03") if name == "stress" else Decimal(0)}

    hub_scenarios = []
    choice_summary = []
    for choice in choices:
        scenarios = {s: scenario_for(choice["codes"], s) for s in ("low", "base", "high", "stress")}
        for item in scenarios.values():
            hub_scenarios.append(item)
        first = scenarios["base"]
        item = {"choice": first["choice"], "country": first["country"], "countries": list(choice["codes"]),
                "capex_eur": first["capex_eur"], "fte": first["fte"],
                "low_eur": scenarios["low"]["incremental_contribution_eur"],
                "base_eur": scenarios["base"]["incremental_contribution_eur"],
                "high_eur": scenarios["high"]["incremental_contribution_eur"],
                "stress_eur": scenarios["stress"]["incremental_contribution_eur"],
                "base_payback_years": scenarios["base"]["payback_years"],
                "low_payback_years": scenarios["low"]["payback_years"],
                "high_payback_years": scenarios["high"]["payback_years"],
                "stress_payback_years": scenarios["stress"]["payback_years"], "feasible": True}
        choice_summary.append(item)
    # Defer is the zero-cost, zero-contribution reference, not a hub scenario.
    defer = {"choice": "Defer", "country": "DEFER", "countries": [], "capex_eur": 0, "fte": 0,
             "low_eur": Decimal(0), "base_eur": Decimal(0), "high_eur": Decimal(0), "stress_eur": Decimal(0),
             "base_payback_years": None, "low_payback_years": None, "high_payback_years": None,
             "stress_payback_years": None, "feasible": True}
    choice_summary.append(defer)
    choice_summary.sort(key=lambda x: (D(x["base_eur"]), D(x["stress_eur"])), reverse=True)
    ranked_real_choices = [x for x in choice_summary if x["countries"]]
    # Select the strongest base case from choices that remain contribution-positive
    # under the defined joint stress. If none pass, favor deferral.
    robust_candidates = [x for x in ranked_real_choices if D(x["stress_eur"]) > 0]
    selected = robust_candidates[0] if robust_candidates else defer
    alternative = next((x for x in ranked_real_choices if x["choice"] != selected["choice"]), defer)

    # Recommendation threshold: solve base formula for the required shared volume uplift.
    def break_even_uplift(choice):
        if not choice["countries"]:
            return None
        choice_obj = next(c for c in choices if "+".join(c["codes"]) == choice["country"])
        C = dec_sum(D(country_by_code[c]["contribution_eur"]) for c in choice_obj["codes"])
        U = sum(int(country_by_code[c]["shipped_units"]) for c in choice_obj["codes"])
        F = dec_sum(options[c]["annual_fixed_eur"] for c in choice_obj["codes"])
        saving = dec_sum(D(country_by_code[c]["shipped_units"]) * options[c]["saving_eur_per_unit"] for c in choice_obj["codes"])
        denom = C + saving
        if denom == 0:
            return None
        return (F - saving) / denom

    selected_break_even_uplift = break_even_uplift(selected)

    # Quality diagnostics and reconciliation checks.
    quality = {
        "source_room": "Frozen source-room snapshot downloaded locally; client data are synthetic.",
        "cutoff_inclusive": CUTOFF.isoformat(),
        "orders": {
            "raw_extract_rows": len(order_page_1) + len(order_page_2), "correction_rows": len(order_corrections),
            "rows_by_file": {"orders-part1.csv": len(order_page_1), "orders-part2.csv": len(order_page_2), "order-corrections.csv": len(order_corrections)},
            "raw_rows_total": len(order_all), "exact_duplicate_rows_removed": order_exact_dups,
            "distinct_order_ids": len(orders), "superseded_rows_after_revision_selection": order_superseded,
            "winning_revision_conflicts": order_ties, "selected_latest_revision_rows": len(orders),
            "eligible_2025_shipped_orders": len(eligible_orders), "excluded_by_reason": dict(eligibility_exclusions),
            "missing_values_in_selected_order_rows": {field: sum(not row.get(field, "").strip() for row in orders.values()) for field in order_all[0]},
            "zero_gross_valid_shipments": order_quality["zero_gross_orders"],
            "excluded_order_records": excluded_orders,
        },
        "returns": {
            "raw_rows": len(raw_returns), "exact_duplicate_rows_removed": return_exact_dups,
            "distinct_return_ids": len(returns), "superseded_rows_after_revision_selection": return_superseded,
            "winning_revision_conflicts": return_ties, "included_return_records": return_quality["included"],
            "missing_values_in_selected_return_rows": {field: sum(not row.get(field, "").strip() for row in returns.values()) for field in raw_returns[0]},
            "excluded_by_reason": {k: v for k, v in return_quality.items() if k != "included"},
            "orphan_return_rows_quarantined": orphan_return_rows,
            "linked_to_ineligible_order_examples": linked_ineligible_rows[:30],
            "outside_cutoff_examples": outside_cutoff_rows[:30],
        },
        "fx": {"quote": "local currency units per EUR; not inverted", "EUR": 1,
               "source_observations_by_currency_month": {f"{c}_{m}": len(fx_daily[(c, m)]) for c in ("PLN", "CZK") for m in MONTHS}},
        "calculation": {"source_rows": len(ledger), "orders_with_return_ids": sum(bool(x["return_ids"]) for x in ledger),
                        "currency_mismatches": order_quality["country_currency_mismatch"],
                        "returned_quantity_exceeds_shipped": order_quality["returned_quantity_exceeds_shipped"],
                        "negative_gross_orders": order_quality["negative_gross_orders"],
                        "refunds_exceed_gross_orders": order_quality["refunds_exceed_gross_orders"],
                        "rounding": "Each order gross, summed refunds, net COGS, and fulfillment rounded to EUR cents, ROUND_HALF_UP; contribution is derived from the rounded components."},
        "market_context": {"population_expected_rows": 18, "population_missing": sum(x["population"] is None for x in market_context),
                           "gdp_expected_rows": 18, "gdp_missing": sum(x["gdp_per_capita_usd"] is None for x in market_context),
                           "units": {"population": "persons", "gdp_per_capita_usd": "current US dollars per person"},
                           "vintage": "Archived World Bank API response; response metadata lastupdated 2026-07-13."},
        "reconciliation": {},
        "scenario": {"excluded_pairs": excluded_pairs, "choice_count_including_defer": len(choice_summary),
                     "feasible_hub_choices_including_singles_and_pairs": len(choices),
                     "assumptions": "Synthetic client policy; not a causal forecast or discounted cash-flow model."},
    }

    total_fields = ["shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units"]
    reconciliation = {}
    for field in total_fields:
        month_total = sum((r[field] for r in monthly), 0 if field in ("shipped_orders", "shipped_units", "returned_units") else Decimal(0))
        country_total = sum((r[field] for r in countries), 0 if field in ("shipped_orders", "shipped_units", "returned_units") else Decimal(0))
        reconciliation[field] = {"monthly_total": month_total, "country_total": country_total, "difference": month_total - country_total}
        if month_total != country_total:
            raise AssertionError(f"Monthly/country reconciliation failed for {field}")
    order_contribution_mismatch = [r["order_id"] for r in ledger if r["contribution_eur"] != r["gross_sales_eur"] - r["refunds_eur"] - r["net_cogs_eur"] - r["fulfillment_eur"]]
    if order_contribution_mismatch:
        raise AssertionError("Order contribution identity mismatch")
    if order_ties or return_ties:
        quality["reconciliation"]["manual_conflict_review_required"] = True
    quality["reconciliation"].update({"country_month_grid_rows": len(monthly), "country_year_rows": len(countries),
                                      "all_monthly_totals_equal_country_totals": True,
                                      "per_order_contribution_identity_mismatches": 0,
                                      "summed_order_ledger_equals_monthly": True,
                                      "totals": reconciliation})

    # Convert internal Decimal objects into exchange-friendly deterministic JSON.
    metrics = {
        "monthly": [], "countries": [], "fx_monthly": [], "market_context": market_context,
        "hub_scenarios": [], "recommendation": {}, "quality": quality,
        "metadata": {"analysis_period": "2025-01-01 through 2025-12-31 shipped date",
                     "returns_cutoff_inclusive": CUTOFF.isoformat(), "currency": "EUR", "generated_utc": datetime.now(timezone.utc).isoformat(),
                     "sources": "See source_register.csv and evidence/source-room/source-register.json.",
                     "market_context_sources": [
                         {"series": "Population, total", "file": "population.json", "indicator": "SP.POP.TOTL", "units": "persons", "years": [2022, 2023, 2024],
                          "url": archive_rows["population.json"]["original_url"], "archive_retrieved_utc": archive_rows["population.json"]["retrieved_utc"],
                          "response_lastupdated": wb_pop[0].get("lastupdated"), "missing_values_preserved_as": None},
                         {"series": "GDP per capita (current US$)", "file": "gdp-per-capita.json", "indicator": "NY.GDP.PCAP.CD", "units": "current US dollars per person", "years": [2022, 2023, 2024],
                          "url": archive_rows["gdp-per-capita.json"]["original_url"], "archive_retrieved_utc": archive_rows["gdp-per-capita.json"]["retrieved_utc"],
                          "response_lastupdated": wb_gdp[0].get("lastupdated"), "missing_values_preserved_as": None}],
                     "ecb_archive": {"file": "ecb-history.zip", "url": archive_rows["ecb-history.zip"]["original_url"],
                         "archive_retrieved_utc": archive_rows["ecb-history.zip"]["retrieved_utc"], "quote": "local currency units per EUR",
                         "monthly_aggregation": "arithmetic mean of available 2025 business-day reference rates"}},
    }
    for r in monthly:
        metrics["monthly"].append({"country": r["country"], "month": r["month"],
            **{k: json_num(r[k], 2) if k.endswith("_eur") else r[k] for k in numeric_fields},
            "margin": json_num(r["margin"], 8) if r["margin"] is not None else None})
    for r in countries:
        metrics["countries"].append({"country": r["country"],
            **{k: json_num(r[k], 2) if k.endswith("_eur") else r[k] for k in numeric_fields},
            "margin": json_num(r["margin"], 8) if r["margin"] is not None else None})
    for (currency, month), rate in sorted(fx_monthly_decimal.items(), key=lambda x: (x[0][0], x[0][1])):
        metrics["fx_monthly"].append({"currency": currency, "month": month, "local_per_eur": json_num(rate, 10),
                                      "published_business_days": len(fx_daily[(currency, month)])})
    for r in hub_scenarios:
        metrics["hub_scenarios"].append({"country": r["country"], "scenario": r["scenario"],
            "incremental_contribution_eur": json_num(r["incremental_contribution_eur"], 2),
            "capex_eur": r["capex_eur"], "fte": r["fte"],
            "payback_years": json_num(r["payback_years"], 2) if r["payback_years"] is not None else None,
            "choice": r["choice"], "baseline_contribution_eur": json_num(r["baseline_contribution_eur"], 2),
            "baseline_units": r["baseline_units"], "baseline_gross_sales_eur": json_num(r["baseline_gross_sales_eur"], 2),
            "baseline_net_sales_eur": json_num(r["baseline_net_sales_eur"], 2),
            "annual_fixed_eur": json_num(r["annual_fixed_eur"], 2), "volume_uplift": json_num(r["volume_uplift"], 4),
            "saving_eur_per_unit_total": json_num(r["saving_eur_per_unit_total"], 2),
            "return_shock_eur": json_num(r["return_shock_eur"], 6), "fx_shock_eur": json_num(r["fx_shock_eur"], 6)})
    selected_scenarios = next((x for x in choice_summary if x["choice"] == selected["choice"]), defer)
    metrics["recommendation"] = {"countries": selected["countries"], "choice": selected["choice"],
        "capex_eur": selected["capex_eur"], "fte": selected["fte"], "rationale": "Selected as the highest base-case feasible alternative with positive contribution under the defined joint stress; this remains scenario arithmetic on synthetic assumptions, not proof that hubs cause the uplift.",
        "base_incremental_contribution_eur": json_num(selected["base_eur"], 2),
        "low_incremental_contribution_eur": json_num(selected["low_eur"], 2),
        "high_incremental_contribution_eur": json_num(selected["high_eur"], 2),
        "stress_incremental_contribution_eur": json_num(selected["stress_eur"], 2),
        "base_payback_years": json_num(selected["base_payback_years"], 2) if selected["base_payback_years"] is not None else None,
        "break_even_volume_uplift": json_num(selected_break_even_uplift, 6) if selected_break_even_uplift is not None else None,
        "strongest_alternative": alternative["choice"],
        "alternative_base_incremental_contribution_eur": json_num(alternative["base_eur"], 2),
        "alternative_stress_incremental_contribution_eur": json_num(alternative["stress_eur"], 2),
        "deferral_base_incremental_contribution_eur": 0,
        "all_feasible_choices": [{"choice": r["choice"], "countries": r["countries"], "capex_eur": r["capex_eur"], "fte": r["fte"],
             "low_eur": json_num(r["low_eur"], 2), "base_eur": json_num(r["base_eur"], 2), "high_eur": json_num(r["high_eur"], 2),
             "stress_eur": json_num(r["stress_eur"], 2), "base_payback_years": json_num(r["base_payback_years"], 2) if r["base_payback_years"] is not None else None}
             for r in choice_summary]}

    (OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False, allow_nan=False,
                                                  default=lambda x: float(x) if isinstance(x, Decimal) else str(x)) + "\n", encoding="utf-8")
    (OUT / "order_ledger.json").write_text(json.dumps([{k: json_num(v, 10) if isinstance(v, Decimal) else v for k, v in r.items()} for r in ledger], indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT / "reconciliation.json").write_text(json.dumps({"quality": quality, "checks": {"totals": {k: {x: json_num(y, 2) if isinstance(y, Decimal) else y for x, y in v.items()} for k, v in reconciliation.items()}, "order_contribution_identity_mismatches": 0}}, indent=2, ensure_ascii=False, allow_nan=False,
                                                          default=lambda x: float(x) if isinstance(x, Decimal) else str(x)) + "\n", encoding="utf-8")
    summary = {"countries": [{"country": r["country"], "orders": r["shipped_orders"], "units": r["shipped_units"], "gross": json_num(r["gross_sales_eur"]), "refunds": json_num(r["refunds_eur"]), "net": json_num(r["net_sales_eur"]), "cogs": json_num(r["net_cogs_eur"]), "fulfillment": json_num(r["fulfillment_eur"]), "contribution": json_num(r["contribution_eur"]), "returned_units": r["returned_units"], "margin": json_num(r["margin"], 6)} for r in countries],
               "quality": quality, "recommendation": metrics["recommendation"],
               "top_choices": metrics["recommendation"]["all_feasible_choices"][:8],
               "low_rank": sorted(metrics["recommendation"]["all_feasible_choices"], key=lambda x: x["low_eur"], reverse=True)[:5],
               "high_rank": sorted(metrics["recommendation"]["all_feasible_choices"], key=lambda x: x["high_eur"], reverse=True)[:5]}
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
