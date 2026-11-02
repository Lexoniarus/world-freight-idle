import test from "node:test";
import assert from "node:assert/strict";
import { addOverlayLayers } from "./map/layers.js";

test("moving icons rotate with the map while idle icons remain upright", () => {
  const layers = new Map();
  addOverlayLayers({
    addSource() {},
    addLayer: (layer) => layers.set(layer.id, layer),
    getLayer: (id) => ({ serialize: () => structuredClone(layers.get(id)) }),
    setFilter: (id, filter) => (layers.get(id).filter = filter),
  });
  for (const id of ["vehicles", "multiplayer-vehicles", "selected-vehicle-assets"]) {
    assert.deepEqual(layers.get(id).layout["icon-rotate"], ["get", "bearing"]);
    assert.equal(layers.get(id).layout["icon-rotation-alignment"], "map");
    assert.equal(layers.get(id + "-idle").layout["icon-rotate"], 0);
    assert.equal(layers.get(id + "-idle").layout["icon-rotation-alignment"], "viewport");
  }
});
