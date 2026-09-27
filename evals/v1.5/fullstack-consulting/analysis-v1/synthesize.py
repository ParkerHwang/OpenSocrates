"""Recompute descriptive matched comparisons; no overall quality score or causal claim."""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import csv,hashlib,json,statistics,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT));import summarize_observations as observer
read=lambda p:json.loads(p.read_text())
manifest=read(ROOT/'v2/manifest.json');view=observer.summarize();assert view['state_counts']=={'complete':36}
sem={r['cell']:r for r in read(HERE/'office-semantics.json')['cells']}
supp={r['cell']:r for r in read(HERE/'office-pair-workbook-checks.json')}
source={r['cell']:r for r in read(HERE/'source-collection.json')['cells']}
guidance={r['cell']:r for r in read(ROOT/'qualification-v1/guidance-delivery.json')['cells']}
rows=[]
for cell in manifest['cells']:
 name=cell['id'];r=read(ROOT/'v2/results'/name/'call.json');v=next(x for x in view['cells'] if x['id']==name);u=r['usage'];t=v['tools']
 row={**{k:cell[k] for k in ('id','task','tuple','model','effort','arm')},'subject_attempt':r['attempt'],'process_exit_code':r['exit_code'],'started_utc':r['started_utc'],'ended_utc':r['ended_utc'],'generation_wall_seconds':r['wall_seconds'],**u,'noncached_input_tokens':u['input_tokens']-u['cached_input_tokens'] if None not in (u['input_tokens'],u['cached_input_tokens']) else None,'tool_items':t['count'],'failed_tool_items':t['nonzero_or_failed'],'repeated_command_excess':t['repeated_command_hash_count'],'missing_tool_duration_items':t['missing_duration_count'],'public_messages':t['public_message_count'],'public_provider_error_events':len(r['errors']),'scheduler_regime':v['scheduler_regime'],'overlaps_parallel_amendment':r['started_utc']<'2026-09-27T10:10:37.270936+00:00'<r['ended_utc'],'peak_sampled_process_tree_rss_kib':v['peak_sampled_process_tree_rss_kib'],'peak_sampled_browser_tree_rss_kib':v['peak_sampled_browser_tree_rss_kib'],'source_room_gets':v['source_room_get_requests'],'billed_cost':r['billed_cost'],'backend_model_echo':r['backend_model_echo'],'native_memory':r['native_memory'],'product_memory_enrolled':r['product_memory_enrolled'],'protected_inputs_unchanged':r['protected_inputs_unchanged'],'package_members_unchanged':r['package_members_unchanged'],'specialist_delivery':guidance.get(name,{}).get('complete_body_output_counts'),'human_quality_score':None}
 if cell['task']=='fullstack':
  first=ROOT/'qualification-v1/results'/name;original=read(first/'result.json');effective=first
  replacement=ROOT/'qualification-diagnostic-v1/results'/name
  if replacement.exists():effective=replacement
  core=read(effective/'result.json');api=read(effective/'api.json');mobile=read(ROOT/'qualification-mobile-v1/browser'/name/'result.json')['groups'][0];browser=read(ROOT/'qualification-diagnostic-v3/browser'/name/'result.json')
  transport=next((p for p in (ROOT/'qualification-diagnostic-v1/transport'/name/'result.json',ROOT/'qualification-diagnostic-v2/transport'/name/'result.json') if p.exists()),None)
  tr=read(transport) if transport else None
  row.update({'initial_api':original.get('api'),'initial_harness_error':original.get('harness_error'),'api_after_setup_correction':core['api'],'api_failed_groups':[g for g in api['groups'] if not g['pass']],'restart_pass':core['restart'],'first_pass_browser':core.get('browser'),'readiness_browser_passed':browser['passed'],'readiness_browser_total':browser['total'],'readiness_browser_failed_groups':[g['name'] for g in browser['groups'] if not g['pass']],'business_flow_pass':next(g['pass'] for g in browser['groups'] if g['name']=='create_reserve_ship_return_flow'),'viewer_ready_readonly_pass':next(g['pass'] for g in browser['groups'] if g['name']=='viewer_workflow_read_only'),'mobile_ready_pass':mobile['pass'],'login_form_visible_after_authentication':mobile['details'].get('login_form_visible_after_authentication') if isinstance(mobile['details'],dict) else None,'transport_error_in_original_api':any('URLError' in str(g['details']) for g in api['groups'] if not g['pass']),'preconnected_state_diagnostic':{k:tr[k]['pass'] for k in ('reservations','idempotent_create')} if tr else None,'performance_eligible':core['performance_eligible'],'performance':core['performance'],'api_receipt':str((effective/'api.json').relative_to(ROOT))})
 else:
  sr=sem[name];strict=read(ROOT/'qualification-v1/results'/name/'office.json');core_ok=all(g['pass_'] for g in strict['groups'] if g['name'] in ('monthly_values','countries_values','fx_monthly_values','market_context_values'))
  covered=sr['covered_pair_scenarios'];bad=sr['failed_pair_scenarios']
  if name in supp:covered=supp[name]['total'];bad=sum(not r['pass'] for r in supp[name]['checks'])
  row.update({'strict_office_score':sr['strict_score_unchanged'],'core_accounting_and_official_values_match':core_ok,'pair_scenarios_covered':covered,'material_pair_scenario_mismatches':bad,'strict_shape_annotations':sr['shape_annotations'],'numeric_annotations':sr['numeric_annotations'],'recommendation_countries':sr['recommendation']['countries'],'all_13_substantive_source_files_preserved':all(source[name]['exact_archived_source_matches'][n] for n in source[name]['exact_archived_source_matches'] if n!='index.html')})
 rows.append(row)
ratios=[]
for task in ('fullstack','consulting'):
 for baseline in ('vanilla','v14'):
  pairs=[]
  for tup in dict.fromkeys(c['tuple'] for c in manifest['cells']):
   a=next(r for r in rows if r['task']==task and r['tuple']==tup and r['arm']=='v15');b=next(r for r in rows if r['task']==task and r['tuple']==tup and r['arm']==baseline)
   pairs.append({'tuple':tup,**{k:a[k]/b[k] if a[k] is not None and b[k] not in (None,0) else None for k in ('input_tokens','noncached_input_tokens','output_tokens','reasoning_output_tokens','tool_items','generation_wall_seconds')}})
  ratios.append({'task':task,'comparison':'v15/'+baseline,'paired_ratios':pairs,'median_of_six_ratios':{k:statistics.median(p[k] for p in pairs if p[k] is not None) for k in ('input_tokens','noncached_input_tokens','output_tokens','reasoning_output_tokens','tool_items','generation_wall_seconds')},'interpretation':'Descriptive one-episode ratios; unequal outcomes, scheduler overlap and provider errors prevent causal or equivalent-quality efficiency claims.'})
summary={'generated_utc':datetime.now(timezone.utc).isoformat(),'source_manifest_sha256':hashlib.sha256((ROOT/'v2/manifest.json').read_bytes()).hexdigest(),'outcome_episodes':36,'prior_setup_failures':36,'prior_outcome_episodes':0,'all_process_exit_zero':all(r['process_exit_code']==0 for r in rows),'new_outcome_episodes_in_qualification':0,'usage_totals':view['usage_totals'],'public_provider_error_events':sum(r['public_provider_error_events'] for r in rows),'public_tool_items':sum(r['tool_items'] for r in rows),'failed_public_tool_items':sum(r['failed_tool_items'] for r in rows),'coding_summary':{'cells':18,'restart_pass':sum(r.get('restart_pass',False) for r in rows),'business_flow_pass':sum(r.get('business_flow_pass',False) for r in rows),'viewer_ready_readonly_pass':sum(r.get('viewer_ready_readonly_pass',False) for r in rows),'mobile_ready_pass':sum(r.get('mobile_ready_pass',False) for r in rows),'login_form_remains_visible':sum(r.get('login_form_visible_after_authentication') is True for r in rows),'original_burst_transport_failures':sum(r.get('transport_error_in_original_api',False) for r in rows),'performance_eligible':sum(r.get('performance_eligible',False) for r in rows)},'consulting_summary':{'cells':18,'core_values_match':sum(r.get('core_accounting_and_official_values_match',False) for r in rows),'pair_arithmetic_match':sum(r.get('material_pair_scenario_mismatches')==0 and r.get('pair_scenarios_covered')==44 for r in rows),'sources_preserved':sum(r.get('all_13_substantive_source_files_preserved',False) for r in rows)},'limitations':['One episode per tuple/arm/task; no human scores or causal estimate.','Explicit installed-controller cue, hooks off, product memory unenrolled, English tasks.','All6 Astra episodes have client retry events; backend attempts and billed cost unavailable.','Generation concurrency changed during the cohort; latency not a clean speed comparison.','API burst failures retained; staged-connection diagnostics do not erase transport unreliability.','Raw frozen checker scores and semantic/readiness diagnostics kept distinct.','Visual review sampled pages/ranges; not every page or workbook interaction.','Performance uses short fixed local loopback workloads on eligible servers only; no production SLA or power-loss test.'],'cells':rows,'matched_ratios':ratios}
(HERE/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
flat=[]
compound_keys={k for r in rows for k,v in r.items() if isinstance(v,(dict,list))}
for r in rows:
 item={k:v for k,v in r.items() if k not in compound_keys}
 item['api_passed']=r.get('api_after_setup_correction',{}).get('passed');item['api_critical_pass']=r.get('api_after_setup_correction',{}).get('critical_pass');item['first_api_passed']=(r.get('initial_api') or {}).get('passed');item['office_strict_passed']=r.get('strict_office_score',{}).get('passed')
 item['specialist_complete_body_outputs']=sum(v for k,v in (r.get('specialist_delivery') or {}).items() if k!='router.en.md') if r.get('specialist_delivery') is not None else None
 for kind,label in [('inventory_get','read'),('draft_order_post','write')]:
  measurement=next((p for p in (r.get('performance') or []) if p['concurrency']==8 and p['workload']==kind),{})
  item['performance_'+label+'_rps_c8']=measurement.get('requests_per_second');item['performance_'+label+'_p95_ms_c8']=measurement.get('p95_ms')
 flat.append(item)
fields=list(dict.fromkeys(k for r in flat for k in r))
with (HERE/'cells.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fields,lineterminator="\n");w.writeheader();w.writerows(flat)
print(json.dumps({k:summary[k] for k in ('coding_summary','consulting_summary','public_provider_error_events','public_tool_items','failed_public_tool_items')},indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='paired_ratios'} for r in ratios],indent=2))
