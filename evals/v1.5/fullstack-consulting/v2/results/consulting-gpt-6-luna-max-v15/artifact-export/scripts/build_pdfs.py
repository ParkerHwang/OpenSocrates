"""Create a landscape consulting report and a short board deck as PDFs."""
from collections import defaultdict
from pathlib import Path
import json

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
DELIVER = ROOT / "deliverables"
M = json.loads((DELIVER / "metrics.json").read_text(encoding="utf-8"))
Q = M["quality"]
RECO = M["recommendation"]
PAPER = landscape(A4)
W, H = PAPER
NAVY = colors.HexColor("#16324F")
TEAL = colors.HexColor("#0B8B82")
MINT = colors.HexColor("#DDF3EE")
INK = colors.HexColor("#20313D")
MUTED = colors.HexColor("#61717A")
PALE = colors.HexColor("#F5F8FA")
GRID = colors.HexColor("#D6E0E5")
ORANGE = colors.HexColor("#D97732")
WHITE = colors.white
FONT = "Helvetica"
FONT_B = "Helvetica-Bold"


def money(v, dec=0):
    if v is None:
        return "—"
    return f"€{v:,.{dec}f}"


def money_k(v, dec=1):
    if v is None:
        return "—"
    return f"€{v/1000:,.{dec}f}k"


def pct(v, dec=1):
    return "—" if v is None else f"{100*v:.{dec}f}%"


def text(c, s, x, y, size=9, color=INK, font=FONT):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawString(x, y, str(s))


def right_text(c, s, x, y, size=9, color=INK, font=FONT):
    c.setFillColor(color)
    c.setFont(font, size)
    c.drawRightString(x, y, str(s))


def wrap(c, s, x, y_top, width, size=9, leading=None, color=INK, font=FONT, max_lines=None):
    leading = leading or size * 1.35
    lines = []
    for paragraph in str(s).split("\n"):
        if not paragraph:
            lines.append("")
        else:
            lines.extend(simpleSplit(paragraph, font, size, width))
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = (lines[-1][:-2] + "…") if len(lines[-1]) > 2 else "…"
    c.setFillColor(color)
    c.setFont(font, size)
    y = y_top
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def rounded(c, x, y, w, h, fill, radius=8, stroke=None):
    c.setFillColor(fill)
    c.setStrokeColor(stroke or fill)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=bool(stroke))


def background(c):
    c.setFillColor(PALE)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def header(c, eyebrow, title, subtitle=""):
    c.setFillColor(NAVY)
    c.rect(0, H - 7, W, 7, fill=1, stroke=0)
    text(c, eyebrow.upper(), 38, H - 31, 8, TEAL, FONT_B)
    text(c, title, 38, H - 56, 21, NAVY, FONT_B)
    if subtitle:
        wrap(c, subtitle, 38, H - 74, W - 76, 8.8, 11.3, MUTED)


def footer(c, page, label="Meridian Parts | Decision support | Synthetic client inputs"):
    c.setStrokeColor(GRID)
    c.setLineWidth(0.6)
    c.line(38, 27, W - 38, 27)
    text(c, label, 38, 14, 7, MUTED)
    right_text(c, f"{page:02d}", W - 38, 14, 7, MUTED, FONT_B)


def page_start(c, eyebrow, title, subtitle, page):
    background(c)
    header(c, eyebrow, title, subtitle)
    footer(c, page)


def metric_card(c, x, y, w, h, label, value, detail, accent=TEAL):
    rounded(c, x, y, w, h, WHITE, 8, GRID)
    c.setFillColor(accent)
    c.roundRect(x, y, 4, h, 2, fill=1, stroke=0)
    text(c, label.upper(), x + 14, y + h - 19, 7.3, MUTED, FONT_B)
    text(c, value, x + 14, y + h - 42, 17, NAVY, FONT_B)
    wrap(c, detail, x + 14, y + 18, w - 25, 7.1, 9, MUTED)


def draw_table(c, x, y_top, widths, headers, rows, row_h=20, header_h=25, font_size=7.1,
               aligns=None, highlight_rows=(), header_size=6.5):
    total_w = sum(widths)
    c.setFillColor(NAVY)
    c.roundRect(x, y_top - header_h, total_w, header_h, 4, fill=1, stroke=0)
    cx = x
    for i, h in enumerate(headers):
        align = (aligns or ["left"] * len(headers))[i]
        lines = simpleSplit(str(h), FONT_B, header_size, widths[i] - 8)
        start_y = y_top - 10 if len(lines) == 1 else y_top - 8
        c.setFillColor(WHITE)
        c.setFont(FONT_B, header_size)
        for j, line in enumerate(lines[:2]):
            if align == "right":
                c.drawRightString(cx + widths[i] - 5, start_y - j * 7.2, line)
            elif align == "center":
                c.drawCentredString(cx + widths[i] / 2, start_y - j * 7.2, line)
            else:
                c.drawString(cx + 4, start_y - j * 7.2, line)
        cx += widths[i]
    y = y_top - header_h
    for ri, row in enumerate(rows):
        y -= row_h
        if ri in highlight_rows:
            c.setFillColor(MINT)
        else:
            c.setFillColor(WHITE if ri % 2 == 0 else colors.HexColor("#F0F5F7"))
        c.rect(x, y, total_w, row_h, fill=1, stroke=0)
        c.setStrokeColor(GRID)
        c.setLineWidth(0.3)
        c.line(x, y, x + total_w, y)
        cx = x
        for i, value in enumerate(row):
            align = (aligns or ["left"] * len(headers))[i]
            s = str(value)
            c.setFillColor(NAVY if ri in highlight_rows else INK)
            c.setFont(FONT_B if ri in highlight_rows and i == 0 else FONT, font_size)
            if align == "right":
                c.drawRightString(cx + widths[i] - 5, y + (row_h - font_size) / 2 + 1, s)
            elif align == "center":
                c.drawCentredString(cx + widths[i] / 2, y + (row_h - font_size) / 2 + 1, s)
            else:
                c.drawString(cx + 4, y + (row_h - font_size) / 2 + 1, s)
            cx += widths[i]
    return y


def hbar(c, items, x, y_top, width, row_h=23, max_value=None, unit="EUR", color=TEAL, label_width=85, value_fmt=None):
    max_value = max_value or max((max(0, value) for _, value in items), default=1)
    plot_width = width - label_width - 68
    for i, (label, value) in enumerate(items):
        y = y_top - i * row_h
        text(c, label, x, y - 10, 7.6, INK, FONT_B)
        bar_x = x + label_width
        c.setFillColor(colors.HexColor("#E5ECEF"))
        c.roundRect(bar_x, y - 13, plot_width, 10, 4, fill=1, stroke=0)
        c.setFillColor(color)
        c.roundRect(bar_x, y - 13, max(2, plot_width * max(0, value) / max_value), 10, 4, fill=1, stroke=0)
        fmt = value_fmt or (lambda v: money_k(v))
        right_text(c, fmt(value), x + width, y - 10, 7.2, MUTED, FONT_B)


def line_chart(c, series, x, y, w, h, colorset=None, y_max=None, title=None):
    colorset = colorset or [TEAL, ORANGE]
    if title:
        text(c, title, x, y + h + 10, 8, NAVY, FONT_B)
    left, right = x + 32, x + w - 9
    bottom, top = y + 20, y + h - 12
    vmax = y_max or max(max(v for v in values) for _, values in series) * 1.05
    for tick in range(5):
        yy = bottom + (top - bottom) * tick / 4
        c.setStrokeColor(GRID)
        c.setLineWidth(0.4)
        c.line(left, yy, right, yy)
        right_text(c, f"€{vmax*tick/4/1000:,.0f}k", left - 4, yy - 2, 6.3, MUTED)
    n = len(series[0][1])
    for idx, (label, values) in enumerate(series):
        col = colorset[idx % len(colorset)]
        points = []
        for i, value in enumerate(values):
            px = left + (right - left) * i / max(1, n - 1)
            py = bottom + (top - bottom) * value / vmax
            points.append((px, py))
        c.setStrokeColor(col)
        c.setLineWidth(1.8)
        for a, b in zip(points, points[1:]):
            c.line(a[0], a[1], b[0], b[1])
        c.setFillColor(col)
        for px, py in points:
            c.circle(px, py, 2.1, fill=1, stroke=0)
    c.setFont(FONT, 6.7)
    c.setFillColor(MUTED)
    for i, month in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
        if i < n:
            px = left + (right - left) * i / max(1, n - 1)
            c.drawCentredString(px, bottom - 12, month)
    lx = left
    for idx, (label, _) in enumerate(series):
        c.setFillColor(colorset[idx % len(colorset)])
        c.rect(lx, y - 1, 7, 7, fill=1, stroke=0)
        text(c, label, lx + 10, y, 6.7, MUTED)
        lx += 94


def grouped_bars(c, series, x, y, w, h, max_value=None):
    labels = [r[0] for r in series]
    values_a = [r[1] for r in series]
    values_b = [r[2] for r in series]
    max_value = max_value or max(max(values_a), max(values_b))
    plot_left = x + 75
    plot_width = w - 85
    row_h = h / len(labels)
    for i, label in enumerate(labels):
        base_y = y + h - (i + 1) * row_h + 4
        text(c, label, x, base_y + 6, 7, INK, FONT_B)
        for j, val in enumerate((values_a[i], values_b[i])):
            yy = base_y + j * 9
            c.setFillColor(TEAL if j == 0 else ORANGE)
            c.roundRect(plot_left, yy, max(1.5, plot_width * max(0, val) / max_value), 6, 2, fill=1, stroke=0)
            right_text(c, f"{val/1000:,.0f}", x + w, yy + 1, 6, MUTED)


def get_month_totals():
    by_month = defaultdict(lambda: defaultdict(float))
    for row in M["monthly"]:
        month = row["month"]
        for field in ("gross_sales_eur", "refunds_eur", "net_sales_eur", "net_cogs_eur", "fulfillment_eur", "contribution_eur"):
            by_month[month][field] += row[field]
        by_month[month]["shipped_orders"] += row["shipped_orders"]
        by_month[month]["shipped_units"] += row["shipped_units"]
        by_month[month]["returned_units"] += row["returned_units"]
    return by_month


def create_report():
    path = DELIVER / "meridian_board_report.pdf"
    c = canvas.Canvas(str(path), pagesize=PAPER, pageCompression=1)
    c.setTitle("Meridian Parts | European Service-Hub Expansion Decision Report")
    c.setAuthor("Operations advisory | synthetic case analysis")
    country_order = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
    country_names = {"DEU": "Germany", "FRA": "France", "NLD": "Netherlands", "POL": "Poland", "CZE": "Czechia", "ESP": "Spain"}
    annual = {r["country"]: r for r in M["countries"]}
    hub = defaultdict(dict)
    for r in M["hub_scenarios"]:
        hub[r["country"]][r["scenario"]] = r
    months = get_month_totals()
    market = defaultdict(dict)
    for r in M["market_context"]:
        market[r["country"]][r["year"]] = r

    # 1 — decision memo
    background(c)
    c.setFillColor(NAVY)
    c.rect(0, H - 15, W, 15, fill=1, stroke=0)
    text(c, "MERIDIAN PARTS  /  BOARD DECISION NOTE", 42, H - 48, 9, TEAL, FONT_B)
    text(c, "Fund Czechia + Spain", 42, H - 101, 31, NAVY, FONT_B)
    text(c, "Condition release on a 90-day validation gate", 42, H - 127, 15, MUTED)
    wrap(c, "The two-country option leads the defined base case and leaves room under both board caps. Approve a conditional EUR225,000 year-zero capex envelope for CZE and ESP, staffed at five FTE, with the second-stage release tied to verified volume, per-unit savings and local costs.", 42, H - 164, 420, 10.5, 15, INK)
    metric_card(c, 42, 286, 176, 90, "Base annual gain", money_k(hub["CZE+ESP"]["base"]["incremental_contribution_eur"]), "After EUR95k recurring fixed costs", TEAL)
    metric_card(c, 230, 286, 176, 90, "Year-zero capex", money(hub["CZE+ESP"]["base"]["capex_eur"]), "50% of EUR450k cap", NAVY)
    metric_card(c, 418, 286, 176, 90, "Staffing", "5 FTE", "2 FTE below the seven-person cap", ORANGE)
    metric_card(c, 606, 286, 194, 90, "Base simple payback", f"{hub['CZE+ESP']['base']['payback_years']:.2f} years", "Stress payback: 6.99 years", TEAL)
    rounded(c, 42, 128, 458, 132, WHITE, 8, GRID)
    text(c, "WHY THIS OPTION", 58, 239, 8, TEAL, FONT_B)
    wrap(c, "CZE+ESP produces EUR198.1k modeled annual contribution in the named base scenario, EUR11.8k above the next base-ranked POL+ESP pair, with EUR15k less capex and one fewer FTE. Its defined joint stress remains positive at EUR32.2k/year, but simple stress payback stretches to about seven years.", 58, 219, 425, 9, 12.3, INK)
    rounded(c, 518, 128, 282, 132, MINT, 8)
    text(c, "DECISION BASIS", 534, 239, 8, NAVY, FONT_B)
    wrap(c, "Hard constraints: capex ≤ EUR450,000; ≤7 FTE; ≤2 hubs. Consultant default: maximize base-case annual contribution, then disclose low/high/stress and payback. No scenario probabilities or board risk weights were supplied.", 534, 219, 250, 8.7, 11.8, INK)
    wrap(c, "This is a conditional planning recommendation from synthetic client inputs, not a causal estimate of hub effects. Defer remains defensible if validation does not support the assumed uplift and savings.", 42, 104, 750, 8.2, 11, MUTED)
    footer(c, 1)
    c.showPage()

    # 2 — 2025 country performance
    page_start(c, "01 | Operating baseline", "2025 shipments support a €2.03m contribution pool", "1,254 eligible shipments across six markets. All client order, return, unit-cost and fulfillment inputs are synthetic; no live customer system was accessed.", 2)
    total = Q["country_year_totals"]
    tile_y = 418
    metrics = [
        ("Net sales", money_k(total["net_sales_eur"]), "gross €4.465m less €80.8k refunds"),
        ("Contribution", money_k(total["contribution_eur"]), f"{pct(Q['aggregate_margin'])} of net sales"),
        ("Units shipped", f"{total['shipped_units']:,}", f"{total['returned_units']:,} units returned ({pct(Q['aggregate_returned_units_rate'])})"),
        ("Orders", f"{total['shipped_orders']:,}", "209 in each synthetic market"),
    ]
    for i, (label, val, detail) in enumerate(metrics):
        metric_card(c, 38 + i * 194, tile_y, 180, 64, label, val, detail)
    headers = ["Country", "Orders", "Units", "Gross sales", "Refunds", "Net sales", "Net COGS", "Fulfillment", "Contribution", "Margin", "Returns"]
    rows = []
    for country in country_order:
        r = annual[country]
        rows.append([country, f"{r['shipped_orders']:,}", f"{r['shipped_units']:,}", money(r["gross_sales_eur"]), money(r["refunds_eur"]), money(r["net_sales_eur"]), money(r["net_cogs_eur"]), money(r["fulfillment_eur"]), money(r["contribution_eur"]), pct(r["margin"]), f"{r['returned_units']:,}"])
    rows.append(["TOTAL", f"{total['shipped_orders']:,}", f"{total['shipped_units']:,}", money(total["gross_sales_eur"]), money(total["refunds_eur"]), money(total["net_sales_eur"]), money(total["net_cogs_eur"]), money(total["fulfillment_eur"]), money(total["contribution_eur"]), pct(Q["aggregate_margin"]), f"{total['returned_units']:,}"])
    widths = [46, 43, 48, 72, 67, 72, 70, 72, 77, 48, 51]
    draw_table(c, 38, 391, widths, headers, rows, row_h=22, header_h=27, font_size=7.3, header_size=6.5, aligns=["left"] + ["right"] * 10, highlight_rows=(6,))
    text(c, "Contribution by country", 38, 180, 8.4, NAVY, FONT_B)
    contributions = [(country, annual[country]["contribution_eur"]) for country in country_order]
    hbar(c, contributions, 40, 161, 420, row_h=18, max_value=max(v for _, v in contributions), label_width=72)
    rounded(c, 494, 72, 308, 120, WHITE, 8, GRID)
    text(c, "READOUT", 510, 175, 8, TEAL, FONT_B)
    wrap(c, "Spain (€421.9k) and Czechia (€397.3k) contribute €819.2k, or 40.4% of total. Margins range 41.9%–49.6%. Each country has 209 eligible orders in this generated export; its ranking is not live demand evidence.", 510, 156, 275, 8.1, 10.2, INK)
    c.showPage()

    # 3 — monthly profile and reconciliation
    page_start(c, "02 | Timing and accounting", "Monthly totals reconcile to country and order ledgers", "Sales and refunds are converted using the original shipment month ECB mean; each per-order monetary component is rounded half-up to cents before summation.", 3)
    mlist = [months[f"2025-{m:02d}"] for m in range(1, 13)]
    line_chart(c, [("Net sales", [x["net_sales_eur"] for x in mlist]), ("Contribution", [x["contribution_eur"] for x in mlist])], 44, 359, 748, 112, [TEAL, ORANGE], title="Group monthly profile | EUR")
    m_headers = ["Month", "Orders", "Units", "Gross", "Refunds", "Net sales", "Net COGS", "Fulfillment", "Contribution", "Returned units"]
    m_rows = []
    for idx, m in enumerate(mlist, 1):
        m_rows.append([f"2025-{idx:02d}", f"{int(m['shipped_orders']):,}", f"{int(m['shipped_units']):,}", money(m["gross_sales_eur"]), money(m["refunds_eur"]), money(m["net_sales_eur"]), money(m["net_cogs_eur"]), money(m["fulfillment_eur"]), money(m["contribution_eur"]), f"{int(m['returned_units']):,}"])
    draw_table(c, 42, 340, [50, 40, 45, 58, 52, 58, 58, 59, 67, 55], m_headers, m_rows, row_h=15, header_h=22, font_size=6.3, header_size=6.0, aligns=["left"] + ["right"] * 9)
    rounded(c, 42, 59, 436, 67, WHITE, 8, GRID)
    text(c, "ACCOUNTING BRIDGE", 56, 108, 7.5, TEAL, FONT_B)
    wrap(c, f"Gross {money(total['gross_sales_eur'])} − refunds {money(total['refunds_eur'])} = net sales {money(total['net_sales_eur'])}; net sales − net COGS {money(total['net_cogs_eur'])} − fulfillment {money(total['fulfillment_eur'])} = contribution {money(total['contribution_eur'])}.", 56, 91, 405, 7.0, 8.4, INK)
    rounded(c, 494, 59, 308, 67, MINT, 8)
    text(c, "RECONCILIATION / CUTOFF", 508, 108, 7.5, NAVY, FONT_B)
    wrap(c, "All 9 requested fields reconcile across 72 monthly cells, six country totals and the order ledger. Returns include 2026-01-31; one later return is excluded and one orphan quarantined. Cash settlement data is absent.", 508, 91, 278, 7.0, 8.4, INK)
    c.showPage()

    # 4 — macro context and FX
    page_start(c, "03 | Market context", "Public macro series are context, not a demand proxy", "Archived World Bank responses cover 2022–2024 for six markets. GDP is current US$ (not PPP or constant-price); subsequent archive revisions may be reflected.", 4)
    ctx_headers = ["Market", "Population 2024", "Change 22–24", "GDP pc 2022", "GDP pc 2024", "Change 22–24"]
    ctx_rows = []
    for country in country_order:
        p22, p24 = market[country][2022]["population"], market[country][2024]["population"]
        g22, g24 = market[country][2022]["gdp_per_capita_usd"], market[country][2024]["gdp_per_capita_usd"]
        ctx_rows.append([country_names[country], f"{p24/1e6:.2f}m", pct(p24/p22 - 1, 2), f"${g22:,.0f}", f"${g24:,.0f}", pct(g24/g22 - 1, 1)])
    draw_table(c, 42, 477, [112, 105, 104, 112, 112, 104], ctx_headers, ctx_rows, row_h=17, header_h=22, font_size=7.4, header_size=6.8, aligns=["left", "right", "right", "right", "right", "right"])
    rounded(c, 42, 275, 648, 68, WHITE, 8, GRID)
    text(c, "INTERPRETATION", 58, 326, 7.6, TEAL, FONT_B)
    wrap(c, "Population grew 2.22% in Spain and 2.18% in Czechia over 2022–2024; Poland declined 0.71%. Nominal GDP per capita rose in all markets, most in Poland (+32.9%). These series do not establish product demand or a hub effect.", 58, 309, 610, 7.5, 9.1)
    text(c, "ECB monthly arithmetic means | local currency units per EUR | 2025", 42, 257, 8.4, NAVY, FONT_B)
    fx_rows = []
    fxmap = {(x["currency"], x["month"]): x["local_per_eur"] for x in M["fx_monthly"]}
    daymap = {(r["currency"], r["month"]): r["business_days"] for r in __import__("csv").DictReader(open(ROOT / "analysis" / "fx_monthly.csv", encoding="utf-8"))}
    for m in range(1, 13):
        month = f"2025-{m:02d}"
        pln = fxmap[("PLN", month)]
        czk = fxmap[("CZK", month)]
        fx_rows.append([month, f"{pln:.6f}", f"{czk:.6f}", daymap[("PLN", month)]])
    draw_table(c, 42, 238, [122, 130, 130, 142], ["Month", "PLN / EUR", "CZK / EUR", "Published days / month"], fx_rows, row_h=14, header_h=20, font_size=6.8, header_size=6.5, aligns=["left", "right", "right", "right"])
    rounded(c, 594, 66, 206, 210, MINT, 8)
    text(c, "FX HANDLING", 610, 255, 8, NAVY, FONT_B)
    wrap(c, "The supplied ECB reference rate is quoted as local-currency units per EUR. Conversion divides local amounts by the original shipment-month mean. EUR is 1 by convention. The reference-rate translation is an analytical assumption, not the customer's executed transaction rate.", 610, 235, 174, 8.1, 10.8)
    wrap(c, "World Bank archive last-updated metadata: 2026-07-13. Source-room retrieval: 2026-09-27. No live World Bank or ECB query was made for this analysis.", 610, 145, 174, 7.7, 10.2, MUTED)
    c.showPage()

    # 5 — full alternative matrix
    page_start(c, "04 | Hub scenarios", "CZE + ESP ranks first on the stated base case", "Annual incremental contribution after recurring fixed costs. Year-zero capex is separate. Scenarios use the client policy; pairs have no assumed synergy.", 5)
    comp_by = defaultdict(dict)
    for r in M["hub_scenarios"]:
        comp_by[r["country"]][r["scenario"]] = r
    ranks = [r for r in M["hub_option_ranking_base"] if r["country"] != "DEFER"]
    ranks = sorted(ranks, key=lambda r: (-r["incremental_contribution_eur"], r["country"]))
    labels = []
    for r in ranks:
        labels.append({**r, "country": r["country"].replace("+", " + ")})
    all_rows = []
    for row in labels:
        name = row["country"]
        key = name.replace(" ", "")
        v = comp_by[key]
        all_rows.append([name, money_k(v["base"]["capex_eur"], 0), str(v["base"]["fte"]), money_k(v["low"]["incremental_contribution_eur"]), money_k(v["base"]["incremental_contribution_eur"]), money_k(v["high"]["incremental_contribution_eur"]), money_k(v["stress"]["incremental_contribution_eur"]), f"{v['base']['payback_years']:.2f}", f"{v['stress']['payback_years']:.2f}" if v["stress"]["payback_years"] else "—"])
    de = comp_by["DEFER"]
    all_rows.append(["DEFER", "€0k", "0", "€0.0k", "€0.0k", "€0.0k", "€0.0k", "—", "—"])
    widths = [69, 53, 30, 67, 67, 67, 67, 48, 48]
    draw_table(c, 38, 485, widths, ["Option", "Capex", "FTE", "Low €/yr", "Base €/yr", "High €/yr", "Stress €/yr", "Base PB", "Stress PB"], all_rows, row_h=18, header_h=24, font_size=6.5, header_size=6, aligns=["left"] + ["right"] * 8, highlight_rows=(0,))
    text(c, "Top base-case annual gain | €k", 572, 479, 8, NAVY, FONT_B)
    best_items = [(x["country"], x["incremental_contribution_eur"]) for x in ranks[:5]]
    hbar(c, best_items, 572, 452, 226, row_h=32, max_value=max(v for _, v in best_items), label_width=67)
    rounded(c, 572, 204, 226, 73, MINT, 8)
    text(c, "FEASIBILITY", 586, 258, 7.6, NAVY, FONT_B)
    wrap(c, "17 hub sets: six singles and 11 pairs. Four DEU pairs fail a cap: DEU+FRA exceeds EUR450k; DEU+NLD/POL/ESP exceed seven FTE. CZE+ESP uses EUR225k and five FTE.", 586, 241, 196, 7.4, 9.6)
    rounded(c, 572, 92, 226, 96, WHITE, 8, GRID)
    text(c, "FORMULA", 586, 168, 7.6, TEAL, FONT_B)
    wrap(c, "Low/base/high: C×u + U×(1+u)×saving − fixed cost, with u=10/25/40%. Stress: (C−3%×G−FX shock)×1.25 − C + U×1.25×saving − fixed. Capex is excluded from annual contribution.", 586, 151, 196, 7.3, 9.5)
    wrap(c, "Full pair-by-scenario paybacks and component assumptions are in the workbook and metrics.json. DEFER is zero contribution/capex/staffing.", 38, 77, 500, 7.2, 9.2, MUTED)
    c.showPage()

    # 6 — alternatives, sensitivity, conclusion card
    page_start(c, "05 | Trade-offs and decision conditions", "Base-case leader gives up downside protection", "No scenario probability or board risk weight was supplied. The recommendation uses base-case contribution as the explicit primary criterion and keeps stress visible.", 6)
    compare_names = ["CZE+ESP", "POL+ESP", "NLD+ESP"]
    compare_rows = []
    for name in compare_names:
        compare_rows.append([name, money_k(comp_by[name]["low"]["incremental_contribution_eur"]), money_k(comp_by[name]["base"]["incremental_contribution_eur"]), money_k(comp_by[name]["stress"]["incremental_contribution_eur"]), money_k(comp_by[name]["base"]["capex_eur"], 0), str(comp_by[name]["base"]["fte"]), f"{comp_by[name]['base']['payback_years']:.2f}", f"{comp_by[name]['stress']['payback_years']:.2f}"])
    draw_table(c, 42, 479, [82, 77, 81, 79, 72, 42, 65, 70], ["Option", "Low €/yr", "Base €/yr", "Stress €/yr", "Capex", "FTE", "Base PB", "Stress PB"], compare_rows, row_h=24, header_h=28, font_size=7.5, header_size=6.6, aligns=["left"] + ["right"] * 7, highlight_rows=(0,))
    # Value trade-offs
    rounded(c, 42, 247, 350, 143, WHITE, 8, GRID)
    text(c, "VS. NEXT BASE-RANKED: POL + ESP", 58, 370, 8, TEAL, FONT_B)
    wrap(c, "CZE+ESP adds €11.8k/year in the base case, €6.1k in low and €17.5k in high; it also adds €2.9k/year under the defined stress. It needs €15k less capex, one fewer FTE, and its base payback is 1.14 vs 1.29 years. It is the stronger choice across the supplied scenario values and resource use.", 58, 348, 318, 8.2, 10.7)
    rounded(c, 408, 247, 392, 143, MINT, 8)
    text(c, "VS. STRESS-RESILIENT: NLD + ESP", 424, 370, 8, NAVY, FONT_B)
    wrap(c, "NLD+ESP earns €107.6k/year under stress vs €32.2k for CZE+ESP, but its base gain is €31.2k lower; it needs €45k more capex and one more FTE. Stress payback is 2.51 vs 6.99 years. A board prioritizing the defined joint stress over base-case return could select NLD+ESP.", 424, 348, 360, 8.2, 10.7)
    rounded(c, 42, 83, 758, 142, WHITE, 8, GRID)
    text(c, "CONCLUSION CARD | CONDITIONAL FUNDING RECOMMENDATION", 58, 205, 8.1, TEAL, FONT_B)
    left_y = wrap(c, "Recommendation: authorize up to €225k and five FTE for CZE+ESP, with staged release after live operating validation. The base estimate is computed from the synthetic 2025 contribution pool and option assumptions; it is not causal proof.", 58, 185, 350, 8.2, 10.7)
    wrap(c, "Accepted risk: stress contribution is positive but simple stress payback is about seven years. Missing inputs: real site quotes, local operating costs, validated order density/uplift, observed savings, and a board risk preference. Reopen if these move the ranking or annual contribution below the low case.", 58, left_y - 6, 350, 8.2, 10.7, INK)
    sw = RECO["base_rank_switch_example"]
    wrap(c, f"Observable flip condition: holding ESP and all other inputs fixed, if CZE's actual uplift is below {100*sw['selected_site_uplift_threshold_if_alternative_site_uplift_is_25pct']:.1f}% while POL achieves 25%, POL+ESP overtakes on base annual contribution. Equivalent CZE savings threshold: about €{sw['selected_site_saving_threshold_eur_per_unit_if_both_uplifts_are_25pct']:.2f}/unit at both sites' 25% uplift.", 430, 185, 348, 8.2, 10.7, INK)
    wrap(c, "Defer condition: if day-90 validation cannot support the option's low-case economics, release no second-stage capex and return to the board. Scenarios are not probabilities and the joint stress is not a forecast.", 430, 118, 348, 8.2, 10.7, MUTED)
    c.showPage()

    # 7 — 90-day plan and measurable KPIs
    page_start(c, "06 | Implementation", "Use 90 days to validate before committing irreversible spend", "Owners below are proposed functional roles, not named Meridian personnel. The source room contains no live site quotes, contracts, interviews or operating SLA data.", 7)
    phases = [
        ("DAYS 0–30", "Validate the case", "CFO / FP&A + Operations lead", "Rebuild current demand baseline from live order and return records; validate option capex, fixed-cost and savings inputs; shortlist candidate locations; test CZE/ESP FX and labor assumptions.", "Gate 1: refreshed CZE uplift and savings case remains ahead of POL+ESP; real quote fits EUR225k capex and EUR95k combined annual fixed costs."),
        ("DAYS 31–60", "Design and contract", "Procurement / Facilities + HR", "Obtain site-specific quotations, lease terms, staffing availability and operating model; map inventory, replenishment, IT and return/restock workflow; stage contracts so either site can be stopped.", "Gate 2: CFO and COO approve committed capex within envelope, five FTE plan, local compliance review and written service/stock process."),
        ("DAYS 61–90", "Commission and prove", "Regional Operations + Analytics", "Activate first hub in a controlled pilot; open second only after the Gate 3 economics review; track country-level units, returns, savings, service and actual cost weekly.", "Gate 3: continue only if annualized contribution after recurring cost is at least the low-case EUR64.6k and customer-promise performance is maintained."),
    ]
    x0, ytop = 42, 475
    for i, (period, title, owner, action, gate) in enumerate(phases):
        y = ytop - i * 108
        rounded(c, x0, y - 103, 758, 101, WHITE, 8, GRID)
        rounded(c, x0 + 12, y - 37, 91, 22, NAVY, 5)
        c.setFillColor(WHITE); c.setFont(FONT_B, 7.2); c.drawCentredString(x0 + 57, y - 30, period)
        text(c, title, x0 + 118, y - 23, 10.2, NAVY, FONT_B)
        text(c, f"Owner: {owner}", x0 + 118, y - 39, 7.4, TEAL, FONT_B)
        wrap(c, action, x0 + 118, y - 56, 612, 7.7, 9.8, INK)
        wrap(c, gate, x0 + 118, y - 83, 612, 7.4, 9.5, MUTED)
    # KPI bar
    rounded(c, 42, 64, 758, 76, MINT, 8)
    text(c, "WEEKLY KPI PLAN | PROVISIONAL GATE THRESHOLDS", 58, 122, 8, NAVY, FONT_B)
    kpis = [
        ("Volume", "≥1.25× validated 2025 run rate per market; measure shipped units/orders"),
        ("Savings", "CZE ≥€2.10/unit; ESP ≥€3.00/unit, net of measured incremental handling"),
        ("Refunds", "Track refund EUR / gross sales; trigger review at baseline +3 percentage points"),
        ("Cost / SLA", "Capex ≤€225k; recurring fixed ≤€95k; maintain ≥95% of quoted promise (set live baseline first)"),
    ]
    cellw = 180
    for i, (label, detail) in enumerate(kpis):
        xx = 58 + i * 184
        text(c, label.upper(), xx, 104, 7, TEAL, FONT_B)
        wrap(c, detail, xx, 89, cellw, 7, 9.2, INK)
    c.showPage()

    # 8 — quality, sources and limits
    page_start(c, "Appendix | Evidence and quality", "A complete synthetic ledger, plus archived public context", "The board should distinguish observed archived facts from synthetic client transactions and planning assumptions.", 8)
    rounded(c, 42, 302, 368, 174, WHITE, 8, GRID)
    text(c, "RECONCILED / RETAINED", 58, 456, 8, TEAL, FONT_B)
    qlines = [
        f"Orders: {Q['order_raw_rows']:,} raw rows across two pages + corrections; {Q['order_exact_duplicate_rows_removed']} exact duplicate rows removed; {Q['order_ids_with_multiple_revisions']} order IDs revised, all latest revisions selected from corrections.",
        f"Latest-order exclusions: 24 non-shipped; 18 tests; 1 shipped outside 2025. Kept 12 valid zero-gross shipped orders; {Q['eligible_2025_shipped_orders']:,} eligible orders remain.",
        f"Returns: 20 duplicate rows removed; one revised return resolved by latest revision; {Q['returns_included']} included, one orphan quarantined, one post-cutoff excluded.",
        f"No selected latest-revision conflicts, negative gross orders, refund-above-gross orders, country/currency mismatches, missing unit costs or return quantities above shipped quantities detected.",
        f"World Bank: 18 population + 18 GDP observations, 2022–24; missing values preserved (0 nulls in the archived payload). Source hashes: {sum(1 for x in Q['source_hash_checks'] if x['pass'])}/{len(Q['source_hash_checks'])} match.",
    ]
    yy = 435
    for line in qlines:
        yy = wrap(c, "• " + line, 58, yy, 335, 7.5, 9.4, INK) - 4
    rounded(c, 426, 302, 374, 174, MINT, 8)
    text(c, "LIMITS THAT MATTER", 442, 456, 8, NAVY, FONT_B)
    limits = [
        "All client order, correction, return, unit-cost, hub-option and scenario inputs are synthetic (seed 2026092736). Their orderly 209-order/country pattern is not an observed demand distribution.",
        "Hub uplifts (10/25/40%), savings, fixed costs and capex are assumptions. No site-specific data, causal design, synergies, probability weights or board risk weights exist in the room.",
        "Payback is simple and undiscounted. It excludes ramp, taxes, financing, cash timing, residual value, leases beyond stated cost, working capital and other overhead.",
        "ECB rates are reference translation assumptions, not transaction prices. World Bank GDP per capita is current US$ and not PPP or real income.",
    ]
    yy = 435
    for line in limits:
        yy = wrap(c, "• " + line, 442, yy, 340, 7.5, 9.4, INK) - 5
    text(c, "SOURCE REGISTER | URLs, retrieval times, hashes, units and periods also appear in analysis/source_register.csv and the workbook.", 42, 273, 8, NAVY, FONT_B)
    sources = [
        ("C1 Synthetic client data", "data-dictionary.md; orders-part1.csv; orders-part2.csv; order-corrections.csv; returns.csv; unit-costs.csv; hub-options.csv; scenario-policy.md. Source room captured 2026-09-27 07:56 UTC. Files and hashes are saved under evidence/source_room/.", "http://127.0.0.1:52727/"),
        ("P1 World Bank population", "Archived API response; SP.POP.TOTL; persons, 2022–2024; last updated 2026-07-13; archive retrieved 2026-09-27 06:36 UTC.", "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&format=json&per_page=1000"),
        ("P2 World Bank GDP per capita", "Archived API response; NY.GDP.PCAP.CD; current US dollars/person, 2022–2024; last updated 2026-07-13; archive retrieved 2026-09-27 06:36 UTC.", "https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&format=json&per_page=1000"),
        ("P3 ECB reference rates", "Official euro foreign-exchange reference rates; local units per EUR; daily history; 255 observations in 2025; archive retrieved 2026-09-27 06:36 UTC. Monthly values average published days.", "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"),
    ]
    y = 251
    for name, desc, url in sources:
        text(c, name, 42, y, 7.5, TEAL, FONT_B)
        y = wrap(c, desc, 165, y, 628, 7.2, 9.0, INK) - 2
        # clickable label with the long original URL kept in the source register
        c.linkURL(url, (42, y - 1, 157, y + 10), relative=0, thickness=0)
        y = wrap(c, url, 165, y, 628, 6.5, 8, MUTED) - 4
    wrap(c, "Raw inputs and scripts are saved locally. Source-room URLs are frozen collection provenance and may not resolve outside this disposable environment.", 42, 52, 740, 7, 9, MUTED)
    c.showPage()
    c.save()
    return path


def slide_header(c, number, title, strap=None):
    c.setFillColor(NAVY)
    c.rect(0, H - 12, W, 12, fill=1, stroke=0)
    text(c, "MERIDIAN PARTS  /  EUROPEAN SERVICE HUBS", 36, H - 34, 8, TEAL, FONT_B)
    text(c, title, 36, H - 67, 23, NAVY, FONT_B)
    if strap:
        text(c, strap, 36, H - 88, 9, MUTED)
    c.setStrokeColor(GRID); c.line(36, 28, W - 36, 28)
    text(c, "Synthetic client case | archived public series | 27 Sep 2026", 36, 15, 7, MUTED)
    right_text(c, f"{number} / 6", W - 36, 15, 7, MUTED, FONT_B)


def create_deck():
    global W, H
    size = (960, 540)
    W, H = size
    path = DELIVER / "meridian_board_presentation.pdf"
    c = canvas.Canvas(str(path), pagesize=size, pageCompression=1)
    c.setTitle("Meridian Parts | Service Hub Board Presentation")
    c.setAuthor("Operations advisory | synthetic case analysis")
    # Slide 1
    c.setFillColor(PALE); c.rect(0, 0, *size, fill=1, stroke=0)
    c.setFillColor(NAVY); c.rect(0, 526, 960, 14, fill=1, stroke=0)
    text(c, "MERIDIAN PARTS  /  BOARD DECISION", 44, 489, 9, TEAL, FONT_B)
    text(c, "Approve CZE + ESP", 44, 431, 34, NAVY, FONT_B)
    text(c, "with a 90-day evidence gate before full release", 44, 399, 17, MUTED)
    wrap(c, "Highest modeled base-case annual contribution among options within the budget and staffing caps. Funding is conditional because transaction, site, labor and hub assumptions are synthetic and unvalidated.", 44, 356, 430, 11, 15, INK)
    for x, label, value, detail, col in [(44, "ANNUAL BASE", "€198.1k", "after recurring hub costs", TEAL), (262, "CAPEX", "€225k", "year zero; 50% of cap", NAVY), (480, "STAFF", "5 FTE", "2 below board limit", ORANGE), (698, "BASE PAYBACK", "1.14 yrs", "stress payback 6.99 yrs", TEAL)]:
        metric_card(c, x, 225, 198, 92, label, value, detail, col)
    rounded(c, 44, 74, 870, 112, MINT, 10)
    text(c, "RECOMMENDED BOARD ACTION", 62, 161, 8, NAVY, FONT_B)
    wrap(c, "Authorize a conditional €225,000 capex envelope and five FTE for Czechia + Spain. Release spend in stages; stop or re-rank if live validation does not support the stated low case or if site costs exceed the option inputs.", 62, 139, 820, 10, 13.5, INK)
    c.setStrokeColor(GRID); c.line(36, 28, 924, 28)
    text(c, "Synthetic client case | archived public series | 27 Sep 2026", 36, 15, 7, MUTED)
    right_text(c, "1 / 6", 924, 15, 7, MUTED, FONT_B)
    c.showPage()

    # Slide 2
    c.setFillColor(PALE); c.rect(0, 0, *size, fill=1, stroke=0)
    slide_header(c, 2, "Synthetic 2025 baseline: €2.03m contribution", "1,254 eligible orders | 77,436 units | €4.384m net sales | 46.3% contribution margin")
    country_order = ["DEU", "FRA", "NLD", "POL", "CZE", "ESP"]
    annual = {r["country"]: r for r in M["countries"]}
    hbar(c, [(x, annual[x]["contribution_eur"]) for x in country_order], 52, 416, 485, row_h=38, max_value=max(annual[x]["contribution_eur"] for x in country_order), label_width=55)
    rounded(c, 579, 112, 326, 304, WHITE, 10, GRID)
    text(c, "2025 COUNTRY SNAPSHOT", 599, 389, 9, TEAL, FONT_B)
    snap = [["Market", "Net sales", "Contribution", "Margin"]]
    for country in country_order:
        r = annual[country]
        snap.append([country, money_k(r["net_sales_eur"]), money_k(r["contribution_eur"]), pct(r["margin"])])
    draw_table(c, 596, 366, [62, 83, 94, 65], snap[0], snap[1:], row_h=31, header_h=27, font_size=7.5, header_size=7, aligns=["left", "right", "right", "right"])
    wrap(c, "The generated input has exactly 209 eligible orders in each country. Market rank is an export description, not verified demand.", 599, 104, 290, 8.3, 11, MUTED)
    c.showPage()

    # Slide 3
    c.setFillColor(PALE); c.rect(0, 0, *size, fill=1, stroke=0)
    slide_header(c, 3, "CZE + ESP leads the defined scenarios", "Annual incremental contribution after recurring fixed costs; no probabilities assigned")
    comps = defaultdict(dict)
    for row in M["hub_scenarios"]:
        comps[row["country"]][row["scenario"]] = row
    option_labels = ["CZE+ESP", "POL+ESP", "NLD+ESP"]
    colors_s = [TEAL, NAVY, ORANGE, MUTED]
    x0, y0, plot_w, plot_h = 76, 136, 570, 285
    maxv = 350000
    for tick in range(5):
        yy = y0 + plot_h * tick / 4
        c.setStrokeColor(GRID); c.setLineWidth(0.5); c.line(x0, yy, x0 + plot_w, yy)
        right_text(c, f"€{maxv*tick/4/1000:,.0f}k", x0 - 8, yy - 2, 7, MUTED)
    for i, option in enumerate(option_labels):
        base_x = x0 + 37 + i * 178
        text(c, option, base_x - 4, 116, 8, NAVY, FONT_B)
        for j, scen in enumerate(("low", "base", "high", "stress")):
            val = comps[option][scen]["incremental_contribution_eur"]
            bar_h = plot_h * max(0, val) / maxv
            c.setFillColor(colors_s[j])
            c.roundRect(base_x + j * 28, y0, 19, bar_h, 3, fill=1, stroke=0)
            text(c, f"{val/1000:.0f}", base_x + j * 28 - 1, y0 + bar_h + 5, 6.5, MUTED)
    for j, scen in enumerate(("Low", "Base", "High", "Stress")):
        c.setFillColor(colors_s[j]); c.rect(695, 354 - j * 24, 9, 9, fill=1, stroke=0)
        text(c, scen, 710, 356 - j * 24, 8, INK)
    rounded(c, 680, 168, 228, 128, MINT, 9)
    text(c, "STRESS IS NOT A FORECAST", 696, 272, 8, NAVY, FONT_B)
    wrap(c, "CZE+ESP stress remains +€32.2k/year but stretches payback to ~7 years. NLD+ESP is more resilient under stress (+€107.6k) while giving up €31.2k in the base case and using €45k more capex plus one FTE.", 696, 252, 194, 8.3, 11.2, INK)
    c.showPage()

    # Slide 4
    c.setFillColor(PALE); c.rect(0, 0, *size, fill=1, stroke=0)
    slide_header(c, 4, "The choice is sensitive to modest relative uplift differences", "CZE + ESP is the base leader; rankings are estimates from synthetic planning assumptions")
    rounded(c, 44, 123, 418, 296, WHITE, 10, GRID)
    text(c, "NEXT BASE-CASE ALTERNATIVE", 64, 390, 8, TEAL, FONT_B)
    text(c, "POL + ESP", 64, 360, 18, NAVY, FONT_B)
    wrap(c, "CZE+ESP is +€11.8k/year in base and +€2.9k in stress, while requiring €15k less capex and one fewer FTE. It is ahead in low, base, high and stress scenarios.", 64, 333, 370, 9, 12.5, INK)
    text(c, "STRESS-RESILIENT ALTERNATIVE", 64, 258, 8, ORANGE, FONT_B)
    text(c, "NLD + ESP", 64, 229, 18, NAVY, FONT_B)
    wrap(c, "Stress contribution is €107.6k/year vs €32.2k for CZE+ESP, at the cost of €31.2k lower base contribution, €45k more capex and one more FTE.", 64, 205, 370, 9, 12.5, INK)
    rounded(c, 490, 123, 420, 296, MINT, 10)
    text(c, "SWITCH CONDITION", 512, 390, 8, NAVY, FONT_B)
    sw = RECO["base_rank_switch_example"]
    text(c, f"CZE uplift threshold: {100*sw['selected_site_uplift_threshold_if_alternative_site_uplift_is_25pct']:.1f}%", 512, 355, 16, NAVY, FONT_B)
    wrap(c, "Holding ESP and every other input constant, if the validated CZE volume uplift is below this threshold while POL reaches the policy's 25% base uplift, POL+ESP overtakes on modeled annual contribution. The supplied model assumes the same uplift across countries.", 512, 326, 370, 9, 12.2, INK)
    text(c, "What could reverse the recommendation", 512, 237, 9, TEAL, FONT_B)
    wrap(c, "Lower CZE order density or savings; higher actual site/fixed cost; staffing constraints; or a board preference for stress resilience rather than base-case return. Defer remains valid if validation fails.", 512, 216, 370, 9, 12.2, INK)
    wrap(c, "No causal effect or statistical certainty is claimed. The scenario policy specifies assumptions, not observed hub outcomes.", 44, 82, 850, 8.5, 11, MUTED)
    c.showPage()

    # Slide 5
    c.setFillColor(PALE); c.rect(0, 0, *size, fill=1, stroke=0)
    slide_header(c, 5, "90-day staged implementation", "Functional owners are proposed; validate current operating data before committing to either site")
    milestones = [
        ("0–30", "VALIDATE", "CFO / FP&A + Operations", "Rebuild actual order/return baseline; verify uplift, savings, capex, fixed cost, FX and site shortlist.", "Gate: CZE still beats POL+ESP at current inputs; no contract."),
        ("31–60", "DESIGN", "Procurement / Facilities + HR", "Secure comparable quotations, staffing, lease/compliance review, inventory/returns workflow and staged terms.", "Gate: five FTE feasible; capex ≤€225k; fixed cost ≤€95k/year."),
        ("61–90", "PROVE", "Regional Ops + Analytics", "Pilot one site, then release the second only after economics and service check; weekly KPI review.", "Gate: annualized gain ≥ low case (€64.6k) and customer-promise KPI holds."),
    ]
    for i, (period, title, owner, action, gate) in enumerate(milestones):
        xx = 44 + i * 292
        rounded(c, xx, 179, 270, 240, WHITE, 10, GRID)
        rounded(c, xx + 16, 378, 69, 24, NAVY, 5)
        c.setFillColor(WHITE); c.setFont(FONT_B, 8); c.drawCentredString(xx + 50, 386, f"DAY {period}")
        text(c, title, xx + 16, 346, 15, NAVY, FONT_B)
        wrap(c, owner, xx + 16, 325, 237, 8, 10, TEAL, FONT_B)
        wrap(c, action, xx + 16, 293, 237, 8.1, 11, INK)
        c.setStrokeColor(GRID); c.line(xx + 16, 222, xx + 254, 222)
        wrap(c, gate, xx + 16, 207, 237, 8, 10.5, MUTED)
    rounded(c, 44, 73, 854, 78, MINT, 9)
    text(c, "WEEKLY KPI CONTROL", 62, 130, 8, NAVY, FONT_B)
    wrap(c, "Volume ≥1.25× validated country run rate; realized savings ≥€2.10/unit CZE and €3.00/unit ESP; refund-to-gross ratio tracked with a +3pp stress trigger; capex ≤€225k; recurring fixed cost ≤€95k/year; service target ≥95% of quoted promise after live baseline is set. These are proposed gates, not measured client targets.", 62, 111, 816, 8.3, 11, INK)
    c.showPage()

    # Slide 6
    c.setFillColor(PALE); c.rect(0, 0, *size, fill=1, stroke=0)
    slide_header(c, 6, "Board ask and evidence boundary", "Recommendation is conditional; decision should reopen on measured input changes")
    rounded(c, 44, 128, 487, 285, WHITE, 10, GRID)
    text(c, "APPROVE", 66, 378, 8, TEAL, FONT_B)
    text(c, "CZE + ESP | €225k | 5 FTE", 66, 344, 21, NAVY, FONT_B)
    wrap(c, "Authorize the envelope with staged release. Require Gate 1 validation of live country volume, site capex, annual fixed cost and savings before binding commitments. Require Gate 3 low-case annual contribution ≥€64.6k before completing the second-site release.", 66, 311, 435, 9.2, 13, INK)
    text(c, "KEEP THE DECISION REVERSIBLE", 66, 217, 8, ORANGE, FONT_B)
    wrap(c, "If actual CZE uplift is below 22.2% while POL is at 25%, re-rank against POL+ESP. If downside resilience takes priority, compare NLD+ESP. If the low-case gate fails, defer.", 66, 197, 435, 9, 12.2, INK)
    rounded(c, 554, 128, 354, 285, MINT, 10)
    text(c, "EVIDENCE INCLUDED", 576, 378, 8, NAVY, FONT_B)
    wrap(c, "Synthetic client order pages, corrections, returns, unit costs, hub assumptions and policy; archived official ECB 2025 reference rates; archived official World Bank 2022–2024 population and current-US$ GDP per capita. Files, URLs and hashes are in the workbook/source register.", 576, 353, 310, 9, 12, INK)
    text(c, "MATERIAL LIMITS", 576, 258, 8, ORANGE, FONT_B)
    wrap(c, "No live customer data, customer interviews, site quotes, contracts, causal test, probabilities, or real transaction FX. Current-dollar GDP and population do not prove product demand. No full discounted cash-flow or ramp model.", 576, 237, 310, 8.8, 11.7, INK)
    wrap(c, "Raw source snapshot and reproducible scripts are delivered with this deck. Metrics and country-month detail are in meridian_analysis.xlsx and metrics.json.", 44, 92, 850, 8.3, 11, MUTED)
    c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    p1 = create_report()
    p2 = create_deck()
    print(f"Created {p1} and {p2}")
