from pathlib import Path
import json
HERE=Path(__file__).resolve().parent;s=json.loads((HERE/'summary.json').read_text());rows=s['cells']
models=['gpt-6-sol-high','gpt-6-luna-max','gpt-6-luna-high','gpt-5.6-luna-max','gpt-5.6-luna-high','gpt-6-astra-xhigh']
lines=['# Per-cell observation and qualification tables','', 'One episode per cell. All raw first-pass outcomes remain in qualification-v1; diagnostics are separate. Token categories below are reported CLI fields.','']
for task,title in [('fullstack','Coding'),('consulting','Consulting')]:
 lines += ['## '+title,'','| Tuple | Arm | Minutes | Input / cached | Output / reasoning | Tool items / failed | Qualification |','| --- | --- | ---: | ---: | ---: | ---: | --- |']
 for model in models:
  for arm in ['vanilla','v14','v15']:
   r=next(r for r in rows if r['task']==task and r['tuple']==model and r['arm']==arm)
   if task=='fullstack':
    notes=[]
    if r['transport_error_in_original_api']:notes.append('burst transport failure; staged-body invariants pass')
    if not r['business_flow_pass']:notes.append('multi-line UI fails')
    if not r['mobile_ready_pass']:notes.append('mobile overflow')
    if r['login_form_visible_after_authentication']:notes.append('login form remains visible')
    if r['id'].endswith('gpt-5.6-luna-high-v15'):notes.append('price-field400 is contract ambiguity')
    verdict='; '.join(notes) or 'original critical API + restart + readiness flow pass'
   else:verdict=('core values match' if r['core_accounting_and_official_values_match'] else 'effective-date cost error')+'; '+('44/44 pair cases match' if r['material_pair_scenario_mismatches']==0 else '44/44 pair cases wrong')+f"; frozen score {r['strict_office_score']['passed']}/17"
   lines.append(f"| {model} | {arm} | {r['generation_wall_seconds']/60:.2f} | {r['input_tokens']:,} / {r['cached_input_tokens']:,} | {r['output_tokens']:,} / {r['reasoning_output_tokens']:,} | {r['tool_items']} / {r['failed_tool_items']} | {verdict} |")
 lines += ['']
lines += ['## Serial local performance at concurrency 8','','Read workload500 requests; write workload200 unique draft orders. Fresh store per concurrency. No concurrent benchmark. All32 measured workload batches returned only2xx. First-pass burst transport failures keep10 servers ineligible.','', '| Tuple | Arm | Read req/s | Read p95 ms | Write req/s | Write p95 ms |','| --- | --- | ---: | ---: | ---: | ---: |']
for model in models:
 for arm in ['vanilla','v14','v15']:
  r=next(r for r in rows if r['task']=='fullstack' and r['tuple']==model and r['arm']==arm)
  if not r['performance_eligible']:continue
  get=next(x for x in r['performance'] if x['concurrency']==8 and x['workload']=='inventory_get');post=next(x for x in r['performance'] if x['concurrency']==8 and x['workload']=='draft_order_post')
  lines.append(f"| {model} | {arm} | {get['requests_per_second']:,.0f} | {get['p95_ms']:.2f} | {post['requests_per_second']:,.0f} | {post['p95_ms']:.2f} |")
lines += ['', 'All per-request latencies/status/errors and concurrency1 results are retained in qualification-v1/results and the two declared runtime-correction results. These short local workloads do not establish production capacity or power-loss durability.','']
(HERE/'TABLES.md').write_text('\n'.join(lines))
