"""Build a formula-linked XLSX with cached results, audit detail and native charts."""
import csv
import json
from pathlib import Path
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name as col

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'
m=json.loads((OUT/'metrics.json').read_text())
d=json.loads((OUT/'decision-support.json').read_text())
sources=json.loads((OUT/'source-register.json').read_text())
countries=[r['country'] for r in m['countries']]
wb=xlsxwriter.Workbook(OUT/'Meridian_analytical_workbook.xlsx')
wb.set_properties(dict(title='Meridian Parts | European hub decision', author='Operations advisory',
                       subject='2025 shipment cohort; returns through 31 January 2026',
                       comments='Synthetic client; archived official macro/FX. Generated from saved inputs.'))
wb.set_calc_mode('auto')
NAVY='#162D43'; TEAL='#087F8C'; BLUE='#2266AA'; GRAY='#607283'; LIGHT='#EAF1F5'; RED='#B34145'
fmt={
 'title':wb.add_format({'font_size':21,'bold':True,'font_color':NAVY}),
 'sub':wb.add_format({'font_size':10,'font_color':GRAY,'text_wrap':True,'valign':'top'}),
 'header':wb.add_format({'bold':True,'bg_color':NAVY,'font_color':'white','text_wrap':True,'valign':'vcenter'}),
 'money':wb.add_format({'num_format':'#,##0.00;[Red](#,##0.00);–'}),
 'int':wb.add_format({'num_format':'#,##0'}),
 'pct':wb.add_format({'num_format':'0.0%;[Red](0.0%);–'}),
 'rate':wb.add_format({'num_format':'0.000000'}),
 'years':wb.add_format({'num_format':'0.00;[Red](0.00);–'}),
 'text':wb.add_format({'text_wrap':True,'valign':'top'}),
 'input':wb.add_format({'font_color':BLUE,'bg_color':'#EAF4FE','num_format':'#,##0.00'}),
 'inputpct':wb.add_format({'font_color':BLUE,'bg_color':'#EAF4FE','num_format':'0.0%'}),
 'good':wb.add_format({'font_color':'#216C49','bg_color':'#E8F5EF'}),
 'bad':wb.add_format({'font_color':RED,'bg_color':'#FCEDEE'}),
 'big':wb.add_format({'font_size':26,'bold':True,'font_color':TEAL,'num_format':'€#,##0'}),
 'k':wb.add_format({'num_format':'€0.0,"k"'}),
}
worksheets={}
def sheet(name,title,note,widths):
    ws=wb.add_worksheet(name);worksheets[name]=ws
    ws.hide_gridlines(2)
    ws.merge_range(0,0,0,max(len(widths)-1,1),title,fmt['title'])
    ws.merge_range(1,0,2,max(len(widths)-1,1),note,fmt['sub'])
    for i,width in enumerate(widths): ws.set_column(i,i,width)
    ws.freeze_panes(5,1)
    ws.set_landscape();ws.fit_to_pages(1,0);ws.repeat_rows(0,4)
    ws.set_header('&LMeridian Parts | Synthetic client&R2025 cohort')
    ws.set_footer('&LSource: saved source room and reproducible scripts&RPage &P of &N')
    ws.set_tab_color(TEAL)
    return ws

def headers(ws,fields):
    ws.write_row(4,0,fields,fmt['header']);ws.set_row(4,33)

def finish(ws,rows,cols):
    if rows: ws.autofilter(4,0,4+rows,cols-1)
    ws.print_area(0,0,max(5,4+rows),cols-1)

def simple(name,title,note,rows,widths=None):
    keys=list(rows[0]);widths=widths or [18]*len(keys)
    ws=sheet(name,title,note,widths);headers(ws,keys)
    for i,row in enumerate(rows,5):
        for j,k in enumerate(keys):
            val=row[k]
            if isinstance(val,(list,dict)):val=json.dumps(val)
            if val is None:ws.write_blank(i,j,None)
            elif isinstance(val,(int,float)) and not isinstance(val,bool):
                style=fmt['money'] if 'eur' in k or k=='gdp_per_capita_usd' else fmt['pct'] if k=='margin' or 'pct' in k or 'uplift' in k else fmt['years'] if 'years' in k else fmt['int']
                ws.write_number(i,j,val,style)
            else:ws.write(i,j,val,fmt['text'] if isinstance(val,str) and len(val)>40 else None)
    finish(ws,len(rows),len(keys));return ws

def readcsv(name):
    with (OUT/name).open(newline='') as f:return list(csv.DictReader(f))

dash=sheet('Dashboard','Reserve Czechia + Spain; stage the commitment',
           'Conditional recommendation | €225,000 capex / 5 FTE | Spain first, Czechia after savings, demand and FX gates. Annual figures are full run-rate increments, not cash forecasts.',[18]*10)
dash.freeze_panes(0,0)
dash.merge_range('A5:C5','BASE ANNUAL INCREMENT',fmt['header'])
dash.merge_range('A6:C7',m['recommendation']['base_incremental_contribution_eur'],fmt['big'])
dash.merge_range('D5:F5','JOINT STRESS INCREMENT',fmt['header'])
dash.merge_range('D6:F7',m['recommendation']['stress_incremental_contribution_eur'],fmt['big'])
dash.merge_range('G5:J5','CONTRIBUTION / NET SALES',fmt['header'])
dash.merge_range('G6:J7',f"{m['totals']['margin']:.1%}",fmt['title'])
dash.merge_range('A9:J10','Critical gap: every assumed unit saving exceeds recorded fulfillment cost per unit. Capping savings at recorded fulfillment reduces CZE+ESP base to €164,331.65 and stress to -€1,587.95. The prescribed scenario is preserved; do not commit without cost-scope evidence.',fmt['text'])
dash.set_row(8,24);dash.set_row(9,24)

readme=sheet('Read me','How to use this model','Read-only historical base; blue input cells are editable scenario assumptions. All formula cells include cached results for immediate viewing.',[28,120])
notes=[
 ('Scope','2025 shipped_at cohort; returns received through 2026-01-31 inclusive, attributed back to the sale month.'),
 ('Evidence','Client transactions and hub inputs are entirely synthetic. World Bank/ECB values are public observations from saved official archives. Live checks concern definitions only.'),
 ('Workflow','Dashboard → Countries / Monthly → Scenarios / Portfolios → Sensitivities. Inspect Orders and audit tabs for traceability. Sources holds original and collection URLs, times and SHA256.'),
 ('Accounting','Gross is after discounts, before returns, ex tax. Gross and aggregated refunds divided by original sale-month local/EUR quote. All order monetary components rounded half up to cents; sums are exact.'),
 ('COGS','Shipment-date effective EUR cost. Only restocked units recover cost at original unit cost. Fulfillment is actual nonrefundable EUR expense. Margin = contribution / net sales; blank if zero.'),
 ('Formula scope','Monthly formulas sum the static cent-rounded ledger. Countries sum Monthly. Scenarios link Countries and Hub Inputs. Portfolios sum Scenarios. No re-import or order-level FX recalculation occurs when you edit the historical ledger; regenerate scripts for source changes.'),
 ('Scenario editing','Edit blue Hub Inputs cells B:E and L6:L13 to test assumptions. Scenarios, Portfolios and chart ranges recalculate in Excel-compatible software. Dashboard recommendation, narrative, static base rank and diagnostic sensitivity values describe the delivered run; rerun analysis for a new decision.'),
 ('Null payback','Blank means annual incremental contribution is <=0 (or defer); it is not zero-year payback. Simple payback excludes ramp-up and cash timing.'),
 ('Risk','No demand probabilities, causal hub evidence, delivery data, inventory/working-capital plan, lease quotes or full cash-flow model. Cost-scope inconsistency must be resolved.'),
 ('Sources and vintage','Archive fetched by source-room provider 2026-09-27; World Bank lastupdated 2026-07-13. Separate analyst collection timestamps appear in Sources. Do not substitute today’s FX.'),
 ('Presentation','EUR amounts are exact cents in tables, rounded in decision charts. Market GDP is current USD/person; population persons. Read sources and quality notes before using charts.'),
 ('Verification','verification/checks.json and verification/verification-report.md record actual computational, XLSX and PDF checks and limits. Native Excel rendering/recalculation has not been asserted.'),
]
headers(readme,['Topic','Use / limitation'])
for i,row in enumerate(notes,5):readme.write_row(i,0,row,fmt['text']);readme.set_row(i,46)
finish(readme,len(notes),2)

ledger=readcsv('order-ledger.csv')
numeric=['revision','fx_local_per_eur','shipped_orders','shipped_units','gross_local','refunds_local','gross_sales_eur','refunds_eur','net_sales_eur','unit_cost_eur','gross_cogs_eur','recovered_cogs_eur','net_cogs_eur','fulfillment_eur','contribution_eur','returned_units','restocked_units','source_line']
for row in ledger:
    for k in numeric:row[k]=float(row[k])
ows=simple('Orders','Canonical order ledger','1254 eligible order IDs. Each monetary amount is already Decimal half-up rounded. See source_file and source_line for the winning record.',ledger)
lk=list(ledger[0]);last=5+len(ledger)
fields=list(m['monthly'][0]);mws=sheet('Monthly','Country × month | 2025 shipped cohort','Refunds known by 31 January 2026 restated to sale month. Monetary columns EUR; margin on net sales.',[12,14]+[18]*(len(fields)-2));headers(mws,fields)
for i,row in enumerate(m['monthly'],5):
    er=i+1
    for j,k in enumerate(fields):
        v=row[k]
        if k in ['country','month']:mws.write(i,j,v)
        elif k=='margin':
            n=col(fields.index('net_sales_eur'));cc=col(fields.index('contribution_eur'))
            mws.write_formula(i,j,f'=IF({n}{er}=0,"",{cc}{er}/{n}{er})',fmt['pct'],v if v is not None else '')
        else:
            lc=col(lk.index(k));ct=col(lk.index('country'));mt=col(lk.index('month'))
            formula=f'=SUMIFS(Orders!${lc}$6:${lc}${last},Orders!${ct}$6:${ct}${last},$A{er},Orders!${mt}$6:${mt}${last},$B{er})'
            mws.write_formula(i,j,formula,fmt['money'] if k.endswith('_eur') else fmt['int'],v)
finish(mws,72,len(fields))
cf=list(m['countries'][0]);cws=sheet('Countries','2025 country totals | EUR','Formula totals from 12 monthly cohort records; margin recomputed from annual contribution / annual net sales.',[12]+[18]*(len(cf)-1));headers(cws,cf)
for i,row in enumerate(m['countries'],5):
    er=i+1
    for j,k in enumerate(cf):
        v=row[k]
        if k=='country':cws.write(i,j,v)
        elif k=='margin':cws.write_formula(i,j,f'=IF(F{er}=0,"",I{er}/F{er})',fmt['pct'],v or '')
        else:
            mc=col(fields.index(k))
            cws.write_formula(i,j,f'=SUMIF(Monthly!$A$6:$A$77,$A{er},Monthly!${mc}$6:${mc}$77)',fmt['money'] if k.endswith('_eur') else fmt['int'],v)
totalrow=12
cws.write(totalrow,0,'TOTAL',fmt['header'])
for j,k in enumerate(cf[1:],1):
    if k=='margin':formula='=IF(F13=0,"",I13/F13)'
    else:formula=f'=SUM({col(j)}6:{col(j)}11)'
    cws.write_formula(totalrow,j,formula,fmt['pct'] if k=='margin' else fmt['money'] if k.endswith('_eur') else fmt['int'],m['totals'][k])
finish(cws,8,len(cf))

fxd=readcsv('fx-daily-2025.csv')
for row in fxd:row['local_per_eur']=float(row['local_per_eur'])
simple('FX Daily','Published 2025 observations','ECB archive. One row per date and currency; no weekend, holiday or missing-quote imputation. Units per EUR.',fxd,[16,14,20])
fws=simple('FX Monthly','Original sale-month FX translation','Arithmetic means of available published daily observations. PLN and CZK units per EUR; EUR=1. Divide local amounts by these rates.',m['fx_monthly'],[14,15,24,24,18,18])
for i,row in enumerate(m['fx_monthly'],5):fws.write_number(i,2,row['local_per_eur'],fmt['rate'])
marketws=simple('Market','Public market context | 2022–2024','World Bank: persons; GDP per capita current USD (not PPP or real growth). Vintage lastupdated 2026-07-13; no missing values in this snapshot. Context does not establish product demand.',m['market_context'],[14,14,24,26])
marketws.write_row('F5',['Country','Population change 22–24','GDP/person change 22–24'],fmt['header'])
for i,r in enumerate(m['market_changes'],5):
    marketws.write(i,5,r['country']);marketws.write(i,6,r['population_change_pct'],fmt['pct']);marketws.write(i,7,r['gdp_per_capita_change_pct'],fmt['pct'])
marketws.set_column('F:F',14);marketws.set_column('G:H',25)
marketws.print_area(0,0,22,7)

inputs=sheet('Hub Inputs','Synthetic planning assumptions','Blue cells are editable. Full-run-rate annual model. FTE/capex are hard resource limits, not monetary scores. No portfolio synergy.',[12,18,10,20,21,20,20,3,20,3,30,20])
headers(inputs,['Country','Capex EUR','FTE','Fixed EUR/year','Saving EUR/unit','2025 fulfillment/unit','Saving / recorded','', 'Cost gap','','Global input','Value'])
rawoptions=list(csv.DictReader((ROOT/'raw'/'hub-options.csv').open()))
for i,o in enumerate(rawoptions,5):
    inputs.write(i,0,o['country'])
    for j,k in enumerate(['capex_eur','fte','annual_fixed_eur','saving_eur_per_unit'],1):inputs.write(i,j,float(o[k]),fmt['input'])
    cap=next(x for x in d['savings_cap_sensitivity'] if x['country']==o['country'])
    inputs.write(i,5,cap['recorded_fulfillment_eur_per_unit'],fmt['money'])
    inputs.write_formula(i,6,f'=E{i+1}/F{i+1}',fmt['years'],cap['ratio_assumed_saving_to_recorded_cost'])
    inputs.write(i,8,'Unverified scope',fmt['bad'])
global_inputs=[('Low uplift',.10),('Base uplift',.25),('High uplift',.40),('Refund shock / gross',.03),('FX shock / net PLN,CZK',.10),('Capex limit EUR',450000),('FTE limit',7),('Hub limit',2)]
for i,(label,v) in enumerate(global_inputs,5):inputs.write(i,10,label);inputs.write(i,11,v,fmt['inputpct'] if i<10 else fmt['input'])
inputs.data_validation('B6:B11',{'validate':'decimal','criteria':'>=','value':0})
inputs.data_validation('C6:C11',{'validate':'integer','criteria':'>=','value':0})
inputs.data_validation('D6:E11',{'validate':'decimal','criteria':'>=','value':0})
inputs.data_validation('L6:L10',{'validate':'decimal','criteria':'between','minimum':0,'maximum':1})
finish(inputs,8,12)

sf=['country','scenario','uplift','incremental_contribution_eur','capex_eur','fte','payback_years','annual_fixed_eur','saving_eur_per_unit','refund_shock_eur','fx_shock_eur','contribution_after_shock_eur']
sws=sheet('Scenarios','Each hub | annual contribution after recurring fixed cost','Low/base/high uplifts 10%/25%/40%. Stress = base volume + 3% of gross refund loss + 10% of net FX loss (PLN/CZK only), relative to unchanged normal baseline. Capex is separate.',[12,14,13,25,19,10,18,20,20,22,20,26]);headers(sws,sf)
scenario_rows={}
for i,r in enumerate(m['hub_scenarios'],5):
    er=i+1;cr=countries.index(r['country'])+6;scenario_rows[r['country'],r['scenario']]=er
    sws.write(i,0,r['country']);sws.write(i,1,r['scenario'])
    ur={'low':6,'base':7,'high':8,'stress':7}[r['scenario']]
    forms={2:f"='Hub Inputs'!$L${ur}",
           3:f'=ROUND(L{er}*(1+C{er})-Countries!I{cr}+Countries!C{cr}*(1+C{er})*I{er}-H{er},2)',
           4:f"='Hub Inputs'!B{cr}",5:f"='Hub Inputs'!C{cr}",6:f'=IF(D{er}>0,E{er}/D{er},"")',
           7:f"='Hub Inputs'!D{cr}",8:f"='Hub Inputs'!E{cr}",
           9:f'=IF(B{er}="stress",Countries!D{cr}*\'Hub Inputs\'!$L$9,0)',
           10:f'=IF(AND(B{er}="stress",OR(A{er}="POL",A{er}="CZE")),Countries!F{cr}*\'Hub Inputs\'!$L$10,0)',
           11:f'=Countries!I{cr}-J{er}-K{er}'}
    for j,formula in forms.items():
        k=sf[j];style=fmt['pct'] if j==2 else fmt['years'] if j==6 else fmt['int'] if j==5 else fmt['money']
        sws.write_formula(i,j,formula,style,r[k] if r[k] is not None else '')
finish(sws,24,len(sf));sws.conditional_format('D6:D29',{'type':'cell','criteria':'<','value':0,'format':fmt['bad']})

pf=['option','capex_eur','fte','feasible','low_incremental_eur','base_incremental_eur','high_incremental_eur','stress_incremental_eur','base_payback_years','low_payback_years','high_payback_years','stress_payback_years','base_rank','constraint_failures']
portfolios=sorted(m['portfolio_scenarios'],key=lambda p:(not p['feasible'],p['base_rank'] or 99))
pws=sheet('Portfolios','All 22 choices | six singles, 15 pairs, defer','18 feasible choices at delivery; four pairs fail resource limits. Rank is the original base result (static); sort recalculated annual contribution for edited assumptions. Pairs add country results, no synergy.',[17,18,10,12,21,21,21,21,18,18,18,18,12,38]);headers(pws,pf)
port_rows={}
for i,r in enumerate(portfolios,5):
    er=i+1;port_rows[r['option']]=er;pws.write(i,0,r['option'])
    for j,k in enumerate(pf[1:],1):
        v=r[k]
        if k in ['base_rank','constraint_failures']:
            pws.write(i,j,v if v is not None else '',fmt['text']);continue
        if k=='feasible':formula=f'=AND(B{er}<=\'Hub Inputs\'!$L$11,C{er}<=\'Hub Inputs\'!$L$12,{len(r["countries"])}<=\'Hub Inputs\'!$L$13)'
        elif k in ['capex_eur','fte']:
            ref='E' if k=='capex_eur' else 'F';formula='='+('+'.join(f'Scenarios!{ref}{scenario_rows[c,"base"]}' for c in r['countries']) or '0')
        elif k.endswith('_incremental_eur'):
            sc=k.split('_')[0];formula='='+('+'.join(f'Scenarios!D{scenario_rows[c,sc]}' for c in r['countries']) or '0')
        else:
            sc=k.split('_')[0];pc=col(pf.index(sc+'_incremental_eur'));formula=f'=IF({pc}{er}>0,B{er}/{pc}{er},"")'
        style=fmt['years'] if 'payback' in k else fmt['int'] if k=='fte' else fmt['money']
        pws.write_formula(i,j,formula,style,v if v is not None else '')
finish(pws,len(portfolios),len(pf));pws.conditional_format('E6:H27',{'type':'cell','criteria':'<','value':0,'format':fmt['bad']})

sensrows=[]
for r in d['savings_cap_sensitivity']:
    th=next(x for x in m['decision_thresholds'] if x['country']==r['country'])
    sensrows.append({**r,'break_even_uplift':th['break_even_uplift']})
simple('Sensitivities','Cost-scope diagnostic and break-even volume','STATIC diagnostic, not replacement policy: cap savings at historical fulfillment EUR/unit, assuming this is the entire avoidable cost pool. No residual fulfillment expense assumed, so this is still optimistic.',sensrows,[12,24,29,27,25,25,21])
sens=worksheets['Sensitivities']
sens.merge_range('A14:G16','Switching conditions (original inputs): CZE uplift <17.69% while NLD stays at 25%, or €31,167.88 extra annual CZE fixed cost, erases its base advantage over NLD. Scaling both stress shocks together to 29.23% of their full size makes NLD+ESP equal CZE+ESP. These are deterministic thresholds, not probabilities.',fmt['text'])
sens.merge_range('A18:G20','CZE+ESP under fulfillment-capped savings: €164,331.65 base and -€1,587.95 stress. NLD+ESP: €113,512.52 base and €54,211.22 stress. Cost evidence and the board’s downside preference can change the decision.',fmt['text'])
for nm,fn in [('Order Audit','order-audit.csv'),('Return Audit','return-audit.csv')]:
    rows=readcsv(fn)
    simple(nm,'Raw row disposition | '+nm,'One row per input record with source line and handling: include, exclusion, exact duplicate, superseded revision or quarantined orphan. No silent joins.',rows,[24,14]+[18]*(len(rows[0])-3)+[44])
qrows=[]
for group in ['order_reconciliation','return_reconciliation','missing_values']:
    for k,v in m['quality'][group].items():qrows.append(dict(group=group,check=k,value=json.dumps(v),handling='See audit tabs and README; no guessed joins or imputations.'))
for note in m['quality']['handling_notes']:qrows.append(dict(group='Accounting and limitation',check='Policy',value=note,handling='Disclosed'))
qrows.append(dict(group='Savings scope',check='Cost assumption mismatch',value=m['quality']['savings_assumption_anomaly'],handling='Separate Sensitivities tab; gating item.'))
qws=simple('Quality','Data quality and limitations','Reconciliation and exclusions are deliberate; zero-price shipments remain in order count, units, COGS and fulfillment.',qrows,[27,37,100,58])
for i in range(5,5+len(qrows)):qws.set_row(i,36)
srcws=simple('Sources','Source register | original vs analyst collection','Original public retrieval and analyst collection are distinct. SHA256 checksums describe the saved bytes. Live-source text is web-tool extraction, not raw HTML; no live series used.',sources,[12,35,60,29,70,14,65,29,42,45,48,48,18])
for i in range(5,5+len(sources)):srcws.set_row(i,56)

checks=sheet('Checks','Reconciliation controls','Zero difference is required for each additive measure. Values are cached and recalculate in compatible spreadsheet software. Full independent verification lives in verification/.',[30,25,25,25,22]);headers(checks,['Measure','Country total','Order ledger total','Difference','Status'])
for i,k in enumerate([x for x in cf if x not in ['country','margin']],5):
    er=i+1;cc=col(cf.index(k));lc=col(lk.index(k));v=m['totals'][k]
    checks.write(i,0,k);checks.write_formula(i,1,f'=Countries!{cc}13',fmt['money'],v)
    checks.write_formula(i,2,f'=SUM(Orders!{lc}6:{lc}{last})',fmt['money'],v)
    checks.write_formula(i,3,f'=ROUND(B{er}-C{er},2)',fmt['money'],0)
    checks.write_formula(i,4,f'=IF(D{er}=0,"PASS","FAIL")',fmt['good'],'PASS')
finish(checks,9,5)

chart=wb.add_chart({'type':'column'})
chart.add_series({'name':'2025 contribution','categories':'=Countries!$A$6:$A$11','values':'=Countries!$I$6:$I$11','fill':{'color':TEAL},'border':{'none':True},'data_labels':{'value':True,'num_format':'€0,"k"'}})
chart.set_title({'name':'Spain and Czechia lead observed contribution'})
chart.set_y_axis({'name':'EUR / 2025','num_format':'€0,"k"','major_gridlines':{'visible':True,'line':{'color':LIGHT}}})
chart.set_legend({'none':True});chart.set_size({'width':620,'height':315});chart.set_style(10)
dash.insert_chart('A12',chart)
chart2=wb.add_chart({'type':'column'})
for name,pc,color in [('Low','E','#9AB7C1'),('Base','F',TEAL),('Stress','H','#D28C54')]:
    chart2.add_series({'name':name,'categories':'=Portfolios!$A$6:$A$9','values':f'=Portfolios!${pc}$6:${pc}$9','fill':{'color':color},'border':{'none':True}})
chart2.set_title({'name':'Base leader versus downside resilience'})
chart2.set_y_axis({'name':'Annual increment EUR','num_format':'€0,"k"'})
chart2.set_legend({'position':'bottom'});chart2.set_size({'width':620,'height':315});chart2.set_style(10)
dash.insert_chart('A29',chart2)
dash.merge_range('G13:J18','Decision gates\n1. Cost savings have a signed, itemized bridge.\n2. Pilot supports incremental demand after seasonality and central-channel cannibalization.\n3. FX and return stress are rerun with costs evidenced.\n4. Board confirms whether base contribution or downside preservation governs the second hub.',fmt['text'])
dash.merge_range('G21:J26','Key concessions\nNLD+ESP gives up €31,167.88/year base contribution, costs €45,000 more and needs one more FTE; it produces €75,450.42/year more contribution in joint stress. Defer preserves all capital if evidence fails.',fmt['text'])
dash.merge_range('G31:J38','Model boundaries\nNo statistical proof of uplift. No ramp-up cash model, working capital, local lease/labor evidence, capacity validation or actual service-level data. Simple payback is capex / positive annual increment.\n\nOriginal observations and public indicators must not be interpreted as six real customer samples.',fmt['text'])
dash.print_area('A1:J46');dash.fit_to_pages(1,2)
wb.close()
print('Created formula-linked workbook with',len(worksheets),'sheets')
