import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { html, requiredElement } from "./ui/dom.js";
import { renderShell } from "./views/shell.js";
import { renderPanel } from "./panels.js";
import { GameApiClient, ApiError } from "./api.js";
import { GameState } from "./state.js";
import { GameActions } from "./controllers/game-actions.js";
import { PanelController } from "./controllers/panel-controller.js";
import { MobileSheet } from "./controllers/mobile-sheet.js";
import { Notifications } from "./controllers/notifications.js";
import { RefreshScheduler } from "./controllers/refresh-scheduler.js";
import { BrowserRouter } from "./navigation.js";
import { VehicleAnimator } from "./map/vehicle-animator.js";
import { OverlayData, previewFeatures } from "./map/overlay-data.js";
import { GameApplication } from "./application.js";
import { money, number } from "./format.js";
import { formatDuration, routeProgress } from "./time.js";

const hub = {
  id: "berlin",
  label: "Westhafen",
  city: "Berlin",
  address: "Westhafen 1",
  lat: 52,
  lon: 13,
  resolution_status: "resolved",
};
const contract = {
  id: "job",
  origin_hub_id: hub.id,
  origin: hub,
  destination: { ...hub, city: "Hamburg" },
  mode: "truck",
  tons: 10,
  cargo: "Steel",
  shipper_name: "A",
  consignee_name: "B",
};
const vehicle = {
  id: "truck",
  name: "Lkw",
  mode: "truck",
  status: "idle",
  hub_id: hub.id,
  hub,
  capacity_tons: 24,
};
const quote = {
  vehicle_id: vehicle.id,
  operating_cost_eur_per_km: 0.62,
  route_geojson: {
    type: "LineString",
    coordinates: [
      [179, 0],
      [-179, 0],
    ],
  },
  distance_km: 100,
  duration_seconds: 3600,
  payout_eur: 2000,
  operating_cost_eur: 500,
  profit_eur: 1500,
};
const trip = {
  ...quote,
  id: "trip",
  vehicle_id: vehicle.id,
  origin: hub,
  destination: contract.destination,
  contract,
  departed_at: 0,
  arrives_at: 100,
};

function createView(path = "/contracts/job") {
  return {
    url: new URL(path, "http://test"),
    state: {
      contracts: [contract],
      vehicles: [vehicle],
      transports: [],
      player: { cash: 25000, completed: 0, reputation: 0 },
      time_scale: 1,
      idle_vehicles: 1,
      active_transports: 0,
    },
    user: { username: "driver" },
    quote: null,
    selectedVehicle: "",
    mutating: false,
    quoting: false,
    get busy() {
      return this.mutating || this.quoting;
    },
    rankings: null,
    catalogue: null,
    panelError: false,
  };
}

function mountPanel(request = async () => ({})) {
  document.body.replaceChildren(renderShell({ username: "driver" }));
  const panel = new PanelController({ view: createView(), request, notify() {}, now: () => 50 });
  panel.render();
  return panel;
}

test("DOM binding preserves malicious text and quoted attributes without parsing them", () => {
  const input = '"><img src=x onerror="alert(1)"><script>x</script>';
  const fragment = html`<div title="${input}">
    ${input}${[html`<strong>safe</strong>`, " & text"]}
  </div>`;
  assert.equal(fragment.querySelector("img, script"), null);
  assert.equal(fragment.firstElementChild.getAttribute("title"), input);
  assert.equal(fragment.textContent.trim(), input + "safe & text");
  assert.equal(html`<button disabled="${false}">ok</button>`.firstElementChild.disabled, false);
  assert.equal(html`<option selected="${true}">ok</option>`.firstElementChild.selected, true);
  assert.equal(html`<button disabled="${null}">ok</button>`.firstElementChild.disabled, false);
  assert.throws(() => html`<a href="${"javascript:alert(1)"}">bad</a>`, /protocol/);
  assert.throws(() => html`<iframe srcdoc="${input}"></iframe>`, /forbidden/);
  assert.throws(() => requiredElement("#missing"), /Missing element/);
});

test("migrated display helpers preserve money, measurement and time behavior", () => {
  assert.match(money(1200), /1\.200/);
  assert.equal(number(12.5), "12,5");
  assert.equal(formatDuration(3660), "1 h 1 min");
  assert.equal(formatDuration(90061), "1 T 1 h 1 min");
  assert.equal(routeProgress(5, 10, 20), 0);
  assert.equal(routeProgress(15, 10, 20), 0.5);
  assert.equal(routeProgress(25, 10, 20), 1);
  assert.equal(routeProgress(5, 10, 10), 1);
});

test("API client sends credentials only to API v1 and aborts pending transport", async () => {
  const calls = [];
  const api = new GameApiClient(
    async (url, options) => {
      calls.push({ url, options });
      return { ok: true, json: async () => ({ id: "ok" }) };
    },
    () => {},
  );
  assert.deepEqual(
    await api.request("/fleet/purchase", {
      method: "POST",
      body: JSON.stringify({ model_id: "regional" }),
    }),
    { id: "ok" },
  );
  assert.equal(calls[0].url, "/api/v1/fleet/purchase");
  assert.equal(calls[0].options.credentials, "same-origin");
  assert.equal(calls[0].options.redirect, "error");
  assert.equal(calls[0].options.headers.get("X-Freight-Request"), "1");
  assert.deepEqual(JSON.parse(calls[0].options.body), { model_id: "regional" });
  await assert.rejects(api.request("https://other.test/"), /API-relative/);
  await assert.rejects(api.request("//other.test/"), /API-relative/);
  api.destroy();
  assert.equal(calls[0].options.signal.aborted, true);
});

test("API errors distinguish expired sessions, validation errors and non-JSON failures", async () => {
  const redirects = [];
  let response = { ok: false, status: 401, json: async () => ({ detail: "expired" }) };
  const api = new GameApiClient(
    async () => response,
    (path) => redirects.push(path),
  );
  await assert.rejects(
    api.request("/fleet"),
    (error) => error instanceof ApiError && error.status === 401,
  );
  await assert.rejects(api.request("/auth/login"), /expired/);
  assert.deepEqual(redirects, ["/login"]);
  response = { ok: false, status: 422, json: async () => ({ detail: [{ msg: "bad" }] }) };
  await assert.rejects(api.request("/auth/register"), /Eingaben/);
  response = {
    ok: false,
    status: 503,
    json: async () => {
      throw new Error("not json");
    },
  };
  await assert.rejects(api.request("/fleet"), /HTTP 503/);
  api.destroy();
});

test("panel controls retain focus and selection across authoritative refreshes", () => {
  const panel = mountPanel();
  const select = requiredElement("#vehicle-choice");
  select.value = vehicle.id;
  panel.view.selectedVehicle = vehicle.id;
  select.focus();
  panel.view.quote = quote;
  panel.render();
  assert.equal(document.activeElement.id, "vehicle-choice");
  assert.equal(document.activeElement.value, vehicle.id);
  assert.equal(requiredElement('[data-action="dispatch"]').hasAttribute("disabled"), false);
  const navigation = requiredElement(".nav-item");
  navigation.focus();
  panel.view.state.player.cash = 100;
  panel.render();
  assert.equal(requiredElement('[data-action="dispatch"]').hasAttribute("disabled"), true);
  assert.equal(document.activeElement, navigation);
  panel.destroy();
});

test("late panel data is ignored after navigation and destruction", async () => {
  const responses = [];
  const panel = mountPanel(
    (_path, options) =>
      new Promise((resolve) => responses.push({ resolve, signal: options.signal })),
  );
  panel.view.url = new URL("http://test/leaderboard");
  const first = panel.loadDetails();
  panel.selectRoute(new URL("http://test/fleet"));
  assert.equal(responses[0].signal.aborted, true);
  responses[0].resolve({ players: [{ username: "obsolete" }] });
  await first;
  assert.equal(panel.view.rankings, null);
  panel.view.url = new URL("http://test/leaderboard");
  const second = panel.loadDetails();
  panel.destroy();
  responses[1].resolve({ players: [{ username: "disposed" }] });
  await second;
  assert.equal(panel.view.rankings, null);
});

test("late quotes neither replace a new selection nor clear its busy state", async () => {
  const panel = mountPanel();
  const pending = [];
  const actions = new GameActions({
    panel,
    request: (_path, options) =>
      new Promise((resolve) => pending.push({ resolve, signal: options.signal })),
    map: null,
  });
  const first = actions.calculateQuote();
  actions.cancelQuote();
  panel.view.state.contracts.push({ ...contract, id: "new" });
  panel.selectRoute(new URL("http://test/contracts/new"));
  const second = actions.calculateQuote();
  pending[0].resolve(quote);
  await first;
  assert.equal(panel.view.quote, null);
  assert.equal(panel.view.quoting, true);
  assert.equal(pending[0].signal.aborted, true);
  pending[1].resolve({ ...quote, profit_eur: 900 });
  await second;
  assert.equal(panel.view.quote.profit_eur, 900);
  assert.equal(panel.view.quoting, false);
  actions.destroy();
  panel.destroy();
});

test("uncertain write responses refresh server state instead of repeating the write", async () => {
  const panel = mountPanel();
  let writes = 0,
    refreshes = 0;
  const messages = [];
  const actions = new GameActions({
    panel,
    request: async () => {
      writes++;
      throw new Error("lost response");
    },
    notify: (message) => messages.push(message),
    state: {
      afterMutation: async () => {
        refreshes++;
      },
    },
  });
  await actions.handle("buy", "regional");
  assert.equal(writes, 1);
  assert.equal(refreshes, 1);
  assert.deepEqual(messages, ["lost response"]);
  assert.equal(panel.view.busy, false);
  actions.destroy();
  panel.destroy();
});

test("disposed state suppresses late snapshots even when a transport ignores abort", async () => {
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const state = new GameState(async (path) => {
    await gate;
    return path === "/dashboard"
      ? { server_time: 0 }
      : path === "/fleet"
        ? { vehicles: [] }
        : { contracts: [] };
  });
  let changes = 0;
  state.addEventListener("change", () => changes++);
  const pending = state.refresh();
  state.destroy();
  release();
  await pending;
  assert.equal(state.lifetime.signal.aborted, true);
  assert.equal(state.data, null);
  assert.equal(changes, 0);
});

test("polling only runs when visible and eligible, and releases both intervals", () => {
  const page = new EventTarget(),
    browser = new EventTarget();
  page.hidden = false;
  let allowed = true,
    polls = 0,
    ticks = 0;
  const timers = new Map();
  const scheduler = new RefreshScheduler({
    page,
    browser,
    canRefresh: () => allowed,
    refresh: () => {
      polls++;
    },
    updateProgress: () => ticks++,
    timers: {
      setInterval(callback, delay) {
        timers.set(delay, callback);
        return delay;
      },
      clearInterval(id) {
        timers.delete(id);
      },
    },
  });
  scheduler.start();
  scheduler.start();
  assert.equal(timers.size, 2);
  timers.get(10000)();
  timers.get(1000)();
  page.hidden = true;
  timers.get(10000)();
  timers.get(1000)();
  page.hidden = false;
  allowed = false;
  browser.dispatchEvent(new Event("online"));
  allowed = true;
  page.dispatchEvent(new Event("visibilitychange"));
  assert.equal(polls, 2);
  assert.equal(ticks, 1);
  scheduler.destroy();
  browser.dispatchEvent(new Event("online"));
  assert.equal(timers.size, 0);
  assert.equal(polls, 2);
});

test("animation respects reduced motion, visibility and cancellation", () => {
  let next,
    draws = 0,
    hidden = false,
    reduced = false,
    cancelled;
  const animator = new VehicleAnimator({
    draw: () => draws++,
    isActive: () => true,
    isHidden: () => hidden,
    reducedMotion: () => reduced,
    requestFrame: (callback) => {
      next = callback;
      return 1;
    },
    cancelFrame: (id) => {
      cancelled = id;
    },
  });
  animator.start();
  animator.start();
  next(0);
  next(30);
  next(70);
  reduced = true;
  next(200);
  next(1070);
  hidden = true;
  next(2070);
  assert.equal(draws, 3);
  animator.destroy();
  next(3070);
  assert.equal(cancelled, 1);
  assert.equal(draws, 3);
});

test("map projections aggregate locations, discard invalid hubs and remove settled trips", () => {
  const data = new OverlayData();
  data.setHubs([hub, { ...hub, id: "missing", resolution_status: "unavailable", lon: null }]);
  data.update({
    vehicles: [vehicle],
    contracts: [contract, { ...contract, id: "another" }],
    transports: [trip],
  });
  assert.equal(data.hubFeatures().features.length, 1);
  assert.equal(data.locationFeatures(data.state.contracts, "origin_hub_id").features.length, 1);
  assert.deepEqual(data.vehicleFeatures(50).features[0].geometry.coordinates, [180, 0]);
  assert.deepEqual(data.routeFeatures().features[0].geometry.coordinates, [
    [179, 0],
    [181, 0],
  ]);
  assert.equal(data.fleetCoordinates(50).length, 2);
  assert.equal(previewFeatures(quote).features.length, 1);
  assert.equal(previewFeatures(null).features.length, 0);
  data.update({ ...data.state, transports: [] });
  assert.equal(data.routes.size, 0);
  assert.equal(data.vehicleFeatures(200).features.length, 0);
});

test("mobile sheet handles keyboard clicks and a drag without double advancement", () => {
  document.body.replaceChildren(
    html`<section id="panel"><button id="handle">resize</button></section>`,
  );
  const panel = requiredElement("#panel"),
    handle = requiredElement("#handle");
  handle.setPointerCapture = () => {};
  const sheet = new MobileSheet(handle, panel);
  sheet.start();
  handle.click();
  assert.equal(sheet.height, 90);
  sheet.startDrag({ clientY: 100, pointerId: 1 });
  sheet.finishDrag({ clientY: 200, preventDefault() {} });
  handle.click();
  assert.equal(sheet.height, 60);
  handle.click();
  assert.equal(sheet.height, 90);
  sheet.destroy();
  handle.click();
  assert.equal(sheet.height, 90);
});

test("notifications use literal text and release the dismissal timer", () => {
  const toast = document.createElement("div"),
    map = document.createElement("div");
  let callback, cleared;
  const notices = new Notifications(toast, map, {
    setTimeout(fn) {
      callback = fn;
      return 9;
    },
    clearTimeout(id) {
      cleared = id;
    },
  });
  notices.show("<img> hello");
  assert.equal(toast.textContent, "<img> hello");
  assert.equal(toast.children.length, 0);
  callback();
  assert.equal(toast.classList.contains("visible"), false);
  notices.show("offline", "map");
  assert.equal(map.hidden, false);
  notices.destroy();
  assert.equal(cleared, 9);
});

test("router preserves URL history and removes the back-navigation listener", () => {
  const browser = new EventTarget();
  browser.location = { origin: "http://test", href: "http://test/fleet" };
  const visits = [],
    pushes = [];
  browser.history = { pushState: (_state, _title, path) => pushes.push(path) };
  const router = new BrowserRouter(browser, (url) => visits.push(url.pathname));
  router.start();
  router.navigate("/contracts?hub=berlin");
  router.navigate("https://external.test");
  browser.dispatchEvent(new Event("popstate"));
  router.destroy();
  browser.dispatchEvent(new Event("popstate"));
  assert.deepEqual(pushes, ["/contracts?hub=berlin"]);
  assert.deepEqual(visits, ["/contracts", "/fleet"]);
});

test("application disposal releases every component exactly once", () => {
  const released = [];
  const dependencies = Object.fromEntries(
    [
      "api",
      "state",
      "panel",
      "map",
      "actions",
      "sync",
      "router",
      "scheduler",
      "input",
      "sheet",
      "notifications",
    ].map((name) => [name, { destroy: () => released.push(name) }]),
  );
  const app = new GameApplication(dependencies);
  app.destroy();
  app.destroy();
  assert.equal(released.length, 11);
  assert.equal(new Set(released).size, 11);
  assert.equal(released.at(-1), "api");
});

test("all feature views render active, empty, unavailable and shop states", () => {
  const view = createView("/contracts");
  assert.equal(renderPanel(view).querySelectorAll(".job-card").length, 1);
  view.url = new URL("http://test/contracts?hub=missing");
  assert.match(renderPanel(view).textContent, /Keine Aufträge/);
  view.url = new URL("http://test/fleet");
  assert.equal(renderPanel(view).querySelectorAll(".vehicle-card").length, 1);
  view.url = new URL("http://test/fleet?tab=shop");
  assert.match(renderPanel(view).textContent, /werden geladen/);
  view.catalogue = {
    delivery_hub: "Berlin",
    models: [
      {
        id: "regional",
        name: "Regional",
        price_eur: 12000,
        capacity_tons: 12,
        unlock_reputation: 0,
        operating_cost_eur_per_km: 0.49,
        powertrain: "combustion",
      },
    ],
  };
  assert.equal(renderPanel(view).querySelector('[data-action="buy"]').disabled, false);
  view.state.player.cash = 0;
  assert.equal(renderPanel(view).querySelector('[data-action="buy"]').disabled, true);
  view.url = new URL("http://test/transports");
  assert.match(renderPanel(view).textContent, /Die Straße wartet/);
  view.state.transports = [trip];
  view.now = 110;
  assert.match(renderPanel(view).textContent, /Ankunft wird bestätigt/);
  view.url = new URL("http://test/transports/trip");
  assert.equal(renderPanel(view).querySelector('[data-action="focus-trip"]').dataset.id, "trip");
  view.url = new URL("http://test/unknown");
  assert.match(renderPanel(view).textContent, /nicht gefunden/);
});

test("uncertain writes wait for old polls then read a fresh snapshot", async () => {
  const panel = mountPanel();
  let release,
    reads = 0,
    writes = 0;
  const oldPoll = new Promise((resolve) => {
    release = resolve;
  });
  const state = new GameState(async (path) => {
    if (path === "/dashboard") {
      reads++;
      const cash = reads === 1 ? 175000 : 26000;
      if (reads === 1) await oldPoll;
      return { player: { cash }, server_time: Date.now() / 1000 };
    }
    return path === "/fleet" ? { vehicles: [] } : { contracts: [] };
  });
  const actions = new GameActions({
    panel,
    state,
    notify() {},
    request: async () => {
      writes++;
      throw new Error("response lost after commit");
    },
  });
  const poll = state.refresh();
  const mutation = actions.handle("buy", "iveco_sway_500");
  await Promise.resolve();
  assert.equal(reads, 1);
  release();
  await Promise.all([poll, mutation]);
  assert.equal(reads, 2);
  assert.equal(writes, 1);
  assert.equal(state.data.player.cash, 26000);
  actions.destroy();
  state.destroy();
  panel.destroy();
});

test("vehicle changes invalidate pending quotes and preserve the selected vehicle", async () => {
  const panel = mountPanel();
  panel.view.state.vehicles.push({ ...vehicle, id: "second", name: "Second" });
  const pending = [];
  const actions = new GameActions({
    panel,
    map: null,
    notify() {},
    request: (_path, options) => new Promise((resolve) => pending.push({ resolve, options })),
  });
  const first = actions.calculateQuote();
  actions.selectVehicle("second");
  assert.equal(panel.view.quote, null);
  assert.equal(requiredElement('[data-action="dispatch"]').disabled, true);
  const second = actions.calculateQuote();
  assert.deepEqual(JSON.parse(pending[1].options.body), { vehicle_id: "second" });
  pending[0].resolve(quote);
  await first;
  assert.equal(panel.view.quote, null);
  assert.equal(panel.view.quoting, true);
  pending[1].resolve({ ...quote, vehicle_id: "second", operating_cost_eur: 276 });
  await second;
  assert.equal(panel.view.quote.operating_cost_eur, 276);
  assert.equal(requiredElement('[data-action="dispatch"]').disabled, false);
  assert.equal(requiredElement("#vehicle-choice").value, "second");
  actions.destroy();
  panel.destroy();
});

test("catalogue reputations gate offers independently of funds", () => {
  const view = createView("/fleet?tab=shop");
  view.state.player.cash = 500000;
  view.catalogue = {
    delivery_hub: "Berlin",
    models: [
      {
        id: "daf",
        name: "DAF",
        price_eur: 162000,
        capacity_tons: 24.3,
        unlock_reputation: 5,
        operating_cost_eur_per_km: 0.49,
        powertrain: "combustion",
      },
    ],
  };
  const locked = renderPanel(view);
  assert.equal(locked.querySelector('[data-action="buy"]').disabled, true);
  assert.match(locked.textContent, /Reputation reicht nicht/);
  assert.match(locked.textContent, /0,49/);
  view.state.player.reputation = 5;
  assert.equal(renderPanel(view).querySelector('[data-action="buy"]').disabled, false);
});
