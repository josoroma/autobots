import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import {
  parseApprovalList,
  parseRunList,
  parseWorkflowList,
} from "@autobots/api-client";

import { getJson } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { optional } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import {
  arrangeSurfaces,
  openThemedContexts,
  type OpenContext,
} from "./support/visual/arrange.ts";
import { measure } from "./support/visual/measure.ts";
import {
  atEachZoom,
  readDisabled,
  readMotion,
  sidewaysOverflow,
  walkKeyboard,
} from "./support/visual/probes.ts";
import {
  findingsOf,
  writeEvidence,
  type Walk,
} from "./support/visual/report.ts";
import { pageRoutes, unwalkedRoutes } from "./support/visual/routes.ts";
import { settle } from "./support/visual/settle.ts";
import {
  ABSENT_ROUTES,
  SURFACES,
  THEMES,
  type SurfaceIds,
  type Theme,
} from "./support/visual/surfaces.ts";

// US-11.11: every named surface in both themes, on the final screens. Its name puts it with the slice
// suites, so the scripted worker can finish a run. WCAG 2.1 AA is the pass line, by Decision 0010.
const OUT = optional("AUTOBOTS_TEST_VISUAL_DIR", "test-results/visual");

// The screens the zoom test loads at each zoom's width.
const ZOOM_PATHS = [
  "/",
  "/runs",
  "/experts",
  "/workflows",
  "/approvals",
  "/settings",
  "/settings/models",
  "/operations",
];

// Each surface in one theme, as a step of its own: a finding or a surface that never becomes ready
// is reported by name, and the walk goes on to the next (TWEB-03).
async function walkTheme(
  openContext: OpenContext,
  theme: Theme,
  ids: SurfaceIds,
  walk: Walk,
): Promise<void> {
  const contexts = await test.step(`sign in for ${theme}`, () =>
    openThemedContexts(openContext, theme));
  for (const surface of SURFACES) {
    await test.step(`${surface.name} in ${theme}`, async () => {
      const page = await contexts[surface.context].newPage();
      try {
        const reason = await settle(page, surface, ids, theme);
        if (reason !== null) {
          walk.neverReady.push({ surface: surface.name, theme, reason });
          expect
            .soft(reason, `${surface.name} in ${theme} never became ready`)
            .toBeNull();
          return;
        }
        const measured = await measure(page, {
          surface: surface.name,
          theme,
          out: OUT,
        });
        walk.results.push(measured);
        expect
          .soft(findingsOf(measured), `${surface.name} in ${theme}`)
          .toEqual([]);
      } finally {
        await page.close();
      }
    });
  }
  for (const context of Object.values(contexts)) await context.close();
}

test("every named surface is captured in both themes, with measured contrast and axe", async ({
  openContext,
}, testInfo) => {
  test.setTimeout(600_000);
  mkdirSync(OUT, { recursive: true });
  const ids = await test.step("arrange what the surfaces show", () =>
    arrangeSurfaces(openContext));
  await test.step("every page route is a surface or absent with its reason", () => {
    const routes = pageRoutes(
      join(testInfo.project.testDir, "..", "..", "app"),
    );
    const paths = SURFACES.map((surface) => surface.path(ids));
    expect.soft(unwalkedRoutes(routes, paths, ABSENT_ROUTES)).toEqual([]);
  });
  // Written whatever happens, so a failure part way still leaves the evidence gathered so far.
  const walk: Walk = { results: [], neverReady: [] };
  try {
    for (const theme of THEMES) await walkTheme(openContext, theme, ids, walk);
  } finally {
    writeEvidence(OUT, walk);
  }
});

test("the walk's checks fail when they should, on a page broken on purpose", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "New goal" })).toBeVisible();
  await expect(page.getByLabel("Model for this run")).toBeVisible();
  await page.waitForLoadState("networkidle");
  // Before: a clean page has nothing to report, so what follows comes from the breakage.
  const clean = await walkKeyboard(page);
  expect(clean.upward_in_main).toEqual([]);
  expect(clean.unreached_in_main).toEqual([]);
  expect(clean.positive_tabindex).toBe(0);
  await page.evaluate(() => {
    const main = document.querySelector("main");
    if (main === null) throw new Error("The page has no main");
    // Painted out of order, so Tab climbs the page while following the document.
    for (const [text, top] of [
      ["Painted low", "2000px"],
      ["Painted high", "10px"],
    ] as const) {
      const link = document.createElement("a");
      link.href = "#";
      link.textContent = text;
      link.style.position = "absolute";
      link.style.top = top;
      main.append(link);
    }
    const out = document.createElement("div");
    out.inert = true;
    const unreachable = document.createElement("button");
    unreachable.textContent = "Can't be reached";
    out.append(unreachable);
    main.append(out);
    const jumpy = document.createElement("a");
    jumpy.href = "#";
    jumpy.textContent = "Jumps ahead";
    jumpy.tabIndex = 5;
    main.append(jumpy);
    const moving = document.createElement("div");
    moving.setAttribute(
      "style",
      "transition: opacity 1s !important; transition-duration: 1s !important;",
    );
    main.append(moving);
    const nameless = document.createElement("button");
    nameless.disabled = true;
    main.append(nameless);
  });
  const keyboard = await walkKeyboard(page);
  expect(keyboard.positive_tabindex).toBeGreaterThan(0);
  expect(keyboard.upward_in_main.join()).toContain("Painted high");
  expect(keyboard.unreached_in_main.join()).toContain("Can't be reached");
  const motion = await readMotion(page);
  expect(motion.moving_when_reduced.length).toBeGreaterThan(0);
  expect(motion.moving_by_default).toBeGreaterThan(0);
  const disabled = await readDisabled(page);
  expect(disabled.unnamed.length).toBeGreaterThan(0);
});

test("keyboard use reaches every control on a form, with focus visible, and starts nothing by itself", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "New goal" })).toBeVisible();
  await expect(page.getByLabel("Model for this run")).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  const reached: string[] = [];
  for (let index = 0; index < 30; index += 1) {
    await page.keyboard.press("Tab");
    reached.push(
      await page.evaluate(
        () =>
          document.activeElement?.id || document.activeElement?.tagName || "",
      ),
    );
    if (reached.at(-1) === "goal") break;
  }
  expect(reached).toContain("goal");
  await page.keyboard.type("A goal typed by keyboard");
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Model for this run")).toBeFocused();
});

test("at 200% and at 400% zoom nothing is lost to sideways scrolling", async ({
  page,
}) => {
  await signIn(page, users.owner);
  // Each screen loads at the zoom's width, as it would in a zoomed window.
  const results = await atEachZoom(page, async () => {
    const overflow: Record<string, number> = {};
    for (const path of ZOOM_PATHS) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      overflow[path] = await sidewaysOverflow(page);
    }
    return overflow;
  });
  mkdirSync(OUT, { recursive: true });
  writeFileSync(`${OUT}/zoom.json`, JSON.stringify(results, null, 2));
  for (const widthsAt of Object.values(results)) {
    for (const over of Object.values(widthsAt)) {
      expect(over).toBeLessThanOrEqual(0);
    }
  }
});

test("with reduced motion, nothing animates", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signIn(page, users.owner);
  for (const path of ["/", "/runs", "/settings", "/operations"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const moving = await page.evaluate(() =>
      document
        .getAnimations()
        .filter((animation) => {
          const timing = animation.effect?.getTiming();
          return Number(timing?.duration ?? 0) > 1;
        })
        .map((animation) => String(animation.effect?.getTiming().duration)),
    );
    expect(moving).toEqual([]);
  }
});

test("changing appearance sends no model or task request, and changes no run or approval", async ({
  page,
}) => {
  await signIn(page, users.owner);
  const state = async () => ({
    runs: (await getJson(page, { path: "/api/v1/runs", parse: parseRunList }))
      .runs,
    approvals: (
      await getJson(page, {
        path: "/api/v1/approvals",
        parse: parseApprovalList,
      })
    ).approvals,
    workflows: (
      await getJson(page, {
        path: "/api/v1/workflows",
        parse: parseWorkflowList,
      })
    ).workflows,
  });
  await page.goto("/settings");
  await expect(page.getByLabel("Dark")).toBeVisible();
  const before = await state();
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/")) {
      requests.push(`${request.method()} ${request.url()}`);
    }
  });
  await page.getByLabel("Light").check();
  await expect(page.locator("html")).toHaveClass(/light/);
  // US-15.20: every preference, each changed and then put back, while a run runs and approvals wait.
  await page.getByRole("radio", { name: "System" }).check();
  await page.getByRole("checkbox", { name: "Serif for documents" }).uncheck();
  await page.getByRole("radio", { name: "Compact" }).check();
  await page.getByRole("radio", { name: "Always reduce motion" }).check();
  await page
    .getByRole("checkbox", { name: "Stream text as it's written" })
    .uncheck();
  await expect(page.locator("html")).toHaveAttribute("data-density", "compact");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduce");
  await expect(page.locator("html")).toHaveAttribute("data-serif", "off");
  await page.getByRole("checkbox", { name: "Serif for documents" }).check();
  await page.getByRole("radio", { name: "Comfortable" }).check();
  await page.getByRole("radio", { name: "Follow this Mac" }).check();
  await page
    .getByRole("checkbox", { name: "Stream text as it's written" })
    .check();
  await page.getByLabel("Dark").check();
  await expect(page.locator("html")).toHaveClass(/dark/);
  await page.waitForTimeout(500);
  expect(requests).toEqual([]);
  expect(await state()).toEqual(before);
  expect(before.runs.some((run) => run.status === "running")).toBe(true);
  expect(before.approvals.some((item) => item.status === "pending")).toBe(true);
});
