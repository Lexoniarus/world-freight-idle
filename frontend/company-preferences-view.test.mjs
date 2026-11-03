import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { renderCompanyPreferences } from "./ui/company-preferences.js";

test("palette renders loading, retry and accessible selected swatches", () => {
  const view = { user: { company_color: "#4c78a8" }, state: { vehicles: [] } };
  const container = document.createElement("div");
  container.append(renderCompanyPreferences(view));
  assert.match(container.textContent, /Farben werden geladen/);
  view.preferenceStatus = "error";
  container.replaceChildren(renderCompanyPreferences(view));
  assert.ok(container.querySelector("[data-preference-retry]"));
  assert.match(container.textContent, /konnten nicht geladen/);
  view.preferenceStatus = "ready";
  view.companyPalette = ["#4c78a8", ...Array.from({ length: 9 }, (_, index) => "#00000" + index)];
  container.replaceChildren(renderCompanyPreferences(view));
  assert.equal(container.querySelectorAll("[data-company-color]").length, 10);
  assert.equal(container.querySelectorAll('[aria-pressed="true"]').length, 1);
  assert.equal(container.querySelector("details"), null);
});
