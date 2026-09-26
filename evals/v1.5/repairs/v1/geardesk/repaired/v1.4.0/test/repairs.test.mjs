import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import * as d from '../src/domain.mjs';
const catalog=JSON.parse(await readFile(new URL('../fixtures/catalog.json',import.meta.url),'utf8'));
const base={type:'reserve',id:'r',memberId:'regular',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:2},{itemId:'tripod',quantity:1}]};
const call=(store,request)=>d.command(store,catalog,request,'fixed');
const bat=(store,request)=>d.batch(store,catalog,request,'fixed');
const result=out=>out.data;
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

function oldMixed(evidenced=false,status='checked_out') {
  const fixture=structuredClone(legacyFixture),r=fixture.reservations[0];
  r.status=status;r.lines=[{itemId:'camera',quantity:1},{itemId:'tripod',quantity:1}];
  r.quote.lines=r.lines.map((l,i)=>({...l,...(evidenced?{deposit:i===0?5000:1000}:{})}));
  r.quote.deposit=6000;r.quote.totalDue=r.quote.rentalTotal+6000;
  return fixture;
}
const legacyFixture=JSON.parse(await readFile(new URL('../fixtures/legacy-v1-store.json',import.meta.url),'utf8'));
test('ambiguous old mixed deposits reject partial return and preserve aggregate full return',()=>{
  const legacy=oldMixed(),before=structuredClone(legacy);
  const loaded=d.validateStore(legacy);assert.equal(loaded.reservations[0].depositPlan,null);
  assert.equal(d.report(loaded).depositHeld,6000);
  assert.throws(()=>step(legacy,{type:'return.partial',id:'legacy-active',returnedOn:base.end,lines:[{itemId:'camera',quantity:1}]},'unknown'),/allocation is unknown/);
  assert.deepEqual(legacy,before);
  const full=step(legacy,{type:'return',id:'legacy-active'},'full-legacy');
  assert.equal(result(full).refund,6000);assert.equal(d.report(full.store).depositHeld,0);
  assert.equal(full.store.reservations.find(r=>r.id==='legacy-returned').refunded,1000);
  assert.equal(full.store.reservations.find(r=>r.id==='legacy-cancelled').status,'cancelled');
  assert.equal(d.validateStore(full.store).reservations[0].depositPlan,null);
  const replay=call(full.store,{type:'return',id:'legacy-active',expectedRevision:7,idempotencyKey:'full-legacy'});
  assert.equal(result(replay).refund,6000);assert.equal(replay.store.revision,8);
  for(const status of ['returned','cancelled']) {
    const state=d.validateStore(oldMixed(false,status));
    assert.equal(state.reservations[0].depositPlan,null);
    assert.equal(state.reservations[0].refunded,status==='returned'?6000:0);
    assert.throws(()=>step(state,{type:'return',id:'legacy-active'}),{code:'INVALID_TRANSITION'});
  }
});
test('retained historical line evidence controls refunds through migration, catalog edits and replay',()=>{
  const historical=oldMixed(true),changed=structuredClone(catalog);changed.items.forEach(i=>i.deposit=999);
  const req={type:'return.partial',id:'legacy-active',returnedOn:base.end,lines:[{itemId:'camera',quantity:1}],expectedRevision:7,idempotencyKey:'evidenced'};
  const first=d.command(historical,changed,req,'fixed');
  assert.equal(first.data.refund,5000);assert.equal(d.report(first.store).depositHeld,1000);
  assert.equal(first.store.reservations[0].quote.lines[0].deposit,5000);
  assert.equal(d.command(first.store,changed,req,'later').data.refund,5000);
  const last=d.command(first.store,changed,{type:'return',id:'legacy-active',expectedRevision:8,idempotencyKey:'rest'},'fixed');
  assert.equal(last.data.refund,1000);assert.equal(last.data.refunded,6000);assert.equal(last.data.lateFees,0);
  assert.equal(d.validateStore(last.store).reservations[0].status,'returned');
  const invalid=oldMixed(true);invalid.reservations[0].quote.lines[0].deposit=4000;
  assert.throws(()=>d.validateStore(invalid),/historical line deposits/);
  const newBooking=step(d.emptyStore(),base);assert.deepEqual(newBooking.data.quote.lines.map(l=>l.deposit),[10000,1000]);
});

test('single-item derivation is exact and retained line amounts remain internally consistent',()=>{
  const single=structuredClone(legacyFixture);single.reservations[0].lines[0].quantity=2;single.reservations[0].quote.lines[0].quantity=2;
  const first=step(single,{type:'return.partial',id:'legacy-active',returnedOn:base.end,lines:[{itemId:'camera',quantity:1}]},'single');
  assert.equal(first.data.refund,2500);assert.equal(d.report(first.store).depositHeld,2500);
  const uneven=structuredClone(single);uneven.reservations[0].quote.deposit=5001;uneven.reservations[0].quote.totalDue=9801;
  assert.equal(d.validateStore(uneven).reservations[0].depositPlan,null);
  assert.throws(()=>step(uneven,{type:'return.partial',id:'legacy-active',returnedOn:base.end,lines:[{itemId:'camera',quantity:1}]}),/allocation is unknown/);
  const newBooking=step(d.emptyStore(),base).store;newBooking.reservations[0].quote.lines[0].deposit=9000;
  assert.throws(()=>d.validateStore(newBooking),/Line deposit differs/);
});
