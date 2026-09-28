export type Incident={incident_id:string,status:string,severity:string,latest_at:string,note:string,sequence:number};
export type Summary={total:number,open:number,acknowledged:number,resolved:number};
export const requestHeaders=(tenant:string,role:string)=>({'X-Tenant':tenant,'X-Role':role});
async function response<T>(res:Response):Promise<T>{if(!res.ok)throw new Error(`Request failed (${res.status})`);return await res.json() as T}
export async function fetchIncidents(params:URLSearchParams,headers:Record<string,string>):Promise<Incident[]>{
 const body=await response<{items:Incident[]}>(await fetch(`/api/incidents?${params}`,{headers}));return body.items;
}
export async function fetchSummary(params:URLSearchParams,headers:Record<string,string>):Promise<Summary>{
 return await response<Summary>(await fetch(`/api/summary?${params}`,{headers}));
}
export async function postAction(incident:Incident,kind:'ACK'|'RESOLVE'|'REOPEN',headers:Record<string,string>):Promise<void>{
 const body={event_id:crypto.randomUUID(),incident_id:incident.incident_id,sequence:incident.sequence+1,kind,occurred_at:new Date().toISOString(),severity:kind==='REOPEN'?incident.severity:undefined,note:''};
 await response(await fetch('/api/events',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:JSON.stringify(body)}));
}
