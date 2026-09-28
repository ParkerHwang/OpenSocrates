// Supplied adapter-only console. Contains no rental/pricing rules.
const $=id=>document.getElementById(id);
let revision=0;
const quote={memberId:'club',start:'2026-11-06',end:'2026-11-09',lines:[{itemId:'camera',quantity:1}]};
function example(kind) {
  $('operation').value=kind;
  const mutation=kind==='maintenance.add'
    ? {type:kind,id:`maintenance-${crypto.randomUUID().slice(0,8)}`,itemId:'camera',start:'2026-11-10',end:'2026-11-12',quantity:1}
    : {type:'reserve',id:`booking-${crypto.randomUUID().slice(0,8)}`,...quote};
  $('request').value=JSON.stringify(kind==='quote'?quote:{...mutation,idempotencyKey:crypto.randomUUID(),expectedRevision:revision},null,2);
  if(kind==='maintenance.add') $('operation').value='command';
}
async function request(operation,payload) {
  const options=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
  const response=await fetch(`/api/${operation}`,options);
  const data=await response.json();
  if(Number.isInteger(data.revision)) revision=data.revision;
  $('response').textContent=JSON.stringify(data,null,2);
  $('status').textContent=data.ok?`완료 · revision ${revision}`:`요청 실패: ${data.error?.code ?? response.status} · ${data.error?.message ?? ''}`;
  return data;
}
async function bookings() {
  const response=await fetch('/api/reservations'); const result=await response.json();
  if(Number.isInteger(result.revision))revision=result.revision;
  $('bookings').replaceChildren();
  if(!result.ok || !Array.isArray(result.data)) { $('bookings').textContent='예약을 읽지 못했습니다.'; return; }
  if(!result.data.length) { $('bookings').textContent='등록된 예약이 없습니다.'; return; }
  for(const item of result.data) {
    const row=document.createElement('article');
    const heading=document.createElement('strong'); heading.textContent=`${item.id} · ${item.status}`;
    const detail=document.createElement('p');detail.textContent=`${item.memberId} · ${item.start} ~ ${item.end} · ${item.quote?.totalDue ?? '—'}원`;
    row.append(heading,detail);$('bookings').append(row);
  }
}
document.querySelectorAll('[data-read]').forEach(button=>button.addEventListener('click',()=>request(button.dataset.read).catch(e=>{$('status').textContent=e.message;})));
$('quote-example').addEventListener('click',()=>example('quote'));
$('reserve-example').addEventListener('click',()=>example('command'));
$('maintenance-example').addEventListener('click',()=>example('maintenance.add'));
$('refresh').addEventListener('click',()=>bookings().catch(e=>{$('status').textContent=e.message;}));
$('request-form').addEventListener('submit',async event=>{
  event.preventDefault();
  try { await request($('operation').value,JSON.parse($('request').value));await bookings(); }
  catch(error) { $('status').textContent=`오류: ${error.message}`; }
});
example('quote');bookings().catch(error=>{$('status').textContent=`서버 연결: ${error.message}`;});
