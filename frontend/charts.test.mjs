import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { renderChart } from "./ui/charts.js";

test("chart exposes its values as an accessible table", () => {
  const chart = renderChart(
    "Finanzen",
    [{ date: "2026-09-25", profit_eur: -20 }],
    [["profit_eur", "Ergebnis"]],
  );
  assert.equal(chart.querySelector("svg").getAttribute("role"), "img");
  assert.match(chart.querySelector("table").textContent, /-20/);
  assert.equal(chart.querySelectorAll("circle").length, 1);
});
