import { defineConfig, devices } from "@playwright/test";

// Run through scripts/qualify_web.py, which starts real local services and passes their addresses.
export default defineConfig({
  testDir: "./tests/browser",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: true,
  reporter: [
    [
      "json",
      {
        outputFile: process.env.AUTOBOTS_WEB_REPORT ?? "playwright-report.json",
      },
    ],
    ["line"],
  ],
  outputDir: process.env.AUTOBOTS_WEB_OUTPUT ?? "test-results",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.AUTOBOTS_WEB_URL ?? "http://127.0.0.1:3000",
  },
});
