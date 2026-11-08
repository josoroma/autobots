import { readFileSync } from "node:fs";
import { join } from "node:path";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type BrowserContext, type Page } from "@playwright/test";

const LUMA = readFileSync(
  join(__dirname, "../../../../docs/design/luma.css"),
  "utf8",
);
const SCREENSHOTS =
  process.env.AUTOBOTS_WEB_SCREENSHOTS ?? "test-results/screenshots";
const SEEN = `
  window.__seen = [];
  const record = () => {
    const root = document.documentElement;
    if (root && document.body) {
      window.__seen.push({ root: root.className, background: getComputedStyle(document.body).backgroundColor });
    }
    if (!window.__stopSeen) requestAnimationFrame(record);
  };
  requestAnimationFrame(record);
`;

function tokens(selector: string): Record<string, string> {
  const start = LUMA.indexOf(`${selector} {`);
  const block = LUMA.slice(start, LUMA.indexOf("}", start));
  return Object.fromEntries(
    [...block.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map((match) => [
      match[1],
      match[2]?.trim(),
    ]),
  );
}

async function visit(page: Page, path = "/"): Promise<void> {
  await page.addInitScript(SEEN);
  await page.goto(path);
  await page.waitForLoadState("networkidle");
}

async function seen(
  page: Page,
): Promise<{ root: string; background: string }[]> {
  return page.evaluate(
    () =>
      (window as unknown as { __seen: { root: string; background: string }[] })
        .__seen,
  );
}

async function expectConsistent(
  page: Page,
  theme: "dark" | "light",
): Promise<void> {
  const frames = await seen(page);
  expect(frames.length).toBeGreaterThan(0);
  const expected = theme === "dark" ? "dark" : "light";
  for (const frame of frames) {
    expect(frame.root).toContain(expected);
    expect(frame.root).not.toContain(theme === "dark" ? "light" : "dark");
  }
  expect(new Set(frames.map((frame) => frame.background)).size).toBe(1);
}

function failOnHydrationProblem(page: Page): string[] {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      /hydrat|did not match/i.test(message.text())
    )
      problems.push(message.text());
  });
  return problems;
}

async function setStored(
  context: BrowserContext,
  value: string,
): Promise<void> {
  await context.addInitScript(
    (stored) => window.localStorage.setItem("autobots.theme", stored),
    value,
  );
}

for (const colorScheme of ["light", "dark"] as const) {
  test(`fresh visit renders dark with a ${colorScheme} operating system`, async ({
    browser,
  }) => {
    const context = await browser.newContext({ colorScheme });
    const page = await context.newPage();
    const problems = failOnHydrationProblem(page);
    await visit(page);
    await expectConsistent(page, "dark");
    expect(problems).toEqual([]);
    await page.screenshot({
      path: `${SCREENSHOTS}/first-visit-dark-os-${colorScheme}.png`,
      fullPage: true,
    });
    await context.close();
  });
}

test("the server's HTML is already dark, before any script runs", async ({
  browser,
}) => {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    colorScheme: "light",
  });
  const page = await context.newPage();
  await page.goto("/");
  expect(await page.locator("html").getAttribute("class")).toContain("dark");
  const colors = await page.locator("body").evaluate((body) => {
    const probe = document.createElement("div");
    probe.style.backgroundColor = "oklch(0.145 0 0)";
    body.append(probe);
    const wanted = getComputedStyle(probe).backgroundColor;
    probe.remove();
    return { actual: getComputedStyle(body).backgroundColor, wanted };
  });
  expect(colors.actual).toBe(colors.wanted);
  await context.close();
});

test("the consumed tokens render exactly as the canonical file says, in both modes", async ({
  page,
}) => {
  await visit(page);
  for (const [selector, theme] of [
    [":root", "light"],
    [".dark", "dark"],
  ] as const) {
    await page.evaluate((next) => {
      document.documentElement.className = next;
    }, theme);
    const expected = { ...tokens(":root"), ...tokens(selector) };
    expect(Object.keys(expected).length).toBeGreaterThan(30);
    // The build may re-serialize a color, so each is compared as the browser resolves it.
    const differences = await page.evaluate((all) => {
      const resolve = (value: string): string => {
        const probe = document.createElement("div");
        probe.style.backgroundColor = value;
        document.body.append(probe);
        const color = getComputedStyle(probe).backgroundColor;
        probe.remove();
        return color;
      };
      return Object.entries(all).flatMap(([name, value]) => {
        if (name === "--radius") {
          const actual = getComputedStyle(document.documentElement)
            .getPropertyValue(name)
            .trim();
          const same =
            actual.endsWith("rem") &&
            parseFloat(actual) === parseFloat(value as string);
          return same ? [] : [`${name}: ${actual} != ${value}`];
        }
        const actual = resolve(`var(${name})`);
        const wanted = resolve(value as string);
        return actual === wanted && wanted !== ""
          ? []
          : [`${name}: ${actual} != ${wanted}`];
      });
    }, expected);
    expect(differences).toEqual([]);
  }
});

test("there is one token definition, imported unedited", () => {
  const globals = readFileSync(
    join(__dirname, "../../app/globals.css"),
    "utf8",
  );
  expect(globals).toContain('@import "../../../docs/design/luma.css";');
  expect(globals).not.toMatch(/oklch\(/);
  expect(tokens(":root")["--radius"]).toBe("0.625rem");
  expect(tokens(".dark")["--radius"]).toBeUndefined();
});

test("an explicit light choice persists across navigation and reload, before paint", async ({
  browser,
}) => {
  const context = await browser.newContext({ colorScheme: "dark" });
  const page = await context.newPage();
  const problems = failOnHydrationProblem(page);
  const requests: string[] = [];
  await visit(page, "/settings");
  page.on("request", (request) =>
    requests.push(`${request.method()} ${request.url()}`),
  );
  await page.getByRole("radio", { name: "Light" }).check();
  await expect(page.locator("html")).toHaveClass(/light/);
  await page.waitForTimeout(300);
  expect(requests, "changing appearance issues no request at all").toEqual([]);
  expect(
    await page.evaluate(() => localStorage.getItem("autobots.theme")),
  ).toBe("light");
  await page.screenshot({
    path: `${SCREENSHOTS}/settings-light.png`,
    fullPage: true,
  });
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await expectConsistent(page, "light");
  await page.reload();
  await page.waitForLoadState("networkidle");
  await expectConsistent(page, "light");
  await page.screenshot({
    path: `${SCREENSHOTS}/home-light-after-reload.png`,
    fullPage: true,
  });
  expect(problems).toEqual([]);
  await context.close();
});

test("an explicit dark choice persists too", async ({ browser }) => {
  const context = await browser.newContext({ colorScheme: "light" });
  await setStored(context, "dark");
  const page = await context.newPage();
  await visit(page);
  await expectConsistent(page, "dark");
  await context.close();
});

// "system" is a choice now (Decision 0022 D2). Any other value, even "System", is not.
for (const stored of ["garbage", "", "System"]) {
  test(`an invalid saved value "${stored}" falls back to dark`, async ({
    browser,
  }) => {
    const context = await browser.newContext({ colorScheme: "light" });
    await setStored(context, stored);
    const page = await context.newPage();
    await visit(page);
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect(page.locator("html")).not.toHaveClass(
      new RegExp(`light${stored ? `|${stored}` : ""}`),
    );
    await expectConsistent(page, "dark");
    await context.close();
  });
}

test("unavailable storage falls back to dark without crashing, and a choice works for the session", async ({
  browser,
}) => {
  const context = await browser.newContext({ colorScheme: "light" });
  await context.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("storage is unavailable");
      },
    });
  });
  const page = await context.newPage();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/settings");
  await page.waitForLoadState("networkidle");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.getByRole("radio", { name: "Light" }).check();
  await expect(page.locator("html")).toHaveClass(/light/);
  expect(errors).toEqual([]);
  await page.reload();
  await page.waitForLoadState("networkidle");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await context.close();
});

for (const theme of ["dark", "light"] as const) {
  for (const path of ["/", "/settings"]) {
    test(`no automated accessibility violation: ${path} in ${theme}`, async ({
      browser,
    }) => {
      const context = await browser.newContext();
      await setStored(context, theme);
      const page = await context.newPage();
      await visit(page, path);
      const results = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
        .analyze();
      expect(
        results.violations.map((item) => `${item.id}: ${item.nodes.length}`),
      ).toEqual([]);
      await context.close();
    });
  }

  test(`keyboard flow, focus and dialog in ${theme}`, async ({ browser }) => {
    const context = await browser.newContext();
    await setStored(context, theme);
    const page = await context.newPage();
    await visit(page);
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "Skip to content" }),
    ).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("link", { name: "Home" })).toBeFocused();
    const outline = await page.evaluate(() => {
      const style = getComputedStyle(document.activeElement as Element);
      return { style: style.outlineStyle, width: style.outlineWidth };
    });
    expect(outline.style).toBe("solid");
    expect(parseFloat(outline.width)).toBeGreaterThanOrEqual(2);
    const opener = page.getByRole("button", { name: "About local services" });
    await opener.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog", { name: "About local services" });
    await expect(dialog).toBeVisible();
    const surface = await dialog.evaluate((element) => {
      const probe = document.createElement("div");
      probe.style.backgroundColor = "var(--popover)";
      document.body.append(probe);
      const expected = getComputedStyle(probe).backgroundColor;
      probe.remove();
      return { actual: getComputedStyle(element).backgroundColor, expected };
    });
    expect(surface.actual).toBe(surface.expected);
    await page.screenshot({ path: `${SCREENSHOTS}/dialog-${theme}.png` });
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();
    await expect(opener).toBeFocused();
    await context.close();
  });
}

test("status meaning is in text and icon, not color alone", async ({
  page,
}) => {
  await visit(page);
  const status = page.getByRole("status");
  await expect(status).toContainText("Python API: available");
  // The decorative service icon isn't the meaning, so only the state icon is counted.
  await expect(status.locator("svg[data-status-icon]")).toHaveCount(1);
});

test("the settings radios have labels and are usable by keyboard", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await visit(page, "/settings");
  // System, Light, Dark: one step back from the first visit's Dark is Light.
  await page.getByRole("radio", { name: "Dark" }).focus();
  await page.keyboard.press("ArrowUp");
  await expect(page.getByRole("radio", { name: "Light" })).toBeChecked();
  await expect(page.locator("html")).toHaveClass(/light/);
  await page.setViewportSize({ width: 640, height: 800 });
  await expect(page.getByRole("radio", { name: "Dark" })).toBeVisible();
  await context.close();
});

// US-15.20, PRD-Studio SE-03 and DS-02 as amended by Decision 0022 D2.
test("System follows the OS only once chosen, and a reload restores it before paint", async ({
  browser,
}) => {
  const context = await browser.newContext({ colorScheme: "light" });
  const page = await context.newPage();
  const problems = failOnHydrationProblem(page);
  await visit(page, "/settings");
  // A first visit is dark, whatever the OS prefers.
  await expectConsistent(page, "dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();
  await page.getByRole("radio", { name: "System" }).check();
  await expect(page.locator("html")).toHaveClass(/light/);
  expect(
    await page.evaluate(() => localStorage.getItem("autobots.theme")),
  ).toBe("system");
  // The OS switches while the page is open.
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.locator("html")).not.toHaveClass(/light/);
  await page.reload();
  await page.waitForLoadState("networkidle");
  await expectConsistent(page, "dark");
  await expect(page.getByRole("radio", { name: "System" })).toBeChecked();
  // And back, so System is seen following the OS both ways, before paint.
  await page.emulateMedia({ colorScheme: "light" });
  await page.reload();
  await page.waitForLoadState("networkidle");
  await expectConsistent(page, "light");
  await page.screenshot({
    path: `${SCREENSHOTS}/settings-system-light.png`,
    fullPage: true,
  });
  expect(problems).toEqual([]);
  await context.close();
});

async function presentation(page: Page): Promise<{
  font: string;
  padding: number;
  transition: string;
}> {
  const font = await page
    .locator('[data-field="document-sample"]')
    .evaluate((element) => getComputedStyle(element).fontFamily);
  const padding = await page
    .locator('section[aria-labelledby="appearance-heading"]')
    .evaluate((element) => parseFloat(getComputedStyle(element).paddingTop));
  // A probe with its own transition: forced or OS reduced motion shortens it to 0.01 ms.
  const transition = await page.evaluate(() => {
    const probe = document.createElement("div");
    probe.style.transition = "color 300ms linear";
    document.body.append(probe);
    const duration = getComputedStyle(probe).transitionDuration;
    probe.remove();
    return duration;
  });
  return { font, padding, transition };
}

test("serif documents, density and forced reduced motion apply, survive a reload, and motion otherwise follows the OS", async ({
  browser,
}) => {
  const context = await browser.newContext({ reducedMotion: "no-preference" });
  const page = await context.newPage();
  const problems = failOnHydrationProblem(page);
  const requests: string[] = [];
  await visit(page, "/settings");
  page.on("request", (request) =>
    requests.push(`${request.method()} ${request.url()}`),
  );
  const fresh = await presentation(page);
  // Serif documents are on by default, comfortable, and motion runs as the OS allows.
  await expect(
    page.getByRole("checkbox", { name: "Serif for documents" }),
  ).toBeChecked();
  expect(fresh.font).toContain("Georgia");
  expect(fresh.padding).toBe(20);
  expect(fresh.transition).toBe("0.3s");

  await page.getByRole("checkbox", { name: "Serif for documents" }).uncheck();
  await page.getByRole("radio", { name: "Compact" }).check();
  await page.getByRole("radio", { name: "Always reduce motion" }).check();
  const chosen = await presentation(page);
  expect(chosen.font).not.toContain("Georgia");
  expect(chosen.font).toMatch(/sans-serif|system-ui/);
  expect(chosen.padding).toBe(16);
  expect(chosen.transition).toBe("1e-05s");
  await page.waitForTimeout(300);
  expect(requests, "presentation choices issue no request").toEqual([]);

  await page.reload();
  await page.waitForLoadState("networkidle");
  expect(await presentation(page)).toEqual(chosen);
  await expect(
    page.getByRole("checkbox", { name: "Serif for documents" }),
  ).not.toBeChecked();
  await expect(page.getByRole("radio", { name: "Compact" })).toBeChecked();
  await expect(
    page.getByRole("radio", { name: "Always reduce motion" }),
  ).toBeChecked();
  expect(
    await page.evaluate(() => document.documentElement.dataset.motion),
  ).toBe("reduce");

  // With nothing forced, motion follows the OS.
  await page.getByRole("radio", { name: "Follow this Mac" }).check();
  expect((await presentation(page)).transition).toBe("0.3s");
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect((await presentation(page)).transition).toBe("1e-05s");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  expect((await presentation(page)).transition).toBe("0.3s");
  for (const theme of ["dark", "light"] as const) {
    await page
      .getByRole("radio", { name: theme === "dark" ? "Dark" : "Light" })
      .check();
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
      .analyze();
    expect(
      results.violations.map((item) => `${item.id}: ${item.nodes.length}`),
      `${theme}, compact and sans documents`,
    ).toEqual([]);
  }
  expect(problems).toEqual([]);
  await context.close();
});

test("invalid stored preferences are ignored, and unwritable storage keeps a choice for the page", async ({
  browser,
}) => {
  const invalid = await browser.newContext({ reducedMotion: "no-preference" });
  await invalid.addInitScript(() => {
    localStorage.setItem("autobots.serif", "maybe");
    localStorage.setItem("autobots.density", "huge");
    localStorage.setItem("autobots.motion", "fast");
  });
  const page = await invalid.newPage();
  await visit(page, "/settings");
  const shown = await presentation(page);
  expect(shown.font).toContain("Georgia");
  expect(shown.padding).toBe(20);
  expect(shown.transition).toBe("0.3s");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await invalid.close();

  const unavailable = await browser.newContext({
    colorScheme: "light",
    reducedMotion: "no-preference",
  });
  await unavailable.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new Error("storage is unavailable");
      },
    });
  });
  const blocked = await unavailable.newPage();
  const errors: string[] = [];
  blocked.on("pageerror", (error) => errors.push(error.message));
  await blocked.goto("/settings");
  await blocked.waitForLoadState("networkidle");
  await expect(blocked.locator("html")).toHaveClass(/dark/);
  await blocked.getByRole("radio", { name: "Compact" }).check();
  expect((await presentation(blocked)).padding).toBe(16);
  await blocked
    .getByRole("checkbox", { name: "Serif for documents" })
    .uncheck();
  expect((await presentation(blocked)).font).not.toContain("Georgia");
  expect(errors).toEqual([]);
  await unavailable.close();
});
