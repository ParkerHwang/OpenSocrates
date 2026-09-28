"""Narrow CI portability bridge; no outcome model or unchanged live runs."""
import errno,hashlib,json,os,signal,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
R=Path('$REPO');O=Path('$VERIFIER_TEMP');COMMIT='6eb8d3774f3a9032f580359b38b8bf11208f70d3';BASE='b32dbdba4e53ad08e90e4a4a97a30d4fe57c5a27';sys.dont_write_bytecode=True;sys.path.insert(0,str(R/'src'));tempfile.tempdir=str(O);os.environ['PYTHONDONTWRITEBYTECODE']='1'
from opensocrates.orchestration import paths,adapter
from opensocrates.orchestration.paths import BoundaryError,BoundDirectory

def sha(b):return hashlib.sha256(b).hexdigest()
def git(p,c=COMMIT):return subprocess.check_output(['git','show',c+':'+p],cwd=R)
checks=[]
def result(name,passed,**evidence):checks.append({'id':name,'passed':bool(passed),**evidence})
# Missing/invalid required flags must fail closed before creating directory handles.
for name,flag,value,delete in [('nofollow_missing','O_NOFOLLOW',None,True),('directory_zero','O_DIRECTORY',0,False),('nofollow_boolean','O_NOFOLLOW',True,False)]:
 proxy=SimpleNamespace(O_RDONLY=os.O_RDONLY,O_DIRECTORY=os.O_DIRECTORY,O_NOFOLLOW=os.O_NOFOLLOW,O_CLOEXEC=getattr(os,'O_CLOEXEC',0))
 if delete:delattr(proxy,flag)
 else:setattr(proxy,flag,value)
 with patch.object(paths,'os',proxy):
  try:BoundDirectory._flags();reason=None
  except BoundaryError as e:reason=str(e)
 result(name,reason=='directory_capability_unavailable',reason=reason,scope='source-level simulated missing/invalid flag')
fixture=O/'fixture';fixture.mkdir(exist_ok=True);(fixture/'source.txt').write_text('synthetic scope\n');valid=BoundDirectory._flags();opened=[];original_append=BoundDirectory._append

def tracked_append(self,name,fd):opened.append(fd);return original_append(self,name,fd)
with patch.object(BoundDirectory,'_append',new=tracked_append),patch.object(BoundDirectory,'_flags',side_effect=[valid,BoundaryError('directory_capability_unavailable')]):
 try:BoundDirectory(str(fixture));reason=None
 except BoundaryError as e:reason=str(e)
closed=[]
for fd in opened:
 try:os.fstat(fd);closed.append(False)
 except OSError as e:closed.append(e.errno==errno.EBADF)
result('partial_initialization_closes_handles',reason=='directory_capability_unavailable' and len(opened)==1 and all(closed),opened_handles=len(opened),all_closed=all(closed))
# Windows process cleanup never references POSIX group signaling; POSIX behavior remains.
class Process:
 pid=987654321
 def __init__(self):self.actions=[];self.n=0
 def poll(self):return None
 def terminate(self):self.actions.append('terminate')
 def kill(self):self.actions.append('kill')
 def wait(self,timeout=None):
  self.actions.append('wait');self.n+=1
  if self.n==1:raise subprocess.TimeoutExpired('synthetic',timeout)
  return 0
for platform in ('win32','darwin'):
 process=Process()
 with patch.object(adapter.sys,'platform',platform),patch.object(adapter.os,'killpg') as killpg:
  adapter._stop(process);signals=[call.args[1] for call in killpg.call_args_list]
 expected=process.actions==['terminate','wait','kill','wait'] and not signals if platform=='win32' else process.actions==['wait','wait'] and signals==[signal.SIGTERM,signal.SIGKILL]
 result('cleanup_'+platform,expected,actions=process.actions,group_signals=[int(s) for s in signals],scope='mocked process, no signals sent')
with patch.object(adapter.sys,'platform','win32'),patch.object(adapter.CodexAdapter,'_inspect') as inspected:
 try:adapter.CodexAdapter('/synthetic/no-client').probe();reason=None
 except BoundaryError as e:reason=str(e)
 result('windows_adapter_explicitly_unavailable',reason=='sandbox_platform_unavailable' and inspected.call_count==0,reason=reason,inspection_calls=inspected.call_count)
with patch.object(paths,'os',SimpleNamespace(name='nt')):
 try:BoundDirectory(str(fixture));reason=None
 except BoundaryError as e:reason=str(e)
 result('nonposix_directory_explicitly_unavailable',reason=='directory_capability_unavailable',reason=reason)
# Local Windows-stub type check, with all cache/temp output kept here.
type_argv=[str(R/'.venv/bin/python'),'-B','-m','mypy','--platform','win32','--cache-dir',str(O/'mypy-cache'),'--config-file',str(R/'pyproject.toml'),'src'];env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','MYPYPATH':str(R/'src'),'TMPDIR':str(O)};typed=subprocess.run(type_argv,cwd=R,env=env,capture_output=True,text=True);(O/'windows-target-mypy.txt').write_text(typed.stdout+typed.stderr);result('windows_target_typing',typed.returncode==0,argv=type_argv,exit_code=typed.returncode,stdout=typed.stdout.strip(),stderr=typed.stderr.strip(),scope='macOS host with mypy --platform win32; not hosted Windows execution')
# The rebuilt frozen runtime exercises regular required-flag source setup and no-follow rejection.
native=R/'dist/codex/runtime/darwin-arm64/opensocrates-runtime/opensocrates-runtime';native_sha=sha(native.read_bytes());result('native_expected_identity',native_sha=='329d71719667bebdf42df29d2dc2440429d3c9e70b212ae745f8ebfd949434f9',sha256=native_sha)
request={'schema':'opensocrates.orchestration.request/1.0.0','operation':'run','run_id':'00000000-0000-4000-8000-000000000101','task_id':'00000000-0000-4000-8000-000000000102','revision':1,'authorization':{'reference':'fixture:ci-portability','attribution':'operator_declared'},'model':{'name':'gpt-6-astra','effort':'max'},'locale':'en','objective':'Synthetic setup capability check; missing client prevents any role/model invocation.','required_artifacts':['out.txt'],'constraints':[{'id':'r','text':'Read scoped synthetic source. No role or model launch is allowed in this capability fixture.'}],'permissions':[],'prohibitions':[],'source_root':str(fixture),'sources':[{'id':'s','path':'source.txt','sha256':'sha256:'+sha((fixture/'source.txt').read_bytes())}],'candidate_root':str(O/'never-published-regular'),'client_path':str(O/'intentionally-unavailable-client'),'repair_limit':0,'memory':None,'handoff':['Current synthetic contract only.'],'units':[{'unit_id':'u','domain':'software','task_kind':'mechanical','role':'production','objective':'Synthetic setup only.','owned_paths':['out.txt'],'dependencies':[],'source_ids':['s'],'requirement_ids':['r'],'specialists':[],'obligations':[{'id':'o','requirement_id':'r','description':'Synthetic setup only.','required':True}],'checks':[],'seed':None}]}
nenv={'PATH':'/usr/bin:/bin','LANG':'C','TMPDIR':str(O),'PYTHONDONTWRITEBYTECODE':'1'}
for mode in ('regular','symlink'):
 q=json.loads(json.dumps(request));q['candidate_root']=str(O/('never-published-'+mode))
 if mode=='symlink':(fixture/'linked.txt').symlink_to(fixture/'source.txt');q['sources'][0]['path']='linked.txt'
 proc=subprocess.run([str(native),'orchestrate'],input=json.dumps(q),env=nenv,capture_output=True,text=True);value=json.loads(proc.stdout);(O/(mode+'-native-response.json')).write_text(json.dumps(value,indent=2)+'\n');expected=(value['units'][0]['reason']=='client_or_sandbox_unavailable') if mode=='regular' else ('setup_capability_or_source_unavailable' in value['limitations']);result('native_source_'+mode,proc.returncode==3 and value['status']=='unavailable' and value['calls']==[] and expected and not Path(q['candidate_root']).exists(),exit_code=proc.returncode,status=value['status'],calls=len(value['calls']),limitations=value['limitations'],scope='real frozen runtime, intentionally nonexistent client; no outcome calls')
# One positive read and one prohibited write through the same current native CLI sandbox primitive.
cli=Path('$CODEX_CLIENT');cli_sha=sha(cli.read_bytes())
for name,args in [('read',['/bin/cat','source.txt']),('write',['/usr/bin/touch','forbidden-write'])]:
 argv=[str(cli),'sandbox','-P',':read-only','-C',str(fixture),'--',*args];proc=subprocess.run(argv,env=nenv,capture_output=True,text=True);ok=proc.returncode==0 and proc.stdout=='synthetic scope\n' if name=='read' else proc.returncode!=0 and not (fixture/'forbidden-write').exists();result('native_sandbox_'+name,ok,argv=argv,exit_code=proc.returncode,stdout_sha256=sha(proc.stdout.encode()),stderr_sha256=sha(proc.stderr.encode()),scope='actual local sandbox, no model process')
# Exact unchanged-source bridge, without replaying prior outcome tasks.
prior=json.loads((R/'evals/v1.5/orchestration/v1/validation.json').read_text())['runtime_package_inputs'];changed=[];mismatches=[]
for path,old in prior.items():
 new=sha(git(path));old=old.removeprefix('sha256:')
 if new!=old:changed.append(path)
 if sha((R/path).read_bytes())!=new:mismatches.append(path)
result('exact_source_identity_bridge',set(changed)=={'src/opensocrates/orchestration/adapter.py','src/opensocrates/orchestration/paths.py'} and not mismatches,prior_input_count=len(prior),changed=changed,unchanged=len(prior)-len(changed),working_tree_mismatches=mismatches)
# Native assets are unchanged data: compare all schemas plus guidance sets previously qualified.
package=R/'dist/codex';internal=package/'runtime/darwin-arm64/opensocrates-runtime/_internal';assets=[]
for path in sorted((R/'schemas/v1').glob('*.schema.json')):assets.append((str(path.relative_to(R)),str(path.relative_to(R)),str(path.relative_to(R))))
shared=R/'plugin-src/shared';guide_paths=list((shared/'orchestration/v0.1.0').glob('*.md'))+list((shared/'coding-specialists/v0.1.1').glob('*.md'))+list((shared/'assistance').glob('verification.*.md'))
for path in sorted(guide_paths):rel=str(path.relative_to(shared));assets.append((str(path.relative_to(R)),'skills/opensocrates/references/'+rel,'plugin-src/shared/'+rel))
asset_errors=[]
for source,outer,embedded in assets:
 expected=git(source)
 if expected!=git(source,BASE) or (package/outer).read_bytes()!=expected or (internal/embedded).read_bytes()!=expected:asset_errors.append(source)
result('schema_guide_native_identity_bridge',not asset_errors,schemas=len(list((R/'schemas/v1').glob('*.schema.json'))),guides=len(guide_paths),copies_checked=2*len(assets),mismatches=asset_errors)
# Frozen v1 is read-only and recorded, not modified by this recheck.
v1=R/'evals/v1.5/orchestration/v1';v1_hashes={str(p.relative_to(v1)):sha(p.read_bytes()) for p in sorted(v1.rglob('*')) if p.is_file()};out={'schema':'independent-ci-portability-bridge/1','source_commit':COMMIT,'prior_commit':BASE,'scope':'Required-flag rejection/cleanup/platform availability, local Windows-target typing, current native source/sandbox boundary and unchanged schema/guide identity only.','checks':checks,'all_expected':all(x['passed'] for x in checks),'outcome_model_calls':0,'native_binary_sha256':native_sha,'codex_client_sha256':cli_sha,'affected_source_hashes':{p:sha(git(p)) for p in ('src/opensocrates/orchestration/adapter.py','src/opensocrates/orchestration/paths.py','tools/check_orchestration.py')},'frozen_v1_snapshot_hash':sha(json.dumps(v1_hashes,sort_keys=True,separators=(',',':')).encode()),'limits':['Missing/invalid OS flags and Windows process cleanup were source-level simulations on macOS; no hosted Windows runtime test.','Native macOS exercised positive required flags and actual no-follow/sandbox write denial. It did not simulate missing native OS constants.','Hosted Windows CI after push remains separate and pending. No prior live-v2/v3 model or outcome re-execution.']};(O/'results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'root':str(O),'all_expected':out['all_expected'],'checks':len(checks),'failed':[x for x in checks if not x['passed']],'report_sha256':sha((O/'results.json').read_bytes())},indent=2))
