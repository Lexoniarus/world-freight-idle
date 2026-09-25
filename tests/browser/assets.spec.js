import { test, expect } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { tile } from "./tile.js";

test("fixed asset reference: fleet and shop on desktop and mobile", async ({ page, context }) => {
  await context.route("https://tile.openstreetmap.org/**", route => route.fulfill({contentType: "image/png", body: tile}));
  await page.emulateMedia({reducedMotion: "reduce"});
  await page.goto("/login");
  await page.getByRole("button", {name: "Konto erstellen", exact: true}).click();
  await page.getByLabel("Spielername", {exact: true}).fill("AssetReference");
  await page.getByLabel("Passwort", {exact: true}).fill("asset-test-password-42");
  await page.getByRole("button", {name: "Konto erstellen & losfahren"}).click();
  await expect(page.locator("#world-map")).toHaveAttribute("aria-busy", "false");
  const folder = "artifacts/assets-" + (process.env.ASSET_VISUAL_PHASE || "current");
  await mkdir(folder, {recursive: true});
  for (const [name, viewport] of [["desktop", {width: 1440, height: 900}], ["mobile", {width: 390, height: 844}]]) {
    await page.setViewportSize(viewport);
    for (const [surface, title] of [["fleet", "Flotte"], ["shop", "Fahrzeugshop"]]) {
      const link = page.getByRole("link", {name: title, exact: true}).filter({visible: true}).first();
      if (!(await link.count())) await page.getByRole("button", {name: "Mehr", exact: true}).click();
      await page.getByRole("link", {name: title, exact: true}).filter({visible: true}).first().click();
      const images = page.locator("#panel img[data-local-vehicle-asset]:visible");
      await expect(images.first()).toBeVisible();
      await images.first().evaluate(image => image.decode());
      await expect(images.first()).toHaveAttribute("src", /^blob:/);
      await expect(images.first()).toHaveAttribute("data-vehicle-role", "front");
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({path: `${folder}/${surface}-${name}.png`, animations: "disabled"});
    }
  }
});
