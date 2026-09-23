import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { getVehicleAssets } from "./vehicle-assets.js";

const root = new URL("../", import.meta.url);
const inventory = JSON.parse(readFileSync(new URL("assets/inventory.json", root), "utf8")).files;

test("inventory preserves every SVG and its independently captured content", () => {
  const shipped = readdirSync(new URL("assets/", root), { recursive: true })
    .filter((path) => String(path).endsWith(".svg"))
    .map((path) => "assets/" + String(path).replaceAll("\\", "/"));
  assert.equal(inventory.length, 134);
  assert.deepEqual(new Set(shipped), new Set(inventory.map((entry) => entry.target_path)));
  for (const entry of inventory) {
    assert.equal(
      createHash("sha256")
        .update(readFileSync(new URL(entry.target_path, root)))
        .digest("hex"),
      entry.sha256,
      entry.target_path,
    );
  }
});

test("all 14 models retain the exact captured map, front and side selection", () => {
  const active = inventory.filter((entry) => entry.usage !== "reference");
  assert.equal(active.length, 42);
  assert.equal(new Set(active.map((entry) => entry.model_id)).size, 14);
  for (const entry of active) {
    const selected = getVehicleAssets(entry.model_id)[entry.usage];
    assert.equal(selected, "/" + entry.target_path);
  }
  assert.equal(getVehicleAssets("unknown"), null);
  assert.equal(getVehicleAssets(undefined), null);
});

test("model assets are immutable and unknown or absent identities have no mapping", () => {
  for (const modelId of [undefined, null, "", "missing", "constructor", "__proto__"]) {
    assert.equal(getVehicleAssets(modelId), null);
  }
  const assets = getVehicleAssets("iveco_sway_500");
  assert.ok(Object.isFrozen(assets));
  assert.throws(() => {
    assets.front = "/other.svg";
  }, TypeError);
  assert.equal(getVehicleAssets("iveco_sway_500"), assets);
});
