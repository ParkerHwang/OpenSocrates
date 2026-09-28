import {dayNumber,daysInRange,isWeekend,daysLate} from './shared/dates.mjs';
import {integer,addMoney,multiplyMoney,roundRatio} from './shared/money.mjs';

export class DomainError extends Error {
  constructor(code,message) { super(message); this.code=code; }
}
const fail=(code,message)=>{throw new DomainError(code,message);};
const object=value=>value!==null && typeof value==='object' && !Array.isArray(value);
const id=value=>typeof value==='string' && value.trim().length>0;
const int=(value,min=0,max=Number.MAX_SAFE_INTEGER)=>integer(value,{min,max});
function valid(test,message) { if(!test) fail('VALIDATION',message); }
function safe(fn) { try { return fn(); } catch(error) { if(error instanceof DomainError) throw error; if(error instanceof TypeError || error instanceof RangeError) fail('VALIDATION',error.message); throw error; } }
export function validateCatalog(catalog) { return safe(()=>{
  valid(object(catalog) && Array.isArray(catalog.items) && Array.isArray(catalog.members),'Invalid catalog');
  if(catalog.pricing!==undefined) {
    valid(object(catalog.pricing),'Invalid pricing');
    int(catalog.pricing.weekendBps);
    if(catalog.pricing.discountCap!==undefined) int(catalog.pricing.discountCap);
    if(catalog.pricing.lateFeePerUnitDay!==undefined) int(catalog.pricing.lateFeePerUnitDay);
  }
  for(const [kind,records] of [['item',catalog.items],['member',catalog.members]]) {
    const seen=new Set();
    for(const record of records) {
      valid(object(record) && id(record.id) && typeof record.name==='string' && record.name.trim(),'Invalid '+kind);
      valid(!seen.has(record.id),'Duplicate '+kind+' ID'); seen.add(record.id);
      if(kind==='item') { int(record.stock,1); int(record.rate); int(record.deposit); }
      else int(record.discountBps,0,10000);
    }
  }
  return catalog;
}); }
export function emptyStore() { return {schemaVersion:2,revision:0,reservations:[],maintenance:[],audit:[],idempotency:{},batchIdempotency:{}}; }
export function validateStore(store) { return safe(()=>{
  valid(object(store) && [1,2].includes(store.schemaVersion) && Array.isArray(store.reservations) && Array.isArray(store.audit) && object(store.idempotency),'Invalid store');
  if(store.schemaVersion===2) valid(object(store.batchIdempotency),'Invalid batch idempotency');
  valid(store.maintenance===undefined || Array.isArray(store.maintenance),'Invalid maintenance');
  int(store.revision); valid(store.audit.length===store.revision,'Invalid store audit');
  const seen=new Set();
  for(const r of store.reservations) {
    valid(object(r) && id(r.id) && !seen.has(r.id) && id(r.memberId) && Array.isArray(r.lines) && ['reserved','checked_out','returned','cancelled'].includes(r.status),'Invalid reservation');
    seen.add(r.id); daysInRange(r.start,r.end);
    valid(r.lines.length>0,'Invalid reservation lines');
    const lines=new Set(); for(const line of r.lines) {valid(object(line)&&id(line.itemId)&&!lines.has(line.itemId),'Invalid reservation line'); lines.add(line.itemId);int(line.quantity,1);}
    valid(object(r.quote) && r.quote.memberId===r.memberId && r.quote.start===r.start && r.quote.end===r.end && Array.isArray(r.quote.lines) && r.quote.lines.length===r.lines.length,'Invalid reservation quote');
    for(const key of ['rentalSubtotal','discount','rentalTotal','deposit','totalDue']) int(r.quote[key]);
    valid(r.quote.rentalTotal===r.quote.rentalSubtotal-r.quote.discount && r.quote.totalDue===addMoney(r.quote.rentalTotal,r.quote.deposit),'Invalid reservation totals');
    let rentalSum=0,depositSum=0;
    for(let i=0;i<r.lines.length;i++) {
      const line=r.quote.lines[i];valid(object(line) && line.itemId===r.lines[i].itemId && line.quantity===r.lines[i].quantity,'Invalid quote line');
      int(line.rental);int(line.deposit);rentalSum=addMoney(rentalSum,line.rental);depositSum=addMoney(depositSum,line.deposit);
    }
    valid(rentalSum===r.quote.rentalSubtotal && depositSum===r.quote.deposit,'Invalid quote totals');
    if(store.schemaVersion===2) {
      int(r.quote.lateFeePerUnitDay);
      valid(Array.isArray(r.returnedLines) && r.returnedLines.length===r.lines.length,'Invalid returned lines');
      let returnedDeposit=0,allReturned=true,anyReturned=false;
      for(let i=0;i<r.lines.length;i++) {
        const line=r.returnedLines[i],booked=r.lines[i],priced=r.quote.lines[i];
        valid(object(line)&&line.itemId===booked.itemId,'Invalid returned line');
        int(line.quantity,0,booked.quantity);
        valid(priced.deposit%booked.quantity===0,'Invalid unit deposit');
        returnedDeposit=addMoney(returnedDeposit,multiplyMoney(priced.deposit/booked.quantity,line.quantity));
        if(line.quantity<booked.quantity) allReturned=false;
        if(line.quantity>0) anyReturned=true;
      }
      int(r.refunded);int(r.lateFees);
      valid(addMoney(r.refunded,r.lateFees)===returnedDeposit,'Invalid return accounting');
      valid((r.status==='returned')===allReturned,'Invalid returned status');
      valid(!(r.status==='reserved'||r.status==='cancelled')||!anyReturned,'Invalid return state');
    }
  }
  const maintenanceIds=new Set();
  for(const record of store.maintenance??[]) {
    valid(object(record) && id(record.id) && !maintenanceIds.has(record.id) && id(record.itemId),'Invalid maintenance');
    maintenanceIds.add(record.id);range(record.start,record.end);int(record.quantity,1);
  }
  for(let i=0;i<store.audit.length;i++) {
    const event=store.audit[i];valid(object(event) && id(event.type) && id(event.id) && event.revision===i+1,'Invalid audit');
  }
  if(store.schemaVersion===1) valid(Object.keys(store.idempotency).length===store.revision,'Invalid idempotency records');
  for(const [key,entry] of Object.entries(store.idempotency)) valid(id(key)&&object(entry)&&typeof entry.fingerprint==='string'&&object(entry.result),'Invalid idempotency record');
  for(const [key,entry] of Object.entries(store.batchIdempotency??{})) valid(id(key)&&object(entry)&&typeof entry.fingerprint==='string'&&Array.isArray(entry.result),'Invalid batch idempotency record');
  return store;
}); }
export function migrateStore(store) { validateStore(store);if(store.schemaVersion===2) return store;
  const next=structuredClone(store);next.schemaVersion=2;next.batchIdempotency={};next.maintenance??=[];
  for(const r of next.reservations) {
    r.quote.lateFeePerUnitDay=0;
    r.returnedLines=r.lines.map(line=>({itemId:line.itemId,quantity:r.status==='returned'?line.quantity:0}));
    r.refunded=r.status==='returned'?r.quote.deposit:0;r.lateFees=0;
  }
  return validateStore(next);
}
function range(start,end) { return safe(()=>daysInRange(start,end)); }
function requestLines(lines) { return safe(()=>{
  valid(Array.isArray(lines)&&lines.length>0,'Lines required'); const seen=new Set();
  return lines.map(line=>{valid(object(line)&&id(line.itemId)&&!seen.has(line.itemId),'Invalid or duplicate item ID');seen.add(line.itemId);int(line.quantity,1);return {itemId:line.itemId,quantity:line.quantity};});
}); }
function occupied(r,day) {return (r.status==='reserved'||r.status==='checked_out') && r.start<=day && day<r.end;}
function unreturned(r,line) {return line.quantity-(r.returnedLines?.find(x=>x.itemId===line.itemId)?.quantity??0);}
function maintained(record,day) {return record.start<=day && day<record.end;}
export function availability(catalog,store,request) { return safe(()=>{
  validateCatalog(catalog);validateStore(store); valid(object(request),'Request required');
  const days=range(request.start,request.end);
  return catalog.items.map(item=>{
    let minimum=item.stock;
    for(const day of days) {
      let used=0;
      for(const r of store.reservations) if(occupied(r,day)) for(const line of r.lines) if(line.itemId===item.id) used=addMoney(used,unreturned(r,line));
      for(const record of store.maintenance??[]) if(record.itemId===item.id && maintained(record,day)) used=addMoney(used,record.quantity);
      minimum=Math.min(minimum,item.stock-used);
    }
    return {itemId:item.id,available:minimum};
  });
}); }
export function quote(catalog,store,request) { return safe(()=>{
  validateCatalog(catalog);validateStore(store);valid(object(request)&&id(request.memberId),'Member ID required');
  const member=catalog.members.find(m=>m.id===request.memberId);if(!member) fail('NOT_FOUND','Member not found');
  const days=range(request.start,request.end), lines=requestLines(request.lines);
  const available=new Map(availability(catalog,store,request).map(x=>[x.itemId,x.available]));
  let rentalSubtotal=0,deposit=0;
  const priced=lines.map(line=>{
    const item=catalog.items.find(i=>i.id===line.itemId);if(!item) fail('NOT_FOUND','Item not found');
    if(line.quantity>available.get(item.id)) fail('CAPACITY','Insufficient capacity for '+item.id);
    let unitDays=0;
    for(const day of days) unitDays=addMoney(unitDays,isWeekend(day)?roundRatio(item.rate,catalog.pricing?.weekendBps??10000,10000):item.rate);
    const rental=multiplyMoney(line.quantity,unitDays), lineDeposit=multiplyMoney(line.quantity,item.deposit);
    rentalSubtotal=addMoney(rentalSubtotal,rental);deposit=addMoney(deposit,lineDeposit);
    return {...line,rental,deposit:lineDeposit};
  });
  const discount=Math.min(roundRatio(rentalSubtotal,member.discountBps,10000),catalog.pricing?.discountCap??Number.MAX_SAFE_INTEGER),rentalTotal=rentalSubtotal-discount;
  return {memberId:request.memberId,start:request.start,end:request.end,lines:priced,rentalSubtotal,discount,rentalTotal,deposit,totalDue:addMoney(rentalTotal,deposit)};
}); }
export function reservations(store) { validateStore(store);return store.reservations.map(r=>structuredClone(r)); }
export function maintenance(store) { validateStore(store);return structuredClone(store.maintenance??[]); }
export function report(store) { return safe(()=>{
  validateStore(store); const counts={reserved:0,checked_out:0,returned:0,cancelled:0};
  let rentalRevenue=0,depositHeld=0,refunded=0,lateFees=0;
  for(const r of store.reservations) {
    counts[r.status]++;
    if(r.status!=='cancelled') rentalRevenue=addMoney(rentalRevenue,r.quote.rentalTotal);
    if(r.status==='reserved'||r.status==='checked_out') for(let i=0;i<r.lines.length;i++) depositHeld=addMoney(depositHeld,multiplyMoney(r.quote.lines[i].deposit/r.lines[i].quantity,unreturned(r,r.lines[i])));
    refunded=addMoney(refunded,r.refunded??(r.status==='returned'?r.quote.deposit:0));
    lateFees=addMoney(lateFees,r.lateFees??0);
  }
  return {reservationCount:store.reservations.length,maintenanceCount:(store.maintenance??[]).length,counts,rentalRevenue,depositHeld,refunded,lateFees,auditCount:store.audit.length};
}); }
function canonical(value) {if(Array.isArray(value)) return value.map(canonical);if(object(value)) return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical(value[k])]));return value;}
function fingerprint(command) {const content={...command};delete content.expectedRevision;delete content.idempotencyKey;return JSON.stringify(canonical(content));}
export function command(catalog,store,request,{timestamp=null}={}) { return safe(()=>{
  validateCatalog(catalog);validateStore(store);valid(object(request),'Command required');
  valid(id(request.idempotencyKey),'Idempotency key required');int(request.expectedRevision);
  const signature=fingerprint(request),prior=Object.hasOwn(store.idempotency,request.idempotencyKey)?store.idempotency[request.idempotencyKey]:undefined;
  if(prior) {if(prior.fingerprint!==signature) fail('IDEMPOTENCY_CONFLICT','Idempotency key already used');return {store,result:structuredClone(prior.result),replay:true};}
  if(request.expectedRevision!==store.revision) fail('REVISION_CONFLICT','Revision mismatch');
  const outcome=applyCommand(catalog,structuredClone(migrateStore(store)),request,timestamp);
  Object.defineProperty(outcome.store.idempotency,request.idempotencyKey,{value:{fingerprint:signature,result:structuredClone(outcome.result)},enumerable:true,writable:true,configurable:true});
  return {...outcome,replay:false};
}); }
function applyCommand(catalog,store,request,timestamp) {
  valid(id(request.id),'ID required');
  // The private transition receives an exclusively owned transaction draft.
  const next=store;let result;
  if(request.type==='reserve') {
    if(next.reservations.some(r=>r.id===request.id)) fail('VALIDATION','Reservation ID already used');
    const accepted=quote(catalog,store,request);
    accepted.lateFeePerUnitDay=catalog.pricing?.lateFeePerUnitDay??0;
    const lines=accepted.lines.map(({itemId,quantity})=>({itemId,quantity}));
    const r={id:request.id,memberId:accepted.memberId,start:accepted.start,end:accepted.end,lines,status:'reserved',quote:accepted,returnedLines:lines.map(({itemId})=>({itemId,quantity:0})),refunded:0,lateFees:0};
    next.reservations.push(r);result=structuredClone(r);
  } else if(['cancel','checkout','return','return.partial'].includes(request.type)) {
    const r=next.reservations.find(x=>x.id===request.id);if(!r) fail('NOT_FOUND','Reservation not found');
    const returning=request.type==='return'||request.type==='return.partial';
    const required=returning?'checked_out':'reserved';
    if(r.status!==required) fail('INVALID_TRANSITION','Invalid status transition');
    if(returning) {
      valid(request.type!=='return.partial'||request.returnedOn!==undefined,'Expected returnedOn');
      const returnedOn=request.returnedOn===undefined?r.end:request.returnedOn;
      valid(dayNumber(returnedOn)>=dayNumber(r.start),'Return date precedes start');
      const lines=request.type==='return.partial'?requestLines(request.lines):r.lines.map(line=>({itemId:line.itemId,quantity:unreturned(r,line)}));
      let deposit=0,returnedQuantity=0;
      for(const line of lines) {
        const booked=r.lines.find(x=>x.itemId===line.itemId);
        valid(booked!==undefined,'Item is not in reservation');
        valid(line.quantity<=unreturned(r,booked),'Return quantity exceeds remaining units');
        const priced=r.quote.lines.find(x=>x.itemId===line.itemId);
        deposit=addMoney(deposit,multiplyMoney(priced.deposit/booked.quantity,line.quantity));
        returnedQuantity=addMoney(returnedQuantity,line.quantity);
        r.returnedLines.find(x=>x.itemId===line.itemId).quantity+=line.quantity;
      }
      const rawFee=BigInt(returnedQuantity)*BigInt(daysLate(returnedOn,r.end))*BigInt(r.quote.lateFeePerUnitDay);
      const lateFee=Number(rawFee>BigInt(deposit)?BigInt(deposit):rawFee);
      const refund=deposit-lateFee;
      r.refunded=addMoney(r.refunded,refund);r.lateFees=addMoney(r.lateFees,lateFee);
      if(r.lines.every(line=>unreturned(r,line)===0)) r.status='returned';
      result={...structuredClone(r),refund,lateFee,returnedQuantity};
    } else {r.status=request.type==='cancel'?'cancelled':'checked_out';result=structuredClone(r);}
  } else if(request.type==='maintenance.add') {
    if((next.maintenance??[]).some(x=>x.id===request.id)) fail('VALIDATION','Maintenance ID already used');
    valid(id(request.itemId),'Item ID required');int(request.quantity,1);
    const item=catalog.items.find(x=>x.id===request.itemId);if(!item) fail('NOT_FOUND','Item not found');
    const available=availability(catalog,store,{start:request.start,end:request.end}).find(x=>x.itemId===item.id).available;
    if(request.quantity>available) fail('CAPACITY','Insufficient capacity for '+item.id);
    result={id:request.id,itemId:item.id,start:request.start,end:request.end,quantity:request.quantity};
    if(!next.maintenance) next.maintenance=[];
    next.maintenance.push(result);
  } else if(request.type==='maintenance.remove') {
    const index=(next.maintenance??[]).findIndex(x=>x.id===request.id);
    if(index<0) fail('NOT_FOUND','Maintenance not found');
    result=next.maintenance.splice(index,1)[0];
  } else fail('VALIDATION','Unknown command type');
  next.revision++;
  next.audit.push({revision:next.revision,type:request.type,id:request.id,timestamp});
  return {store:next,result:structuredClone(result)};
}
export function batch(catalog,store,request,{timestamp=null}={}) {return safe(()=>{
  validateCatalog(catalog);validateStore(store);valid(object(request),'Batch required');
  valid(id(request.idempotencyKey),'Idempotency key required');int(request.expectedRevision);
  valid(Array.isArray(request.commands)&&request.commands.length>=1&&request.commands.length<=20,'Batch requires 1..20 commands');
  const signature=fingerprint(request),prior=Object.hasOwn(store.batchIdempotency??{},request.idempotencyKey)?store.batchIdempotency[request.idempotencyKey]:undefined;
  if(prior) {if(prior.fingerprint!==signature) fail('IDEMPOTENCY_CONFLICT','Idempotency key already used');return {store,result:structuredClone(prior.result),replay:true};}
  if(request.expectedRevision!==store.revision) fail('REVISION_CONFLICT','Revision mismatch');
  let current=structuredClone(migrateStore(store));const results=[];
  for(const inner of request.commands) {
    valid(object(inner)&&!Object.hasOwn(inner,'expectedRevision')&&!Object.hasOwn(inner,'idempotencyKey'),'Inner commands cannot contain mutation fields');
    const outcome=applyCommand(catalog,current,inner,timestamp);current=outcome.store;results.push(outcome.result);
  }
  Object.defineProperty(current.batchIdempotency,request.idempotencyKey,{value:{fingerprint:signature,result:structuredClone(results)},enumerable:true,writable:true,configurable:true});
  return {store:current,result:results,replay:false};
});}
