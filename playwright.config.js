import { defineConfig } from "@playwright/test";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const testTimeout = process.env.CI ? 20000 : 10000;
const browserPort = process.env.WFI_BROWSER_PORT || "8011";
const browserOrigin = "http://127.0.0.1:" + browserPort;

export default defineConfig({
  testDir: "./tests/browser",
  outputDir: join(tmpdir(), "world-freight-playwright-results"),
  fullyParallel: false,
  workers: 1,
  timeout: testTimeout,
  expect: { timeout: 8000 },
  reporter: "list",
  use: {
    baseURL: browserOrigin,
    viewport: { width: 1440, height: 900 },
    channel: process.env.PLAYWRIGHT_CHANNEL || "msedge",
    launchOptions: { args: ["--enable-webgl", "--enable-unsafe-swiftshader"] },
  },
  webServer: {
    command: `"${process.env.PYTHON_EXECUTABLE || resolve(process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python")}" -m uvicorn tests.browser_server:app --host 127.0.0.1 --port ${browserPort} --log-level warning`,
    env: { ...process.env, LOG_LEVEL: "WARNING" },
    url: browserOrigin + "/api/v1/system/health",
    reuseExistingServer: false,
  },
});
