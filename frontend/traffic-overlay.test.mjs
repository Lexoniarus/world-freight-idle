import test from "node:test";
import assert from "node:assert/strict";
import { OverlayData } from "./map/overlay-data.js";
import { focusCoordinates } from "./map/focus-targets.js";

function trafficTrip(overrides = {}) {
  return {
    id: "own",
    vehicle_id: "own-truck",
    model_id: "iveco_sway_500",
    model_name: "IVECO S-Way 500 XC13",
    username: "Alice",
    player_color: "#e45756",
    is_own: true,
    journey: {
      distance_km: 100,
      segments: [
        {
          phase: "driving",
          starts_at: 0,
          ends_at: 10,
          start_km: 0,
          end_km: 100,
        },
      ],
    },
    departed_at: 0,
    arrives_at: 10,
    route_geojson: {
      type: "LineString",
      coordinates: [
        [0, 0],
        [1, 0],
      ],
    },
    ...overrides,
  };
}

test("traffic projection separates own and public vehicles", () => {
  const ownTrip = trafficTrip();
  const otherTrip = trafficTrip({
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
  });
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
  const publicFeatures = overlays.multiplayerVehicleFeatures(5).features;
  assert.equal(ownFeatures.length, 1);
  assert.equal(publicFeatures.length, 1);
  assert.equal(ownFeatures[0].properties.username, "Alice");
  assert.equal(publicFeatures[0].properties.username, "Bob");
  assert.equal(ownFeatures[0].properties.modelName, "IVECO S-Way 500 XC13");
  assert.equal(publicFeatures[0].properties.modelName, "DAF XG+ 480 MX-13");
  assert.notEqual(ownFeatures[0].properties.iconImage, publicFeatures[0].properties.iconImage);
  assert.deepEqual(overlays.fleetCoordinates(5), [[0.5, 0]]);
  assert.equal(overlays.routeFeatures().features.length, 1);
});

test("unsupported public models keep their player-colored fallback", () => {
  const overlays = new OverlayData();
  overlays.update({
    vehicles: [],
    contracts: [],
    transports: [],
    traffic: [
      trafficTrip({
        id: "unknown",
        vehicle_id: "unknown-truck",
        model_id: "unsupported_model",
        model_name: "Unsupported vehicle",
        player_color: "#123456",
        is_own: false,
      }),
    ],
  });

  const feature = overlays.multiplayerVehicleFeatures(5).features[0];
  assert.equal(feature.properties.hasIcon, false);
  assert.equal(feature.properties.playerColor, "#123456");
});

test("own movement requires route geometry and not public traffic", () => {
  const trip = trafficTrip({
    id: "t",
    vehicle_id: "v",
    journey: {
      distance_km: 1,
      segments: [
        {
          phase: "driving",
          starts_at: 0,
          ends_at: 10,
          start_km: 0,
          end_km: 1,
        },
      ],
    },
    distance_km: 1,
    route_geojson: { type: "LineString", coordinates: [] },
  });
  const state = {
    vehicles: [{ id: "v", status: "enroute" }],
    transports: [trip],
    contracts: [],
    traffic: [],
  };
  const overlay = new OverlayData();
  overlay.update(state);
  assert.equal(overlay.vehicleFeatures(5).features.length, 0);
  assert.equal(focusCoordinates(state, new URL("http://game/transports/t"), 5, null, "", []), null);
  assert.equal(focusCoordinates(state, new URL("http://game/fleet/v"), 5, null, "", []), null);

  trip.route_geojson.coordinates = [
    [10, 50],
    [11, 51],
  ];
  overlay.update(state);
  assert.equal(overlay.vehicleFeatures(5).features.length, 1);
  assert.ok(focusCoordinates(state, new URL("http://game/transports/t"), 5, null, "", []).length);
  assert.equal(overlay.multiplayerVehicleFeatures(5).features.length, 0);

  overlay.update({ ...state, transports: [], traffic: [{ ...trip, is_own: true }] });
  assert.equal(overlay.vehicleFeatures(5).features.length, 0);
});
