import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { LayerStateController } from "./controllers/layer-state-controller.js";
import { layerPresets } from "./layer-presets.js";

test("layer overrides remain scoped to account and view", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key),
    setItem: (key, value) => values.set(key, value),
  };
  const map = { toggle() {}, setGrouping() {}, setPreset() {} };
  const layers = new LayerStateController({ userId: "id-one", storage, map });
  for (const name of Object.keys(layerPresets)) {
    layers.select(new URL("http://test/" + (name === "world" ? "" : name)));
    assert.deepEqual(layers.effective(), layerPresets[name]);
  }
  layers.select(new URL("http://test/fleet"));
  layers.set("routes", false);
  layers.setGrouping(false);
  const restored = new LayerStateController({ userId: "id-one", storage, map });
  restored.select(new URL("http://test/fleet"));
  assert.equal(restored.effective().routes, false);
  assert.equal(restored.grouping, false);
  restored.select(new URL("http://test/contracts"));
  restored.set("orders", false);
  restored.reset();
  assert.equal(restored.effective().orders, true);
  restored.select(new URL("http://test/fleet"));
  assert.equal(restored.effective().routes, false);
  const separate = new LayerStateController({ userId: "id-two", storage, map });
  assert.equal(separate.effective().routes, true);
  assert.equal(separate.grouping, true);
});
