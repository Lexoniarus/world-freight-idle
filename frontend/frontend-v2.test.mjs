import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { CityContextController } from "./controllers/city-context-controller.js";
import { LayerStateController } from "./controllers/layer-state-controller.js";
import { AnalyticsController } from "./controllers/analytics-controller.js";
import { ContractMarketController } from "./controllers/contract-market-controller.js";
import { nearestLongitude } from "./geometry.js";
import { selectedLocations } from "./map/selection.js";
import { opportunityGroups } from "./map/opportunities.js";
import { GameState } from "./state.js";
import { layerPresets } from "./layer-presets.js";
import { groupVehicles } from "./map/grouping.js";
import { filterContracts } from "./views/contracts.js";
import { fleetGroups } from "./views/fleet.js";
import { renderVehicleImage } from "./ui/vehicle-image.js";
import { html } from "./ui/dom.js";
import { renderChart } from "./ui/charts.js";

const berlin = {
  city_uid: "a",
  city: "Same Name",
  id: "facility-a",
  aliases: ["legacy"],
  lat: 52,
  lon: 13,
};
const other = { city_uid: "b", city: "Same Name", id: "facility-b", lat: 50, lon: 12 };
const vehicle = {
  id: "v1",
  status: "idle",
  hub: berlin,
  model_id: "iveco_sway_500",
  name: "IVECO",
  capacity_tons: 24,
};
const offer = {
  id: "offer",
  origin: berlin,
  destination: other,
  cargo: "Fahrzeugteile",
  transport_class: "general",
  distance_band: "short",
  eligible_vehicle_ids: ["v1"],
};

function cityFixture() {
  const state = new GameState(async () => {});
  state.data = { vehicles: [vehicle], transports: [], contracts: [offer] };
  const view = {};
  const focus = [];
  const reads = [];
  const city = new CityContextController({
    state,
    view,
    notify() {},
    map: { camera: { fitCoordinates: (points) => focus.push(points) } },
    request: async (path) => {
      reads.push(path);
      if (path.endsWith("bad")) throw new Error("404");
      return { city_uid: "c", city: "Remote" };
    },
  });
  city.start();
  city.update();
  return { state, view, focus, reads, city };
}

test("city defaults, identical names and explicit inactive city survive polling", async () => {
  const { city, state, view, focus } = cityFixture();
  assert.equal(view.cityUid, "a");
  await city.selectRoute(new URL("http://test/contracts?city=b"));
  assert.equal(view.cityUid, "b");
  assert.equal(view.cities.length, 2);
  assert.equal(focus.length, 1);
  state.data.vehicles = [];
  city.update();
  city.update();
  assert.equal(view.cityUid, "b");
  assert.deepEqual(view.activeCities, []);
  assert.equal(focus.length, 1);
  await city.selectRoute(new URL("http://test/fleet?city="));
  state.data.vehicles = [vehicle];
  city.update();
  assert.equal(view.cityUid, "");
  city.destroy();
  state.destroy();
});

test("city links prefer explicit UID, then saved aliases, then exact lookups", async () => {
  const { city, view, reads } = cityFixture();
  await city.selectRoute(new URL("http://test/contracts?hub=legacy"));
  assert.equal(view.cityUid, "a");
  assert.equal(reads.length, 0);
  await city.selectRoute(new URL("http://test/fleet?city=b&hub=bad"));
  assert.equal(view.cityUid, "b");
  assert.equal(reads.length, 0);
  await city.selectRoute(new URL("http://test/fleet/v1"));
  assert.equal(view.cityUid, "a");
  await city.selectRoute(new URL("http://test/fleet?hub=remote"));
  assert.deepEqual(reads, ["/map/facilities/remote"]);
  await city.selectRoute(new URL("http://test/fleet?city=bad"));
  assert.equal(view.cityUid, "");
  city.destroy();
});

test("automatic alternative is deterministic; late city lookup cannot replace navigation", async () => {
  const fixture = cityFixture();
  fixture.state.data.vehicles = [{ ...vehicle, hub: other }, vehicle];
  fixture.city.update();
  assert.equal(fixture.view.cityUid, "a");
  fixture.state.data.vehicles = [{ ...vehicle, hub: other }];
  fixture.city.update();
  assert.equal(fixture.view.cityUid, "b");
  let finish;
  fixture.city.request = () =>
    new Promise((resolve) => {
      finish = resolve;
    });
  const old = fixture.city.selectRoute(new URL("http://test/fleet?city=remote"));
  await fixture.city.selectRoute(new URL("http://test/fleet?city=a"));
  finish({ city_uid: "remote", city: "Old" });
  await old;
  assert.equal(fixture.view.cityUid, "a");
  fixture.city.destroy();
});

test("presets and overrides are per stable account ID and view, reset is scoped", () => {
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key),
    setItem: (key, value) => values.set(key, value),
  };
  const map = { toggle() {}, setGrouping() {}, setPreset() {} };
  const layers = new LayerStateController({ userId: "id-one", storage, map });
  for (const name of Object.keys(layerPresets)) {
    layers.select(new URL("http://test/" + (name === "world" ? "" : name)));
    assert.deepEqual(layers.effective(), layerPresets[name]);
  }
  layers.select(new URL("http://test/fleet"));
  layers.set("routes", false);
  layers.select(new URL("http://test/contracts"));
  layers.set("orders", false);
  layers.setGrouping(false);
  const renamed = new LayerStateController({ userId: "id-one", storage, map });
  renamed.select(new URL("http://test/fleet"));
  assert.equal(renamed.effective().routes, false);
  assert.equal(renamed.grouping, false);
  renamed.select(new URL("http://test/contracts"));
  renamed.reset();
  assert.equal(renamed.effective().orders, true);
  renamed.select(new URL("http://test/fleet"));
  assert.equal(renamed.effective().routes, false);
  const otherAccount = new LayerStateController({ userId: "id-two", storage, map });
  assert.equal(otherAccount.effective().routes, true);
  assert.equal(otherAccount.grouping, true);
  assert.ok([...values.keys()].every((key) => key.includes("id-one")));
});

test("screen grouping preserves coordinates, ownership, selection and disable preference", () => {
  const point = (key, x, own = true) => ({
    geometry: { coordinates: [x, 0] },
    properties: { key, id: key, isOwn: own },
  });
  const features = [point("a", 0), point("b", 0), point("c", 1, false)];
  const original = JSON.stringify(features);
  const project = ([x, y]) => ({ x, y });
  assert.equal(groupVehicles(features, project).length, 2);
  assert.equal(groupVehicles(features, project, "a").length, 3);
  assert.equal(groupVehicles(features, project, "", false).length, 3);
  assert.equal(
    groupVehicles([point("a", 0), point("b", 10)], ([x, y]) => ({ x: x * 100, y })).length,
    2,
  );
  assert.equal(JSON.stringify(features), original);
});

test("offer filters use server IDs exclusively even with incompatible-looking vehicle facts", () => {
  const contracts = [offer, { ...offer, id: "other", origin: other, eligible_vehicle_ids: [] }];
  for (const query of [
    "vehicle=v1",
    "band=short",
    "class=general",
    "cargo=fahrzeug",
    "destination=same",
  ])
    assert.deepEqual(filterContracts(contracts, "a", new URLSearchParams(query)), [offer]);
  for (const query of [
    "vehicle=unknown",
    "band=long",
    "class=parcel",
    "cargo=steel",
    "destination=else",
  ])
    assert.deepEqual(filterContracts(contracts, "a", new URLSearchParams(query)), []);
});

test("fleet city roles never count an arriving truck as stationed or double count local trips", () => {
  const state = {
    vehicles: [vehicle],
    transports: [{ vehicle_id: "v1", origin: berlin, destination: other }],
  };
  const groups = fleetGroups(state, "");
  assert.equal(groups[0].outbound.length, 1);
  assert.equal(groups[0].stationed.length, 0);
  assert.equal(groups[1].inbound.length, 1);
  assert.equal(groups[1].stationed.length, 0);
  state.transports[0].destination = berlin;
  const local = fleetGroups(state, "a");
  assert.equal(local[0].outbound.length, 1);
  assert.equal(local[0].inbound.length, 0);
});

test("detail updates never replace list and analytics ignores late scope responses", async () => {
  const state = new GameState(async () => {});
  state.data = { contracts: [offer] };
  state.replaceContractDetail({ ...offer, id: "detail" });
  assert.equal(state.data.contracts[0], offer);
  state.replaceContractDetail(null, "detail");
  assert.equal(state.contractDetailId, "detail");
  assert.equal(state.data.contracts[0], offer);
  const pending = [];
  const panel = { view: { url: new URL("http://test/company?days=7") }, render() {} };
  const controller = new AnalyticsController({
    panel,
    request: (path, options) => new Promise((resolve) => pending.push({ resolve, path, options })),
  });
  const first = controller.refresh();
  panel.view.url = new URL("http://test/company?days=90");
  const second = controller.refresh();
  pending[1].resolve({ scope: { type: "company" }, breakdowns: {}, id: "new" });
  await second;
  pending[0].resolve({ scope: { type: "company" }, id: "old" });
  await first;
  assert.equal(panel.view.analytics.id, "new");
  assert.equal(pending[0].options.signal.aborted, true);
  panel.view.url = new URL("http://test/fleet");
  await controller.refresh();
  assert.equal(pending.length, 2);
  controller.destroy();
});

test("asset roles and chart tables expose real data without new model assets", () => {
  assert.ok(renderVehicleImage(vehicle, "front").querySelector(".asset-front"));
  assert.ok(renderVehicleImage(vehicle, "side").querySelector(".asset-side"));
  const chart = renderChart(
    "Finanzen",
    [{ date: "2026-09-25", profit_eur: -20 }],
    [["profit_eur", "Ergebnis"]],
  );
  assert.equal(chart.querySelector("svg").getAttribute("role"), "img");
  assert.match(chart.querySelector("table").textContent, /-20/);
  assert.equal(chart.querySelectorAll("circle").length, 1);
});

test("wrapped grouping counts each identity once and never selects a foreign truck by local ID", () => {
  const features = [
    {
      geometry: { coordinates: [179.9, 0] },
      properties: { key: "own", vehicleId: "truck_01", isOwn: true },
    },
    {
      geometry: { coordinates: [-180.1, 0] },
      properties: { key: "other-a", vehicleId: "truck_01", isOwn: false },
    },
    {
      geometry: { coordinates: [179.9, 0] },
      properties: { key: "other-b", vehicleId: "other", isOwn: false },
    },
  ];
  const groups = groupVehicles(
    features,
    ([lon, lat]) => ({ x: nearestLongitude(lon, 180), y: lat }),
    "truck_01",
  );
  assert.deepEqual(groups.map((group) => group.members.length).sort(), [1, 2]);
  assert.equal(groups.flatMap((group) => group.members).length, 3);
  assert.equal(features[1].geometry.coordinates[0], -180.1);
});

test("opportunities aggregate by UID and selected endpoints retain their exact geography", () => {
  const contracts = [offer, { ...offer, id: "two" }, { ...offer, id: "other", origin: other }];
  assert.equal(opportunityGroups(contracts, true).size, 2);
  assert.equal(opportunityGroups(contracts, false).get(berlin.id).count, 2);
  const selected = selectedLocations({ transports: [], contracts }, offer.id);
  assert.deepEqual(selected.features[0].geometry.coordinates, [berlin.lon, berlin.lat]);
  assert.equal(selected.features.length, 2);
});

test("list and detail reads publish independently and cancel obsolete detail navigation", async () => {
  const state = new GameState(async () => {});
  state.data = { contracts: [], vehicles: [], transports: [] };
  let url = new URL("http://test/contracts/one");
  const requests = [];
  const market = new ContractMarketController({
    state,
    request: (path) => new Promise((resolve) => requests.push({ path, resolve })),
    notify: () => {},
    currentUrl: () => url,
  });
  market.ordersVisible = () => true;
  market.start();
  const first = market.refresh();
  requests.find((row) => row.path === "/contracts").resolve({ contracts: [offer] });
  await Promise.resolve();
  assert.equal(state.data.contracts[0], offer);
  url = new URL("http://test/contracts/two");
  const second = market.refresh();
  requests[2].resolve({ contracts: [offer] });
  requests[3].resolve({ ...offer, id: "two" });
  await second;
  requests[1].resolve({ ...offer, id: "one" });
  await first;
  assert.equal(state.contractDetail.id, "two");
  assert.equal(state.data.contracts[0], offer);
  market.destroy();
});

test("optional filters start collapsed with safe boolean semantics", () => {
  assert.equal(
    html`<details open="${false}"><summary>Filter</summary></details>`.querySelector("details")
      .open,
    false,
  );
  assert.equal(
    html`<details open="${true}"><summary>Filter</summary></details>`.querySelector("details").open,
    true,
  );
});

test("navigation before the first fleet snapshot does not freeze an accidental all-cities choice", async () => {
  const state = new GameState(async () => {});
  const view = {};
  const city = new CityContextController({
    state,
    view,
    request: async () => {},
    notify: () => {},
    map: null,
  });
  const route = new URL("http://test/fleet");
  await city.selectRoute(route);
  assert.equal(route.searchParams.has("city"), false);
  state.data = { vehicles: [vehicle], contracts: [], transports: [] };
  city.update();
  await city.selectRoute(route);
  assert.equal(route.searchParams.get("city"), berlin.city_uid);
  assert.equal(city.explicit, false);
  city.destroy();
});
