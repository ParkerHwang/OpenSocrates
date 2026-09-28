import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as d from '../src/domain.mjs';
const catalog=JSON.parse(await readFile(new URL('../fixtures/catalog.json',import.meta.url),'utf8'));
const base={type:'reserve',id:'r',memberId:'regular',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:2},{itemId:'tripod',quantity:1}]};
const call=(store,request)=>d.command(catalog,store,request,{timestamp:'fixed'});
const bat=(store,request)=>d.batch(catalog,store,request,{timestamp:'fixed'});
const result=out=>out.result;
const step=(store,request,key=request.type)=>call(store,{...request,expectedRevision:store.revision,idempotencyKey:key});
function checked() {return step(step(d.emptyStore(),base).store,{type:'checkout',id:'r'}).store;}
test('partial date boundaries reject immutably; full return alone defaults to scheduled end',()=>{
  const store=checked(),before=structuredClone(store);
  for(const date of [undefined,null,'',false,0,'2026-02-30','2026-11-05']) {
    assert.throws(()=>step(store,{type:'return.partial',id:'r',returnedOn:date,lines:[{itemId:'camera',quantity:1}]}),{code:'VALIDATION'});
    assert.deepEqual(store,before);
  }
  const first=step(store,{type:'return.partial',id:'r',returnedOn:'2026-11-10',lines:[{itemId:'camera',quantity:1}]},'partial');
  assert.deepEqual([result(first).refund,result(first).lateFee],[4900,100]);
  assert.equal(first.store.revision,3);
  const second=step(first.store,{type:'return',id:'r'},'full');
  assert.deepEqual([result(second).refund,result(second).lateFee],[6000,0]);
  assert.equal(result(second).refunded,10900);
  assert.equal(result(second).status,'returned');
  assert.equal(d.report(second.store).depositHeld,0);
  const replay=call(second.store,{type:'return.partial',id:'r',returnedOn:'2026-11-10',lines:[{itemId:'camera',quantity:1}],expectedRevision:2,idempotencyKey:'partial'});
  assert.equal(replay.replay,true);assert.deepEqual(result(replay),result(first));assert.equal(replay.store.revision,4);
  assert.throws(()=>step(second.store,{type:'return',id:'r'},'again'),{code:'INVALID_TRANSITION'});
});
test('new, replay and per-command batch results own nested mutable values',()=>{
  const store=d.emptyStore(),snapshot=structuredClone(store);
  const request={...base,expectedRevision:0,idempotencyKey:'book'};
  const fresh=call(store,request);result(fresh).lines[0].quantity=999;
  assert.equal(fresh.store.reservations[0].lines[0].quantity,2);assert.deepEqual(store,snapshot);
  const replay=call(fresh.store,request);result(replay).quote.lines[0].quantity=999;
  assert.equal(result(call(fresh.store,request)).quote.lines[0].quantity,2);
  const maintenance=step(d.emptyStore(),{type:'maintenance.add',id:'m',itemId:'camera',quantity:1,start:base.start,end:base.end});
  result(maintenance).quantity=999;assert.equal(maintenance.store.maintenance[0].quantity,1);
  const batchRequest={expectedRevision:0,idempotencyKey:'b',commands:[base,{type:'checkout',id:'r'},{type:'return.partial',id:'r',returnedOn:base.end,lines:[{itemId:'camera',quantity:1}]}]};
  const batch=bat(store,batchRequest),values=result(batch);
  assert.deepEqual(values.map(v=>v.status),['reserved','checked_out','checked_out']);
  assert.equal(values[0].refunded,0);assert.equal(values[1].refunded,0);assert.equal(values[2].refunded,5000);
  values[0].lines[0].quantity=999;values[2].quote.deposit=0;
  assert.equal(batch.store.reservations[0].quote.deposit,11000);
  const replayBatch=bat(batch.store,batchRequest);assert.equal(result(replayBatch)[0].lines[0].quantity,2);
  result(replayBatch)[0].lines[0].quantity=888;
  assert.equal(result(bat(batch.store,batchRequest))[0].lines[0].quantity,2);
  assert.deepEqual(batch.store.audit.map(a=>a.revision),[1,2,3]);
});
test('invalid batch beginning, middle and end discard every owned draft mutation',()=>{
  const store=d.emptyStore(),before=structuredClone(store);
  const commands=[{type:'maintenance.add',id:'a',itemId:'camera',quantity:1,start:base.start,end:base.end},{type:'maintenance.remove',id:'a'}];
  for(const index of [0,1,2]) {
    const inner=[...commands];inner.splice(index,0,{type:'maintenance.remove',id:'missing'});
    assert.throws(()=>bat(store,{expectedRevision:0,idempotencyKey:'failed',commands:inner}),{code:'NOT_FOUND'});
    assert.deepEqual(store,before);
  }
  assert.throws(()=>bat(store,{expectedRevision:0,idempotencyKey:'date',commands:[base,{type:'checkout',id:'r'},{type:'return.partial',id:'r',lines:[{itemId:'camera',quantity:1}]}]}),{code:'VALIDATION'});
  assert.deepEqual(store,before);
});
