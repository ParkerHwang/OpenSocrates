#!/usr/bin/env python3
"""Repeatable local read/write benchmark. Start app with seeded DATA_DIR first."""
import argparse, concurrent.futures, json, statistics, time, urllib.error, urllib.request, uuid

def request(base,path,method='GET',token=None,data=None,key=None):
 h={};
 if token:h['Authorization']='Bearer '+token
 if key:h['Idempotency-Key']=key
 raw=None if data is None else json.dumps(data).encode()
 if raw is not None:h['Content-Type']='application/json'
 req=urllib.request.Request(base+path,data=raw,headers=h,method=method);t=time.perf_counter()
 try:
  with urllib.request.urlopen(req,timeout=15) as r: r.read();code=r.status
 except urllib.error.HTTPError as e:code=e.code;e.read()
 except Exception:code=0
 return (time.perf_counter()-t)*1000,code
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--base',default='http://127.0.0.1:8000');ap.add_argument('--requests',type=int,default=500);ap.add_argument('--concurrency',type=int,default=8);ap.add_argument('--email',default='operator@north.example');ap.add_argument('--password',default='DepotDemo!2026');a=ap.parse_args()
 token=json.loads(urllib.request.urlopen(urllib.request.Request(a.base+'/api/session',data=json.dumps({'email':a.email,'password':a.password}).encode(),headers={'Content-Type':'application/json'},method='POST')).read())['token']
 specs=[('read','GET','/api/inventory',None,None) if i%2==0 else ('write','POST','/api/orders',{'client_ref':'load-'+uuid.uuid4().hex,'lines':[{'sku':'SAMPLE','quantity':1}]},'load-'+uuid.uuid4().hex) for i in range(a.requests)]
 def run(spec):name,m,p,d,k=spec;return name,request(a.base,p,m,token,d,k)
 start=time.perf_counter()
 with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:results=list(pool.map(run,specs))
 elapsed=time.perf_counter()-start
 print(f'workload requests={a.requests} concurrency={a.concurrency} elapsed_s={elapsed:.3f} overall_rps={a.requests/elapsed:.1f}')
 for kind in ('read','write'):
  vals=[r for n,r in results if n==kind];lat=sorted(x[0] for x in vals);ok=sum(200<=x[1]<300 for x in vals)
  pct=lambda p:lat[min(len(lat)-1,int((len(lat)-1)*p))] if lat else 0
  print(f'{kind}: count={len(vals)} success={ok} errors={len(vals)-ok} rps={len(vals)/elapsed:.1f} latency_ms mean={statistics.mean(lat):.2f} p50={pct(.50):.2f} p95={pct(.95):.2f} p99={pct(.99):.2f}')
if __name__=='__main__':main()
