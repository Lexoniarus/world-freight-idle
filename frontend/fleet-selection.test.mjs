import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { fleetEntries, groupFleetEntries, selectFleetEntries } from "./fleet-selection.js";
import { renderFleet } from "./views/fleet.js";

const berlin = { city_uid: "berlin", city: "Berlin" };
const hamburg = { city_uid: "hamburg", city: "Hamburg" };
const vehicle = {
  id: "truck-1",
  name: "Nordstern",
  model_id: "iveco_sway_500",
  status: "enroute",
  hub: berlin,
  capacity_tons: 24,
  energy: {
    kind: "diesel",
    unit: "l",
    capacity: 100,
    consumption_per_100km: 20,
    stop_minutes: 10,
  },
  energy_level: 100,
};
const trip = {
  id: "trip-1",
  vehicle_id: vehicle.id,
  origin: berlin,
  destination: hamburg,
  departed_at: 0,
  arrives_at: 100,
  journey: {
    distance_km: 100,
    segments: [
      {
        phase: "driving",
        starts_at: 0,
        ends_at: 100,
        start_km: 0,
        end_km: 100,
        start_energy: 100,
        end_energy: 80,
      },
    ],
  },
};
const state = { vehicles: [vehicle], transports: [trip] };

test("active vehicle joins its transport exactly once", () => {
  const entries = fleetEntries(state);

  assert.equal(entries.length, 1);
  assert.equal(entries[0].vehicle, vehicle);
  assert.equal(entries[0].trip, trip);
});

test("active vehicle remains distinct for origin and destination filters", () => {
  for (const cityUid of ["", berlin.city_uid, hamburg.city_uid]) {
    const entries = selectFleetEntries(state, new URL("http://test/fleet"), cityUid);
    assert.deepEqual(
      entries.map((entry) => entry.vehicle.id),
      [vehicle.id],
    );
  }
  assert.deepEqual(selectFleetEntries(state, new URL("http://test/fleet"), "missing"), []);
});

test("stationed vehicles group by their physical city", () => {
  const stationed = {
    ...vehicle,
    status: "idle",
    location_snapshot: berlin,
  };
  const sections = groupFleetEntries(fleetEntries({ vehicles: [stationed], transports: [] }));

  assert.equal(sections.length, 1);
  assert.equal(sections[0].kind, "stationed");
  assert.equal(sections[0].label, "Berlin");
  assert.equal(sections[0].entries[0].vehicle, stationed);
});

test("active vehicles share one journey section without duplicate cards", () => {
  const second = { ...vehicle, id: "truck-2", name: "Suedstern" };
  const sections = groupFleetEntries(
    fleetEntries({
      vehicles: [vehicle, second],
      transports: [trip, { ...trip, id: "trip-2", vehicle_id: second.id }],
    }),
  );

  assert.equal(sections.length, 1);
  assert.equal(sections[0].kind, "enroute");
  assert.deepEqual(
    sections[0].entries.map((entry) => entry.vehicle.id),
    [vehicle.id, second.id],
  );
});

test("fleet view renders one card for one active vehicle", () => {
  const view = renderFleet({
    state,
    url: new URL("http://test/fleet"),
    now: 50,
    cityUid: "",
  });

  assert.equal(view.querySelectorAll(".vehicle-card").length, 1);
  assert.match(view.textContent, /Berlin → Hamburg/);
  assert.match(view.textContent, /Unterwegs/);
});
