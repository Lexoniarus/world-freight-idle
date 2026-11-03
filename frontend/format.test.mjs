import test from "node:test";
import assert from "node:assert/strict";
import { money, number } from "./format.js";
import { formatDuration } from "./time.js";

test("display formatters preserve money, measurement and duration semantics", () => {
  assert.match(money(1200), /1\.200/);
  assert.equal(number(12.5), "12,5");
  assert.equal(formatDuration(3660), "1 h 1 min");
  assert.equal(formatDuration(90061), "1 T 1 h 1 min");
});
