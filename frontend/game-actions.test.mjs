import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { GameActions } from "./controllers/game-actions.js";
import { GameState } from "./game-state.js";
import { requiredElement } from "./ui/dom.js";
import {
  contract,
  freightApi,
  mountPanel,
  quote,
  vehicle,
} from "./test-support/controller-fixtures.mjs";

test("late quote cannot replace a newer vehicle selection", async () => {
  const panel = mountPanel();
  panel.view.state.vehicles.push({ ...vehicle, id: "second", name: "Second" });
  panel.view.state.contracts = [{ ...contract, eligible_vehicle_ids: ["truck", "second"] }];
  const pending = [];
  const actions = new GameActions({
    panel,
    map: null,
    notify() {},
    api: freightApi(
      (_path, options) => new Promise((resolve) => pending.push({ resolve, options })),
    ),
  });
  const first = actions.calculateQuote();
  actions.selectVehicle("second");
  const second = actions.calculateQuote();
  pending[0].resolve(quote);
  await first;
  assert.equal(panel.view.quote, null);
  assert.equal(panel.view.quoting, true);
  pending[1].resolve({ ...quote, vehicle_id: "second", operating_cost_eur: 276 });
  await second;
  assert.equal(panel.view.quote.operating_cost_eur, 276);
  assert.equal(requiredElement("#vehicle-choice").value, "second");
  actions.destroy();
  panel.destroy();
});

test("uncertain write refreshes state without repeating the mutation", async () => {
  const panel = mountPanel();
  let writes = 0;
  let refreshes = 0;
  const messages = [];
  const actions = new GameActions({
    panel,
    api: freightApi(async () => {
      writes++;
      throw new Error("lost response");
    }),
    notify: (message) => messages.push(message),
    state: { afterMutation: async () => refreshes++ },
  });
  await actions.handle("buy", "regional");
  assert.equal(writes, 1);
  assert.equal(refreshes, 1);
  assert.deepEqual(messages, ["lost response"]);
  actions.destroy();
  panel.destroy();
});

test("mutation waits for an old poll before publishing its fresh read", async () => {
  const panel = mountPanel();
  let release;
  let reads = 0;
  const oldPoll = new Promise((resolve) => (release = resolve));
  const state = new GameState(async (path) => {
    if (path !== "/runtime") return { transports: [] };
    reads++;
    if (reads === 1) await oldPoll;
    return {
      player: { cash: reads === 1 ? 175000 : 26000 },
      server_time: Date.now() / 1000,
      vehicles: [],
      transports: [],
    };
  });
  let writes = 0;
  const actions = new GameActions({
    panel,
    state,
    notify() {},
    api: freightApi(async () => {
      writes++;
      throw new Error("response lost after commit");
    }),
  });
  const poll = state.refresh();
  const mutation = actions.handle("buy", "iveco_sway_500");
  await Promise.resolve();
  assert.equal(reads, 1);
  release();
  await Promise.all([poll, mutation]);
  assert.equal(reads, 2);
  assert.equal(writes, 1);
  assert.equal(state.data.player.cash, 26000);
  actions.destroy();
  state.destroy();
  panel.destroy();
});

test("dispatch follows its trip unless newer navigation already won", async () => {
  for (const navigated of [false, true]) {
    const panel = mountPanel();
    panel.view.quote = quote;
    panel.render();
    const paths = [];
    const actions = new GameActions({
      panel,
      api: freightApi(async () => ({ id: "started" })),
      notify() {},
      navigate: (path) => paths.push(path),
      state: {
        afterMutation: async () => {
          if (navigated) panel.view.url = new URL("http://test/fleet");
          else panel.view.url.searchParams.set("city", "");
        },
      },
    });
    await actions.dispatchTransport();
    assert.deepEqual(paths, navigated ? [] : ["/transports/started"]);
    actions.destroy();
    panel.destroy();
  }
});
