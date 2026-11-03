import { test, expect } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { tile } from "./tile.js";

const password = "browser-test-password-42";
const screenshot = (name) => join(tmpdir(), "world-freight-" + name + ".png");
// A tiny local PNG replaces all public tiles. No automated OSM downloads.
let counter = 0;

test.beforeEach(async ({ context, page }) => {
  await page.request.post("/__tests__/preparation-scope");
  await context.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({ contentType: "image/png", body: tile }),
  );
  if (!process.env.REAL_VEHICLE_PHOTO) {
    await context.route("https://upload.wikimedia.org/**", (route) => {
      const headers = route.request().headers();
      expect(headers["x-freight-request"]).toBeUndefined();
      expect(headers.cookie).toBeUndefined();
      expect(headers.referer).toBeUndefined();
      return route.fulfill({
        contentType: "image/png",
        headers: { "access-control-allow-origin": "*" },
        body: tile,
      });
    });
  }
  page.on("pageerror", (error) => {
    throw error;
  });
});

async function waitForAuthenticatedShell(page, waitForMap) {
  await expect(page.locator("#cash")).toContainText("175.000");
  if (!waitForMap) return;
  await expect(page.locator(".maplibregl-canvas")).toBeVisible();
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
}

async function createPlayerSession(
  page,
  { allowMarketPreparation = false, waitForMap = false } = {},
) {
  const username = "driver_" + Date.now().toString(36) + ++counter;
  const response = await page.request.post("/api/v1/auth/register", {
    data: { username, password },
    headers: { "x-freight-request": "1" },
  });
  expect(response.status()).toBe(201);
  if (!allowMarketPreparation) {
    const runtime = await page.request.get("/api/v1/runtime");
    expect(runtime.ok()).toBe(true);
    const paused = await page.request.post("/__tests__/preparation-scope");
    expect(paused.ok()).toBe(true);
  }
  await page.goto("/");
  await waitForAuthenticatedShell(page, waitForMap);
  return username;
}

async function registerThroughUi(page, { waitForMap = false } = {}) {
  const username = "driver_" + Date.now().toString(36) + ++counter;
  await page.goto("/login");
  await expect(page).toHaveTitle(/World Freight/);
  await page.getByRole("button", { name: "Konto erstellen", exact: true }).click();
  await page.getByLabel("Spielername", { exact: true }).fill(username);
  await page.getByLabel("Passwort", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Konto erstellen & losfahren" }).click();
  await waitForAuthenticatedShell(page, waitForMap);
  return username;
}

async function readyContracts(page, vehicleIds = ["truck_01"], matches = () => true) {
  let contracts;
  await expect
    .poll(
      async () => {
        const scopedContracts = await Promise.all(
          vehicleIds.map(async (vehicleId) => {
            const response = await page.request.get(
              "/api/v1/contracts?vehicle_id=" + encodeURIComponent(vehicleId),
            );
            return (await response.json()).contracts;
          }),
        );
        contracts = [
          ...new Map(scopedContracts.flat().map((contract) => [contract.id, contract])).values(),
        ];
        if (vehicleIds.length > 1) {
          contracts = await Promise.all(
            contracts.map(async (contract) => {
              const response = await page.request.get(
                "/api/v1/contracts/" + encodeURIComponent(contract.id),
              );
              return response.json();
            }),
          );
        }
        return contracts.some(
          (item) =>
            matches(item) && vehicleIds.every((id) => item.eligible_vehicle_ids.includes(id)),
        );
      },
      { timeout: 30000 },
    )
    .toBe(true);
  return contracts;
}

async function openEligibleOffer(page, vehicleIds = ["truck_01"], matches = () => true) {
  const contracts = await readyContracts(page, vehicleIds, matches);
  const offer = contracts.find(
    (item) => matches(item) && vehicleIds.every((id) => item.eligible_vehicle_ids.includes(id)),
  );
  expect(offer).toBeTruthy();
  await page.goto("/contracts/" + offer.id + "?vehicle=" + encodeURIComponent(vehicleIds[0]));
  await page.getByLabel("Fahrzeug disponieren").selectOption(vehicleIds[0]);
  return offer;
}

async function openVehicleMarket(page, vehicleId = "truck_01") {
  await readyContracts(page);
  await page.goto("/fleet/" + vehicleId);
  await page.getByRole("link", { name: "Stadtmarkt öffnen" }).click();
}

async function advanceServerTime(page, seconds) {
  const response = await page.request.post(
    "/__tests__/advance-time?seconds=" + encodeURIComponent(seconds),
  );
  expect(response.ok()).toBe(true);
}

async function synchronizeGameState(page) {
  const refreshed = page.waitForResponse((response) => response.url().endsWith("/api/v1/runtime"));
  await page.evaluate(() => window.dispatchEvent(new Event("online")));
  await refreshed;
}

export {
  advanceServerTime,
  createPlayerSession,
  expect,
  openEligibleOffer,
  openVehicleMarket,
  password,
  readyContracts,
  registerThroughUi,
  screenshot,
  synchronizeGameState,
  test,
};
