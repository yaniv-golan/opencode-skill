// Grader for the A/B. Writes ../verify.json ({pass, failures}); always exits 0.
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import assert from "node:assert/strict";
const failures = [];
async function check(name, fn) { try { await fn(); } catch (e) { failures.push(`${name}: ${e.message}`); } }
await check("sub", async () => {
  const m = await import("./math.js");
  assert.equal(m.sub(5, 3), 2);
  assert.equal(m.sub(-1, -1), 0);
  assert.equal(m.add(2, 3), 5);
});
await check("sub tested", async () => {
  assert.match(readFileSync(new URL("./test/math.test.js", import.meta.url), "utf8"), /\bsub\(/);
});

const t = spawnSync(process.execPath, ["--test"], { encoding: "utf8" });
if (t.status !== 0) failures.push("node --test failed:\n" + (t.stdout + t.stderr).slice(-1500));
writeFileSync(new URL("../verify.json", import.meta.url), JSON.stringify({ pass: failures.length === 0, failures }, null, 2));
console.log(failures.length ? "FAIL\n" + failures.join("\n") : "PASS");
