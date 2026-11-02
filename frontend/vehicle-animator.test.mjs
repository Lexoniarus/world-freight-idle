import test from "node:test";
import assert from "node:assert/strict";
import { VehicleAnimator } from "./map/vehicle-animator.js";

test("animation respects reduced motion, visibility and cancellation", () => {
  let next;
  let draws = 0;
  let hidden = false;
  let reduced = false;
  let cancelled;
  const animator = new VehicleAnimator({
    draw: () => draws++,
    isActive: () => true,
    isHidden: () => hidden,
    reducedMotion: () => reduced,
    requestFrame: (callback) => {
      next = callback;
      return 1;
    },
    cancelFrame: (id) => (cancelled = id),
  });
  animator.start();
  animator.start();
  next(0);
  next(30);
  next(70);
  reduced = true;
  next(200);
  next(1070);
  hidden = true;
  next(2070);
  assert.equal(draws, 3);
  animator.destroy();
  next(3070);
  assert.equal(cancelled, 1);
  assert.equal(draws, 3);
});
