"""Static descriptive figures from reviewed receipts; no quality-weighted ranking."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
HERE=Path(__file__).resolve().parent
s=json.loads((HERE/'summary.json').read_text());rows=s['cells']
models=['gpt-6-sol-high','gpt-6-luna-max','gpt-6-luna-high','gpt-5.6-luna-max','gpt-5.6-luna-high','gpt-6-astra-xhigh']
labels=['GPT-6 Sol\nhigh','GPT-6 Luna\nmax','GPT-6 Luna\nhigh','GPT-5.6 Luna\nmax','GPT-5.6 Luna\nhigh','GPT-6 Astra\nxhigh']
colors={'vanilla':'#5E7085','v14':'#D79C42','v15':'#087F8C'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
for field,title,filename in [('output_tokens','Reported output tokens, including reported reasoning','output-tokens.png'),('noncached_input_tokens','Reported input minus the cached subset','noncached-input.png')]:
 fig,axs=plt.subplots(2,1,figsize=(12,8),sharex=True,sharey=True)
 for ax,task,label in zip(axs,['fullstack','consulting'],['Full-stack development','Consulting']):
  for i,arm in enumerate(['vanilla','v14','v15']):
   vals=[next(r[field] for r in rows if r['task']==task and r['tuple']==m and r['arm']==arm)/1000 for m in models]
   bars=ax.bar(np.arange(6)+(i-1)*.25,vals,.23,color=colors[arm],label={'vanilla':'Vanilla Codex','v14':'OpenSocrates v1.4.0','v15':'OpenSocrates v1.5.0 RC'}[arm])
   ax.bar_label(bars,labels=[f'{v:.1f}' for v in vals],fontsize=8,padding=2)
  ax.set_title(label,loc='left',fontweight='bold');ax.set_ylabel('Thousand tokens');ax.set_ylim(0,max(r[field] for r in rows)/1000*1.18);ax.grid(axis='y',alpha=.16);ax.set_axisbelow(True)
 axs[-1].set_xticks(np.arange(6),labels);fig.legend(*axs[0].get_legend_handles_labels(),ncol=3,loc='upper left',bbox_to_anchor=(.075,.94),frameon=False)
 fig.suptitle(title,x=.08,ha='left',fontweight='bold',fontsize=15)
 fig.text(.08,.025,'One episode per bar. Descriptive usage, not billed cost or an equivalent-quality efficiency estimate.\nSource: 36 original call.json receipts; no added outcome episodes.',fontsize=9,color='#526170')
 fig.tight_layout(rect=(.03,.08,.995,.88));fig.savefig(HERE/filename,dpi=160);plt.close(fig)
perf=[r for r in rows if r.get('performance_eligible')]
perf.sort(key=lambda r:(models.index(r['tuple']),['vanilla','v14','v15'].index(r['arm'])))
fig,axs=plt.subplots(1,2,figsize=(13,6),sharey=True)
y=np.arange(len(perf))
for ax,work,title in zip(axs,['inventory_get','draft_order_post'],['Inventory GET (500 requests)','Draft order POST (200 requests)']):
 vals=[next(x['requests_per_second'] for x in r['performance'] if x['concurrency']==8 and x['workload']==work) for r in perf]
 bars=ax.barh(y,vals,color=[colors[r['arm']] for r in perf]);ax.bar_label(bars,labels=[f'{v:,.0f}' for v in vals],padding=4,fontsize=9);ax.set_xlim(0,max(vals)*1.16);ax.set_xlabel('Requests / second');ax.set_title(title,loc='left');ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
axs[0].set_yticks(y,[r['tuple'].replace('gpt-','GPT-')+' / '+r['arm'] for r in perf]);axs[0].invert_yaxis()
fig.suptitle('Local artifact performance: 8 eligible servers, concurrency 8',x=.05,ha='left',fontweight='bold')
fig.text(.05,.025,'Serial tests on Apple M5 / 10 cores / 32 GiB. All measured requests returned 2xx. Short fixed workloads.\nTen servers retain burst transport failures and were not benchmarked. No production SLA or causal model ranking.',fontsize=9,color='#526170')
fig.tight_layout(rect=(.015,.11,.99,.93));fig.savefig(HERE/'eligible-performance.png',dpi=160);plt.close(fig)
print('3 figures saved')
