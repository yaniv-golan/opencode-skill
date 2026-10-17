'use strict';

// Parse "YYYY-MM-DD" into a Date (UTC midnight).
function parseDate(input) {
  const [y, m, d] = String(input).split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

module.exports = { parseDate };
