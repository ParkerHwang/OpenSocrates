#!/usr/bin/env python3
"""Reproducible Meridian Parts analysis.

Reads only the preserved files under evidence/raw and writes deterministic
intermediate tables, metrics.json, and a merged source register.  Monetary
calculation is performed with Decimal and ROUND_HALF_UP at order level before
aggregation, following evidence/raw/data-dictionary.md.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence" / "raw"
PROCESSED = ROOT / "analysis" / "processed"
DELIVERABLES = ROOT / "deliverables"
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
COUNTRY_NAMES = {
    "DEU": "Germany",
    "FRA": "France",
    "NLD": "Netherlands",
    "POL": "Poland",
    "CZE": "Czechia",
    "ESP": "Spain",
}
COUNTRY_CURRENCY = {"DEU": "EUR", "FRA": "EUR", "NLD": "EUR", "POL": "PLN", "CZE": "CZK", "ESP": "EUR"}
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
BASE_URL = "http://127.0.0.1:49685/"
CUTOFF = date(2026, 1, 31)
MONEY_Q = Decimal("0.01")
ZERO = Decimal("0.00")


def dec(value: Any, default: Decimal | None = None) -> Decimal | None:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return default


def money(value: Decimal | None) -> Decimal:
    if value is None:
        return ZERO
    return value.quantize(MONEY_Q, rounding=ROUND_HALF_UP)


def iso_decimal(value: Decimal | None, places: int = 2) -> float | None:
    if value is None:
        return None
    q = Decimal(1).scaleb(-places)
    return float(value.quantize(q, rounding=ROUND_HALF_UP))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def file_retrieved_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def month_of(value: str) -> str:
    return str(value)[:7]


def date_of(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def row_signature(row: dict[str, Any], fields: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(k, "")) for k in fields)


def select_revisions(
    rows: list[dict[str, Any]], key: str, revision_field: str, fields: list[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Drop exact repeats, then retain highest numeric revision per key.

    A same-revision conflict is retained as a quality issue and resolved by
    source order (later input wins), a deterministic fallback not expected in
    the supplied files.
    """
    before = len(rows)
    seen: set[tuple[str, ...]] = set()
    deduped: list[dict[str, Any]] = []
    identical_duplicates = 0
    for row in rows:
        sig = row_signature(row, fields)
        if sig in seen:
            identical_duplicates += 1
            continue
        seen.add(sig)
        deduped.append(row)
    by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for i, row in enumerate(deduped):
        row["_input_order"] = i
        by_key[str(row[key])].append(row)
    selected: list[dict[str, Any]] = []
    same_revision_conflicts: list[str] = []
    revision_replacements = 0
    for k, group in by_key.items():
        max_rev = max(int(row.get(revision_field, 0) or 0) for row in group)
        max_rows = [row for row in group if int(row.get(revision_field, 0) or 0) == max_rev]
        sigs = {row_signature(row, fields) for row in max_rows}
        if len(sigs) > 1:
            same_revision_conflicts.append(k)
        chosen = sorted(max_rows, key=lambda x: x["_input_order"])[-1]
        if any(int(row.get(revision_field, 0) or 0) < max_rev for row in group):
            revision_replacements += 1
        selected.append(chosen)
    for row in selected:
        row.pop("_input_order", None)
    selected.sort(key=lambda x: str(x[key]))
    return selected, {
        "raw_rows": before,
        "identical_duplicate_rows": identical_duplicates,
        "rows_after_exact_dedupe": len(deduped),
        "unique_keys": len(by_key),
        "revision_replacements": revision_replacements,
        "same_revision_conflicts": same_revision_conflicts,
    }


def read_orders() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = [
        "order_id", "revision", "country", "ordered_at", "shipped_at", "status",
        "is_test", "sku", "quantity", "unit_price_local", "discount_local",
        "currency", "fulfillment_eur",
    ]
    rows: list[dict[str, Any]] = []
    for source in ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]:
        for row in read_csv(RAW / source):
            row["_source"] = source
            rows.append(row)
    selected, stats = select_revisions(rows, "order_id", "revision", fields)
    for row in selected:
        row["revision"] = int(row["revision"])
    stats["source_rows"] = {
        name: sum(1 for row in rows if row.get("_source") == name)
        for name in ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]
    }
    return selected, stats


def read_returns() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = ["return_id", "revision", "order_id", "received_at", "quantity", "restocked_quantity", "refund_local"]
    rows = read_csv(RAW / "returns.csv")
    selected, stats = select_revisions(rows, "return_id", "revision", fields)
    for row in selected:
        row["revision"] = int(row["revision"])
    return selected, stats


def fx_means() -> tuple[dict[tuple[str, str], Decimal], list[dict[str, Any]], dict[str, Any]]:
    rows = read_csv(RAW / "ecb-history.csv")
    buckets: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    dates_2025: set[str] = set()
    for row in rows:
        d = date_of(row.get("Date", ""))
        if d is None or d.year != 2025:
            continue
        month = d.strftime("%Y-%m")
        dates_2025.add(str(d))
        for currency in ["PLN", "CZK"]:
            value = dec(row.get(currency))
            if value is not None:
                buckets[(currency, month)].append(value)
    means: dict[tuple[str, str], Decimal] = {}
    out: list[dict[str, Any]] = []
    for currency in ["PLN", "CZK"]:
        for month in MONTHS:
            values = buckets.get((currency, month), [])
            if not values:
                continue
            mean = sum(values, ZERO) / Decimal(len(values))
            means[(currency, month)] = mean
            out.append({
                "currency": currency,
                "month": month,
                "local_per_eur": iso_decimal(mean, 9),
                "business_days": len(values),
            })
    stats = {
        "source_file": "ecb-history.csv",
        "observations_2025": len(dates_2025),
        "months_with_complete_pln_czk": sum(1 for m in MONTHS if ("PLN", m) in means and ("CZK", m) in means),
        "quote_definition": "ECB reference quote: local currency units per EUR; arithmetic mean over available published business days",
    }
    return means, out, stats


def unit_cost_lookup() -> tuple[list[dict[str, Any]], dict[tuple[str, str], Decimal]]:
    rows = read_csv(RAW / "unit-costs.csv")
    parsed: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str], Decimal] = {}
    for row in rows:
        value = {
            "sku": row["sku"],
            "valid_from": row["valid_from"],
            "unit_cost_eur": dec(row["unit_cost_eur"], ZERO),
        }
        parsed.append(value)
        lookup[(value["sku"], value["valid_from"])] = value["unit_cost_eur"]
    parsed.sort(key=lambda x: (x["sku"], x["valid_from"]))
    return parsed, lookup


def applicable_unit_cost(costs: list[dict[str, Any]], sku: str, shipment: date) -> Decimal | None:
    valid = [r for r in costs if r["sku"] == sku and date_of(r["valid_from"]) is not None and date_of(r["valid_from"]) <= shipment]
    if not valid:
        return None
    return sorted(valid, key=lambda x: x["valid_from"])[-1]["unit_cost_eur"]


def clean_order_and_return_data(
    orders: list[dict[str, Any]], returns: list[dict[str, Any]], order_stats: dict[str, Any], return_stats: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Decimal], dict[str, Any]]:
    selected_by_id = {row["order_id"]: row for row in orders}
    exclusion_counts: Counter[str] = Counter()
    eligible: list[dict[str, Any]] = []
    for row in orders:
        ship = date_of(row.get("shipped_at", ""))
        if row.get("country") not in COUNTRIES:
            exclusion_counts["country_out_of_scope"] += 1
            continue
        if row.get("status") != "shipped":
            exclusion_counts["status_not_shipped"] += 1
            continue
        if parse_bool(row.get("is_test", "false")):
            exclusion_counts["is_test"] += 1
            continue
        if ship is None:
            exclusion_counts["missing_shipped_at"] += 1
            continue
        if ship < date(2025, 1, 1):
            exclusion_counts["shipped_before_2025"] += 1
            continue
        if ship > date(2025, 12, 31):
            exclusion_counts["shipped_after_2025"] += 1
            continue
        eligible.append(row)
    eligible_ids = {row["order_id"] for row in eligible}
    selected_return_by_id = {row["return_id"]: row for row in returns}
    # Track quarantines before date filtering, with no guessing of orphan links.
    return_exclusions: Counter[str] = Counter()
    included_returns: list[dict[str, Any]] = []
    for row in returns:
        received = date_of(row.get("received_at", ""))
        if row.get("order_id") not in selected_by_id:
            return_exclusions["orphan_order_id"] += 1
            continue
        if row.get("order_id") not in eligible_ids:
            return_exclusions["linked_order_ineligible"] += 1
            continue
        if received is None:
            return_exclusions["missing_received_at"] += 1
            continue
        if received > CUTOFF:
            return_exclusions["received_after_cutoff"] += 1
            continue
        included_returns.append(row)
    returns_by_order: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"returned_units": ZERO, "restocked_units": ZERO, "refund_local": ZERO})
    for row in included_returns:
        agg = returns_by_order[row["order_id"]]
        agg["returned_units"] += dec(row.get("quantity"), ZERO) or ZERO
        agg["restocked_units"] += dec(row.get("restocked_quantity"), ZERO) or ZERO
        agg["refund_local"] += dec(row.get("refund_local"), ZERO) or ZERO
    anomaly_return_over_order: list[str] = []
    for row in eligible:
        if returns_by_order[row["order_id"]]["returned_units"] > (dec(row.get("quantity"), ZERO) or ZERO):
            anomaly_return_over_order.append(row["order_id"])
    stats = {
        "order_selection": order_stats,
        "return_selection": return_stats,
        "eligible_orders": len(eligible),
        "excluded_orders": dict(exclusion_counts),
        "included_return_rows": len(included_returns),
        "excluded_return_rows": dict(return_exclusions),
        "eligible_returned_order_count": sum(1 for x in returns_by_order.values() if x["returned_units"] > 0),
        "return_units_exceed_order_units": anomaly_return_over_order,
        "cutoff_inclusive": CUTOFF.isoformat(),
    }
    return eligible, returns_by_order, stats


def calculate_orders(
    eligible: list[dict[str, Any]],
    returns_by_order: dict[str, dict[str, Decimal]],
    fx: dict[tuple[str, str], Decimal],
    costs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    out: list[dict[str, Any]] = []
    missing_fx: list[str] = []
    missing_cost: list[str] = []
    zero_price_order_ids: list[str] = []
    for row in eligible:
        ship = date_of(row["shipped_at"])
        assert ship is not None
        month = ship.strftime("%Y-%m")
        currency = row["currency"]
        rate = Decimal("1") if currency == "EUR" else fx.get((currency, month))
        if rate is None:
            missing_fx.append(row["order_id"])
            continue
        unit_cost = applicable_unit_cost(costs, row["sku"], ship)
        if unit_cost is None:
            missing_cost.append(row["order_id"])
            continue
        qty = dec(row["quantity"], ZERO) or ZERO
        price = dec(row["unit_price_local"], ZERO) or ZERO
        discount = dec(row["discount_local"], ZERO) or ZERO
        gross_local = qty * price - discount
        if gross_local == 0:
            zero_price_order_ids.append(row["order_id"])
        ret = returns_by_order.get(row["order_id"], {"returned_units": ZERO, "restocked_units": ZERO, "refund_local": ZERO})
        gross_sales_eur = money(gross_local / rate)
        refunds_eur = money(ret["refund_local"] / rate)
        gross_cogs_eur = money(qty * unit_cost)
        recovered_cogs_eur = money(ret["restocked_units"] * unit_cost)
        net_cogs_eur = money(gross_cogs_eur - recovered_cogs_eur)
        fulfillment_eur = money(dec(row["fulfillment_eur"], ZERO))
        contribution_eur = money(gross_sales_eur - refunds_eur - net_cogs_eur - fulfillment_eur)
        out.append({
            "order_id": row["order_id"],
            "revision": row["revision"],
            "country": row["country"],
            "month": month,
            "shipped_at": row["shipped_at"],
            "sku": row["sku"],
            "currency": currency,
            "quantity": int(qty),
            "unit_price_local": str(row["unit_price_local"]),
            "discount_local": str(row["discount_local"]),
            "fx_local_per_eur": str(rate),
            "unit_cost_eur": str(unit_cost),
            "gross_sales_eur": str(gross_sales_eur),
            "refunds_eur": str(refunds_eur),
            "gross_cogs_eur": str(gross_cogs_eur),
            "recovered_cogs_eur": str(recovered_cogs_eur),
            "net_cogs_eur": str(net_cogs_eur),
            "fulfillment_eur": str(fulfillment_eur),
            "contribution_eur": str(contribution_eur),
            "returned_units": int(ret["returned_units"]),
            "restocked_units": int(ret["restocked_units"]),
            "refund_local": str(ret["refund_local"]),
        })
    stats = {
        "calculated_orders": len(out),
        "missing_fx_orders": missing_fx,
        "missing_unit_cost_orders": missing_cost,
        "zero_gross_sales_orders_included": zero_price_order_ids,
    }
    return out, stats


def add_decimal(target: dict[str, Decimal], key: str, value: Any) -> None:
    target[key] += dec(value, ZERO) or ZERO


def aggregate_rows(order_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    numeric_money = ["gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"]
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for country in COUNTRIES:
        for month in MONTHS:
            grouped[(country, month)] = {
                "country": country,
                "month": month,
                "shipped_orders": 0,
                "shipped_units": 0,
                "returned_units": 0,
                **{k: ZERO for k in numeric_money},
            }
    for row in order_rows:
        g = grouped[(row["country"], row["month"])]
        g["shipped_orders"] += 1
        g["shipped_units"] += int(row["quantity"])
        g["returned_units"] += int(row["returned_units"])
        add_decimal(g, "gross_sales_eur", row["gross_sales_eur"])
        add_decimal(g, "refunds_eur", row["refunds_eur"])
        add_decimal(g, "net_cogs_eur", row["net_cogs_eur"])
        add_decimal(g, "fulfillment_eur", row["fulfillment_eur"])
        add_decimal(g, "contribution_eur", row["contribution_eur"])
    monthly: list[dict[str, Any]] = []
    for key in sorted(grouped):
        g = grouped[key]
        g["net_sales_eur"] = money(g["gross_sales_eur"] - g["refunds_eur"])
        g["gross_sales_eur"] = money(g["gross_sales_eur"])
        g["refunds_eur"] = money(g["refunds_eur"])
        g["net_cogs_eur"] = money(g["net_cogs_eur"])
        g["fulfillment_eur"] = money(g["fulfillment_eur"])
        g["contribution_eur"] = money(g["contribution_eur"])
        g["margin"] = (g["contribution_eur"] / g["net_sales_eur"]) if g["net_sales_eur"] != 0 else None
        monthly.append(g)
    country_groups: dict[str, dict[str, Any]] = {}
    for country in COUNTRIES:
        rows = [r for r in monthly if r["country"] == country]
        g: dict[str, Any] = {"country": country, "shipped_orders": 0, "shipped_units": 0, "returned_units": 0, **{k: ZERO for k in numeric_money}}
        for r in rows:
            g["shipped_orders"] += r["shipped_orders"]
            g["shipped_units"] += r["shipped_units"]
            g["returned_units"] += r["returned_units"]
            for k in numeric_money:
                add_decimal(g, k, r[k])
        g["net_sales_eur"] = money(g["gross_sales_eur"] - g["refunds_eur"])
        for k in numeric_money:
            g[k] = money(g[k])
        g["margin"] = (g["contribution_eur"] / g["net_sales_eur"]) if g["net_sales_eur"] != 0 else None
        country_groups[country] = g
    countries = [country_groups[c] for c in COUNTRIES]
    reconcile_issues: list[str] = []
    for country in COUNTRIES:
        c = country_groups[country]
        for k in ["shipped_orders", "shipped_units", "returned_units"] + numeric_money:
            v = sum((r[k] for r in monthly if r["country"] == country), 0 if k in {"shipped_orders", "shipped_units", "returned_units"} else ZERO)
            if v != c[k]:
                reconcile_issues.append(f"{country}:{k}:{v}!={c[k]}")
    stats = {"monthly_row_count": len(monthly), "country_row_count": len(countries), "reconciliation_issues": reconcile_issues}
    return monthly, countries, stats


def json_ready_aggregate(rows: list[dict[str, Any]], has_month: bool) -> list[dict[str, Any]]:
    fields = ["country"] + (["month"] if has_month else []) + [
        "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"
    ]
    out: list[dict[str, Any]] = []
    for row in rows:
        x: dict[str, Any] = {}
        for k in fields:
            v = row.get(k)
            if k == "margin" and v is not None:
                x[k] = float(v)
            elif isinstance(v, Decimal):
                x[k] = iso_decimal(v, 2)
            else:
                x[k] = v
        out.append(x)
    return out


def csv_aggregate_value(key: str, value: Any) -> Any:
    if key == "margin" and value is not None:
        return float(value)
    if isinstance(value, Decimal):
        return iso_decimal(value, 2)
    return value


def market_context() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pop_meta, pop_rows = json.loads((RAW / "population.json").read_text(encoding="utf-8"))
    gdp_meta, gdp_rows = json.loads((RAW / "gdp-per-capita.json").read_text(encoding="utf-8"))
    pop = {(r.get("countryiso3code"), int(r.get("date"))): r.get("value") for r in pop_rows}
    gdp = {(r.get("countryiso3code"), int(r.get("date"))): r.get("value") for r in gdp_rows}
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for country in COUNTRIES:
        for year in [2022, 2023, 2024]:
            p = pop.get((country, year))
            g = gdp.get((country, year))
            if p is None or g is None:
                missing.append({"country": country, "year": year, "population_missing": p is None, "gdp_per_capita_missing": g is None})
            rows.append({"country": country, "year": year, "population": p, "gdp_per_capita_usd": g})
    meta = {
        "population_indicator": "SP.POP.TOTL",
        "population_units": "persons",
        "gdp_indicator": "NY.GDP.PCAP.CD",
        "gdp_units": "current US$ per person",
        "world_bank_population_lastupdated": pop_meta.get("lastupdated"),
        "world_bank_gdp_lastupdated": gdp_meta.get("lastupdated"),
        "missing_values": missing,
        "source_urls": {
            "population": "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&format=json&per_page=1000",
            "gdp_per_capita": "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&format=json&per_page=1000",
        },
        "interpretation": "Population and GDP per capita are context indicators, not direct proof of replacement-assembly demand.",
    }
    return rows, meta


def options_and_scenarios(countries: list[dict[str, Any]], options_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metrics = {r["country"]: r for r in countries}
    options = {r["country"]: {
        "country": r["country"], "capex_eur": dec(r["capex_eur"], ZERO) or ZERO,
        "fte": int(r["fte"]), "annual_fixed_eur": dec(r["annual_fixed_eur"], ZERO) or ZERO,
        "saving_eur_per_unit": dec(r["saving_eur_per_unit"], ZERO) or ZERO,
    } for r in options_rows}
    # Retain all individual options and only pairs inside the board caps.
    alternatives: list[dict[str, Any]] = []
    for country in COUNTRIES:
        alternatives.append({"option": country, "members": [country], "feasible": True})
    pair_rejections: list[dict[str, Any]] = []
    for i, left in enumerate(COUNTRIES):
        for right in COUNTRIES[i + 1:]:
            members = [left, right]
            capex = sum((options[x]["capex_eur"] for x in members), ZERO)
            fte = sum(options[x]["fte"] for x in members)
            feasible = capex <= Decimal("450000") and fte <= 7
            item = {"option": f"{left}+{right}", "members": members, "feasible": feasible, "capex_eur": capex, "fte": fte}
            if feasible:
                alternatives.append(item)
            else:
                pair_rejections.append(item)
    scenarios: list[dict[str, Any]] = []
    for alt in alternatives:
        members = alt["members"]
        capex = sum((options[x]["capex_eur"] for x in members), ZERO)
        fte = sum(options[x]["fte"] for x in members)
        fixed = sum((options[x]["annual_fixed_eur"] for x in members), ZERO)
        saving = sum((options[x]["saving_eur_per_unit"] for x in members), ZERO)
        C = sum((dec(metrics[x]["contribution_eur"], ZERO) or ZERO for x in members), ZERO)
        U = sum(int(metrics[x]["shipped_units"]) for x in members)
        G = sum((dec(metrics[x]["gross_sales_eur"], ZERO) or ZERO for x in members), ZERO)
        N = sum((dec(metrics[x]["net_sales_eur"], ZERO) or ZERO for x in members), ZERO)
        fx_shock = sum((Decimal("0.10") * (dec(metrics[x]["net_sales_eur"], ZERO) or ZERO) for x in members if x in {"POL", "CZE"}), ZERO)
        c_stress = C - Decimal("0.03") * G - fx_shock
        for scenario, uplift in [("low", Decimal("0.10")), ("base", Decimal("0.25")), ("high", Decimal("0.40"))]:
            incremental = C * uplift + Decimal(U) * (Decimal("1") + uplift) * saving - fixed
            payback = capex / incremental if incremental > 0 else None
            scenarios.append({
                "country": alt["option"], "scenario": scenario,
                "incremental_contribution_eur": iso_decimal(incremental, 2),
                "capex_eur": iso_decimal(capex, 2), "fte": fte,
                "payback_years": float(payback) if payback is not None else None,
                "option_type": "pair" if len(members) == 2 else "country",
                "members": "+".join(members), "baseline_contribution_eur": iso_decimal(C, 2),
                "shipped_units": U, "gross_sales_eur": iso_decimal(G, 2), "net_sales_eur": iso_decimal(N, 2),
                "annual_fixed_eur": iso_decimal(fixed, 2), "saving_eur_per_unit": iso_decimal(saving, 2),
                "volume_uplift": float(uplift), "stress_fx_shock_eur": iso_decimal(fx_shock, 2),
            })
        stress_incremental = c_stress * Decimal("1.25") - C + Decimal(U) * Decimal("1.25") * saving - fixed
        stress_payback = capex / stress_incremental if stress_incremental > 0 else None
        scenarios.append({
            "country": alt["option"], "scenario": "stress",
            "incremental_contribution_eur": iso_decimal(stress_incremental, 2),
            "capex_eur": iso_decimal(capex, 2), "fte": fte,
            "payback_years": float(stress_payback) if stress_payback is not None else None,
            "option_type": "pair" if len(members) == 2 else "country",
            "members": "+".join(members), "baseline_contribution_eur": iso_decimal(C, 2),
            "shipped_units": U, "gross_sales_eur": iso_decimal(G, 2), "net_sales_eur": iso_decimal(N, 2),
            "annual_fixed_eur": iso_decimal(fixed, 2), "saving_eur_per_unit": iso_decimal(saving, 2),
            "volume_uplift": 0.25, "stress_fx_shock_eur": iso_decimal(fx_shock, 2),
            "stress_refund_shock_eur": iso_decimal(Decimal("0.03") * G, 2),
            "stress_contribution_baseline_eur": iso_decimal(c_stress, 2),
        })
    # Defer is explicit in the comparison, even though it is not a hub row.
    for scenario in ["low", "base", "high", "stress"]:
        scenarios.append({
            "country": "DEFER", "scenario": scenario, "incremental_contribution_eur": 0.0,
            "capex_eur": 0.0, "fte": 0, "payback_years": None, "option_type": "defer", "members": "",
            "baseline_contribution_eur": 0.0, "shipped_units": 0, "gross_sales_eur": 0.0, "net_sales_eur": 0.0,
            "annual_fixed_eur": 0.0, "saving_eur_per_unit": 0.0, "volume_uplift": None,
        })
    scenario_meta = {
        "policy": {
            "max_capex_eur": 450000,
            "max_fte": 7,
            "low_uplift": 0.10, "base_uplift": 0.25, "high_uplift": 0.40,
            "stress_refund_shock_rate_of_gross_sales": 0.03,
            "stress_fx_shock_rate_of_net_sales_for_pln_czk": 0.10,
            "formula": "annual incremental = C*u + U*(1+u)*s - F; stress = C_stress*1.25 - C + U*1.25*s - F",
        },
        "feasible_pairs": [x["option"] for x in alternatives if len(x["members"]) == 2],
        "infeasible_pairs": [{"option": x["option"], "capex_eur": iso_decimal(x["capex_eur"], 2), "fte": x["fte"]} for x in pair_rejections],
    }
    return scenarios, scenario_meta


def choose_recommendation(scenarios: list[dict[str, Any]], options_rows: list[dict[str, str]]) -> dict[str, Any]:
    """Select the most resilient feasible pair under the stated stress.

    The rule is deliberately visible: eligible pairs must be positive in low,
    base, high and stress; rank first on stress contribution, then on base
    contribution.  This is a risk-adjusted board choice, not a statistical
    estimate of demand.
    """
    by_option: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in scenarios:
        if row.get("option_type") == "pair":
            by_option[row["country"]][row["scenario"]] = row
    candidates: list[dict[str, Any]] = []
    for option, rows in by_option.items():
        if all(s in rows and float(rows[s]["incremental_contribution_eur"]) > 0 for s in ["low", "base", "high", "stress"]):
            candidates.append({
                "option": option,
                "stress": float(rows["stress"]["incremental_contribution_eur"]),
                "base": float(rows["base"]["incremental_contribution_eur"]),
                "low": float(rows["low"]["incremental_contribution_eur"]),
                "high": float(rows["high"]["incremental_contribution_eur"]),
                "rows": rows,
            })
    candidates.sort(key=lambda x: (x["stress"], x["base"]), reverse=True)
    selected = candidates[0]
    members = selected["option"].split("+")
    option_map = {r["country"]: r for r in options_rows}
    capex = sum(float(option_map[m]["capex_eur"]) for m in members)
    fte = sum(int(option_map[m]["fte"]) for m in members)
    base_alt = max((x for x in candidates if x["option"] != selected["option"]), key=lambda x: x["base"], default=None)
    return {
        "countries": members,
        "option": selected["option"],
        "capex_eur": capex,
        "fte": fte,
        "rationale": "Recommend the risk-adjusted feasible pair with positive low/base/high/stress economics and the strongest defined-stress incremental contribution. This is an assumption-led scenario choice, not a statistically proven or causal demand forecast.",
        "decision_rule": "Feasible pair; positive incremental contribution in all four modeled scenarios; rank by stress contribution, then base contribution.",
        "selected_scenarios": {k: {"incremental_contribution_eur": v["incremental_contribution_eur"], "payback_years": v["payback_years"]} for k, v in selected["rows"].items()},
        "strongest_base_alternative": None if base_alt is None else {
            "option": base_alt["option"],
            "incremental_contribution_eur": base_alt["base"],
            "stress_incremental_contribution_eur": base_alt["stress"],
            "comparison_note": "Higher base case but lower defined-stress result; it includes a PLN/CZK market and therefore receives the policy's 10% net-sales FX shock.",
        },
        "budget_headroom": {"capex_eur": 450000 - capex, "fte": 7 - fte},
        "alternatives_positive_all_scenarios": [x["option"] for x in candidates],
    }


def source_register() -> list[dict[str, Any]]:
    supplied = json.loads((RAW / "source-register.json").read_text(encoding="utf-8"))
    public_by_file = {r["file"]: r for r in supplied.get("public", [])}
    descriptions = {
        "data-dictionary.md": ("rules and definitions", "2025 shipment/return accounting; cutoff 2026-01-31", "synthetic_client_metadata"),
        "hub-options.csv": ("capex EUR; FTE; annual fixed EUR; saving EUR/unit", "2025 option assumptions", "synthetic_client_assumption"),
        "order-corrections.csv": ("one corrected order/SKU row; local price/currency; fulfillment EUR", "2025 orders", "synthetic_client_export_correction"),
        "orders-part1.csv": ("one order/SKU row; local price/currency; fulfillment EUR", "2025 and out-of-period order extract", "synthetic_client_export"),
        "orders-part2.csv": ("one order/SKU row; local price/currency; fulfillment EUR", "2025 and out-of-period order extract", "synthetic_client_export"),
        "returns.csv": ("one return ID; units; restocked units; refund in original currency", "2025-01-28 to 2026-02-01", "synthetic_client_export"),
        "scenario-policy.md": ("policy formulas and constraints", "2025 baseline scenario assumptions", "synthetic_client_assumption"),
        "unit-costs.csv": ("EUR/unit", "effective dates from 2025-01-01", "synthetic_client_assumption"),
        "source-register.json": ("provenance metadata", "archive vintage and synthetic seed", "synthetic_client_metadata"),
        "source-room-index.html": ("source-room index", "collection index", "synthetic_client_metadata"),
        "population.json": ("persons", "2022-2024", "official_public_snapshot_archived"),
        "gdp-per-capita.json": ("current US$ per person", "2022-2024", "official_public_snapshot_archived"),
        "ecb-history.zip": ("local currency units per EUR", "1999-01-04 to archive vintage", "official_public_snapshot_archived"),
        "ecb-history.csv": ("local currency units per EUR", "1999-01-04 to archive vintage; lossless ZIP extraction", "official_public_snapshot_archived"),
    }
    rows: list[dict[str, Any]] = []
    for path in sorted(RAW.iterdir()):
        if not path.is_file():
            continue
        name = path.name
        units, period, status = descriptions.get(name, ("see file", "see file", "source_room"))
        p = public_by_file.get(name, {})
        original_url = p.get("original_url", BASE_URL + quote(name))
        retrieval = p.get("retrieved_utc", file_retrieved_utc(path))
        provenance = p.get("transformation", "direct download from frozen source room")
        if name == "ecb-history.csv":
            provenance = "lossless ZIP extraction / source-room derivative; preserved as served"
        rows.append({
            "file": name,
            "original_url": original_url,
            "retrieved_utc": retrieval,
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
            "units": units,
            "period": period,
            "status": status,
            "provenance": provenance,
        })
    return rows


def export_register(rows: list[dict[str, Any]]) -> None:
    (ROOT / "evidence" / "source-register.json").write_text(json.dumps({"sources": rows}, indent=2) + "\n", encoding="utf-8")
    write_csv(ROOT / "evidence" / "source-register.csv", rows, ["file", "original_url", "retrieved_utc", "sha256", "bytes", "units", "period", "status", "provenance"])


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    DELIVERABLES.mkdir(parents=True, exist_ok=True)
    orders, order_stats = read_orders()
    returns, return_stats = read_returns()
    fx, fx_rows, fx_stats = fx_means()
    costs, _ = unit_cost_lookup()
    eligible, returns_by_order, cleaning_stats = clean_order_and_return_data(orders, returns, order_stats, return_stats)
    order_rows, calc_stats = calculate_orders(eligible, returns_by_order, fx, costs)
    monthly, countries, aggregation_stats = aggregate_rows(order_rows)
    market_rows, market_meta = market_context()
    options_rows = read_csv(RAW / "hub-options.csv")
    scenarios, scenario_meta = options_and_scenarios(countries, options_rows)
    recommendation = choose_recommendation(scenarios, options_rows)
    register_rows = source_register()
    export_register(register_rows)

    # Intermediate tables retain auditable precision as strings for money and
    # make the workbook/report reproducible without rereading raw extracts.
    order_fields = [
        "order_id", "revision", "country", "month", "shipped_at", "sku", "currency", "quantity",
        "unit_price_local", "discount_local", "fx_local_per_eur", "unit_cost_eur", "gross_sales_eur",
        "refunds_eur", "gross_cogs_eur", "recovered_cogs_eur", "net_cogs_eur", "fulfillment_eur",
        "contribution_eur", "returned_units", "restocked_units", "refund_local",
    ]
    write_csv(PROCESSED / "order_level.csv", order_rows, order_fields)
    write_csv(PROCESSED / "monthly.csv", [{k: csv_aggregate_value(k, v) for k, v in r.items()} for r in monthly], ["country", "month", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"])
    write_csv(PROCESSED / "countries.csv", [{k: csv_aggregate_value(k, v) for k, v in r.items()} for r in countries], ["country", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"])
    write_csv(PROCESSED / "fx_monthly.csv", fx_rows, ["currency", "month", "local_per_eur", "business_days"])
    write_csv(PROCESSED / "market_context.csv", market_rows, ["country", "year", "population", "gdp_per_capita_usd"])
    write_csv(PROCESSED / "hub_scenarios.csv", scenarios, ["country", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years", "option_type", "members", "baseline_contribution_eur", "shipped_units", "gross_sales_eur", "net_sales_eur", "annual_fixed_eur", "saving_eur_per_unit", "volume_uplift", "stress_fx_shock_eur", "stress_refund_shock_eur", "stress_contribution_baseline_eur"])
    write_csv(PROCESSED / "hub_options.csv", options_rows, list(options_rows[0].keys()))

    # Full quality notes are deliberately verbose: they are also consumed by
    # the report and workbook.
    quality = {
        "source_room": "Frozen local source room; client exports and assumptions are synthetic; official series are archived snapshots.",
        "accounting_cutoff": "2026-01-31 inclusive for returns; only 2025 shipped_at orders enter the base.",
        "order_handling": cleaning_stats,
        "calculation": calc_stats,
        "fx": fx_stats,
        "aggregation": aggregation_stats,
        "market": market_meta,
        "scenario": scenario_meta,
        "rounding": "Gross sales, refunds, gross/recovered/net COGS, fulfillment and contribution are rounded per eligible order to EUR cents with Decimal ROUND_HALF_UP before summing. Refunds use original sale month FX, not receipt month.",
        "zero_price_handling": "Valid zero-gross-sales shipments remain in shipped orders/units; they contribute zero gross sales but retain costs and can have negative contribution.",
        "return_handling": "Highest return revision retained; exact repeats removed; included only for eligible 2025 orders and received_at through 2026-01-31; orphan and after-cutoff records quarantined.",
        "missing_values": {
            "order_rows": sum(1 for row in orders if any(row.get(k, "") == "" for k in ["country", "shipped_at", "currency", "quantity"])),
            "market_context": market_meta["missing_values"],
        },
        "limitations": [
            "Synthetic order/return history and hub assumptions are not measured demand or causal evidence.",
            "ECB reference rates are analytical translation assumptions, not the actual transaction rates or hedging outcomes.",
            "Scenario arithmetic is undiscounted and excludes taxes, working capital, ramp timing, shared fixed costs, and synergy; pairs are additive with no synergy.",
            "World Bank GDP per capita is current US$, not PPP or constant-price real income, and neither GDP nor population proves product demand.",
        ],
    }
    metrics = {
        "monthly": json_ready_aggregate(monthly, True),
        "countries": json_ready_aggregate(countries, False),
        "fx_monthly": [{"currency": r["currency"], "month": r["month"], "local_per_eur": r["local_per_eur"]} for r in fx_rows],
        "market_context": [{"country": r["country"], "year": r["year"], "population": r["population"], "gdp_per_capita_usd": r["gdp_per_capita_usd"]} for r in market_rows],
        "hub_scenarios": [{"country": r["country"], "scenario": r["scenario"], "incremental_contribution_eur": r["incremental_contribution_eur"], "capex_eur": r["capex_eur"], "fte": r["fte"], "payback_years": r["payback_years"]} for r in scenarios],
        "recommendation": {
            **recommendation,
        },
        "quality": quality,
        "metadata": {
            "client": "Meridian Parts (synthetic)",
            "analysis_period": "2025 shipped sales; returns known through 2026-01-31",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "country_names": COUNTRY_NAMES,
            "source_register": "evidence/source-register.json",
            "processed_tables": "analysis/processed/",
        },
    }
    (DELIVERABLES / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (PROCESSED / "quality.json").write_text(json.dumps(quality, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "orders_selected": len(orders), "eligible_orders": len(eligible), "calculated_orders": len(order_rows),
        "returns_selected": len(returns), "monthly_rows": len(monthly), "countries": len(countries),
        "scenario_rows": len(scenarios), "feasible_pairs": scenario_meta["feasible_pairs"],
        "infeasible_pairs": scenario_meta["infeasible_pairs"], "quality": quality,
    }, indent=2, default=str))


if __name__ == "__main__":
    main()
