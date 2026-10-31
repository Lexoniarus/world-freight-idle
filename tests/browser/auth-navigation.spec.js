import { expect, openEligibleOffer, register, screenshot, test } from "./support.js";

test("fleet controls work while the map renderer module is delayed", async ({ page }) => {
  await register(page);
  let release;
  const blocked = new Promise((resolve) => {
    release = resolve;
  });
  await page.route("**/world-map-*.js", async (route) => {
    await blocked;
    await route.continue();
  });
  try {
    await page.goto("/fleet", { waitUntil: "domcontentloaded" });
    await expect(page.locator("#panel .vehicle-card").first()).toBeVisible();
    await expect(page.locator(".maplibregl-canvas")).toHaveCount(0);
    await page.getByLabel("Fahrzeugname").fill("missing-model");
    await expect(page.locator("#panel .vehicle-card")).toHaveCount(0);
  } finally {
    release();
  }
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
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
  if (!(await page.getByRole("link", { name: "Rangliste", exact: true }).isVisible()))
    await page.getByRole("button", { name: "Mehr", exact: true }).click();
  await page.getByRole("link", { name: "Rangliste", exact: true }).click();
  await expect(page.locator(".rankings li.you")).toBeVisible();
});

test("routing failure stays visible and keeps dispatch disabled", async ({ page }) => {
  await register(page);
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
