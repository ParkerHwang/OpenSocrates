import test from 'node:test';
import assert from 'node:assert/strict';
import {emptyStore,validateCatalog,validateStore,quote,availability,command,report,BusinessError} from '../src/domain.mjs';

const catalog=validateCatalog({items:[{id:'a',name:'A',stock:2,rate:101,deposit:50},{id:'free',name:'Free',stock:1,rate:0,deposit:75}],members:[{id:'m',name:'M',discountBps:5000}]});
const base={memberId:'m',start:'2026-11-01',end:'2026-11-03',lines:[{itemId:'a',quantity:1}]};
const run=(store,type,id,key,more={})=>command(store,catalog,{type,id,idempotencyKey:key,expectedRevision:store.revision,...more},'fixed').store;
const code=(fn,want)=>assert.throws(fn,e=>e instanceof BusinessError&&e.code===want);

test('quote uses aggregate rounding, deposits, and strict inputs',()=>{
  const q=quote(emptyStore(),catalog,base);
  assert.deepEqual([q.rentalSubtotal,q.discount,q.rentalTotal,q.deposit,q.totalDue],[202,101,101,50,151]);
  assert.equal(quote(emptyStore(),catalog,{...base,lines:[{itemId:'free',quantity:1}]}).totalDue,75);
  for(const lines of [[],[{itemId:'a',quantity:1.5}],[{itemId:'a',quantity:true}],[{itemId:'a',quantity:1},{itemId:'a',quantity:1}]]) code(()=>quote(emptyStore(),catalog,{...base,lines}),'VALIDATION');
  code(()=>quote(emptyStore(),catalog,{...base,start:'2026-02-30'}),'VALIDATION');
  code(()=>quote(emptyStore(),catalog,{...base,memberId:'missing'}),'NOT_FOUND');
});

test('capacity counts simultaneous days and state changes release it',()=>{
  let s=run(emptyStore(),'reserve','r1','k1',base);
  s=run(s,'reserve','r2','k2',{...base,start:'2026-11-03',end:'2026-11-04'});
  assert.equal(availability(s,catalog,{start:'2026-11-01',end:'2026-11-04'})[0].available,1);
  s=run(s,'reserve','r3','k3',base);
  code(()=>quote(s,catalog,base),'CAPACITY');
  s=run(s,'cancel','r3','k4');
  assert.equal(availability(s,catalog,base)[0].available,1);
  s=run(s,'checkout','r1','k5');
  assert.equal(availability(s,catalog,base)[0].available,1);
  const returned=command(s,catalog,{type:'return',id:'r1',idempotencyKey:'k6',expectedRevision:s.revision},'fixed');
  assert.equal(returned.data.refund,50);
  assert.equal(availability(returned.store,catalog,base)[0].available,2);
  assert.deepEqual(report(returned.store),{reservationCount:3,counts:{reserved:1,checked_out:0,returned:1,cancelled:1},rentalRevenue:151,depositHeld:50,refunded:50,auditCount:6,maintenanceCount:0});
});

test('replay precedes revision check and failed commands leave store untouched',()=>{
  const first={type:'reserve',id:'r',idempotencyKey:'key',expectedRevision:0,...base};
  const result=command(emptyStore(),catalog,first,'fixed');
  const replay=command(result.store,catalog,{...first,lines:[{quantity:1,itemId:'a'}]},'later');
  assert.equal(replay.replay,true); assert.equal(replay.store,result.store);
  code(()=>command(result.store,catalog,{...first,id:'different'},'fixed'),'IDEMPOTENCY_CONFLICT');
  code(()=>command(result.store,catalog,{...first,idempotencyKey:'new'},'fixed'),'REVISION_CONFLICT');
  code(()=>command(result.store,catalog,{type:'return',id:'r',idempotencyKey:'bad',expectedRevision:1},'fixed'),'INVALID_TRANSITION');
  assert.equal(result.store.audit.length,1);
});

test('unsafe arithmetic fails before mutation',()=>{
  const huge=validateCatalog({items:[{id:'h',name:'H',stock:2,rate:Number.MAX_SAFE_INTEGER,deposit:0}],members:[{id:'m',name:'M',discountBps:0}]});
  code(()=>quote(emptyStore(),huge,{...base,lines:[{itemId:'h',quantity:2}]}),'VALIDATION');
});
test('special object property names remain valid idempotency keys',()=>{
  const result=command(emptyStore(),catalog,{type:'reserve',id:'r',idempotencyKey:'__proto__',expectedRevision:0,...base},'fixed');
  assert.equal(Object.keys(result.store.idempotency).length,1);
  assert.equal(command(result.store,catalog,{type:'reserve',id:'r',idempotencyKey:'__proto__',expectedRevision:0,...base},'fixed').replay,true);
});

test('weekend rate rounds per unit per day, then aggregate discount is capped',()=>{
  const priced=validateCatalog({items:[{id:'a',name:'A',stock:4,rate:101,deposit:50}],members:[{id:'m',name:'M',discountBps:5000}],pricing:{weekendBps:15000,discountCap:300}});
  const request={memberId:'m',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'a',quantity:2}]};
  const q=quote(emptyStore(),priced,request);
  assert.deepEqual([q.rentalSubtotal,q.discount,q.rentalTotal,q.deposit,q.totalDue],[810,300,510,100,610]);
  const saved=command(emptyStore(),priced,{type:'reserve',id:'r',...request,idempotencyKey:'k',expectedRevision:0},'fixed').store;
  priced.items[0].rate=200;
  assert.equal(quote(saved,priced,request).rentalSubtotal,1600);
  assert.equal(saved.reservations[0].quote.totalDue,610);
  assert.equal(report(saved).rentalRevenue,510);
});

test('maintenance shares daily capacity, supports adjacent intervals and replay',()=>{
  let s=run(emptyStore(),'reserve','r','k1',{...base,start:'2026-11-06',end:'2026-11-08'});
  s=run(s,'maintenance.add','m1','k2',{itemId:'a',start:'2026-11-07',end:'2026-11-09',quantity:1});
  code(()=>command(s,catalog,{type:'maintenance.add',id:'m2',itemId:'a',start:'2026-11-07',end:'2026-11-08',quantity:1,idempotencyKey:'k3',expectedRevision:s.revision},'fixed'),'CAPACITY');
  s=run(s,'maintenance.add','m2','k3',{itemId:'a',start:'2026-11-08',end:'2026-11-09',quantity:1});
  assert.equal(availability(s,catalog,{start:'2026-11-07',end:'2026-11-09'})[0].available,0);
  code(()=>quote(s,catalog,{...base,start:'2026-11-08',end:'2026-11-09'}),'CAPACITY');
  const removal={type:'maintenance.remove',id:'m2',idempotencyKey:'k4',expectedRevision:s.revision};
  const removed=command(s,catalog,removal,'fixed');
  assert.equal(command(removed.store,catalog,removal,'later').replay,true);
  assert.equal(availability(removed.store,catalog,{start:'2026-11-08',end:'2026-11-09'})[0].available,1);
  assert.equal(report(removed.store).maintenanceCount,1);
  code(()=>command(removed.store,catalog,{type:'maintenance.remove',id:'m2',idempotencyKey:'k5',expectedRevision:removed.store.revision},'fixed'),'NOT_FOUND');
});

test('old stores gain empty maintenance without losing history',()=>{
  const existing=run(emptyStore(),'reserve','r','key',base);
  delete existing.maintenance;
  const loaded=validateStore(structuredClone(existing));
  assert.deepEqual(loaded.maintenance,[]);
  const next=run(loaded,'maintenance.add','m','new',{itemId:'a',start:'2026-11-03',end:'2026-11-04',quantity:1});
  assert.equal(next.reservations[0].id,'r');
  assert.equal(next.audit.length,2);
  assert.equal(Object.keys(next.idempotency).length,2);
});
