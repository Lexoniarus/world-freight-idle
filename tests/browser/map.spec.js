import { createPlayerSession, expect, openVehicleMarket, test } from "./support.js";

test("map instance survives in-app navigation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await createPlayerSession(page, { waitForMap: true });
  const canvas = page.locator(".maplibregl-canvas");
  await canvas.evaluate((element) => {
    element.dataset.browserTestIdentity = "persistent-map";
  });
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.locator("#panel-title")).toHaveText("Deine Flotte");
  await expect(canvas).toHaveAttribute("data-browser-test-identity", "persistent-map");
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await expect(page.locator("#panel-title")).toHaveText("Stadtmarkt");
  await expect(canvas).toHaveAttribute("data-browser-test-identity", "persistent-map");
  await page.locator(".maplibregl-ctrl-zoom-out").click();
  await expect(canvas).toHaveAttribute("data-browser-test-identity", "persistent-map");
});

test("missing fleet coordinates and tile outages preserve the playable lists", async ({
  page,
  context,
}) => {
  await context.route("https://tile.openstreetmap.org/**", (route) => route.abort());
  await page.route("**/api/v1/runtime", async (route) => {
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
  await createPlayerSession(page, { allowMarketPreparation: true });
  await expect(page.locator("#map-notice")).toBeVisible();
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.getByRole("link", { name: "IVECO S-Way 500 XC13", exact: true })).toBeVisible();
  await openVehicleMarket(page);
  await expect(page.locator(".job-card").first()).toBeVisible();
});

test("runtime remains usable while shared traffic is blocked", async ({ page }) => {
  let release;
  const blocked = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/map/traffic?representation=summary", async (route) => {
    await blocked;
    await route.fulfill({ json: { transports: [] } }).catch(() => {});
  });
  await createPlayerSession(page);
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.locator("#panel-content")).toContainText("IVECO");
  release();
  await page.unroute("**/api/v1/map/traffic?representation=summary");
  await expect(page.locator("#cash")).toContainText("175.000");
});
