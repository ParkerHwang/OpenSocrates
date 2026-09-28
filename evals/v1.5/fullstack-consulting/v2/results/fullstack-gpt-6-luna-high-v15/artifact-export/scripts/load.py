#!/usr/bin/env python3
"""Repeatable concurrent local HTTP workload against a fresh DepotFlow DB."""
import argparse, concurrent.futures, json, os, platform, socket, statistics, subprocess, tempfile, threading, time, urllib.error, urllib.request, collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def port():
    s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return p
def req(base,path,method='GET',body=None,headers=None):
    h=headers or {}; data=json.dumps(body).encode() if body is not None else None
    if data is not None:h={**h,'Content-Type':'application/json'}
    r=urllib.request.Request(base+path,data=data,headers=h,method=method)
    with urllib.request.urlopen(r,timeout=20) as x:return x.status,json.loads(x.read())
def summary(samples,errors,elapsed):
    ordered=sorted(samples)
    return {'requests':len(samples)+errors,'successes':len(samples),'errors':errors,'elapsed_seconds':round(elapsed,4),'throughput_rps':round((len(samples)+errors)/elapsed,2),'latency_ms':{'mean':round(statistics.mean(samples),3) if samples else 0,'p50':round(ordered[int((len(ordered)-1)*.50)],3) if ordered else 0,'p95':round(ordered[int((len(ordered)-1)*.95)],3) if ordered else 0,'max':round(max(samples),3) if samples else 0}}
def main():
    a=argparse.ArgumentParser();a.add_argument('--reads',type=int,default=800);a.add_argument('--writes',type=int,default=200);a.add_argument('--concurrency',type=int,default=8);args=a.parse_args()
    if min(args.reads,args.writes)<0 or args.concurrency<1:raise SystemExit('reads/writes must be nonnegative and concurrency positive')
    p=port(); data=tempfile.mkdtemp(prefix='depotflow-load-',dir=ROOT);base=f'http://127.0.0.1:{p}';env=os.environ.copy();env.update(PORT=str(p),DATA_DIR=data,SEED_DEMO='1')
    child=subprocess.Popen([str(ROOT/'run.sh')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(150):
            try:req(base,'/api/health');break
            except Exception:time.sleep(.03)
        else:raise RuntimeError('server did not start')
        _,auth=req(base,'/api/session','POST',{'email':'operator@north.example','password':'DepotDemo!2026'});token=auth['token'];lock=threading.Lock();counter=iter(range(args.writes))
        def read(_):
            t=time.perf_counter()
            try:req(base,'/api/inventory',headers={'Authorization':'Bearer '+token});return ('read',(time.perf_counter()-t)*1000,False,'')
            except Exception as e:return ('read',(time.perf_counter()-t)*1000,True,type(e).__name__+': '+str(e))
        def write(_):
            with lock:i=next(counter)
            t=time.perf_counter()
            try:
                req(base,'/api/orders','POST',{'client_ref':f'load-{i:06d}','lines':[{'sku':'BOLT','quantity':1}]},{'Authorization':'Bearer '+token,'Idempotency-Key':f'load-key-{i}'})
                return ('write',(time.perf_counter()-t)*1000,False,'')
            except Exception as e:return ('write',(time.perf_counter()-t)*1000,True,type(e).__name__+': '+str(e))
        jobs=[(read,i) for i in range(args.reads)]+[(write,i) for i in range(args.writes)]
        start=time.perf_counter(); results=[]
        with concurrent.futures.ThreadPoolExecutor(args.concurrency) as pool:
            fs=[pool.submit(fn,i) for fn,i in jobs]
            for f in concurrent.futures.as_completed(fs):results.append(f.result())
        elapsed=time.perf_counter()-start
        reads=[x[1] for x in results if x[0]=='read' and not x[2]]; re=sum(x[2] for x in results if x[0]=='read')
        writes=[x[1] for x in results if x[0]=='write' and not x[2]]; we=sum(x[2] for x in results if x[0]=='write')
        errors=collections.Counter(x[3] for x in results if x[2])
        report={'environment':{'os':platform.platform(),'python':platform.python_version(),'logical_cpus':os.cpu_count(),'concurrency':args.concurrency,'seeded_database':'fresh SQLite WAL database','workload':'GET /api/inventory and POST /api/orders with unique tenant-local reference and idempotency key','reads_requested':args.reads,'writes_requested':args.writes},'combined':summary(reads+writes,re+we,elapsed),'read':summary(reads,re,elapsed),'write':summary(writes,we,elapsed),'error_details':dict(errors)}
        print(json.dumps(report,indent=2));
        if re or we:raise SystemExit(1)
    finally:
        child.terminate();child.wait(timeout=8)
        import shutil;shutil.rmtree(data,ignore_errors=True)
if __name__=='__main__':main()
