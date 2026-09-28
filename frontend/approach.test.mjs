import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { OverlayData } from "./map/overlay-data.js";
import { transportProgress } from "./journey.js";
import { progressDisplay } from "./views/transports.js";

const trip = {
  id: "pickup",
  vehicle_id: "truck",
  departed_at: 100,
  arrives_at: 140,
  route_geojson: {
    type: "LineString",
    coordinates: [
      [0, 0],
      [10, 0],
      [11, 0],
    ],
  },
  route_legs: [
    {
      purpose: "approach",
      start_km: 0,
      end_km: 10,
      coordinates: [
        [0, 0],
        [10, 0],
      ],
    },
    {
      purpose: "delivery",
      start_km: 10,
      end_km: 110,
      coordinates: [
        [10, 0],
        [11, 0],
      ],
    },
  ],
  journey: {
    distance_km: 110,
    segments: [
      { phase: "driving", starts_at: 0, ends_at: 10, start_km: 0, end_km: 5 },
      { phase: "refuelling", starts_at: 10, ends_at: 15, start_km: 5, end_km: 5 },
      { phase: "driving", starts_at: 15, ends_at: 20, start_km: 5, end_km: 10 },
      { phase: "driving", starts_at: 20, ends_at: 30, start_km: 10, end_km: 60 },
      { phase: "charging", starts_at: 30, ends_at: 35, start_km: 60, end_km: 60 },
      { phase: "driving", starts_at: 35, ends_at: 40, start_km: 60, end_km: 110 },
    ],
  },
};

test("own and public geometry follow road leg boundaries, including both energy stops", () => {
  const data = new OverlayData();
  data.update({
    vehicles: [],
    contracts: [],
    transports: [trip],
    traffic: [
      { ...trip, is_own: true },
      { ...trip, id: "public", is_own: false },
    ],
  });
  const cached = data.trafficRoutes.get(trip.id);
  for (const [elapsed, longitude, stage] of [
    [0, 0, "approach"],
    [10, 5, "approach"],
    [14, 5, "approach"],
    [20, 10, "delivery"],
    [30, 10.5, "delivery"],
    [34, 10.5, "delivery"],
    [40, 11, null],
  ]) {
    assert.equal(transportProgress(trip, 100 + elapsed).stage, stage);
    for (const own of [true, false]) {
      const position = data.trafficFeatures(100 + elapsed, own).features[0].geometry.coordinates;
      assert.deepEqual(position, [longitude, 0]);
    }
  }
  data.update(data.state);
  assert.equal(data.trafficRoutes.get(trip.id), cached);
  assert.deepEqual(data.routeFeatures().features[0].geometry.coordinates, [
    [0, 0],
    [10, 0],
    [11, 0],
  ]);
});

test("pickup labels follow half-open section intervals without hiding energy stops", () => {
  assert.equal(progressDisplay(trip, 100).phase, "Zur Abholung");
  assert.equal(progressDisplay(trip, 112).phase, "Tankt");
  assert.equal(progressDisplay(trip, 120).phase, "Fracht unterwegs");
  assert.equal(progressDisplay(trip, 132).phase, "Lädt");
  assert.equal(progressDisplay(trip, 140).phase, "Ankunft");
  const historical = { ...trip, route_legs: undefined };
  assert.equal(progressDisplay(historical, 100).phase, "Unterwegs");
});
