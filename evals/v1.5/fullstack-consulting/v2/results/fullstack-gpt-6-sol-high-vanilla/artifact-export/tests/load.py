"""Repeatable local HTTP workload: concurrent reads and unique order creations."""
import concurrent.futures
from collections import Counter
import http.client
import json
import os
import platform
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
READS = int(os.environ.get('LOAD_READS', '500'))
WRITES = int(os.environ.get('LOAD_WRITES', '100'))
CONCURRENCY = int(os.environ.get('LOAD_CONCURRENCY', '8'))
thread_state = threading.local()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def request(base, method, path, token=None, body=None, key=None):
    headers = {}
    if token: headers['Authorization'] = 'Bearer ' + token
    if body is not None:
        headers['Content-Type'] = 'application/json'
        if key: headers['Idempotency-Key'] = key
    req = Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:
        with urlopen(req,timeout=30) as response:
            return response.status,json.load(response)
    except HTTPError as exc:
        return exc.code,json.load(exc)
    except (URLError, OSError, TimeoutError) as exc:
        return 0,{'error':str(exc)}


def benchmark_request(port, method, path, token, body=None, key=None):
    if not hasattr(thread_state,'connection'):
        thread_state.connection=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
    headers={'Authorization':'Bearer '+token}
    if body is not None:
        headers['Content-Type']='application/json'
        headers['Idempotency-Key']=key
    try:
        thread_state.connection.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers)
        response=thread_state.connection.getresponse()
        return response.status,json.loads(response.read())
    except (OSError,TimeoutError,ValueError) as exc:
        thread_state.connection.close()
        del thread_state.connection
        return 0,{'error':str(exc)}


def percentile(values, pct):
    ordered=sorted(values)
    return round(ordered[min(len(ordered)-1,int((len(ordered)-1)*pct))],2)


def run_phase(tasks, worker):
    start=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results=list(pool.map(worker,tasks))
    elapsed=time.perf_counter()-start
    latencies=[r[1] for r in results]
    return {'requests':len(tasks),'concurrency':CONCURRENCY,'elapsed_seconds':round(elapsed,3),
            'throughput_rps':round(len(tasks)/elapsed,1),'latency_ms_p50':percentile(latencies,.5),
            'latency_ms_p95':percentile(latencies,.95),'latency_ms_max':round(max(latencies),2),
            'errors':sum(status not in (200,201) for status,*_ in results),
            'successes':sum(status in (200,201) for status,*_ in results),
            'error_types':dict(Counter(str(detail)[:120] for status,_,detail in results if status not in (200,201)))}


def main():
    if min(READS,WRITES,CONCURRENCY)<1: raise ValueError('LOAD_* values must be positive')
    port=free_port();base=f'http://127.0.0.1:{port}'
    with tempfile.TemporaryDirectory(dir=ROOT) as data_dir:
        env=os.environ.copy();env.update(PORT=str(port),DATA_DIR=data_dir,SEED_DEMO='1')
        proc=subprocess.Popen([str(ROOT/'run.sh')],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                try:
                    if request(base,'GET','/api/health')[0]==200: break
                except Exception: pass
                time.sleep(.05)
            status,session=request(base,'POST','/api/session',body={'email':'operator@north.example','password':'DepotDemo!2026'})
            if status!=200: raise RuntimeError('Login failed')
            token=session['token']
            def read(_):
                start=time.perf_counter();status,data=benchmark_request(port,'GET','/api/inventory',token)
                return status,(time.perf_counter()-start)*1000,data if status not in (200,201) else None
            def write(i):
                body={'client_ref':f'load-{i:06d}','lines':[{'sku':'SAMPLE','quantity':1}]}
                start=time.perf_counter();status,data=benchmark_request(port,'POST','/api/orders',token,body,f'load-{i:06d}')
                return status,(time.perf_counter()-start)*1000,data if status not in (200,201) else None
            reads=run_phase(range(READS),read)
            writes=run_phase(range(WRITES),write)
            status,dashboard=request(base,'GET','/api/dashboard',token)
            assert status==200 and dashboard['orders_by_status'].get('draft',0)==writes['successes']
            assert dashboard['inventory_units']==180 and dashboard['reserved_units']==0
            result={'environment':{'platform':platform.platform(),'python':platform.python_version(),'logical_cpus':os.cpu_count(),
                                   'server':'Python ThreadingHTTPServer + SQLite WAL, loopback'},
                    'method':'Fresh seeded SQLite store; persistent HTTP/1.1 connections per worker; GET /api/inventory then POST /api/orders with unique one-line SAMPLE references; each phase uses a fixed thread pool; client-side wall-clock latency includes HTTP and JSON; no warmup excluded.',
                    'reads':reads,'writes':writes,'postcondition':dashboard}
            print(json.dumps(result,indent=2))
            (ROOT/'evidence-load.json').write_text(json.dumps(result,indent=2)+'\n')
        finally:
            proc.terminate();proc.wait(timeout=5)


if __name__=='__main__': main()
