import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { GameApiClient } from "./api.js";
import { bearingBetween, prepareRoute, routePose } from "./geometry.js";
import { GameState } from "./state.js";
import { OverlayData } from "./map/overlay-data.js";
import {
  DEFAULT_VEHICLE_COLOR,
  VehicleIconRegistry,
  colorizeVehicleSvg,
  normalizeVehicleColor,
  rasterizeVehicleSvg,
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

test("vehicle asset registry maps model and player color to one image id", () => {
  assert.equal(vehicleAssetPath("iveco_sway_500"), "/assets/iveco_s_way_500_xc13_map.svg");
  assert.equal(vehicleIconId("iveco_sway_500", "#E45756"), "vehicle-iveco_sway_500-e45756");
  assert.equal(normalizeVehicleColor("red"), DEFAULT_VEHICLE_COLOR);
  assert.equal(vehicleAssetPath("iveco_daily_35s18"), null);
  assert.equal(vehicleIconId("iveco_daily_35s18", "#123456"), "");
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

test("colored vehicle icon registry reuses one SVG source across player colors", async () => {
  const images = new Map();
  let loads = 0;
  const map = {
    hasImage: (id) => images.has(id),
    addImage: (id, image) => images.set(id, image),
  };
  const registry = new VehicleIconRegistry(
    map,
    async () => {
      loads++;
      return '<svg style="--vehicle-color:#ffffff"></svg>';
    },
    {
      rasterize: async () => ({
        width: 1,
        height: 1,
        data: new Uint8ClampedArray(4),
      }),
    },
  );
  const registered = await registry.ensure([
    {
      model_id: "iveco_sway_500",
      player_color: "#e45756",
    },
    {
      model_id: "iveco_sway_500",
      player_color: "#4c78a8",
    },
    {
      model_id: "iveco_daily_35s18",
      player_color: "#123456",
    },
  ]);
  assert.equal(loads, 1);
  assert.equal(registered.size, 2);
  assert.equal(images.has("vehicle-iveco_sway_500-e45756"), true);
  assert.equal(images.has("vehicle-iveco_sway_500-4c78a8"), true);
});

test("shared traffic projects both players while private route lines stay private", () => {
  const ownTrip = {
    id: "own",
    vehicle_id: "own-truck",
    model_id: "iveco_sway_500",
    username: "Alice",
    player_color: "#e45756",
    is_own: true,
    departed_at: 0,
    arrives_at: 10,
    route_geojson: {
      type: "LineString",
      coordinates: [
        [0, 0],
        [1, 0],
      ],
    },
  };
  const otherTrip = {
    ...ownTrip,
    id: "other",
    vehicle_id: "other-truck",
    username: "Bob",
    player_color: "#4c78a8",
    is_own: false,
    route_geojson: {
      type: "LineString",
      coordinates: [
        [0, 1],
        [1, 1],
      ],
    },
  };
  const overlays = new OverlayData();
  overlays.setVehicleIcons(
    new Set(["vehicle-iveco_sway_500-e45756", "vehicle-iveco_sway_500-4c78a8"]),
  );
  overlays.update({
    vehicles: [],
    contracts: [],
    transports: [
      {
        ...ownTrip,
        origin: {},
        destination: {},
      },
    ],
    traffic: [ownTrip, otherTrip],
  });
  const features = overlays.vehicleFeatures(5).features;
  assert.equal(features.length, 2);
  assert.equal(features[0].properties.username, "Alice");
  assert.equal(features[1].properties.username, "Bob");
  assert.equal(features[0].properties.playerColor, "#e45756");
  assert.equal(features[1].properties.playerColor, "#4c78a8");
  assert.equal(features[0].properties.hasIcon, true);
  assert.equal(features[1].properties.hasIcon, true);
  assert.equal(overlays.routeFeatures().features.length, 1);
  assert.deepEqual(overlays.fleetCoordinates(5), [[0.5, 0]]);
});

test("unsupported public vehicle models keep the player-colored fallback", () => {
  const overlays = new OverlayData();
  overlays.update({
    vehicles: [],
    contracts: [],
    transports: [],
    traffic: [
      {
        id: "daily",
        vehicle_id: "daily-truck",
        model_id: "iveco_daily_35s18",
        username: "Alice",
        player_color: "#123456",
        is_own: true,
        departed_at: 0,
        arrives_at: 10,
        route_geojson: {
          type: "LineString",
          coordinates: [
            [0, 0],
            [1, 0],
          ],
        },
      },
    ],
  });
  const feature = overlays.vehicleFeatures(5).features[0];
  assert.equal(feature.properties.hasIcon, false);
  assert.equal(feature.properties.playerColor, "#123456");
});

test("game snapshots load shared traffic and preserve it on a map-only failure", async () => {
  let trafficFails = false;
  const requests = [];
  const state = new GameState(async (path) => {
    requests.push(path);
    if (path === "/dashboard")
      return {
        server_time: Date.now() / 1000,
        player: { cash: 1, completed: 0, reputation: 0 },
        transports: [],
      };
    if (path === "/fleet") return { vehicles: [] };
    if (path === "/contracts") return { contracts: [] };
    if (path === "/map/traffic") {
      if (trafficFails) throw new Error("map offline");
      return { transports: [{ id: "public-trip" }] };
    }
    throw new Error(`unexpected ${path}`);
  });
  await state.refresh();
  assert.deepEqual(state.data.traffic, [{ id: "public-trip" }]);
  assert.equal(requests.includes("/map/traffic"), true);
  trafficFails = true;
  await state.refresh();
  assert.deepEqual(state.data.traffic, [{ id: "public-trip" }]);
  state.destroy();
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
