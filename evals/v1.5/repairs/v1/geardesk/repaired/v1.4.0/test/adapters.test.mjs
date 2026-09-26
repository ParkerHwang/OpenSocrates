import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {spawn} from 'node:child_process';

const root=resolve('.'),fixture=join(root,'fixtures/catalog.json');
const request={type:'reserve',id:'x',memberId:'club',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:1}],idempotencyKey:'one',expectedRevision:0};
async function cli(dir,operation,input={}) {
  return new Promise((resolve,reject)=>{
    const p=spawn(process.execPath,[join(root,'cli.mjs'),'--data-dir',dir,'--catalog',fixture,operation]); let out='';
    p.stdout.on('data',chunk=>out+=chunk); p.once('error',reject); p.once('close',code=>resolve({code,result:JSON.parse(out)}));
    p.stdin.end(JSON.stringify(input));
  });
}
function start(dir,catalog) {
  return new Promise((resolve,reject)=>{
    const p=spawn(process.execPath,[join(root,'server.mjs'),'--data-dir',dir,'--catalog',catalog,'--port','0']);
    let out=''; p.stdout.on('data',chunk=>{out+=chunk; if(out.includes('\n')) resolve({process:p,port:JSON.parse(out.split('\n')[0]).port});});
    p.once('error',reject); p.once('exit',code=>reject(new Error(`Server exited ${code}`)));
  });
}
test('CLI persists, replays, reports, and protects invalid store',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-cli-'));
  const first=await cli(dir,'command',request); assert.equal(first.code,0); assert.equal(first.result.revision,1);
  const replay=await cli(dir,'command',{...request,expectedRevision:0}); assert.equal(replay.result.revision,1);
  const report=await cli(dir,'report'); assert.equal(report.result.data.auditCount,1);
  const conflict=await cli(dir,'command',{...request,idempotencyKey:'two'}); assert.notEqual(conflict.code,0); assert.equal(conflict.result.error.code,'REVISION_CONFLICT');
  const file=join(dir,'store.json'); await writeFile(file,'{"schemaVersion":99}');
  const bad=await cli(dir,'command',{...request,idempotencyKey:'three'}); assert.equal(bad.result.error.code,'VALIDATION'); assert.equal(await readFile(file,'utf8'),'{"schemaVersion":99}');
});
test('HTTP and CLI share revisions and reload catalog',async(t)=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-http-')),catalog=join(dir,'catalog.json');
  const original=JSON.parse(await readFile(fixture,'utf8')); await writeFile(catalog,JSON.stringify(original));
  const server=await start(dir,catalog); t.after(()=>server.process.kill());
  const url=`http://127.0.0.1:${server.port}`;
  const post=async(route,body)=>{const response=await fetch(url+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});return {status:response.status,body:await response.json()};};
  assert.equal((await (await fetch(url+'/api/health')).json()).ok,true);
  const quoted=await post('/api/quote',request); assert.equal(quoted.body.data.totalDue,9500);
  const saved=await post('/api/command',request); assert.equal(saved.body.revision,1);
  assert.equal((await cli(dir,'reservations')).result.data[0].quote.totalDue,9500);
  original.items[0].rate=2000; await writeFile(catalog,JSON.stringify(original));
  assert.equal((await post('/api/quote',request)).body.data.totalDue,12700);
  const reservations=await (await fetch(url+'/api/reservations')).json(); assert.equal(reservations.data[0].quote.totalDue,9500);
  const failure=await post('/api/command',{...request,id:'y',idempotencyKey:'two'}); assert.equal(failure.status,409); assert.equal(failure.body.error.code,'REVISION_CONFLICT');
  assert.equal((await fetch(url+'/../package.json')).status,404);
});
test('HTTP and CLI expose the same maintenance records and capacity',async(t)=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-maintenance-'));
  const server=await start(dir,fixture); t.after(()=>server.process.kill());
  const url=`http://127.0.0.1:${server.port}`;
  const add={type:'maintenance.add',id:'service',itemId:'camera',start:'2026-11-07',end:'2026-11-09',quantity:2,idempotencyKey:'maint-1',expectedRevision:0};
  const result=await fetch(url+'/api/command',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(add)}).then(r=>r.json());
  assert.equal(result.revision,1);
  assert.deepEqual((await cli(dir,'maintenance')).result.data,[result.data]);
  assert.deepEqual((await fetch(url+'/api/maintenance').then(r=>r.json())).data,[result.data]);
  assert.equal((await cli(dir,'report')).result.data.maintenanceCount,1);
  const quote=await cli(dir,'quote',{...request,lines:[{itemId:'camera',quantity:2}]});
  assert.equal(quote.result.error.code,'CAPACITY');
  const remove=await cli(dir,'command',{type:'maintenance.remove',id:'service',idempotencyKey:'maint-2',expectedRevision:1});
  assert.equal(remove.result.revision,2);
  assert.deepEqual((await fetch(url+'/api/maintenance').then(r=>r.json())).data,[]);
  const page=await fetch(url+'/').then(r=>r.text());
  const client=await fetch(url+'/console.mjs').then(r=>r.text());
  assert.match(page,/data-read="maintenance"/);
  assert.match(page,/id="maintenance-example"/);
  assert.match(client,/maintenance\.add/);
});
test('CLI migrates an old store on mutation without dropping historical records',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-legacy-'));
  assert.equal((await cli(dir,'command',request)).result.revision,1);
  const file=join(dir,'store.json'),legacy=JSON.parse(await readFile(file,'utf8'));
  delete legacy.maintenance; await writeFile(file,JSON.stringify(legacy));
  assert.deepEqual((await cli(dir,'maintenance')).result.data,[]);
  const added=await cli(dir,'command',{type:'maintenance.add',id:'m',itemId:'camera',start:'2026-11-09',end:'2026-11-10',quantity:1,idempotencyKey:'two',expectedRevision:1});
  assert.equal(added.result.revision,2);
  const saved=JSON.parse(await readFile(file,'utf8'));
  assert.equal(saved.reservations[0].id,'x');
  assert.deepEqual(saved.maintenance,[added.result.data]);
  assert.equal(saved.audit.length,2);
  assert.equal(Object.keys(saved.idempotency).length,2);
});
test('concurrent CLI writers serialize expected revisions',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-race-'));
  const [a,b]=await Promise.all([cli(dir,'command',request),cli(dir,'command',{...request,id:'y',idempotencyKey:'two'})]);
  assert.deepEqual([a.result.ok,b.result.ok].sort(),[false,true]);
  assert.equal((await cli(dir,'report')).result.revision,1);
});
test('HTTP and CLI writers contend on the same revision',async(t)=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-mixed-'));
  const server=await start(dir,fixture); t.after(()=>server.process.kill());
  const http=fetch(`http://127.0.0.1:${server.port}/api/command`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)}).then(r=>r.json());
  const other=cli(dir,'command',{...request,id:'y',idempotencyKey:'two'});
  const [a,b]=await Promise.all([http,other]);
  assert.deepEqual([a.ok,b.result.ok].sort(),[false,true]);
  assert.equal((await cli(dir,'report')).result.data.auditCount,1);
});

test('legacy fixture migrates only on successful write and keeps historical totals',async()=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-v1-')),file=join(dir,'store.json');
  const bytes=await readFile(join(root,'fixtures/legacy-v1-store.json'),'utf8'); await writeFile(file,bytes);
  const before=await cli(dir,'report');
  assert.deepEqual([before.result.data.depositHeld,before.result.data.refunded,before.result.data.lateFees],[5000,1000,0]);
  const failed=await cli(dir,'command',{type:'return.partial',id:'legacy-active',returnedOn:'2026-11-10',lines:[{itemId:'camera',quantity:2}],expectedRevision:7,idempotencyKey:'bad'});
  assert.equal(failed.result.error.code,'VALIDATION'); assert.equal(await readFile(file,'utf8'),bytes);
  const returned=await cli(dir,'command',{type:'return',id:'legacy-active',returnedOn:'2026-11-12',expectedRevision:7,idempotencyKey:'good'});
  assert.deepEqual([returned.result.data.refund,returned.result.data.lateFee],[5000,0]);
  const saved=JSON.parse(await readFile(file,'utf8'));
  assert.equal(saved.schemaVersion,2); assert.equal(saved.audit.length,8);
  assert.equal(saved.reservations.find(r=>r.id==='legacy-cancelled').status,'cancelled');
  assert.equal(saved.reservations.find(r=>r.id==='legacy-returned').refunded,1000);
  assert.equal(saved.reservations.find(r=>r.id==='legacy-active').quote.lateFeePerUnitDay,0);
  assert.equal(Object.keys(saved.idempotency).length,8);
});

test('HTTP batch is atomic, replays across CLI, and shares revision lock',async(t)=>{
  const dir=await mkdtemp(join(tmpdir(),'gear-batch-')),file=join(dir,'store.json');
  const server=await start(dir,fixture); t.after(()=>server.process.kill());
  const url=`http://127.0.0.1:${server.port}/api/batch`;
  const post=body=>fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}).then(r=>r.json());
  const input={expectedRevision:0,idempotencyKey:'b',commands:[{type:'reserve',id:'x',memberId:'club',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:1}]},{type:'checkout',id:'x'}]};
  const bad=await post({...input,commands:[...input.commands,{type:'cancel',id:'x'}]});
  assert.equal(bad.error.code,'INVALID_TRANSITION');
  await assert.rejects(readFile(file,'utf8'));
  const good=await post(input); assert.equal(good.revision,2); assert.equal(good.data.length,2);
  const bytes=await readFile(file,'utf8');
  const replay=await cli(dir,'batch',input); assert.deepEqual(replay.result,good); assert.equal(await readFile(file,'utf8'),bytes);
  const conflict=await cli(dir,'batch',{...input,idempotencyKey:'new'}); assert.equal(conflict.result.error.code,'REVISION_CONFLICT');
  assert.equal(await readFile(file,'utf8'),bytes);
});
