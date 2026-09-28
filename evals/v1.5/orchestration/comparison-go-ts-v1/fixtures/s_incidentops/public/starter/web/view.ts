import type {Incident} from './api.js';
export const get=<T extends HTMLElement>(id:string)=>document.getElementById(id) as T;
export function renderIncidents(items:Incident[]):void{
 const list=get('incidents');list.replaceChildren();
 for(const item of items){const row=document.createElement('article');row.className='incident';const text=document.createElement('span');text.textContent=`${item.incident_id} — ${item.status} — ${item.severity} — ${item.note}`;row.append(text);list.append(row)}
 if(!items.length)list.textContent='No incidents';
}
export function renderSummary(items:Incident[]):void{get('summary').textContent=`${items.length} incidents`}
