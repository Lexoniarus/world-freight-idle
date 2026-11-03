import test from "node:test";
import assert from "node:assert/strict";
import { marketMapState } from "./market-context.js";

test("market map follows authoritative eligibility and idle selection", () => {
  const state = {
    vehicles: [
      { id: "one", status: "idle" },
      { id: "two", status: "idle" },
    ],
    contracts: [
      { id: "shared", eligible_vehicle_ids: ["one", "two"] },
      { id: "first", eligible_vehicle_ids: ["one"] },
      { id: "second", eligible_vehicle_ids: ["two"] },
    ],
  };
  const url = new URL("http://test/contracts?vehicle=two");
  assert.deepEqual(
    marketMapState(state, url).contracts.map((offer) => offer.id),
    ["shared", "second"],
  );
  assert.equal(marketMapState(state, url).marketVehicleId, "two");
  state.vehicles[1].status = "enroute";
  assert.deepEqual(marketMapState(state, url).contracts, []);
  assert.equal(marketMapState(state, new URL("http://test/")), state);
});
