import type {Incident,Summary} from './api.js';
export const get=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T;
export function renderIncidents(items:Incident[],role:string,onAction:(incident:Incident,kind:'ACK'|'RESOLVE'|'REOPEN')=>void):void{
 const list=get('incidents');list.replaceChildren();
 for(const item of items){const row=document.createElement('article');row.className='incident';row.dataset.incidentId=item.incident_id;const text=document.createElement('span');text.textContent=`${item.incident_id} — ${item.status} — ${item.severity} — ${item.note}`;row.append(text);
  const actions=document.createElement('div');actions.className='actions';const kinds:('ACK'|'RESOLVE'|'REOPEN')[]=item.status==='open'?['ACK','RESOLVE']:item.status==='acknowledged'?['RESOLVE']:['REOPEN'];
  for(const kind of kinds){const button=document.createElement('button');button.type='button';button.dataset.action=kind;button.textContent=kind;button.disabled=role!=='operator';button.addEventListener('click',()=>onAction(item,kind));actions.append(button)}row.append(actions);list.append(row)}
 if(!items.length)list.textContent='No incidents';
}
export function renderSummary(summary:Summary):void{get('summary').textContent=`${summary.total} total · ${summary.open} open · ${summary.acknowledged} acknowledged · ${summary.resolved} resolved`}
