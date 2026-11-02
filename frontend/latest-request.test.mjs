import test from "node:test";
import assert from "node:assert/strict";
import { LatestRequest } from "./latest-request.js";

test("starting a request aborts and invalidates its predecessor", () => {
  const requests = new LatestRequest();
  const first = requests.start();
  const second = requests.start();

  assert.equal(first.signal.aborted, true);
  assert.equal(first.isCurrent(), false);
  assert.equal(second.signal.aborted, false);
  assert.equal(second.isCurrent(), true);
});

test("cancelling a request prevents its completion from publishing", () => {
  const requests = new LatestRequest();
  const current = requests.start();

  requests.cancel();

  assert.equal(current.signal.aborted, true);
  assert.equal(current.isCurrent(), false);
});
