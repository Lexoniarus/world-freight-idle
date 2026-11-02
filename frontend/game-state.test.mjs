import test from "node:test";
import assert from "node:assert/strict";
import { GameState } from "./state.js";
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
