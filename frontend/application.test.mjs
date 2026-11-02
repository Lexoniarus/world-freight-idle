import test from "node:test";
import assert from "node:assert/strict";
import { GameApplication } from "./application.js";

test("application releases every owned component exactly once", () => {
  const released = [];
  const dependencies = Object.fromEntries(
    [
      "api",
      "state",
      "panel",
      "map",
      "actions",
      "sync",
      "router",
      "scheduler",
      "input",
      "sheet",
      "notifications",
    ].map((name) => [name, { destroy: () => released.push(name) }]),
  );
  const app = new GameApplication(dependencies);
  app.destroy();
  app.destroy();
  assert.equal(released.length, 11);
  assert.equal(new Set(released).size, 11);
  assert.equal(released.at(-1), "api");
});
