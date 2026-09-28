"""Build the executive report and board deck as self-contained HTML print masters."""
from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEL = ROOT / "deliverables"
OUT = ROOT / "analysis" / "output"
NAME = {"DEU": "Germany", "FRA": "France", "NLD": "Netherlands", "POL": "Poland", "CZE": "Czechia", "ESP": "Spain"}
NAVY = "#17324d"
TEAL = "#087e8b"
GOLD = "#e4a23a"
RED = "#bc514b"
GREEN = "#277753"
PALE = "#e9f2f5"
MUTED = "#63717c"


def esc(v):
    return html.escape(str(v))


def money(v, cents=True):
    if v is None:
        return "—"
    return ("−" if v < 0 else "") + "€" + f"{abs(v):,.2f}" if cents else ("−" if v < 0 else "") + "€" + f"{abs(v):,.0f}"


def eur_k(v):
    return ("−" if v < 0 else "") + f"€{abs(v)/1000:,.1f}k"


def pct(v, digits=1):
    return "—" if v is None else f"{v*100:.{digits}f}%"


def years(v):
    return "—" if v is None else f"{v:.2f} y"


def label(country):
    return f"{NAME.get(country, country)} ({country})"


def table(headers, rows, cls="data"):
    head = "".join(f"<th>{esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in row) + "</tr>" for row in rows)
    return f'<table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def metric_card(label_text, value, note="", accent=TEAL):
    return f'<div class="metric" style="border-top-color:{accent}"><div class="mlabel">{esc(label_text)}</div><div class="mvalue">{value}</div><div class="mnote">{note}</div></div>'


def svg_country_bars(countries, width=1020, height=220):
    rows = sorted(countries, key=lambda x: x["contribution_eur"], reverse=True)
    margin_left, margin_right, top, bottom = 150, 90, 18, 28
    maxval = max(r["contribution_eur"] for r in rows)
    chartw = width - margin_left - margin_right
    gap = 7
    barh = (height - top - bottom - gap * (len(rows)-1)) / len(rows)
    pieces = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="2025 contribution by country">']
    for i, r in enumerate(rows):
        y = top + i * (barh + gap)
        w = chartw * r["contribution_eur"] / maxval
        pieces.append(f'<text x="{margin_left-12}" y="{y+barh*0.72:.1f}" text-anchor="end" font-size="15" fill="{NAVY}">{esc(r["country"])}</text>')
        pieces.append(f'<rect x="{margin_left}" y="{y:.1f}" width="{w:.1f}" height="{barh:.1f}" rx="3" fill="{TEAL if r["country"] in ("CZE","ESP") else "#9fb8c3"}"/>')
        pieces.append(f'<text x="{margin_left+w+9:.1f}" y="{y+barh*0.72:.1f}" font-size="14" fill="{NAVY}">€{r["contribution_eur"]/1000:,.1f}k</text>')
    pieces.append("</svg>")
    return "".join(pieces)


def svg_monthly_lines(monthly, width=1040, height=220):
    countries = list(NAME)
    months = [f"2025-{m:02d}" for m in range(1,13)]
    data = {(r["country"],r["month"]): r["contribution_eur"] for r in monthly}
    vals = [data[(c,m)] for c in countries for m in months]
    low, high = min(vals), max(vals)
    pad = 28; left = 45; right = 135; top=18; bottom=27
    plotw = width-left-right; ploth=height-top-bottom
    def y(v): return top+ploth-(v-low)/(high-low)*ploth
    lines = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Monthly contribution by country">']
    for i in range(4):
        v=low+(high-low)*i/3; yy=y(v)
        lines.append(f'<line x1="{left}" y1="{yy:.1f}" x2="{width-right}" y2="{yy:.1f}" stroke="#d9e2e6"/>')
        lines.append(f'<text x="{left-6}" y="{yy+4:.1f}" text-anchor="end" font-size="11" fill="{MUTED}">€{v/1000:.0f}k</text>')
    colors={"DEU":"#4b7083","FRA":"#899ca6","NLD":"#087e8b","POL":"#d08c32","CZE":"#277753","ESP":"#b95347"}
    for ci,c in enumerate(countries):
        pts=[]
        for j,m in enumerate(months):
            x=left+j*plotw/(len(months)-1); pts.append(f"{x:.1f},{y(data[(c,m)]):.1f}")
        lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{colors[c]}" stroke-width="2.5"/>')
        lines.append(f'<text x="{width-right+12}" y="{y(data[(c,months[-1])])+4:.1f}" font-size="12" font-weight="bold" fill="{colors[c]}">{c}</text>')
    for j in [0,2,4,6,8,10,11]:
        x=left+j*plotw/(len(months)-1)
        lines.append(f'<text x="{x:.1f}" y="{height-6}" text-anchor="middle" font-size="10" fill="{MUTED}">{months[j][5:]}</text>')
    lines.append("</svg>")
    return "".join(lines)


def svg_pairs(alternatives, width=1040, height=245, selected=True):
    pairs=[r for r in alternatives if "+" in r["label"]]
    pairs=sorted(pairs,key=lambda r:r["base"],reverse=True)[:5]
    left=190; right=75; top=26; bottom=28; gap=14
    maxv=max(max(r["base"],r["stress"]) for r in pairs)
    plotw=width-left-right
    rowh=(height-top-bottom-gap*(len(pairs)-1))/len(pairs)
    bits=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Top feasible hub pairs, base and stress">']
    for i,r in enumerate(pairs):
        y=top+i*(rowh+gap)
        bits.append(f'<text x="{left-12}" y="{y+rowh*.42:.1f}" text-anchor="end" font-size="14" font-weight="bold" fill="{NAVY}">{esc(r["label"])}</text>')
        for j,key in enumerate(["base","stress"]):
            yy=y+j*rowh*.44
            w=plotw*max(0,r[key])/maxv
            color=TEAL if key=="base" else (GREEN if r[key]>=0 else RED)
            bits.append(f'<rect x="{left}" y="{yy:.1f}" width="{w:.1f}" height="{rowh*.32:.1f}" rx="2" fill="{color}"/>')
            bits.append(f'<text x="{left+w+7:.1f}" y="{yy+rowh*.27:.1f}" font-size="11" fill="{NAVY}">{"Base" if key=="base" else "Stress"} {eur_k(r[key])}</text>')
    bits.append("</svg>")
    return "".join(bits)


def report_page(title, kicker, body, page_num):
    return f'<section class="page"><div class="pagehead"><span>MERIDIAN PARTS</span><span>{esc(kicker)}</span></div><h1>{title}</h1>{body}<div class="footer"><span>Decision support · Synthetic client inputs · Archive cut 27 Sep 2026</span><span>{page_num:02d}</span></div></section>'


def report_html(d):
    countries=d["countries"]
    monthly=d["monthly"]
    scenarios=d["hub_scenarios"]
    alternatives=d["option_comparison"]
    markets=d["market_context"]
    pop_change=d["country_population_change_2022_2024_pct"]
    byyear={c:{r["year"]:r for r in markets if r["country"]==c} for c in NAME}
    base_choice=next(r for r in alternatives if r["label"]=="CZE+ESP")
    risk_choice=next(r for r in alternatives if r["label"]=="NLD+ESP")
    second=next(r for r in alternatives if r["label"]=="POL+ESP")
    totals={k:sum(r[k] for r in countries) for k in ["shipped_orders","shipped_units","gross_sales_eur","refunds_eur","net_sales_eur","net_cogs_eur","fulfillment_eur","contribution_eur","returned_units"]}

    # Cover / recommendation.
    hero=(
        '<div class="eyebrow">BOARD DECISION | 2025 SHIPPED-ORDER ECONOMICS</div>'
        '<h2>Stage a Czechia + Spain<br>service-hub program</h2>'
        '<p class="lead">Approve a €225,000, five-FTE envelope in two releases. Open Spain first; hold Czechia’s €95,000 / two-FTE release until the day-90 evidence gate. This pair ranks first on the client’s 25% volume-uplift case and stays positive under the specified joint return/FX stress.</p>'
        '<div class="cards">'
        + metric_card("Base annual incremental contribution", money(base_choice["base"],False), f"after {money(base_choice['annual_fixed_eur'],False)} combined annual fixed cost", TEAL)
        + metric_card("Year-zero capex", money(base_choice["capex_eur"],False), "€225k below €450k ceiling", GOLD)
        + metric_card("Simple payback", years(base_choice["base_payback_years"]), "undiscounted, if base contribution persists", GREEN)
        + metric_card("Defined joint stress", money(base_choice["stress"],False), "positive; lower than NLD + ESP’s €107.6k", RED)
        + '</div>'
        + '<div class="columns"><div><h3>Why this choice</h3><ul><li>Highest feasible base-case annual contribution among six singles, eleven feasible pairs and defer.</li><li>Low case remains positive at €64.6k; stress remains positive at €32.2k.</li><li>Uses 5 of 7 FTE, €225k of €450k capex and assumes no pair synergy.</li></ul></div><div><h3>What would change it</h3><p>If the board sets a €50k minimum for the defined joint stress and otherwise ranks qualifying options by base contribution, choose <b>NLD + ESP</b>. It is the highest-base option clearing that floor: €107.6k stress versus €32.2k, giving up €31.2k in base and using €45k more capex plus one FTE.</p><p class="small">The contribution uplift and cost savings are client planning assumptions, not observed hub results. Keep the Czech release conditional.</p></div></div>'
        + '<div class="sourcebar">Basis: synthetic order/return/cost exports and synthetic hub assumptions; archived official ECB and World Bank snapshots. No live customer records, interviews or pilot outcomes were accessed.</div>'
    )

    # Country baseline full metrics.
    crows=[]
    for r in countries:
        crows.append([esc(r["country"]),f'{r["shipped_orders"]:,}',f'{r["shipped_units"]:,}',money(r["gross_sales_eur"]),money(r["refunds_eur"]),money(r["net_sales_eur"]),money(r["net_cogs_eur"]),money(r["fulfillment_eur"]),money(r["contribution_eur"]),f'{r["returned_units"]:,}',pct(r["margin"])])
    crows.append(["TOTAL",f'{totals["shipped_orders"]:,}',f'{totals["shipped_units"]:,}',money(totals["gross_sales_eur"]),money(totals["refunds_eur"]),money(totals["net_sales_eur"]),money(totals["net_cogs_eur"]),money(totals["fulfillment_eur"]),money(totals["contribution_eur"]),f'{totals["returned_units"]:,}',pct(totals["contribution_eur"]/totals["net_sales_eur"])])
    country_table=table(["Country","Orders","Units","Gross sales","Refunds","Net sales","Net COGS","Fulfillment","Contribution","Returned units","Margin"],crows,"dense")
    baseline_body=(
        '<div class="callout"><b>Decision signal.</b> 1,254 eligible shipments produced €4.08m gross sales and €2.03m contribution after refunds, recovered-cost treatment and nonrefundable fulfillment. Spain and Czechia had the largest country contributions, €421.9k and €397.3k.</div>'
        + country_table
        + '<div class="columns"><div><h3>Monthly contribution, EUR</h3><div class="chart">'+svg_monthly_lines(monthly)+'</div></div><div><h3>What the figures mean</h3><p>Gross sales are the order’s quantity × local price less discount, translated at the original shipment month’s ECB monthly mean. Net sales subtract refunds known by 31 Jan 2026. Contribution then subtracts net COGS (including recovery only for restocked units) and actual nonrefundable fulfillment.</p><p><b>Booked revenue ≠ cash ≠ contribution.</b> Net sales are a retrospective shipment/refund measure, not settlement cash; timing, fees, tax and working-capital cash are outside this extract. Contribution also excludes company overhead and any hub’s recurring fixed cost.</p></div></div>'
        + '<div class="sourcebar">Monthly rows by country, every requested monetary component and return-unit total are in the workbook and metrics.json; all 72 monthly rows reconcile to these country totals.</div>'
    )

    # Macro and FX page.
    market_rows=[]
    for c in NAME:
        y22,y23,y24=byyear[c][2022],byyear[c][2023],byyear[c][2024]
        chg=f'{pop_change[c]:+.2f}%' if pop_change[c] is not None else "—"
        gdp22=f'${y22["gdp_per_capita_usd"]:,.0f}' if y22["gdp_per_capita_usd"] is not None else "—"
        gdp24=f'${y24["gdp_per_capita_usd"]:,.0f}' if y24["gdp_per_capita_usd"] is not None else "—"
        market_rows.append([esc(c),f'{y22["population"]:,}' if y22["population"] is not None else "—",f'{y24["population"]:,}' if y24["population"] is not None else "—",chg,gdp22,gdp24])
    market_table=table(["Market","Population 2022","Population 2024","Change 2022–24","GDP pc 2022¹","GDP pc 2024¹"],market_rows,"data compact")
    fxrows=[]
    for m in range(1,13):
        mon=f"2025-{m:02d}"
        pln=next(r["local_per_eur"] for r in d["fx_monthly"] if r["currency"]=="PLN" and r["month"]==mon)
        czk=next(r["local_per_eur"] for r in d["fx_monthly"] if r["currency"]=="CZK" and r["month"]==mon)
        fxrows.append([mon,f'{pln:.6f}',f'{czk:.6f}'])
    fx_table=table(["Month","PLN per EUR","CZK per EUR"],fxrows,"data compact")
    macro_body=(
        '<div class="columns macro"><div><h3>Market context</h3>'+market_table+'<p class="small">Population comes from archived World Bank SP.POP.TOTL; GDP per capita from NY.GDP.PCAP.CD. The 2022–24 population change and 2024 income levels are context only: neither establishes aftermarket demand. ¹ Current US dollars per person, not PPP or constant-price income. Missing years remain missing in the machine-readable output.</p></div><div><h3>ECB reference-rate monthly means</h3>'+fx_table+'<p class="small">Arithmetic mean of available published business-day observations in each 2025 calendar month. ECB quote is local currency units per EUR and is not inverted. The original sale month’s mean is applied to both gross sale and summed refunds. EUR markets use 1.000000.</p></div></div>'
        + '<div class="callout pale"><b>Context is not demand.</b> Spain (+2.22%) and Czechia (+2.18%) had the strongest 2022–24 population growth among these markets; Poland declined 0.71%. 2024 GDP per capita ranges from $25.1k in Poland to $67.5k in the Netherlands. These macro series do not measure vehicle parc, installed base, product eligibility or service-distance economics.</div>'
        + '<div class="sourcebar">Archived World Bank API responses carry a 2026-07-13 last-updated vintage; archived ECB historical reference rates were collected 2026-09-27. The report uses the source-room snapshots and does not claim a live refresh.</div>'
    )

    # Six individual country options.
    single_rows=[]
    for c in NAME:
        sc={r["scenario"]:r for r in scenarios if r["country"]==c}
        opt=next(r for r in d["option_comparison"] if r["label"]==NAME[c])
        single_rows.append([esc(c),money(sc["low"]["incremental_contribution_eur"],False),money(sc["base"]["incremental_contribution_eur"],False),money(sc["high"]["incremental_contribution_eur"],False),money(sc["stress"]["incremental_contribution_eur"],False),money(opt["capex_eur"],False),money(opt["annual_fixed_eur"],False),f'{opt["fte"]}',years(opt["base_payback_years"])])
    singles=table(["Hub","Low","Base","High","Stress","Capex (yr 0)","Fixed / year","FTE","Base payback"],single_rows,"dense")
    singles_body=(
        '<div class="formula"><b>Annual incremental contribution (recurring fixed cost already deducted):</b> low/base/high = C×u + U×(1+u)×s − F, where u=10%/25%/40%. Simple payback = capex ÷ positive annual incremental contribution; otherwise null. Capex remains a separate year-zero outlay. All single hub options fit the €450k/7-FTE limits.</div>'
        + singles
        + '<div class="columns"><div><h3>Base case and volume sensitivity</h3><p>Spain is the strongest single option (€102.7k), followed by Czechia (€95.4k). Spain has a 1.27-year simple payback; Czechia 1.00 year. France and Germany have long simple paybacks (7.74 and 27.75 years) under this scenario. Poland’s normal cases are attractive, but its defined joint stress is −€40.7k.</p><p>CZE + ESP leads at all policy volume points: 10%, 25% and 40%. Extrapolating the linear formula below the 10% low case, deferral leads below about 2.62% uplift, Czechia alone leads from about 2.62% to 2.85%, and CZE + ESP leads above about 2.85%. These breakpoints are computed from fixed synthetic point assumptions, not observed demand ranges.</p></div><div><h3>Stress definition</h3><p>At 25% volume uplift, the model adds refunds equal to 3% of gross sales with no extra cost recovery and applies a further 10% reduction to net sales in PLN/CZK markets. This is a deliberately conservative joint scenario, not a forecast probability. The FX stress applies to Poland and Czechia only.</p></div></div>'
        + '<div class="sourcebar">Input C is 2025 contribution; U is 2025 shipped units; s and F are client option assumptions. No measured hub attribution, local staffing quote or market-specific demand uplift was supplied.</div>'
    )

    # All feasible pairs + defer.
    pair_rows=[]
    for r in alternatives:
        if "+" not in r["label"]: continue
        pair_rows.append([esc(r["label"]),money(r["low"],False),money(r["base"],False),money(r["high"],False),money(r["stress"],False),money(r["capex_eur"],False),money(r["annual_fixed_eur"],False),str(r["fte"]),years(r["base_payback_years"])])
    pair_rows.append(["Defer",money(0,False),money(0,False),money(0,False),money(0,False),money(0,False),money(0,False),"0","—"])
    pairs=table(["Feasible pair / defer","Low","Base","High","Stress","Capex (yr 0)","Fixed / year","FTE","Base payback"],pair_rows,"dense pairs")
    pair_body=(
        '<p class="small">All 15 possible pairs were screened; 11 satisfy both €450k capex and seven-FTE limits. Table rows are the 11 feasible pairs plus defer. Pair economics add country outcomes with no synergy; annual fixed cost is included in the scenario totals.</p>'
        + pairs
        + '<div class="columns"><div><h3>Top base-case pairs</h3><div class="chart">'+svg_pairs(alternatives)+'</div></div><div><h3>Choice and concession</h3><p><b>CZE + ESP</b> leads the base case at €198.1k, €225k capex, five FTE and 1.14-year payback. Its low case is +€64.6k; stress is +€32.2k.</p><p><b>POL + ESP</b> is the closest base alternative at €186.3k (+€58.6k low; +€29.3k stress), but costs €15k more capex and one additional FTE.</p><p><b>NLD + ESP</b> gives up €31.2k in base contribution and uses €45k more capex and one more FTE than the recommendation. It is the best stress and worst-case-floor pair: +€107.6k stress and +€44.0k low. If the board sets a €50k minimum stress floor and otherwise ranks qualifying options by base contribution, NLD + ESP is the highest-base pair clearing that floor.</p><p class="small">Capex is a year-zero amount, separate from annual fixed cost. Payback is simple, undiscounted and excludes ramp time.</p></div></div>'
    )

    # 90-day plan + KPIs.
    roadmap=table(["Window / owner","Work and dependency","Decision gate"],[
        ["Days 0–15<br><b>COO sponsor</b>; Finance Controller + BI lead", "Re-run the base with actual operational exports; validate order/return join, FX, SKU costs, customer locations and current delivery baseline. Select candidate sites only after lane and lease diligence. Establish one version-controlled metric definition.", "Gate 1: no lease or hiring. Finance signs actual baseline and revised low/base/stress; board confirms CZE+ESP or switches under the stress-floor rule."],
        ["Days 16–35<br><b>EU Operations lead</b>; Procurement, HR, Legal", "Validate site, inventory, staffing, employment/tax, systems, security and service partner costs. Stage Spain first (3 FTE, €130k capex assumption) because the standalone stress case is +€70.0k. Keep spend cancellable pending diligence.", "Gate 2: release Spain only if capex remains within €130k plan, staffing within 3 FTE, and the refreshed annual contribution case stays positive in low and stress."],
        ["Days 36–65<br><b>Spain Hub Manager</b>; Supply Chain + IT", "Launch limited SKU / customer lane pilot; keep central-hub control group and record order timestamps, delivery promise, unit savings, return reasons, stock recovery and actual local fixed costs.", "Weekly review: no scale if service is worse than central baseline, actual saving is below €3.00/unit assumption, or refunds exceed the stress allowance."],
        ["Days 66–90<br><b>COO + CFO</b>; Czech Operations lead", "Review rolling eight-week pilot and build the Czech readiness case. Czech option assumes €2.10/unit savings, €40k fixed cost, €95k capex and two FTE. Continue measurement if uplift is seasonal or inconclusive.", "Gate 3: release Czech only when measured run-rate supports ≥25% volume uplift, saving ≥€2.10/unit, refund shock ≤3% of gross sales, combined annual contribution remains positive under defined stress, and total stays ≤€225k / 5 FTE. Otherwise defer Czech and retain Spain only."]
    ],"dense roadmap")
    kpis=table(["KPI / cadence","Target or trigger","Owner / evidence"],[
        ["Incremental shipped units vs baseline<br>weekly", "Annualized run-rate supports the modeled +25% uplift before Czech release; report order counts and units, not raw extract rows.", "BI + country managers; stable order_id / shipment definition."],
        ["Fulfillment savings per shipped unit<br>weekly", "≥€3.00 Spain; ≥€2.10 Czech (client assumptions used in model).", "Operations Finance; compare actual nonrefundable fulfillment cost to central baseline."],
        ["Refund shock and return recovery<br>monthly", "Incremental refund amount ≤3% of gross sales for stress gate; track returned and restocked units separately.", "Returns lead + Finance; preserve original sale-month FX and refund linkage."],
        ["Contribution after local recurring cost<br>monthly", "Annualized combined run-rate >€0 under stress; base case reference €198.1k/year.", "CFO; actual COGS recovery only for restocked goods, less actual hub fixed cost."],
        ["On-time delivery to promised date<br>weekly", "Proposed operating guardrail: ≥5 percentage-point improvement vs the day-15 baseline by pilot exit; board may reset before launch.", "Service lead; baseline is currently unavailable and must be measured before pilot."],
        ["Capex / staffing<br>monthly", "Cumulative ≤€225k for selected pair and ≤5 FTE; remain within overall €450k and seven-FTE board limits.", "CFO + HR; commitment ledger and named hires."],
    ],"dense kpis")
    plan_body='<div class="small note">Owners below are proposed role assignments for the plan; no actual Meridian employee or customer contact is represented. Site, employment, tax and service constraints require local diligence not present in the frozen data room.</div><div class="plan-grid">'+roadmap+'<div>'+kpis+'<p class="small">If early data cannot separate a seasonal change from hub effect, continue the pilot and hold the Czech tranche. The 90-day gate is a capital-control decision, not proof of causality.</p></div></div>'

    # Quality/source page.
    quality_body=(
        '<div class="columns"><div><h3>Reconciliation and exclusions</h3><ul><li>1,328 raw order rows across two pages and corrections → 13 exact duplicate rows removed, 18 lower revisions superseded, 1,297 unique order IDs selected.</li><li>2025 base: 1,254 shipped non-test orders. Excluded 24 cancelled/non-shipped records, 18 test orders and one 2026 shipment.</li><li>12 zero-price shipments were valid and retained as orders and units.</li><li>264 return rows → 20 exact duplicates removed, one lower revision superseded; 243 return IDs selected.</li><li>241 valid return IDs / 1,081 returned units included. One after-cutoff return excluded; one orphan quarantined (no guessed join).</li><li>No missing calculation fields among eligible shipments; no unresolved same-revision conflicts. All country totals reconcile to 12 monthly records.</li></ul></div><div><h3>Evidence and limits</h3><p><b>Synthetic client sources:</b> frozen source-room order pages, corrections, returns, data dictionary, unit costs, hub options and scenario policy. The room records synthetic generation and seed; no live client account, customer interview or real sales records were accessed.</p><p><b>Public archived sources:</b> [1] <a href="https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/SP.POP.TOTL?date=2022:2024&amp;format=json&amp;per_page=1000">World Bank population API response</a>; [2] <a href="https://api.worldbank.org/v2/country/DEU;FRA;NLD;POL;CZE;ESP/indicator/NY.GDP.PCAP.CD?date=2022:2024&amp;format=json&amp;per_page=1000">World Bank current-USD GDP-per-capita response</a>; [3] <a href="https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip">ECB historical reference-rate archive</a>.</p><p>Source-room archive retrieval is stamped 2026-09-27 06:36 UTC for official snapshots. World Bank responses report lastupdated 2026-07-13 and may include subsequent historical revisions. This analysis recollected the frozen files through the provided local source room at 2026-09-27 10:11 UTC. Per-file URL, collection time, SHA-256, period, units and status are in <b>deliverables/source_register.json</b>.</p></div></div>'
        + '<div class="limitations"><b>Limits that matter:</b> no customer-level market sizing, postcode or service-time baseline, actual operating quote, headcount cost, facility lease, causal pilot, probability weights or discount rate is supplied. GDP per capita and population are not product demand. ECB references are not settlement rates. Returns after 31 Jan 2026 are absent. Scenario math is undiscounted, annual, additive and excludes synergy, tax, working capital, ramp, terminal value and central overhead. Do not read the base case as statistically established or causal.</div>'
        + '<div class="sourcebar">Reproduction: python analysis/build_analysis.py → python analysis/build_workbook.py → python analysis/build_documents.py; then node analysis/render_documents.js. Saved inputs are under evidence/source_room/; environment/dependency notes in TOOLING.md.</div>'
    )

    pages=[
        report_page("European service hubs: fund in stages", "EXECUTIVE DECISION", hero, 1),
        report_page("The 2025 shipment base is strongest in Spain and Czechia", "OPERATING DIAGNOSIS", baseline_body, 2),
        report_page("Macro context supports comparison, not demand claims", "MARKET CONTEXT & FX", macro_body, 3),
        report_page("Czechia and Spain lead the single-hub base case", "INDIVIDUAL HUB OPTIONS", singles_body, 4),
        report_page("The two-hub winner gives up stress protection", "FEASIBLE PAIRS", pair_body, 5),
        report_page("Release capital against measurable operating gates", "90-DAY IMPLEMENTATION", plan_body, 6),
        report_page("Provenance is strong for arithmetic, limited for causality", "DATA QUALITY & LIMITATIONS", quality_body, 7),
    ]
    css=f"""
    @page {{ size:A4 landscape; margin:0; }}
    * {{ box-sizing:border-box; }}
    html,body {{ margin:0; padding:0; font-family:Arial,Helvetica,sans-serif; color:#24313a; background:#edf1f3; }}
    .page {{ width:297mm; height:210mm; padding:10mm 13mm 9mm; margin:0 auto; background:white; overflow:hidden; page-break-after:always; position:relative; }}
    .pagehead {{ display:flex; justify-content:space-between; border-bottom:1px solid #cdd9de; padding-bottom:2.4mm; color:{NAVY}; font-size:8pt; font-weight:bold; letter-spacing:1.1px; }}
    h1 {{ color:{NAVY}; font-size:21pt; margin:4mm 0 4mm; line-height:1.1; }}
    h2 {{ color:{NAVY}; font-size:30pt; line-height:1.04; margin:2mm 0 3mm; }}
    h3 {{ color:{TEAL}; font-size:11pt; margin:0 0 2mm; }}
    p {{ margin:1.5mm 0 2.6mm; font-size:9.1pt; line-height:1.36; }}
    ul {{ padding-left:5mm; margin:1.5mm 0 2.2mm; font-size:9pt; line-height:1.35; }}
    li {{ margin:0 0 1mm; }}
    a {{ color:{TEAL}; text-decoration:none; }}
    .eyebrow {{ font-size:9pt; font-weight:bold; letter-spacing:1.4px; color:{TEAL}; margin:4mm 0 3mm; }}
    .lead {{ font-size:13pt; line-height:1.38; max-width:260mm; margin:2mm 0 5mm; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:4mm; margin:4mm 0 5mm; }}
    .metric {{ border-top:3px solid {TEAL}; background:#f4f7f8; padding:3mm 3.5mm; min-height:23mm; }}
    .mlabel {{ color:{MUTED}; font-size:8pt; text-transform:uppercase; letter-spacing:.5px; }}
    .mvalue {{ color:{NAVY}; font-size:20pt; font-weight:bold; margin:1mm 0; }}
    .mnote {{ color:{MUTED}; font-size:8pt; line-height:1.25; }}
    .columns {{ display:grid; grid-template-columns:1fr 1fr; gap:7mm; margin-top:3mm; }}
    .columns > div {{ min-width:0; }}
    .callout {{ background:#eff7f7; border-left:4px solid {TEAL}; padding:3mm 4mm; margin:1mm 0 3mm; font-size:9.4pt; line-height:1.35; }}
    .callout.pale {{ border-color:{GOLD}; background:#fbf7ec; margin-top:3mm; }}
    .sourcebar {{ position:absolute; bottom:9mm; left:13mm; right:20mm; color:{MUTED}; border-top:1px solid #dbe3e6; padding-top:1.7mm; font-size:7pt; line-height:1.25; }}
    .footer {{ position:absolute; bottom:3.2mm; left:13mm; right:13mm; display:flex; justify-content:space-between; color:#85939b; font-size:7pt; }}
    .data {{ border-collapse:collapse; width:100%; font-size:8.4pt; margin:2mm 0; }}
    .data th {{ background:{NAVY}; color:white; text-align:left; padding:1.8mm 2mm; }}
    .data td {{ padding:1.55mm 2mm; border-bottom:1px solid #dfe7ea; }}
    .data tbody tr:nth-child(even) {{ background:#f5f8f9; }}
    .dense {{ border-collapse:collapse; width:100%; font-size:7.5pt; margin:2mm 0; }}
    .dense th {{ background:{NAVY}; color:white; text-align:left; padding:1.5mm 1.7mm; }}
    .dense td {{ padding:1.5mm 1.7mm; border-bottom:1px solid #dfe7ea; white-space:nowrap; }}
    .dense tbody tr:nth-child(even) {{ background:#f5f8f9; }}
    .dense tbody tr:first-child td {{ }}
    .pairs {{ border-collapse:collapse; width:100%; font-size:7.1pt; margin:1.5mm 0; }}
    .pairs th {{ background:{NAVY}; color:white; text-align:left; padding:1.25mm 1.5mm; }}
    .pairs td {{ padding:1.15mm 1.5mm; border-bottom:1px solid #dfe7ea; white-space:nowrap; }}
    .pairs tbody tr:nth-child(even) {{ background:#f5f8f9; }}
    .compact {{ font-size:8pt; }}
    .small {{ color:{MUTED}; font-size:7.6pt; line-height:1.35; }}
    .formula {{ background:#f3f6f7; padding:2.5mm 3mm; border-radius:2mm; margin-bottom:2mm; font-size:8.5pt; line-height:1.35; }}
    .chart svg {{ width:100%; height:auto; max-height:58mm; }}
    .macro {{ margin-top:1mm; grid-template-columns:1.15fr .85fr; gap:8mm; }}
    .macro .data {{ font-size:8pt; }}
    .roadmap {{ font-size:7.1pt; table-layout:fixed; }} .roadmap th {{ padding:1.4mm; }} .roadmap td {{ padding:1.7mm; vertical-align:top; line-height:1.25; white-space:normal; overflow-wrap:anywhere; }}
    .roadmap th:nth-child(1) {{ width:24%; }} .roadmap th:nth-child(2) {{ width:41%; }} .roadmap th:nth-child(3) {{ width:35%; }}
    .kpis {{ font-size:7.0pt; table-layout:fixed; }} .kpis th {{ padding:1.3mm; }} .kpis td {{ padding:1.45mm; vertical-align:top; line-height:1.2; white-space:normal; overflow-wrap:anywhere; }}
    .plan-grid {{ display:grid; grid-template-columns:1.2fr .8fr; gap:6mm; }} .plan-grid > div {{ min-width:0; }}
    .note {{ background:#fbf7ec; padding:2mm 3mm; margin:1mm 0 3mm; }}
    .limitations {{ background:#f8f2e9; border-left:4px solid {GOLD}; padding:3mm 4mm; margin-top:4mm; font-size:8.5pt; line-height:1.35; }}
    """
    return '<!doctype html><html><head><meta charset="utf-8"><title>Meridian Parts European service hubs — Executive report</title><style>'+css+'</style></head><body>'+"".join(pages)+'</body></html>'


def slide_html(d):
    alternatives=d["option_comparison"]
    countries=d["countries"]
    base=next(r for r in alternatives if r["label"]=="CZE+ESP")
    risk=next(r for r in alternatives if r["label"]=="NLD+ESP")
    runner=next(r for r in alternatives if r["label"]=="POL+ESP")
    def slide(title, eyebrow, content, num):
        return f'<section class="slide"><div class="shead"><b>MERIDIAN PARTS</b><span>{esc(eyebrow)}</span></div><h1>{title}</h1>{content}<div class="sfoot"><span>Source: frozen synthetic client room + archived ECB / World Bank snapshots · Scenario arithmetic, not causal proof</span><span>{num:02d}</span></div></section>'
    # Slide 1
    s1=(f'<div class="hero">STAGE CZECHIA + SPAIN<br><span>Approve €225k / 5 FTE in two releases; Spain first, Czechia gated.</span></div><div class="cards">{metric_card("Base annual contribution",money(base["base"],False),f"after {money(base['annual_fixed_eur'],False)} recurring fixed cost",TEAL)}{metric_card("Low case",money(base["low"],False),"positive",GREEN)}{metric_card("Stress case",money(base["stress"],False),"positive; risk alternative is €107.6k",GOLD)}{metric_card("Simple payback",years(base["base_payback_years"]),"undiscounted",TEAL)}</div><div class="twocol"><div><h3>Funding envelope</h3><p class="big">€225,000 capex · 5 FTE</p><p>€225k below the €450k limit; 2 FTE below the seven-FTE limit. Pair adds country outcomes with no synergy.</p></div><div class="riskbox"><h3>Risk-sensitive choice</h3><p><b>NLD + ESP</b> earns €31.2k less in base, but €107.6k in stress. It becomes the preferred alternative if the board sets a €50k minimum stress floor and otherwise ranks qualifying options by base contribution.</p></div></div>')
    # Slide 2
    bars=svg_country_bars(countries,1000,265)
    s2=(f'<div class="twocol"><div><p class="big">1,254</p><p>eligible, distinct shipped orders · 72 reconciled country-month records</p><p class="big">€4.08m</p><p>gross sales · €2.03m 2025 contribution after returns, COGS and fulfillment</p><p>Spain (€421.9k) and Czechia (€397.3k) have the largest country contribution in the synthetic base.</p></div><div><h3>2025 contribution by country</h3>{bars}</div></div><div class="callout"><b>Booked sales, cash and contribution differ.</b> Net sales subtract refunds known by 31 Jan 2026; settlement timing/fees/tax are absent. Contribution further subtracts net COGS and nonrefundable fulfillment; central overhead and future hub cost are excluded.</div>')
    # Slide 3
    s3=('<div class="threecards"><div class="panel"><h3>Czechia</h3><p class="big">€397.3k</p><p>2025 contribution · 13,733 units · 48.7% margin</p><p>Hub assumptions: €95k capex, 2 FTE, €40k annual fixed cost, €2.10/unit saving.</p></div><div class="panel"><h3>Spain</h3><p class="big">€421.9k</p><p>2025 contribution · 13,931 units · 49.6% margin</p><p>Hub assumptions: €130k capex, 3 FTE, €55k annual fixed cost, €3.00/unit saving.</p></div><div class="panel muted"><h3>Demand evidence gap</h3><p>Country volume and margins are observed only in the synthetic extract; no city/postcode demand, service-distance, competitor, or installed-base data are supplied.</p><p>Population/GDP series are context, not product demand.</p></div></div><div class="callout">Market context: Spain population +2.22% and Czechia +2.18% from 2022–24; GDP per capita in 2024 was $35.3k and $31.8k current USD, respectively. Poland population −0.71%; Netherlands GDP per capita $67.5k.</div>')
    # Slide 4
    top_pairs=[r for r in alternatives if "+" in r["label"]]
    top_pairs=sorted(top_pairs,key=lambda r:r["base"],reverse=True)[:4]
    pairtable=table(["Pair","Low","Base","High","Stress","Capex","Fixed/y","FTE"],[[esc(r["label"]),money(r["low"],False),money(r["base"],False),money(r["high"],False),money(r["stress"],False),money(r["capex_eur"],False),money(r["annual_fixed_eur"],False),str(r["fte"])] for r in top_pairs],"decktable")
    s4=(f'<div class="twocol"><div><h3>Best feasible pairs</h3>{pairtable}<p>11 of 15 country pairs fit €450k and seven FTE. Defer remains an available €0 option.</p></div><div><h3>Base vs stress across pairs</h3>{svg_pairs(alternatives,900,265)}</div></div><div class="callout">Base volume uplift is an explicit client assumption, not measured demand. Stress jointly adds refunds equal to 3% of gross sales and 10% net-sales depreciation for PLN/CZK markets.</div>')
    # Slide 5
    s5=(f'<div class="twocol"><div><h3>Base-led recommendation</h3><p class="big">CZE + ESP: {money(base["base"],False)} / year</p><p>{money(base["capex_eur"],False)} capex · {base["fte"]} FTE · {years(base["base_payback_years"])} simple payback</p><p>Low: {money(base["low"],False)} · Stress: {money(base["stress"],False)}</p><p>Closest base alternative, POL + ESP: {money(runner["base"],False)} base, {money(runner["stress"],False)} stress; costs €15k more and uses one more FTE.</p></div><div class="riskbox"><h3>Risk floor flips the choice</h3><p class="big">NLD + ESP: {money(risk["stress"],False)} stress</p><p>It gives up {money(base["base"]-risk["base"],False)} in base, adds €45k capex and one FTE. It is the highest-base alternative clearing a €50k stress floor.</p></div></div><div class="callout">CZE + ESP stays first at the 10% / 25% / 40% policy uplifts. Model extrapolation below 10% switches from defer at ~2.62% to Czechia solo, then to CZE + ESP at ~2.85%. The board can set a different stress floor; none was supplied.</div>')
    # Slide 6
    plan=table(["Days","Owner","Actions / dependency","Gate"],[
        ["0–15","COO; CFO / BI","Validate actual order, return, cost, FX and location baseline; site shortlist; no noncancelable lease.","Finance signs refreshed low/base/stress."],
        ["16–35","EU Ops; Procurement / HR / Legal","Site and lane diligence; Spain first; confirm capex, staffing, inventory, systems and local compliance.","Spain only if low + stress stay positive and within €130k / 3 FTE."],
        ["36–65","Spain Hub Manager; IT / Supply Chain","Limited launch; log promised vs actual delivery, order volume, unit saving, refunds, stock recovery and fixed cost.","Pause scale if service deteriorates or saving <€3/unit."],
        ["66–90","COO + CFO; Czech lead","Review rolling 8 weeks; build Czech readiness case; extend pilot if seasonality clouds signal.","Release Czech only if ≥25% volume run-rate, ≥€2.10/unit savings, refund shock ≤3% gross, stress contribution >0, total ≤€225k / 5 FTE."]
    ],"decktable plan")
    s6=(plan+'<div class="callout">Owners are proposed roles, not named employees. Site, tax, employment and lease diligence are dependencies; no site-level data were supplied.</div>')
    # Slide 7
    s7=('<div class="twocol"><div><h3>Scorecard</h3><ul><li>Weekly incremental order units vs baseline; day-90 run-rate needs to support +25% uplift before Czech release.</li><li>Measured fulfillment savings: ≥€3.00/unit Spain; ≥€2.10/unit Czech.</li><li>Incremental refund shock ≤3% of gross sales; report returned and restocked units separately.</li><li>Annualized contribution after local fixed cost positive under stress; capex ≤€225k and total staffing ≤5 FTE.</li><li>On-time to promise: proposed +5pp vs day-15 baseline by pilot exit; baseline is currently unknown.</li></ul></div><div><h3>Evidence & limits</h3><p>Order/return/cost/hub inputs are synthetic. Public inputs are archived World Bank 2022–24 population and current-USD GDP per capita and ECB daily reference rates averaged by month.</p><p>Returns are included only through 31 Jan 2026; ECB reference quotes are not actual transaction FX. The hub model is additive, undiscounted, annual and unvalidated; it excludes synergy, tax, ramp, working capital and terminal value.</p><p>No customer interviews, live account access, actual pilot or measured causal lift.</p></div></div><div class="sourcebar dark">Decision: stage Spain first; reserve Czech tranche until gate; switch to NLD + ESP if the board adopts a €50k minimum stress floor and otherwise ranks qualifying options by base contribution. Source register and checks in the analytical workbook.</div>')
    slides=[slide("Stage a Czechia + Spain service-hub program","BOARD DECISION",s1,1),slide("The shipment base concentrates value in Spain and Czechia","2025 BASELINE",s2,2),slide("Strong local economics; no direct market-demand evidence","WHY THESE MARKETS",s3,3),slide("CZE + ESP leads on base, not on stress floor","OPTION COMPARISON",s4,4),slide("Use a clear risk threshold to choose the alternative","TRADE-OFF",s5,5),slide("Release capital only after observable operating gates","90-DAY PLAN",s6,6),slide("Track uplift, savings, refunds, service and cash commitments","MEASUREMENT & LIMITS",s7,7)]
    css=f"""
    @page {{ size:13.333in 7.5in; margin:0; }} * {{ box-sizing:border-box; }}
    html,body {{ margin:0; padding:0; background:#edf1f3; font-family:Arial,Helvetica,sans-serif; color:#24313a; }}
    .slide {{ width:13.333in; height:7.5in; padding:.38in .55in .34in; margin:0 auto; overflow:hidden; page-break-after:always; position:relative; background:#fff; }}
    .shead {{ border-bottom:1px solid #d6e0e4; padding-bottom:.10in; color:{NAVY}; display:flex; justify-content:space-between; font-size:9pt; letter-spacing:1px; }}
    h1 {{ color:{NAVY}; font-size:25pt; margin:.18in 0 .16in; line-height:1.08; }} h3 {{ color:{TEAL}; font-size:12pt; margin:0 0 .08in; }}
    p {{ font-size:11pt; line-height:1.32; margin:.07in 0 .12in; }} ul {{ font-size:10.5pt; line-height:1.36; padding-left:.24in; }} li {{ margin-bottom:.08in; }}
    .hero {{ color:{NAVY}; font-size:34pt; font-weight:bold; line-height:1.08; margin:.35in 0 .25in; }} .hero span {{ display:inline-block; margin-top:.10in; font-size:18pt; font-weight:normal; color:{TEAL}; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:.12in; margin:.20in 0 .25in; }} .metric {{ background:#f4f7f8; border-top:3px solid {TEAL}; padding:.10in .13in; min-height:.93in; }}
    .mlabel {{ color:{MUTED}; font-size:8.2pt; text-transform:uppercase; }} .mvalue {{ font-size:19pt; font-weight:bold; color:{NAVY}; margin:.06in 0; }} .mnote {{ font-size:8.3pt; color:{MUTED}; }}
    .twocol {{ display:grid; grid-template-columns:1fr 1fr; gap:.25in; align-items:start; }} .threecards {{ display:grid; grid-template-columns:repeat(3,1fr); gap:.18in; margin:.25in 0; }} .panel,.riskbox {{ background:#f4f7f8; border-left:4px solid {TEAL}; padding:.17in .2in; }} .riskbox {{ border-color:{GOLD}; background:#fbf7ec; }} .muted {{ border-color:#9baeb7; }}
    .big {{ font-size:20pt; font-weight:bold; color:{NAVY}; margin:.04in 0; }} .callout {{ background:#eff7f7; border-left:4px solid {TEAL}; padding:.13in .17in; margin:.16in 0; font-size:10pt; }}
    .decktable {{ width:100%; border-collapse:collapse; font-size:9pt; margin:.08in 0; }} .decktable th {{ background:{NAVY}; color:white; padding:.07in; text-align:left; }} .decktable td {{ padding:.07in; border-bottom:1px solid #dfe7ea; white-space:nowrap; }} .decktable tr:nth-child(even) {{ background:#f5f8f9; }}
    .plan {{ font-size:8.9pt; }} .plan th {{ padding:.07in; }} .plan td {{ white-space:normal; vertical-align:top; padding:.09in; line-height:1.25; }}
    .sfoot {{ position:absolute; bottom:.12in; left:.55in; right:.55in; display:flex; justify-content:space-between; color:#84929a; font-size:7.4pt; border-top:1px solid #dfe7ea; padding-top:.06in; }} .dark {{ color:white; background:{NAVY}; border-color:{GOLD}; }} .dark b {{ color:white; }} .sourcebar {{ padding:.13in .17in; }}
    """
    return '<!doctype html><html><head><meta charset="utf-8"><title>Meridian Parts — Board presentation</title><style>'+css+'</style></head><body>'+"".join(slides)+'</body></html>'


def main():
    metrics=json.loads((DEL/"metrics.json").read_text())
    (DEL/"executive_report.html").write_text(report_html(metrics),encoding="utf-8")
    (DEL/"board_presentation.html").write_text(slide_html(metrics),encoding="utf-8")
    print("Wrote self-contained HTML print masters for report and 7-slide board deck.")


if __name__ == "__main__":
    main()
