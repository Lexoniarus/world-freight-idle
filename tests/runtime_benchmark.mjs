import { chromium } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tile } from "./browser/tile.js";

const session = JSON.parse(await readFile(process.argv[2], "utf8"));
const browser = await chromium.launch({channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
  args: ["--enable-webgl", "--enable-unsafe-swiftshader"]});
try {
  const profiles = [];
  for (const [index, token] of session.tokens.entries()) {
    const context = await browser.newContext({viewport: {width: 1440, height: 900}});
    await context.addCookies([{name: "freight_session", value: token, url: "http://127.0.0.1:8027"}]);
    await context.route("https://tile.openstreetmap.org/**", route => route.fulfill({contentType:"image/png", body:tile}));
    await context.route("https://upload.wikimedia.org/**", route => route.fulfill({contentType:"image/png", body:tile}));
    const page = await context.newPage();
    await page.addInitScript(() => {
      window.benchmarkLongTasks = [];
      new PerformanceObserver(list => {
        for (const entry of list.getEntries())
          window.benchmarkLongTasks.push({start_ms: entry.startTime, duration_ms: entry.duration});
      }).observe({type: "longtask", buffered: true});
    });
    const errors = [], geometry = new Map(), requests = new Map(), timings = [];
    page.on("pageerror", error => errors.push(error.message));
    page.on("request", request => {
      requests.set(request, performance.now());
      if(request.url().includes("/map/routes/")) geometry.set(request.url(), (geometry.get(request.url()) ?? 0) + 1);
    });
    page.on("requestfinished", request => {
      const path = new URL(request.url()).pathname;
      if(path.startsWith("/api/v1/") && !path.includes("/map/routes/"))
        timings.push({path, start_ms: Math.round(requests.get(request) - start), duration_ms: Math.round(performance.now() - requests.get(request))});
    });
    const start = performance.now();
    await page.goto("http://127.0.0.1:8027/fleet", {waitUntil:"domcontentloaded"});
    await page.locator("#panel .vehicle-card").first().waitFor();
    const playable = performance.now() - start;
    const startup = await page.evaluate(() => ({
      navigation: performance.getEntriesByType("navigation").map(entry => entry.toJSON()),
      resources: performance.getEntriesByType("resource").filter(entry => entry.startTime < 3000).map(entry => ({name: new URL(entry.name).pathname, start_ms: entry.startTime, duration_ms: entry.duration})),
      long_tasks: window.benchmarkLongTasks,
    }));
    await page.waitForTimeout(22000);
    profiles.push({profile: index + 1, playable_ms: Math.round(playable), startup, unique_geometry_downloads: geometry.size,
      repeated_geometry_downloads: [...geometry.values()].filter(count => count > 1).length, page_errors:errors, requests:timings});
    for(const [name,width,height] of [["desktop",1440,900],["mobile",390,844],["tablet",1024,768]]) {
      await page.setViewportSize({width,height});
      await page.screenshot({path:join(session.output,`profile-${index + 1}-${name}.png`)});
    }
    await context.close();
  }
  const report = {playable_ms: Math.max(...profiles.map(profile => profile.playable_ms)), profiles,
    unique_geometry_downloads: profiles.reduce((total, profile) => total + profile.unique_geometry_downloads, 0),
    repeated_geometry_downloads: profiles.reduce((total, profile) => total + profile.repeated_geometry_downloads, 0),
    page_errors: profiles.flatMap(profile => profile.page_errors)};
  await writeFile(join(session.output,"browser.json"),JSON.stringify(report,null,2));
  if(report.page_errors.length || report.repeated_geometry_downloads) throw new Error("Browser acceptance failed");
} finally {
  await browser.close();
}
