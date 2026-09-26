import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createService} from '../src/service.mjs';
const root=path.resolve(import.meta.dirname??path.dirname(new URL(import.meta.url).pathname),'..');
const fixture=path.join(root,'fixtures/catalog.json');
const request={type:'reserve',id:'x',idempotencyKey:'k',expectedRevision:0,memberId:'club',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:1}]};
function runCli(dataDir,operation,payload={}) {return new Promise((resolve,reject)=>{
  const child=spawn(process.execPath,[path.join(root,'cli.mjs'),'--data-dir',dataDir,'--catalog',fixture,operation]);
  let stdout='',stderr='';child.stdout.on('data',b=>stdout+=b);child.stderr.on('data',b=>stderr+=b);child.on('error',reject);
  child.on('close',code=>resolve({code,result:JSON.parse(stdout),stderr,lines:stdout.trim().split('\n').length}));child.stdin.end(JSON.stringify(payload));
});}
test('CLI and service share durable behavior; invalid store is preserved',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-'));
  try {
    const cli=await runCli(dir,'command',request);assert.equal(cli.code,0);assert.equal(cli.lines,1);assert.equal(cli.result.revision,1);
    const service=createService({dataDir:dir,catalogPath:fixture,now:()=> 'fixed'});
    assert.equal((await service.execute('report')).data.auditCount,1);
    const replay=await runCli(dir,'command',request);assert.equal(replay.result.revision,1);
    const failed=await runCli(dir,'command',{type:'return',id:'x',idempotencyKey:'bad',expectedRevision:1});assert.notEqual(failed.code,0);
    assert.equal((await service.execute('report')).revision,1);
    const storePath=path.join(dir,'store.json');await writeFile(storePath,'{"schemaVersion":999}');
    assert.equal((await service.execute('command',{...request,id:'y',idempotencyKey:'new',expectedRevision:1})).ok,false);
    assert.equal(await readFile(storePath,'utf8'),'{"schemaVersion":999}');
  } finally {await rm(dir,{recursive:true,force:true});}
});
test('competing CLI processes serialize expected revision',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-'));
  try {
    const [a,b]=await Promise.all([runCli(dir,'command',{...request,id:'a',idempotencyKey:'a'}),runCli(dir,'command',{...request,id:'b',idempotencyKey:'b'})]);
    assert.deepEqual([a.result.ok,b.result.ok].sort(),[false,true]);
    assert.equal((await createService({dataDir:dir,catalogPath:fixture}).execute('report')).data.auditCount,1);
  } finally {await rm(dir,{recursive:true,force:true});}
});
test('service observes catalog edits while historical quotes stay frozen',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-'));
  const catalogPath=path.join(dir,'catalog.json');
  try {
    const original=JSON.parse(await readFile(fixture,'utf8'));
    await writeFile(catalogPath,JSON.stringify(original));
    const service=createService({dataDir:dir,catalogPath});
    const booked=await service.execute('command',request);
    assert.equal(booked.data.quote.rentalTotal,4500);
    original.items[0].rate=2000;await writeFile(catalogPath,JSON.stringify(original));
    const current=await service.execute('quote',{...request,expectedRevision:undefined});
    assert.equal(current.data.rentalTotal,7700);
    assert.equal((await service.execute('reservations')).data[0].quote.rentalTotal,4500);
  } finally {await rm(dir,{recursive:true,force:true});}
});
test('HTTP routes return wire envelopes and serve only web files',async()=>{
  const dir=await mkdtemp(path.join(tmpdir(),'geardesk-'));
  const child=spawn(process.execPath,[path.join(root,'server.mjs'),'--data-dir',dir,'--catalog',fixture,'--port','0']);
  try {
    const port=await new Promise((resolve,reject)=>{
      let buffer='';child.stdout.on('data',chunk=>{buffer+=chunk;const end=buffer.indexOf('\n');if(end>=0) resolve(JSON.parse(buffer.slice(0,end)).port);});
      child.on('error',reject);child.on('exit',code=>reject(new Error('Server exited '+code)));
    });
    const base='http://127.0.0.1:'+port;
    const get=await fetch(base+'/api/catalog');assert.equal(get.status,200);assert.equal((await get.json()).data.items.length,3);
    const reserved=await fetch(base+'/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)});
    assert.equal(reserved.status,200);assert.equal((await reserved.json()).revision,1);
    const conflict=await fetch(base+'/api/command',{method:'POST',body:JSON.stringify({...request,id:'y',idempotencyKey:'y'})});
    assert.equal(conflict.status,409);assert.equal((await conflict.json()).error.code,'REVISION_CONFLICT');
    assert.match(await (await fetch(base+'/')).text(),/GearDesk/);
    const hidden=await fetch(base+'/%2e%2e/package.json');assert.notEqual(hidden.status,200);
  } finally {child.kill();await rm(dir,{recursive:true,force:true});}
});
