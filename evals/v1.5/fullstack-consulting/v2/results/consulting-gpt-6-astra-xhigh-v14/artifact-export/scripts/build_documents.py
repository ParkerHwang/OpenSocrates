"""Create the executive report, board PDF, charts and public decision basis."""
from pathlib import Path
import os
import sys
import json
import math
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.deps'))
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT,TA_RIGHT

OUT=ROOT/'deliverables'
ASSETS=OUT/'charts'
ASSETS.mkdir(exist_ok=True)
M=json.loads((OUT/'metrics.json').read_text())
S=json.loads((ROOT/'evidence/source-register.json').read_text())
C={r['country']:r for r in M['countries']}
SC={(r['country'],r['scenario']):r for r in M['hub_scenarios']}
P={(r['portfolio'],r['scenario']):r for r in M['portfolios']}
SEN={(r['country'],r['test']):r for r in M['sensitivity']}
T={r['country']:r for r in M['thresholds']}
NAMES=dict(DEU='Germany',FRA='France',NLD='Netherlands',POL='Poland',CZE='Czechia',ESP='Spain')
NAVY='#17324D';TEAL='#087F8C';GOLD='#C47F25';MUTED='#536879';RED='#B7473D';PALE='#EEF4F7'
FONT=Path(matplotlib.get_data_path())/'fonts/ttf'
pdfmetrics.registerFont(TTFont('DV',str(FONT/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('DV-Bold',str(FONT/'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFont(TTFont('DV-Oblique',str(FONT/'DejaVuSans-Oblique.ttf')))
pdfmetrics.registerFontFamily('DV',normal='DV',bold='DV-Bold',italic='DV-Oblique',boldItalic='DV-Bold')
def euros(v,dec=0):return f'€{v:,.{dec}f}'
def num(v,dec=0):return f'{v:,.{dec}f}'
def pct(v,dec=1):return f'{v*100:.{dec}f}%'
def years(v):return '—' if v is None else f'{v:.2f}'
def inc(p,sc):return P[p,sc]['incremental_contribution_eur']
def cap(p):return P[p,'base']['capex_eur']
def sumsen(cs,test):return sum(SEN[c,test]['incremental_contribution_eur'] for c in cs)
def src(*ids):return 'Sources: '+', '.join(f'<link href="#S{i:02d}" color="{TEAL}">S{i:02d}</link>' for i in ids)+'.'

def charts():
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':MUTED,'xtick.color':MUTED,'ytick.color':MUTED,'text.color':NAVY,'axes.titleweight':'bold','axes.titlecolor':NAVY,'figure.facecolor':'white','axes.facecolor':'white'})
    def save(fig,name):
        fig.savefig(ASSETS/f'{name}.png',dpi=180,bbox_inches='tight',facecolor='white')
        fig.savefig(ASSETS/f'{name}.pdf',bbox_inches='tight',facecolor='white')
        plt.close(fig)
    fig,ax=plt.subplots(figsize=(8.1,3.4),layout='constrained')
    cs=sorted(C,key=lambda c:C[c]['contribution_eur'])
    ax.barh([NAMES[c] for c in cs],[C[c]['contribution_eur']/1000 for c in cs],color=[TEAL if c in ['CZE','ESP'] else '#91A9B7' for c in cs],height=.62)
    for i,c in enumerate(cs):ax.text(C[c]['contribution_eur']/1000+6,i,f"{C[c]['contribution_eur']/1000:,.1f}  |  {pct(C[c]['margin'])}",va='center',fontsize=9)
    ax.set_xlim(0,550);ax.set_xlabel('2025 contribution, EUR thousands | labels also show margin');ax.spines['left'].set_visible(False);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    save(fig,'country_contribution')
    fig,ax=plt.subplots(figsize=(8.4,4.0),layout='constrained')
    ps=['CZE+ESP','NLD+ESP','POL+ESP','ESP','DEFER'];x=list(range(len(ps)))
    for j,(sc,color) in enumerate([('low','#A7BDC7'),('base',TEAL),('high',NAVY),('stress',GOLD)]):
        ax.bar([v+(j-1.5)*.19 for v in x],[inc(p,sc)/1000 for p in ps],width=.18,color=color,label=sc.capitalize())
    ax.set_xticks(x,ps);ax.set_ylabel('Annual incremental contribution, EUR thousands');ax.legend(ncol=4,loc='upper right',frameon=False);ax.axhline(0,color=MUTED,lw=.8);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    save(fig,'portfolio_scenarios')
    fig,ax=plt.subplots(figsize=(8.1,3.1),layout='constrained')
    for c,color in [('CZE',NAVY),('ESP',TEAL),('NLD',GOLD)]:
        rows=[r for r in M['monthly'] if r['country']==c]
        ax.plot(range(1,13),[r['contribution_eur']/1000 for r in rows],marker='o',ms=3,label=NAMES[c],color=color)
    ax.set_xticks(range(1,13),['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']);ax.set_ylabel('Contribution, EUR thousands');ax.legend(ncol=3,frameon=False);ax.grid(alpha=.15)
    save(fig,'monthly_contribution')
    fig,ax=plt.subplots(figsize=(8.1,3.2),layout='constrained')
    for cur,color in [('PLN',TEAL),('CZK',NAVY)]:
        rr=[r for r in M['fx_monthly'] if r['currency']==cur];base=rr[0]['local_per_eur']
        ax.plot(range(1,13),[r['local_per_eur']/base*100 for r in rr],label=cur,color=color,lw=2,marker='o',ms=3)
    ax.set_xticks(range(1,13),['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']);ax.set_ylabel('Local units per EUR, Jan 2025 = 100');ax.legend(frameon=False,ncol=2);ax.grid(alpha=.15)
    save(fig,'fx_index')
    fig,ax=plt.subplots(figsize=(8.1,3.1),layout='constrained');cs=list(C)
    ax.bar([i-.18 for i in range(6)],[C[c]['fulfillment_eur']/C[c]['shipped_units'] for c in cs],width=.35,color='#91A9B7',label='Recorded fulfillment / shipped unit')
    ax.bar([i+.18 for i in range(6)],[T[c]['saving_eur_per_unit'] for c in cs],width=.35,color=GOLD,label='Assumed hub saving / shipped unit')
    ax.set_xticks(range(6),cs);ax.set_ylabel('EUR per shipped unit');ax.legend(ncol=1,frameon=False,fontsize=8,loc='upper left');ax.set_ylim(0,4);ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
    save(fig,'saving_gap')

ST={
 'title':ParagraphStyle('title',fontName='DV-Bold',fontSize=25,leading=31,textColor=colors.HexColor(NAVY),spaceAfter=14),
 'h':ParagraphStyle('h',fontName='DV-Bold',fontSize=16,leading=21,textColor=colors.HexColor(NAVY),spaceAfter=10),
 'sub':ParagraphStyle('sub',fontName='DV-Bold',fontSize=11,leading=15,textColor=colors.HexColor(TEAL),spaceBefore=10,spaceAfter=5),
 'body':ParagraphStyle('body',fontName='DV',fontSize=9.5,leading=14,textColor=colors.HexColor(NAVY),spaceAfter=8),
 'small':ParagraphStyle('small',fontName='DV',fontSize=7.7,leading=11,textColor=colors.HexColor(MUTED),spaceAfter=7),
 'cell':ParagraphStyle('cell',fontName='DV',fontSize=8,leading=11,textColor=colors.HexColor(NAVY)),
 'head':ParagraphStyle('head',fontName='DV-Bold',fontSize=7.7,leading=10,textColor=colors.white),
 'callout':ParagraphStyle('callout',fontName='DV-Bold',fontSize=12,leading=18,textColor=colors.HexColor(TEAL),spaceAfter=10),
}
def para(s,style='body'):return Paragraph(s,ST[style])
def table(headers,rows,widths,small=False):
    body_style=ST['cell'] if not small else ParagraphStyle('tiny',parent=ST['cell'],fontSize=7.3,leading=10)
    data=[[Paragraph(escape(str(x)),ST['head']) for x in headers]]+[[Paragraph(str(x),body_style) for x in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor(PALE)]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor(NAVY))]))
    return t
def img(name,width=495,height=None):
    from PIL import Image as PI
    path=ASSETS/f'{name}.png'
    iw,ih=PI.open(path).size
    return Image(str(path),width=width,height=height or width*ih/iw,hAlign='LEFT')

def report():
    story=[]
    def add(*items):story.extend(items)
    def page(title,kicker=None):
        if story:story.append(PageBreak())
        if kicker:add(para(kicker.upper(),'small'))
        add(para(title,'h'))
    def foot(c,doc):
        w,h=doc.pagesize
        c.setStrokeColor(colors.HexColor('#D5E1E8'));c.line(42,38,w-42,38)
        c.setFont('DV',7);c.setFillColor(colors.HexColor(MUTED));c.drawString(42,25,'MERIDIAN PARTS  •  Synthetic client case  •  27 September 2026');c.drawRightString(w-42,25,f'{doc.page}')
        if doc.page>1:c.drawString(42,h-27,'European service-hub expansion | Board decision report')
    add(para('BOARD DECISION REPORT | 27 SEPTEMBER 2026','small'),Spacer(1,16),para('Fund a staged Czechia<br/>and Spain expansion','title'))
    add(para('Reserve €225,000 and five FTE. Start with Spain; release Czechia after validating demand, saving scope and FX exposure.','callout'))
    add(table(['Annual contribution uplift','Year-zero investment','Resources'],[[f"Base <b>{euros(inc('CZE+ESP','base'))}</b><br/>Low {euros(inc('CZE+ESP','low'))}<br/>Stress {euros(inc('CZE+ESP','stress'))}",'<b>€225,000 capex</b><br/>€95,000 recurring fixed cost/year<br/>Base simple payback: 1.14 years','<b>5 of 7 FTE</b><br/>2 of 2 possible hubs<br/>€225,000 capex headroom']],[171,171,169]))
    add(Spacer(1,12),para('<b>Why this pair.</b> It produces the highest low, base and high annual increment among all feasible alternatives. Both countries have strong contribution in the reconciled synthetic sales base, and their lower recurring costs support investment at modest volume uplifts. The aggregate specified stress stays positive, although Czechia alone turns negative. '+src(6,8,9,11,12,14)))
    add(para('<b>The concession.</b> Netherlands + Spain gives up €31,168 of base annual contribution and uses €45,000 more capex plus one more FTE, but improves the specified stress result by €75,450. It is the preferred alternative if the board prioritizes the worst of the four supplied scenarios over the base case.'))
    add(img('portfolio_scenarios',495),para('<b>Decision strength: provisional.</b> These are reproducible scenario results, not a measured effect of opening hubs. Volume uplifts and per-unit savings are synthetic planning assumptions; no probabilities are assigned. A supplemental saving cap combined with stress makes the recommended pair slightly negative (−€1,588/year), reinforcing staged release.','small'))

    page('Spain and Czechia lead the contribution pool','2025 operating diagnosis')
    totals=M['totals']
    add(para(f"The reconciled base contains <b>{num(totals['shipped_orders'])} shipped orders and {num(totals['shipped_units'])} units</b>. Gross sales after discounts are {euros(totals['gross_sales_eur'],2)}; refunds of {euros(totals['refunds_eur'],2)} reduce net sales to {euros(totals['net_sales_eur'],2)}. Contribution is {euros(totals['contribution_eur'],2)}, or {pct(totals['margin'])} of net sales. "+src(2,3,7,8,9,11,14)))
    rows=[]
    for c,r in C.items():rows.append([c,num(r['shipped_orders']),num(r['shipped_units']),num(r['gross_sales_eur'],2),num(r['refunds_eur'],2),num(r['net_sales_eur'],2)])
    rows.append(['ALL',num(totals['shipped_orders']),num(totals['shipped_units']),num(totals['gross_sales_eur'],2),num(totals['refunds_eur'],2),num(totals['net_sales_eur'],2)])
    add(table(['Market','Orders','Units','Gross EUR','Refunds EUR','Net sales EUR'],rows,[47,46,55,120,98,145]),Spacer(1,10))
    rows=[]
    for c,r in list(C.items())+[('ALL',totals)]:rows.append([c,num(r['net_cogs_eur'],2),num(r['fulfillment_eur'],2),num(r['contribution_eur'],2),num(r['returned_units']),pct(r['margin'])])
    add(table(['Market','Net COGS EUR','Fulfillment EUR','Contribution EUR','Returned units','Margin'],rows,[47,103,103,123,72,63]))
    add(Spacer(1,12),para(f"<b>Operational implication.</b> Spain and Czechia together generate {pct((C['ESP']['contribution_eur']+C['CZE']['contribution_eur'])/totals['contribution_eur'])} of contribution. Czechia has the highest returned-unit rate ({pct(C['CZE']['returned_units']/C['CZE']['shipped_units'],2)}), followed by Spain ({pct(C['ESP']['returned_units']/C['ESP']['shipped_units'],2)}); validation of returns handling belongs in both pilots. These rates describe physical units, not refund value or the share of orders returned."))
    add(para('Every market has 209 eligible orders. The difference in economics comes from shipped units, price/mix, returns and costs; equal synthetic order counts do not establish equal market opportunity. The workbook contains all 72 country-month records and reconciles them to these totals.','small'))

    page('The financial base is a shipment cohort, not cash','Reconciliation and accounting')
    add(table(['Control','Observed result','Treatment'],[
        ['Order reconciliation','1,328 raw rows → 1,297 IDs','13 identical duplicate rows removed; 18 lower revisions superseded by whole-row corrections.'],
        ['Eligibility','1,254 included orders','Exclude 24 cancelled, 18 test, one January 2026 shipment. All 24 missing shipment dates belong to cancelled records.'],
        ['Valid free shipments','12 orders; 739 units','Kept in counts and costs; zero sales; combined contribution −€14,565.90.'],
        ['Return reconciliation','264 rows → 243 return IDs','20 duplicates removed; one old revision replaced. Include 241 eligible IDs.'],
        ['Cutoff and orphan','R-CUTOFF included; two excluded','2026-01-31 is inclusive. R-LATE (2026-02-01; €33) excluded. R-ORPHAN (2 units, 60 local) quarantined; currency unknown.'],
        ['COGS recovery','481 restocked / 1,081 returned units','Recover €18,485.50 at original shipment cost; no cost recovery for 600 un-restocked units.'],
        ['Missingness / joins','No eligible monetary, FX or cost gaps','No imputations; no conflicting equal revisions. No observed eligible order has multiple distinct return IDs; code supports additive IDs.'],
    ],[100,132,279]))
    add(Spacer(1,10),para('<b>Per-order accounting.</b> Gross local = units × local price − discount. Gross EUR and summed order credits are each divided by the original shipment month’s ECB mean. Gross COGS and recovered COGS use the latest effective SKU cost on or before shipment. Each monetary component is rounded half-up to cents before aggregation. Fulfillment is nonrefundable. Net sales = gross − refunds; contribution = net sales − net COGS − fulfillment. Margin is null when net sales is zero. '+src(2,3,14)))
    add(para('<b>Boundary examples.</b> R-CUTOFF is received 31 January 2026 but reduces the December 2025 shipment cohort by €54 and recovers €29.50 of BRAKE cost. R-M1-01-003 revision 2 replaces the €150 credit with €149. The future order FUTURE-2026 does not enter 2025 even though its date is before the return cutoff. '+src(7,9,11)))
    add(para('<b>Booked revenue, cash and contribution.</b> This report’s sales measure is a reconstructed tax-exclusive shipped-sales cohort, net of known credits, not a general-ledger audit. Credit timing is assigned back to the shipment month, so monthly results need not equal a calendar-month revenue ledger. Cash depends on collection/refund dates, credit terms, taxes and realized FX; none is supplied. Contribution further deducts product and fulfillment costs, but is before existing central overhead, tax, financing and hub capex.'))

    page('Public market context informs scale, not product demand','Archived World Bank observations')
    add(para('Germany and France have the largest populations; the Netherlands has the highest current-US-dollar GDP per capita. Poland’s population declined while the other five grew from 2022 to 2024. These observations describe national context. They neither measure replacement-assembly demand nor explain the synthetic sales ranking. '+src(5,10,13)))
    rows=[]
    for c in C:
        rr={r['year']:r for r in M['market_context'] if r['country']==c}
        rows.append([c,num(rr[2022]['population']),num(rr[2023]['population']),num(rr[2024]['population']),pct(rr[2024]['population']/rr[2022]['population']-1,2)])
    add(table(['Market','Population 2022','Population 2023','Population 2024','2022–24 change'],rows,[45,117,117,117,115]),Spacer(1,12))
    rows=[]
    for c in C:
        rr={r['year']:r for r in M['market_context'] if r['country']==c}
        rows.append([c,*[f"${rr[y]['gdp_per_capita_usd']:,.2f}" for y in [2022,2023,2024]]])
    add(table(['Market','GDP/person 2022','GDP/person 2023','GDP/person 2024'],rows,[65,148,149,149]))
    add(Spacer(1,12),para('<b>Interpretation limits.</b> GDP per capita is current US$, not purchasing-power parity or constant-price real income. Changes include price and exchange-rate effects and are not evidence of equivalent real purchasing-power growth. Population differences do not proxy installed equipment, channel access or service intensity. No market-size or causal uplift estimate is derived from these series.'))
    add(para('<b>Vintage and completeness.</b> Both World Bank responses contain all 18 requested country-years with no null values. Original API pagination reports one page; source lastupdated is 2026-07-13. The archive fetched them on 2026-09-27 at 06:36 UTC; this analysis collected those saved bytes at 10:12 UTC the same day. Historical values may incorporate later revisions. The workbook and JSON preserve full source precision; this page displays GDP per capita to cents.','small'))
    add(para('<b>Next decision evidence.</b> Commercial leads should validate serviceable installed base, customer service needs and qualified pipeline by country. No customer interviews, competitor study or live demand research were performed. The transaction base is synthetic, independently of the public source status.','small'))

    page('Lower fixed cost makes Czechia and Spain attractive','Single-hub economics')
    add(para('<b>Normal case:</b> ΔC = C × u + U × (1 + u) × s − F. Here C is 2025 contribution, U shipped units, s saving per unit, F recurring annual fixed cost, and u is 10% / 25% / 40% for low / base / high. <b>Stress:</b> ΔC = (C − 0.03G − FX shock) × 1.25 − C + U × 1.25 × s − F; FX shock = 0.10N in PLN/CZK markets only. G and N are gross and net sales. '+src(6,12)))
    rows=[]
    for c in C:
        b=SC[c,'base'];t=T[c]
        rows.append([c,num(b['capex_eur']),str(b['fte']),num(b['annual_fixed_eur']),f"{t['saving_eur_per_unit']:.2f}",pct(t['break_even_uplift'],2),years(b['payback_years'])])
    add(table(['Market','Capex EUR','FTE','Fixed EUR/yr','Saving EUR/unit','Break-even uplift','Base payback years'],rows,[45,86,36,93,80,86,85]),Spacer(1,12))
    rows=[[c,*[num(SC[c,sc]['incremental_contribution_eur'],2) for sc in ['low','base','high','stress']]] for c in C]
    add(table(['Market','Low ΔC EUR','Base ΔC EUR','High ΔC EUR','Stress ΔC EUR'],rows,[45,116,116,116,118]))
    add(Spacer(1,12),para('Spain has the highest base increment (€102,716), with Czechia second (€95,383). Germany requires a 21.57% volume uplift to break even and has a 27.75-year base payback; France also loses contribution in the low case. They are unattractive priorities despite larger national populations.'))
    add(para('<b>Timing matters.</b> Capex is a year-zero investment; the table shows a full year at steady state after recurring fixed cost. Simple payback is capex divided by positive annual increment and is null when that increment is zero or negative. Payback excludes ramp-up, financing, tax, working capital and residual value. A 90-day implementation is not an assumption that the first year achieves a full run rate.'))
    add(para('<b>Stress is deliberately conservative.</b> It compares the shocked hub case with an unchanged normal baseline, per policy. It is not a forecast probability, a mechanically recalculated 10% exchange quote depreciation, or a comparison of both alternatives under the same macro shock. Pair benefits and resources add without synergy. Supplemental analyses do not replace this required definition.','small'))

    page('All feasible portfolios have been tested','Feasible set and rankings')
    ranked=sorted([r for r in M['portfolios'] if r['scenario']=='base' and r['feasible']],key=lambda r:r['rank_within_scenario'])
    rows=[]
    for r in ranked:
        p=r['portfolio'];rows.append([str(r['rank_within_scenario']),p,num(r['capex_eur']/1000),str(r['fte']),*[num(inc(p,sc)/1000,1) for sc in ['low','base','high','stress']],years(r['payback_years'])])
    add(table(['Base rank','Portfolio','Capex €k','FTE','Low €k/yr','Base €k/yr','High €k/yr','Stress €k/yr','Base PB yrs'],rows,[38,87,51,29,60,60,60,67,59],True))
    add(Spacer(1,10),para('<b>Hard constraints, supplied by the board:</b> no more than €450,000 capex, seven FTE and two hubs. Eleven of 15 possible pairs are feasible. DEU+FRA fails both (€490,000; 9 FTE). DEU+NLD (€420,000), DEU+POL (€390,000) and DEU+ESP (€410,000) each need 8 FTE and fail staffing. All six singles and defer are feasible. '+src(6,12),'small'))
    add(para('<b>Decision rule, consultant assumption:</b> prioritize base annual increment under hard limits, check downside and stage spend; no weighted score or scenario probabilities. CZE+ESP dominates POL+ESP on all four contribution cases, capex and FTE. NLD+ESP is incomparable: less base upside and more resources, but stronger stress. Under a maximin rule across the four supplied cases, NLD+ESP wins with a minimum €43,994, versus €32,180 for CZE+ESP.','small'))
    add(para('Table values are € thousands rounded for legibility; the workbook and metrics.json retain cents and payback for every case, including infeasible alternatives. Defer is zero incremental contribution under the policy benchmark; it retains current operations.','small'))

    page('The second hub should earn its release','Switching assumptions and risks')
    add(table(['Comparison','CZE + ESP','NLD + ESP','What is given up'],[
        ['Base annual increment',euros(inc('CZE+ESP','base')),euros(inc('NLD+ESP','base')),'Choose NLD: −€31,168/year'],
        ['Specified stress',euros(inc('CZE+ESP','stress')),euros(inc('NLD+ESP','stress')),'Choose CZE: −€75,450/year in stress'],
        ['Capex / FTE','€225,000 / 5','€270,000 / 6','Choose NLD: +€45,000 and +1 FTE'],
        ['Cap savings at recorded fulfillment: base',euros(sumsen(['CZE','ESP'],'saving_capped_base')),euros(sumsen(['NLD','ESP'],'saving_capped_base')),'Analyst conservative saving boundary'],
        ['Cap savings + specified stress',euros(sumsen(['CZE','ESP'],'saving_capped_stress')),euros(sumsen(['NLD','ESP'],'saving_capped_stress')),'Recommended pair becomes slightly negative'],
    ],[154,102,102,153]))
    add(Spacer(1,10),para('<b>Demand flip.</b> With the Netherlands held at 25% uplift and normal FX/returns, Czechia must deliver about <b>17.7%</b> uplift to match its annual increment. Czechia’s own normal-case operating break-even is only 2.62%, but merely clearing break-even does not make it the best second hub. The recommended pair’s common uplift break-even is 2.74%; at zero uplift it loses €24,368/year.'))
    add(para('<b>FX flip.</b> At base volume and an additional refund cost of 3% of gross sales in both markets, Netherlands overtakes Czechia once the Czech net-sales FX haircut exceeds approximately <b>2.6%</b>. Czechia’s own increment reaches zero at about a 6.3% haircut. These are model sensitivities using the policy’s revenue-haircut convention, not forecast exchange rates or hedging advice.'))
    add(img('saving_gap',495))
    add(para('<b>Validate the saving scope first.</b> Czechia’s assumed €2.10/unit exceeds recorded fulfillment of €1.52; Spain’s €3.00 exceeds €1.63. Every option has this mismatch. Savings may involve other costs, but their scope is unspecified. The cap sensitivity assumes fulfillment is the only pool, and even full elimination is an optimistic operational bound. Procurement and Finance must obtain a net saving bridge, including local variable costs and any stranded central cost, before release. '+src(6,8,9,12),'small'))

    page('A 90-day plan with separate capital gates','Execution proposal — roles and dates are planning assumptions')
    add(table(['Stage / owner','Work and dependency','Measurable gate / decision'],[
        ['Days 1–15<br/><b>CFO + data lead</b>','Reconcile ledger to the saved cohort; resolve orphan documentation; establish SKU/customer mix and service baseline. Treasurer maps CZK receivables and EUR cost exposure. Depends on ledger/payment exports and service-event definitions.','Gate A: no unexplained financial variance; owner assigned to each return exception. Produce all-in capex and working-capital estimate. Confirm €225k envelope / 5 FTE remains viable.'],
        ['Days 16–30<br/><b>COO + Procurement + country leads</b>','Obtain site and service quotes; document net unit-saving bridge; qualify Spanish and Czech pipeline. Select comparison customers served centrally. HR validates service-window coverage. Depends on demand/quote inputs from Gate A.','Gate B: release Spain within €130k and 3 FTE only if low case stays positive using validated net savings, and supply/IT readiness is complete. Reserve Czechia €95k / 2 FTE; do not bind its site yet.'],
        ['Days 31–60<br/><b>Spain operations lead + IT + HR</b>','Launch a limited SKU/service pilot after integration, stock traceability, staff training and fulfillment acceptance. Keep a matched central-service comparison and weekly mix-adjusted reporting. Depends on Gate B and stocked eligible SKUs.','Gate C: ≥95% eligible pilot orders dispatched within one business day; ≥99% inventory accuracy; no critical unresolved reconciliation defect. Four weekly reviews of cost/unit, contribution and exceptions.'],
        ['Days 61–75<br/><b>CFO + Commercial + Treasury</b>','Update scenarios with pilot unit economics, season-matched demand and receivables FX exposure. Refresh Netherlands alternative with equally scoped quotes. Wait for return cohorts to mature where needed.','Gate D: choose CZE, NLD or defer second hub. Reopen CZE below ~17.7% uplift if NLD remains 25%, or above ~2.6% FX haircut with 3% refund shock. Recalculate both thresholds if savings/costs change.'],
        ['Days 76–90<br/><b>COO + board sponsor</b>','If Gate D passes, contract and prepare second hub with limited stock and staff; otherwise keep Spain only and review next quarter. An NLD substitution needs a revised €270k / 6 FTE envelope.','Gate E: confirm projected positive annual increment, resource compliance and KPI ownership. Report committed capex separately from annualized benefit; no automatic second-site launch date.'],
    ],[119,206,186]))
    add(Spacer(1,12),para('<b>Staffing concept.</b> Spain: one site lead, one parts/dispatch coordinator and one service technician (3 FTE). Czechia: one lead technician and one stock/dispatch coordinator (2 FTE). These are proposed allocations, not a validated shift roster; HR must test absence coverage and opening hours. The remaining two FTE and €225,000 are headroom, not committed reserve spending.'))
    add(para('<b>Readiness limitation.</b> Local permits, lease terms, inventory investment, IT effort and recruitment lead times are unpriced. Existing owners’ project time is not automatically included in hub FTE or capex. Confirm these costs at Gate A; do not assert an operational launch within 90 days if dependencies fail.','small'))

    page('Measure contribution, service and capital separately','KPI and risk plan')
    add(table(['KPI / owner','Baseline / proposed target','Measurement and cadence'],[
        ['Incremental contribution<br/>CFO','Model base: CZE €95,383; ESP €102,716 annually. No measured uplift. Target: positive validated low case before release.','Monthly bridge: mix-adjusted net sales − net product/fulfillment cost − hub fixed cost versus central comparison. Report run rate and realized YTD separately.'],
        ['Volume uplift<br/>Commercial leads','Base assumption 25%; low 10%. CZE selection threshold ~17.7% vs NLD at 25%.','Weekly shipped units vs same 2025 seasonal period and matched central-service cohort; exclude test/future orders and log price/mix changes.'],
        ['Net saving per unit<br/>Procurement / Finance','Assumed CZE €2.10; ESP €3.00. Validate rather than treat as achieved.','Weekly cost bridge for transport, handling, product and local variable costs; reconcile invoices monthly. No double-counting COGS recovery.'],
        ['Returned-unit rate / refunds<br/>Quality lead','2025: CZE 2.10%, ESP 1.81% units. Proposed alert: >baseline +0.5 percentage points.','Monthly shipment cohorts, age-matched; show refund/gross sales and reusable share separately. Proposed alert is not the policy’s 3% gross-sales credit shock.'],
        ['Service / stock accuracy<br/>Operations lead','Baseline unavailable. Proposed: ≥95% dispatched within one business day; ≥99% stock accuracy.','Timestamp eligible orders and dispatch; weekly service dashboard, weekly cycle counts. Validate customer relevance before setting service commitments.'],
        ['Capex, fixed cost and staffing<br/>CFO / HR','CZE+ESP: capex ≤€225k, fixed cost €95k/year, 5 FTE. Absolute board ceilings €450k / 7 FTE.','Weekly purchase-commitment log and monthly P&amp;L/payroll review. Forecast deposits, inventory and implementation cash separately.'],
    ],[126,190,195]))
    add(Spacer(1,12),para('<b>Risk priorities.</b> Demand attribution and saving scope are high-priority unknowns: control comparisons and invoice-based cost bridges address them. FX can reverse the second-site choice: Treasury updates the exposure sensitivity monthly. Return censoring can overstate margins: Quality tracks mature cohorts and separates reusable from non-reusable units. Site/ramp costs can extend payback: Finance gates binding spend on an all-in cash plan.'))
    add(para('The pilot can establish readiness and improve unit-cost estimates; a short, small sample cannot prove a sustained 25% demand lift. No statistical power claim is made. If return maturity or seasonality prevents a fair read by day 75, retain the Spain-only stage and defer the second-site commitment.','small'))

    page('What the evidence supports—and what remains unverified','Claim-to-source assessment')
    add(para('<b>Claim and threshold.</b> For these six markets, the predictive claim is that a hub can generate incremental annual contribution sufficient to justify investment. The decision threshold is positive modeled contribution within the capex/FTE constraints; preference for base-case maximization is a consultant default. Calculation accuracy and real-world hub impact are separate claims.'))
    add(table(['Claim / evidence state','Basis, directness and quality','Conclusion / reopening evidence'],[
        ['2025 contribution ranking<br/><b>Computed / supported within synthetic case</b>','S02, S07–S09, S11, S14: transaction exports and explicit accounting rules; complete downloaded pages, controlled IDs/revisions, effective cost schedule. Direct for the defined synthetic cohort; no ledger/cash audit.','CZE and ESP have the strongest contribution pools. Reopen on valid source corrections, cost changes or eligible credits received by cutoff.'],
        ['National context<br/><b>Verified archive bytes / contextual</b>','S05, S10, S13: official aggregate series, all 18 country-years; hashes and metadata checked. Strong for national measures, indirect for the product; later historical revisions possible.','Preserve population and current-US$ income context. Demand claim remains unverified. Reopen context on a documented source revision; demand needs product/customer evidence.'],
        ['Historical FX translation<br/><b>Computed / supported</b>','S03–S04: official reference observations; 255 published dates per required currency, 12 monthly means; ZIP extraction verified. Valid translation convention, not realized FX.','Use shipment-month quote for sale/refund. Reopen on archived observation changes or an explicit alternative accounting convention.'],
        ['Hub uplift and savings<br/><b>Assumed / unverified effect</b>','S06, S12: six synthetic options and scenario ranges. Direct to the requested arithmetic; no experiment, quote support, customer research or reference-case validation. Saving scope is unresolved.','Hold any claim that hubs cause 25% growth. Validate demand and net savings; second-hub choice flips at the quantified thresholds.'],
        ['Staged CZE+ESP decision<br/><b>Inferred / provisional</b>','Reproducible portfolio comparison plus explicit consultant preference; no probabilities, invented weights or claim of certainty. NLD+ESP remains stronger in stress.','Reserve the envelope and test before committing. Maximin preference, weaker Czech demand, FX exposure or saving revisions can change the choice.'],
    ],[139,197,175]))
    add(Spacer(1,10),para('<b>Quality dimensions.</b> Transaction completeness is supported within the supplied exports; measurement validity is bounded by the dictionary and cutoff, and synthetic generation limits external applicability. Official series have strong provenance for their stated units, but limited product relevance. Scenario design is transparent; causal rigor is absent, optimism/selection bias is possible, and implementation cash costs are incomplete. These qualitative judgments do not form a composite score.','small'))
    add(para('<b>Agreement and conflicts.</b> Official and client sources measure different things and do not independently corroborate hub demand. The required model reconciles internally. The saving-versus-fulfillment gap is an unresolved scope issue, not permission to alter supplied assumptions silently. Missing support narrows the impact claim; it does not prevent arithmetic comparison or a conditional action recommendation.','small'))

    page('Historical FX is tied to the original shipment month','Technical appendix')
    fx={(r['currency'],r['month']):r for r in M['fx_monthly']}
    rows=[[f'2025-{i:02d}',f"{fx['PLN',f'2025-{i:02d}']['local_per_eur']:.8f}",f"{fx['CZK',f'2025-{i:02d}']['local_per_eur']:.8f}",str(fx['PLN',f'2025-{i:02d}']['observation_count'])] for i in range(1,13)]
    add(table(['Month','PLN per EUR','CZK per EUR','Published days each'],rows,[100,143,143,125]),Spacer(1,10),para('Arithmetic means use all available published business-day observations in each 2025 month. EUR = 1. No inverse quote, current rate or early rounding is used. JSON stores full numeric means; the audit CSV preserves Decimal precision and the workbook includes all 510 currency-date observations. '+src(2,3,4),'small'))
    add(img('fx_index',490))
    add(para('A falling local-per-EUR quote means each local currency unit translates into more EUR, holding price constant. The chart is an indexed historical comparison; the model uses actual monthly means. It does not forecast FX or estimate actual realized conversion gains.','small'))

    page('Evidence register and reproducible handover','Source links and completion boundaries')
    for s in S:
        if s['source_id']=='S01':continue
        file=Path(s['file']).name
        status='Archived official public data' if s['source_kind']=='archived_official_public' else 'Synthetic client source' if s['source_kind']=='synthetic_client' else 'Archive metadata'
        title=f'<a name="{s["source_id"]}"/><b>{s["source_id"]} · {escape(file)}</b> — {status}. '
        if s['source_kind']=='archived_official_public':
            url=escape(s['original_url'],{'"':'&quot;'})
            text=title+f'<link href="{url}" color="{TEAL}">Original publisher endpoint</link>. '+('World Bank lastupdated 2026-07-13; 2022–2024 observations.' if 'json' in file else 'ECB quote: local currency units per EUR; model period 2025.')
        else:text=title+f'<link href="../evidence/raw/{file}" color="{TEAL}">Saved source file</link>. '
        add(para(text,'small'))
    add(Spacer(1,6),para('<b>Provenance.</b> All 13 indexed source files plus the index were collected from the frozen local source room. Public archive retrieval was 2026-09-27 06:36 UTC; analyst collection was 2026-09-27 10:12 UTC. The full register in evidence/source-register.csv and .json records collection URL, original URL, time, SHA-256, units, period, status and source vintage for every file. Public hashes match the supplied archive register; the ZIP member is byte-identical to the saved ECB CSV. No live source refresh or customer-account access was used.'))
    add(para('<b>Files.</b> meridian_analysis.xlsx contains formula-linked financial summaries and scenarios, market context, source/quality notes and charts. metrics.json is the deterministic data exchange. audit/ retains order calculations, exclusions, revision handling, FX observations, scenario runs and thresholds. scripts/ contains source collection, calculation, artifact generation and verification; README.md gives offline reproduction commands.'))
    add(para('<b>Verification.</b> See verification.json and VERIFICATION.md for actual raw-data cross-checks, workbook cache/formula inspection, PDF rendering and identified limits. Verification of this package does not validate the synthetic commercial assumptions. The 2025 shipment cohort is reproducible; customer demand, saving scope, cash realization, working capital, site feasibility and ramp remain decision gaps.'))
    add(para('Public method grounds are documented in decision_basis.json. Native method selection was available for the portfolio comparison; native activation/application remains unconfirmed. Evidence calibration used a complete installed reference after the initial selector requests failed. No private reasoning or customer interviews are included.','small'))
    doc=SimpleDocTemplate(str(OUT/'meridian_report.pdf'),pagesize=(595.28,841.89),rightMargin=42,leftMargin=42,topMargin=48,bottomMargin=49,title='Meridian Parts — European service-hub expansion',author='Operations consulting')
    doc.build(story,onFirstPage=foot,onLaterPages=foot)

def board():
    path=OUT/'meridian_board.pdf';cv=canvas.Canvas(str(path),pagesize=(960,540))
    cv.setTitle('Meridian Parts | Board decision');cv.setAuthor('Operations consulting')
    page_no=0
    def text(x,y,w,s,size=16,bold=False,color=NAVY):
        p=Paragraph(s,ParagraphStyle('slide',fontName='DV-Bold' if bold else 'DV',fontSize=size,leading=size*1.32,textColor=colors.HexColor(color)))
        _,h=p.wrap(w,1000);p.drawOn(cv,x,y-h);return h
    def start(title,kicker):
        nonlocal page_no
        page_no+=1
        cv.setFillColor(colors.white);cv.rect(0,0,960,540,fill=1,stroke=0)
        cv.setFillColor(colors.HexColor(TEAL));cv.rect(0,525,960,15,fill=1,stroke=0)
        text(40,500,880,kicker.upper(),10,True,TEAL);text(40,473,880,title,27,True)
        cv.setStrokeColor(colors.HexColor('#D5E1E8'));cv.line(40,35,920,35)
        text(40,25,820,'MERIDIAN PARTS • Synthetic client case • 27 September 2026',8,False,MUTED)
        text(895,25,30,str(page_no),8,False,MUTED)
    def end(source):text(40,58,880,source,8,False,MUTED);cv.showPage()
    def box(x,y,w,h,label,value,detail):
        cv.setFillColor(colors.HexColor(PALE));cv.roundRect(x,y,w,h,7,fill=1,stroke=0)
        text(x+16,y+h-13,w-32,label,11,True,MUTED);text(x+16,y+h-40,w-32,value,25,True,TEAL);text(x+16,y+35,w-32,detail,10,False,MUTED)
    def picture(name,x,y,w,h):cv.drawImage(str(ASSETS/f'{name}.png'),x,y,width=w,height=h,preserveAspectRatio=True,anchor='c',mask='auto')
    def tab(headers,rows,widths,x=40,top=405,size=10):
        style=ParagraphStyle('slidecell',fontName='DV',fontSize=size,leading=size*1.25,textColor=colors.HexColor(NAVY))
        head=ParagraphStyle('slidehead',parent=style,fontName='DV-Bold',textColor=colors.white)
        data=[[Paragraph(str(v),head) for v in headers]]+[[Paragraph(str(v),style) for v in row] for row in rows]
        t=Table(data,colWidths=widths);t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor(NAVY)),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor(PALE),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        _,h=t.wrap(880,450);t.drawOn(cv,x,top-h);return h
    start('Reserve Czechia + Spain; release capital in stages','Decision requested')
    box(40,277,280,119,'BASE ANNUAL INCREMENT','€198,099','After €95,000 recurring fixed cost')
    box(340,277,280,119,'YEAR-ZERO CAPEX','€225,000','50% of the €450,000 ceiling')
    box(640,277,280,119,'HUB STAFFING','5 FTE','Two hubs; two FTE headroom')
    text(40,243,880,'Start with Spain. Release Czechia after validating demand, net savings and FX exposure.',21,True)
    text(40,177,880,'Low: €64,619/year  •  High: €331,580/year  •  Stress: €32,180/year<br/>Base simple payback: 1.14 years at steady state; first-year ramp is unmodeled.',15)
    text(40,111,880,'Provisional recommendation. Uplift and saving assumptions are synthetic; no measured causal effect or forecast probability.',12,False,MUTED)
    end('Sources: hub-options.csv; scenario-policy.md; reconciled 2025 order ledger. Report pp. 1, 5–7; workbook Scenarios / Portfolios.')

    start('Contribution supports the choice; population does not','2025 operating diagnosis')
    picture('country_contribution',35,160,565,245)
    text(635,403,285,'€4.384m net sales<br/>€2.030m contribution<br/>46.3% margin',22,True,TEAL)
    text(635,292,285,'1,254 orders • 77,436 units<br/>All six markets: 209 orders.<br/><br/>CZE+ESP produce 40.4% of total contribution.',13)
    text(40,136,870,'Country economics reflect volume, price/mix, returns and costs. Czechia’s returned-unit rate is 2.10%; Spain’s is 1.81%. Track mature shipment cohorts in the pilot.',14)
    end('Sources: order extracts and corrections; returns; effective-dated unit costs; archived ECB. Report pp. 2–3; workbook Monthly / Countries.')

    start('Czechia + Spain wins normal cases; NLD protects stress','Quantified alternatives')
    picture('portfolio_scenarios',45,94,580,315)
    text(660,405,265,'CZE + ESP',17,True,TEAL)
    text(660,373,265,'€225k capex / 5 FTE<br/>Base €198.1k/year<br/>Stress €32.2k/year',15)
    text(660,285,265,'NLD + ESP',17,True,NAVY)
    text(660,253,265,'€270k capex / 6 FTE<br/>Base €166.9k/year<br/>Stress €107.6k/year',15)
    text(660,158,265,'No probabilities assigned.<br/>Maximin across these four cases selects NLD+ESP.',12,False,MUTED)
    end('Source: required scenario policy; capex is separate from annual contribution. All 11 feasible pairs, six singles and defer are in report p. 6 / workbook.')

    start('The feasible frontier fits well inside the capital ceiling','Portfolio choice and concession')
    rows=[]
    for p in ['CZE+ESP','POL+ESP','NLD+ESP','ESP','DEFER']:
        r=P[p,'base'];rows.append([p,euros(r['capex_eur']),str(r['fte']),euros(inc(p,'base')),euros(inc(p,'stress')),years(r['payback_years'])])
    tab(['Portfolio','Capex','FTE','Base / year','Stress / year','Base PB yrs'],rows,[160,150,65,180,180,145])
    text(40,185,880,'CZE+ESP dominates the base runner-up POL+ESP: more contribution in all four cases, €15k less capex and one fewer FTE.',15,True)
    text(40,121,880,'Versus NLD+ESP, accept €75.5k less annual contribution in stress for €31.2k more base contribution, €45k less capex and one fewer FTE. A stronger downside preference changes the choice.',14)
    end('Hard constraints: ≤€450,000 capex; ≤7 FTE; ≤2 hubs. Four DEU pairs fail constraints. Source: hub-options.csv and portfolio model.')

    start('Public context is useful—but it is not demand evidence','Archived World Bank 2022–2024')
    rows=[]
    for c in C:
        rr={r['year']:r for r in M['market_context'] if r['country']==c}
        rows.append([NAMES[c],f"{rr[2024]['population']/1e6:.2f}m",pct(rr[2024]['population']/rr[2022]['population']-1,2),f"${rr[2024]['gdp_per_capita_usd']:,.0f}"])
    tab(['Market','Population 2024','Change 2022–24','GDP/person 2024'],rows,[230,210,220,220],size=12)
    text(40,151,880,'Germany and France offer population scale; the Netherlands has higher GDP per capita. The client’s contribution ranking differs. Product installed base, service needs and qualified pipeline remain unmeasured.',14)
    text(40,94,880,'Current US$ is neither PPP nor real income. No null observations in the 18 country-years; historical values can be revised.',11,False,MUTED)
    end('World Bank archived APIs SP.POP.TOTL / NY.GDP.PCAP.CD. Retrieved 2026-09-27; source lastupdated 2026-07-13. Report p. 4.')

    start('Demand, FX and saving scope can change the second hub','Release conditions')
    box(40,284,280,116,'CZE DEMAND THRESHOLD','~17.7% uplift','Matches NLD held at 25%; normal FX')
    box(340,284,280,116,'CZE FX SWITCH','~2.6% haircut','Of net sales; with 3% gross refund shock')
    box(640,284,280,116,'ZERO-UPLIFT PAIR','−€24,368/year','CZE+ESP, normal FX and client savings')
    picture('saving_gap',40,85,510,180)
    text(590,259,330,'Saving scope is unverified',17,True,RED)
    text(590,222,330,'All supplied savings exceed actual fulfillment cost per unit. Validate other savings and local costs.<br/><br/>Cap savings at fulfillment and add stress: CZE+ESP falls to −€1,588/year; NLD+ESP stays +€54,211.',13)
    end('Source: required scenarios plus separate analyst boundary tests. Thresholds change if costs/savings change. Full precision: workbook Switching values.')

    start('Reconciliation is complete; hub impact is unverified','Evidence quality')
    tab(['Checked or computed','Result','Material limit'],[
        ['Orders and corrections','1,328 rows → 1,254 eligible orders','13 duplicates; 18 old revisions; 43 eligibility exclusions'],
        ['Returns through 31 Jan 2026','264 rows → 241 included return IDs','Orphan quarantined; late credit excluded; later returns censored'],
        ['Free shipments and cost recovery','12 free orders retained; 481 restocked units','Costs retained; no recovery for 600 un-restocked returned units'],
        ['Official archives','Hashes match; 12 means per currency; 18 WB country-years','Archive collection, not live research; FX is analytical translation'],
        ['Hub impact / investment cash','Model arithmetic, not observed effect','Demand, savings, ramp, working capital and site quotes unverified'],
    ],[220,280,380],size=11)
    text(40,128,880,'Booked cohort revenue is not cash. Contribution deducts product and fulfillment costs; hub recurring costs enter scenarios, and capex remains a separate year-zero investment.',14,True)
    end('Source: data-dictionary.md and raw audit files. No interviews or client account access. Report pp. 3, 10–12; full register with hashes supplied.')

    start('Five gates protect the investment envelope','90-day implementation proposal')
    tab(['When / owner','Work and dependency','Gate'],[
        ['1–15 days<br/>CFO + data lead','Reconcile; baseline service and FX exposure; all-in cash plan','A: finance/quality sign-off; capex and working capital known'],
        ['16–30 days<br/>COO + Procurement','Quotes, net saving bridge, pipeline; depends on A','B: Spain ≤€130k / 3 FTE; validated low case positive'],
        ['31–60 days<br/>Spain lead + IT + HR','Limited SKU pilot; trained staff, system and stock ready','C: ≥95% one-day dispatch; ≥99% stock accuracy'],
        ['61–75 days<br/>CFO + Commercial + Treasury','Update demand, return cohorts and FX; compare NLD','D: select CZE, NLD or defer the second site'],
        ['76–90 days<br/>COO + board sponsor','Contract / prepare second site only if gate passes','E: positive updated increment, budget/FTE fit, KPI ownership'],
    ],[180,350,350],size=11)
    text(40,114,880,'If cohort maturity or seasonality prevents a fair decision, retain Spain only. A 90-day pilot can test readiness and unit cost; it cannot establish a sustained 25% demand effect.',13)
    end('Owners, timing and service targets are consultant proposals. Dependencies can delay opening. Report pp. 8–9 contains staffing, KPI definitions and risk owners.')

    start('Track contribution, service and capital','Measurement proposal')
    tab(['Measure / cadence','Owner','Target or decision use'],[
        ['Contribution bridge / monthly','CFO','Actual + annualized run rate vs central-service comparison; positive validated low case'],
        ['Demand and mix / weekly','Commercial','Season-matched units; test 25% assumption and Czech selection threshold'],
        ['Net saving per unit / weekly','Procurement + Finance','Invoice-supported saving bridge; do not assume €2.10 CZE / €3.00 ESP'],
        ['Age-matched returns / monthly','Quality lead','CZE baseline 2.10%, ESP 1.81%; proposed alert +0.5 percentage points'],
        ['Dispatch and inventory / weekly','Operations','Proposed ≥95% within one business day; ≥99% stock accuracy'],
        ['Capex / FTE / commitments / weekly','CFO + HR','CZE+ESP envelope €225k / 5 FTE; all-in cash needs separately forecast'],
    ],[290,195,395],size=11)
    text(40,99,880,'No service baseline or causal uplift estimate is supplied. Validate definitions and compare pilot cohorts with similar centrally served customers.',12,False,MUTED)
    end('KPI targets are planning assumptions, not measured outcomes. Return-rate alert is distinct from the scenario’s 3%-of-gross refund-cost shock.')

    start('Approve the envelope; require evidence before site two','Proposed board resolution')
    text(40,401,860,'1. Reserve Czechia + Spain: €225,000 capex and five FTE.<br/>2. Release Spain after validated cost, service and cash gates.<br/>3. Keep Czechia conditional; use Netherlands as the stress-resilient alternative.<br/>4. Reopen the choice when demand, FX or saving thresholds move.<br/>5. Review realized contribution and committed cash monthly.',20,True)
    text(40,198,860,'Choosing NLD+ESP instead is reasonable if downside protection is the primary objective: €270,000 capex, six FTE, €166,931 base and €107,630 stress annual contribution.',16)
    text(40,118,860,'Evidence gaps: measured demand uplift; net saving scope; site quotes; working capital; ramp and cash realization. These limit certainty and funding release, while the supplied arithmetic is reproducible.',13,False,MUTED)
    end('Handover: executive report, formula-linked XLSX, metrics.json, saved raw sources/register, scripts, audit outputs and verification record.')
    cv.save()

def evidence_basis():
    card={
        'claim':'CZE+ESP is the preferred staged envelope under the consultant default of maximizing base annual incremental contribution within board constraints.',
        'claim_type':'Conditional action recommendation informed by a predictive financial model; not a causal claim.',
        'claim_to_source_table':[
            {'claim':'2025 cohort economics','sources':['S02','S03','S07','S08','S09','S11','S14'],'type':'synthetic transaction census within frozen exports','basis':'1254 eligible orders; 241 retained eligible return IDs','directness':'direct for defined cohort','status':'computed; downloaded sources checked','scope':'2025 shipments; returns through inclusive 2026-01-31'},
            {'claim':'Market context','sources':['S05','S10','S13'],'type':'official national aggregate series archive','basis':'18 country-years, two indicators','directness':'contextual only for demand','status':'archive provenance verified','scope':'2022–2024 values; source lastupdated 2026-07-13'},
            {'claim':'Hub effect','sources':['S06','S12'],'type':'synthetic planning assumptions','basis':'six options; low/base/high and joint stress','directness':'direct for model, no empirical causal evidence','status':'assumed / unverified effect','scope':'steady-state annual model'},
        ],
        'quality_limits':M['quality']['limitations'],
        'quality_dimensions':{'synthetic_exports':{'design_rigor':'explicit grain/revision/accounting rules; no external audit','bias_risk':'synthetic generation; not real demand','measurement_validity':'supported within dictionary/cutoff','completeness':'all indexed pages and corrections collected','applicability':'limited to synthetic case'},'official_archives':{'design_rigor':'official aggregate definitions','bias_risk':'revision and aggregation limits','measurement_validity':'strong for stated national units / reference FX','completeness':'all requested country-years and FX months present','applicability':'contextual; no product effect'},'hub_assumptions':{'design_rigor':'transparent arithmetic; no causal design','bias_risk':'possible optimism and unpriced scope','measurement_validity':'uplift and savings unverified','completeness':'working capital/ramp/site cash gaps','applicability':'scenario comparison only'}},
        'hierarchy_position_and_limits':'Official archive provenance is strongest for macro/FX measures; synthetic exports directly define this case; planning assumptions are weakest for actual hub impact. Prestige does not make macro data direct demand evidence.',
        'agreement_and_conflicts':'Model reconciles; source types measure different claims, so there is no independent corroboration of demand. Supplied savings exceed recorded fulfillment per unit; scope unresolved.',
        'missing_evidence':['measured causal uplift','supported net unit savings','site quotes','working capital','ramp','cash collections/refund timing','service baseline'],
        'resulting_evidence_state':'Arithmetic supported within synthetic case; real-world effect unverified; action recommendation provisional.',
        'calibrated_conclusion':M['recommendation']['rationale'],
        'flip_condition':M['recommendation']['release_conditions'],
        'choice_frame':{'options':'defer, six singles, all 15 pairs (11 feasible)','time':'steady-state annual benefit; separate year-zero capex','stakeholders':'board capital allocation; operations/HR feasibility; finance control; commercial demand'},
        'hard_constraints':{'source':'scenario-policy.md, user decision rules','capex_eur':450000,'fte':7,'hub_count':2,'status':'supplied binding'},
        'criteria_and_weight_provenance':{'owner':'consultant default for independent task execution, not claimed board preference','date':'2026-09-27','criteria':['maximize base annual increment','inspect low/high/stress','capex and FTE efficiency','stage irreversible commitments'],'weights':None,'probabilities':None,'scale':'EUR/year, EUR capex, FTE; no composite rating'},
        'option_comparison':'metrics.json portfolios contains every option/scenario with feasibility and rank.',
        'dominated_or_incomparable':'CZE+ESP dominates POL+ESP across all four contribution cases, capex and FTE. CZE+ESP and NLD+ESP are incomparable because stress protection trades against normal-case contribution and resources.',
        'selected_option':['CZE','ESP'],
        'concessions':{'stress_income_given_up_vs_nld_esp_eur':round(inc('NLD+ESP','stress')-inc('CZE+ESP','stress'),2)},
        'accepted_risks':'Unmeasured uplift and savings; CZK shock; implementation timing. Envelope recommendation is conditional, and second-site spend remains gated.',
        'baseline':{'formula':'C*u + U*(1+u)*s - F','selected_base_increment_eur':inc('CZE+ESP','base'),'decision_threshold':'positive annual increment within hard limits; maximize base by default'},
        'tested_ranges':[{'variable':'volume uplift','range':[.10,.25,.40],'provenance':'synthetic scenario policy'},{'variable':'joint stress','range':{'u':.25,'refund_cost_times_gross':.03,'fx_haircut_times_net_PLN_CZK':.10},'provenance':'synthetic conservative stress, no probability'},{'variable':'supplemental zero uplift','range':[0],'provenance':'analyst boundary test'},{'variable':'saving cap','range':'min(client saving, historical fulfillment/units)','provenance':'analyst cost-pool bound; not a measured saving'}],
        'perturbation_results':'metrics.json hub_scenarios, portfolios and sensitivity; audit CSVs retain exact values. Required stress changes refunds and FX jointly; boundary tests separately label combinations.',
        'switching_values':M['recommendation']['switching_values'],
        'robust_or_fragile_conclusion':'CZE+ESP leads normal volume cases but second-hub choice is fragile to FX and saving scope; recommendation provisional.',
        'research_priority':'Validate net saving bridge and Czech demand relative to Netherlands; Treasury quantifies relevant revenue exposure. Working-capital/site cash gates are separate from estimating uplift.',
        'public_questions':[
            {'question':'What are 2025 cohort economics?','conclusion':'computed and reconciled','missing_inputs':'cash ledger only for a separate cash reconciliation','reopen':'valid source correction or cutoff-eligible missing records'},
            {'question':'Do hubs cause 25% volume uplift?','conclusion':'unverified; causal claim held','missing_inputs':'credible pilot/control or demand evidence','reopen':'measured cohort effect with mix/seasonality/return maturity addressed'},
            {'question':'Which envelope should the board reserve?','conclusion':'provisional staged CZE+ESP','missing_inputs':'no input prevents arithmetic selection; release requires stated quote/cash/saving validation','reopen':'downside preference or threshold changes'},
        ],
        'controller_status':{'native_activation':'unconfirmed','application':'unverified','native_selection':'trade-off-analysis and sensitivity-analysis emitted complete procedures; no model calls','fallback':'evidence-hierarchy complete installed canonical reference read after selector request failures'},
        'grounding':'OpenSocrates grounding: evidence-hierarchy@3, trade-off-analysis@3, sensitivity-analysis@3',
    }
    (OUT/'decision_basis.json').write_text(json.dumps(card,indent=2)+'\n')

def main():
    charts();evidence_basis();report();board()
    print('Built executive report, 10-slide board PDF, charts and public decision basis.')

if __name__=='__main__':main()
