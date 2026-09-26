import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {emptyStore,quote,availability,command,maintenance,report} from '../src/domain.mjs';
import {createService} from '../src/service.mjs';

const catalog=JSON.parse(await readFile(new URL('../fixtures/catalog.json',import.meta.url),'utf8'));
const fixture=path.resolve('fixtures/catalog.json');
const booking={memberId:'club',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:1}]};
const mutate=(store,type,id,key,fields={})=>command(catalog,store,{type,id,idempotencyKey:key,expectedRevision:store.revision,...fields}).store;

test('weekend rounding is per unit and day; pricing defaults and cap',()=>{
  const priced=quote(catalog,emptyStore(),booking);
  assert.deepEqual([priced.lines[0].rental,priced.rentalSubtotal,priced.discount,priced.rentalTotal,priced.deposit,priced.totalDue],[4800,4800,300,4500,5000,9500]);
  const legacy={...catalog,pricing:undefined,items:catalog.items.map(item=>item.id==='camera'?{...item,rate:1}:item)};
  const two=quote(legacy,emptyStore(),{...booking,lines:[{itemId:'camera',quantity:2}]});
  assert.deepEqual([two.rentalSubtotal,two.discount],[6,1]);
  const rounded=quote({...legacy,pricing:{weekendBps:15000}},emptyStore(),{...booking,lines:[{itemId:'camera',quantity:2}]});
  assert.deepEqual([rounded.rentalSubtotal,rounded.discount],[10,1]);
});

test('maintenance uses daily overlap, replay, removal and audit',()=>{
  let store=emptyStore();
  store=mutate(store,'reserve','booking','r',{...booking,start:'2026-11-01',end:'2026-11-03',lines:[{itemId:'camera',quantity:2}]});
  store=mutate(store,'maintenance.add','m1','m1',{itemId:'camera',start:'2026-11-03',end:'2026-11-05',quantity:2});
  assert.equal(availability(catalog,store,{start:'2026-11-01',end:'2026-11-05'})[0].available,1);
  assert.equal(maintenance(store).length,1);
  assert.equal(report(store).maintenanceCount,1);
  assert.throws(()=>mutate(store,'maintenance.add','m2','m2',{itemId:'camera',start:'2026-11-02',end:'2026-11-04',quantity:2}),{code:'CAPACITY'});
  assert.throws(()=>quote(catalog,store,{...booking,start:'2026-11-03',end:'2026-11-04',lines:[{itemId:'camera',quantity:2}]}),{code:'CAPACITY'});
  assert.throws(()=>mutate(store,'maintenance.add','m1','different',{itemId:'camera',start:'2026-11-05',end:'2026-11-06',quantity:1}),{code:'VALIDATION'});
  const removal={type:'maintenance.remove',id:'m1',idempotencyKey:'remove',expectedRevision:store.revision};
  const first=command(catalog,store,removal);store=first.store;
  assert.equal(command(catalog,store,removal).replay,true);
  assert.equal(report(store).maintenanceCount,0);
  assert.equal(report(store).auditCount,3);
  assert.equal(availability(catalog,store,{start:'2026-11-03',end:'2026-11-05'})[0].available,3);
  assert.throws(()=>mutate(store,'maintenance.remove','m1','missing'),{code:'NOT_FOUND'});
});

test('old store retains history when maintenance is added; historical pricing stays frozen',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-followup-'));
  const catalogPath=path.join(dir,'catalog.json');
  try {
    const oldCatalog={...catalog,pricing:undefined,items:catalog.items.map(item=>item.id==='camera'?{...item,rate:1000}:item)};
    await writeFile(catalogPath,JSON.stringify(oldCatalog));
    let old=emptyStore();
    old=command(oldCatalog,old,{type:'reserve',id:'old',idempotencyKey:'old',expectedRevision:0,...booking}).store;
    delete old.maintenance;
    await writeFile(path.join(dir,'store.json'),JSON.stringify(old));
    await writeFile(catalogPath,JSON.stringify(catalog));
    const service=createService({dataDir:dir,catalogPath});
    assert.equal((await service.execute('reservations')).data[0].quote.rentalTotal,2700);
    assert.equal((await service.execute('quote',{...booking,start:'2026-11-10',end:'2026-11-11'})).data.rentalTotal,1080);
    const added=await service.execute('command',{type:'maintenance.add',id:'m',itemId:'camera',start:'2026-11-10',end:'2026-11-11',quantity:1,idempotencyKey:'m',expectedRevision:1});
    assert.equal(added.ok,true);
    assert.equal((await service.execute('maintenance')).data.length,1);
    assert.equal((await service.execute('report')).data.rentalRevenue,2700);
    const stored=JSON.parse(await readFile(path.join(dir,'store.json'),'utf8'));
    assert.equal(stored.audit.length,2);assert.equal(Object.keys(stored.idempotency).length,2);
  } finally {await rm(dir,{recursive:true,force:true});}
});

test('CLI and HTTP expose the same maintenance state',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-followup-'));
  const child=spawn(process.execPath,['server.mjs','--data-dir',dir,'--catalog',fixture,'--port','0']);
  try {
    const port=await new Promise((resolve,reject)=>{
      let output='';child.stdout.on('data',part=>{output+=part;const end=output.indexOf('\n');if(end>=0) resolve(JSON.parse(output.slice(0,end)).port);});
      child.on('error',reject);child.on('exit',code=>reject(new Error('Server exited '+code)));
    });
    const base=`http://127.0.0.1:${port}`;
    const cmd={type:'maintenance.add',id:'web',itemId:'camera',start:'2026-11-10',end:'2026-11-11',quantity:1,idempotencyKey:'web',expectedRevision:0};
    const sent=await fetch(base+'/api/command',{method:'POST',body:JSON.stringify(cmd)});
    assert.equal(sent.status,200);
    const http=(await (await fetch(base+'/api/maintenance')).json()).data;
    const cli=await new Promise((resolve,reject)=>{
      const proc=spawn(process.execPath,['cli.mjs','--data-dir',dir,'--catalog',fixture,'maintenance']);
      let output='';proc.stdout.on('data',part=>output+=part);proc.on('error',reject);proc.on('close',code=>code===0?resolve(JSON.parse(output)):reject(new Error(`CLI exit ${code}`)));proc.stdin.end();
    });
    assert.deepEqual(cli.data,http);
  } finally {child.kill();await rm(dir,{recursive:true,force:true});}
});
