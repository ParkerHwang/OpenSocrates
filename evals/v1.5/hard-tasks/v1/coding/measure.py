#!/usr/bin/env python3
"""Bounded, serial cell meter. Invoke only after all model/build work finishes."""
import argparse
import concurrent.futures
import json
import pathlib
import sqlite3
import subprocess
import threading
import time
import uuid
from acceptance import Server, check, source_identity, subset

# Raw results include all starts, completions and window membership. A request
# that completes after measurement closes is drained and verified but is not
# credited as an in-window completion. Windows use monotonic wall time.
def window_flags(start, end, measured_start, measured_end):
    return {"started_in_window":measured_start <= start < measured_end,
            "completed_in_window":measured_start <= end < measured_end}

def quantile(values,p):
    if not values: return None
    data=sorted(values); return data[max(0,min(len(data)-1,__import__('math').ceil(p*len(data))-1))]

def process_sample(pid):
    try:
        wire=subprocess.check_output(["ps","-o","time=","-o","rss=","-p",str(pid)],text=True,timeout=1).split()
        clock=wire[0].split(":"); cpu=0.0
        for part in clock: cpu=cpu*60+float(part)
        return {"cpu_s":cpu,"rss_kib":int(wire[1])}
    except (OSError,subprocess.SubprocessError,ValueError,IndexError): return None

def result_stats(rows, begin, finish):
    in_starts=[r for r in rows if r["started_in_window"]]
    completed=[r for r in in_starts if r["completed_in_window"]]
    credited=[r for r in completed if r["success"]]
    latencies=[r["latency_s"] for r in in_starts]
    elapsed=finish-begin
    return {"window_s":elapsed,"attempts_started":len(in_starts),"carry_in_completions":sum(r["completed_in_window"] and not r["started_in_window"] for r in rows),"attempts_completed_in_window":len(completed),"successful_completions_in_window":len(credited),"attempts_failed":sum(not r["success"] for r in in_starts),"attempts_drained_after_window":sum(r["ended"]>=finish for r in in_starts),"throughput_success_rps":len(credited)/elapsed if elapsed>0 else None,"latency_s":{"p50":quantile(latencies,.5),"p95":quantile(latencies,.95),"p99":quantile(latencies,.99),"max":max(latencies) if latencies else None}}

def cell(binary,root,workload,concurrency,rep,warmup=1.0,duration=5.0,seed_db=None,seed_snapshot=None):
    name=f"{workload}-c{concurrency}-r{rep}"; directory=pathlib.Path(root)/name; directory.mkdir(parents=True)
    server=Server(binary,directory/"ledger.db",directory)
    rows=[]; lock=threading.Lock(); samples=[]; sampling_stop=threading.Event(); errors=[]
    result={"workload":workload,"concurrency":concurrency,"repetition":rep,"correctness":None,"stats":None,"resources":None,"raw_attempts":rows,"artifacts":str(directory)}
    sampler=None
    try:
        if seed_db is None: raise ValueError("populated seed database required")
        with sqlite3.connect(seed_db) as old, sqlite3.connect(server.db) as fresh: old.backup(fresh)
        server.start()
        baseline_entries=10002; baseline_version=5001
        read_path="/summary?snapshot="+str(seed_snapshot)
        barrier=threading.Barrier(concurrency+1)
        # Windows begin only when all workers are ready. No measuring startup.
        timing={}
        def sample_loop():
            while not sampling_stop.wait(.1):
                sample=process_sample(server.process.pid)
                if sample is not None: samples.append(dict(sample,monotonic=time.monotonic()))
        sampler=threading.Thread(target=sample_loop,daemon=True); sampler.start()
        def worker(index):
            iteration=0; barrier.wait()
            while True:
                started=time.monotonic()
                if started >= timing["finish"]: return
                phase="warmup" if started < timing["begin"] else "measured"
                key=f"meter_{index}_{iteration}"; iteration+=1
                request={"from":"a" if iteration%2 else "b","to":"b" if iteration%2 else "a","amount":1} if workload=="write" else None
                status,body=None,None
                try:
                    status,body=server.req("POST" if workload=="write" else "GET","/transfers" if workload=="write" else read_path,request,key=key if workload=="write" else None,record=False,timeout=3)
                    success=status==(201 if workload=="write" else 200)
                    if success:
                        if workload=="read": subset(body,{"totals":{"balance":2_000_000_000,"reserved":0,"available":2_000_000_000},"entry_count":baseline_entries})
                        else: subset(body,{"transfer":{"from":request["from"],"to":request["to"],"amount":1,"reversed":False}})
                    exception=None
                except Exception as exc:
                    success,exception=False,repr(exc)
                ended=time.monotonic()
                row={"worker":index,"iteration":iteration,"phase":phase,"started":started,"ended":ended,"latency_s":ended-started,"status":status,"success":success,"exception":exception,**window_flags(started,ended,timing["begin"],timing["finish"])}
                if workload=="write": row["key"]=key; row["request"]=request
                if not success: row["response"]=body
                with lock: rows.append(row)
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures=[pool.submit(worker,i) for i in range(concurrency)]
            now=time.monotonic(); timing.update(begin=now+warmup,finish=now+warmup+duration)
            before=process_sample(server.process.pid); barrier.wait()
            # Worker futures drain requests after the bounded start window.
            for future in futures: future.result()
        after=process_sample(server.process.pid)
        sampling_stop.set(); sampler.join(timeout=2)
        stats=result_stats(rows,timing["begin"],timing["finish"])
        stats.update({"warmup_s":warmup,"all_attempts_started":len(rows),"all_attempts_completed":len(rows),"all_successful":sum(r["success"] for r in rows),"all_failed":sum(not r["success"] for r in rows),"drain_s":max(0,max((r["ended"] for r in rows),default=timing["finish"])-timing["finish"]),"measured_start_monotonic":timing["begin"],"measured_end_monotonic":timing["finish"]})
        result["stats"]=stats
        result["resources"]={"cpu_s_warmup_measurement_drain":after["cpu_s"]-before["cpu_s"] if before and after else None,"rss_kib_sampled_peak":max((r["rss_kib"] for r in samples),default=None),"samples":samples,"scope":"server process only; sampled RSS is not guaranteed peak"}
        summary=server.summary(); a=server.state("a"); b=server.state("b")
        successful=[r for r in rows if r["success"]]
        delta=sum((-1 if r["request"]["from"]=="a" else 1) for r in successful) if workload=="write" else 0
        expected_count=baseline_entries+2*len(successful) if workload=="write" else baseline_entries
        subset(summary,{"totals":{"balance":2_000_000_000,"reserved":0,"available":2_000_000_000},"entry_count":expected_count})
        subset(a,{"balance":1_000_000_000+delta,"reserved":0,"version":baseline_version+len(successful) if workload=="write" else baseline_version})
        subset(b,{"balance":1_000_000_000-delta,"reserved":0,"version":baseline_version+len(successful) if workload=="write" else baseline_version})
        result["final_state"]={"summary":summary,"accounts":[a,b],"expected_entry_count":expected_count,"expected_a_delta":delta}
        check(all(r["success"] for r in rows),"one or more requests failed or violated response contract")
        result["correctness"]=True
    except Exception as exc:
        result["correctness"]=False; errors.append(repr(exc))
    finally:
        sampling_stop.set()
        if sampler: sampler.join(timeout=2)
        server.stop()
    result["errors"]=errors
    (directory/"cell.json").write_text(json.dumps(result,indent=2)); return result

def prepare_seed(binary,root):
    directory=pathlib.Path(root)/"seed"; directory.mkdir()
    server=Server(binary,directory/"original.db",directory)
    metadata={"ready":False,"entry_count":10002,"account_version":5001,"posting_count":5000,"api_batches":250,"error":None}
    try:
        server.start(); server.account("a",1_000_000_000); server.account("b",1_000_000_000)
        transfers=[{"from":"a" if i%2==0 else "b","to":"b" if i%2==0 else "a","amount":1} for i in range(20)]
        for i in range(250):
            result=server.write("/batches",{"transfers":transfers},"seed_"+str(i))
            check(len(result["transfers"])==20,"seed batch response count")
        subset(server.summary(),{"entry_count":10002,"totals":{"balance":2_000_000_000,"reserved":0,"available":2_000_000_000}})
        for name in ["a","b"]: subset(server.state(name),{"balance":1_000_000_000,"reserved":0,"version":5001})
        snapshot=server.summary()["snapshot"]
        metadata.update(ready=True,snapshot=snapshot)
    except Exception as exc: metadata["error"]=repr(exc)
    finally: server.stop()
    if metadata["ready"]:
        # SQLite backup incorporates any WAL pages without assuming a candidate
        # checkpoint policy. Every cell clones this exact populated snapshot.
        db=directory/"seed.db"
        with sqlite3.connect(server.db) as original, sqlite3.connect(db) as copy: original.backup(copy)
        metadata["database"]=str(db)
    (directory/"seed.json").write_text(json.dumps(metadata,indent=2)); return metadata

def measure(binary,output,acceptance=None,source=None,warmup=1.0,duration=5.0,repetitions=3):
    output=pathlib.Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    root=output.parent/(output.stem+"-artifacts-"+uuid.uuid4().hex[:8]); root.mkdir()
    identity=source_identity(binary,source)
    correctness=None
    if acceptance:
        report=json.loads(pathlib.Path(acceptance).read_text())
        if report.get("source_identity",{}).get("binary_sha256")==identity["binary_sha256"]:
            correctness=report.get("passed") is True and report.get("group_count")==28 and report.get("passed_count")==28 and len(report.get("groups",[]))==28 and len({g.get("name") for g in report.get("groups",[])})==28
    seed=prepare_seed(binary,root)
    cells=[]
    for workload in ["read","write"]:
        for concurrency in [1,16]:
            for rep in range(1,repetitions+1):
                if seed["ready"]:
                    cells.append(cell(binary,root,workload,concurrency,rep,warmup,duration,seed["database"],seed["snapshot"]))
                else:
                    cells.append({"workload":workload,"concurrency":concurrency,"repetition":rep,"correctness":None,"stats":None,"resources":None,"raw_attempts":[],"errors":["populated seed unavailable: "+str(seed["error"])]})
    result={"schema":"auditledger.measure.v1","source_identity":identity,"acceptance_passed":correctness,"interpretation":"eligible" if correctness is True and all(c.get("correctness") is True for c in cells) else "diagnostic_only","configuration":{"warmup_s":warmup,"duration_s":duration,"repetitions":repetitions,"workloads":["read","write"],"concurrencies":[1,16]},"seed":seed,"cells":cells}
    output.write_text(json.dumps(result,indent=2)); return result

def selfcheck():
    check(window_flags(9.9,10.1,10,15)=={"started_in_window":False,"completed_in_window":True},"warmup carry-over")
    check(window_flags(14.9,15.1,10,15)=={"started_in_window":True,"completed_in_window":False},"late drain")
    check(window_flags(15,15.1,10,15)=={"started_in_window":False,"completed_in_window":False},"exclusive window end")
    rows=[{"started_in_window":True,"completed_in_window":True,"success":True,"latency_s":.1,"ended":11},
          {"started_in_window":True,"completed_in_window":True,"success":False,"latency_s":.2,"ended":12},
          {"started_in_window":True,"completed_in_window":False,"success":True,"latency_s":.3,"ended":16}]
    rows.append({"started_in_window":False,"completed_in_window":True,"success":True,"latency_s":.4,"ended":10.2})
    stats=result_stats(rows,10,15)
    check(stats["attempts_started"]==3 and stats["attempts_failed"]==1 and stats["successful_completions_in_window"]==1,"all attempts accounted")
    check(stats["carry_in_completions"]==1,"warmup carry-in excluded")
    check(stats["throughput_success_rps"]==.2 and stats["latency_s"]["p95"]==.3,"throughput denominator and quantile")
    check(quantile([],.95) is None,"missing is null")
    check(result_stats([],10,15)["latency_s"]["p50"] is None,"empty latency is null")
    return {"passed":True,"checks":["boundary_windows","late_drain","failed_attempts","null_missing","quantiles"]}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("binary",nargs="?"); p.add_argument("--output",default="measure.json"); p.add_argument("--acceptance"); p.add_argument("--source"); p.add_argument("--selfcheck",action="store_true")
    a=p.parse_args()
    if a.selfcheck: print(json.dumps(selfcheck())); raise SystemExit(0)
    if not a.binary: p.error("binary required")
    r=measure(a.binary,a.output,a.acceptance,a.source); print(json.dumps({"cells":len(r["cells"]),"interpretation":r["interpretation"],"output":a.output}))
