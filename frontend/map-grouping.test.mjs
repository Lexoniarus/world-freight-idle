import test from "node:test";
import assert from "node:assert/strict";
import { nearestLongitude } from "./geometry.js";
import { groupVehicles } from "./map/grouping.js";

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
