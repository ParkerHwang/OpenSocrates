import test from 'node:test';
import assert from 'node:assert/strict';
import {integer,addMoney,multiplyMoney,roundRatio} from '../src/shared/money.mjs';
import {dayNumber,daysInRange,isWeekend,daysLate} from '../src/shared/dates.mjs';
test('shared integer helpers',()=>{
  assert.equal(roundRatio(3,1,2),2); assert.equal(roundRatio(5,1,2),3);
  assert.equal(multiplyMoney(0,3),0); assert.equal(addMoney(0,10,20),30);
  for (const n of [NaN,Infinity,true,1.5,-1,'1']) assert.throws(()=>integer(n));
  assert.throws(()=>addMoney(Number.MAX_SAFE_INTEGER,1));
});
test('shared date helpers',()=>{
  assert.deepEqual(daysInRange('2026-11-06','2026-11-09'),['2026-11-06','2026-11-07','2026-11-08']);
  assert.equal(isWeekend('2026-11-07'),true); assert.equal(isWeekend('2026-11-09'),false);
  assert.equal(daysLate('2026-11-10','2026-11-09'),1);
  for (const day of ['2026-02-30','2026-13-01','not-a-date']) assert.throws(()=>dayNumber(day));
  assert.throws(()=>daysInRange('2026-11-06','2026-11-06'));
});
