import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { renderShop } from "./views/shop.js";
import { vehicle } from "./test-support/controller-fixtures.mjs";

const model = {
  id: "daf",
  name: "DAF",
  price_eur: 162000,
  capacity_tons: 24.3,
  unlock_reputation: 5,
  operating_cost_eur_per_km: 0.49,
  maintenance_eur_per_1000_km: 80,
  powertrain: "combustion",
  energy: vehicle.energy,
  top_speed_kmh: 90,
};

test("shop distinguishes loading, reputation and available funds", () => {
  assert.match(
    renderShop({ catalogue: null, state: {}, busy: false }).textContent,
    /werden geladen/,
  );
  const state = { player: { cash: 500000, reputation: 0 } };
  const catalogue = { delivery_hub: "Berlin", models: [model] };
  const locked = renderShop({ catalogue, state, busy: false });
  assert.equal(locked.querySelector('[data-action="buy"]').disabled, true);
  assert.match(locked.textContent, /Reputation reicht nicht/);
  state.player.reputation = 5;
  assert.equal(
    renderShop({ catalogue, state, busy: false }).querySelector('[data-action="buy"]').disabled,
    false,
  );
  state.player.cash = 0;
  assert.match(renderShop({ catalogue, state, busy: false }).textContent, /Guthaben reicht nicht/);
});
