import test from "node:test";
import assert from "node:assert/strict";
import { MapSelectionController } from "./controllers/map-selection-controller.js";

test("map selection routes typed objects and releases its listener", () => {
  const map = new EventTarget();
  const visits = [];
  const notices = [];
  const controller = new MapSelectionController({
    map,
    navigate: (path) => visits.push(path),
    notify: (message, kind) => notices.push([message, kind]),
  });
  controller.start();
  for (const detail of [
    { kind: "own-vehicle", idle: true, vehicleId: "truck 1", transportId: "" },
    { kind: "facility", cityUid: "city 1", parked: false, vehicleId: "truck 1" },
    { kind: "public-vehicle", username: "Alex", modelName: "S-Way" },
  ])
    map.dispatchEvent(new CustomEvent("object-selected", { detail }));
  controller.destroy();
  map.dispatchEvent(
    new CustomEvent("object-selected", {
      detail: { kind: "facility", cityUid: "ignored", parked: true },
    }),
  );
  assert.deepEqual(visits, ["/fleet/truck%201", "/contracts?city=city%201&vehicle=truck%201"]);
  assert.deepEqual(notices, [["Alex · S-Way", "map"]]);
});
