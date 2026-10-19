export function to_title_case(s) {
  return s.replace(/\b\w/g, (c) => c.toUpperCase());
}

export function count_words(s) {
  return s.trim() === "" ? 0 : s.trim().split(/\s+/).length;
}

export function truncate_text(s, n) {
  return s.length <= n ? s : s.slice(0, Math.max(0, n - 1)) + "…";
}
