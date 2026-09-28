import concurrent.futures, json, os, pathlib, sqlite3, subprocess, tempfile, time, urllib.request, urllib.error
BIN = str(pathlib.Path.cwd()/'server')
PYTHON=__import__('sys').executable
def start(db, port):
 p=subprocess.Popen([BIN,'--db',db,'--listen',f'127.0.0.1:{port}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for _ in range(100):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.2) as r:
    assert r.status==200; return p
  except Exception: time.sleep(.03)
 raise RuntimeError(p.stderr.read().decode())
def call(port,method,path,body=None,key=None,tenant='t'):
 h={'X-Tenant':tenant}
 if key:h['Idempotency-Key']=key
 if body is not None:h['Content-Type']='application/json'
 data=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request(f'http://127.0.0.1:{port}{path}',data=data,headers=h,method=method)
 try:r=urllib.request.urlopen(req,timeout=5)
 except urllib.error.HTTPError as e:r=e
 with r:return r.status,json.loads(r.read())
def expect(v,status):assert v[0]==status,v;return v[1]
with tempfile.TemporaryDirectory() as d:
 db=d+'/new.db'; p=start(db,19031);p2=start(db,19032)
 try:
  a=expect(call(19031,'POST','/accounts',{'name':'A','opening':100},'a'),201)
  expect(call(19031,'POST','/accounts',{'name':'B','opening':0},'b'),201)
  assert expect(call(19032,'POST','/accounts',{'opening':100,'name':'A'},'a'),201)==a
  expect(call(19032,'POST','/accounts',{'name':'C','opening':0},'c'),201)
  assert expect(call(19031,'POST','/accounts',{'name':'D','opening':0},'a'),409)['error']['code']=='idempotency_conflict'
  with concurrent.futures.ThreadPoolExecutor(16) as pool:
   vals=list(pool.map(lambda _:call(19031 if _%2 else 19032,'POST','/transfers',{'from':'A','to':'B','amount':10},'shared'),range(16)))
  assert all(v==vals[0] for v in vals),vals
  t=expect(vals[0],201)['transfer']
  batch={'transfers':[{'from':'A','to':'B','amount':5},{'from':'A','to':'B','amount':999}]}
  assert expect(call(19031,'POST','/batches',batch,'fail'),409)['error']['code']=='insufficient'
  assert expect(call(19032,'GET','/accounts/A'),200)['account']['balance']==90
  h=expect(call(19031,'POST','/holds',{'account':'A','amount':20},'h'),201)['hold']
  assert expect(call(19032,'GET','/accounts/A'),200)['account']['available']==70
  cap=expect(call(19032,'POST',f"/holds/{h['id']}/capture",{'to':'C'},'cap'),200)
  assert cap['accounts'][0]['balance']==70
  assert expect(call(19031,'POST',f"/holds/{h['id']}/release",{},'rel'),409)['error']['code']=='terminal'
  rev=expect(call(19031,'POST',f"/transfers/{cap['transfer']['id']}/reverse",{},'rev'),200)
  assert rev['accounts'][0]['balance']==90
  assert expect(call(19032,'POST',f"/transfers/{rev['reversal']['id']}/reverse",{},'rev2'),409)['error']['code']=='terminal'
  page=expect(call(19031,'GET','/entries?after=0&limit=2'),200)
  assert len(page['entries'])==2 and page['has_more']
  snap=page['snapshot']; after=page['next_after']; seen=page['entries'][:]
  while True:
   nxt=expect(call(19032,'GET',f'/entries?after={after}&limit=2&snapshot={snap}'),200)
   seen+=nxt['entries']; after=nxt['next_after']
   if not nxt['has_more']:break
  assert [x['seq'] for x in seen]==list(range(1,snap+1))
  summ=expect(call(19031,'GET',f'/summary?snapshot={snap}'),200)
  assert summ['totals']['balance']==100 and summ['totals']['reserved']==0 and summ['entry_count']==snap
  assert expect(call(19031,'GET','/summary?snapshot=2'),200)['totals']['balance']==100
  assert expect(call(19031,'POST','/holds',{'account':'A','amount':1,'version':None},'bad'),400)['error']['code']=='invalid'
  print('new database: concurrency, replay, rollback, holds, capture, reversal, pagination, historical summary passed')
 finally:
  for proc in (p,p2):proc.terminate()
  for proc in (p,p2):proc.wait(timeout=5)
 legacy=d+'/legacy.db'; subprocess.run([PYTHON,'legacy/produce.py',legacy],check=True)
 orig=sqlite3.connect(legacy).execute('select key,value from legacy_notes order by key').fetchall()
 lp=start(legacy,19033)
 try:
  s=expect(call(19033,'GET','/summary',tenant='old'),200)
  assert s['totals']['balance']==120 and s['entry_count']==6
  ents=expect(call(19033,'GET','/entries',tenant='old'),200)['entries']
  assert [e['kind'] for e in ents]==['opening','opening','transfer','transfer','transfer','transfer']
  assert {e['legacy_id'] for e in ents if e['kind']=='transfer'}=={7,11}
  assert expect(call(19033,'GET','/accounts/alpha',tenant='old'),200)['account']['version']==3
  assert sqlite3.connect(legacy).execute('pragma user_version').fetchone()[0]==2
  assert sqlite3.connect(legacy).execute('select key,value from legacy_notes order by key').fetchall()==orig
  print('legacy migration: history, versions, original notes, schema version passed')
 finally:lp.terminate();lp.wait(timeout=5)
