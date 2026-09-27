#!/usr/bin/env python3
"""Build the board-ready workbook, report and deck from metrics.json."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence" / "raw"
OUT = ROOT / "deliverables"
EVIDENCE = ROOT / "evidence"
DATA = json.loads((OUT / "metrics.json").read_text())
CS = {r["country"]: r for r in DATA["countries"]}
SC = {(r["country"], r["scenario"]): r for r in DATA["hub_scenarios"]}
COUNTRIES = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
NAVY = "#11243A"
BLUE = "#17659A"
TEAL = "#087E8B"
GOLD = "#E3A33D"
PALE = "#EAF3F6"
GRAY = "#536275"
RED = "#B44B50"


def eur(v, decimals=0):
    return f"€{v:,.{decimals}f}"


def pct(v, decimals=1):
    return f"{100*v:.{decimals}f}%"


def source_register():
    archive = json.loads((RAW / "source-register.json").read_text())
    public = {r["file"]: r for r in archive["public"]}
    inventory = {
        "index.html": ("Source-room index", "site index", "metadata"),
        "data-dictionary.md": ("Accounting definitions", "2025 shipments, returns through 2026-01-31", "synthetic_client"),
        "scenario-policy.md": ("Scenario method and stress assumptions", "annual model", "synthetic_client"),
        "orders-part1.csv": ("order rows; local currency and EUR fulfillment", "2025-2026", "synthetic_client"),
        "orders-part2.csv": ("order rows; local currency and EUR fulfillment", "2025-2026", "synthetic_client"),
        "order-corrections.csv": ("replacement order rows", "2025", "synthetic_client"),
        "returns.csv": ("physical units and original-currency refunds", "received through 2026-02-01", "synthetic_client"),
        "unit-costs.csv": ("EUR per unit, effective-dated", "2025", "synthetic_client"),
        "hub-options.csv": ("EUR capex/fixed/savings; FTE", "annual model", "synthetic_client"),
        "population.json": ("persons", "2022-2024", "official_public_snapshot"),
        "gdp-per-capita.json": ("current USD per person", "2022-2024", "official_public_snapshot"),
        "ecb-history.zip": ("local currency units per EUR", "ECB daily historical series; 2025 used", "official_public_snapshot"),
        "ecb-history.csv": ("local currency units per EUR", "ECB daily historical series; 2025 used", "official_public_snapshot"),
        "source-register.json": ("original URL, archive retrieval and hash", "archive vintage 2026-09-27", "metadata"),
    }
    register = []
    for name, (units, period, status) in inventory.items():
        path = RAW / name
        if not path.exists():
            raise FileNotFoundError(path)
        content = path.read_bytes()
        p = public.get(name, {})
        origin = public.get(p.get("derived_from", ""), p) if p.get("derived_from") else p
        digest = hashlib.sha256(content).hexdigest()
        if p and digest != p["sha256"]:
            raise ValueError(f"Archived hash mismatch: {name}")
        register.append({
            "file": f"evidence/raw/{name}", "room_url": f"http://127.0.0.1:49684/{name if name != 'index.html' else ''}",
            "original_public_url": origin.get("original_url", ""),
            "room_collected_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "archive_retrieved_utc": origin.get("retrieved_utc", ""),
            "sha256": digest, "bytes": len(content), "units": units, "period": period,
            "status": status, "derived_from": p.get("derived_from", ""),
        })
    (EVIDENCE / "source_register.json").write_text(json.dumps(register, indent=2) + "\n")
    with (EVIDENCE / "source_register.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(register[0]))
        w.writeheader(); w.writerows(register)
    return register


def workbook(register):
    path = OUT / "meridian_analysis.xlsx"
    wb = xlsxwriter.Workbook(path)
    wb.set_properties({"title": "Meridian Parts European hub decision", "subject": "2025 shipment reconciliation and hub scenarios", "author": "Operations analysis"})
    f_title = wb.add_format({"bold": 1, "font_size": 17, "font_color": "#FFFFFF", "bg_color": NAVY, "valign": "vcenter"})
    f_sub = wb.add_format({"font_size": 10, "font_color": GRAY, "text_wrap": True, "valign": "top"})
    f_header = wb.add_format({"bold": 1, "font_color": "#FFFFFF", "bg_color": BLUE, "text_wrap": True, "valign": "vcenter", "border": 0})
    f_text = wb.add_format({"font_color": NAVY})
    f_wrap = wb.add_format({"font_color": NAVY, "text_wrap": True, "valign": "top"})
    f_money = wb.add_format({"num_format": '#,##0.00;[Red](#,##0.00)', "font_color": NAVY})
    f_int = wb.add_format({"num_format": '#,##0', "font_color": NAVY})
    f_rate = wb.add_format({"num_format": '0.000000', "font_color": NAVY})
    f_pct = wb.add_format({"num_format": '0.0%', "font_color": NAVY})
    f_pay = wb.add_format({"num_format": '0.00', "font_color": NAVY})
    f_total = wb.add_format({"bold": 1, "bg_color": PALE, "num_format": '#,##0.00;[Red](#,##0.00)'})
    f_note = wb.add_format({"bg_color": PALE, "text_wrap": True, "valign": "top", "font_color": NAVY})

    def sheet(name, title, subtitle, headers, data, widths=None, formats=None, table=True):
        ws = wb.add_worksheet(name)
        ws.hide_gridlines(2)
        ws.merge_range(0, 0, 0, max(2, len(headers)-1), title, f_title)
        ws.set_row(0, 31)
        ws.merge_range(1, 0, 2, max(2, len(headers)-1), subtitle, f_sub)
        ws.set_row(1, 23); ws.set_row(2, 21)
        for col, h in enumerate(headers):
            ws.write(4, col, h, f_header)
            ws.set_column(col, col, (widths or {}).get(col, 16))
        ws.set_row(4, 34)
        for ri, record in enumerate(data, 5):
            for col, value in enumerate(record):
                fmt = (formats or {}).get(col, f_text)
                if value is None:
                    ws.write_blank(ri, col, None, fmt)
                else:
                    ws.write(ri, col, value, fmt)
        ws.freeze_panes(5, 1)
        if table and data:
            ws.autofilter(4, 0, 4 + len(data), len(headers)-1)
        ws.set_landscape(); ws.fit_to_pages(1, 0)
        ws.set_header('&CMeridian Parts | Board analysis')
        ws.set_footer('&CPage &P of &N')
        return ws

    notes = [
        ("Decision", "Stage ESP first; release CZE only after day-90 gate. Pair base €198,099/year, stress €32,180/year; €225,000 capex and 5 FTE."),
        ("Scope", "2025 shipped orders; returns received through 2026-01-31 inclusive. One row per highest-revision order ID; legitimate zero-price orders retained."),
        ("Accounting", "Gross = units × local price − discount; refunds summed by original order; both translated with original sale-month ECB local units per EUR. Per-order EUR components rounded half-up to cents, then summed."),
        ("Contribution", "Net sales − net COGS − actual nonrefundable fulfillment. Net COGS recovers only restocked units. This is neither cash flow nor GAAP profit."),
        ("Scenario", "Annual incremental = C×u + U×(1+u)×saving − fixed. Stress = (C−3% gross−10% net sales for PLN/CZK)×1.25 − C + U×1.25×saving − fixed. Capex is year zero; payback only when annual increment >0."),
        ("Sources", "All raw inputs, original official URLs, retrieval vintages, hashes, units and periods are in evidence/source_register.csv. Official series are archived snapshots; client data and policies are synthetic."),
        ("Limits", "Uplift and savings are assumptions, not causal estimates. No service-time, distance, capacity, tax, financing, working-capital or 2026 demand forecast is supplied."),
    ]
    sheet("Read me", "Meridian Parts | decision workbook", "Use the tabs for audited records, country and monthly results, archived context, scenario comparisons and source/quality evidence.", ["Topic", "Guidance"], notes, {0: 19, 1: 115}, {1: f_wrap})
    annual_headers = ["Country", "Shipped orders", "Shipped units", "Gross sales EUR", "Refunds EUR", "Net sales EUR", "Net COGS EUR", "Fulfillment EUR", "Contribution EUR", "Returned units", "Margin"]
    annual_data = [[r[k] for k in ("country", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin")] for r in DATA["countries"]]
    ws = sheet("Annual", "2025 contribution by market", "EUR after returns known through 31 Jan 2026. Each annual column reconciles exactly to the 12 sale-month rows in Monthly.", annual_headers, annual_data, {0: 12, 1: 15, 2: 15, 3: 20, 4: 16, 5: 19, 6: 18, 7: 19, 8: 21, 9: 17, 10: 14}, {1:f_int,2:f_int,3:f_money,4:f_money,5:f_money,6:f_money,7:f_money,8:f_money,9:f_int,10:f_pct})
    total_row = 5 + len(annual_data)
    ws.write(total_row, 0, "TOTAL", f_total)
    for col in range(1, 10):
        ws.write_formula(total_row, col, f"=SUM({xlsxwriter.utility.xl_col_to_name(col)}6:{xlsxwriter.utility.xl_col_to_name(col)}{total_row})", f_total, sum(float(r[col]) for r in annual_data))
    total_net = sum(r["net_sales_eur"] for r in DATA["countries"])
    total_cont = sum(r["contribution_eur"] for r in DATA["countries"])
    ws.write_formula(total_row, 10, f"=I{total_row+1}/F{total_row+1}", f_pct, total_cont/total_net)
    chart = wb.add_chart({"type": "bar"})
    chart.add_series({"name": "2025 contribution", "categories": "=Annual!$A$6:$A$11", "values": "=Annual!$I$6:$I$11", "fill": {"color": TEAL}, "border": {"none": True}})
    chart.set_title({"name": "Contribution by market"}); chart.set_x_axis({"name": "EUR", "num_format": '#,##0'}); chart.set_legend({"none": True}); chart.set_style(10)
    ws.insert_chart("M5", chart, {"x_scale": 1.2, "y_scale": 1.15})

    monthly_headers = ["Country", "Sale month"] + annual_headers[1:]
    monthly_data = [[r[k] for k in ("country", "month", "shipped_orders", "shipped_units", "gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur", "returned_units", "margin")] for r in DATA["monthly"]]
    sheet("Monthly", "Monthly shipment-cohort economics", "Refunds are assigned to the original sale month, not the return receipt month. EUR values are sums of per-order rounded components.", monthly_headers, monthly_data, {0:12,1:14,2:14,3:14,4:19,5:17,6:19,7:18,8:19,9:21,10:15,11:13}, {2:f_int,3:f_int,4:f_money,5:f_money,6:f_money,7:f_money,8:f_money,9:f_money,10:f_int,11:f_pct})

    fx_data = [[r["currency"], r["month"], r["local_per_eur"], r["observation_days"]] for r in DATA["fx_monthly"]]
    sheet("FX", "ECB 2025 monthly means", "Arithmetic mean of available published business-day rates. Quote is local currency units per EUR. EUR sales use 1. These are analytical translation rates, not realized transaction FX.", ["Currency", "Month", "Local units / EUR", "Observation days"], fx_data, {0:14,1:15,2:23,3:19}, {2:f_rate,3:f_int})

    market_data = [[r["country"],r["year"],r["population"],r["gdp_per_capita_usd"]] for r in DATA["market_context"]]
    ws = sheet("Market context", "Archived World Bank market context", "Population = persons; GDP per capita = current US$, not PPP or real income. Snapshot fetched 27 Sep 2026; World Bank response lastupdated 13 Jul 2026. Neither series proves product demand.", ["Country","Year","Population persons","GDP per capita current US$"], market_data, {0:14,1:12,2:24,3:30}, {1:f_int,2:f_int,3:f_money})
    ws.write(25,0,"2022–24 population change", f_header)
    ws.write(25,1,"Percent", f_header)
    for i,c in enumerate(COUNTRIES,26):
        vals = [r for r in DATA["market_context"] if r["country"]==c]
        change = vals[-1]["population"]/vals[0]["population"]-1 if vals[0]["population"] and vals[-1]["population"] else None
        ws.write(i,0,c); ws.write(i,1,change,f_pct)

    with (RAW/"hub-options.csv").open(newline="") as f:
        opts = list(csv.DictReader(f))
    options_data = [[r["country"],int(r["capex_eur"]),int(r["fte"]),int(r["annual_fixed_eur"]),float(r["saving_eur_per_unit"])] for r in opts]
    sheet("Hub inputs", "Synthetic client hub options", "Capex is spent in year zero; recurring fixed cost is deducted from annual incremental contribution. Savings are per shipped unit, including uplifted units.", ["Country","Capex EUR","FTE","Annual fixed EUR","Saving EUR/unit"], options_data, {0:14,1:18,2:12,3:22,4:22}, {1:f_money,2:f_int,3:f_money,4:f_money})

    scenario_data = [[r["country"],r["scenario"],r["incremental_contribution_eur"],r["capex_eur"],r["fte"],r["payback_years"]] for r in DATA["hub_scenarios"]]
    sheet("Scenarios", "All feasible hub configurations", "All single hubs and capex/FTE-feasible pairs; additive, with no synergy. DEFER is the zero-investment comparator. Payback is simple, undiscounted and blank when annual contribution is nonpositive.", ["Configuration","Scenario","Incremental annual EUR","Year-zero capex EUR","FTE","Payback years"], scenario_data, {0:20,1:15,2:26,3:23,4:12,5:19}, {2:f_money,3:f_money,4:f_int,5:f_pay})

    configs = sorted({r["country"] for r in DATA["hub_scenarios"]}, key=lambda c:-SC[(c,"base")]["incremental_contribution_eur"])
    decision_data = [[c,SC[(c,"low")]["incremental_contribution_eur"],SC[(c,"base")]["incremental_contribution_eur"],SC[(c,"high")]["incremental_contribution_eur"],SC[(c,"stress")]["incremental_contribution_eur"],SC[(c,"base")]["capex_eur"],SC[(c,"base")]["fte"],SC[(c,"base")]["payback_years"]] for c in configs]
    ws = sheet("Decision", "Ranked feasible alternatives", "Sorted by base annual increment. Stress combines +3% gross-sales refunds with 10% net-sales depreciation for PLN/CZK markets. This is a conservative joint case, not a probability-weighted forecast.", ["Configuration","Low EUR/yr","Base EUR/yr","High EUR/yr","Stress EUR/yr","Capex EUR","FTE","Base payback yr"], decision_data, {0:20,1:20,2:20,3:20,4:20,5:18,6:12,7:20}, {1:f_money,2:f_money,3:f_money,4:f_money,5:f_money,6:f_int,7:f_pay})
    ws.conditional_format(5,4,4+len(decision_data),4,{"type":"cell","criteria":"<","value":0,"format":wb.add_format({"font_color":RED,"bg_color":"#FCE9E9"})})
    chart = wb.add_chart({"type":"bar"})
    for col,name,color in [(2,"Base",TEAL),(4,"Stress",GOLD)]:
        chart.add_series({"name":name,"categories":"=Decision!$A$6:$A$13","values":f"=Decision!${xlsxwriter.utility.xl_col_to_name(col)}$6:${xlsxwriter.utility.xl_col_to_name(col)}$13","fill":{"color":color},"border":{"none":True}})
    chart.set_title({"name":"Top eight: base vs joint stress"}); chart.set_x_axis({"name":"Incremental EUR/year","num_format":"#,##0"}); chart.set_legend({"position":"bottom"}); chart.set_style(10)
    ws.insert_chart("J5",chart,{"x_scale":1.45,"y_scale":1.45})

    q = DATA["quality"]
    quality_rows = [("Raw order rows",q["raw_order_rows"]),("Distinct order IDs",q["distinct_order_ids"]),("Identical duplicate order rows",q["identical_order_duplicates"]),("Superseded order revisions",q["superseded_order_revisions"])]
    quality_rows += [(f"Excluded order: {k}",v) for k,v in q["order_exclusions"].items()]
    quality_rows += [("Eligible 2025 orders",q["eligible_2025_orders"]),("Valid zero-price shipments",q["valid_zero_price_shipped_orders"]),("Raw return rows",q["raw_return_rows"]),("Distinct return IDs",q["distinct_return_ids"]),("Identical duplicate return rows",q["identical_return_duplicates"]),("Superseded return revisions",q["superseded_return_revisions"])]
    quality_rows += [(f"Excluded return: {k}",v) for k,v in q["return_exclusions"].items()]
    quality_rows += [("Eligible return IDs",q["eligible_return_ids"]),("Returned units",q["eligible_returned_units"]),("Restocked units",q["eligible_restocked_units"])]
    quality_rows += [(f"Missing: {k}",v) for k,v in q["missing_values"].items()]
    quality_rows += [("Missing-value handling",q["missing_value_handling"])]
    quality_rows += [("Reconciliation",q["reconciliation"]),("Synthetic-pattern caution","Exactly 209 eligible orders per market; treat this balanced pattern as synthetic design, not market evidence.")]
    sheet("Quality", "Reconciliation and exceptions", "Rows count raw export records, not orders. Quarantined return IDs are not guessed onto orders. Corrected rows replace whole rows.", ["Check","Result / handling"], quality_rows, {0:39,1:100}, {1:f_wrap})

    reg_data = [[r[k] for k in ("file","status","units","period","room_collected_utc","archive_retrieved_utc","original_public_url","sha256")] for r in register]
    sheet("Sources", "Frozen source register", "Public official series were collected from the source room, which preserves their original URLs and archive vintage. Synthetic client records are separate from public observations.", ["Saved file","Status","Units","Period","Room collected UTC","Archive retrieved UTC","Original public URL","SHA-256"], reg_data, {0:35,1:25,2:38,3:34,4:30,5:30,6:85,7:69}, {0:f_wrap,1:f_wrap,2:f_wrap,3:f_wrap,4:f_wrap,5:f_wrap,6:f_wrap,7:f_wrap})
    wb.close()
    return path


def report(register):
    path = OUT/"executive_report.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=16*mm, leftMargin=16*mm, topMargin=17*mm, bottomMargin=16*mm,
                            title="Meridian Parts | European service hub decision", author="Operations analysis")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleX",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=20,leading=23,textColor=colors.HexColor(NAVY),spaceAfter=7))
    styles.add(ParagraphStyle(name="SubX",parent=styles["Normal"],fontSize=10.2,leading=14,textColor=colors.HexColor(GRAY),spaceAfter=11))
    styles.add(ParagraphStyle(name="HeadX",parent=styles["Heading2"],fontSize=12.2,leading=15,textColor=colors.HexColor(BLUE),spaceBefore=12,spaceAfter=5))
    styles.add(ParagraphStyle(name="BodyX",parent=styles["BodyText"],fontSize=9.3,leading=13,spaceAfter=7,textColor=colors.HexColor(NAVY)))
    styles.add(ParagraphStyle(name="SmallX",parent=styles["BodyText"],fontSize=7.6,leading=10.2,spaceAfter=5,textColor=colors.HexColor(GRAY)))
    styles.add(ParagraphStyle(name="CellX",fontName="Helvetica",fontSize=7.6,leading=9.7,textColor=colors.HexColor(NAVY)))
    styles.add(ParagraphStyle(name="CellH",fontName="Helvetica-Bold",fontSize=7.5,leading=9.5,textColor=colors.white))
    story=[]
    def P(t,style="BodyX"):
        story.append(Paragraph(t,styles[style]))
    def H(t): P(t,"HeadX")
    def tab(headers, records, widths, aligns=None):
        arr=[[Paragraph(str(x),styles["CellH"]) for x in headers]]
        arr += [[Paragraph(str(x),styles["CellX"]) for x in row] for row in records]
        t=Table(arr,colWidths=widths,repeatRows=1,hAlign="LEFT")
        ts=[("BACKGROUND",(0,0),(-1,0),colors.HexColor(BLUE)),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F5F7")]),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),("LINEBELOW",(0,0),(-1,0),0.5,colors.HexColor(NAVY))]
        if aligns:
            for col in aligns: ts.append(("ALIGN",(col,1),(col,-1),"RIGHT"))
        t.setStyle(TableStyle(ts)); story.append(t); story.append(Spacer(1,5*mm))

    P("European service-hub expansion | board decision","TitleX")
    P("Meridian Parts • 2025 shipped-sale base • returns known through 31 January 2026 • 27 September 2026 source-room archive","SubX")
    H("Recommendation")
    P("<b>Authorize a staged Spain (ESP) then Czechia (CZE) program, capped at €225,000 of year-zero capex and five FTE.</b> Start ESP first; release the €95,000 CZE commitment only at a day-90 gate. In the client’s base assumption, the pair adds <b>€198,099 per year after recurring fixed costs</b> and has <b>1.14-year simple payback</b>. The joint return/FX stress leaves only €32,180 per year, a 6.99-year payback, so the second commitment must be conditional. [S1–S5]")
    P("At the gate, update the CZE model from actual return credits, restocking, local-currency exposure and signed operating costs. Release CZE only if annualized incremental contribution exceeds €47,500 (under two-year simple payback), service capacity is validated and no persistent joint stress is evident. Otherwise operate ESP alone and defer CZE. This threshold is a board decision rule, not a statistical confidence bound.")
    H("What the 2025 records show")
    total={k:sum(c[k] for c in DATA["countries"]) for k in ["shipped_orders","shipped_units","gross_sales_eur","refunds_eur","net_sales_eur","net_cogs_eur","fulfillment_eur","contribution_eur","returned_units"]}
    P(f"Across six markets, {total['shipped_orders']:,} eligible shipped orders ({total['shipped_units']:,} units) generated {eur(total['gross_sales_eur'],2)} gross sales, {eur(total['refunds_eur'],2)} refunds and {eur(total['net_sales_eur'],2)} net sales. After {eur(total['net_cogs_eur'],2)} net COGS and {eur(total['fulfillment_eur'],2)} actual fulfillment cost, contribution was <b>{eur(total['contribution_eur'],2)}</b>. Returned units were {total['returned_units']:,}, of which 481 were restocked. This is a shipment-cohort contribution view; it excludes hub fixed cost, capex, financing, tax and working capital. [S1–S4]")
    country_rows=[]
    for c in COUNTRIES:
        r=CS[c]
        country_rows.append([c, f"{r['shipped_orders']:,}",f"{r['shipped_units']:,}",eur(r['net_sales_eur']),eur(r['contribution_eur']),pct(r['margin']),str(r['returned_units'])])
    tab(["Market","Orders","Units","Net sales","Contribution","Margin","Returned units"],country_rows,[20*mm,19*mm,18*mm,32*mm,32*mm,20*mm,27*mm])
    P("ESP and CZE have the highest 2025 contribution (€421,900 and €397,335) and margins (49.6% and 48.7%) in this synthetic export. This describes the existing sales mix and fulfillment economics; it does not establish that local hubs cause volume growth. Monthly detail and all per-order conversions are in the workbook and order audit. [S2–S4]","SmallX")

    H("Reconciliation and accounting controls")
    q=DATA["quality"]
    P(f"The two order pages and correction file contain {q['raw_order_rows']:,} rows: {q['distinct_order_ids']:,} distinct IDs, {q['identical_order_duplicates']} identical repeats and {q['superseded_order_revisions']} superseded revisions. After selecting each ID’s highest revision, 24 cancelled, 18 test and one 2026 shipment are excluded; {q['eligible_2025_orders']:,} orders remain, including 12 valid zero-price shipments. All 24 blank raw shipment dates belong to cancelled records. The returns file has {q['raw_return_rows']} rows, 20 identical repeats and one superseded revision; one 1 February return and one orphan ID are quarantined, leaving 241 eligible return IDs. All six annual columns reconcile to monthly rows; no eligible shipment date, return field, effective cost or World Bank value is missing. [S1–S4]")
    P("Gross sales are booked shipment values net of discounts, excluding tax. A refund is an explicit later credit linked to that shipment, assigned to its original sale month; booked net sales therefore differ from contemporaneous cash receipts or collections. Contribution subtracts net product COGS and nonrefundable fulfillment; cost is recovered only on physically restocked units. Both sales and refunds use the original sale-month ECB mean quote, local currency per EUR; components are rounded per order half-up before aggregation. The rates are an analytical translation proxy, not realized settlement rates. [S1, S4, S6]")

    story.append(PageBreak())
    H("Market context: scale and currency, not demand proof")
    market_rows=[]
    for c in COUNTRIES:
        vals=[r for r in DATA["market_context"] if r["country"]==c]
        change=vals[2]["population"]/vals[0]["population"]-1
        market_rows.append([c,f"{vals[0]['population']/1e6:.2f}",f"{vals[2]['population']/1e6:.2f}",pct(change,2),f"${vals[2]['gdp_per_capita_usd']:,.0f}"])
    tab(["Market","2022 pop m","2024 pop m","Pop change","2024 GDP/head current US$"],market_rows,[24*mm,29*mm,29*mm,30*mm,56*mm])
    P("The archived World Bank responses cover 2022–2024, with response lastupdated 13 July 2026 and archive retrieval 27 September 2026. Population rose most in ESP (+2.22%) and fell in POL (−0.71%); 2024 GDP per capita ranged from $25,104 in POL to $67,465 in NLD. Current-dollar GDP per capita is affected by prices and exchange rates and is not a product-demand measure. The archived ECB 2025 monthly PLN and CZK means are in the workbook; original quotes are never inverted. [S6–S8]","SmallX")

    P("Investment case","TitleX")
    P("Feasible alternatives are constrained to at most two hubs, €450,000 capex and seven FTE; no pair synergy is assumed.","SubX")
    H("Comparable scenario economics")
    selected=["CZE+ESP","POL+ESP","NLD+ESP","POL+CZE","ESP","CZE","DEFER"]
    sc_rows=[]
    for c in selected:
        base=SC[(c,"base")]
        sc_rows.append([c,eur(SC[(c,"low")]["incremental_contribution_eur"]),eur(base["incremental_contribution_eur"]),eur(SC[(c,"high")]["incremental_contribution_eur"]),eur(SC[(c,"stress")]["incremental_contribution_eur"]),eur(base["capex_eur"]),str(base["fte"]),f"{base['payback_years']:.2f}" if base["payback_years"] else "—"])
    tab(["Option","Low €/yr","Base €/yr","High €/yr","Stress €/yr","Capex","FTE","Payback yr"],sc_rows,[23*mm,25*mm,25*mm,25*mm,25*mm,21*mm,10*mm,14*mm])
    P("Low/base/high assume 10%/25%/40% volume uplift. For each market, annual incremental contribution is baseline contribution × uplift + uplifted units × per-unit saving − annual fixed cost. Stress keeps 25% uplift, adds refunds of 3% of gross sales without COGS recovery, and for PLN/CZK deducts 10% of net sales as a depreciation proxy before comparing with the unchanged baseline. Year-zero capex is excluded from annual contribution. These are client assumptions, not forecasts or causal hub effects. [S5]")
    P("The highest base alternative is POL+ESP at €186,329/year, €240,000 capex, six FTE and 1.29-year payback. CZE+ESP is €11,770/year higher with €15,000 less capex and one fewer FTE, and also leads POL+ESP in low, high and stress cases. NLD+ESP has the strongest joint-stress result (€107,630/year) but a €31,168 lower base outcome, €45,000 more capex and one more FTE than CZE+ESP. ESP alone is the lower-commitment alternative: €102,716/year base, €70,007/year stress and €130,000 capex. Under persistent stress, CZE contributes −€37,827/year; defer it and reassess NLD as a second hub. With a 3% gross-sales refund shock, a CZE FX deduction above 1.63% of net sales fails the two-year payback gate; above 6.29% makes its annual increment negative. These are model thresholds, not predicted exchange moves. [S4–S5]")
    story.append(PageBreak())
    P("Execution and control","TitleX")
    H("90-day staged execution")
    plan=[
      ["0–30","COO + finance","Confirm ESP site/service footprint, lease/3PL terms, SKU capacity and capex; validate shipment, return and FX mappings against invoices.","Gate 1: signed cost envelope ≤€130k capex, three FTE plan, data sign-off."],
      ["31–60","ESP operations lead + IT","Configure inventory, scan-to-ship and returns workflow; train team; run parallel order routing and daily reconciliation.","Gate 2: test orders reconcile; dispatch and returns controls pass."],
      ["61–90","COO + FP&A + CZE lead","Pilot ESP with controlled routing; collect service, unit savings, returns and quality evidence; hold a cancellable CZE option and screen NLD as fallback.","Gate 3: ESP pilot KPI review; release CZE only if updated CZE annual increment >€47.5k and capacity/FX checks pass."],
    ]
    tab(["Days","Owner","Actions / dependencies","Decision gate"],plan,[18*mm,34*mm,77*mm,39*mm])
    H("KPI plan and risks")
    P("Measure weekly by country and shipment cohort: on-time local delivery, median order-to-delivery hours, eligible units routed through each hub, actual fulfillment €/unit versus 2025 baseline, gross-to-net refund rate, returned and restocked units, inventory fill rate and 30-day contribution per shipped order. Use the first 30 pilot days to establish a clean pre/post service baseline; FP&A recalculates monthly annualized incremental contribution from observed volumes and signed fixed costs. Review at days 30, 60 and 90, then monthly for two quarters. Targets for the gate: ≥95% on-time dispatch, ≥98% inventory accuracy, no deterioration in refund rate versus the corresponding 2025 cohort, and CZE modeled payback <2 years. Service targets are management thresholds, not source-room observations.")
    P("Key risks are volume uplift failing to materialize, local-currency depreciation, higher refunds with poor restocking, inventory duplication, labor/site cost creep and service disruption during routing. Mitigations are capped contracts, ESP-first controlled rollout, weekly cohort tracking and a cancellable CZE option. The source room has no direct delivery-time, capacity, customer willingness-to-pay or realized FX data, so the case cannot quantify service causality or a discounted NPV. [S1–S8]")
    story.append(PageBreak())
    P("Scenario and evidence appendix","TitleX")
    H("All feasible configurations: base-case ranking")
    ranked=sorted({r["country"] for r in DATA["hub_scenarios"]},key=lambda x:-SC[(x,"base")]["incremental_contribution_eur"])
    all_rows=[]
    for name in ranked:
        b=SC[(name,"base")]; s=SC[(name,"stress")]
        all_rows.append([name,eur(b["incremental_contribution_eur"]),eur(s["incremental_contribution_eur"]),eur(b["capex_eur"]),str(b["fte"]),f"{b['payback_years']:.2f}" if b["payback_years"] else "—"])
    tab(["Configuration","Base €/yr","Stress €/yr","Capex","FTE","Base payback yr"],all_rows,[34*mm,34*mm,34*mm,25*mm,14*mm,27*mm])
    H("Evidence register")
    sources=[
      "[S1] evidence/raw/data-dictionary.md — synthetic accounting rules.",
      "[S2] evidence/raw/orders-part1.csv, orders-part2.csv, order-corrections.csv — synthetic order exports and revisions.",
      "[S3] evidence/raw/returns.csv and unit-costs.csv — synthetic return credits, restocking and costs.",
      "[S4] deliverables/order_audit.csv, monthly.csv, countries.csv; generated from saved raw files by scripts/analyze.py.",
      "[S5] evidence/raw/hub-options.csv and scenario-policy.md — synthetic board assumptions.",
      '[S6] evidence/raw/ecb-history.csv/.zip — archived ECB reference rates; <link href="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip" color="#17659A">original ECB archive</link>.',
      '[S7] evidence/raw/population.json — archived World Bank SP.POP.TOTL; <link href="https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&amp;format=json&amp;per_page=1000" color="#17659A">original World Bank endpoint</link>.',
      '[S8] evidence/raw/gdp-per-capita.json — archived World Bank NY.GDP.PCAP.CD; <link href="https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&amp;format=json&amp;per_page=1000" color="#17659A">original World Bank endpoint</link>.',
    ]
    for s in sources: P(s,"SmallX")
    P("The full source register records source-room collection time, original public URL, archived retrieval vintage, SHA-256, units, period and synthetic/public status. All figures can be rebuilt using README.md. The archive may contain later revisions of historical 2022–2024 indicators.","SmallX")
    def footer(c,doc):
        c.setStrokeColor(colors.HexColor("#D3DCE3")); c.line(16*mm,13*mm,194*mm,13*mm)
        c.setFont("Helvetica",7); c.setFillColor(colors.HexColor(GRAY))
        c.drawString(16*mm,9*mm,"Meridian Parts | synthetic client decision analysis")
        c.drawRightString(194*mm,9*mm,f"Page {doc.page}")
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    return path


def deck():
    path=OUT/"board_presentation.pdf"
    W,H=landscape(A4)
    c=canvas.Canvas(str(path),pagesize=(W,H),pageCompression=1)
    c.setTitle("Meridian Parts | Board decision on European service hubs")
    def base(num,title,kicker="BOARD DECISION | SEPTEMBER 2026"):
        c.setFillColor(colors.HexColor(NAVY)); c.rect(0,H-18*mm,W,18*mm,fill=1,stroke=0)
        c.setFillColor(colors.HexColor(GOLD)); c.setFont("Helvetica-Bold",8.5); c.drawString(14*mm,H-11*mm,kicker)
        c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica-Bold",22); c.drawString(14*mm,H-31*mm,title)
        c.setStrokeColor(colors.HexColor("#D5E0E7")); c.line(14*mm,12*mm,W-14*mm,12*mm)
        c.setFillColor(colors.HexColor(GRAY)); c.setFont("Helvetica",7.8)
        c.drawString(14*mm,8*mm,"Meridian Parts • synthetic client inputs + archived official series")
        c.drawRightString(W-14*mm,8*mm,f"{num} / 6")
    def textblock(x,y,width,lines,size=12,leading=17,color=NAVY):
        c.setFillColor(colors.HexColor(color)); c.setFont("Helvetica",size)
        for line in lines:
            if stringWidth(line,"Helvetica",size)>width:
                raise ValueError(f"Deck text overflow: {line}")
            c.drawString(x,y,line); y-=leading
        return y
    def box(x,y,w,h,label,value,sub="",fill=PALE):
        c.setFillColor(colors.HexColor(fill)); c.roundRect(x,y,w,h,5*mm,fill=1,stroke=0)
        c.setFillColor(colors.HexColor(GRAY)); c.setFont("Helvetica-Bold",9); c.drawString(x+5*mm,y+h-10*mm,label)
        c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica-Bold",22); c.drawString(x+5*mm,y+h-21*mm,value)
        c.setFont("Helvetica",8.5); c.drawString(x+5*mm,y+7*mm,sub)
    def page(): c.showPage()

    base(1,"Fund Spain first; gate Czechia at day 90")
    textblock(15*mm,H-45*mm,265*mm,["Authorize up to two hubs, but release the second commitment only after", "pilot evidence and an updated return/FX assessment."],14,21)
    box(15*mm,77*mm,81*mm,53*mm,"PAIR BASE INCREMENT", "€198k / year","after recurring fixed cost")
    box(105*mm,77*mm,81*mm,53*mm,"YEAR-ZERO CAPEX", "€225k","5 FTE; within board limits")
    box(195*mm,77*mm,81*mm,53*mm,"JOINT STRESS", "€32k / year","6.99-year simple payback")
    c.setFillColor(colors.HexColor(TEAL)); c.roundRect(15*mm,29*mm,261*mm,34*mm,4*mm,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold",12); c.drawString(21*mm,49*mm,"Day-90 CZE gate")
    c.setFont("Helvetica",10); c.drawString(21*mm,39*mm,"Release €95k only if updated annual increment >€47.5k and operations/FX checks pass.")
    page()

    base(2,"The 2025 base is profitable but synthetic")
    box(15*mm,116*mm,81*mm,49*mm,"ELIGIBLE SHIPMENTS","1,254 orders","77,436 units")
    box(105*mm,116*mm,81*mm,49*mm,"NET SALES","€4.384m","€80.8k refunds")
    box(195*mm,116*mm,81*mm,49*mm,"CONTRIBUTION","€2.030m","after net COGS and fulfillment")
    labels=["DEU","FRA","NLD","POL","CZE","ESP"]
    values=[CS[x]["contribution_eur"]/1000 for x in labels]
    x0,y0=35*mm,38*mm; maxv=450
    for i,(label,v) in enumerate(zip(labels,values)):
        y=y0+i*11*mm
        c.setFillColor(colors.HexColor(GRAY)); c.setFont("Helvetica-Bold",9); c.drawRightString(x0-4*mm,y+2*mm,label)
        c.setFillColor(colors.HexColor(TEAL if label in ("CZE","ESP") else BLUE)); c.rect(x0,y,170*mm*v/maxv,6*mm,fill=1,stroke=0)
        c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica",9); c.drawString(x0+170*mm*v/maxv+3*mm,y+1*mm,f"€{v:.0f}k")
    c.setFont("Helvetica",8.5); c.setFillColor(colors.HexColor(GRAY)); c.drawString(15*mm,23*mm,"Source: reconciled client exports [S1-S4]. Same 209 eligible orders in each market is a synthetic pattern.")
    page()

    base(3,"Revisions and returns materially change the base")
    lines=[
      ("1,328", "raw order rows across both pages and corrections"),
      ("1,297", "distinct order IDs after 13 identical repeats and 18 superseded rows"),
      ("1,254", "eligible 2025 shipments after 24 cancelled, 18 test and one 2026 shipment"),
      ("241", "eligible return IDs after 20 repeats, one revision, one late and one orphan"),
    ]
    for i,(big,detail) in enumerate(lines):
        y=H-(54+i*31)*mm
        c.setFillColor(colors.HexColor(TEAL)); c.setFont("Helvetica-Bold",20); c.drawString(17*mm,y,big)
        c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica",11); c.drawString(60*mm,y+2*mm,detail)
    c.setFillColor(colors.HexColor(PALE)); c.roundRect(15*mm,22*mm,260*mm,33*mm,4*mm,fill=1,stroke=0)
    textblock(21*mm,45*mm,250*mm,["Twelve valid zero-price shipments stay in units/orders. One orphan return is quarantined.","Refunds use the original sale month; only physically restocked units recover COGS."],9.5,12)
    page()

    base(4,"The pair leads base, low and high cases")
    configs=["CZE+ESP","POL+ESP","POL+CZE","NLD+ESP","ESP","DEFER"]
    headers=["Option","Low €/yr","Base €/yr","High €/yr","Stress €/yr","Capex","FTE"]
    xs=[17,63,105,147,189,231,264]
    c.setFillColor(colors.HexColor(BLUE)); c.rect(15*mm,H-58*mm,262*mm,13*mm,fill=1,stroke=0)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold",8.5)
    for x,h in zip(xs,headers): c.drawString(x*mm,H-53*mm,h)
    for i,opt in enumerate(configs):
        y=H-(70+i*18)*mm
        if i%2==0:
            c.setFillColor(colors.HexColor(PALE)); c.rect(15*mm,y-5*mm,262*mm,17*mm,fill=1,stroke=0)
        vals=[opt]+[f"{SC[(opt,s)]['incremental_contribution_eur']/1000:,.0f}k" for s in ("low","base","high","stress")]+[f"{SC[(opt,'base')]['capex_eur']/1000:.0f}k",str(SC[(opt,'base')]["fte"])]
        c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica-Bold" if i==0 else "Helvetica",10)
        for x,v in zip(xs,vals): c.drawString(x*mm,y,v)
    textblock(17*mm,25*mm,260*mm,["Uplift assumptions: 10% / 25% / 40%. Stress: 25% uplift + 3% gross refund shock;", "PLN/CZK also lose 10% of net sales. Simple annual arithmetic, not a demand forecast."],8.5,11,color=GRAY)
    page()

    base(5,"Stress changes the preferred pace")
    box(15*mm,113*mm,81*mm,49*mm,"CZE+ESP BASE","€198k / yr","1.14-year payback")
    box(105*mm,113*mm,81*mm,49*mm,"CZE+ESP STRESS","€32k / yr","6.99-year payback")
    box(195*mm,113*mm,81*mm,49*mm,"ESP ONLY STRESS","€70k / yr","1.86-year payback")
    c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica-Bold",13); c.drawString(17*mm,97*mm,"Why stage the second hub")
    textblock(17*mm,86*mm,260*mm,["CZE's own annual increment falls from +€95k base to -€38k under joint stress.","POL+ESP is the next highest base pair (+€186k), but uses €15k more capex", "and one more FTE; its stress result is +€29k.","NLD+ESP leads stress at +€108k, with €45k more capex than CZE+ESP.","If CZE stress persists, defer it and reassess NLD or stay with ESP alone."],10.5,15)
    c.setFillColor(colors.HexColor(GRAY)); c.setFont("Helvetica",8.5); c.drawString(17*mm,25*mm,"Stress is a conservative assumption with no assigned probability; it is not observed 2026 performance.")
    page()

    base(6,"Use 90 days to turn assumptions into gates")
    stages=[
      ("0–30", "COO + FP&A", "Sign ESP cost envelope; validate data, site and SKU capacity.", "≤€130k capex, 3 FTE"),
      ("31–60", "ESP ops + IT", "Set up inventory, routing, returns and parallel reconciliations.", "Controls and test orders pass"),
      ("61–90", "COO + CZE lead", "Pilot ESP; measure returns; hold CZE option; screen NLD fallback.", "CZE >€47.5k/yr, <2yr payback"),
    ]
    for i,(period,owner,action,gate) in enumerate(stages):
        y=H-(63+i*39)*mm
        c.setFillColor(colors.HexColor(PALE)); c.roundRect(15*mm,y-15*mm,262*mm,32*mm,3*mm,fill=1,stroke=0)
        c.setFillColor(colors.HexColor(TEAL)); c.setFont("Helvetica-Bold",15); c.drawString(21*mm,y+5*mm,period)
        c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica-Bold",10); c.drawString(62*mm,y+5*mm,owner)
        c.setFont("Helvetica",9); c.drawString(62*mm,y-4*mm,action)
        c.setFillColor(colors.HexColor(BLUE)); c.setFont("Helvetica-Bold",9); c.drawString(62*mm,y-12*mm,"Gate: "+gate)
    c.setFillColor(colors.HexColor(NAVY)); c.setFont("Helvetica-Bold",10); c.drawString(17*mm,31*mm,"Weekly KPIs: on-time dispatch ≥95%; inventory accuracy ≥98%; refund rate, unit savings,")
    c.setFont("Helvetica",10); c.drawString(17*mm,23*mm,"restocking and contribution per shipment cohort. Reforecast monthly for two quarters.")
    page()
    c.save()
    return path


if __name__=="__main__":
    reg=source_register()
    print(workbook(reg))
    print(report(reg))
    print(deck())
