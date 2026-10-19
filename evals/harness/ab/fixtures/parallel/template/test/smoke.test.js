import test from "node:test";
import assert from "node:assert/strict";
import { slugify } from "../text.js";
import { LRUCache } from "../cache.js";

test("modules load", () => {
  assert.equal(typeof slugify, "function");
  assert.equal(typeof LRUCache, "function");
});
