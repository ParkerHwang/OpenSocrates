"""Build a cached, formula-linked XLSX; preserves exact Decimal results as caches."""
from pathlib import Path
import csv
import json
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name as col

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables'

def main():
    m=json.loads((OUT/'metrics.json').read_text())
    ledger=list(csv.DictReader((OUT/'audit/order_ledger.csv').open()))
    sources=json.loads((ROOT/'evidence/source-register.json').read_text())
    countries=[r['country'] for r in m['countries']]
    wb=xlsxwriter.Workbook(OUT/'meridian_analysis.xlsx')
    wb.set_properties(dict(title='Meridian Parts | European hub decision',author='Operations consulting',comments='Synthetic client case; official data from frozen archive.'))
    wb.set_calc_mode('auto')
    navy='#17324D'; teal='#087F8C'; gold='#D58A2D'; muted='#536879'
    fmt={
        'title':wb.add_format({'bold':True,'font_size':20,'font_color':navy}),
        'sub':wb.add_format({'font_size':10,'font_color':muted,'text_wrap':True,'valign':'top'}),
        'header':wb.add_format({'bold':True,'bg_color':navy,'font_color':'white','text_wrap':True,'valign':'vcenter','border':0}),
        'text':wb.add_format({'font_size':10,'valign':'top'}),
        'wrap':wb.add_format({'font_size':10,'text_wrap':True,'valign':'top'}),
        'money':wb.add_format({'num_format':'#,##0.00;[Red](#,##0.00);–','font_size':10}),
        'int':wb.add_format({'num_format':'#,##0','font_size':10}),
        'pct':wb.add_format({'num_format':'0.0%;[Red](0.0%);–','font_size':10}),
        'rate':wb.add_format({'num_format':'0.000000','font_size':10}),
        'year':wb.add_format({'num_format':'0.00','font_size':10}),
        'input':wb.add_format({'num_format':'#,##0.00','font_color':'#165AC6','bg_color':'#EAF2FF','font_size':10}),
        'input_pct':wb.add_format({'num_format':'0.0%','font_color':'#165AC6','bg_color':'#EAF2FF','font_size':10}),
        'bad':wb.add_format({'bg_color':'#FBE9E7','font_color':'#AD342B'}),
        'good':wb.add_format({'bg_color':'#E3F2EF','font_color':teal}),
        'link':wb.add_format({'font_color':teal,'underline':True,'font_size':10}),
        'kpi':wb.add_format({'bold':True,'font_color':teal,'font_size':26,'num_format':'#,##0'}),
    }
    sheets={}
    def sheet(name,headers,widths=None,note=None):
        ws=wb.add_worksheet(name); sheets[name]=ws
        ws.hide_gridlines(2);ws.set_tab_color(teal);ws.freeze_panes(1,1)
        ws.write_row(0,0,headers,fmt['header']);ws.set_row(0,34)
        for i,h in enumerate(headers):ws.set_column(i,i,(widths[i] if widths else max(14,min(23,len(h)+2))))
        ws.set_landscape();ws.set_paper(9);ws.fit_to_pages(1,0);ws.repeat_rows(0)
        ws.set_header('&LMeridian Parts | synthetic case&R'+name)
        ws.set_footer('&L2025 shipments • cutoff 2026-01-31&RPage &P of &N')
        if note:ws.write_comment(0,0,note)
        return ws
    def finish(ws,rows,cols):
        ws.autofilter(0,0,rows,cols-1);ws.print_area(0,0,rows,cols-1)
    def val(ws,r,c,v,kind='text'):
        if v is None:ws.write_blank(r,c,None,fmt[kind])
        elif isinstance(v,(list,dict)):ws.write(r,c,json.dumps(v),fmt['wrap'])
        else:ws.write(r,c,v,fmt[kind])
    def formula(ws,r,c,expr,result,kind='money'):
        ws.write_formula(r,c,expr,fmt[kind],'' if result is None else result)

    dashboard=wb.add_worksheet('Decision');sheets['Decision']=dashboard;dashboard.hide_gridlines(2)
    dashboard.set_column('A:L',12);dashboard.set_row(0,32)
    dashboard.merge_range('A1:L2','Reserve Czechia + Spain; launch in stages',fmt['title'])
    dashboard.merge_range('A3:L4','Provisional recommendation | Spain first; Czechia released after demand, savings and FX review. No measured hub uplift or transaction cash ledger supplied.',fmt['sub'])
    for rg,label in [('A6:D6','Base annual increment (EUR)'),('E6:H6','Year-zero capex (EUR)'),('I6:L6','Total hub FTE')]:dashboard.merge_range(rg,label,fmt['header'])
    dashboard.merge_range('A7:D8',198099.31,fmt['kpi']);dashboard.merge_range('E7:H8',225000,fmt['kpi']);dashboard.merge_range('I7:L8',5,fmt['kpi'])
    dashboard.merge_range('A10:L11','CZE+ESP: low EUR64,619; stress EUR32,180. NLD+ESP: base EUR166,931; stress EUR107,630. All are annual increments after recurring fixed cost. Capex is separate.',fmt['sub'])
    dashboard.merge_range('A12:L13','Use the Guide for scope, Sources for provenance, and blue cells on Inputs for scenario changes. Recommendation text and supplemental sensitivity are analyst snapshots; rerun scripts after changing source data.',fmt['sub'])
    dashboard.set_landscape();dashboard.fit_to_pages(1,1);dashboard.print_area('A1:L57')

    guide=sheet('Guide',['Topic','Definition / use'],[28,125])
    guide_rows=[
        ('Start here','Decision shows the chosen envelope. Countries and Monthly are formulas from the order ledger. Scenarios and Portfolios link to baseline and editable Inputs; cached results permit immediate viewing.'),
        ('Evidence states','Client transactions/options/policy are synthetic. ECB and World Bank are archived official public observations. Archive collection is not a live client account or current market research.'),
        ('Baseline scope','Highest numeric revision per ID across both order pages and corrections; full-row replacement. Eligible: shipped, not test, shipment in 2025. Keep zero-price shipments.'),
        ('Returns','Highest revision per return ID. Received through inclusive 2026-01-31; link only to eligible orders. Orphans quarantined. Distinct return IDs add; none of the included orders happens to have multiple IDs.'),
        ('Gross / net sales','Gross means quantity × price minus discount, tax excluded and before refunds. Net = gross less explicit credit amounts. Returns are assigned to the original shipment month for cohort analysis.'),
        ('FX','Arithmetic mean of published 2025 ECB business-day local units per EUR; EUR=1. Divide local gross and summed order refunds by the original shipment-month rate. Means are not rounded before conversion.'),
        ('Rounding','Python Decimal, ROUND_HALF_UP to cents for gross, summed refunds, gross COGS, recovered COGS and fulfillment on each order; then sum. Excel ROUND is used on nonnegative monetary components. Caches are the exact Decimal outputs; Excel floating-point recalculation can differ at rare half-cent boundaries.'),
        ('Costs and margin','Latest SKU cost valid on/before shipment. Recover only restocked units × original cost. Fulfillment is nonrefundable. Contribution = net sales - net COGS - fulfillment. Margin = contribution/net sales; blank if net sales=0.'),
        ('Scenario formula','C*u + U*(1+u)*s - F. Stress = base increment - 1.25*(0.03*G + 0.10*N for PLN/CZK). Baseline normal contribution is unchanged in the stress comparison. Capex is not deducted from annual contribution.'),
        ('Timing / cash','Scenarios are steady-state annual run rates. Simple capex/positive annual increment is undiscounted payback, not a cash-flow forecast. No ramp, tax, financing, working capital, lease deposits or residual value supplied.'),
        ('Inputs','Blue values on Inputs may be edited. Columns hold capex, FTE, recurring annual cost and per-unit saving. Scenario uplifts and stress rates are in H:I. Defaults reproduce scenario-policy.md. Scenarios groups intermediate calculation columns; expand the + controls to inspect them.'),
        ('Pair rules','Up to two hubs, EUR450,000 capex and 7 FTE. No synergy or cannibalization adjustment. All 15 pairs are shown, including four infeasible pairs; 11 pairs are feasible. Defer has zero increment and no payback.'),
        ('Decision rule','Consultant default maximizes base annual contribution within hard limits while testing downside and staging spend. No weights or probabilities. Maximin across the four supplied scenarios would choose NLD+ESP.'),
        ('Savings caution','All proposed unit savings exceed actual fulfillment per shipped unit. Scope must include evidenced other savings, or be revised. Sensitivity caps savings at historic fulfillment; this is a separate analyst boundary test.'),
        ('Workbook limitations','Inputs, Scenarios and Portfolios form an editable financial model. Notes, decision wording, supplemental sensitivity and source register are saved snapshots; rebuild for a fully refreshed package. No macros or external workbook links.'),
        ('Reproduce','From saved evidence: python scripts/analyze.py; python scripts/build_workbook.py; python scripts/build_documents.py; python scripts/verify.py. See README.md for local dependencies and environment setup.'),
    ]
    for r,row in enumerate(guide_rows,1):guide.write_row(r,0,row,fmt['wrap']);guide.set_row(r,46 if r!=7 else 60)
    finish(guide,len(guide_rows),2)

    ws=sheet('Sources',['ID','File','Status','Units','Period','Collected UTC','Archive retrieval UTC','Source revision','SHA-256','Original URL','Collection URL'],[9,31,25,48,45,30,30,45,68,80,55])
    for r,s in enumerate(sources,1):
        for j,k in enumerate(['source_id','file','source_kind','units','period','collected_at_utc','archive_retrieved_utc','revision_vintage','sha256','original_url','collection_url']):val(ws,r,j,s[k],'wrap')
        ws.write_url(r,9,s['original_url'],fmt['link'],s['original_url']);ws.set_row(r,62)
    finish(ws,len(sources),11)
    q=m['quality']
    qr=[('Order raw rows',1328,'655 + 655 extract rows + 18 corrections'),('Order identical duplicates',13,'Removed before revision selection'),('Superseded order revisions',18,'Corrections replace the entire previous row'),('Retained order IDs',1297,'No equal-revision conflicts'),('Eligible 2025 shipments',1254,'24 cancelled + 18 test + 1 future shipment excluded'),('Free shipments retained',12,'739 units; contribution -EUR14,565.90'),('Return raw rows',264,'20 duplicates + 1 old revision removed'),('Retained return IDs',243,'241 included; 1 orphan and 1 after cutoff excluded'),('Restocked units',481,'Of 1,081 returned; recover EUR18,485.50 of COGS only'),('Missing shipment dates',24,'All cancelled; no eligible missing monetary, cost or FX values'),('World Bank missing values',0,'18 country-years × two indicators; missing values would stay null'),('ECB observations per currency',255,'Available published dates; no imputation'),('Public archive hash matches',4,'ZIP CSV bytes also match archive CSV'),('Orphan R-ORPHAN',2,'2 units; refund_local 60; currency unknown. No guessed match or EUR conversion'),('Cutoff R-CUTOFF',1,'2026-01-31 included against Dec 2025; EUR54 refund, EUR29.50 COGS recovery'),('Late R-LATE',1,'2026-02-01 excluded; EUR33 credit outside cutoff'),('Return correction',1,'R-M1-01-003 revision 2: credit 149, supersedes 150'),('Censored returns',None,'No estimate of later returns; no cash ledger; no measured hub effect')]
    ws=sheet('Quality',['Control / anomaly','Count / quantity','Handling / limitation'],[34,20,105])
    for r,row in enumerate(qr,1):
        for j,v in enumerate(row):val(ws,r,j,v,'wrap' if j!=1 else 'int')
        ws.set_row(r,34)
    finish(ws,len(qr),3)

    # Inputs: fixed row positions are used in formula references below.
    ws=sheet('Inputs',['Country','Capex EUR','FTE','Annual fixed EUR','Saving EUR/unit','','','Policy assumption','Value'],[13,19,10,21,21,3,3,32,18])
    options=list(csv.DictReader((ROOT/'evidence/raw/hub-options.csv').open()))
    for r,row in enumerate(options,1):
        ws.write(r,0,row['country'])
        for j,k in enumerate(['capex_eur','fte','annual_fixed_eur','saving_eur_per_unit'],1):ws.write_number(r,j,float(row[k]),fmt['input'])
    policy=[('Low uplift',.10),('Base uplift',.25),('High uplift',.40),('Refund shock × gross',.03),('PLN/CZK FX shock × net',.10),('Capex ceiling EUR',450000),('FTE ceiling',7),('Hub ceiling',2)]
    for r,(label,v) in enumerate(policy,1):ws.write(r,7,label,fmt['wrap']);ws.write(r,8,v,fmt['input_pct' if r<=5 else 'input'])
    ws.data_validation('B2:E7',{'validate':'decimal','criteria':'>=','value':0})
    ws.data_validation('I2:I6',{'validate':'decimal','criteria':'between','minimum':0,'maximum':1})
    ws.merge_range('A11:I12','Synthetic board assumptions; no uplift or saving is an observed causal effect.',fmt['sub'])
    ws.merge_range('A14:I15','Do not treat unspent capex or FTE headroom as a required investment.',fmt['sub'])
    ws.print_area('A1:I16')

    ws=sheet('FX daily',['Date','Currency','Local units / EUR'],[17,14,24])
    daily=list(csv.DictReader((OUT/'audit/fx_daily_2025.csv').open()))
    for r,x in enumerate(daily,1):ws.write(r,0,x['date']);ws.write(r,1,x['currency']);ws.write_number(r,2,float(x['local_per_eur']),fmt['rate'])
    finish(ws,len(daily),3)
    ws=sheet('FX monthly',['Currency','Month','Local units / EUR','Published observations','Join key'],[15,18,26,26,24])
    fxmap={}
    for r,x in enumerate(m['fx_monthly'],1):
        er=r+1;ws.write(r,0,x['currency']);ws.write(r,1,x['month'])
        formula(ws,r,2,f'=AVERAGEIFS(\'FX daily\'!$C$2:$C$511,\'FX daily\'!$B$2:$B$511,A{er},\'FX daily\'!$A$2:$A$511,B{er}&"*")',x['local_per_eur'],'rate')
        formula(ws,r,3,f'=COUNTIFS(\'FX daily\'!$B$2:$B$511,A{er},\'FX daily\'!$A$2:$A$511,B{er}&"*")',x['observation_count'],'int')
        ws.write(r,4,x['currency']+'|'+x['month']);fxmap[x['currency'],x['month']]=r+1
    finish(ws,24,5)

    ws=sheet('Market',['Country','Year','Population persons','GDP per capita current US$','Population source','GDP source','WB lastupdated'],[14,12,26,31,22,22,24])
    for r,x in enumerate(m['market_context'],1):
        for j,k in enumerate(['country','year','population','gdp_per_capita_usd']):val(ws,r,j,x[k],'int' if j==2 else 'money' if j==3 else 'text')
        ws.write(r,4,'S10 / SP.POP.TOTL');ws.write(r,5,'S05 / NY.GDP.PCAP.CD');ws.write(r,6,'2026-07-13')
    finish(ws,18,7)

    # Full order ledger: rounded component formulas feed every financial summary.
    headers=['Order ID','Revision','Country','Month','Shipped at','SKU','Currency','Orders','Units','Unit price local','Discount local','Gross local','Refund local','Local / EUR','Unit cost EUR','Cost valid from','Gross EUR','Refund EUR','Net EUR','Gross COGS EUR','Restocked units','Recovered COGS EUR','Net COGS EUR','Fulfillment EUR','Contribution EUR','Returned units','Return IDs','Source file','Source line']
    ws=sheet('Orders',headers);ws.freeze_panes(1,4);ws.set_column('A:A',20);ws.set_column('AA:AA',24)
    keys=['order_id','revision','country','month','shipped_at','sku','currency','shipped_orders','shipped_units','unit_price_local','discount_local','gross_local','refund_local','fx_local_per_eur','unit_cost_eur','cost_valid_from','gross_sales_eur','refunds_eur','net_sales_eur','gross_cogs_eur','restocked_units','recovered_cogs_eur','net_cogs_eur','fulfillment_eur','contribution_eur','returned_units','return_ids','source_file','source_line']
    numeric={1,7,8,9,10,11,12,13,14,16,17,18,19,20,21,22,23,24,25,28}
    for r,x in enumerate(ledger,1):
        er=r+1
        forms={11:f'=I{er}*J{er}-K{er}',16:f'=ROUND(L{er}/N{er},2)',17:f'=ROUND(M{er}/N{er},2)',18:f'=Q{er}-R{er}',19:f'=ROUND(I{er}*O{er},2)',21:f'=ROUND(U{er}*O{er},2)',22:f'=T{er}-V{er}',24:f'=S{er}-W{er}-X{er}'}
        if x['currency']!='EUR':forms[13]=f"='FX monthly'!C{fxmap[x['currency'],x['month']]}"
        for j,k in enumerate(keys):
            v=float(x[k]) if j in numeric else x[k]
            kind='rate' if j==13 else 'int' if j in {1,7,8,20,25,28} else 'money' if j in numeric else 'text'
            if j in forms:formula(ws,r,j,forms[j],v,kind)
            else:val(ws,r,j,v,kind)
    finish(ws,len(ledger),len(headers))
    order_last=len(ledger)+1
    summary_keys=['country','shipped_orders','shipped_units','gross_sales_eur','refunds_eur','net_sales_eur','net_cogs_eur','fulfillment_eur','contribution_eur','returned_units','margin']
    summary_headers=['Country','Shipped orders','Shipped units','Gross sales EUR','Refunds EUR','Net sales EUR','Net COGS EUR','Fulfillment EUR','Contribution EUR','Returned units','Margin']
    order_cols={'shipped_orders':'H','shipped_units':'I','gross_sales_eur':'Q','refunds_eur':'R','net_sales_eur':'S','net_cogs_eur':'W','fulfillment_eur':'X','contribution_eur':'Y','returned_units':'Z'}
    ws=sheet('Monthly',[summary_headers[0],'Month']+summary_headers[1:]);ws.freeze_panes(1,2)
    for r,x in enumerate(m['monthly'],1):
        er=r+1;ws.write(r,0,x['country']);ws.write(r,1,x['month'])
        for j,k in enumerate(summary_keys[1:],2):
            if k=='margin':expr=f'=IF(G{er}=0,"",J{er}/G{er})';kind='pct'
            else:
                oc=order_cols[k];expr=f'=SUMIFS(Orders!${oc}$2:${oc}${order_last},Orders!$C$2:$C${order_last},A{er},Orders!$D$2:$D${order_last},B{er})'
                kind='int' if k in ['shipped_orders','shipped_units','returned_units'] else 'money'
            formula(ws,r,j,expr,x[k],kind)
    finish(ws,72,12)
    ws=sheet('Countries',summary_headers)
    for r,x in enumerate(m['countries'],1):
        er=r+1;ws.write(r,0,x['country'])
        for j,k in enumerate(summary_keys[1:],1):
            if k=='margin':expr=f'=IF(F{er}=0,"",I{er}/F{er})';kind='pct'
            else:
                mc=col(j+1);expr=f'=SUMIF(Monthly!$A$2:$A$73,A{er},Monthly!${mc}$2:${mc}$73)';kind='int' if k in ['shipped_orders','shipped_units','returned_units'] else 'money'
            formula(ws,r,j,expr,x[k],kind)
    ws.write(8,0,'ALL',fmt['header'])
    for j,k in enumerate(summary_keys[1:],1):formula(ws,8,j,f'=IF(F9=0,"",I9/F9)' if k=='margin' else f'=SUM({col(j)}2:{col(j)}7)',m['totals'][k],'pct' if k=='margin' else 'int' if k in ['shipped_orders','shipped_units','returned_units'] else 'money')
    finish(ws,6,11);ws.print_area('A1:K9')

    ws=sheet('Scenarios',['Country','Scenario','Volume uplift','Baseline C EUR','Units U','Gross G EUR','Net N EUR','Saving EUR/unit','Fixed EUR/year','Capex EUR','FTE','Volume contribution EUR','Unit savings EUR','Stress penalty EUR','Annual increment EUR','Payback years'],[12,14,16,20,14,20,20,18,20,20,10,23,23,23,25,18])
    for r,x in enumerate(m['hub_scenarios'],1):
        er=r+1;ir=countries.index(x['country'])+2
        ws.write(r,0,x['country']);ws.write(r,1,x['scenario'])
        ucell={'low':2,'base':3,'high':4,'stress':3}[x['scenario']]
        br=m['countries'][ir-2];op=options[ir-2]
        raw_penalty=(1+x['volume_uplift'])*(.03*br['gross_sales_eur']+(.10*br['net_sales_eur'] if x['country'] in ['POL','CZE'] else 0)) if x['scenario']=='stress' else 0
        specs=[(2,f'=Inputs!I{ucell}',x['volume_uplift'],'pct'),(3,f'=Countries!I{ir}',br['contribution_eur'],'money'),(4,f'=Countries!C{ir}',br['shipped_units'],'int'),(5,f'=Countries!D{ir}',br['gross_sales_eur'],'money'),(6,f'=Countries!F{ir}',br['net_sales_eur'],'money'),(7,f'=Inputs!E{ir}',float(op['saving_eur_per_unit']),'money'),(8,f'=Inputs!D{ir}',x['annual_fixed_eur'],'money'),(9,f'=Inputs!B{ir}',x['capex_eur'],'money'),(10,f'=Inputs!C{ir}',x['fte'],'int'),(11,f'=D{er}*C{er}',br['contribution_eur']*x['volume_uplift'],'money'),(12,f'=E{er}*(1+C{er})*H{er}',br['shipped_units']*(1+x['volume_uplift'])*float(op['saving_eur_per_unit']),'money'),(13,f'=IF(B{er}="stress",(1+C{er})*(Inputs!$I$5*F{er}+IF(OR(A{er}="POL",A{er}="CZE"),Inputs!$I$6*G{er},0)),0)',x['stress_penalty_eur'],'money'),(14,f'=ROUND(L{er}+M{er}-I{er}-N{er},2)',x['incremental_contribution_eur'],'money'),(15,f'=IF(O{er}>0,J{er}/O{er},"")',x['payback_years'],'year')]
        for j,e,v,k in specs:formula(ws,r,j,e,raw_penalty if j==13 else v,k)
    ws.freeze_panes(1,2)
    for j in list(range(3,9))+[11,12,13]:ws.set_column(j,j,23 if j>=11 else 20,None,{'level':1,'hidden':True})
    ws.set_column(9,9,20,None,{'collapsed':True});ws.set_column(14,14,25,None,{'collapsed':True})
    ws.conditional_format('O2:O25',{'type':'cell','criteria':'<','value':0,'format':fmt['bad']});finish(ws,24,16)

    ws=sheet('Portfolios',['Portfolio','Hub 1','Hub 2','Scenario','Capex EUR','FTE','Annual increment EUR','Payback years','Feasible','Base/scenario rank','Constraint issue'],[20,12,12,14,20,10,26,19,12,21,37])
    portfolio_row={}
    for r,x in enumerate(m['portfolios'],1):
        er=r+1;h=(x['countries']+['',''])[:2]
        ws.write(r,0,x['portfolio']);ws.write(r,1,h[0]);ws.write(r,2,h[1]);ws.write(r,3,x['scenario']);portfolio_row[x['portfolio'],x['scenario']]=er
        for j,sc_col,v,k in [(4,'J',x['capex_eur'],'money'),(5,'K',x['fte'],'int'),(6,'O',x['incremental_contribution_eur'],'money')]:
            e=f'=SUMIFS(Scenarios!${sc_col}$2:${sc_col}$25,Scenarios!$A$2:$A$25,B{er},Scenarios!$B$2:$B$25,D{er})+SUMIFS(Scenarios!${sc_col}$2:${sc_col}$25,Scenarios!$A$2:$A$25,C{er},Scenarios!$B$2:$B$25,D{er})'
            formula(ws,r,j,e,v,k)
        formula(ws,r,7,f'=IF(G{er}>0,E{er}/G{er},"")',x['payback_years'],'year')
        formula(ws,r,8,f'=AND(E{er}<=Inputs!$I$7,F{er}<=Inputs!$I$8,COUNTA(B{er}:C{er})<=Inputs!$I$9)',x['feasible'],'text')
        formula(ws,r,9,f'=IF(I{er},COUNTIFS($D$2:$D$89,D{er},$I$2:$I$89,TRUE,$G$2:$G$89,">"&G{er})+1,"")',x.get('rank_within_scenario'),'int')
        formula(ws,r,10,f'=IF(E{er}>Inputs!$I$7,"Capex exceeded; ","")&IF(F{er}>Inputs!$I$8,"FTE exceeded","")',x['infeasibility_reason'],'text')
    ws.set_column('B:C',12,None,{'level':1,'hidden':True});ws.set_column('D:D',14,None,{'collapsed':True})
    ws.conditional_format('I2:I89',{'type':'cell','criteria':'==','value':False,'format':fmt['bad']});ws.conditional_format('G2:G89',{'type':'cell','criteria':'<','value':0,'format':fmt['bad']});finish(ws,88,11)
    # Link the decision KPI caches to the chosen base portfolio.
    pr=portfolio_row['CZE+ESP','base']
    dashboard.write_formula('A7',f'=Portfolios!G{pr}',fmt['kpi'],198099.31)
    dashboard.write_formula('E7',f'=Portfolios!E{pr}',fmt['kpi'],225000)
    dashboard.write_formula('I7',f'=Portfolios!F{pr}',fmt['kpi'],5)

    ws=sheet('Sensitivity',['Country','Boundary test','Volume uplift','Saving EUR/unit','Annual increment EUR','Provenance'],[13,26,18,21,25,100])
    for r,x in enumerate(m['sensitivity'],1):
        for j,k in enumerate(['country','test','volume_uplift','saving_eur_per_unit','incremental_contribution_eur','provenance']):val(ws,r,j,x[k],'pct' if j==2 else 'money' if j in [3,4] else 'wrap')
        ws.set_row(r,32)
    finish(ws,24,6)
    ws=sheet('Switching values',['Metric','Value','Meaning / held-constant assumptions'],[56,20,105])
    rows=[('CZE uplift to equal NLD base',m['recommendation']['switching_values']['cze_uplift_to_match_nld_base'],'NLD uplift remains 25%; normal returns/FX; unchanged savings/fixed costs.'),('CZE net-sales FX haircut to equal NLD',m['recommendation']['switching_values']['cze_fx_net_sales_haircut_to_match_nld_with_3pct_refund'],'Both at base 25%; both have additional refunds = 3% of gross sales; no cost recovery.'),('CZE net-sales FX haircut at break-even',m['recommendation']['switching_values']['cze_fx_net_sales_haircut_to_break_even_with_3pct_refund'],'CZE base volume, 3% refund shock; benchmark remains normal no-hub baseline.'),('CZE+ESP common uplift at break-even',m['recommendation']['switching_values']['cze_esp_common_uplift_to_break_even'],'Normal FX/returns; client savings; recurring cost included; capex excluded.')]
    rows +=[(r['country']+' individual volume break-even',r['break_even_uplift'],'Normal FX/returns; client saving and recurring fixed cost.') for r in m['thresholds']]
    for r,(a,b,c) in enumerate(rows,1):ws.write(r,0,a,fmt['wrap']);ws.write(r,1,b,fmt['pct']);ws.write(r,2,c,fmt['wrap']);ws.set_row(r,35)
    finish(ws,len(rows),3)

    for name,file in [('Exclusions','exclusions.csv'),('Revisions','revision_audit.csv'),('Returns','retained_returns.csv')]:
        rows=list(csv.DictReader((OUT/'audit'/file).open()));ws=sheet(name,list(rows[0]))
        for r,x in enumerate(rows,1):
            for j,v in enumerate(x.values()):ws.write(r,j,v,fmt['text'])
        finish(ws,len(rows),len(rows[0]))
    rows=list(csv.DictReader((ROOT/'evidence/raw/unit-costs.csv').open()));ws=sheet('Costs',list(rows[0]))
    for r,x in enumerate(rows,1):ws.write(r,0,x['sku']);ws.write(r,1,x['valid_from']);ws.write_number(r,2,float(x['unit_cost_eur']),fmt['money'])
    finish(ws,6,3)

    # Legible native Excel charts, also rendered independently as PNG/PDF assets.
    chart=wb.add_chart({'type':'column'})
    chart.add_series({'name':'2025 contribution EUR','categories':'=Countries!$A$2:$A$7','values':'=Countries!$I$2:$I$7','fill':{'color':teal},'border':{'none':True}})
    chart.set_title({'name':'2025 contribution by market'});chart.set_y_axis({'name':'EUR','num_format':'0,"k"','major_gridlines':{'visible':True,'line':{'color':'#E0E8EF'}}});chart.set_legend({'none':True});chart.set_size({'width':580,'height':310});chart.set_chartarea({'border':{'none':True}});dashboard.insert_chart('A15',chart)
    cs=sheet('Chart data',['Portfolio','Low EUR','Base EUR','High EUR','Stress EUR'],[22,22,22,22,22])
    for r,p in enumerate(['CZE+ESP','NLD+ESP','POL+ESP','ESP','DEFER'],1):
        cs.write(r,0,p)
        for j,sc in enumerate(['low','base','high','stress'],1):
            x=next(x for x in m['portfolios'] if x['portfolio']==p and x['scenario']==sc)
            formula(cs,r,j,f"=Portfolios!G{portfolio_row[p,sc]}",x['incremental_contribution_eur'])
    finish(cs,5,5)
    chart=wb.add_chart({'type':'column'})
    for j,color in enumerate(['#A7BDC7',teal,navy,gold],1):chart.add_series({'name':f"='Chart data'!${col(j)}$1",'categories':"='Chart data'!$A$2:$A$6",'values':f"='Chart data'!${col(j)}$2:${col(j)}$6",'fill':{'color':color},'border':{'none':True}})
    chart.set_title({'name':'Annual increment after recurring fixed cost'});chart.set_y_axis({'name':'EUR','num_format':'0,"k"'});chart.set_legend({'position':'bottom'});chart.set_size({'width':580,'height':330});chart.set_chartarea({'border':{'none':True}});dashboard.insert_chart('A32',chart)
    dashboard.merge_range('A50:L53','Source: synthetic client exports/options/policy, reconciled with archived ECB FX. Capex/payback are separate from annual contribution. Workbook market context preserves 2022–2024 World Bank values and source vintage; it does not establish demand.',fmt['sub'])
    for name in ['Guide','Sources','Quality','Monthly','Countries','Scenarios','Portfolios']:
        dashboard.write_url(54, ['Guide','Sources','Quality','Monthly','Countries','Scenarios','Portfolios'].index(name),f"internal:'{name}'!A1",fmt['link'],name)
    wb.close()
    print('Built deliverables/meridian_analysis.xlsx')

if __name__=='__main__':main()
