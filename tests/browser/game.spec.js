import { test, expect } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { tile } from "./tile.js";

const password = "browser-test-password-42";
const screenshot = (name) => join(tmpdir(), "world-freight-" + name + ".png");
// A tiny local PNG replaces all public tiles. No automated OSM downloads.
let counter = 0;

test.beforeEach(async ({ context, page }) => {
  await context.route("https://tile.openstreetmap.org/**", (route) => route.fulfill({ contentType: "image/png", body: tile }));
  if (!process.env.REAL_VEHICLE_PHOTO) {
    await context.route("https://upload.wikimedia.org/**", route => {
      const headers = route.request().headers();
      expect(headers["x-freight-request"]).toBeUndefined();
      expect(headers.cookie).toBeUndefined();
      expect(headers.referer).toBeUndefined();
      return route.fulfill({contentType: "image/png", headers: {"access-control-allow-origin":"*"}, body: tile});
    });
  }
  page.on("pageerror", (error) => { throw error; });
});

async function register(page) {
  const username = "driver_" + Date.now().toString(36) + (++counter);
  await page.goto("/login");
  await expect(page).toHaveTitle(/World Freight/);
  await page.getByRole("button", { name: "Konto erstellen", exact: true }).click();
  await page.getByLabel("Spielername", { exact: true }).fill(username);
  await page.getByLabel("Passwort", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Konto erstellen & losfahren" }).click();
  await expect(page.locator("#cash")).toContainText("175.000");
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
  return username;
}

test("desktop: registration, map, quote, dispatch, purchase, arrival, logout and login", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  const username = await register(page);
  await expect(page.locator("#map-notice")).toBeHidden();
  await page.screenshot({ animations: "disabled", path: screenshot("desktop") });
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await page.locator(".job-card").filter({ hasText: "Lkw bereit" }).first().click();
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  await expect(page.getByText("Dein Gewinn", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeEnabled();
  await page.screenshot({ animations: "disabled", path: screenshot("dispatch") });
  await page.getByRole("button", { name: "Transport starten" }).click();
  await expect(page).toHaveURL(/transports\//);
  await expect(page.getByText("Transport läuft", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Fahrzeugshop", exact: true }).first().click();
  await page.locator(".shop-card").filter({ hasText: "S-Way" }).getByRole("button", { name: "Fahrzeug kaufen" }).click();
  await expect(page.locator("#fleet-count")).toHaveText("2");
  await page.keyboard.press("Escape");
  await expect(page.locator("#panel")).toBeHidden();
  await page.goBack();
  await expect(page.locator("#panel")).toBeVisible();
  // The accelerated, server-authoritative test trip arrives after 16 seconds.
  await expect(page.locator("#reputation")).toHaveText("1", { timeout: 35000 });
  const cash = await page.locator("#cash").textContent();
  await page.getByRole("button", { name: "Abmelden" }).click();
  await expect(page).toHaveURL(/login/);
  await page.getByLabel("Spielername", { exact: true }).fill(username);
  await page.getByLabel("Passwort", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Anmelden", exact: true }).last().click();
  await expect(page.locator("#cash")).toHaveText(cash);
  await expect(page.locator("#fleet-count")).toHaveText("2");
  await expect(page.locator("#reputation")).toHaveText("1");
  expect(errors).toEqual([]);
});

test("mobile: sheets, navigation, keyboard and attribution stay usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await register(page);
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.locator("#panel-title")).toHaveText("Deine Flotte");
  await expect(page.locator("#panel-title")).toBeFocused();
  await page.screenshot({ animations: "disabled", path: screenshot("mobile") });
  const first = await page.locator("#panel").boundingBox();
  await page.getByRole("button", { name: "Panelhöhe ändern" }).click();
  const larger = await page.locator("#panel").boundingBox();
  expect(larger.height).toBeGreaterThan(first.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await expect(page.getByRole("link", { name: "OpenStreetMap", exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.locator("#panel")).toBeHidden();
  await expect(page.getByRole("link", { name: "Flotte", exact: true })).toBeFocused();
  await page.goto("/fleet?tab=shop");
  const catalogue = (await (await page.request.get("/api/v1/fleet/catalogue")).json()).models;
  expect(catalogue.length).toBeGreaterThanOrEqual(8);
  await expect(page.locator(".shop-card")).toHaveCount(catalogue.length);
  await page.getByRole("link", { name: "Rangliste", exact: true }).click();
  await expect(page.locator(".rankings li.you")).toBeVisible();
});

test("stale quote cannot overwrite a new panel; failures and session expiry are visible", async ({ page }) => {
  await register(page);
  await page.route("**/api/v1/contracts/*/quote", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.fulfill({ status: 502, contentType: "application/json", body: JSON.stringify({ detail: "Routing ist offline." }) }).catch(() => {});
  });
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await page.locator(".job-card").first().click();
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.locator("#panel-title")).toHaveText("Deine Flotte");
  await expect(page.getByText("Dein Gewinn", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await page.locator(".job-card").first().click();
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  await expect(page.locator("#toasts")).toContainText("Routing ist offline");
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeDisabled();
  await page.route("**/api/v1/dashboard", (route) => route.fulfill({ status: 401, contentType: "application/json", body: '{"detail":"Bitte anmelden."}' }));
  await page.reload();
  await expect(page).toHaveURL(/login/);
});

test("parallel trips persist across navigation and map controls work without rebuilding the canvas", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await register(page);
  const headers = { "X-Freight-Request": "1" };
  const purchase = await page.request.post("/api/v1/fleet/purchase", { headers, data: { model_id: "iveco_sway_500" } });
  expect(purchase.ok()).toBeTruthy();
  const fleet = (await (await page.request.get("/api/v1/fleet")).json()).vehicles;
  for (const vehicle of fleet) {
    await page.request.post("/api/v1/contracts/refresh", { headers });
    const contracts = (await (await page.request.get("/api/v1/contracts")).json()).contracts;
    const contract = contracts.find((item) => item.origin_hub_id === vehicle.hub_id && item.tons <= vehicle.capacity_tons);
    const dispatch = await page.request.post("/api/v1/contracts/" + contract.id + "/accept", { headers, data: { vehicle_id: vehicle.id } });
    expect(dispatch.ok()).toBeTruthy();
  }
  await page.goto("/transports");
  await expect(page.locator(".job-card")).toHaveCount(2);
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
  const originalCanvas = await page.locator(".maplibregl-canvas").elementHandle();
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  expect(await originalCanvas.evaluate((element) => element.isConnected)).toBeTruthy();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Flotte zentrieren" }).click();
  const before = await page.locator(".maplibregl-canvas").screenshot();
  await page.locator(".maplibregl-ctrl-zoom-out").click();
  const after = await page.locator(".maplibregl-canvas").screenshot();
  expect(Buffer.compare(before, after)).not.toBe(0);
  await page.locator(".layer-menu summary").click();
  await page.getByLabel("Transportrouten", { exact: true }).uncheck();
  await expect(page.getByLabel("Transportrouten", { exact: true })).not.toBeChecked();
  await page.keyboard.press("Escape");
});

test("missing fleet coordinates and tile outages preserve the playable lists", async ({ page, context }) => {
  await context.route("https://tile.openstreetmap.org/**", (route) => route.abort());
  await page.route("**/api/v1/fleet", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    for (const vehicle of data.vehicles) {
      vehicle.hub = { ...vehicle.hub, lat: null, lon: null, resolution_status: "unavailable" };
      if (vehicle.location_snapshot)
        vehicle.location_snapshot = {
          ...vehicle.location_snapshot,
          lat: null,
          lon: null,
          resolution_status: "unavailable",
        };
    }
    await route.fulfill({ json: data });
  });
  await register(page);
  await expect(page.locator("#map-notice")).toBeVisible();
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.getByText("IVECO S-Way 500 XC13", { exact: true })).toBeVisible();
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await expect(page.locator(".job-card").first()).toBeVisible();
});


test("DB vehicle selection changes costs, dispatches and settles after relogin", async ({ page }) => {
  const username = await register(page);
  await page.getByRole("link", { name: "Fahrzeugshop", exact: true }).first().click();
  const catalogue = (await (await page.request.get("/api/v1/fleet/catalogue")).json()).models;
  expect(catalogue.length).toBeGreaterThanOrEqual(8);
  await expect(page.locator(".shop-card")).toHaveCount(catalogue.length);
  await expect(page.locator(".shop-card").filter({ hasText: "DAF" }).getByRole("button")).toBeDisabled();
  await page.screenshot({ animations: "disabled", path: screenshot("catalogue-desktop") });
  await page.locator(".shop-card").filter({ hasText: "Renault" }).getByRole("button", { name: "Fahrzeug kaufen" }).click();
  await expect(page.locator("#cash")).toContainText("21.000");
  await expect(page.locator("#fleet-count")).toHaveText("2");
  const vehicles = (await (await page.request.get("/api/v1/fleet")).json()).vehicles;
  const purchased = vehicles.find(vehicle => vehicle.model_id === "renault_t_high_520");
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await page.locator(".job-card").filter({ hasText: "Lkw bereit" }).first().click();
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeEnabled();
  await page.getByLabel("Fahrzeug disponieren").selectOption(purchased.id);
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeDisabled();
  const response = page.waitForResponse(response => response.url().endsWith("/quote") && response.request().postDataJSON()?.vehicle_id === purchased.id);
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  const quote = await (await response).json();
  expect(quote.operating_cost_eur_per_km).toBe(purchased.operating_cost_eur_per_km);
  expect(quote.operating_cost_eur).toBe(Math.round(80 + 400 * purchased.operating_cost_eur_per_km));
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeEnabled();
  await page.getByRole("button", { name: "Transport starten" }).click();
  await expect(page).toHaveURL(/transports\//);
  await page.getByRole("button", { name: "Abmelden" }).click();
  await expect(page).toHaveURL(/login/);
  // Test server accelerates a four-hour route to 16 seconds.
  await page.waitForTimeout(17000);
  await page.getByLabel("Spielername", { exact: true }).fill(username);
  await page.getByLabel("Passwort", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Anmelden", exact: true }).last().click();
  await expect(page.locator("#reputation")).toHaveText("1");
  const dashboard = await (await page.request.get("/api/v1/dashboard")).json();
  expect(dashboard.player.cash).toBe(21000 - quote.operating_cost_eur + quote.payout_eur);
  expect(dashboard.transports).toHaveLength(0);
});

test("mobile DB shop preserves focus, shows failure and supports purchase", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await register(page);
  await page.route("**/api/v1/fleet/catalogue", route => route.fulfill({ status: 503, json: { detail: "Fahrzeugkatalog derzeit nicht verfügbar." } }));
  await page.getByRole("link", { name: "Fahrzeugshop", exact: true }).first().click();
  await expect(page.locator("#panel-content")).toContainText("Erneut");
  await page.unroute("**/api/v1/fleet/catalogue");
  await page.locator('[data-action="retry-panel"]').click();
  const catalogue = (await (await page.request.get("/api/v1/fleet/catalogue")).json()).models;
  expect(catalogue.length).toBeGreaterThanOrEqual(8);
  await expect(page.locator(".shop-card")).toHaveCount(catalogue.length);
  await page.screenshot({ animations: "disabled", path: screenshot("catalogue-mobile") });
  await page.locator(".shop-card").filter({ hasText: "S-Way" }).getByRole("button", { name: "Fahrzeug kaufen" }).click();
  await expect(page.locator("#fleet-count")).toHaveText("2");
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("link", { name: "Fahrzeugshop", exact: true }).first()).toBeFocused();
});


test("two independent profiles stay isolated and local vehicle assets are deterministic", async ({ page, browser }) => {
  await register(page);
  const second = await browser.newContext({ viewport: { width: 1024, height: 1366 }, isMobile: true, hasTouch: true, baseURL: "http://127.0.0.1:8011" });
  await second.route("https://tile.openstreetmap.org/**", route => route.fulfill({ contentType: "image/png", body: tile }));
  await second.route("https://upload.wikimedia.org/**", route => route.abort());
  const ipad = await second.newPage();
  try {
    await register(ipad);
    const headers = { "X-Freight-Request": "1" };
    await page.goto("/fleet?tab=shop");
    const offer = page.locator(".shop-card").filter({ hasText: "S-Way" });
    await offer.scrollIntoViewIfNeeded();
    await expect(offer.locator("figure")).toHaveClass(/vehicle-game-asset/);
    await expect(offer.locator("img[data-local-vehicle-asset]")).toHaveCount(2);
    await expect(offer.locator("figcaption")).toContainText("Spielgrafik");
    await offer.getByRole("button", { name: "Fahrzeug kaufen" }).click();
    await expect(page.locator("#fleet-count")).toHaveText("2");
    const purchased = (await (await page.request.get("/api/v1/fleet")).json()).vehicles.find(v => v.id !== "truck_01");
    expect((await ipad.request.get("/api/v1/fleet/" + purchased.id)).status()).toBe(404);
    const dashboard = await (await ipad.request.get("/api/v1/dashboard")).json();
    expect(dashboard.player.cash).toBe(175000);
    expect(dashboard.idle_vehicles).toBe(1);
    await page.goto("/fleet");
    await expect(page.locator(".vehicle-card").filter({ hasText: "S-Way" }).first().locator("img[data-local-vehicle-asset]")).toHaveCount(2);
    await ipad.goto("/fleet?tab=shop");
    const ipadOffer = ipad.locator(".shop-card").first();
    await expect(ipadOffer.locator("img[data-local-vehicle-asset]")).toHaveCount(2);
    await expect(ipadOffer.locator("[data-image-state]")).toHaveCount(0);
    const response = await ipad.request.post("/api/v1/fleet/purchase", { headers, data: { model_id: "iveco_sway_500" } });
    expect(response.status()).toBe(201);
    await ipad.reload();
    await expect(ipad.locator("#fleet-count")).toHaveText("2");
  } finally {
    await second.close();
  }
});


test("starter game assets survive polling and changed transport panel content", async ({ page }) => {
  await register(page);
  const vehicles = (await (await page.request.get("/api/v1/fleet")).json()).vehicles;
  expect(vehicles[0].model_id).toBe("iveco_sway_500");
  expect(vehicles[0].operating_cost_eur_per_km).toBe(0.51);
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  const figure = page.locator(".vehicle-photo").first();
  await expect(figure).toHaveClass(/vehicle-game-asset/);
  await expect(figure.locator("img[data-local-vehicle-asset]")).toHaveCount(2);
  await expect(figure.locator("img").first()).toHaveAttribute("src", "/assets/vehicles/iveco_sway_500/front.svg");
  await page.waitForResponse(response => response.url().endsWith("/api/v1/fleet"), { timeout: 15000 });
  await expect(figure.locator("img[data-local-vehicle-asset]")).toHaveCount(2);
  const headers = { "X-Freight-Request": "1" };
  const contracts = (await (await page.request.get("/api/v1/contracts")).json()).contracts;
  const contract = contracts.find(item => item.origin_hub_id === vehicles[0].hub_id && item.tons <= vehicles[0].capacity_tons);
  const response = await page.request.post("/api/v1/contracts/" + contract.id + "/accept", { headers, data: { vehicle_id: vehicles[0].id } });
  expect(response.ok()).toBeTruthy();
  await expect(page.locator(".vehicle-card .badge")).toHaveText("Unterwegs", { timeout: 15000 });
  await expect(figure.locator("img[data-local-vehicle-asset]")).toHaveCount(2);
});

test("facility identities, lazy market scope and catalogue outages preserve the game", async ({ page }) => {
  await register(page);
  const response = await page.request.get("/api/v1/map/facilities?bbox=13,52,14,53");
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  expect(result.unavailable_count).toBe(0);
  const berlin = result.facilities.find(f => f.aliases.includes("berlin_westhafen"));
  expect(berlin.facility_uid).toMatch(/^[0-9a-f-]{36}$/);
  expect(berlin.facility_id).toBeUndefined();
  expect(berlin.company_uid).toBe(berlin.company.company_uid);
  expect(berlin.company.company_id).toBeUndefined();
  expect(berlin.company.display_name).toBeTruthy();
  expect(berlin.company.legal_name).toBeTruthy();
  expect(berlin.company.country).toBeTruthy();
  expect(berlin.coordinate_evidence.length).toBeGreaterThan(0);
  expect(berlin.resolution_status).toBe("resolved");

  const allResult = await (await page.request.get("/api/v1/map/facilities")).json();
  expect(allResult.unavailable_count).toBe(0);
  expect(allResult.facilities).toHaveLength(352);

  const localJobs = (await (await page.request.get("/api/v1/contracts")).json()).contracts;
  expect(new Set(localJobs.map(job => job.origin_facility_uid))).toEqual(new Set([berlin.facility_uid]));
  expect(localJobs.every(job => job.market_model === "nhm_v1")).toBeTruthy();
  expect(localJobs.every(job => ["documented", "derived"].includes(job.cargo_basis))).toBeTruthy();
  expect(localJobs.every(job => job.cargo_evidence)).toBeTruthy();

  const viewportJobs = (await (await page.request.get("/api/v1/contracts?bbox=8,48,15,54&zoom=7")).json()).contracts;
  expect(new Set(viewportJobs.map(job => job.origin_facility_uid)).size).toBeGreaterThan(1);

  await page.goto("/contracts?hub=berlin_westhafen");
  const originalCanvas = await page.locator(".maplibregl-canvas").elementHandle();
  await expect(page.locator(".job-card").first()).toContainText("Berlin Westhafen");
  await page.locator(".job-card").first().click();
  await expect(page.locator(".footnote").first()).toContainText("Geschäftsbeziehung, Menge und Auftrag simuliert");
  expect(await originalCanvas.evaluate(element => element.isConnected)).toBeTruthy();

  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await page.route("**/api/v1/contracts?*", route => route.fulfill({
    status: 503,
    json: { detail: "Weltkatalog derzeit nicht verfügbar." },
  }));
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await expect(page.locator("#toasts")).toContainText("Weltkatalog derzeit nicht verfügbar");
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.locator(".vehicle-card")).toContainText("Berlin Westhafen");
});
