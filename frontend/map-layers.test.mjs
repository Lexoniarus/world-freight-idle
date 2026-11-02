import test from "node:test";
import assert from "node:assert/strict";
import { addOverlayLayers } from "./map/overlay-layers.js";

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

test("own and public vehicles use independent map sources", () => {
  const sources = [];
  const layers = [];
  const map = {
    addSource: (id) => sources.push(id),
    addLayer: (layer) => layers.push(layer),
    getLayer: (id) => ({
      serialize: () => structuredClone(layers.find((layer) => layer.id === id)),
    }),
    setFilter: (id, filter) => {
      layers.find((layer) => layer.id === id).filter = filter;
    },
  };

  addOverlayLayers(map);

  assert.equal(sources.includes("vehicles"), true);
  assert.equal(sources.includes("multiplayer-vehicles"), true);
  assert.equal(
    layers.some((layer) => layer.id === "vehicle-owner-ring"),
    false,
  );
  assert.equal(layers.find((layer) => layer.id === "vehicles").source, "vehicles");
  assert.equal(
    layers.find((layer) => layer.id === "multiplayer-vehicles").source,
    "multiplayer-vehicles",
  );
});
