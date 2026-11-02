import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { html, requiredElement } from "./ui/dom.js";

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

test("DOM binding preserves untrusted text without parsing markup", () => {
  const input = '"><img src=x onerror="alert(1)"><script>x</script>';
  const fragment = html`<div title="${input}">
    ${input}${[html`<strong>safe</strong>`, " & text"]}
  </div>`;
  assert.equal(fragment.querySelector("img, script"), null);
  assert.equal(fragment.firstElementChild.getAttribute("title"), input);
  assert.equal(fragment.textContent.trim(), input + "safe & text");
  assert.throws(() => html`<a href="${"javascript:alert(1)"}">bad</a>`, /protocol/);
  assert.throws(() => html`<iframe srcdoc="${input}"></iframe>`, /forbidden/);
  assert.throws(() => requiredElement("#missing"), /Missing element/);
});
