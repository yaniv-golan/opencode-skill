# Duration spec

`parseDuration(str)` returns a whole number of milliseconds (`Math.round`).
- Units: `d`, `h`, `m`, `s`, `ms`. A duration is one or more `<number><unit>` components, optionally
  separated by whitespace, e.g. `90s`, `1h30m`, `2d 4h`, `1.5h`, `250ms`, `1h 0m 5s`.
- Numbers are non-negative decimals (`1`, `1.5`, `0.25`); no sign, no exponent.
- Units must appear in descending order (d, h, m, s, ms) and at most once each.
- Leading and trailing whitespace is ignored.
- A non-string argument throws `TypeError`. An empty, invalid, duplicated or out-of-order input throws
  `RangeError`.

`formatDuration(ms)` is the inverse for whole, non-negative numbers of milliseconds.
- Anything else (negative, fractional, non-number, NaN, Infinity) throws `RangeError`.
- Largest units first, no spaces, zero components omitted: `5400000` → `1h30m`,
  `93784005` → `1d2h3m4s5ms`, `0` → `0ms`.
- `parseDuration(formatDuration(n)) === n` for every whole `n >= 0`.
