// Grader for the A/B. Writes ../verify.json ({pass, failures}); always exits 0.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import assert from "node:assert/strict";
const failures = [];
async function check(name, fn) { try { await fn(); } catch (e) { failures.push(`${name}: ${e.message}`); } }
const { slugify } = await import("./text.js");
const { LRUCache } = await import("./cache.js");
const sl = [[["Héllo, Wörld!"], "hello-world"], [["  a--b  "], "a-b"], [["Foo Bar", { separator: "_" }], "foo_bar"],
  [["Foo Bar", { lowercase: false }], "Foo-Bar"], [["!!!"], ""], [["Crème brûlée 2"], "creme-brulee-2"]];
for (const [args, out] of sl) await check(`slugify ${JSON.stringify(args)}`, () => assert.equal(slugify(...args), out));
await check("slugify TypeError", () => assert.throws(() => slugify(5), TypeError));
for (const c of [0, -1, 1.5, "2"]) await check(`LRU rejects ${c}`, () => assert.throws(() => new LRUCache(c), RangeError));
await check("LRU behaviour", () => {
  const c = new LRUCache(2);
  assert.equal(c.set("a", 1), c);
  c.set("b", 2);
  assert.equal(c.get("a"), 1);          // a is now most recent
  c.set("c", 3);                         // evicts b
  assert.equal(c.has("b"), false);
  assert.deepEqual(c.keys(), ["a", "c"]);
  assert.equal(c.has("a"), true);        // no recency change
  c.set("a", 10);                        // update makes a most recent
  assert.deepEqual(c.keys(), ["c", "a"]);
  c.set("d", 4);                         // evicts c
  assert.deepEqual(c.keys(), ["a", "d"]);
  assert.equal(c.size, 2);
  assert.equal(c.delete("a"), true);
  assert.equal(c.delete("a"), false);
  assert.equal(c.get("zz"), undefined);
  assert.equal(c.size, 1);
});
await check("tests written", () => {
  assert.ok(existsSync(new URL("./test/text.test.js", import.meta.url)), "test/text.test.js missing");
  assert.ok(existsSync(new URL("./test/cache.test.js", import.meta.url)), "test/cache.test.js missing");
});

const t = spawnSync(process.execPath, ["--test"], { encoding: "utf8" });
if (t.status !== 0) failures.push("node --test failed:\n" + (t.stdout + t.stderr).slice(-1500));
writeFileSync(new URL("../verify.json", import.meta.url), JSON.stringify({ pass: failures.length === 0, failures }, null, 2));
console.log(failures.length ? "FAIL\n" + failures.join("\n") : "PASS");
