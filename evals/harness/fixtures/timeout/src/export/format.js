'use strict';

function toCsv(rows) {
  if (!rows.length) return '';
  const cols = Object.keys(rows[0]);
  const lines = rows.map((r) => cols.map((c) => JSON.stringify(r[c] ?? '')).join(','));
  return [cols.join(','), ...lines].join('\n');
}

function toJson(rows) {
  return JSON.stringify(rows, null, 2);
}

module.exports = { toCsv, toJson };
