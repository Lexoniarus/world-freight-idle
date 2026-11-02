import { expect, register, screenshot, test } from "./support.js";

test("fleet and shop render their local vehicle asset", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await register(page);
  for (const [surface, title] of [
    ["fleet", "Flotte"],
    ["shop", "Fahrzeugshop"],
  ]) {
    await page
      .getByRole("navigation", { name: "Spielnavigation" })
      .getByRole("link", { name: title, exact: true })
      .click();
    const image = page.locator("#panel img[data-local-vehicle-asset]:visible").first();
    await expect(image).toBeVisible();
    await expect(image).toHaveAttribute("src", /^blob:/);
    await expect(image).toHaveAttribute("data-vehicle-role", "front");
    await expect.poll(() => image.evaluate((node) => node.naturalWidth > 0)).toBe(true);
    await page.screenshot({
      path: screenshot(`assets-${surface}-desktop`),
      animations: "disabled",
    });
  }
});
