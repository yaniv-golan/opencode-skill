// Grader for the A/B. Writes ../verify.json ({pass, failures}); always exits 0.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import assert from "node:assert/strict";
const failures = [];
async function check(name, fn) { try { await fn(); } catch (e) { failures.push(`${name}: ${e.message}`); } }
const want = {
  strings: { toTitleCase: [["the fox"], "The Fox"], countWords: [["a b  c"], 3], truncateText: [["hello world", 5], "hell…"] },
  arrays: { uniqueValues: [[[1, 1, 2]], [1, 2]], chunkArray: [[[1, 2, 3], 2], [[1, 2], [3]]], flattenDeep: [[[1, [2, [3]]]], [1, 2, 3]] },
  objects: { pickKeys: [[{ a: 1, b: 2 }, ["a"]], { a: 1 }], omitKeys: [[{ a: 1, b: 2 }, ["a"]], { b: 2 }], deepClone: [[{ a: { b: 1 } }], { a: { b: 1 } }] },
  numbers: { clampValue: [[15, 0, 10], 10], roundTo: [[3.14159, 2], 3.14], sumAll: [[[1, 2, 3]], 6] },
};
for (const [mod, fns] of Object.entries(want)) {
  const m = await import(`./src/${mod}.js`);
  await check(`${mod} no snake_case exports`, () => assert.deepEqual(Object.keys(m).filter((k) => k.includes("_")), []));
  for (const [fn, [args, out]] of Object.entries(fns)) await check(`${mod}.${fn}`, () => assert.deepEqual(m[fn](...args), out));
  await check(`test/${mod}.test.js covers every export`, () => {
    const src = readFileSync(new URL(`./test/${mod}.test.js`, import.meta.url), "utf8");
    for (const fn of Object.keys(fns)) assert.match(src, new RegExp(`\\b${fn}\\b`), `${fn} not tested`);
  });
}
await check("cli runs, no old names", () => {
  const src = readFileSync(new URL("./cli.js", import.meta.url), "utf8");
  assert.doesNotMatch(src, /\b[a-z]+_[a-z_]+\(/);
  const r = spawnSync(process.execPath, ["cli.js"], { encoding: "utf8", cwd: new URL(".", import.meta.url) });
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /The Quick Brown Fox 4 the quick…/);
});

const t = spawnSync(process.execPath, ["--test"], { encoding: "utf8" });
if (t.status !== 0) failures.push("node --test failed:\n" + (t.stdout + t.stderr).slice(-1500));
writeFileSync(new URL("../verify.json", import.meta.url), JSON.stringify({ pass: failures.length === 0, failures }, null, 2));
console.log(failures.length ? "FAIL\n" + failures.join("\n") : "PASS");
