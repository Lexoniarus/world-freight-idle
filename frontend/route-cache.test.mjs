import test from "node:test";
import assert from "node:assert/strict";
import { RouteCache } from "./route-cache.js";

const geometry = {
  coordinates: [
    [10, 50],
    [11, 51],
  ],
  legs: [],
};
const turn = () => new Promise((resolve) => setImmediate(resolve));

test("route cache coalesces, prioritizes and bounds downloads", async () => {
  const calls = [];
  const cache = new RouteCache(
    (path, options) =>
      new Promise((resolve, reject) => {
        calls.push({ path, resolve, reject, signal: options.signal });
      }),
  );
  const first = cache.load("0");
  assert.equal(cache.load("0", -1), first);
  const promises = [first, ...[1, 2, 3, 4, 5, 6].map((id) => cache.load(String(id)))];
  assert.equal(calls.length, 4);

  cache.load("6", -1);
  calls[0].resolve(geometry);
  await turn();
  assert.equal(calls[4].path, "/map/routes/6");
  assert.equal(cache.active, 4);

  calls[1].reject(new Error("network"));
  const failure = assert.rejects(promises[1], /network/);
  await turn();
  calls[2].resolve(geometry);
  await turn();
  for (const call of calls.slice(3)) call.resolve(geometry);
  await Promise.all([failure, ...promises.filter((_, index) => index !== 1)]);
  const count = calls.length;
  await cache.load("0");
  assert.equal(calls.length, count);
  cache.destroy();
});

test("route cache aborts pending work when its account lifetime ends", async () => {
  const calls = [];
  const cache = new RouteCache(
    (path, options) =>
      new Promise((resolve) => calls.push({ path, resolve, signal: options.signal })),
  );
  const pending = cache.load("late");
  const rejected = assert.rejects(pending, { name: "AbortError" });

  cache.destroy();

  await rejected;
  assert.equal(calls[0].signal.aborted, true);
  calls[0].resolve(geometry);
  await turn();
  assert.equal(cache.values.size, 0);
  await assert.rejects(cache.load("new"), { name: "AbortError" });
});

test("route cache retains only the 200 most recent geometries", async () => {
  const cache = new RouteCache(async () => geometry);
  for (let index = 0; index < 200; index++) await cache.load(String(index));
  cache.get("0");
  await cache.load("200");
  assert.equal(cache.values.size, 200);
  assert.equal(cache.get("1"), undefined);
  assert.ok(cache.get("0"));
  cache.destroy();
});
