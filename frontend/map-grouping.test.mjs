import test from "node:test";
import assert from "node:assert/strict";
import { nearestLongitude } from "./geometry.js";
import { groupVehicles } from "./map/grouping.js";
import {
  footprintsOverlap,
  spriteBounds,
  vehicleFootprint,
  vehicleIconScale,
} from "./map/vehicle-footprint.js";

const point = (key, x, own = true) => ({
  geometry: { coordinates: [x, 0] },
  properties: { key, id: key, isOwn: own },
});

test("screen grouping preserves identity, selection and input coordinates", () => {
  const features = [point("a", 0), point("b", 0), point("c", 1, false)];
  const original = JSON.stringify(features);
  const project = ([x, y]) => ({ x, y });
  assert.equal(groupVehicles(features, project).length, 2);
  assert.equal(groupVehicles(features, project, "a").length, 3);
  assert.equal(groupVehicles(features, project, "", false).length, 3);
  assert.equal(
    groupVehicles([point("a", 0), point("b", 10)], ([x, y]) => ({ x: x * 100, y })).length,
    2,
  );
  assert.equal(JSON.stringify(features), original);
});

test("wrapped grouping counts each owner identity once", () => {
  const features = [
    point("own", 179.9),
    {
      geometry: { coordinates: [-180.1, 0] },
      properties: {
        key: "other-a",
        vehicleId: "truck_01",
        isOwn: false,
      },
    },
    {
      geometry: { coordinates: [179.9, 0] },
      properties: {
        key: "other-b",
        vehicleId: "other",
        isOwn: false,
      },
    },
  ];
  features[0].properties.vehicleId = "truck_01";
  const groups = groupVehicles(
    features,
    ([lon, lat]) => ({ x: nearestLongitude(lon, 180), y: lat }),
    "truck_01",
  );
  assert.deepEqual(groups.map((group) => group.members.length).sort(), [1, 2]);
  assert.equal(groups.flatMap((group) => group.members).length, 3);
  assert.equal(features[1].geometry.coordinates[0], -180.1);
});

test("groups never mix movement state or owner and ignore input order", () => {
  const feature = (id, idle, owner = "own") => ({
    geometry: { coordinates: [0, 0] },
    properties: {
      key: `${owner}:${id}`,
      id,
      vehicleId: id,
      isOwn: owner === "own",
      username: owner,
      idle,
      movementState: idle ? "idle" : "enroute",
    },
  });
  const features = [
    feature("b", true),
    feature("a", true),
    feature("d", false),
    feature("c", false),
    feature("e", false, "Alice"),
    feature("f", false, "Bob"),
  ];
  const project = ([x, y]) => ({ x, y });
  const groups = groupVehicles(features, project);
  assert.deepEqual(
    groups.map((group) => group.members.map((item) => item.properties.key)),
    groupVehicles([...features].reverse(), project).map((group) =>
      group.members.map((item) => item.properties.key),
    ),
  );
  for (const group of groups) {
    assert.equal(new Set(group.members.map((item) => item.properties.movementState)).size, 1);
    assert.equal(new Set(group.members.map((item) => item.properties.username)).size, 1);
  }
});

test("rendered footprints determine grouping at every zoom", () => {
  const truck = {
    geometry: { coordinates: [0, 0] },
    properties: {
      key: "own:a",
      id: "a",
      vehicleId: "a",
      isOwn: true,
      idle: false,
      movementState: "enroute",
      hasIcon: true,
      iconBounds: [-4, -32, 4, 32],
      bearing: 0,
    },
  };
  const other = structuredClone(truck);
  other.properties.key = "own:b";
  other.properties.id = "b";
  other.geometry.coordinates = [12, 0];
  const project = ([x, y]) => ({ x, y });
  assert.equal(groupVehicles([truck, other], project, "", true, 17).length, 2);
  other.geometry.coordinates = [6, 0];
  assert.equal(groupVehicles([truck, other], project, "", true, 17).length, 1);
  assert.equal(groupVehicles([truck, other], project, "", true, 5).length, 2);
  other.geometry.coordinates = [0, 20];
  assert.equal(groupVehicles([truck, other], project, "", true, 5).length, 1);
  truck.properties.bearing = other.properties.bearing = 90;
  assert.equal(groupVehicles([truck, other], project, "", true, 17).length, 2);
  const rotated = vehicleFootprint(truck, { x: 0, y: 0 }, 13, 90);
  assert.ok(
    footprintsOverlap(
      rotated,
      vehicleFootprint(
        { ...truck, properties: { ...truck.properties, bearing: 0 } },
        { x: 0, y: 20 },
        13,
        0,
      ),
    ),
  );
  const pixels = new Uint8ClampedArray(4 * 4 * 4);
  pixels[(1 * 4 + 2) * 4 + 3] = 255;
  assert.deepEqual(spriteBounds({ width: 4, height: 4, data: pixels }), [0, -0.5, 0.5, 0]);
  assert.deepEqual(
    spriteBounds({ width: 4, height: 4, data: new Uint8ClampedArray(64) }),
    [0, 0, 0, 0],
  );
  assert.equal(vehicleIconScale(1), 0.55);
  assert.equal(vehicleIconScale(20), 1.15);
});
