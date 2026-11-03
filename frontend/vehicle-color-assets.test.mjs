import test from "node:test";
import assert from "node:assert/strict";
import { model, source, TestColorAssets } from "./test-support/vehicle-color-fixtures.mjs";

test("color assets share sources and release color-specific leases", async () => {
  let reads = 0;
  const service = new TestColorAssets(async () => {
    reads++;
    return source;
  });
  const [first, shared, distinct] = await Promise.all([
    service.acquire(model, "front", "#e45756"),
    service.acquire(model, "front", "#e45756"),
    service.acquire(model, "front", "#4c78a8"),
  ]);
  assert.equal(reads, 2);
  assert.equal(first.url, shared.url);
  assert.notEqual(first.url, distinct.url);
  assert.match(await (await fetch(first.url)).text(), /--vehicle-color:#e45756/);
  first.release();
  assert.equal(service.peek(model, "front", "#e45756"), shared.url);
  shared.release();
  assert.equal(service.peek(model, "front", "#e45756"), undefined);
  distinct.release();
  service.destroy();
  await assert.rejects(service.acquire(model, "front", "#e45756"));
});
