import test from "node:test";
import assert from "node:assert/strict";
import { GameState, LatestRequest } from "./state.js";
import { offer } from "./test-support/freight-fixtures.mjs";

test("contract detail updates never replace the saved market list", () => {
  const state = new GameState(async () => {});
  state.data = { contracts: [offer] };
  state.replaceContractDetail({ ...offer, id: "detail" });
  assert.equal(state.data.contracts[0], offer);
  state.replaceContractDetail(null, "detail");
  assert.equal(state.contractDetailId, "detail");
  assert.equal(state.data.contracts[0], offer);
  state.destroy();
});

test("destroyed state suppresses late snapshots", async () => {
  let release;
  const paths = [];
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const state = new GameState(async (path) => {
    paths.push(path);
    await gate;
    return { server_time: 0, vehicles: [], transports: [] };
  });
  let changes = 0;
  state.addEventListener("change", () => changes++);
  const pending = state.refresh();
  state.destroy();
  release();
  await pending;
  assert.equal(state.lifetime.signal.aborted, true);
  assert.equal(state.data, null);
  assert.equal(changes, 0);
  assert.deepEqual(paths, ["/runtime"]);
});

test("runtime reads coalesce and mutations schedule one fresh read", async () => {
  let release;
  let reads = 0;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const state = new GameState(async (path) => {
    if (path === "/runtime") {
      reads++;
      await gate;
      return {
        server_time: Date.now() / 1000,
        player: { completed: 0 },
        vehicles: [],
        transports: [],
      };
    }
    return { transports: [] };
  });
  const first = state.refresh();
  assert.equal(first, state.refresh());
  const after = state.afterMutation();
  release();
  await Promise.all([first, after]);

  assert.equal(reads, 2);
  assert.ok(Math.abs(state.now() - Date.now() / 1000) < 1);
  state.destroy();
});

test("failed runtime reads preserve the snapshot and allow retry", async () => {
  const state = new GameState(async () => {
    throw new Error("offline");
  });
  state.data = { player: { cash: 12 } };

  await assert.rejects(state.refresh(), /offline/);

  assert.equal(state.pending, null);
  assert.equal(state.data.player.cash, 12);
  state.destroy();
});

test("latest request aborts and rejects superseded publications", () => {
  const gate = new LatestRequest();
  const first = gate.start();
  const next = gate.start();

  assert.equal(first.signal.aborted, true);
  assert.equal(first.isCurrent(), false);
  assert.equal(next.isCurrent(), true);
  gate.cancel();
});
