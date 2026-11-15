import { defineConfig, devices, type Project } from "@playwright/test";

import projects from "./tests/browser/projects.json";

// One project per environment, and each runner passes its own with --project (R-58, TWEB-01). The
// spec files of each are listed in tests/browser/projects.json, which tests/harness/test_suite_claims.py
// also reads, and tests/browser/README.md names the runner that arranges each environment.
// A failure keeps its trace and screenshot in the runner's ignored output directory, on the
// disposable stacks only (TWEB-15). The install projects sign in with the persistent owner's real
// password, which a trace would record, and release-latency times what tracing would slow.
const KEPT_ON_FAILURE: ReadonlySet<string> = new Set([
  "web",
  "main",
  "arranged",
  "slice",
]);

function project(name: string, specs: readonly string[]): Project {
  return {
    name,
    testMatch: specs.map((spec) => `**/${spec}`),
    ...(KEPT_ON_FAILURE.has(name)
      ? { use: { trace: "retain-on-failure", screenshot: "only-on-failure" } }
      : {}),
  };
}

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
  projects: Object.entries(projects).map(([name, specs]) =>
    project(name, specs),
  ),
});
