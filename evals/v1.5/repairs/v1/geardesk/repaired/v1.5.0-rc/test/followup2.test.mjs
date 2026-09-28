import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {emptyStore,command,batch,availability,report} from '../src/domain.mjs';
import {createService} from '../src/service.mjs';

const catalogPath=path.resolve('fixtures/catalog.json');
const catalog=JSON.parse(await readFile(catalogPath,'utf8'));
const booking={memberId:'regular',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:2}]};
const run=(store,type,id,key,extra={})=>command(catalog,store,{type,id,idempotencyKey:key,expectedRevision:store.revision,...extra});

test('partial returns release scheduled units, cap fees, and never refund twice',()=>{
  let store=run(emptyStore(),'reserve','r','r',booking).store;
  store=run(store,'checkout','r','checkout').store;
  assert.equal(store.reservations[0].quote.lateFeePerUnitDay,100);
  const first=run(store,'return.partial','r','partial',{returnedOn:'2026-11-12',lines:[{itemId:'camera',quantity:1}]});store=first.store;
  assert.deepEqual([first.result.refund,first.result.lateFee,first.result.returnedQuantity],[4700,300,1]);
  assert.equal(store.reservations[0].status,'checked_out');
  assert.equal(availability(catalog,store,{start:booking.start,end:booking.end})[0].available,2);
  assert.deepEqual([report(store).depositHeld,report(store).refunded,report(store).lateFees],[5000,4700,300]);
  assert.throws(()=>run(store,'return.partial','r','duplicate',{lines:[{itemId:'camera',quantity:2}]}),{code:'VALIDATION'});
  assert.throws(()=>run(store,'return.partial','r','date',{returnedOn:'2026-02-30',lines:[{itemId:'camera',quantity:1}]}),{code:'VALIDATION'});
  const last=run(store,'return','r','last',{returnedOn:'2027-03-01'});store=last.store;
  assert.deepEqual([last.result.refund,last.result.lateFee,last.result.returnedQuantity],[0,5000,1]);
  assert.deepEqual([report(store).depositHeld,report(store).refunded,report(store).lateFees],[0,4700,5300]);
  assert.equal(store.reservations[0].status,'returned');
  assert.throws(()=>run(store,'return','r','again'),{code:'INVALID_TRANSITION'});
});

test('rate is frozen for new bookings and absent from historical charges',()=>{
  let store=run(emptyStore(),'reserve','r','r',booking).store;
  store=run(store,'checkout','r','c').store;
  const changed={...catalog,pricing:{...catalog.pricing,lateFeePerUnitDay:999}};
  const returned=command(changed,store,{type:'return',id:'r',returnedOn:'2026-11-10',expectedRevision:2,idempotencyKey:'ret'});
  assert.equal(returned.result.lateFee,200);
  const noRate={...catalog,pricing:{weekendBps:15000}};
  let old=command(noRate,emptyStore(),{type:'reserve',id:'old',expectedRevision:0,idempotencyKey:'old',...booking}).store;
  old=run(old,'checkout','old','old-c').store;
  assert.equal(run(old,'return','old','old-r',{returnedOn:'2026-11-20'}).result.lateFee,0);
});

test('batch uses command rules atomically with isolated replay identity',()=>{
  const request={expectedRevision:0,idempotencyKey:'batch',commands:[{type:'reserve',id:'r',...booking},{type:'checkout',id:'r'},{type:'return.partial',id:'r',lines:[{itemId:'camera',quantity:1}],returnedOn:'2026-11-10'}]};
  const outcome=batch(catalog,emptyStore(),request);
  assert.equal(outcome.store.revision,3);assert.equal(outcome.store.audit.length,3);
  assert.deepEqual(outcome.store.audit.map(x=>x.type),request.commands.map(x=>x.type));
  assert.equal(outcome.result[2].refund,4900);
  assert.equal(Object.keys(outcome.store.idempotency).length,0);
  assert.equal(batch(catalog,outcome.store,request).replay,true);
  assert.throws(()=>batch(catalog,outcome.store,{...request,commands:[...request.commands.slice(0,2)]}),{code:'IDEMPOTENCY_CONFLICT'});
  assert.equal(command(catalog,outcome.store,{type:'return',id:'r',expectedRevision:3,idempotencyKey:'batch'}).store.revision,4);
  const failed={...request,idempotencyKey:'failed',commands:[...request.commands,{type:'return.partial',id:'r',lines:[{itemId:'camera',quantity:2}]}]};
  assert.throws(()=>batch(catalog,emptyStore(),failed),{code:'VALIDATION'});
  assert.equal(emptyStore().revision,0);
  assert.throws(()=>batch(catalog,emptyStore(),{...request,commands:[{...request.commands[0],idempotencyKey:'inner'}]}),{code:'VALIDATION'});
});

test('legacy store migration preserves history and failed writes preserve bytes',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-v2-'));
  const file=path.join(dir,'store.json');
  try {
    const original=await readFile(path.resolve('fixtures/legacy-v1-store.json'),'utf8');await writeFile(file,original);
    const service=createService({dataDir:dir,catalogPath});
    assert.equal((await service.execute('report')).data.refunded,1000);
    const failed=await service.execute('batch',{expectedRevision:7,idempotencyKey:'fail',commands:[{type:'return',id:'legacy-active',returnedOn:'2026-11-10'},{type:'checkout',id:'legacy-cancelled'}]});
    assert.equal(failed.ok,false);assert.equal(await readFile(file,'utf8'),original);
    const success=await service.execute('command',{type:'return',id:'legacy-active',returnedOn:'2026-11-20',expectedRevision:7,idempotencyKey:'new'});
    assert.equal(success.ok,true);assert.equal(success.data.lateFee,0);
    const migrated=JSON.parse(await readFile(file,'utf8'));
    assert.equal(migrated.schemaVersion,2);assert.equal(migrated.revision,8);
    assert.deepEqual(migrated.audit.slice(0,7),JSON.parse(original).audit);
    assert.deepEqual(migrated.idempotency['legacy-seed-4'],JSON.parse(original).idempotency['legacy-seed-4']);
    assert.equal(migrated.reservations.find(x=>x.id==='legacy-returned').refunded,1000);
    assert.equal(migrated.reservations.find(x=>x.id==='legacy-cancelled').status,'cancelled');
    assert.equal((await service.execute('report')).data.refunded,6000);
  } finally {await rm(dir,{recursive:true,force:true});}
});

test('CLI and HTTP batch share service state and stale revision protection',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-v2-'));
  const child=spawn(process.execPath,['server.mjs','--data-dir',dir,'--catalog',catalogPath,'--port','0']);
  try {
    const port=await new Promise((resolve,reject)=>{let output='';child.stdout.on('data',x=>{output+=x;const i=output.indexOf('\n');if(i>=0) resolve(JSON.parse(output.slice(0,i)).port);});child.on('error',reject);child.on('exit',x=>reject(new Error('server exited '+x)));});
    const payload={expectedRevision:0,idempotencyKey:'http-batch',commands:[{type:'reserve',id:'r',...booking},{type:'checkout',id:'r'}]};
    const response=await fetch(`http://127.0.0.1:${port}/api/batch`,{method:'POST',body:JSON.stringify(payload)});
    assert.equal(response.status,200);assert.equal((await response.json()).revision,2);
    const cli=await new Promise((resolve,reject)=>{const proc=spawn(process.execPath,['cli.mjs','--data-dir',dir,'--catalog',catalogPath,'batch']);let output='';proc.stdout.on('data',x=>output+=x);proc.on('error',reject);proc.on('close',()=>resolve(JSON.parse(output)));proc.stdin.end(JSON.stringify(payload));});
    assert.equal(cli.ok,true);assert.equal(cli.revision,2);
    const stale=await fetch(`http://127.0.0.1:${port}/api/batch`,{method:'POST',body:JSON.stringify({...payload,idempotencyKey:'stale'})});
    assert.equal(stale.status,409);assert.equal((await stale.json()).error.code,'REVISION_CONFLICT');
  } finally {child.kill();await rm(dir,{recursive:true,force:true});}
});
