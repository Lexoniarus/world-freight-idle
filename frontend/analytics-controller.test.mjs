import test from "node:test";
import assert from "node:assert/strict";
import { AnalyticsController } from "./controllers/analytics-controller.js";

test("analytics publishes only the newest requested scope", async () => {
  const pending = [];
  const panel = {
    view: { url: new URL("http://test/company?days=7") },
    render() {},
  };
  const controller = new AnalyticsController({
    panel,
    request: (path, options) => new Promise((resolve) => pending.push({ resolve, path, options })),
  });
  const first = controller.refresh();
  panel.view.url = new URL("http://test/company?days=90");
  const second = controller.refresh();
  pending[1].resolve({ scope: { type: "company" }, breakdowns: {}, id: "new" });
  await second;
  pending[0].resolve({ scope: { type: "company" }, id: "old" });
  await first;
  assert.equal(panel.view.analytics.id, "new");
  assert.equal(pending[0].options.signal.aborted, true);
  panel.view.url = new URL("http://test/fleet");
  await controller.refresh();
  assert.equal(pending.length, 2);
  controller.destroy();
});
