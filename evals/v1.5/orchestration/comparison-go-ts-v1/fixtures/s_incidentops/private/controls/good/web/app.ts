import {fetchIncidents,fetchSummary,postAction,requestHeaders,type Incident} from './api.js';
import {get,renderIncidents,renderSummary} from './view.js';
const value=(id:string)=>get<HTMLInputElement|HTMLSelectElement>(id).value;
let serial=0;
async function refresh():Promise<void>{
 const current=++serial;get('error').textContent='';
 const params=new URLSearchParams();for(const key of ['status','severity','q']){const v=value(key);if(v)params.set(key,v)}
 const headers=requestHeaders(value('tenant'),value('role'));
 try{const [items,summary]=await Promise.all([fetchIncidents(params,headers),fetchSummary(params,headers)]);if(current!==serial)return;renderIncidents(items,value('role'),action);renderSummary(summary)}
 catch(e){if(current===serial)get('error').textContent=String(e)}
}
async function action(item:Incident,kind:'ACK'|'RESOLVE'|'REOPEN'):Promise<void>{
 if(value('role')!=='operator')return;
 try{await postAction(item,kind,requestHeaders(value('tenant'),value('role')));await refresh()}
 catch(e){get('error').textContent=String(e)}
}
for(const id of ['tenant','role','status','severity','q'])get(id).addEventListener('change',()=>void refresh());
get('refresh').addEventListener('click',()=>void refresh());void refresh();
