#!/usr/bin/env python3
"""Black-box AuditLedger correctness checks. No candidate implementation here."""
import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import pathlib
import socket
import sqlite3
import subprocess
import time
import traceback
import urllib.error
import urllib.request
import uuid

HERE = pathlib.Path(__file__).resolve().parent
GROUPS = []

def check(condition, message="assertion failed"):
    if not condition:
        raise AssertionError(message)

def subset(actual, expected, path=""):
    """Expected contract fields matter; extra response fields never false-fail."""
    if isinstance(expected, dict):
        check(isinstance(actual, dict), f"{path}: expected object, got {actual!r}")
        for key, value in expected.items():
            check(key in actual, f"{path}: missing {key}")
            subset(actual[key], value, path + "/" + key)
    elif isinstance(expected, list):
        check(isinstance(actual, list) and len(actual) == len(expected), f"{path}: array length/type")
        for i, (a, b) in enumerate(zip(actual, expected)):
            subset(a, b, path + f"/{i}")
    else:
        check(type(actual) is type(expected) and actual == expected, f"{path}: {actual!r} != {expected!r}")

def contract_projection(value, shape="account_response"):
    fields={
        "account":{"name":None,"balance":None,"reserved":None,"available":None,"version":None},
        "historical_account":{"name":None,"balance":None,"reserved":None,"available":None},
        "hold":{"id":None,"account":None,"amount":None,"state":None},
        "transfer":{"id":None,"from":None,"to":None,"amount":None,"reversed":None},
        "entry":{"seq":None,"account":None,"kind":None,"balance_delta":None,"reserved_delta":None,"operation_id":None,"legacy_id":None},
        "totals":{"balance":None,"reserved":None,"available":None},
    }
    roots={
        "account_response":{"account":"account"},
        "transfer_response":{"transfer":"transfer","accounts":"account"},
        "batch_response":{"transfers":"transfer","accounts":"account"},
        "release_response":{"hold":"hold","account":"account"},
        "reverse_response":{"transfer":"transfer","reversal":"transfer","accounts":"account"},
        "summary_response":{"snapshot":None,"accounts":"historical_account","totals":"totals","entry_count":None},
        "entries_response":{"entries":"entry","snapshot":None,"next_after":None,"has_more":None},
    }
    schema=roots[shape] if shape in roots else fields[shape]
    return {key:([contract_projection(x, child) for x in item] if isinstance(item,list) and child else contract_projection(item,child) if child else item)
            for key,item in value.items() if key in schema for child in [schema[key]]}

def semantic(value, shape="account_response"):
    return json.dumps(contract_projection(value,shape), sort_keys=True, separators=(",", ":"))

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]

class Server:
    def __init__(self, binary, db, root, label="server", timeout=10):
        self.binary = str(pathlib.Path(binary).resolve())
        self.db, self.root = pathlib.Path(db), pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.label, self.timeout, self.process, self.trace = label, timeout, None, []
        self.base = "http://127.0.0.1:" + str(free_port())
    def start(self):
        self.log = (self.root / (self.label + ".log")).open("ab")
        self.process = subprocess.Popen([self.binary, "--db", str(self.db), "--listen", self.base.split("//")[1]], stdout=self.log, stderr=self.log)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise RuntimeError(f"server exited {self.process.returncode}; see {self.label}.log")
            try:
                status, data = self.req("GET", "/health", tenant=None, record=False, timeout=.3)
                if status == 200 and data.get("ok") is True: return self
            except (OSError, ValueError, AttributeError):
                pass
            time.sleep(.04)
        raise TimeoutError("health readiness timeout")
    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try: self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=3)
        if hasattr(self, "log"): self.log.close()
        (self.root / (self.label + "-http.json")).write_text(json.dumps(self.trace, indent=2, ensure_ascii=False))
    def req(self, method, path, body=None, tenant="t", key=None, expected=None, error=None, raw=None, record=True, timeout=5):
        headers = {"Content-Type":"application/json"}
        if tenant is not None: headers["X-Tenant"] = tenant
        if key is not None: headers["Idempotency-Key"] = key
        payload = raw if raw is not None else (None if body is None else json.dumps(body).encode())
        request = urllib.request.Request(self.base + path, payload, headers, method=method)
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status, wire = response.status, response.read().decode()
        except urllib.error.HTTPError as exc:
            status, wire = exc.code, exc.read().decode()
        except Exception as exc:
            if record: self.trace.append({"method":method,"path":path,"headers":headers,"request":payload.decode(errors="replace") if payload else None,"exception":repr(exc)})
            raise
        try: data = json.loads(wire)
        except ValueError: data = {"_non_json":wire}
        if record: self.trace.append({"method":method,"path":path,"headers":headers,"request":payload.decode(errors="replace") if payload else None,"status":status,"response":data,"elapsed_s":time.monotonic()-started})
        if expected is not None: check(status == expected, f"{method} {path}: HTTP {status} != {expected}, {data}")
        if error is not None: subset(data, {"error":{"code":error}})
        return status, data
    def write(self, path, body, key=None, tenant="t", expected=201, error=None):
        return self.req("POST", path, body, tenant, key or uuid.uuid4().hex, expected, error)[1]
    def account(self, name, opening=100, tenant="t"):
        return self.write("/accounts", {"name":name,"opening":opening}, tenant=tenant)["account"]
    def state(self, name, tenant="t"):
        return self.req("GET", "/accounts/"+name, tenant=tenant, expected=200)[1]["account"]
    def summary(self, query="", tenant="t"):
        return self.req("GET", "/summary"+query, tenant=tenant, expected=200)[1]
    def entries(self, query="", tenant="t"):
        return self.req("GET", "/entries"+query, tenant=tenant, expected=200)[1]
    def transfer(self, amount=7, **kw):
        body={"from":"a","to":"b","amount":amount}; body.update(kw)
        return self.write("/transfers",body)

def group(name):
    def decorate(function): GROUPS.append((name,function)); return function
    return decorate

def seed(s, a=100, b=40):
    s.account("a",a); s.account("b",b)

def balance(s,name,balance,reserved=0,version=None,tenant="t"):
    expected={"name":name,"balance":balance,"reserved":reserved,"available":balance-reserved}
    if version is not None: expected["version"]=version
    subset(s.state(name,tenant),expected)

def ledger_consistent(s, tenant="t"):
    page=s.entries("?limit=100",tenant)
    rows=list(page["entries"]); snapshot=page["snapshot"]
    while page["has_more"]:
        page=s.entries(f"?limit=100&after={page['next_after']}&snapshot={snapshot}",tenant)
        rows.extend(page["entries"])
    seqs=[r["seq"] for r in rows]
    check(seqs==sorted(set(seqs)) and all(type(x) is int and x>0 for x in seqs),"entry sequences")
    sums={}
    for row in rows:
        check(row["kind"] in {"opening","transfer","hold","capture","release","reversal"},"entry kind")
        check(isinstance(row["operation_id"],str) and row["operation_id"],"operation id")
        check(type(row["balance_delta"]) is int and type(row["reserved_delta"]) is int,"integer deltas")
        v=sums.setdefault(row["account"],[0,0]); v[0]+=row["balance_delta"]; v[1]+=row["reserved_delta"]
    accounts=[{"name":n,"balance":v[0],"reserved":v[1],"available":v[0]-v[1]} for n,v in sorted(sums.items())]
    total_b=sum(v[0] for v in sums.values()); total_r=sum(v[1] for v in sums.values())
    subset(s.summary(f"?snapshot={snapshot}",tenant),{"snapshot":snapshot,"accounts":accounts,"entry_count":len(rows),"totals":{"balance":total_b,"reserved":total_r,"available":total_b-total_r}})
    for acc in accounts: subset(s.state(acc["name"],tenant),acc)
    return rows

@group("01_empty_health_and_summary")
def empty(s):
    subset(s.summary(),{"snapshot":0,"accounts":[],"entry_count":0,"totals":{"balance":0,"reserved":0,"available":0}})
    subset(s.entries(),{"snapshot":0,"entries":[],"next_after":0,"has_more":False})

@group("02_account_opening_zero_and_duplicate")
def accounts(s):
    s.account("a",0); balance(s,"a",0,version=1)
    s.write("/accounts",{"name":"a","opening":9},expected=409,error="exists")
    rows=ledger_consistent(s); check(len(rows)==1 and rows[0]["balance_delta"]==0,"zero opening entry")

@group("03_required_body_and_integer_validation")
def required(s):
    for raw in [b"",b"null",b"[]",b"{}",b'{"name":"a"}',b'{"name":"a","opening":null}',b'{"name":"a","opening":true}',b'{"name":"a","opening":1.5}',b'{"name":"a","opening":-1}',b'{"name":"a","opening":1000000001}',b'{"name":"a","opening":0,"extra":1}',b'{"name":"a","opening":0} {}']:
        s.req("POST","/accounts",key=uuid.uuid4().hex,raw=raw,expected=400,error="invalid")
    subset(s.summary(),{"entry_count":0})

@group("04_tenant_and_key_validation")
def headers(s):
    for tenant,key in [(None,"k"),("bad space","k"),("x"*41,"k"),("t",None),("t","bad space"),("t","x"*81)]:
        s.req("POST","/accounts",{"name":"a","opening":1},tenant,key,expected=400,error="invalid")
    s.req("GET","/summary",tenant=None,expected=400,error="invalid")

@group("05_tenant_isolation_same_names_and_keys")
def isolation(s):
    s.write("/accounts",{"name":"a","opening":100},"shared","t")
    s.write("/accounts",{"name":"a","opening":3},"shared","u")
    s.account("b",0); transfer=s.transfer()["transfer"]
    s.req("GET","/accounts/b",tenant="u",expected=404,error="not_found")
    s.write("/transfers/"+transfer["id"]+"/reverse",{},tenant="u",expected=404,error="not_found")
    balance(s,"a",3,tenant="u"); ledger_consistent(s,"u")

@group("06_single_transfer_versions_and_entries")
def transfer(s):
    seed(s); result=s.transfer(7,from_version=1,to_version=1)
    subset(result,{"transfer":{"from":"a","to":"b","amount":7,"reversed":False},"accounts":[{"name":"a","balance":93,"version":2},{"name":"b","balance":47,"version":2}]})
    rows=ledger_consistent(s); check([r["balance_delta"] for r in rows]==[100,40,-7,7],"posting deltas")

@group("07_transfer_invalid_and_insufficient")
def transfer_invalid(s):
    seed(s)
    bodies=[{}, {"from":"a","to":"b"},{"from":"a","to":"b","amount":0},{"from":"a","to":"b","amount":True},{"from":"a","to":"a","amount":1},{"from":"a","to":"b","amount":1,"from_version":0},{"from":"a","to":"b","amount":1,"to_version":None},{"from":"a","to":"b","amount":1000000001}]
    for body in bodies: s.write("/transfers",body,expected=400,error="invalid")
    s.write("/transfers",{"from":"a","to":"b","amount":101},expected=409,error="insufficient")
    s.write("/transfers",{"from":"missing","to":"b","amount":101},expected=404,error="not_found")
    balance(s,"a",100,version=1); subset(s.summary(),{"entry_count":2})

@group("08_idempotency_semantic_replay")
def retry(s):
    seed(s); body={"from":"a","to":"b","amount":9,"from_version":1,"to_version":1}
    first=s.write("/transfers",body,"retry")
    s.transfer(3)
    raw=b'{ "to_version": 1, "amount": 9, "to": "b", "from": "a", "from_version": 1 }'
    again=s.req("POST","/transfers",key="retry",raw=raw,expected=201)[1]
    check(semantic(first,"transfer_response")==semantic(again,"transfer_response"),"replay original result")
    balance(s,"a",88,version=3); subset(s.summary(),{"entry_count":6})

@group("09_idempotency_conflict_and_failed_key_reuse")
def key_conflict(s):
    seed(s); body={"from":"a","to":"b","amount":9}
    s.write("/transfers",body,"fixed")
    s.write("/transfers",dict(body,amount=8),"fixed",expected=409,error="idempotency_conflict")
    s.write("/holds",{"account":"a","amount":9},"fixed",expected=409,error="idempotency_conflict")
    s.write("/transfers",dict(body,amount=100),"unused",expected=409,error="insufficient")
    s.write("/transfers",body,"unused")
    balance(s,"a",82,version=3)

@group("10_optimistic_stale_atomicity")
def stale(s):
    seed(s); s.transfer(4)
    s.write("/transfers",{"from":"a","to":"b","amount":5,"from_version":1},expected=409,error="version_conflict")
    s.write("/transfers",{"from":"a","to":"b","amount":5,"to_version":1},expected=409,error="version_conflict")
    balance(s,"a",96,version=2); balance(s,"b",44,version=2); subset(s.summary(),{"entry_count":4})

@group("11_batch_sequential_versions_and_replay")
def batch(s):
    seed(s); body={"transfers":[{"from":"a","to":"b","amount":10,"from_version":1},{"from":"b","to":"a","amount":3,"from_version":2,"to_version":2}]}
    first=s.write("/batches",body,"batch")
    subset(first,{"accounts":[{"name":"a","balance":93,"version":3},{"name":"b","balance":47,"version":3}]})
    check(len(first["transfers"])==2,"batch ids")
    check(semantic(first,"batch_response")==semantic(s.write("/batches",body,"batch"),"batch_response"),"batch retry")
    check(len(ledger_consistent(s))==6,"batch entries")

@group("12_batch_rollback_late_failure")
def rollback(s):
    seed(s); before=s.summary()
    body={"transfers":[{"from":"a","to":"b","amount":10},{"from":"b","to":"a","amount":1000}]}
    s.write("/batches",body,"retrybatch",expected=409,error="insufficient")
    check(semantic(s.summary(),"summary_response")==semantic(before,"summary_response"),"late batch failure rollback")
    balance(s,"a",100,version=1)
    body["transfers"][1]["amount"]=2
    s.write("/batches",body,"retrybatch"); balance(s,"a",92,version=3)

@group("13_batch_limits_and_staged_conflict")
def batch_limits(s):
    seed(s); item={"from":"a","to":"b","amount":1}
    for body in [{},{"transfers":[]},{"transfers":[item]*21},{"transfers":[item,{}]}]:
        s.write("/batches",body,expected=400,error="invalid")
    s.write("/batches",{"transfers":[dict(item,from_version=1),dict(item,from_version=1)]},expected=409,error="version_conflict")
    subset(s.summary(),{"entry_count":2}); balance(s,"a",100,version=1)

@group("14_hold_reservation_blocks_spending")
def holds(s):
    seed(s); result=s.write("/holds",{"account":"a","amount":80,"version":1})
    subset(result,{"hold":{"account":"a","amount":80,"state":"active"},"account":{"balance":100,"reserved":80,"available":20,"version":2}})
    s.write("/transfers",{"from":"a","to":"b","amount":21},expected=409,error="insufficient")
    s.write("/holds",{"account":"a","amount":21},expected=409,error="insufficient")
    s.transfer(20); balance(s,"a",80,80,3); ledger_consistent(s)

@group("15_capture_and_terminal_hold")
def capture(s):
    seed(s); hold=s.write("/holds",{"account":"a","amount":30})["hold"]
    path="/holds/"+hold["id"]+"/capture"
    result=s.write(path,{"to":"b","from_version":2,"to_version":1},expected=200)
    subset(result,{"hold":{"state":"captured"},"transfer":{"from":"a","to":"b","amount":30}})
    balance(s,"a",70,0,3); balance(s,"b",70,0,2)
    s.write(path,{"to":"b"},expected=409,error="terminal")
    s.write("/holds/"+hold["id"]+"/release",{},expected=409,error="terminal")
    rows=ledger_consistent(s); check([r["reserved_delta"] for r in rows]==[0,0,30,-30,0],"capture reservations")

@group("16_release_replay_and_stale_version")
def release(s):
    seed(s); hold=s.write("/holds",{"account":"a","amount":30})["hold"]
    path="/holds/"+hold["id"]+"/release"
    s.write(path,{"version":1},expected=409,error="version_conflict")
    result=s.write(path,{"version":2},"release",expected=200)
    check(semantic(result,"release_response")==semantic(s.write(path,{"version":2},"release",expected=200),"release_response"),"release retry")
    s.write(path,{},expected=409,error="terminal")
    balance(s,"a",100,0,3); ledger_consistent(s)

@group("17_hold_input_and_capture_rollback")
def hold_invalid(s):
    seed(s)
    for body in [{},{"account":"a","amount":0},{"account":"a","amount":1,"version":None}]:
        s.write("/holds",body,expected=400,error="invalid")
    hold=s.write("/holds",{"account":"a","amount":30})["hold"]
    path="/holds/"+hold["id"]+"/capture"
    s.write(path,{"to":"a"},expected=400,error="invalid")
    s.write(path,{"to":"absent"},expected=404,error="not_found")
    s.write(path,{"to":"b","to_version":9},expected=409,error="version_conflict")
    balance(s,"a",100,30,2); subset(s.summary(),{"entry_count":3})

@group("18_reverse_compensation_and_terminal")
def reverse(s):
    seed(s); transfer=s.transfer(20)["transfer"]
    path="/transfers/"+transfer["id"]+"/reverse"
    result=s.write(path,{"from_version":2,"to_version":2},"reverse",expected=200)
    subset(result,{"transfer":{"id":transfer["id"],"reversed":True},"reversal":{"from":"b","to":"a","amount":20,"reversed":False}})
    check(semantic(result,"reverse_response")==semantic(s.write(path,{"from_version":2,"to_version":2},"reverse",expected=200),"reverse_response"),"reverse replay")
    s.write(path,{},expected=409,error="terminal")
    s.write("/transfers/"+result["reversal"]["id"]+"/reverse",{},expected=409,error="terminal")
    balance(s,"a",100,version=3); balance(s,"b",40,version=3)
    rows=ledger_consistent(s); check([r["balance_delta"] for r in rows]==[100,40,-20,20,-20,20],"compensating entries")

@group("19_reverse_available_funds_and_capture")
def reverse_funds(s):
    seed(s,100,0); transfer=s.transfer(20)["transfer"]
    h=s.write("/holds",{"account":"b","amount":20})["hold"]
    path="/transfers/"+transfer["id"]+"/reverse"
    s.write(path,{},"funds",expected=409,error="insufficient")
    cap=s.write("/holds/"+h["id"]+"/capture",{"to":"a"},expected=200)["transfer"]
    s.write("/transfers/"+cap["id"]+"/reverse",{},expected=200)
    s.write(path,{},"funds",expected=200)
    balance(s,"a",100); balance(s,"b",0); ledger_consistent(s)

@group("20_snapshot_pagination_intervening_writes")
def pagination(s):
    seed(s); s.transfer(9); first=s.entries("?limit=1")
    snap=first["snapshot"]; historical=s.summary(f"?snapshot={snap}")
    s.transfer(3); s.write("/holds",{"account":"a","amount":4})
    rows=list(first["entries"]); page=first
    while page["has_more"]:
        page=s.entries(f"?limit=1&after={page['next_after']}&snapshot={snap}"); rows.extend(page["entries"])
        check(len(rows)<=4,"pagination did not advance")
    check(len(rows)==4 and all(r["seq"]<=snap for r in rows),"frozen pagination")
    check(semantic(historical,"summary_response")==semantic(s.summary(f"?snapshot={snap}"),"summary_response"),"historical summary changed")
    subset(historical,{"entry_count":4,"totals":{"balance":140,"reserved":0,"available":140}})
    ledger_consistent(s)

@group("21_snapshot_partial_operation_and_query_validation")
def query_validation(s):
    seed(s); s.transfer(9); rows=s.entries()["entries"]
    snap=rows[2]["seq"]
    subset(s.summary(f"?snapshot={snap}"),{"accounts":[{"name":"a","balance":91},{"name":"b","balance":40}],"totals":{"balance":131,"reserved":0,"available":131},"entry_count":3})
    for path in ["/entries?after=-1","/entries?limit=0","/entries?limit=101","/entries?limit=x","/entries?snapshot=-1","/entries?snapshot=999999","/entries?after=9&snapshot=0","/entries?wat=1","/summary?snapshot=1.5","/summary?wat=1"]:
        s.req("GET",path,expected=400,error="invalid")
    subset(s.entries("?snapshot=0"),{"entries":[],"snapshot":0,"next_after":0,"has_more":False})

@group("22_restart_persistence_of_state_and_retries")
def restart(s):
    seed(s); first=s.write("/transfers",{"from":"a","to":"b","amount":12},"persist")
    hold=s.write("/holds",{"account":"a","amount":8})["hold"]
    summary=s.summary(); s.stop(); s.start()
    check(semantic(summary,"summary_response")==semantic(s.summary(),"summary_response"),"restart state")
    check(semantic(first,"transfer_response")==semantic(s.write("/transfers",{"from":"a","to":"b","amount":12},"persist"),"transfer_response"),"restart retry")
    s.write("/holds/"+hold["id"]+"/release",{},expected=200); ledger_consistent(s)

@group("23_concurrent_identical_key_one_effect")
def concurrent_retry(s):
    seed(s); body={"from":"a","to":"b","amount":8}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        results=list(pool.map(lambda _:s.write("/transfers",body,"race"),range(24)))
    check(len({semantic(r,"transfer_response") for r in results})==1,"concurrent replay mismatch")
    balance(s,"a",92,version=2); subset(s.summary(),{"entry_count":4})

@group("24_two_process_writers_no_lost_updates")
def two_process(s):
    seed(s,1000,1000); other=Server(s.binary,s.db,s.root,"second").start()
    try:
        def post(i):
            server=s if i%2==0 else other
            body={"from":"a" if i%3 else "b","to":"b" if i%3 else "a","amount":1}
            return server.write("/transfers",body,"parallel"+str(i))
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            results=list(pool.map(post,range(96)))
        check(len({r["transfer"]["id"] for r in results})==96,"unique transfer IDs")
        balance(s,"a",968,version=97); balance(s,"b",1032,version=97)
        subset(s.summary(),{"entry_count":194,"totals":{"balance":2000,"reserved":0,"available":2000}})
        ledger_consistent(s)
    finally: other.stop()

@group("25_two_process_version_compare_and_hold_overspend")
def conditional_race(s):
    seed(s,10,0); other=Server(s.binary,s.db,s.root,"second").start()
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(server.req,"POST","/transfers",{"from":"a","to":"b","amount":1,"from_version":1},"t","v"+str(i)) for i,server in enumerate([s,other])]
            results=[f.result() for f in futures]
        check(sorted(r[0] for r in results)==[201,409],"CAS exactly one winner")
        subset(next(r[1] for r in results if r[0]==409),{"error":{"code":"version_conflict"}})
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(server.req,"POST","/holds",{"account":"a","amount":7},"t","h"+str(i)) for i,server in enumerate([s,other])]
            results=[f.result() for f in futures]
        check(sorted(r[0] for r in results)==[201,409],"reservation exactly one winner")
        subset(next(r[1] for r in results if r[0]==409),{"error":{"code":"insufficient"}})
        balance(s,"a",9,7,3); ledger_consistent(s)
    finally: other.stop()

def legacy_data(alternate=False):
    if not alternate: return json.loads((HERE/"starter/legacy/fixture.json").read_text())
    return {"accounts":[["old","zeta",51],["old","eta",24],["u","eta",9]],"movements":[[41,"old","zeta","eta",6],[44,"old","eta","zeta",2]],"notes":[["custom","\u0000 durable 🧪\n"],["empty",""]]}

def legacy_rows(db):
    with sqlite3.connect(db) as conn:
        return {table:conn.execute("SELECT * FROM "+table+" ORDER BY 1,2").fetchall() for table in ["legacy_accounts","legacy_movements","legacy_notes"]}

def produce_legacy(db,data):
    fixture=pathlib.Path(db).with_suffix(".json"); fixture.write_text(json.dumps(data,ensure_ascii=False))
    spec=importlib.util.spec_from_file_location("producer",HERE/"starter/legacy/produce.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.produce(str(db),str(fixture))

def verify_legacy(s,data,before):
    movements=data["movements"]
    for tenant,name,final in data["accounts"]:
        count=sum(tenant==m[1] and name in m[2:4] for m in movements)
        balance(s,name,final,0,1+count,tenant)
    for tenant in sorted({a[0] for a in data["accounts"]}):
        rows=ledger_consistent(s,tenant)
        check(len(rows)==sum(a[0]==tenant for a in data["accounts"])+2*sum(m[1]==tenant for m in movements),"migration entry count")
        opening_rows=[r for r in rows if r["kind"]=="opening"]
        check([r["account"] for r in opening_rows]==sorted(a[1] for a in data["accounts"] if a[0]==tenant),"migration opening order")
        check(all(r["kind"]=="opening" for r in rows[:len(opening_rows)]),"openings precede movements")
        imported=[r for r in rows if r["kind"]=="transfer"]
        expected_pairs=[(m[0],m[2],-m[4]) for m in sorted(movements) if m[1]==tenant]
        check([(r["legacy_id"],r["account"],r["balance_delta"]) for r in imported[::2]]==expected_pairs,"legacy movement source/order")
        check([(r["legacy_id"],r["account"],r["balance_delta"]) for r in imported[1::2]]==[(m[0],m[3],m[4]) for m in sorted(movements) if m[1]==tenant],"legacy movement destination/order")
        openings={a[1]:a[2] for a in data["accounts"] if a[0]==tenant}
        for _,t,source,target,units in movements:
            if t==tenant: openings[source]+=units; openings[target]-=units
        actual={r["account"]:r["balance_delta"] for r in rows if r["kind"]=="opening"}
        check(actual==openings,"independent inferred opening oracle")
        check(sorted({r.get("legacy_id") for r in rows if r["kind"]=="transfer"})==sorted(m[0] for m in movements if m[1]==tenant),"legacy provenance IDs")
    check(legacy_rows(s.db)==before,"legacy source values changed")
    with sqlite3.connect(s.db) as conn: check(conn.execute("PRAGMA user_version").fetchone()[0]==2,"migration version")

@group("26_genuine_legacy_and_restart_preservation")
def migration(s):
    # runner prepares old database before first startup for this group.
    data=legacy_data(); before=s.legacy_before
    verify_legacy(s,data,before); old=s.summary(tenant="old"); s.stop(); s.start()
    check(semantic(old,"summary_response")==semantic(s.summary(tenant="old"),"summary_response"),"migration repeated")
    rows=s.entries(tenant="old")["entries"]; entry=next(r for r in rows if r.get("legacy_id")==7)
    s.write("/transfers/"+entry["operation_id"]+"/reverse",{},tenant="old",expected=200)
    balance(s,"alpha",103,tenant="old"); balance(s,"beta",17,tenant="old")
    check(legacy_rows(s.db)==before,"source changed after reverse")

@group("27_alternate_legacy_simultaneous_start")
def alternate_migration(s):
    other=Server(s.binary,s.db,s.root,"second").start()
    try: verify_legacy(s,legacy_data(True),s.legacy_before)
    finally: other.stop()

@group("28_routes_names_missing_objects")
def routes(s):
    for name in ["", "bad/name", "space name", "x"*41]:
        s.write("/accounts",{"name":name,"opening":1},expected=400,error="invalid")
    s.req("GET","/missing",expected=404,error="not_found")
    s.req("GET","/accounts/missing",expected=404,error="not_found")
    s.write("/holds/absent/release",{},expected=404,error="not_found")
    s.write("/transfers/absent/reverse",{},expected=404,error="not_found")
    status,data=s.req("PUT","/accounts",{"name":"a","opening":1},key="method")
    check(status in (404,405),"wrong method")


def source_identity(binary,source=None):
    result={"binary_sha256":hashlib.sha256(pathlib.Path(binary).read_bytes()).hexdigest(),"binary":str(pathlib.Path(binary).resolve())}
    if source:
        root=pathlib.Path(source); files=[]
        for path in sorted(root.rglob("*")):
            if path.is_file() and ".git" not in path.parts and (path.suffix in (".go",".md") or path.name in ("go.mod","go.sum")):
                files.append([str(path.relative_to(root)),hashlib.sha256(path.read_bytes()).hexdigest()])
        result["source_files"]=files
        result["source_tree_sha256"]=hashlib.sha256(json.dumps(files,separators=(",",":")).encode()).hexdigest()
    return result

def run_checks(binary, output, source=None, startup_timeout=10, only=None):
    """Run independently isolated groups; output is a JSON filename."""
    output=pathlib.Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    root=output.parent/(output.stem+"-artifacts-"+uuid.uuid4().hex[:8]); root.mkdir()
    identity=source_identity(binary,source); results=[]
    for name,function in GROUPS:
        if only and name not in only: continue
        directory=root/name; directory.mkdir(); db=directory/"ledger.db"
        server=Server(binary,db,directory,timeout=startup_timeout)
        started=time.monotonic()
        try:
            if name.startswith(("26_","27_")):
                produce_legacy(db,legacy_data(name.startswith("27_"))); server.legacy_before=legacy_rows(db)
            if name.startswith("27_"):
                # Race the schema transition itself, not just later reads.
                peer=Server(binary,db,directory,"migration-peer",startup_timeout)
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                        futures=[pool.submit(x.start) for x in [server,peer]]
                        for future in futures: future.result()
                finally: peer.stop()
            else: server.start()
            function(server)
            result={"name":name,"passed":True,"failure":None}
        except Exception as exc:
            result={"name":name,"passed":False,"failure":str(exc),"traceback":traceback.format_exc()}
        finally: server.stop()
        result.update({"elapsed_s":time.monotonic()-started,"artifacts":str(directory)})
        results.append(result)
    report={"schema":"auditledger.acceptance.v1","source_identity":identity,"groups":results,"passed":bool(results) and all(r["passed"] for r in results),"passed_count":sum(r["passed"] for r in results),"group_count":len(results)}
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)); return report

def selfcheck():
    # Deliberately bad responses prove checker rejects booleans-as-integers,
    # wrong values, absent fields, array mismatches while allowing extensions.
    subset({"a":1,"extra":9},{"a":1})
    for actual,expected in [({"a":True},{"a":1}),({}, {"a":1}),({"a":2},{"a":1}),({"a":[]},{"a":[1]})]:
        try: subset(actual,expected)
        except AssertionError: pass
        else: raise AssertionError("bad response accepted")
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        db=pathlib.Path(temp)/"old.db"; data=legacy_data(); produce_legacy(db,data)
        check(legacy_rows(db)["legacy_accounts"]==[("old","alpha",83),("old","beta",37),("other","alpha",12),("other","gamma",8)],"genuine source fixture")
        with sqlite3.connect(db) as conn:
            check(conn.execute("PRAGMA user_version").fetchone()[0]==1,"genuine source version")
            check(len(conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall())==3,"old schema only")
    # This local stub deliberately violates status and error contracts. It
    # implements no ledger operation; exercise the real HTTP assertion path.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    class BadHandler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            status,body=(400,{"error":{"code":"wrong"}}) if self.path=="/wrong_error" else (200,{"a":True,"extra":"allowed"})
            self.send_response(status); self.send_header("Content-Type","application/json"); self.end_headers(); self.wfile.write(json.dumps(body).encode())
    http=ThreadingHTTPServer(("127.0.0.1",0),BadHandler)
    thread=threading.Thread(target=http.serve_forever,daemon=True); thread.start()
    try:
        with tempfile.TemporaryDirectory() as temp:
            stub=Server(__file__,pathlib.Path(temp)/"unused.db",temp)
            stub.base="http://127.0.0.1:"+str(http.server_port)
            for path,kwargs in [("/wrong_status",{"expected":400}),("/wrong_error",{"expected":400,"error":"invalid"})]:
                try: stub.req("GET",path,**kwargs)
                except AssertionError: pass
                else: raise AssertionError("bad HTTP control accepted")
            check(len(stub.trace)==2 and stub.trace[1]["response"]["error"]["code"]=="wrong","bad evidence retained")
    finally: http.shutdown(); http.server_close(); thread.join(timeout=2)
    check(semantic({"account":{"name":"a","balance":1,"reserved":0,"available":1,"version":1,"extra":3},"extra":1})==semantic({"account":{"name":"a","balance":1,"reserved":0,"available":1,"version":1,"extra":4}}),"extensions do not false-fail replay")
    check(len(GROUPS)==28,"group registry")
    return {"passed":True,"checks":["extra_fields","bad_responses","legacy_schema","bad_http_controls","replay_extensions","28_groups"]}

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("binary",nargs="?"); p.add_argument("--output",default="acceptance.json"); p.add_argument("--source"); p.add_argument("--startup-timeout",type=float,default=10); p.add_argument("--selfcheck",action="store_true")
    a=p.parse_args()
    if a.selfcheck: print(json.dumps(selfcheck())); raise SystemExit(0)
    if not a.binary: p.error("binary required")
    r=run_checks(a.binary,a.output,a.source,a.startup_timeout); print(json.dumps({"passed":r["passed"],"passed_count":r["passed_count"],"group_count":r["group_count"],"output":a.output})); raise SystemExit(0 if r["passed"] else 1)
