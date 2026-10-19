export function unique_values(a) {
  return [...new Set(a)];
}

export function chunk_array(a, n) {
  const out = [];
  for (let i = 0; i < a.length; i += n) out.push(a.slice(i, i + n));
  return out;
}

export function flatten_deep(a) {
  return a.reduce((acc, x) => acc.concat(Array.isArray(x) ? flatten_deep(x) : x), []);
}
