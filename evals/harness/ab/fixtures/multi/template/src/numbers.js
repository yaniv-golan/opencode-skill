export function clamp_value(x, lo, hi) {
  return Math.min(hi, Math.max(lo, x));
}

export function round_to(x, d) {
  const f = 10 ** d;
  return Math.round(x * f) / f;
}

export function sum_all(a) {
  return a.reduce((s, x) => s + x, 0);
}
