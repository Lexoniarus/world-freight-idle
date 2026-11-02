import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { renderTransports } from "./views/transports.js";
import { trip, vehicle } from "./test-support/controller-fixtures.mjs";

test("transport view distinguishes empty, arrived and selected states", () => {
  const state = { transports: [], vehicles: [vehicle] };
  assert.match(
    renderTransports({ state, url: new URL("http://test/transports"), now: 0 }).textContent,
    /Die Straße wartet/,
  );
  state.transports = [trip];
  assert.match(
    renderTransports({ state, url: new URL("http://test/transports"), now: 110 }).textContent,
    /Ankunft wird bestätigt/,
  );
  assert.equal(
    renderTransports({
      state,
      url: new URL("http://test/transports/trip"),
      now: 50,
    }).querySelector('[data-action="focus-trip"]').dataset.id,
    "trip",
  );
});
