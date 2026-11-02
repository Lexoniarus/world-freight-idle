import {
  advanceServerTime,
  expect,
  openEligibleOffer,
  register,
  synchronizeGameState,
  test,
} from "./support.js";

test("dispatch and settlement render authoritative state", async ({ page }) => {
  const errors = [];
  page.on("console", (message) => {
    if (message.type() === "error")
      errors.push(message.text() + " (" + message.location().url + ")");
  });
  await register(page, { waitForMap: false });
  await expect(page.locator("#map-notice")).toBeHidden();
  const fleetForOffer = (await (await page.request.get("/api/v1/fleet")).json()).vehicles;
  await openEligibleOffer(page, [fleetForOffer[0].id]);
  await page.getByRole("button", { name: "Route & Ertrag berechnen" }).click();
  await expect(page.getByText("Dein Gewinn", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Transport starten" })).toBeEnabled();
  const accepted = page.waitForResponse((response) => response.url().endsWith("/accept"));
  await page.getByRole("button", { name: "Transport starten" }).click();
  const trip = await (await accepted).json();
  await page.goto("/transports/" + trip.id);
  await expect(page.locator("[data-phase-trip]")).toBeVisible();
  await advanceServerTime(page, trip.arrives_at - trip.departed_at + 1);
  await synchronizeGameState(page);
  await expect(page.locator("#reputation")).toHaveText("1");
  await expect(page.locator("#fleet-count")).toHaveText("1");
  expect(errors).toEqual([]);
});
