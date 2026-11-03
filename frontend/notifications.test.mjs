import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { Notifications } from "./controllers/notifications.js";

test("notifications use literal text and own their dismissal timer", () => {
  const toast = document.createElement("div");
  const map = document.createElement("div");
  let callback;
  let cleared;
  const notices = new Notifications(toast, map, {
    setTimeout(fn) {
      callback = fn;
      return 9;
    },
    clearTimeout(id) {
      cleared = id;
    },
  });
  notices.show("<img> hello");
  assert.equal(toast.textContent, "<img> hello");
  assert.equal(toast.children.length, 0);
  callback();
  notices.show("offline", "map");
  assert.equal(map.hidden, false);
  notices.destroy();
  assert.equal(cleared, 9);
});
