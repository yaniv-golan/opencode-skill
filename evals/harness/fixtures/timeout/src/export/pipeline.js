'use strict';

const fs = require('fs');
const { toCsv, toJson } = require('./format');

// Load, filter, format and write in one function: this is what needs refactoring.
function runExport(inputPath, outputPath, { format = 'csv', minAge = 0 } = {}) {
  const raw = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
  const rows = raw.filter((r) => (r.age || 0) >= minAge);
  let out;
  if (format === 'csv') out = toCsv(rows);
  else if (format === 'json') out = toJson(rows);
  else throw new Error('unknown format: ' + format);
  fs.writeFileSync(outputPath, out);
  return rows.length;
}

module.exports = { runExport };
