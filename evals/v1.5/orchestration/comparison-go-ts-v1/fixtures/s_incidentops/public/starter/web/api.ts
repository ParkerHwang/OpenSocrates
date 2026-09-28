export type Incident={incident_id:string,status:string,severity:string,latest_at:string,note:string};
export const requestHeaders=(tenant:string,role:string)=>({'X-Tenant':tenant,'X-Role':role});
export async function fetchIncidents(params:URLSearchParams,headers:Record<string,string>):Promise<Incident[]>{
 const res=await fetch(`/api/incidents?${params}`,{headers});if(!res.ok)throw new Error(`Request failed (${res.status})`);
 const body=await res.json() as {items:Incident[]};return body.items;
}
