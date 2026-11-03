import test from "node:test";
import assert from "node:assert/strict";
import { RasterBasemapProvider, createRasterBasemap } from "./map/provider.js";

test("raster providers replace URLs and attribution without changing overlays", () => {
  const source = createRasterBasemap({}).style().sources.basemap;
  assert.equal(source.tiles[0], "https://tile.openstreetmap.org/{z}/{x}/{y}.png");

  const custom = new RasterBasemapProvider({
    tiles: ["/local/{z}/{x}/{y}"],
    attribution: "Test",
    maxZoom: 12,
  });
  assert.equal(custom.style().sources.basemap.attribution, "Test");
  assert.equal(custom.style().sources.basemap.maxzoom, 12);
});
