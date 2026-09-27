"""Build a filterable, formula-backed workbook with cached, independently checkable outputs."""
from pathlib import Path
import csv, json
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
M=json.loads((OUT/'metrics.json').read_text())
REG=json.loads((ROOT/'evidence/source_register.json').read_text())
def rows(name):
    with (OUT/'data'/name).open() as f: return list(csv.DictReader(f))

wb=xlsxwriter.Workbook(OUT/'Meridian_analytical_workbook.xlsx')
wb.set_properties({'title':'Meridian Parts | European service-hub decision','subject':'2025 shipment cohort; return cutoff 31 January 2026','author':'Meridian strategy analysis','comments':'Synthetic client inputs; archived official context. See Read Me.'})
wb.set_calc_mode('auto')
navy='#122C43'; teal='#008577'; gold='#D49A25'; red='#B34A48'; light='#EDF4F6'
fmt={
    'title':wb.add_format({'bold':True,'font_size':20,'font_color':navy}),
    'sub':wb.add_format({'font_size':10,'font_color':'#536675','text_wrap':True,'valign':'top'}),
    'head':wb.add_format({'bold':True,'font_color':'white','bg_color':navy,'text_wrap':True,'valign':'vcenter','border':0}),
    'text':wb.add_format({'font_size':10,'valign':'top'}),
    'wrap':wb.add_format({'font_size':10,'text_wrap':True,'valign':'top'}),
    'money':wb.add_format({'num_format':'#,##0.00;[Red](#,##0.00);–','font_size':10}),
    'int':wb.add_format({'num_format':'#,##0;[Red](#,##0);–','font_size':10}),
    'rate':wb.add_format({'num_format':'0.000000','font_size':10}),
    'pct':wb.add_format({'num_format':'0.00%;[Red](0.00%);–','font_size':10}),
    'years':wb.add_format({'num_format':'0.00','font_size':10}),
    'input':wb.add_format({'num_format':'#,##0.00','bg_color':'#FFF2CF','font_color':'#245A9E','font_size':10}),
    'inputpct':wb.add_format({'num_format':'0.0%','bg_color':'#FFF2CF','font_color':'#245A9E','font_size':10}),
}

def sheet(name,title,subtitle,headers,widths=None):
    s=wb.add_worksheet(name); s.hide_gridlines(2)
    s.merge_range(0,0,0,max(3,len(headers)-1),title,fmt['title']);s.set_row(0,30)
    s.merge_range(1,0,2,max(3,len(headers)-1),subtitle,fmt['sub']);s.set_row(1,23);s.set_row(2,20)
    if headers:
        for j,h in enumerate(headers): s.write(4,j,h,fmt['head'])
        s.set_row(4,34)
    s.freeze_panes(5,1)
    s.set_landscape();s.set_paper(9);s.fit_to_pages(1,0);s.repeat_rows(0,4)
    s.set_margins(.3,.3,.4,.4);s.set_header('&LMeridian Parts | Synthetic case&R&[Tab]');s.set_footer('&L2025 cohort; returns to 2026-01-31&RPage &P of &N')
    s.set_column(0,max(3,len(headers)-1),17)
    if widths:
        for j,w in enumerate(widths):s.set_column(j,j,w)
    return s

def write(s,r,c,v,kind='text'):
    if v is None:s.write_blank(r,c,None,fmt[kind])
    elif isinstance(v,(int,float)):s.write_number(r,c,v,fmt[kind])
    else:s.write(r,c,v,fmt[kind])

def finish(s,n,cols):
    s.autofilter(4,0,4+n,cols-1)
    s.print_area(0,0,4+n,cols-1)

read=sheet('Read Me','Meridian Parts | model guide','Frozen-source analysis • amounts in EUR unless marked • all client transactions and scenarios are synthetic', ['Topic','How to use / interpretation'],[27,118])
read_rows=[
('Decision','Conditionally reserve EUR225,000 and five FTE for Spain and Czechia. Spain first. All economics are full annual run-rates; release capital only at the validation gates.'),
('Navigation','Decision: charts and board snapshot. Inputs: yellow cells drive hub scenarios and portfolios. Monthly and Countries: formulas sum Order Ledger. Sources / Quality / raw resolution sheets preserve the audit trail.'),
('Editable assumptions','Inputs yellow cells may be edited. Scenario, portfolio, sensitivity and chart formulas recalculate in Excel/compatible software. Baseline order ledger is a frozen analytical output: rebuild with scripts to change transaction, cutoff, cost or historical FX rules.'),
('Scope','Shipments from 2025-01-01 to 2025-12-31. Highest numeric revision per ID across every extract and correction, then filter. Returns received on or before 2026-01-31 only, linked to eligible orders.'),
('Money','Gross = units × local unit price − local discount. Gross and summed refunds are divided by original shipment-month local units/EUR. Each order component uses decimal half-up cent rounding. Net sales = gross − refunds; net COGS = original COGS − cost of restocked units only.'),
('Contribution','Contribution = net sales − net COGS − actual nonrefundable fulfillment. Margin = contribution / net sales, blank if zero denominator. Counts retain valid zero-price orders. Returns are assigned to original shipment month, not receipt month.'),
('Accounting boundary','Booked-revenue proxy is shipped net sales under this client convention. Cash cannot be reconstructed without payment/collection, transaction FX, refund settlement and working-capital data. Contribution is before corporate overhead and hub investment; it is not free cash flow.'),
('Scenario formula','Low/base/high annual increment = C×u + U×(1+u)×s − F. Stress = (C−0.03G−0.10N for PLN/CZK)×1.25 − C + U×1.25×s − F. The 0.10N term is zero for EUR countries. Capex is year zero; annual fixed cost is recurring.'),
('Payback','Capex / positive annual increment. Blank means no positive payback; zero is not substituted. Simple undiscounted payback assumes immediate steady state and excludes taxes, financing, working capital and ramp-up.'),
('Constraints','At most two hubs, capex ≤ EUR450,000 and FTE ≤ 7. All 22 combinations (six singles, fifteen pairs and defer) are present; four pairs are infeasible. Portfolio rank reflects the saved base assumptions and is not dynamic after edits; sort Base EUR after changes.'),
('Sources and vintage','Client data: synthetic. World Bank and ECB: official public archives downloaded from the frozen room, not live research. WB lastupdated 2026-07-13; archive retrieval 2026-09-27. Sources sheet separates original URLs, archive time and analyst collection time; full hashes also in evidence/source_register.csv.'),
('Market context','Population is persons; GDP per capita is current US$, not PPP or real income. No missing observations among 36 requested values. Population/GDP per capita are context, not proof of product demand.'),
('Precision','Full means used for FX, displayed at six decimals. Spreadsheet values/caches match metrics.json. Scenario outputs rounded to cents and pairs sum those amounts. Summary documents show rounded thousands where stated; detailed sheets retain cents.'),
('Material assumption risk','All six supplied savings/unit exceed recorded fulfillment/unit. Validate which additional central costs are avoidable. Treat supplied fixed costs as complete recurring hub costs only for policy calculations; payroll, rent and coverage are not confirmed. No guessed salaries added.'),
('Verification','See verification/verification_report.json and VERIFICATION.md for actual checks and rendering review. No desktop Excel/LibreOffice engine is installed: cached values and formula structure are checked, with native recalculation an explicit limitation.'),
('Reproduce','From project root run analysis/reproduce.sh with the documented Python environment. No network required once evidence/raw is saved. See README.md. TASK.md and TOOLING.md are preserved.')]
for i,(a,b) in enumerate(read_rows,5):read.write(i,0,a,fmt['head']);read.write(i,1,b,fmt['wrap']);read.set_row(i,60 if len(b)>300 else 47)
finish(read,len(read_rows),2)

dash=sheet('Decision','Conditional choice: Spain + Czechia','Full steady-state annual increment after recurring fixed costs. Capital release is gated; Spain first. Chart values in EUR.', ['Portfolio','Low EUR','Base EUR','High EUR','Stress EUR','Capex EUR','FTE'],[24,18,18,18,18,18,10])
inputs=sheet('Inputs','Planning assumptions | editable yellow cells','Synthetic board policy. Savings and annual fixed-cost coverage require validation; no synergy between countries.', ['Country','Capex EUR','FTE','Annual fixed EUR','Saving EUR/unit'],[18,19,12,22,23])
options=list(csv.DictReader((ROOT/'evidence/raw/hub-options.csv').open()))
inputrow={}
for i,o in enumerate(options,5):
    inputrow[o['country']]=i+1
    inputs.write(i,0,o['country'],fmt['text'])
    for j,k in enumerate(['capex_eur','fte','annual_fixed_eur','saving_eur_per_unit'],1):inputs.write_number(i,j,float(o[k]),fmt['input'])
    inputs.data_validation(i,1,i,4,{'validate':'decimal','criteria':'>=','value':0})
inputs.write_row(13,0,['Global policy','Value'],fmt['head'])
globals_=[('Low uplift',.10),('Base uplift',.25),('High uplift',.40),('Refund shock / gross',.03),('FX shock / net',.10),('Capex ceiling',450000),('FTE ceiling',7),('Hub ceiling',2)]
for i,(name,v) in enumerate(globals_,14):inputs.write(i,0,name,fmt['text']);inputs.write_number(i,1,v,fmt['inputpct'] if i<19 else fmt['input'])
inputs.set_column(0,0,27)
inputs.merge_range('A25:E28','Yellow cells are assumptions, not observed facts. Staff counts are resource ceilings; detailed rosters and salary/lease coverage are not supplied. The model uses full annual fixed cost from day one and does not price ramp-up.',fmt['wrap'])

# Frozen order values; summaries and downstream decisions use formulas with caches.
ledger=rows('order_ledger.csv'); lf=list(ledger[0]); lc={k:i for i,k in enumerate(lf)}
s=sheet('Order Ledger','Audited eligible order ledger','One selected, eligible order per row. EUR components rounded half up before aggregation. Source line decisions are in Order Resolution.',lf,[18 if k not in ['return_ids','cost_valid_from'] else 24 for k in lf])
ints={'revision','shipped_orders','shipped_units','returned_units','restocked_units','return_records'}
numeric=ints|{k for k in lf if k.endswith('_eur') or k.endswith('_local')}|{'local_per_eur','margin'}
for i,r in enumerate(ledger,5):
    for j,k in enumerate(lf):
        v=float(r[k]) if k in numeric and r[k]!='' else (None if r[k]=='' else r[k])
        kind='pct' if k=='margin' else 'rate' if k=='local_per_eur' else 'int' if k in ints else 'money' if k in numeric else 'text'
        write(s,i,j,v,kind)
finish(s,len(ledger),len(lf))

summary_fields=['country','shipped_orders','shipped_units','gross_sales_eur','refunds_eur','net_sales_eur','net_cogs_eur','fulfillment_eur','contribution_eur','returned_units','margin','gross_cogs_eur','recovered_cogs_eur','restocked_units','returned_unit_rate']
cr={}
for name,records,fields in [('Monthly',M['monthly'],['country','month']+summary_fields[1:]),('Countries',M['countries'],summary_fields)]:
    s=sheet(name,name+' | reconciled 2025 cohort','EUR, units and orders. Refunds known through 2026-01-31 attributed to original shipment month. Blank margin means zero net sales.',fields)
    cmap={f:i for i,f in enumerate(fields)}
    for i,r in enumerate(records,5):
        er=i+1
        if name=='Countries':cr[r['country']]=er
        for j,k in enumerate(fields):
            if k in ['country','month']:write(s,i,j,r[k]);continue
            kind='pct' if k in ['margin','returned_unit_rate'] else 'money' if k.endswith('_eur') else 'int'
            if k=='margin':formula=f'=IF({xl_col_to_name(cmap["net_sales_eur"])}{er}=0,"",{xl_col_to_name(cmap["contribution_eur"])}{er}/{xl_col_to_name(cmap["net_sales_eur"])}{er})'
            elif k=='returned_unit_rate':formula=f'=IF({xl_col_to_name(cmap["shipped_units"])}{er}=0,"",{xl_col_to_name(cmap["returned_units"])}{er}/{xl_col_to_name(cmap["shipped_units"])}{er})'
            else:
                end=5+len(ledger); col=xl_col_to_name(lc[k]); cc=xl_col_to_name(lc['country']); mc=xl_col_to_name(lc['month'])
                formula=f'=SUMIFS(\'Order Ledger\'!{col}$6:{col}${end},\'Order Ledger\'!{cc}$6:{cc}${end},A{er}'
                if name=='Monthly':formula+=f',\'Order Ledger\'!{mc}$6:{mc}${end},B{er}'
                formula+=')'
            s.write_formula(i,j,formula,fmt[kind],r[k] if r[k] is not None else '')
    finish(s,len(records),len(fields))
    s.conditional_format(5,cmap['contribution_eur'],4+len(records),cmap['contribution_eur'],{'type':'data_bar','bar_color':teal})

daily=rows('fx_daily_2025.csv');s=sheet('FX Daily','ECB daily observations | 2025','Published observations only. Quote is local currency units per EUR. No forward-filling weekends/holidays.', ['Date','Currency','Local per EUR'],[18,15,22])
for i,r in enumerate(daily,5):s.write_row(i,0,[r['date'],r['currency'],float(r['local_per_eur'])],fmt['rate'])
finish(s,len(daily),3)
s=sheet('FX Monthly','ECB monthly means | 2025','Full precision used in order calculation; displayed six decimals. EUR = 1. Mean is not inverted; divide local sales/refunds by this quote.', ['Currency','Month','Local per EUR','Observations','First date','Last date'],[15,15,23,18,18,18])
for i,r in enumerate(M['fx_monthly'],5):
    s.write(i,0,r['currency']);s.write(i,1,r['month']);end=5+len(daily);er=i+1
    s.write_formula(i,2,f'=AVERAGEIFS(\'FX Daily\'!C$6:C${end},\'FX Daily\'!B$6:B${end},A{er},\'FX Daily\'!A$6:A${end},B{er}&"*")',fmt['rate'],r['local_per_eur'])
    for j,k in enumerate(['observations','first_date','last_date'],3):write(s,i,j,r[k],'int' if j==3 else 'text')
finish(s,24,6)

s=sheet('Market Context','Market context | official archived observations','Population: persons. GDP per capita: current US$, not PPP/real income or a product-demand forecast. WB lastupdated 2026-07-13; archive 2026-09-27.', ['Country','Year','Population (persons)','GDP/person current USD','Population change 2022–24','Nominal GDP/person change 2022–24'],[15,12,24,26,29,34])
mc={r['country']:r for r in M['market_changes']}
for i,r in enumerate(M['market_context'],5):
    for j,k in enumerate(['country','year','population','gdp_per_capita_usd']):write(s,i,j,r[k],'int' if j in [1,2] else 'money' if j==3 else 'text')
    if r['year']==2024:
        er=i+1;s.write_formula(i,4,f'=C{er}/C{er-2}-1',fmt['pct'],mc[r['country']]['population_change_pct'])
        s.write_formula(i,5,f'=D{er}/D{er-2}-1',fmt['pct'],mc[r['country']]['nominal_usd_gdp_per_capita_change_pct'])
finish(s,18,6)

headers=['Country','Scenario','Uplift','Baseline C EUR','Baseline units','Gross sales EUR','Net sales EUR','Saving EUR/unit','Annual fixed EUR','Volume contribution EUR','Savings EUR','Stress penalty EUR','Annual increment EUR','Year-zero capex EUR','FTE','Payback years','First full year less capex EUR']
sc=sheet('Hub Scenarios','Hub scenarios | annual increments','Formula model; no capex subtraction from annual increment. Stress uses base uplift and a conservative refund/FX haircut relative to unchanged normal baseline.',headers)
sr={}
for i,r in enumerate(M['hub_scenarios'],5):
    c=r['country'];er=i+1;ir=inputrow[c];br=cr[c];scenario=r['scenario'];sr[c,scenario]=er
    sc.write(i,0,c);sc.write(i,1,scenario)
    urow={'low':15,'base':16,'high':17,'stress':16}[scenario]
    formula_values={2:(f'=Inputs!B{urow}',r['volume_uplift']),3:(f'=Countries!I{br}',r['baseline_contribution_eur']),4:(f'=Countries!C{br}',r['baseline_units']),
        5:(f'=Countries!D{br}',next(b['gross_sales_eur'] for b in M['countries'] if b['country']==c)),
        6:(f'=Countries!F{br}',next(b['net_sales_eur'] for b in M['countries'] if b['country']==c)),
        7:(f'=Inputs!E{ir}',r['saving_eur_per_unit']),8:(f'=Inputs!D{ir}',r['annual_fixed_eur']),
        9:(f'=D{er}*C{er}',r['baseline_contribution_eur']*r['volume_uplift']),
        10:(f'=E{er}*(1+C{er})*H{er}',r['baseline_units']*(1+r['volume_uplift'])*r['saving_eur_per_unit']),
        11:(f'=IF(B{er}="stress",(Inputs!B18*F{er}+IF(OR(A{er}="POL",A{er}="CZE"),Inputs!B19*G{er},0))*(1+C{er}),0)',(1+r['volume_uplift'])*(.03*next(b['gross_sales_eur'] for b in M['countries'] if b['country']==c)+(.10*next(b['net_sales_eur'] for b in M['countries'] if b['country']==c) if c in ['POL','CZE'] else 0)) if scenario=='stress' else 0),
        12:(f'=ROUND(J{er}+K{er}-I{er}-L{er},2)',r['incremental_contribution_eur']),
        13:(f'=Inputs!B{ir}',r['capex_eur']),14:(f'=Inputs!C{ir}',r['fte']),
        15:(f'=IF(M{er}>0,N{er}/M{er},"")',r['payback_years']),16:(f'=M{er}-N{er}',r['first_full_year_less_capex_eur'])}
    for j,(f,v) in formula_values.items():sc.write_formula(i,j,f,fmt['pct' if j==2 else 'int' if j in [4,14] else 'years' if j==15 else 'money'],v if v is not None else '')
finish(sc,24,len(headers));sc.conditional_format('M6:M29',{'type':'3_color_scale'})

ps=sheet('Portfolios','All portfolios | rank by saved base case','Six singles + fifteen pairs + defer. Feasibility recalculates against Inputs. Saved rank is a snapshot: sort Base EUR after edits. No pair synergy.', ['Option','Capex EUR','FTE','Hub count','Feasible','Saved rank','Low EUR','Base EUR','High EUR','Stress EUR','Low payback','Base payback','High payback','Stress payback','Base first year less capex'],[22,19,10,12,14,14,19,19,19,19,17,17,17,17,27])
pr={}
for i,p in enumerate(M['portfolio_scenarios'],5):
    er=i+1;pr[p['option']]=er;cc=p['countries'];ps.write(i,0,p['option']);ps.write(i,3,len(cc),fmt['int']);write(ps,i,5,p['base_rank'],'int')
    for j,col,key in [(1,'B','capex_eur'),(2,'C','fte')]:ps.write_formula(i,j,'='+'+'.join(f'Inputs!{col}{inputrow[c]}' for c in cc) if cc else '=0',fmt['money' if j==1 else 'int'],p[key])
    ps.write_formula(i,4,f'=AND(B{er}<=Inputs!B20,C{er}<=Inputs!B21,D{er}<=Inputs!B22)',fmt['text'],p['feasible'])
    for j,scenario in enumerate(['low','base','high','stress'],6):
        f='='+'+'.join(f"'Hub Scenarios'!M{sr[c,scenario]}" for c in cc) if cc else '=0'
        ps.write_formula(i,j,f,fmt['money'],p[scenario+'_eur'])
        col=xl_col_to_name(j);ps.write_formula(i,j+4,f'=IF({col}{er}>0,B{er}/{col}{er},"")',fmt['years'],p[scenario+'_payback_years'] if p[scenario+'_payback_years'] is not None else '')
    ps.write_formula(i,14,f'=H{er}-B{er}',fmt['money'],p['base_first_full_year_less_capex_eur'])
finish(ps,len(M['portfolio_scenarios']),15)
ps.conditional_format(5,4,26,4,{'type':'cell','criteria':'==','value':False,'format':wb.add_format({'bg_color':'#F9DDDB'})})

choices=['CZE+ESP','POL+ESP','NLD+ESP','ESP','DEFER'];pm={p['option']:p for p in M['portfolio_scenarios']}
for i,label in enumerate(choices,5):
    dash.write(i,0,label);p=pm[label];r=pr[label]
    for j,col,key in [(1,'G','low_eur'),(2,'H','base_eur'),(3,'I','high_eur'),(4,'J','stress_eur'),(5,'B','capex_eur'),(6,'C','fte')]:dash.write_formula(i,j,f'=Portfolios!{col}{r}',fmt['int' if j==6 else 'money'],p[key])
chart=wb.add_chart({'type':'column'})
for col,label,color in [(1,'Low',gold),(2,'Base',teal),(4,'Stress',red)]:chart.add_series({'name':label,'categories':['Decision',5,0,9,0],'values':['Decision',5,col,9,col],'fill':{'color':color},'border':{'none':True}})
chart.set_title({'name':'Return / FX stress changes the preferred risk profile'});chart.set_y_axis({'name':'Incremental contribution EUR / year','num_format':'€#,##0','major_gridlines':{'visible':True}});chart.set_legend({'position':'bottom'});chart.set_style(10);chart.set_size({'width':860,'height':390})
dash.insert_chart('A13',chart)
dash.merge_range('A34:G37','Decision gates: validate avoidable savings and fully loaded recurring cost; run a measured Spain pilot; release Czechia only with an acceptable FX/returns case and demonstrated demand. Netherlands + Spain gives EUR107,630.13 in stress versus EUR32,179.71 for Czechia + Spain, at EUR45,000 more capex and one extra FTE.',fmt['wrap'])
dash.print_area('A1:G37')

s=sheet('Decision Charts','Economics before market size','These are synthetic client economics. Savings assumptions exceed the fulfillment costs observed in all six markets.', ['Country','Contribution EUR','Recorded fulfillment EUR/unit','Assumed saving EUR/unit'],[18,25,34,31])
for i,b in enumerate(M['countries'],5):
    c=b['country'];er=cr[c];ir=inputrow[c];s.write(i,0,c)
    s.write_formula(i,1,f'=Countries!I{er}',fmt['money'],b['contribution_eur'])
    s.write_formula(i,2,f'=Countries!H{er}/Countries!C{er}',fmt['money'],b['fulfillment_eur']/b['shipped_units'])
    s.write_formula(i,3,f'=Inputs!E{ir}',fmt['money'],float(next(o['saving_eur_per_unit'] for o in options if o['country']==c)))
ch=wb.add_chart({'type':'bar'});ch.add_series({'name':'2025 contribution EUR','categories':['Decision Charts',5,0,10,0],'values':['Decision Charts',5,1,10,1],'fill':{'color':teal},'border':{'none':True}})
ch.set_title({'name':'Spain and Czechia lead existing contribution'});ch.set_x_axis({'name':'EUR','num_format':'#,##0'});ch.set_y_axis({'reverse':True});ch.set_legend({'none':True});ch.set_size({'width':800,'height':330});s.insert_chart('A14',ch)
ch=wb.add_chart({'type':'column'})
for col,title,color in [(2,'Recorded fulfillment cost',navy),(3,'Assumed hub saving',gold)]:ch.add_series({'name':title,'categories':['Decision Charts',5,0,10,0],'values':['Decision Charts',5,col,10,col],'fill':{'color':color},'border':{'none':True}})
ch.set_title({'name':'Validate the avoidable cost pool before capital release'});ch.set_y_axis({'name':'EUR per shipped unit','num_format':'0.00'});ch.set_legend({'position':'bottom'});ch.set_size({'width':800,'height':330});s.insert_chart('A32',ch);s.print_area('A1:H49')

s=sheet('Reconciliation','Monthly to annual controls','Every additive country metric must reconcile to the twelve monthly rows. Zero differences are cached and recalculate in spreadsheet software.', ['Country']+summary_fields[1:10],[17]*10)
for i,b in enumerate(M['countries'],5):
    er=i+1;br=cr[b['country']];s.write(i,0,b['country'])
    for j,k in enumerate(summary_fields[1:10],1):
        countrycol=xl_col_to_name(j);monthcol=xl_col_to_name(j+1)
        s.write_formula(i,j,f'=Countries!{countrycol}{br}-SUMIF(Monthly!A$6:A$77,A{er},Monthly!{monthcol}$6:{monthcol}$77)',fmt['money' if k.endswith('_eur') else 'int'],0)
finish(s,6,10)

se=sheet('Sensitivity','Czechia + Spain | volume and savings sensitivity','Additional analyst sensitivities; not client low/base/high/stress forecasts. No FX or refund shock here. Zero savings breaks even at 11.60% volume uplift.', ['Volume uplift','Savings realization','Annual increment EUR'],[23,27,28])
for i,r in enumerate(M['sensitivities'],5):
    se.write_number(i,0,r['volume_uplift'],fmt['pct']);se.write_number(i,1,r['savings_realization'],fmt['pct']);er=i+1
    terms=[]
    for c in ['CZE','ESP']:
        br=cr[c];ir=inputrow[c];terms.append(f'ROUND(Countries!I{br}*A{er}+Countries!C{br}*(1+A{er})*Inputs!E{ir}*B{er}-Inputs!D{ir},2)')
    se.write_formula(i,2,'='+'+'.join(terms),fmt['money'],r['incremental_contribution_eur'])
finish(se,12,3);se.conditional_format('C6:C17',{'type':'3_color_scale'})

q=M['quality'];qrows=[('Order raw rows',1328,'655 + 655 extract rows + 18 corrections'),('Order identical repeats',13,'Remove exact repeated rows, retain one'),('Order superseded revisions',18,'Highest numeric revision replaces whole row'),('Distinct selected orders',1297,'Apply eligibility after revision selection'),('Cancelled orders',24,'Exclude; these account for all 24 blank shipped_at values'),('Test orders',18,'Exclude'),('Future shipment',1,'Exclude FUTURE-2026 from 2025 base'),('Eligible orders',1254,'Count distinct eligible order IDs'),('Zero-price orders / units','12 / 739','Retained with product and fulfillment costs; contribution EUR−14,565.90'),('Return raw rows',264,'Resolve return_id independently'),('Return identical repeats / superseded','20 / 1','243 selected return IDs; 241 eligible'),('Cutoff return','R-CUTOFF','2026-01-31 included: DEU December; EUR54 refund, EUR29.50 COGS recovery'),('Late return','R-LATE','2026-02-01 excluded; EUR33 refund outside cutoff'),('Orphan return','R-ORPHAN','Order ABSENT: quarantine 2 units, 1 restocked, 60 local. Currency and EUR unknown; not inferred.'),('Multiple eligible return IDs/order',0,'None present; code sums all distinct eligible IDs if present'),('Missing eligible required fields',0,'No imputation; missing effective cost or FX would fail the build'),('Missing WB/FX observations','0 / 0','36 WB values present; 24 monthly FX means present'),('Restocked vs returned units','481 / 1,081','Recover only restocked product cost, EUR18,485.50'),('Physical quantity validation','Passed','Each eligible order: 0 ≤ restocked ≤ returned ≤ shipped'),('Unobserved operations','Material limitation','No live client access, interviews, site quotes, customer concentration, service baseline, cash ledger or validated uplift.')]
s=sheet('Quality','Data quality | detected and handled','Detailed row-level dispositions are on Order Resolution and Return Resolution; excluded lists also saved in deliverables/data.', ['Issue','Count / identifier','Handling'],[33,26,105])
for i,r in enumerate(qrows,5):
    for j,v in enumerate(r):write(s,i,j,v,'wrap')
    s.set_row(i,37)
finish(s,len(qrows),3)

s=sheet('Sources','Source register | complete provenance','Collection URLs are frozen-room locations. Original public URLs and archive retrieval times are distinct. Hashes authenticate saved bytes; see evidence/raw.', ['ID','File','Status','Units','Period','Archive retrieved UTC','Collected UTC','Revision vintage','Original URL','Collection URL','SHA-256'],[10,26,25,30,47,32,32,24,70,55,70])
for i,r in enumerate(REG,5):
    for j,k in enumerate(['source_id','file','status','units','period','archive_retrieved_utc','collected_at_utc','revision_vintage','original_url','collection_url','sha256']):write(s,i,j,r.get(k),'wrap')
    s.set_row(i,59)
finish(s,len(REG),11)
for name,file in [('Order Resolution','order_resolution.csv'),('Return Resolution','return_resolution.csv')]:
    data=rows(file);keys=list(data[0]);s=sheet(name,name+' | raw row audit','All original source rows retained, with source file/line, revision resolution and final eligibility.',keys,[23]*len(keys))
    for i,r in enumerate(data,5):
        for j,k in enumerate(keys):write(s,i,j,r[k])
    finish(s,len(data),len(keys))

costs=list(csv.DictReader((ROOT/'evidence/raw/unit-costs.csv').open()));s=sheet('Unit Costs','Original effective-dated unit costs','Synthetic EUR cost per unit. Latest valid_from ≤ original shipment date; recovered stock uses that same original cost.',list(costs[0]),[20,20,24])
for i,r in enumerate(costs,5):s.write_row(i,0,[r['sku'],r['valid_from'],float(r['unit_cost_eur'])])
finish(s,len(costs),3)

for s in wb.worksheets():s.set_tab_color(teal if s.name in ['Decision','Inputs','Hub Scenarios','Portfolios','Sensitivity'] else navy)
dash.activate();wb.close()
print('Created analytical workbook with cached formula results, reconciliation controls and three decision charts.')
