"""Create the board-ready PDF report, slide PDF and analytical XLSX.

Run after analysis/build.py. All numbers are read from deliverables/metrics.json.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether,
                                 PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables"
DATA = json.loads((OUT / "metrics.json").read_text())
NAVY = colors.HexColor("#142840")
TEAL = colors.HexColor("#087F8C")
PALE = colors.HexColor("#EAF4F5")
LIGHT = colors.HexColor("#F4F7FA")
INK = colors.HexColor("#223447")
GRAY = colors.HexColor("#5F6F7D")
ORANGE = colors.HexColor("#D26A3C")
RED = colors.HexColor("#BB4D51")
WHITE = colors.white


def eur(v, decimals=0):
    return f"€{v:,.{decimals}f}"


def pct(v, digits=1):
    return f"{v*100:.{digits}f}%"


def by_option(option, scenario):
    return next(x for x in DATA["hub_combinations"] if x["option"] == option and x["scenario"] == scenario)


def by_single(country, scenario):
    return next(x for x in DATA["hub_scenarios"] if x["country"] == country and x["scenario"] == scenario)


def setup_fonts():
    base = Path("/System/Library/Fonts/Supplemental")
    for name, filename in [("DejaVu", "Arial.ttf"), ("DejaVuBold", "Arial Bold.ttf")]:
        p = base / filename
        if p.exists():
            pdfmetrics.registerFont(TTFont(name, str(p)))
    return ("DejaVu" if "DejaVu" in pdfmetrics.getRegisteredFontNames() else "Helvetica",
            "DejaVuBold" if "DejaVuBold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold")


FONT, BOLD = setup_fonts()


def make_workbook():
    wb = Workbook()
    dash = wb.active
    dash.title = "Decision dashboard"
    header_fill = PatternFill("solid", fgColor="142840")
    teal_fill = PatternFill("solid", fgColor="087F8C")
    pale_fill = PatternFill("solid", fgColor="EAF4F5")
    light_fill = PatternFill("solid", fgColor="F4F7FA")
    title_font = Font(name="Aptos Display", size=18, bold=True, color="FFFFFF")
    regular = Font(name="Aptos", size=10, color="223447")
    money_fmt = '#,##0.00;[Red](#,##0.00);–'
    int_fmt = '#,##0;[Red](#,##0);–'
    percent_fmt = '0.0%;[Red](0.0%);–'

    def sheet(name, title, columns, rows, widths=None, money_cols=(), int_cols=(), percent_cols=()):
        ws = wb.create_sheet(name)
        ws.sheet_view.showGridLines = False
        ws.sheet_view.zoomScale = 90
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
        c = ws.cell(1, 1, title)
        c.fill = header_fill
        c.font = title_font
        c.alignment = Alignment(vertical="center")
        ws.row_dimensions[1].height = 32
        for j, head in enumerate(columns, 1):
            cell = ws.cell(3, j, head)
            cell.fill = teal_fill
            cell.font = Font(name="Aptos", size=10, bold=True, color="FFFFFF")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[3].height = 30
        for i, row in enumerate(rows, 4):
            for j, val in enumerate(row, 1):
                cell = ws.cell(i, j, val)
                cell.font = regular
                cell.fill = light_fill if i % 2 == 0 else PatternFill(fill_type=None)
                cell.alignment = Alignment(vertical="center", wrap_text=False)
                if j in money_cols:
                    cell.number_format = money_fmt
                elif j in int_cols:
                    cell.number_format = int_fmt
                elif j in percent_cols:
                    cell.number_format = percent_fmt
        ws.auto_filter.ref = f"A3:{get_column_letter(len(columns))}{3+len(rows)}"
        ws.freeze_panes = "C4" if len(columns) > 3 else "B4"
        for j in range(1, len(columns)+1):
            ws.column_dimensions[get_column_letter(j)].width = widths[j-1] if widths else max(13, len(columns[j-1])+2)
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        return ws

    # A single front sheet keeps the answer, quantitative trade-off and key assumptions visible.
    dash.sheet_view.showGridLines = False
    dash.sheet_view.zoomScale = 85
    dash.merge_cells("A1:N2")
    dash["A1"] = "MERIDIAN PARTS  |  European service hubs"
    dash["A1"].font = Font(name="Aptos Display", size=21, bold=True, color="FFFFFF")
    dash["A1"].fill = header_fill
    dash["A1"].alignment = Alignment(vertical="center")
    dash.row_dimensions[1].height = 24
    dash.row_dimensions[2].height = 23
    dash.merge_cells("A4:N5")
    dash["A4"] = "Recommendation: fund Spain first; reserve Czechia subject to a day-60 gate. Combined ceiling: €225,000 capex / 5 FTE."
    dash["A4"].font = Font(name="Aptos", size=14, bold=True, color="142840")
    dash["A4"].fill = pale_fill
    dash["A4"].alignment = Alignment(wrap_text=True, vertical="center")
    cards = [("2025 contribution", sum(x["contribution_eur"] for x in DATA["countries"])),
             ("CZE+ESP base / year", by_option("CZE+ESP", "base")["incremental_contribution_eur"]),
             ("CZE+ESP stress / year", by_option("CZE+ESP", "stress")["incremental_contribution_eur"]),
             ("NLD+ESP stress / year", by_option("NLD+ESP", "stress")["incremental_contribution_eur"])]
    for idx, (label, value) in enumerate(cards):
        col = 1 + 3*idx
        dash.merge_cells(start_row=7, start_column=col, end_row=7, end_column=col+2)
        dash.merge_cells(start_row=8, start_column=col, end_row=9, end_column=col+2)
        dash.cell(7, col, label).font = Font(name="Aptos", size=10, bold=True, color="5F6F7D")
        v = dash.cell(8, col, value)
        v.font = Font(name="Aptos Display", size=17, bold=True, color="087F8C")
        v.number_format = '"€"#,##0'
        v.alignment = Alignment(vertical="center")
    dash["A12"] = "Option"
    dash["B12"] = "Base €/year"
    dash["C12"] = "Stress €/year"
    dash["D12"] = "Capex €"
    dash["E12"] = "FTE"
    dash["F12"] = "Base payback y"
    options = ["CZE+ESP", "POL+ESP", "NLD+ESP", "ESP", "DEFER"]
    for i, name in enumerate(options, 13):
        b, s = by_option(name, "base"), by_option(name, "stress")
        vals = [name, b["incremental_contribution_eur"], s["incremental_contribution_eur"], b["capex_eur"], b["fte"], b["payback_years"]]
        for j, value in enumerate(vals, 1):
            dash.cell(i, j, value)
            dash.cell(i, j).fill = light_fill if i % 2 else pale_fill
            dash.cell(i, j).font = regular
            if j in (2, 3, 4):
                dash.cell(i, j).number_format = money_fmt
    for cell in dash[12][:6]:
        cell.fill = teal_fill
        cell.font = Font(name="Aptos", size=10, bold=True, color="FFFFFF")
    dash["A20"] = "Hard constraints"
    dash["B20"] = "≤2 hubs | ≤€450,000 capex | ≤7 FTE"
    dash["A21"] = "Model scope"
    dash["B21"] = "Annual incremental contribution excludes year-zero capex; simple payback is undiscounted."
    dash["A22"] = "Evidence state"
    dash["B22"] = "2025 client transactions and hub inputs are synthetic; ECB/WB series are archived official observations."
    dash["A23"] = "Decision limit"
    dash["B23"] = "Volume uplift and saving assumptions are unvalidated; stress is deterministic, not a probability."
    for row in range(20, 24):
        dash.cell(row, 1).font = Font(name="Aptos", size=10, bold=True, color="142840")
        dash.merge_cells(start_row=row, start_column=2, end_row=row, end_column=12)
        dash.cell(row, 2).alignment = Alignment(wrap_text=True)
    dash.freeze_panes = "A12"
    for c in range(1, 15):
        dash.column_dimensions[get_column_letter(c)].width = 15
    dash.column_dimensions["A"].width = 18
    dash.column_dimensions["B"].width = 19
    dash.column_dimensions["C"].width = 19
    dash.column_dimensions["D"].width = 17
    dash.column_dimensions["E"].width = 13
    dash.column_dimensions["F"].width = 19

    chart = BarChart()
    chart.type = "bar"
    chart.style = 10
    chart.title = "Annual incremental contribution: base vs stress"
    chart.y_axis.title = "Option"
    chart.x_axis.title = "EUR / year"
    chart.add_data(Reference(dash, min_col=2, max_col=3, min_row=12, max_row=17), titles_from_data=True)
    chart.set_categories(Reference(dash, min_col=1, min_row=13, max_row=17))
    chart.height = 9
    chart.width = 20
    chart.legend.position = "b"
    dash.add_chart(chart, "A26")

    country_fields = ["country", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"]
    country_cols = ["Country", "Shipped orders", "Shipped units", "Gross sales EUR", "Refunds EUR", "Net sales EUR", "Net COGS EUR", "Fulfillment EUR", "Contribution EUR", "Returned units", "Margin"]
    country_ws = sheet("Country 2025", "2025 shipped contribution by country", country_cols,
                       [[x[f] for f in country_fields] for x in DATA["countries"]],
                       [13,17,17,20,18,20,19,20,21,18,13], money_cols=(4,5,6,7,8,9), int_cols=(2,3,10), percent_cols=(11,))
    country_ws["M3"] = "Monthly contribution reconciliation"
    country_ws["M3"].fill = teal_fill
    country_ws["M3"].font = Font(name="Aptos", size=10, bold=True, color="FFFFFF")
    country_ws.column_dimensions["M"].width = 31
    for r in range(4, 10):
        country_ws.cell(r, 13, f'=SUMIF(Monthly!$A$4:$A$75,A{r},Monthly!$J$4:$J$75)-I{r}')
        country_ws.cell(r, 13).number_format = money_fmt
    country_chart = BarChart()
    country_chart.type = "bar"
    country_chart.style = 10
    country_chart.title = "2025 contribution by country"
    country_chart.x_axis.title = "EUR"
    country_chart.add_data(Reference(country_ws, min_col=9, min_row=3, max_row=9), titles_from_data=True)
    country_chart.set_categories(Reference(country_ws, min_col=1, min_row=4, max_row=9))
    country_chart.legend = None
    country_chart.width, country_chart.height = 17, 9
    country_ws.add_chart(country_chart, "A13")

    month_fields = ["country", "month", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin"]
    sheet("Monthly", "Monthly 2025 shipped-cohort accounting | sale month", ["Country", "Month", "Shipped orders", "Shipped units", "Gross sales EUR", "Refunds EUR", "Net sales EUR", "Net COGS EUR", "Fulfillment EUR", "Contribution EUR", "Returned units", "Margin"],
          [[x[f] for f in month_fields] for x in DATA["monthly"]],
          [13,15,17,17,20,18,20,19,20,21,18,13], money_cols=(5,6,7,8,9,10), int_cols=(3,4,11), percent_cols=(12,))
    sheet("FX monthly", "ECB 2025 business-day arithmetic means | local units per EUR", ["Currency", "Month", "Local per EUR", "Observations"],
          [[x["currency"], x["month"], x["local_per_eur"], x["observations"]] for x in DATA["fx_observation_counts"]],
          [15,17,21,18], int_cols=(4,))
    fxws = wb["FX monthly"]
    for row in fxws.iter_rows(min_row=4, max_row=27, min_col=3, max_col=3):
        row[0].number_format = '0.0000000000'
    sheet("Market context", "World Bank archived series | 2022–2024", ["Country", "Year", "Population persons", "GDP per capita current US$"],
          [[x["country"], x["year"], x["population"], x["gdp_per_capita_usd"]] for x in DATA["market_context"]],
          [15,13,25,31], int_cols=(2,3), money_cols=(4,))
    singles = DATA["hub_scenarios"]
    sheet("Single hubs", "Client scenario model | annual incremental contribution after fixed cost", ["Country", "Scenario", "Incremental EUR/year", "Capex EUR year zero", "FTE", "Payback years"],
          [[x["country"], x["scenario"], x["incremental_contribution_eur"], x["capex_eur"], x["fte"], x["payback_years"]] for x in singles],
          [15,16,26,24,12,19], money_cols=(3,4), int_cols=(5,))
    sheet("All combinations", "All single, paired and defer choices | filter Feasible = Yes", ["Option", "Scenario", "Incremental EUR/year", "Capex EUR year zero", "FTE", "Feasible", "Payback years"],
          [[x["option"], x["scenario"], x["incremental_contribution_eur"], x["capex_eur"], x["fte"], "Yes" if x["feasible"] else "No", x["payback_years"]] for x in DATA["hub_combinations"]],
          [20,16,26,24,12,15,19], money_cols=(3,4), int_cols=(5,))
    feasible = [x for x in DATA["hub_combinations"] if x["feasible"]]
    sheet("Feasible scenarios", "Options meeting all three board hard constraints", ["Option", "Scenario", "Incremental EUR/year", "Capex EUR year zero", "FTE", "Payback years"],
          [[x["option"], x["scenario"], x["incremental_contribution_eur"], x["capex_eur"], x["fte"], x["payback_years"]] for x in feasible],
          [20,16,26,24,12,19], money_cols=(3,4), int_cols=(5,))
    q = DATA["quality"]
    qrows = [("Order page rows", q["order_page_rows"]), ("Correction rows", q["correction_rows"]),
             ("Raw order rows", q["raw_order_rows"]), ("Distinct order IDs", q["distinct_order_ids"]),
             ("Exact repeated order rows", q["exact_repeated_order_rows"]),
             ("Superseded order revision rows", q["superseded_order_revision_rows"]),
             ("Raw rows missing shipped_at", q["missing_shipped_at_raw_rows"]),
             ("Eligible 2025 shipped orders", q["order_decisions"]["included"]),
             ("Cancelled/other excluded", q["order_decisions"]["cancelled_or_other_status"]),
             ("Test excluded", q["order_decisions"]["test"]),
             ("Future/missing ship date excluded", q["order_decisions"]["outside_2025_or_missing_ship_date"]),
             ("Included free orders", q["included_zero_price_orders"]),
             ("Raw return rows", q["raw_return_rows"]), ("Distinct return IDs", q["distinct_return_ids"]),
             ("Exact repeated return rows", q["exact_repeated_return_rows"]),
             ("Superseded return revision rows", q["superseded_return_revision_rows"]),
             ("Included return IDs", q["return_decisions"]["included"]),
             ("Orphan quarantined", q["return_decisions"]["orphan_quarantined"]),
             ("After cutoff excluded", q["return_decisions"]["after_inclusive_cutoff"]),
             ("Returned units", q["included_returned_units"]),
             ("Restocked units", q["included_restocked_units"]),
             ("Core missing values", str(q["missing_core_values"])),
             ("Reconciliation", q["monetary_reconciliation"]),
             ("Archive vintage", q["archive_vintage_note"]),
             ("FX limitation", q["fx_note"]) ]
    qws = sheet("Quality notes", "Data-quality and accounting decisions", ["Check", "Observed result / treatment"], qrows, [36,115])
    for row in range(4, 4+len(qrows)):
        qws.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="center")
        qws.row_dimensions[row].height = 27 if row > 23 else 19
    import csv
    with (ROOT / "evidence" / "source_register.csv").open(newline="") as f:
        sources = list(csv.DictReader(f))
    srcols = ["file", "status", "original_public_url", "source_room_url", "archive_retrieved_utc", "local_downloaded_utc", "sha256", "units", "period", "source_revision"]
    sws = sheet("Sources", "Frozen source-room register | original URLs, hashes, vintages", ["File", "Status", "Original public URL", "Source room URL", "Archive retrieved UTC", "Local downloaded UTC", "SHA-256", "Units", "Period", "Source revision"],
                [[x.get(k, "") for k in srcols] for x in sources],
                [28,26,64,45,29,29,68,28,22,20])
    sws.freeze_panes = "C4"
    readme = wb.create_sheet("Read me", 1)
    readme.sheet_view.showGridLines = False
    readme.column_dimensions["A"].width = 28
    readme.column_dimensions["B"].width = 110
    readme.merge_cells("A1:B1")
    readme["A1"] = "MODEL GUIDE"
    readme["A1"].fill = header_fill
    readme["A1"].font = title_font
    readme.row_dimensions[1].height = 32
    notes = [
        ("Scope", "2025 shipped order cohort; returns known through 2026-01-31 inclusive and assigned to original sale month."),
        ("Accounting", "Highest numeric revision wins. Identical repeats collapse. Cancelled, tests, and January 2026 shipments are excluded. Free shipments remain."),
        ("Order rounding", "Gross, summed refunds, gross COGS, recovered COGS, and fulfillment are rounded per order to cents, half up; then summed."),
        ("FX", "ECB quote is local units per EUR. Use the original shipment month's arithmetic mean of available 2025 business-day observations; EUR = 1."),
        ("Contribution", "Net sales less net COGS and actual nonrefundable fulfillment. No hub fixed cost is included in the 2025 base."),
        ("Hub annual model", "Low/base/high: C*u + U*(1+u)*saving - annual fixed, u=10%/25%/40%."),
        ("Stress", "(C - 3%*G - 10%*N for PLN/CZK)*1.25 - C + U*1.25*saving - annual fixed; no additional COGS recovery."),
        ("Pair rule", "Country annual contributions, capex and FTE add; no synergy. Year-zero capex is separate from recurring annual contribution."),
        ("Payback", "Year-zero capex / positive annual incremental contribution; undiscounted; blank when contribution ≤0 or defer."),
        ("Status", "Client sales, costs and hub assumptions are synthetic. World Bank and ECB are frozen official-series archives, not live queries by this analysis."),
        ("Reproducibility", "Run python analysis/build.py then python analysis/publish.py from the project root. Order-level ledger and audits are in evidence/."),
        ("Workbook use", "Filter Monthly or All combinations; compare sources and quality tabs. Country reconciliation formulas should calculate to zero in Excel."),
    ]
    for i, (a, b) in enumerate(notes, 3):
        readme.cell(i, 1, a).font = Font(name="Aptos", size=11, bold=True, color="142840")
        readme.cell(i, 2, b).font = regular
        readme.cell(i, 2).alignment = Alignment(wrap_text=True, vertical="center")
        readme.row_dimensions[i].height = 35
    readme.freeze_panes = "B3"
    wb.active = 0
    out = OUT / "meridian_analytical_workbook.xlsx"
    wb.save(out)
    # Structural check on the actual saved workbook, not the in-memory object.
    check = load_workbook(out, read_only=False, data_only=False)
    assert len(check["Monthly"]._cells) > 800
    assert check["Country 2025"]["M4"].value.startswith("=SUMIF")
    assert len(check["Decision dashboard"]._charts) == 1
    assert len(check["Country 2025"]._charts) == 1
    check.close()


STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name="TitleCustom", fontName=BOLD, fontSize=21, leading=26, textColor=NAVY, spaceAfter=11, keepWithNext=True))
STYLES.add(ParagraphStyle(name="SubCustom", fontName=FONT, fontSize=11, leading=15, textColor=GRAY, spaceAfter=16))
STYLES.add(ParagraphStyle(name="HeadCustom", fontName=BOLD, fontSize=13, leading=17, textColor=NAVY, spaceBefore=13, spaceAfter=7, keepWithNext=True))
STYLES.add(ParagraphStyle(name="BodyCustom", fontName=FONT, fontSize=9, leading=13, textColor=INK, spaceAfter=7))
STYLES.add(ParagraphStyle(name="SmallCustom", fontName=FONT, fontSize=7.7, leading=10.5, textColor=INK, spaceAfter=5))
STYLES.add(ParagraphStyle(name="TinyCustom", fontName=FONT, fontSize=7, leading=9, textColor=GRAY, spaceAfter=4))
STYLES.add(ParagraphStyle(name="WhiteCustom", fontName=BOLD, fontSize=10, leading=14, textColor=WHITE))


def P(s, style="BodyCustom"):
    return Paragraph(s, STYLES[style])


def report_table(rows, widths, header=True, font=7.7, aligns=None):
    cooked = []
    for i, row in enumerate(rows):
        cooked.append([P(str(x), "WhiteCustom" if i == 0 and header else "SmallCustom") for x in row])
    t = Table(cooked, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    styles = [
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("ROWBACKGROUNDS", (0,1 if header else 0), (-1,-1), [WHITE, LIGHT]),
        ("LINEBELOW", (0,-1), (-1,-1), 0.4, colors.HexColor("#D8E0E7")),
    ]
    if header:
        styles.append(("BACKGROUND", (0,0), (-1,0), NAVY))
    if aligns:
        for col in aligns:
            styles.append(("ALIGN", (col,1), (col,-1), "RIGHT"))
    t.setStyle(TableStyle(styles))
    return t


def report_page(canvas_obj, doc):
    canvas_obj.saveState()
    w, h = doc.pagesize
    canvas_obj.setStrokeColor(TEAL)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(17*mm, h-15*mm, w-17*mm, h-15*mm)
    canvas_obj.setFont(FONT, 8)
    canvas_obj.setFillColor(GRAY)
    canvas_obj.drawString(17*mm, 12*mm, "MERIDIAN PARTS  •  BOARD DECISION BRIEF  •  27 SEP 2026")
    canvas_obj.drawRightString(w-17*mm, 12*mm, f"{doc.page}")
    canvas_obj.restoreState()


def make_report():
    path = OUT / "meridian_executive_report.pdf"
    doc = BaseDocTemplate(str(path), pagesize=(210*mm, 297*mm),
                          leftMargin=18*mm, rightMargin=18*mm,
                          topMargin=22*mm, bottomMargin=19*mm,
                          title="Meridian Parts | European service-hub expansion")
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=report_page))
    story = []
    add = story.append
    add(P("European service-hub expansion", "TitleCustom"))
    add(P("Board decision brief  |  synthetic client data  |  frozen official-series archive", "SubCustom"))
    add(P("Recommendation", "HeadCustom"))
    add(P("Approve a staged ceiling of <b>€225,000 year-zero capex and five FTE</b> for Spain and Czechia. Commit Spain first (€130,000; three FTE); reserve Czechia (€95,000; two FTE) until the day-60 operating and commercial gate. The pair has <b>€198,099</b> modeled annual incremental contribution after recurring fixed costs in the client base case and a <b>1.14-year</b> simple payback. The defined severe joint stress reduces its annual gain to <b>€32,180</b> and extends simple payback to <b>6.99 years</b>. [C1, C2, A2]"))
    add(P("Decision frame and status", "HeadCustom"))
    add(report_table([
        ["Question", "Hard conditions", "Decision basis"],
        ["Fund up to two of six local hubs, or defer.", "≤€450k capex; ≤7 FTE; ≤2 hubs.", "Primary planning criterion: incremental annual contribution after recurring fixed cost; then resilience, cash exposure and staged execution. The board has not supplied numerical weights."],
        ["Time boundary", "2025 shipped cohort, returns known through 31 Jan 2026.", "Hub estimates are annual run-rate assumptions, not observed causal effects or a discounted cash-flow forecast."],
    ], [39*mm, 51*mm, 84*mm]))
    add(P("<b>Conclusion card.</b> The base-case choice is CZE+ESP; the strongest stress alternative is NLD+ESP. The choice accepts Czechia’s PLN/CZK-style FX sensitivity and unproven 25% volume uplift. If roughly <b>29% of the defined joint stress</b> materializes on the second-hub comparison, NLD replaces CZE on annual incremental contribution; a measured Czechia pilot below the NLD-equivalent economics also reopens the choice. The actual uplift, savings and operating costs need validation before Czechia capex is released. [C2, A2]", "SmallCustom"))
    add(Spacer(1, 5*mm))
    add(P("1  Evidence-linked diagnosis", "HeadCustom"))
    total = {k: sum(x[k] for x in DATA["countries"]) for k in ["shipped_orders","shipped_units","gross_sales_eur","refunds_eur","net_sales_eur","net_cogs_eur","fulfillment_eur","contribution_eur","returned_units"]}
    add(P(f"The resolved 2025 cohort contains <b>{total['shipped_orders']:,} orders and {total['shipped_units']:,} units</b>. It booked {eur(total['gross_sales_eur'])} gross sales and {eur(total['refunds_eur'])} credits, yielding {eur(total['net_sales_eur'])} net sales. After {eur(total['net_cogs_eur'])} net COGS and {eur(total['fulfillment_eur'])} nonrefundable fulfillment, contribution is <b>{eur(total['contribution_eur'])}</b>. All 72 country-month records reconcile to the six totals below. [C1, A1]"))
    rows = [["Market", "Orders", "Units", "Net sales €", "Contribution €", "Margin", "Returned units"]]
    for x in DATA["countries"]:
        rows.append([x["country"], f"{x['shipped_orders']:,}", f"{x['shipped_units']:,}", f"{x['net_sales_eur']:,.0f}", f"{x['contribution_eur']:,.0f}", pct(x["margin"]), f"{x['returned_units']:,}"])
    rows.append(["TOTAL", f"{total['shipped_orders']:,}", f"{total['shipped_units']:,}", f"{total['net_sales_eur']:,.0f}", f"{total['contribution_eur']:,.0f}", pct(total['contribution_eur']/total['net_sales_eur']), f"{total['returned_units']:,}"])
    add(report_table(rows, [22*mm, 18*mm, 20*mm, 31*mm, 34*mm, 20*mm, 29*mm]))
    add(P("Spain and Czechia have the highest 2025 contribution among these synthetic country cohorts; each market happens to have 209 eligible orders, so the differences arise from units, price/cost and returns rather than observed order counts. This is a client-specific financial signal, not a population-based demand estimate. [C1]"))
    add(P("Booked net sales equal shipped goods value less eligible credits, translated at the original sale-month reference quote. Cash receipts and payments may occur on different dates and at actual bank rates; no settlement ledger or receivable balance was supplied. Contribution further deducts product cost net of only <i>restocked</i> units and actual fulfillment. It omits corporate overhead, taxes, hub startup capex and recurring hub fixed cost, which enter the option model separately. [A1]"))
    add(P("Data reconciliation and quality", "HeadCustom"))
    q = DATA["quality"]
    add(P(f"Across two pages and corrections there are {q['raw_order_rows']:,} raw order rows, {q['distinct_order_ids']:,} distinct IDs, {q['exact_repeated_order_rows']} exact repeats and {q['superseded_order_revision_rows']} superseded revision rows. Highest numeric revision wins; {q['order_decisions']['cancelled_or_other_status']} cancelled, {q['order_decisions']['test']} test and one January 2026 shipment are excluded. The {q['missing_shipped_at_raw_rows']} raw missing shipment dates belong to cancelled rows. All {q['included_zero_price_orders']} valid free shipments stay in units, COGS and fulfillment. [C1, A1]"))
    add(P(f"Returns have {q['raw_return_rows']} raw rows, {q['distinct_return_ids']} IDs, {q['exact_repeated_return_rows']} exact repeats and one superseded revision. {q['return_decisions']['included']} resolved return IDs enter the 2025 shipped cohort; one orphan is quarantined and one 1 Feb 2026 return is after the inclusive cutoff. The included {q['included_returned_units']:,} returned units yield only {q['included_restocked_units']:,} reusable units for COGS recovery. The order/return audit and ledger preserve every decision. [C1, A1]"))
    add(Spacer(1, 4*mm))
    add(P("2  Market context and exchange rates", "TitleCustom"))
    add(P("These are contextual public observations, not evidence of assembly demand or a causal hub uplift. The World Bank archive was collected by the source room on 27 Sep 2026 and labels the series last updated 13 Jul 2026. Values may contain later revisions of 2022–2024 observations. [P1, P2]"))
    ctx = {(x["country"], x["year"]): x for x in DATA["market_context"]}
    rows = [["Market", "Population 2022", "Population 2024", "Change", "2024 GDP/capita, current US$"]]
    for c in ["DEU","FRA","NLD","POL","CZE","ESP"]:
        a, b = ctx[(c,2022)], ctx[(c,2024)]
        rows.append([c, f"{a['population']:,}", f"{b['population']:,}", pct(b['population']/a['population']-1,2), f"{b['gdp_per_capita_usd']:,.0f}"])
    add(report_table(rows, [22*mm, 37*mm, 37*mm, 21*mm, 57*mm]))
    add(P("Spain has the largest 2022–2024 population increase in this set (+2.22%); Poland declined (−0.71%). The Netherlands’ 2024 current-US$ GDP per capita is highest here, while Poland’s is lowest. These series help frame size and economic context but do not measure Meridian’s installed base, service failures, willingness to pay or local delivery advantage. All 18 country-year combinations are present in the archive; the workbook retains each year and underlying values. [P1, P2]"))
    fxrows = DATA["fx_observation_counts"]
    add(P("The 2025 ECB archive supplies all 12 monthly means for PLN and CZK. The quoted direction is <b>local currency units per EUR</b>; the model divides local gross sales and aggregate local refunds by the original sale month’s mean. The 2025 PLN monthly means range from " + f"{min(x['local_per_eur'] for x in fxrows if x['currency']=='PLN'):.4f} to {max(x['local_per_eur'] for x in fxrows if x['currency']=='PLN'):.4f}" + "; CZK from " + f"{min(x['local_per_eur'] for x in fxrows if x['currency']=='CZK'):.4f} to {max(x['local_per_eur'] for x in fxrows if x['currency']=='CZK'):.4f}" + ". EUR orders use 1. These means are analytical translations, not actual transaction settlement rates. The workbook lists all 24 means and observation counts. [E1, A1]"))
    add(P("3  Quantified option screen", "TitleCustom"))
    add(P("Client-owned synthetic assumptions: volume uplifts 10%/25%/40%; per-unit savings and recurring fixed costs from the option file. Annual incremental contribution = baseline contribution × uplift + baseline units × (1+uplift) × savings per unit − recurring fixed cost. Year-zero capex is separate; simple payback divides capex by positive annual gain. The joint stress adds a refund shock of 3% of gross sales without further cost recovery, plus a 10% net-sales depreciation shock in PLN/CZK markets. [C2, A2]"))
    rows = [["Hub", "Capex €", "FTE", "Low €/yr", "Base €/yr", "High €/yr", "Stress €/yr"]]
    for c in ["DEU","FRA","NLD","POL","CZE","ESP"]:
        b = by_single(c,"base")
        rows.append([c, f"{b['capex_eur']:,.0f}", str(b["fte"]), *[f"{by_single(c,s)['incremental_contribution_eur']:,.0f}" for s in ["low","base","high","stress"]]])
    add(report_table(rows, [20*mm, 27*mm, 13*mm, 27*mm, 29*mm, 29*mm, 29*mm]))
    add(P("All six singles meet the hard budget and staffing limits. Of 15 possible pairs, 11 are feasible; each pair adds its constituent country economics with no synergy. The workbook includes every single, all pairs, defer, all four scenarios, feasibility and payback. Negative annual contribution has no payback. [C2, A2]"))
    pairs = [x for x in DATA["hub_combinations"] if x["feasible"] and len(x["countries"]) == 2 and x["scenario"] == "base"]
    pairs.sort(key=lambda x: x["incremental_contribution_eur"], reverse=True)
    rows = [["Feasible pair", "Base €/yr", "Stress €/yr", "Capex €", "FTE", "Base payback y"]]
    for x in pairs:
        stress = by_option(x["option"], "stress")
        rows.append([x["option"], f"{x['incremental_contribution_eur']:,.0f}", f"{stress['incremental_contribution_eur']:,.0f}", f"{x['capex_eur']:,.0f}", str(x["fte"]), f"{x['payback_years']:.2f}"])
    add(report_table(rows, [32*mm, 29*mm, 29*mm, 29*mm, 14*mm, 41*mm]))
    add(Spacer(1, 4*mm))
    add(P("4  Choice, alternatives and switching test", "TitleCustom"))
    add(P("The hard constraints are capex, staffing and hub count. Among feasible choices, CZE+ESP is first on annual gain in low (€64,619), base (€198,099) and high (€331,580). It consumes €225,000, five FTE and two hubs, leaving €225,000 budget headroom and two FTE. Its base gain is €11,770 above the second-ranked base pair POL+ESP; the stress gain is €2,916 higher than POL+ESP but still thin relative to capex. [C2]"))
    add(P("The more consequential alternative is <b>NLD+ESP</b>. It gives up €31,168 annual base gain and needs €45,000 more capex and one more FTE, but delivers €107,630 under the defined joint stress versus €32,180 for CZE+ESP. It avoids the modeled CZK depreciation shock. In the stress criterion, NLD+ESP dominates the selected pair; in base annual gain and capital efficiency, CZE+ESP is stronger. Neither dominates across all criteria. Deferring has zero capex and zero modeled incremental gain, and remains sensible if uplift or savings fail validation. [C2]"))
    add(P("The base-vs-stress second-hub edge changes from +€31,168 for Czechia to −€75,450 under the full defined joint stress. Linear interpolation of that <i>specific</i> stress bundle crosses zero at about <b>29.2% of the bundle</b>. This is a scenario sensitivity, not a probability, confidence interval or forecast. It provides the board a measurable switch trigger: if updated, evidenced Czechia refund/FX and unit economics imply a worse annual second-hub gain than the Netherlands on the same basis, select NLD or defer the second hub. [C2, A2]"))
    add(P("5  First 90 days: staged execution", "TitleCustom"))
    implementation = [
        ["Days", "Accountable owner", "Dependency and work", "Decision gate / evidence"],
        ["0–15", "COO + Finance", "Approve Spain spend ceiling; validate 2025 ledger, carrier/service baseline and site quote. Ring-fence Czechia spend only.", "Signed costed Spain charter; monthly country ledger reconciles to source; legal and tax checks assigned."],
        ["16–30", "Spain operations lead", "Finalize lease/3PL and inventory layout; define SKU stocking and reverse logistics with Finance.", "Contracted annual fixed cost and savings per shipped unit remain within model tolerance; launch readiness review."],
        ["31–60", "Spain lead + Commercial", "Pilot Spain routing and scan events; run Czechia carrier and customer-order feasibility sample from real operations.", "≥95% on-time dispatch, ≥98% scan completeness; verified unit savings and return handling. CFO compares refreshed CZE vs NLD annual gain."],
        ["61–90", "COO + CFO + board sponsor", "Scale Spain if service and economics hold; release CZE only after gate; otherwise compare NLD or defer.", "CZE release requires a positive risk-adjusted case, documented FX/return sensitivity, signed fixed-cost quote and capacity plan; board records decision."],
    ]
    add(report_table(implementation, [19*mm, 33*mm, 64*mm, 58*mm]))
    add(P("KPI plan", "HeadCustom"))
    kpi = [
        ["Metric", "Definition / cadence", "Owner and action threshold"],
        ["Delivery", "On-time dispatch ÷ eligible hub shipments, weekly; compare to central baseline for same destinations/SKUs.", "Spain lead; ≥95% pilot target, investigate any 2-week shortfall."],
        ["Unit economics", "Actual carrier + handling EUR per shipped unit against pre-launch country baseline, weekly.", "Finance; verify at least the option-file €3.0 Spain and €2.1 Czechia unit saving before scale."],
        ["Returns", "Returned units ÷ shipped units by sale cohort; refund EUR ÷ gross sales EUR, monthly.", "Finance + Quality; re-run 3% gross-sales shock and quarantine unmatched returns."],
        ["Contribution", "Order-rounded net sales − net COGS − fulfillment − annualized hub fixed cost, monthly.", "CFO; positive forward annualized gain and refreshed payback before second commitment."],
        ["Data quality", "Unmatched return IDs, duplicate IDs, missing cost/FX, monthly-to-country difference.", "Data lead; unresolved unmatched records remain quarantined; monetary reconciliation target €0."],
    ]
    add(report_table(kpi, [30*mm, 76*mm, 68*mm]))
    add(P("Owners are proposed roles, not named client personnel. KPI thresholds are implementation controls, not observations from the source room. A 90-day pilot cannot prove a full-year uplift; continuation requires updated run-rate evidence and a conservative capacity check. [A2]", "SmallCustom"))
    add(PageBreak())
    add(P("6  Risks, evidence status and limitations", "TitleCustom"))
    risks = [
        ["Risk", "Why it matters", "Control / owner"],
        ["Volume uplift is assumed", "The 10/25/40% cases are client planning inputs, with no observed hub experiment or demand elasticity.", "Commercial and Finance compare routed cohorts with the central baseline; do not interpret modeled gain as causal."],
        ["FX and refund stress", "Czechia’s modeled annual gain turns negative under the combined shock; actual settlement FX is unavailable.", "CFO refreshes monthly FX and refund sensitivity before CZE release; NLD+ESP is the stress fallback."],
        ["Fixed-cost/site quote risk", "A higher lease/3PL fixed cost lowers annual gain euro-for-euro; capex overspend consumes headroom.", "COO obtains binding quotes and logs committed versus authorized capex."],
        ["Service and stock-outs", "A hub can raise inventory burden or miss service promises despite forecast savings.", "Spain lead pilots SKU assortment, scan completeness and dispatch service before scale."],
        ["Data scope", "Returns after 31 Jan 2026 and transaction cash timing are outside the cohort; orphan return is not attributed.", "Data lead refreshes cohort roll-forward and keeps unmatched records separate."],
    ]
    add(report_table(risks, [35*mm, 75*mm, 64*mm]))
    add(P("Evidence register (saved locally in evidence/raw and evidence/source_register.csv)", "HeadCustom"))
    refs = [
        ("[C1]", "Synthetic client exports: orders-part1.csv, orders-part2.csv, order-corrections.csv, returns.csv, unit-costs.csv; full hashes, collection timestamps and units in source register."),
        ("[C2]", "Synthetic client hub-options.csv; capex, FTE, fixed cost and saving EUR/unit."),
        ("[A1]", "Synthetic client data-dictionary.md; grain, revision, currency, cost and return rules."),
        ("[A2]", "Synthetic client scenario-policy.md; uplift, stress, pair and payback rules."),
        ("[P1]", "Archived World Bank population, SP.POP.TOTL, 2022–2024: https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&amp;format=json&amp;per_page=1000"),
        ("[P2]", "Archived World Bank GDP per capita current US$, NY.GDP.PCAP.CD, 2022–2024: https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&amp;format=json&amp;per_page=1000"),
        ("[E1]", "Archived ECB euro reference history ZIP: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip; extracted CSV saved in source room."),
    ]
    for code, desc in refs:
        add(P(f"<b>{code}</b> {desc}", "TinyCustom"))
    add(P("Archive versus live research.", "HeadCustom"))
    add(P("The analysis copied the frozen source room at http://127.0.0.1:65178/ and verified public archive file hashes against its provenance metadata. It did not query live ECB or World Bank endpoints for the core calculations. The copied public responses were archived on 27 Sep 2026; local copy times, hashes, periods and units appear in the source register. No customer interviews, actual settlement rates, demand study, route-time baseline, site quotes or operational pilot outcomes were supplied. The board recommendation is conditional on those missing operating inputs, rather than statistically proven. [C1, C2, P1, P2, E1]"))
    doc.build(story)


def draw_slide_common(c, n, title, kicker=None):
    W, H = 960, 540
    c.setFillColor(WHITE)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.rect(0, H-72, W, 72, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont(BOLD, 23)
    c.drawString(44, H-45, title)
    if kicker:
        c.setFont(FONT, 10)
        c.setFillColor(TEAL)
        c.drawString(45, H-91, kicker.upper())
    c.setFillColor(GRAY)
    c.setFont(FONT, 8)
    c.drawString(44, 22, "MERIDIAN PARTS  |  synthetic client case • frozen ECB/WB archive • 27 SEP 2026")
    c.drawRightString(W-44, 22, str(n))
    c.setStrokeColor(colors.HexColor("#D9E3E8"))
    c.line(44, 35, W-44, 35)


def slide_text(c, x, y, text, width, size=15, color=INK, bold=False, leading=None):
    style = ParagraphStyle("slide", fontName=BOLD if bold else FONT, fontSize=size,
                           leading=leading or size*1.3, textColor=color)
    p = Paragraph(text, style)
    _, h = p.wrap(width, 500)
    p.drawOn(c, x, y-h)
    return h


def slide_card(c, x, y, w, h, label, value, note="", accent=TEAL):
    c.setFillColor(LIGHT)
    c.roundRect(x,y,w,h,10,fill=1,stroke=0)
    c.setFillColor(accent)
    c.rect(x,y+h-6,w,6,fill=1,stroke=0)
    c.setFillColor(GRAY)
    c.setFont(BOLD, 10)
    c.drawString(x+16,y+h-31,label.upper())
    c.setFillColor(NAVY)
    c.setFont(BOLD, 25)
    c.drawString(x+16,y+h-67,value)
    if note:
        slide_text(c,x+16,y+41,note,w-32,10,GRAY)


def make_deck():
    path = OUT / "meridian_board_presentation.pdf"
    c = canvas.Canvas(str(path), pagesize=(960,540))
    c.setTitle("Meridian Parts | European service-hub board presentation")
    # Slide 1
    draw_slide_common(c,1,"Approve Spain; gate Czechia", "Decision request")
    slide_text(c,50,415,"Authorize a staged <b>€225k / 5 FTE</b> ceiling for Spain + Czechia. Commit Spain first; release Czechia only after a day-60 commercial and operating review.",850,24,NAVY,False,32)
    slide_card(c,52,182,264,118,"Annual base gain","€198,099","After recurring hub fixed cost")
    slide_card(c,342,182,264,118,"Year-zero capex","€225,000","€225k below board ceiling")
    slide_card(c,632,182,264,118,"Simple payback","1.14 years","Undiscounted base case")
    slide_text(c,52,132,"Decision strength: modeled, conditional. The stress case leaves €32,180/year and a 6.99-year simple payback.",835,14,ORANGE,True)
    c.showPage()
    # Slide 2
    draw_slide_common(c,2,"The 2025 cohort supports a focused screen", "Resolved client accounting")
    countries = DATA["countries"]
    total = sum(x["contribution_eur"] for x in countries)
    slide_text(c,48,426,f"1,254 eligible orders • 77,436 shipped units • €4.384m net sales • <b>{eur(total)} contribution</b>",870,16,NAVY,True)
    maxval = max(x["contribution_eur"] for x in countries)
    for i, x in enumerate(countries):
        y = 360-i*45
        c.setFont(BOLD,12);c.setFillColor(NAVY);c.drawString(55,y,x["country"])
        c.setFillColor(LIGHT);c.roundRect(112,y-4,600,20,4,fill=1,stroke=0)
        c.setFillColor(TEAL if x["country"] in ("CZE","ESP") else colors.HexColor("#7FAAB1"))
        c.roundRect(112,y-4,600*x["contribution_eur"]/maxval,20,4,fill=1,stroke=0)
        c.setFillColor(NAVY);c.setFont(BOLD,12);c.drawRightString(855,y+1,eur(x["contribution_eur"]))
    slide_text(c,54,84,"209 eligible orders in every market; contribution differences reflect units and economics, not an observed order-count gap. [C1, A1]",845,11,GRAY)
    c.showPage()
    # Slide 3
    draw_slide_common(c,3,"CZE+ESP wins the client volume cases", "Annual incremental contribution after recurring costs")
    labels = ["CZE+ESP","POL+ESP","NLD+ESP","ESP","DEFER"]
    xs = [48,223,398,573,748]
    for idx, name in enumerate(labels):
        x = xs[idx]
        b,s = by_option(name,"base"),by_option(name,"stress")
        c.setFillColor(PALE if name == "CZE+ESP" else LIGHT)
        c.roundRect(x,115,167,300,8,fill=1,stroke=0)
        c.setFillColor(NAVY);c.setFont(BOLD,14);c.drawCentredString(x+83,383,name)
        c.setFont(FONT,10);c.setFillColor(GRAY);c.drawCentredString(x+83,357,"BASE")
        c.setFont(BOLD,19);c.setFillColor(TEAL);c.drawCentredString(x+83,328,eur(b["incremental_contribution_eur"]))
        c.setFont(FONT,10);c.setFillColor(GRAY);c.drawCentredString(x+83,281,"STRESS")
        c.setFont(BOLD,18);c.setFillColor(RED if s["incremental_contribution_eur"] < 0 else NAVY);c.drawCentredString(x+83,251,eur(s["incremental_contribution_eur"]))
        c.setStrokeColor(colors.HexColor("#D7E2E6"));c.line(x+16,220,x+151,220)
        c.setFont(FONT,11);c.setFillColor(INK);c.drawCentredString(x+83,192,f"Capex {eur(b['capex_eur'])}")
        c.drawCentredString(x+83,166,f"{b['fte']} FTE")
        c.drawCentredString(x+83,140,"Defer" if name=="DEFER" else f"{b['payback_years']:.2f}y payback")
    slide_text(c,52,85,"Eleven of 15 pairs are feasible under ≤€450k capex, ≤7 FTE and ≤2 hubs. Full pair and single screens are in the workbook. [C2, A2]",842,11,GRAY)
    c.showPage()
    # Slide 4
    draw_slide_common(c,4,"Stress changes the second-hub choice", "Trade-off and flip condition")
    slide_card(c,55,256,398,148,"CZE+ESP base / stress","€198k / €32k","€225k capex • 5 FTE • stronger low/base/high",TEAL)
    slide_card(c,505,256,398,148,"NLD+ESP base / stress","€167k / €108k","€270k capex • 6 FTE • strongest stress",ORANGE)
    slide_text(c,62,217,"CZE costs €45k less and yields €31k more annual base contribution; NLD protects €75k more annual contribution in the defined stress.",832,16,NAVY)
    c.setFillColor(PALE);c.roundRect(55,71,848,91,8,fill=1,stroke=0)
    slide_text(c,75,146,"<b>Switching condition:</b> ~29.2% of the defined joint stress bundle erases Czechia’s second-hub advantage over the Netherlands. This is a sensitivity threshold, not a forecast probability.",805,14,INK)
    c.showPage()
    # Slide 5
    draw_slide_common(c,5,"Make the second commitment earned", "90-day implementation gates")
    stages = [
        ("0–15","COO + Finance","Reconcile ledger; approve Spain charter and spend ceiling.","Signed plan; €0 ledger difference"),
        ("16–30","Spain operations","Quote site/3PL, carrier routing and reverse logistics.","Cost and saving check"),
        ("31–60","Spain + Commercial","Pilot dispatch; test Czechia carrier and order economics.","≥95% on-time; ≥98% scans"),
        ("61–90","CFO + board sponsor","Scale Spain; release CZE, choose NLD or defer.","Revised economics and risk gate"),
    ]
    for i,(days,owner,work,gate) in enumerate(stages):
        x=43+i*220
        c.setFillColor(PALE if i in (0,3) else LIGHT);c.roundRect(x,114,205,303,8,fill=1,stroke=0)
        c.setFillColor(TEAL);c.setFont(BOLD,24);c.drawString(x+16,376,days)
        slide_text(c,x+16,340,owner,173,13,NAVY,True)
        slide_text(c,x+16,287,work,173,12,INK)
        c.setStrokeColor(TEAL);c.line(x+16,214,x+189,214)
        slide_text(c,x+16,198,"GATE: "+gate,173,11,TEAL,True)
    slide_text(c,48,85,"Owners are proposed roles. Day-60 evidence can validate operating economics; it cannot prove the annual uplift. [A2]",850,11,GRAY)
    c.showPage()
    # Slide 6
    draw_slide_common(c,6,"Manage the value drivers visibly", "KPI and risk controls")
    kpis=[("Dispatch","On-time dispatch ≥95% weekly","Spain lead"),
          ("Unit savings","Verify €3.0/Spain and €2.1/Czechia per unit","Finance"),
          ("Returns","Returned units and refund/gross by sale cohort","Finance + Quality"),
          ("Contribution","Monthly run-rate net of recurring fixed cost","CFO"),
          ("Data quality","Unmatched IDs quarantined; €0 reconciliation","Data lead")]
    for i,(name,definition,owner) in enumerate(kpis):
        y=394-i*68
        c.setFillColor(LIGHT if i%2==0 else WHITE);c.roundRect(50,y-39,860,57,5,fill=1,stroke=0)
        c.setFillColor(NAVY);c.setFont(BOLD,13);c.drawString(65,y-5,name)
        slide_text(c,245,y+7,definition,430,11,INK)
        c.setFont(FONT,10);c.setFillColor(GRAY);c.drawRightString(888,y-6,owner)
    slide_text(c,54,71,"Largest uncertainty: assumed uplift and savings. Use actual routing, cost, return and FX evidence before Czechia capex release. [A2]",848,11,ORANGE,True)
    c.showPage()
    # Slide 7
    draw_slide_common(c,7,"Decision conditions and evidence", "Board record")
    slide_text(c,54,423,"<b>Authorize:</b> Spain launch now; up to €95k Czechia only after the day-60 gate. Keep NLD+ESP as the defined-stress fallback and preserve the right to defer.",846,20,NAVY)
    c.setFillColor(PALE);c.roundRect(52,198,850,140,8,fill=1,stroke=0)
    slide_text(c,72,318,"Evidence states",805,14,NAVY,True)
    slide_text(c,72,288,"<b>Computed:</b> 2025 ledger, scenario arithmetic, feasibility. <b>Observed public archive:</b> 2022–24 World Bank and 2025 ECB. <b>Assumed:</b> 10/25/40% uplift, per-unit savings, fixed costs and stress. <b>Missing:</b> actual cash FX, site quotes, route baseline, customer demand validation.",805,13,INK)
    slide_text(c,55,157,"Source key: [C1] synthetic order/return/cost files; [C2] synthetic hub options; [A1–A2] client rules; [P1–P2] archived World Bank; [E1] archived ECB. Full URLs, hashes and vintages: evidence/source_register.csv.",846,11,GRAY)
    slide_text(c,55,93,"The modeled choice is conditional, not statistically proven or causal. Preserve cutoff and orphan-return quarantine when refreshing the case.",845,12,ORANGE,True)
    c.showPage()
    c.save()


def main():
    make_workbook()
    make_report()
    make_deck()
    print("Wrote", *(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
