import { test, expect } from "@playwright/test";
import { readFile, mkdir } from "node:fs/promises";
import { resolve } from "node:path";

/** Serve source modules only inside the intercepted browser test origin. */
async function harness(page) {
  await page.route("**/assets/vehicles/**", async (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: await readFile(resolve(new URL(route.request().url()).pathname.slice(1)), "utf8"),
    }),
  );
  await page.route("**/__modules__/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/__modules__/", "");
    if (path === "maplibre.js")
      return route.fulfill({
        contentType: "text/javascript",
        body: "export const Marker=window.maplibregl.Marker;export const Popup=window.maplibregl.Popup;export const LngLatBounds=window.maplibregl.LngLatBounds;",
      });
    const source = await readFile(resolve(path), "utf8");
    await route.fulfill({
      contentType: "text/javascript",
      body: source.replaceAll('from "maplibre-gl"', 'from "/__modules__/maplibre.js"'),
    });
  });
  await page.route("**/__harness__", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: '<!doctype html><html><head></head><body><div id="map" style="width:100vw;height:100vh"></div></body></html>',
    }),
  );
  await page.goto("/__harness__");
  for (const path of [
    "base.css",
    "controls-and-cards.css",
    "contract-and-progress.css",
    "map-feedback.css",
    "auth.css",
    "vehicle-media.css",
    "workspace.css",
    "responsive.css",
    "catalogue-components.css",
    "presentation-refinements.css",
  ])
    await page.addStyleTag({ path: `frontend/styles/${path}` });
  await page.addStyleTag({ path: "node_modules/maplibre-gl/dist/maplibre-gl.css" });
  await page.evaluate(async () => {
    window.maplibregl = await import("/__modules__/node_modules/maplibre-gl/dist/maplibre-gl.mjs");
    window.maplibregl.setWorkerUrl(
      "/__modules__/node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs",
    );
  });
  await mkdir("artifacts/maplibre-vehicle-groups", { recursive: true });
}
async function setupMap(page) {
  await harness(page);
  await page.evaluate(async () => {
    const { addOverlayLayers } = await import("/__modules__/frontend/map/overlay-layers.js");
    const { VehicleGroups } = await import("/__modules__/frontend/map/vehicle-groups.js");
    const { VehicleColorAssets } = await import("/__modules__/frontend/vehicle-color-assets.js");
    const { VehicleIconRegistry } =
      await import("/__modules__/frontend/map/vehicle-icon-registry.js");
    const map = new window.maplibregl.Map({
      container: "map",
      style: {
        version: 8,
        sources: {},
        layers: [
          { id: "background", type: "background", paint: { "background-color": "#70828c" } },
        ],
      },
      center: [13, 52],
      zoom: 14,
      attributionControl: false,
      canvasContextAttributes: { preserveDrawingBuffer: true },
    });
    await new Promise((resolve) => map.on("load", resolve));
    addOverlayLayers(map);
    const assets = new VehicleColorAssets((path) => fetch(path).then((r) => r.text()));
    const registry = new VehicleIconRegistry(map, (path) => fetch(path).then((r) => r.text()), {
      coloredSource: assets.source.bind(assets),
    });
    await registry.ensure([
      { model_id: "daf_xg_plus_480", player_color: "#4c78a8" },
      { model_id: "daf_xg_plus_480", player_color: "#4c78a8", role: "front" },
    ]);
    const groups = new VehicleGroups(
      map,
      () => {},
      () => false,
    );
    const feature = (id, idle = false) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [13, 52] },
      properties: {
        key: "own:" + id,
        id,
        vehicleId: id,
        isOwn: true,
        idle,
        movementState: idle ? "idle" : "enroute",
        modelId: "daf_xg_plus_480",
        modelName: "DAF XG+",
        bearing: 0,
        playerColor: "#4c78a8",
        hasIcon: true,
        iconImage: "vehicle-daf_xg_plus_480-4c78a8" + (idle ? "-front" : ""),
      },
    });
    window.proof = { map, groups, feature, assets, registry };
    window.drawProof = async (features, selected = "") => {
      const shown = groups.update(features, selected, true);
      for (const [name, own] of [
        ["vehicles", true],
        ["multiplayer-vehicles", false],
      ])
        map.getSource(name).setData({
          type: "FeatureCollection",
          features: shown.filter((f) => f.properties.isOwn === own),
        });
      await new Promise((resolve) => {
        map.once("idle", resolve);
        map.triggerRepaint();
      });
      return shown.map((f) => f.properties.key);
    };
  });
}

test("vehicle group keyboard activation zooms before opening its accessible list", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await setupMap(page);
  await page.evaluate(async () => {
    const { feature } = window.proof;
    await window.drawProof([feature("a"), feature("b")]);
  });
  const group = page.locator(".vehicle-group");
  await group.focus();
  await expect(group).toBeFocused();
  await group.press("Enter");
  await expect.poll(() => page.evaluate(() => window.proof.map.getZoom())).toBe(16);
  await page.locator(".vehicle-group").press("Enter");
  await expect.poll(() => page.evaluate(() => window.proof.map.getZoom())).toBe(17);
  await page.locator(".vehicle-group").press("Enter");
  await expect(page.locator(".map-object-list button")).toHaveCount(2);
  await expect(page.locator(".map-object-list button").first()).toBeFocused();
});
