// Grader for the A/B. Writes ../verify.json ({pass, failures}); always exits 0.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import assert from "node:assert/strict";
const failures = [];
async function check(name, fn) { try { await fn(); } catch (e) { failures.push(`${name}: ${e.message}`); } }
const { parseDuration: p, formatDuration: f } = await import("./duration.js");
const ok = { "90s": 90000, "1h30m": 5400000, "2d 4h": 187200000, "1.5h": 5400000, "250ms": 250,
  "1h 0m 5s": 3605000, "  10m  ": 600000, "1d2h3m4s5ms": 93784005, "0.25s": 250, "0ms": 0, "1m1ms": 60001 };
for (const [s, v] of Object.entries(ok)) await check(`parse ${JSON.stringify(s)}`, () => assert.equal(p(s), v));
for (const s of ["", "  ", "5", "h", "1x", "-1h", "1m1h", "1h1h", "1e3s", "1.h", "1 h", "abc", "1h,30m"])
  await check(`parse rejects ${JSON.stringify(s)}`, () => assert.throws(() => p(s), RangeError));
for (const v of [5, null, undefined, {}]) await check(`parse TypeError ${String(v)}`, () => assert.throws(() => p(v), TypeError));
const fm = { 5400000: "1h30m", 93784005: "1d2h3m4s5ms", 0: "0ms", 1000: "1s", 86400000: "1d", 61001: "1m1s1ms" };
for (const [n, s] of Object.entries(fm)) await check(`format ${n}`, () => assert.equal(f(Number(n)), s));
for (const v of [-1, 1.5, NaN, Infinity, "5"]) await check(`format rejects ${String(v)}`, () => assert.throws(() => f(v), RangeError));
await check("round trip", () => { for (const n of [0, 1, 999, 1000, 59999, 3600001, 90061001, 123456789]) assert.equal(p(f(n)), n); });
await check("tests written", () => {
  const src = readFileSync(new URL("./test/duration.test.js", import.meta.url), "utf8");
  assert.match(src, /parseDuration/); assert.match(src, /formatDuration/);
});

const t = spawnSync(process.execPath, ["--test"], { encoding: "utf8" });
if (t.status !== 0) failures.push("node --test failed:\n" + (t.stdout + t.stderr).slice(-1500));
writeFileSync(new URL("../verify.json", import.meta.url), JSON.stringify({ pass: failures.length === 0, failures }, null, 2));
console.log(failures.length ? "FAIL\n" + failures.join("\n") : "PASS");
