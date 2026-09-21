import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { GameApiClient } from "./api.js";
import { bearingBetween, prepareRoute, routePose } from "./geometry.js";
import { GameState } from "./state.js";
import { addOverlayLayers } from "./map/layers.js";
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

test("vehicle asset registry maps distinct models and player colors to distinct images", () => {
  assert.equal(vehicleAssetPath("iveco_sway_500"), "/assets/iveco_s_way_500_xc13_map.svg");
  assert.equal(vehicleAssetPath("daf_xg_plus_480"), "/assets/daf_xg_plus_480_map.svg");
  assert.notEqual(vehicleAssetPath("iveco_sway_500"), vehicleAssetPath("daf_xg_plus_480"));
  assert.equal(vehicleIconId("iveco_sway_500", "#E45756"), "vehicle-iveco_sway_500-e45756");
  assert.equal(vehicleIconId("daf_xg_plus_480", "#E45756"), "vehicle-daf_xg_plus_480-e45756");
  assert.equal(normalizeVehicleColor("red"), DEFAULT_VEHICLE_COLOR);
  assert.equal(vehicleAssetPath("iveco_daily_35s18"), "/assets/iveco_daily_35s18_map.svg");
  assert.equal(vehicleIconId("iveco_daily_35s18", "#123456"), "vehicle-iveco_daily_35s18-123456");
});

test("all catalogue vehicle models resolve to shipped map assets", () => {
  const modelIds = [
    "daf_xg_plus_480",
    "iveco_sway_500",
    "man_tgx_520",
    "mercedes_actros_l_380",
    "mercedes_eactros_600",
    "renault_t_high_520",
    "scania_r460_gas",
    "volvo_fh_aero_500_isave",
    "mercedes_sprinter_317_cdi",
    "vw_crafter_35_130kw",
    "iveco_daily_35s18",
    "mercedes_atego_818_l",
    "mercedes_atego_1224_l",
    "man_tgl_12_250",
  ];
  for (const modelId of modelIds) {
    const path = vehicleAssetPath(modelId);
    assert.ok(path, modelId);
    assert.equal(existsSync(new URL(`..${path}`, import.meta.url)), true, path);
  }
});

test("vehicle svg color replacement validates the requested paint", () => {
  const source = '<svg style="--vehicle-color:#ffffff"></svg>';
  assert.match(colorizeVehicleSvg(source, "#123abc"), /--vehicle-color:#123abc/);
  assert.match(colorizeVehicleSvg(source, "red"), new RegExp(DEFAULT_VEHICLE_COLOR));
});

test("shipped map assets expose the recolorable vehicle paint variable", () => {
  const iveco = readFileSync(
    new URL("../assets/iveco_s_way_500_xc13_map.svg", import.meta.url),
    "utf8",
  );
  const daf = readFileSync(new URL("../assets/daf_xg_plus_480_map.svg", import.meta.url), "utf8");
  assert.match(iveco, /--vehicle-color:#ffffff/i);
  assert.match(colorizeVehicleSvg(iveco, "#2fda6a"), /--vehicle-color:#2fda6a/i);
  assert.notEqual(iveco, daf);
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
    { model_id: "iveco_sway_500", player_color: "#e45756" },
    { model_id: "iveco_sway_500", player_color: "#4c78a8" },
    { model_id: "iveco_daily_35s18", player_color: "#123456" },
  ]);
  assert.equal(loads, 2);
  assert.equal(registered.size, 3);
  assert.equal(images.has("vehicle-iveco_sway_500-e45756"), true);
  assert.equal(images.has("vehicle-iveco_sway_500-4c78a8"), true);
  assert.equal(images.has("vehicle-iveco_daily_35s18-123456"), true);
});

test("shared traffic projects players, model names and private route lines separately", () => {
  const ownTrip = {
    id: "own",
    vehicle_id: "own-truck",
    model_id: "iveco_sway_500",
    model_name: "IVECO S-Way 500 XC13",
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
    model_id: "daf_xg_plus_480",
    model_name: "DAF XG+ 480 MX-13",
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
    new Set(["vehicle-iveco_sway_500-e45756", "vehicle-daf_xg_plus_480-4c78a8"]),
  );
  overlays.update({
    vehicles: [],
    contracts: [],
    transports: [{ ...ownTrip, origin: {}, destination: {} }],
    traffic: [ownTrip, otherTrip],
  });
  const ownFeatures = overlays.vehicleFeatures(5).features;
  const multiplayerFeatures = overlays.multiplayerVehicleFeatures(5).features;
  assert.equal(ownFeatures.length, 1);
  assert.equal(multiplayerFeatures.length, 1);
  assert.equal(ownFeatures[0].properties.username, "Alice");
  assert.equal(multiplayerFeatures[0].properties.username, "Bob");
  assert.equal(ownFeatures[0].properties.modelName, "IVECO S-Way 500 XC13");
  assert.equal(multiplayerFeatures[0].properties.modelName, "DAF XG+ 480 MX-13");
  assert.notEqual(ownFeatures[0].properties.iconImage, multiplayerFeatures[0].properties.iconImage);
  assert.equal(ownFeatures[0].properties.playerColor, "#e45756");
  assert.equal(multiplayerFeatures[0].properties.playerColor, "#4c78a8");
  assert.equal(ownFeatures[0].properties.hasIcon, true);
  assert.equal(multiplayerFeatures[0].properties.hasIcon, true);
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
        id: "unknown",
        vehicle_id: "unknown-truck",
        model_id: "unsupported_model",
        model_name: "Unsupported vehicle",
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

test("game snapshots expose shared traffic failures instead of silently hiding them", async () => {
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
  assert.equal(state.data.trafficAvailable, true);
  assert.equal(requests.includes("/map/traffic"), true);
  trafficFails = true;
  await state.refresh();
  assert.deepEqual(state.data.traffic, [{ id: "public-trip" }]);
  assert.equal(state.data.trafficAvailable, false);
  state.destroy();
});

test("own and multiplayer vehicles use independent sources without decorative rings", () => {
  const sources = [];
  const layers = [];
  const map = {
    addSource: (id) => sources.push(id),
    addLayer: (layer) => layers.push(layer),
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
