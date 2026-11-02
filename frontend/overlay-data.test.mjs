import test from "node:test";
import assert from "node:assert/strict";
import { OverlayData, previewFeatures } from "./map/overlay-data.js";
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
