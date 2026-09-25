import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { PreferencesController } from "./controllers/preferences-controller.js";
import { renderCompanyPreferences } from "./ui/company-preferences.js";

test("preference queue previews immediately, serializes writes and rolls back failed final save", async () => {
  const responses = [];
  const panel = {
    view: { user: { company_color: "#e45756" }, companyPalette: ["#e45756", "#4c78a8", "#54a24b"] },
    render() {},
  };
  const controller = new PreferencesController({
    panel,
    map: null,
    notify() {},
    request: (_path, options) =>
      new Promise((resolve, reject) => responses.push({ resolve, reject, options })),
  });
  const first = controller.save("#4c78a8");
  assert.equal(panel.view.user.company_color, "#4c78a8");
  await controller.save("#54a24b");
  assert.equal(panel.view.user.company_color, "#54a24b");
  assert.equal(responses.length, 1);
  responses[0].resolve({ company_color: "#4c78a8" });
  await new Promise((r) => setTimeout(r, 0));
  assert.equal(responses.length, 2);
  assert.equal(panel.view.user.company_color, "#54a24b");
  responses[1].reject(new Error("offline"));
  await first;
  assert.equal(panel.view.user.company_color, "#4c78a8");
  assert.equal(panel.view.preferenceSaveError, true);
  controller.destroy();
});

test("palette renders explicit loading, error retry and all accessible selected swatches", () => {
  const view = { user: { company_color: "#4c78a8" }, state: { vehicles: [] } };
  const container = document.createElement("div");
  container.append(renderCompanyPreferences(view));
  assert.match(container.textContent, /Farben werden geladen/);
  view.preferenceStatus = "error";
  container.replaceChildren(renderCompanyPreferences(view));
  assert.ok(container.querySelector("[data-preference-retry]"));
  assert.match(container.textContent, /konnten nicht geladen/);
  view.preferenceStatus = "ready";
  view.companyPalette = ["#4c78a8", ...Array.from({ length: 9 }, (_, i) => "#00000" + i)];
  container.replaceChildren(renderCompanyPreferences(view));
  assert.equal(container.querySelectorAll("[data-company-color]").length, 10);
  assert.equal(container.querySelectorAll('[aria-pressed="true"]').length, 1);
  assert.equal(container.querySelector("details"), null);
});
