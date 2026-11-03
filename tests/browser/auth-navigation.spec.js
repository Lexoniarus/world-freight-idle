import {
  createPlayerSession,
  expect,
  openEligibleOffer,
  registerThroughUi,
  screenshot,
  test,
} from "./support.js";

test("registration remains usable while the map renderer is delayed", async ({ page }) => {
  let release;
  const blocked = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/world-map-*.js", async (route) => {
    await blocked;
    await route.continue();
  });
  try {
    await registerThroughUi(page);
    await page.getByRole("link", { name: "Flotte", exact: true }).click();
    await expect(page.locator("#panel .vehicle-card").first()).toBeVisible();
    await expect(page.locator(".maplibregl-canvas")).toHaveCount(0);
    await page.getByLabel("Fahrzeugname").fill("missing-model");
    await expect(page.locator("#panel .vehicle-card")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
});

test("mobile sheet navigation, keyboard and attribution stay usable", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await createPlayerSession(page, { waitForMap: true });
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
});

test("routing failure stays visible and keeps dispatch disabled", async ({ page }) => {
  await createPlayerSession(page, { allowMarketPreparation: true });
  await page.route("**/api/v1/contracts/*/quote", (route) =>
    route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Routing ist offline." }),
    }),
  );
  await page.getByRole("link", { name: "Aufträge", exact: true }).click();
  await openEligibleOffer(page);
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  await expect(page.locator("#toasts")).toContainText("Routing ist offline");
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeDisabled();
});
