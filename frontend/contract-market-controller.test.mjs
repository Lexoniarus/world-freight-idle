import test from "node:test";
import assert from "node:assert/strict";
import { ContractMarketController } from "./controllers/contract-market-controller.js";
import { GameState } from "./state.js";
import { freightApi, offer } from "./test-support/freight-fixtures.mjs";

test("market list and detail publish independently", async () => {
  const state = new GameState(async () => {});
  state.data = {
    contracts: [],
    vehicles: [{ id: "truck", status: "idle" }],
    transports: [],
  };
  let url = new URL("http://test/contracts?vehicle=truck");
  const requests = [];
  const market = new ContractMarketController({
    state,
    api: freightApi((path) => new Promise((resolve) => requests.push({ path, resolve }))),
    notify: () => {},
    currentUrl: () => url,
  });
  market.start();
  const list = market.refresh();
  requests[0].resolve({ contracts: [offer] });
  await list;
  assert.equal(state.data.contracts[0], offer);
  url = new URL("http://test/contracts/one");
  const first = market.refresh();
  url = new URL("http://test/contracts/two");
  const second = market.refresh();
  requests
    .find((row) => row.path === "/contracts/two")
    .resolve({
      ...offer,
      id: "two",
    });
  await second;
  requests
    .find((row) => row.path === "/contracts/one")
    .resolve({
      ...offer,
      id: "one",
    });
  await first;
  assert.equal(state.contractDetail.id, "two");
  assert.equal(state.data.contracts[0], offer);
  market.destroy();
  state.destroy();
});
