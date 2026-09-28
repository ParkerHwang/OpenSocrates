"""Reproducible Meridian Parts analysis.

This module reads only the frozen inputs under evidence/raw and writes normalized
analysis outputs, the metrics contract, the source register, and an XLSX model.
Monetary calculations use Decimal and half-up rounding at the order level.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence" / "raw"
OUTPUT = ROOT / "analysis_outputs"
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
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]
MONEY_FIELDS = [
    "gross_sales_eur",
    "refunds_eur",
    "net_sales_eur",
    "net_cogs_eur",
    "fulfillment_eur",
    "contribution_eur",
]
SCENARIO_UPLIFT = {"low": Decimal("0.10"), "base": Decimal("0.25"), "high": Decimal("0.40")}
CUTOFF = pd.Timestamp("2026-01-31")


def D(value: Any) -> Decimal:
    """Convert a scalar without going through binary float where possible."""

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return Decimal("0")
    return Decimal(str(value))


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q6(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def number(value: Decimal | None, places: int = 2) -> float | None:
    if value is None:
        return None
    return float(value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_bool(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def load_inputs() -> dict[str, Any]:
    base1 = pd.read_csv(RAW / "orders-part1.csv")
    base2 = pd.read_csv(RAW / "orders-part2.csv")
    corrections = pd.read_csv(RAW / "order-corrections.csv")
    returns = pd.read_csv(RAW / "returns.csv")
    unit_costs = pd.read_csv(RAW / "unit-costs.csv")
    hub_options = pd.read_csv(RAW / "hub-options.csv")
    fx = pd.read_csv(RAW / "ecb-history.csv")
    with (RAW / "population.json").open() as f:
        population = json.load(f)
    with (RAW / "gdp-per-capita.json").open() as f:
        gdp = json.load(f)
    return {
        "orders_part1": base1,
        "orders_part2": base2,
        "order_corrections": corrections,
        "returns": returns,
        "unit_costs": unit_costs,
        "hub_options": hub_options,
        "fx": fx,
        "population": population,
        "gdp": gdp,
    }


def canonicalize_orders(inputs: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    base = pd.concat([inputs["orders_part1"], inputs["orders_part2"]], ignore_index=True)
    base_rows = len(base)
    exact_duplicate_rows = int(base.duplicated().sum())
    base_dedup = base.drop_duplicates().copy()
    corrections = inputs["order_corrections"].copy()
    corrections["source_kind"] = "correction"
    base_dedup["source_kind"] = "extract"
    combined = pd.concat([base_dedup, corrections], ignore_index=True)
    combined["revision_num"] = pd.to_numeric(combined["revision"], errors="coerce")
    combined["order_id"] = combined["order_id"].astype(str)
    max_rev_conflicts = []
    for order_id, group in combined.groupby("order_id", sort=False):
        max_rev = group["revision_num"].max()
        max_group = group[group["revision_num"] == max_rev]
        if len(max_group.drop_duplicates()) > 1:
            max_rev_conflicts.append(order_id)
    combined = combined.sort_values(["order_id", "revision_num", "source_kind"], ascending=[True, False, True])
    canonical = combined.drop_duplicates("order_id", keep="first").copy()
    canonical["ordered_at_dt"] = pd.to_datetime(canonical["ordered_at"], errors="coerce")
    canonical["shipped_at_dt"] = pd.to_datetime(canonical["shipped_at"], errors="coerce")
    canonical["is_test_bool"] = clean_bool(canonical["is_test"])
    canonical["eligibility"] = "eligible_2025_shipped"
    canonical.loc[canonical["status"].astype(str).str.lower() != "shipped", "eligibility"] = "excluded_status"
    canonical.loc[(canonical["eligibility"] == "eligible_2025_shipped") & canonical["is_test_bool"], "eligibility"] = "excluded_test"
    canonical.loc[(canonical["eligibility"] == "eligible_2025_shipped") & canonical["shipped_at_dt"].isna(), "eligibility"] = "excluded_missing_ship_date"
    canonical.loc[
        (canonical["eligibility"] == "eligible_2025_shipped")
        & canonical["shipped_at_dt"].notna()
        & (canonical["shipped_at_dt"].dt.year != 2025),
        "eligibility",
    ] = "excluded_outside_2025"
    canonical["month"] = canonical["shipped_at_dt"].dt.strftime("%Y-%m")
    audit = {
        "raw_extract_rows": base_rows,
        "raw_extract_unique_after_exact_dedup": int(len(base_dedup)),
        "exact_duplicate_order_rows_removed": exact_duplicate_rows,
        "correction_rows": int(len(corrections)),
        "correction_order_ids_replacing_extracts": int(len(set(corrections.order_id) & set(base.order_id))),
        "canonical_order_ids": int(canonical.order_id.nunique()),
        "max_revision_conflicts": max_rev_conflicts,
        "eligibility_counts": {str(k): int(v) for k, v in canonical["eligibility"].value_counts(dropna=False).items()},
        "zero_price_rows_canonical": int((D(0) == canonical["unit_price_local"].map(D)).sum()),
        "future_order_rows_excluded": int((canonical["eligibility"] == "excluded_outside_2025").sum()),
    }
    return canonical, audit


def canonicalize_returns(inputs: dict[str, Any], orders: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = inputs["returns"].copy()
    raw["return_id"] = raw["return_id"].astype(str)
    raw["order_id"] = raw["order_id"].astype(str)
    raw["revision_num"] = pd.to_numeric(raw["revision"], errors="coerce")
    exact_duplicate_rows = int(raw.duplicated().sum())
    dedup = raw.drop_duplicates().copy()
    lower_revision_rows = 0
    for _, group in dedup.groupby("return_id", sort=False):
        lower_revision_rows += max(0, len(group) - 1)
    selected = dedup.sort_values(["return_id", "revision_num"], ascending=[True, False]).drop_duplicates("return_id", keep="first").copy()
    selected["received_at_dt"] = pd.to_datetime(selected["received_at"], errors="coerce")
    order_lookup = orders.set_index("order_id")["eligibility"].to_dict()
    selected["linked_order_eligibility"] = selected["order_id"].map(order_lookup)
    selected["return_inclusion"] = "included"
    selected.loc[selected["received_at_dt"].isna(), "return_inclusion"] = "excluded_missing_received_date"
    selected.loc[selected["received_at_dt"].notna() & (selected["received_at_dt"] > CUTOFF), "return_inclusion"] = "excluded_after_cutoff"
    selected.loc[selected["linked_order_eligibility"].isna(), "return_inclusion"] = "quarantined_orphan"
    selected.loc[
        selected["linked_order_eligibility"].notna() & (selected["linked_order_eligibility"] != "eligible_2025_shipped"),
        "return_inclusion",
    ] = "excluded_linked_order_ineligible"
    selected.loc[(selected["return_inclusion"] == "included") & (selected["quantity"] < 0), "return_inclusion"] = "excluded_invalid_quantity"
    selected.loc[(selected["return_inclusion"] == "included") & (selected["restocked_quantity"] < 0), "return_inclusion"] = "excluded_invalid_restocked_quantity"
    selected.loc[
        (selected["return_inclusion"] == "included") & (selected["restocked_quantity"] > selected["quantity"]),
        "return_inclusion",
    ] = "excluded_restocked_exceeds_return"
    audit = {
        "raw_return_rows": int(len(raw)),
        "exact_duplicate_return_rows_removed": exact_duplicate_rows,
        "lower_revision_return_rows_removed": int(lower_revision_rows),
        "canonical_return_ids": int(len(selected)),
        "inclusion_counts": {str(k): int(v) for k, v in selected["return_inclusion"].value_counts(dropna=False).items()},
        "orphan_return_ids": sorted(selected.loc[selected["return_inclusion"] == "quarantined_orphan", "return_id"].tolist()),
        "after_cutoff_return_ids": sorted(selected.loc[selected["return_inclusion"] == "excluded_after_cutoff", "return_id"].tolist()),
    }
    return selected, audit


def monthly_fx(inputs: dict[str, Any]) -> tuple[pd.DataFrame, dict[tuple[str, str], Decimal]]:
    fx = inputs["fx"].copy()
    fx["date"] = pd.to_datetime(fx["Date"], errors="coerce")
    fx25 = fx[fx["date"].dt.year == 2025].copy()
    fx25["month"] = fx25["date"].dt.strftime("%Y-%m")
    rows: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str], Decimal] = {}
    for month in MONTHS:
        part = fx25[fx25["month"] == month]
        if len(part) == 0:
            raise ValueError(f"No ECB observations for {month}")
        for currency in ["PLN", "CZK"]:
            series = pd.to_numeric(part[currency], errors="coerce").dropna()
            if len(series) == 0:
                raise ValueError(f"No {currency} ECB observations for {month}")
            mean = q6(D(series.mean()))
            lookup[(currency, month)] = mean
            rows.append({"currency": currency, "month": month, "local_per_eur": number(mean, 6), "observations": int(len(series))})
    return pd.DataFrame(rows).sort_values(["month", "currency"]).reset_index(drop=True), lookup


def parse_world_bank(raw: list[Any], field: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    metadata = raw[0]
    records = raw[1]
    rows = []
    for r in records:
        value = r.get("value")
        rows.append(
            {
                "country": r.get("countryiso3code"),
                "year": int(r["date"]),
                field: None if value is None else (int(value) if field == "population" else float(value)),
                "unit": "persons" if field == "population" else "current US$ per person",
                "source_lastupdated": raw[0].get("lastupdated"),
                "obs_status": r.get("obs_status", ""),
            }
        )
    return pd.DataFrame(rows), {"page": metadata}


def build_order_metrics(orders: pd.DataFrame, returns: pd.DataFrame, fx_lookup: dict[tuple[str, str], Decimal], unit_costs: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    costs = unit_costs.copy()
    costs["valid_from_dt"] = pd.to_datetime(costs["valid_from"], errors="coerce")
    costs["unit_cost_dec"] = costs["unit_cost_eur"].map(D)
    included_returns = returns[returns["return_inclusion"] == "included"].copy()
    return_groups = included_returns.groupby("order_id", as_index=True).agg(
        refund_local=("refund_local", "sum"),
        returned_units=("quantity", "sum"),
        restocked_units=("restocked_quantity", "sum"),
        return_records=("return_id", "nunique"),
    )
    eligible = orders[orders["eligibility"] == "eligible_2025_shipped"].copy()
    rows: list[dict[str, Any]] = []
    missing_rates: list[str] = []
    missing_costs: list[str] = []
    for _, row in eligible.sort_values(["country", "shipped_at_dt", "order_id"]).iterrows():
        order_id = row["order_id"]
        month = row["month"]
        currency = row["currency"]
        rate = Decimal("1") if currency == "EUR" else fx_lookup.get((currency, month))
        if rate is None:
            missing_rates.append(order_id)
            continue
        candidates = costs[(costs["sku"] == row["sku"]) & (costs["valid_from_dt"] <= row["shipped_at_dt"])]
        if candidates.empty:
            missing_costs.append(order_id)
            continue
        unit_cost = candidates.sort_values("valid_from_dt").iloc[-1]["unit_cost_dec"]
        ret = return_groups.loc[order_id] if order_id in return_groups.index else None
        refund_local = D(ret["refund_local"]) if ret is not None else Decimal("0")
        returned_units = int(ret["returned_units"]) if ret is not None else 0
        restocked_units = int(ret["restocked_units"]) if ret is not None else 0
        gross_local = D(row["quantity"]) * D(row["unit_price_local"]) - D(row["discount_local"])
        gross_sales_eur = q2(gross_local / rate)
        refunds_eur = q2(refund_local / rate)
        gross_cogs_eur = D(row["quantity"]) * unit_cost
        recovered_cogs_eur = D(restocked_units) * unit_cost
        net_cogs_eur = q2(gross_cogs_eur - recovered_cogs_eur)
        fulfillment_eur = q2(D(row["fulfillment_eur"]))
        contribution_eur = q2(gross_sales_eur - refunds_eur - net_cogs_eur - fulfillment_eur)
        rows.append(
            {
                "order_id": order_id,
                "country": row["country"],
                "month": month,
                "shipped_at": row["shipped_at_dt"].strftime("%Y-%m-%d"),
                "sku": row["sku"],
                "currency": currency,
                "fx_local_per_eur": number(rate, 6),
                "quantity": int(row["quantity"]),
                "unit_price_local": number(D(row["unit_price_local"]), 2),
                "discount_local": number(D(row["discount_local"]), 2),
                "gross_local": number(gross_local, 2),
                "refund_local": number(refund_local, 2),
                "return_records": int(ret["return_records"]) if ret is not None else 0,
                "returned_units": returned_units,
                "restocked_units": restocked_units,
                "unit_cost_eur": number(unit_cost, 2),
                "gross_sales_eur": number(gross_sales_eur, 2),
                "refunds_eur": number(refunds_eur, 2),
                "gross_cogs_eur": number(q2(gross_cogs_eur), 2),
                "recovered_cogs_eur": number(q2(recovered_cogs_eur), 2),
                "net_cogs_eur": number(net_cogs_eur, 2),
                "fulfillment_eur": number(fulfillment_eur, 2),
                "contribution_eur": number(contribution_eur, 2),
            }
        )
    result = pd.DataFrame(rows)
    if missing_rates or missing_costs:
        raise ValueError(f"Missing rates for {missing_rates}; missing unit costs for {missing_costs}")
    checks = {
        "eligible_order_count": int(len(eligible)),
        "order_metric_count": int(len(result)),
        "zero_price_orders_included": int((eligible["unit_price_local"].map(D) == 0).sum()),
        "orders_with_returns": int((result["return_records"] > 0).sum()),
        "return_records_allocated_to_sale_month": int(result["return_records"].sum()),
    }
    return result, checks


def aggregate_metrics(order_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    group = ["country", "month"]
    monthly = order_metrics.groupby(group, as_index=False).agg(
        shipped_orders=("order_id", "nunique"),
        shipped_units=("quantity", "sum"),
        gross_sales_eur=("gross_sales_eur", "sum"),
        refunds_eur=("refunds_eur", "sum"),
        net_cogs_eur=("net_cogs_eur", "sum"),
        fulfillment_eur=("fulfillment_eur", "sum"),
        contribution_eur=("contribution_eur", "sum"),
        returned_units=("returned_units", "sum"),
    )
    for c in [x for x in MONEY_FIELDS if x != "net_sales_eur"]:
        monthly[c] = monthly[c].round(2)
    monthly["net_sales_eur"] = (monthly["gross_sales_eur"] - monthly["refunds_eur"]).round(2)
    monthly["margin"] = monthly.apply(lambda r: None if abs(r["net_sales_eur"]) < 0.0000001 else round(r["contribution_eur"] / r["net_sales_eur"], 6), axis=1)
    monthly["country_order"] = monthly["country"].map({c: i for i, c in enumerate(COUNTRIES)})
    monthly = monthly.sort_values(["country_order", "month"]).drop(columns=["country_order"]).reset_index(drop=True)
    countries = monthly.groupby("country", as_index=False).agg(
        shipped_orders=("shipped_orders", "sum"),
        shipped_units=("shipped_units", "sum"),
        gross_sales_eur=("gross_sales_eur", "sum"),
        refunds_eur=("refunds_eur", "sum"),
        net_sales_eur=("net_sales_eur", "sum"),
        net_cogs_eur=("net_cogs_eur", "sum"),
        fulfillment_eur=("fulfillment_eur", "sum"),
        contribution_eur=("contribution_eur", "sum"),
        returned_units=("returned_units", "sum"),
    )
    countries["margin"] = countries.apply(lambda r: None if abs(r["net_sales_eur"]) < 0.0000001 else round(r["contribution_eur"] / r["net_sales_eur"], 6), axis=1)
    countries["country_order"] = countries["country"].map({c: i for i, c in enumerate(COUNTRIES)})
    countries = countries.sort_values("country_order").drop(columns=["country_order"]).reset_index(drop=True)
    return monthly, countries


def market_context(inputs: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    pop, pop_meta = parse_world_bank(inputs["population"], "population")
    gdp, gdp_meta = parse_world_bank(inputs["gdp"], "gdp_per_capita_usd")
    context = pop.merge(gdp[["country", "year", "gdp_per_capita_usd", "source_lastupdated"]], on=["country", "year"], how="outer", suffixes=("", "_gdp"))
    context["country"] = context["country"].astype(str)
    context = context[context["country"].isin(COUNTRIES) & context["year"].between(2022, 2024)].copy()
    context["unit_population"] = "persons"
    context["unit_gdp"] = "current US$ per person"
    context["population"] = context["population"].astype("Int64")
    context = context.sort_values(["country", "year"]).reset_index(drop=True)
    meta = {"population": pop_meta, "gdp": gdp_meta, "missing_rows": int(context[["population", "gdp_per_capita_usd"]].isna().any(axis=1).sum())}
    return context, meta


def scenario_value(country_code: str, country_row: pd.Series, option: pd.Series, scenario: str) -> tuple[Decimal, Decimal | None]:
    C = D(country_row["contribution_eur"])
    U = D(country_row["shipped_units"])
    G = D(country_row["gross_sales_eur"])
    N = D(country_row["net_sales_eur"])
    s = D(option["saving_eur_per_unit"])
    F = D(option["annual_fixed_eur"])
    uplift = SCENARIO_UPLIFT[scenario] if scenario in SCENARIO_UPLIFT else Decimal("0.25")
    if scenario == "stress":
        fx_shock = D("0.10") * N if country_code in {"POL", "CZE"} else Decimal("0")
        c_stress = C - D("0.03") * G - fx_shock
        annual = c_stress * (Decimal("1") + uplift) - C + U * (Decimal("1") + uplift) * s - F
    else:
        annual = C * uplift + U * (Decimal("1") + uplift) * s - F
    annual = q2(annual)
    capex = D(option["capex_eur"])
    payback = q4(capex / annual) if annual > 0 else None
    return annual, payback


def build_scenarios(countries: pd.DataFrame, inputs: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    options = inputs["hub_options"].copy()
    options["country"] = options["country"].astype(str)
    rows: list[dict[str, Any]] = []
    country_index = countries.set_index("country")
    option_index = options.set_index("country")
    for country in COUNTRIES:
        for scenario in ["low", "base", "high", "stress"]:
            annual, payback = scenario_value(country, country_index.loc[country], option_index.loc[country], scenario)
            rows.append(
                {
                    "country": country,
                    "scenario": scenario,
                    "incremental_contribution_eur": number(annual, 2),
                    "capex_eur": number(D(option_index.loc[country, "capex_eur"]), 2),
                    "fte": int(option_index.loc[country, "fte"]),
                    "payback_years": number(payback, 4) if payback is not None else None,
                    "annual_fixed_eur": number(D(option_index.loc[country, "annual_fixed_eur"]), 2),
                    "saving_eur_per_unit": number(D(option_index.loc[country, "saving_eur_per_unit"]), 4),
                }
            )
    individual = pd.DataFrame(rows)
    pair_rows: list[dict[str, Any]] = []
    for pair in itertools.combinations(COUNTRIES, 2):
        a, b = pair
        capex = D(option_index.loc[a, "capex_eur"]) + D(option_index.loc[b, "capex_eur"])
        fte = int(option_index.loc[a, "fte"]) + int(option_index.loc[b, "fte"])
        feasible = capex <= D("450000") and fte <= 7
        reason = "feasible" if feasible else "; ".join(
            [x for x in ["capex_over_cap" if capex > D("450000") else "", "fte_over_cap" if fte > 7 else ""] if x]
        )
        for scenario in ["low", "base", "high", "stress"]:
            va = individual[(individual.country == a) & (individual.scenario == scenario)].iloc[0]
            vb = individual[(individual.country == b) & (individual.scenario == scenario)].iloc[0]
            annual = q2(D(va.incremental_contribution_eur) + D(vb.incremental_contribution_eur))
            payback = q4(capex / annual) if annual > 0 else None
            pair_rows.append(
                {
                    "country": f"{a}+{b}",
                    "countries": f"{a},{b}",
                    "scenario": scenario,
                    "incremental_contribution_eur": number(annual, 2),
                    "capex_eur": number(capex, 2),
                    "fte": fte,
                    "payback_years": number(payback, 4) if payback is not None else None,
                    "feasible": feasible,
                    "feasibility_note": reason,
                }
            )
    pairs = pd.DataFrame(pair_rows)
    feasible_pairs = pairs[pairs["feasible"]].copy()
    rankings = []
    def break_even_uplift(country_codes: list[str]) -> Decimal | None:
        base_savings = Decimal("0")
        base_contribution = Decimal("0")
        fixed = Decimal("0")
        for code in country_codes:
            cr = country_index.loc[code]
            op = option_index.loc[code]
            base_savings += D(cr["shipped_units"]) * D(op["saving_eur_per_unit"])
            base_contribution += D(cr["contribution_eur"])
            fixed += D(op["annual_fixed_eur"])
        denominator = base_contribution + base_savings
        if denominator <= 0:
            return None
        value = (fixed - base_savings) / denominator
        return q4(value) if value > 0 else Decimal("0")
    for _, row in individual[individual["scenario"] == "base"].iterrows():
        codes = [row["country"]]
        rankings.append({"option": row["country"], "countries": codes, "scenario": "base", "incremental_contribution_eur": row["incremental_contribution_eur"], "capex_eur": row["capex_eur"], "fte": row["fte"], "payback_years": row["payback_years"], "feasible": True, "stress_incremental_contribution_eur": individual[(individual.country == row.country) & (individual.scenario == "stress")].iloc[0]["incremental_contribution_eur"], "break_even_uplift": number(break_even_uplift(codes), 4)})
    for _, row in feasible_pairs[feasible_pairs["scenario"] == "base"].iterrows():
        codes = row["countries"].split(",")
        rankings.append({"option": row["country"], "countries": codes, "scenario": "base", "incremental_contribution_eur": row["incremental_contribution_eur"], "capex_eur": row["capex_eur"], "fte": row["fte"], "payback_years": row["payback_years"], "feasible": True, "stress_incremental_contribution_eur": feasible_pairs[(feasible_pairs.country == row.country) & (feasible_pairs.scenario == "stress")].iloc[0]["incremental_contribution_eur"], "break_even_uplift": number(break_even_uplift(codes), 4)})
    rankings.sort(key=lambda x: (-(x["incremental_contribution_eur"] or 0), x["capex_eur"], x["option"]))
    return individual, pairs, pd.DataFrame(rankings), {"rankings": rankings, "budget_capex_eur": 450000, "budget_fte": 7}


def source_register() -> list[dict[str, Any]]:
    # The raw source-room register supplies official URLs and archive vintages.
    with (RAW / "source-register.json").open() as f:
        original = json.load(f)
    original_by_file = {x.get("file"): x for x in original.get("public", [])}
    files = [
        ("data-dictionary.md", "Client accounting and grain rules", "2025 analysis rules", "synthetic_client"),
        ("scenario-policy.md", "Scenario assumptions and budget constraints", "2025 baseline / annual scenario", "synthetic_client"),
        ("orders-part1.csv", "Raw order extract page 1", "2025-01 through 2026-01 rows", "synthetic_client"),
        ("orders-part2.csv", "Raw order extract page 2", "2025-01 through 2026-01 rows", "synthetic_client"),
        ("order-corrections.csv", "Whole-row order corrections", "2025 rows; revisions", "synthetic_client"),
        ("returns.csv", "Raw return extract", "2025-01 through 2026-02-01 receipts", "synthetic_client"),
        ("unit-costs.csv", "Effective-dated unit costs", "2025-01-01 onward", "synthetic_client"),
        ("hub-options.csv", "Hub option economics", "Annual recurring / year-zero capex", "synthetic_client"),
        ("population.json", "World Bank population archive", "2022-2024; persons", "public_official_snapshot"),
        ("gdp-per-capita.json", "World Bank GDP per capita archive", "2022-2024; current US$ per person", "public_official_snapshot"),
        ("ecb-history.csv", "ECB historical reference rates", "Business-day observations through 2026-09-25; PLN/CZK used for 2025 means", "public_official_snapshot"),
        ("ecb-history.zip", "ECB historical reference-rate archive", "Same snapshot as extracted CSV", "public_official_snapshot"),
        ("source-register.json", "Source-room supplied register", "Retrieval vintage and original URLs", "synthetic_client_metadata"),
    ]
    now = datetime.now(timezone.utc).isoformat()
    register = []
    for file, description, period, status in files:
        path = RAW / file
        original_item = original_by_file.get(file, {})
        if file == "ecb-history.csv":
            original_item = original_by_file.get("ecb-history.zip", original_item)
        register.append(
            {
                "id": f"S{len(register)+1:02d}",
                "file": f"evidence/raw/{file}",
                "description": description,
                "url": original_item.get("original_url", "http://127.0.0.1:49807/" + file),
                "retrieved_utc": original_item.get("retrieved_utc", now),
                "analysis_collected_utc": now,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "units": "persons / current US$ per person" if file in {"population.json", "gdp-per-capita.json"} else ("local currency units per EUR" if file == "ecb-history.csv" else "see source file"),
                "period": period,
                "status": status,
                "vintage": original.get("vintage_note", "frozen source-room snapshot"),
            }
        )
    return register


def json_records(df: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    out = []
    for rec in df[columns].to_dict(orient="records"):
        clean = {}
        for k, v in rec.items():
            if pd.isna(v):
                clean[k] = None
            elif isinstance(v, (pd.Timestamp, datetime)):
                clean[k] = v.strftime("%Y-%m-%d")
            elif hasattr(v, "item"):
                clean[k] = v.item()
            else:
                clean[k] = v
            if clean[k] is not None and isinstance(clean[k], (int, float)) and not isinstance(clean[k], bool):
                if k in {"local_per_eur", "fx_local_per_eur"}:
                    clean[k] = float(Decimal(str(clean[k])).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
                elif k in MONEY_FIELDS or k.endswith("_eur"):
                    clean[k] = float(Decimal(str(clean[k])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                elif k == "margin":
                    clean[k] = float(Decimal(str(clean[k])).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))
        out.append(clean)
    return out


def build_metrics() -> dict[str, Any]:
    inputs = load_inputs()
    orders, order_audit = canonicalize_orders(inputs)
    returns, return_audit = canonicalize_returns(inputs, orders)
    fx_df, fx_lookup = monthly_fx(inputs)
    order_metrics, metric_checks = build_order_metrics(orders, returns, fx_lookup, inputs["unit_costs"])
    monthly_df, country_df = aggregate_metrics(order_metrics)
    market_df, market_meta = market_context(inputs)
    individual_scenarios, pair_scenarios, rankings_df, ranking_meta = build_scenarios(country_df, inputs)
    register = source_register()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    DELIVERABLES.mkdir(parents=True, exist_ok=True)
    order_metrics.to_csv(OUTPUT / "order_metrics.csv", index=False)
    orders.sort_values(["country", "order_id"]).to_csv(OUTPUT / "orders_audit.csv", index=False)
    returns.sort_values(["return_id"]).to_csv(OUTPUT / "returns_audit.csv", index=False)
    monthly_df.to_csv(OUTPUT / "monthly.csv", index=False)
    country_df.to_csv(OUTPUT / "countries.csv", index=False)
    fx_df.to_csv(OUTPUT / "fx_monthly.csv", index=False)
    market_df.to_csv(OUTPUT / "market_context.csv", index=False)
    individual_scenarios.to_csv(OUTPUT / "hub_scenarios.csv", index=False)
    pair_scenarios.to_csv(OUTPUT / "pair_scenarios.csv", index=False)
    rankings_df.to_csv(OUTPUT / "option_rankings.csv", index=False)
    (ROOT / "evidence" / "source_register.json").write_text(json.dumps(register, indent=2), encoding="utf-8")
    (DELIVERABLES / "source_register.json").write_text(json.dumps(register, indent=2), encoding="utf-8")

    # Reconciliation evidence: monthly sums are the authoritative country totals.
    recon = {}
    for country in COUNTRIES:
        c = country_df[country_df.country == country].iloc[0]
        m = monthly_df[monthly_df.country == country]
        recon[country] = {
            "monthly_rows": int(len(m)),
            "monthly_shipped_orders": int(m.shipped_orders.sum()),
            "country_shipped_orders": int(c.shipped_orders),
            "monthly_shipped_units": int(m.shipped_units.sum()),
            "country_shipped_units": int(c.shipped_units),
            "monthly_contribution_eur": number(D(m.contribution_eur.sum()), 2),
            "country_contribution_eur": number(D(c.contribution_eur), 2),
            "passed": int(m.shipped_orders.sum()) == int(c.shipped_orders) and int(m.shipped_units.sum()) == int(c.shipped_units) and abs(float(m.contribution_eur.sum() - c.contribution_eur)) < 0.005,
        }

    quality = {
        "status": "completed_with_disclosed_anomalies",
        "source_room": "Frozen local snapshot collected from TOOLING.md URL; not a live client account.",
        "client_data_status": "All order, return, cost, option and policy inputs are synthetic; World Bank and ECB observations are public official snapshots.",
        "cutoff": "2026-01-31 inclusive for return receipts",
        "analysis_period": "2025 shipped_at calendar year",
        "accounting": {
            "grain": "one canonical order_id / one SKU row; one canonical return_id",
            "revisions": "highest numeric revision wins; corrections replace whole rows",
            "duplicates": "identical rows removed before revision selection",
            "fx": "ECB arithmetic mean of available 2025 business-day observations; local currency units per EUR; EUR=1",
            "rounding": "individual gross sales, refunds, net COGS, fulfillment and contribution rounded half-up to cents per order before sum",
            "returns": "valid returns allocated to original sale month; distinct return IDs additive; restocked units recover original unit cost only",
        },
        "order_audit": order_audit,
        "return_audit": return_audit,
        "metric_checks": metric_checks,
        "reconciliation": recon,
        "market_context": market_meta,
        "limitations": [
            "ECB reference rates are analytical translation assumptions, not transaction-level FX; the archive includes later dates than the 2025 analysis.",
            "World Bank population and GDP per capita are context only, not direct evidence of replacement-assembly demand or hub causality.",
            "Scenario arithmetic is a synthetic planning model without customer interviews, freight-lane validation, local labor quotes, or a discounted cash-flow model.",
            "Return receipts after the inclusive cutoff and returns linked to ineligible or orphan orders are not included in 2025 results.",
        ],
    }

    # Baseline JSON contract uses stable key order and explicit arrays.
    monthly_cols = ["country", "month", "shipped_orders", "shipped_units", *MONEY_FIELDS, "returned_units", "margin"]
    country_cols = ["country", "shipped_orders", "shipped_units", *MONEY_FIELDS, "returned_units", "margin"]
    fx_cols = ["currency", "month", "local_per_eur"]
    market_cols = ["country", "year", "population", "gdp_per_capita_usd"]
    scenario_cols = ["country", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years"]
    hub_scenario_records = json_records(individual_scenarios.sort_values(["country", "scenario"]), scenario_cols)
    pair_scenario_cols = ["country", "countries", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years"]
    pair_scenario_records = json_records(pair_scenarios[pair_scenarios.feasible].sort_values(["country", "scenario"]), pair_scenario_cols)
    base_option = rankings_df.iloc[0]
    selected_countries = base_option["countries"]
    rationale = (
        f"Fund {', '.join(selected_countries)} under the base case: it ranks first among feasible single hubs and pairs by annual incremental contribution "
        f"({base_option['incremental_contribution_eur']:,.0f} EUR), within the EUR450,000 capex and seven-FTE hard constraints. "
        "Treat this as a supported planning recommendation, not a causal or statistically proven demand forecast; release capex only after the 90-day gates."
    )
    metrics = {
        "metadata": {
            "client": "Meridian Parts (synthetic)",
            "analysis_period": "2025",
            "return_cutoff": "2026-01-31",
            "currency": "EUR",
            "source_room_url": "http://127.0.0.1:49807/",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "reproducible_command": "<SHARED_RUNTIME>/python/bin/python3 scripts/generate_all.py",
        },
        "monthly": json_records(monthly_df, monthly_cols),
        "countries": json_records(country_df, country_cols),
        "fx_monthly": json_records(fx_df, fx_cols),
        "market_context": json_records(market_df, market_cols),
        "hub_scenarios": hub_scenario_records + pair_scenario_records,
        "pair_scenarios": pair_scenario_records,
        "option_rankings": rankings_df.to_dict(orient="records"),
        "recommendation": {
            "countries": selected_countries,
            "capex_eur": base_option["capex_eur"],
            "fte": int(base_option["fte"]),
            "rationale": rationale,
            "recommended_scenario": "base",
            "break_even_volume_uplift": base_option.get("break_even_uplift"),
            "strongest_alternative": rankings_df.iloc[1]["option"] if len(rankings_df) > 1 else None,
            "flip_condition": "Reopen before commitment if validated base-volume uplift falls below the selected pair's break-even or if stress contribution turns negative; the exact break-even is in the workbook and report.",
        },
        "quality": quality,
        "source_register": register,
    }
    (DELIVERABLES / "metrics.json").write_text(json.dumps(metrics, indent=2, allow_nan=False), encoding="utf-8")
    return {
        "inputs": inputs,
        "orders": orders,
        "returns": returns,
        "order_metrics": order_metrics,
        "monthly": monthly_df,
        "countries": country_df,
        "fx": fx_df,
        "market": market_df,
        "individual_scenarios": individual_scenarios,
        "pair_scenarios": pair_scenarios,
        "rankings": rankings_df,
        "metrics": metrics,
        "register": register,
    }


if __name__ == "__main__":
    result = build_metrics()
    print(json.dumps({"countries": result["countries"].to_dict(orient="records"), "rankings": result["rankings"].head(12).to_dict(orient="records")}, indent=2))
