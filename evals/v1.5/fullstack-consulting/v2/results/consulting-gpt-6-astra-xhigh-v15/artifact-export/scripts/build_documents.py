"""Create an executive PDF report and vector board presentation from metrics.json."""
import csv
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
M=json.loads((OUT/'metrics.json').read_text())
D=json.loads((OUT/'decision-support.json').read_text())
S=json.loads((OUT/'source-register.json').read_text())
C={r['country']:r for r in M['countries']}
P={r['option']:r for r in M['portfolio_scenarios']}
H={(r['country'],r['scenario']):r for r in M['hub_scenarios']}
T={r['country']:r for r in M['decision_thresholds']}
W={(r['country'],r['year']):r for r in M['market_context']}
src={r['source_id']:r for r in S}
NAVY=HexColor('#162D43');TEAL=HexColor('#087F8C');ORANGE=HexColor('#CB824F');RED=HexColor('#AB4248');GRAY=HexColor('#52677A');PALE=HexColor('#EDF3F6');LINE=HexColor('#D6E1E7')
FONT,BOLD='Helvetica','Helvetica-Bold'
fontdir=Path('/System/Library/Fonts/Supplemental')
if (fontdir/'Arial.ttf').exists():
    pdfmetrics.registerFont(TTFont('Arial',str(fontdir/'Arial.ttf')))
    pdfmetrics.registerFont(TTFont('Arial-Bold',str(fontdir/'Arial Bold.ttf')))
    pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='Arial-Bold',italic='Arial',boldItalic='Arial-Bold')
    FONT,BOLD='Arial','Arial-Bold'

def eur(v,dp=0):return f'€{v:,.{dp}f}' if v>=0 else f'-€{-v:,.{dp}f}'
def k(v,dp=1):return f'{v/1000:,.{dp}f}'
def pct(v,dp=1):return f'{v:.{dp}%}' if v is not None else '—'
def yrs(v):return '—' if v is None else f'{v:.2f}'
def linkrefs(text):
    def sub(match):
        sid=match.group(1);r=src[sid]
        url=r['original_url'] or r['collection_url']
        return f'<link href="{escape(url, {chr(34):"&quot;"})}" color="#087F8C">[{sid}]</link>'
    return re.sub(r'\[(S\d\d|L\d\d)\]',sub,text)

class PDF:
    def __init__(self,path,width,height,deck=False):
        self.c=canvas.Canvas(str(path),pagesize=(width,height),pageCompression=1)
        self.c.setTitle('Meridian Parts | European service-hub expansion'+(' | Board briefing' if deck else ' | Executive report'))
        self.c.setAuthor('Operations advisory | Synthetic case')
        self.w,self.h,self.deck=width,height,deck
        self.margin=42 if not deck else 38
        self.width=width-2*self.margin
        self.page=0;self.boxes=[]
    def new(self,title,kicker='MERIDIAN PARTS  /  EUROPEAN SERVICE HUBS'):
        if self.page:self.c.showPage()
        self.page+=1
        self.c.setFillColor(NAVY);self.c.rect(0,self.h-9,self.w,9,fill=1,stroke=0)
        self.c.setFont(BOLD,8 if not self.deck else 9);self.c.setFillColor(TEAL)
        self.c.drawString(self.margin,self.h-34,kicker)
        self.y=self.h-52
        self.p(title,22 if not self.deck else 27,bold=True,color=NAVY,space=16)
        self.footer()
    def footer(self):
        c=self.c;c.setStrokeColor(LINE);c.line(self.margin,37,self.w-self.margin,37)
        c.setFillColor(GRAY);c.setFont(FONT,7.2 if not self.deck else 8)
        c.drawString(self.margin,24,'SYNTHETIC CLIENT  •  2025 SHIPMENTS  •  RETURNS THROUGH 31 JAN 2026')
        c.drawRightString(self.w-self.margin,24,f'{self.page:02d}')
    def p(self,text,size=10.3,bold=False,color=NAVY,space=9,width=None,x=None):
        width=width or self.width;x=self.margin if x is None else x
        style=ParagraphStyle('p',fontName=BOLD if bold else FONT,fontSize=size,leading=size*1.37,textColor=color,spaceAfter=0)
        p=Paragraph(linkrefs(text),style)
        _,height=p.wrap(width,2000)
        bottom=self.y-height
        assert bottom>=49, f'Overflow page {self.page}: {text[:80]} at {bottom}'
        p.drawOn(self.c,x,bottom)
        self.boxes.append(dict(page=self.page,kind='paragraph',x=x,y=bottom,w=width,h=height,text=re.sub('<[^>]+>','',text)))
        self.y=bottom-space
        return height
    def section(self,text):self.p(text,12.2,bold=True,color=TEAL,space=7)
    def table(self,headers,rows,widths=None,size=8.1,rowheight=None,highlight=None):
        widths=widths or [self.width/len(headers)]*len(headers)
        assert abs(sum(widths)-self.width)<1
        ps=ParagraphStyle('cell',fontName=FONT,fontSize=size,leading=size*1.24,textColor=NAVY)
        hs=ParagraphStyle('head',fontName=BOLD,fontSize=size,leading=size*1.24,textColor=white)
        data=[[Paragraph(escape(str(x)).replace('\n','<br/>'),hs) for x in headers]]
        for row in rows:
            data.append([Paragraph(linkrefs(str(x)).replace('\n','<br/>'),ps) for x in row])
        t=Table(data,colWidths=widths,repeatRows=1,rowHeights=rowheight)
        st=[('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,PALE]),('LINEBELOW',(0,-1),(-1,-1),.6,LINE)]
        if highlight:
            for row in highlight:st.append(('BACKGROUND',(0,row),(-1,row),HexColor('#DDF0EF')))
        t.setStyle(TableStyle(st));_,height=t.wrap(self.width,2000)
        assert self.y-height>=49, f'Table overflow page {self.page}: {self.y-height}'
        t.drawOn(self.c,self.margin,self.y-height)
        self.boxes.append(dict(page=self.page,kind='table',x=self.margin,y=self.y-height,w=self.width,h=height,rows=len(rows)+1,cols=len(headers)))
        self.y-=height+13
    def note(self,text):self.p(text,8.1 if not self.deck else 9.1,color=GRAY,space=10)
    def tiles(self,items,height=73):
        gap=12;width=(self.width-gap*(len(items)-1))/len(items);y=self.y-height
        assert y>=49
        for i,(label,value,detail) in enumerate(items):
            x=self.margin+i*(width+gap);self.c.setFillColor(PALE);self.c.roundRect(x,y,width,height,6,fill=1,stroke=0)
            self.c.setFillColor(GRAY);self.c.setFont(BOLD,8.2 if not self.deck else 10);self.c.drawString(x+12,y+height-18,label)
            self.c.setFillColor(TEAL);self.c.setFont(BOLD,23 if not self.deck else 26);self.c.drawString(x+12,y+height-45,value)
            self.c.setFillColor(GRAY);self.c.setFont(FONT,7.7 if not self.deck else 9);self.c.drawString(x+12,y+11,detail)
        self.y=y-16
    def bars(self,labels,values,height=176,caption='EUR thousands',colors=None):
        left=self.margin+62;right=self.w-self.margin-65;top=self.y-7
        vmax=max(abs(v) for v in values)*1.08
        barspace=height/len(labels)
        self.c.setFillColor(GRAY);self.c.setFont(FONT,8 if not self.deck else 11)
        for i,(label,v) in enumerate(zip(labels,values)):
            yy=top-i*barspace-16
            self.c.setFillColor(NAVY);self.c.drawRightString(left-12,yy+3,label)
            self.c.setFillColor(colors[i] if colors else TEAL);self.c.rect(left,yy,(right-left)*abs(v)/vmax,15 if not self.deck else 18,fill=1,stroke=0)
            self.c.setFillColor(NAVY);self.c.drawString(left+(right-left)*abs(v)/vmax+7,yy+3,k(v))
        self.y-=height+13;self.note(caption)
    def save(self,path):
        self.c.save()
        (ROOT/'verification'/path).write_text(json.dumps(self.boxes,indent=2)+'\n')

def make_report():
    r=PDF(OUT/'Meridian_executive_report.pdf',595.28,841.89)
    r.new('Reserve Czechia + Spain.\nRelease the investment in stages.')
    r.p('Board recommendation | 27 September 2026',10,color=GRAY)
    r.tiles([('BASE ANNUAL INCREMENT','€198.1k','after €95k recurring fixed cost'),('YEAR-ZERO CAPEX','€225k','five FTE; two proposed hubs'),('BASE SIMPLE PAYBACK','1.14 years','full run-rate; excludes ramp-up')])
    r.p('<b>Conditionally fund Czechia and Spain, with Spain first.</b> This pair produces the highest modeled annual increment in low, base and high volume cases among all feasible choices. It uses half of the €450,000 capex ceiling and five of seven FTE. Reserve the envelope; release commitments only after evidence gates. [S06] [S12]')
    r.p('The base case adds <b>€198,099.31/year</b>; low adds €64,619.11; high adds €331,579.51. The defined joint return/FX stress leaves €32,179.71, but Czechia alone loses €37,826.95. Simple stress payback stretches to 6.99 years. These are deterministic planning outcomes, with no assigned probabilities.')
    r.section('The decision-changing issue')
    r.p('Every proposed per-unit saving exceeds the fulfillment cost actually recorded per unit. If savings are capped at that recorded cost, the preferred pair produces €164,331.65 in base and <b>-€1,587.95 in stress</b>. This does not invalidate the prescribed arithmetic; it makes the cost scope unverified and the commitment conditional. [S06] [S08] [S09]')
    r.section('What the board gives up')
    r.p('<b>Netherlands + Spain</b> is the strongest downside alternative: €166,931.43 base and €107,630.13 stress, at €270,000 and six FTE. Choosing it sacrifices €31,167.88/year in base and consumes €45,000 more capex plus one FTE, but gains €75,450.42/year in stress. Poland + Spain is the second-highest base choice, yet Czechia + Spain is better on every modeled scenario and uses fewer resources.')
    r.section('Decision frame and evidence strength')
    r.p('Hard limits come from the board: at most two hubs, €450,000 capex and seven FTE. The analyst’s stated default is to maximize base annual contribution inside those limits and expose downside separately; no invented weights or statistical certainty. A board preference for downside preservation changes the second hub to the Netherlands. Defer remains valid if the evidence gates fail.')
    r.note('Evidence: client records and hub inputs are synthetic; accounting outputs are computed; public macro/FX series are frozen official observations. No customer interviews, lease offers or live client access were undertaken. The recommendation is an inference from this limited model, not causal proof.')

    r.new('Reconcile the cohort before judging the market')
    r.table(['Reconciliation step','Orders','Returns'],[
        ['Raw rows collected','1,328','264'],['Identical duplicate rows removed','13','20'],
        ['Lower revisions superseded','18','1'],['Unique IDs after revision selection','1,297','243'],
        ['Eligibility / cutoff exclusions','24 cancelled + 18 tests + 1 future','1 received 1 Feb 2026'],
        ['Orphans quarantined','—','1 return linked to ABSENT'],['Included IDs','1,254 shipped orders','241 return IDs'],
    ],[252,110,149.28],8.8,highlight=[7])
    r.p('All 18 order corrections replace whole rows across both pages. Return R-M1-01-003 revision 2 replaces a €150 refund with €149; the original is not additive. R-CUTOFF on 31 January 2026 is included against its December sale; R-LATE on 1 February is excluded. R-ORPHAN is quarantined: its 60 local-currency refund cannot be translated because the original order and currency are absent. [S02] [S07] [S11]')
    r.p('The 24 missing shipment dates belong to cancelled orders. No eligible required field, effective unit cost, FX month or core market observation is missing. The retained 12 zero-price orders contain 739 units and <b>-€14,565.90 contribution</b>; removing them would overstate economics. No eligible order has multiple distinct return IDs in this file, but the calculation supports additive legitimate returns.')
    r.section('An exact contribution bridge')
    r.table(['2025 shipment cohort','EUR'],[
        ['Gross sales after discounts, before returns','4,464,622.33'],['Refunds known by cutoff','(80,830.57)'],
        ['Net sales','4,383,791.76'],['Gross product cost','(2,265,404.50)'],
        ['Cost recovered on 481 restocked units','18,485.50'],['Net product cost','(2,246,919.00)'],
        ['Nonrefundable fulfillment','(106,862.28)'],['Contribution','2,030,010.48'],
    ],[365,146.28],8.4,highlight=[3,8])
    r.note('Contribution / net sales = 46.31%. Returned units = 1,081; only 481 are restocked. “Booked revenue” here is a shipment-cohort analytical sales measure, not a reconciled general ledger. Cash receipts, settlement FX, receivables, tax, depreciation and corporate overhead are unavailable. Contribution therefore is neither cash flow nor net profit. [S02] [S14]')

    r.new('Spain and Czechia lead the observed economics')
    ranked=sorted(C.values(),key=lambda v:v['contribution_eur'],reverse=True)
    r.bars([x['country'] for x in ranked],[x['contribution_eur'] for x in ranked],height=156,caption='2025 contribution, EUR thousands. Every country has 209 eligible shipped orders; differing units, prices, costs and returns drive the spread.')
    r.table(['Market','Units','Gross €k','Refund €k','Net €k','Contrib. €k','Margin'],[
        [c,f"{v['shipped_units']:,}",k(v['gross_sales_eur']),k(v['refunds_eur']),k(v['net_sales_eur']),k(v['contribution_eur']),pct(v['margin'])] for c,v in C.items()
    ],[47,64,82,75,82,91,70.28],8.6)
    r.table(['Market','Net COGS €k','Fulfill. €k','Returned units','Units returned','Contrib. / unit'],[
        [c,k(v['net_cogs_eur']),k(v['fulfillment_eur']),v['returned_units'],pct(T[c]['return_rate'],2),eur(T[c]['contribution_per_shipped_unit'],2)] for c,v in C.items()
    ],[47,98,83,98,85,100.28],8.3)
    r.p('Spain contributes €421,900.47 and Czechia €397,335.25; together they account for <b>'+pct((C['ESP']['contribution_eur']+C['CZE']['contribution_eur'])/M['totals']['contribution_eur'])+'</b> of the six-market total. Their contribution per shipped unit is €30.29 and €28.93 versus Germany’s €21.59. This is observed synthetic cohort economics, not an estimate of what a hub causes.')
    r.p('Czechia also has the highest physical return rate (2.10%), followed by Spain (1.81%). No defect reasons, service times or satisfaction data are supplied, so the data do not show whether local hubs would reduce returns or generate demand. Use a measured pilot to test those mechanisms.')
    r.note('Source: [S08] [S09] [S07] [S11] [S14], translated using [S03]. Figures rounded to €k here; exact cents and all 72 country-month records are in the workbook, CSV and metrics.json. Annual totals equal summed monthly records, and annual margin is recalculated, not averaged.')

    r.new('Use macro context to size the setting, not demand')
    r.p('The archive contains all 36 requested observations: six countries × three years × two indicators. World Bank population is persons; GDP per capita is current US dollars, neither PPP-adjusted purchasing power nor constant-price growth. All values below are from the same frozen vintage. [S10] [S05]')
    r.table(['Market','Pop. 2022 m','2023 m','2024 m','GDP/pc 2022 $','2023 $','2024 $'],[
        [c]+[f"{W[c,y]['population']/1e6:.3f}" for y in [2022,2023,2024]]+[f"{W[c,y]['gdp_per_capita_usd']:,.0f}" for y in [2022,2023,2024]] for c in C
    ],[47,77,71,71,91,77,77.28],8.3)
    r.table(['Market','Population change 2022–24','Change %','GDP/pc nominal change'],[
        [x['country'],f"{x['population_change_2022_2024']:+,}",f"{x['population_change_pct']:+.2%}",f"{x['gdp_per_capita_change_pct']:+.1%}"] for x in M['market_changes']
    ],[63,178,100,170.28],9)
    r.section('Implications for the choice')
    r.p('Spain and Czechia have the fastest population increases in this six-country window, 2.22% and 2.18%. Poland’s population declines 0.71% while current-dollar GDP per capita rises 32.9%. That combination illustrates why macro variables cannot be collapsed into a product-demand score.')
    r.p('The Netherlands has the highest 2024 GDP per capita ($67,465), while Germany has the largest population (83.52m). Neither fact overturns the client economics: German hub fixed cost and staffing consume much more of the modeled benefit. GDP/person does not measure replacement-assembly demand, serviceable installed base, price tolerance or Meridian’s share.')
    r.section('Vintage and missingness')
    r.p('The source-room provider retrieved these responses on 27 September 2026. Both responses report <b>lastupdated 2026-07-13</b>; historical 2022–2024 values can therefore incorporate later revisions. No population or GDP/person value is null in this archive. The pipeline preserves nulls rather than inventing replacements if a source is missing.')
    r.note('Source URLs, metadata, SHA256 and collection timestamps are in source-register.json/csv and the workbook Sources tab. Full numerical precision is retained in market-context.csv and metrics.json. A supplemental live definition check [L02] was used only for interpretation; no live observation replaced the archive.')

    r.new('Translate at the original sale-month mean')
    fx={(x['currency'],x['month']):x for x in M['fx_monthly']}
    r.table(['2025 month','PLN per EUR','CZK per EUR','Published observations'],[
        [f'{i:02}',f"{fx['PLN',f'2025-{i:02}']['local_per_eur']:.6f}",f"{fx['CZK',f'2025-{i:02}']['local_per_eur']:.6f}",fx['PLN',f'2025-{i:02}']['business_day_observations']] for i in range(1,13)
    ],[87,136,136,152.28],8.8)
    r.p('Means use every available published 2025 business-day observation, without filling weekends or ECB closing days. Each currency has 255 observations across the year. The quote is <b>local units per EUR</b>; EUR is 1. Divide local sales and refunds by the mean. The full mean is used in calculations; six decimals are displayed here. [S03] [S04]')
    r.section('Order-level accounting, then aggregation')
    r.p('Gross local = quantity × local unit price − local discount. Refund local = sum of included return credits for that order. Convert each component at the original shipment month’s mean and round each order component half up to cents. Gross COGS = quantity × effective EUR unit cost; recovered COGS = restocked units × that same cost. Net COGS is the difference. Contribution = gross − refunds − net COGS − fulfillment. [S02] [S14]')
    r.table(['Worked control','Result'],[
        ['POL M4-02-006, revision 2','13,329.36 PLN ÷ 4.172225 = €3,194.78 gross'],
        ['DEU M1-01-003, revised return','€2,550 gross − €149 refund − €1,419 net COGS − €42.60 fulfillment = €939.40 contribution'],
        ['R-CUTOFF linked to M1-12-002','31 Jan 2026 receipt: €54 refund and €29.50 recovery attributed to Dec 2025'],
    ],[188,323.28],8.4)
    r.note('ECB states its euro reference rates are informational, not transaction settlement rates. [L01] This analysis uses them as the client’s historical translation convention. It does not reconcile cash FX or revalue refunds at receipt-date rates.')

    r.new('Six hubs: materially different cost and risk profiles')
    r.table(['Market','Capex €k','FTE','Fixed €k/yr','Saving €/unit','Base payback yr'],[
        [c,k(H[c,'base']['capex_eur'],0),H[c,'base']['fte'],k(H[c,'base']['annual_fixed_eur'],0),f"{H[c,'base']['saving_eur_per_unit']:.2f}",yrs(H[c,'base']['payback_years'])] for c in C
    ],[59,77,44,102,112,117.28],8.8)
    r.table(['Annual increment €k','Low 10%','Base 25%','High 40%','Joint stress'],[
        [c]+[k(H[c,sc]['incremental_contribution_eur']) for sc in ['low','base','high','stress']] for c in C
    ],[119,98,98,98,98.28],9.2)
    r.section('The prescribed model')
    r.p('<b>Normal increment = C × u + U × (1 + u) × s − F.</b> C is 2025 contribution, U shipped units, u uplift, s savings/unit, F recurring annual fixed cost. Savings apply to existing and incremental units. Capex K is a year-zero outlay and is not subtracted from annual contribution. [S06] [S12]')
    r.p('<b>Stress:</b> C* = C − 0.03 × gross sales − FX shock; FX shock = 0.10 × net sales only for PLN/CZK markets. Increment = 1.25 × C* − C + 1.25 × U × s − F. There is no extra COGS recovery for the refund shock. This is the defined conservative comparison against an unchanged normal baseline; defer is zero by policy, not a forecast of an unstressed economy.')
    r.p('Payback = capex / positive annual increment; otherwise null. At base, Spain is €102.7k and Czechia €95.4k; Germany delivers only €10.1k and requires five FTE. Low volume makes Germany and France negative. Stress makes Germany, Poland and Czechia negative.')
    r.note('The annual model assumes full realization from a run-rate year, stable unit economics, no cannibalization, no capacity ceiling, no pair synergy and no ramp-up. Savings, fixed costs and uplifts are synthetic assumptions, not observed hub outcomes. Base payback is an operating-contribution proxy, not a discounted investment return.')

    r.new('Rank every feasible choice, including defer')
    feasible=sorted([x for x in P.values() if x['feasible']],key=lambda x:x['base_rank'])
    r.table(['Choice','K €k','FTE','Low €k','Base €k','High €k','Stress €k','Base yr'],[
        [x['option'],k(x['capex_eur'],0),x['fte'],k(x['low_incremental_eur']),k(x['base_incremental_eur']),k(x['high_incremental_eur']),k(x['stress_incremental_eur']),yrs(x['base_payback_years'])] for x in feasible
    ],[83,50,37,65,73,65,73,65.28],8.0,highlight=[1,4])
    r.p('<b>Four pairs fail hard limits:</b> DEU+FRA costs €490k and nine FTE; DEU+NLD uses eight FTE; DEU+POL uses eight; DEU+ESP uses eight. The latter three fit capex but fail staffing. Their economics are still calculated in the workbook for traceability. No numerical score compensates for a failed constraint.')
    r.p('CZE+ESP ranks first on low, base and high annual contribution. NLD+ESP ranks first under the joint stress. POL+ESP is the base runner-up but is dominated by CZE+ESP on all four scenario increments, capex and FTE. Defer uses no resources and adds no hub contribution; retain it as the fallback if validation fails.')
    r.note('All 15 pairs evaluated; 11 feasible pairs + six feasible singles + defer = 18 feasible alternatives. Pair capex, FTE and increments are additive, without synergy. Table uses €k; exact values, four scenario paybacks and infeasibility reasons are in Portfolios and portfolio-scenarios.csv. [S06] [S12]')

    r.new('Choose the concession explicitly')
    r.table(['Criteria / provenance','CZE + ESP','NLD + ESP','POL + ESP'],[
        ['Base increment, computed','€198,099.31','€166,931.43','€186,328.84'],
        ['Joint stress, computed','€32,179.71','€107,630.13','€29,263.85'],
        ['Capex / FTE, supplied','€225k / 5','€270k / 6','€240k / 6'],
        ['Base / stress payback','1.14 / 6.99 yr','1.62 / 2.51 yr','1.29 / 8.20 yr'],
        ['Decision implication, inferred','Best base; FX exposure','Best stress; more capital','Dominated by CZE+ESP'],
    ],[177,111,112,111.28],8.8)
    r.p('The board supplied resource ceilings and required scenario analysis; it did not supply risk weights, a payback hurdle or a cost of capital. We use <b>base contribution as the primary analyst preference</b>, with capital/FTE and positive payback as secondary comparisons. Downside is disclosed in euros, not compressed into an unsupported score. Service improvements and demand uplift remain unverified.')
    r.section('Observable conditions that change the second hub')
    r.table(['Change, holding other stated inputs fixed','Implication'],[
        ['CZE volume uplift below 17.69%, with NLD still at 25%','NLD overtakes CZE in base annual increment.'],
        ['CZE recurring fixed cost rises by €31,167.88/year','The CZE base advantage over NLD is eliminated.'],
        ['Both defined shocks reach 29.23% of their full sizes','NLD+ESP matches CZE+ESP. This equals 0.877% of gross extra refunds and 2.923% of net FX loss for exposed markets.'],
        ['Board prioritizes worst defined stress outcome','Select NLD+ESP, subject to the same cost/demand gates.'],
        ['No credible positive increment after verified costs and demand','Defer; no obligation to spend the budget.'],
    ],[255,256.28],8.8)
    r.p('These thresholds are scenario arithmetic, not probabilities or statistical confidence bounds. The uplift threshold changes only Czechia; the joint-shock threshold scales both shocks together. Poland does not solve the FX problem: POL+CZE loses €78,569.76/year under the prescribed stress.')
    r.note('Conclusion: reserve CZE+ESP under the stated base-led preference; accept exposed Czechia downside only after the gate. Missing evidence: avoidable-cost scope, causally credible incremental demand, FX settlement exposure and cash timing. Reopen the location choice when measured uplift/costs cross the thresholds or the board selects a downside-first preference. [S06] [S12]')

    r.new('Validate savings before committing to the model')
    r.table(['Market','Assumed saving €/unit','Recorded fulfill. €/unit','Saving / recorded'],[
        [x['country'],f"{x['assumed_saving_eur_per_unit']:.2f}",f"{x['recorded_fulfillment_eur_per_unit']:.2f}",f"{x['ratio_assumed_saving_to_recorded_cost']:.2f}×"] for x in D['savings_cap_sensitivity']
    ],[66,153,162,130.28],9.2)
    r.p('The proposed savings range from 1.38× to 2.43× current recorded fulfillment cost. If they refer only to that expense, the assumption is not supported. If they include other avoided handling, transport or service costs, those costs and the risk of double counting need an itemized bridge. The files provide no such bridge. [S06] [S08] [S09]')
    r.section('Supplementary sensitivity: cap savings at recorded fulfillment')
    r.table(['Portfolio','Capped base €/yr','Capped stress €/yr'],[
        [x['option'],eur(x['base_incremental_eur'],2),eur(x['stress_incremental_eur'],2)] for x in D['savings_cap_portfolios']
    ],[151,180,180.28],9.4,highlight=[1,2])
    r.p('This diagnostic assumes all recorded fulfillment could be eliminated; local variable expense is not separately modeled. It is therefore an upper bound on savings from the recorded cost pool, not a validated forecast. It preserves the required scenarios in parallel and changes only the saving parameter.')
    r.p('<b>Release gate:</b> the CFO and COO must reconcile current avoidable cost, new local variable cost and the proposed saving per unit. Re-run every portfolio using evidenced savings, quoted recurring cost, capacity and a conservative demand estimate. Do not present the €32.2k policy stress surplus as robust once the plausible cost scope is challenged.')
    r.section('Timing and cash are a second unresolved gate')
    r.p('The chosen pair’s base annual increment is €198,099.31 against €225,000 initial capex; subtracting capex from a full base year gives -€26,900.69 as an illustrative bridge, <b>not cash flow</b>. A real ramp, inventory build, deposits, receivables, tax and financing may worsen early funding needs. Obtain a month-by-month funding plan before signing commitments.')
    r.note('The original 1.14-year payback is a simple steady-state quotient. Calendar recovery from commitment cannot be estimated from these files. No guaranteed opening date, supplier quote or inventory capacity is implied.')

    r.new('A staged 90-day plan with explicit release gates')
    r.p('Day 0 means board endorsement of this conditional plan, not an assumed lease start. Owners below are proposed accountable roles. Pilot and procurement costs must fit the reserved envelope and be defined before purchase; no additional budget is invented.')
    r.table(['When / accountable owner','Work and dependencies','Gate / output'],[
        ['Days 1–15\nCFO + Data Lead','Reconcile the ledger to finance; resolve orphan return; confirm sample policy; collect current freight, handling and service costs. Requires operations and finance records.','G1: signed unit-cost/savings bridge, source coverage and month-by-month cash budget. Hold if material cost scope remains unknown.'],
        ['Days 16–30\nCOO + Procurement + HR','Validate Spain first: nonbinding facility/carrier quotes, staffing coverage, capacity and inventory requirements. Assess Czechia FX exposure and Netherlands backup. Depends on G1.','G2: costs and staffing fit €225k / 5 FTE envelope; necessary lease, employment, tax and safety reviews complete before commitments. Rerun ranked scenarios.'],
        ['Days 31–60\nCommercial Director + Operations','Run a limited Spain service pilot and Czechia demand test using approved capacity. Compare with a matched control or phased rollout; track prices, stock availability and channel shifts. Depends on G2 design and instrumentation.','G3: observed contribution bridge; no double-counted transfer from central channel; return and service cohorts mature enough to interpret. Extend test if evidence is weak.'],
        ['Days 61–75\nCFO + COO','Update uplift, net savings, recurring costs, returns, FX exposure and working capital. Compare CZE+ESP, NLD+ESP, Spain-only and defer. Requires pilot data and firm quotes.','G4: board confirms base-led versus downside-led preference. Release Spain €130k / 3 FTE only on supported economics; release CZE €95k / 2 FTE only after its separate gate.'],
        ['Days 76–90\nProgram Lead + Country Ops','Phase launch of approved footprint, train staff, reconcile stock and route eligible orders. Depends on local readiness and G4; do not force opening to meet a calendar target.','G5: weekly KPI dashboard, signed operational acceptance and day-90 continue / revise / pause review. Retain remaining €225k and 2 FTE as uncommitted capacity.'],
    ],[123,221,167.28],8.7)
    r.section('A gate is a choice, not a paperwork milestone')
    r.p('If Czechia evidence weakens below its relative threshold, compare the Netherlands using the same scope and evidence quality. If both fail, retain Spain only or defer. Local compliance, staffing capacity and inventory readiness are operational prerequisites; no jurisdiction-specific legal conclusion is claimed in this report.')
    r.note('Dependencies and numeric release amounts are a proposed execution design. Actual legal reviews, recruiting, contracting and pilot activity have not been performed. The 90-day plan tests the investment case and readiness; it does not promise two fully ramped hubs within 90 days.')

    r.new('Measure economics and service without inventing proof')
    r.table(['KPI / owner','Definition and baseline','Target / review rule'],[
        ['Incremental contribution\nCFO; weekly, monthly close','Net sales − net COGS − fulfillment − new recurring hub costs, compared with an agreed counterfactual. Policy pair base +€198.1k/year.','Re-estimate full-run-rate benefit; base forecast must remain positive. Report capex and cash separately; reconcile within five business days of close.'],
        ['Unit savings\nCOO; weekly','Current avoidable cost minus new local variable cost per shipped unit; volume/mix normalized. Recorded CZE €1.52 and ESP €1.63/unit.','Support each saving with invoices/time records. Targets €2.10 / €3.00 are assumptions until bridged; stop escalation if cost pool cannot support them.'],
        ['Incremental volume\nCommercial; weekly','Pilot versus matched control or phased baseline; adjust for seasonality, price, stockouts and central-channel transfer. Base assumption +25%.','Show uncertainty and sample sizes. If CZE falls below 17.69% while NLD remains credible at 25%, revisit location. No pass based solely on raw growth.'],
        ['Returned / restocked units\nQuality Lead; monthly cohorts','Returned units / shipped units; separate restocked share and credit value. CZE 2.10%, ESP 1.81%; total 481/1,081 restocked.','Do not worsen physical return rate vs matched baseline; label recent cohorts immature. Monitor refund value separately; use the specified +3% gross stress.'],
        ['Service reliability\nCountry Ops; daily','On-time delivery = orders within promised date / eligible delivered orders; median and p95 order-to-delivery time. No supplied baseline.','Proposed pilot target: ≥95% on-time and ≥20% faster median vs matched central service, with no fill-rate decline; validate promise definition at day 15.'],
        ['FX / capital / staffing\nTreasury + CFO; weekly','CZK net exposure after natural offsets and settlement terms; committed capex, cash and actual FTE. No settlement data supplied.','Re-run 10% net-sales FX stress. Never exceed €450k / 7 FTE overall or approved release tranche; no assumed hedge benefit.'],
    ],[120,221,170.28],8.4)
    r.section('Risks, consequences and response')
    r.p('<b>Demand/cannibalization:</b> a faster service promise may shift existing orders rather than add contribution; Commercial owns a controlled comparison. <b>Cost overlap:</b> unsupported saving scope can erase stress headroom; CFO signs the bridge. <b>FX and returns:</b> Czechia is stress-negative; Treasury and Quality monitor exposure and mature cohorts. <b>Inventory and ramp:</b> capital can be tied up before benefits; COO validates stock capacity and CFO gates cash. [S06] [S12]')
    r.note('Targets without a supplied baseline are explicitly proposed management thresholds, not historical facts or industry benchmarks. Pilot results are not statistically decisive until design, sample size, duration and uncertainty support that claim.')

    r.new('Evidence, verification and limits of the conclusion')
    r.table(['Evidence group','Saved files / public link','Use and status'],[
        ['Client transactions','[S08] [S09] orders; [S07] corrections; [S11] returns','Synthetic observations. Full raw bytes and row disposition preserved.'],
        ['Accounting and cost','[S02] dictionary; [S14] unit costs','Client policy and effective-dated synthetic cost.'],
        ['Hub options / policy','[S06] options; [S12] scenarios','Synthetic assumptions, not measured demand or quoted hub costs.'],
        ['World Bank','[S10] population; [S05] GDP/person','Official archived observations, 2022–2024. Provider retrieval 27 Sep 2026; lastupdated 13 Jul 2026.'],
        ['ECB','[S04] ZIP and [S03] extracted CSV','Official archive; original provider retrieval 27 Sep 2026. CSV hash and ZIP bytes agree.'],
        ['Provenance / live checks','[S13] supplied register; [L01] ECB; [L02] World Bank','Live checks only establish definitions. Shell TLS retrieval failed; saved web-tool extracts identify that limitation.'],
    ],[104,216,191.28],8.3)
    r.p('The consolidated source register records original URLs, analyst collection URLs and UTC times, byte hashes, units, periods, synthetic/public status and revision vintage. The local source-room URL is a disposable endpoint; saved bytes are the reproducibility anchor. Original official URLs remain linked for attribution, not for replacing the frozen calculation inputs.')
    r.section('Verification delivered with the files')
    r.p('The independent check script rebuilds the accounting from raw files using exact rational FX arithmetic and integer cents, compares every monthly and country field, checks scenario constraints and positive-only payback, and verifies archived hashes. Workbook checks inspect formulas, cached numeric results and chart structure. Both PDFs are rasterized for page review; the verification folder records actual results and limitations.')
    r.section('Material gaps and reopening evidence')
    r.p('Accounting totals are supported within the source-room scope; a real general-ledger/cash reconciliation is absent. The investment estimate lacks observed hub demand, service times, avoided-cost detail, firm fixed-cost quotes, staffing capacity, inventory/working capital, ramp, tax, financing and discount rates. Resolve those inputs at the appropriate gate; none is silently filled with a macro proxy.')
    r.p('Reopen the historical calculation if corrected shipments or returns known by the cutoff appear. Reopen the hub estimate when costs, uplift or exposure change. Reopen the action preference if the board prioritizes stress preservation over base contribution. The preferred pair is a conditional planning recommendation, not a statistically proven optimum.')
    r.note('Reproduction: README.md → scripts/analyze.py → scripts/decision.py → scripts/build_workbook.py → scripts/build_documents.py → scripts/verify.py. All source inputs are saved. OpenSocrates grounding: trade-off-analysis@3. Native application evidence remains unverified; that instrumentation limit is separate from artifact completion.')
    r.save('report-layout.json')
    return r.page

def make_deck():
    r=PDF(OUT/'Meridian_board_presentation.pdf',960,540,deck=True)
    r.new('Reserve €225k for Czechia + Spain; start with Spain')
    r.tiles([('BASE ANNUAL INCREMENT','€198.1k','after recurring fixed cost'),('RESOURCE COMMITMENT','5 FTE','two hubs; capex ceiling €450k'),('BASE SIMPLE PAYBACK','1.14 yr','run-rate quotient, not cash recovery')],height=83)
    r.p('<b>Conditional recommendation:</b> reserve the envelope, release Spain first, and gate Czechia on demand, savings and FX evidence.',18,space=14)
    r.p('The pair leads low, base and high scenarios. Netherlands + Spain is stronger in stress. No uplift probability or causal hub effect has been established.',16,space=14)
    r.note('Critical finding: all unit-saving assumptions exceed recorded fulfillment cost per unit. This must be resolved before full commitment. Sources: [S06] [S12]; calculations in the companion workbook.')

    r.new('A reconciled €2.03m contribution base supports the model')
    r.tiles([('2025 SHIPPED ORDERS','1,254','77,436 shipped units'),('NET SALES','€4.384m','€80,830.57 refunds at cutoff'),('CONTRIBUTION MARGIN','46.31%','contribution / net sales')],83)
    r.table(['Orders: 1,328 raw rows → 1,254 included','Returns: 264 rows → 241 included IDs'],[
        ['13 identical duplicates; 18 superseded revisions','20 identical duplicates; one superseded revision'],
        ['24 cancellations; 18 tests; one future order excluded','31 Jan included; 1 Feb excluded; one orphan quarantined'],
        ['12 free orders / 739 units retained','Only 481 of 1,081 returned units recover COGS'],
    ],[442,442],12)
    r.note('Shipment-cohort revenue is not cash. Contribution subtracts net COGS and nonrefundable fulfillment, before corporate overhead, tax, finance and depreciation. No live client account or customer interviews. [S02] [S07] [S08] [S09] [S11] [S14]')

    r.new('Spain and Czechia lead contribution, with higher return rates')
    r.table(['2025 market','Units shipped','Contribution €k','Margin','Returned units %'],[
        [c,f"{v['shipped_units']:,}",k(v['contribution_eur']),pct(v['margin']),pct(T[c]['return_rate'],2)] for c,v in C.items()
    ],[149,172,196,166,201],12,highlight=[5,6])
    r.p('All six countries have 209 eligible orders. Spain and Czechia generate 40.4% of total contribution; this reflects cohort economics, not proven hub demand.',16)
    r.note('Sources: reconciled synthetic shipments and returns [S07] [S08] [S09] [S11], effective EUR unit costs [S14], original sale-month ECB means [S03]. Service times and return reasons are absent.')

    r.new('Macro context informs the setting; it does not prove demand')
    r.table(['Market','2024 population m','2022–24 pop. change','2024 GDP/person US$'],[
        [x['country'],f"{W[x['country'],2024]['population']/1e6:.2f}",f"{x['population_change_pct']:+.2%}",f"{W[x['country'],2024]['gdp_per_capita_usd']:,.0f}"] for x in M['market_changes']
    ],[115,223,270,276],12)
    r.p('Spain and Czechia grew fastest in population; the Netherlands has the highest GDP/person. Germany’s scale alone does not offset its hub cost and staffing burden.',16)
    r.note('Archived World Bank 2022–2024 series [S10] [S05]; lastupdated 2026-07-13. GDP/person is current USD, not PPP or real income growth. No core observations are missing. Full three-year values in report and workbook.')

    r.new('Czechia + Spain wins base; Netherlands + Spain wins stress')
    choices=['CZE+ESP','POL+ESP','NLD+ESP','ESP','DEFER']
    r.table(['Choice','Capex €k / FTE','Low €k','Base €k','High €k','Stress €k'],[
        [p,f"{k(P[p]['capex_eur'],0)} / {P[p]['fte']}"]+[k(P[p][sc+'_incremental_eur']) for sc in ['low','base','high','stress']] for p in choices
    ],[163,173,137,137,137,137],12,highlight=[1,3])
    r.p('All 22 choices evaluated; 18 feasible. Germany + France fails capex and FTE. Germany paired with the Netherlands, Poland or Spain fails the seven-FTE ceiling.',15)
    r.note('Annual increment = C×u + U×(1+u)×s − fixed cost. Uplifts: 10% / 25% / 40%. Stress: base volume, 3% of gross extra refunds, plus 10% of net FX loss in PLN/CZK; unchanged normal baseline. Capex is separate. [S06] [S12]')

    r.new('Base and stress point to different second hubs')
    c=r.c; left=215; right=850; top=r.y-26; scale=(right-left)/220
    for tick in [0,50,100,150,200]:
        x=left+tick*scale;c.setStrokeColor(LINE);c.line(x,top-228,x,top+8)
        c.setFillColor(GRAY);c.setFont(FONT,11);c.drawCentredString(x,top-247,str(tick))
    for i,name in enumerate(['CZE+ESP','NLD+ESP','POL+ESP','ESP']):
        y=top-i*57
        c.setFillColor(NAVY);c.setFont(BOLD,13);c.drawRightString(left-18,y-8,name)
        for j,(sc,color) in enumerate([('base',TEAL),('stress',ORANGE)]):
            value=P[name][sc+'_incremental_eur']/1000
            c.setFillColor(color);c.rect(left,y-j*19,value*scale,13,stroke=0,fill=1)
            c.setFillColor(NAVY);c.setFont(FONT,11);c.drawString(left+value*scale+7,y-j*19+2,f'{value:.1f}')
    c.setFillColor(TEAL);c.rect(640,top+28,14,10,fill=1,stroke=0);c.setFillColor(NAVY);c.setFont(FONT,11);c.drawString(661,top+28,'Base')
    c.setFillColor(ORANGE);c.rect(730,top+28,14,10,fill=1,stroke=0);c.setFillColor(NAVY);c.drawString(751,top+28,'Joint stress')
    r.y=top-274
    r.note('EUR thousands of annual incremental contribution, after recurring fixed cost; capital and staffing constraints applied. NLD+ESP buys €75.5k/year more stress contribution for €31.2k/year less base benefit, €45k more capex and one additional FTE. Source: [S06] [S12].')

    r.new('The savings assumption is the first investment gate')
    r.table(['Market','Saving assumed €/unit','Recorded fulfill. €/unit','Ratio'],[
        [x['country'],f"{x['assumed_saving_eur_per_unit']:.2f}",f"{x['recorded_fulfillment_eur_per_unit']:.2f}",f"{x['ratio_assumed_saving_to_recorded_cost']:.2f}×"] for x in D['savings_cap_sensitivity']
    ],[130,266,290,198],12)
    r.p('<b>Cap savings at recorded fulfillment:</b> CZE+ESP base falls to €164.3k and stress to <b>-€1.6k</b>. NLD+ESP remains +€54.2k in stress.',17)
    r.note('Diagnostic sensitivity, not a replacement client forecast. Even full elimination of recorded fulfillment may be optimistic. CFO + COO must evidence avoided costs and new local variable costs; unrecorded savings cannot be presumed. [S06] [S08] [S09]')

    r.new('The second hub depends on the board’s downside preference')
    r.tiles([('CZE+ESP BASE ADVANTAGE','€31.2k/yr','versus NLD+ESP'),('NLD+ESP STRESS ADVANTAGE','€75.5k/yr','but €45k more capex, +1 FTE'),('CZE UPLIFT SWITCH','17.69%','if NLD remains at 25%')],83)
    r.p('Base-led preference: choose CZE+ESP. Downside-led preference: choose NLD+ESP. Poland + Spain is the base runner-up but is worse than CZE+ESP on all four modeled scenarios, capex and FTE.',17)
    r.p('The ranking also flips at €31,167.88 additional annual Czechia fixed cost, or at 29.23% of the full joint stress severity. These are deterministic thresholds, not probabilities.',16)
    r.note('Czechia alone: -€37,826.95/year stress; Spain offsets this in the policy pair. Pair stress payback is 6.99 years. The analyst preference maximizes base increment subject to hard limits; no weighted scoring or risk tolerance is attributed to the board. [S06] [S12]')

    r.new('Ninety days to evidence, gated commitments and readiness')
    r.table(['When','Accountable role','Deliverable / dependency','Release gate'],[
        ['1–15','CFO + Data Lead','Reconcile costs, cash and source gaps','Signed cost-savings bridge; no unresolved material scope'],
        ['16–30','COO + Procurement + HR','Quotes, staffing, capacity, inventory; after G1','Revised economics and operational prerequisites'],
        ['31–60','Commercial + Operations','Spain pilot / Czechia demand test; after G2','Adjusted uplift and contribution; no channel double count'],
        ['61–75','CFO + COO + Board','Compare CZE/NLD/Spain-only/defer','Spain €130k / 3 FTE; Czechia €95k / 2 FTE separately gated'],
        ['76–90','Program Lead + Country Ops','Phase approved scope; after release','Acceptance and day-90 continue / revise / pause'],
    ],[85,189,315,295],11.4)
    r.note('Proposed owners and schedule; no actual procurement or implementation has occurred. Firm local reviews and readiness are prerequisites. Do not promise full ramp within 90 days; do not spend unused budget merely because it is available.')

    r.new('Track the mechanism, then close the financial loop')
    r.table(['Measure / owner','Baseline or modeled target','Review / decision rule'],[
        ['Contribution / CFO','Pair +€198.1k/year base model','Weekly operating bridge; monthly finance close; cash separate'],
        ['Savings / COO','CZE €2.10; ESP €3.00/unit assumed','Invoice-backed cost bridge; reject unsupported double count'],
        ['Volume / Commercial','+25% assumed, not measured','Control or phased comparison; adjust mix, availability and cannibalization'],
        ['Returns / Quality','CZE 2.10%; ESP 1.81% physical','Mature cohorts; track restocking and refund values separately'],
        ['Service / Country Ops','Baseline absent','Proposed ≥95% on-time, ≥20% faster median, no fill-rate decline'],
        ['FX / Treasury; capex / CFO','CZE exposed; €225k / 5 FTE reserved','Re-run 10% net FX stress; gate cash and hiring'],
    ],[210,266,408],11.5)
    r.note('Management targets are proposed, not source facts or industry benchmarks. Sample size, uncertainty and cohort maturity determine what a pilot can establish. Detailed definitions, cadence and owners are in the executive report.')

    r.new('Approve a conditional envelope, with a credible fallback')
    r.p('<b>Decision proposed:</b> reserve €225,000 and five FTE for Czechia + Spain; Spain first. Make the second-hub decision after cost, demand, FX and cash gates. Retain Netherlands + Spain as the downside alternative and defer as the fallback.',20,space=19)
    r.p('<b>What is supported:</b> the reconciled 2025 base, archived FX and macro comparisons, and exact policy scenario arithmetic. <b>What is unverified:</b> causal demand uplift, service gains, avoidable-cost scope, staffing/capacity feasibility and calendar cash recovery.',16,space=16)
    r.p('Companion evidence: executive report; formula-linked XLSX; metrics.json; order and return audits; source register and saved bytes; reproduction scripts and verification results.',15,space=15)
    r.note('No customer interviews or live client access. Archived official data remains the core calculation source; public live checks only verify definitions. All scenario assumptions are synthetic. Source attribution: [S02] [S03] [S05] [S06] [S07] [S08] [S09] [S10] [S11] [S12] [S14]. OpenSocrates grounding: trade-off-analysis@3.')
    r.save('deck-layout.json')
    return r.page

if __name__=='__main__':
    print('Report pages:',make_report())
    print('Board slides:',make_deck())
