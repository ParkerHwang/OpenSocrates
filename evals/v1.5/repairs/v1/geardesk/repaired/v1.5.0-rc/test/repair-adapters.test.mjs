import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createService} from '../src/service.mjs';
const root=path.resolve(import.meta.dirname,'..'),fixture=path.join(root,'fixtures/catalog.json');
const reserve={type:'reserve',id:'r',memberId:'regular',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:2}],expectedRevision:0,idempotencyKey:'book'};
async function cli(dir,operation,input) {
  const child=spawn(process.execPath,[path.join(root,'cli.mjs'),'--data-dir',dir,'--catalog',fixture,operation]);
  let stdout='',stderr='';child.stdout.on('data',x=>stdout+=x);child.stderr.on('data',x=>stderr+=x);child.stdin.end(JSON.stringify(input));
  return await new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',code=>{try{resolve({code,body:JSON.parse(stdout)});}catch{reject(new Error(stderr));}});});
}
async function server(dir,t) {
  const child=spawn(process.execPath,[path.join(root,'server.mjs'),'--data-dir',dir,'--catalog',fixture,'--port','0']);t.after(()=>child.kill());
  let stdout='',stderr='';child.stderr.on('data',x=>stderr+=x);
  const port=await new Promise((resolve,reject)=>{child.stdout.on('data',x=>{stdout+=x;if(stdout.includes('\n'))resolve(JSON.parse(stdout.split('\n')[0]).port);});child.on('error',reject);child.on('exit',code=>reject(new Error(`Server exited ${code}: ${stderr}`)));});
  return async(operation,body)=>{const response=await fetch(`http://127.0.0.1:${port}/api/${operation}`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});return {status:response.status,body:await response.json()};};
}
test('service, CLI and HTTP reject partial date boundaries without disk/history changes; full default still works',async(t)=>{
  const dir=await mkdtemp(path.join(tmpdir(),'gear-repair-adapter-'));t.after(()=>rm(dir,{recursive:true,force:true}));
  const service=createService({dataDir:dir,catalogPath:fixture,now:()=> 'fixed'}),http=await server(dir,t);
  assert.equal((await service.execute('command',reserve)).revision,1);
  assert.equal((await cli(dir,'command',{type:'checkout',id:'r',expectedRevision:1,idempotencyKey:'out'})).body.revision,2);
  const file=path.join(dir,'store.json'),bytes=await readFile(file,'utf8');
  for(const date of [undefined,null,'',false,0,'2026-02-30','2026-11-05']) {
    const request={type:'return.partial',id:'r',lines:[{itemId:'camera',quantity:1}],expectedRevision:2,idempotencyKey:'reject',...(date===undefined?{}:{returnedOn:date})};
    for(const invoke of [async()=>({body:await service.execute('command',request)}),()=>cli(dir,'command',request),()=>http('command',request)]) {
      const response=await invoke();assert.equal(response.body.ok,false);assert.equal(response.body.error.code,'VALIDATION');assert.equal(response.body.revision,2);
      assert.equal(await readFile(file,'utf8'),bytes);
    }
    const invalidBatch=await http('batch',{expectedRevision:2,idempotencyKey:'invalid-date',commands:[{type:'maintenance.add',id:'m',itemId:'tripod',quantity:1,start:reserve.start,end:reserve.end},requestWithoutMutation(request)]});
    assert.equal(invalidBatch.body.error.code,'VALIDATION');assert.equal(await readFile(file,'utf8'),bytes);
  }
  const partial=await http('command',{type:'return.partial',id:'r',returnedOn:'2026-11-10',lines:[{itemId:'camera',quantity:1}],expectedRevision:2,idempotencyKey:'part'});
  assert.deepEqual([partial.body.data.refund,partial.body.data.lateFee],[4900,100]);
  const full=await cli(dir,'command',{type:'return',id:'r',expectedRevision:3,idempotencyKey:'full'});assert.equal(full.body.data.refund,5000);
  const finalBytes=await readFile(file,'utf8');assert.equal(JSON.parse(finalBytes).revision,4);
  const replay=await http('command',{type:'return',id:'r',expectedRevision:3,idempotencyKey:'full'});assert.deepEqual(replay.body,full.body);assert.equal(await readFile(file,'utf8'),finalBytes);
});
function requestWithoutMutation({expectedRevision,idempotencyKey,...inner}) {return inner;}
test('HTTP and CLI batch failures at beginning, middle and end preserve persisted bytes',async(t)=>{
  const dir=await mkdtemp(path.join(tmpdir(),'gear-repair-batch-'));t.after(()=>rm(dir,{recursive:true,force:true}));
  const http=await server(dir,t);assert.equal((await cli(dir,'command',reserve)).body.revision,1);
  const file=path.join(dir,'store.json'),bytes=await readFile(file,'utf8');
  const commands=[{type:'maintenance.add',id:'m',itemId:'tripod',quantity:1,start:reserve.start,end:reserve.end},{type:'maintenance.remove',id:'m'}];
  for(const index of [0,1,2]) {
    const inner=[...commands];inner.splice(index,0,{type:'maintenance.remove',id:'missing'});
    const request={expectedRevision:1,idempotencyKey:'rollback',commands:inner};
    for(const invoke of [()=>http('batch',request),()=>cli(dir,'batch',request)]) {const failure=await invoke();assert.equal(failure.body.error.code,'NOT_FOUND');assert.equal(failure.body.revision,1);assert.equal(await readFile(file,'utf8'),bytes);}
  }
});
