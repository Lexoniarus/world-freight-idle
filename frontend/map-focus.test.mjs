import test from "node:test";
import assert from "node:assert/strict";
import { MapFocusController } from "./controllers/map-focus-controller.js";
import { focusCoordinates } from "./map/focus-targets.js";

const hub = { lon: 10, lat: 50, city_uid: "a", city: "Alpha" };
const destination = { lon: 12, lat: 52, city_uid: "b", city: "Beta" };
const trip = {
  id: "trip",
  vehicle_id: "moving",
  origin: hub,
  start: { lon: 9, lat: 49 },
  destination,
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
      },
    ],
  },
  route_geojson: {
    type: "LineString",
    coordinates: [
      [9, 49],
      [10, 50],
      [12, 52],
    ],
  },
};
const snapshot = {
  vehicles: [
    { id: "idle", name: "Idle", model_id: "van", status: "idle", hub },
    {
      id: "moving",
      name: "Moving",
      model_id: "heavy",
      status: "enroute",
      hub,
    },
  ],
  transports: [trip],
  contracts: [{ id: "offer", origin: hub, destination }],
};
const url = (path) => new URL("http://test" + path);

test("navigation targets use current vehicle positions and saved routes", () => {
  const focus = (path) => focusCoordinates(snapshot, url(path), 50, null, "", []);
  assert.deepEqual(focus("/fleet/idle"), [[10, 50]]);
  assert.equal(focus("/fleet/moving").length, 1);
  assert.notDeepEqual(focus("/fleet/moving"), [[9, 49]]);
  assert.ok(focus("/transports/trip").some((point) => point[0] === 9));
  assert.ok(focus("/transports").some((point) => point[0] === 12));
  assert.deepEqual(focus("/fleet?status=idle"), [[10, 50]]);
  assert.deepEqual(focus("/fleet?model=van"), [[10, 50]]);
  assert.deepEqual(focus("/fleet?search=absent"), []);
  assert.deepEqual(focus("/contracts/offer"), [
    [10, 50],
    [12, 52],
  ]);
  assert.equal(focus("/contracts/missing"), null);
});

test("focus consumes each navigation intent exactly once", () => {
  const state = new EventTarget();
  state.data = structuredClone(snapshot);
  state.now = () => 50;
  const calls = [];
  const map = {
    ready: false,
    addEventListener() {},
    removeEventListener() {},
    fitCoordinates: (points) => calls.push(points),
    focusRoute: (route) => calls.push(route),
  };
  const focus = new MapFocusController({
    state,
    map,
    view: { cityUid: "", cities: [] },
  });
  focus.start();
  focus.select(url("/fleet/idle"));
  assert.equal(calls.length, 0);
  map.ready = true;
  focus.flush();
  assert.equal(calls.length, 1);
  state.dispatchEvent(new Event("change"));
  focus.select(url("/fleet/idle"));
  assert.equal(calls.length, 1);
  focus.cancel();
  focus.select(url("/fleet/moving"));
  assert.equal(calls.length, 2);
  focus.cancel();
  focus.select(url("/fleet/idle"));
  assert.equal(calls.length, 3);
  focus.quote({ route_geojson: trip.route_geojson });
  assert.equal(calls.length, 4);
  state.dispatchEvent(new Event("change"));
  assert.equal(calls.length, 4);
  focus.destroy();
});
