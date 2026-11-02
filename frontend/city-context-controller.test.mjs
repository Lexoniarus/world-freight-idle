import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { CityContextController } from "./controllers/city-context-controller.js";
import { GameState } from "./game-state.js";
import { berlin, offer, other, vehicle } from "./test-support/freight-fixtures.mjs";

function panelFor(view) {
  return {
    publishCityContext(cityUid, cities, activeCities) {
      Object.assign(view, {
        cityUid,
        cities,
        activeCities,
        marketCities: cities.filter((city) => activeCities.includes(city.city_uid)),
      });
    },
  };
}

function cityFixture() {
  const state = new GameState(async () => {});
  state.data = { vehicles: [vehicle], transports: [], contracts: [offer] };
  const view = {};
  const focus = [];
  const reads = [];
  const city = new CityContextController({
    state,
    panel: panelFor(view),
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

test("overview stays unscoped and explicit fleet filters survive polling", async () => {
  const { city, state, view, focus } = cityFixture();
  assert.equal(view.cityUid, "");
  await city.selectRoute(new URL("http://test/fleet?city=b"));
  assert.equal(view.cityUid, "b");
  assert.equal(view.cities.length, 2);
  assert.equal(focus.length, 0);
  state.data.vehicles = [];
  city.update();
  city.update();
  assert.equal(view.cityUid, "b");
  assert.deepEqual(view.activeCities, []);
  assert.equal(focus.length, 0);
  await city.selectRoute(new URL("http://test/fleet?city="));
  state.data.vehicles = [vehicle];
  city.update();
  assert.equal(view.cityUid, "");
  city.destroy();
  state.destroy();
});

test("city links prefer explicit UID, saved aliases and exact lookups", async () => {
  const { city, view, reads } = cityFixture();
  await city.selectRoute(new URL("http://test/contracts?vehicle=v1&hub=legacy"));
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

test("late city lookup cannot replace newer navigation", async () => {
  const fixture = cityFixture();
  fixture.state.data.vehicles = [{ ...vehicle, hub: other }, vehicle];
  fixture.city.update();
  assert.equal(fixture.view.cityUid, "");
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

test("navigation waits for an explicit vehicle or city context", async () => {
  const state = new GameState(async () => {});
  const view = {};
  const city = new CityContextController({
    state,
    panel: panelFor(view),
    request: async () => {},
    notify: () => {},
    map: null,
  });
  const route = new URL("http://test/fleet");
  await city.selectRoute(route);
  assert.equal(route.searchParams.has("city"), false);
  state.data = { vehicles: [vehicle], contracts: [], transports: [] };
  city.update();
  await city.selectRoute(new URL("http://test/contracts?vehicle=v1"));
  assert.equal(view.cityUid, berlin.city_uid);
  city.destroy();
});

test("market cities contain only origins of currently idle vehicles", async () => {
  const state = new GameState(async () => {});
  state.data = {
    vehicles: [vehicle],
    contracts: [offer],
    transports: [],
  };
  const view = { url: new URL("http://test/contracts?city=b") };
  const city = new CityContextController({
    state,
    panel: panelFor(view),
    request: async () => other,
    notify() {},
    map: null,
  });
  city.update();

  await city.selectRoute(view.url);
  assert.deepEqual(
    view.marketCities.map((item) => item.city_uid),
    [berlin.city_uid],
  );
  assert.equal(view.cityUid, "");

  city.selected = berlin.city_uid;
  city.explicit = true;
  state.data.vehicles[0].status = "enroute";
  city.update();
  assert.deepEqual(view.marketCities, []);
  assert.equal(view.cityUid, "");
  assert.equal(view.url.searchParams.has("city"), false);
  assert.equal(view.cities.length, 2);
  city.destroy();
  state.destroy();
});
