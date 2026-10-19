import test from "node:test";
import assert from "node:assert/strict";
import * as d from "../duration.js";

test("module loads", () => {
  assert.equal(typeof d.parseDuration, "function");
});
