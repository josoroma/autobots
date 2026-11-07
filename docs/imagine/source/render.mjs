// Render the Studio concept screens to PNG in both themes.
// Usage (repo root): node docs/imagine/source/render.mjs [screen-id ...]
// Uses the web app's pinned Playwright (no install) and its cached Chromium.
import { createRequire } from "node:module";
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..", "..");
const require = createRequire(join(repo, "apps", "web", "package.json"));
const { chromium } = require("@playwright/test");

const only = process.argv.slice(2);
const screens = readdirSync(here)
  .filter((f) => /^\d\d-.*\.html$/.test(f))
  .map((f) => f.replace(/\.html$/, ""))
  .filter((id) => only.length === 0 || only.includes(id));

// Prefer an explicit browser (CHROME_PATH), then any cached Chrome for Testing build.
import { existsSync } from "node:fs";
import { homedir } from "node:os";
function cachedChrome() {
  const cache = join(homedir(), "Library", "Caches", "ms-playwright");
  if (!existsSync(cache)) return undefined;
  for (const dir of readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse()) {
    const exe = join(cache, dir, "chrome-mac-arm64", "Google Chrome for Testing.app", "Contents", "MacOS", "Google Chrome for Testing");
    if (existsSync(exe)) return exe;
  }
}
const executablePath = process.env.CHROME_PATH || cachedChrome();
const browser = await chromium.launch(executablePath ? { executablePath } : {});
const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
for (const id of screens) {
  for (const theme of ["dark", "light"]) {
    const url = `${pathToFileURL(join(here, `${id}.html`)).href}?theme=${theme}`;
    await page.goto(url, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(250);
    const out = join(here, "..", theme === "dark" ? `${id}.png` : `${id}-light.png`);
    await page.screenshot({ path: out });
    console.log(out.replace(repo + "/", ""));
  }
}
await browser.close();
