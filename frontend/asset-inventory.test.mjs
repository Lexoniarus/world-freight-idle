import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { vehicleCardAssetPaths } from "./vehicle-card-assets.js";
import { vehicleAssetPath } from "./map/vehicle-assets.js";

const root = new URL("../", import.meta.url);
const inventory = JSON.parse(readFileSync(new URL("assets/inventory.json", root), "utf8")).files;

test("inventory preserves every SVG and its independently captured content", () => {
  const shipped = readdirSync(new URL("assets/", root), { recursive: true })
    .filter((path) => String(path).endsWith(".svg"))
    .map((path) => "assets/" + String(path).replaceAll("\\", "/"));
  assert.equal(inventory.length, 134);
  assert.deepEqual(new Set(shipped), new Set(inventory.map((entry) => entry.original_path)));
  for (const entry of inventory) {
    assert.equal(
      createHash("sha256")
        .update(readFileSync(new URL(entry.original_path, root)))
        .digest("hex"),
      entry.sha256,
      entry.original_path,
    );
  }
});

test("all 14 models retain the exact captured map, front and side selection", () => {
  const active = inventory.filter((entry) => entry.usage !== "reference");
  assert.equal(active.length, 42);
  assert.equal(new Set(active.map((entry) => entry.model_id)).size, 14);
  for (const entry of active) {
    const selected =
      entry.usage === "map"
        ? vehicleAssetPath(entry.model_id)
        : vehicleCardAssetPaths(entry.model_id)[entry.usage];
    assert.equal(selected, "/" + entry.original_path);
  }
  assert.equal(vehicleCardAssetPaths("unknown"), null);
  assert.equal(vehicleAssetPath(undefined), null);
});
