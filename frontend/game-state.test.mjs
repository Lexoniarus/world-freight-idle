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
