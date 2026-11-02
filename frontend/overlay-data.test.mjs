import test from "node:test";
import assert from "node:assert/strict";
import { OverlayData, previewFeatures } from "./map/overlay-data.js";
import { vehicleIconId } from "./map/vehicle-assets.js";
import { contract, hub, quote, trip, vehicle } from "./test-support/controller-fixtures.mjs";

test("overlay projections discard invalid hubs and release settled routes", () => {
  const data = new OverlayData();
  const unavailable = {
    ...hub,
    id: "missing",
    facility_uid: "missing",
    resolution_status: "unavailable",
    lon: null,
  };
  data.update({
    vehicles: [vehicle],
    contracts: [
      contract,
      { ...contract, id: "another", origin_hub_id: unavailable.id, origin: unavailable },
    ],
    transports: [trip],
    traffic: [
      {
        id: trip.id,
        vehicle_id: trip.vehicle_id,
        model_id: "iveco_sway_500",
        username: "driver",
        player_color: "#123456",
        is_own: true,
        journey: trip.journey,
        departed_at: trip.departed_at,
        arrives_at: trip.arrives_at,
        route_geojson: trip.route_geojson,
      },
    ],
  });
  assert.equal(data.hubFeatures().features.length, 1);
  assert.deepEqual(data.vehicleFeatures(50).features[0].geometry.coordinates, [180, 0]);
  assert.equal(data.fleetCoordinates(50).length, 1);
  assert.equal(previewFeatures(quote).features.length, 1);
  data.update({ ...data.state, transports: [], traffic: [] });
  assert.equal(data.routes.size, 0);
  assert.equal(data.trafficRoutes.size, 0);
});

test("idle vehicle projection uses the company color without hiding its city", () => {
  const data = new OverlayData();
  const model = "iveco_sway_500";
  const companyColor = "#e45756";
  const facility = {
    id: "a",
    city_uid: "city",
    resolution_status: "resolved",
    lon: 13,
    lat: 52,
  };
  data.companyColor = companyColor;
  data.update({
    vehicles: [
      {
        id: "v",
        model_id: model,
        status: "idle",
        hub: facility,
        hub_id: facility.id,
      },
    ],
    contracts: [
      {
        origin: facility,
        destination: facility,
        origin_hub_id: facility.id,
      },
    ],
    transports: [],
    traffic: [],
  });
  const icon = vehicleIconId(model, companyColor, "front");
  data.setVehicleIcons([icon]);

  const vehicles = data.vehicleFeatures(0).features;
  assert.equal(vehicles[0].properties.iconImage, icon);
  assert.equal(vehicles[0].properties.playerColor, companyColor);
  assert.equal(data.hubFeatures(vehicles).features.length, 0);
  assert.equal(data.hubFeatures().features.length, 1);
  assert.equal(data.locationFeatures(data.state.contracts, "origin_hub_id").features.length, 1);
  assert.equal(data.hubs.length, 1);
});
