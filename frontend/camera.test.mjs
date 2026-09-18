import test from "node:test";
import assert from "node:assert/strict";
import { MapCamera, shiftRoute, frameFleet } from "./map/camera.js";

test("route framing preserves continuity at the camera antipode and across the dateline", () => {
  for (const [points, reference, expectedSpan] of [
    [
      [
        [10, 53],
        [13, 52],
      ],
      -168,
      3,
    ],
    [
      [
        [179, 0],
        [181, 0],
      ],
      0,
      2,
    ],
    [
      [
        [179, 0],
        [181, 0],
      ],
      720,
      2,
    ],
  ]) {
    let result, options;
    const map = {
      getCenter: () => ({ lng: reference }),
      fitBounds: (bounds, config) => {
        result = bounds.toArray();
        options = config;
      },
    };
    new MapCamera(
      map,
      () => true,
      () => ({ width: 1440, height: 900, panelOpen: true }),
    ).fitRoute(points);
    assert.equal(result[1][0] - result[0][0], expectedSpan);
    assert.equal(options.duration, 0);
    assert.equal(options.padding.right, 470);
  }
});

test("fleet framing selects the minimum circular interval and supports empty and single positions", () => {
  const points = frameFleet(
    [
      [179, 1],
      [-179, 2],
      [178, 3],
    ],
    720,
  );
  assert.equal(Math.max(...points.map((p) => p[0])) - Math.min(...points.map((p) => p[0])), 3);
  assert.deepEqual(frameFleet([], 0), []);
  assert.deepEqual(shiftRoute([], 0), []);
  assert.deepEqual(frameFleet([[10, 20]], 370), [[370, 20]]);
  let calls = 0;
  const map = {
    getCenter: () => ({ lng: 0 }),
    fitBounds: (_bounds, options) => {
      calls++;
      assert.equal(options.padding.bottom, 480);
    },
  };
  const camera = new MapCamera(
    map,
    () => false,
    () => ({ width: 390, height: 844, panelOpen: true }),
  );
  camera.fitCoordinates([]);
  camera.fitCoordinates([[10, 20]]);
  assert.equal(calls, 1);
});
