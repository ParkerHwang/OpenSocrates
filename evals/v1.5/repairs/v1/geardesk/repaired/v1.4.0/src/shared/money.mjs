/** Generic integer helpers supplied before either implementation. */
export function integer(value, {min=0,max=Number.MAX_SAFE_INTEGER}={}) {
  if (!Number.isSafeInteger(value) || value<min || value>max) throw new TypeError('Expected bounded integer');
  return value;
}
export function addMoney(...values) {
  let total=0;
  for (const value of values) { integer(value); total=integer(total+value); }
  return total;
}
export function multiplyMoney(value, quantity) {
  integer(value); integer(quantity); return integer(value*quantity);
}
export function roundRatio(value, numerator, denominator) {
  integer(value); integer(numerator); integer(denominator,{min:1});
  const v=BigInt(value)*BigInt(numerator), d=BigInt(denominator);
  return integer(Number((2n*v+d)/(2n*d)));
}
