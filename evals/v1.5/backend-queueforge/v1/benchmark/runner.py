#!/usr/bin/env python3
"""Bounded independent localhost measurement; see README.md for APIs."""
import argparse, json, os, pathlib, shutil, signal, subprocess, threading, time, urllib.request, urllib.error, resource, sys, sqlite3, http.client, socket, urllib.parse
HERE=pathlib.Path(__file__).resolve().parent
MAX_DATA=2*1024**3
TENANTS=['bench0','bench1','bench2','bench3']
PAYLOAD={'blob':'x'*245} # compact JSON is exactly 256 ASCII bytes
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*a,**kw): return None
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
def public(base,tenant,path,body=None,key=None,deadline=None):
    # Absolute total deadline includes headers and trickling body reads.
    u=urllib.parse.urlsplit(base)
    if u.scheme!='http' or u.hostname!='127.0.0.1' or not u.port: raise ValueError('loopback HTTP only')
    total=2 if deadline is None else min(2,deadline-time.monotonic())
    if total<=0: raise TimeoutError('public request/seed preparation deadline')
    request_end=time.monotonic()+total
    headers={'X-Tenant-ID':tenant,'Content-Type':'application/json'}
    if key: headers['Idempotency-Key']=key
    data=None if body is None else json.dumps(body,separators=(',',':')).encode()
    conn=http.client.HTTPConnection(u.hostname,u.port,timeout=total)
    timer=None
    try:
        conn.connect();owned_socket=conn.sock
        remaining=request_end-time.monotonic()
        if remaining<=0: raise TimeoutError('public request total deadline')
        def interrupt():
            try: owned_socket.shutdown(socket.SHUT_RDWR)
            except OSError: pass
        timer=threading.Timer(remaining,interrupt);timer.daemon=True;timer.start()
        conn.request('GET' if body is None else 'POST',path,body=data,headers=headers)
        response=conn.getresponse()
        if response.status not in (200,201): raise RuntimeError('unexpected status: '+str(response.status))
        raw=response.read((1<<20)+1)
        if time.monotonic()>=request_end: raise TimeoutError('public request total deadline')
        if len(raw)>1<<20: raise RuntimeError('public response exceeded 1MiB')
        return json.loads(raw)
    finally:
        if timer: timer.cancel()
        conn.close()
def size_tree(path): return sum(p.stat().st_size for p in pathlib.Path(path).rglob('*') if p.is_file() and p.suffix in ('.sqlite','.sqlite-wal','.sqlite-shm'))
def check_cap(path):
    if size_tree(path)>MAX_DATA: raise RuntimeError('2GiB database cap exceeded')
def spawn_server(binary,db,out,env,deadline=None):
    f=open(out/'server.stderr','wb'); proc=subprocess.Popen([str(pathlib.Path(binary).resolve()),'--addr','127.0.0.1:0','--db',str(db)],stdout=subprocess.PIPE,stderr=f,env={**os.environ,**env,'GOMAXPROCS':'4'})
    lines=[]
    def read(): lines.append(proc.stdout.readline())
    t=threading.Thread(target=read,daemon=True);t.start();t.join(10 if deadline is None else max(.001,min(10,deadline-time.monotonic())))
    if t.is_alive() or not lines or not lines[0]: stop(proc);f.close();raise RuntimeError('server port not reported within 10s')
    try: port=json.loads(lines[0])['port']; assert isinstance(port,int) and 0<port<65536
    except Exception: stop(proc);f.close();raise RuntimeError('invalid server startup record')
    return proc,f,f'http://127.0.0.1:{port}'
def reap(proc):
    _,status,ru=os.wait4(proc.pid,0);proc.returncode=os.waitstatus_to_exitcode(status)
    return {'cpu_seconds':ru.ru_utime+ru.ru_stime,'peak_rss_bytes':ru.ru_maxrss if sys.platform=='darwin' else ru.ru_maxrss*1024,'exit_code':proc.returncode}
def stop(proc):
    try: proc.send_signal(signal.SIGTERM)
    except ProcessLookupError: pass
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        try:
            pid,status,ru=os.wait4(proc.pid,os.WNOHANG)
        except ChildProcessError: return {'cpu_seconds':None,'peak_rss_bytes':None,'exit_code':proc.returncode}
        if pid:
            proc.returncode=os.waitstatus_to_exitcode(status)
            return {'cpu_seconds':ru.ru_utime+ru.ru_stime,'peak_rss_bytes':ru.ru_maxrss if sys.platform=='darwin' else ru.ru_maxrss*1024,'exit_code':proc.returncode}
        time.sleep(.05)
    proc.kill();return reap(proc)
def stats(base,deadline=None): return {t:public(base,t,'/v1/stats',deadline=deadline) for t in TENANTS}
def prepare_seed(binary,output_dir,env=None):
    deadline=time.monotonic()+120
    try: return _prepare_seed(binary,output_dir,env,deadline)
    except Exception as error:
        out=pathlib.Path(output_dir)
        if out.exists(): (out/'seed-failure.json').write_text(json.dumps({'unavailable_reason':str(error),'seed_count_unverified':True,'deadline_seconds':120}))
        raise
def seed_deadline(deadline):
    if time.monotonic()>=deadline: raise TimeoutError('120s overall seed preparation deadline')
def _prepare_seed(binary,output_dir,env,deadline):
    env=env or {};out=pathlib.Path(output_dir).resolve();out.mkdir(parents=True,exist_ok=False);db=out/'seed.sqlite';proc,f,base=spawn_server(binary,db,out,env,deadline);refs=[];all_refs=[]
    try:
        for t in TENANTS:
            for batch in range(125):
                seed_deadline(deadline)
                result=public(base,t,'/v1/jobs/batch',{'jobs':[{'queue':'mail','payload':PAYLOAD,'max_attempts':3} for _ in range(100)]},f'seed-{batch}',deadline=deadline)
                jobs=result.get('jobs');assert isinstance(jobs,list) and len(jobs)==100 and result.get('replayed') is False
                for j in jobs:
                    assert j['tenant']==t and j['queue']=='mail' and j['state']=='ready' and j['attempts']==0 and j['payload']==PAYLOAD and isinstance(j['id'],str) and j['id']
                all_refs.extend({'tenant':t,'id':j['id']} for j in jobs)
                if batch<25: refs.extend({'tenant':t,'id':j['id']} for j in jobs)
                check_cap(out.parent)
        observed=stats(base,deadline)
        for s in observed.values(): assert s['total']==12500 and s['ready']==12500 and sum(s.get(k,0) for k in ['leased','completed','dead','cancelled'])==0
        assert len({(r['tenant'],r['id']) for r in refs})==10000
    except Exception as error:
        (out/'seed-failure.json').write_text(json.dumps({'unavailable_reason':str(error),'seed_count_unverified':True}))
        raise
    finally:
        metrics=stop(proc);f.close()
    # Only metadata/checkpoint operations through SQLite, never schema-private writes.
    seed_deadline(deadline)
    with sqlite3.connect(db,timeout=min(2,max(.001,deadline-time.monotonic()))) as connection:
        connection.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        checkpoint=list(connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
    if checkpoint[0]!=0: raise RuntimeError('seed checkpoint busy')
    seed_deadline(deadline)
    verify=out/'reopen';verify.mkdir();p2,f2,base2=spawn_server(binary,db,verify,env,deadline)
    try:
        reopened=stats(base2,deadline)
        if reopened!=observed: raise RuntimeError('seed counts changed across producer restart')
        for ref in [refs[0],refs[2500],refs[5000],refs[7500]]:
            job=public(base2,ref['tenant'],'/v1/jobs/'+ref['id'],deadline=deadline)['job']
            assert job['id']==ref['id'] and job['tenant']==ref['tenant'] and job['payload']==PAYLOAD
    finally:
        reopen_resources=stop(p2);f2.close()
    seed_deadline(deadline)
    with sqlite3.connect(db,timeout=min(2,max(.001,deadline-time.monotonic()))) as connection:
        connection.set_progress_handler(lambda:int(time.monotonic()>=deadline),1000)
        checkpoint_after_reopen=list(connection.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone())
    if checkpoint_after_reopen[0]!=0: raise RuntimeError('reopened seed checkpoint busy')
    wal=pathlib.Path(str(db)+'-wal')
    if wal.exists() and wal.stat().st_size: raise RuntimeError('seed not checkpointed after clean server shutdown')
    seed_deadline(deadline)
    all_path=out/'lifecycle-refs.json';all_path.write_text(json.dumps(all_refs,separators=(',',':')))
    refs_path=out/'refs.json';refs_path.write_text(json.dumps(refs,separators=(',',':')))
    metadata={'db':str(db),'refs':str(refs_path),'lifecycle_refs':str(all_path),'seed_count':50000,'read_count':10000,'tenants':TENANTS,'payload_serialized_bytes':256,'payload':PAYLOAD,'stats':observed,'seed_server_resources':metrics,'checkpoint':checkpoint,'checkpoint_after_reopen':checkpoint_after_reopen,'reopened_stats':reopened,'reopen_resources':reopen_resources}
    (out/'seed.json').write_text(json.dumps(metadata,indent=2));return metadata
def run_cell(binary,seed_metadata,config,output_dir,env=None):
    env=env or {};out=pathlib.Path(output_dir).resolve();out.mkdir(parents=True,exist_ok=False);db=out/'cell.sqlite';shutil.copyfile(seed_metadata['db'],db);check_cap(out.parent);proc,f,base=spawn_server(binary,db,out,env);gen=None;gf=None;sampling=[];deadline=time.monotonic()+60
    try:
        initial=stats(base)
        before_db=db.stat().st_size; before_wal=pathlib.Path(str(db)+'-wal'); before_wal_size=before_wal.stat().st_size if before_wal.exists() else 0
        warm=config.get('warmup_seconds',3);duration=config.get('measure_seconds',10)
        if warm!=3 or duration not in (8,10): raise ValueError('frozen 3s warmup, 8s/10s measure required')
        genbin=HERE/'loadgen'/'loadgen'
        args=[str(genbin),'--url',base,'--refs',seed_metadata['lifecycle_refs'] if config['workload']=='lifecycle' else seed_metadata['refs'],'--output',str(out/'generator.json'),'--workload',config['workload'],'--concurrency',str(config.get('concurrency',1)),'--rate',str(config.get('rate',0)),'--warmup','3s','--duration',str(duration)+'s']
        gf=open(out/'generator.log','wb');gen=subprocess.Popen(args,stdout=gf,stderr=gf,env={**os.environ,**env,'GOMAXPROCS':'2'})
        gen_resources=None;server_crash=False
        while time.monotonic()<deadline:
            pid,status,ru=os.wait4(gen.pid,os.WNOHANG)
            if pid:
                gen.returncode=os.waitstatus_to_exitcode(status);gen_resources={'cpu_seconds':ru.ru_utime+ru.ru_stime,'peak_rss_bytes':ru.ru_maxrss if sys.platform=='darwin' else ru.ru_maxrss*1024,'exit_code':gen.returncode};break
            # Read owned process resource samples only. ps reports RSS in KiB and cumulative CPU time.
            snapshot=subprocess.run(['ps','-p',f'{proc.pid},{gen.pid}','-o','pid=,rss=,time=,%cpu=,stat='],capture_output=True,text=True)
            sampling.append({'elapsed_seconds':time.monotonic()-(deadline-60),'ps':snapshot.stdout.strip() or None})
            if any(line.split() and line.split()[0]==str(proc.pid) and line.split()[-1].startswith('Z') for line in snapshot.stdout.splitlines()): raise RuntimeError('server crashed during timed cell')
            try: os.kill(proc.pid,0)
            except ProcessLookupError: server_crash=True;break
            check_cap(out.parent);time.sleep(.2)
        if gen_resources is None: gen_resources=stop(gen);raise RuntimeError('generator deadline or server crash')
        if gen.returncode!=0: raise RuntimeError('generator failed; retain generator.log')
        live_wal=pathlib.Path(str(db)+'-wal');live_wal_bytes=live_wal.stat().st_size if live_wal.exists() else 0
        live_db_bytes=db.stat().st_size
        final=stats(base);result=json.loads((out/'generator.json').read_text());acks=result['acknowledged_unique'];claims=result['claimed_unique']
        conservation={'initial':initial,'final':final,'valid':True,'violations':[]}
        for t,s in final.items():
            if sum(s.get(k,0) for k in ['ready','leased','completed','dead','cancelled'])!=s['total'] or s['total']!=12500: conservation['violations'].append(t+': count conservation')
        completed=sum(s['completed'] for s in final.values())-sum(s['completed'] for s in initial.values());leased=sum(s['leased'] for s in final.values());
        if config['workload']=='lifecycle' and (completed!=acks or leased!=claims-acks): conservation['violations'].append('acknowledgement/state mismatch')
        if config['workload']=='read' and final!=initial: conservation['violations'].append('read changed stored state')
        conservation['valid']=not conservation['violations'];result.update({'config':config,'seed':{k:v for k,v in seed_metadata.items() if k not in ('payload','stats')},'conservation':conservation,'generator_resources':gen_resources,'resource_samples':sampling,'db_bytes_before':before_db,'wal_bytes_before':before_wal_size,'db_bytes_at_measure_end':live_db_bytes,'wal_bytes_at_measure_end':live_wal_bytes,'host_interpretation':'Shared Mac, no affinity. Closed loop limits offered work when latency rises; fixed arrivals expose scheduler delay/drops. Timeout latencies are censored.'})
    except Exception as e:
        result={'config':config,'unavailable_reason':str(e),'resource_samples':sampling,'generator_resources':locals().get('gen_resources'),'conservation':None,'db_bytes_at_measure_end':None,'wal_bytes_at_measure_end':None}
        if gen is not None and gen.returncode is None: result['generator_resources']=stop(gen)
    finally:
        result['server_resources']=stop(proc);f.close()
        if gf: gf.close()
    result['db_bytes']=db.stat().st_size if db.exists() else None;wal=pathlib.Path(str(db)+'-wal');result['wal_bytes']=wal.stat().st_size if wal.exists() else 0
    (out/'result.json').write_text(json.dumps(result,indent=2));return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',type=pathlib.Path);p.add_argument('--stage',type=int,choices=[2,3]);p.add_argument('--arm');p.add_argument('--output',type=pathlib.Path);p.add_argument('--selfcheck',action='store_true');a=p.parse_args()
    if a.selfcheck: subprocess.run([str(HERE/'loadgen'/'loadgen'),'--selfcheck'],check=True);return
    if not all((a.binary,a.stage,a.arm,a.output)): p.error('binary, stage, arm, output required')
    a.output.mkdir(parents=True,exist_ok=False);seed=prepare_seed(a.binary,a.output/'seed',{});start=time.monotonic()
    for rep in range(1 if a.stage==2 else 3):
        cells=[{'workload':w,'concurrency':c,'rate':0} for w in ['read','lifecycle'] for c in [1,16,64]]
        if a.stage==3: cells += [{'workload':'read','rate':r,'concurrency':1} for r in [100,500,1000]]
        for i,c in enumerate(cells):
            if time.monotonic()-start>1800: raise RuntimeError('30 minute wall cap')
            c.update(stage=a.stage,arm=a.arm,repetition=rep,warmup_seconds=3,measure_seconds=8 if a.stage==2 else 10)
            result=run_cell(a.binary,seed,c,a.output/f'cell-{rep}-{i}',{})
            if 'unavailable_reason' in result or result.get('stopped_transport_failures') or result.get('drain_budget_exceeded'): return
if __name__=='__main__': main()
