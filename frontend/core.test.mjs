import "./test-dom.mjs";
import test from "node:test";
import assert from "node:assert/strict";
import { prepareRoute, routePosition, nearestLongitude, eligibleVehicles } from "./geometry.js";
import { GameState, LatestRequest } from "./state.js";
import { BasemapProvider, createBasemap } from "./map/provider.js";
import { renderPanel } from "./panels.js";

test("short antimeridian route and nearest world copy remain continuous", () => {
  const route = prepareRoute([
    [179, 0],
    [-179, 0],
  ]);
  assert.deepEqual(route.points, [
    [179, 0],
    [181, 0],
  ]);
  assert.deepEqual(routePosition(route, 0.5), [180, 0]);
  assert.equal(nearestLongitude(-179, 540), 541);
  assert.deepEqual(routePosition(route, 2), [181, 0]);
  assert.deepEqual(routePosition(route, -1), [179, 0]);
  assert.equal(routePosition(prepareRoute([]), 0.5), null);
  assert.deepEqual(
    routePosition(
      prepareRoute([
        [1, 2],
        [1, 2],
      ]),
      0.5,
    ),
    [1, 2],
  );
});

test("route interpolation uses distance, not vertex count", () => {
  const route = prepareRoute([
    [0, 0],
    [1, 0],
    [4, 0],
  ]);
  assert.ok(Math.abs(routePosition(route, 0.5)[0] - 2) < 1e-6);
});

test("dispatch choices use server eligibility rather than duplicating market rules", () => {
  const base = { id: "valid", hub_id: "berlin", capacity_tons: 24, mode: "truck", status: "idle" };
  const fleet = [
    base,
    { ...base, id: "busy", status: "enroute" },
    { ...base, id: "small", capacity_tons: 2 },
    { ...base, id: "elsewhere", hub_id: "hamburg" },
    { ...base, id: "rail", mode: "rail" },
  ];
  assert.deepEqual(
    eligibleVehicles(fleet, { eligible_vehicle_ids: ["valid"] }).map((v) => v.id),
    ["valid"],
  );
});

test("polls coalesce and a mutation always causes a fresh subsequent read", async () => {
  let release;
  let reads = 0;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const state = new GameState(async (path) => {
    if (path === "/dashboard") {
      reads++;
      await gate;
      return { server_time: Date.now() / 1000, player: { completed: 0 } };
    }
    return path === "/fleet" ? { vehicles: [] } : { contracts: [] };
  });
  const first = state.refresh();
  assert.equal(first, state.refresh());
  const after = state.afterMutation();
  release();
  await Promise.all([first, after]);
  assert.equal(reads, 2);
  assert.ok(Math.abs(state.now() - Date.now() / 1000) < 1);
});

test("failed refresh preserves last server snapshot and allows retry", async () => {
  const state = new GameState(async () => {
    throw new Error("offline");
  });
  state.data = { player: { cash: 12 } };
  await assert.rejects(state.refresh(), /offline/);
  assert.equal(state.pending, null);
  assert.equal(state.data.player.cash, 12);
});

test("outdated detail requests abort and cannot publish results", () => {
  const gate = new LatestRequest();
  const first = gate.start();
  const next = gate.start();
  assert.equal(first.signal.aborted, true);
  assert.equal(first.isCurrent(), false);
  assert.equal(next.isCurrent(), true);
});

test("raster providers replace URLs and attribution without changing overlays", () => {
  const source = createBasemap({}).style().sources.basemap;
  assert.equal(source.tiles[0], "https://tile.openstreetmap.org/{z}/{x}/{y}.png");
  const custom = new BasemapProvider({
    tiles: ["/local/{z}/{x}/{y}"],
    attribution: "Test",
    maxZoom: 12,
  });
  assert.equal(custom.style().sources.basemap.attribution, "Test");
  assert.equal(custom.style().sources.basemap.maxzoom, 12);
});

test("ranking names are escaped and finished transports are not presented as active", () => {
  const state = { transports: [] };
  const ranking = renderPanel({
    url: new URL("http://test/leaderboard"),
    state,
    rankings: [{ username: "<script>x</script>", completed: 2 }],
    user: { username: "x" },
  });
  assert.ok(ranking.textContent.includes("<script>x</script>"));
  assert.equal(ranking.querySelector("script"), null);
  const finished = renderPanel({ url: new URL("http://test/transports/old"), state });
  assert.ok(finished.textContent.includes("nicht mehr aktiv"));
});
