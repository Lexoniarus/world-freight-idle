import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { journeyProgress, transportProgress } from "./journey.js";
import { progressDisplay } from "./views/transports.js";
import { OverlayData } from "./map/overlay-data.js";
import { renderFleet } from "./views/fleet.js";
import { GameSync } from "./controllers/game-sync.js";
import { renderEnergySpecification } from "./ui/vehicle-energy.js";

const fixture = JSON.parse(
  readFileSync(new URL("../tests/fixtures/energy-timeline.json", import.meta.url)),
);
const trip = {
  id: "trip",
  vehicle_id: "truck",
  journey: fixture.journey,
  departed_at: 100,
  arrives_at: 1960,
  origin: { city: "A" },
  destination: { city: "B" },
  route_geojson: {
    type: "LineString",
    coordinates: [
      [0, 0],
      [5, 0],
    ],
  },
};

test("shared Python timeline samples agree at movement, stop and arrival boundaries", () => {
  for (const sample of fixture.samples) {
    const state = transportProgress(trip, 100 + sample.elapsed);
    assert.equal(state.phase, sample.phase);
    assert.ok(Math.abs(state.fraction - sample.fraction) < 1e-12);
    assert.ok(Math.abs(state.energyLevel - sample.energy) < 1e-9);
  }
  assert.throws(() => journeyProgress(fixture.journey, NaN));
  assert.throws(() => journeyProgress({ distance_km: 1, segments: [] }, 1));
  const stopped = progressDisplay(trip, 1750);
  assert.equal(stopped.phase, "Tankt");
  assert.equal(stopped.percent, 90);
  assert.match(stopped.eta, /Weiter in 30 s/);
  assert.match(progressDisplay(trip, 1960).eta, /bestätigt/);
});

test("private and public map vehicles stay at the identical stop position", () => {
  const publicJourney = {
    distance_km: fixture.journey.distance_km,
    segments: fixture.journey.segments.map(({ phase, starts_at, ends_at, start_km, end_km }) => ({
      phase,
      starts_at,
      ends_at,
      start_km,
      end_km,
    })),
  };
  const overlays = new OverlayData();
  overlays.update({
    vehicles: [],
    contracts: [],
    transports: [],
    traffic: [
      { ...trip, is_own: true, model_id: "iveco_sway_500", player_color: "#123456" },
      {
        ...trip,
        id: "other",
        journey: publicJourney,
        is_own: false,
        model_id: "iveco_sway_500",
        player_color: "#abcdef",
      },
    ],
  });
  for (const now of [1720, 1750, 1779]) {
    assert.deepEqual(overlays.vehicleFeatures(now).features[0].geometry.coordinates, [4.5, 0]);
    assert.deepEqual(
      overlays.multiplayerVehicleFeatures(now).features[0].geometry.coordinates,
      [4.5, 0],
    );
  }
  assert.ok(overlays.multiplayerVehicleFeatures(1800).features[0].geometry.coordinates[0] > 4.5);
  assert.equal(transportProgress({ ...trip, journey: publicJourney }, 1750).energyLevel, null);
});

test("meter and phase ticks preserve vehicle images and use safe text", () => {
  const vehicle = {
    id: "truck",
    name: "IVECO",
    model_id: "iveco_sway_500",
    capacity_tons: 24,
    energy: fixture.journey.energy,
    energy_level: 100,
    top_speed_kmh: 90,
    hub: { label: "Origin" },
    hub_id: "origin",
    status: "enroute",
  };
  const data = { vehicles: [vehicle], transports: [trip], idle_vehicles: 0, active_transports: 1 };
  let now = 1720;
  document.body.replaceChildren(
    renderFleet({ state: data, url: new URL("http://test/fleet"), now }),
  );
  const picture = document.querySelector("img");
  const state = { data, now: () => now };
  const sync = new GameSync({ state, panel: {}, map: null, notify: () => {} });
  sync.updateProgress();
  assert.equal(document.querySelector("meter").value, 10);
  assert.equal(document.querySelector("[data-phase-trip]").textContent, "Tankt");
  now = 1780;
  sync.updateProgress();
  assert.equal(document.querySelector("meter").value, 100);
  assert.equal(document.querySelector("[data-phase-trip]").textContent, "Unterwegs");
  assert.equal(document.querySelector("img"), picture);
  const unsafe = renderEnergySpecification({
    ...vehicle,
    energy: { ...vehicle.energy, unit: "<img onerror=bad()>" },
  });
  assert.equal(unsafe.querySelector("img"), null);
  assert.match(unsafe.textContent, /<img onerror=bad\(\)>/);
});
