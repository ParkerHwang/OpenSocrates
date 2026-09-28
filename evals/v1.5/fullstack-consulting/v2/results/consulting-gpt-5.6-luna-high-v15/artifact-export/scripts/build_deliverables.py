#!/usr/bin/env python3
"""Build Meridian Parts analysis and deliverables from saved source-room inputs.

Run from the project root:
    python3 scripts/build_deliverables.py

The script intentionally reads only evidence/raw and writes deliverables,
analysis_output, and evidence/source-register.csv.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import os
import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table as RLTable, TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence" / "raw"
OUT = ROOT / "deliverables"
CHARTS = ROOT / "analysis_output"
OUT.mkdir(exist_ok=True)
CHARTS.mkdir(exist_ok=True)

COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
COUNTRY_NAMES = {
    "DEU": "Germany", "FRA": "France", "NLD": "Netherlands",
    "POL": "Poland", "CZE": "Czechia", "ESP": "Spain",
}
COUNTRY_CURRENCY = {"DEU": "EUR", "FRA": "EUR", "NLD": "EUR", "POL": "PLN", "CZE": "CZK", "ESP": "EUR"}
SCENARIO_UPLIFT = {"low": 0.10, "base": 0.25, "high": 0.40}
MONEY_COLUMNS = ["gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"]


def q2(x: Any) -> Decimal:
    """Round monetary values half-up to cents."""
    if x is None or (not isinstance(x, (list, tuple, dict)) and bool(pd.isna(x))):
        return Decimal("0.00")
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def jsafe(x: Any) -> Any:
    if isinstance(x, Decimal):
        return float(x)
    if not isinstance(x, (list, dict, tuple)):
        try:
            if bool(pd.isna(x)):
                return None
        except (TypeError, ValueError):
            pass
    if isinstance(x, pd.Timestamp) and pd.isna(x):
        return None
    if isinstance(x, (pd.Timestamp, datetime)):
        return x.strftime("%Y-%m-%d")
    if pd.isna(x) if not isinstance(x, (list, dict, tuple)) else False:
        return None
    if isinstance(x, dict):
        return {str(k): jsafe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsafe(v) for v in x]
    if hasattr(x, "item"):
        return jsafe(x.item())
    return x


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(jsafe(data), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW / name)


def source_register() -> pd.DataFrame:
    now = datetime.now(timezone.utc).isoformat()
    original = {}
    try:
        original = json.loads((RAW / "source-register.json").read_text(encoding="utf-8"))
    except Exception:
        pass
    public_by_file = {x.get("file"): x for x in original.get("public", [])}
    rows = []
    specs = {
        "data-dictionary.md": ("synthetic", "rules; accounting and grain", "2025-01-01 to 2026-01-31", "Source-room local snapshot"),
        "scenario-policy.md": ("synthetic", "scenario policy", "annual planning horizon", "Source-room local snapshot"),
        "hub-options.csv": ("synthetic", "EUR, FTE, EUR/unit", "current planning assumptions", "Source-room local snapshot"),
        "unit-costs.csv": ("synthetic", "EUR per unit", "2025 effective dates", "Source-room local snapshot"),
        "orders-part1.csv": ("synthetic", "local currency and EUR fulfillment", "2025 orders", "Source-room local snapshot"),
        "orders-part2.csv": ("synthetic", "local currency and EUR fulfillment", "2025 orders", "Source-room local snapshot"),
        "order-corrections.csv": ("synthetic", "local currency and EUR fulfillment", "2025 order corrections", "Source-room local snapshot"),
        "returns.csv": ("synthetic", "local currency", "2025-01-01 to 2026-01-31", "Source-room local snapshot"),
        "source-register.json": ("synthetic", "provenance metadata", "archive vintage", "Source-room local snapshot"),
        "population.json": ("public archived", "persons", "2022-2024", "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&format=json&per_page=1000"),
        "gdp-per-capita.json": ("public archived", "current US$ per person", "2022-2024", "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&format=json&per_page=1000"),
        "ecb-history.zip": ("public archived", "local currency units per EUR", "historical archive; 2025 used", "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"),
        "ecb-history.csv": ("public archived derived", "local currency units per EUR", "historical archive; 2025 used", "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"),
    }
    for fn, (status, units, period, url) in specs.items():
        p = RAW / fn
        meta = public_by_file.get(fn, {})
        rows.append({
            "file": fn,
            "original_url": meta.get("original_url", url if url.startswith("http") else "http://127.0.0.1:55510/" + fn),
            "retrieved_utc": meta.get("retrieved_utc", now),
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "units": units,
            "period": period,
            "status": status,
            "notes": "Frozen source-room input; no live client access."
                     if status == "synthetic" else "Archived public snapshot; use original URL for provenance.",
        })
    reg = pd.DataFrame(rows).sort_values("file")
    reg.to_csv(ROOT / "evidence" / "source-register.csv", index=False)
    reg.to_csv(OUT / "source-register.csv", index=False)
    return reg


def load_and_calculate() -> dict[str, Any]:
    # Orders: duplicate exact repeated rows are one record; max revision wins.
    order_frames = [read_csv(x) for x in ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]]
    orders_all = pd.concat(order_frames, ignore_index=True)
    raw_order_rows = len(orders_all)
    exact_dup_rows = int(orders_all.duplicated().sum())
    orders_all = orders_all.drop_duplicates().copy()
    orders_all["revision"] = pd.to_numeric(orders_all["revision"], errors="coerce").fillna(0).astype(int)
    orders_all = orders_all.sort_values(["order_id", "revision"]).drop_duplicates("order_id", keep="last").copy()
    orders_all["shipped_at"] = pd.to_datetime(orders_all["shipped_at"], errors="coerce")
    orders_all["ordered_at"] = pd.to_datetime(orders_all["ordered_at"], errors="coerce")
    orders_all["is_test"] = orders_all["is_test"].astype(str).str.lower().eq("true")
    orders_all["status"] = orders_all["status"].astype(str).str.lower()
    eligible_mask = (
        orders_all["status"].eq("shipped") &
        ~orders_all["is_test"] &
        orders_all["shipped_at"].between(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31 23:59:59"))
    )
    excluded_orders = orders_all.loc[~eligible_mask].copy()
    orders = orders_all.loc[eligible_mask].copy()
    orders["month"] = orders["shipped_at"].dt.strftime("%Y-%m")

    # ECB business-day means for all 2025 months; quote is local units per EUR.
    fx = pd.read_csv(RAW / "ecb-history.csv")
    fx["Date"] = pd.to_datetime(fx["Date"], errors="coerce")
    fx25 = fx[fx["Date"].dt.year.eq(2025)].copy()
    fx_monthly = []
    fx_map: dict[tuple[str, str], Decimal] = {}
    for currency in ["PLN", "CZK"]:
        for month in pd.period_range("2025-01", "2025-12", freq="M").astype(str):
            vals = pd.to_numeric(fx25.loc[fx25["Date"].dt.strftime("%Y-%m").eq(month), currency], errors="coerce").dropna()
            mean = Decimal(str(vals.mean())) if len(vals) else Decimal("1")
            fx_monthly.append({"currency": currency, "month": month, "local_per_eur": q2(mean)})
            fx_map[(currency, month)] = mean
    fx_monthly.extend({"currency": "EUR", "month": m, "local_per_eur": Decimal("1.00")} for m in pd.period_range("2025-01", "2025-12", freq="M").astype(str))
    fx_monthly = sorted(fx_monthly, key=lambda x: (x["currency"], x["month"]))

    # Returns: max revision per return_id; eligible linked orders only; late returns are allowed through cutoff.
    ret = read_csv("returns.csv")
    raw_return_rows = len(ret)
    return_exact_dups = int(ret.duplicated().sum())
    ret = ret.drop_duplicates().copy()
    ret["revision"] = pd.to_numeric(ret["revision"], errors="coerce").fillna(0).astype(int)
    ret = ret.sort_values(["return_id", "revision"]).drop_duplicates("return_id", keep="last").copy()
    ret["received_at"] = pd.to_datetime(ret["received_at"], errors="coerce")
    eligible_order_ids = set(orders["order_id"])
    orphan = ret[~ret["order_id"].isin(eligible_order_ids)].copy()
    late = ret[ret["received_at"] > pd.Timestamp("2026-01-31 23:59:59")].copy()
    returns = ret[ret["order_id"].isin(eligible_order_ids) & ret["received_at"].le(pd.Timestamp("2026-01-31 23:59:59"))].copy()
    # Keep an orphan/late note separately; neither is matched by guess.

    # Unit costs: latest effective date on or before shipment.
    costs = read_csv("unit-costs.csv")
    costs["valid_from"] = pd.to_datetime(costs["valid_from"])
    costs = costs.sort_values(["sku", "valid_from"])
    orders = pd.merge_asof(
        orders.sort_values("shipped_at"), costs.sort_values("valid_from"),
        by="sku", left_on="shipped_at", right_on="valid_from", direction="backward",
    ).sort_index()
    if orders["unit_cost_eur"].isna().any():
        raise ValueError("Missing unit cost for eligible order")

    # Refund/recovery by linked order, converting with original sale month FX.
    ret_ag = returns.groupby("order_id", as_index=False).agg(
        returned_units=("quantity", "sum"), restocked_quantity=("restocked_quantity", "sum"), refund_local=("refund_local", "sum"), return_ids=("return_id", "count")
    )
    orders = orders.merge(ret_ag, on="order_id", how="left")
    orders[["returned_units", "restocked_quantity", "refund_local", "return_ids"]] = orders[["returned_units", "restocked_quantity", "refund_local", "return_ids"]].fillna(0)
    orders["currency"] = orders["currency"].str.upper()
    anomalies = []
    bad_restock = orders[orders["restocked_quantity"] > orders["returned_units"]]
    if len(bad_restock):
        anomalies.append(f"{len(bad_restock)} eligible orders have restocked quantity above returned quantity; calculations use supplied restocked quantity and flag this for validation.")
    bad_currency = orders[~orders["currency"].isin(["EUR", "PLN", "CZK"])]
    if len(bad_currency):
        anomalies.append(f"{len(bad_currency)} eligible orders have unsupported currency; not silently converted.")

    def fx_for(row):
        if row["currency"] == "EUR":
            return Decimal("1")
        return fx_map[(row["currency"], row["month"])]

    orders["fx_local_per_eur"] = orders.apply(fx_for, axis=1)
    # Decimal order-level components, then sum; float output is only at aggregate/report boundary.
    calc = []
    for _, r in orders.iterrows():
        fxv = r["fx_local_per_eur"]
        gross_local = Decimal(str(r["quantity"])) * Decimal(str(r["unit_price_local"])) - Decimal(str(r["discount_local"]))
        refund_local = Decimal(str(r["refund_local"]))
        gross_sales = q2(gross_local / fxv)
        refunds = q2(refund_local / fxv)
        gross_cogs = q2(Decimal(str(r["quantity"])) * Decimal(str(r["unit_cost_eur"])))
        recovered_cogs = q2(Decimal(str(r["restocked_quantity"])) * Decimal(str(r["unit_cost_eur"])))
        net_cogs = q2(gross_cogs - recovered_cogs)
        fulfillment = q2(r["fulfillment_eur"])
        contribution = q2(gross_sales - refunds - net_cogs - fulfillment)
        calc.append((gross_sales, refunds, gross_cogs, recovered_cogs, net_cogs, fulfillment, contribution))
    # fulfillment_eur is already an input field; do not concatenate a duplicate
    # column with the same name.
    calc_df = pd.DataFrame(calc, columns=["gross_sales_eur", "refunds_eur", "gross_cogs_eur", "recovered_cogs_eur", "net_cogs_eur", "_rounded_fulfillment_eur", "contribution_eur"], index=orders.index)
    orders["fulfillment_eur"] = orders["fulfillment_eur"].apply(q2)
    orders = pd.concat([orders, calc_df], axis=1)
    orders["net_sales_eur"] = orders.apply(lambda r: q2(r["gross_sales_eur"] - r["refunds_eur"]), axis=1)

    # Create full country-month panel, with country/year rollups exact to monthly.
    months = [str(x) for x in pd.period_range("2025-01", "2025-12", freq="M")]
    monthly_rows = []
    for country in COUNTRIES:
        for month in months:
            sub = orders[(orders["country"] == country) & (orders["month"] == month)]
            vals = {
                "country": country, "month": month,
                "shipped_orders": int(sub["order_id"].nunique()),
                "shipped_units": int(sub["quantity"].sum()),
                "gross_sales_eur": q2(sub["gross_sales_eur"].sum()),
                "refunds_eur": q2(sub["refunds_eur"].sum()),
                "net_sales_eur": q2(sub["net_sales_eur"].sum()),
                "net_cogs_eur": q2(sub["net_cogs_eur"].sum()),
                "fulfillment_eur": q2(sub["fulfillment_eur"].sum()),
                "contribution_eur": q2(sub["contribution_eur"].sum()),
                "returned_units": int(sub["returned_units"].sum()),
            }
            vals["margin"] = None if vals["net_sales_eur"] == 0 else q2(vals["contribution_eur"] / vals["net_sales_eur"] * 10000) / Decimal("10000")
            monthly_rows.append(vals)
    monthly = pd.DataFrame(monthly_rows)
    country_rows = []
    for country in COUNTRIES:
        sub = monthly[monthly["country"] == country]
        vals = {"country": country, "shipped_orders": int(sub["shipped_orders"].sum()), "shipped_units": int(sub["shipped_units"].sum()), "returned_units": int(sub["returned_units"].sum())}
        for c in MONEY_COLUMNS:
            vals[c] = q2(sub[c].sum())
        vals["margin"] = None if vals["net_sales_eur"] == 0 else q2(vals["contribution_eur"] / vals["net_sales_eur"] * 10000) / Decimal("10000")
        country_rows.append(vals)
    countries = pd.DataFrame(country_rows)

    # Archived World Bank response rows: preserve missing values, years, units and vintage metadata.
    def wb_context(fn):
        raw = json.loads((RAW / fn).read_text(encoding="utf-8"))
        meta, data = raw[0], raw[1]
        rows = []
        for r in data:
            rows.append({"country": r["countryiso3code"], "year": int(r["date"]), "population": r["value"] if "population" in fn else None, "gdp_per_capita_usd": r["value"] if "gdp" in fn else None})
        return meta, rows
    pop_meta, pop_rows = wb_context("population.json")
    gdp_meta, gdp_rows = wb_context("gdp-per-capita.json")
    ctx: dict[tuple[str, int], dict[str, Any]] = {}
    for r in pop_rows + gdp_rows:
        k = (r["country"], r["year"]); ctx.setdefault(k, {"country": r["country"], "year": r["year"], "population": None, "gdp_per_capita_usd": None})
        if r["population"] is not None: ctx[k]["population"] = r["population"]
        if r["gdp_per_capita_usd"] is not None: ctx[k]["gdp_per_capita_usd"] = r["gdp_per_capita_usd"]
    market_context = pd.DataFrame(sorted(ctx.values(), key=lambda x: (x["country"], x["year"])))

    # Scenario arithmetic from the supplied policy. Individual and feasible-pair entries.
    opts = read_csv("hub-options.csv")
    base = countries.set_index("country").to_dict("index")
    opt = opts.set_index("country").to_dict("index")
    scenario_rows = []
    def scenario_for(label: str, members: list[str], scenario: str):
        upl = SCENARIO_UPLIFT.get(scenario, 0.25)
        capex = sum(Decimal(str(opt[c]["capex_eur"])) for c in members)
        fte = sum(int(opt[c]["fte"]) for c in members)
        annual = Decimal("0")
        for c in members:
            C = Decimal(str(base[c]["contribution_eur"]))
            U = Decimal(str(base[c]["shipped_units"]))
            G = Decimal(str(base[c]["gross_sales_eur"]))
            N = Decimal(str(base[c]["net_sales_eur"]))
            s = Decimal(str(opt[c]["saving_eur_per_unit"]))
            F = Decimal(str(opt[c]["annual_fixed_eur"]))
            if scenario in SCENARIO_UPLIFT:
                annual += C * Decimal(str(upl)) + U * (Decimal("1") + Decimal(str(upl))) * s - F
            else:
                fx_shock = Decimal("0.10") * N if COUNTRY_CURRENCY[c] in ["PLN", "CZK"] else Decimal("0")
                C_stress = C - Decimal("0.03") * G - fx_shock
                annual += C_stress * Decimal("1.25") - C + U * Decimal("1.25") * s - F
        payback = None if annual <= 0 else capex / annual
        scenario_rows.append({"country": label, "scenario": scenario, "incremental_contribution_eur": q2(annual), "capex_eur": q2(capex), "fte": fte, "payback_years": None if payback is None else round(float(payback), 2)})
    for c in COUNTRIES:
        for s in ["low", "base", "high", "stress"]: scenario_for(c, [c], s)
    feasible_pairs = []
    for a, b in itertools.combinations(COUNTRIES, 2):
        if int(opt[a]["fte"]) + int(opt[b]["fte"]) <= 7 and float(opt[a]["capex_eur"]) + float(opt[b]["capex_eur"]) <= 450000:
            feasible_pairs.append((a, b))
            for s in ["low", "base", "high", "stress"]: scenario_for(f"{a}+{b}", [a, b], s)
    scenario_df = pd.DataFrame(scenario_rows)
    base_scen = scenario_df[scenario_df["scenario"] == "base"].sort_values("incremental_contribution_eur", ascending=False).copy()
    stress_scen = scenario_df[scenario_df["scenario"] == "stress"].set_index("country")
    best = base_scen.iloc[0]
    selected = str(best["country"]).split("+")
    # Strongest alternative is the next feasible entry by base annual contribution.
    alternative = base_scen.iloc[1]
    stress_leader = scenario_df[scenario_df["scenario"] == "stress"].sort_values("incremental_contribution_eur", ascending=False).iloc[0]
    # Decision guard: recommend the base leader subject to 90-day validation, not as causal certainty.
    recommendation = {
        "countries": selected,
        "capex_eur": int(best["capex_eur"]),
        "fte": int(best["fte"]),
        "rationale": f"Base-case annual incremental contribution is highest among feasible one- and two-hub alternatives at EUR {float(best['incremental_contribution_eur']):,.0f}; the pair remains within EUR450,000 capex and seven FTE. Proceed only through the 90-day gates because uplift, savings and return/FX stress are planning assumptions, not measured causal effects.",
        "base_annual_incremental_contribution_eur": float(best["incremental_contribution_eur"]),
        "base_payback_years": best["payback_years"],
        "strongest_alternative": str(alternative["country"]),
        "strongest_alternative_base_annual_incremental_contribution_eur": float(alternative["incremental_contribution_eur"]),
        "stress_case_leader": str(stress_leader["country"]),
        "stress_case_leader_annual_incremental_contribution_eur": float(stress_leader["incremental_contribution_eur"]),
        "flip_condition": "Defer or fund the strongest alternative if the 90-day pilot evidence cannot support at least the base-case uplift/savings run-rate, if capex or FTE gates are breached, or if the defined stress case becomes the more credible planning case.",
    }
    quality = {
        "source_room": "Frozen local source room collected from http://127.0.0.1:55510/ on the run date; client extracts are synthetic.",
        "raw_order_rows": raw_order_rows,
        "exact_duplicate_order_rows_removed": exact_dup_rows,
        "order_revision_winners": int(len(orders_all)),
        "excluded_order_rows_after_revision_winner": int(len(excluded_orders)),
        "excluded_order_reasons": excluded_orders[["order_id", "status", "is_test", "shipped_at"]].to_dict("records"),
        "raw_return_rows": raw_return_rows,
        "exact_duplicate_return_rows_removed": return_exact_dups,
        "orphan_returns_quarantined": int(len(orphan)),
        "late_returns_after_cutoff_excluded": int(len(late)),
        "orphan_return_ids": orphan["return_id"].tolist(),
        "late_return_ids": late["return_id"].tolist(),
        "zero_price_shipments_included": int(((orders["quantity"] * orders["unit_price_local"] - orders["discount_local"]) == 0).sum()),
        "missing_fx_values": [f"{k[0]} {k[1]}" for k, v in fx_map.items() if v is None],
        "calculation_notes": [
            "One order is one SKU row; duplicate repeats are collapsed and highest numeric revision wins.",
            "Returns are max revision per return_id, additive across return IDs, linked only to eligible orders, and converted at the original sale month FX.",
            "Individual gross sales, refunds, COGS components, fulfillment, net sales and contribution are rounded half-up to cents before aggregation.",
            "Contribution is an operating measure: net sales less net COGS and nonrefundable fulfillment. It is not booked revenue or cash.",
        ] + anomalies,
        "wb_population_vintage": pop_meta.get("lastupdated"),
        "wb_gdp_vintage": gdp_meta.get("lastupdated"),
        "ecb_quote": "local currency units per EUR; arithmetic mean over available published business days in each 2025 month; EUR=1.",
        "scenario_limitations": [
            "Client policy arithmetic is deterministic but synthetic; no customer interviews, causal hub experiment, or full discounted cash-flow model was supplied.",
            "Stress is a deliberate joint stress, not a probability forecast; PLN/CZK receive 10% of net sales as the defined FX shock and all markets receive a 3% gross-sales refund shock.",
            "Pairs add country figures/capex/FTE without synergy.",
        ],
    }

    return {
        "orders": orders, "excluded_orders": excluded_orders, "returns": returns, "orphan_returns": orphan, "late_returns": late,
        "monthly": monthly, "countries": countries, "fx_monthly": pd.DataFrame(fx_monthly), "market_context": market_context,
        "hub_options": opts, "hub_scenarios": scenario_df, "feasible_pairs": feasible_pairs, "recommendation": recommendation, "quality": quality,
    }


def make_metrics(d: dict[str, Any]) -> None:
    def records(df): return [{k: jsafe(v) for k, v in row.items()} for row in df.to_dict("records")]
    metrics = {
        "monthly": records(d["monthly"][["country", "month", "shipped_orders", "shipped_units"] + MONEY_COLUMNS + ["returned_units", "margin"]]),
        "countries": records(d["countries"][["country", "shipped_orders", "shipped_units"] + MONEY_COLUMNS + ["returned_units", "margin"]]),
        "fx_monthly": records(d["fx_monthly"][["currency", "month", "local_per_eur"]]),
        "market_context": records(d["market_context"][["country", "year", "population", "gdp_per_capita_usd"]]),
        "hub_scenarios": records(d["hub_scenarios"][["country", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years"]]),
        "recommendation": d["recommendation"],
        "quality": d["quality"],
    }
    write_json(OUT / "metrics.json", metrics)


def format_ws(ws, freeze="A2", widths=None):
    ws.freeze_panes = freeze
    ws.sheet_view.showGridLines = False
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30
    if widths:
        for col, width in widths.items(): ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=False)


def add_table(ws, name):
    if ws.max_row < 2 or ws.max_column < 1: return
    ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
    tab = Table(displayName=name, ref=ref)
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    ws.add_table(tab)


def df_sheet(wb, title, df, money_cols=None, pct_cols=None, widths=None):
    ws = wb.create_sheet(title)
    cols = list(df.columns)
    ws.append(cols)
    for row in df.itertuples(index=False, name=None): ws.append([jsafe(x) for x in row])
    format_ws(ws, widths=widths)
    add_table(ws, "T_" + re.sub(r"[^A-Za-z0-9]", "", title))
    money_cols = money_cols or []
    pct_cols = pct_cols or []
    for col in money_cols:
        if col in cols:
            ci = cols.index(col) + 1
            for cell in ws.iter_cols(min_col=ci, max_col=ci, min_row=2):
                for c in cell: c.number_format = '#,##0.00;[Red](#,##0.00)'
    for col in pct_cols:
        if col in cols:
            ci = cols.index(col) + 1
            for cell in ws.iter_cols(min_col=ci, max_col=ci, min_row=2):
                for c in cell: c.number_format = '0.0%'
    return ws


def make_workbook(d: dict[str, Any], reg: pd.DataFrame) -> None:
    wb = Workbook()
    ws = wb.active; ws.title = "Readme"
    ws.append(["Meridian Parts | analytical workbook"])
    ws.append(["Purpose", "Reproducible 2025 shipped-sales, returns, FX, market-context and hub-scenario analysis."])
    ws.append(["Source boundary", "Saved files under evidence/raw; synthetic client exports are not live customer data. Archived World Bank and ECB inputs retain original URLs and vintages in Source_Register."])
    ws.append(["Accounting", "Highest revision per order_id/return_id; exact duplicates removed; sale-month mean ECB quote; order-level half-up cents; returns through 2026-01-31 only when linked to an eligible 2025 shipment."])
    ws.append(["Contribution", "Net sales - net COGS - nonrefundable fulfillment. Not booked revenue or cash."])
    ws.append(["Scenario policy", "Low/base/high = 10%/25%/40% uplift. Stress = base uplift plus defined refund and PLN/CZK FX shocks. Capex is year-zero and excluded from annual contribution."])
    ws.append(["Build command", "python3 scripts/build_deliverables.py"])
    ws.append(["Important", "Scenario arithmetic is synthetic planning analysis, not a causal estimate or a full discounted cash-flow model."])
    ws.column_dimensions["A"].width = 24; ws.column_dimensions["B"].width = 125
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
        row[0].font = Font(bold=True, color="FFFFFF") if row[0].row == 1 else Font(bold=True, color="1F4E78")
        if row[0].row == 1:
            row[0].fill = PatternFill("solid", fgColor="1F4E78"); row[0].font = Font(bold=True, color="FFFFFF", size=14)
        row[1].alignment = Alignment(wrap_text=True, vertical="top") if len(row) > 1 else row[0].alignment
    ws.row_dimensions[1].height = 26
    df_sheet(wb, "Monthly", d["monthly"], MONEY_COLUMNS, ["margin"], {"A":10,"B":10,"C":14,"D":14,"E":16,"F":14,"G":14,"H":14,"I":16,"J":16,"K":16,"L":16,"M":14})
    df_sheet(wb, "Countries", d["countries"], MONEY_COLUMNS, ["margin"], {"A":10,"B":14,"C":14,"D":16,"E":14,"F":14,"G":14,"H":16,"I":16,"J":16,"K":16,"L":14})
    df_sheet(wb, "FX_Monthly", d["fx_monthly"], ["local_per_eur"], widths={"A":12,"B":12,"C":16})
    df_sheet(wb, "Market_Context", d["market_context"], ["gdp_per_capita_usd"], widths={"A":12,"B":10,"C":16,"D":22})
    df_sheet(wb, "Hub_Scenarios", d["hub_scenarios"], ["incremental_contribution_eur","capex_eur"], widths={"A":14,"B":12,"C":24,"D":14,"E":10,"F":15})
    df_sheet(wb, "Hub_Options", d["hub_options"], ["capex_eur","annual_fixed_eur","saving_eur_per_unit"], widths={"A":12,"B":14,"C":10,"D":16,"E":20})
    df_sheet(wb, "Clean_Orders", d["orders"].drop(columns=["fx_local_per_eur"], errors="ignore"), MONEY_COLUMNS + ["gross_cogs_eur","recovered_cogs_eur"], widths={"A":16,"B":10,"C":10,"D":13,"E":13,"F":12,"G":10,"H":10,"I":10,"J":14,"K":14,"L":10,"M":14,"N":12,"O":14,"P":16,"Q":16,"R":16,"S":14,"T":16,"U":16,"V":16,"W":16,"X":15,"Y":14})
    df_sheet(wb, "Used_Returns", d["returns"], ["refund_local"], widths={"A":22,"B":10,"C":16,"D":13,"E":12,"F":18,"G":14})
    df_sheet(wb, "Excluded_Orders", d["excluded_orders"], widths={"A":18,"B":10,"C":10,"D":14,"E":14,"F":12,"G":10,"H":13,"I":13,"J":13,"K":10,"L":16,"M":14})
    df_sheet(wb, "Quarantined_Returns", pd.concat([d["orphan_returns"].assign(reason="orphan linked order"), d["late_returns"].assign(reason="received after cutoff")], ignore_index=True), ["refund_local"], widths={"A":22,"B":10,"C":16,"D":13,"E":12,"F":18,"G":14,"H":26})
    # Quality and source register as legible narrative sheets.
    qws = wb.create_sheet("Quality")
    qws.append(["quality item", "value"])
    for k, v in d["quality"].items(): qws.append([k, json.dumps(jsafe(v), ensure_ascii=False) if isinstance(v, (list, dict)) else jsafe(v)])
    format_ws(qws, widths={"A":40,"B":130}); qws.column_dimensions["B"].width = 130
    for r in range(2, qws.max_row + 1): qws.cell(r,2).alignment = Alignment(wrap_text=True, vertical="top")
    add_table(qws, "T_Quality")
    df_sheet(wb, "Source_Register", reg, widths={"A":22,"B":80,"C":34,"D":66,"E":12,"F":28,"G":20,"H":18,"I":60})
    # Charts sheet: source values are visible and charts remain native Excel objects.
    cws = wb.create_sheet("Charts")
    cws.append(["Chart", "Use"]); cws.append(["Country contribution", "Annual 2025 contribution EUR by country"]); cws.append(["Scenario comparison", "Base annual incremental contribution EUR for feasible options"])
    format_ws(cws, widths={"A":24,"B":80})
    # helper data to the right
    cws.cell(1, 5, "Country"); cws.cell(1, 6, "Contribution EUR")
    for i, r in enumerate(d["countries"].itertuples(index=False), start=2): cws.cell(i,5,r.country); cws.cell(i,6,float(r.contribution_eur))
    ch = BarChart(); ch.type="bar"; ch.style=10; ch.title="2025 contribution by country"; ch.y_axis.title="Country"; ch.x_axis.title="EUR"
    ch.add_data(Reference(cws,min_col=6,min_row=1,max_row=1+len(d["countries"])), titles_from_data=True); ch.set_categories(Reference(cws,min_col=5,min_row=2,max_row=1+len(d["countries"]))); ch.height=8; ch.width=15; cws.add_chart(ch,"A6")
    cws.cell(1,8,"Option"); cws.cell(1,9,"Base annual incremental EUR")
    bs=d["hub_scenarios"][d["hub_scenarios"].scenario.eq("base")].sort_values("incremental_contribution_eur",ascending=False)
    for i, r in enumerate(bs.itertuples(index=False), start=2): cws.cell(i,8,r.country); cws.cell(i,9,float(r.incremental_contribution_eur))
    ch2=BarChart(); ch2.type="bar"; ch2.style=11; ch2.title="Feasible options: base annual incremental contribution"; ch2.y_axis.title="Option"; ch2.x_axis.title="EUR"; ch2.add_data(Reference(cws,min_col=9,min_row=1,max_row=1+len(bs)),titles_from_data=True); ch2.set_categories(Reference(cws,min_col=8,min_row=2,max_row=1+len(bs))); ch2.height=10; ch2.width=18; cws.add_chart(ch2,"J6")
    for col in ["E","F","H","I"]: cws.column_dimensions[col].width = 26
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.save(OUT / "meridian_parts_analysis.xlsx")


def money(v):
    if v is None or (isinstance(v, float) and math.isnan(v)): return "—"
    return f"EUR {float(v):,.0f}"


def pct(v):
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{float(v)*100:.1f}%"


def make_report(d: dict[str, Any], reg: pd.DataFrame) -> None:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Title2", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.HexColor("#1F4E78"), spaceAfter=12))
    styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=colors.HexColor("#1F4E78"), spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor("#2F5597"), spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.5, leading=11, spaceAfter=5))
    styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=7, leading=8.5, textColor=colors.HexColor("#555555"), spaceAfter=3))
    story = []
    story.append(Paragraph("Meridian Parts", styles["Title2"]))
    story.append(Paragraph("European service-hub expansion | board decision report", styles["Heading2"]))
    story.append(Paragraph("Decision basis: 2025 shipped sales and returns known through 31 January 2026; frozen source room collected 27 September 2026 UTC. All client exports and hub assumptions are synthetic. World Bank and ECB series are archived public snapshots.", styles["Smallx"]))
    rec = d["recommendation"]
    option_label = "+".join(rec["countries"])
    best = d["hub_scenarios"].query("country == @option_label and scenario == 'base'").iloc[0]
    story.append(Spacer(1, 8))
    story.append(Paragraph("Recommendation", styles["H1x"]))
    story.append(Paragraph(f"Fund a staged two-hub pilot for <b>{' + '.join(rec['countries'])}</b>, with year-zero capex of <b>{money(rec['capex_eur'])}</b> and <b>{rec['fte']} FTE</b>, subject to the 90-day gates below. The base policy case implies {money(best['incremental_contribution_eur'])} annual incremental contribution and {float(best['payback_years']):.2f}-year simple payback; this is a planning estimate, not a proven causal effect.", styles["Bodyx"]))
    story.append(Paragraph(f"The choice is supported by trade-off analysis: the selected pair is the highest base-case feasible alternative. It gives up the lower capex of {d['hub_scenarios'].query("country == 'CZE' and scenario == 'base'").iloc[0]['capex_eur'] if False else 'single-hub options'} in exchange for more modeled contribution. The strongest alternative is <b>{rec['strongest_alternative']}</b> at {money(rec['strongest_alternative_base_annual_incremental_contribution_eur'])} annual incremental contribution. Defer remains valid if the pilot cannot validate the volume uplift/savings assumptions or the stress case is judged more credible.", styles["Bodyx"]))
    story.append(Paragraph("Executive diagnosis", styles["H1x"]))
    c = d["countries"].copy(); c["name"] = c.country.map(COUNTRY_NAMES); c = c.sort_values("contribution_eur", ascending=False)
    diagnosis = [
        ["Market / operating base", "2025 net sales", "Contribution", "Margin", "Units", "Returned units"],
    ] + [[r["name"], money(r["net_sales_eur"]), money(r["contribution_eur"]), pct(r["margin"]), f"{int(r['shipped_units']):,}", f"{int(r['returned_units']):,}"] for _, r in c.iterrows()]
    t = RLTable(diagnosis, colWidths=[3.0*cm,2.5*cm,2.5*cm,1.6*cm,1.8*cm,2.0*cm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#B7C9D6")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EFF5F9")]),("ALIGN",(1,1),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(t)
    story.append(Paragraph("Operationally, contribution is concentrated in the larger EUR markets, while POL/CZE carry the only non-EUR translation exposure. Population and GDP per capita provide context only; they are not direct evidence of replacement-assembly demand.", styles["Bodyx"]))
    story.append(Paragraph("Accounting and evidence reconciliation", styles["H1x"]))
    story.append(Paragraph(f"The order extracts contain {d['quality']['raw_order_rows']:,} rows. Exact repeated rows were collapsed, then the highest numeric revision per order_id was retained; {d['quality']['excluded_order_rows_after_revision_winner']} post-revision rows were excluded for status/test/date rules. Free or zero-price shipments were retained ({d['quality']['zero_price_shipments_included']}). Returns were deduplicated by highest revision per return_id, added across legitimate IDs, and limited to eligible linked orders received by the inclusive cutoff. {d['quality']['orphan_returns_quarantined']} orphan return(s) were quarantined and {d['quality']['late_returns_after_cutoff_excluded']} late return(s) excluded; neither was joined by guess.", styles["Bodyx"]))
    story.append(Paragraph("For EUR orders the rate is 1. For PLN and CZK, each sale and its summed refund use the original sale month’s arithmetic mean of available ECB business-day reference observations, quoted as local currency units per EUR. Individual monetary components are half-up rounded to cents before summation. Gross sales are booked sales after discount; cash can differ because refunds/settlement timing and FX differ; contribution further subtracts net COGS and nonrefundable fulfillment.", styles["Bodyx"]))
    story.append(Paragraph("Core evidence links: [S-pop] archived World Bank population snapshot; [S-gdp] archived World Bank GDP-per-capita snapshot; [S-ecb] archived ECB historical FX archive; [S-client] synthetic source-room exports, dictionary and policy. Full URLs, hashes, periods, units and retrieval metadata are in the source register and workbook.", styles["Smallx"]))
    story.append(PageBreak())
    story.append(Paragraph("Market context", styles["H1x"]))
    ctx = d["market_context"].copy(); ctx["name"] = ctx.country.map(COUNTRY_NAMES)
    piv = ctx.pivot(index="name", columns="year", values=["population","gdp_per_capita_usd"])
    headers=["Market","Pop 2022","Pop 2024","Change","GDP pc 2022","GDP pc 2024"]
    rows=[headers]
    for name in [COUNTRY_NAMES[x] for x in COUNTRIES]:
        rr=ctx[ctx.name.eq(name)].set_index("year")
        p22=rr.loc[2022,"population"]; p24=rr.loc[2024,"population"]; g22=rr.loc[2022,"gdp_per_capita_usd"]; g24=rr.loc[2024,"gdp_per_capita_usd"]
        chg=(p24/p22-1) if p22 and p24 else None
        rows.append([name, f"{p22:,.0f}" if pd.notna(p22) else "—", f"{p24:,.0f}" if pd.notna(p24) else "—", pct(chg), f"${g22:,.0f}" if pd.notna(g22) else "—", f"${g24:,.0f}" if pd.notna(g24) else "—"])
    mt=RLTable(rows,colWidths=[3*cm,2.3*cm,2.3*cm,1.6*cm,2.6*cm,2.6*cm],repeatRows=1); mt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#B7C9D6")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EFF5F9")]),("ALIGN",(1,1),(-1,-1),"RIGHT")]))
    story.append(mt)
    story.append(Paragraph("The archived World Bank responses carry a 2026-07-13 last-updated metadata vintage. The measures are descriptive context in current US dollars and persons; they should not be read as demand forecasts, market shares or causal evidence for a hub.", styles["Bodyx"]))
    story.append(Paragraph("Scenario comparison", styles["H1x"]))
    scen = d["hub_scenarios"].query("scenario in ['low','base','high','stress']").copy()
    base_s = scen[scen.scenario.eq("base")].sort_values("incremental_contribution_eur", ascending=False).head(10)
    srows=[["Option","Low","Base","High","Stress","Capex","FTE"]]
    for option in base_s.country:
        rr=scen[scen.country.eq(option)].set_index("scenario")
        srows.append([option]+[money(rr.loc[x,"incremental_contribution_eur"]) for x in ["low","base","high","stress"]]+[money(rr.loc["base","capex_eur"]), int(rr.loc["base","fte"])])
    st=RLTable(srows,colWidths=[2.4*cm,2.0*cm,2.0*cm,2.0*cm,2.0*cm,2.0*cm,1.0*cm],repeatRows=1); st.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),6.5),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#B7C9D6")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EFF5F9")]),("ALIGN",(1,1),(-1,-1),"RIGHT")]))
    story.append(st)
    story.append(Paragraph("Hard constraints are EUR450,000 year-zero capex, seven FTE, and at most two hubs. Annual incremental contribution excludes capex; payback is simple undiscounted capex divided by positive annual contribution. Pairs add country arithmetic with no synergy. The stress column is the policy’s joint stress, not a probability forecast.", styles["Bodyx"]))
    story.append(Paragraph("What changes the decision", styles["H1x"]))
    story.append(Paragraph(f"The recommendation should be reopened if measured pilot evidence cannot support the assumed uplift/savings run-rate; if actual capex or staffing breaches the hard budget; if return behavior or PLN/CZK FX makes the defined stress case the more credible operating case; or if a stronger alternative becomes demonstrably executable at lower risk. Under the defined stress, {rec['stress_case_leader']} is the strongest alternative at {money(rec['stress_case_leader_annual_incremental_contribution_eur'])} annual incremental contribution, versus {money(best['incremental_contribution_eur'])} for the selected base leader. Those are observable gates, not claims about statistical certainty.", styles["Bodyx"]))
    story.append(PageBreak())
    story.append(Paragraph("90-day implementation and KPI plan", styles["H1x"]))
    plan = [
        ["Timing / owner", "Action and dependency", "Decision gate / KPI"],
        ["Days 0–15 | COO + Finance", "Confirm site shortlist, carrier lanes, labor plan, capex quotes and local tax/returns process. Dependency: vendor quotes and legal/finance review.", "Gate 1: capex ≤ EUR450k, FTE ≤7, named owners. KPI baseline: order-to-delivery, fulfillment EUR/order, return rate, contribution/order."],
        ["Days 16–45 | Operations + Commercial", "Run controlled service-level and routing pilot for selected countries using existing central-hub flows; instrument promised vs actual delivery, conversion/volume, and savings per unit.", "Gate 2: measured uplift and savings trend toward base assumptions; no material service-level regression. KPI: on-time %, lead-time p50/p90, incremental units, saving EUR/unit."],
        ["Days 46–75 | Finance + Data", "Reconcile pilot invoices/refunds, FX translation and COGS recovery; stress-test return and FX cases; finalize staffing and launch readiness.", "Gate 3: data-quality sign-off; KPI: refund rate, returned units, net sales, net COGS, contribution margin, FX variance."],
        ["Days 76–90 | Board sponsor + COO", "Approve, resize, defer or switch to strongest alternative based on observed run-rate and constraints.", "Go/no-go: fund only if evidence supports the selected case and risk controls; otherwise defer or choose the next feasible option."],
    ]
    table_cell = ParagraphStyle(name="TableCell", parent=styles["Smallx"], fontSize=6.6, leading=8)
    plan_wrapped = [[Paragraph(str(cell), table_cell) for cell in row] for row in plan]
    pt=RLTable(plan_wrapped,colWidths=[3.0*cm,7.3*cm,6.0*cm],repeatRows=1); pt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#B7C9D6")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EFF5F9")]),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(pt)
    story.append(Paragraph("Risks and mitigations", styles["H1x"]))
    story.append(Paragraph("Demand uplift risk: validate incrementality during the pilot and hold capex until Gate 3. Return-rate risk: use return rate and returned units as explicit stop metrics; do not assume every return recovers product cost. FX risk: preserve sale-month ECB translation and monitor PLN/CZK variance; the stress case is a guardrail. Execution risk: stage staffing and site commitments; use the hard FTE/capex limits. Evidence risk: synthetic client inputs and no interviews mean this is a decision support model, not field validation.", styles["Bodyx"]))
    story.append(Paragraph("Limitations and reproducibility", styles["H1x"]))
    story.append(Paragraph("No customer interviews, live account access, demand elasticity study, competitor data, labor quotes, tax/legal review, actual transaction FX, or discounted cash flow were available. The raw source room is saved under evidence/raw with SHA-256 hashes and original public URLs. Run python3 scripts/build_deliverables.py to regenerate metrics.json, the XLSX, this PDF and the PPTX from saved inputs.", styles["Bodyx"]))
    story.append(Paragraph("Source register identifiers: S-pop = population.json; S-gdp = gdp-per-capita.json; S-ecb = ecb-history.zip/csv; S-client = synthetic source-room files. See deliverables/source-register.csv.", styles["Smallx"]))
    doc = SimpleDocTemplate(str(OUT / "meridian_parts_board_report.pdf"), pagesize=A4, rightMargin=1.35*cm, leftMargin=1.35*cm, topMargin=1.2*cm, bottomMargin=1.2*cm, title="Meridian Parts board report")
    doc.build(story)


def add_textbox(slide, x, y, w, h, text, size=18, color=(31,78,121), bold=False, align=PP_ALIGN.LEFT):
    box=slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h)); tf=box.text_frame; tf.clear(); tf.word_wrap=True
    p=tf.paragraphs[0]; p.alignment=align; r=p.add_run(); r.text=text; r.font.name="Aptos"; r.font.size=Pt(size); r.font.bold=bold; r.font.color.rgb=RGBColor(*color); return box


def make_presentation(d: dict[str, Any]) -> None:
    prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5)
    navy=(31,78,121); dark=(45,45,45); blue=(47,85,151); light=(239,245,249); green=(31,120,80); red=(170,60,50)
    def slide(title, subtitle=None):
        s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=RGBColor(255,255,255)
        add_textbox(s,0.55,0.35,12.2,0.55,title,25,navy,True)
        if subtitle: add_textbox(s,0.58,0.95,12.1,0.35,subtitle,10,(95,95,95))
        return s
    # 1
    s=prs.slides.add_slide(prs.slide_layouts[6]); s.background.fill.solid(); s.background.fill.fore_color.rgb=RGBColor(*navy)
    add_textbox(s,0.8,1.1,11.8,1.3,"Meridian Parts",30,(255,255,255),True); add_textbox(s,0.85,2.5,11.2,1.0,"European service-hub expansion",27,(220,235,245),True); add_textbox(s,0.85,3.75,10.9,0.7,"Board decision | 2025 shipped-sales evidence + staged 90-day validation",15,(255,255,255)); add_textbox(s,0.85,6.65,11.5,0.35,"Synthetic client inputs; archived public World Bank and ECB snapshots; 27 Sep 2026 vintage",9,(210,225,235))
    # 2
    s=slide("Decision in one sentence","Fund a staged pilot, with explicit stop gates")
    rec=d["recommendation"]; option_label="+".join(rec["countries"]); best=d["hub_scenarios"].query("country == @option_label and scenario == 'base'").iloc[0]
    add_textbox(s,0.7,1.55,12,0.65,f"Recommend: {' + '.join(rec['countries'])} | {money(rec['capex_eur'])} capex | {rec['fte']} FTE",24,green,True)
    add_textbox(s,0.75,2.45,5.6,1.6,f"Base policy case\n{money(best['incremental_contribution_eur'])} annual incremental contribution\n{float(best['payback_years']):.2f}-year simple payback",18,dark,True)
    add_textbox(s,6.7,2.45,5.7,1.6,f"Decision guard\n90-day validation of uplift, savings, returns, FX and budget\nNo claim of causal certainty",18,dark,True)
    add_textbox(s,0.75,5.25,11.5,0.8,"Defer all hubs remains the correct action if measured evidence cannot support the planning case or hard constraints are breached.",16,red,True)
    # 3
    s=slide("What the 2025 base says","Contribution, not booked revenue or cash")
    c=d["countries"].copy().sort_values("contribution_eur",ascending=False)
    headers=["Market","Net sales","Contribution","Margin","Units"]
    rows=[[x for x in headers]]+[[COUNTRY_NAMES[r.country],money(r.net_sales_eur),money(r.contribution_eur),pct(r.margin),f"{int(r.shipped_units):,}"] for r in c.itertuples()]
    tb=s.shapes.add_table(len(rows),len(headers),Inches(0.75),Inches(1.55),Inches(11.8),Inches(4.5)).table
    for i,row in enumerate(rows):
        for j,val in enumerate(row):
            cell=tb.cell(i,j); cell.text=str(val); cell.fill.solid(); cell.fill.fore_color.rgb=RGBColor(*(navy if i==0 else (245,249,252) if i%2==0 else (255,255,255)))
            for p in cell.text_frame.paragraphs:
                p.font.size=Pt(11); p.font.name="Aptos"; p.font.color.rgb=RGBColor(*(255,255,255) if i==0 else dark); p.font.bold=(i==0); p.alignment=PP_ALIGN.RIGHT if j else PP_ALIGN.LEFT
    add_textbox(s,0.8,6.35,11.5,0.45,"Larger EUR markets supply the operating base; POL/CZE add non-EUR translation exposure and require sale-month ECB rates.",11,dark)
    # 4
    s=slide("The comparison is constrained and transparent","Hard limits: EUR450k capex, 7 FTE, max two hubs")
    bs=d["hub_scenarios"][d["hub_scenarios"].scenario.eq("base")].sort_values("incremental_contribution_eur",ascending=False).head(8)
    rows=[["Option","Low","Base","High","Stress"]]+[[r.country]+[money(d["hub_scenarios"].query("country == @r.country and scenario == @sc").iloc[0].incremental_contribution_eur) for sc in ["low","base","high","stress"]] for r in bs.itertuples()]
    tb=s.shapes.add_table(len(rows),5,Inches(0.55),Inches(1.35),Inches(12.2),Inches(5.3)).table
    for i,row in enumerate(rows):
        for j,val in enumerate(row):
            cell=tb.cell(i,j); cell.text=str(val); cell.fill.solid(); cell.fill.fore_color.rgb=RGBColor(*(navy if i==0 else (235,247,239) if i==1 else (245,249,252) if i%2==0 else (255,255,255)))
            for p in cell.text_frame.paragraphs: p.font.size=Pt(9); p.font.name="Aptos"; p.font.color.rgb=RGBColor(*(255,255,255) if i==0 else dark); p.font.bold=(i==0 or (i==1 and j==0)); p.alignment=PP_ALIGN.RIGHT if j else PP_ALIGN.LEFT
    # 5
    s=slide("Evidence and accounting controls","Reconciliation is part of the recommendation, not an appendix")
    controls=[
        ("Revision control","Highest numeric revision per order_id and return_id; exact repeats collapsed."),
        ("Eligibility","Shipped, non-test, shipped in 2025; Jan 2026 orders excluded from 2025 base."),
        ("Returns","Cutoff inclusive through 31 Jan 2026; orphan returns quarantined; legitimate IDs additive."),
        ("FX","Original sale-month mean ECB business-day quote; PLN/CZK not inverted; EUR=1."),
        ("Rounding","Order-level half-up cents before aggregation; zero-price shipments retained."),
    ]
    for i,(a,b) in enumerate(controls):
        add_textbox(s,0.85,1.45+i*0.85,2.15,0.35,a,15,blue,True); add_textbox(s,3.1,1.45+i*0.85,9.1,0.42,b,14,dark)
    add_textbox(s,0.85,6.0,11.5,0.65,"Known limits: synthetic client data, no interviews or live account access, no actual transaction FX or full DCF. Public World Bank/ECB inputs are archived snapshots.",12,red,True)
    # 6
    s=slide("90-day implementation","Stage the irreversible commitments")
    phases=[("0–15","COO + Finance","Quotes, sites, labor, tax/returns review","Gate: capex/FTE within limits"),("16–45","Operations + Commercial","Controlled routing/service pilot","KPI: uplift, savings, on-time %"),("46–75","Finance + Data","Reconcile refunds, FX, COGS recovery","Gate: data sign-off, stress test"),("76–90","Board sponsor + COO","Approve, resize, defer or switch","Go/no-go on measured run-rate")]
    for i,(days,owner,act,gate) in enumerate(phases):
        y=1.35+i*1.25; add_textbox(s,0.75,y,1.0,0.35,days,16,blue,True); add_textbox(s,1.9,y,2.2,0.35,owner,14,navy,True); add_textbox(s,4.3,y,4.3,0.45,act,13,dark); add_textbox(s,8.8,y,3.7,0.45,gate,12,green,True)
    # 7
    s=slide("What would change the decision","Observable flip conditions")
    flips=["Pilot cannot support the modeled uplift/savings run-rate.","Capex exceeds EUR450k or staffing exceeds seven FTE.","Returns or PLN/CZK FX make the defined stress case more credible.","The strongest alternative becomes executable with lower delivery risk.","Data reconciliation fails at the Gate 3 sign-off."]
    for i,x in enumerate(flips): add_textbox(s,1.0,1.45+i*0.8,11.0,0.45,"• "+x,17,red if i<3 else dark,True if i<3 else False)
    add_textbox(s,1.0,6.0,11.2,0.5,"The recommendation is supported by the current planning evidence, but it is not statistically proven, causal or certain.",14,navy,True)
    # 8
    s=slide("Board action","Approve a gated pilot, preserve the option to defer")
    add_textbox(s,0.9,1.4,11.4,0.75,f"Authorize preparatory work for {' + '.join(rec['countries'])}: {money(rec['capex_eur'])} capex envelope and {rec['fte']} FTE envelope.",22,green,True)
    add_textbox(s,0.95,2.75,11.2,1.8,"At Day 90, release full commitments only if the evidence supports the operating case. If not, defer or fund the strongest alternative. The analytical workbook, metrics JSON, raw evidence and build script are the audit trail.",17,dark)
    add_textbox(s,0.95,5.9,11.2,0.55,"Source register and reproducibility: deliverables/source-register.csv | scripts/build_deliverables.py",11,(95,95,95))
    prs.save(OUT / "meridian_parts_board_presentation.pptx")


def main():
    reg = source_register()
    d = load_and_calculate()
    make_metrics(d)
    make_workbook(d, reg)
    make_report(d, reg)
    make_presentation(d)
    # Human-readable build summary for verification.
    summary = {
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "deliverables": [p.name for p in sorted(OUT.iterdir()) if p.is_file()],
        "recommendation": d["recommendation"],
        "monthly_rows": len(d["monthly"]),
        "country_rows": len(d["countries"]),
        "scenario_rows": len(d["hub_scenarios"]),
    }
    write_json(ROOT / "analysis_output" / "build_summary.json", summary)
    print(json.dumps(jsafe(summary), indent=2))


if __name__ == "__main__":
    main()
