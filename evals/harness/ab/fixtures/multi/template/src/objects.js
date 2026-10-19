export function pick_keys(o, keys) {
  return Object.fromEntries(keys.filter((k) => k in o).map((k) => [k, o[k]]));
}

export function omit_keys(o, keys) {
  return Object.fromEntries(Object.entries(o).filter(([k]) => !keys.includes(k)));
}

export function deep_clone(o) {
  return structuredClone(o);
}
