import { createPlayerSession, expect, test } from "./support.js";

test("mobile shop recovers from a catalogue failure and preserves focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await createPlayerSession(page);
  await page.route("**/api/v1/fleet/catalogue", (route) =>
    route.fulfill({ status: 503, json: { detail: "Fahrzeugkatalog derzeit nicht verfügbar." } }),
  );
  await page.getByRole("button", { name: "Mehr", exact: true }).click();
  await page.getByRole("link", { name: "Fahrzeugshop", exact: true }).first().click();
  await expect(page.locator("#panel-content")).toContainText("Erneut");
  await page.unroute("**/api/v1/fleet/catalogue");
  await page.locator('[data-action="retry-panel"]').click();
  const catalogue = (await (await page.request.get("/api/v1/fleet/catalogue")).json()).models;
  await expect(page.locator(".shop-card")).toHaveCount(catalogue.length);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("link", { name: "Fahrzeugshop", exact: true }).first()).toBeFocused();
});

test("account layer overrides persist per view and reload", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await createPlayerSession(page);
  const user = await (await page.request.get("/api/v1/auth/me")).json();
  await page.goto("/fleet");
  await page.locator(".layer-menu summary").click();
  await page.getByLabel("Eigene Fahrzeuge", { exact: true }).uncheck();
  await page.getByLabel("Objekte gruppieren", { exact: true }).uncheck();
  const preferences = await page.evaluate(() =>
    Object.fromEntries(
      Object.entries(localStorage).filter(([key]) => key.startsWith("world-freight:layers:")),
    ),
  );
  expect(Object.keys(preferences)).toEqual(["world-freight:layers:v2:" + user.id]);
  await page.getByRole("link", { name: "Unternehmen", exact: true }).click();
  await expect(page.getByLabel("Eigene Fahrzeuge", { exact: true })).toBeChecked();
  await page.getByRole("link", { name: "Flotte", exact: true }).click();
  await expect(page.getByLabel("Eigene Fahrzeuge", { exact: true })).not.toBeChecked();
  await page.getByRole("button", { name: "Ansicht zurücksetzen" }).click();
  await expect(page.getByLabel("Eigene Fahrzeuge", { exact: true })).toBeChecked();
  await expect(page.getByLabel("Objekte gruppieren", { exact: true })).not.toBeChecked();
  await page.reload();
  await page.locator(".layer-menu summary").click();
  await expect(page.getByLabel("Objekte gruppieren", { exact: true })).not.toBeChecked();
});

test("company palette exposes a retry after a failed preference read", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await createPlayerSession(page);
  let failing = true;
  await page.route("**/api/v1/auth/preferences", (route) =>
    failing && route.request().method() === "GET"
      ? route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "offline" }),
        })
      : route.continue(),
  );
  await page.goto("/company");
  await expect(page.getByText("Firmenfarben konnten nicht geladen werden.")).toBeVisible();
  failing = false;
  await page.locator("[data-preference-retry]").click();
  await expect(page.locator("[data-company-color]")).toHaveCount(10);
});
