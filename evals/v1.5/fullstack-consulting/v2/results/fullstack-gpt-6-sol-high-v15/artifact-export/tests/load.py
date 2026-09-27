"""Repeatable local HTTP read/write exercise. Run: python3 tests/load.py --reads 400 --writes 200 --concurrency 8"""
import argparse, concurrent.futures, json, os, platform, socket, statistics, subprocess, tempfile, time, urllib.error, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def free_port():
    s=socket.socket(); s.bind(('127.0.0.1',0)); p=s.getsockname()[1]; s.close(); return p
def request(base,method,path,body=None,token=None,key=None):
    headers={}
    if token: headers['Authorization']='Bearer '+token
    if body is not None:
        headers['Content-Type']='application/json'
        if key is not None: headers['Idempotency-Key']=key
    r=urllib.request.Request(base+path,method=method,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    start=time.perf_counter()
    try: response=urllib.request.urlopen(r,timeout=30)
    except urllib.error.HTTPError as e: response=e
    with response:
        result=json.load(response); status=response.status
    return status,result,(time.perf_counter()-start)*1000
def percentile(values,p):
    values=sorted(values); return round(values[min(len(values)-1,int((len(values)-1)*p))],2)
def phase(name,count,concurrency,fn):
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool: results=list(pool.map(fn,range(count)))
    elapsed=time.perf_counter()-start; latencies=[r[2] for r in results]
    output={'phase':name,'requests':count,'concurrency':concurrency,'seconds':round(elapsed,3),'rps':round(count/elapsed,1),'p50_ms':percentile(latencies,.5),'p95_ms':percentile(latencies,.95),'max_ms':round(max(latencies),2),'errors':sum(r[0]<200 or r[0]>=300 for r in results),'status_counts':{str(s):sum(r[0]==s for r in results) for s in sorted({r[0] for r in results})}}
    print(json.dumps(output)); return output
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--reads',type=int,default=400); ap.add_argument('--writes',type=int,default=200); ap.add_argument('--concurrency',type=int,default=8); args=ap.parse_args()
    if min(args.reads,args.writes,args.concurrency)<1: ap.error('counts and concurrency must be positive')
    with tempfile.TemporaryDirectory() as data_dir:
        port=free_port(); base=f'http://127.0.0.1:{port}'
        env={**os.environ,'PORT':str(port),'DATA_DIR':data_dir,'SEED_DEMO':'1'}
        process=subprocess.Popen([str(ROOT/'run.sh')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(100):
                try:
                    if request(base,'GET','/api/health')[0]==200: break
                except Exception: time.sleep(.05)
            else: raise RuntimeError('Server did not start')
            status,session,_=request(base,'POST','/api/session',{'email':'operator@north.example','password':'DepotDemo!2026'})
            if status!=200: raise RuntimeError('Login failed')
            token=session['token']
            print(json.dumps({'machine':platform.platform(),'processor':platform.processor(),'logical_cpus':os.cpu_count(),'python':platform.python_version(),'method':'HTTP over loopback; isolated temporary SQLite store; warm login; ThreadPoolExecutor; wall-clock phase throughput and client-observed latency; reads alternate inventory/dashboard; writes create unique one-line draft orders; no intentional errors'}))
            phase('reads',args.reads,args.concurrency,lambda i:request(base,'GET','/api/inventory' if i%2==0 else '/api/dashboard',token=token))
            phase('writes',args.writes,args.concurrency,lambda i:request(base,'POST','/api/orders',{'client_ref':f'load-{i}','lines':[{'sku':'SAMPLE','quantity':1}]},token=token,key=f'load-key-{i}'))
        finally:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill();process.wait()
            error=process.stderr.read().decode(); process.stderr.close()
            if error: print('server_stderr:',error)
