import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { MobileSheet } from "./controllers/mobile-sheet.js";
import { html, requiredElement } from "./ui/dom.js";

test("mobile sheet handles keyboard clicks and one drag", () => {
  document.body.replaceChildren(
    html`<section id="panel"><button id="handle">resize</button></section>`,
  );
  const panel = requiredElement("#panel");
  const handle = requiredElement("#handle");
  handle.setPointerCapture = () => {};
  const sheet = new MobileSheet(handle, panel);
  sheet.start();
  handle.click();
  assert.equal(sheet.height, 90);
  sheet.startDrag({ clientY: 100, pointerId: 1 });
  sheet.finishDrag({ clientY: 200, preventDefault() {} });
  handle.click();
  assert.equal(sheet.height, 60);
  sheet.destroy();
  handle.click();
  assert.equal(sheet.height, 60);
});
