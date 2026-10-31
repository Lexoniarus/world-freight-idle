import { expect, openVehicleMarket, register, test } from "./support.js";

test("map controls survive navigation without rebuilding the canvas", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await register(page);
  await page.goto("/fleet");
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
  const originalCanvas = await page.locator(".maplibregl-canvas").elementHandle();
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
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
  await register(page, { waitForMap: false });
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
  await register(page);
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.locator("#panel-content")).toContainText("IVECO");
  release();
  await page.unroute("**/api/v1/map/traffic?representation=summary");
  await expect(page.locator("#cash")).toContainText("175.000");
});
