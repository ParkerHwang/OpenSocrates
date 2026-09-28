#!/usr/bin/env python3
"""Repeatable threaded read/write HTTP workload; reports latency percentiles and errors."""
import argparse, concurrent.futures, json, statistics, time, urllib.error, urllib.request, uuid
from collections import Counter

def call(base, method, path, token, body=None, key=None):
    headers={"Authorization":"Bearer "+token}
    if body is not None: headers["Content-Type"]="application/json"
    if key: headers["Idempotency-Key"]=key
    req=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    start=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=15) as r: r.read();status=r.status
    except urllib.error.HTTPError as e: e.read();status=e.code
    except Exception: status=0
    return (time.perf_counter()-start)*1000,status

def report(label, samples, elapsed):
    lat=[x for x,_ in samples]; errors=sum(1 for _,s in samples if s<200 or s>=300); statuses=Counter(s for _,s in samples)
    ordered=sorted(lat)
    p=lambda q:ordered[min(len(ordered)-1,int((len(ordered)-1)*q))]
    print(f"{label}: requests={len(samples)} errors={errors} statuses={dict(sorted(statuses.items()))} throughput={len(samples)/elapsed:.1f} req/s wall={elapsed:.3f}s mean={statistics.mean(lat):.2f}ms p50={p(.50):.2f}ms p95={p(.95):.2f}ms p99={p(.99):.2f}ms")

def main():
    a=argparse.ArgumentParser();a.add_argument("--base",default="http://127.0.0.1:8000");a.add_argument("--token",required=True);a.add_argument("--count",type=int,default=500);a.add_argument("--workers",type=int,default=16);args=a.parse_args()
    base=args.base.rstrip("/");readpaths=["/api/inventory","/api/dashboard","/api/orders?limit=20","/api/audit?limit=20"]
    def read(i):return call(base,"GET",readpaths[i%len(readpaths)],args.token)
    t=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool: reads=list(pool.map(read,range(args.count)))
    read_elapsed=time.perf_counter()-t
    report("read",reads,read_elapsed)
    def write(i):return call(base,"POST","/api/orders",args.token,{"client_ref":"load-"+str(uuid.uuid4()),"lines":[{"sku":"SAMPLE","quantity":1}]},"load-"+str(uuid.uuid4()))
    t=time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers,8)) as pool: writes=list(pool.map(write,range(args.count)))
    write_elapsed=time.perf_counter()-t
    report("write",writes,write_elapsed)

if __name__=="__main__":main()
