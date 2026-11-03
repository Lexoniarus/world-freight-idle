import test from "node:test";
import assert from "node:assert/strict";
import { RefreshScheduler } from "./controllers/refresh-scheduler.js";

test("scheduler polls only while visible and releases its intervals", () => {
  const page = new EventTarget();
  const browser = new EventTarget();
  page.hidden = false;
  let allowed = true;
  let polls = 0;
  let ticks = 0;
  const timers = new Map();
  const scheduler = new RefreshScheduler({
    page,
    browser,
    canRefresh: () => allowed,
    refresh: () => polls++,
    updateProgress: () => ticks++,
    timers: {
      setInterval(callback, delay) {
        timers.set(delay, callback);
        return delay;
      },
      clearInterval(id) {
        timers.delete(id);
      },
    },
  });
  scheduler.start();
  scheduler.start();
  timers.get(10000)();
  timers.get(1000)();
  page.hidden = true;
  timers.get(10000)();
  page.hidden = false;
  allowed = false;
  browser.dispatchEvent(new Event("online"));
  allowed = true;
  page.dispatchEvent(new Event("visibilitychange"));
  assert.equal(polls, 2);
  assert.equal(ticks, 1);
  scheduler.destroy();
  assert.equal(timers.size, 0);
});
