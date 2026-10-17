#!/usr/bin/env node
'use strict';

const { parseDate } = require('./date');

const args = process.argv.slice(2);
const flags = { format: 'iso', verbose: false, date: null };

for (let i = 0; i < args.length; i++) {
  const arg = args[i];
  if (arg === '--format' || arg === '-f') flags.format = args[++i];
  else if (arg === '--verbose' || arg === '-v') flags.verbose = true;
  else if (arg === '--date' || arg === '-d') flags.date = args[++i];
  else if (arg === '--help' || arg === '-h') {
    console.log('usage: cli [--date YYYY-MM-DD] [--format iso|epoch] [--verbose]');
    process.exit(0);
  }
}

const date = parseDate(flags.date || new Date().toISOString().slice(0, 10));
if (flags.verbose) console.error(`parsed ${flags.date}`);
console.log(flags.format === 'epoch' ? String(date.getTime()) : date.toISOString());
