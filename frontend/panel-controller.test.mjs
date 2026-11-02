import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { requiredElement } from "./ui/dom.js";
import { contract, mountPanel, quote, vehicle } from "./test-support/controller-fixtures.mjs";

test("panel preserves focused controls across authoritative rendering", () => {
  const panel = mountPanel();
  const select = requiredElement("#vehicle-choice");
  select.value = vehicle.id;
  panel.view.selectedVehicle = vehicle.id;
  select.focus();
  panel.view.quote = quote;
  panel.render();
  assert.equal(document.activeElement.id, "vehicle-choice");
  assert.equal(document.activeElement.value, vehicle.id);
  assert.equal(requiredElement('[data-action="dispatch"]').disabled, false);
  panel.view.state.player.cash = 100;
  panel.render();
  assert.equal(requiredElement('[data-action="dispatch"]').disabled, true);
  panel.destroy();
});

test("panel ignores data returned after navigation or destruction", async () => {
  const responses = [];
  const panel = mountPanel(
    (_path, options) =>
      new Promise((resolve) => responses.push({ resolve, signal: options.signal })),
  );
  panel.view.url = new URL("http://test/leaderboard");
  const first = panel.loadDetails();
  panel.selectRoute(new URL("http://test/fleet"));
  assert.equal(responses[0].signal.aborted, true);
  responses[0].resolve({ players: [{ username: "obsolete" }] });
  await first;
  assert.equal(panel.view.rankings, null);
  panel.view.url = new URL("http://test/leaderboard");
  const second = panel.loadDetails();
  panel.destroy();
  responses[1].resolve({ players: [{ username: "disposed" }] });
  await second;
  assert.equal(panel.view.rankings, null);
});

test("incompatible explicit vehicle requires a deliberate replacement", () => {
  const panel = mountPanel();
  panel.view.state.contracts = [contract];
  panel.selectRoute(new URL("http://test/contracts/job?vehicle=too-small"));
  assert.equal(panel.view.selectedVehicle, "");
  assert.equal(document.querySelector('[data-action="quote"]').disabled, true);
  assert.match(panel.content.textContent, /nicht geeignet/);
  panel.view.selectedVehicle = vehicle.id;
  panel.render();
  assert.equal(document.querySelector('[data-action="quote"]').disabled, false);
  panel.destroy();
});
