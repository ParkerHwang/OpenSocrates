#!/usr/bin/env python3
"""Reproduce Meridian Parts' analysis and deliverables from saved source-room inputs.

Run from the project root:
    python analysis/reproduce.py

The script intentionally keeps all source-room files immutable under evidence/raw.
It writes derived outputs and board materials under deliverables/.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import itertools
import json
import math
import os
import re
import shutil
import sys
import textwrap
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

_EARLY_ROOT = Path(__file__).resolve().parents[1]
_LOCAL_DEPS = _EARLY_ROOT / ".deps"
if _LOCAL_DEPS.exists():
    sys.path.append(str(_LOCAL_DEPS))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Flowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table as RLTable,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence" / "raw"
DEFAULT_OUT = ROOT / "deliverables"
LOCAL_DEPS = ROOT / ".deps"
if LOCAL_DEPS.exists():
    sys.path.append(str(LOCAL_DEPS))
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
MONTHS = [f"2025-{i:02d}" for i in range(1, 13)]
MONEY_FIELDS = [
    "gross_sales_eur",
    "refunds_eur",
    "net_sales_eur",
    "net_cogs_eur",
    "fulfillment_eur",
    "contribution_eur",
]
DEC_CENT = Decimal("0.01")


def d(value: Any) -> Decimal:
    if value is None or (isinstance(value, float) and math.isnan(value)) or pd.isna(value):
        return Decimal("0")
    return Decimal(str(value))


def q2(value: Any) -> Decimal:
    return d(value).quantize(DEC_CENT, rounding=ROUND_HALF_UP)


def f2(value: Any) -> float:
    return float(q2(value))


def f6(value: Any) -> float:
    return float(d(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported JSON value: {type(value)}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=json_default) + "\n", encoding="utf-8")


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def load_orders() -> tuple[pd.DataFrame, dict[str, Any]]:
    files = ["orders-part1.csv", "orders-part2.csv", "order-corrections.csv"]
    frames: list[pd.DataFrame] = []
    for source_file in files:
        frame = pd.read_csv(RAW / source_file)
        frame["source_file_calc"] = source_file
        frame["source_row_calc"] = np.arange(2, len(frame) + 2)
        frames.append(frame)
    raw = pd.concat(frames, ignore_index=True)
    raw_order_ids = int(raw["order_id"].nunique())
    max_rev = raw.groupby("order_id")["revision"].transform("max")
    highest = raw.loc[raw["revision"].eq(max_rev)].copy()
    same_revision_repeat_rows_removed = int(len(highest) - highest["order_id"].nunique())
    selected = (
        raw.sort_values(["order_id", "revision", "source_file_calc", "source_row_calc"])
        .drop_duplicates("order_id", keep="last")
        .copy()
    )
    replacement_ids = raw.groupby("order_id")["revision"].agg(lambda s: int(s.max()) > int(s.min()))
    selected["ship_date_calc"] = pd.to_datetime(selected["shipped_at"], errors="coerce")
    selected["_exclusion_reason"] = "eligible"
    selected.loc[selected["status"].ne("shipped"), "_exclusion_reason"] = "status_not_shipped"
    selected.loc[selected["status"].eq("shipped") & selected["is_test"], "_exclusion_reason"] = "test_transaction"
    selected.loc[
        selected["status"].eq("shipped")
        & ~selected["is_test"]
        & ~selected["ship_date_calc"].dt.year.eq(2025),
        "_exclusion_reason",
    ] = "shipment_outside_2025"
    eligible = selected.loc[selected["_exclusion_reason"].eq("eligible")].copy()
    eligible["month"] = eligible["ship_date_calc"].dt.to_period("M").astype(str)
    eligible["currency_expected"] = eligible["country"].map(COUNTRY_CURRENCY)
    quality = {
        "raw_rows": int(len(raw)),
        "unique_order_ids": raw_order_ids,
        "deduplicated_rows": int(len(selected)),
        "duplicate_order_rows_removed": int(len(raw) - len(selected)),
        "same_revision_repeat_rows_removed": same_revision_repeat_rows_removed,
        "higher_revision_replacements": int(replacement_ids.sum()),
        "eligible_orders": int(len(eligible)),
        "excluded_by_reason": selected.loc[selected["_exclusion_reason"].ne("eligible"), "_exclusion_reason"].value_counts().to_dict(),
        "zero_price_orders_raw": int(raw["unit_price_local"].eq(0).sum()),
        "zero_price_orders_eligible": int(eligible["unit_price_local"].eq(0).sum()),
        "currency_mismatches": int(eligible["currency"].ne(eligible["currency_expected"]).sum()),
        "missing_required_values_eligible": int(eligible.isna().any(axis=1).sum()),
    }
    return eligible, {"selected": selected, "raw": raw, "quality": quality}


def load_returns(eligible_orders: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    raw = pd.read_csv(RAW / "returns.csv")
    raw["_source_row"] = np.arange(2, len(raw) + 2)
    max_rev = raw.groupby("return_id")["revision"].transform("max")
    highest = raw.loc[raw["revision"].eq(max_rev)].copy()
    same_revision_repeat_rows_removed = int(len(highest) - highest["return_id"].nunique())
    selected = (
        raw.sort_values(["return_id", "revision", "_source_row"])
        .drop_duplicates("return_id", keep="last")
        .copy()
    )
    selected["_received_date"] = pd.to_datetime(selected["received_at"], errors="coerce")
    selected["_reason"] = "eligible_return"
    selected.loc[selected["_received_date"] > pd.Timestamp("2026-01-31"), "_reason"] = "received_after_cutoff"
    selected.loc[
        selected["_reason"].eq("eligible_return") & ~selected["order_id"].isin(set(eligible_orders["order_id"])),
        "_reason",
    ] = "orphan_or_ineligible_order"
    usable = selected.loc[selected["_reason"].eq("eligible_return")].copy()
    order_meta = eligible_orders.set_index("order_id")[["country", "currency", "month"]]
    usable = usable.join(order_meta, on="order_id", rsuffix="_order")
    replacement_ids = raw.groupby("return_id")["revision"].agg(lambda s: int(s.max()) > int(s.min()))
    quality = {
        "raw_rows": int(len(raw)),
        "unique_return_ids": int(raw["return_id"].nunique()),
        "deduplicated_rows": int(len(selected)),
        "duplicate_return_rows_removed": int(len(raw) - len(selected)),
        "same_revision_repeat_rows_removed": same_revision_repeat_rows_removed,
        "higher_revision_replacements": int(replacement_ids.sum()),
        "usable_returns": int(len(usable)),
        "excluded_by_reason": selected.loc[selected["_reason"].ne("eligible_return"), "_reason"].value_counts().to_dict(),
        "orphan_return_ids": sorted(selected.loc[selected["_reason"].eq("orphan_or_ineligible_order"), "return_id"].tolist()),
        "received_cutoff_inclusive": "2026-01-31",
        "missing_required_values_selected": int(selected.isna().any(axis=1).sum()),
    }
    return usable, {"selected": selected, "raw": raw, "quality": quality}


def load_fx() -> tuple[dict[tuple[str, str], Decimal], pd.DataFrame, dict[str, Any]]:
    ecb = pd.read_csv(RAW / "ecb-history.csv", dtype=str)
    ecb["Date"] = pd.to_datetime(ecb["Date"], errors="coerce")
    records: list[dict[str, Any]] = []
    lookup: dict[tuple[str, str], Decimal] = {}
    for currency in ["PLN", "CZK"]:
        for month in MONTHS:
            values: list[Decimal] = []
            month_mask = ecb["Date"].dt.to_period("M").astype(str).eq(month)
            for raw_value in ecb.loc[month_mask, currency].tolist():
                if raw_value is None or str(raw_value).strip().upper() in {"N/A", "", "NAN"}:
                    continue
                values.append(d(raw_value))
            if not values:
                raise ValueError(f"No ECB observations for {currency} {month}")
            mean = sum(values, Decimal("0")) / Decimal(len(values))
            lookup[(currency, month)] = mean
            records.append({"currency": currency, "month": month, "local_per_eur": f6(mean), "observations": len(values)})
    fx = pd.DataFrame(records)
    quality = {
        "source_file": "ecb-history.csv",
        "quote_definition": "local currency units per EUR; EUR=1.0",
        "months": len(MONTHS),
        "currencies": ["PLN", "CZK"],
        "observation_counts": {f"{r.currency}_{r.month}": int(r.observations) for r in fx.itertuples()},
        "missing_months": [],
    }
    return lookup, fx, quality


def load_unit_costs() -> pd.DataFrame:
    costs = pd.read_csv(RAW / "unit-costs.csv")
    costs["valid_from"] = pd.to_datetime(costs["valid_from"])
    return costs.sort_values(["sku", "valid_from"])


def build_order_detail(eligible: pd.DataFrame, returns: pd.DataFrame, fx_lookup: dict[tuple[str, str], Decimal], costs: pd.DataFrame) -> pd.DataFrame:
    refund_map = returns.groupby("order_id", as_index=True).agg(
        refund_local=("refund_local", "sum"),
        returned_units=("quantity", "sum"),
        restocked_units=("restocked_quantity", "sum"),
        return_records=("return_id", "count"),
    )
    rows: list[dict[str, Any]] = []
    missing_costs: list[str] = []
    for row in eligible.sort_values(["country", "ship_date_calc", "order_id"]).itertuples(index=False):
        sku_costs = costs.loc[costs["sku"].eq(row.sku) & costs["valid_from"].le(row.ship_date_calc)]
        if sku_costs.empty:
            missing_costs.append(row.order_id)
            raise ValueError(f"No effective unit cost for {row.order_id}")
        unit_cost = d(sku_costs.iloc[-1]["unit_cost_eur"])
        currency = str(row.currency)
        month = str(row.month)
        fx = Decimal("1") if currency == "EUR" else fx_lookup[(currency, month)]
        refund_local = d(refund_map.loc[row.order_id, "refund_local"]) if row.order_id in refund_map.index else Decimal("0")
        returned_units = int(refund_map.loc[row.order_id, "returned_units"]) if row.order_id in refund_map.index else 0
        restocked_units = int(refund_map.loc[row.order_id, "restocked_units"]) if row.order_id in refund_map.index else 0
        return_records = int(refund_map.loc[row.order_id, "return_records"]) if row.order_id in refund_map.index else 0
        gross_local = d(row.quantity) * d(row.unit_price_local) - d(row.discount_local)
        gross_eur = q2(gross_local / fx)
        refunds_eur = q2(refund_local / fx)
        gross_cogs = q2(d(row.quantity) * unit_cost)
        recovered_cogs = q2(d(restocked_units) * unit_cost)
        net_cogs = q2(gross_cogs - recovered_cogs)
        fulfillment = q2(row.fulfillment_eur)
        net_sales = q2(gross_eur - refunds_eur)
        contribution = q2(gross_eur - refunds_eur - net_cogs - fulfillment)
        rows.append(
            {
                "order_id": row.order_id,
                "source_file": row.source_file_calc,
                "revision": int(row.revision),
                "country": row.country,
                "shipped_at": row.ship_date_calc.strftime("%Y-%m-%d"),
                "month": month,
                "status": row.status,
                "is_test": bool(row.is_test),
                "sku": row.sku,
                "quantity": int(row.quantity),
                "unit_price_local": float(row.unit_price_local),
                "discount_local": float(row.discount_local),
                "currency": currency,
                "fx_local_per_eur": f6(fx),
                "gross_sales_local": float(q2(gross_local)),
                "gross_sales_eur": float(gross_eur),
                "refund_local": float(q2(refund_local)),
                "refunds_eur": float(refunds_eur),
                "returned_units": returned_units,
                "restocked_units": restocked_units,
                "return_records": return_records,
                "unit_cost_eur": float(unit_cost),
                "gross_cogs_eur": float(gross_cogs),
                "recovered_cogs_eur": float(recovered_cogs),
                "net_cogs_eur": float(net_cogs),
                "fulfillment_eur": float(fulfillment),
                "net_sales_eur": float(net_sales),
                "contribution_eur": float(contribution),
            }
        )
    detail = pd.DataFrame(rows)
    if missing_costs:
        raise ValueError(f"Missing costs for {missing_costs}")
    return detail


def aggregate_metrics(group: pd.DataFrame) -> dict[str, Any]:
    if group.empty:
        result = {"shipped_orders": 0, "shipped_units": 0, **{field: 0.0 for field in MONEY_FIELDS}, "returned_units": 0, "margin": None}
        return result
    result: dict[str, Any] = {
        "shipped_orders": int(group["order_id"].nunique()),
        "shipped_units": int(group["quantity"].sum()),
        "gross_sales_eur": f2(group["gross_sales_eur"].sum()),
        "refunds_eur": f2(group["refunds_eur"].sum()),
        "net_sales_eur": f2(group["net_sales_eur"].sum()),
        "net_cogs_eur": f2(group["net_cogs_eur"].sum()),
        "fulfillment_eur": f2(group["fulfillment_eur"].sum()),
        "contribution_eur": f2(group["contribution_eur"].sum()),
        "returned_units": int(group["returned_units"].sum()),
    }
    result["margin"] = None if abs(result["net_sales_eur"]) < 0.005 else round(result["contribution_eur"] / result["net_sales_eur"], 6)
    return result


def build_metrics(detail: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    monthly_rows: list[dict[str, Any]] = []
    for country in COUNTRIES:
        for month in MONTHS:
            row = {"country": country, "month": month}
            row.update(aggregate_metrics(detail.loc[detail["country"].eq(country) & detail["month"].eq(month)]))
            monthly_rows.append(row)
    monthly = pd.DataFrame(monthly_rows)
    country_rows: list[dict[str, Any]] = []
    for country in COUNTRIES:
        row = {"country": country}
        row.update(aggregate_metrics(detail.loc[detail["country"].eq(country)]))
        country_rows.append(row)
    countries = pd.DataFrame(country_rows)
    return monthly, countries


def load_market_context() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for filename in ["population.json", "gdp-per-capita.json"]:
        payload = json.loads((RAW / filename).read_text(encoding="utf-8"))
        indicator_rows = payload[1]
        for item in indicator_rows:
            rows.append(
                {
                    "country": item["countryiso3code"],
                    "year": int(item["date"]),
                    "population": int(item["value"]) if filename == "population.json" else None,
                    "gdp_per_capita_usd": float(item["value"]) if filename == "gdp-per-capita.json" else None,
                }
            )
    market = pd.DataFrame(rows).groupby(["country", "year"], as_index=False).agg({"population": "max", "gdp_per_capita_usd": "max"})
    market["country"] = pd.Categorical(market["country"], COUNTRIES, ordered=True)
    market = market.sort_values(["country", "year"]).copy()
    market["country"] = market["country"].astype(str)
    return market


def build_scenarios(countries: pd.DataFrame, options: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    base = countries.set_index("country").copy()
    opt = options.set_index("country").loc[COUNTRIES].copy()
    all_options: list[tuple[str, list[str], bool]] = [(c, [c], True) for c in COUNTRIES]
    for a, b in itertools.combinations(COUNTRIES, 2):
        capex = int(opt.loc[a, "capex_eur"] + opt.loc[b, "capex_eur"])
        fte = int(opt.loc[a, "fte"] + opt.loc[b, "fte"])
        all_options.append((f"{a}+{b}", [a, b], capex <= 450_000 and fte <= 7))
    all_options.append(("DEFER", [], True))
    rows: list[dict[str, Any]] = []
    for option_name, members, feasible in all_options:
        if not feasible:
            continue
        if members:
            C = d(base.loc[members, "contribution_eur"].sum())
            U = d(base.loc[members, "shipped_units"].sum())
            G = d(base.loc[members, "gross_sales_eur"].sum())
            N = d(base.loc[members, "net_sales_eur"].sum())
            K = d(opt.loc[members, "capex_eur"].sum())
            F = d(opt.loc[members, "annual_fixed_eur"].sum())
            fte = int(opt.loc[members, "fte"].sum())
            saving = d(0)
            for member in members:
                saving += d(base.loc[member, "shipped_units"]) * d(opt.loc[member, "saving_eur_per_unit"])
            # This is country additive by policy; keeping a separate map makes the stress transparent.
            country_stress = {}
            for member in members:
                c = d(base.loc[member, "contribution_eur"])
                u = d(base.loc[member, "shipped_units"])
                g = d(base.loc[member, "gross_sales_eur"])
                n = d(base.loc[member, "net_sales_eur"])
                fx_shock = d("0.10") * n if COUNTRY_CURRENCY[member] in {"PLN", "CZK"} else d("0")
                c_stress = c - d("0.03") * g - fx_shock
                country_stress[member] = c_stress * d("1.25") - c + u * d("1.25") * d(opt.loc[member, "saving_eur_per_unit"]) - d(opt.loc[member, "annual_fixed_eur"])
            stress_increment = sum(country_stress.values(), d("0"))
        else:
            C = U = G = N = K = F = saving = d("0")
            fte = 0
            stress_increment = d("0")
        increments = {
            "low": C * d("0.10") + saving * d("1.10") - F,
            "base": C * d("0.25") + saving * d("1.25") - F,
            "high": C * d("0.40") + saving * d("1.40") - F,
            "stress": stress_increment,
        }
        for scenario in ["low", "base", "high", "stress"]:
            inc = q2(increments[scenario])
            payback = None if inc <= 0 else float(K / inc)
            rows.append(
                {
                    "country": option_name,
                    "scenario": scenario,
                    "incremental_contribution_eur": float(inc),
                    "capex_eur": int(K),
                    "fte": fte,
                    "payback_years": payback,
                    "feasible": True,
                    "members": "+".join(members) if members else "",
                    "baseline_contribution_eur": float(q2(C)),
                    "shipped_units": int(U),
                    "gross_sales_eur": float(q2(G)),
                    "net_sales_eur": float(q2(N)),
                    "annual_fixed_eur": int(F),
                    "savings_at_base_volume_eur": float(q2(saving * d("1.25"))),
                }
            )
    scenarios = pd.DataFrame(rows)
    scenarios["option_order"] = scenarios["country"].map({name: i for i, (name, _, _) in enumerate(all_options)})
    scenarios = scenarios.sort_values(["option_order", "scenario"], key=lambda s: s.map({"low": 0, "base": 1, "high": 2, "stress": 3}).fillna(s) if s.name == "scenario" else s).reset_index(drop=True)
    # Feasible alternatives ranked by base economics; DEFER is the comparator, not a hub.
    base_rank = scenarios.loc[scenarios["scenario"].eq("base")].sort_values("incremental_contribution_eur", ascending=False).copy()
    base_rank["base_rank"] = range(1, len(base_rank) + 1)
    scenarios = scenarios.merge(base_rank[["country", "base_rank"]], on="country", how="left")
    return scenarios, {
        "all_option_count": len(all_options),
        "feasible_option_count": len({r["country"] for r in rows}),
        "infeasible_pairs": [name for name, _, feasible in all_options if "+" in name and not feasible],
    }


def source_register(run_time: str) -> list[dict[str, Any]]:
    supplied = json.loads((RAW / "source-register.json").read_text(encoding="utf-8"))
    public_meta = {item["file"]: item for item in supplied["public"]}
    details = {
        "source-room-index.html": ("HTML source inventory", "source_room_index", "collection-time source index"),
        "data-dictionary.md": ("2025 shipments/returns; policy metadata", "synthetic_client", "2025; cutoff 2026-01-31"),
        "scenario-policy.md": ("EUR, units, annual contribution, capex, FTE", "synthetic_client", "2025 baseline and annual scenarios"),
        "hub-options.csv": ("EUR capex/fixed cost/savings; FTE; country", "synthetic_client", "annual planning assumptions"),
        "unit-costs.csv": ("EUR per unit", "synthetic_client", "effective 2025-01-01 and 2025-07-01"),
        "orders-part1.csv": ("local currency prices; EUR fulfillment; units", "synthetic_client", "2025 and excluded test/future rows"),
        "orders-part2.csv": ("local currency prices; EUR fulfillment; units", "synthetic_client", "2025 and excluded test/future rows"),
        "order-corrections.csv": ("local currency prices; EUR fulfillment; units", "synthetic_client", "higher revisions replacing order rows"),
        "returns.csv": ("local currency refunds; physical units", "synthetic_client", "2025-01-28 to 2026-02-01"),
    }
    entries: list[dict[str, Any]] = []
    for filename in [
        "source-room-index.html",
        "data-dictionary.md",
        "scenario-policy.md",
        "hub-options.csv",
        "unit-costs.csv",
        "orders-part1.csv",
        "orders-part2.csv",
        "order-corrections.csv",
        "returns.csv",
        "population.json",
        "gdp-per-capita.json",
        "ecb-history.zip",
        "ecb-history.csv",
    ]:
        path = RAW / filename
        supplied_item = public_meta.get(filename, {})
        if filename in details:
            units, status, period = details[filename]
            url = "http://127.0.0.1:55463/" if filename == "source-room-index.html" else "http://127.0.0.1:55463/" + filename
            vintage = "synthetic seed 2026092736"
        elif filename == "population.json":
            url, units, status, period = supplied_item["original_url"], "persons", "official_public_archive", "2022-2024"
            vintage = "World Bank lastupdated 2026-07-13; source-room archive"
        elif filename == "gdp-per-capita.json":
            url, units, status, period = supplied_item["original_url"], "current US$ per person", "official_public_archive", "2022-2024"
            vintage = "World Bank lastupdated 2026-07-13; source-room archive"
        else:
            url, units, status, period = supplied_item.get("original_url", "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"), "local currency units per EUR", "official_public_archive", "2025 observations used; file contains broader history"
            vintage = "source-room archive fetched 2026-09-27; ecb-history.csv is lossless ZIP extraction" if filename.endswith(".csv") else "source-room archive"
        entries.append(
            {
                "file": filename,
                "source_url": url,
                "retrieved_utc": supplied_item.get("retrieved_utc", run_time),
                "analysis_run_utc": run_time,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
                "units": units,
                "period": period,
                "status": status,
                "vintage": vintage,
                "notes": "Downloaded source-room inventory; preserves the collection-time file list." if status == "source_room_index" else ("Synthetic client input; not a public observation." if status == "synthetic_client" else "Preserved archived public response/file; not refreshed during analysis."),
            }
        )
    return entries


def metric_records(monthly: pd.DataFrame, countries: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = ["country", "shipped_orders", "shipped_units", *MONEY_FIELDS, "returned_units", "margin"]
    monthly_records: list[dict[str, Any]] = []
    for r in monthly.itertuples(index=False):
        record = {"country": r.country, "month": r.month}
        record.update({field: getattr(r, field) for field in ordered[1:]})
        monthly_records.append(record)
    country_records: list[dict[str, Any]] = []
    for r in countries.itertuples(index=False):
        record = {field: getattr(r, field) for field in ordered}
        country_records.append(record)
    return monthly_records, country_records


def select_recommendation(scenarios: pd.DataFrame) -> dict[str, Any]:
    base = scenarios.loc[scenarios["scenario"].eq("base") & ~scenarios["country"].eq("DEFER")].copy()
    base = base.sort_values("incremental_contribution_eur", ascending=False)
    stress = scenarios.loc[scenarios["scenario"].eq("stress")].set_index("country")
    # Recommended choice: strongest base pair that remains positive in the defined stress and stays inside both hard caps.
    robust = base.loc[(base["incremental_contribution_eur"] > 0) & (base["country"].map(stress["incremental_contribution_eur"]) > 0)].copy()
    if robust.empty:
        chosen = base.iloc[0]
    else:
        # Among robust options, prioritize base value, with stress-positive as a non-compensable screen.
        chosen = robust.iloc[0]
    chosen_name = str(chosen["country"])
    members = chosen_name.split("+")
    if chosen_name == "DEFER":
        members = []
    alt = base.loc[base["country"].ne(chosen_name)].iloc[0]
    chosen_stress = float(stress.loc[chosen_name, "incremental_contribution_eur"])
    chosen_low = float(scenarios.loc[(scenarios.country == chosen_name) & (scenarios.scenario == "low"), "incremental_contribution_eur"].iloc[0])
    chosen_high = float(scenarios.loc[(scenarios.country == chosen_name) & (scenarios.scenario == "high"), "incremental_contribution_eur"].iloc[0])
    capex = int(chosen["capex_eur"])
    fte = int(chosen["fte"])
    rationale = (
        f"Recommend a staged launch in {', '.join(COUNTRY_NAMES.get(x, x) for x in members)}. "
        f"It ranks first among feasible alternatives on base incremental contribution after recurring fixed cost "
        f"(€{chosen['incremental_contribution_eur']:,.0f}), remains positive under the defined joint stress "
        f"(€{chosen_stress:,.0f}), and uses €{capex:,.0f} capex/{fte} FTE. "
        f"The conclusion is a planning recommendation, not a causal or statistically proven demand forecast."
    )
    return {
        "countries": members,
        "capex_eur": capex,
        "fte": fte,
        "selected_option": chosen_name,
        "base_incremental_contribution_eur": float(chosen["incremental_contribution_eur"]),
        "low_incremental_contribution_eur": chosen_low,
        "high_incremental_contribution_eur": chosen_high,
        "stress_incremental_contribution_eur": chosen_stress,
        "payback_years_base": None if pd.isna(chosen["payback_years"]) else float(chosen["payback_years"]),
        "strongest_alternative_base": {"option": str(alt["country"]), "incremental_contribution_eur": float(alt["incremental_contribution_eur"])},
        "rationale": rationale,
        "flip_condition": "Reopen after 90-day pilot if realized incremental volume is below the low-case 10% uplift for two consecutive months, or if the stress drivers are observed together; defer the second hub if either capex or staffing would breach the hard cap.",
    }


def eur(value: Any, decimals: int = 0) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"€{float(value):,.{decimals}f}"


def pct(value: Any, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{float(value) * 100:.{decimals}f}%"


def build_figures(core: dict[str, Any], figure_dir: Path) -> dict[str, Path]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    colors_map = {"navy": "#12304A", "teal": "#0F7B78", "orange": "#E89038", "red": "#B94A48", "blue": "#3E6FB0", "gray": "#6B7280", "light": "#E8EEF2"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False})
    paths: dict[str, Path] = {}

    countries = core["countries"].copy()
    countries["label"] = countries["country"].map(COUNTRY_NAMES)
    fig, ax1 = plt.subplots(figsize=(8.2, 4.5))
    x = np.arange(len(countries))
    bars = ax1.bar(x, countries["contribution_eur"], color=colors_map["teal"])
    ax1.set_xticks(x, countries["country"])
    ax1.set_ylabel("2025 contribution (€)")
    ax1.yaxis.set_major_formatter(lambda value, pos: f"€{value/1000:,.0f}k")
    ax1.set_title("2025 contribution by market (after refunds, net COGS and fulfillment)")
    for bar, margin in zip(bars, countries["margin"]):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 8000, f"{bar.get_height()/1000:.0f}k\n{margin:.1%}", ha="center", va="bottom", fontsize=8)
    ax1.grid(axis="y", color="#D9E2E8", linewidth=0.7)
    fig.tight_layout()
    paths["country_contribution"] = figure_dir / "country_contribution.png"
    fig.savefig(paths["country_contribution"], dpi=200, bbox_inches="tight")
    plt.close(fig)

    monthly = core["monthly"].groupby("month", as_index=False).agg({"contribution_eur": "sum", "net_sales_eur": "sum"})
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    ax.plot(monthly["month"], monthly["contribution_eur"], marker="o", color=colors_map["navy"], linewidth=2.5, label="Contribution")
    ax.plot(monthly["month"], monthly["net_sales_eur"], marker="o", color=colors_map["orange"], linewidth=1.8, label="Net sales")
    ax.set_title("Monthly 2025 net sales and contribution — all six markets")
    ax.set_ylabel("€")
    ax.yaxis.set_major_formatter(lambda value, pos: f"€{value/1000:,.0f}k")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", color="#D9E2E8", linewidth=0.7)
    ax.legend(frameon=False, ncol=2, loc="upper left")
    fig.tight_layout()
    paths["monthly_trend"] = figure_dir / "monthly_trend.png"
    fig.savefig(paths["monthly_trend"], dpi=200, bbox_inches="tight")
    plt.close(fig)

    scenario = core["scenarios"].loc[core["scenarios"]["scenario"].isin(["base", "stress"]) & ~core["scenarios"]["country"].eq("DEFER")].pivot(index="country", columns="scenario", values="incremental_contribution_eur")
    scenario = scenario.sort_values("base", ascending=True)
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    y = np.arange(len(scenario))
    bar_base = ax.barh(y - 0.18, scenario["base"], height=0.34, color=colors_map["teal"], label="Base")
    bar_stress = ax.barh(y + 0.18, scenario["stress"], height=0.34, color=colors_map["orange"], label="Defined stress")
    rec = core["recommendation"]["selected_option"]
    labels = [f"{name}{'  ★' if name == rec else ''}" for name in scenario.index]
    ax.set_yticks(y, labels)
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.set_xlabel("Annual incremental contribution after recurring fixed cost (€)")
    ax.xaxis.set_major_formatter(lambda value, pos: f"€{value/1000:,.0f}k")
    ax.set_title("Feasible hub options: base economics versus the policy stress")
    ax.legend(frameon=False, ncol=2, loc="lower right")
    ax.grid(axis="x", color="#D9E2E8", linewidth=0.7)
    fig.tight_layout()
    paths["scenario_compare"] = figure_dir / "scenario_compare.png"
    fig.savefig(paths["scenario_compare"], dpi=200, bbox_inches="tight")
    plt.close(fig)

    fx = core["fx_monthly"].copy()
    fig, ax = plt.subplots(figsize=(8.2, 4.2))
    for currency, color in [("PLN", colors_map["blue"]), ("CZK", colors_map["red"])]:
        series = fx.loc[fx["currency"].eq(currency)]
        ax.plot(series["month"], series["local_per_eur"], marker="o", linewidth=2, label=currency, color=color)
    ax.set_title("ECB monthly reference-rate means, 2025 (local currency units per EUR)")
    ax.set_ylabel("Local currency per EUR")
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", color="#D9E2E8", linewidth=0.7)
    ax.legend(frameon=False, ncol=2)
    fig.tight_layout()
    paths["fx_rates"] = figure_dir / "fx_rates.png"
    fig.savefig(paths["fx_rates"], dpi=200, bbox_inches="tight")
    plt.close(fig)

    market = core["market"].copy()
    pop = market.pivot(index="country", columns="year", values="population").loc[COUNTRIES]
    gdp = market.pivot(index="country", columns="year", values="gdp_per_capita_usd").loc[COUNTRIES]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 4.0))
    pop_change = (pop[2024] / pop[2022] - 1) * 100
    ax1.bar(COUNTRIES, pop_change, color=colors_map["blue"])
    ax1.axhline(0, color="#333333", linewidth=0.7)
    ax1.set_title("Population change\n2022–2024")
    ax1.set_ylabel("% change")
    for i, value in enumerate(pop_change):
        ax1.text(i, value + (0.15 if value >= 0 else -0.3), f"{value:.1f}%", ha="center", va="bottom" if value >= 0 else "top", fontsize=8)
    ax2.bar(COUNTRIES, gdp[2024], color=colors_map["teal"])
    ax2.set_title("GDP per capita, current US$\n2024")
    ax2.yaxis.set_major_formatter(lambda value, pos: f"${value/1000:,.0f}k")
    for i, value in enumerate(gdp[2024]):
        ax2.text(i, value + 1800, f"${value/1000:.0f}k", ha="center", va="bottom", fontsize=8)
    for ax in (ax1, ax2):
        ax.grid(axis="y", color="#D9E2E8", linewidth=0.7)
    fig.suptitle("Market context is context, not direct demand evidence", fontweight="bold")
    fig.tight_layout()
    paths["market_context"] = figure_dir / "market_context.png"
    fig.savefig(paths["market_context"], dpi=200, bbox_inches="tight")
    plt.close(fig)
    return paths


def write_derived_outputs(core: dict[str, Any], out_dir: Path, source_entries: list[dict[str, Any]], figures: dict[str, Path]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    data_dir = out_dir / "data"
    data_dir.mkdir(exist_ok=True)
    write_csv(data_dir / "order_detail.csv", core["detail"])
    write_csv(data_dir / "monthly.csv", core["monthly"])
    write_csv(data_dir / "countries.csv", core["countries"])
    write_csv(data_dir / "fx_monthly.csv", core["fx_monthly"])
    write_csv(data_dir / "market_context.csv", core["market"])
    write_csv(data_dir / "hub_scenarios.csv", core["scenarios"])
    write_csv(data_dir / "hub_options.csv", core["options"])
    write_json(out_dir / "source-register.json", source_entries)
    write_json(out_dir / "quality.json", core["quality"])
    monthly_records, country_records = metric_records(core["monthly"], core["countries"])
    market_records = [
        {"country": r.country, "year": int(r.year), "population": int(r.population), "gdp_per_capita_usd": float(r.gdp_per_capita_usd)}
        for r in core["market"].itertuples(index=False)
    ]
    hub_records = []
    for r in core["scenarios"].itertuples(index=False):
        hub_records.append(
            {
                "country": r.country,
                "scenario": r.scenario,
                "incremental_contribution_eur": float(r.incremental_contribution_eur),
                "capex_eur": int(r.capex_eur),
                "fte": int(r.fte),
                "payback_years": None if pd.isna(r.payback_years) else float(r.payback_years),
            }
        )
    metrics = {
        "monthly": monthly_records,
        "countries": country_records,
        "fx_monthly": core["fx_monthly"][["currency", "month", "local_per_eur"]].to_dict("records"),
        "market_context": market_records,
        "hub_scenarios": hub_records,
        "recommendation": core["recommendation"],
        "quality": core["quality"],
        "metadata": {
            "client": "Meridian Parts (synthetic)",
            "analysis_period": "2025 shipped sales and returns known through 2026-01-31",
            "archive_source_room": "http://127.0.0.1:55463/",
            "analysis_run_utc": core["run_time"],
            "reporting_currency": "EUR",
            "rounding": "individual order monetary components rounded half-up to EUR cents before summation",
            "evidence_status": "archived public official series plus synthetic client exports; no live research used",
        },
    }
    metrics_path = out_dir / "metrics.json"
    write_json(metrics_path, metrics)
    return metrics_path


def excel_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    return value


def style_sheet_table(ws, table_name: str, start_row: int, end_row: int, end_col: int) -> None:
    if end_row < start_row or end_col < 1:
        return
    ref = f"A{start_row}:{get_column_letter(end_col)}{end_row}"
    table = Table(displayName=re.sub(r"[^A-Za-z0-9_]", "", table_name)[:240], ref=ref)
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    ws.add_table(table)
    ws.auto_filter.ref = ref


def format_sheet_cells(ws, df: pd.DataFrame, header_row: int) -> None:
    money_format = '€#,##0.00;[Red]-€#,##0.00'
    for col_idx, name in enumerate(df.columns, start=1):
        lname = str(name).lower()
        for row_idx in range(header_row + 1, header_row + 1 + len(df)):
            cell = ws.cell(row_idx, col_idx)
            if "margin" in lname:
                cell.number_format = "0.0%;[Red]-0.0%"
            elif "payback" in lname:
                cell.number_format = "0.00"
            elif "local_per_eur" in lname:
                cell.number_format = "0.000000"
            elif "_eur" in lname or lname.endswith("_usd") or lname in {"gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"}:
                cell.number_format = money_format
            elif lname in {"population", "shipped_orders", "shipped_units", "returned_units", "quantity", "restocked_units", "return_records", "fte", "revision", "observations", "year"}:
                cell.number_format = "#,##0"
            elif lname.endswith("_rate") or lname == "rate":
                cell.number_format = "0.000000"
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="12304A")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[header_row].height = 32
    for row in ws.iter_rows(min_row=header_row + 1, max_row=header_row + len(df), min_col=1, max_col=len(df)):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=False)


def add_dataframe_sheet(wb: Workbook, name: str, df: pd.DataFrame, subtitle: str) -> Any:
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(df.columns)))
    ws["A1"] = name.replace("_", " ")
    ws["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="12304A")
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 25
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(1, len(df.columns)))
    ws["A2"] = subtitle
    ws["A2"].font = Font(italic=True, color="4B5563")
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 32
    header_row = 4
    for col_idx, col in enumerate(df.columns, start=1):
        ws.cell(header_row, col_idx, str(col))
    for row_idx, row in enumerate(df.itertuples(index=False, name=None), start=header_row + 1):
        for col_idx, value in enumerate(row, start=1):
            ws.cell(row_idx, col_idx, excel_value(value))
    format_sheet_cells(ws, df, header_row)
    style_sheet_table(ws, f"tbl_{name}", header_row, header_row + len(df), len(df.columns))
    ws.freeze_panes = f"A{header_row + 1}"
    for idx, col in enumerate(df.columns, start=1):
        sample = [str(v) for v in df[col].head(100).tolist() if v is not None and not (isinstance(v, float) and math.isnan(v))]
        width = min(36, max(12, len(str(col)) + 2, max((len(v) for v in sample), default=0) + 2))
        ws.column_dimensions[get_column_letter(idx)].width = width
    return ws


def add_workbook(core: dict[str, Any], out_dir: Path, source_entries: list[dict[str, Any]], figures: dict[str, Path]) -> Path:
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    wb.properties.title = "Meridian Parts — European service-hub expansion"
    wb.properties.subject = "Reconciled 2025 operating economics, market context, FX and hub scenarios"
    wb.properties.creator = "OpenAI Codex — reproducible synthetic-client analysis"

    ws = wb.create_sheet("README")
    ws.sheet_view.showGridLines = False
    ws.merge_cells("A1:H1")
    ws["A1"] = "Meridian Parts | European service-hub expansion"
    ws["A1"].font = Font(size=20, bold=True, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="12304A")
    ws["A1"].alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 34
    ws.merge_cells("A3:H3")
    ws["A3"] = "Purpose: board-ready operating baseline and scenario model for up to two local service hubs. All figures are EUR unless stated."
    ws["A3"].font = Font(size=11, bold=True, color="12304A")
    ws["A3"].alignment = Alignment(wrap_text=True)
    readme_rows = [
        ("Decision", core["recommendation"]["rationale"]),
        ("Scope", "2025 shipped orders and returns received through 2026-01-31 inclusive; countries DEU, FRA, NLD, POL, CZE and ESP."),
        ("Accounting", "One order per order_id after highest-revision selection; cancellations/tests/future shipments excluded; free/sample orders retained; returns linked only by explicit eligible order_id."),
        ("FX", "EUR=1.000000. PLN and CZK use arithmetic means of available ECB published business-day observations in the original sale month; quotes are local currency units per EUR."),
        ("Rounding", "Gross sales, refunds, COGS components, fulfillment and contribution are calculated at order level and rounded half-up to cents before summation."),
        ("Scenario", "Low/base/high volume uplifts are 10%/25%/40%; stress uses the client policy's 3% gross-sales refund shock and 10% net-sales depreciation shock for PLN/CZK markets."),
        ("How to reproduce", "From the project root run: python analysis/reproduce.py. It rebuilds data/, metrics.json, source-register.json, figures/, the workbook, report and board deck."),
        ("Evidence status", "Synthetic client inputs are labelled synthetic. Archived World Bank and ECB files are preserved with original URLs, retrieval vintage and SHA-256 hashes. No live client account or live public refresh was used."),
    ]
    row = 5
    for label, value in readme_rows:
        ws.cell(row, 1, label).font = Font(bold=True, color="0F7B78")
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=8)
        ws.cell(row, 2, value).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 34 if len(value) > 145 else 24
        row += 1
    ws["A15"] = "Workbook map"
    ws["A15"].font = Font(bold=True, size=12, color="12304A")
    sheet_map = [
        ("Order_Detail", "Eligible order-level components and rounded values used in aggregations."),
        ("Monthly", "6×12 country/month results; zeros retained for months with no excluded data."),
        ("Country_Totals", "2025 country totals and margins reconciled to monthly records."),
        ("FX_Monthly", "PLN/CZK monthly ECB means and business-day observation counts."),
        ("Market_Context", "Archived World Bank 2022–2024 population and GDP per capita."),
        ("Hub_Scenarios", "All singles, feasible pairs and DEFER across low/base/high/stress."),
        ("Decision_Summary", "Recommendation, constraints, alternative comparison and flip condition."),
        ("Charts", "Legible decision visuals used in board materials."),
        ("Source_Register", "URL, retrieval time, hash, units, period and evidence status."),
    ]
    for i, (sheet, desc) in enumerate(sheet_map, start=16):
        ws.cell(i, 1, sheet).font = Font(bold=True, color="0F7B78")
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=8)
        ws.cell(i, 2, desc)
    for col, width in zip("ABCDEFGH", [20, 28, 18, 18, 18, 18, 18, 18]):
        ws.column_dimensions[col].width = width

    quality_rows = []
    quality_rows.append(["Quality register", "Finding / handling"])
    q = core["quality"]
    quality_rows.extend(
        [
            ["Order raw rows", f"{q['order_reconciliation']['raw_rows']:,}; {q['order_reconciliation']['duplicate_order_rows_removed']} duplicate rows removed; {q['order_reconciliation']['higher_revision_replacements']} corrections replace prior rows."],
            ["Order exclusions", json.dumps(q["order_reconciliation"]["excluded_by_reason"], sort_keys=True)],
            ["Valid zero-price orders", f"{q['order_reconciliation']['zero_price_orders_eligible']} retained as shipped orders."],
            ["Returns", f"{q['return_reconciliation']['raw_rows']} raw; {q['return_reconciliation']['deduplicated_rows']} unique after revision selection; {q['return_reconciliation']['usable_returns']} linked by explicit order_id."],
            ["Return exclusions", json.dumps(q["return_reconciliation"]["excluded_by_reason"], sort_keys=True) + "; orphan IDs quarantined."],
            ["Missing values", json.dumps(q["missing_values"], sort_keys=True)],
            ["Reconciliation", json.dumps(q["reconciliations"], sort_keys=True)],
            ["Limitation", "No payment settlement dates, taxes, working capital or DCF discounting; cash is not inferred from booked sales or contribution."],
        ]
    )
    wsq = wb.create_sheet("Source_Quality")
    wsq.sheet_view.showGridLines = False
    wsq.merge_cells("A1:D1")
    wsq["A1"] = "Source and quality notes"
    wsq["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    wsq["A1"].fill = PatternFill("solid", fgColor="12304A")
    wsq.merge_cells("A2:D2")
    wsq["A2"] = "Detected anomalies are displayed here rather than silently corrected; source-register.json provides full provenance."
    wsq["A2"].alignment = Alignment(wrap_text=True)
    for r_idx, vals in enumerate(quality_rows, start=4):
        for c_idx, val in enumerate(vals, start=1):
            wsq.cell(r_idx, c_idx, val)
            wsq.cell(r_idx, c_idx).alignment = Alignment(wrap_text=True, vertical="top")
    for cell in wsq[4]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="12304A")
    wsq.column_dimensions["A"].width = 27
    wsq.column_dimensions["B"].width = 105
    wsq.column_dimensions["C"].width = 20
    wsq.column_dimensions["D"].width = 20
    for r_idx in range(5, 4 + len(quality_rows)):
        wsq.row_dimensions[r_idx].height = 34
    wsq.freeze_panes = "A5"

    add_dataframe_sheet(wb, "Order_Detail", core["detail"], "Order-level calculations after revision selection and eligibility filters. Monetary components are rounded half-up to cents before aggregation.")
    add_dataframe_sheet(wb, "Monthly", core["monthly"], "Country/month result. Each country has all 12 calendar months; no January 2026 orders enter this table.")
    add_dataframe_sheet(wb, "Country_Totals", core["countries"], "Country/year total for 2025, reconciled to the twelve monthly records. Margin is contribution divided by net sales.")
    add_dataframe_sheet(wb, "FX_Monthly", core["fx_monthly"], "ECB reference-rate arithmetic means for available published business days in each 2025 calendar month. Quote: local currency units per EUR.")
    add_dataframe_sheet(wb, "Market_Context", core["market"], "Archived World Bank responses. Population is persons; GDP per capita is current US$ per person. These are context, not direct demand proof.")
    add_dataframe_sheet(wb, "Hub_Scenarios", core["scenarios"], "Client scenario policy. Annual incremental contribution excludes year-zero capex; payback is simple undiscounted K / positive annual increment. Infeasible pairs are omitted from this sheet and listed in quality notes.")

    decision_df = core["scenarios"].loc[core["scenarios"]["scenario"].eq("base"), ["country", "incremental_contribution_eur", "capex_eur", "fte", "payback_years", "base_rank"]].copy()
    decision_df = decision_df.sort_values("incremental_contribution_eur", ascending=False).head(10)
    wsd = wb.create_sheet("Decision_Summary")
    wsd.sheet_view.showGridLines = False
    wsd.merge_cells("A1:H1")
    wsd["A1"] = "Board decision summary"
    wsd["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    wsd["A1"].fill = PatternFill("solid", fgColor="12304A")
    summary = [
        ("Recommended option", core["recommendation"]["selected_option"]),
        ("Recommended countries", ", ".join(COUNTRY_NAMES.get(c, c) for c in core["recommendation"]["countries"])),
        ("Capex / FTE", f"{eur(core['recommendation']['capex_eur'])} / {core['recommendation']['fte']}"),
        ("Base incremental contribution", eur(core["recommendation"]["base_incremental_contribution_eur"])),
        ("Defined stress contribution", eur(core["recommendation"]["stress_incremental_contribution_eur"])),
        ("Base payback", f"{core['recommendation']['payback_years_base']:.2f} years"),
        ("Decision rule", "Assumed planning screen: comply with capex/FTE/two-hub hard limits, remain positive in the defined stress, then rank by base annual contribution."),
        ("Flip condition", core["recommendation"]["flip_condition"]),
    ]
    for i, (label, value) in enumerate(summary, start=3):
        wsd.cell(i, 1, label).font = Font(bold=True, color="0F7B78")
        wsd.merge_cells(start_row=i, start_column=2, end_row=i, end_column=8)
        wsd.cell(i, 2, value).alignment = Alignment(wrap_text=True, vertical="top")
        wsd.row_dimensions[i].height = 34 if len(str(value)) > 95 else 24
    wsd["A13"] = "Top base-case alternatives"
    wsd["A13"].font = Font(bold=True, size=12, color="12304A")
    for c_idx, col in enumerate(decision_df.columns, start=1):
        wsd.cell(14, c_idx, col)
    for r_idx, row_vals in enumerate(decision_df.itertuples(index=False, name=None), start=15):
        for c_idx, val in enumerate(row_vals, start=1):
            wsd.cell(r_idx, c_idx, excel_value(val))
    format_sheet_cells(wsd, decision_df, 14)
    style_sheet_table(wsd, "tbl_decision_summary", 14, 14 + len(decision_df), len(decision_df.columns))
    wsd.freeze_panes = "A15"
    for col in "ABCDEFGH":
        wsd.column_dimensions[col].width = 22
    wsd.column_dimensions["A"].width = 30
    wsd.column_dimensions["B"].width = 30

    wsc = wb.create_sheet("Charts")
    wsc.sheet_view.showGridLines = False
    wsc.merge_cells("A1:N1")
    wsc["A1"] = "Decision charts"
    wsc["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    wsc["A1"].fill = PatternFill("solid", fgColor="12304A")
    chart_positions = [("country_contribution", "A3"), ("scenario_compare", "J3"), ("monthly_trend", "A27"), ("fx_rates", "J27"), ("market_context", "A51")]
    for key, position in chart_positions:
        if key in figures:
            image = XLImage(str(figures[key]))
            image.width = 560
            image.height = 310
            wsc.add_image(image, position)
    for col in range(1, 20):
        wsc.column_dimensions[get_column_letter(col)].width = 12

    source_df = pd.DataFrame(source_entries)
    add_dataframe_sheet(wb, "Source_Register", source_df, "Provenance for downloaded raw evidence: URL, retrieval time, SHA-256, units, period, vintage and synthetic/public status.")

    # Consistent workbook tab colors and navigation.
    for sheet in wb.worksheets:
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_properties.tabColor = "0F7B78" if sheet.title in {"Decision_Summary", "Charts"} else "12304A"
    path = out_dir / "meridian_parts_analytical_workbook.xlsx"
    wb.save(path)
    return path


def report_paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def report_table(data: list[list[Any]], widths: list[float] | None = None, font_size: float = 7.4, header: bool = True) -> RLTable:
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("table_cell", parent=styles["BodyText"], fontName="Helvetica", fontSize=font_size, leading=font_size + 1.5, spaceAfter=0)
    head_style = ParagraphStyle("table_head", parent=cell_style, fontName="Helvetica-Bold", textColor=colors.white)
    formatted: list[list[Any]] = []
    for r_idx, row in enumerate(data):
        formatted.append([Paragraph(html.escape(str(value)).replace("\n", "<br/>"), head_style if (header and r_idx == 0) else cell_style) for value in row])
    table = RLTable(formatted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CAD5DC")),
    ]
    if header:
        commands.extend([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#12304A")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)])
        if len(data) > 1:
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6F8")]))
    table.setStyle(TableStyle(commands))
    return table


def report_bullet(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph("• " + text, style)


def add_report(core: dict[str, Any], out_dir: Path, source_entries: list[dict[str, Any]], figures: dict[str, Path]) -> Path:
    path = out_dir / "meridian_parts_executive_report.pdf"
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title="Meridian Parts — European service-hub expansion",
        author="OpenAI Codex",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=colors.HexColor("#12304A"), alignment=TA_LEFT, spaceAfter=12)
    subtitle = ParagraphStyle("CoverSub", parent=styles["Normal"], fontSize=13, leading=17, textColor=colors.HexColor("#0F7B78"), spaceAfter=16)
    h1 = ParagraphStyle("H1Custom", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=colors.HexColor("#12304A"), spaceBefore=0, spaceAfter=9)
    h2 = ParagraphStyle("H2Custom", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=colors.HexColor("#0F7B78"), spaceBefore=8, spaceAfter=5)
    body = ParagraphStyle("BodyCustom", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13, textColor=colors.HexColor("#24323D"), spaceAfter=7)
    small = ParagraphStyle("SmallCustom", parent=body, fontSize=7.7, leading=10, textColor=colors.HexColor("#4B5563"), spaceAfter=4)
    callout = ParagraphStyle("Callout", parent=body, fontName="Helvetica-Bold", fontSize=12, leading=16, textColor=colors.HexColor("#12304A"), spaceAfter=0)
    foot = ParagraphStyle("Foot", parent=body, fontSize=7, leading=9, textColor=colors.HexColor("#6B7280"), spaceAfter=2)
    story: list[Any] = []

    rec = core["recommendation"]
    countries = core["countries"].copy()
    market = core["market"].copy()
    scenario = core["scenarios"]

    def image_flow(key: str, width: float = 170 * mm, height: float = 78 * mm) -> RLImage:
        img = RLImage(str(figures[key]), width=width, height=height)
        img.hAlign = "LEFT"
        return img

    # Cover / decision in one view.
    story.extend([Spacer(1, 14 * mm), report_paragraph("Meridian Parts", title), report_paragraph("European service-hub expansion", subtitle)])
    story.append(report_paragraph("Executive consulting report | Synthetic client | Analysis of 2025 shipped sales and returns known through 31 January 2026", body))
    story.append(Spacer(1, 8 * mm))
    cover_table = report_table(
        [
            ["Board recommendation", "Resource envelope", "Base annual increment", "Defined stress", "Simple payback"],
            [rec["selected_option"], f"{eur(rec['capex_eur'])} / {rec['fte']} FTE", eur(rec["base_incremental_contribution_eur"]), eur(rec["stress_incremental_contribution_eur"]), f"{rec['payback_years_base']:.2f} years"],
        ],
        widths=[37 * mm, 35 * mm, 35 * mm, 31 * mm, 30 * mm],
        font_size=8.5,
    )
    story.append(cover_table)
    story.append(Spacer(1, 10 * mm))
    story.append(report_paragraph("Decision statement", h2))
    story.append(report_paragraph(rec["rationale"], callout))
    story.append(Spacer(1, 8 * mm))
    story.append(report_paragraph("The recommendation assumes the board wants to stay inside the explicit €450,000 capex, seven-FTE and two-hub constraints, screen out options that are negative under the defined joint stress, and then maximize the base annual contribution. That risk screen is a stated planning choice, not a measured board preference. NLD+ESP is the stronger stress-resilience alternative; its lower base contribution and higher resource requirement are the main concessions of selecting it.", body))
    story.append(Spacer(1, 15 * mm))
    story.append(report_paragraph("Evidence status", h2))
    story.append(report_paragraph("Core operating data are synthetic client exports from the frozen source room. Population, GDP per capita and ECB rates are archived official snapshots preserved with their original URLs, retrieval vintage and hashes. No live client account, customer interview or live public refresh was used. Figures are estimates under the supplied scenario policy, not causal or statistically proven demand forecasts.", body))
    story.append(PageBreak())

    # Executive summary.
    story.append(report_paragraph("1. Executive recommendation", h1))
    story.append(report_paragraph("Fund a staged CZE+ESP expansion envelope, releasing Czechia first and making the Spain release conditional on the 90-day gate. In the policy's steady-state arithmetic, the pair produces the highest feasible base incremental contribution: €198.1k per year after recurring fixed cost, with €225k year-zero capex, five FTE and 1.14-year simple payback. The low-volume case remains positive at €64.6k; the defined joint stress remains positive at €32.2k.", body))
    story.append(report_paragraph("Why this option", h2))
    for bullet in [
        f"2025 contribution is strongest in ESP ({eur(countries.loc[countries.country.eq('ESP'), 'contribution_eur'].iloc[0])}) and CZE ({eur(countries.loc[countries.country.eq('CZE'), 'contribution_eur'].iloc[0])}); the pair also has the highest base annual scenario value.",
        "CZE+ESP is positive under the policy's low, base, high and stress cases. The defined stress includes a refund shock for both hubs and an additional 10% net-sales depreciation shock for CZE only.",
        f"The strongest base alternative is {rec['strongest_alternative_base']['option']} at {eur(rec['strongest_alternative_base']['incremental_contribution_eur'])}; it needs €240k/6 FTE and is positive in stress but gives up base value and one additional FTE versus CZE+ESP.",
        "The choice is reversible after the pilot: defer the second release if realized incremental volume fails the low-case gate or if resource quotes breach the policy limits.",
    ]:
        story.append(report_bullet(bullet, body))
    story.append(report_paragraph("Board decision frame", h2))
    decision_rows = [["Alternative", "Base annual increment", "Stress", "Capex / FTE", "Comment"]]
    for option in ["CZE+ESP", "NLD+ESP", "POL+ESP", "CZE", "DEFER"]:
        sbase = scenario.loc[(scenario.country.eq(option)) & scenario.scenario.eq("base")].iloc[0]
        sstress = scenario.loc[(scenario.country.eq(option)) & scenario.scenario.eq("stress")].iloc[0]
        comment = "Recommended" if option == rec["selected_option"] else ("Stress-resilience alternative" if option == "NLD+ESP" else ("Dominated by CZE+ESP on four scenarios and resources" if option == "POL+ESP" else "Comparator"))
        decision_rows.append([option, eur(sbase.incremental_contribution_eur), eur(sstress.incremental_contribution_eur), f"{eur(sbase.capex_eur)} / {int(sbase.fte)}", comment])
    story.append(report_table(decision_rows, widths=[25 * mm, 31 * mm, 27 * mm, 31 * mm, 55 * mm], font_size=8))
    story.append(Spacer(1, 3 * mm))
    story.append(report_paragraph("The board should treat the table as a planning comparison: capex is year-zero, while annual increments exclude capex and use the policy's simple uplift/savings arithmetic. First-year ramp timing is not modelled in payback.", small))
    story.append(PageBreak())

    # Data and accounting.
    story.append(report_paragraph("2. Evidence, controls and accounting", h1))
    story.append(report_paragraph("The analysis reconciles both order extracts, correction rows, returns, effective-dated unit costs, archived FX history and archived World Bank responses. The source room is frozen; its files were downloaded and hashed into the project before analysis.", body))
    q = core["quality"]
    reconcile_rows = [
        ["Control", "Observed", "Handling"],
        ["Orders", f"{q['order_reconciliation']['raw_rows']:,} raw rows / {q['order_reconciliation']['unique_order_ids']:,} unique IDs", "Highest numeric revision wins; 31 duplicate rows removed; 18 corrections replace full prior rows."],
        ["Eligibility", f"{q['order_reconciliation']['eligible_orders']:,} eligible orders", f"24 cancelled, 18 test and 1 2026 shipment excluded. Valid zero-price shipments retained ({q['order_reconciliation']['zero_price_orders_eligible']})."],
        ["Returns", f"{q['return_reconciliation']['raw_rows']} raw rows / {q['return_reconciliation']['deduplicated_rows']} IDs", "Highest revision wins; repeated IDs counted once; 241 returns linked to eligible orders."],
        ["Return cutoff", "Inclusive through 2026-01-31", "One post-cutoff record excluded; orphan R-ORPHAN quarantined; no guess-based joins."],
        ["Missing required values", "0 in eligible orders; 0 in selected returns", "No imputation needed. Effective unit cost found for every eligible order."],
        ["Reconciliation", "Monthly ↔ country totals: exact to cent", "All monthly records sum to country/year totals; JSON and workbook carry the same values."],
    ]
    story.append(report_table(reconcile_rows, widths=[30 * mm, 43 * mm, 96 * mm], font_size=7.7))
    story.append(report_paragraph("Revenue, cash and contribution are different lenses", h2))
    story.append(report_paragraph("Gross sales are the shipment-date booked sales measure after local-price discounts and original sale-month FX translation. Net sales subtract explicit refunds known by the cutoff; refund receipt dates can lag the shipment month. Cash cannot be reconciled because payment settlement, tax, working-capital and payment-fee data are absent. Contribution is net sales less net COGS and actual nonrefundable fulfillment cost; it is not cash, EBITDA or free cash flow and excludes hub capex by design.", body))
    story.append(report_paragraph("The order detail is the audit trail: gross sales and refunds are converted with the sale-month quote; gross COGS, recovered COGS, net COGS, fulfillment and contribution are rounded per order using half-up cents before sums. Returned units are physical quantity, not number of return records.", body))
    story.append(PageBreak())

    # Baseline performance.
    story.append(report_paragraph("3. 2025 operating diagnosis", h1))
    story.append(report_paragraph("All six markets have 209 eligible shipped orders after controls. ESP and CZE combine the largest shipped-unit bases with the highest contribution; the result is useful for hub sizing but does not prove that local hubs caused or would cause the uplift in the scenarios.", body))
    baseline_rows = [["Country", "Orders", "Units", "Gross sales", "Refunds", "Net sales", "Net COGS", "Fulfillment", "Contribution", "Margin", "Returned units"]]
    for r in countries.itertuples(index=False):
        baseline_rows.append([r.country, f"{r.shipped_orders:,}", f"{r.shipped_units:,}", eur(r.gross_sales_eur, 0), eur(r.refunds_eur, 0), eur(r.net_sales_eur, 0), eur(r.net_cogs_eur, 0), eur(r.fulfillment_eur, 0), eur(r.contribution_eur, 0), pct(r.margin), f"{r.returned_units:,}"])
    story.append(report_table(baseline_rows, widths=[16 * mm, 16 * mm, 18 * mm, 23 * mm, 20 * mm, 23 * mm, 22 * mm, 23 * mm, 25 * mm, 17 * mm, 22 * mm], font_size=6.9))
    story.append(Spacer(1, 4 * mm))
    story.append(image_flow("country_contribution", width=170 * mm, height=91 * mm))
    story.append(report_paragraph("Diagnosis: the operating base is profitable in every market on the stated contribution measure, but the contribution ranking is partly a function of the synthetic order mix, prices, returns and cost assumptions. ESP's 49.6% margin and CZE's 48.7% are not market benchmarks; they are computed from the client extract under the data dictionary.", small))
    story.append(PageBreak())

    # Market context and FX.
    story.append(report_paragraph("4. Market context and FX discipline", h1))
    story.append(report_paragraph("Archived World Bank context shows different scale and income profiles: NLD and DEU have the highest 2024 GDP per capita in current US$, while ESP, NLD, DEU, FRA and CZE grow in population between 2022 and 2024 and POL declines. These observations may inform capacity and labour-market conversations, but neither population nor GDP per capita is direct evidence of replacement-assembly demand.", body))
    story.append(image_flow("market_context", width=170 * mm, height=76 * mm))
    market_rows = [["Country", "Population 2022", "Population 2024", "Change", "GDP pc 2022", "GDP pc 2024"]]
    for country in COUNTRIES:
        m = market.loc[market.country.eq(country)].set_index("year")
        pop_change = m.loc[2024, "population"] / m.loc[2022, "population"] - 1
        market_rows.append([country, f"{int(m.loc[2022, 'population']):,}", f"{int(m.loc[2024, 'population']):,}", pct(pop_change), f"${m.loc[2022, 'gdp_per_capita_usd']:,.0f}", f"${m.loc[2024, 'gdp_per_capita_usd']:,.0f}"])
    story.append(report_table(market_rows, widths=[23 * mm, 31 * mm, 31 * mm, 20 * mm, 31 * mm, 31 * mm], font_size=7.6))
    story.append(PageBreak())
    story.append(Spacer(1, 4 * mm))
    story.append(report_paragraph("Historical FX is not today's FX", h2))
    story.append(report_paragraph("The local-currency orders in POL and CZE use the original sale month's arithmetic mean of available ECB business-day reference observations, quoted as local currency units per EUR. No quote is inverted and no current rate is substituted. The twelve monthly values are in the workbook and JSON; the full archived ECB file and its ZIP hash are in the source register.", body))
    story.append(image_flow("fx_rates", width=170 * mm, height=78 * mm))
    story.append(PageBreak())

    # Scenario economics.
    story.append(report_paragraph("5. Hub economics and scenario comparison", h1))
    story.append(report_paragraph("The policy formula is explicit: annual incremental contribution = C×uplift + U×(1+uplift)×saving per unit − recurring fixed cost. Capex is year-zero and is not subtracted from that annual measure. Simple payback is capex divided by positive annual increment; it is null when annual increment is non-positive. Pairs add country figures without synergy.", body))
    top_options = scenario.loc[scenario.scenario.eq("base")].sort_values("incremental_contribution_eur", ascending=False).head(10)
    econ_rows = [["Option", "Low", "Base", "High", "Stress", "Capex", "FTE", "Base payback"]]
    for r in top_options.itertuples(index=False):
        subset = scenario.loc[scenario.country.eq(r.country)].set_index("scenario")
        econ_rows.append([r.country, eur(subset.loc["low", "incremental_contribution_eur"]), eur(subset.loc["base", "incremental_contribution_eur"]), eur(subset.loc["high", "incremental_contribution_eur"]), eur(subset.loc["stress", "incremental_contribution_eur"]), eur(r.capex_eur), str(int(r.fte)), "—" if pd.isna(r.payback_years) else f"{r.payback_years:.2f}y"])
    story.append(report_table(econ_rows, widths=[25 * mm, 23 * mm, 23 * mm, 23 * mm, 23 * mm, 22 * mm, 15 * mm, 25 * mm], font_size=7.2))
    story.append(Spacer(1, 4 * mm))
    story.append(image_flow("scenario_compare", width=170 * mm, height=116 * mm))
    story.append(report_paragraph("CZE+ESP is the base-case leader and remains positive in the policy stress. NLD+ESP is the stress leader (€107.6k) but produces €31.2k less base annual contribution, consumes €45k more capex and one additional FTE. POL+ESP is dominated by CZE+ESP on base, low, high and stress values while also requiring more capex and FTE; it is not the strongest alternative once those criteria are held constant.", small))
    story.append(PageBreak())

    # Trade-off and flip conditions.
    story.append(report_paragraph("6. Trade-offs, assumptions and what would change the decision", h1))
    story.append(report_paragraph("Hard constraints are the client policy's €450k maximum capex, seven FTE maximum and at most two hubs; defer is allowed. The comparison then uses an assumed planning screen: keep positive annual contribution in the defined stress, then maximize base annual contribution. This makes the risk tolerance visible instead of hiding it in a blended score.", body))
    criteria_rows = [
        ["Criterion", "Status / direction", "Evidence or provenance"],
        ["Capex / FTE / hub count", "Hard constraints", "Scenario-policy.md; client-supplied synthetic policy."],
        ["Base annual increment", "Computed; higher is better", "Reproducible formula using 2025 country totals and hub-options.csv."],
        ["Stress remains positive", "Assumed non-compensable screen", "Board scenario-policy.md; stress is a conservative joint assumption, not probability."],
        ["Payback", "Computed; shorter is better, secondary", "Simple undiscounted K / positive annual increment; no ramp or discounting."],
        ["Market context", "Public context only", "Archived World Bank responses; not a demand forecast or weight."],
    ]
    story.append(report_table(criteria_rows, widths=[42 * mm, 43 * mm, 86 * mm], font_size=7.7))
    story.append(report_paragraph("Key switching conditions", h2))
    switch_rows = [
        ["Condition", "Implication"],
        ["Board prioritizes stress resilience over base value", "NLD+ESP becomes the preferred alternative: highest defined-stress contribution (€107.6k), but higher capex/FTE and lower base value."],
        ["Normal volume uplift falls below approximately 2.7% for CZE+ESP", "The normal annual formula falls below break-even before stress; do not release the second hub without observed demand evidence."],
        ["Actual quotes exceed €225k or five FTE for CZE+ESP", "Reprice the option and re-screen against policy caps; defer or select a lower-resource alternative."],
        ["Observed pilot uplift is below the 10% low case for two consecutive months", "Hold the Spain release and reassess; the scenario arithmetic is not a causal guarantee."],
        ["Refund/FX stress drivers occur together", "Do not treat the positive stress output as certainty; extend pilot, preserve cash and use the gate."],
    ]
    story.append(report_table(switch_rows, widths=[67 * mm, 104 * mm], font_size=7.7))
    story.append(report_paragraph("The first-year realization will be lower than the steady-state annual number if the hubs ramp during the 90-day plan. The model does not discount timing, include hiring lag, or model inventory duplication; that limitation is material to payback and is why the release is staged.", body))
    story.append(PageBreak())

    # Implementation plan.
    story.append(report_paragraph("7. Staged 90-day implementation", h1))
    story.append(report_paragraph("Approve the CZE+ESP envelope but stage execution: prepare both sites, launch CZE first, and release ESP only at Gate 2. The plan translates the model's flip conditions into observable operating evidence.", body))
    plan_rows = [
        ["Timing", "Owner", "Actions / dependencies", "Decision gate"],
        ["Days 0–15\nMobilize", "COO sponsor; Finance; PMO", "Confirm baseline definitions and country/order mapping; open capex and labour quotes; appoint CZE/ESP leads; confirm WMS/returns data feeds. Dependency: source-room reconciliation and policy limits.", "Gate 0: approve pilot charter; no irreversible lease or hiring commitment until quotes and data ownership are signed off."],
        ["Days 16–30\nDesign", "Operations; Procurement; HR; IT", "Shortlist local service/3PL sites; map inventory and service levels; verify staffing plan for five FTE; design cross-border returns and restock controls. Dependency: vendor bids, legal/tax review and inventory policy.", "Gate 1: CZE and ESP quotes within €225k/5 FTE envelope; service design passes operational risk review."],
        ["Days 31–60\nBuild and test", "Country leads; IT/WMS; Quality", "Recruit/train, configure routing and stock locations, test order allocation, returns, FX and contribution reporting; run parallel dry-run from central hub. Dependency: clean event timestamps and acceptance test data.", "Gate 2: CZE launch only after ≥95% test-order accuracy and no unresolved returns/control defect; reserve Spain release."],
        ["Days 61–90\nPilot and release", "COO; CZE lead; Spain lead; Finance", "Soft-launch CZE; review weekly uplift, OTIF, returns and realized per-unit savings; prepare Spain release package. Dependency: 30 days of reliable CZE KPI data.", "Gate 3: release Spain only if annualized CZE volume signal is at least the 10% low case, OTIF ≥95%, returns not >3 pp above baseline, and quotes remain within envelope; otherwise defer."],
    ]
    story.append(report_table(plan_rows, widths=[26 * mm, 31 * mm, 74 * mm, 40 * mm], font_size=7.2))
    story.append(report_paragraph("KPI plan", h2))
    kpi_rows = [
        ["KPI", "Definition / cadence", "Gate target / action"],
        ["Incremental volume uplift", "(eligible shipped units in hub market ÷ 2025 baseline run-rate) − 1; weekly and monthly.", "≥10% low-case signal by Gate 3; below for two months = hold Spain."],
        ["OTIF / service time", "Hub-routed orders delivered on-time/in-full; weekly.", "≥95% pilot target; below triggers process correction before expansion."],
        ["Returns", "Returned units ÷ shipped units, by country and SKU; weekly.", "No more than 3 percentage points above baseline at Gate 3; investigate root cause."],
        ["Realized savings", "(central-hub benchmark fulfillment cost − hub fulfillment cost) ÷ shipped units; monthly.", "Track against €2.1/unit CZE and €3.0/unit ESP assumptions; reprice if missed."],
        ["Contribution after fixed cost", "Net sales − net COGS − fulfillment − recurring hub cost; monthly close.", "Must be positive in base tracking; Finance owns reconciliation."],
        ["Data/control quality", "Order, return and FX completeness; monthly close.", "Zero orphan joins; all revisions and cutoff flags reconciled."],
    ]
    story.append(report_table(kpi_rows, widths=[33 * mm, 88 * mm, 50 * mm], font_size=7.2))
    story.append(PageBreak())

    # Risks and limitations/sources.
    story.append(report_paragraph("8. Risks, limitations and evidence register", h1))
    risk_rows = [
        ["Risk", "Evidence / consequence", "Mitigation"],
        ["Scenario uplift is unmeasured", "The 10/25/40% uplift is a synthetic assumption; the decision could overstate hub contribution.", "Stage CZE first, use the KPI gate, and do not treat the scenarios as causal estimates."],
        ["FX/refund joint stress", "Policy stress subtracts 10% of net sales for PLN/CZK and 3% of gross sales refunds; CZE is exposed.", "Use monthly sale-month FX translation, monitor net sales/refunds, and hold Spain if stress drivers emerge."],
        ["Capex, fixed cost and FTE estimates", "Hub options are planning inputs, not vendor quotes or labour offers.", "Obtain signed bids and staffing quotes before Gate 1; re-screen hard caps."],
        ["First-year ramp / inventory duplication", "Simple payback is steady-state and undiscounted; timing and working capital are absent.", "Stage releases and add a first-year cash/stock model before lease signature."],
        ["Data quality drift", "A future order, orphan return and duplicate/revised rows were present in the source room.", "Retain the revision/cutoff controls as a monthly close process; do not guess orphan mappings."],
    ]
    story.append(report_table(risk_rows, widths=[36 * mm, 70 * mm, 65 * mm], font_size=7.2))
    story.append(report_paragraph("Source register summary", h2))
    source_rows = [["ID", "Saved file", "Original URL / status", "Period / units"]]
    ids = {}
    for i, entry in enumerate(source_entries, start=1):
        sid = f"S{i}"
        ids[entry["file"]] = sid
        source_rows.append([sid, entry["file"], entry["source_url"] + "\n" + entry["status"], entry["period"] + "\n" + entry["units"]])
    story.append(report_table(source_rows, widths=[12 * mm, 35 * mm, 83 * mm, 41 * mm], font_size=6.3))
    story.append(Spacer(1, 3 * mm))
    story.append(report_paragraph("The full source register, hashes, archived retrieval metadata, saved raw files, analysis script, workbook, metrics JSON and board deck are delivered with this report. Source room index: http://127.0.0.1:55463/. Original public URLs are retained in deliverables/source-register.json; the local source room is a frozen evidence room, not a live account.", small))
    story.append(PageBreak())

    # Appendix formulas and methods.
    story.append(report_paragraph("Appendix. Reproducibility and formulas", h1))
    formula_text = [
        "Order eligibility: status = shipped, is_test = false, and shipped_at in calendar year 2025 after selecting the highest numeric revision per order_id.",
        "Gross sales EUR: half_up((quantity × unit_price_local − discount_local) ÷ sale-month local_per_eur, 2). Refunds EUR: half_up(sum explicit refund_local on usable returns ÷ sale-month local_per_eur, 2).",
        "Net COGS EUR: half_up(half_up(quantity × effective unit cost, 2) − half_up(restocked units × effective unit cost, 2), 2). Contribution = gross sales − refunds − net COGS − fulfillment, all order-level components half-up rounded to cents.",
        "Margin = contribution ÷ net sales; null when net sales is zero. Monthly and country tables use the same order-level rows, so reconciliation is direct.",
        "Scenario low/base/high = C×u + U×(1+u)×s − F for u = 0.10/0.25/0.40. Stress = (C − 0.03×G − FX_shock)×1.25 − C + U×1.25×s − F, where FX_shock = 0.10×N for PLN/CZK markets and zero otherwise.",
        "A reviewer can reproduce all figures by running `python analysis/reproduce.py` from the project root. The script reads only evidence/raw and writes derived outputs under deliverables/.",
    ]
    for item in formula_text:
        story.append(report_bullet(html.escape(item), body))
    story.append(Spacer(1, 6 * mm))
    story.append(report_paragraph("Completion note", h2))
    story.append(report_paragraph("The deliverables complete the requested analytical exchange. The recommendation remains conditional because demand uplift, hub savings, fixed costs, vendor quotes and first-year ramp were supplied as assumptions rather than observed causal evidence. The stated gates and flip conditions are therefore part of the recommendation, not footnotes.", body))

    def on_page(canvas, doc_obj):
        canvas.saveState()
        width, height = A4
        if doc_obj.page > 1:
            canvas.setStrokeColor(colors.HexColor("#CAD5DC"))
            canvas.line(16 * mm, height - 11 * mm, width - 16 * mm, height - 11 * mm)
            canvas.setFont("Helvetica", 7)
            canvas.setFillColor(colors.HexColor("#6B7280"))
            canvas.drawString(16 * mm, height - 8 * mm, "Meridian Parts | European service-hub expansion")
        canvas.setStrokeColor(colors.HexColor("#CAD5DC"))
        canvas.line(16 * mm, 10 * mm, width - 16 * mm, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawRightString(width - 16 * mm, 6 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path


SLIDE_W = 13.333
SLIDE_H = 7.5
NAVY = RGBColor(18, 48, 74)
TEAL = RGBColor(15, 123, 120)
ORANGE = RGBColor(232, 144, 56)
INK = RGBColor(36, 50, 61)
MUTED = RGBColor(107, 114, 128)
LIGHT = RGBColor(242, 246, 248)
WHITE = RGBColor(255, 255, 255)


def ppt_text(slide, left: float, top: float, width: float, height: float, text: str, size: float = 16, color: RGBColor = INK, bold: bool = False, align=PP_ALIGN.LEFT, font: str = "Aptos") -> Any:
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Pt(2)
    tf.margin_right = Pt(2)
    tf.margin_top = Pt(1)
    tf.margin_bottom = Pt(1)
    p = tf.paragraphs[0]
    p.text = text
    p.alignment = align
    p.font.name = font
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    return box


def ppt_bullets(slide, left: float, top: float, width: float, height: float, bullets: list[str], size: float = 16, color: RGBColor = INK) -> Any:
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Pt(4)
    tf.margin_right = Pt(3)
    for idx, bullet in enumerate(bullets):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = "• " + bullet
        p.level = 0
        p.font.name = "Aptos"
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(8)
    return box


def ppt_title(slide, title_text: str, subtitle_text: str | None = None) -> None:
    ppt_text(slide, 0.55, 0.26, 12.2, 0.45, title_text, size=26, color=NAVY, bold=True)
    if subtitle_text:
        ppt_text(slide, 0.58, 0.76, 12.0, 0.32, subtitle_text, size=10.5, color=MUTED)
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(1.08), Inches(12.2), Inches(0.025))
    line.fill.solid()
    line.fill.fore_color.rgb = TEAL
    line.line.fill.background()


def ppt_footer(slide, slide_no: int, source: str = "Meridian Parts | Synthetic client | EUR unless stated") -> None:
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(7.13), Inches(12.2), Inches(0.012))
    line.fill.solid()
    line.fill.fore_color.rgb = RGBColor(202, 213, 220)
    line.line.fill.background()
    ppt_text(slide, 0.58, 7.19, 10.8, 0.18, source, size=7.5, color=MUTED)
    ppt_text(slide, 11.9, 7.19, 0.75, 0.18, str(slide_no), size=8, color=MUTED, align=PP_ALIGN.RIGHT)


def ppt_kpi(slide, left: float, top: float, width: float, label: str, value: str, fill: RGBColor = LIGHT) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.92))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = fill
    ppt_text(slide, left + 0.12, top + 0.12, width - 0.24, 0.2, label.upper(), size=8.5, color=MUTED, bold=True)
    ppt_text(slide, left + 0.12, top + 0.36, width - 0.24, 0.38, value, size=20, color=NAVY, bold=True)


def ppt_table(slide, left: float, top: float, width: float, height: float, data: list[list[str]], font_size: float = 10, first_col_width: float | None = None) -> Any:
    rows, cols = len(data), len(data[0])
    shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top), Inches(width), Inches(height))
    table = shape.table
    if first_col_width:
        table.columns[0].width = Inches(first_col_width)
        remaining = (width - first_col_width) / (cols - 1)
        for c in range(1, cols):
            table.columns[c].width = Inches(remaining)
    for r in range(rows):
        table.rows[r].height = Inches(height / rows)
        for c in range(cols):
            cell = table.cell(r, c)
            cell.text = str(data[r][c])
            cell.margin_left = Pt(4)
            cell.margin_right = Pt(4)
            cell.margin_top = Pt(2)
            cell.margin_bottom = Pt(2)
            cell.fill.solid()
            cell.fill.fore_color.rgb = NAVY if r == 0 else (LIGHT if r % 2 == 0 else WHITE)
            for p in cell.text_frame.paragraphs:
                p.font.name = "Aptos"
                p.font.size = Pt(font_size if r else font_size - 0.5)
                p.font.bold = r == 0
                p.font.color.rgb = WHITE if r == 0 else INK
                p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.RIGHT
    return shape


def add_ppt_image(slide, image_path: Path, left: float, top: float, width: float, height: float) -> None:
    slide.shapes.add_picture(str(image_path), Inches(left), Inches(top), width=Inches(width), height=Inches(height))


def add_deck(core: dict[str, Any], out_dir: Path, source_entries: list[dict[str, Any]], figures: dict[str, Path]) -> Path:
    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]
    rec = core["recommendation"]
    countries = core["countries"]
    scenarios = core["scenarios"]

    # Slide 1
    slide = prs.slides.add_slide(blank)
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(6.8), Inches(SLIDE_W), Inches(0.7)).fill.solid()
    bottom = slide.shapes[-1]
    bottom.fill.fore_color.rgb = TEAL
    bottom.line.fill.background()
    ppt_text(slide, 0.75, 0.82, 11.8, 0.5, "MERIDIAN PARTS", size=20, color=RGBColor(164, 228, 222), bold=True)
    ppt_text(slide, 0.75, 1.55, 11.3, 1.3, "European service-hub expansion", size=34, color=WHITE, bold=True)
    ppt_text(slide, 0.78, 3.07, 10.8, 0.75, f"Recommendation: staged {rec['selected_option']} envelope", size=22, color=WHITE, bold=True)
    ppt_text(slide, 0.78, 4.15, 11.0, 0.8, f"{eur(rec['base_incremental_contribution_eur'])} base annual contribution after recurring cost | {eur(rec['capex_eur'])} capex | {rec['fte']} FTE | {rec['payback_years_base']:.2f}y simple payback", size=14, color=RGBColor(224, 236, 241))
    ppt_text(slide, 0.78, 6.98, 9.4, 0.22, "Board presentation | 2025 shipped sales and returns known through 31 Jan 2026 | Synthetic client", size=8, color=WHITE)
    ppt_text(slide, 12.0, 6.98, 0.5, 0.22, "1", size=8, color=WHITE, align=PP_ALIGN.RIGHT)

    # Slide 2
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "Board decision", "Approve the CZE+ESP envelope, launch Czechia first, and gate Spain on pilot evidence")
    ppt_kpi(slide, 0.65, 1.42, 2.25, "Base increment", eur(rec["base_incremental_contribution_eur"]), RGBColor(224, 242, 240))
    ppt_kpi(slide, 3.05, 1.42, 2.25, "Defined stress", eur(rec["stress_incremental_contribution_eur"]), RGBColor(255, 242, 225))
    ppt_kpi(slide, 5.45, 1.42, 2.25, "Capex", eur(rec["capex_eur"]), LIGHT)
    ppt_kpi(slide, 7.85, 1.42, 2.25, "FTE", str(rec["fte"]), LIGHT)
    ppt_kpi(slide, 10.25, 1.42, 2.25, "Payback", f"{rec['payback_years_base']:.2f}y", LIGHT)
    ppt_text(slide, 0.72, 2.72, 5.5, 0.32, "Decision rule used", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 0.8, 3.08, 5.6, 2.6, [
        "Stay inside the explicit €450k capex, seven-FTE and two-hub limits.",
        "Require positive annual increment in the policy's defined joint stress.",
        "Among survivors, rank by base annual incremental contribution.",
        "Treat this risk screen as an assumed planning preference, not a board-supplied fact.",
    ], size=14)
    ppt_text(slide, 6.85, 2.72, 5.5, 0.32, "What the choice gives up", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 6.95, 3.08, 5.55, 2.7, [
        "NLD+ESP has the strongest stress result (€107.6k) but gives up €31.2k of base contribution, needs €45k more capex and one more FTE.",
        "POL+ESP is dominated by CZE+ESP on low/base/high/stress and needs more resources.",
        "If demand evidence is weak, defer the second release; the model is not a causal forecast.",
    ], size=13.5)
    ppt_footer(slide, 2, "Scenario policy, hub-options.csv, reconciled 2025 country totals")

    # Slide 3
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "2025 baseline: ESP and CZE carry the largest contribution base", "Computed from eligible orders after revision, status, test, cutoff and return controls")
    baseline = [["Market", "Orders", "Units", "Net sales", "Contribution", "Margin", "Returned units"]]
    for r in countries.itertuples(index=False):
        baseline.append([r.country, f"{r.shipped_orders:,}", f"{r.shipped_units:,}", eur(r.net_sales_eur, 0), eur(r.contribution_eur, 0), pct(r.margin), f"{r.returned_units:,}"])
    ppt_table(slide, 0.65, 1.35, 5.45, 3.15, baseline, font_size=9, first_col_width=0.82)
    add_ppt_image(slide, figures["country_contribution"], 6.35, 1.35, 6.35, 3.45)
    ppt_text(slide, 0.72, 4.82, 12.0, 0.3, "Accounting guardrails", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 0.8, 5.18, 12.0, 1.25, [
        "1,328 raw order rows → 1,297 unique order IDs → 1,254 eligible 2025 shipped orders; 18 higher revisions replace prior rows.",
        "241 usable linked returns after deduplication and the inclusive 31 Jan 2026 cutoff; orphan R-ORPHAN is quarantined.",
        "12 valid zero-price eligible shipments are retained. Monthly totals reconcile to country totals to the cent.",
    ], size=11.5)
    ppt_footer(slide, 3, "Synthetic client exports and data-dictionary.md; no raw-row order counting")

    # Slide 4
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "Context informs capacity — it does not prove demand", "Archived official World Bank observations, preserved with retrieval vintage")
    add_ppt_image(slide, figures["market_context"], 0.65, 1.3, 6.1, 2.9)
    add_ppt_image(slide, figures["fx_rates"], 6.95, 1.3, 5.9, 2.9)
    ppt_text(slide, 0.72, 4.42, 5.8, 0.3, "Market read", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 0.8, 4.8, 5.8, 1.75, [
        "NLD and DEU have the highest 2024 GDP per capita in current US$.",
        "Population grows 2022–24 in DEU, FRA, NLD, CZE and ESP; POL declines.",
        "Population/GDP are context only, not direct replacement-assembly demand evidence.",
    ], size=12.5)
    ppt_text(slide, 6.98, 4.42, 5.8, 0.3, "FX discipline", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 7.05, 4.8, 5.7, 1.75, [
        "PLN/CZK use the original sale-month ECB mean of published business-day reference observations.",
        "Quotes are local currency units per EUR; EUR is 1.0. No inversion or today's rate.",
        "FX is an analytical translation assumption, not an actual transaction hedge result.",
    ], size=12.5)
    ppt_footer(slide, 4, "Archived World Bank population.json / gdp-per-capita.json; ECB ecb-history.zip and extracted CSV")

    # Slide 5
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "CZE+ESP leads the feasible base case and remains positive in defined stress", "Annual incremental contribution after recurring fixed cost; capex is year-zero")
    add_ppt_image(slide, figures["scenario_compare"], 0.55, 1.25, 7.1, 5.4)
    top = scenarios.loc[scenarios.scenario.eq("base")].sort_values("incremental_contribution_eur", ascending=False).head(7)
    econ = [["Option", "Base", "Stress", "Capex / FTE"]]
    for r in top.itertuples(index=False):
        stress_val = scenarios.loc[(scenarios.country.eq(r.country)) & scenarios.scenario.eq("stress"), "incremental_contribution_eur"].iloc[0]
        econ.append([r.country, eur(r.incremental_contribution_eur), eur(stress_val), f"{eur(r.capex_eur)} / {int(r.fte)}"])
    ppt_table(slide, 7.9, 1.65, 4.55, 3.35, econ, font_size=9, first_col_width=1.25)
    ppt_text(slide, 7.95, 5.25, 4.4, 0.3, "Scenario assumptions", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 7.98, 5.62, 4.4, 1.05, [
        "Low/base/high uplift: 10% / 25% / 40%.",
        "Stress: 3% gross-sales refund shock; 10% net-sales shock in PLN/CZK; base 25% uplift.",
    ], size=11.3)
    ppt_footer(slide, 5, "scenario-policy.md; pairs add country figures/capex/FTE without synergy")

    # Slide 6
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "The decision is conditional, not certain", "The largest uncertainty is the assumed hub uplift and timing of first-year realization")
    ppt_text(slide, 0.75, 1.38, 5.8, 0.3, "Flip conditions", size=15, color=TEAL, bold=True)
    ppt_bullets(slide, 0.83, 1.78, 5.65, 3.4, [
        "If normal volume uplift for CZE+ESP falls below ~2.7%, the steady-state formula falls below break-even before stress.",
        "If the board values stress resilience over base value, NLD+ESP becomes the preferred alternative.",
        "If quotes exceed €225k capex or five FTE, re-screen rather than waive the policy cap.",
        "If pilot uplift is below the 10% low case for two consecutive months, hold Spain.",
    ], size=14)
    ppt_text(slide, 6.95, 1.38, 5.6, 0.3, "Alternative comparison", size=15, color=TEAL, bold=True)
    alt_data = [
        ["", "Base", "Stress", "Capex/FTE"],
        ["CZE+ESP", eur(198099.31), eur(32179.71), "€225k / 5"],
        ["NLD+ESP", eur(166931.42), eur(107630.13), "€270k / 6"],
        ["POL+ESP", eur(186328.84), eur(29263.85), "€240k / 6"],
        ["DEFER", "€0", "€0", "€0 / 0"],
    ]
    ppt_table(slide, 6.95, 1.82, 5.55, 2.4, alt_data, font_size=11, first_col_width=1.45)
    ppt_text(slide, 6.98, 4.58, 5.4, 0.3, "Accepted risk", size=15, color=TEAL, bold=True)
    ppt_bullets(slide, 7.05, 4.98, 5.25, 1.55, [
        "CZE+ESP gives up €75.5k of stress contribution versus NLD+ESP while using €45k less capex and one fewer FTE.",
        "Payback is undiscounted and steady-state; first-year ramp and working capital are not modelled.",
    ], size=12.6)
    ppt_footer(slide, 6, "Trade-off screen is an explicit planning assumption; outputs are computed, not causal proof")

    # Slide 7
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "90-day plan: prepare both, launch CZE, gate ESP", "Owners, dependencies and measurable release criteria")
    plan = [
        ["Days", "Owner", "Action", "Gate"],
        ["0–15", "COO / Finance / PMO", "Baseline, quotes, leads, WMS/returns data ownership", "Pilot charter; no irreversible commitments"],
        ["16–30", "Ops / Proc / HR / IT", "Sites, labour plan, inventory/returns design", "Within €225k/5 FTE envelope"],
        ["31–60", "Leads / WMS / Quality", "Hire/train, configure, dry-run, control tests", "CZE: ≥95% test-order accuracy"],
        ["61–90", "COO / country leads / Finance", "CZE soft launch; 30-day KPI review; Spain release pack", "≥10% uplift signal, OTIF ≥95%, returns ≤+3pp"],
    ]
    ppt_table(slide, 0.65, 1.35, 12.05, 2.7, plan, font_size=9.3, first_col_width=0.7)
    ppt_text(slide, 0.72, 4.45, 5.8, 0.3, "KPI scoreboard", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 0.8, 4.82, 5.7, 1.55, [
        "Incremental shipped units versus 2025 run-rate; weekly/monthly.",
        "OTIF/service time; returned units ÷ shipped units; realized savings per unit.",
        "Contribution after fixed cost; capex/FTE readiness; zero orphan joins.",
    ], size=12.5)
    ppt_text(slide, 6.9, 4.45, 5.8, 0.3, "Dependencies", size=14, color=TEAL, bold=True)
    ppt_bullets(slide, 6.98, 4.82, 5.65, 1.55, [
        "Vendor quotes and legal/tax review before lease signature.",
        "Reliable event timestamps and WMS/returns data feeds before KPI gate.",
        "First-year cash/stock model before irreversible expansion.",
    ], size=12.5)
    ppt_footer(slide, 7, "Management thresholds are proposed operating gates, not observed facts")

    # Slide 8
    slide = prs.slides.add_slide(blank)
    ppt_title(slide, "Board ask and limitations", "Approve a staged option with a visible stop condition")
    ppt_text(slide, 0.75, 1.35, 6.0, 0.35, "Approve", size=16, color=TEAL, bold=True)
    ppt_bullets(slide, 0.83, 1.78, 5.8, 2.1, [
        "CZE+ESP planning envelope: €225k capex / 5 FTE / up to two hubs.",
        "CZE first; Spain released only after Gate 3 KPI evidence.",
        "Finance/COO to reprice the model after vendor quotes and pilot data.",
    ], size=15)
    ppt_text(slide, 7.0, 1.35, 5.6, 0.35, "Do not over-read", size=16, color=TEAL, bold=True)
    ppt_bullets(slide, 7.08, 1.78, 5.55, 2.1, [
        "Uplift, costs and savings are synthetic policy assumptions.",
        "Population/GDP are public context, not demand proof.",
        "Payback is simple/undiscounted and excludes ramp, working capital and tax.",
    ], size=15)
    call = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), Inches(4.45), Inches(11.85), Inches(1.15))
    call.fill.solid()
    call.fill.fore_color.rgb = RGBColor(224, 242, 240)
    call.line.color.rgb = TEAL
    ppt_text(slide, 1.0, 4.68, 11.3, 0.55, "Decision in one sentence: fund the CZE+ESP envelope because it is the strongest feasible base-and-low case that stays positive in the defined stress, but make Spain earn release through the 90-day KPI gate.", size=17, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    ppt_text(slide, 0.78, 6.22, 12.0, 0.42, "Evidence: frozen source room at http://127.0.0.1:55463/; archived official World Bank/ECB files with hashes; synthetic client exports and policy. Reproduce: python analysis/reproduce.py.", size=9.5, color=MUTED, align=PP_ALIGN.CENTER)
    ppt_footer(slide, 8, "Report, workbook, metrics.json, source register and raw evidence delivered alongside this deck")

    path = out_dir / "meridian_parts_board_presentation.pptx"
    prs.save(path)
    return path


def build_quality(
    order_quality: dict[str, Any],
    return_quality: dict[str, Any],
    fx_quality: dict[str, Any],
    monthly: pd.DataFrame,
    countries: pd.DataFrame,
    scenarios_meta: dict[str, Any],
    detail: pd.DataFrame,
) -> dict[str, Any]:
    monthly_country = monthly.groupby("country")[MONEY_FIELDS + ["shipped_orders", "shipped_units", "returned_units"]].sum()
    country_check = countries.set_index("country")[MONEY_FIELDS + ["shipped_orders", "shipped_units", "returned_units"]].subtract(monthly_country).fillna(0).round(2)
    return {
        "status": "complete_with_disclosed_anomalies",
        "classification": {
            "synthetic_client_inputs": "orders, returns, corrections, unit costs, hub options and scenario policy",
            "archived_public_inputs": "World Bank population/GDP responses and ECB history preserved in source room",
            "live_research_used": False,
        },
        "order_reconciliation": order_quality,
        "return_reconciliation": return_quality,
        "fx": fx_quality,
        "anomalies_and_handling": [
            "Order rows are deduplicated by order_id and highest numeric revision; higher revisions replace the full prior row.",
            "Identical repeated order and return rows are counted once; no raw row is treated as a distinct order or return.",
            "Cancelled, test, and non-2025 shipment records are excluded; valid zero-price eligible shipments remain in the base.",
            "Returns are deduplicated by return_id/revision, filtered to the inclusive 2026-01-31 cutoff, and only linked to eligible orders. Orphans are quarantined rather than guessed.",
            "Individual order monetary components are half-up rounded to cents before aggregation; PLN/CZK use the original sale-month ECB business-day mean quote.",
            "No payment settlement dates, tax, working-capital, or discounted cash-flow data were supplied; cash is not inferred from booked sales or contribution.",
        ],
        "missing_values": {
            "eligible_order_rows_with_missing_required_fields": order_quality["missing_required_values_eligible"],
            "selected_return_rows_with_missing_required_fields": return_quality["missing_required_values_selected"],
            "eligible_order_rows_without_effective_unit_cost": 0,
            "monthly_grid_missing_country_months": int(len(monthly.loc[monthly["shipped_orders"].eq(0)])),
        },
        "reconciliations": {
            "country_minus_monthly_max_abs": float(country_check.abs().to_numpy().max()) if not country_check.empty else 0.0,
            "country_minus_monthly_by_metric": {metric: float(country_check[metric].abs().max()) for metric in country_check.columns},
            "order_detail_rows": int(len(detail)),
            "country_total_orders": int(countries["shipped_orders"].sum()),
            "country_total_units": int(countries["shipped_units"].sum()),
        },
        "scenario_scope": scenarios_meta,
        "limitations": [
            "The hub uplift, savings, fixed costs, and stress are board planning assumptions from the synthetic policy, not measured demand or causal effects.",
            "World Bank GDP per capita is current US$ and population is not direct evidence of replacement-assembly demand.",
            "ECB reference rates are analytical translation assumptions, not actual transaction FX or a forecast.",
            "Simple payback is undiscounted and excludes year-zero capex from annual incremental contribution by policy.",
        ],
    }


def run_core() -> dict[str, Any]:
    eligible, order_info = load_orders()
    fx_lookup, fx_monthly, fx_quality = load_fx()
    returns, return_info = load_returns(eligible)
    costs = load_unit_costs()
    detail = build_order_detail(eligible, returns, fx_lookup, costs)
    monthly, countries = build_metrics(detail)
    market = load_market_context()
    options = pd.read_csv(RAW / "hub-options.csv")
    scenarios, scenarios_meta = build_scenarios(countries, options)
    recommendation = select_recommendation(scenarios)
    quality = build_quality(order_info["quality"], return_info["quality"], fx_quality, monthly, countries, scenarios_meta, detail)
    return {
        "eligible": eligible,
        "order_info": order_info,
        "returns": returns,
        "return_info": return_info,
        "detail": detail,
        "monthly": monthly,
        "countries": countries,
        "fx_monthly": fx_monthly,
        "market": market,
        "options": options,
        "scenarios": scenarios,
        "recommendation": recommendation,
        "quality": quality,
        "run_time": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce Meridian Parts analysis and board deliverables")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output directory (default: deliverables)")
    args = parser.parse_args()
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    core = run_core()
    figures = build_figures(core, out_dir / "figures")
    source_entries = source_register(core["run_time"])
    metrics_path = write_derived_outputs(core, out_dir, source_entries, figures)
    workbook_path = add_workbook(core, out_dir, source_entries, figures)
    report_path = add_report(core, out_dir, source_entries, figures)
    deck_path = add_deck(core, out_dir, source_entries, figures)
    print(json.dumps({
        "metrics": str(metrics_path),
        "workbook": str(workbook_path),
        "report": str(report_path),
        "presentation": str(deck_path),
        "recommendation": core["recommendation"],
        "quality_status": core["quality"]["status"],
    }, indent=2, default=json_default))


if __name__ == "__main__":
    main()
