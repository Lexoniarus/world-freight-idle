import {
  expect,
  openVehicleMarket,
  readyContracts,
  register,
  screenshot,
  test,
} from "./support.js";

test("city offers survive pan and zoom without market requests", async ({ page }) => {
  await page.clock.install();
  await register(page);
  await openVehicleMarket(page);
  await expect(page.locator(".job-card").first()).toBeVisible();
  await page.clock.pauseAt(await page.evaluate(() => Date.now() + 1000));
  const requests = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/v1/contracts"))
      requests.push(request.url());
  });
  const before = await page.locator(".job-card").allTextContents();
  await page.locator(".maplibregl-ctrl-zoom-out").click();
  await page.mouse.move(500, 400);
  await page.mouse.down();
  await page.mouse.move(650, 400, { steps: 5 });
  await page.mouse.up();
  await page.clock.runFor(1200);
  expect(requests).toEqual([]);
  expect(await page.locator(".job-card").allTextContents()).toEqual(before);
  await expect(page.locator(".job-card").first()).toContainText(/ca\. .*km/);
  await page.screenshot({ path: screenshot("market-v2-desktop"), animations: "disabled" });
  await page.locator(".job-card").first().click();
  await expect(page.locator("#panel-content")).toContainText("Warenwert");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.clock.runFor(100);
  await page.screenshot({ path: screenshot("market-v2-mobile"), animations: "disabled" });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
});

test("vehicle market shows only eligible offers and switches shared city vehicles", async ({
  page,
}) => {
  await register(page);
  await expect(page.locator("#current-city-label")).toHaveCount(0);
  await expect(page).not.toHaveURL(/city=/);
  const fleet = await (await page.request.get("/api/v1/fleet")).json();
  const vehicle = fleet.vehicles[0];
  const offers = await readyContracts(page);
  const second = { ...vehicle, id: "vehicle-second", name: "Second city truck" };
  const shared = { ...offers[0], id: "shared", eligible_vehicle_ids: [vehicle.id, second.id] };
  const onlyFirst = { ...offers[0], id: "only-first", eligible_vehicle_ids: [vehicle.id] };
  const onlySecond = { ...offers[0], id: "only-second", eligible_vehicle_ids: [second.id] };
  const neither = { ...offers[0], id: "neither", eligible_vehicle_ids: [] };
  await page.route("**/api/v1/runtime", async (route) =>
    route.fulfill({
      json: { ...(await (await route.fetch()).json()), vehicles: [vehicle, second] },
    }),
  );
  await page.route(/\/api\/v1\/contracts(?:\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        contracts: [shared, onlyFirst, onlySecond, neither],
        preparation: { status: "partial" },
      },
    }),
  );
  await page.goto("/fleet/" + vehicle.id);
  await page.getByRole("link", { name: "Stadtmarkt öffnen" }).click();
  await expect(page).toHaveURL(/vehicle=truck_01/);
  await expect(page.locator('[data-filter="city"]')).toHaveCount(0);
  await expect(page.locator(".job-card")).toHaveCount(2);
  await expect(page.locator('a.job-card[href*="/contracts/shared?"]')).toBeVisible();
  await expect(page.locator('a.job-card[href*="/contracts/only-first?"]')).toBeVisible();
  await expect(page.locator('a.job-card[href*="/contracts/only-second?"]')).toHaveCount(0);
  await expect(page.locator('a.job-card[href*="/contracts/neither?"]')).toHaveCount(0);
  await expect(page.getByText(/nicht geeignet/)).toHaveCount(0);
  await expect(page.getByText(/Straßenverbindungen werden vorbereitet/)).toBeVisible();
  await page.locator('[data-filter="vehicle"]').selectOption(second.id);
  await expect(page).toHaveURL(/vehicle=vehicle-second/);
  await expect(page.locator(".job-card")).toHaveCount(2);
  await expect(page.locator('a.job-card[href*="/contracts/only-second?"]')).toBeVisible();
  await expect(page.locator('a.job-card[href*="/contracts/only-first?"]')).toHaveCount(0);
  await expect(page.locator(".opportunity-marker")).toContainText("2 Aufträge");
  await page.screenshot({ path: screenshot("vehicle-ready-market"), animations: "disabled" });
  await page.locator('[data-filter="vehicle"]').selectOption("");
  await expect(page.locator(".job-card")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Fahrzeug wählen" })).toBeVisible();
  await page.getByRole("link", { name: "Weltkarte", exact: true }).click();
  await expect(page).not.toHaveURL(/city=|vehicle=/);
  await expect(page.locator("#panel")).toBeHidden();
});
