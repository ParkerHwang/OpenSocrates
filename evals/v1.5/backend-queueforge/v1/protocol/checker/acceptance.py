#!/usr/bin/env python3
"""Independent QueueForge public-API acceptance checks. Python standard library only."""
import argparse, base64, concurrent.futures, hashlib, contextlib, http.client, json, os, socket, pathlib, queue, signal, sqlite3, subprocess, tempfile, threading, time, urllib.error, urllib.parse, urllib.request

NOW = 1800000000000
MAX_REQUEST_SECONDS = 3
class Failure(Exception): pass
class SetupFailure(Exception): pass
class Deadline(Exception): pass

def require(condition, message):
    if not condition: raise Failure(message)

def unique_ids(jobs):
    ids = [j.get('id') for j in jobs]
    return all(isinstance(i,str) and i for i in ids) and len(ids)==len(set(ids))

JOB_FIELDS=('id','tenant','queue','payload','state','attempts','max_attempts','created_seq','created_at_ms','available_at_ms','lease_until_ms','last_error','result')
def semantic_job_equal(left,right,stage):
    fields=JOB_FIELDS+(('priority','retry_base_ms') if stage>=2 else ())
    return isinstance(left,dict) and isinstance(right,dict) and all(k in left and k in right and left[k]==right[k] for k in fields)

def error_code(body):
    return body.get('error',{}).get('code') if isinstance(body,dict) else None

def safe_text(data):
    return data.decode('utf-8','replace')[-12000:]

class Server:
    def __init__(self, fixture, binary, flags=()):
        self.fixture=fixture; self.stdout=bytearray(); self.stderr=bytearray(); self.lines=queue.Queue(); self.race_warning=False
        args=[binary,'--addr','127.0.0.1:0','--db',str(fixture.db),'--clock-file',str(fixture.clock),*flags]
        self.args=args
        if time.monotonic() >= fixture.runner.deadline: raise SetupFailure('whole-run startup budget exhausted')
        self.process=subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, cwd=str(fixture.directory), env={**os.environ,'GOMAXPROCS':'4'})
        def drain(stream, target, linequeue=None):
            while True:
                line=stream.readline()
                if not line: break
                target.extend(line)
                if b'DATA RACE' in line: self.race_warning=True
                if len(target)>65536: del target[:-65536]
                if linequeue: linequeue.put(line)
        self.threads=[threading.Thread(target=drain,args=(self.process.stdout,self.stdout,self.lines),daemon=True),threading.Thread(target=drain,args=(self.process.stderr,self.stderr),daemon=True)]
        for t in self.threads: t.start()
        fixture.servers.append(self)
        with fixture.runner.lock: fixture.runner.active_servers.append(self)
        try:
            startup_deadline=min(time.monotonic()+5,fixture.runner.deadline)
            while True:
                try: first=self.lines.get(timeout=max(.01,min(.1,startup_deadline-time.monotonic()))); break
                except queue.Empty:
                    if self.process.poll() is not None: raise ValueError('process exited before startup JSON')
                    if time.monotonic()>=startup_deadline: raise ValueError('startup timeout')
            port=json.loads(first).get('port')
            if type(port) is not int or not 0<port<65536: raise ValueError('invalid port')
            self.url='http://127.0.0.1:'+str(port)
        except Exception as e: raise SetupFailure('startup JSON port missing/invalid: '+str(e))
    def stop(self, kill=False):
        if self.process.poll() is None:
            self.process.kill() if kill else self.process.terminate()
            try: self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill(); self.process.wait(timeout=1)
        for t in self.threads: t.join(timeout=.2)
    def diagnostics(self):
        return {'argv':self.args,'exit_code':self.process.poll(),'stdout':safe_text(self.stdout),'stderr':safe_text(self.stderr),'race_warning':self.race_warning}

class Fixture:
    def __init__(self, runner, flags=()):
        self.runner=runner; self.temp=tempfile.TemporaryDirectory(prefix='qf-check-',dir=runner.temp_root)
        self.directory=pathlib.Path(self.temp.name); self.db=self.directory/'store.sqlite'; self.clock=self.directory/'clock'; self.servers=[]; self.flags=flags; self.now=NOW; self.set_time(NOW)
    def set_time(self, value):
        p=self.directory/'clock.new'; p.write_text(str(value)); os.replace(p,self.clock); self.now=value
    def start(self, binary=None, flags=None): return Server(self,binary or self.runner.binary, self.flags if flags is None else flags)
    def close(self):
        for s in self.servers: s.stop()
        logs=[s.diagnostics() for s in self.servers]
        self.temp.cleanup(); return logs

class Runner:
    def __init__(self,binary,stage,legacy_binary=None,temp_root=None):
        self.binary=binary; self.stage=stage; self.legacy_binary=legacy_binary; self.temp_root=temp_root
        self.requests=[]; self.scenarios=[]; self.active_servers=[]; self.lock=threading.Lock(); self.current=None; self.local=threading.local()
        self.start=time.monotonic(); self.deadline=self.start+165
    def check(self,condition,name):
        with self.lock: self.current['checks'].append({'name':name,'passed':bool(condition)})
        require(condition,name)
    def request(self,s,method,path,body=None,tenant='alpha',key=None,expected=200,code=None,raw=None):
        if time.monotonic()>self.deadline: raise Deadline('whole-run budget reached')
        data=raw if raw is not None else (None if body is None else json.dumps(body,separators=(',',':')).encode())
        headers={'Content-Type':'application/json'}
        if tenant is not None: headers['X-Tenant-ID']=tenant
        if key is not None: headers['Idempotency-Key']=key
        start=time.monotonic(); response=None; status=None; problem=None
        endpoint=urllib.parse.urlsplit(s.url)
        require(endpoint.hostname=='127.0.0.1' and endpoint.scheme=='http','requests must remain synthetic loopback')
        connection=http.client.HTTPConnection(endpoint.hostname,endpoint.port,timeout=MAX_REQUEST_SECONDS)
        transport=[]; expired=threading.Event()
        def abort():
            expired.set(); sock=connection.sock or (transport[0] if transport else None)
            if sock:
                with contextlib.suppress(OSError): sock.shutdown(socket.SHUT_RDWR)
        timer=threading.Timer(MAX_REQUEST_SECONDS-.05,abort); timer.daemon=True; timer.start()
        try:
            connection.request(method,path,body=data,headers=headers)
            if connection.sock: transport.append(connection.sock)
            resp=connection.getresponse(); status=resp.status
            try: result=resp.read(2*1024*1024)
            finally: resp.close()
            if expired.is_set(): raise TimeoutError('three-second total request deadline')
            response=json.loads(result)
            if not isinstance(response,dict): raise ValueError('response must be JSON object')
        except Exception as e: problem=type(e).__name__+': '+str(e)
        finally: timer.cancel(); connection.close()
        record={'scenario':self.current['name'],'method':method,'path':path,'tenant':tenant,'idempotency_key':key,'request':body if raw is None else {'raw_bytes':len(raw)},'status':status,'response':response,'error':problem,'duration_ms':(time.monotonic()-start)*1000,'expected_status':expected,'expected_code':code}
        with self.lock: self.requests.append(record)
        self.local.status=status
        if problem: raise Failure('HTTP transport/JSON failure: '+problem)
        accepted=expected if isinstance(expected,(list,tuple)) else [expected]
        require(status in accepted, f'{method} {path}: expected {accepted}, got {status}')
        if status>=400:
            require(isinstance(response.get('error'),dict) and isinstance(response['error'].get('code'),str) and isinstance(response['error'].get('message'),str) and bool(response['error']['message']), 'error envelope code/message required')
            require(str(s.fixture.db) not in json.dumps(response) if hasattr(s,'fixture') else True, 'error must not expose DB path')
        if code: require(error_code(response)==code,f'{path}: expected error code {code}')
        return response
    def job(self,j,tenant='alpha',state=None,policy=True):
        fields=JOB_FIELDS
        self.check(isinstance(j,dict) and all(k in j for k in fields),'JOB required fields')
        self.check(isinstance(j['id'],str) and bool(j['id']) and j['tenant']==tenant,'job identity and tenant')
        self.check(type(j['created_seq']) is int and j['created_seq']>0 and type(j['created_at_ms']) is int and type(j['available_at_ms']) is int,'job integer creation/time fields')
        self.check(type(j['attempts']) is int and type(j['max_attempts']) is int and 0<=j['attempts']<=j['max_attempts']<=10,'attempt fields')
        self.check(isinstance(j['payload'],dict) and isinstance(j['queue'],str) and 'lease_token' not in j,'payload and no job lease token')
        self.check(j['state'] in (('ready','leased','completed','dead','cancelled') if self.stage>=2 else ('ready','leased','completed','dead')),'state vocabulary')
        if state: self.check(j['state']==state,'expected state '+state)
        if self.stage>=2 and policy:
            self.check(type(j.get('priority')) is int and type(j.get('retry_base_ms')) is int,'stage2 policy fields')
        return j
    def enqueue(self,s,key='one',tenant='alpha',**extra):
        body={'queue':'mail','payload':{'n':1},**extra}
        r=self.request(s,'POST','/v1/jobs',body,tenant,key,201)
        self.check(r.get('replayed') is False,'new replayed false'); j=self.job(r.get('job'),tenant,'ready')
        self.check(j['queue']==body['queue'] and j['payload']==body['payload'] and j['max_attempts']==body.get('max_attempts',3),'accepted input preserved')
        if self.stage>=2: self.check(j['priority']==body.get('priority',0) and j['retry_base_ms']==body.get('retry_base_ms',1000),'accepted stage2 policy preserved')
        return j
    def immutable(self,original,current):
        fields=('id','tenant','queue','payload','max_attempts','created_seq','created_at_ms','priority','retry_base_ms')
        self.check(all(current.get(k)==original[k] for k in fields if k in original),'immutable identity/input/creation fields preserved')
    def get(self,s,j,tenant='alpha'):
        current=self.job(self.request(s,'GET','/v1/jobs/'+j['id'],tenant=tenant)['job'],tenant); self.immutable(j,current); return current
    def claim(self,s,queue_name='mail',tenant='alpha',lease=100,policy=True):
        r=self.request(s,'POST','/v1/queues/'+queue_name+'/claim',{'worker_id':'worker','lease_ms':lease},tenant)
        self.check(all(k in r for k in ('job','lease_token','lease_until_ms')),'claim envelope fields')
        if r['job'] is None: self.check(r['lease_token'] is None and r['lease_until_ms'] is None,'empty claim all null')
        else:
            self.job(r['job'],tenant,'leased',policy=policy); self.check(isinstance(r['lease_token'],str) and bool(r['lease_token']) and type(r['lease_until_ms']) is int and r['job']['lease_until_ms']==r['lease_until_ms'],'claim token/deadline consistency')
        return r
    def stats(self,s,tenant='alpha',queue_name=None):
        r=self.request(s,'GET','/v1/stats'+('?' + urllib.parse.urlencode({'queue':queue_name}) if queue_name else ''),tenant=tenant)
        states=('ready','leased','completed','dead','cancelled')
        self.check(all(type(r.get(k)) is int and r[k]>=0 for k in ('total',*states)),'stats counts nonnegative integers')
        self.check(sum(r[k] for k in states)==r['total'] and 'lease_token' not in r,'stats conservation/no token')
        if self.stage==1: self.check(r['cancelled']==0,'stage1 cancelled count zero')
        return r
    def contention(self,s,method,path,body,tenant='alpha',key=None,expected=(200,201)):
        accepted=tuple(expected) if isinstance(expected,(tuple,list)) else (expected,)
        for _ in range(3):
            result=self.request(s,method,path,body,tenant,key,(*accepted,503))
            if self.local.status!=503: return result
        raise SetupFailure('temporary storage unavailable after three recorded contention attempts')
    def parallel(self,funcs):
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8,len(funcs))) as pool:
            futures=[pool.submit(f) for f in funcs]; out=[]; errors=[]
            for f in futures:
                try: out.append(f.result())
                except Exception as e: errors.append(e)
        if errors: raise errors[0]
        return out
    def scenario(self,name,fn,flags=()):
        row={'name':name,'status':'running','checks':[],'error':None,'diagnostics':[],'duration_ms':None}; self.current=row; self.scenarios.append(row); f=Fixture(self,flags); start=time.monotonic()
        try:
            fn(f); row['status']='pass'
        except SetupFailure as e: row['status']='unassessable'; row['error']=str(e)
        except Exception as e: row['status']='fail' if isinstance(e,Failure) else 'error'; row['error']=type(e).__name__+': '+str(e)
        finally:
            row['diagnostics']=f.close(); row['duration_ms']=(time.monotonic()-start)*1000
            if any(d['race_warning'] for d in row['diagnostics']): row['status']='fail'; row['error']=(row['error'] or '')+' Go DATA RACE detected'
    def run(self):
        for name,fn,flags in scenarios(self):
            if time.monotonic()>self.deadline:
                self.scenarios.append({'name':name,'status':'unassessable','checks':[],'error':'whole-run budget exhausted','diagnostics':[],'duration_ms':None}); continue
            self.scenario(name,fn,flags)
        return {'format_version':1,'binary':self.binary,'legacy_binary':self.legacy_binary,'stage':self.stage,'passed':all(s['status']=='pass' for s in self.scenarios),'scenarios':self.scenarios,'requests':self.requests,'duration_ms':(time.monotonic()-self.start)*1000,'metrics':{'server_cpu_seconds':None,'peak_rss_bytes':None},'limits':['HTTP acknowledgement plus SIGKILL/restart is not power-loss durability proof.','SQLite PRAGMAs and implementation reuse require separate source review.','Synthetic localhost fixtures do not exercise production authentication or external effects.']}

def scenarios(r):
    def basic(f):
        s=f.start(); h=r.request(s,'GET','/health',tenant=None); r.check(h.get('ok') is True and h.get('schema_version')==(1 if r.stage==1 else 2),'health schema')
        j=r.enqueue(s); r.check(j['attempts']==0 and j['max_attempts']==3 and j['created_at_ms']==NOW and j['available_at_ms']==NOW and j['lease_until_ms'] is None and j['last_error'] is None and j['result'] is None,'new job defaults/time/nulls')
        r.check(semantic_job_equal(r.get(s,j),j,r.stage),'GET preserves required job fields'); r.check(r.stats(s)['total']==1,'single total')
    yield 'basic_semantic_fields',basic,()
    def validation(f):
        s=f.start(); body={'queue':'mail','payload':{}}
        for tenant in (None,'','bad space','a'*65): r.request(s,'POST','/v1/jobs',body,tenant,'valid',400,'validation')
        for key in (None,'','k'*129): r.request(s,'POST','/v1/jobs',body,'alpha',key,400,'validation')
        invalid=[{'queue':'bad queue','payload':{}},{'queue':'mail','payload':[]},{'queue':'mail','payload':{},'max_attempts':0},{'queue':'mail','payload':{},'max_attempts':1.5},{'queue':'mail','payload':{},'unknown':1},{'queue':'mail','payload':{'x':'x'*17000}}]
        if r.stage>=2: invalid += [{'queue':'mail','payload':{},'priority':11},{'queue':'mail','payload':{},'retry_base_ms':60001},{'queue':'mail','payload':{},'run_at_ms':-1}]
        for i,b in enumerate(invalid): r.request(s,'POST','/v1/jobs',b,key='bad'+str(i),expected=400,code='validation')
        r.request(s,'POST','/v1/jobs',key='raw',raw=b'{',expected=400,code='validation')
        r.request(s,'POST','/v1/jobs',key='huge',raw=b'{"queue":"mail","payload":{"x":"'+b'x'*(1024*1024)+b'"}}',expected=400,code='validation')
        r.request(s,'POST','/v1/queues/mail/claim',{'worker_id':'bad space','lease_ms':100},expected=400,code='validation')
        r.check(r.stats(s)['total']==0,'invalid commands leave no jobs')
    yield 'validation_atomic_no_side_effects',validation,()
    def idem(f):
        a=f.start(); b=f.start(); body={'queue':'mail','payload':{'n':1,'a':2}}
        rs=r.parallel([lambda s=s:r.contention(s,'POST','/v1/jobs',body,key='shared',expected=(200,201)) for s in (a,b,a,b,a,b,a,b)])
        r.check(len({x['job']['id'] for x in rs})==1 and sum(x.get('replayed') is False for x in rs)==1 and all(type(x.get('replayed')) is bool for x in rs),'concurrent idempotency one creation')
        original=rs[0]['job']; f.set_time(NOW+1000)
        replay=r.request(b,'POST','/v1/jobs',{'payload':{'a':2,'n':1},'max_attempts':3,'queue':'mail'},key='shared',expected=200)
        r.check(replay.get('replayed') is True and replay['job']['id']==original['id'] and replay['job']['created_at_ms']==NOW,'logical defaults/order/clock replay')
        r.request(a,'POST','/v1/jobs',{'queue':'mail','payload':{'n':2}},key='shared',expected=409,code='idempotency_conflict')
        foreign=r.enqueue(b,key='shared',tenant='beta'); r.check(foreign['id']!=original['id'],'tenant idempotency namespace')
        r.request(a,'GET','/v1/jobs/'+original['id'],tenant='beta',expected=404,code='not_found')
        r.request(a,'POST','/v1/jobs/'+original['id']+'/complete',{'lease_token':'fake','result':{}},tenant='beta',expected=404,code='not_found')
        batch=r.request(a,'POST','/v1/jobs/batch',{'jobs':[{'queue':'mail','payload':{}}]},key='shared',expected=201)
        r.check(batch.get('replayed') is False and batch['jobs'][0]['id']!=original['id'],'endpoint idempotency namespace')
        r.check(r.stats(a)['total']==2 and r.stats(b,'beta')['total']==1,'tenant totals after conflict')
    yield 'two_process_idempotency_and_tenancy',idem,()
    def bulk(f):
        s=f.start(); bad={'jobs':[{'queue':'mail','payload':{'n':1}},{'queue':'mail','payload':{},'max_attempts':0}]}
        r.request(s,'POST','/v1/jobs/batch',bad,key='bulk',expected=400,code='validation'); r.check(r.stats(s)['total']==0,'batch invalid suffix rollback')
        good={'jobs':[{'queue':'mail','payload':{'n':i}} for i in range(4)]}
        x=r.request(s,'POST','/v1/jobs/batch',good,key='bulk',expected=201)
        js=x.get('jobs',[]); r.check(len(js)==4 and unique_ids(js) and x.get('replayed') is False,'batch length unique IDs and no poisoned key')
        for j in js: r.job(j,state='ready')
        r.check([j['payload']['n'] for j in js]==list(range(4)) and [j['created_seq'] for j in js]==sorted(set(j['created_seq'] for j in js)),'batch order unique increasing seq')
        y=r.request(s,'POST','/v1/jobs/batch',good,key='bulk',expected=200); r.check(y.get('replayed') is True and [j['id'] for j in y['jobs']]==[j['id'] for j in js],'batch replay identity')
        r.request(s,'POST','/v1/jobs/batch',{'jobs':[]},key='empty',expected=400,code='validation'); r.check(r.stats(s)['total']==4,'batch conservation')
    yield 'atomic_bulk_and_replay',bulk,()
    def leasing(f):
        a=f.start(); b=f.start(); jobs=[r.enqueue(a,key=str(i)) for i in range(4)]
        claims=r.parallel([lambda s=s:r.claim(s) for s in (a,b,a,b)])
        r.check(unique_ids([c['job'] for c in claims]) and {c['job']['id'] for c in claims}=={j['id'] for j in jobs},'two processes unique live leases')
        r.check(len({c['lease_token'] for c in claims})==4 and all(c['job']['attempts']==1 and c['lease_until_ms']==NOW+100 for c in claims),'unique tokens attempts and deadline')
        r.check(r.claim(a)['job'] is None,'no double live claim'); c=claims[0]; path='/v1/jobs/'+c['job']['id']; f.set_time(NOW+50)
        h=r.request(b,'POST',path+'/heartbeat',{'lease_token':c['lease_token'],'lease_ms':200}); r.job(h['job'],state='leased'); r.check(h['job']['attempts']==1 and h['job']['lease_until_ms']==NOW+250,'heartbeat deadline now plus lease, attempts stable')
        r.request(a,'POST',path+'/heartbeat',{'lease_token':'wrong','lease_ms':100},expected=409,code='lease_conflict')
        f.set_time(NOW+250); r.request(a,'POST',path+'/complete',{'lease_token':c['lease_token'],'result':{}},expected=409,code='lease_conflict')
        reclaim=r.claim(b); r.check(reclaim['job'] is not None,'expired lease reclaimed')
        # All old deadlines have expired; FIFO/priority ties select original first job.
        r.check(reclaim['job']['id']==jobs[0]['id'] and reclaim['job']['attempts']==2 and reclaim['job']['last_error']=='lease_expired','deadline equality reconciliation FIFO')
        old=next(x for x in claims if x['job']['id']==reclaim['job']['id']); r.check(reclaim['lease_token']!=old['lease_token'],'new attempt new token')
        for op,body in [('heartbeat',{'lease_ms':100}),('complete',{'result':{}}),('fail',{'error':'late'})]: r.request(a,'POST','/v1/jobs/'+reclaim['job']['id']+'/'+op,{'lease_token':old['lease_token'],**body},expected=409,code='lease_conflict')
        r.check(r.get(a,reclaim['job'])['attempts']==2,'stale mutations preserve attempts')
    if r.stage==1: yield 'live_lease_races_heartbeat_deadline_fencing',leasing,()
    else:
        # Zero retry base isolates the stage1 fencing contract from scheduling.
        def fencing2(f):
            a=f.start(); b=f.start(); j=r.enqueue(a,retry_base_ms=0); c=r.claim(a); f.set_time(NOW+50)
            h=r.request(b,'POST','/v1/jobs/'+j['id']+'/heartbeat',{'lease_token':c['lease_token'],'lease_ms':100})['job']; r.check(h['attempts']==1 and h['lease_until_ms']==NOW+150,'heartbeat stable attempts and extension')
            f.set_time(NOW+150)
            for op,extra in [('heartbeat',{'lease_ms':100}),('complete',{'result':{}}),('fail',{'error':'late'})]: r.request(a,'POST','/v1/jobs/'+j['id']+'/'+op,{'lease_token':c['lease_token'],**extra},expected=409,code='lease_conflict')
            n=r.claim(b); r.check(n['job']['id']==j['id'] and n['job']['attempts']==2 and n['lease_token']!=c['lease_token'] and n['job']['last_error']=='lease_expired','expiry reclaim fencing')
            r.request(a,'POST','/v1/jobs/'+j['id']+'/complete',{'lease_token':c['lease_token'],'result':{}},expected=409,code='lease_conflict'); r.check(r.get(a,j)['state']=='leased','stale complete has no effect')
        yield 'heartbeat_deadline_stale_token_fencing',fencing2,()
        def claimrace(f):
            a=f.start(); b=f.start(); jobs=[r.enqueue(a,key=str(i),retry_base_ms=0) for i in range(6)]; cs=r.parallel([lambda s=s:r.claim(s) for s in (a,b,a,b,a,b)])
            r.check(unique_ids([c['job'] for c in cs]) and {c['job']['id'] for c in cs}=={j['id'] for j in jobs} and len({c['lease_token'] for c in cs})==6,'cross-process unique claims/tokens')
        yield 'two_process_claim_race',claimrace,()
    def completion(f):
        s=f.start(); j=r.enqueue(s); c=r.claim(s); path='/v1/jobs/'+j['id']; result={'answer':42}
        done=r.request(s,'POST',path+'/complete',{'lease_token':c['lease_token'],'result':result})['job']; r.job(done,state='completed'); r.immutable(j,done); r.check(done['result']==result and done['lease_until_ms'] is None and done['attempts']==1,'completed result and released lease')
        f.set_time(NOW+10000); repeat=r.request(s,'POST',path+'/complete',{'lease_token':c['lease_token'],'result':result})['job']; r.job(repeat,state='completed'); r.check(semantic_job_equal(repeat,done,r.stage),'completion idempotent required fields after deadline')
        for token,res in [(c['lease_token'],{'answer':43}),('wrong',result)]: r.request(s,'POST',path+'/complete',{'lease_token':token,'result':res},expected=409,code='lease_conflict')
        r.check(semantic_job_equal(r.get(s,j),done,r.stage) and r.stats(s)['completed']==1,'conflicting completion no mutation')
    yield 'completion_result_and_exact_replay',completion,()
    def attempts(f):
        s=f.start(); extra={'retry_base_ms':0} if r.stage>=2 else {}; j=r.enqueue(s,max_attempts=2,**extra); c=r.claim(s); path='/v1/jobs/'+j['id']
        failed=r.request(s,'POST',path+'/fail',{'lease_token':c['lease_token'],'error':'first'})['job']; r.job(failed,state='ready'); r.immutable(j,failed); r.check(failed['attempts']==1 and failed['last_error']=='first' and failed['lease_until_ms'] is None and failed['available_at_ms']==NOW,'retry fail accounting')
        r.request(s,'POST',path+'/fail',{'lease_token':c['lease_token'],'error':'again'},expected=409,code='lease_conflict')
        n=r.claim(s); dead=r.request(s,'POST',path+'/fail',{'lease_token':n['lease_token'],'error':'last'})['job']; r.job(dead,state='dead'); r.immutable(j,dead); r.check(dead['attempts']==2 and dead['lease_until_ms'] is None and dead['last_error']=='last','last fail dead')
        r.check(r.claim(s)['job'] is None and r.stats(s)['dead']==1,'dead never reclaims')
        j2=r.enqueue(s,key='expiry',max_attempts=1,**extra); c2=r.claim(s); f.set_time(c2['lease_until_ms']); r.check(r.claim(s)['job'] is None,'exhausted expiry no claim'); d=r.get(s,j2); r.check(d['state']=='dead' and d['attempts']==1,'exhausted expiry dead accounting')
    yield 'fail_retry_dead_and_expiry_max_attempts',attempts,()
    def crash(f):
        s=f.start(); j=r.enqueue(s); c=r.claim(s); s.stop(kill=True); s=f.start(); restored=r.get(s,j); r.check(restored['state']=='leased' and restored['attempts']==1 and restored['lease_until_ms']==c['lease_until_ms'],'acknowledged lease survives SIGKILL')
        result={'durable':True}; r.request(s,'POST','/v1/jobs/'+j['id']+'/complete',{'lease_token':c['lease_token'],'result':result}); s.stop(kill=True); s=f.start(); d=r.get(s,j); r.check(d['state']=='completed' and d['result']==result,'acknowledged complete survives SIGKILL')
        replay=r.request(s,'POST','/v1/jobs',{'queue':'mail','payload':{'n':1}},key='one',expected=200); r.check(replay.get('replayed') is True and replay['job']['id']==j['id'],'idempotency survives SIGKILL')
    yield 'acknowledged_mutations_SIGKILL_restart',crash,()
    if r.stage<2: return
    def priority(f):
        s=f.start(); future=r.enqueue(s,key='future',priority=10,run_at_ms=NOW+500); low=r.enqueue(s,key='low',priority=-2); high=r.enqueue(s,key='high',priority=5); tie=r.enqueue(s,key='tie',priority=5)
        claimed=[r.claim(s)['job']['id'] for _ in range(3)]; r.check(claimed==[high['id'],tie['id'],low['id']],'eligible priority desc FIFO ties future not blocking')
        r.check(r.claim(s)['job'] is None,'future unavailable'); f.set_time(NOW+500); r.check(r.claim(s)['job']['id']==future['id'],'run_at equality eligible')
    yield 'scheduling_priority_fifo',priority,()
    def backoff(f):
        s=f.start(); j=r.enqueue(s,retry_base_ms=200,max_attempts=4); c=r.claim(s); path='/v1/jobs/'+j['id']; f.set_time(NOW+25)
        x=r.request(s,'POST',path+'/fail',{'lease_token':c['lease_token'],'error':'retry'})['job']; r.check(x['available_at_ms']==NOW+225,'attempt1 fail base delay')
        f.set_time(NOW+224); r.check(r.claim(s)['job'] is None,'retry unavailable before boundary'); f.set_time(NOW+225); c2=r.claim(s); r.check(c2['job']['id']==j['id'] and c2['job']['attempts']==2,'retry equality and attempt2')
        deadline=c2['lease_until_ms']; f.set_time(deadline+300); r.check(r.claim(s)['job'] is None,'late expiry discovery still delayed'); x=r.get(s,j); r.check(x['available_at_ms']==deadline+400 and x['state']=='ready','expiry backoff anchored deadline exponential')
        f.set_time(deadline+400); c3=r.claim(s); r.check(c3['job']['attempts']==3,'third attempt'); x=r.request(s,'POST',path+'/fail',{'lease_token':c3['lease_token'],'error':'third'})['job']; r.check(x['available_at_ms']==f.now+800,'attempt3 exponential delay')
    yield 'fail_and_expiry_backoff_boundaries',backoff,()
    def capbackoff(f):
        s=f.start(); j=r.enqueue(s,retry_base_ms=60000); c=r.claim(s); p='/v1/jobs/'+j['id']; x=r.request(s,'POST',p+'/fail',{'lease_token':c['lease_token'],'error':'one'})['job']; f.set_time(x['available_at_ms']); c=r.claim(s); x=r.request(s,'POST',p+'/fail',{'lease_token':c['lease_token'],'error':'two'})['job']; r.check(x['available_at_ms']==f.now+60000,'retry delay capped 60000')
    yield 'retry_cap',capbackoff,()
    def pending(f):
        a=f.start(); b=f.start(); body={'queue':'mail','payload':{}}
        rs=r.parallel([lambda s=s,i=i:r.contention(s,'POST','/v1/jobs',body,key='q'+str(i),expected=(201,429)) for i,s in enumerate((a,b,a,b,a,b))])
        successes=[x for x in rs if 'job' in x]; r.check(len(successes)==2 and unique_ids([x['job'] for x in successes]) and all(error_code(x)=='capacity' for x in rs if 'job' not in x),'pending capacity race accepts exactly2')
        r.check(r.stats(a)['total']==2,'pending race conservation'); j=successes[0]['job']; index=next(q['idempotency_key'] for q in r.requests if q['scenario']==r.current['name'] and q['status']==201 and q['response']['job']['id']==j['id'])
        r.request(b,'POST','/v1/jobs',body,key=index,expected=200)
        r.request(a,'POST','/v1/jobs/batch',{'jobs':[body,body]},key='capacitybulk',expected=429,code='capacity'); r.check(r.stats(a)['total']==2,'capacity bulk no prefix writes')
        r.request(a,'POST','/v1/jobs/'+j['id']+'/cancel',{}); new=r.enqueue(b,key='released'); r.check(r.stats(a)['total']==3 and new['state']=='ready','cancel releases pending slot')
        beta=r.enqueue(a,key='beta',tenant='beta'); r.check(beta['tenant']=='beta','pending quota tenant scoped')
    yield 'cross_process_pending_quota_atomic_bulk_replay',pending,('--max-pending','2')
    def inflight(f):
        a=f.start(); b=f.start(); [r.enqueue(a,key=str(i),retry_base_ms=0) for i in range(4)]
        cs=r.parallel([lambda s=s:r.claim(s) for s in (a,b,a,b)]); live=[c for c in cs if c['job'] is not None]; r.check(len(live)==1,'inflight race one lease')
        c=live[0]; r.request(a,'POST','/v1/jobs/'+c['job']['id']+'/heartbeat',{'lease_token':c['lease_token'],'lease_ms':200}); r.check(r.claim(b)['job'] is None,'heartbeat consumes no additional slot or release')
        r.enqueue(a,key='otherqueue',queue='other'); r.check(r.claim(b,'other')['job'] is not None,'inflight per queue')
        r.enqueue(a,key='otherTenant',tenant='beta'); r.check(r.claim(b,tenant='beta')['job'] is not None,'inflight per tenant')
        f.set_time(NOW+200); n=r.claim(b); r.check(n['job'] is not None,'expired leases do not block inflight')
    yield 'cross_process_inflight_quota_expiry',inflight,('--max-inflight','1')
    def cancel(f):
        a=f.start(); b=f.start(); j=r.enqueue(a); c=r.claim(a); p='/v1/jobs/'+j['id']; x=r.request(b,'POST',p+'/cancel',{})['job']; r.job(x,state='cancelled'); r.check(x['lease_until_ms'] is None,'cancel clears lease'); r.request(a,'POST',p+'/cancel',{})
        for op,extra in [('complete',{'result':{}}),('heartbeat',{'lease_ms':100}),('fail',{'error':'late'})]: r.request(a,'POST',p+'/'+op,{'lease_token':c['lease_token'],**extra},expected=409,code='lease_conflict')
        r.check(r.claim(a)['job'] is None and r.stats(a)['cancelled']==1,'cancel terminal conservation')
        j2=r.enqueue(a,key='done'); c2=r.claim(a); r.request(a,'POST','/v1/jobs/'+j2['id']+'/complete',{'lease_token':c2['lease_token'],'result':{}}); r.request(b,'POST','/v1/jobs/'+j2['id']+'/cancel',{},expected=409,code='invalid_transition'); r.check(r.get(a,j2)['state']=='completed','completed cancel no mutation')
    yield 'cancel_idempotency_and_fencing',cancel,()
    def cancelrace(f):
        a=f.start(); b=f.start(); j=r.enqueue(a); c=r.claim(a); p='/v1/jobs/'+j['id']; rs=r.parallel([lambda:r.request(a,'POST',p+'/cancel',{},expected=(200,409)),lambda:r.request(b,'POST',p+'/complete',{'lease_token':c['lease_token'],'result':{'winner':1}},expected=(200,409))]); final=r.get(a,j)
        r.check(final['state'] in ('completed','cancelled'),'cancel complete race terminal'); r.check(sum('job' in x for x in rs)==1,'one terminal race winner')
        losers=[x for x in rs if 'job' not in x]; r.check(error_code(losers[0])==('invalid_transition' if final['state']=='completed' else 'lease_conflict'),'terminal loser code'); r.check(r.stats(a)['total']==1,'race conservation')
    yield 'cancel_complete_race',cancelrace,()
    def listing(f):
        a=f.start(); b=f.start(); js=[r.enqueue(a,key=str(i),queue='mail' if i%2==0 else 'other') for i in range(7)]; first=r.request(a,'GET','/v1/jobs?limit=2'); r.check(len(first.get('items',[]))==2 and isinstance(first.get('next_cursor'),str) and bool(first['next_cursor']),'first listing page cursor')
        seen=list(first['items']); cursor=first['next_cursor']; r.enqueue(b,key='later'); r.request(b,'POST','/v1/jobs/'+js[4]['id']+'/cancel',{})
        r.request(a,'GET','/v1/jobs?limit=2&cursor='+urllib.parse.quote(cursor,safe=''),tenant='beta',expected=400,code='validation'); r.request(a,'GET','/v1/jobs?queue=mail&limit=2&cursor='+urllib.parse.quote(cursor,safe=''),expected=400,code='validation')
        for _ in range(10):
            page=r.request(a,'GET','/v1/jobs?limit=2&cursor='+urllib.parse.quote(cursor,safe='')); r.check(isinstance(page.get('items'),list) and 'next_cursor' in page,'listing envelope'); seen.extend(page['items']); cursor=page['next_cursor']
            if cursor is None: break
            r.check(isinstance(cursor,str) and bool(cursor),'cursor string or null')
        r.check(cursor is None and unique_ids(seen) and [x['id'] for x in seen]==[x['id'] for x in js],'stable snapshot excludes later insert without skip/duplicate')
        for j in seen: r.job(j)
        filtered=r.request(a,'GET','/v1/jobs?queue=other&limit=100'); r.check([j['id'] for j in filtered['items']]==[j['id'] for j in js if j['queue']=='other'] and filtered['next_cursor'] is None,'queue filtered listing')
        for q in ('limit=0','limit=101','limit=no','cursor=invalid'): r.request(a,'GET','/v1/jobs?'+q,expected=400,code='validation')
    yield 'snapshot_keyset_pagination_tenant_filter_binding',listing,()
    def migration(f):
        if not r.legacy_binary: raise SetupFailure('--legacy-binary required for genuine prior-stage migration')
        old=f.start(r.legacy_binary,flags=()); h=r.request(old,'GET','/health',tenant=None); r.check(h.get('schema_version')==1,'genuine stage1 health')
        body={'queue':'mail','payload':{'old':1}}; created=r.request(old,'POST','/v1/jobs',body,key='legacy',expected=201)['job']; live=r.claim(old,policy=False); completed=r.request(old,'POST','/v1/jobs',{'queue':'done','payload':{}},key='done',expected=201)['job']; donelease=r.claim(old,'done',policy=False); r.request(old,'POST','/v1/jobs/'+completed['id']+'/complete',{'lease_token':donelease['lease_token'],'result':{'kept':1}}); old.stop()
        # Both current processes start against the actual old DB.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: a,b=[future.result() for future in [pool.submit(f.start),pool.submit(f.start)]]
        r.check(r.request(a,'GET','/health',tenant=None).get('schema_version')==2,'migration schema2'); restored=r.get(a,created); r.check(restored['id']==created['id'] and restored['attempts']==1 and restored['state']=='leased' and restored['lease_until_ms']==live['lease_until_ms'] and restored['priority']==0 and restored['retry_base_ms']==0,'legacy live lease and historical policy preserved')
        replay=r.request(b,'POST','/v1/jobs',body,key='legacy',expected=200); r.check(replay.get('replayed') is True and replay['job']['id']==created['id'],'original body legacy replay')
        r.request(a,'POST','/v1/jobs',{**body,'retry_base_ms':1000},key='legacy',expected=409,code='idempotency_conflict'); r.check(r.get(a,completed)['result']=={'kept':1},'legacy result preserved')
        r.request(b,'POST','/v1/jobs/'+created['id']+'/complete',{'lease_token':live['lease_token'],'result':{'oldtoken':True}}); r.check(r.get(a,created)['state']=='completed','old live token completes after migration')
        r.check(r.stats(b)['total']==2,'migration no duplicate rows')
    yield 'genuine_stage1_migration_two_startups_and_original_replay',migration,()
    def future_schema(f):
        with sqlite3.connect(f.db) as conn:
            conn.execute('PRAGMA user_version=999')
            conn.execute('CREATE TABLE future_sentinel (id INTEGER PRIMARY KEY, content TEXT NOT NULL)')
            conn.execute('INSERT INTO future_sentinel VALUES (?,?)',(7,'future schema data must remain intact'))
        original_bytes=f.db.read_bytes()
        with sqlite3.connect('file:'+str(f.db)+'?mode=ro',uri=True) as conn:
            original_schema=conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
            original_rows=conn.execute('SELECT id,content FROM future_sentinel ORDER BY id').fetchall()
        r.current['future_store_before']={'db_bytes_base64':base64.b64encode(original_bytes).decode('ascii'),'sha256':hashlib.sha256(original_bytes).hexdigest(),'byte_count':len(original_bytes),'schema':original_schema,'sentinel_rows':original_rows}
        try:
            s=f.start(); raise Failure('unknown future version unexpectedly started')
        except SetupFailure:
            if not f.servers: raise SetupFailure('future-schema startup was not attempted')
            for server in f.servers:
                try: server.process.wait(timeout=1)
                except subprocess.TimeoutExpired: raise Failure('future schema process did not exit promptly')
                r.check(server.process.returncode!=0,'future schema exits with failure')
        after_bytes=f.db.read_bytes()
        r.current['future_store_after']={'sha256':hashlib.sha256(after_bytes).hexdigest(),'byte_count':len(after_bytes)}
        r.check(after_bytes==original_bytes,'future schema refusal preserves exact original DB bytes')
        with sqlite3.connect('file:'+str(f.db)+'?mode=ro',uri=True) as conn:
            version=conn.execute('PRAGMA user_version').fetchone()[0]
            after_schema=conn.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name').fetchall()
            after_rows=conn.execute('SELECT id,content FROM future_sentinel ORDER BY id').fetchall()
        r.check(version==999 and after_schema==original_schema and after_rows==original_rows,'future schema refusal preserves schema/version/sentinel data')
    yield 'future_schema_startup_refusal',future_schema,()

def main():
    p=argparse.ArgumentParser(); p.add_argument('--binary',required=True); p.add_argument('--stage',type=int,choices=(1,2,3),required=True); p.add_argument('--output',required=True); p.add_argument('--legacy-binary'); p.add_argument('--temp-root'); args=p.parse_args()
    for binary in (args.binary,args.legacy_binary):
        if binary and (not os.path.isabs(binary) or not os.path.isfile(binary) or not os.access(binary,os.X_OK)): p.error('binary must be absolute path to executable')
    # Reserve the output before any requests; preserve every run, including failures.
    output=open(args.output,'x',encoding='utf-8'); runner=Runner(args.binary,args.stage,args.legacy_binary,args.temp_root)
    finished=threading.Event()
    def watchdog():
        if not finished.wait(175):
            with runner.lock: servers=list(runner.active_servers)
            for server in servers:
                if server.process.poll() is None:
                    with contextlib.suppress(ProcessLookupError): server.process.kill()
    threading.Thread(target=watchdog,daemon=True).start()
    try:
        report=runner.run()
    except BaseException as e:
        report={'passed':False,'fatal_error':type(e).__name__+': '+str(e),'scenarios':runner.scenarios,'requests':runner.requests,'duration_ms':(time.monotonic()-runner.start)*1000}
    finally:
        for server in runner.active_servers: server.stop()
        finished.set()
    json.dump(report,output,indent=2); output.write('\n'); output.flush(); os.fsync(output.fileno()); output.close()
    print(json.dumps({'passed':report['passed'],'output':os.path.abspath(args.output),'scenarios':len(runner.scenarios),'requests':len(runner.requests)}))
    return 0 if report['passed'] else 1
if __name__=='__main__': raise SystemExit(main())
