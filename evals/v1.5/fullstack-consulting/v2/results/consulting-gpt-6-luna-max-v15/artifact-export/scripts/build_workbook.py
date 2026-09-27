"""Build the analytical workbook from the reproducible outputs."""
from collections import defaultdict
from pathlib import Path
import csv
import json

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "analysis"
DELIVER = ROOT / "deliverables"
METRICS = json.loads((DELIVER / "metrics.json").read_text(encoding="utf-8"))
NAVY = "16324F"
TEAL = "0B8B82"
PALE = "EAF3F4"
WHITE = "FFFFFF"
INK = "1F2933"
MUTED = "52616B"
ORANGE = "D97732"
MONEY_FMT = '€#,##0.00;[Red](€#,##0.00);-'
RATE_FMT = '0.00000000'


def csv_rows(name):
    with (ANALYSIS / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def style_header(ws, row=1):
    for cell in ws[row]:
        if cell.value is not None:
            cell.fill = PatternFill("solid", fgColor=NAVY)
            cell.font = Font(name="Aptos", bold=True, color=WHITE, size=10)
            cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 30


def table_sheet(wb, title, headers, rows, widths=None, money_columns=(), percent_columns=(), integer_columns=(), date_columns=(), tab_color=TEAL):
    ws = wb.create_sheet(title)
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = 85
    ws.sheet_properties.tabColor = tab_color
    ws.append(headers)
    for row in rows:
        ws.append([row.get(h, None) for h in headers])
    style_header(ws)
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"
        if ws.max_row > 2:
            table_name = "T" + "".join(ch for ch in title if ch.isalnum())[:22]
            table = Table(displayName=table_name, ref=f"A1:{get_column_letter(ws.max_column)}{ws.max_row}")
            table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False, showRowStripes=True, showColumnStripes=False)
            ws.add_table(table)
    for idx, header in enumerate(headers, 1):
        letter = get_column_letter(idx)
        if widths and header in widths:
            ws.column_dimensions[letter].width = widths[header]
        else:
            ws.column_dimensions[letter].width = min(max(len(str(header)) + 3, 12), 24)
        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row_idx, idx)
            cell.font = Font(name="Aptos", size=9, color=INK)
            cell.alignment = Alignment(vertical="top", wrap_text=(header in ("decision", "notes", "url", "vintage_or_note", "return_ids", "interpretation", "rationale", "description")))
            if header in money_columns:
                cell.number_format = MONEY_FMT
                cell.alignment = Alignment(horizontal="right", vertical="top")
            elif header in percent_columns:
                cell.number_format = "0.0%"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            elif header in integer_columns:
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right", vertical="top")
            elif header in date_columns:
                cell.number_format = "yyyy-mm-dd"
    return ws


def main():
    wb = Workbook()
    intro = wb.active
    intro.title = "Start Here"
    intro.sheet_view.showGridLines = False
    intro.sheet_view.zoomScale = 90
    intro.sheet_properties.tabColor = NAVY
    intro.merge_cells("A1:H1")
    intro["A1"] = "MERIDIAN PARTS | EUROPEAN SERVICE HUBS"
    intro["A1"].fill = PatternFill("solid", fgColor=NAVY)
    intro["A1"].font = Font(name="Aptos Display", size=18, bold=True, color=WHITE)
    intro["A1"].alignment = Alignment(vertical="center")
    intro.row_dimensions[1].height = 38
    intro.merge_cells("A3:H3")
    intro["A3"] = "Board recommendation: conditional CZE + ESP funding envelope"
    intro["A3"].font = Font(name="Aptos Display", size=15, bold=True, color=NAVY)
    rec = METRICS["recommendation"]
    intro.append([])
    facts = [
        ("Base annual incremental contribution", next(x for x in METRICS["hub_scenarios"] if x["country"] == "CZE+ESP" and x["scenario"] == "base")["incremental_contribution_eur"], "EUR/year after recurring fixed cost"),
        ("Defined stress annual contribution", next(x for x in METRICS["hub_scenarios"] if x["country"] == "CZE+ESP" and x["scenario"] == "stress")["incremental_contribution_eur"], "EUR/year; joint stress, not a probability"),
        ("Capex / staffing", f"EUR {rec['capex_eur']:,.0f} / {rec['fte']} FTE", "Year-zero capex; five of seven FTE"),
        ("Base simple payback", next(x for x in METRICS["hub_scenarios"] if x["country"] == "CZE+ESP" and x["scenario"] == "base")["payback_years"], "Years; capex divided by positive annual contribution"),
    ]
    row = 5
    for label, value, note in facts:
        intro.cell(row, 1, label).font = Font(name="Aptos", bold=True, color=MUTED)
        intro.cell(row, 2, value).font = Font(name="Aptos Display", size=14, bold=True, color=TEAL)
        intro.merge_cells(start_row=row, start_column=3, end_row=row, end_column=8)
        intro.cell(row, 3, note).font = Font(name="Aptos", size=10, color=INK)
        intro.cell(row, 3).alignment = Alignment(vertical="center")
        intro.row_dimensions[row].height = 28
        row += 1
    intro.merge_cells("A11:H11")
    intro["A11"] = "How to use the workbook"
    intro["A11"].font = Font(name="Aptos Display", bold=True, size=13, color=NAVY)
    guide = [
        "Country totals and Monthly contain all requested 2025 sales, refunds, costs, contribution, returned units and margin fields. All 6 × 12 country-month cells are present, including zeros.",
        "Hub scenarios contains the full low/base/high/stress arithmetic for every single-country option, every pair that fits EUR450,000 / 7 FTE / two hubs, and DEFER. See Hub assumptions for inputs.",
        "Market context preserves all 2022–2024 World Bank observations and adds a derived comparison. GDP per capita is current US$, not PPP or real income and is not a direct demand measure.",
        "Quality & method, Sources, Order ledger, Order exclusions and Return decisions document revision selection, duplicates, cutoffs, joins, anomalies and provenance.",
        "All client exports and planning assumptions are synthetic. World Bank and ECB files are archived public snapshots in evidence/source_room, not live account data.",
        "Run python3 scripts/analyze.py, then python3 scripts/build_workbook.py and python3 scripts/build_pdfs.py to reproduce outputs. See README.md.",
    ]
    for i, line in enumerate(guide, 12):
        intro.merge_cells(start_row=i, start_column=1, end_row=i, end_column=8)
        c = intro.cell(i, 1, "• " + line)
        c.font = Font(name="Aptos", size=10, color=INK)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        intro.row_dimensions[i].height = 36
    intro.merge_cells("A20:H20")
    intro["A20"] = "Accounting boundary"
    intro["A20"].font = Font(name="Aptos Display", bold=True, size=13, color=NAVY)
    intro.merge_cells("A21:H23")
    intro["A21"] = "Net sales = order gross less refunds received by 2026-01-31, converted at the original shipment month's archived ECB monthly mean. Contribution = net sales − net COGS − nonrefundable fulfillment. Cash settlement, payment timing, tax, other overhead, ramp, discounting and residual value are not present in the source data. Monetary components are rounded per order to cents with half-up rounding."
    intro["A21"].font = Font(name="Aptos", size=10, color=INK)
    intro["A21"].alignment = Alignment(wrap_text=True, vertical="top")
    for col, width in zip("ABCDEFGH", [30, 25, 22, 20, 20, 20, 20, 20]):
        intro.column_dimensions[col].width = width
    intro.freeze_panes = "A4"

    monthly = METRICS["monthly"]
    monthly_headers = ["country", "month", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"]
    table_sheet(wb, "Monthly", monthly_headers, monthly,
                widths={"country": 12, "month": 12, "shipped_orders": 16, "shipped_units": 15, "gross_sales_eur": 18, "refunds_eur": 16, "net_sales_eur": 18, "net_cogs_eur": 18, "fulfillment_eur": 18, "contribution_eur": 20, "returned_units": 15, "margin": 12},
                money_columns=monthly_headers[4:10], percent_columns=("margin",), integer_columns=("shipped_orders", "shipped_units", "returned_units"))
    table_sheet(wb, "Country totals", monthly_headers[:1] + monthly_headers[2:], METRICS["countries"],
                widths={"country": 12, "shipped_orders": 16, "shipped_units": 15, "gross_sales_eur": 18, "refunds_eur": 16, "net_sales_eur": 18, "net_cogs_eur": 18, "fulfillment_eur": 18, "contribution_eur": 20, "returned_units": 15, "margin": 12},
                money_columns=monthly_headers[4:10], percent_columns=("margin",), integer_columns=("shipped_orders", "shipped_units", "returned_units"))

    fx_rows = csv_rows("fx_monthly.csv")
    table_sheet(wb, "FX monthly", ["currency", "month", "local_per_eur", "business_days"], fx_rows,
                widths={"currency": 14, "month": 14, "local_per_eur": 22, "business_days": 18}, integer_columns=("business_days",))
    fx_ws = wb["FX monthly"]
    for r in range(2, fx_ws.max_row + 1):
        fx_ws.cell(r, 3).number_format = RATE_FMT
    note_row = fx_ws.max_row + 2
    fx_ws.cell(note_row, 1, "EUR convention")
    fx_ws.cell(note_row, 2, "EUR = 1.00000000 by definition; not included as a published quote series.")
    fx_ws.cell(note_row, 1).font = Font(bold=True, color=NAVY)
    fx_ws.merge_cells(start_row=note_row, start_column=2, end_row=note_row, end_column=4)
    fx_ws.cell(note_row, 2).alignment = Alignment(wrap_text=True)

    market_rows = METRICS["market_context"]
    table_sheet(wb, "Market context", ["country", "year", "population", "gdp_per_capita_usd"], market_rows,
                widths={"country": 13, "year": 12, "population": 20, "gdp_per_capita_usd": 26},
                integer_columns=("year", "population"))
    market_ws = wb["Market context"]
    for r in range(2, market_ws.max_row + 1):
        market_ws.cell(r, 4).number_format = '"$"#,##0.00;[Red]("$"#,##0.00);-'
    context_by_country = defaultdict(dict)
    for row in market_rows:
        context_by_country[row["country"]][row["year"]] = row
    summary = []
    for country, by_year in context_by_country.items():
        p22, p24 = by_year[2022]["population"], by_year[2024]["population"]
        g22, g24 = by_year[2022]["gdp_per_capita_usd"], by_year[2024]["gdp_per_capita_usd"]
        summary.append({"country": country, "population_2024": p24, "population_change_2022_2024_pct": p24 / p22 - 1 if p22 else None,
                        "gdp_per_capita_2022_usd": g22, "gdp_per_capita_2024_usd": g24,
                        "gdp_per_capita_change_2022_2024_pct_current_usd": g24 / g22 - 1 if g22 else None,
                        "interpretation": "Current US$ change is nominal/current-dollar context; not PPP or real growth and not direct product demand."})
    table_sheet(wb, "Market summary", ["country", "population_2024", "population_change_2022_2024_pct", "gdp_per_capita_2022_usd", "gdp_per_capita_2024_usd", "gdp_per_capita_change_2022_2024_pct_current_usd", "interpretation"], summary,
                widths={"country": 12, "population_2024": 17, "population_change_2022_2024_pct": 24, "gdp_per_capita_2022_usd": 22, "gdp_per_capita_2024_usd": 22, "gdp_per_capita_change_2022_2024_pct_current_usd": 35, "interpretation": 68},
                integer_columns=("population_2024",))
    summary_ws = wb["Market summary"]
    for r in range(2, summary_ws.max_row + 1):
        summary_ws.cell(r, 3).number_format = "0.00%"
        summary_ws.cell(r, 4).number_format = '"$"#,##0.00'
        summary_ws.cell(r, 5).number_format = '"$"#,##0.00'
        summary_ws.cell(r, 6).number_format = "0.0%"

    baselines = {x["country"]: x for x in METRICS["country_baseline"]}
    assumption_rows = []
    for b in METRICS["country_baseline"]:
        assumption_rows.append({
            "country": b["country"], "capex_eur": b["capex_eur"], "fte": b["fte"], "annual_fixed_eur": b["annual_fixed_eur"],
            "saving_eur_per_unit": b["saving_eur_per_unit"], "baseline_contribution_eur": b["contribution_eur"],
            "baseline_units": b["units"], "gross_sales_eur": b["gross_sales_eur"], "net_sales_eur": b["net_sales_eur"],
            "return_rate_units": b["returns_rate_units"], "source": "hub-options.csv, 2025 synthetic ledger, scenario-policy.md",
        })
    table_sheet(wb, "Hub assumptions", ["country", "capex_eur", "fte", "annual_fixed_eur", "saving_eur_per_unit", "baseline_contribution_eur", "baseline_units", "gross_sales_eur", "net_sales_eur", "return_rate_units", "source"], assumption_rows,
                widths={"country": 12, "capex_eur": 16, "fte": 10, "annual_fixed_eur": 21, "saving_eur_per_unit": 22, "baseline_contribution_eur": 25, "baseline_units": 17, "gross_sales_eur": 18, "net_sales_eur": 18, "return_rate_units": 19, "source": 58},
                money_columns=("capex_eur", "annual_fixed_eur", "saving_eur_per_unit", "baseline_contribution_eur", "gross_sales_eur", "net_sales_eur"), percent_columns=("return_rate_units",), integer_columns=("fte", "baseline_units"))
    assumptions_ws = wb["Hub assumptions"]
    for r in range(2, assumptions_ws.max_row + 1):
        assumptions_ws.cell(r, 5).number_format = '€0.00'
        assumptions_ws.cell(r, 10).number_format = "0.00%"

    scenario_rows = METRICS["hub_scenarios"]
    scenario_headers = ["country", "scenario", "incremental_contribution_eur", "capex_eur", "fte", "payback_years", "countries"]
    rows = [{**r, "countries": "+".join(r["countries"]) if r["countries"] else "No hub"} for r in scenario_rows]
    table_sheet(wb, "Hub scenarios", scenario_headers, rows,
                widths={"country": 16, "scenario": 14, "incremental_contribution_eur": 32, "capex_eur": 16, "fte": 10, "payback_years": 20, "countries": 20},
                money_columns=("incremental_contribution_eur", "capex_eur"), integer_columns=("fte",))
    scenarios_ws = wb["Hub scenarios"]
    for r in range(2, scenarios_ws.max_row + 1):
        scenarios_ws.cell(r, 6).number_format = "0.0000"
        if scenarios_ws.cell(r, 6).value is None:
            scenarios_ws.cell(r, 6).value = "n/a"
    alternatives = []
    grouped = defaultdict(dict)
    for item in scenario_rows:
        grouped[item["country"]][item["scenario"]] = item
    base_rank = {x["country"]: i + 1 for i, x in enumerate([r for r in METRICS["hub_option_ranking_base"]])}
    for country, values in grouped.items():
        ref = values["base"]
        alternatives.append({
            "base_rank": base_rank.get(country, "—"), "option": country, "capex_eur": ref["capex_eur"], "fte": ref["fte"],
            "low_eur_year": values["low"]["incremental_contribution_eur"], "base_eur_year": ref["incremental_contribution_eur"],
            "high_eur_year": values["high"]["incremental_contribution_eur"], "stress_eur_year": values["stress"]["incremental_contribution_eur"],
            "low_payback_years": values["low"]["payback_years"], "base_payback_years": ref["payback_years"],
            "high_payback_years": values["high"]["payback_years"], "stress_payback_years": values["stress"]["payback_years"],
        })
    alternatives.sort(key=lambda x: (x["base_rank"] == "—", x["base_rank"] if x["base_rank"] != "—" else 999))
    table_sheet(wb, "Option comparison", list(alternatives[0].keys()), alternatives,
                widths={"base_rank": 12, "option": 16, "capex_eur": 16, "fte": 10, "low_eur_year": 22, "base_eur_year": 22, "high_eur_year": 22, "stress_eur_year": 22, "low_payback_years": 19, "base_payback_years": 20, "high_payback_years": 20, "stress_payback_years": 22},
                money_columns=("capex_eur", "low_eur_year", "base_eur_year", "high_eur_year", "stress_eur_year"), integer_columns=("fte",))
    option_ws = wb["Option comparison"]
    for r in range(2, option_ws.max_row + 1):
        for col in (9, 10, 11, 12):
            option_ws.cell(r, col).number_format = "0.0000"
            if option_ws.cell(r, col).value is None:
                option_ws.cell(r, col).value = "n/a"

    # Detailed quality/cutoff/reconciliation values and their handling.
    quality = METRICS["quality"]
    quality_rows = []
    for key, value in quality.items():
        if key == "source_hash_checks":
            value = f"{sum(1 for x in value if x['pass'])}/{len(value)} saved-source hashes matched the collection manifest"
        elif key == "reconciliation":
            value = "; ".join(f"{name}: monthly={r['monthly_sum']}, country={r['country_sum']}, ledger={r['order_ledger_sum']}, pass={r['pass']}" for name, r in value.items())
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        quality_rows.append({"check_or_note": key, "result": value})
    quality_rows += [
        {"check_or_note": "Order rule", "result": "Highest revision selected by order_id across both pages and corrections; full-row corrections replace prior revision; identical rows removed; non-shipped, test, and non-2025 rows excluded."},
        {"check_or_note": "Return rule", "result": "Highest revision by return_id; exact duplicates removed; returns through inclusive 2026-01-31 joined only by exact order_id; orphan rows remain quarantined."},
        {"check_or_note": "FX/rounding", "result": "ECB arithmetic monthly business-day mean, local currency per EUR. Both sales and summed refunds converted at original shipment month. Components rounded per order half-up to cents."},
        {"check_or_note": "Cost recovery", "result": "COGS recovery only for restocked_quantity at shipment-date-effective unit cost; refunds do not automatically recover cost."},
        {"check_or_note": "Cash boundary", "result": "No actual settlement/cash data. Net sales and contribution are calculated accounting measures, not cash-flow observations."},
    ]
    table_sheet(wb, "Quality & method", ["check_or_note", "result"], quality_rows, widths={"check_or_note": 42, "result": 120}, tab_color=ORANGE)

    source_rows = csv_rows("source_register.csv")
    table_sheet(wb, "Sources", list(source_rows[0].keys()), source_rows,
                widths={"file": 38, "url": 72, "retrieved_at_utc": 34, "sha256": 68, "units": 60, "period": 54, "status": 60, "vintage_or_note": 74}, tab_color=NAVY)

    order_rows = csv_rows("order_ledger.csv")
    table_sheet(wb, "Order ledger", list(order_rows[0].keys()), order_rows,
                widths={k: (22 if k.endswith("_eur") or k in ("gross_local", "refund_local") else 18 if k in ("order_id", "return_ids", "ecb_local_per_eur") else 13) for k in order_rows[0]},
                money_columns=tuple(k for k in order_rows[0] if k.endswith("_eur") or k in ("gross_local", "refund_local", "unit_cost_eur")), integer_columns=("revision", "quantity", "shipped_orders", "shipped_units", "restocked_units", "returned_units"))
    for r in range(2, wb["Order ledger"].max_row + 1):
        wb["Order ledger"].cell(r, 9).number_format = RATE_FMT
    exclusion_rows = csv_rows("order_exclusions.csv")
    table_sheet(wb, "Order exclusions", list(exclusion_rows[0].keys()), exclusion_rows,
                widths={"order_id": 24, "revision": 12, "decision": 42, "source_file": 28}, integer_columns=("revision",), tab_color=ORANGE)
    ret_rows = csv_rows("return_decisions.csv")
    table_sheet(wb, "Return decisions", list(ret_rows[0].keys()), ret_rows,
                widths={"return_id": 28, "revision": 12, "order_id": 24, "received_at": 17, "decision": 62}, integer_columns=("revision",), tab_color=ORANGE)

    # Two native Excel charts with auditable data beneath them.
    chart_ws = wb.create_sheet("Decision charts")
    chart_ws.sheet_view.showGridLines = False
    chart_ws.sheet_view.zoomScale = 80
    chart_ws.sheet_properties.tabColor = TEAL
    chart_ws["A1"] = "Scenario contribution and monthly demand profile"
    chart_ws["A1"].font = Font(name="Aptos Display", size=16, bold=True, color=NAVY)
    chart_ws["A2"] = "Annual incremental contribution, EUR; exact scenario arithmetic. Up to top 10 base-ranked sets shown."
    chart_ws["A2"].font = Font(name="Aptos", size=9, italic=True, color=MUTED)
    ranked = [r for r in alternatives if r["option"] != "DEFER"][:10]
    for col, name in enumerate(("Option", "Low", "Base", "High", "Stress"), 1):
        chart_ws.cell(60, col, name)
    for idx, item in enumerate(ranked, 61):
        vals = grouped[item["option"]]
        chart_ws.cell(idx, 1, item["option"])
        for col, scen in enumerate(("low", "base", "high", "stress"), 2):
            chart_ws.cell(idx, col, vals[scen]["incremental_contribution_eur"])
    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.grouping = "clustered"
    chart.overlap = 0
    chart.title = "Annual incremental contribution by scenario"
    chart.y_axis.title = "Option"
    chart.x_axis.title = "EUR per year"
    chart.height = 11.0
    chart.width = 21.0
    chart.legend.position = "b"
    data = Reference(chart_ws, min_col=2, max_col=5, min_row=60, max_row=60 + len(ranked))
    cats = Reference(chart_ws, min_col=1, min_row=61, max_row=60 + len(ranked))
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart_ws.add_chart(chart, "A4")

    chart_ws["G22"] = "Monthly contribution by country, 2025"
    chart_ws["G22"].font = Font(name="Aptos", size=10, bold=True, color=NAVY)
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    chart_ws.cell(60, 7, "Month")
    for col, country in enumerate(["DEU", "FRA", "NLD", "POL", "CZE", "ESP"], 8):
        chart_ws.cell(60, col, country)
    monthly_lookup = {(r["country"], r["month"]): r for r in monthly}
    for idx, month in enumerate(months, 61):
        chart_ws.cell(idx, 7, month)
        for col, country in enumerate(["DEU", "FRA", "NLD", "POL", "CZE", "ESP"], 8):
            chart_ws.cell(idx, col, monthly_lookup[(country, month)]["contribution_eur"])
    line = LineChart()
    line.style = 13
    line.title = "Monthly contribution by country"
    line.y_axis.title = "EUR"
    line.x_axis.title = "Month"
    line.height = 10
    line.width = 19
    line.legend.position = "b"
    line.add_data(Reference(chart_ws, min_col=8, max_col=13, min_row=60, max_row=72), titles_from_data=True)
    line.set_categories(Reference(chart_ws, min_col=7, min_row=61, max_row=72))
    chart_ws.add_chart(line, "G23")
    for col in range(1, 14):
        chart_ws.column_dimensions[get_column_letter(col)].width = 15
    for r in range(60, 73):
        for c in range(1, 14):
            chart_ws.cell(r, c).font = Font(name="Aptos", size=9, color=INK)
            if c >= 2 and r >= 40:
                chart_ws.cell(r, c).number_format = MONEY_FMT
    for c in range(1, 6):
        chart_ws.cell(60, c).fill = PatternFill("solid", fgColor=NAVY)
        chart_ws.cell(60, c).font = Font(bold=True, color=WHITE)
    for c in range(7, 14):
        chart_ws.cell(60, c).fill = PatternFill("solid", fgColor=NAVY)
        chart_ws.cell(60, c).font = Font(bold=True, color=WHITE)

    # Source/quality links and formula caveat are intentionally visible on first tab.
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    path = DELIVER / "meridian_analysis.xlsx"
    wb.save(path)
    # Structural reopen check before completion.
    reopened = load_workbook(path, data_only=False)
    assert len(reopened["Monthly"].tables) == 1
    assert reopened["Monthly"].max_row == 73
    assert reopened["Country totals"].max_row == 7
    assert reopened["Hub scenarios"].max_row == 73
    assert len(reopened["Decision charts"]._charts) == 2
    print(f"Created {path} ({path.stat().st_size:,} bytes); {len(reopened.sheetnames)} sheets, 2 charts")


if __name__ == "__main__":
    main()
