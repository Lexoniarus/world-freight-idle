import test from "node:test";
import assert from "node:assert/strict";
import {
  collectResolvedHubs,
  mergeOwnTraffic,
  synchronizeRoutePlans,
} from "./map/overlay-state.js";
import { hub, trip, vehicle } from "./test-support/controller-fixtures.mjs";

test("own transport details replace the matching public traffic row", () => {
  const other = { ...trip, id: "other", is_own: false };
  const state = mergeOwnTraffic(
    {
      vehicles: [vehicle],
      contracts: [],
      transports: [trip],
      traffic: [{ ...trip, is_own: true, username: "driver", player_color: "#111111" }, other],
    },
    "#222222",
  );

  assert.deepEqual(
    state.traffic.map((item) => item.id),
    ["other", trip.id],
  );
  assert.equal(state.traffic[1].model_id, vehicle.model_id);
  assert.equal(state.traffic[1].player_color, "#222222");
});

test("resolved hubs are distinct and invalid coordinates are excluded", () => {
  const invalid = { ...hub, id: "invalid", facility_uid: "invalid", lon: null };
  const hubs = collectResolvedHubs({
    vehicles: [vehicle],
    contracts: [{ origin: hub, destination: invalid }],
    transports: [],
  });

  assert.deepEqual(
    hubs.map((item) => item.facility_uid),
    [hub.facility_uid],
  );
});

test("route synchronization removes stale plans and reuses private plans", () => {
  const privatePlans = new Map();
  synchronizeRoutePlans(privatePlans, [trip]);
  const privatePlan = privatePlans.get(trip.id);
  privatePlans.set("stale", privatePlan);

  synchronizeRoutePlans(privatePlans, [trip]);
  assert.equal(privatePlans.has("stale"), false);

  const trafficPlans = new Map();
  synchronizeRoutePlans(trafficPlans, [{ ...trip, is_own: true }], privatePlans);
  assert.equal(trafficPlans.get(trip.id), privatePlan);
});
