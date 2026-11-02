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

test("market preserves saved contracts after failure or disposal", async () => {
  const notices = [];
  const saved = { ...offer, id: "saved" };
  const state = {
    data: {
      contracts: [saved],
      vehicles: [{ id: "truck", status: "idle" }],
      transports: [],
    },
    replaceContracts(contracts) {
      this.data.contracts = contracts;
    },
  };
  const currentUrl = () => new URL("http://test/contracts?vehicle=truck");
  let resolve;
  const disposed = new ContractMarketController({
    state,
    api: freightApi(() => new Promise((done) => (resolve = done))),
    notify: (message) => notices.push(message),
    currentUrl,
  });
  disposed.start();
  const pending = disposed.refresh();
  disposed.destroy();
  resolve({ contracts: [offer] });
  await pending;
  assert.deepEqual(state.data.contracts, [saved]);
  const live = new ContractMarketController({
    state,
    api: freightApi(async () => {
      throw new Error("503");
    }),
    notify: (message) => notices.push(message),
    currentUrl,
  });
  live.start();
  await live.refresh();
  assert.deepEqual(state.data.contracts, [saved]);
  assert.equal(notices.at(-1), "503");
  live.destroy();
});

test("market requires an idle reference vehicle before reads or refresh", async () => {
  const paths = [];
  let url = new URL("http://test/contracts");
  const state = {
    data: { contracts: [offer], vehicles: [], transports: [] },
    detail: offer,
    replaceContractDetail(value) {
      this.detail = value;
    },
    replaceContracts(contracts) {
      this.data.contracts = contracts;
    },
  };
  const controller = new ContractMarketController({
    state,
    currentUrl: () => url,
    notify: () => {},
    api: freightApi(async (path) => {
      paths.push(path);
      if (path === "/contracts/removed") throw Object.assign(new Error("removed"), { status: 404 });
      return { contracts: [offer] };
    }),
  });
  controller.start();
  await controller.refresh();
  assert.equal(await controller.forceRefresh(), false);
  assert.deepEqual(paths, []);
  state.data.vehicles = [{ id: "truck", status: "idle" }];
  url = new URL("http://test/contracts?vehicle=truck");
  await controller.refresh();
  assert.equal(await controller.forceRefresh(), true);
  url = new URL("http://test/contracts/removed");
  await controller.refresh();
  assert.deepEqual(state.data.contracts, [offer]);
  assert.equal(state.detail, null);
  controller.destroy();
});
