import test from "node:test";
import assert from "node:assert/strict";
import { DeferredMap } from "./map/deferred-map.js";

function fixture(create) {
  const frames = new Map(),
    notices = [];
  let next = 0;
  const map = new DeferredMap({
    create,
    notify: (message) => notices.push(message),
    frame: (callback) => {
      frames.set(++next, callback);
      return next;
    },
    cancelFrame: (id) => frames.delete(id),
  });
  const tick = () => {
    const callbacks = [...frames.values()];
    frames.clear();
    for (const callback of callbacks) callback();
  };
  return { map, frames, tick, notices };
}

test("map waits for a painted runtime and applies only latest presentation state", async () => {
  const renderer = new EventTarget(),
    calls = [];
  renderer.ready = false;
  for (const name of [
    "update",
    "setCompanyColor",
    "setGrouping",
    "setPreset",
    "setPreview",
    "select",
    "toggle",
    "fitCoordinates",
    "focusRoute",
    "focusFleet",
    "destroy",
  ])
    renderer[name] = (...args) => calls.push([name, ...args]);
  let creates = 0;
  const { map, tick } = fixture(async () => {
    creates++;
    return renderer;
  });
  let ready = 0;
  map.addEventListener("ready", () => ready++);
  map.setCompanyColor("red");
  assert.equal(creates, 0);
  map.update({ vehicles: ["old"] });
  map.update({ vehicles: ["current"] });
  map.setGrouping(false);
  map.setPreset("fleet");
  map.setPreview(null);
  map.select("old");
  map.select("current");
  map.toggle("routes", true);
  map.toggle("vehicles", false);
  map.fitCoordinates([[10, 50]]);
  map.focusRoute({ type: "LineString", coordinates: [] });
  map.focusFleet();
  tick();
  assert.equal(creates, 0);
  tick();
  await new Promise(setImmediate);
  assert.equal(creates, 1);
  assert.equal(map.ready, false);
  assert.deepEqual(
    calls.filter((c) => c[0] === "update"),
    [["update", { vehicles: ["current"] }]],
  );
  assert.deepEqual(
    calls.filter((c) => c[0] === "select"),
    [["select", "current", null]],
  );
  assert.equal(calls.filter((c) => c[0] === "toggle").length, 2);
  assert.equal(calls.at(-1)[0], "focusFleet");
  renderer.ready = true;
  renderer.dispatchEvent(new Event("ready"));
  assert.equal(ready, 1);
  assert.equal(map.ready, true);
  map.setCompanyColor("blue");
  assert.deepEqual(calls.at(-1), ["setCompanyColor", "blue"]);
  map.destroy();
  map.destroy();
  renderer.dispatchEvent(new Event("ready"));
  map.update({ vehicles: [] });
  assert.equal(ready, 1);
  assert.equal(calls.at(-1)[0], "destroy");
  assert.equal(map.pending.size, 0);
});

test("map cancellation, late load and module failure leave controls independent", async () => {
  let creates = 0;
  const cancelled = fixture(async () => {
    creates++;
    return null;
  });
  cancelled.map.update({});
  cancelled.map.destroy();
  cancelled.tick();
  assert.equal(creates, 0);
  assert.equal(cancelled.frames.size, 0);
  let resolve;
  const late = fixture(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  late.map.update({});
  late.tick();
  late.tick();
  late.map.destroy();
  let removed = 0;
  resolve({
    destroy() {
      removed++;
    },
  });
  await new Promise(setImmediate);
  assert.equal(removed, 1);
  assert.equal(late.map.renderer, null);
  const failed = fixture(async () => {
    throw new Error("module offline");
  });
  await failed.map.load();
  assert.equal(failed.notices.length, 1);
  failed.map.destroy();
  await failed.map.load();
  assert.equal(failed.notices.length, 1);
  const missing = fixture(async () => null);
  await missing.map.load();
  assert.equal(missing.map.ready, false);
  const ready = new EventTarget();
  ready.ready = true;
  const existing = fixture(async () => ready);
  let events = 0;
  existing.map.addEventListener("ready", () => events++);
  await existing.map.load();
  assert.equal(events, 1);
});
