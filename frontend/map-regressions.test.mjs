import {
  vehicleFootprint,
  footprintsOverlap,
  spriteBounds,
  vehicleIconScale,
} from "./map/vehicle-footprint.js";
import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { groupVehicles } from "./map/grouping.js";
import { VehicleGroups } from "./map/vehicle-groups.js";
import { paintPixels, originalVehicleSvg } from "./vehicle-paint.js";
import { MapFocusController } from "./controllers/map-focus-controller.js";
import { focusCoordinates } from "./map/focus-targets.js";
import { addOverlayLayers } from "./map/layers.js";

const point = (id, idle, owner = "own", x = 0) => ({
  geometry: { coordinates: [x, 0] },
  properties: {
    key: owner + ":" + id,
    id,
    vehicleId: id,
    isOwn: owner === "own",
    username: owner,
    idle,
    movementState: idle ? "idle" : "enroute",
    bearing: 137,
    modelId: "daf_xg_plus_480",
    playerColor: "#4c78a8",
  },
});
const project = ([x, y]) => ({ x, y });

test("group partitions are invariant under input order and never mix movement or owner", () => {
  const features = [
    point("b", true),
    point("a", true),
    point("d", false),
    point("c", false),
    point("e", false, "Alice"),
    point("f", false, "Bob"),
  ];
  const groups = groupVehicles(features, project);
  assert.deepEqual(
    groups.map((g) => g.members.map((m) => m.properties.key)),
    groupVehicles([...features].reverse(), project).map((g) =>
      g.members.map((m) => m.properties.key),
    ),
  );
  assert.deepEqual(groups.map((g) => g.members.length).sort(), [1, 1, 2, 2]);
  for (const group of groups) {
    assert.equal(new Set(group.members.map((m) => m.properties.movementState)).size, 1);
    assert.equal(new Set(group.members.map((m) => m.properties.username)).size, 1);
  }
  assert.equal(groupVehicles(features, project, "a").length, 5);
  assert.equal(groupVehicles(features, project, "", false).length, 6);
  assert.equal(groupVehicles([point("a", false), point("b", true)], project).length, 2);
});

test("throttled groups refresh representative pose without choosing another member", () => {
  const positions = [];
  const button = document.createElement("button");
  const first = point("a", false);
  const entry = {
    button,
    members: [first, point("b", false)],
    marker: { setLngLat: (p) => positions.push(p) },
  };
  const group = { map: { getCenter: () => ({ lng: 0 }) }, markers: new Map([["own:a", entry]]) };
  const moved = point("a", false, "own", 12);
  moved.properties.bearing = 271;
  VehicleGroups.prototype.updatePoses.call(group, [moved, point("b", false, "own", 13)]);
  assert.deepEqual(positions, [[12, 0]]);
  assert.equal(entry.members[0], moved);
  VehicleGroups.prototype.renderVisual(button, entry.members);
  assert.equal(button.dataset.representative, "own:a");
  assert.equal(button.dataset.movement, "enroute");
  assert.equal(button.querySelector("img"), null);
  assert.equal(button.textContent, "2");
});

test("singleton and representative share direction layers while idle remains screen upright", () => {
  const layers = new Map();
  addOverlayLayers({
    addSource() {},
    addLayer: (l) => layers.set(l.id, l),
    getLayer: (id) => ({ serialize: () => structuredClone(layers.get(id)) }),
    setFilter: (id, f) => (layers.get(id).filter = f),
  });
  for (const id of ["vehicles", "multiplayer-vehicles", "selected-vehicle-assets"]) {
    assert.deepEqual(layers.get(id).layout["icon-rotate"], ["get", "bearing"]);
    assert.equal(layers.get(id).layout["icon-rotation-alignment"], "map");
    assert.equal(layers.get(id + "-idle").layout["icon-rotate"], 0);
    assert.equal(layers.get(id + "-idle").layout["icon-rotation-alignment"], "viewport");
  }
});

test("paint preserves protected colors, alpha and shadow contrast with fractional masks", () => {
  const base = new Uint8ClampedArray([
    240, 240, 240, 255, 100, 100, 100, 255, 35, 40, 45, 255, 250, 250, 250, 0, 200, 200, 200, 128,
  ]);
  const mask = new Uint8ClampedArray([
    255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 255, 255, 255, 255, 255, 128, 128, 128, 255,
  ]);
  const out = paintPixels(base, mask, "#4080c0");
  assert.deepEqual([...out.slice(8, 12)], [35, 40, 45, 255]);
  assert.deepEqual(
    [3, 7, 11, 15, 19].map((i) => out[i]),
    [255, 255, 255, 0, 128],
  );
  assert.ok(out[0] > out[4]);
  assert.ok(out[0] < base[0]);
  assert.ok(out[16] < 200 && out[16] > 100);
  assert.equal(base[0], 240);
  assert.throws(() => paintPixels(base, new Uint8ClampedArray(), "#ffffff"));
});

test("original extraction discards filters, injected markup and mask rasters", () => {
  const original =
    '<svg width="2" height="3"><defs><mask><image href="data:image/png;base64,TUF"/></mask></defs><image filter="url(#bad)" onload="bad()" href="data:image/png;base64,QUJD"/><script>bad()</script></svg>';
  const result = originalVehicleSvg(original);
  assert.equal(result.width, 2);
  assert.equal(result.height, 3);
  assert.match(result.svg, /QUJD/);
  assert.doesNotMatch(result.svg, /filter|script|onload|TUF/);
  assert.throws(() => originalVehicleSvg("<svg/>"));
  assert.throws(() => originalVehicleSvg('<svg><image href="data:image/png;base64,QUJD"/></svg>'));
});

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
    segments: [{ phase: "driving", starts_at: 0, ends_at: 100, start_km: 0, end_km: 100 }],
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
    { id: "moving", name: "Moving", model_id: "heavy", status: "enroute", hub },
  ],
  transports: [trip],
  contracts: [{ id: "offer", origin: hub, destination }],
};
const url = (path) => new URL("http://test" + path);

test("navigation targets distinguish vehicle positions, saved routes and visible fleet filters", () => {
  const focus = (path) => focusCoordinates(snapshot, url(path), 50, null, "", []);
  assert.deepEqual(focus("/fleet/idle"), [[10, 50]]);
  assert.equal(focus("/fleet/moving").length, 1);
  assert.notDeepEqual(focus("/fleet/moving"), [[9, 49]]);
  assert.ok(focus("/transports/trip").some((p) => p[0] === 9));
  assert.ok(focus("/transports").some((p) => p[0] === 12));
  assert.deepEqual(focus("/fleet?status=idle"), [[10, 50]]);
  assert.deepEqual(focus("/fleet?model=van"), [[10, 50]]);
  assert.deepEqual(focus("/fleet?search=absent"), []);
  assert.deepEqual(focus("/contracts/offer"), [
    [10, 50],
    [12, 52],
  ]);
  assert.equal(focus("/contracts/missing"), null);
  assert.deepEqual(focusCoordinates(snapshot, url("/contracts?city=a"), 50, null, "a", [hub]), [
    [10, 50],
    [10, 50],
    [10, 50],
    [10, 50],
    [10, 50],
  ]);
});

test("focus consumes navigation once; polling and obsolete detail responses cannot refocus", () => {
  const state = new EventTarget();
  state.data = structuredClone(snapshot);
  state.now = () => 50;
  const calls = [];
  const map = {
    ready: false,
    map: { on() {}, off() {} },
    camera: { fitCoordinates: (p) => calls.push(p) },
    focusRoute: (r) => calls.push(r),
  };
  const focus = new MapFocusController({ state, map, view: { cityUid: "", cities: [] } });
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
  focus.select(url("/contracts/missing"));
  assert.equal(calls.length, 1);
  focus.cancel();
  focus.select(url("/fleet/moving"));
  assert.equal(calls.length, 2);
  state.contractDetail = { id: "missing", origin: hub, destination };
  state.dispatchEvent(new Event("change"));
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

test("grouping follows actual rendered overlap at every zoom, not a fixed radius", () => {
  const truck = point("a", false);
  Object.assign(truck.properties, { hasIcon: true, iconBounds: [-4, -32, 4, 32], bearing: 0 });
  const other = structuredClone(truck);
  other.properties.key = "own:b";
  other.properties.id = "b";
  other.geometry.coordinates = [12, 0];
  assert.equal(groupVehicles([truck, other], project, "", true, 17).length, 2);
  other.geometry.coordinates = [6, 0];
  assert.equal(groupVehicles([truck, other], project, "", true, 17).length, 1);
  assert.equal(groupVehicles([truck, other], project, "", true, 5).length, 2);
  other.geometry.coordinates = [0, 20];
  assert.equal(groupVehicles([truck, other], project, "", true, 5).length, 1);
  truck.properties.bearing = other.properties.bearing = 90;
  assert.equal(groupVehicles([truck, other], project, "", true, 17).length, 2);
  const rotated = vehicleFootprint(truck, { x: 0, y: 0 }, 13, 90);
  assert.ok(
    footprintsOverlap(
      rotated,
      vehicleFootprint(
        { ...truck, properties: { ...truck.properties, bearing: 0 } },
        { x: 0, y: 20 },
        13,
        0,
      ),
    ),
  );
  const pixels = new Uint8ClampedArray(4 * 4 * 4);
  pixels[(1 * 4 + 2) * 4 + 3] = 255;
  assert.deepEqual(spriteBounds({ width: 4, height: 4, data: pixels }), [0, -0.5, 0.5, 0]);
  assert.deepEqual(
    spriteBounds({ width: 4, height: 4, data: new Uint8ClampedArray(64) }),
    [0, 0, 0, 0],
  );
  assert.equal(vehicleIconScale(1), 0.55);
  assert.equal(vehicleIconScale(20), 1.15);
});

test("vehicle context opens every city offer with authoritative suitability", async () => {
  const { renderContracts } = await import("./views/contracts.js");
  const { CityContextController } = await import("./controllers/city-context-controller.js");
  const { marketVehicle } = await import("./market-context.js");
  const { renderShell } = await import("./views/shell.js");
  const { GameState } = await import("./state.js");
  const city = { city_uid: "a", city: "Alpha", label: "Depot", lat: 1, lon: 2 };
  const other = { ...city, city_uid: "b", city: "Beta" };
  const idle = { id: "v", name: "Reference truck", status: "idle", hub: city };
  const state = new GameState(async () => {});
  state.data = {
    vehicles: [idle, { ...idle, id: "w", hub: other }],
    contracts: [],
    transports: [],
  };
  const view = { state: state.data, url: new URL("http://test/") };
  const controller = new CityContextController({
    state,
    view,
    request: async () => {},
    notify() {},
  });
  await controller.selectRoute(new URL("http://test/?city=a&vehicle=v"));
  assert.equal(controller.route.search, "");
  assert.equal(view.cityUid, "");
  assert.equal(renderShell({ username: "Tester" }).querySelector("#current-city-label"), null);
  view.url = new URL("http://test/contracts?vehicle=v&city=b");
  await controller.selectRoute(view.url);
  assert.equal(view.cityUid, "a");
  assert.equal(view.url.searchParams.get("city"), "a");
  state.data.contracts = [
    {
      id: "yes",
      cargo: "Parts",
      tons: 2,
      origin: city,
      destination: other,
      eligible_vehicle_ids: ["v"],
    },
    {
      id: "no",
      cargo: "Large parts",
      tons: 20,
      origin: city,
      destination: other,
      eligible_vehicle_ids: [],
    },
    {
      id: "away",
      cargo: "Parts",
      tons: 2,
      origin: other,
      destination: city,
      eligible_vehicle_ids: ["w"],
    },
  ];
  const fragment = renderContracts(view);
  const cards = [...fragment.querySelectorAll(".job-card")];
  assert.equal(cards.length, 2);
  assert.match(cards[0].textContent, /Reference truck · geeignet/);
  assert.match(cards[1].textContent, /Reference truck · nicht geeignet/);
  assert.equal(fragment.querySelector('[data-filter="city"]'), null);
  assert.equal(fragment.querySelector('[data-filter="vehicle"]').value, "v");
  idle.status = "enroute";
  controller.update();
  assert.equal(view.cityUid, "");
  assert.equal(view.url.searchParams.has("vehicle"), false);
  assert.equal(renderContracts(view).querySelectorAll(".job-card").length, 0);
  assert.equal(marketVehicle(state.data, new URL("http://test/contracts?vehicle=v"), true), null);
  await controller.selectRoute(new URL("http://test/"));
  assert.equal(view.cityUid, "");
  controller.destroy();
  state.destroy();
});
