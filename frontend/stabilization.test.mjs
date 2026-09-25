import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { VehicleColorAssets } from "./vehicle-color-assets.js";
import { VehicleImageController } from "./vehicle-image-bindings.js";
import { OverlayData } from "./map/overlay-data.js";
import { VehicleGroups } from "./map/vehicle-groups.js";
import { groupVehicles } from "./map/grouping.js";
import { PreferencesController } from "./controllers/preferences-controller.js";
import { CityContextController } from "./controllers/city-context-controller.js";
import { GameState } from "./state.js";
import { vehicleIconId } from "./map/vehicle-assets.js";
import { renderVehicleImage } from "./ui/vehicle-image.js";
import { matchVehicleImages } from "./ui/preserve-vehicle-images.js";

const model = "iveco_sway_500";
const source = "<svg style='--vehicle-color:#ffffff'></svg>";
const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test("color assets share sources, separate colors and release leases", async () => {
  let reads = 0;
  const service = new VehicleColorAssets(async () => {
    reads++;
    return source;
  });
  const [a, b, c] = await Promise.all([
    service.acquire(model, "front", "#e45756"),
    service.acquire(model, "front", "#e45756"),
    service.acquire(model, "front", "#4c78a8"),
  ]);
  assert.equal(reads, 1);
  assert.equal(a.url, b.url);
  assert.notEqual(a.url, c.url);
  assert.match(await (await fetch(a.url)).text(), /--vehicle-color:#e45756/);
  a.release();
  assert.equal(service.peek(model, "front", "#e45756"), b.url);
  b.release();
  assert.equal(service.peek(model, "front", "#e45756"), undefined);
  c.release();
  service.destroy();
  await assert.rejects(service.acquire(model, "front", "#e45756"));
});

test("late asset loads cannot repaint disposed image bindings", async () => {
  let finish;
  const service = new VehicleColorAssets(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const controller = new VehicleImageController(service);
  const image = document.createElement("img");
  Object.assign(image.dataset, {
    vehicleModel: model,
    vehicleRole: "front",
    vehicleColor: "#e45756",
  });
  controller.update([image]);
  controller.update([]);
  finish(source);
  await tick();
  assert.equal(image.getAttribute("src"), null);
  assert.equal(service.variants.size, 0);
  controller.destroy();
  service.destroy();
});

test("colored panel polling preserves actual image nodes", async () => {
  const service = new VehicleColorAssets(async () => source);
  const controller = new VehicleImageController(service);
  const vehicle = { model_id: model, name: "Truck", capacity_tons: 24 };
  const current = document.createElement("div");
  current.append(renderVehicleImage(vehicle));
  controller.prepare(current, "#e45756");
  controller.update(current.querySelectorAll("img[data-vehicle-model]"));
  await tick();
  const next = renderVehicleImage(vehicle);
  controller.prepare(next, "#e45756");
  assert.equal(matchVehicleImages(current, next).length, 1);
  const changed = renderVehicleImage(vehicle);
  controller.prepare(changed, "#4c78a8");
  assert.equal(matchVehicleImages(current, changed).length, 0);
  controller.destroy();
  service.destroy();
});

test("idle front uses company color and hides only the facility projection", () => {
  const overlay = new OverlayData();
  overlay.companyColor = "#e45756";
  const hub = { id: "a", city_uid: "city", resolution_status: "resolved", lon: 13, lat: 52 };
  overlay.update({
    vehicles: [{ id: "v", model_id: model, status: "idle", hub, hub_id: "a" }],
    contracts: [{ origin: hub, destination: hub, origin_hub_id: "a" }],
    transports: [],
    traffic: [],
  });
  const icon = vehicleIconId(model, "#e45756", "front");
  overlay.setVehicleIcons([icon]);
  assert.equal(overlay.vehicleFeatures(0).features[0].properties.iconImage, icon);
  assert.equal(overlay.vehicleFeatures(0).features[0].properties.playerColor, "#e45756");
  assert.equal(overlay.hubFeatures(true).features.length, 0);
  assert.equal(overlay.hubFeatures(false).features.length, 1);
  assert.equal(
    overlay.locationFeatures(overlay.state.contracts, "origin_hub_id").features.length,
    1,
  );
  assert.equal(overlay.hubs.length, 1);
});

test("group visuals retain a deterministic vehicle and count; foreign owners remain separate", () => {
  const members = ["one", "two"].map((username, index) => ({
    properties: {
      key: username,
      username,
      modelId: index ? model : "unknown",
      playerColor: "#e45756",
      idle: true,
    },
    geometry: { coordinates: [13, 52] },
  }));
  assert.equal(groupVehicles(members, () => ({ x: 0, y: 0 })).length, 2);
  const button = document.createElement("button");
  VehicleGroups.prototype.renderVisual(button, members);
  assert.equal(button.querySelector("img").dataset.vehicleModel, model);
  assert.equal(button.querySelector("img").dataset.vehicleRole, "front");
  assert.equal(button.querySelector(".vehicle-group-count").textContent, "2");
  const image = button.querySelector("img");
  VehicleGroups.prototype.renderVisual(button, members);
  assert.equal(button.querySelector("img"), image);
});

test("market city options exclude destinations and enroute checkpoints", async () => {
  const a = { id: "a", city_uid: "a", city: "Active" };
  const b = { id: "b", city_uid: "b", city: "Destination" };
  const state = new GameState(async () => {});
  state.data = {
    vehicles: [{ id: "v", status: "idle", hub: a }],
    contracts: [{ origin: a, destination: b }],
    transports: [],
  };
  const view = { url: new URL("http://test/contracts?city=b") };
  const city = new CityContextController({
    state,
    view,
    request: async () => b,
    notify() {},
    map: null,
  });
  city.update();
  await city.selectRoute(view.url);
  assert.deepEqual(
    view.marketCities.map((item) => item.city_uid),
    ["a"],
  );
  assert.equal(view.cityUid, "");
  city.selected = "a";
  city.explicit = true;
  state.data.vehicles[0].status = "enroute";
  city.update();
  assert.deepEqual(view.marketCities, []);
  assert.equal(view.cityUid, "");
  assert.equal(view.url.searchParams.get("city"), "");
  assert.equal(view.cities.length, 2);
  city.destroy();
  state.destroy();
});

test("image replacement transfers its lease before revoking the displayed URL", async () => {
  const assets = new VehicleColorAssets(async () => source);
  const controller = new VehicleImageController(assets);
  const root = document.createElement("div");
  root.append(renderVehicleImage({ model_id: model, name: "Truck" }));
  controller.prepare(root, "#e45756");
  controller.update(root.querySelectorAll("img"));
  await tick();
  const oldUrl = root.querySelector("img").src;
  const next = document.createElement("div");
  next.append(renderVehicleImage({ model_id: model, name: "Truck" }));
  controller.prepare(next, "#e45756");
  controller.update(next.querySelectorAll("img"));
  assert.equal(assets.peek(model, "front", "#e45756"), oldUrl);
  assert.equal((await fetch(oldUrl)).status, 200);
  await tick();
  assert.equal(next.querySelector("img").src, oldUrl);
  controller.destroy();
  assets.destroy();
});

test("a late old-color image cannot overwrite the current selection", async () => {
  let finish;
  const assets = new VehicleColorAssets(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const controller = new VehicleImageController(assets);
  const image = document.createElement("img");
  Object.assign(image.dataset, {
    vehicleModel: model,
    vehicleRole: "front",
    vehicleColor: "#e45756",
  });
  controller.update([image]);
  image.dataset.vehicleColor = "#4c78a8";
  controller.update([image]);
  finish(source);
  await tick();
  assert.match(await (await fetch(image.src)).text(), /--vehicle-color:#4c78a8/);
  assert.equal(assets.variants.size, 1);
  controller.destroy();
  assets.destroy();
});

test("late preference reads cannot overwrite a confirmed color change", async () => {
  const responses = [];
  const panel = { view: { user: {} }, render() {} };
  const published = [];
  const controller = new PreferencesController({
    request: () => new Promise((resolve) => responses.push(resolve)),
    panel,
    map: { setCompanyColor: (color) => published.push(color) },
    notify() {},
  });
  const read = controller.refresh();
  const write = controller.save("#4c78a8");
  responses[1]({ company_color: "#4c78a8" });
  await write;
  responses[0]({ company_color: "#e45756", palette: [] });
  await read;
  assert.deepEqual(published, ["#4c78a8"]);
  assert.equal(panel.view.user.company_color, "#4c78a8");
  controller.destroy();
});
