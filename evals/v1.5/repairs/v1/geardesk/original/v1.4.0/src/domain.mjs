import {daysInRange,dayNumber,isWeekend,daysLate} from './shared/dates.mjs';
import {integer,addMoney,multiplyMoney,roundRatio} from './shared/money.mjs';

export class BusinessError extends Error {
  constructor(code,message) { super(message); this.code=code; }
}
const fail=(code,message)=>{throw new BusinessError(code,message);};
const object=x=>x!==null && typeof x==='object' && !Array.isArray(x);
const id=(x,label='id')=>{if(typeof x!=='string'||!x.trim()) fail('VALIDATION',`Invalid ${label}`); return x;};
const bounded=(x,min=0)=>{try{return integer(x,{min});}catch{fail('VALIDATION','Expected safe integer');}};
const sum=(...xs)=>{try{return addMoney(...xs);}catch{fail('VALIDATION','Unsafe aggregate amount');}};
const product=(a,b)=>{try{return multiplyMoney(a,b);}catch{fail('VALIDATION','Unsafe aggregate amount');}};
export function range(start,end) { try {return daysInRange(start,end).map(dayNumber);} catch {fail('VALIDATION','Invalid date range');} }
export function validateCatalog(c) {
  if(!object(c)||!Array.isArray(c.items)||!Array.isArray(c.members)) fail('VALIDATION','Invalid catalog');
  if(c.pricing!==undefined) {
    if(!object(c.pricing)) fail('VALIDATION','Invalid pricing');
    bounded(c.pricing.weekendBps);
    if(c.pricing.discountCap!==undefined) bounded(c.pricing.discountCap);
    if(c.pricing.lateFeePerUnitDay!==undefined) bounded(c.pricing.lateFeePerUnitDay);
  }
  const items=new Set(),members=new Set();
  for(const x of c.items) {if(!object(x)) fail('VALIDATION','Invalid item'); id(x.id); if(items.has(x.id)) fail('VALIDATION','Duplicate item'); items.add(x.id); if(typeof x.name!=='string') fail('VALIDATION','Invalid item name'); bounded(x.stock,1); bounded(x.rate); bounded(x.deposit);}
  for(const x of c.members) {if(!object(x)) fail('VALIDATION','Invalid member'); id(x.id); if(members.has(x.id)) fail('VALIDATION','Duplicate member'); members.add(x.id); if(typeof x.name!=='string') fail('VALIDATION','Invalid member name'); bounded(x.discountBps); if(x.discountBps>10000) fail('VALIDATION','Invalid discount');}
  return c;
}
export function emptyStore() {return {schemaVersion:2,revision:0,reservations:[],maintenance:[],audit:[],idempotency:{},batchIdempotency:{}};}
export function validateStore(input) {
  if(!object(input)||![1,2].includes(input.schemaVersion)) fail('VALIDATION','Invalid store');
  const s=structuredClone(input),legacy=s.schemaVersion===1;
  if(!Number.isSafeInteger(s.revision)||s.revision<0||!Array.isArray(s.reservations)||!Array.isArray(s.audit)||!object(s.idempotency)||s.audit.length!==s.revision||Object.keys(s.idempotency).length>s.revision||(legacy&&Object.keys(s.idempotency).length!==s.revision)) fail('VALIDATION','Invalid store history');
  if(s.maintenance===undefined) s.maintenance=[];
  if(!Array.isArray(s.maintenance)) fail('VALIDATION','Invalid maintenance');
  if(s.batchIdempotency===undefined) s.batchIdempotency={};
  if(!object(s.batchIdempotency)) fail('VALIDATION','Invalid batch history');
  const maintenanceIds=new Set();
  for(const m of s.maintenance) {
    if(!object(m)) fail('VALIDATION','Invalid maintenance');
    id(m.id); id(m.itemId,'itemId'); bounded(m.quantity,1); range(m.start,m.end);
    if(maintenanceIds.has(m.id)) fail('VALIDATION','Duplicate maintenance ID');
    maintenanceIds.add(m.id);
  }
  const seen=new Set();
  for(const r of s.reservations) {
    if(!object(r)||typeof r.id!=='string'||!r.id||seen.has(r.id)||!['reserved','checked_out','returned','cancelled'].includes(r.status)||!object(r.quote)||!Array.isArray(r.lines)||!r.lines.length) fail('VALIDATION','Invalid store reservation');
    seen.add(r.id); id(r.memberId,'memberId'); range(r.start,r.end);
    const lineIds=new Set();
    for(const line of r.lines) {if(!object(line)) fail('VALIDATION','Invalid store line'); id(line.itemId,'itemId'); bounded(line.quantity,1); if(lineIds.has(line.itemId)) fail('VALIDATION','Invalid store line'); lineIds.add(line.itemId);}
    const q=r.quote;
    if(q.memberId!==r.memberId||q.start!==r.start||q.end!==r.end||!Array.isArray(q.lines)||JSON.stringify(q.lines)!==JSON.stringify(r.lines)) fail('VALIDATION','Invalid store quote');
    for(const field of ['rentalSubtotal','discount','rentalTotal','deposit','totalDue']) bounded(q[field]);
    if(q.discount>q.rentalSubtotal||q.rentalTotal!==q.rentalSubtotal-q.discount||sum(q.rentalTotal,q.deposit)!==q.totalDue) fail('VALIDATION','Invalid store quote');
    if(legacy) {
      // V1 saved only an aggregate deposit. Split it deterministically across units.
      // This preserves the historical total without consulting the current catalog.
      const units=r.lines.reduce((n,l)=>sum(n,l.quantity),0),base=Math.floor(q.deposit/units);
      let remainder=q.deposit%units;
      r.depositPlan=Object.fromEntries(r.lines.map(l=>{const extra=Math.min(l.quantity,remainder); remainder-=extra; return [l.itemId,{base,extra}];}));
      r.returnedUnits=Object.fromEntries(r.lines.map(l=>[l.itemId,0]));
      if(r.status==='returned') {for(const l of r.lines) r.returnedUnits[l.itemId]=l.quantity;}
      r.refunded=r.status==='returned'?q.deposit:0; r.lateFees=0;
      q.lateFeePerUnitDay=0;
    } else {
      bounded(q.lateFeePerUnitDay); bounded(r.refunded); bounded(r.lateFees);
      if(!object(r.depositPlan)||!object(r.returnedUnits)) fail('VALIDATION','Invalid return accounting');
      let held=0,returnedDeposit=0;
      if(Object.keys(r.depositPlan).length!==r.lines.length||Object.keys(r.returnedUnits).length!==r.lines.length) fail('VALIDATION','Invalid return accounting');
      for(const l of r.lines) {
        const plan=r.depositPlan[l.itemId],count=r.returnedUnits[l.itemId];
        if(!object(plan)) fail('VALIDATION','Invalid deposit plan');
        bounded(plan.base); bounded(plan.extra); if(plan.extra>l.quantity) fail('VALIDATION','Invalid deposit plan');
        bounded(count); if(count>l.quantity) fail('VALIDATION','Invalid returned quantity');
        returnedDeposit=sum(returnedDeposit,depositPart(plan,0,count)); held=sum(held,depositPart(plan,count,l.quantity-count));
      }
      if(sum(held,returnedDeposit)!==q.deposit||sum(r.refunded,r.lateFees)!==returnedDeposit) fail('VALIDATION','Invalid return totals');
      const allReturned=r.lines.every(l=>r.returnedUnits[l.itemId]===l.quantity);
      if((r.status==='returned')!==allReturned && (r.status==='returned'||r.status==='checked_out')) fail('VALIDATION','Invalid return status');
      if(['reserved','cancelled'].includes(r.status)&&returnedDeposit!==0) fail('VALIDATION','Invalid return status');
    }
  }
  for(let i=0;i<s.audit.length;i++) {const a=s.audit[i]; if(!object(a)||a.revision!==i+1||!['reserve','cancel','checkout','return','return.partial','maintenance.add','maintenance.remove'].includes(a.type)||typeof a.id!=='string') fail('VALIDATION','Invalid audit');}
  for(const records of [s.idempotency,s.batchIdempotency]) for(const [key,value] of Object.entries(records)) if(!key||!object(value)||typeof value.fingerprint!=='string'||(records===s.idempotency?!object(value.data):!Array.isArray(value.data))) fail('VALIDATION','Invalid idempotency record');
  s.schemaVersion=2;
  return s;
}
export function availability(store,catalog,request) {
  if(!object(request)) fail('VALIDATION','Invalid request');
  const days=range(request.start,request.end);
  return catalog.items.map(item=>{
    let available=item.stock;
    for(const day of days) {
      let used=0;
      for(const r of store.reservations) if((r.status==='reserved'||r.status==='checked_out')&&day>=dayNumber(r.start)&&day<dayNumber(r.end)) {
        for(const line of r.lines) if(line.itemId===item.id) used=sum(used,line.quantity-(r.returnedUnits?.[line.itemId]??0));
      }
      for(const m of store.maintenance??[]) if(m.itemId===item.id&&day>=dayNumber(m.start)&&day<dayNumber(m.end)) used=sum(used,m.quantity);
      available=Math.min(available,Math.max(0,item.stock-used));
    }
    return {itemId:item.id,available};
  });
}
export function quote(store,catalog,request) {
  if(!object(request)) fail('VALIDATION','Invalid request');
  id(request.memberId,'memberId'); const member=catalog.members.find(x=>x.id===request.memberId); if(!member) fail('NOT_FOUND','Unknown member');
  const days=range(request.start,request.end);
  if(!Array.isArray(request.lines)||!request.lines.length) fail('VALIDATION','Expected nonempty lines');
  const seen=new Set(), stock=new Map(availability(store,catalog,request).map(x=>[x.itemId,x.available]));
  let rentalSubtotal=0,deposit=0;
  const lines=request.lines.map(line=>{
    if(!object(line)) fail('VALIDATION','Invalid line'); id(line.itemId,'itemId'); const quantity=bounded(line.quantity,1);
    if(seen.has(line.itemId)) fail('VALIDATION','Duplicate item line'); seen.add(line.itemId);
    const item=catalog.items.find(x=>x.id===line.itemId); if(!item) fail('NOT_FOUND','Unknown item');
    if(quantity>stock.get(item.id)) fail('CAPACITY','Insufficient capacity');
    for(const day of days) {
      let daily=item.rate;
      if(isWeekend(new Date(day*86400000).toISOString().slice(0,10))) {
        try {daily=roundRatio(item.rate,catalog.pricing?.weekendBps??10000,10000);} catch {fail('VALIDATION','Unsafe weekend rate');}
      }
      rentalSubtotal=sum(rentalSubtotal,product(quantity,daily));
    }
    deposit=sum(deposit,product(quantity,item.deposit));
    return {itemId:item.id,quantity};
  });
  let discount; try {discount=roundRatio(rentalSubtotal,member.discountBps,10000);} catch {fail('VALIDATION','Unsafe discount');}
  if(catalog.pricing?.discountCap!==undefined) discount=Math.min(discount,catalog.pricing.discountCap);
  const rentalTotal=rentalSubtotal-discount,totalDue=sum(rentalTotal,deposit);
  return {memberId:request.memberId,start:request.start,end:request.end,lines,rentalSubtotal,discount,rentalTotal,deposit,totalDue};
}
export function stable(value) {if(Array.isArray(value)) return value.map(stable); if(object(value)) return Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])])); return value;}
export function fingerprint(command) {const {expectedRevision,...content}=command; return JSON.stringify(stable(content));}
function depositPart(plan,start,count) {return sum(product(plan.base,count),Math.max(0,Math.min(start+count,plan.extra)-start));}
function applyOne(next,catalog,input,timestamp) {
  if(!object(input)||typeof input.type!=='string') fail('VALIDATION','Invalid command');
  let data;
  if(input.type==='reserve') {
    id(input.id); if(next.reservations.some(r=>r.id===input.id)) fail('VALIDATION','Duplicate reservation ID');
    const q=quote(next,catalog,input);
    q.lateFeePerUnitDay=catalog.pricing?.lateFeePerUnitDay??0;
    data={id:input.id,memberId:q.memberId,start:q.start,end:q.end,lines:q.lines,status:'reserved',quote:q,
      depositPlan:Object.fromEntries(q.lines.map(l=>[l.itemId,{base:catalog.items.find(i=>i.id===l.itemId).deposit,extra:0}])),
      returnedUnits:Object.fromEntries(q.lines.map(l=>[l.itemId,0])),refunded:0,lateFees:0};
    next.reservations.push(data);
  } else if(['cancel','checkout','return','return.partial'].includes(input.type)) {
    id(input.id); const r=next.reservations.find(x=>x.id===input.id); if(!r) fail('NOT_FOUND','Unknown reservation');
    const returning=input.type==='return'||input.type==='return.partial';
    if(r.status!==(returning?'checked_out':'reserved')) fail('INVALID_TRANSITION','Unsupported status transition');
    if(returning) {
      if(input.type==='return.partial'&&input.returnedOn===undefined) fail('VALIDATION','Expected returnedOn');
      const returnedOn=input.returnedOn??r.end;
      let lateDays; try {lateDays=daysLate(returnedOn,r.end); if(dayNumber(returnedOn)<dayNumber(r.start)) fail('VALIDATION','Return before start');} catch(e) {if(e instanceof BusinessError) throw e; fail('VALIDATION','Invalid returnedOn');}
      const lines=input.type==='return'?r.lines.map(l=>({itemId:l.itemId,quantity:l.quantity-r.returnedUnits[l.itemId]})).filter(l=>l.quantity):input.lines;
      if(!Array.isArray(lines)||!lines.length) fail('VALIDATION','Expected nonempty return lines');
      let deposit=0,returnedQuantity=0; const seen=new Set();
      for(const line of lines) {
        if(!object(line)) fail('VALIDATION','Invalid return line'); id(line.itemId,'itemId'); const quantity=bounded(line.quantity,1);
        if(seen.has(line.itemId)) fail('VALIDATION','Duplicate item line'); seen.add(line.itemId);
        const booked=r.lines.find(l=>l.itemId===line.itemId);
        if(!booked||quantity>booked.quantity-r.returnedUnits[line.itemId]) fail('VALIDATION','Invalid return quantity');
        const start=r.returnedUnits[line.itemId];
        deposit=sum(deposit,depositPart(r.depositPlan[line.itemId],start,quantity));
        returnedQuantity=sum(returnedQuantity,quantity);
      }
      const rate=r.quote.lateFeePerUnitDay;
      const lateFee=rate===0||lateDays===0?0:(lateDays>Math.floor(deposit/rate/returnedQuantity)?deposit:product(product(returnedQuantity,lateDays),rate));
      const refund=deposit-lateFee;
      for(const line of lines) r.returnedUnits[line.itemId]+=line.quantity;
      r.refunded=sum(r.refunded,refund); r.lateFees=sum(r.lateFees,lateFee);
      if(r.lines.every(l=>r.returnedUnits[l.itemId]===l.quantity)) r.status='returned';
      data={...r,refund,lateFee,returnedQuantity};
    } else {r.status=input.type==='cancel'?'cancelled':'checked_out'; data=r;}
  } else if(input.type==='maintenance.add') {
    id(input.id); id(input.itemId,'itemId'); const quantity=bounded(input.quantity,1);
    if(next.maintenance.some(m=>m.id===input.id)) fail('VALIDATION','Duplicate maintenance ID');
    const item=catalog.items.find(x=>x.id===input.itemId); if(!item) fail('NOT_FOUND','Unknown item');
    range(input.start,input.end);
    if(quantity>availability(next,catalog,input).find(x=>x.itemId===item.id).available) fail('CAPACITY','Insufficient capacity');
    data={id:input.id,itemId:item.id,start:input.start,end:input.end,quantity}; next.maintenance.push(data);
  } else if(input.type==='maintenance.remove') {
    id(input.id); const index=next.maintenance.findIndex(m=>m.id===input.id);
    if(index<0) fail('NOT_FOUND','Unknown maintenance'); data=next.maintenance.splice(index,1)[0];
  } else fail('VALIDATION','Unknown command type');
  next.revision++;
  next.audit.push({revision:next.revision,type:input.type,id:input.id,timestamp});
  return structuredClone(data);
}
export function command(store,catalog,input,timestamp) {
  if(!object(input)) fail('VALIDATION','Invalid command');
  id(input.idempotencyKey,'idempotencyKey'); bounded(input.expectedRevision);
  const fp=fingerprint(input),prior=Object.hasOwn(store.idempotency,input.idempotencyKey)?store.idempotency[input.idempotencyKey]:undefined;
  if(prior) {if(prior.fingerprint!==fp) fail('IDEMPOTENCY_CONFLICT','Key already used for different command'); return {store,data:prior.data,replay:true};}
  if(input.expectedRevision!==store.revision) fail('REVISION_CONFLICT','Expected revision does not match');
  const next=structuredClone(store),data=applyOne(next,catalog,input,timestamp);
  Object.defineProperty(next.idempotency,input.idempotencyKey,{value:{fingerprint:fp,data:structuredClone(data)},writable:true,enumerable:true,configurable:true});
  return {store:next,data,replay:false};
}
export function batch(store,catalog,input,timestamp) {
  if(!object(input)) fail('VALIDATION','Invalid batch');
  id(input.idempotencyKey,'idempotencyKey'); bounded(input.expectedRevision);
  if(!Array.isArray(input.commands)||input.commands.length<1||input.commands.length>20) fail('VALIDATION','Expected 1..20 commands');
  for(const c of input.commands) if(!object(c)||Object.hasOwn(c,'expectedRevision')||Object.hasOwn(c,'idempotencyKey')) fail('VALIDATION','Invalid inner command');
  const fp=fingerprint(input),prior=Object.hasOwn(store.batchIdempotency,input.idempotencyKey)?store.batchIdempotency[input.idempotencyKey]:undefined;
  if(prior) {if(prior.fingerprint!==fp) fail('IDEMPOTENCY_CONFLICT','Key already used for different batch'); return {store,data:prior.data,replay:true};}
  if(input.expectedRevision!==store.revision) fail('REVISION_CONFLICT','Expected revision does not match');
  const next=structuredClone(store),data=input.commands.map(c=>applyOne(next,catalog,c,timestamp));
  Object.defineProperty(next.batchIdempotency,input.idempotencyKey,{value:{fingerprint:fp,data:structuredClone(data)},writable:true,enumerable:true,configurable:true});
  return {store:next,data,replay:false};
}
export function report(store) {
  const counts={reserved:0,checked_out:0,returned:0,cancelled:0};
  let rentalRevenue=0,depositHeld=0,refunded=0,lateFees=0;
  for(const r of store.reservations) {
    counts[r.status]++;
    if(r.status!=='cancelled') rentalRevenue=sum(rentalRevenue,r.quote.rentalTotal);
    if(r.status==='reserved'||r.status==='checked_out') for(const l of r.lines) depositHeld=sum(depositHeld,depositPart(r.depositPlan[l.itemId],r.returnedUnits[l.itemId],l.quantity-r.returnedUnits[l.itemId]));
    refunded=sum(refunded,r.refunded); lateFees=sum(lateFees,r.lateFees);
  }
  return {reservationCount:store.reservations.length,counts,rentalRevenue,depositHeld,refunded,lateFees,auditCount:store.audit.length,maintenanceCount:(store.maintenance??[]).length};
}
