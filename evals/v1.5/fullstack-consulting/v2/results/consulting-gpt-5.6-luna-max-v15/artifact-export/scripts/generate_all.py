"""Build the full Meridian Parts deliverable set.

Run from the project root:
  python3 scripts/generate_all.py

The script rebuilds analysis_outputs, deliverables/metrics.json, the workbook,
the executive PDF, the board PPTX and the saved chart assets from evidence/raw.
"""

from __future__ import annotations

from pathlib import Path
import math
import os
import sys
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

from analysis import (
    COUNTRIES,
    COUNTRY_NAMES,
    DELIVERABLES,
    OUTPUT,
    build_metrics,
)


CHARTS = OUTPUT / "charts"
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttf",
    "/Library/Fonts/Arial.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

NAVY = (15, 34, 58)
BLUE = (30, 104, 172)
TEAL = (0, 143, 136)
ORANGE = (224, 122, 42)
RED = (191, 61, 61)
GREEN = (42, 137, 91)
SLATE = (84, 100, 117)
LIGHT = (235, 241, 247)
GRID = (209, 218, 228)
WHITE = (255, 255, 255)


def font(size: int, bold: bool = False):
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_CANDIDATES
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fmt_eur(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "—"
    return f"€{value:,.{decimals}f}"


def fmt_pct(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%"


def draw_title(draw: ImageDraw.ImageDraw, title: str, subtitle: str, width: int):
    draw.text((56, 34), title, fill=NAVY, font=font(30, True))
    draw.text((58, 78), subtitle, fill=SLATE, font=font(16))
    draw.line((56, 116, width - 56, 116), fill=GRID, width=2)


def draw_base_contribution(data) -> Path:
    width, height = 1400, 760
    im = Image.new("RGB", (width, height), WHITE)
    d = ImageDraw.Draw(im)
    draw_title(d, "2025 contribution by market", "Country totals; EUR, after refunds, net COGS and fulfillment", width)
    countries = data["countries"].set_index("country").loc[COUNTRIES].reset_index()
    vals = countries["contribution_eur"].tolist()
    maxv = max(vals) * 1.16
    left, right, top, bottom = 115, 60, 170, 125
    plot_h = height - top - bottom
    bar_w = (width - left - right) / len(vals) * 0.62
    gap = (width - left - right) / len(vals)
    for tick in range(0, 5):
        y = top + plot_h - plot_h * tick / 4
        v = maxv * tick / 4
        d.line((left, y, width - right, y), fill=GRID, width=1)
        d.text((18, y - 9), f"€{v/1000:,.0f}k", fill=SLATE, font=font(15))
    for i, row in countries.iterrows():
        x0 = left + gap * i + (gap - bar_w) / 2
        x1 = x0 + bar_w
        y1 = top + plot_h
        y0 = y1 - plot_h * float(row.contribution_eur) / maxv
        d.rounded_rectangle((x0, y0, x1, y1), radius=8, fill=BLUE if row.country not in {"CZE", "ESP"} else TEAL)
        label = f"€{row.contribution_eur/1000:,.0f}k"
        bbox = d.textbbox((0, 0), label, font=font(16, True))
        d.text((x0 + (bar_w - (bbox[2] - bbox[0])) / 2, y0 - 30), label, fill=NAVY, font=font(16, True))
        code = row.country
        name = COUNTRY_NAMES[code]
        d.text((x0 + (bar_w - d.textlength(code, font=font(17, True))) / 2, y1 + 16), code, fill=NAVY, font=font(17, True))
        d.text((x0 + (bar_w - d.textlength(name, font=font(14))) / 2, y1 + 42), name, fill=SLATE, font=font(14))
    d.text((56, height - 45), "Source: computed from canonical shipped orders; source register S03–S08.", fill=SLATE, font=font(14))
    path = CHARTS / "baseline_contribution.png"
    im.save(path)
    return path


def draw_option_chart(data) -> Path:
    width, height = 1700, 1180
    im = Image.new("RGB", (width, height), WHITE)
    d = ImageDraw.Draw(im)
    draw_title(d, "Feasible hub options: base contribution with defined stress", "Annual incremental contribution; sorted by base case, EUR", width)
    ranks = data["rankings"].copy()
    # Keep all feasible options; labels are short and the chart is intentionally tall.
    left, right, top, bottom = 240, 95, 160, 92
    plot_w = width - left - right
    row_h = (height - top - bottom) / len(ranks)
    max_positive = float(ranks.incremental_contribution_eur.max())
    max_negative = float(abs(ranks.stress_incremental_contribution_eur.min()))
    range_value = (max_positive + max_negative) * 1.10
    zero_x = left + plot_w * (max_negative * 1.05) / range_value
    for i, row in ranks.iterrows():
        y = top + row_h * i + row_h * 0.18
        d.text((45, y + 8), row.option, fill=NAVY, font=font(17, True))
        base_w = plot_w * float(row.incremental_contribution_eur) / range_value
        stress_w = plot_w * float(row.stress_incremental_contribution_eur) / range_value
        d.rounded_rectangle((zero_x, y, zero_x + base_w, y + row_h * 0.25), radius=5, fill=BLUE if row.option != "CZE+ESP" else TEAL)
        if stress_w >= 0:
            d.rounded_rectangle((zero_x, y + row_h * 0.34, zero_x + stress_w, y + row_h * 0.59), radius=5, fill=ORANGE)
        else:
            d.rounded_rectangle((zero_x + stress_w, y + row_h * 0.34, zero_x, y + row_h * 0.59), radius=5, fill=RED)
        d.text((zero_x + base_w + 10, y - 2), f"{row.incremental_contribution_eur/1000:,.0f}k", fill=NAVY, font=font(14, True))
        d.text((zero_x + (stress_w if stress_w >= 0 else 0) + 10 if stress_w >= 0 else zero_x + stress_w - 64, y + row_h * 0.34 - 1), f"{row.stress_incremental_contribution_eur/1000:,.0f}k", fill=RED if stress_w < 0 else ORANGE, font=font(14, True))
    d.rounded_rectangle((width - 440, 126, width - 398, 148), radius=4, fill=BLUE)
    d.text((width - 385, 126), "Base case", fill=NAVY, font=font(15))
    d.rounded_rectangle((width - 260, 126, width - 218, 148), radius=4, fill=ORANGE)
    d.text((width - 205, 126), "Defined stress", fill=NAVY, font=font(15))
    d.text((56, height - 45), "Stress = 3% of gross sales refund shock plus 10% of net sales FX shock for PLN/CZK markets; source S02.", fill=SLATE, font=font(14))
    path = CHARTS / "option_comparison.png"
    im.save(path)
    return path


def draw_monthly_chart(data) -> Path:
    width, height = 1500, 820
    im = Image.new("RGB", (width, height), WHITE)
    d = ImageDraw.Draw(im)
    draw_title(d, "Monthly contribution pattern", "2025 contribution by country; EUR", width)
    monthly = data["monthly"]
    left, right, top, bottom = 105, 70, 160, 105
    plot_w, plot_h = width - left - right, height - top - bottom
    maxv = monthly.contribution_eur.max() * 1.16
    for tick in range(5):
        y = top + plot_h - plot_h * tick / 4
        d.line((left, y, width - right, y), fill=GRID, width=1)
        d.text((16, y - 9), f"€{maxv*tick/4/1000:,.0f}k", fill=SLATE, font=font(14))
    colors = {"DEU": BLUE, "FRA": ORANGE, "NLD": TEAL, "POL": (128, 91, 165), "CZE": GREEN, "ESP": (210, 76, 104)}
    month_x = {month: left + plot_w * i / 11 for i, month in enumerate(sorted(monthly.month.unique()))}
    for country in COUNTRIES:
        part = monthly[monthly.country == country].sort_values("month")
        pts = []
        for _, row in part.iterrows():
            x = month_x[row.month]
            y = top + plot_h - plot_h * float(row.contribution_eur) / maxv
            pts.append((x, y))
        d.line(pts, fill=colors[country], width=4)
        for x, y in pts:
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=colors[country])
        d.text((pts[-1][0] + 10, pts[-1][1] - 9), country, fill=colors[country], font=font(15, True))
    for i, month in enumerate(sorted(monthly.month.unique())):
        x = month_x[month]
        d.text((x - 22, top + plot_h + 20), month[-2:], fill=SLATE, font=font(14))
    d.text((56, height - 45), "Each line sums order-level half-up rounded components by original shipment month.", fill=SLATE, font=font(14))
    path = CHARTS / "monthly_contribution.png"
    im.save(path)
    return path


def draw_fx_chart(data) -> Path:
    width, height = 1400, 720
    im = Image.new("RGB", (width, height), WHITE)
    d = ImageDraw.Draw(im)
    draw_title(d, "2025 ECB monthly reference-rate means", "Local currency units per EUR; not transaction FX", width)
    fx = data["fx"]
    left, right, top, bottom = 120, 90, 165, 100
    plot_w, plot_h = width - left - right, height - top - bottom
    lo, hi = fx.local_per_eur.min() * 0.96, fx.local_per_eur.max() * 1.04
    colors = {"PLN": BLUE, "CZK": TEAL}
    months = sorted(fx.month.unique())
    xmap = {m: left + plot_w * i / 11 for i, m in enumerate(months)}
    for tick in range(5):
        v = lo + (hi - lo) * tick / 4
        y = top + plot_h - plot_h * (v - lo) / (hi - lo)
        d.line((left, y, width - right, y), fill=GRID, width=1)
        d.text((25, y - 9), f"{v:.1f}", fill=SLATE, font=font(14))
    for currency in ["PLN", "CZK"]:
        part = fx[fx.currency == currency].sort_values("month")
        pts = []
        for _, row in part.iterrows():
            x = xmap[row.month]
            y = top + plot_h - plot_h * (row.local_per_eur - lo) / (hi - lo)
            pts.append((x, y))
        d.line(pts, fill=colors[currency], width=4)
        for x, y in pts:
            d.ellipse((x - 4, y - 4, x + 4, y + 4), fill=colors[currency])
        d.text((pts[-1][0] + 12, pts[-1][1] - 9), currency, fill=colors[currency], font=font(16, True))
    for i, month in enumerate(months):
        d.text((xmap[month] - 20, top + plot_h + 20), month[-2:], fill=SLATE, font=font(14))
    d.text((56, height - 42), "Source: archived ECB history S11/S12; arithmetic mean across available published business days.", fill=SLATE, font=font(14))
    path = CHARTS / "fx_monthly.png"
    im.save(path)
    return path


def build_charts(data) -> dict[str, Path]:
    CHARTS.mkdir(parents=True, exist_ok=True)
    return {
        "baseline": draw_base_contribution(data),
        "options": draw_option_chart(data),
        "monthly": draw_monthly_chart(data),
        "fx": draw_fx_chart(data),
    }


def write_workbook(data, charts: dict[str, Path]) -> Path:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.formatting.rule import ColorScaleRule
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.table import Table, TableStyleInfo

    wb = Workbook()
    wb.remove(wb.active)
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    header_fill = PatternFill("solid", fgColor="0F223A")
    header_font = Font(name="Aptos", size=10, bold=True, color="FFFFFF")
    title_font = Font(name="Aptos Display", size=18, bold=True, color="0F223A")
    note_font = Font(name="Aptos", size=10, italic=True, color="546475")
    thin = Side(style="thin", color="D1DAE4")
    border = Border(bottom=thin)

    def format_value_column(ws, col_idx: int, key: str):
        for cell in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            c = cell[0]
            if key == "margin":
                c.number_format = "0.0%"
            elif key in {"local_per_eur", "fx_local_per_eur"}:
                c.number_format = "0.000000"
            elif key == "payback_years" or key == "break_even_uplift":
                c.number_format = "0.00"
            elif key.endswith("_eur") or key in {"gross_local", "refund_local", "unit_price_local", "discount_local"}:
                c.number_format = '€#,##0.00;[Red]-€#,##0.00'
            elif key in {"population", "quantity", "returned_units", "restocked_units", "shipped_orders", "shipped_units", "return_records", "fte", "observations"}:
                c.number_format = "#,##0"

    def write_df(name: str, df, columns: list[str] | None = None, widths: dict[str, int] | None = None):
        ws = wb.create_sheet(name)
        columns = columns or list(df.columns)
        ws.append(columns)
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        for record in df[columns].itertuples(index=False, name=None):
            values = []
            for value in record:
                if isinstance(value, (list, tuple, dict)):
                    value = ",".join(str(x) for x in value) if not isinstance(value, dict) else str(value)
                values.append(value)
            ws.append(values)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        ws.row_dimensions[1].height = 30
        for cell in ws[1]:
            cell.border = border
        widths = widths or {}
        for idx, key in enumerate(columns, 1):
            ws.column_dimensions[chr(64 + idx) if idx <= 26 else "A"].width = widths.get(key, min(max(len(str(key)) + 2, 12), 24))
            format_value_column(ws, idx, key)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=False)
        if len(df) > 0:
            ref = f"A1:{chr(64 + len(columns)) if len(columns) <= 26 else 'Z'}{len(df)+1}"
            table_name = "T" + "".join(ch for ch in name if ch.isalnum())
            tab = Table(displayName=table_name[:250], ref=ref)
            tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
            ws.add_table(tab)
        return ws

    # Readme first: a board-friendly landing page.
    ws = wb.create_sheet("Readme")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Meridian Parts — European service-hub expansion"
    ws["A1"].font = title_font
    ws.merge_cells("A1:H1")
    ws["A3"] = "Recommendation"
    ws["A3"].font = Font(bold=True, color="0F223A", size=12)
    rec = data["metrics"]["recommendation"]
    ws["A4"] = f"Gated funding for {', '.join(rec['countries'])}: {fmt_eur(rec['capex_eur'])} year-zero capex, {rec['fte']} FTE."
    ws["A5"] = f"Base annual incremental contribution: {fmt_eur(data['rankings'].iloc[0].incremental_contribution_eur)}; base payback: {data['rankings'].iloc[0].payback_years:.2f} years; volume break-even: {rec['break_even_volume_uplift']:.2%}."
    ws["A6"] = "Release capex only after the 90-day gates; synthetic scenarios are planning arithmetic, not causal demand evidence."
    ws.merge_cells("A4:H4")
    ws.merge_cells("A5:H5")
    ws.merge_cells("A6:H6")
    for r in [4, 5, 6]:
        ws[f"A{r}"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A8"] = "How to use"
    ws["A8"].font = Font(bold=True, color="0F223A", size=12)
    readme_rows = [
        ("Scope", "2025 shipped_at calendar year; return receipts known through 2026-01-31 inclusive."),
        ("Order grain", "One canonical order_id / one SKU row; raw duplicates removed, highest numeric revision wins."),
        ("FX", "Original sale month ECB mean business-day quote, local currency units per EUR; EUR=1."),
        ("Rounding", "Order-level gross sales, refunds, net COGS, fulfillment and contribution rounded half-up to cents before summing."),
        ("Returns", "Highest return revision wins; exact duplicates removed; valid return IDs additive; orphan and post-cutoff returns quarantined/excluded."),
        ("Scenario", "Annual incremental contribution after recurring fixed cost; capex is year-zero only. Pair figures add without synergy."),
        ("Evidence status", "Synthetic client exports/assumptions are separated from public official World Bank/ECB snapshots in Source Register."),
        ("Reproduce", "Run the bundled Python command in REPRODUCE.md; it rebuilds analysis_outputs, charts, metrics.json, this workbook, the report and deck."),
    ]
    for i, (k, v) in enumerate(readme_rows, 10):
        ws[f"A{i}"] = k
        ws[f"A{i}"].font = Font(bold=True, color="0F223A")
        ws[f"B{i}"] = v
        ws[f"B{i}"].alignment = Alignment(wrap_text=True, vertical="top")
        ws.merge_cells(start_row=i, start_column=2, end_row=i, end_column=8)
    ws.column_dimensions["A"].width = 22
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 18
    ws.row_dimensions[10].height = 32
    ws.row_dimensions[11].height = 32
    ws.row_dimensions[12].height = 34
    ws.row_dimensions[13].height = 34
    ws.row_dimensions[14].height = 34
    ws.row_dimensions[15].height = 34
    ws.row_dimensions[16].height = 34
    ws.row_dimensions[17].height = 34

    register_df = __import__("pandas").DataFrame(data["register"])
    write_df("Source Register", register_df, ["id", "file", "url", "retrieved_utc", "analysis_collected_utc", "sha256", "bytes", "units", "period", "status", "vintage"], {"id": 8, "file": 32, "url": 54, "retrieved_utc": 28, "analysis_collected_utc": 28, "sha256": 68, "bytes": 12, "units": 28, "period": 42, "status": 26, "vintage": 44})
    ws = wb["Source Register"]
    for row in range(2, ws.max_row + 1):
        url_cell = ws.cell(row=row, column=3)
        url_cell.hyperlink = url_cell.value
        url_cell.style = "Hyperlink"

    quality_rows = []
    q = data["metrics"]["quality"]
    quality_rows.extend([
        ("Status", q["status"], "The table is complete; anomalies are disclosed below."),
        ("Source room", q["source_room"], "Frozen local source room, not live client access."),
        ("Client/public status", q["client_data_status"], "See Source Register for URL, hash and vintage."),
        ("Raw order rows", q["order_audit"]["raw_extract_rows"], "Two extract pages."),
        ("Exact order duplicates removed", q["order_audit"]["exact_duplicate_order_rows_removed"], "Identical repeated rows counted once."),
        ("Order correction rows", q["order_audit"]["correction_rows"], "Whole-row replacements; highest revision wins."),
        ("Canonical orders", q["order_audit"]["canonical_order_ids"], "Unique order IDs after revision selection."),
        ("Eligible 2025 shipped orders", q["order_audit"]["eligibility_counts"].get("eligible_2025_shipped", 0), "Included in monthly/country results."),
        ("Excluded cancelled orders", q["order_audit"]["eligibility_counts"].get("excluded_status", 0), "Status is not shipped."),
        ("Excluded test orders", q["order_audit"]["eligibility_counts"].get("excluded_test", 0), "is_test=true."),
        ("Excluded outside-2025 orders", q["order_audit"]["eligibility_counts"].get("excluded_outside_2025", 0), "Shipped in January 2026; not applied to 2025 base."),
        ("Zero-price shipments retained", q["metric_checks"]["zero_price_orders_included"], "Valid shipments; not filtered as zero revenue."),
        ("Raw return rows", q["return_audit"]["raw_return_rows"], "Returns extract."),
        ("Exact return duplicates removed", q["return_audit"]["exact_duplicate_return_rows_removed"], "Identical repeated rows counted once."),
        ("Lower-revision returns removed", q["return_audit"]["lower_revision_return_rows_removed"], "Highest revision wins."),
        ("Included returns", q["return_audit"]["inclusion_counts"].get("included", 0), "Linked to eligible order and received by cutoff."),
        ("Orphan returns quarantined", q["return_audit"]["inclusion_counts"].get("quarantined_orphan", 0), "No guess-join; IDs listed in metrics.json."),
        ("Post-cutoff returns excluded", q["return_audit"]["inclusion_counts"].get("excluded_after_cutoff", 0), "Received after 2026-01-31."),
    ])
    qdf = __import__("pandas").DataFrame(quality_rows, columns=["check", "value", "handling"])
    write_df("Quality", qdf, ["check", "value", "handling"], {"check": 34, "value": 30, "handling": 80})
    qws = wb["Quality"]
    for row in range(2, qws.max_row + 1):
        qws.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical="top")
    qws.conditional_formatting.add(f"B2:B{qws.max_row}", ColorScaleRule(start_type="min", start_color="EAF4EE", mid_type="percentile", mid_value=50, mid_color="FFF1D6", end_type="max", end_color="F9D6D5"))

    orders_cols = ["order_id", "revision", "source_kind", "country", "ordered_at", "shipped_at", "status", "is_test", "sku", "quantity", "unit_price_local", "discount_local", "currency", "fulfillment_eur", "eligibility", "month"]
    write_df("Orders Audit", data["orders"], orders_cols, {"order_id": 18, "source_kind": 14, "country": 10, "ordered_at": 14, "shipped_at": 14, "status": 12, "is_test": 10, "sku": 10, "currency": 10, "eligibility": 28, "month": 12})
    returns_cols = ["return_id", "revision", "order_id", "received_at", "quantity", "restocked_quantity", "refund_local", "linked_order_eligibility", "return_inclusion"]
    write_df("Returns Audit", data["returns"], returns_cols, {"return_id": 18, "order_id": 18, "received_at": 14, "linked_order_eligibility": 28, "return_inclusion": 32})
    order_metric_cols = ["order_id", "country", "month", "shipped_at", "sku", "currency", "fx_local_per_eur", "quantity", "unit_price_local", "discount_local", "gross_local", "refund_local", "return_records", "returned_units", "restocked_units", "unit_cost_eur", "gross_sales_eur", "refunds_eur", "gross_cogs_eur", "recovered_cogs_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"]
    write_df("Order Metrics", data["order_metrics"], order_metric_cols, {"order_id": 18, "country": 10, "month": 12, "shipped_at": 14, "sku": 10, "currency": 10})
    monthly_cols = ["country", "month", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"]
    write_df("Monthly", data["monthly"], monthly_cols, {"country": 10, "month": 12})
    country_cols = ["country", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"]
    write_df("Countries", data["countries"], country_cols, {"country": 10})
    write_df("FX Monthly", data["fx"], ["currency", "month", "local_per_eur", "observations"], {"currency": 12, "month": 12, "observations": 14})
    market_cols = ["country", "year", "population", "gdp_per_capita_usd", "unit_population", "unit_gdp", "source_lastupdated", "obs_status"]
    write_df("Market Context", data["market"], market_cols, {"country": 10, "unit_population": 16, "unit_gdp": 28, "source_lastupdated": 18, "obs_status": 12})
    scenario_cols = ["country", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years", "annual_fixed_eur", "saving_eur_per_unit"]
    write_df("Hub Scenarios", data["individual_scenarios"], scenario_cols, {"country": 12, "scenario": 12})
    pair_cols = ["country", "countries", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years", "feasible", "feasibility_note"]
    write_df("Pair Scenarios", data["pair_scenarios"], pair_cols, {"country": 14, "countries": 16, "scenario": 12, "feasibility_note": 28})
    rank_cols = ["option", "countries", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years", "feasible", "stress_incremental_contribution_eur", "break_even_uplift"]
    write_df("Option Rankings", data["rankings"], rank_cols, {"option": 14, "countries": 18, "scenario": 12})
    rws = wb["Option Rankings"]
    rws.conditional_formatting.add(f"D2:D{rws.max_row}", ColorScaleRule(start_type="min", start_color="F9D6D5", mid_type="percentile", mid_value=50, mid_color="FFF1D6", end_type="max", end_color="EAF4EE"))

    ws = wb.create_sheet("Charts")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Decision charts"
    ws["A1"].font = title_font
    ws["A3"] = "Charts are saved as PNG assets under analysis_outputs/charts and embedded here for board use."
    ws["A3"].font = note_font
    ws.add_image(XLImage(str(charts["baseline"])), "A5")
    ws.add_image(XLImage(str(charts["options"])), "A27")
    ws.add_image(XLImage(str(charts["monthly"])), "A62")
    ws.add_image(XLImage(str(charts["fx"])), "A95")
    ws.column_dimensions["A"].width = 18

    path = DELIVERABLES / "meridian_parts_analysis.xlsx"
    wb.save(path)
    return path


def market_summary(data):
    market = data["market"].copy()
    rows = []
    for c in COUNTRIES:
        part = market[market.country == c].set_index("year")
        p22, p24 = part.loc[2022, "population"], part.loc[2024, "population"]
        g22, g24 = part.loc[2022, "gdp_per_capita_usd"], part.loc[2024, "gdp_per_capita_usd"]
        rows.append({"country": c, "population_2022": int(p22), "population_2024": int(p24), "population_change_pct": (p24 / p22 - 1) * 100, "gdp_2022": float(g22), "gdp_2024": float(g24), "gdp_change_pct": (g24 / g22 - 1) * 100})
    return rows


def report_table(data, rows, headers, widths, font_size=7.5, header_bg="#0F223A"):
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Table, TableStyle, Paragraph

    style = ParagraphStyle("table", fontName="Helvetica", fontSize=font_size, leading=font_size + 2, textColor=colors.HexColor("#27364A"))
    head = ParagraphStyle("tablehead", fontName="Helvetica-Bold", fontSize=font_size, leading=font_size + 2, textColor=colors.white)
    pdata = [[Paragraph(str(h), head) for h in headers]]
    for row in rows:
        pdata.append([Paragraph(str(v), style) for v in row])
    t = Table(pdata, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D1DAE4")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def generate_report(data, charts: dict[str, Path]) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Image as RLImage, KeepTogether

    path = DELIVERABLES / "meridian_parts_executive_report.pdf"
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=28, leading=32, textColor=colors.HexColor("#0F223A"), alignment=TA_LEFT, spaceAfter=12))
    styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=14, leading=19, textColor=colors.HexColor("#546475"), spaceAfter=16))
    styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=colors.HexColor("#0F223A"), spaceBefore=5, spaceAfter=8))
    styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=colors.HexColor("#1E68AC"), spaceBefore=8, spaceAfter=5))
    styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=colors.HexColor("#27364A"), spaceAfter=6))
    styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.4, leading=9.5, textColor=colors.HexColor("#546475"), spaceAfter=4))
    styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=11, leading=15, textColor=colors.HexColor("#0F223A"), backColor=colors.HexColor("#EAF4EE"), borderColor=colors.HexColor("#2A895B"), borderWidth=1, borderPadding=8, spaceBefore=6, spaceAfter=8))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#D1DAE4"))
        canvas.line(18 * mm, 13 * mm, 192 * mm, 13 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#546475"))
        canvas.drawString(18 * mm, 8 * mm, "Meridian Parts | Synthetic client analysis | 2025 shipped sales; returns through 2026-01-31")
        canvas.drawRightString(192 * mm, 8 * mm, f"{doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(str(path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm, bottomMargin=19 * mm, title="Meridian Parts European service-hub expansion")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="all", frames=frame, onPage=footer)])
    S = []
    rec = data["metrics"]["recommendation"]
    ranks = data["rankings"]
    selected = ranks.iloc[0]
    alternative = ranks.iloc[1]
    selected_scenarios = data["pair_scenarios"][data["pair_scenarios"].country == selected.option].set_index("scenario")
    market_rows = market_summary(data)

    S += [Spacer(1, 28 * mm), Paragraph("Meridian Parts", styles["CoverTitle"]), Paragraph("European service-hub expansion", styles["CoverSub"]), Spacer(1, 7 * mm)]
    S.append(Paragraph(f"<b>Board recommendation:</b> fund {', '.join(rec['countries'])} through a gated 90-day validation, reserving {fmt_eur(rec['capex_eur'])} of year-zero capex and {rec['fte']} FTE. The selected pair produces {fmt_eur(selected.incremental_contribution_eur)} of base-case annual incremental contribution, with a {selected.payback_years:.2f}-year simple payback.", styles["Callout"]))
    S += [Paragraph("Decision date: 27 September 2026", styles["Smallx"]), Paragraph("Scope: 2025 shipped sales and returns received by 31 January 2026; six European markets. Inputs are synthetic client exports and assumptions, with archived official World Bank and ECB snapshots identified in the source register.", styles["Bodyx"]), Spacer(1, 10 * mm), Paragraph("Prepared for the Meridian Parts board", styles["H2x"]), PageBreak()]

    S += [Paragraph("1. Executive decision", styles["H1x"]), Paragraph(f"Approve a <b>gated two-hub plan in Czechia (CZE) and Spain (ESP)</b>, but release capex only after the 90-day validation gates. The pair is the highest-ranked feasible alternative on the stated base-case planning metric: {fmt_eur(selected.incremental_contribution_eur)} annual incremental contribution after recurring fixed cost, {fmt_eur(selected.capex_eur)} capex, {int(selected.fte)} FTE and {selected.payback_years:.2f} years simple payback.", styles["Bodyx"]), Paragraph(f"The recommendation is robust to the defined joint stress in sign but not in magnitude: stress contribution is {fmt_eur(selected.stress_incremental_contribution_eur)} and payback extends to {selected_scenarios.loc['stress','payback_years']:.2f} years. Low/base/high volume cases produce {fmt_eur(selected_scenarios.loc['low','incremental_contribution_eur'])}, {fmt_eur(selected_scenarios.loc['base','incremental_contribution_eur'])} and {fmt_eur(selected_scenarios.loc['high','incremental_contribution_eur'])}. The pair's calculated volume-uplift break-even is {rec['break_even_volume_uplift']:.2%}; the board should treat that as a gate, not as evidence that demand will materialize.", styles["Bodyx"])]
    exec_rows = [
        ["Selected pair", "Capex", "FTE", "Low", "Base", "High", "Stress", "Base payback"],
        [selected.option, fmt_eur(selected.capex_eur), int(selected.fte), fmt_eur(selected_scenarios.loc["low", "incremental_contribution_eur"]), fmt_eur(selected_scenarios.loc["base", "incremental_contribution_eur"]), fmt_eur(selected_scenarios.loc["high", "incremental_contribution_eur"]), fmt_eur(selected_scenarios.loc["stress", "incremental_contribution_eur"]), f"{selected.payback_years:.2f} years"],
    ]
    S.append(report_table(data, exec_rows[1:], exec_rows[0], [25 * mm, 19 * mm, 12 * mm, 20 * mm, 20 * mm, 20 * mm, 20 * mm, 22 * mm], 7.0))
    S += [Spacer(1, 4 * mm), Paragraph(f"<b>Trade-off.</b> The strongest base-case alternative is {alternative.option}: {fmt_eur(alternative.incremental_contribution_eur)} base contribution, {fmt_eur(alternative.capex_eur)} capex, {int(alternative.fte)} FTE, {alternative.payback_years:.2f} years payback and {fmt_eur(alternative.stress_incremental_contribution_eur)} stress contribution. NLD+ESP is the more conservative stress-oriented alternative ({fmt_eur(float(ranks[ranks.option == 'NLD+ESP'].iloc[0].stress_incremental_contribution_eur))} stress contribution) but gives up {fmt_eur(selected.incremental_contribution_eur - float(ranks[ranks.option == 'NLD+ESP'].iloc[0].incremental_contribution_eur))} of base-case annual contribution. This is a preference trade-off, not a claim that one scenario is true.", styles["Bodyx"]), Paragraph("<b>Board ask:</b> authorize discovery, lane-cost validation, and hiring/partner selection work inside the 90-day plan; make the capex release contingent on measured service economics and the volume gate.", styles["Callout"]), PageBreak()]

    S += [Paragraph("2. Evidence, scope and accounting", styles["H1x"]), Paragraph("The analysis uses the frozen source room collected from the TOOLING.md URL. Synthetic client files define the transaction grain, revisions, costs, hub options and scenario policy [S01–S08]. Public context is taken from archived World Bank responses for population and GDP per capita [S09–S10] and an archived ECB historical reference-rate file [S11–S12]. The source register preserves the original URL, retrieval vintage, local hash, units, period and public/synthetic status.", styles["Bodyx"]), Paragraph("The 2025 base is defined by <b>shipped_at</b> in calendar 2025. Returns are included when the selected return revision is linked to an eligible order and received by 31 January 2026 inclusive; refund and returned-unit amounts are allocated to the original sale month. For PLN and CZK, gross sale and refund conversion uses the sale month's arithmetic mean of available ECB business-day quotes in local currency units per EUR; EUR uses 1.0. Monetary components are rounded half-up per order to cents before aggregation [S01].", styles["Bodyx"]), Paragraph("Booked revenue is the order-ledger sale measure: gross sales before refunds, or net sales after refund credits. Cash is not directly observed in the exports; settlement timing, payment fees, taxes, chargebacks and cash collection are therefore not estimated. Contribution is the analytical operating measure: net sales less net COGS and fulfillment. It excludes hub capex and recurring hub fixed cost, which are modeled separately in scenario economics.", styles["Bodyx"]), Paragraph("<b>Evidence state:</b> transaction results are computed from saved synthetic inputs; World Bank and ECB values are archived official observations; hub demand uplift, savings per unit, recurring cost and capex are synthetic assumptions. No interviews or live customer account access were used.", styles["Callout"]), PageBreak()]

    S += [Paragraph("3. 2025 operating diagnosis", styles["H1x"]), Paragraph("The baseline is concentrated in the markets that also rank well in the hub arithmetic. Spain has the highest contribution and margin; Czechia is second on contribution and has the lowest capex/FTE intensity among the top-volume options. This supports prioritizing them for validation, but the observed 2025 ledger is not causal evidence that a local hub created demand.", styles["Bodyx"]), RLImage(str(charts["baseline"]), width=170 * mm, height=92 * mm), Spacer(1, 3 * mm)]
    c = data["countries"]
    country_rows = []
    for _, r in c.iterrows():
        country_rows.append([r.country, f"{int(r.shipped_orders):,}", f"{int(r.shipped_units):,}", fmt_eur(r.gross_sales_eur), fmt_eur(r.refunds_eur), fmt_eur(r.net_sales_eur), fmt_eur(r.net_cogs_eur), fmt_eur(r.fulfillment_eur), fmt_eur(r.contribution_eur), fmt_pct(r.margin), f"{int(r.returned_units):,}"])
    S.append(report_table(data, country_rows, ["Country", "Orders", "Units", "Gross", "Refunds", "Net sales", "Net COGS", "Fulfillment", "Contribution", "Margin", "Returned units"], [11 * mm, 11 * mm, 12 * mm, 17 * mm, 15 * mm, 17 * mm, 17 * mm, 17 * mm, 20 * mm, 12 * mm, 15 * mm], 6.0))
    S += [Spacer(1, 3 * mm), Paragraph("The 2025 country totals reconcile to 72 monthly records (12 months × 6 countries); all six reconciliation checks pass. Contribution margin ranges from 41.9% in Germany to 49.6% in Spain on this accounting definition. Returns are physical units, not return-order counts; restocked units recover only the original unit cost [S01].", styles["Smallx"]), PageBreak()]

    S += [Paragraph("4. Data quality and reconciliation", styles["H1x"]), Paragraph("The source room contains deliberate duplicates, corrections and edge cases. The controls below are part of the analysis rather than post-hoc cleanup. Counts are computed from the saved files and can be reproduced from analysis_outputs/orders_audit.csv and returns_audit.csv.", styles["Bodyx"])]
    qrows = [
        ["Issue", "Count", "Handling"],
        ["Raw order rows", "1,310", "Two extract pages combined."],
        ["Identical order rows", "13", "Removed once; not counted as orders."],
        ["Order corrections", "18", "Whole-row replacement; revision 2 selected."],
        ["Canonical orders", "1,297", "Highest revision per order_id."],
        ["Cancelled rows", "24", "Excluded; status not shipped."],
        ["Test rows", "18", "Excluded; is_test=true."],
        ["January 2026 shipped rows", "1", "Excluded from 2025 base."],
        ["Zero-price valid shipments", "12", "Retained; quantity and costs remain in the base."],
        ["Raw return rows", "264", "Return extract combined."],
        ["Identical return rows", "20", "Removed once."],
        ["Lower-revision return rows", "1", "Highest return revision selected."],
        ["Included returns", "241", "Linked and received by cutoff."],
        ["Orphan / post-cutoff returns", "1 / 1", "Orphan quarantined; late return excluded."],
    ]
    S.append(report_table(data, qrows[1:], qrows[0], [37 * mm, 15 * mm, 115 * mm], 7.4))
    S += [Spacer(1, 4 * mm), Paragraph("No missing 2025 PLN/CZK rate means or missing effective unit costs were detected for eligible orders. Monthly totals use distinct canonical order IDs and are the sum of order-level rounded components. The model does not silently join the orphan return or treat a raw row as an order.", styles["Bodyx"]), RLImage(str(charts["monthly"]), width=170 * mm, height=93 * mm), PageBreak()]

    S += [Paragraph("5. Market context and FX", styles["H1x"]), Paragraph("World Bank context shows population change and nominal GDP per capita trends across the six markets. It provides economic context for execution and service design, not direct proof of product demand [S09–S10].", styles["Bodyx"])]
    mrows = []
    for r in market_rows:
        mrows.append([r["country"], f"{r['population_2022']:,}", f"{r['population_2024']:,}", f"{r['population_change_pct']:+.1f}%", f"${r['gdp_2022']:,.0f}", f"${r['gdp_2024']:,.0f}", f"{r['gdp_change_pct']:+.1f}%"])
    S.append(report_table(data, mrows, ["Country", "Pop. 2022", "Pop. 2024", "Change", "GDP pc 2022", "GDP pc 2024", "Change"], [20 * mm, 27 * mm, 27 * mm, 20 * mm, 28 * mm, 28 * mm, 20 * mm], 7.0))
    S += [Spacer(1, 3 * mm), Paragraph("Population increased in Germany, France, Netherlands, Czechia and Spain over 2022–2024 in the archive; Poland declined. Nominal current-US-dollar GDP per capita increased in all six in the archived values, but exchange rates and price effects mean it is not a real-income or demand measure.", styles["Smallx"]), RLImage(str(charts["fx"]), width=170 * mm, height=87 * mm), Paragraph("The workbook and metrics.json preserve all twelve monthly PLN and CZK means. The FX series is an official reference-rate archive, not a record of Meridian's actual transaction conversion or a forecast.", styles["Smallx"]), PageBreak()]

    S += [Paragraph("6. Options and trade-offs", styles["H1x"]), Paragraph("Scenario policy [S02] defines annual incremental contribution as C×u + U×(1+u)×s − F for low/base/high uplifts u={10%, 25%, 40%}; capex K is year-zero and payback is K divided by positive annual incremental contribution. Stress uses the base uplift, a 3% of gross-sales refund shock and a 10% of net-sales FX shock in PLN/CZK markets, with no additional cost recovery. Pairs add country figures without synergy.", styles["Bodyx"]), RLImage(str(charts["options"]), width=170 * mm, height=116 * mm), PageBreak()]

    S += [Paragraph("Feasible-pair comparison", styles["H2x"])]
    pair_base = data["pair_scenarios"][data["pair_scenarios"].scenario == "base"].copy()
    pair_base = pair_base[pair_base.feasible].sort_values("incremental_contribution_eur", ascending=False)
    prow = []
    for _, r in pair_base.iterrows():
        stress = data["pair_scenarios"][(data["pair_scenarios"].country == r.country) & (data["pair_scenarios"].scenario == "stress")].iloc[0]
        prow.append([r.country, fmt_eur(r.incremental_contribution_eur), fmt_eur(r.capex_eur), int(r.fte), f"{r.payback_years:.2f}", fmt_eur(stress.incremental_contribution_eur)])
    S.append(report_table(data, prow, ["Pair", "Base annual", "Capex", "FTE", "Payback", "Stress annual"], [30 * mm, 32 * mm, 28 * mm, 18 * mm, 25 * mm, 32 * mm], 7.2))
    S += [Spacer(1, 4 * mm), Paragraph("The selected CZE+ESP pair is the base-case leader. It gives up some stress resilience versus NLD+ESP, but it has materially higher base contribution and a lower capex requirement. POL+ESP is the strongest base alternative and is close in stress performance; it is the most relevant like-for-like challenge to the recommendation.", styles["Bodyx"]), Paragraph("Switching conditions: reopen the funding decision if the measured uplift is below 2.74% on the selected pair, realized savings per unit do not cover recurring fixed cost, service-level improvement cannot be verified, or the defined stress becomes negative. These conditions are decision gates, not claims about probabilities.", styles["Callout"]), PageBreak()]

    S += [Paragraph("7. Staged 90-day implementation", styles["H1x"]), Paragraph("Owners below are operating roles, not named people. The sequence protects the board from committing year-zero capex before the synthetic assumptions are checked against live operational evidence.", styles["Bodyx"])]
    plan_rows = [
        ["Timing", "Owner", "Work / dependency", "Decision gate / output"],
        ["Days 0–15", "COO + CFO", "Authorize discovery envelope; confirm CZE/ESP lane map, current central-hub service baseline, candidate partner model and capex approval path. Dependency: Finance baseline and Ops data extracts.", "Gate 0: approve validation scope only; no full capex release. Output: signed KPI definitions and data owners."],
        ["Days 16–45", "Ops + Procurement", "Validate lane-level freight, handling, labor/partner quotes, local service promise, return routing and staffing plan. Dependency: carrier/partner bids and HR/legal review.", "Gate 1: proceed only if validated annual savings and capacity support the scenario, and no hard capex/FTE breach. Output: business case v2."],
        ["Days 46–75", "Country launch leads", "Run controlled operating pilot in the two selected markets with weekly dashboard; reconcile shipped volume, delivery promise, return rate, savings per unit and fulfillment cost against central-hub baseline.", "Gate 2: continue only if observed uplift is at least 2.74% run-rate or board explicitly accepts a lower hurdle with evidence. Output: pilot readout."],
        ["Days 76–90", "Board + COO", "Review pilot, finalize contracts, staffing and inventory/returns controls; release capex in tranches if evidence supports the decision.", "Gate 3: launch, defer, or switch to POL+ESP/NLD+ESP. Output: signed go/no-go and 13-week operating plan."],
    ]
    S.append(report_table(data, plan_rows[1:], plan_rows[0], [17 * mm, 25 * mm, 74 * mm, 54 * mm], 6.8))
    S += [Spacer(1, 4 * mm), Paragraph("Proposed KPI plan", styles["H2x"])]
    kpi_rows = [
        ["KPI", "Frequency / owner", "Target or gate"],
        ["Incremental shipped volume uplift", "Weekly / Finance + Ops", "≥2.74% run-rate for selected pair before full release; compare with matched central-hub baseline."],
        ["Savings per shipped unit", "Weekly / Procurement", "At or above the option assumption: CZE €2.10; ESP €3.00; report realized and contracted separately."],
        ["Contribution per order", "Weekly / Finance", "Non-negative after refunds, net COGS and fulfillment; reconcile to monthly ledger definition."],
        ["Return/refund rate", "Weekly / Quality", "No deterioration versus 2025 baseline without a documented service or mix explanation."],
        ["Promised-day hit rate and cycle time", "Weekly / Country leads", "Baseline in days 0–15; board sets service threshold after lane validation."],
        ["Capex and FTE burn", "Weekly / CFO + HR", "≤€225k and ≤5 FTE for selected pair; stage release and hiring commitments."],
    ]
    S.append(report_table(data, kpi_rows[1:], kpi_rows[0], [42 * mm, 33 * mm, 93 * mm], 7.0))
    S += [PageBreak(), Paragraph("8. Risks, limitations and evidence gaps", styles["H1x"]), Paragraph("<b>Demand risk:</b> 2025 shipped sales are observed history, not a causal forecast of volume uplift from local hubs. Mitigation is a staged pilot and an explicit volume break-even gate.", styles["Bodyx"]), Paragraph("<b>Economics risk:</b> savings per unit, fixed cost and capex are synthetic policy inputs; local quotes and freight-lane costs are not in the source room. Mitigation is Procurement validation before Gate 1 and reporting contracted versus realized savings.", styles["Bodyx"]), Paragraph("<b>FX/returns risk:</b> the ECB rate is a reference-rate mean and stress is deliberately conservative but not a probability-weighted forecast. Returns after the cutoff and the orphan return are excluded from the base. Mitigation is weekly return/refund and FX monitoring.", styles["Bodyx"]), Paragraph("<b>Execution risk:</b> the analysis does not include local regulatory, tax, labor, lease, inventory-transfer or customer service design evidence. These are dependencies for the 90-day plan, not hidden assumptions in the baseline.", styles["Bodyx"]), Paragraph("<b>Decision strength:</b> the recommendation is supported by reconciled transaction arithmetic and transparent scenario trade-offs. It is not statistically proven, causal or certain. The smallest useful next evidence is the lane-level cost and service validation that can confirm or reject the selected pair's savings and uplift assumptions.", styles["Callout"]), Paragraph("Source register and raw evidence", styles["H2x"])]
    source_rows = []
    for s in data["register"]:
        source_rows.append([s["id"], s["file"].replace("evidence/raw/", ""), s["status"], s["units"], s["period"], s["url"][:70]])
    S.append(report_table(data, source_rows, ["ID", "File", "Status", "Units", "Period", "Original URL (truncated)"], [10 * mm, 25 * mm, 25 * mm, 25 * mm, 34 * mm, 42 * mm], 5.9))
    S += [Spacer(1, 4 * mm), Paragraph("Full URLs, retrieval times, hashes and vintages are in deliverables/source_register.json and the workbook Source Register sheet. Reproduction instructions are in REPRODUCE.md.", styles["Smallx"])]
    doc.build(S)
    return path


def pptx_text(slide, text, x, y, w, h, size=18, color=(39, 54, 74), bold=False, align=None):
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.name = "Aptos"
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = RGBColor(*color)
    if align is not None:
        p.alignment = align
    return box


def add_slide_title(slide, title, subtitle=None):
    pptx_text(slide, title, 0.55, 0.28, 12.2, 0.55, size=25, color=(15, 34, 58), bold=True)
    if subtitle:
        pptx_text(slide, subtitle, 0.58, 0.88, 12.0, 0.32, size=10.5, color=(84, 100, 117))
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.dml.color import RGBColor
    from pptx.util import Inches
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(1.2), Inches(12.2), Inches(0.02))
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(209, 218, 228); shape.line.fill.background()


def add_footer(slide, page):
    pptx_text(slide, "Meridian Parts | Synthetic client inputs + archived official snapshots | Not a causal forecast", 0.55, 7.12, 11.6, 0.2, size=7.5, color=(84, 100, 117))
    pptx_text(slide, str(page), 12.35, 7.12, 0.45, 0.2, size=7.5, color=(84, 100, 117), align=2)


def make_presentation(data, charts: dict[str, Path]) -> Path:
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import PP_ALIGN
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]
    rec = data["metrics"]["recommendation"]
    selected = data["rankings"].iloc[0]
    selected_scenarios = data["pair_scenarios"][data["pair_scenarios"].country == selected.option].set_index("scenario")

    def new_slide(title, subtitle=None):
        slide = prs.slides.add_slide(blank)
        add_slide_title(slide, title, subtitle)
        add_footer(slide, len(prs.slides))
        return slide

    # 1 cover
    slide = prs.slides.add_slide(blank)
    bg = slide.background.fill; bg.solid(); bg.fore_color.rgb = RGBColor(15, 34, 58)
    pptx_text(slide, "MERIDIAN PARTS", 0.72, 1.25, 7.3, 0.4, size=16, color=(122, 206, 193), bold=True)
    pptx_text(slide, "European service-hub expansion", 0.72, 1.9, 10.8, 0.85, size=35, color=(255, 255, 255), bold=True)
    pptx_text(slide, f"Board recommendation: gated funding for {', '.join(rec['countries'])}", 0.75, 3.1, 9.7, 0.5, size=22, color=(255, 255, 255), bold=True)
    pptx_text(slide, f"{fmt_eur(rec['capex_eur'])} capex | {rec['fte']} FTE | {fmt_eur(selected.incremental_contribution_eur)} base annual incremental contribution | {selected.payback_years:.2f}-year payback", 0.75, 3.8, 11.5, 0.35, size=14, color=(218, 230, 239))
    pptx_text(slide, "2025 shipped sales and returns through 2026-01-31\nSynthetic client data; archived official World Bank and ECB context", 0.75, 5.75, 8.5, 0.6, size=13, color=(218, 230, 239))
    pptx_text(slide, "27 September 2026", 0.75, 6.8, 4, 0.25, size=10, color=(122, 206, 193))

    # 2 decision
    slide = new_slide("Decision in one view", "Approve discovery now; release capex only after the 90-day gates.")
    for x, title, value, sub, fill in [(0.75, "Selected pair", "CZE + ESP", "Highest base-case feasible pair", (0, 143, 136)), (3.55, "Annual base", fmt_eur(selected.incremental_contribution_eur), "After recurring fixed cost", (30, 104, 172)), (6.35, "Year-zero capex", fmt_eur(selected.capex_eur), "50% of EUR450k cap", (224, 122, 42)), (9.15, "People", f"{int(selected.fte)} FTE", "Within seven-FTE cap", (42, 137, 91))]:
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(1.65), Inches(2.35), Inches(1.35)); shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(*fill); shape.line.fill.background()
        pptx_text(slide, title, x+0.16, 1.83, 2.05, 0.22, size=10, color=(255,255,255), bold=True)
        pptx_text(slide, value, x+0.16, 2.15, 2.05, 0.35, size=19, color=(255,255,255), bold=True)
        pptx_text(slide, sub, x+0.16, 2.58, 2.05, 0.25, size=9, color=(240,248,250))
    pptx_text(slide, "Hard constraints", 0.78, 3.55, 2.0, 0.3, size=16, color=(15,34,58), bold=True)
    pptx_text(slide, "≤2 hubs  •  ≤€450,000 capex  •  ≤7 FTE  •  defer all remains feasible", 0.8, 3.95, 8.8, 0.3, size=16, color=(39,54,74))
    pptx_text(slide, "Flip before commitment if validated volume uplift is below 2.74%, realized savings do not cover fixed cost, service-level improvement is not verified, or the defined stress becomes negative.", 0.8, 4.65, 11.4, 0.7, size=17, color=(15,34,58), bold=True)

    # 3 baseline
    slide = new_slide("2025 baseline: where contribution is concentrated", "Country totals from reconciled canonical orders; source register S03–S08.")
    slide.shapes.add_picture(str(charts["baseline"]), Inches(0.75), Inches(1.45), width=Inches(7.0))
    pptx_text(slide, "Read-out", 8.1, 1.65, 2.0, 0.3, size=16, color=(15,34,58), bold=True)
    c = data["countries"].set_index("country").loc[COUNTRIES]
    lines = [f"{code}: {fmt_eur(c.loc[code,'contribution_eur'])} contribution, {fmt_pct(c.loc[code,'margin'])} margin, {int(c.loc[code,'shipped_units']):,} units" for code in COUNTRIES]
    pptx_text(slide, "\n".join(lines), 8.1, 2.1, 4.4, 2.5, size=14, color=(39,54,74))
    pptx_text(slide, "Spain leads contribution; Czechia is second and has a low capex/FTE option. These are observed ledger facts, not proof that hubs cause demand.", 8.1, 5.1, 4.3, 0.9, size=14, color=(15,34,58), bold=True)

    # 4 data integrity
    slide = new_slide("The base is controlled, not cosmetically cleaned", "Edge cases were reconciled and disclosed in the workbook Quality sheet and metrics.json.")
    quality_lines = [
        ("1,310", "raw order rows"), ("13", "identical order rows removed"), ("18", "whole-row corrections applied"), ("1,297", "canonical order IDs"), ("1,254", "eligible 2025 shipped orders"), ("241", "included returns"), ("1", "orphan return quarantined"), ("1", "post-cutoff return excluded"),
    ]
    for i, (value, label) in enumerate(quality_lines):
        x = 0.85 + (i % 4) * 3.05; y = 1.65 + (i // 4) * 1.55
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(2.55), Inches(1.05)); shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(235,241,247); shape.line.color.rgb = RGBColor(209,218,228)
        pptx_text(slide, value, x+0.15, y+0.15, 2.2, 0.35, size=21, color=(15,34,58), bold=True)
        pptx_text(slide, label, x+0.15, y+0.58, 2.2, 0.27, size=10, color=(84,100,117))
    pptx_text(slide, "Valid zero-price shipments remain in the base. January 2026 shipped rows do not enter 2025. Refunds use the original sale month's ECB mean; return units are physical units, not return orders.", 0.9, 5.2, 11.4, 0.8, size=16, color=(15,34,58), bold=True)

    # 5 market/FX
    slide = new_slide("Market context informs execution, not demand proof", "Archived World Bank series [S09–S10] and ECB rates [S11–S12].")
    slide.shapes.add_picture(str(charts["fx"]), Inches(0.75), Inches(1.45), width=Inches(6.4))
    msum = market_summary(data)
    top_lines = []
    for r in msum:
        top_lines.append(f"{r['country']}: population {r['population_change_pct']:+.1f}% (2022–24); GDP pc ${r['gdp_2024']:,.0f} in 2024")
    pptx_text(slide, "Archived context", 7.55, 1.62, 3.0, 0.3, size=16, color=(15,34,58), bold=True)
    pptx_text(slide, "\n".join(top_lines), 7.55, 2.05, 5.0, 3.0, size=12.5, color=(39,54,74))
    pptx_text(slide, "FX means are translation assumptions for comparable reporting; they are not Meridian transaction rates or a forecast.", 7.55, 5.55, 4.7, 0.62, size=13, color=(15,34,58), bold=True)

    # 6 options
    slide = new_slide("Options: CZE + ESP leads on the stated base metric", "All feasible single hubs and pairs shown; pairs add country figures without synergy.")
    slide.shapes.add_picture(str(charts["options"]), Inches(0.6), Inches(1.28), width=Inches(8.6))
    pptx_text(slide, "Base-case leaders", 9.35, 1.55, 3.2, 0.3, size=16, color=(15,34,58), bold=True)
    top = data["rankings"].head(5)
    lines = [f"{r.option}: {fmt_eur(r.incremental_contribution_eur)} base | {fmt_eur(r.stress_incremental_contribution_eur)} stress | {r.payback_years:.2f}y" for _, r in top.iterrows()]
    pptx_text(slide, "\n".join(lines), 9.35, 2.0, 3.35, 2.6, size=12.5, color=(39,54,74))
    pptx_text(slide, "CZE+ESP has a positive defined stress result but the smallest stress cushion among the top base options. This is why the recommendation is gated.", 9.35, 5.1, 3.2, 0.9, size=13, color=(15,34,58), bold=True)

    # 7 scenario economics
    slide = new_slide("Selected pair economics across scenarios", "Scenario values are annual incremental contribution after recurring cost; capex is year-zero.")
    scen_lines = []
    for s in ["low", "base", "high", "stress"]:
        r = selected_scenarios.loc[s]
        scen_lines.append([s.title(), fmt_eur(r.incremental_contribution_eur), f"{r.payback_years:.2f} years" if not math.isnan(r.payback_years) else "n/a"])
    # simple table
    x0, y0 = 0.95, 1.75
    headers = ["Scenario", "Annual contribution", "Payback"]
    colx = [x0, 3.6, 7.0]
    for x, h in zip(colx, headers):
        pptx_text(slide, h, x, y0, 2.8, 0.28, size=13, color=(15,34,58), bold=True)
    for i, row in enumerate(scen_lines):
        y = y0 + 0.55 + i * 0.7
        fill = (234,244,238) if row[0] in {"Base", "High"} else ((249,214,213) if row[0] == "Stress" else (255,241,214))
        shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.85), Inches(y-0.08), Inches(8.4), Inches(0.55)); shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(*fill); shape.line.fill.background()
        for x, val in zip(colx, row):
            pptx_text(slide, val, x, y, 2.8, 0.25, size=16 if x == x0+3.0 else 14, color=(15,34,58), bold=(x == x0+3.0))
    pptx_text(slide, f"Break-even volume uplift: {rec['break_even_volume_uplift']:.2%}\nSelected pair capex: {fmt_eur(selected.capex_eur)} | FTE: {int(selected.fte)}\nDefined stress includes 3% gross-sales refund shock plus 10% net-sales FX shock for PLN/CZK only.", 9.55, 1.95, 3.0, 2.1, size=14, color=(39,54,74))
    pptx_text(slide, "Do not read low/base/high as probabilities. They are planning cases from the synthetic policy.", 9.55, 5.05, 2.9, 0.8, size=14, color=(15,34,58), bold=True)

    # 8 alternatives
    slide = new_slide("The decision is a trade-off, not a single-score proof", "Base contribution, stress resilience, capex and staffing point in different directions.")
    alt = data["rankings"][data["rankings"].option.isin(["CZE+ESP", "POL+ESP", "NLD+ESP"])].copy()
    alt = alt.set_index("option").loc[["CZE+ESP", "POL+ESP", "NLD+ESP"]].reset_index()
    headers = ["Option", "Base", "Stress", "Capex", "FTE", "Payback"]
    colx = [0.8, 2.6, 4.35, 6.15, 8.0, 9.35]
    for x, h in zip(colx, headers): pptx_text(slide, h, x, 1.7, 1.35, 0.25, size=12, color=(15,34,58), bold=True)
    for i, (_, r) in enumerate(alt.iterrows()):
        y = 2.25 + i * 0.85
        fill = (234,244,238) if r.option == "CZE+ESP" else (244,247,250)
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.7), Inches(y-0.12), Inches(10.7), Inches(0.62)); shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(*fill); shape.line.color.rgb = RGBColor(209,218,228)
        vals = [r.option, fmt_eur(r.incremental_contribution_eur), fmt_eur(r.stress_incremental_contribution_eur), fmt_eur(r.capex_eur), str(int(r.fte)), f"{r.payback_years:.2f}y"]
        for x, v in zip(colx, vals): pptx_text(slide, v, x, y, 1.55, 0.25, size=14 if x == colx[0] else 13, color=(15,34,58), bold=(x == colx[0]))
    pptx_text(slide, "CZE+ESP wins the base metric; POL+ESP is the strongest base alternative; NLD+ESP is the stress-oriented alternative. The board's preference between upside and downside resilience should be made explicit at Gate 3.", 0.85, 5.35, 11.4, 0.8, size=16, color=(15,34,58), bold=True)

    # 9 plan
    slide = new_slide("90-day implementation: validate before committing", "Owners are operating roles; gates protect against assumption risk.")
    steps = [("0–15", "COO + CFO", "Define KPI baseline, lane map, data owners; authorize discovery only."), ("16–45", "Ops + Procurement", "Validate freight, labor/partner quotes, returns routing and service promise."), ("46–75", "Country leads", "Run controlled pilot; report uplift, service, savings, refunds and fulfillment."), ("76–90", "Board + COO", "Go / defer / switch; release capex in tranches if evidence supports." )]
    for i, (days, owner, desc) in enumerate(steps):
        y = 1.6 + i * 1.18
        circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.85), Inches(y), Inches(0.65), Inches(0.65)); circle.fill.solid(); circle.fill.fore_color.rgb = RGBColor(0,143,136); circle.line.fill.background()
        pptx_text(slide, days, 0.92, y+0.18, 0.52, 0.2, size=10, color=(255,255,255), bold=True, align=PP_ALIGN.CENTER)
        pptx_text(slide, owner, 1.8, y+0.02, 2.0, 0.22, size=13, color=(15,34,58), bold=True)
        pptx_text(slide, desc, 3.55, y+0.02, 8.6, 0.42, size=13, color=(39,54,74))
        if i < 3:
            line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.15), Inches(y+0.64), Inches(0.08), Inches(0.55)); line.fill.solid(); line.fill.fore_color.rgb = RGBColor(209,218,228); line.line.fill.background()
    pptx_text(slide, "Gate: measured uplift ≥2.74% for selected pair, realized savings cover fixed cost, and service quality does not deteriorate versus baseline.", 0.9, 6.18, 11.2, 0.42, size=15, color=(15,34,58), bold=True)

    # 10 KPIs/risk/ask
    slide = new_slide("Board ask and KPI control loop", "Use the dashboard to turn a planning recommendation into an evidence-based release decision.")
    pptx_text(slide, "Weekly KPI dashboard", 0.85, 1.55, 4, 0.3, size=16, color=(15,34,58), bold=True)
    kpis = ["Incremental shipped volume uplift", "Savings per shipped unit", "Contribution per order", "Return/refund rate", "Promised-day hit rate", "Capex and FTE burn"]
    for i, k in enumerate(kpis):
        y = 2.05 + i * 0.53
        pptx_text(slide, "•", 0.95, y, 0.2, 0.2, size=15, color=(0,143,136), bold=True)
        pptx_text(slide, k, 1.22, y, 4.3, 0.23, size=12.5, color=(39,54,74))
    pptx_text(slide, "Board decision", 6.45, 1.55, 3, 0.3, size=16, color=(15,34,58), bold=True)
    pptx_text(slide, "Authorize the 90-day validation envelope.\n\nAt Gate 3: release CZE + ESP capex, defer, or switch to POL + ESP / NLD + ESP based on measured economics and explicit risk preference.", 6.45, 2.05, 5.3, 1.65, size=17, color=(15,34,58), bold=True)
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.45), Inches(4.55), Inches(5.25), Inches(1.0)); shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor(234,244,238); shape.line.color.rgb = RGBColor(42,137,91)
    pptx_text(slide, "Recommendation: proceed, but make the capex release conditional.", 6.72, 4.85, 4.65, 0.35, size=16, color=(15,34,58), bold=True, align=PP_ALIGN.CENTER)

    path = DELIVERABLES / "meridian_parts_board_presentation.pptx"
    prs.save(path)
    return path


def main():
    data = build_metrics()
    charts = build_charts(data)
    workbook = write_workbook(data, charts)
    report = generate_report(data, charts)
    deck = make_presentation(data, charts)
    print(f"Workbook: {workbook}")
    print(f"Report: {report}")
    print(f"Presentation: {deck}")
    print(f"Metrics: {DELIVERABLES / 'metrics.json'}")


if __name__ == "__main__":
    main()
