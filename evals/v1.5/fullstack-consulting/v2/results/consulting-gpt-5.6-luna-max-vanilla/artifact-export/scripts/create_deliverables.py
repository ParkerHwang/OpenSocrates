#!/usr/bin/env python3
"""Create the Meridian Parts workbook, consulting report, and board deck."""

from __future__ import annotations

import csv
import json
import math
import os
import textwrap
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table as ExcelTable, TableStyleInfo

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "analysis" / "processed"
DELIVERABLES = ROOT / "deliverables"
EVIDENCE = ROOT / "evidence"
COUNTRY_NAMES = {
    "DEU": "Germany",
    "FRA": "France",
    "NLD": "Netherlands",
    "POL": "Poland",
    "CZE": "Czechia",
    "ESP": "Spain",
}
COUNTRIES = list(COUNTRY_NAMES)
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]

# Shared palette.
NAVY = "17324D"
TEAL = "008C95"
TEAL_DARK = "00686E"
ORANGE = "E27D42"
GOLD = "F0B44D"
RED = "BD4B4B"
GREEN = "2D8A64"
INK = "243746"
MUTED = "607382"
PALE = "F4F7F8"
PALE_TEAL = "E7F4F4"
PALE_ORANGE = "FFF1E8"
WHITE = "FFFFFF"


def load_csv(name: str) -> list[dict[str, str]]:
    with (PROCESSED / name).open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def load_json(name: str) -> dict:
    return json.loads((DELIVERABLES / name).read_text(encoding="utf-8"))


def num(value, default=0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value) -> str:
    if value is None or value == "":
        return "—"
    return f"€{num(value):,.0f}"


def money2(value) -> str:
    if value is None or value == "":
        return "—"
    return f"€{num(value):,.2f}"


def pct(value, digits=1) -> str:
    if value is None or value == "":
        return "—"
    return f"{num(value) * 100:.{digits}f}%"


def integer(value) -> str:
    if value is None or value == "":
        return "—"
    return f"{int(round(num(value))):,}"


def one_decimal(value) -> str:
    if value is None or value == "":
        return "—"
    return f"{num(value):,.1f}"


def esc(value) -> str:
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def read_all() -> dict:
    metrics = load_json("metrics.json")
    data = {
        "metrics": metrics,
        "monthly": load_csv("monthly.csv"),
        "countries": load_csv("countries.csv"),
        "fx": load_csv("fx_monthly.csv"),
        "market": load_csv("market_context.csv"),
        "scenarios": load_csv("hub_scenarios.csv"),
        "options": load_csv("hub_options.csv"),
        "orders": load_csv("order_level.csv"),
        "sources": json.loads((EVIDENCE / "source-register.json").read_text(encoding="utf-8"))["sources"],
    }
    return data


# --------------------------- Excel workbook ---------------------------


def excel_style(ws, title: str, subtitle: str | None = None) -> None:
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_margins.left = 0.25
    ws.page_margins.right = 0.25
    ws.page_margins.top = 0.45
    ws.page_margins.bottom = 0.45
    ws["A1"] = title
    ws["A1"].font = Font(name="Aptos Display", size=15, bold=True, color=NAVY)
    if subtitle:
        ws["A2"] = subtitle
        ws["A2"].font = Font(name="Aptos", size=9, italic=True, color=MUTED)


def add_excel_table(ws, start_row: int, start_col: int, headers: list[str], rows: list[list], name: str, widths: dict[int, float] | None = None):
    for c, header in enumerate(headers, start_col):
        cell = ws.cell(start_row, c, header)
        cell.font = Font(name="Aptos", size=9, bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for r_idx, row in enumerate(rows, start_row + 1):
        for c_idx, value in enumerate(row, start_col):
            cell = ws.cell(r_idx, c_idx, value)
            cell.font = Font(name="Aptos", size=9, color=INK)
            cell.alignment = Alignment(vertical="center")
            if r_idx % 2 == 0:
                cell.fill = PatternFill("solid", fgColor="F7F9FA")
    end_row = start_row + len(rows)
    end_col = start_col + len(headers) - 1
    ref = f"{get_column_letter(start_col)}{start_row}:{get_column_letter(end_col)}{end_row}"
    tab = ExcelTable(displayName=name, ref=ref)
    tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    ws.add_table(tab)
    ws.freeze_panes = ws.cell(start_row + 1, start_col)
    ws.auto_filter.ref = ref
    if widths:
        for c, width in widths.items():
            ws.column_dimensions[get_column_letter(c)].width = width
    ws.row_dimensions[start_row].height = 30
    return start_row + len(rows)


def style_sheet_borders(ws):
    thin = Side(style="thin", color="D9E2E6")
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell.border = Border(bottom=thin)


def build_workbook(data: dict) -> Path:
    metrics = data["metrics"]
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title = "Meridian Parts — European service-hub expansion"
    wb.properties.subject = "Reproducible 2025 sales, returns, FX, market context and hub scenarios"
    wb.properties.creator = "Meridian Parts operations analysis"

    # Readme / quality notes.
    ws = wb.create_sheet("Readme")
    excel_style(ws, "Meridian Parts | Service-hub expansion", "Analytical workbook • generated from saved source-room inputs • all monetary values EUR unless noted")
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 105
    notes = [
        ("Decision", f"Recommend {metrics['recommendation']['option']} (NLD + ESP) conditionally: €270,000 capex, six FTE, positive low/base/high/stress modeled contribution. See Hub Scenarios and Recommendation in metrics.json."),
        ("Scope", "2025 shipped orders and returns known through inclusive cutoff 2026-01-31. Only shipped, non-test orders with shipped_at in 2025 enter the base."),
        ("Sources", "Client exports, corrections, assumptions and archived official snapshots were collected from the frozen source room. Client data and board policy are synthetic; ECB and World Bank files are official archived public observations. No live customer account or interviews were used."),
        ("Accounting", "Select highest numeric revision per order_id/return_id across extracts; remove identical repeats; quarantine orphan/after-cutoff returns. Convert local sales/refunds with the original sale month's ECB mean business-day quote. Round monetary components per order half-up to cents, then sum."),
        ("Contribution", "Contribution = gross sales − refunds − net COGS − non-refundable fulfillment. Net COGS includes recovery only for restocked units at the original unit cost. This is not cash flow."),
        ("Scenario", "Low/base/high uplifts are 10%/25%/40%. Stress uses base volume plus 3% of gross sales refund shock and 10% of net sales depreciation/FX shock for PLN/CZK markets. Capex is year-zero and excluded from annual contribution; payback is undiscounted K / positive annual increment."),
        ("Reproduce", "Run the bundled Python against evidence/raw: python scripts/analyze.py && python scripts/create_deliverables.py && python scripts/verify_outputs.py. See REPRODUCE.md."),
        ("Limitations", "Synthetic order history and options are not measured demand. GDP per capita is current US$, not PPP or constant-price income. Scenario arithmetic omits tax, working capital, ramp timing, shared costs and synergy."),
    ]
    r = 4
    for label, value in notes:
        ws.cell(r, 1, label).font = Font(bold=True, color=TEAL_DARK)
        ws.cell(r, 2, value).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(r, 2).font = Font(size=10, color=INK)
        ws.row_dimensions[r].height = 46 if len(value) > 180 else 32
        r += 1
    ws["A14"] = "Workbook tabs"
    ws["A14"].font = Font(bold=True, color=NAVY, size=11)
    tabs = "Country Results; Monthly Results; FX Monthly; Market Context; Hub Scenarios; Scenario Summary; Order Detail; Sources; Quality"
    ws["B14"] = tabs
    ws["B14"].alignment = Alignment(wrap_text=True)
    ws["A16"] = "Generated UTC"
    ws["B16"] = metrics["metadata"]["generated_utc"]
    ws["A17"] = "Source register"
    ws["B17"] = "evidence/source-register.json and evidence/source-register.csv"
    ws.freeze_panes = "A4"

    # Country results.
    ws = wb.create_sheet("Country Results")
    excel_style(ws, "Country Results | 2025 base", "Monthly records reconcile to these totals; margin = contribution / net sales")
    rows = []
    for row in data["countries"]:
        rr = dict(row)
        rr["country_name"] = COUNTRY_NAMES[rr["country"]]
        rr["return_rate"] = num(rr["returned_units"]) / num(rr["shipped_units"]) if num(rr["shipped_units"]) else None
        rows.append(rr)
    headers = ["Country", "Country name", "Shipped orders", "Shipped units", "Gross sales EUR", "Refunds EUR", "Net sales EUR", "Net COGS EUR", "Fulfillment EUR", "Contribution EUR", "Returned units", "Margin", "Return rate"]
    values = [[r["country"], r["country_name"], int(num(r["shipped_orders"])), int(num(r["shipped_units"])), num(r["gross_sales_eur"]), num(r["refunds_eur"]), num(r["net_sales_eur"]), num(r["net_cogs_eur"]), num(r["fulfillment_eur"]), num(r["contribution_eur"]), int(num(r["returned_units"])), num(r["margin"]), r["return_rate"]] for r in rows]
    last = add_excel_table(ws, 4, 1, headers, values, "CountryResults", {1: 11, 2: 16, 3: 14, 4: 14, 5: 16, 6: 14, 7: 16, 8: 16, 9: 16, 10: 17, 11: 14, 12: 10, 13: 11})
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=5, max_col=10):
        for cell in row:
            cell.number_format = '€#,##0.00;[Red]-€#,##0.00'
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=12, max_col=13):
        for cell in row:
            cell.number_format = '0.0%'
    for col in [3, 4, 11]:
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=5, max_row=last).__next__():
            cell.number_format = '#,##0'
    ws.conditional_formatting.add(f"J5:J{last}", ColorScaleRule(start_type="min", start_color="FCE3E3", mid_type="percentile", mid_value=50, mid_color="FFF3D6", end_type="max", end_color="D7F0E5"))
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = "Net sales and contribution by country"
    chart.y_axis.title = "Country"
    chart.x_axis.title = "EUR"
    chart.height = 8
    chart.width = 15
    chart.add_data(Reference(ws, min_col=7, max_col=7, min_row=4, max_row=last), titles_from_data=True)
    chart.add_data(Reference(ws, min_col=10, max_col=10, min_row=4, max_row=last), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
    chart.legend.position = "b"
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = False
    ws.add_chart(chart, "O4")
    ws["O22"] = "Evidence: synthetic orders/returns/costs; see Sources and Quality."
    ws["O22"].font = Font(italic=True, color=MUTED, size=9)

    # Monthly results.
    ws = wb.create_sheet("Monthly Results")
    excel_style(ws, "Monthly Results | 2025", "All country-month combinations retained, including valid zero-price shipments")
    headers = ["Country", "Month", "Shipped orders", "Shipped units", "Gross sales EUR", "Refunds EUR", "Net sales EUR", "Net COGS EUR", "Fulfillment EUR", "Contribution EUR", "Returned units", "Margin"]
    values = [[r["country"], r["month"], int(num(r["shipped_orders"])), int(num(r["shipped_units"])), num(r["gross_sales_eur"]), num(r["refunds_eur"]), num(r["net_sales_eur"]), num(r["net_cogs_eur"]), num(r["fulfillment_eur"]), num(r["contribution_eur"]), int(num(r["returned_units"])), num(r["margin"]) if r["margin"] != "" else None] for r in data["monthly"]]
    last = add_excel_table(ws, 4, 1, headers, values, "MonthlyResults", {1: 11, 2: 12, 3: 14, 4: 14, 5: 16, 6: 14, 7: 16, 8: 16, 9: 16, 10: 17, 11: 14, 12: 10})
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=5, max_col=10):
        for cell in row:
            cell.number_format = '€#,##0.00;[Red]-€#,##0.00'
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=12, max_col=12):
        for cell in row:
            cell.number_format = '0.0%'
    chart = LineChart()
    chart.title = "Monthly contribution by country"
    chart.style = 13
    chart.y_axis.title = "EUR"
    chart.x_axis.title = "Month"
    chart.height = 8
    chart.width = 18
    # Build compact chart data to the right.
    ws["N4"] = "Month"
    for i, c in enumerate(COUNTRIES, 15):
        ws.cell(4, i, c)
    by_month_country = {(r["month"], r["country"]): num(r["contribution_eur"]) for r in data["monthly"]}
    for idx, month in enumerate(MONTHS, 5):
        ws.cell(idx, 14, month)
        for j, c in enumerate(COUNTRIES, 15):
            ws.cell(idx, j, by_month_country.get((month, c), 0.0))
    chart.add_data(Reference(ws, min_col=15, max_col=20, min_row=4, max_row=16), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=14, min_row=5, max_row=16))
    chart.legend.position = "b"
    ws.add_chart(chart, "N19")

    # FX monthly.
    ws = wb.create_sheet("FX Monthly")
    excel_style(ws, "ECB FX | 2025 monthly means", "Quote is local currency units per EUR; arithmetic mean of available official business-day observations")
    headers = ["Currency", "Month", "Local per EUR", "Business-day observations"]
    values = [[r["currency"], r["month"], num(r["local_per_eur"]), int(num(r["business_days"]))] for r in data["fx"]]
    last = add_excel_table(ws, 4, 1, headers, values, "FXMonthly", {1: 12, 2: 12, 3: 16, 4: 24})
    for cell in ws["C"][4:last]:
        cell.number_format = '0.000000'
    ws["F4"] = "Month"
    ws["G4"] = "PLN"
    ws["H4"] = "CZK"
    fx_map = {(r["currency"], r["month"]): num(r["local_per_eur"]) for r in data["fx"]}
    for i, month in enumerate(MONTHS, 5):
        ws.cell(i, 6, month)
        ws.cell(i, 7, fx_map.get(("PLN", month)))
        ws.cell(i, 8, fx_map.get(("CZK", month)))
        ws.cell(i, 7).number_format = '0.000000'
        ws.cell(i, 8).number_format = '0.000000'
    chart = LineChart()
    chart.title = "PLN and CZK local units per EUR"
    chart.y_axis.title = "Local per EUR"
    chart.x_axis.title = "Month"
    chart.height = 8
    chart.width = 15
    chart.add_data(Reference(ws, min_col=7, max_col=8, min_row=4, max_row=16), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=6, min_row=5, max_row=16))
    chart.legend.position = "b"
    ws.add_chart(chart, "F19")
    ws["F33"] = "EUR markets use EUR=1. Historical sale-month means drive both sales and refunds; no inversion or current FX is used."
    ws["F33"].font = Font(italic=True, color=MUTED, size=9)
    ws["F33"].alignment = Alignment(wrap_text=True)

    # Market context.
    ws = wb.create_sheet("Market Context")
    excel_style(ws, "Market Context | World Bank archive", "Population is persons; GDP per capita is current US$ per person; context only, not direct demand proof")
    headers = ["Country", "Year", "Population", "GDP per capita current US$"]
    values = [[r["country"], int(r["year"]), int(num(r["population"])) if r["population"] else None, num(r["gdp_per_capita_usd"]) if r["gdp_per_capita_usd"] else None] for r in data["market"]]
    last = add_excel_table(ws, 4, 1, headers, values, "MarketContext", {1: 12, 2: 10, 3: 18, 4: 28})
    for cell in ws["C"][4:last]:
        cell.number_format = '#,##0'
    for cell in ws["D"][4:last]:
        cell.number_format = '$#,##0.00'
    ws["F4"] = "Country"
    ws["G4"] = "Population change 2022→2024"
    ws["H4"] = "GDP pc 2024 current US$"
    ws["I4"] = "GDP pc change 2022→2024"
    m_map = {(r["country"], int(r["year"])): r for r in data["market"]}
    for i, c in enumerate(COUNTRIES, 5):
        p22 = num(m_map[(c, 2022)]["population"])
        p24 = num(m_map[(c, 2024)]["population"])
        g22 = num(m_map[(c, 2022)]["gdp_per_capita_usd"])
        g24 = num(m_map[(c, 2024)]["gdp_per_capita_usd"])
        ws.cell(i, 6, c)
        ws.cell(i, 7, p24 / p22 - 1 if p22 else None)
        ws.cell(i, 8, g24)
        ws.cell(i, 9, g24 / g22 - 1 if g22 else None)
        ws.cell(i, 7).number_format = '0.0%'
        ws.cell(i, 8).number_format = '$#,##0'
        ws.cell(i, 9).number_format = '0.0%'
    for cell in [ws["G4"], ws["H4"], ws["I4"]]:
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    ws.row_dimensions[4].height = 38
    ws["F14"] = "Archive vintage"
    ws["G14"] = metrics["quality"]["market"]["world_bank_population_lastupdated"]
    ws["F15"] = "Population source"
    ws["G15"] = metrics["quality"]["market"]["source_urls"]["population"]
    ws["F16"] = "GDP source"
    ws["G16"] = metrics["quality"]["market"]["source_urls"]["gdp_per_capita"]
    ws["G15"].alignment = Alignment(wrap_text=True)
    ws["G16"].alignment = Alignment(wrap_text=True)
    ws.column_dimensions["G"].width = 34
    ws.column_dimensions["H"].width = 24
    ws.column_dimensions["I"].width = 22

    # Hub scenario detail.
    ws = wb.create_sheet("Hub Scenarios")
    excel_style(ws, "Hub Scenarios | options and feasible pairs", "Annual incremental contribution is after recurring fixed cost; capex is year-zero and not subtracted from the annual measure")
    scenario_headers = list(data["scenarios"][0].keys())
    scenario_values = []
    for r in data["scenarios"]:
        row = []
        for h in scenario_headers:
            if h in {"country", "scenario", "option_type", "members"}:
                row.append(r[h])
            elif h == "fte":
                row.append(int(num(r[h])))
            elif h == "payback_years" or h == "volume_uplift":
                row.append(num(r[h]) if r[h] != "" else None)
            else:
                row.append(num(r[h]) if r[h] != "" else None)
        scenario_values.append(row)
    last = add_excel_table(ws, 4, 1, scenario_headers, scenario_values, "HubScenarios", {1: 14, 2: 12, 3: 20, 4: 14, 5: 9, 6: 15, 7: 12, 8: 14, 9: 18, 10: 15, 11: 16, 12: 16, 13: 17, 14: 18, 15: 16, 16: 15, 17: 17, 18: 18, 19: 22})
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=3, max_col=4):
        for cell in row:
            cell.number_format = '€#,##0.00;[Red]-€#,##0.00'
    for col in [6, 15, 16]:
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=5, max_row=last).__next__():
            cell.number_format = '0.00'
    for col in [9, 10, 11, 12, 13, 14, 17, 18, 19]:
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=5, max_row=last).__next__():
            cell.number_format = '€#,##0.00;[Red]-€#,##0.00'
    ws.conditional_formatting.add(f"C5:C{last}", ColorScaleRule(start_type="min", start_color="FCE3E3", mid_type="percentile", mid_value=50, mid_color="FFF3D6", end_type="max", end_color="D7F0E5"))
    ws["A80"] = "Feasible pairs are constrained by €450,000 capex and seven FTE. DEU+FRA, DEU+NLD, DEU+POL and DEU+ESP are excluded by caps."
    ws["A80"].font = Font(italic=True, color=MUTED, size=9)

    # Scenario summary / decision chart.
    ws = wb.create_sheet("Scenario Summary")
    excel_style(ws, "Scenario Summary | board comparison", "Risk-adjusted recommendation ranks feasible pairs by defined-stress contribution after requiring positive low/base/high/stress results")
    by_opt = defaultdict(dict)
    for r in data["scenarios"]:
        by_opt[r["country"]][r["scenario"]] = r
    order = sorted(by_opt, key=lambda o: num(by_opt[o].get("base", {}).get("incremental_contribution_eur")), reverse=True)
    summary_headers = ["Option", "Type", "Capex EUR", "FTE", "Low inc. EUR", "Base inc. EUR", "High inc. EUR", "Stress inc. EUR", "Base payback yrs", "Stress payback yrs", "Members"]
    summary_values = []
    for o in order:
        base = by_opt[o].get("base", {})
        stress = by_opt[o].get("stress", {})
        summary_values.append([o, base.get("option_type", ""), num(base.get("capex_eur")), int(num(base.get("fte"))), num(by_opt[o].get("low", {}).get("incremental_contribution_eur")), num(base.get("incremental_contribution_eur")), num(by_opt[o].get("high", {}).get("incremental_contribution_eur")), num(stress.get("incremental_contribution_eur")), num(base.get("payback_years")) if base.get("payback_years") else None, num(stress.get("payback_years")) if stress.get("payback_years") else None, base.get("members", "")])
    last = add_excel_table(ws, 4, 1, summary_headers, summary_values, "ScenarioSummary", {1: 14, 2: 12, 3: 14, 4: 8, 5: 15, 6: 15, 7: 15, 8: 16, 9: 16, 10: 17, 11: 14})
    for col in [3, 5, 6, 7, 8]:
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=5, max_row=last).__next__():
            cell.number_format = '€#,##0;[Red]-€#,##0'
    for col in [9, 10]:
        for cell in ws.iter_cols(min_col=col, max_col=col, min_row=5, max_row=last).__next__():
            cell.number_format = '0.00'
    ws.conditional_formatting.add(f"H5:H{last}", ColorScaleRule(start_type="min", start_color="FCE3E3", mid_type="percentile", mid_value=50, mid_color="FFF3D6", end_type="max", end_color="D7F0E5"))
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = "Base versus defined stress incremental contribution"
    chart.y_axis.title = "Option"
    chart.x_axis.title = "EUR"
    chart.height = 10
    chart.width = 17
    chart.add_data(Reference(ws, min_col=6, max_col=6, min_row=4, max_row=min(last, 15)), titles_from_data=True)
    chart.add_data(Reference(ws, min_col=8, max_col=8, min_row=4, max_row=min(last, 15)), titles_from_data=True)
    chart.set_categories(Reference(ws, min_col=1, min_row=5, max_row=min(last, 15)))
    chart.legend.position = "b"
    ws.add_chart(chart, "M4")
    rec = metrics["recommendation"]
    ws["M26"] = "Recommendation"
    ws["M26"].font = Font(bold=True, color=TEAL_DARK)
    ws["N26"] = rec["option"]
    ws["M27"] = "Decision rule"
    ws["N27"] = rec["decision_rule"]
    ws["N27"].alignment = Alignment(wrap_text=True)
    ws["M28"] = "Budget headroom"
    ws["N28"] = f"€{rec['budget_headroom']['capex_eur']:,.0f} capex; {rec['budget_headroom']['fte']} FTE"
    ws.column_dimensions["N"].width = 58

    # Order detail.
    ws = wb.create_sheet("Order Detail")
    excel_style(ws, "Order Detail | eligible 2025 orders", "One row per retained eligible order after revision selection; money is rounded per order before aggregation")
    order_headers = list(data["orders"][0].keys())
    order_values = []
    for r in data["orders"]:
        row = []
        for h in order_headers:
            if h in {"revision", "quantity", "returned_units", "restocked_units"}:
                row.append(int(num(r[h])))
            elif h in {"unit_price_local", "discount_local", "fx_local_per_eur", "unit_cost_eur", "gross_sales_eur", "refunds_eur", "gross_cogs_eur", "recovered_cogs_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "refund_local"}:
                row.append(num(r[h]))
            else:
                row.append(r[h])
        order_values.append(row)
    last = add_excel_table(ws, 4, 1, order_headers, order_values, "OrderDetail", {1: 16, 2: 9, 3: 10, 4: 11, 5: 12, 6: 10, 7: 10, 8: 10, 9: 14, 10: 14, 11: 16, 12: 15, 13: 17, 14: 15, 15: 16, 16: 18, 17: 15, 18: 15, 19: 17, 20: 15, 21: 15, 22: 15})
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=13, max_col=20):
        for cell in row:
            cell.number_format = '€#,##0.00;[Red]-€#,##0.00'
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=11, max_col=11):
        for cell in row:
            cell.number_format = '0.000000'

    # Sources.
    ws = wb.create_sheet("Sources")
    excel_style(ws, "Sources | provenance register", "URL, retrieval time, hash, units, period and synthetic/public status for preserved raw files")
    source_headers = ["File", "Original URL", "Retrieved UTC", "SHA-256", "Bytes", "Units", "Period", "Status", "Provenance"]
    source_values = [[r.get(k, "") for k in ["file", "original_url", "retrieved_utc", "sha256", "bytes", "units", "period", "status", "provenance"]] for r in data["sources"]]
    last = add_excel_table(ws, 4, 1, source_headers, source_values, "Sources", {1: 24, 2: 62, 3: 27, 4: 68, 5: 12, 6: 30, 7: 32, 8: 34, 9: 48})
    for row in ws.iter_rows(min_row=5, max_row=last, min_col=2, max_col=9):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[4].height = 36
    for r in range(5, last + 1):
        ws.row_dimensions[r].height = 42

    # Quality notes.
    ws = wb.create_sheet("Quality")
    excel_style(ws, "Quality | checks, anomalies and limitations", "Quality issues are disclosed; no rows were hidden to produce complete tables")
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 100
    q = metrics["quality"]
    quality_rows = [
        ("Raw order rows", q["order_handling"]["order_selection"]["raw_rows"]),
        ("Identical order duplicate rows removed", q["order_handling"]["order_selection"]["identical_duplicate_rows"]),
        ("Order revision replacements", q["order_handling"]["order_selection"]["revision_replacements"]),
        ("Retained unique order IDs", q["order_handling"]["order_selection"]["unique_keys"]),
        ("Eligible 2025 orders", q["order_handling"]["eligible_orders"]),
        ("Excluded order handling", json.dumps(q["order_handling"]["excluded_orders"])),
        ("Raw return rows", q["order_handling"]["return_selection"]["raw_rows"]),
        ("Identical return duplicate rows removed", q["order_handling"]["return_selection"]["identical_duplicate_rows"]),
        ("Return revision replacements", q["order_handling"]["return_selection"]["revision_replacements"]),
        ("Included return rows", q["order_handling"]["included_return_rows"]),
        ("Quarantined returns", json.dumps(q["order_handling"]["excluded_return_rows"])),
        ("Zero-gross shipments included", len(q["calculation"]["zero_gross_sales_orders_included"])),
        ("Monthly reconciliation issues", json.dumps(q["aggregation"]["reconciliation_issues"])),
        ("FX months complete", q["fx"]["months_with_complete_pln_czk"]),
        ("Market missing values", json.dumps(q["market"]["missing_values"])),
        ("Rounding", q["rounding"]),
        ("Return handling", q["return_handling"]),
    ]
    ws["A4"] = "Check"
    ws["B4"] = "Result / handling"
    for cell in ws[4]:
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
    for i, (label, value) in enumerate(quality_rows, 5):
        ws.cell(i, 1, label).font = Font(bold=True, color=TEAL_DARK)
        ws.cell(i, 2, value).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(i, 2).font = Font(size=9, color=INK)
        ws.row_dimensions[i].height = 34 if len(str(value)) > 120 else 23
    ws["A24"] = "Limitations"
    ws["A24"].font = Font(bold=True, color=NAVY, size=11)
    for i, value in enumerate(q["limitations"], 25):
        ws.cell(i, 1, f"L{i-24}")
        ws.cell(i, 2, value).alignment = Alignment(wrap_text=True)
        ws.row_dimensions[i].height = 28

    # Workbook-wide polish.
    for ws in wb.worksheets:
        style_sheet_borders(ws)
        ws.sheet_view.zoomScale = 90
        ws.oddFooter.center.text = "Meridian Parts | Internal board analysis | &P / &N"
        ws.oddFooter.center.size = 8
        ws.oddFooter.center.font = "Aptos"
    path = DELIVERABLES / "meridian_parts_analytical_workbook.xlsx"
    wb.save(path)
    return path


# --------------------------- PDF report ---------------------------


def p(text: str, style) -> Paragraph:
    return Paragraph(text, style)


def link_text(label: str, url: str) -> str:
    return f'<link href="{esc(url)}" color="{TEAL}">{esc(label)}</link>'


def report_table(data_rows, col_widths, header=True, font_size=7.5, alignments=None):
    header_style = ParagraphStyle(name=f"TableHeader{font_size}", fontName="Helvetica-Bold", fontSize=font_size, leading=font_size + 1.6, textColor=colors.white, alignment=TA_LEFT)
    body_styles = {}
    converted = []
    for ridx, row in enumerate(data_rows):
        converted_row = []
        for cidx, value in enumerate(row):
            if isinstance(value, Paragraph):
                converted_row.append(value)
                continue
            alignment = (alignments or {}).get(cidx, "LEFT")
            if alignment == "RIGHT":
                palign = TA_RIGHT
            elif alignment == "CENTER":
                palign = TA_CENTER
            else:
                palign = TA_LEFT
            key = (font_size, palign, ridx == 0 and header)
            if key not in body_styles:
                body_styles[key] = ParagraphStyle(name=f"TableCell{len(body_styles)}", fontName="Helvetica-Bold" if ridx == 0 and header else "Helvetica", fontSize=font_size, leading=font_size + 1.6, textColor=colors.white if ridx == 0 and header else colors.HexColor(f"#{INK}"), alignment=palign)
            text = esc(value).replace("\n", "<br/>")
            converted_row.append(Paragraph(text, body_styles[key]))
        converted.append(converted_row)
    t = LongTable(converted, colWidths=col_widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{NAVY}")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E0E4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F9FA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if alignments:
        for col, alignment in alignments.items():
            style.append(("ALIGN", (col, 1 if header else 0), (col, -1), alignment))
    t.setStyle(TableStyle(style))
    return t


def build_report(data: dict) -> Path:
    metrics = data["metrics"]
    rec = metrics["recommendation"]
    q = metrics["quality"]
    country_rows = data["countries"]
    scenario_rows = data["scenarios"]
    by_opt = defaultdict(dict)
    for row in scenario_rows:
        by_opt[row["country"]][row["scenario"]] = row
    selected = by_opt[rec["option"]]
    base_alt = by_opt[rec["strongest_base_alternative"]["option"]]
    all_country = {r["country"]: r for r in country_rows}
    total = {
        "orders": sum(num(r["shipped_orders"]) for r in country_rows),
        "units": sum(num(r["shipped_units"]) for r in country_rows),
        "gross": sum(num(r["gross_sales_eur"]) for r in country_rows),
        "refunds": sum(num(r["refunds_eur"]) for r in country_rows),
        "net": sum(num(r["net_sales_eur"]) for r in country_rows),
        "cogs": sum(num(r["net_cogs_eur"]) for r in country_rows),
        "fulfill": sum(num(r["fulfillment_eur"]) for r in country_rows),
        "contribution": sum(num(r["contribution_eur"]) for r in country_rows),
        "returned": sum(num(r["returned_units"]) for r in country_rows),
    }
    total["margin"] = total["contribution"] / total["net"] if total["net"] else None
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=27, leading=32, textColor=colors.HexColor(f"#{NAVY}"), spaceAfter=12))
    styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontName="Helvetica", fontSize=13, leading=18, textColor=colors.HexColor(f"#{TEAL_DARK}"), spaceAfter=20))
    styles.add(ParagraphStyle(name="H1x", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=colors.HexColor(f"#{NAVY}"), spaceBefore=10, spaceAfter=8))
    styles.add(ParagraphStyle(name="H2x", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=colors.HexColor(f"#{TEAL_DARK}"), spaceBefore=8, spaceAfter=5))
    styles.add(ParagraphStyle(name="Bodyx", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.2, leading=13.2, textColor=colors.HexColor(f"#{INK}"), spaceAfter=6))
    styles.add(ParagraphStyle(name="Smallx", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.4, leading=10, textColor=colors.HexColor(f"#{MUTED}"), spaceAfter=3))
    styles.add(ParagraphStyle(name="Callout", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=10.5, leading=15, textColor=colors.HexColor(f"#{NAVY}"), backColor=colors.HexColor(f"#{PALE_TEAL}"), borderColor=colors.HexColor(f"#{TEAL}"), borderWidth=0.7, borderPadding=8, spaceBefore=5, spaceAfter=9))
    styles.add(ParagraphStyle(name="RiskCallout", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=13, textColor=colors.HexColor(f"#{INK}"), backColor=colors.HexColor(f"#{PALE_ORANGE}"), borderColor=colors.HexColor(f"#{ORANGE}"), borderWidth=0.7, borderPadding=8, spaceBefore=5, spaceAfter=9))
    styles.add(ParagraphStyle(name="Foot", parent=styles["BodyText"], fontName="Helvetica", fontSize=6.8, leading=8.5, textColor=colors.HexColor(f"#{MUTED}")))
    doc_path = DELIVERABLES / "meridian_parts_executive_report.pdf"
    doc = SimpleDocTemplate(str(doc_path), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=16 * mm, bottomMargin=15 * mm, title="Meridian Parts — European service-hub expansion", author="Meridian Parts operations analysis")

    def on_page(canvas, doc_obj):
        canvas.saveState()
        width, height = A4
        if doc_obj.page > 1:
            canvas.setStrokeColor(colors.HexColor(f"#{TEAL}"))
            canvas.setLineWidth(1)
            canvas.line(15 * mm, height - 11 * mm, width - 15 * mm, height - 11 * mm)
            canvas.setFont("Helvetica-Bold", 7)
            canvas.setFillColor(colors.HexColor(f"#{NAVY}"))
            canvas.drawString(15 * mm, height - 8 * mm, "MERIDIAN PARTS | EUROPEAN SERVICE-HUB EXPANSION")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor(f"#{MUTED}"))
        canvas.drawRightString(width - 15 * mm, 8 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    story = []
    story.append(Spacer(1, 18 * mm))
    story.append(p("Meridian Parts", styles["CoverTitle"]))
    story.append(p("European service-hub expansion", styles["CoverSub"]))
    story.append(Spacer(1, 7 * mm))
    story.append(p("Board decision report", styles["H1x"]))
    story.append(p("Decision basis: 2025 shipped sales and returns known through 31 January 2026; archived ECB and World Bank public observations; synthetic hub-option policy.", styles["Bodyx"]))
    story.append(Spacer(1, 8 * mm))
    story.append(p(f"Recommendation: conditionally fund <b>{esc(rec['option'])}</b> — Netherlands + Spain — with <b>€270,000 year-zero capex and six FTE</b>, subject to the 90-day gates in this report.", styles["Callout"]))
    story.append(Spacer(1, 7 * mm))
    cover_kpis = [[p("2025 net sales", styles["Smallx"]), p("2025 contribution", styles["Smallx"]), p("Recommended base increment", styles["Smallx"]), p("Defined-stress increment", styles["Smallx"])], [p(f"<b>{money(total['net'])}</b>", styles["H2x"]), p(f"<b>{money(total['contribution'])}</b> ({pct(total['margin'])})", styles["H2x"]), p(f"<b>{money(selected['base']['incremental_contribution_eur'])}</b>", styles["H2x"]), p(f"<b>{money(selected['stress']['incremental_contribution_eur'])}</b>", styles["H2x"])]]
    kt = Table(cover_kpis, colWidths=[43 * mm] * 4)
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(f"#{PALE}")), ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D7E0E4")), ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D7E0E4")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.append(kt)
    story.append(Spacer(1, 16 * mm))
    story.append(p("Prepared from the frozen source room; client data and scenario policy are synthetic. No live customer account or customer interviews were used.", styles["Smallx"]))
    story.append(PageBreak())

    # Executive summary.
    story.append(p("Executive decision", styles["H1x"]))
    story.append(p(f"Fund <b>{esc(rec['option'])}</b> conditionally, with a staged release of capex. It is the highest-stress feasible pair among alternatives that remain positive in low, base, high and stress cases. The board should approve the option envelope and the first 90 days, then release the second-hub commitment only if the measurable operating gates are met.", styles["Bodyx"]))
    story.append(p(f"The recommendation gives up <b>{money(num(base_alt['base']['incremental_contribution_eur']) - num(selected['base']['incremental_contribution_eur']))}</b> of modeled base annual increment versus the strongest base-only alternative ({esc(rec['strongest_base_alternative']['option'])}), but improves the defined-stress result by <b>{money(num(selected['stress']['incremental_contribution_eur']) - num(base_alt['stress']['incremental_contribution_eur']))}</b>. This is a risk preference under the client policy, not a proven forecast.", styles["Bodyx"]))
    summary_rows = [[p("Scenario", styles["Smallx"]), p("Recommended NLD+ESP", styles["Smallx"]), p("CZE+ESP base leader", styles["Smallx"]), p("Payback NLD+ESP", styles["Smallx"])]]
    for s in ["low", "base", "high", "stress"]:
        summary_rows.append([s.title(), money(selected[s]["incremental_contribution_eur"]), money(base_alt[s]["incremental_contribution_eur"]), f"{num(selected[s]['payback_years']):.2f}x" if selected[s].get("payback_years") else "—"])
    story.append(report_table(summary_rows, [34 * mm, 43 * mm, 43 * mm, 35 * mm], font_size=8, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT"}))
    story.append(Spacer(1, 5 * mm))
    story.append(p("Board asks", styles["H2x"]))
    for item in [
        "Approve a €270,000 / six-FTE NLD+ESP envelope, with €180,000 capex and one FTE headroom remaining under policy.",
        "Authorize a 90-day validation sprint with a hard second-hub gate; do not treat the modeled payback as a guarantee.",
        "Require Finance, Operations and Data to sign off on actual lane-level SLA, return and contribution evidence before full release.",
    ]:
        story.append(p(f"• {esc(item)}", styles["Bodyx"]))
    story.append(p("What would change the decision? A credible local-lane demand/uplift estimate below the low case, a site or labor quote that pushes capex above the envelope, or failure to meet the gate KPI plan would support deferring. If the board optimizes only for base-case arithmetic and accepts the modeled CZK exposure, CZE+ESP is the strongest alternative.", styles["RiskCallout"]))

    # Scope and evidence.
    story.append(p("1. Scope, evidence and accounting", styles["H1x"]))
    story.append(p("The model covers 2025 shipped orders, one SKU per order row, and returns received through the inclusive 31 January 2026 cutoff. It uses the highest numeric revision across both order extracts and corrections; identical repeats are one record. Returns are selected by return_id revision, additive across legitimate return IDs, and linked only to eligible orders. No orphan is matched by inference.", styles["Bodyx"]))
    story.append(p("Evidence status", styles["H2x"]))
    story.append(p("Client exports, corrections, costs, hub options and policy are synthetic source-room inputs. ECB reference-rate history and World Bank population/GDP are official public snapshots preserved in the source room, with original URLs and retrieval vintage. This report does not rely on live research, interviews or private customer data.", styles["Bodyx"]))
    quality_table = [
        ["Check", "Finding", "Handling"],
        ["Order rows", f"{q['order_handling']['order_selection']['raw_rows']:,} raw; {q['order_handling']['order_selection']['identical_duplicate_rows']} exact repeats; {q['order_handling']['order_selection']['revision_replacements']} revision replacements", "Highest revision retained; no same-revision conflicts"],
        ["Eligibility", f"{q['order_handling']['eligible_orders']:,} eligible 2025 orders; exclusions {q['order_handling']['excluded_orders']}", "Cancelled/test/future records excluded"],
        ["Returns", f"{q['order_handling']['return_selection']['raw_rows']} raw; {q['order_handling']['return_selection']['identical_duplicate_rows']} exact repeats; {q['order_handling']['included_return_rows']} included", "One orphan and one after-cutoff row quarantined"],
        ["Zero-price shipments", f"{len(q['calculation']['zero_gross_sales_orders_included'])} valid orders", "Kept in orders/units; costs retained; no revenue invented"],
        ["Reconciliation", "72 country-month rows → six country totals", "No monthly-to-country reconciliation issues"],
    ]
    story.append(report_table(quality_table, [37 * mm, 62 * mm, 56 * mm], font_size=7.5))
    story.append(p("Revenue, cash and contribution", styles["H2x"]))
    story.append(p(f"The analysis treats shipment-date gross sales as the booked-sales base and subtracts explicit refunds known by the cutoff to form net sales ({money(total['net'])}). It does not reconstruct cash: payment settlement, receivables, taxes, inventory cash timing and refund settlement dates are not in the source room. Contribution ({money(total['contribution'])}) is a management measure after net COGS and non-refundable fulfillment, not cash and not accounting profit.", styles["Bodyx"]))

    # Base diagnosis.
    story.append(p("2. 2025 base diagnosis", styles["H1x"]))
    story.append(p(f"Across the six markets, the retained base is {integer(total['orders'])} shipped orders and {integer(total['units'])} units, producing {money(total['net'])} net sales and {money(total['contribution'])} contribution ({pct(total['margin'])} margin). Spain has the highest contribution and net sales; Czechia has the next-highest contribution margin. Returns are physical units, not return-order counts, and the cutoff makes the comparison comparable across countries.", styles["Bodyx"]))
    ctable = [["Market", "Orders", "Units", "Net sales", "Contribution", "Margin", "Returned units", "Return rate"]]
    for row in country_rows:
        ctable.append([row["country"], integer(row["shipped_orders"]), integer(row["shipped_units"]), money(row["net_sales_eur"]), money(row["contribution_eur"]), pct(row["margin"]), integer(row["returned_units"]), pct(num(row["returned_units"]) / num(row["shipped_units"]) if num(row["shipped_units"]) else None)])
    ctable.append(["Total", integer(total["orders"]), integer(total["units"]), money(total["net"]), money(total["contribution"]), pct(total["margin"]), integer(total["returned"]), pct(total["returned"] / total["units"])])
    story.append(report_table(ctable, [20 * mm, 17 * mm, 19 * mm, 28 * mm, 31 * mm, 18 * mm, 23 * mm, 22 * mm], font_size=7.1, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT", 6: "RIGHT", 7: "RIGHT"}))
    story.append(Spacer(1, 4 * mm))
    bridge = [["Market", "Gross sales", "Refunds", "Net sales", "Net COGS", "Fulfillment", "Contribution"]]
    for row in country_rows:
        bridge.append([row["country"], money(row["gross_sales_eur"]), money(row["refunds_eur"]), money(row["net_sales_eur"]), money(row["net_cogs_eur"]), money(row["fulfillment_eur"]), money(row["contribution_eur"])])
    bridge.append(["Total", money(total["gross"]), money(total["refunds"]), money(total["net"]), money(total["cogs"]), money(total["fulfill"]), money(total["contribution"])])
    story.append(p("Financial bridge (EUR)", styles["H2x"]))
    story.append(report_table(bridge, [20 * mm, 27 * mm, 23 * mm, 27 * mm, 27 * mm, 27 * mm, 30 * mm], font_size=7.1, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT", 6: "RIGHT"}))
    story.append(Spacer(1, 4 * mm))
    story.append(p("Read-through", styles["H2x"]))
    story.append(p("The country ranking is a diagnostic of this synthetic 2025 flow, not a causal estimate of hub demand. Spain and Czechia have the largest unit/contribution base, while Netherlands is smaller but has a favorable contribution profile and no PLN/CZK stress penalty. A hub case still depends on actual lane-level response, service-level improvement and the fixed-cost/fulfillment savings assumptions.", styles["Bodyx"]))

    # Market context and FX.
    story.append(PageBreak())
    story.append(p("3. Market context and historical FX", styles["H1x"]))
    market = data["market"]
    market_map = {(r["country"], int(r["year"])): r for r in market}
    mtable = [["Market", "Population 2022", "Population 2024", "Change", "GDP pc 2024", "GDP pc change"]]
    for c in COUNTRIES:
        p22, p24 = num(market_map[(c, 2022)]["population"]), num(market_map[(c, 2024)]["population"])
        g22, g24 = num(market_map[(c, 2022)]["gdp_per_capita_usd"]), num(market_map[(c, 2024)]["gdp_per_capita_usd"])
        mtable.append([c, integer(p22), integer(p24), pct(p24 / p22 - 1 if p22 else None), money2(g24).replace("€", "$"), pct(g24 / g22 - 1 if g22 else None)])
    story.append(p("The archived World Bank series show population change and current-US$ GDP-per-capita context. Netherlands has the highest GDP per capita in 2024; Spain has the largest population growth among the six in this archive, while Poland is the only market with a population decline from 2022 to 2024. These are context signals only, not direct proof of product demand. Source vintage: 2026-07-13 in the archived response [S5–S6].", styles["Bodyx"]))
    story.append(report_table(mtable, [24 * mm, 29 * mm, 29 * mm, 20 * mm, 30 * mm, 24 * mm], font_size=7.5, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT"}))
    story.append(Spacer(1, 4 * mm))
    fx_map = {(r["currency"], r["month"]): r for r in data["fx"]}
    fxtable = [["Month", "PLN / EUR", "CZK / EUR", "PLN business days", "CZK business days"]]
    for month in MONTHS:
        pln, czk = fx_map[("PLN", month)], fx_map[("CZK", month)]
        fxtable.append([month, f"{num(pln['local_per_eur']):.4f}", f"{num(czk['local_per_eur']):.4f}", pln["business_days"], czk["business_days"]])
    story.append(p("ECB reference rates are quote units per EUR. The model calculates an arithmetic mean over available published business days in each 2025 calendar month and uses that original sale month for both sales and refunds. It does not invert the quote or use today’s rate. This is an analytical translation assumption, not the actual transaction rate [S4].", styles["Bodyx"]))
    story.append(report_table(fxtable, [28 * mm, 30 * mm, 30 * mm, 33 * mm, 33 * mm], font_size=7.2, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT"}))

    # Options.
    story.append(PageBreak())
    story.append(p("4. Hub options and scenario economics", styles["H1x"]))
    story.append(p("The client policy models annual incremental contribution after recurring fixed cost as C×u + U×(1+u)×s − F. Capex is year-zero and separate. Payback is simple undiscounted K / positive annual increment; negative or zero increments have no payback. Feasible pairs add country figures without synergy and must fit €450,000 capex and seven FTE [S7].", styles["Bodyx"]))
    chosen_table = [["Option", "Capex", "FTE", "Low", "Base", "High", "Stress", "Base payback", "Stress payback"],
                    [rec["option"], money(selected["base"]["capex_eur"]), selected["base"]["fte"], money(selected["low"]["incremental_contribution_eur"]), money(selected["base"]["incremental_contribution_eur"]), money(selected["high"]["incremental_contribution_eur"]), money(selected["stress"]["incremental_contribution_eur"]), f"{num(selected['base']['payback_years']):.2f} yrs", f"{num(selected['stress']['payback_years']):.2f} yrs"],
                    [rec["strongest_base_alternative"]["option"], money(base_alt["base"]["capex_eur"]), base_alt["base"]["fte"], money(base_alt["low"]["incremental_contribution_eur"]), money(base_alt["base"]["incremental_contribution_eur"]), money(base_alt["high"]["incremental_contribution_eur"]), money(base_alt["stress"]["incremental_contribution_eur"]), f"{num(base_alt['base']['payback_years']):.2f} yrs", f"{num(base_alt['stress']['payback_years']):.2f} yrs"]]
    story.append(report_table(chosen_table, [18 * mm, 18 * mm, 10 * mm, 19 * mm, 19 * mm, 19 * mm, 19 * mm, 22 * mm, 23 * mm], font_size=7.2, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT", 6: "RIGHT", 7: "RIGHT", 8: "RIGHT"}))
    story.append(Spacer(1, 4 * mm))
    feasible_pairs = [o for o in by_opt if "+" in o]
    rank_pairs = sorted(feasible_pairs, key=lambda o: num(by_opt[o]["base"]["incremental_contribution_eur"]), reverse=True)
    rtable = [["Feasible pair", "Base increment", "Stress increment", "Capex", "FTE", "Base payback"]]
    for o in rank_pairs:
        b, s = by_opt[o]["base"], by_opt[o]["stress"]
        rtable.append([o, money(b["incremental_contribution_eur"]), money(s["incremental_contribution_eur"]), money(b["capex_eur"]), b["fte"], f"{num(b['payback_years']):.2f} yrs" if b.get("payback_years") else "—"])
    story.append(p("Feasible pair ranking (base case)", styles["H2x"]))
    story.append(report_table(rtable, [34 * mm, 32 * mm, 34 * mm, 26 * mm, 16 * mm, 28 * mm], font_size=7.4, alignments={1: "RIGHT", 2: "RIGHT", 3: "RIGHT", 4: "RIGHT", 5: "RIGHT"}))
    story.append(p("The four DEU pairs with FRA, NLD, POL and ESP are not feasible under the stated caps; they are retained as explicit rejections in the workbook and scenario metadata. The selected NLD+ESP pair is not the base-case maximum, but it is the highest defined-stress feasible pair among alternatives positive in all four cases. Its stress case avoids the policy’s additional 10% net-sales shock for PLN/CZK markets.", styles["Bodyx"]))
    story.append(p("Interpretation guardrail", styles["RiskCallout"]))
    story.append(p("These are scenario arithmetic outputs, not a statistical confidence interval, causal elasticity estimate or discounted cash-flow model. The decisive unmeasured assumption is local response: the modeled volume uplift and savings must be validated against actual service-lane evidence before full capex release.", styles["Bodyx"]))

    # Recommendation and implementation.
    story.append(p("5. Recommendation and 90-day implementation", styles["H1x"]))
    story.append(p(f"Recommendation: approve <b>{esc(rec['option'])}</b> with a staged release. Commit to the option envelope (€270,000 capex, six FTE) only as a controlled test. Base economics are {money(selected['base']['incremental_contribution_eur'])} annual incremental contribution and 1.00-year simple payback; the defined stress remains {money(selected['stress']['incremental_contribution_eur'])} with 1.28-year payback. The strongest base alternative CZE+ESP is €16,352 higher in base annual increment but €90,267 lower in stress increment, reflecting the client policy’s CZK shock.", styles["Bodyx"]))
    impl = [
        ["Window", "Owner", "Actions and dependencies", "Decision gate / output"],
        ["Days 0–30\nFrame", "COO / Network lead\nFinance / Data", "Validate country-lane SLA baseline, order density, return reasons and actual local carrier/lease/labor quotes. Build a lane-level hub baseline; dependency: carrier, site and labor data.", "Gate 1: signed data dictionary, site shortlist, quote pack and KPI baseline. Stop if modeled uplift cannot be tied to an observable lane problem."],
        ["Days 31–60\nDesign", "Ops / HR / IT\nProcurement / Legal", "Design inventory pool, WMS/RMA flows, staffing, training, tax/compliance and carrier handoffs. Dependency: site economics, systems integration and local compliance review.", "Gate 2: approve or reject NLD+ESP envelope; no lease/capex release without site quote, service case and risk owner."],
        ["Days 61–90\nPilot", "Hub GM / Quality\nCommercial", "Soft-launch one validated lane/hub first; stage second site only after data shows service and contribution signal. Run weekly control tower with Finance and Data.", "Gate 3: release second-hub spend only if 8-week run-rate achieves ≥80% of base increment for the pilot scope, OTIF ≥95%, stockout ≤3%, and return rate ≤ baseline +1pp."],
    ]
    story.append(report_table(impl, [25 * mm, 31 * mm, 69 * mm, 54 * mm], font_size=7.1))
    story.append(Spacer(1, 4 * mm))
    story.append(p("KPI plan", styles["H2x"]))
    kpi = [["KPI", "Definition", "Initial target / use"]]
    for row in [
        ("OTIF", "On-time, in-full dispatch for hub-served orders", "≥95% through pilot; gate metric"),
        ("Order-to-ship", "Median hours from order release to dispatch", "≤24h or ≥20% improvement vs lane baseline"),
        ("Contribution", "Net sales − net COGS − fulfillment, after actual recurring cost", "≥80% of modeled base run-rate before second-hub release"),
        ("Return rate", "Returned units / shipped units by hub-served lane", "No more than baseline +1 percentage point"),
        ("Stockout / fill", "Orders delayed by inventory availability", "Stockout ≤3%; fill ≥95%"),
        ("Capex / staffing", "Committed capex and filled FTE vs envelope", "≤€270k and ≤6 FTE unless board re-approves"),
    ]:
        kpi.append(list(row))
    story.append(report_table(kpi, [31 * mm, 86 * mm, 62 * mm], font_size=7.3))
    story.append(p("Key risks and mitigations", styles["H2x"]))
    for item in [
        "Demand/uplift risk — validate order density and SLA pain by lane; use the 90-day gate and defer if evidence is weak.",
        "FX / return risk — keep PLN/CZK exposure explicit; monitor refund rate using the original sale-month rate and run monthly stress refreshes.",
        "Fixed-cost and labor risk — require signed quotes and staged hiring; do not convert simple payback into a promise.",
        "Data / process risk — preserve order-level revision and RMA lineage; reconcile weekly hub KPIs to the source-room definitions.",
    ]:
        story.append(p(f"• {esc(item)}", styles["Bodyx"]))

    # Methods and references.
    story.append(PageBreak())
    story.append(p("6. Methods, limitations and source register", styles["H1x"]))
    story.append(p("Calculation method", styles["H2x"]))
    story.append(p("For each eligible order, gross local sales = quantity × unit price − discount; local gross sales and explicit summed refunds are divided by the original sale month’s mean ECB local-per-EUR quote. Unit cost uses the latest effective-dated EUR/unit record on or before shipment. Net COGS = gross COGS − restocked quantity × original unit cost. Gross sales, refunds, gross/recovered/net COGS, fulfillment and contribution are rounded per order to cents using half-up rounding, then summed. Country and monthly margins are null only where net sales is zero.", styles["Bodyx"]))
    story.append(p("Limitations", styles["H2x"]))
    for item in q["limitations"]:
        story.append(p(f"• {esc(item)}", styles["Bodyx"]))
    story.append(p("Source register and links", styles["H2x"]))
    story.append(p("The full machine-readable register is in evidence/source-register.json and the workbook Sources tab. Key links:", styles["Bodyx"]))
    sources = [
        ("S1", "Client data dictionary", "evidence/raw/data-dictionary.md", "Synthetic client metadata; grain, revisions, FX and accounting rules."),
        ("S2", "Client orders, corrections and returns", "evidence/raw/orders-part1.csv; evidence/raw/orders-part2.csv; evidence/raw/order-corrections.csv; evidence/raw/returns.csv", "Synthetic client exports; eligible 2025 orders and cutoff returns."),
        ("S3", "Client unit costs and hub options", "evidence/raw/unit-costs.csv; evidence/raw/hub-options.csv", "Synthetic assumptions; effective-dated unit cost and option economics."),
        ("S4", "ECB historical reference rates", "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip", "Official archived snapshot; quote units per EUR; source-room retrieval 2026-09-27."),
        ("S5", "World Bank population archive", "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&format=json&per_page=1000", "Official archived snapshot; population persons; lastupdated 2026-07-13."),
        ("S6", "World Bank GDP-per-capita archive", "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&format=json&per_page=1000", "Official archived snapshot; current US$ per person; lastupdated 2026-07-13."),
        ("S7", "Scenario policy", "evidence/raw/scenario-policy.md", "Synthetic board assumptions: caps, uplift cases and stress formula."),
    ]
    stable = [["ID", "Source", "Original URL / file", "Use"]]
    for sid, label, url, use in sources:
        stable.append([sid, label, url, use])
    story.append(report_table(stable, [12 * mm, 38 * mm, 85 * mm, 54 * mm], font_size=6.8))
    story.append(Spacer(1, 5 * mm))
    story.append(p("Reproducibility", styles["H2x"]))
    story.append(p("Run python scripts/analyze.py to rebuild analysis/processed, evidence/source-register.* and deliverables/metrics.json from the preserved raw files. Run python scripts/create_deliverables.py to rebuild this report, the board presentation and workbook. Run python scripts/verify_outputs.py for schema, reconciliation, scenario, workbook and PDF checks. The raw files, scripts and instructions stay in this project workspace.", styles["Bodyx"]))
    story.append(p("End of report", styles["Smallx"]))
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return doc_path


# --------------------------- PowerPoint board deck ---------------------------


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def add_textbox(slide, left, top, width, height, text, font_size=18, color=INK, bold=False, align=PP_ALIGN.LEFT, font="Aptos", margin=0.06, valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame
    tf.clear()
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = str(text)
    run.font.name = font
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return box


def add_rich_text(slide, left, top, width, height, paragraphs, fill=None, line=None, margin=0.12):
    shape = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    if fill:
        shape.fill.solid(); shape.fill.fore_color.rgb = rgb(fill)
    else:
        shape.fill.background()
    if line:
        shape.line.color.rgb = rgb(line)
        shape.line.width = Pt(0.8)
    else:
        shape.line.fill.background()
    tf = shape.text_frame
    tf.clear(); tf.margin_left = Inches(margin); tf.margin_right = Inches(margin); tf.margin_top = Inches(margin); tf.margin_bottom = Inches(margin)
    for idx, item in enumerate(paragraphs):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = item.get("text", "")
        p.level = item.get("level", 0)
        p.font.name = item.get("font", "Aptos")
        p.font.size = Pt(item.get("size", 14))
        p.font.bold = item.get("bold", False)
        p.font.color.rgb = rgb(item.get("color", INK))
        p.space_after = Pt(item.get("after", 5))
        p.alignment = item.get("align", PP_ALIGN.LEFT)
    return shape


def slide_base(prs, title: str, section: str = "BOARD DECISION"):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.background.fill
    bg.solid(); bg.fore_color.rgb = rgb(WHITE)
    slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.16)).fill.solid()
    top = slide.shapes[-1]
    top.fill.fore_color.rgb = rgb(TEAL)
    top.line.fill.background()
    add_textbox(slide, 0.55, 0.32, 1.8, 0.18, section, 8, TEAL_DARK, True)
    add_textbox(slide, 0.55, 0.58, 12.1, 0.5, title, 24, NAVY, True)
    add_textbox(slide, 0.55, 7.12, 6.0, 0.18, "Meridian Parts | Synthetic client analysis | Frozen source room", 7, MUTED)
    add_textbox(slide, 12.25, 7.12, 0.55, 0.18, str(len(prs.slides)), 7, MUTED, align=PP_ALIGN.RIGHT)
    return slide


def add_kpi(slide, left, top, width, label, value, sub="", color=TEAL_DARK):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(1.0))
    shape.fill.solid(); shape.fill.fore_color.rgb = rgb(PALE)
    shape.line.color.rgb = rgb("DCE6E9")
    add_textbox(slide, left + 0.12, top + 0.10, width - 0.24, 0.18, label.upper(), 8, MUTED, True)
    add_textbox(slide, left + 0.12, top + 0.32, width - 0.24, 0.32, value, 22, color, True)
    if sub:
        add_textbox(slide, left + 0.12, top + 0.73, width - 0.24, 0.17, sub, 8, MUTED)


def add_bar_chart(slide, left, top, width, height, labels, series, title, max_value=None, colors_list=None, value_fmt="€{:,.0f}"):
    # Lightweight vector bar chart for stable rendering across PowerPoint viewers.
    add_textbox(slide, left, top, width, 0.25, title, 11, NAVY, True)
    n = len(labels)
    series_count = len(series)
    max_val = max_value or max(max(abs(v) for v in vals) for _, vals in series) or 1
    chart_left, chart_top = left + 1.35, top + 0.35
    chart_w, chart_h = width - 1.55, height - 0.7
    # baseline
    base = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(chart_left), Inches(chart_top + chart_h - 0.015), Inches(chart_w), Inches(0.02))
    base.fill.solid(); base.fill.fore_color.rgb = rgb("B8C8CE"); base.line.fill.background()
    group_w = chart_w / max(n, 1)
    bar_w = min(0.22, (group_w * 0.75) / max(series_count, 1))
    for i, label in enumerate(labels):
        add_textbox(slide, chart_left + i * group_w - 0.12, chart_top + chart_h + 0.05, group_w + 0.25, 0.25, label, 8, MUTED, align=PP_ALIGN.CENTER)
        for j, (sname, vals) in enumerate(series):
            val = vals[i]
            bar_h = max(0.01, abs(val) / max_val * (chart_h - 0.08))
            x = chart_left + i * group_w + (group_w - series_count * bar_w) / 2 + j * bar_w
            y = chart_top + chart_h - bar_h
            bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(bar_w - 0.02), Inches(bar_h))
            bar.fill.solid(); bar.fill.fore_color.rgb = rgb((colors_list or [TEAL, ORANGE])[j % len(colors_list or [TEAL, ORANGE])]); bar.line.fill.background()
        if i < len(labels):
            pass
    # legend
    for j, (sname, _) in enumerate(series):
        x = left + width - 1.65 + (j % 2) * 0.85
        y = top + 0.02 + (j // 2) * 0.2
        sq = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y + 0.03), Inches(0.10), Inches(0.10))
        sq.fill.solid(); sq.fill.fore_color.rgb = rgb((colors_list or [TEAL, ORANGE])[j % len(colors_list or [TEAL, ORANGE])]); sq.line.fill.background()
        add_textbox(slide, x + 0.13, y, 0.75, 0.16, sname, 7.5, MUTED)


def add_table_slide(slide, left, top, width, height, headers, rows, col_widths=None, font_size=10, header_fill=NAVY):
    nrows = len(rows) + 1
    ncols = len(headers)
    table = slide.shapes.add_table(nrows, ncols, Inches(left), Inches(top), Inches(width), Inches(height)).table
    if col_widths:
        for i, cw in enumerate(col_widths):
            table.columns[i].width = Inches(cw)
    for c, h in enumerate(headers):
        cell = table.cell(0, c); cell.text = str(h); cell.fill.solid(); cell.fill.fore_color.rgb = rgb(header_fill)
        cell.margin_left = Inches(0.05); cell.margin_right = Inches(0.05)
        for p in cell.text_frame.paragraphs:
            p.font.name = "Aptos"; p.font.size = Pt(font_size - 1); p.font.bold = True; p.font.color.rgb = rgb(WHITE); p.alignment = PP_ALIGN.CENTER
    for r, row in enumerate(rows, 1):
        for c, value in enumerate(row):
            cell = table.cell(r, c); cell.text = str(value); cell.fill.solid(); cell.fill.fore_color.rgb = rgb(WHITE if r % 2 else PALE)
            cell.margin_left = Inches(0.05); cell.margin_right = Inches(0.05); cell.margin_top = Inches(0.02); cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.font.name = "Aptos"; p.font.size = Pt(font_size); p.font.color.rgb = rgb(INK); p.alignment = PP_ALIGN.RIGHT if c > 0 else PP_ALIGN.LEFT
    return table


def build_deck(data: dict) -> Path:
    metrics = data["metrics"]
    rec = metrics["recommendation"]
    q = metrics["quality"]
    countries = data["countries"]
    by_country = {r["country"]: r for r in countries}
    by_opt = defaultdict(dict)
    for r in data["scenarios"]:
        by_opt[r["country"]][r["scenario"]] = r
    sel = by_opt[rec["option"]]
    alt = by_opt[rec["strongest_base_alternative"]["option"]]
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    prs.core_properties.title = "Meridian Parts — European service-hub expansion"
    prs.core_properties.subject = "Board presentation"
    prs.core_properties.author = "Meridian Parts operations analysis"

    # 1 title / decision.
    slide = slide_base(prs, "Fund NLD + ESP conditionally", "BOARD DECISION")
    add_textbox(slide, 0.7, 1.45, 7.2, 0.7, "A risk-adjusted two-hub recommendation", 28, NAVY, True)
    add_textbox(slide, 0.7, 2.22, 7.0, 0.75, "Approve the envelope and a 90-day validation sprint; release the second-hub spend only when actual lane, service and contribution KPIs clear the gates.", 17, INK)
    add_kpi(slide, 8.3, 1.45, 2.05, "Year-zero capex", "€270k", "€180k headroom")
    add_kpi(slide, 10.55, 1.45, 2.05, "Staffing", "6 FTE", "1 FTE headroom")
    add_kpi(slide, 8.3, 2.65, 2.05, "Base increment", "€269.8k", "1.00-year payback")
    add_kpi(slide, 10.55, 2.65, 2.05, "Defined stress", "€210.5k", "1.28-year payback", GREEN)
    add_rich_text(slide, 0.7, 3.55, 11.9, 1.35, [{"text": "Decision logic", "size": 13, "bold": True, "color": TEAL_DARK}, {"text": "Choose the feasible pair that remains positive in low/base/high/stress and ranks first on defined-stress incremental contribution. This is a risk preference under synthetic policy assumptions—not a causal demand forecast.", "size": 15, "color": INK}], fill=PALE_TEAL, line=TEAL)
    add_textbox(slide, 0.7, 5.35, 11.6, 0.65, "Strongest base-only alternative: CZE + ESP — €286.2k base increment / €120.2k stress increment. NLD + ESP gives up €16.4k in base but adds €90.3k in stress.", 15, NAVY, True)

    # 2 executive takeaways.
    slide = slide_base(prs, "What the board should know", "EXECUTIVE TAKEAWAY")
    add_kpi(slide, 0.7, 1.45, 2.45, "2025 net sales", "€4.38m", "6 markets")
    add_kpi(slide, 3.35, 1.45, 2.45, "2025 contribution", "€2.03m", "46.2% margin")
    add_kpi(slide, 6.0, 1.45, 2.45, "Eligible orders", "1,254", "12 months")
    add_kpi(slide, 8.65, 1.45, 2.45, "Returns cutoff", "31 Jan 26", "inclusive")
    bullets = [
        "Spain is the largest synthetic contribution base; Czechia is the strongest base-case pairing partner.",
        "Netherlands + Spain is the most resilient feasible pair under the client’s defined stress because it avoids the extra PLN/CZK shock.",
        "The model is decision support, not proof: local lane demand, service improvement and fixed-cost quotes are the gating evidence.",
    ]
    add_rich_text(slide, 0.7, 3.05, 6.1, 2.7, [{"text": "Diagnosis", "size": 14, "bold": True, "color": TEAL_DARK}] + [{"text": "• " + b, "size": 15, "color": INK, "after": 10} for b in bullets], fill=PALE, line="DCE6E9")
    add_bar_chart(slide, 7.1, 3.05, 5.45, 3.0, ["NLD+ESP", "CZE+ESP", "POL+ESP", "NLD+CZE"], [("Base", [269815, 286167, 277483, 247542]), ("Stress", [210514, 120247, 120418, 87741])], "Incremental contribution", max_value=300000, colors_list=[TEAL, ORANGE])

    # 3 base performance.
    slide = slide_base(prs, "2025 base performance is concentrated in ESP / CZE / POL", "BASE DIAGNOSIS")
    rows = []
    for r in countries:
        rows.append([r["country"], integer(r["shipped_units"]), money(r["net_sales_eur"]), money(r["contribution_eur"]), pct(r["margin"]), integer(r["returned_units"])])
    add_table_slide(slide, 0.7, 1.35, 6.4, 4.5, ["Market", "Units", "Net sales", "Contribution", "Margin", "Returned"], rows, [0.8, 0.9, 1.25, 1.35, 0.8, 0.9], 10)
    labels = [r["country"] for r in countries]
    add_bar_chart(slide, 7.35, 1.35, 5.35, 3.15, labels, [("Contribution", [num(r["contribution_eur"]) for r in countries])], "Contribution by market", max_value=450000, colors_list=[TEAL])
    add_rich_text(slide, 7.35, 4.75, 5.35, 1.1, [{"text": "Read-through", "size": 12, "bold": True, "color": TEAL_DARK}, {"text": "This ranks the synthetic 2025 flow; population/GDP and historical sales do not prove hub demand. Validate actual lane-level SLA pain and density.", "size": 12, "color": INK}], fill=PALE_ORANGE, line=ORANGE)

    # 4 quality/accounting.
    slide = slide_base(prs, "The base is controlled for revisions, returns and historical FX", "DATA QUALITY")
    qrows = [
        ["Raw order rows", f"{q['order_handling']['order_selection']['raw_rows']:,}"],
        ["Exact order repeats removed", str(q['order_handling']['order_selection']['identical_duplicate_rows'])],
        ["Order revision replacements", str(q['order_handling']['order_selection']['revision_replacements'])],
        ["Eligible 2025 orders", f"{q['order_handling']['eligible_orders']:,}"],
        ["Included returns", str(q['order_handling']['included_return_rows'])],
        ["Quarantined returns", "1 orphan; 1 after cutoff"],
        ["Monthly reconciliation", "0 issues"],
        ["Valid zero-price shipments kept", str(len(q['calculation']['zero_gross_sales_orders_included']))],
    ]
    add_table_slide(slide, 0.75, 1.35, 5.6, 4.7, ["Control", "Result"], qrows, [3.4, 2.0], 12)
    add_rich_text(slide, 6.75, 1.35, 5.8, 3.9, [{"text": "Accounting choices", "size": 14, "bold": True, "color": TEAL_DARK}, {"text": "• One order/SKU row; highest numeric revision retained", "size": 14, "color": INK, "after": 8}, {"text": "• Returns linked only to eligible orders; no orphan guessing", "size": 14, "color": INK, "after": 8}, {"text": "• Original sale-month ECB mean used for sale and refund conversion", "size": 14, "color": INK, "after": 8}, {"text": "• Half-up cents at order level before sums", "size": 14, "color": INK, "after": 8}, {"text": "• Contribution is not cash; settlement / working capital are outside source room", "size": 14, "color": INK, "after": 8}], fill=PALE, line="DCE6E9")
    add_textbox(slide, 6.75, 5.65, 5.7, 0.7, "Source status: synthetic client inputs + archived official public snapshots; no live account or interviews.", 13, MUTED, True)

    # 5 context & FX.
    slide = slide_base(prs, "Market context is supportive but not demand proof", "CONTEXT & FX")
    add_table_slide(slide, 0.7, 1.35, 6.1, 4.9, ["Market", "Pop. 22→24", "GDP pc 2024", "GDP pc change"], [[r, pct(num(market_change(data, r))), money2(num(market_2024(data, r))).replace("€", "$"), pct(num(gdp_change(data, r)))] for r in COUNTRIES], [1.0, 1.5, 1.8, 1.7], 10)
    add_textbox(slide, 7.25, 1.35, 5.4, 0.35, "ECB monthly reference means — local units per EUR", 13, NAVY, True)
    # Two lines as vector paths are not portable; use a table plus mini trend bars.
    fx_map = {(r["currency"], r["month"]): num(r["local_per_eur"]) for r in data["fx"]}
    fx_rows = [[m, f"{fx_map[('PLN', m)]:.3f}", f"{fx_map[('CZK', m)]:.3f}"] for m in MONTHS]
    add_table_slide(slide, 7.25, 1.75, 2.45, 4.2, ["Month", "PLN", "CZK"], fx_rows, [1.0, 0.7, 0.7], 8)
    add_rich_text(slide, 9.95, 1.75, 2.7, 2.2, [{"text": "Use in model", "size": 13, "bold": True, "color": TEAL_DARK}, {"text": "PLN and CZK are quote units per EUR. Use the sale-month mean for both sales and refunds; do not invert or use today’s rate.", "size": 12, "color": INK}], fill=PALE_TEAL, line=TEAL)
    add_textbox(slide, 9.95, 4.3, 2.7, 1.3, "World Bank archive vintage\n2026-07-13\n\nContext only", 12, MUTED, True)

    # 6 scenarios.
    slide = slide_base(prs, "NLD + ESP is the stress leader; CZE + ESP is the base leader", "SCENARIO ECONOMICS")
    options = ["NLD+ESP", "CZE+ESP", "POL+ESP", "NLD+CZE", "NLD+POL", "ESP"]
    labels = options
    base_values = [num(by_opt[o]["base"]["incremental_contribution_eur"]) for o in options]
    stress_values = [num(by_opt[o]["stress"]["incremental_contribution_eur"]) for o in options]
    add_bar_chart(slide, 0.7, 1.35, 7.25, 4.8, labels, [("Base", base_values), ("Stress", stress_values)], "Annual incremental contribution after recurring fixed cost", max_value=450000, colors_list=[TEAL, ORANGE])
    rows = [[o, money(by_opt[o]["base"]["capex_eur"]), by_opt[o]["base"]["fte"], f"{num(by_opt[o]['base']['payback_years']):.2f}", f"{num(by_opt[o]['stress']['payback_years']):.2f}" if by_opt[o]["stress"].get("payback_years") else "—"] for o in options]
    add_table_slide(slide, 8.25, 1.35, 4.4, 4.8, ["Option", "Capex", "FTE", "Base PB", "Stress PB"], rows, [1.2, 1.0, 0.6, 0.8, 0.8], 9)

    # 7 recommendation comparison.
    slide = slide_base(prs, "Recommendation: trade a small base premium for a larger stress buffer", "RECOMMENDATION")
    add_rich_text(slide, 0.7, 1.35, 4.0, 3.8, [{"text": "NLD + ESP", "size": 22, "bold": True, "color": TEAL_DARK}, {"text": "€270k capex | 6 FTE", "size": 14, "bold": True, "color": NAVY}, {"text": "Positive in low / base / high / stress", "size": 14, "color": INK, "after": 10}, {"text": "Highest defined-stress feasible pair", "size": 14, "color": INK, "after": 10}, {"text": "Avoids the additional PLN/CZK shock in policy stress", "size": 14, "color": INK, "after": 10}, {"text": "Release second hub only after KPI gate", "size": 14, "color": INK}], fill=PALE_TEAL, line=TEAL)
    comp = [["Metric", "NLD+ESP", "CZE+ESP"], ["Base increment", money(sel["base"]["incremental_contribution_eur"]), money(alt["base"]["incremental_contribution_eur"])], ["Stress increment", money(sel["stress"]["incremental_contribution_eur"]), money(alt["stress"]["incremental_contribution_eur"])], ["Base payback", f"{num(sel['base']['payback_years']):.2f} yrs", f"{num(alt['base']['payback_years']):.2f} yrs"], ["Stress payback", f"{num(sel['stress']['payback_years']):.2f} yrs", f"{num(alt['stress']['payback_years']):.2f} yrs"], ["Policy FX shock", "None", "CZK: 10% of N"], ["Headroom", "€180k / 1 FTE", "€225k / 2 FTE"]]
    add_table_slide(slide, 5.0, 1.35, 7.65, 3.8, comp[0], comp[1:], [2.6, 2.2, 2.4], 12)
    add_textbox(slide, 5.0, 5.45, 7.4, 0.5, "What changes the decision: local uplift, actual SLA gap, site/labor quotes, or failure of KPI gates—not population/GDP alone.", 14, ORANGE, True)

    # 8 implementation.
    slide = slide_base(prs, "90 days: validate one hub, then release the second", "IMPLEMENTATION")
    phases = [("0–30", "Frame", "COO / Finance / Data", "Baseline lanes, SLA, return reasons, sites, carrier and labor quotes"), ("31–60", "Design", "Ops / HR / IT / Legal", "WMS/RMA, inventory pool, staffing, compliance, signed quote pack"), ("61–90", "Pilot", "Hub GM / Quality / Commercial", "Soft launch first validated lane; weekly control tower")]
    x = 0.75
    for i, (day, name, owner, actions) in enumerate(phases):
        add_rich_text(slide, x, 1.55, 3.75, 2.8, [{"text": f"DAYS {day}", "size": 11, "bold": True, "color": TEAL_DARK}, {"text": name, "size": 21, "bold": True, "color": NAVY}, {"text": owner, "size": 11, "bold": True, "color": MUTED}, {"text": actions, "size": 13, "color": INK}], fill=PALE, line="DCE6E9")
        if i < 2:
            arr = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 3.83), Inches(2.55), Inches(0.38), Inches(0.35))
            arr.fill.solid(); arr.fill.fore_color.rgb = rgb(TEAL); arr.line.fill.background()
        x += 4.15
    add_rich_text(slide, 0.75, 4.75, 11.85, 1.25, [{"text": "Gate 3 / second-hub release", "size": 14, "bold": True, "color": TEAL_DARK}, {"text": "Release only if 8-week run-rate reaches ≥80% of base increment for pilot scope, OTIF ≥95%, stockout ≤3%, return rate ≤ baseline +1pp, and capex remains within envelope.", "size": 16, "color": INK}], fill=PALE_ORANGE, line=ORANGE)

    # 9 KPI/risk.
    slide = slide_base(prs, "KPI control tower converts the model into evidence", "GOVERNANCE")
    kpi_rows = [["KPI", "Target", "Owner"], ["OTIF", "≥95%", "Quality / Hub GM"], ["Median order-to-ship", "≤24h or −20%", "Ops"], ["Actual contribution", "≥80% base run-rate", "Finance"], ["Return rate", "≤ baseline +1pp", "Quality / Commercial"], ["Stockout / fill", "≤3% / ≥95%", "Inventory"], ["Capex / staffing", "≤€270k / ≤6 FTE", "Finance / HR"]]
    add_table_slide(slide, 0.75, 1.35, 6.3, 4.8, kpi_rows[0], kpi_rows[1:], [2.1, 2.2, 2.0], 11)
    add_rich_text(slide, 7.4, 1.35, 5.2, 3.8, [{"text": "Risk controls", "size": 14, "bold": True, "color": TEAL_DARK}, {"text": "• Demand: lane-level validation and staged capex", "size": 14, "color": INK, "after": 10}, {"text": "• FX / returns: monthly stress refresh and sale-month rates", "size": 14, "color": INK, "after": 10}, {"text": "• Labor / fixed cost: signed quotes and staged hiring", "size": 14, "color": INK, "after": 10}, {"text": "• Data: preserve revision / RMA lineage and reconcile weekly", "size": 14, "color": INK, "after": 10}], fill=PALE, line="DCE6E9")
    add_textbox(slide, 7.4, 5.55, 5.1, 0.55, "If the gate fails, defer rather than treat the scenario as a promise.", 14, RED, True)

    # 10 decision / references.
    slide = slide_base(prs, "Decision ask and evidence trail", "CLOSE")
    add_rich_text(slide, 0.75, 1.35, 5.8, 3.65, [{"text": "Approve today", "size": 16, "bold": True, "color": TEAL_DARK}, {"text": "1. NLD+ESP option envelope: €270k capex / six FTE", "size": 15, "color": INK, "after": 10}, {"text": "2. 90-day validation sprint and KPI control tower", "size": 15, "color": INK, "after": 10}, {"text": "3. Gate-based release of second-hub spend", "size": 15, "color": INK, "after": 10}, {"text": "4. Re-open if actual demand, SLA, site or labor evidence contradicts the low case", "size": 15, "color": INK}], fill=PALE_TEAL, line=TEAL)
    refs = [["Evidence", "Use"], ["S1–S3", "Synthetic client exports, revisions, returns, costs and options"], ["S4", "Archived ECB reference-rate history; sale-month means"], ["S5–S6", "Archived World Bank population / GDP per capita"], ["S7", "Synthetic scenario policy and stress formula"]]
    add_table_slide(slide, 7.0, 1.35, 5.55, 2.95, refs[0], refs[1:], [1.2, 4.0], 11)
    add_textbox(slide, 7.0, 4.75, 5.45, 1.0, "Full sources, hashes, processed tables and reproducible scripts are delivered with the report and workbook.", 14, NAVY, True)
    add_textbox(slide, 0.75, 6.25, 11.8, 0.4, "Do not read this recommendation as statistically proven, causal or certain; it is a transparent choice under synthetic assumptions and a defined stress.", 12, MUTED, True, align=PP_ALIGN.CENTER)

    path = DELIVERABLES / "meridian_parts_board_presentation.pptx"
    prs.save(path)
    return path


def market_change(data, country):
    rows = {(r["country"], int(r["year"])): r for r in data["market"]}
    p22 = num(rows[(country, 2022)]["population"]); p24 = num(rows[(country, 2024)]["population"])
    return p24 / p22 - 1 if p22 else None


def market_2024(data, country):
    rows = {(r["country"], int(r["year"])): r for r in data["market"]}
    return num(rows[(country, 2024)]["gdp_per_capita_usd"])


def gdp_change(data, country):
    rows = {(r["country"], int(r["year"])): r for r in data["market"]}
    g22 = num(rows[(country, 2022)]["gdp_per_capita_usd"]); g24 = num(rows[(country, 2024)]["gdp_per_capita_usd"])
    return g24 / g22 - 1 if g22 else None


def main():
    DELIVERABLES.mkdir(parents=True, exist_ok=True)
    data = read_all()
    paths = [build_workbook(data), build_report(data), build_deck(data)]
    print("\n".join(str(p) for p in paths))


if __name__ == "__main__":
    main()
