import test from "node:test";
import assert from "node:assert/strict";
import {
  bearingBetween,
  eligibleVehicles,
  matchesFacility,
  nearestLongitude,
  prepareRoute,
  routePose,
  routePosition,
} from "./geometry.js";
import { contract, hub, vehicle } from "./test-support/controller-fixtures.mjs";

test("facility matching accepts stable IDs and explicit legacy aliases", () => {
  const facility = {
    ...hub,
    id: "facility-uuid",
    facility_uid: "facility-uuid",
    aliases: ["berlin"],
  };
  assert.equal(matchesFacility(facility, "berlin"), true);
  assert.equal(matchesFacility(facility, facility.facility_uid), true);
  assert.equal(matchesFacility(facility, "unknown"), false);
  const owned = {
    ...vehicle,
    facility_uid: facility.facility_uid,
    hub_id: facility.id,
    hub: facility,
    location_snapshot: facility,
  };
  const job = {
    ...contract,
    origin_facility_uid: facility.facility_uid,
    origin_hub_id: facility.id,
    origin: facility,
  };
  assert.deepEqual(eligibleVehicles([owned], job), [owned]);
});

test("route poses use compass bearings and distance interpolation", () => {
  assert.ok(Math.abs(bearingBetween([0, 0], [0, 1]) - 0) < 1e-6);
  assert.ok(Math.abs(bearingBetween([0, 0], [1, 0]) - 90) < 1e-6);
  assert.ok(Math.abs(bearingBetween([0, 0], [0, -1]) - 180) < 1e-6);
  assert.ok(Math.abs(bearingBetween([0, 0], [-1, 0]) - 270) < 1e-6);
  const pose = routePose(
    prepareRoute([
      [0, 0],
      [2, 0],
    ]),
    0.5,
  );
  assert.ok(Math.abs(pose.coordinate[0] - 1) < 1e-6);
  assert.ok(Math.abs(pose.bearing - 90) < 1e-6);
  assert.equal(routePose(prepareRoute([]), 0.5), null);
});

test("antimeridian routes stay on the nearest continuous world copy", () => {
  const route = prepareRoute([
    [179, 0],
    [-179, 0],
  ]);
  assert.deepEqual(route.points, [
    [179, 0],
    [181, 0],
  ]);
  assert.deepEqual(routePosition(route, 0.5), [180, 0]);
  assert.equal(nearestLongitude(-179, 540), 541);
  assert.deepEqual(routePosition(route, 2), [181, 0]);
  assert.deepEqual(routePosition(route, -1), [179, 0]);
});

test("route interpolation uses distance and handles empty or stationary routes", () => {
  const route = prepareRoute([
    [0, 0],
    [1, 0],
    [4, 0],
  ]);
  assert.ok(Math.abs(routePosition(route, 0.5)[0] - 2) < 1e-6);
  assert.equal(routePosition(prepareRoute([]), 0.5), null);
  assert.deepEqual(
    routePosition(
      prepareRoute([
        [1, 2],
        [1, 2],
      ]),
      0.5,
    ),
    [1, 2],
  );
});

test("dispatch choices trust server eligibility instead of duplicating rules", () => {
  const base = {
    id: "valid",
    hub_id: "berlin",
    capacity_tons: 24,
    mode: "truck",
    status: "idle",
  };
  const fleet = [
    base,
    { ...base, id: "busy", status: "enroute" },
    { ...base, id: "small", capacity_tons: 2 },
    { ...base, id: "elsewhere", hub_id: "hamburg" },
    { ...base, id: "rail", mode: "rail" },
  ];
  assert.deepEqual(
    eligibleVehicles(fleet, { eligible_vehicle_ids: ["valid"] }).map((item) => item.id),
    ["valid"],
  );
});
