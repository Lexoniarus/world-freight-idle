import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { html } from "./ui/dom.js";

test("boolean DOM attributes preserve false and true values", () => {
  assert.equal(
    html`<details open="${false}"><summary>Filter</summary></details>`.querySelector("details")
      .open,
    false,
  );
  assert.equal(
    html`<details open="${true}"><summary>Filter</summary></details>`.querySelector("details").open,
    true,
  );
});
