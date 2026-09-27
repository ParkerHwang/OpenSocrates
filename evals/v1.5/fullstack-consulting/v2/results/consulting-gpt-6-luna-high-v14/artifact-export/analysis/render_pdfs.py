#!/usr/bin/env python3
"""Render reviewed PDF editions of the report and board deck from metrics.json."""
import json, textwrap
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, KeepTogether, Flowable)
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'deliverables'; D=json.loads((OUT/'metrics.json').read_text())
NAVY=colors.HexColor('#17324D'); BLUE=colors.HexColor('#246B8E'); TEAL=colors.HexColor('#2A9D8F'); PALE=colors.HexColor('#E9F1F5'); INK=colors.HexColor('#273743'); MUTED=colors.HexColor('#617381'); GOLD=colors.HexColor('#EBB34C')
countries=D['countries']; months=D['monthly']; market=D['market_context']; scen=D['hub_scenarios']; alts=D['alternatives']; q=D['quality']; fx=D['fx_monthly']
names={'DEU':'Germany','FRA':'France','NLD':'Netherlands','POL':'Poland','CZE':'Czechia','ESP':'Spain'}
money=lambda x:'—' if x is None else f'€{x:,.0f}'
per=lambda x:'—' if x is None else f'{x:.1%}'
best=next(a for a in alts if a['countries']==D['recommendation']['countries'])
runner=next(a for a in sorted([a for a in alts if a['feasible']],key=lambda a:a['base'],reverse=True) if a['countries']!=best['countries'])

styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleMer',parent=styles['Title'],fontName='Helvetica-Bold',fontSize=27,leading=31,textColor=NAVY,spaceAfter=7))
styles.add(ParagraphStyle(name='H1Mer',parent=styles['Heading1'],fontName='Helvetica-Bold',fontSize=19,leading=23,textColor=NAVY,spaceBefore=3,spaceAfter=10))
styles.add(ParagraphStyle(name='H2Mer',parent=styles['Heading2'],fontName='Helvetica-Bold',fontSize=12,leading=15,textColor=BLUE,spaceBefore=8,spaceAfter=5))
styles.add(ParagraphStyle(name='BodyMer',parent=styles['BodyText'],fontName='Helvetica',fontSize=8.6,leading=12.1,textColor=INK,spaceAfter=6))
styles.add(ParagraphStyle(name='SmallMer',parent=styles['BodyText'],fontName='Helvetica',fontSize=7.1,leading=9,textColor=MUTED,spaceAfter=4))
styles.add(ParagraphStyle(name='CalloutMer',parent=styles['BodyText'],fontName='Helvetica-Bold',fontSize=12.3,leading=17,textColor=NAVY,backColor=PALE,borderColor=TEAL,borderWidth=1,borderPadding=9,spaceBefore=5,spaceAfter=10))
styles.add(ParagraphStyle(name='CellMer',parent=styles['BodyText'],fontName='Helvetica',fontSize=7.2,leading=9,textColor=INK))
styles.add(ParagraphStyle(name='CellHeadMer',parent=styles['BodyText'],fontName='Helvetica-Bold',fontSize=7.2,leading=9,textColor=colors.white))

def P(t,style='BodyMer'): return Paragraph(str(t),styles[style])
def table(data,widths,header=True,fontsize=7.2):
 rows=[]
 for i,row in enumerate(data):
  rows.append([P(x,'CellHeadMer' if header and i==0 else 'CellMer') for x in row])
 t=Table(rows,colWidths=widths,repeatRows=1 if header else 0,hAlign='LEFT')
 cmds=[('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),.25,colors.HexColor('#CAD6DD')),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]
 if header: cmds += [('BACKGROUND',(0,0),(-1,0),NAVY)]
 for r in range(1 if header else 0,len(data)):
  if r%2: cmds.append(('BACKGROUND',(0,r),(-1,r),PALE))
 t.setStyle(TableStyle(cmds)); return t

class ContributionBars(Flowable):
 def __init__(self,rows,width=495,height=142): super().__init__(); self.rows=rows; self.width=width; self.height=height
 def wrap(self,aW,aH): self.width=min(aW,self.width); return self.width,self.height
 def draw(self):
  c=self.canv; maxv=max(r['contribution_eur'] for r in self.rows); x0=102; maxw=self.width-x0-60; y=self.height-18
  c.setFont('Helvetica-Bold',8); c.setFillColor(NAVY); c.drawString(0,self.height-9,'2025 contribution by country (EUR)')
  for r in self.rows:
   v=r['contribution_eur']; c.setFont('Helvetica',7.5); c.setFillColor(INK); c.drawRightString(x0-8,y-3,names[r['country']]); w=maxw*v/maxv
   c.setFillColor(TEAL if r['country'] in best['countries'] else BLUE); c.roundRect(x0,y-7,w,12,2,fill=1,stroke=0)
   c.setFillColor(INK); c.drawString(x0+w+5,y-3,f'€{v:,.0f}'); y-=20

def page_header(c,doc):
 c.saveState(); W,H=A4; c.setStrokeColor(TEAL); c.setLineWidth(2); c.line(doc.leftMargin,H-12*mm,W-doc.rightMargin,H-12*mm)
 c.setFont('Helvetica-Bold',7.5); c.setFillColor(BLUE); c.drawString(doc.leftMargin,H-9*mm,'MERIDIAN PARTS  /  BOARD DECISION NOTE')
 c.setStrokeColor(colors.HexColor('#CAD6DD')); c.setLineWidth(.4); c.line(doc.leftMargin,12*mm,W-doc.rightMargin,12*mm)
 c.setFont('Helvetica',7); c.setFillColor(MUTED); c.drawString(doc.leftMargin,8*mm,'Synthetic client inputs • Public archive vintage 27 Sep 2026')
 c.drawRightString(W-doc.rightMargin,8*mm,str(doc.page)); c.restoreState()

def make_report():
 path=OUT/'meridian_board_brief.pdf'; doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=17*mm,leftMargin=17*mm,topMargin=19*mm,bottomMargin=17*mm,title='Meridian Parts | European service-hub expansion')
 st=[]
 st += [P('MERIDIAN PARTS  /  OPERATIONS STRATEGY','H2Mer'),P('European service-hub expansion','TitleMer'),P('Board decision brief • 27 September 2026<br/>2025 shipped sales and returns known through 31 January 2026','BodyMer'),Spacer(1,8)]
 st += [P(f"Recommendation: stage <b>{best['label']}</b> for a reversible pilot—Spain first, with country-specific tests in the Netherlands—and release site capex only after the 90-day gates. It has the highest minimum across the supplied low/base/high/stress cases: <b>{money(best['minimum_scenario_eur'])}/year floor</b> ({money(best['base'])} base; {money(best['stress'])} stress) on {money(best['capex_eur'])} year-zero capex and {best['fte']} FTE. These are scenario calculations, not a causal hub forecast.",'CalloutMer')]
 st += [P('Board choice','H2Mer'),P('With no board probabilities, this uses the feasible pair with the highest minimum across the client-defined cases. That is an explicit conservative preference, not a statistical result. CZE + ESP is the strongest alternative by base contribution: EUR31,168/year more in base, but EUR75,450/year less under the defined stress. The caps are EUR450,000 and seven FTE; both options fit. Defer carries no investment and remains available.','BodyMer')]
 top=sorted([a for a in alts if a['feasible']],key=lambda a:a['base'],reverse=True)[:7]
 rows=[['Alternative','Capex','FTE','Low / yr','Base / yr','High / yr','Stress / yr']]
 for a in top: rows.append([a.get('label') or 'Defer',money(a['capex_eur']),str(a['fte']),money(a['low']),money(a['base']),money(a['high']),money(a['stress'])])
 st += [table(rows,[105,57,28,58,58,58,64]),Spacer(1,7),P('Hard limits are board rules. Scenarios are not probability-weighted and option economics assume additive pairs with no network synergy.','SmallMer'),PageBreak()]

 st += [P('1  /  2025 operating diagnosis','H1Mer'),P('The shipment ledger establishes where Meridian already sells and earns contribution. It does not show how much demand a local hub would create. Modeled hub economics have two levers—added volume at current market contribution economics and assumed per-unit fulfillment savings—less annual fixed cost.','BodyMer')]
 rows=[['Market','Orders','Units','Net sales','Net COGS','Fulfillment','Contribution','Margin','Returned units']]
 for r in countries: rows.append([names[r['country']],f"{r['shipped_orders']:,}",f"{r['shipped_units']:,}",money(r['net_sales_eur']),money(r['net_cogs_eur']),money(r['fulfillment_eur']),money(r['contribution_eur']),per(r['margin']),f"{r['returned_units']:,}"])
 st += [table(rows,[68,37,43,53,53,53,61,40,48]),Spacer(1,7),ContributionBars(countries),P('Revenue, cash and contribution','H2Mer'),P('Gross sales are shipped quantity × price less discounts. Refund credits reduce net sales. Net sales approximate booked revenue under the supplied credit ledger, not cash collected: payment timing, settlement FX, fees and working capital were unavailable. Contribution further deducts net COGS after recovered restocked units and nonrefundable fulfillment. It is not EBITDA or hub profit; option recurring costs are deducted separately.','BodyMer'),P('Country margins equal contribution ÷ net sales. Monthly records contain 72 rows (six countries × 12 months); each annual country total reconciles to its monthly rows.','SmallMer'),PageBreak()]

 st += [P('2  /  Reconciliation and source quality','H1Mer'),P('The client’s transaction, cost and option data are synthetic. They were collected from the frozen local source room; no live client account, customer or interview was accessed. Raw inputs and source-room metadata are retained under sources/raw.','BodyMer')]
 oq=q['orders']; rq=q['returns']
 st += [P(f"Orders: {oq['raw_rows']:,} raw rows represent {oq['unique_order_ids']:,} IDs. {oq['duplicate_rows_removed']} exact duplicate rows were removed; {oq['revisioned_ids']} IDs contain distinct revisions; no same-revision conflicts were found. Highest numeric revision wins across both extract pages and the whole-row correction file. {oq['eligible_2025_shipped_orders']:,} shipped, non-test, 2025 orders are included; {oq['excluded_status_or_test_or_date']} selected records are excluded ({oq['exclusion_counts_after_revision']}). Zero-price shipment orders are retained ({q['sales_checks']['valid_zero_price_shipments']}); January 2026 shipments are not applied to the base.",'BodyMer')]
 st += [P(f"Returns: {rq['raw_rows']} rows represent {rq['unique_return_ids']} IDs. {rq['exact_duplicate_rows_removed']} exact duplicate rows removed; {rq['revisioned_ids']} ID had multiple revisions; none have conflicting same-revision rows. The highest revision is kept. Through the inclusive 31 January 2026 cutoff, {rq['eligible_linked_returns']} returns linked to eligible selected sales are included. {rq['quarantined_orphan_or_ineligible_returns']} orphan/ineligible record is quarantined ({', '.join(rq['orphan_ids'])}); {rq['after_cutoff_returns']} record arrived after cutoff. Return consistency checks: {rq['return_units_exceeding_shipped_orders']} orders exceed shipped units, {rq['rows_restocking_more_than_returned']} return rows restock more units than returned, and {rq['orders_with_refunds_above_gross_local_sales']} orders refund more than gross local sales.",'BodyMer')]
 st += [P('FX and rounding','H2Mer'),P('For PLN and CZK, sales and refund credits use the arithmetic mean of published daily ECB reference observations in the original shipment month, quoted as local currency units per EUR; EUR is 1. No inversion or current FX is used. Each order’s gross, refund, gross COGS, recovered COGS and fulfillment amounts are rounded half-up to cents before summation. These reference quotes are analytical translation assumptions, not transaction rates.','BodyMer'),P(f"Missing costs: {len(q['missing']['missing_cost_orders'])}; missing FX: {len(q['missing']['missing_fx_orders'])}; missing World Bank population cells: {q['missing']['missing_world_bank_population']}; missing GDP cells: {q['missing']['missing_world_bank_gdp']}. No values are imputed.",'BodyMer'),PageBreak()]

 st += [P('3  /  Market context','H1Mer'),P('Archived official World Bank series provide population (persons) and GDP per capita (current US dollars) for 2022–2024. Population change and income level contextualize scale and economic environment only; neither is direct evidence of Meridian product demand.','BodyMer')]
 pm={(r['country'],r['year']):r['population'] for r in market}; gm={(r['country'],r['year']):r['gdp_per_capita_usd'] for r in market}
 rows=[['Country','Population 2022','Population 2023','Population 2024','Change 2022–24','GDP/capita 2024, current USD']]
 for c in names:
  a=pm[c,2022]; b=pm[c,2024]; change=b/a-1 if a and b else None
  rows.append([names[c],f'{a:,}' if a is not None else 'missing',f'{pm[c,2023]:,}' if pm[c,2023] is not None else 'missing',f'{b:,}' if b is not None else 'missing',per(change),f"${gm[c,2024]:,.0f}" if gm[c,2024] is not None else 'missing'])
 st += [table(rows,[76,74,74,74,75,95]),Spacer(1,10),P('All 18 archived year-country cells are present. Population values are persons. GDP per capita is nominal current USD—not PPP and not constant-price real income. Historical public series were collected into a frozen source room on 27 September 2026 and may incorporate revisions after the measured 2025 trading year. Original API URLs, response hashes and vintage are listed in sources/source-register.json.','BodyMer'),P('Market scope limitation','H2Mer'),P('No market sizing, competitor comparison, localized demand survey, labor cost benchmark, real-estate quote, service-level history or regulatory diligence was supplied or added. This recommendation does not infer product fit from GDP per capita or population.','BodyMer'),PageBreak()]

 st += [P('4  /  Hub economics and decision','H1Mer'),P('For each country, annual incremental contribution equals C×u + U×(1+u)×s − F: C is 2025 contribution, U shipped units, u is assumed volume uplift (10%, 25%, 40%), s is client-assumed fulfillment saving per unit and F recurring annual fixed cost. Capex K is separate year-zero investment; simple undiscounted payback is K ÷ positive annual increment, otherwise null.','BodyMer'),P('Stress is the defined joint sensitivity, not a forecast probability: base uplift 25%, refund shock 3% of gross sales without added cost recovery, plus 10% of net sales depreciation for PLN/CZK options. Stressed contribution is compared against the unchanged normal baseline, then uplifted savings and recurring cost are applied. Pairs add country economics without synergy.','BodyMer')]
 rows=[['Option','Capex yr 0','Fixed / yr','FTE','Low / yr','Base / yr','High / yr','Stress / yr','Base payback']]
 for a in [best,runner]+[a for a in sorted([x for x in alts if x['feasible'] and len(x['countries'])==2],key=lambda x:x['base'],reverse=True) if a['countries'] not in (best['countries'],runner['countries'])][:3]:
  rows.append([a.get('label') or 'Defer',money(a['capex_eur']),money(a['annual_fixed_eur']),str(a['fte']),money(a['low']),money(a['base']),money(a['high']),money(a['stress']),f"{a['capex_eur']/a['base']:.1f} years" if a['base']>0 else '—'])
 st += [table(rows,[73,50,50,25,48,49,48,52,63]),Spacer(1,10),P(f"The strongest different feasible alternative is {runner['label']}: {money(runner['base'])}/year base against {money(best['base'])}/year for {best['label']}—a modeled difference of {money(best['base']-runner['base'])}/year. The stress values are {money(runner['stress'])} and {money(best['stress'])}/year respectively. It uses {money(runner['capex_eur'])} capex and {runner['fte']} FTE, compared with {money(best['capex_eur'])} and {best['fte']} FTE. Defer avoids all capex and recurring cost while foregoing modeled increment.",'BodyMer'),P('Switching condition','H2Mer'),P('The choice assumes 10%–40% volume uplift and the stated per-unit savings. For one option, the break-even uplift is (F−U×s)/(C+U×s), when the denominator is positive. If a reversible pilot shows savings are not avoidable, uplift misses break-even, or annual fixed cost rises enough to erase contribution, defer, reconfigure, or select the runner-up. Validate all levers before a full lease or site commitment.','BodyMer'),P('Preference provenance: selecting the combination with the highest minimum across low/base/high/stress is a conservative judgment because no board probabilities or weights were supplied. A base-only choice selects CZE + ESP.','SmallMer'),PageBreak()]

 st += [P('5  /  First 90 days','H1Mer'),P('Stage investment so the board can stop after learning whether customer and cost response support the modeled economics.','BodyMer')]
 rows=[['Timing / owner','Work, dependencies and decision gate'],
 ['Days 0–15<br/>COO + Finance','Reconcile 2025 cohort and return baseline; validate invoice-level avoidable fulfillment cost, option cost assumptions, pilot SKU/zone, comparison design and KPI definitions. Gate 1: auditable baseline and target cohort before any site commitment.'],
 ['Days 16–35<br/>Operations + Data','Cost and design the service zone, inventory/transfer process, staffing, temporary 3PL/space, country legal/tax review and service SLA. Gate 2: signed costed design, data coverage ≥98%, capex and FTE inside board caps.'],
 ['Days 36–65<br/>Country lead + Supply Chain','Run a reversible, limited-SKU pilot with temporary space/3PL or reserved stock; monitor matched/holdout cohorts, delivery promise, fill rate, contribution and handling cost. Gate 3: require at least four weeks usable data; stop for legal/safety breach, stock accuracy <98%, or negative contribution trend.'],
 ['Days 66–90<br/>CFO + COO + Board sponsor','Compare to pre-registered baseline; update scenarios, quotes, FX/returns stress, recurring costs and staffing. Gate 4: release site capex only if base annual contribution remains positive after fixed cost, all caps hold, and downside is accepted; otherwise defer/reconfigure.']]
 st += [table(rows,[112,387]),P('KPI plan: weekly pilot and monthly board reporting for incremental shipped orders/units, net sales and return rate by sale cohort, contribution after returns, avoidable fulfillment EUR/unit, median/P90 delivery time, on-time-in-full, fill rate, stock accuracy, restocked share and return cycle time, capex committed and staffed FTE. Publish numerator, denominator, comparison period and data coverage. Do not call seasonal/mix changes hub lift without a credible comparison.','BodyMer'),P('Principal risks: demand does not rise; savings are not truly avoidable; reference FX differs from settlement; inventory fragmentation increases stockouts or working capital; returns erode margins; local fixed costs, labor, lease or compliance assumptions are incomplete. Mitigations are a matched reversible pilot, invoice checks, monthly settlement-FX monitoring, narrow SKU scope and local quotes/legal review before commitment.','BodyMer'),PageBreak()]

 st += [P('Appendix  /  ECB reference-rate means','H1Mer'),P('Arithmetic means of published business-day reference rates during each 2025 calendar month. Quote: local currency units per EUR. Daily observation counts vary with the calendar and ECB publication availability. EUR-denominated markets use 1.00.','BodyMer')]
 pln={r['month']:r for r in fx if r['currency']=='PLN'}; czk={r['month']:r for r in fx if r['currency']=='CZK'}
 rows=[['Month','PLN per EUR','Days','CZK per EUR','Days']]
 for m in sorted(pln): rows.append([m,f"{pln[m]['local_per_eur']:.6f}",str(pln[m]['published_business_days']),f"{czk[m]['local_per_eur']:.6f}",str(czk[m]['published_business_days'])])
 st += [table(rows,[110,100,65,100,65]),Spacer(1,12),P('Source: archived ECB daily reference rates from ecb-history.zip and its lossless ecb-history.csv extraction in sources/raw. The source register records original URL, retrieval timestamp, hashes, bytes, units and coverage. Public series is an official snapshot; the synthetic client transaction data are distinct from these observations.','BodyMer'),P('Reproducibility: run <b>python3 analysis/build.py</b>, then <b>python3 analysis/render_pdfs.py</b> from the project root. The metrics JSON is the canonical exchange dataset; the workbook includes all monthly and country calculations, scenarios, context, sources and quality notes.','BodyMer'),P('Limits: one synthetic trading year; no demand causal design, discounted cash flow, ramp-up, synergies, tax, lease exit, working capital or probability model. Public historical revisions may post-date the trading year. Recommendation is conditional; it is not statistically proven.','SmallMer')]
 doc.build(st,onFirstPage=page_header,onLaterPages=page_header)

def wrap_lines(text,font,size,maxw):
 words=text.split(); lines=[]; line=''
 for word in words:
  trial=word if not line else line+' '+word
  if stringWidth(trial,font,size)<=maxw: line=trial
  else:
   if line: lines.append(line)
   line=word
 if line: lines.append(line)
 return lines

def make_deck_pdf():
 path=OUT/'meridian_board_deck.pdf'; W,H=landscape((960,540)); c=canvas.Canvas(str(path),pagesize=(W,H)); c.setTitle('Meridian Parts | Board presentation')
 def base(title,kicker,n):
  c.setFillColor(colors.white);c.rect(0,0,W,H,fill=1,stroke=0);c.setFillColor(TEAL);c.rect(0,H-8,W,8,fill=1,stroke=0);c.setFillColor(BLUE);c.setFont('Helvetica-Bold',10);c.drawString(42,H-35,kicker.upper());c.setFillColor(NAVY);c.setFont('Helvetica-Bold',25);c.drawString(42,H-68,title);c.setStrokeColor(colors.HexColor('#D5E1E6'));c.line(42,31,W-42,31);c.setFillColor(MUTED);c.setFont('Helvetica',8);c.drawString(42,17,'MERIDIAN PARTS  •  Synthetic case  •  Source vintage 27 Sep 2026');c.drawRightString(W-42,17,str(n))
 def box(x,y,w,h,fill=PALE,stroke=colors.HexColor('#D5E1E6')):
  c.setFillColor(fill);c.setStrokeColor(stroke);c.roundRect(x,y,w,h,8,fill=1,stroke=1)
 def textblock(x,y,w,text,size=15,color=INK,leading=None,bold=False):
  leading=leading or size*1.35; font='Helvetica-Bold' if bold else 'Helvetica'; c.setFont(font,size);c.setFillColor(color)
  yy=y
  for para in text.split('\n'):
   if para=='': yy-=leading*.65; continue
   for line in wrap_lines(para,font,size,w): c.drawString(x,yy,line);yy-=leading
  return yy
 def drawtable(x,y,widths,rows,rowh=36,fs=11):
  yy=y
  for i,row in enumerate(rows):
   xx=x; h=rowh
   for j,val in enumerate(row):
    c.setFillColor(NAVY if i==0 else (PALE if i%2==1 else colors.white));c.setStrokeColor(colors.HexColor('#CCD8DE'));c.rect(xx,yy-h,widths[j],h,fill=1,stroke=1)
    c.setFillColor(colors.white if i==0 else INK);c.setFont('Helvetica-Bold' if i==0 else 'Helvetica',fs)
    lines=wrap_lines(str(val),'Helvetica-Bold' if i==0 else 'Helvetica',fs,widths[j]-10)
    for k,line in enumerate(lines[:2]):c.drawString(xx+5,yy-14-k*(fs+2),line)
    xx+=widths[j]
   yy-=h
  return yy
 # slide 1
 base('Stage Netherlands + Spain behind a 90-day pilot','Board decision • 27 September 2026',1)
 box(42,116,515,330);textblock(66,407,460,f"{best['label']} has the strongest floor across defined cases",29,NAVY,37,True);textblock(66,295,440,f"Floor  {money(best['minimum_scenario_eur'])} / year\nBase  {money(best['base'])} / year\nStress  {money(best['stress'])} / year\nCapex  {money(best['capex_eur'])}  •  {best['fte']} FTE",17,BLUE,25,True)
 box(586,116,332,330,fill=PALE);textblock(610,410,285,'Board action',18,BLUE,24,True);textblock(610,374,280,'Approve a 90-day reversible pilot and staged capex envelope. Release full investment only after measured savings and incremental volume clear the operating gates. Defer remains a valid outcome.',15,INK,22)
 c.showPage()
 # slide 2
 base('2025 contribution describes the baseline, not hub causality','Operating diagnosis',2)
 textblock(44,438,870,'Sales and margin vary across markets; option economics depend on local volume response and avoidable fulfillment savings.',14,INK,20)
 rows=[['Country','Orders','Units','Net sales','Contribution','Margin']]+[[names[r['country']],f"{r['shipped_orders']:,}",f"{r['shipped_units']:,}",money(r['net_sales_eur']),money(r['contribution_eur']),per(r['margin'])] for r in countries]
 drawtable(48,390,[190,112,112,155,165,100],rows,39,11)
 textblock(50,95,860,'No lead-time, lost-sales, customer-interview or controlled service-hub evidence was supplied. Historical shipped mix is not proof of incremental demand from a local hub.',13,BLUE,18)
 c.showPage()
 # slide 3
 base('The leading feasible alternatives trade modeled return for resilience','Scenario comparison',3)
 textblock(44,438,870,'Annual incremental contribution after recurring fixed cost; capex is separate year-zero investment.',14,INK,20)
 comp=[best,runner]+[a for a in sorted([x for x in alts if x['feasible'] and len(x['countries'])==2],key=lambda x:x['base'],reverse=True) if a['countries'] not in (best['countries'],runner['countries'])][:2]
 rows=[['Option','Capex yr 0','Fixed / yr','FTE','Base / yr','Stress / yr','Payback']]+[[a.get('label') or 'Defer',money(a['capex_eur']),money(a['annual_fixed_eur']),str(a['fte']),money(a['base']),money(a['stress']),f"{a['capex_eur']/a['base']:.1f} years" if a['base']>0 else '—'] for a in comp]
 drawtable(50,385,[190,110,115,55,120,120,120],rows,50,11)
 textblock(52,100,850,'Stress is the client policy’s joint refund and FX shock, not a probability forecast. Recommendation uses the highest minimum across low/base/high/stress; CZE + ESP is the leading base-only alternative.',13,BLUE,19)
 c.showPage()
 # slide 4
 base('Market context helps locate scale, not product demand','External evidence',4)
 textblock(44,438,870,'Archived official World Bank population and current-USD GDP/capita, 2022–2024; snapshot vintage 27 Sep 2026.',14,INK,20)
 pop={(r['country'],r['year']):r['population'] for r in market}; gdp={(r['country'],r['year']):r['gdp_per_capita_usd'] for r in market}
 rows=[['Country','Population change 2022–24','GDP/capita 2024']]
 for co in names:
  a,b=pop[co,2022],pop[co,2024]; rows.append([names[co],per(b/a-1 if a and b else None),f"${gdp[co,2024]:,.0f}" if gdp[co,2024] is not None else 'missing'])
 drawtable(80,395,[300,290,290],rows,42,13)
 textblock(82,125,790,'GDP/capita is current USD, not PPP or constant-price income. Population and GDP do not establish Meridian product demand.',14,BLUE,20)
 c.showPage()
 # slide 5
 base('Use staged gates to turn assumptions into evidence','90-day plan',5)
 stages=[('Days 0–15','COO + Finance','Reconcile baseline; validate avoidable cost, cohort and KPI definitions.','Gate: auditable baseline'),('Days 16–35','Operations + Data','Costed design, pilot zone/SKUs, staffing, legal and inventory dependencies.','Gate: budget and controls'),('Days 36–65','Country + Supply Chain','Reversible limited-SKU pilot; matched baseline and weekly operating data.','Gate: ≥4 usable weeks'),('Days 66–90','CFO + COO + Board','Update scenarios, stress and quotes; release, reconfigure or defer.','Gate: positive base economics')]
 yy=433
 for i,(when,owner,work,gate) in enumerate(stages):
  box(45,yy-70,870,78);textblock(60,yy-23,100,when,14,TEAL,18,True);textblock(170,yy-23,145,owner,13,NAVY,17,True);textblock(320,yy-20,390,work,12,INK,16);textblock(728,yy-23,168,gate,12,BLUE,16,True);yy-=91
 textblock(50,66,855,'Weekly: incremental units/orders, return rate, contribution after returns, avoidable EUR/unit, OTIF, P90 delivery, fill rate, stock accuracy, capex and FTE.',11,INK,15)
 c.showPage()
 # slide 6
 base('Reopen the choice on measured unit economics','Risks and switch conditions',6)
 box(45,86,420,355);box(495,86,420,355)
 textblock(69,407,365,'What changes the choice',17,BLUE,22,True);textblock(69,369,365,'• Volume response below modeled 10–40%\n• Savings prove not avoidable\n• Fixed costs exceed quotes\n• Return stress erodes contribution\n• Pilot misses service or stock gates\n• Capex/FTE exceed board caps',14,INK,24)
 textblock(520,407,365,'Risk controls',17,BLUE,22,True);textblock(520,369,365,'• Matched pilot before lift claims\n• Validate savings against invoices\n• Track cash FX separately from booked revenue\n• Limit initial SKU scope\n• Monitor restocked share and stock accuracy\n• Defer or reconfigure if downside is not accepted',14,INK,24)
 c.showPage()
 # slide 7
 base('Appendix: model boundaries and reproducibility','Sources and limitations',7)
 textblock(48,445,855,'Synthetic inputs: order extracts, revisions/corrections, returns, unit costs, hub options and scenario policy from the frozen source room.\n\nPublic inputs: archived World Bank population and GDP/capita plus ECB daily reference rates, with URLs, timestamps, hashes, units and periods in sources/source-register.json.\n\nReproduce: python3 analysis/build.py; python3 analysis/render_pdfs.py. Workbook has 72 monthly results, country totals, 24 PLN/CZK FX means, market context, all hub scenarios and feasible combinations.\n\nLimits: one synthetic baseline year; monthly ECB translation is not transaction FX; no causal lift, probability distributions, ramp, discounting, synergy, tax, working capital or site/legal quotes. Public archive may contain later revisions.',14,INK,20)
 c.save()

make_report();make_deck_pdf();print('Rendered PDF report and deck')
