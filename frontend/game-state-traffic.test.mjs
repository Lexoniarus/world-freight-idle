import test from "node:test";
import assert from "node:assert/strict";
import { GameState } from "./state.js";

test("traffic failures preserve the last public snapshot and remain visible", async () => {
  let trafficFails = false;
  const requests = [];
  const state = new GameState(async (path) => {
    requests.push(path);
    if (path === "/runtime") {
      return {
        server_time: Date.now() / 1000,
        player: { cash: 1, completed: 0, reputation: 0 },
        transports: [],
        vehicles: [],
      };
    }
    if (path === "/fleet") return { vehicles: [] };
    if (path === "/contracts") return { contracts: [] };
    if (path === "/map/traffic?representation=summary") {
      if (trafficFails) throw new Error("map offline");
      return { transports: [{ id: "public-trip" }] };
    }
    throw new Error(`unexpected ${path}`);
  });

  await state.refresh();
  await state.refreshTraffic();
  assert.equal(state.data.traffic[0].id, "public-trip");
  assert.equal(state.data.trafficAvailable, true);
  assert.equal(requests.includes("/map/traffic?representation=summary"), true);

  trafficFails = true;
  await state.refresh();
  await state.refreshTraffic();
  assert.equal(state.data.traffic[0].id, "public-trip");
  assert.equal(state.data.trafficAvailable, false);
  state.destroy();
});

test("runtime publishes before traffic and shares the owner's route geometry", async () => {
  let releaseTraffic;
  let downloads = 0;
  let releaseGeometry;
  const geometry = {
    coordinates: [
      [10, 50],
      [11, 51],
    ],
    legs: [],
  };
  const shape = new Promise((resolve) => {
    releaseGeometry = resolve;
  });
  const traffic = new Promise((resolve) => {
    releaseTraffic = resolve;
  });
  const state = new GameState(async (path) => {
    if (path === "/runtime") {
      return {
        server_time: Date.now() / 1000,
        vehicles: [],
        transports: [{ id: "t", route_ref: "r" }],
      };
    }
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
