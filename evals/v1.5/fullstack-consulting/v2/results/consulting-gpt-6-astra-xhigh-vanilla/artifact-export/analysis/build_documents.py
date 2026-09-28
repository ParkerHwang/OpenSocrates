"""Generate the report and board deck as searchable, vector PDFs from metrics.json."""
from pathlib import Path
import json, csv, math
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.graphics import renderPDF

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'deliverables'
M=json.loads((OUT/'metrics.json').read_text()); C={r['country']:r for r in M['countries']}
S={(r['country'],r['scenario']):r for r in M['hub_scenarios']}
P={r['option']:r for r in M['portfolio_scenarios']}
REG=json.loads((ROOT/'evidence/source_register.json').read_text()); REGFILE={r['file']:r for r in REG}
T=M['totals'];Q=M['quality'];TH=M['decision_thresholds']
NAVY=colors.HexColor('#122C43'); TEAL=colors.HexColor('#008577'); GOLD=colors.HexColor('#D49A25'); RED=colors.HexColor('#B34A48'); LIGHT=colors.HexColor('#EDF4F6'); GRAY=colors.HexColor('#536675'); WHITE=colors.white
def eur(v,dec=0): return f'€{v:,.{dec}f}'
def k(v,dec=1):return f'{v/1000:,.{dec}f}'
def pct(v,dec=1):return f'{v*100:.{dec}f}%'
def years(v):return '—' if v is None else f'{v:.2f}'
def link(file,label=None):
    r=REGFILE[file];return f'<a href="../evidence/raw/{file}" color="#008577">{label or r["source_id"]}</a>'
def refs(files):return 'Sources: '+', '.join(link(f) for f in files)+'. Calculations: saved order ledger / metrics.json.'
ORD=['orders-part1.csv','orders-part2.csv','order-corrections.csv','returns.csv','unit-costs.csv','data-dictionary.md','ecb-history.csv']
SCEN=['hub-options.csv','scenario-policy.md']
styles={
 'kicker':ParagraphStyle('kicker',fontName='Helvetica-Bold',fontSize=9,leading=12,textColor=TEAL,spaceAfter=8),
 'h1':ParagraphStyle('h1',fontName='Helvetica-Bold',fontSize=24,leading=29,textColor=NAVY,spaceAfter=14),
 'h2':ParagraphStyle('h2',fontName='Helvetica-Bold',fontSize=12,leading=16,textColor=NAVY,spaceBefore=12,spaceAfter=6),
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=14,textColor=NAVY,spaceAfter=9),
 'small':ParagraphStyle('small',fontName='Helvetica',fontSize=8,leading=11,textColor=GRAY,spaceAfter=6),
 'table':ParagraphStyle('table',fontName='Helvetica',fontSize=8.3,leading=11,textColor=NAVY),
 'th':ParagraphStyle('th',fontName='Helvetica-Bold',fontSize=8,leading=10,textColor=WHITE),
}
def para(txt,sty='body'):return Paragraph(txt,styles[sty])
def table(headers,data,widths,fs=8.3,highlight=None,padding=6):
    sty=ParagraphStyle('cell',parent=styles['table'],fontSize=fs,leading=fs+3)
    matrix=[[Paragraph(str(v),styles['th']) for v in headers]]
    for row in data:matrix.append([Paragraph(escape(str(v)),sty) for v in row])
    tb=Table(matrix,colWidths=widths,hAlign='LEFT',repeatRows=1)
    commands=[('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),padding),('BOTTOMPADDING',(0,0),(-1,-1),padding),('LINEBELOW',(0,0),(-1,0),.5,NAVY)]
    for i in range(1,len(matrix)):
        if i%2==0:commands.append(('BACKGROUND',(0,i),(-1,i),LIGHT))
        if highlight is not None and str(data[i-1][0]) in highlight:commands.append(('BACKGROUND',(0,i),(-1,i),colors.HexColor('#D9EFE9')))
    tb.setStyle(TableStyle(commands));return tb

def bar_chart(labels,series,width=499,height=225,title='',unit='€k / year'):
    """Horizontal grouped bars with explicit zero line, labels and no clipped negatives."""
    d=Drawing(width,height);left=79;right=45;bottom=30;top=height-34
    values=[v/1000 for _,vs,_ in series for v in vs];vmin=min(0,min(values));vmax=max(values)
    vmin=math.floor(vmin/25)*25 if vmin<0 else 0;vmax=math.ceil(vmax/25)*25 or 1
    plotw=width-left-right;plotheight=top-bottom
    x=lambda v:left+(v-vmin)/(vmax-vmin)*plotw
    for i in range(5):
        v=vmin+(vmax-vmin)*i/4;xx=x(v);d.add(Line(xx,bottom,xx,top,strokeColor=colors.HexColor('#DCE5E8'),strokeWidth=.5));d.add(String(xx,bottom-12,f'{v:.0f}',fontName='Helvetica',fontSize=7,textAnchor='middle',fillColor=GRAY))
    d.add(Line(x(0),bottom,x(0),top,strokeColor=GRAY,strokeWidth=.8))
    group=plotheight/len(labels);bh=min(15,(group-10)/len(series))
    for i,l in enumerate(labels):
        center=top-(i+.5)*group;d.add(String(left-8,center-3,l,fontName='Helvetica-Bold',fontSize=8,textAnchor='end',fillColor=NAVY))
        for j,(name,vs,color) in enumerate(series):
            v=vs[i]/1000;y=center+(len(series)/2-j-1)*bh
            a=x(0);b=x(v);d.add(Rect(min(a,b),y,abs(b-a),bh-2,fillColor=color,strokeColor=None))
            d.add(String(b+(4 if v>=0 else -4),y+2,f'{v:.1f}',fontName='Helvetica',fontSize=7,textAnchor='start' if v>=0 else 'end',fillColor=NAVY))
    d.add(String(0,height-10,title,fontName='Helvetica-Bold',fontSize=10,fillColor=NAVY))
    d.add(String(width-2,1,unit,fontName='Helvetica',fontSize=7,textAnchor='end',fillColor=GRAY))
    lx=left
    for name,_,color in series:d.add(Rect(lx,1,7,7,fillColor=color,strokeColor=None));d.add(String(lx+11,1,name,fontName='Helvetica',fontSize=7,fillColor=GRAY));lx+=80
    return d

W,H=A4;CW=W-96
story=[];page_titles=[]
def start(num,title,kicker='BOARD DECISION | MERIDIAN PARTS'):
    if story:story.append(PageBreak())
    page_titles.append(title);story.extend([para(f'{kicker} / {num:02}', 'kicker'),para(title,'h1')])
def p(txt,sty='body'):story.append(para(txt,sty))
def t(headers,data,widths=None,**kwargs):story.append(table(headers,data,widths or [CW/len(headers)]*len(headers),**kwargs));story.append(Spacer(1,8))

start(1,'Fund Spain and Czechia in stages')
p('Reserve <b>€225,000 capex and five FTE</b> for two local hubs. Launch Spain first; release Czechia only after the operating-cost, demand and FX gates pass. The pair leaves €225,000 and two FTE unused against the board ceilings. This is a conditional allocation based on synthetic client economics, not a demand forecast.')
t(['Base annual increment','Low / high annual increment','Joint stress annual increment'],[[eur(P['CZE+ESP']['base_eur'],2),f"{eur(P['CZE+ESP']['low_eur'],2)} / {eur(P['CZE+ESP']['high_eur'],2)}",eur(P['CZE+ESP']['stress_eur'],2)]],[CW/3]*3)
p(f"Base simple payback is <b>{years(P['CZE+ESP']['base_payback_years'])} years</b>; low case {years(P['CZE+ESP']['low_payback_years'])} years; stress {years(P['CZE+ESP']['stress_payback_years'])} years. Recurring hub fixed cost is €95,000 a year, already deducted. Capex is a separate year-zero outflow. After one full base operating year, cumulative increment less capex remains {eur(P['CZE+ESP']['base_first_full_year_less_capex_eur'],2)}; ramp-up would delay recovery.")
p('Why these two markets','h2')
p(f"Spain and Czechia generate {pct((C['ESP']['contribution_eur']+C['CZE']['contribution_eur'])/T['contribution_eur'])} of existing contribution and {pct((C['ESP']['shipped_units']+C['CZE']['shipped_units'])/T['shipped_units'])} of shipped units. Their combined option ranks first in low, base and high volume cases. Poland plus Spain is the base runner-up: €11,770.47 less annual contribution, €15,000 more capex and one more FTE.")
p('What can overturn the choice','h2')
p('Czechia loses €37,826.95 annually under the prescribed stress; Spain remains positive at €70,006.66. Netherlands plus Spain has the highest feasible stress contribution, €107,630.13, but costs €270,000 and six FTE. If the board prioritizes the defined downside case, choose that portfolio instead. If operating gates fail, retain Spain only or defer both.')
p('The largest unverified inputs','h2')
p('The policy assumes 25% volume uplift and savings on every unit. Every supplied saving/unit exceeds recorded fulfillment cost/unit. The €95,000 combined fixed cost is assumed to cover all recurring hub expense, but payroll, lease and service coverage are unconfirmed. Approve a staged envelope, not an unconditional rollout.')
p(refs(ORD+SCEN),'small')
p('Prepared 27 September 2026. 2025 shipments; returns through 31 January 2026 inclusive. Core public calculations use the frozen official archives, not current data. All charts marked €k are rounded; the workbook and JSON retain cents.','small')

start(2,'A reconciled shipment cohort, not an order-row count')
t(['Order reconciliation','Records'],[['Extract pages + corrections','655 + 655 + 18 = 1,328'],['Less identical repeated rows','13'],['Less superseded rows','18'],['Selected distinct order IDs','1,297'],['Less cancelled / test / 2026 shipment','24 / 18 / 1'],['Eligible shipped orders','1,254']],[CW*.69,CW*.31])
p('Selection uses the highest numeric revision before testing eligibility. Corrections replace entire rows. All 12 zero-price shipments (739 units) remain in the cohort and contribute −€14,565.90 after product and fulfillment costs. All 24 blank shipment dates belong to cancelled records; no eligible required fields are missing.')
t(['Return reconciliation','Treatment'],[['264 raw return rows','20 exact repeats and one superseded revision removed → 243 IDs'],['241 eligible returns','1,081 physical units; 481 restocked units'],['R-CUTOFF: 2026-01-31','Included in original DEU December sale: €54 refund; €29.50 cost recovery'],['R-LATE: 2026-02-01','€33 refund excluded after cutoff'],['R-ORPHAN → ABSENT','Quarantined: 2 units, 1 restocked and 60 local currency; no currency/EUR inferred']],[CW*.39,CW*.61])
p('No eligible order has multiple return IDs in these files; the model nevertheless sums all distinct eligible IDs. Returns are restated against the original shipment month. This is a shipment-cohort view, not a cash receipts calendar. Later returns are deliberately outside the cutoff; late-2025 cohorts are less mature.')
p('Revenue, cash and contribution are different','h2')
p('Gross sales are shipped units × unit price less discounts, excluding taxes. Net sales deduct explicit eligible credits. This is the client’s booked-revenue proxy for the analysis; it is not a statutory revenue-recognition opinion. Cash depends on collections, payment terms, actual FX and refund settlement, none of which are supplied. Contribution deducts net product cost and nonrefundable fulfillment but excludes central overhead, hub fixed costs, capex, financing and taxes until separately modeled.')
p(refs(ORD),'small')

start(3,'Existing economics favor Spain and Czechia')
t(['Country','Units','Net sales €k','Contrib. €k','Margin','Returned units / shipped'],[[c,r['shipped_units'],k(r['net_sales_eur']),k(r['contribution_eur']),pct(r['margin']),pct(r['returned_unit_rate'],2)] for c,r in C.items()],[54,62,81,81,65,CW-343],highlight=['CZE','ESP'])
story.append(bar_chart(list(C),[('Contribution',[r['contribution_eur'] for r in C.values()],TEAL)],CW,190,'2025 contribution before any local hub','€k'))
p(f"The group generated <b>{eur(T['net_sales_eur'],2)} net sales</b> and <b>{eur(T['contribution_eur'],2)} contribution</b>, a {pct(T['margin'],2)} margin. Each market has 209 eligible orders; the revenue differences reflect shipped quantities, local prices, discounts, FX and mix rather than more order IDs. No customer identifier exists, so order counts cannot establish customer breadth or retention.")
p('Czechia and Spain have the highest observed returned-unit rates at 2.10% and 1.81%, respectively. Czechia recovered cost on 144 of 288 returned units; Spain on 108 of 252. Product-cost recovery is restricted to actual restocked quantities. Establish disposition controls before scaling either market.')
p('The extracts contain no delivery-time, stockout, conversion or lost-order evidence. Higher contribution makes a market financially attractive under the supplied policy, but does not establish that a local hub will cause incremental demand or that these sites can meet service expectations.')
p(refs(ORD),'small')

start(4,'Use population and income as context')
mk={(r['country'],r['year']):r for r in M['market_context']};chg={r['country']:r for r in M['market_changes']}
p('Population grew most in Spain and Czechia among these six markets between 2022 and 2024; Poland contracted. Germany remains the largest population base and the Netherlands has the highest current-US-dollar GDP per capita. These facts do not overturn the client economics or establish addressable assembly demand.')
t(['Population, persons','2022','2023','2024','2022–24'],[[c,*[f"{mk[c,y]['population']:,}" for y in [2022,2023,2024]],pct(chg[c]['population_change_pct'],2)] for c in C],[96,104,104,104,CW-408],fs=8)
t(['GDP/person, current US$','2022','2023','2024','2022–24'],[[c,*[f"{mk[c,y]['gdp_per_capita_usd']:,.0f}" for y in [2022,2023,2024]],pct(chg[c]['nominal_usd_gdp_per_capita_change_pct'],2)] for c in C],[119,96,96,96,CW-407],fs=8)
p('Spain added 1,062,738 people (+2.22%); Czechia added 232,910 (+2.18%). Poland lost 262,516 (−0.71%), while its GDP per capita in current US$ rose 32.88%. That combination illustrates why these indicators should not be converted into a unit-sales forecast. Nominal US-dollar movements include price and currency effects; they are neither PPP comparisons nor real-income growth.')
p('Evidence vintage and missingness','h2')
p('The archived World Bank responses contain all 18 country-year observations for each indicator, with no missing values. Both responses report <b>lastupdated 2026-07-13</b>; the source-room archive retrieved them on <b>2026-09-27 UTC</b>. These are revised historical observations collected after the sales year, not information demonstrated to be available to a 2025 decision-maker. Original values and precision remain in JSON and the workbook.')
p(refs(['population.json','gdp-per-capita.json','source-register.json']),'small')

start(5,'Translate historical sales at historical monthly rates')
fx={(r['currency'],r['month']):r for r in M['fx_monthly']}
t(['2025 month','PLN per EUR','CZK per EUR','Published days¹'],[[mo, f"{fx['PLN',mo]['local_per_eur']:.6f}",f"{fx['CZK',mo]['local_per_eur']:.6f}",fx['PLN',mo]['observations']] for mo in [f'2025-{i:02}' for i in range(1,13)]],[105,130,130,CW-365])
p('¹ Both currencies have the same observation count in each month: 255 published observations each over 2025. Means are arithmetic averages of available published business-day quotes. Full precision is retained; EUR is exactly 1. Do not invert the quote or substitute today’s spot rate. Sale and refund conversion both divide local value by the <b>original shipment month</b> mean. These reference rates are translation assumptions, not actual transaction rates.','small')
p('An auditable Czech order example','h2')
p('M5-07-003 shipped 91 SENSOR units on 5 July 2025. Gross CZK188,069.70 ÷ 24.624608695652… = €7,637.47 after half-up cent rounding. Its six returned units carry CZK12,400.20 explicit credit, converted using the same July rate to €503.57. Three restocked units recover €124.50 at the original €41.50 unit cost. Net COGS is €3,652.00; fulfillment is €133.94; contribution is <b>€3,347.96</b>.')
p('Select the most recent unit-cost effective date on or before shipment. The July cost changes apply to new July shipments; later returns retain the cost of their original shipment. Gross sales, summed refunds, gross COGS, recovered COGS and fulfillment are rounded per order, half up to cents, then aggregated. Margins are ratios of totals, not averages of order margins.')
p(refs(['ecb-history.csv','ecb-history.zip','data-dictionary.md','unit-costs.csv','returns.csv','orders-part1.csv']),'small')

start(6,'The six hub options have very different economics')
p('Annual increment = <b>C × u + U × (1 + u) × s − F</b>, where C is baseline contribution, U shipped units, s saving/unit and F annual fixed cost. Low/base/high uplift u is 10% / 25% / 40%. Prices, mix, unit economics and capacity are held constant. Savings apply to every shipped unit, including free shipments, as instructed by the client policy.')
t(['Country','Capex €k','FTE','Fixed €k/yr','Saving €/unit','Recorded fulfill. €/unit'],[[c,k(S[c,'base']['capex_eur'],0),S[c,'base']['fte'],k(S[c,'base']['annual_fixed_eur'],0),f"{S[c,'base']['saving_eur_per_unit']:.2f}",f"{C[c]['fulfillment_eur']/C[c]['shipped_units']:.2f}"] for c in C],[58,71,43,90,96,CW-358])
t(['Annual increment €k','Low','Base','High','Stress','Base payback, years'],[[c,*[k(S[c,sc]['incremental_contribution_eur']) for sc in ['low','base','high','stress']],years(S[c,'base']['payback_years'])] for c in C],[101,64,64,64,71,CW-364],highlight=['CZE','ESP'])
p('The joint stress adds refunds equal to 3% of original gross sales with no cost recovery and, in PLN/CZK markets, an FX loss equal to 10% of original net sales. It applies both shocks to the entire base-plus-uplift business: <b>(C − 0.03G − FX loss) × 1.25 − C + U × 1.25 × s − F</b>. It is measured against the unchanged normal baseline, so it is more conservative than stressing the incremental volume alone. Defer is zero by the specified comparison convention; this does not imply central operations are immune to shocks.')
p('All savings assumptions exceed the fulfillment costs visible in the ledger. Validate the additional avoidable cost pool and ensure savings are net of local handling. Fixed costs are treated as fully loaded for policy arithmetic, but detailed payroll, rent and coverage are absent. Proposed staff mix: Spain one site lead plus two service/warehouse associates; Czechia one site lead plus one associate. These role designs are assumptions, with no wage or capacity validation.')
p('Simple payback is capex divided by a positive annual increment; otherwise null. Negative stress increments for Germany, Poland and Czechia therefore have no positive stress payback. Capex is not an annual operating expense.','small')
p(refs(SCEN+['data-dictionary.md']),'small')

start(7,'Rank every feasible portfolio against deferral')
p('The table includes all 18 feasible choices: six singles, 11 pairs and defer. Pairs add economics without synergy. Ranked by base annual contribution; €k values are rounded. All scenario paybacks are in the workbook and JSON. Unused budget is not a reason to add a lower-value hub.','small')
feas=[p for p in M['portfolio_scenarios'] if p['feasible']]
t(['Rank / option','Capex €k','FTE','Low €k','Base €k','High €k','Stress €k','Base PB yrs'],[[str(r['base_rank'])+' '+r['option'],k(r['capex_eur'],0),r['fte'],*[k(r[sc+'_eur']) for sc in ['low','base','high','stress']],years(r['base_payback_years'])] for r in feas],[99,57,33,59,62,62,65,CW-437],fs=7.7,highlight=['1 CZE+ESP'],padding=3.5)
p('Four infeasible pairs','h2')
t(['Pair','Capex / FTE','Reason'],[[r['option'],f"{eur(r['capex_eur'])} / {r['fte']}",r['constraint']] for r in M['portfolio_scenarios'] if not r['feasible']],[105,143,CW-248],fs=8)
p('Czechia plus Spain also ranks first in the low and high cases. Poland plus Spain is closest in base economics. Netherlands plus Spain ranks fourth in base but first in stress, an important alternative for a board with a downside-first objective. Deferring all avoids capital and staffing commitments while retaining the existing central-hub baseline; its incremental contribution is zero.','small')
p(refs(SCEN),'small')

start(8,'Make the risk trade-off explicit')
labels=['CZE+ESP','POL+ESP','NLD+ESP','ESP only']
story.append(bar_chart(labels,[('Base',[P[x]['base_eur'] for x in ['CZE+ESP','POL+ESP','NLD+ESP','ESP']],TEAL),('Stress',[P[x]['stress_eur'] for x in ['CZE+ESP','POL+ESP','NLD+ESP','ESP']],RED)],CW,215,'Base return versus prescribed joint stress'))
p('The proposed pair beats Poland plus Spain in every prescribed scenario, with lower capex and staffing. Its base advantage is only €11,770.47 per year. If Czechia’s own uplift falls below <b>22.24%</b> while Poland retains 25%, the runner-up overtakes it. This one-way threshold assumes all other inputs are unchanged.')
p('The downside alternative is Netherlands plus Spain: €31,167.88 less base contribution, but €75,450.42 more stress contribution for €45,000 additional capex and one additional FTE. With the full 3% refund shock, an FX haircut above <b>2.60% of Czech net sales</b> makes Netherlands plus Spain outperform the recommended pair. Without the refund shock, the crossover is 3.06%. These are policy-style net-sales haircuts, not exact percentage currency depreciation.')
t(['CZE+ESP annual €k','No savings','50% savings','Full savings'],[[pct(u,0),*[k(next(r['incremental_contribution_eur'] for r in M['sensitivities'] if r['volume_uplift']==u and r['savings_realization']==sf)) for sf in [0,.5,1]]] for u in [0,.1,.25,.4]],[151,116,116,CW-383])
p('With no uplift, even full assumed savings lose €24,367.70 annually. With zero savings the pair needs <b>11.60% uplift</b> to break even; low uplift then loses €13,076.43. At base volume with savings capped at all recorded fulfillment cost, annual contribution falls to €164,331.65. This is only a sensitivity: it still assumes all fulfillment cost is avoidable. No probabilities or expected values are assigned to these scenarios.')
p(refs(SCEN+['data-dictionary.md']),'small')

start(9,'A 90-day plan with capital gates')
p('Proposed sequence, not work already performed. Spain is first because it remains positive in the joint stress without PLN/CZK exposure. Czechia’s release is contingent; the plan may end with one hub or continued deferral. Full modeled benefits start only after operational ramp-up, not automatically on day 90.')
t(['Stage / accountable owner','Work and dependencies','Decision gate / evidence'],[
['Days 1–15\nCFO + Finance data lead','Reconcile ledger to client systems; resolve orphan return; define cost pool, service baseline and return cohorts. COO verifies inventory/SKU flow.','Gate 0: zero unexplained reconciliation differences. Document what fixed cost covers. No leases or hiring commitments yet.'],
['Days 16–30\nCOO + Procurement; Sales lead','Obtain site, carrier and payroll quotes; test route economics with existing operations; log qualified pipeline and comparable conversion. Requires approved pilot cost and clean baseline.','Gate 1, CFO/board: Spain ≤€130k capex / 3 FTE; complete recurring cost estimate. Re-run cases using defensible savings. Demand evidence must support the chosen volume case; pause if low case becomes negative.'],
['Days 31–60\nSpain site lead + IT / Supply chain','After Gate 1: prepare Spain site, recruit 1 lead + 2 associates, integrate order/stock/returns records and train staff. Inventory and carrier readiness precede service launch.','Gate 2, COO: inventory accuracy ≥99%, dispatch readiness ≥95% against one-business-day target; 100% traceable trial orders/returns. Release go-live only on acceptance test.'],
['Days 61–90\nCFO + COO; Czech site lead','Track Spain cohorts; refresh demand, full cost and FX exposure for Czechia. Proposed Czech staff: 1 lead + 1 associate. Shared internal support effort must be costed.','Gate 3, board: Czechia ≤€95k / 2 FTE. Reassess NLD if FX haircut planning case exceeds 2.60% with full refund shock. If Czech case fails, hold capital or re-submit NLD+ESP.']
],[113,192,CW-305],fs=8.5)
p('Gate discipline','h2')
p('CFO owns financial definitions and signs the revised case. COO owns service capacity, safety and carrier readiness. Procurement owns contracted cost coverage; Sales owns qualified pipeline evidence; IT owns event-level instrumentation. The board alone releases each capex tranche or changes the country allocation. Staff limits cover direct hub roles; any additional resourcing must be included in the revised constraint test.')
p('Dependency and schedule risk','h2')
p('Lease availability, recruitment, systems integration and inventory placement are unverified. Do not promise both sites live within 90 days. Separate working capital, pilot spend and startup losses are not supplied and need a funding plan before release; if they cannot fit the envelope or receive board approval, pause the launch. A 90-day observation window cannot establish durable causal uplift or fully mature annual returns.')
p(refs(SCEN)+' Implementation dates, roles and targets are consultant proposals.','small')

start(10,'Measure service, economics and return quality')
p('Targets below are proposed gates, not observed client service performance. Record event timestamps, orders, units, SKU, currency, gross credits and restock disposition so Finance can recreate the cohort economics. Separate organic growth, price/mix, FX and hub service effects when interpreting uplift.')
t(['KPI / owner / cadence','Baseline and definition','Proposed target / action'],[
['Contribution run-rate\nCFO, monthly','Increment after all recurring hub costs. Compare against central baseline using fixed definitions and reconciled orders.','Track €102,716.37 Spain and €95,382.94 Czechia base annual increments after ramp. If rolling 8-week annualized increment is negative, stop expansion and revise plan.'],
['Volume uplift\nSales lead, weekly','2025 units: ESP 13,931; CZE 13,733. Normalize by matched calendar weeks and track paid/free mix.','Base assumption 25%; report 10/25/40% range. No causal claim from a before/after comparison; use a matched untreated segment where feasible.'],
['Saving per shipped unit\nOps Finance, weekly','Current fulfillment/unit: ESP €1.63; CZE €1.52. Savings targets are €3.00 / €2.10 and require a broader avoidable cost pool.','Demonstrate net avoidable cost in invoices, including local handling. Escalate any unvalidated cost category; recompute low/base before further spend.'],
['Service and inventory\nSite lead, daily','No historical delivery SLA or inventory-accuracy baseline supplied; establish during days 1–15.','≥95% dispatch within one business day; ≥99% inventory accuracy at launch. Log stockouts and delivery completion, not only dispatch.'],
['Returns and recovery\nQuality lead, weekly / monthly','Returned units / shipped: ESP 1.81%; CZE 2.10%. Restocked / returned: ESP 42.86%; CZE 50.00%.','On comparable matured cohorts, no increase above baseline rate; no recovery below baseline without root-cause review. Monitor refunds separately as % gross.'],
['FX / capital / staffing\nTreasury + CFO, monthly','Policy FX haircut is on net sales, not spot quote. Capex ceiling €225k for proposed pair; 5 FTE.','Report CZK cash and translation exposure separately. Escalate planned haircut ≥2.60% with refund shock. No commitments above approved capex/FTE.']
],[119,184,CW-303],fs=8)
p('Risk controls and honest limits','h2')
p('Uplift is unmeasured: use documented pipeline, matched comparisons and sensitivity gates. Cost scope is incomplete: sign off fully loaded recurring expense and avoidable savings. Currency stress concentrates in Czechia: Treasury should validate invoicing and risk policy before considering hedges; none is priced here. Return maturity differs by cohort: compare like-for-like windows and continue monitoring beyond 90 days. No customer interviews, live client account access or site diligence were performed.')
p(refs(ORD+SCEN)+' KPI targets and governance are proposed.','small')

start(11,'Exact financial bridge and reconciliation')
t(['Country','Gross sales EUR','Refunds EUR','Net sales EUR'],[[c,eur(r['gross_sales_eur'],2),eur(r['refunds_eur'],2),eur(r['net_sales_eur'],2)] for c,r in C.items()]+[['TOTAL',eur(T['gross_sales_eur'],2),eur(T['refunds_eur'],2),eur(T['net_sales_eur'],2)]],[62,149,125,CW-336],fs=8.4)
t(['Country','Net COGS EUR','Fulfillment EUR','Contribution EUR'],[[c,eur(r['net_cogs_eur'],2),eur(r['fulfillment_eur'],2),eur(r['contribution_eur'],2)] for c,r in C.items()]+[['TOTAL',eur(T['net_cogs_eur'],2),eur(T['fulfillment_eur'],2),eur(T['contribution_eur'],2)]],[62,149,125,CW-336],fs=8.4)
p(f"Gross COGS of {eur(T['gross_cogs_eur'],2)} less {eur(T['recovered_cogs_eur'],2)} recovered from restocked goods gives {eur(T['net_cogs_eur'],2)} net COGS. Gross sales less refunds gives net sales; subtract net COGS and fulfillment to obtain contribution. Returned units are physical units, not order counts.")
p('Seventy-two country-month records cover all six countries and all twelve calendar months. Every additive metric reconciles exactly from eligible order components to months to country totals. The workbook Reconciliation sheet shows zero differences for orders, units, gross sales, refunds, net sales, net COGS, fulfillment, contribution and returned units. Full monthly records are in the workbook, metrics.json and deliverables/data/monthly.csv.')
p('Margin is contribution divided by net sales, or null when net sales are zero. At group level, the ratio is 46.307183%; average country or order margins would give a different statistic. Fulfillment remains nonrefundable even when product is returned; unreusable returns do not recover COGS.')
p(refs(ORD),'small')

start(12,'Evidence, reproducibility and decision limits')
t(['Source group','Provenance and use'],[
['Synthetic transactions\nS07–S09, S11','orders-part1.csv, orders-part2.csv, order-corrections.csv and returns.csv. One SKU per order; order and return revisions independently resolved.'],
['Synthetic accounting / options\nS02, S06, S12, S14','data-dictionary.md, hub-options.csv, scenario-policy.md, unit-costs.csv. Define accounting and scenario rules; costs/uplift are client inputs, not observed public market estimates.'],
['Official public archive\nS10 / S05','World Bank SP.POP.TOTL and NY.GDP.PCAP.CD. 2022–2024, persons and current US$/person. Metadata lastupdated 2026-07-13; archive collection 2026-09-27 UTC.'],
['Official public archive\nS03 / S04','ECB eurofxref historical CSV and ZIP. Selected 2025 PLN/CZK daily quotes; full ZIP extraction checked byte-for-byte against CSV.'],
['Collection / provenance\nS01 / S13','Frozen source-room index and original source-register.json preserved. Analyst collection time, URL, SHA-256, size, period, units and synthetic/public status recorded for each saved file.']
],[153,CW-153],fs=8.5)
p('Direct evidence links','h2')
p('Transactions: '+', '.join(link(f,f) for f in ['orders-part1.csv','orders-part2.csv','order-corrections.csv','returns.csv'])+'.<br/>Policy: '+', '.join(link(f,f) for f in ['data-dictionary.md','unit-costs.csv','hub-options.csv','scenario-policy.md'])+'.','small')
for f,label in [('population.json','World Bank population API'),('gdp-per-capita.json','World Bank GDP per capita API'),('ecb-history.zip','ECB historical reference-rate archive')]:
    r=REGFILE[f];p(f'{link(f,"Saved archive: "+f)} · <a href="{escape(r["original_url"], {chr(34): "&quot;"})}" color="#008577">{label} (original URL)</a>','small')
p('Reproduction and verification','h2')
p('Run analysis/reproduce.sh from the project root using the documented Python dependencies. It rebuilds the Decimal model, XLSX and PDFs entirely from saved inputs, then performs independent exact-rational recalculation, workbook/cache consistency and PDF integrity checks. See README.md and VERIFICATION.md for commands, actual results and rendering notes. No private account, credentials, customer data or live official refresh was accessed.')
p('The scenario arithmetic omits discounted cash flow, taxation, working capital, inflation, financing, implementation delay, hub capacity constraints and pair cannibalization. Baseline contribution is not company profit or free cash flow. Market indicators do not provide product demand, and the scenario rankings have no assigned probability or statistical certainty. Budget release should follow refreshed operational evidence, not treat these illustrative annual run-rates as guarantees.')
p('Preserve the handoff folder structure so relative evidence links remain usable. The complete machine-readable source register contains original and frozen-room URLs, archive and analyst retrieval times, hashes, units and vintage.','small')

def footer(c,doc):
    c.setStrokeColor(LIGHT);c.line(48,42,W-48,42);c.setFont('Helvetica',8);c.setFillColor(GRAY)
    c.drawString(48,29,'MERIDIAN PARTS  |  Synthetic case  |  27 Sep 2026');c.drawRightString(W-48,29,f'{doc.page}')
doc=SimpleDocTemplate(str(OUT/'Meridian_executive_report.pdf'),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=43,bottomMargin=54,title='Meridian Parts | European service-hub expansion',author='Meridian strategy analysis')
doc.build(story,onFirstPage=footer,onLaterPages=footer)

# Board deck: native PDF text and vector graphics, 16:9 layout.
SW,SH=960,540
deck=canvas.Canvas(str(OUT/'Meridian_board_presentation.pdf'),pagesize=(SW,SH));deck.setTitle('Meridian Parts | Board decision');deck.setAuthor('Meridian strategy analysis')
deck_checks=[]
def text_box(text,x,y,w,h,size=17,color=NAVY,bold=False):
    style=ParagraphStyle('deck',fontName='Helvetica-Bold' if bold else 'Helvetica',fontSize=size,leading=size*1.28,textColor=color)
    q=Paragraph(text,style);_,used=q.wrap(w,h)
    if used>h+.1:raise ValueError(f'Deck text overflow {used}>{h}: {text[:70]}')
    q.drawOn(deck,x,y+h-used);deck_checks.append({'text':text[:60],'height':used,'available':h})
def slide(n,title,subtitle=''):
    deck.setFillColor(WHITE);deck.rect(0,0,SW,SH,fill=1,stroke=0);deck.setFillColor(TEAL);deck.rect(0,SH-9,SW,9,fill=1,stroke=0)
    text_box('MERIDIAN PARTS  /  EUROPEAN SERVICE HUBS',40,493,870,20,10,TEAL,True)
    text_box(title,40,419,880,67,28,NAVY,True)
    if subtitle:text_box(subtitle,40,380,880,33,12,GRAY)
    deck.setStrokeColor(LIGHT);deck.line(40,37,920,37);text_box('Synthetic client case • 2025 cohort • 31 Jan 2026 returns cutoff',40,14,750,15,9,GRAY);text_box(str(n),885,14,35,15,10,GRAY)
def source(files,extra=''):
    text_box(refs(files)+' '+extra,40,44,880,26,8,GRAY)
def card(x,y,w,h,title,value,note='',color=TEAL):
    deck.setFillColor(LIGHT);deck.roundRect(x,y,w,h,8,fill=1,stroke=0);text_box(title,x+16,y+h-37,w-32,23,12,GRAY,True);text_box(value,x+16,y+h-88,w-32,44,28,color,True)
    if note:text_box(note,x+16,y+10,w-32,h-103,11,GRAY)
def dt(headers,data,x,y,widths,fs=12):
    tb=table(headers,data,widths,fs=fs);_,h=tb.wrap(sum(widths),400);tb.drawOn(deck,x,y-h);return h
def end():deck.showPage()

slide(1,'Approve a staged Spain + Czechia envelope','Spain first; Czechia only after demand, cost and FX validation.')
card(40,224,276,146,'YEAR-ZERO CAPEX','€225,000','€225,000 remains under the capex ceiling.')
card(342,224,276,146,'DIRECT HUB STAFF','5 FTE','Spain: 3. Czechia: 2. Two FTE remain.')
card(644,224,276,146,'BASE ANNUAL INCREMENT','€198.1k','After €95,000 recurring fixed cost; 1.14-year payback.')
text_box('Conditional board choice',40,170,850,32,20,NAVY,True)
text_box('Best low/base/high economics under the supplied assumptions. Combined stress stays positive, but Czechia alone loses €37.8k. Reserve capital now; release it at evidence gates.',40,88,870,77,18)
source(SCEN);end()

slide(2,'The decision starts with €2.03m existing contribution','Country differences reflect units, prices, mix, credits and FX; every market has 209 eligible orders.')
renderPDF.draw(bar_chart(list(C),[('Contribution',[r['contribution_eur'] for r in C.values()],TEAL)],490,286,'2025 contribution before hub costs','€k'),deck,40,88)
card(565,244,355,126,'GROUP NET SALES','€4.384m','1,254 orders • 77,436 shipped units')
text_box('Spain + Czechia account for 40.4% of contribution and 35.7% of units. Their observed margins are 49.6% and 48.7%.',565,142,345,84,17)
text_box('No service-level or lost-order evidence is supplied. The analysis cannot prove a hub will cause growth.',565,81,345,51,12,GRAY)
source(ORD);end()

slide(3,'Data corrections change what the board should count','Every extract page and correction file is reconciled; zero-price shipments are retained.')
dt(['Orders','Rows / IDs'],[['Raw rows','1,328'],['Duplicates / superseded','13 / 18'],['Selected order IDs','1,297'],['Cancelled / test / future','24 / 18 / 1'],['Eligible orders','1,254']],40,370,[260,150],13)
dt(['Returns','Rows / IDs'],[['Raw rows','264'],['Duplicates / superseded','20 / 1'],['Selected return IDs','243'],['Late / orphan excluded','1 / 1'],['Eligible return IDs','241']],500,370,[260,150],13)
text_box('12 free orders / 739 units stay in the baseline. Their contribution is −€14,565.90. Only 481 of 1,081 returned units recover product cost.',40,112,420,80,16)
text_box('31 January return included; 1 February return excluded. Orphan ABSENT is quarantined, with no guessed currency or join. All 24 blank shipment dates are cancelled orders.',500,105,410,90,16)
source(ORD);end()

slide(4,'Market scale is context, not product demand','Official World Bank archives: 2022–2024; revised 2026 vintage.')
dt(['Market','2024 population, m','2022–24 change','2024 GDP/person, US$'],[[c,f"{mk[c,2024]['population']/1e6:.2f}",pct(chg[c]['population_change_pct'],2),f"{mk[c,2024]['gdp_per_capita_usd']:,.0f}"] for c in C],40,373,[160,230,220,270],12)
text_box('Spain and Czechia grew fastest by population; Poland contracted. Germany is largest and the Netherlands has highest nominal GDP/person, yet neither leads the base hub economics.',40,111,875,66,17)
text_box('Current US$ is not PPP or real income. No missing requested values. WB lastupdated: 13 July 2026; archive retrieved: 27 September 2026. Full 2022–2024 values are retained.',40,76,875,32,11,GRAY)
source(['population.json','gdp-per-capita.json','source-register.json']);end()

slide(5,'Spain and Czechia lead standalone base returns','Full annual contribution after recurring fixed cost; €k. Capex is a separate year-zero investment.')
dt(['Hub','Capex','FTE','Low','Base','High','Stress','Base payback'],[[c,k(S[c,'base']['capex_eur'],0),S[c,'base']['fte'],*[k(S[c,x]['incremental_contribution_eur']) for x in ['low','base','high','stress']],years(S[c,'base']['payback_years'])+' yr'] for c in C],40,370,[105,110,65,110,110,110,120,150],12)
text_box('Model: C × uplift + units × (1 + uplift) × saving/unit − annual fixed cost. Uplifts are 10% / 25% / 40%; these are assumptions, not measured responses to a hub.',40,116,875,58,16)
text_box('Stress: extra refunds = 3% of gross sales; PLN/CZK haircut = 10% of net sales; apply to 1.25× volume against unchanged normal baseline. No extra cost recovery.',40,76,875,34,11,GRAY)
source(SCEN);end()

slide(6,'Czechia + Spain leads all three volume cases','18 feasible alternatives evaluated: six singles, eleven pairs and defer. Four pairs exceed resource limits.')
dt(['Portfolio','Capex €k / FTE','Low €k','Base €k','High €k','Stress €k'],[[x,f"{k(P[x]['capex_eur'],0)} / {P[x]['fte']}",*[k(P[x][sc+'_eur']) for sc in ['low','base','high','stress']]] for x in ['CZE+ESP','POL+ESP','NLD+ESP','ESP','DEFER']],40,369,[160,175,130,135,135,145],13)
text_box('Closest base alternative: Poland + Spain',40,177,880,30,19,NAVY,True)
text_box('It earns €11.8k less a year, needs €15k more capex and one more FTE, and is weaker in all four prescribed cases. Czechia + Spain leaves resources unused without sacrificing modeled return.',40,103,875,68,17)
text_box('No synergy, cross-border demand transfer or capacity benefit is assumed for any pair.',40,76,875,23,11,GRAY)
source(SCEN);end()

slide(7,'A downside-first board could choose Netherlands + Spain','The recommended pair is not the best portfolio under every risk preference.')
renderPDF.draw(bar_chart(['CZE+ESP','POL+ESP','NLD+ESP','ESP'],[('Base',[P[x]['base_eur'] for x in ['CZE+ESP','POL+ESP','NLD+ESP','ESP']],TEAL),('Stress',[P[x]['stress_eur'] for x in ['CZE+ESP','POL+ESP','NLD+ESP','ESP']],RED)],520,282,'Annual increments','€k / year'),deck,40,87)
text_box('Netherlands + Spain',595,327,325,33,21,NAVY,True)
text_box('€31.2k less base contribution\n<br/>€75.5k more stress contribution\n<br/>€45k more capex; one more FTE',595,216,325,100,17)
text_box('Czechia + Spain stress payback extends to 6.99 years. Spain alone has €70.0k stress contribution and 1.86-year stress payback.',595,112,325,88,16)
source(SCEN);end()

slide(8,'Validate savings and the volume response before release','All six assumed savings per unit exceed the fulfillment costs recorded in the exports.')
card(40,226,276,142,'CZECHIA: SAVING / COST','€2.10 / €1.52','Spain: €3.00 assumed saving versus €1.63 recorded cost.',GOLD)
card(342,226,276,142,'ZERO UPLIFT, FULL SAVINGS','−€24.4k','Recommended pair loses annually without volume growth.',RED)
card(644,226,276,142,'NO SAVINGS BREAK-EVEN','11.60%','Required pair volume uplift; low case then loses €13.1k.',TEAL)
text_box('Decision-changing thresholds',40,178,880,30,20,NAVY,True)
text_box('Czechia uplift below 22.24% lets Poland + Spain overtake if Poland stays at 25%. A Czech net-sales FX haircut above 2.60%, with the 3% refund shock, favors Netherlands + Spain. These are one-way model thresholds.',40,95,875,75,17)
source(SCEN+['data-dictionary.md']);end()

slide(9,'Stage the 90 days around evidence gates','Owners are proposed. No site, customer or service diligence has yet been performed.')
dt(['Days / owner','Action and dependency','Release gate'],[
['1–15\nCFO + Finance','Reconcile data; define cost pool; baseline service and returns.','Zero unexplained differences; fully loaded cost definition.'],
['16–30\nCOO + Procurement','Quotes, route trial and qualified pipeline; cost the pilot.','Spain ≤€130k / 3 FTE; defensible low case; board release.'],
['31–60\nSpain lead + IT','Site, staff, inventory and systems ready after approval.','≥95% one-day dispatch; ≥99% inventory accuracy; traceable returns.'],
['61–90\nCFO + COO / Board','Observe Spain; refresh Czech cost, demand and FX case.','Czechia ≤€95k / 2 FTE; reassess NLD or retain Spain only.']],40,372,[190,355,335],12)
text_box('Do not promise two live hubs by day 90. Recruitment, sites, integration and working capital are unverified; unbudgeted startup needs must stop release until funded.',40,94,875,61,17)
source(SCEN,'Timeline and gate targets are consultant proposals.');end()

slide(10,'Approve the envelope, retain control of each release','Reserve €225,000 and five FTE; launch Spain first, with Czechia conditional.')
text_box('Finance owns economics',40,322,425,36,22,NAVY,True)
text_box('Monthly reconciled contribution after full hub cost. Target full-run-rate increments: Spain €102.7k; Czechia €95.4k. Stop expansion if the rolling eight-week annualized increment is negative.',40,205,420,108,17)
text_box('Operations owns service and returns',500,322,420,36,22,NAVY,True)
text_box('Daily dispatch and stock accuracy. Weekly return rate and restock disposition, compared at the same cohort age. Validate net savings through invoices; track actual cash FX separately.',500,205,420,108,17)
deck.setFillColor(LIGHT);deck.roundRect(40,87,880,100,8,fill=1,stroke=0)
text_box('Board resolution proposed',57,151,845,25,16,TEAL,True)
text_box('Release funds only after cost, demand and readiness gates. Re-submit Netherlands + Spain if the downside case dominates; retain Spain only or defer when the evidence fails. These scenarios are not causal estimates or a full discounted cash-flow model.',57,99,845,49,14)
source(SCEN,'KPI targets are proposed; report and workbook contain the audit trail and full limitations.');end()
deck.save()
(ROOT/'verification/document_layout_checks.json').write_text(json.dumps({'report_intended_pages':len(page_titles),'report_page_titles':page_titles,'deck_slides':10,'deck_text_boxes_checked':len(deck_checks),'overflow':0},indent=2)+'\n')
print('Created 12-page intended report and 10-slide board PDF; all deck text boxes fit.')
