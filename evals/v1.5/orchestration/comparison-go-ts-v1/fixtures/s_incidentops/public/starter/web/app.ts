import {fetchIncidents, requestHeaders} from './api.js';
import {get, renderIncidents, renderSummary} from './view.js';
const value=(id:string)=>get<HTMLInputElement|HTMLSelectElement>(id).value;
async function refresh():Promise<void>{
  get('error').textContent='';
  const params=new URLSearchParams(); for(const key of ['status','severity','q']){const v=value(key);if(v)params.set(key,v)}
  try{const items=await fetchIncidents(params,requestHeaders(value('tenant'),value('role')));renderIncidents(items);renderSummary(items)}
  catch(e){get('error').textContent=String(e)}
}
for(const id of ['tenant','role','status','severity','q'])get(id).addEventListener('change',()=>void refresh());
get('refresh').addEventListener('click',()=>void refresh());void refresh();
