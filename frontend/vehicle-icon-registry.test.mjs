import test from "node:test";
import assert from "node:assert/strict";
import { VehicleColorAssets } from "./vehicle-color-assets.js";
import {
  DEFAULT_VEHICLE_COLOR,
  normalizeVehicleColor,
  VehicleIconRegistry,
  rasterizeVehicleSvg,
  vehicleIconId,
} from "./map/vehicle-icon-registry.js";

test("vehicle icon identities use normalized paint values", () => {
  assert.equal(normalizeVehicleColor("#123ABC"), "#123abc");
  assert.equal(normalizeVehicleColor("red"), DEFAULT_VEHICLE_COLOR);
  assert.equal(vehicleIconId("iveco_sway_500", "#E45756"), "vehicle-iveco_sway_500-e45756");
});

test("vehicle icon rasterization releases its temporary blob URL", async () => {
  const image = { naturalWidth: 50, naturalHeight: 100, decode: async () => {} };
  let revoked = "";
  const canvas = {
    width: 0,
    height: 0,
    getContext: () => ({
      clearRect() {},
      drawImage() {},
      getImageData: (_x, _y, width, height) => ({
        width,
        height,
        data: new Uint8ClampedArray(4),
      }),
    }),
  };

  const result = await rasterizeVehicleSvg("<svg/>", {
    height: 120,
    imageFactory: () => image,
    canvasFactory: () => canvas,
    createObjectURL: () => "blob:test",
    revokeObjectURL: (url) => {
      revoked = url;
    },
  });

  assert.equal(canvas.width, 60);
  assert.equal(canvas.height, 120);
  assert.equal(result.width, 60);
  assert.equal(revoked, "blob:test");
});

test("vehicle icon registry reuses sources across player colors", async () => {
  const images = new Map();
  let loads = 0;
  const map = {
    hasImage: (id) => images.has(id),
    addImage: (id, image) => images.set(id, image),
  };
  const assets = new VehicleColorAssets(
    async () => {
      loads++;
      return "<svg/>";
    },
    async (_base, _mask, color) => `<svg style="--vehicle-color:${color}"/>`,
  );
  const registry = new VehicleIconRegistry(map, async () => "<svg/>", {
    coloredSource: assets.source.bind(assets),
    rasterize: async () => ({
      width: 1,
      height: 1,
      data: new Uint8ClampedArray(4),
    }),
  });

  const registered = await registry.ensure([
    { model_id: "iveco_sway_500", player_color: "#e45756" },
    { model_id: "iveco_sway_500", player_color: "#4c78a8" },
    { model_id: "iveco_daily_35s18", player_color: "#123456" },
  ]);

  assert.equal(loads, 4);
  assert.equal(registered.size, 3);
  assert.equal(images.has("vehicle-iveco_sway_500-e45756"), true);
  assert.equal(images.has("vehicle-iveco_sway_500-4c78a8"), true);
  assert.equal(images.has("vehicle-iveco_daily_35s18-123456"), true);
  assets.destroy();
});
