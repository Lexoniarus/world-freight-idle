import test from "node:test";
import assert from "node:assert/strict";
import { GameApiClient } from "./api.js";
import { bearingBetween, prepareRoute, routePose } from "./geometry.js";
import { OverlayData } from "./map/overlay-data.js";
import {
  DEFAULT_VEHICLE_COLOR,
  colorizeVehicleSvg,
  rasterizeVehicleSvg,
  registerVehicleIcons,
  vehicleAssetPath,
  vehicleIconId,
} from "./map/vehicle-assets.js";

test("vehicle bearings follow compass orientation and route interpolation", () => {
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

test("vehicle asset registry maps catalogue model ids and preserves a fallback", () => {
  assert.equal(vehicleAssetPath("iveco_sway_500"), "/assets/iveco_s_way_500_xc13_map.svg");
  assert.equal(vehicleIconId("iveco_sway_500"), "vehicle-iveco_sway_500");
  assert.equal(vehicleAssetPath("iveco_daily_35s18"), null);
  assert.equal(vehicleIconId("iveco_daily_35s18"), "");
});

test("vehicle svg color replacement validates the requested paint", () => {
  const source = '<svg style="--vehicle-color:#ffffff"></svg>';
  assert.match(colorizeVehicleSvg(source, "#123abc"), /--vehicle-color:#123abc/);
  assert.match(colorizeVehicleSvg(source, "red"), new RegExp(DEFAULT_VEHICLE_COLOR));
});

test("vehicle svg rasterizer scales the atlas image and releases its blob url", async () => {
  const image = { naturalWidth: 50, naturalHeight: 100, decode: async () => {} };
  let revoked = "";
  const canvas = {
    width: 0,
    height: 0,
    getContext: () => ({
      clearRect() {},
      drawImage() {},
      getImageData: (_x, _y, width, height) => ({ width, height, data: new Uint8ClampedArray(4) }),
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

test("vehicle icon registration records only successfully loaded map sprites", async () => {
  const images = new Map();
  const map = {
    hasImage: (id) => images.has(id),
    addImage: (id, image) => images.set(id, image),
  };
  const registered = await registerVehicleIcons(
    map,
    async (path) => {
      if (path.includes("scania")) throw new Error("missing");
      return '<svg style="--vehicle-color:#ffffff"></svg>';
    },
    { rasterize: async () => ({ width: 1, height: 1, data: new Uint8ClampedArray(4) }) },
  );
  assert.equal(registered.has("iveco_sway_500"), true);
  assert.equal(registered.has("scania_r460_gas"), false);
  assert.equal(images.has("vehicle-iveco_sway_500"), true);
});

test("moving transport features use the owned model sprite and heading or fallback", () => {
  const trip = {
    id: "trip",
    vehicle_id: "truck",
    departed_at: 0,
    arrives_at: 10,
    route_geojson: {
      type: "LineString",
      coordinates: [
        [0, 0],
        [1, 0],
      ],
    },
    origin: {},
    destination: {},
  };
  const overlays = new OverlayData();
  overlays.setVehicleModels(new Set(["iveco_sway_500"]));
  overlays.update({
    vehicles: [{ id: "truck", model_id: "iveco_sway_500" }],
    contracts: [],
    transports: [trip],
  });
  const feature = overlays.vehicleFeatures(5).features[0];
  assert.equal(feature.properties.hasIcon, true);
  assert.equal(feature.properties.iconImage, "vehicle-iveco_sway_500");
  assert.ok(Math.abs(feature.properties.bearing - 90) < 1e-6);
  overlays.update({
    vehicles: [{ id: "truck", model_id: "iveco_daily_35s18" }],
    contracts: [],
    transports: [trip],
  });
  assert.equal(overlays.vehicleFeatures(5).features[0].properties.hasIcon, false);
});

test("asset requests remain same-origin and outside the versioned JSON API", async () => {
  let requested = "";
  const api = new GameApiClient(async (url) => {
    requested = String(url);
    return new Response("<svg/>", { status: 200 });
  });
  assert.equal(await api.requestAsset("/assets/test.svg"), "<svg/>");
  assert.equal(requested, "/assets/test.svg");
  await assert.rejects(api.requestAsset("/other/test.svg"), /Expected \/assets\//);
  api.destroy();
});
