import test from "node:test";
import assert from "node:assert/strict";
import { originalVehicleSvg, paintPixels } from "./vehicle-paint.js";

test("paint preserves protected colors, alpha and shadow contrast", () => {
  const base = new Uint8ClampedArray([
    240, 240, 240, 255, 100, 100, 100, 255, 35, 40, 45, 255, 250, 250, 250, 0, 200, 200, 200, 128,
  ]);
  const mask = new Uint8ClampedArray([
    255, 255, 255, 255, 255, 255, 255, 255, 0, 0, 0, 255, 255, 255, 255, 255, 128, 128, 128, 255,
  ]);
  const out = paintPixels(base, mask, "#4080c0");
  assert.deepEqual([...out.slice(8, 12)], [35, 40, 45, 255]);
  assert.deepEqual(
    [3, 7, 11, 15, 19].map((index) => out[index]),
    [255, 255, 255, 0, 128],
  );
  assert.ok(out[0] > out[4]);
  assert.ok(out[0] < base[0]);
  assert.ok(out[16] < 200 && out[16] > 100);
  assert.equal(base[0], 240);
  assert.throws(() => paintPixels(base, new Uint8ClampedArray(), "#ffffff"));
});

test("original extraction rejects injected markup and mask rasters", () => {
  const original =
    '<svg width="2" height="3"><defs><mask><image href="data:image/png;base64,TUF"/></mask></defs><image filter="url(#bad)" onload="bad()" href="data:image/png;base64,QUJD"/><script>bad()</script></svg>';
  const result = originalVehicleSvg(original);
  assert.equal(result.width, 2);
  assert.equal(result.height, 3);
  assert.match(result.svg, /QUJD/);
  assert.doesNotMatch(result.svg, /filter|script|onload|TUF/);
  assert.throws(() => originalVehicleSvg("<svg/>"));
  assert.throws(() => originalVehicleSvg('<svg><image href="data:image/png;base64,QUJD"/></svg>'));
});
