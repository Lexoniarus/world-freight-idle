import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const testTimeout = process.env.CI ? 15000 : 10000;

export default defineConfig({
  testDir: "./tests/browser",
  outputDir: join(tmpdir(), "world-freight-playwright-results"),
  fullyParallel: false,
  workers: 1,
  timeout: testTimeout,
  expect: { timeout: 8000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8011",
    viewport: { width: 1440, height: 900 },
    channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
    launchOptions: { args: ["--enable-webgl", "--enable-unsafe-swiftshader"] },
  },
  webServer: {
    command: `"${process.env.PYTHON_EXECUTABLE || resolve(process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python")}" -m uvicorn tests.browser_server:app --host 127.0.0.1 --port 8011 --log-level warning`,
    env: { ...process.env, LOG_LEVEL: "WARNING" },
    url: "http://127.0.0.1:8011/api/v1/system/health",
    reuseExistingServer: false,
  },
});
