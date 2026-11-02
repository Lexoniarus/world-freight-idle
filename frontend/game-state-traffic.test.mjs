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
