"""Deterministic checker controls: scripted localhost responses, no queue implementation."""
import contextlib, copy, http.server, json, pathlib, threading, time, tempfile, sqlite3, types, unittest
import acceptance as a

class Boundary:
    def __init__(self, responses):
        self.responses=list(responses); self.errors=[]; outer=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self): self.respond()
            def do_POST(self): self.respond()
            def log_message(self,*args): pass
            def respond(self):
                self.rfile.read(int(self.headers.get('Content-Length',0)))
                if not outer.responses:
                    outer.errors.append('unexpected extra request'); status,body=500,{}
                else: status,body=outer.responses.pop(0)
                data=json.dumps(body).encode(); self.send_response(status); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
        self.http=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler); self.url='http://127.0.0.1:'+str(self.http.server_port); self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
    def close(self): self.http.shutdown(); self.http.server_close(); self.thread.join()

class FakeFixture:
    def __init__(self,server): self.server=server; self.now=a.NOW
    def start(self,*args,**kwargs): return self.server
    def set_time(self,t): self.now=t

def job(i=1,state='ready',attempts=0,deadline=None):
    return dict(id=str(i),tenant='alpha',queue='mail',payload={'n':i-1},state=state,attempts=attempts,max_attempts=3,created_seq=i,created_at_ms=a.NOW,available_at_ms=a.NOW,lease_until_ms=deadline,last_error=None,result=None,priority=0,retry_base_ms=1000)
def stats(n): return dict(total=n,ready=n,leased=0,completed=0,dead=0,cancelled=0)
def error(code): return {'error':{'code':code,'message':'synthetic control'}}

class Controls(unittest.TestCase):
    def run_scenario(self,name,responses,should_fail):
        boundary=Boundary(responses); r=a.Runner('/unused',2); r.current={'name':name,'checks':[]}; fn=next(fn for n,fn,flags in a.scenarios(r) if n==name)
        try:
            if should_fail:
                with self.assertRaises(a.Failure): fn(FakeFixture(boundary))
            else: fn(FakeFixture(boundary)); self.assertFalse(boundary.responses); self.assertFalse(boundary.errors)
        finally: boundary.close()
        self.assertTrue(r.requests,'real localhost requests recorded')
        return r
    def test_additive_get_fields_pass(self):
        initial=job(); initial['payload']={'n':1}
        self.run_scenario('basic_semantic_fields',[(200,{'ok':True,'schema_version':2}),(201,{'job':{**initial,'enqueue_metadata':'one'},'replayed':False}),(200,{'job':{**initial,'read_metadata':'two'}}),(200,stats(1))],False)
    def test_required_get_field_change_rejected(self):
        initial=job(); initial['payload']={'n':1}
        self.run_scenario('basic_semantic_fields',[(200,{'ok':True,'schema_version':2}),(201,{'job':initial,'replayed':False}),(200,{'job':{**initial,'last_error':'unexpected'}})],True)
    def test_additive_completion_fields_pass(self):
        initial=job(); initial['payload']={'n':1}
        leased={**initial,'state':'leased','attempts':1,'lease_until_ms':a.NOW+100}
        done={**initial,'state':'completed','attempts':1,'result':{'answer':42}}
        count={**stats(0),'total':1,'completed':1}
        responses=[(201,{'job':initial,'replayed':False}),(200,{'job':leased,'lease_token':'token','lease_until_ms':a.NOW+100}),(200,{'job':{**done,'completion_metadata':1}}),(200,{'job':{**done,'completion_metadata':2,'extra':True}}),(409,error('lease_conflict')),(409,error('lease_conflict')),(200,{'job':{**done,'read_metadata':3}}),(200,count)]
        self.run_scenario('completion_result_and_exact_replay',responses,False)
    def test_required_completion_field_change_rejected(self):
        initial=job(); initial['payload']={'n':1}
        leased={**initial,'state':'leased','attempts':1,'lease_until_ms':a.NOW+100}
        done={**initial,'state':'completed','attempts':1,'result':{'answer':42}}
        responses=[(201,{'job':initial,'replayed':False}),(200,{'job':leased,'lease_token':'token','lease_until_ms':a.NOW+100}),(200,{'job':done}),(200,{'job':{**done,'result':{'answer':43}}})]
        self.run_scenario('completion_result_and_exact_replay',responses,True)
    def test_semantic_comparison_requires_all_fields(self):
        full=job()
        self.assertTrue(a.semantic_job_equal(full,{**full,'extra':1},2))
        for field in a.JOB_FIELDS+('priority','retry_base_ms'):
            missing=dict(full); del missing[field]
            self.assertFalse(a.semantic_job_equal(full,missing,2),field)
        self.assertTrue(a.semantic_job_equal({k:v for k,v in full.items() if k not in ('priority','retry_base_ms')},full,1))
    def future_control(self,mutate):
        r=a.Runner('/unused',2); r.current={'name':'future_control','checks':[]}
        fn=next(fn for name,fn,flags in a.scenarios(r) if name=='future_schema_startup_refusal')
        with tempfile.TemporaryDirectory() as directory:
            class Refusal:
                db=pathlib.Path(directory)/'future.sqlite'
                servers=[types.SimpleNamespace(process=types.SimpleNamespace(returncode=1,wait=lambda timeout:1))]
                def start(self):
                    if mutate:
                        with sqlite3.connect(self.db) as conn: conn.execute("UPDATE future_sentinel SET content='rewritten'")
                    raise a.SetupFailure('synthetic startup refusal')
            if mutate:
                with self.assertRaises(a.Failure): fn(Refusal())
            else: fn(Refusal())
        self.assertIn('db_bytes_base64',r.current['future_store_before'])
        return r
    def test_future_refusal_preserves_bytes_positive(self): self.future_control(False)
    def test_future_refusal_with_mutation_rejected(self):
        r=self.future_control(True)
        self.assertEqual(r.current['checks'][-1]['name'],'future schema refusal preserves exact original DB bytes')
    def test_duplicate_ids_rejected(self):
        responses=[(400,error('validation')),(200,stats(0)),(201,{'jobs':[job(1)]*4,'replayed':False})]
        r=self.run_scenario('atomic_bulk_and_replay',responses,True)
        self.assertFalse(r.current['checks'][-1]['passed'])
    def test_partial_batch_write_rejected(self):
        r=self.run_scenario('atomic_bulk_and_replay',[(400,error('validation')),(200,stats(1))],True)
        self.assertEqual(r.current['checks'][-1]['name'],'batch invalid suffix rollback')
    def test_correct_batch_boundary_passes(self):
        js=[job(i) for i in range(1,5)]
        self.run_scenario('atomic_bulk_and_replay',[(400,error('validation')),(200,stats(0)),(201,{'jobs':js,'replayed':False}),(200,{'jobs':js,'replayed':True}),(400,error('validation')),(200,stats(4))],False)
    def test_wrong_retry_delay_rejected(self):
        j=job(); j['retry_base_ms']=200; j['max_attempts']=4
        leased={**j,'state':'leased','attempts':1,'lease_until_ms':a.NOW+100}
        failed={**j,'attempts':1,'last_error':'retry','available_at_ms':a.NOW+226}
        self.run_scenario('fail_and_expiry_backoff_boundaries',[(201,{'job':j,'replayed':False}),(200,{'job':leased,'lease_token':'token','lease_until_ms':a.NOW+100}),(200,{'job':failed})],True)
    def test_stale_token_false_success_rejected(self):
        boundary=Boundary([(200,{'job':job(state='completed')})]); r=a.Runner('/unused',2); r.current={'name':'stale_control','checks':[]}
        try:
            with self.assertRaises(a.Failure): r.request(boundary,'POST','/v1/jobs/1/complete',{'lease_token':'stale','result':{}},expected=409,code='lease_conflict')
        finally: boundary.close()
        self.assertEqual(r.requests[0]['status'],200)
    def test_expected_conflict_boundary_passes(self):
        boundary=Boundary([(409,error('lease_conflict'))]); r=a.Runner('/unused',2); r.current={'name':'conflict_control','checks':[]}
        try: r.request(boundary,'POST','/v1/jobs/1/complete',{'lease_token':'stale','result':{}},expected=409,code='lease_conflict')
        finally: boundary.close()
    def test_total_request_deadline(self):
        class Slow(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                threading.Event().wait(4)
                with contextlib.suppress(OSError): self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Slow); thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        class Endpoint: url='http://127.0.0.1:'+str(server.server_port)
        r=a.Runner('/unused',2); r.current={'name':'timeout_control','checks':[]}; started=time.monotonic()
        try:
            with self.assertRaises(a.Failure): r.request(Endpoint(),'GET','/health',tenant=None)
            self.assertLess(time.monotonic()-started,3.2)
            self.assertIsNotNone(r.requests[0]['error'])
        finally: server.shutdown(); server.server_close(); thread.join()
    def test_error_code_required(self):
        boundary=Boundary([(409,error('other'))]); r=a.Runner('/unused',2); r.current={'name':'code_control','checks':[]}
        try:
            with self.assertRaises(a.Failure): r.request(boundary,'POST','/v1/jobs/1/complete',{},expected=409,code='lease_conflict')
        finally: boundary.close()
if __name__=='__main__': unittest.main()
