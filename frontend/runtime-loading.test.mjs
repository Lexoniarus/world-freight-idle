import test from "node:test";
import assert from "node:assert/strict";
import { GameState } from "./state.js";
import { RouteCache } from "./route-cache.js";
import { ContractMarketController } from "./controllers/contract-market-controller.js";
import { OverlayData } from "./map/overlay-data.js";
import { focusCoordinates } from "./map/focus-targets.js";

const geometry = {
  coordinates: [
    [10, 50],
    [11, 51],
  ],
  legs: [],
};
const turn = () => new Promise((resolve) => setImmediate(resolve));

test("market requests follow the selected vehicle and discard older vehicle responses", async () => {
  let url = new URL("http://game/contracts?vehicle=first");
  const state = new GameState(async () => {});
  state.data = { contracts: [], vehicles: [], transports: [] };
  const calls = [];
  const controller = new ContractMarketController({
    state,
    currentUrl: () => url,
    notify() {},
    request: (path, options) =>
      new Promise((resolve) => calls.push({ path, resolve, signal: options.signal })),
  });
  controller.start();
  const first = controller.refresh();
  const same = controller.refresh();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, "/contracts?vehicle_id=first");
  assert.equal(calls[0].signal.aborted, false);
  url = new URL("http://game/contracts?vehicle=second");
  const second = controller.refresh();
  assert.equal(calls[0].signal.aborted, true);
  assert.equal(calls[1].path, "/contracts?vehicle_id=second");
  calls[1].resolve({ contracts: [{ id: "second-only" }] });
  await second;
  calls[0].resolve({ contracts: [{ id: "stale-first" }] });
  await Promise.all([first, same]);
  assert.equal(state.data.contracts[0].id, "second-only");
  const refresh = controller.forceRefresh();
  assert.equal(calls[2].path, "/contracts/refresh?vehicle_id=second");
  calls[2].resolve({ contracts: [{ id: "second-only" }] });
  await refresh;
  controller.destroy();
  state.destroy();
});

test("geometry cache coalesces, prioritizes and bounds downloads and account lifetime", async () => {
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
  const pending = cache.load("late");
  const rejected = assert.rejects(pending, { name: "AbortError" });
  cache.destroy();
  await rejected;
  assert.equal(calls.at(-1).signal.aborted, true);
  calls.at(-1).resolve(geometry);
  await turn();
  assert.equal(cache.values.size, 0);
  await assert.rejects(cache.load("new"), { name: "AbortError" });
});

test("route cache keeps only 200 recent immutable geometries", async () => {
  const cache = new RouteCache(async () => geometry);
  for (let index = 0; index < 200; index++) await cache.load(String(index));
  cache.get("0");
  await cache.load("200");
  assert.equal(cache.values.size, 200);
  assert.equal(cache.get("1"), undefined);
  assert.ok(cache.get("0"));
  cache.destroy();
});

test("runtime publishes while traffic is blocked and shares owner geometry with public traffic", async () => {
  let releaseTraffic;
  let downloads = 0;
  let releaseGeometry;
  const shape = new Promise((resolve) => {
    releaseGeometry = resolve;
  });
  const traffic = new Promise((resolve) => {
    releaseTraffic = resolve;
  });
  const state = new GameState(async (path) => {
    if (path === "/runtime")
      return {
        server_time: Date.now() / 1000,
        vehicles: [],
        transports: [{ id: "t", route_ref: "r" }],
      };
    if (path.startsWith("/map/traffic")) return traffic;
    downloads++;
    return shape;
  });
  await state.refresh();
  assert.equal(state.data.transports[0].id, "t");
  assert.deepEqual(state.data.traffic, []);
  assert.equal(state.data.transports[0].route_geojson.coordinates.length, 0);
  releaseGeometry(geometry);
  await state.loadTransportRoute("t");
  assert.equal(downloads, 1);
  releaseTraffic({ transports: [{ id: "t", route_ref: "r", is_own: true }] });
  await state.refreshTraffic();
  assert.equal(state.data.transports[0].route_geojson, state.data.traffic[0].route_geojson);
  const coverage = [{ vehicle_id: "v", offer_count: 2 }];
  state.replaceContracts([], null, coverage);
  await state.refresh();
  await state.refreshTraffic();
  assert.equal(state.data.vehicle_coverage, coverage);
  assert.equal(downloads, 1);
  state.destroy();
  assert.equal(state.routes.values.size, 0);
});

test("identical market and detail polls coalesce; only changed selection invalidates detail", async () => {
  const calls = [];
  let url = new URL("http://game/contracts/a");
  const state = new GameState(async () => {});
  state.data = { contracts: [], vehicles: [], transports: [] };
  const controller = new ContractMarketController({
    state,
    currentUrl: () => url,
    notify() {},
    request: (path, options) =>
      new Promise((resolve) => calls.push({ path, signal: options.signal, resolve })),
  });
  controller.ordersVisible = () => true;
  controller.start();
  const first = controller.refresh(),
    same = controller.refresh();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].signal.aborted, false);
  url = new URL("http://game/contracts/b");
  const next = controller.refresh();
  assert.equal(calls.length, 3);
  assert.equal(calls[1].signal.aborted, true);
  assert.equal(calls[0].signal.aborted, false);
  calls[0].resolve({ contracts: [] });
  calls[2].resolve({ id: "b" });
  await next;
  calls[1].resolve({ id: "a" });
  await Promise.all([first, same]);
  assert.equal(state.contractDetail.id, "b");
  controller.destroy();
  state.destroy();
});

test("own movement needs actual geometry and remains available without public traffic", () => {
  const overlay = new OverlayData();
  const trip = {
    id: "t",
    vehicle_id: "v",
    departed_at: 0,
    arrives_at: 10,
    journey: {
      distance_km: 1,
      segments: [{ phase: "driving", starts_at: 0, ends_at: 10, start_km: 0, end_km: 1 }],
    },
    distance_km: 1,
    route_geojson: { type: "LineString", coordinates: [] },
  };
  const state = {
    vehicles: [{ id: "v", status: "enroute" }],
    transports: [trip],
    contracts: [],
    traffic: [],
  };
  overlay.update(state);
  assert.equal(overlay.vehicleFeatures(5).features.length, 0);
  assert.equal(focusCoordinates(state, new URL("http://game/transports/t"), 5, null, "", []), null);
  assert.equal(focusCoordinates(state, new URL("http://game/fleet/v"), 5, null, "", []), null);
  trip.route_geojson.coordinates = geometry.coordinates;
  overlay.update(state);
  assert.equal(overlay.vehicleFeatures(5).features.length, 1);
  assert.ok(focusCoordinates(state, new URL("http://game/transports/t"), 5, null, "", []).length);
  assert.equal(overlay.multiplayerVehicleFeatures(5).features.length, 0);
  overlay.update({ ...state, transports: [], traffic: [{ ...trip, is_own: true }] });
  assert.equal(overlay.vehicleFeatures(5).features.length, 0);
});
