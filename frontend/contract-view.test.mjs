import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { filterContracts, renderContracts } from "./views/contracts.js";
import { berlin, offer, other, vehicle } from "./test-support/freight-fixtures.mjs";

test("offer filters use server IDs and authoritative eligibility", () => {
  const contracts = [offer, { ...offer, id: "other", origin: other, eligible_vehicle_ids: [] }];
  for (const query of [
    "vehicle=v1",
    "band=short",
    "class=general",
    "cargo=fahrzeug",
    "destination=same",
  ])
    assert.deepEqual(filterContracts(contracts, "a", new URLSearchParams("vehicle=v1&" + query)), [
      offer,
    ]);
  for (const query of ["band=long", "class=parcel", "cargo=steel", "destination=else"])
    assert.deepEqual(
      filterContracts(contracts, "a", new URLSearchParams("vehicle=v1&" + query)),
      [],
    );
});

test("empty market renders partial and exhausted preparation truthfully", () => {
  const base = {
    url: new URL("http://test/contracts"),
    cityUid: "a",
    activeCities: ["a"],
    cities: [berlin],
    marketLoaded: true,
    state: { vehicles: [vehicle], contracts: [], transports: [] },
  };
  for (const [status, message] of [
    ["partial", "Straßenverbindungen werden vorbereitet"],
    ["exhausted", "keine geprüften Straßenverbindungen"],
  ]) {
    const fragment = renderContracts({
      ...base,
      state: { ...base.state, market_preparation: { status } },
    });
    assert.match(fragment.textContent, new RegExp(message));
    assert.equal(fragment.querySelectorAll(".job-card").length, 0);
  }
});

test("vehicle market renders only offers eligible for its reference vehicle", () => {
  const second = { ...vehicle, id: "v2" };
  const contracts = [
    { ...offer, id: "shared", eligible_vehicle_ids: ["v1", "v2"] },
    { ...offer, id: "only-a", eligible_vehicle_ids: ["v1"] },
    { ...offer, id: "only-b", eligible_vehicle_ids: ["v2"] },
    { ...offer, id: "neither", eligible_vehicle_ids: [] },
  ];
  for (const [id, expected] of [
    ["v1", ["shared", "only-a"]],
    ["v2", ["shared", "only-b"]],
  ]) {
    const url = new URL(`http://test/contracts?vehicle=${id}&band=short`);
    const rendered = renderContracts({
      url,
      cityUid: "a",
      activeCities: ["a"],
      cities: [berlin],
      marketLoaded: true,
      state: {
        vehicles: [vehicle, second],
        contracts,
        transports: [],
        market_preparation: { status: "partial" },
      },
    });
    assert.deepEqual(
      filterContracts(contracts, "a", url.searchParams).map((item) => item.id),
      expected,
    );
    assert.equal(rendered.querySelectorAll(".job-card").length, 2);
  }
});
