import test from "node:test";
import assert from "node:assert/strict";
import { BrowserRouter } from "./navigation.js";

test("router owns same-origin history and its popstate listener", () => {
  const browser = new EventTarget();
  browser.location = { origin: "http://test", href: "http://test/fleet" };
  const visits = [];
  const pushes = [];
  browser.history = { pushState: (_state, _title, path) => pushes.push(path) };
  const router = new BrowserRouter(browser, (url) => visits.push(url.pathname));
  router.start();
  router.navigate("/contracts?hub=berlin");
  router.navigate("https://external.test");
  browser.dispatchEvent(new Event("popstate"));
  router.destroy();
  browser.dispatchEvent(new Event("popstate"));
  assert.deepEqual(pushes, ["/contracts?hub=berlin"]);
  assert.deepEqual(visits, ["/contracts", "/fleet"]);
});
