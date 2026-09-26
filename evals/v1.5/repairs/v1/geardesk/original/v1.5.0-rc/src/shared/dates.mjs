/** Whole UTC days; no current clock or I/O. */
const DAY=86400000;
export function dayNumber(value) {
  if (typeof value!=='string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new TypeError('Expected ISO day');
  const time=Date.parse(value+'T00:00:00.000Z');
  if (!Number.isFinite(time) || new Date(time).toISOString().slice(0,10)!==value) throw new TypeError('Invalid day');
  return time/DAY;
}
export function daysInRange(start,end) {
  const a=dayNumber(start),b=dayNumber(end);
  if (b<=a || b-a>30) throw new RangeError('Expected 1..30 days');
  return Array.from({length:b-a},(_,i)=>new Date((a+i)*DAY).toISOString().slice(0,10));
}
export function isWeekend(value) {
  const d=new Date(dayNumber(value)*DAY).getUTCDay(); return d===0 || d===6;
}
export function daysLate(actual,scheduledEnd) { return Math.max(0,dayNumber(actual)-dayNumber(scheduledEnd)); }
