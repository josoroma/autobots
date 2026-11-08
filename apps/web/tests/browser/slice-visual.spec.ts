import { mkdirSync, writeFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import {
  expect,
  test,
  type Browser,
  type BrowserContext,
  type Page,
  type Request,
} from "@playwright/test";

// US-11.11: every named surface in both themes, on the final screens. Its name puts it with the slice
// suites, so the scripted worker can finish a run. WCAG 2.1 AA is the pass line, by Decision 0010.
const OUT = process.env.AUTOBOTS_TEST_VISUAL_DIR ?? "test-results/visual";
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_D = process.env.AUTOBOTS_TEST_NO_KEY_EMAIL ?? "";
const PASSWORD_D = process.env.AUTOBOTS_TEST_NO_KEY_PASSWORD ?? "";
const THEMES = ["dark", "light"] as const;
type Theme = (typeof THEMES)[number];
const TEXT_MINIMUM = 4.5;
const LARGE_TEXT_MINIMUM = 3;
const NON_TEXT_MINIMUM = 3;
const TAB_STOPS = 8;
const FOCUSED_CONTROLS = 12;
// DS-03's names that have no screen in this release. Recorded, as the story asks, and not captured.
const ABSENT = {
  onboarding:
    "No separate flow. Key setup on Models is what a new owner meets, and it's captured as key-setup.",
  "dialogs and portals":
    "The app has none. Choices are inline, and selects are native.",
  menus: "None apart from native selects, whose open lists the OS draws.",
  notifications:
    "No toast or notification surface. Results are inline status text, measured where they appear.",
  charts: "The app has none, so no chart token is in use.",
  "artifact previews":
    "Artifacts are downloaded through a link, and no preview exists. The list is captured on the run.",
  "file lists":
    "No screen lists a run's working files. Published artifacts are on the run.",
  "workflow canvas":
    "The editor is a validated text form, with no canvas, so no edge or node marker is drawn.",
};

interface Surface {
  name: string;
  context: "signed-out" | "owner" | "no-key";
  path: string;
  arrange?: (page: Page) => Promise<unknown>;
  ready: (page: Page) => Promise<void>;
}

interface Measured {
  surface: string;
  theme: Theme;
  screenshot: string;
  text_checked: number;
  lowest_text_ratio: number | null;
  text_failures: unknown[];
  boundaries: unknown[];
  boundary_failures: unknown[];
  raw_controls: unknown[];
  focus_stops: unknown[];
  focus_failures: unknown[];
  hover: { sample: string; ratio: number } | null;
  axe_violations: { id: string; nodes: number; summary: string }[];
  keyboard: Keyboard;
  disabled: { count: number; unnamed: string[] };
  zoom: Record<string, number>;
  motion: Motion;
}

interface Keyboard {
  stops: number;
  truncated: boolean;
  main_controls: number;
  unreached_in_main: string[];
  upward_in_main: string[];
  positive_tabindex: number;
}

interface Motion {
  checked: number;
  moving_when_reduced: string[];
  moving_by_default: number;
}

// A bound on the walk, not a limit on a page: each Runs row has its goal link and a Details button
// (US-15.17), so a full page of runs needs more than 200 stops. Every control must still be reached.
const KEYBOARD_CAP = 400;

// Everything in the page's own colors, read back through a canvas so any CSS color becomes sRGB.
const MEASURE = `
window.__contrast = (() => {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  const rgba = (color) => {
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = "rgba(0, 0, 0, 0)";
    context.fillStyle = color;
    context.fillRect(0, 0, 1, 1);
    const data = context.getImageData(0, 0, 1, 1).data;
    return [data[0], data[1], data[2], data[3] / 255];
  };
  const over = (top, bottom) => {
    const alpha = top[3] + bottom[3] * (1 - top[3]);
    if (alpha === 0) return [0, 0, 0, 0];
    return [0, 1, 2].map((i) => (top[i] * top[3] + bottom[i] * bottom[3] * (1 - top[3])) / alpha).concat(alpha);
  };
  const behind = (element) => {
    const layers = [];
    for (let node = element; node; node = node.parentElement) {
      const color = rgba(getComputedStyle(node).backgroundColor);
      if (color[3] > 0) layers.push(color);
      if (color[3] === 1) break;
    }
    let result = rgba(getComputedStyle(document.documentElement).backgroundColor);
    if (result[3] < 1) result = over(result, [255, 255, 255, 1]);
    for (const layer of layers.reverse()) result = over(layer, result);
    return result;
  };
  const luminance = (color) => {
    const [r, g, b] = color.slice(0, 3).map((value) => {
      const channel = value / 255;
      return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (a, b) => {
    const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return Math.round(((high + 0.05) / (low + 0.05)) * 100) / 100;
  };
  const visible = (element) => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return style.visibility !== "hidden" && style.display !== "none" && box.width > 1 && box.height > 1;
  };
  const opacity = (element) => {
    let value = 1;
    for (let node = element; node; node = node.parentElement) value *= Number(getComputedStyle(node).opacity);
    return value;
  };
  const text = () => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    const found = [];
    while (walker.nextNode()) {
      const value = walker.currentNode.nodeValue.trim();
      const element = walker.currentNode.parentElement;
      if (!value || !element || seen.has(element)) continue;
      if (["SCRIPT", "STYLE", "NOSCRIPT", "OPTION"].includes(element.tagName)) continue;
      if (!visible(element) || element.closest(":disabled")) continue;
      seen.add(element);
      const style = getComputedStyle(element);
      const size = parseFloat(style.fontSize);
      const bold = Number(style.fontWeight) >= 700;
      const background = behind(element);
      const color = rgba(style.color);
      color[3] *= opacity(element);
      const shown = over(color, background);
      const need = size >= 24 || (bold && size >= 18.66) ? ${LARGE_TEXT_MINIMUM} : ${TEXT_MINIMUM};
      found.push({ sample: value.slice(0, 50), ratio: ratio(shown, background), need });
    }
    return found;
  };
  // An underline drawn in the control's inset shadow counts as its boundary, since it's what is visible.
  const boundaries = () =>
    [...document.querySelectorAll("input:not([type=radio]):not([type=checkbox]):not([type=hidden]), select, textarea")]
      .filter(visible)
      .map((element) => {
        const style = getComputedStyle(element);
        const outside = behind(element.parentElement || element);
        const border = over(rgba(style.borderTopColor), outside);
        const shadow = (style.boxShadow.match(/(rgba?|oklch|lab|oklab|color)\\([^)]*\\)/) || [])[0];
        const underline = shadow ? over(rgba(shadow), behind(element)) : null;
        const ratios = [ratio(border, outside)];
        if (underline) ratios.push(ratio(underline, behind(element)));
        return { slot: element.dataset.slot || "raw", label: element.id || element.name || element.tagName, ratio: Math.max(...ratios), border: ratios[0] };
      });
  const rawControls = () =>
    [...document.querySelectorAll("input:not([type=hidden]), select, textarea")]
      .filter((element) => !element.dataset.slot)
      .map((element) => element.id || element.name || element.tagName);
  const focused = () => {
    const element = document.activeElement;
    if (!element || element === document.body) return null;
    const style = getComputedStyle(element);
    const around = behind(element.parentElement || element);
    const outline = parseFloat(style.outlineWidth) > 0 && style.outlineStyle !== "none" ? ratio(over(rgba(style.outlineColor), around), around) : 0;
    const shadow = (style.boxShadow.match(/(rgba?|oklch|lab|oklab|color)\\([^)]*\\)/g) || []).map((color) => ratio(over(rgba(color), around), around));
    return { element: element.tagName + (element.id ? "#" + element.id : ""), outline_width: style.outlineWidth, ratio: Math.max(outline, ...shadow, 0) };
  };
  // The control under the pointer, in its hovered colors.
  const hover = () => {
    const element = [...document.querySelectorAll("main button:hover")].pop();
    if (!element) return null;
    const style = getComputedStyle(element);
    const background = behind(element);
    return { sample: element.textContent.trim().slice(0, 40), ratio: ratio(over(rgba(style.color), background), background) };
  };
  return { text, boundaries, rawControls, focused, hover };
})();
`;

async function signIn(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

async function write(page: Page, key: string): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  };
}

async function themed(browser: Browser, theme: Theme): Promise<BrowserContext> {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  await context.addInitScript((value) => {
    window.localStorage.setItem("autobots.theme", value);
  }, theme);
  return context;
}

// What the surfaces need, made once through the app's own routes.
async function arrange(page: Page): Promise<Record<string, string>> {
  await page.goto("/settings/models");
  const source = page.locator('[data-field="source"]');
  await expect(source).toBeVisible();
  if ((await source.textContent())?.trim() === "None") {
    await page
      .getByLabel(/API key|Replace key/)
      .fill("sk-or-valid-arranged-first");
    await page.getByRole("button", { name: "Save & validate" }).click();
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
  await page.goto("/");
  const stamp = Date.now();
  const run = await (
    await page.request.post("/api/v1/runs", {
      headers: await write(page, `visual-run-${stamp}`),
      data: {
        goal_text: "slice-visual: report the total of the two counts",
        limit_micro_usd: 1000000,
        acceptance_criteria: ["The report states the correct total"],
        required_artifacts: [{ name: "report.md", must_contain: ["Total: 5"] }],
        input_documents: [
          { path: "inputs/data.md", content: "apples: 2\npears: 3\n" },
        ],
      },
    })
  ).json();
  await page.goto(`/runs/${run.run_id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
    { timeout: 60_000 },
  );
  const expert = await (
    await page.request.post("/api/v1/experts", {
      headers: await write(page, `visual-expert-${stamp}`),
      data: { name: `Visual ${stamp}`, config: { tools: ["calculate"] } },
    })
  ).json();
  const session = await (
    await page.request.post("/api/v1/sessions", {
      headers: await write(page, `visual-session-${stamp}`),
      data: { kind: "direct", experts: [{ expert_id: expert.id }] },
    })
  ).json();
  const workflow = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, `visual-workflow-${stamp}`),
      data: { name: `Visual ${stamp}` },
    })
  ).json();
  const graph = {
    nodes: [
      { id: "in", block: "input", version: 1, config: { type: "string" } },
      { id: "out", block: "output", version: 1, config: {} },
    ],
    links: [
      {
        source: "in",
        source_port: "value",
        target: "out",
        target_port: "value",
      },
    ],
  };
  await page.request.post(`/api/v1/workflows/${workflow.id}/versions`, {
    headers: await write(page, `visual-version-${stamp}`),
    data: { expected_version: 0, graph },
  });
  const execution = await (
    await page.request.post(`/api/v1/workflows/${workflow.id}/executions`, {
      headers: await write(page, `visual-execution-${stamp}`),
      data: { version: 1, inputs: { in: "x" } },
    })
  ).json();
  return {
    run: run.run_id,
    expert: expert.id,
    session: session.id,
    workflow: workflow.id,
    execution: execution.id,
  };
}

const heading = (name: string | RegExp) => async (page: Page) => {
  await expect(page.getByRole("heading", { name }).first()).toBeVisible();
};

function surfaces(ids: Record<string, string>): Surface[] {
  const hang = (page: Page, pattern: string) =>
    page.route(pattern, () => undefined);
  const refuse = (page: Page, pattern: string) =>
    page.route(pattern, (route) => route.abort());
  const signInReady = async (page: Page) => {
    await expect(page.getByLabel("Email")).toBeVisible();
  };
  return [
    {
      name: "sign-in",
      context: "signed-out",
      path: "/sign-in",
      ready: signInReady,
    },
    {
      name: "key-setup",
      context: "no-key",
      path: "/settings/models",
      ready: async (page) => {
        await expect(page.getByLabel("API key")).toBeVisible();
      },
    },
    { name: "home", context: "owner", path: "/", ready: heading("New goal") },
    { name: "runs", context: "owner", path: "/runs", ready: heading("Runs") },
    {
      name: "run",
      context: "owner",
      path: `/runs/${ids.run}`,
      ready: async (page) => {
        await expect(
          page.locator('[data-verification="passed"]'),
        ).toBeVisible();
      },
    },
    {
      name: "inspector",
      context: "owner",
      path: `/runs/${ids.run}/inspector`,
      ready: async (page) => {
        await expect(page.locator("[data-call]").first()).toBeVisible();
      },
    },
    {
      name: "experts",
      context: "owner",
      path: "/experts",
      ready: heading("Experts"),
    },
    {
      name: "expert-editor",
      context: "owner",
      path: `/experts/${ids.expert}`,
      ready: async (page) => {
        await expect(page.getByLabel("Instructions")).toBeVisible();
      },
    },
    {
      name: "session",
      context: "owner",
      path: `/sessions/${ids.session}`,
      ready: async (page) => {
        await expect(page.locator('[data-disclosure="model"]')).toBeVisible();
      },
    },
    {
      name: "workflows",
      context: "owner",
      path: "/workflows",
      ready: heading("Workflows"),
    },
    {
      name: "workflow-editor",
      context: "owner",
      path: `/workflows/${ids.workflow}`,
      ready: async (page) => {
        await expect(page.locator('[data-disclosure="model"]')).toBeVisible();
      },
    },
    {
      name: "workflow-monitor",
      context: "owner",
      path: `/workflow-executions/${ids.execution}`,
      ready: async (page) => {
        await expect(page.locator("main")).not.toContainText("Loading");
      },
    },
    {
      name: "approvals",
      context: "owner",
      path: "/approvals",
      ready: async (page) => {
        await expect(page.locator("[data-approval]").first()).toBeVisible();
      },
    },
    {
      name: "approvals-empty",
      context: "no-key",
      path: "/approvals",
      ready: async (page) => {
        await expect(
          page.getByText("Nothing is waiting for a decision."),
        ).toBeVisible();
      },
    },
    {
      name: "settings",
      context: "owner",
      path: "/settings",
      ready: async (page) => {
        await expect(page.getByLabel("Dark")).toBeVisible();
      },
    },
    {
      name: "models",
      context: "owner",
      path: "/settings/models",
      ready: async (page) => {
        await expect(page.locator('[data-field="role-effect"]')).toBeVisible();
      },
    },
    {
      name: "operations",
      context: "owner",
      path: "/operations",
      ready: heading("Operations"),
    },
    {
      name: "state-loading",
      context: "owner",
      path: "/runs",
      arrange: (page) => hang(page, "**/api/v1/runs"),
      ready: async (page) => {
        await expect(page.locator('[data-state="loading"]')).toBeVisible();
      },
    },
    {
      name: "state-error",
      context: "owner",
      path: "/runs",
      arrange: (page) => refuse(page, "**/api/v1/runs"),
      ready: async (page) => {
        await expect(page.locator('[data-state="unavailable"]')).toBeVisible();
      },
    },
    {
      name: "state-empty",
      context: "no-key",
      path: "/workflows",
      ready: heading("Workflows"),
    },
    {
      name: "state-local-only",
      context: "owner",
      path: "/settings/models",
      arrange: (page) => refuse(page, "**/api/**"),
      ready: async (page) => {
        await expect(page.getByRole("alert").first()).toBeVisible();
      },
    },
  ];
}

// Tab from the top, as a person would. Inside main, focus must reach each visible enabled control
// and never jump back up the page. The platform follows document order, so that's what could differ.
async function walkKeyboard(page: Page): Promise<Keyboard> {
  await page.evaluate(() => {
    (window as unknown as { __reached: Element[] }).__reached = [];
  });
  const upward: string[] = [];
  let stops = 0;
  let previousTop: number | null = null;
  for (let index = 0; index < KEYBOARD_CAP; index += 1) {
    await page.keyboard.press("Tab");
    const step = await page.evaluate(() => {
      const current = document.activeElement;
      if (current === null || current === document.body) return null;
      const reached = (window as unknown as { __reached: Element[] }).__reached;
      reached.push(current);
      const inMain = current.closest("main") !== null;
      return {
        label: `${current.tagName} ${current.textContent?.trim().slice(0, 30) ?? ""}`,
        inMain,
        top: current.getBoundingClientRect().top + window.scrollY,
      };
    });
    if (step === null) break;
    stops += 1;
    if (step.inMain) {
      if (previousTop !== null && step.top < previousTop - 4) {
        upward.push(step.label);
      }
      previousTop = step.top;
    }
  }
  const coverage = await page.evaluate(() => {
    const reached = new Set(
      (window as unknown as { __reached: Element[] }).__reached,
    );
    const controls = [
      ...document.querySelectorAll<HTMLElement>(
        "main a[href], main button, main input, main select, main textarea, main summary",
      ),
    ].filter(
      (item) =>
        item.tabIndex >= 0 &&
        !(item as HTMLButtonElement).disabled &&
        item.getClientRects().length > 0 &&
        // A closed `details` hides what's inside it, and its own summary is still a stop.
        (item.tagName === "SUMMARY" ||
          item.closest("details:not([open])") === null),
    );
    return {
      main_controls: controls.length,
      unreached: controls
        .filter(
          (item) =>
            !reached.has(item) &&
            // Tab lands on one radio in a group, and arrow keys move within it.
            !(
              item instanceof HTMLInputElement &&
              item.type === "radio" &&
              [...reached].some(
                (other) =>
                  other instanceof HTMLInputElement &&
                  other.type === "radio" &&
                  other.name === item.name,
              )
            ),
        )
        .map(
          (item) =>
            `${item.tagName} ${item.id || item.textContent?.trim().slice(0, 30)}`,
        ),
      positive: [
        ...document.querySelectorAll<HTMLElement>("[tabindex]"),
      ].filter((item) => item.tabIndex > 0).length,
    };
  });
  // Back to the top, so what follows starts where a person's first Tab would.
  await page.evaluate(() => {
    const first = document.querySelector<HTMLElement>(
      "a[href], button, input, select, textarea",
    );
    first?.focus();
    first?.blur();
  });
  return {
    stops,
    truncated: stops >= KEYBOARD_CAP,
    main_controls: coverage.main_controls,
    unreached_in_main: coverage.unreached,
    upward_in_main: upward,
    positive_tabindex: coverage.positive,
  };
}

async function readDisabled(page: Page): Promise<Measured["disabled"]> {
  return page.evaluate(() => {
    const items = [
      ...document.querySelectorAll<HTMLElement>(
        'main :disabled, main [aria-disabled="true"]',
      ),
    ];
    const name = (item: HTMLElement) =>
      item.getAttribute("aria-label") ||
      item.innerText?.trim() ||
      (item.id &&
        document.querySelector(`label[for="${item.id}"]`)?.textContent) ||
      "";
    return {
      count: items.length,
      unnamed: items.filter((item) => !name(item)).map((item) => item.tagName),
    };
  });
}

// What could move, not what happens to be moving: each element's own durations, with and without it.
async function readMotion(page: Page): Promise<Motion> {
  const read = () =>
    page.evaluate(() => {
      const seconds = (value: string) =>
        Math.max(...value.split(",").map((part) => parseFloat(part) || 0));
      const items = [...document.querySelectorAll("body *")];
      return {
        checked: items.length,
        moving: items
          .filter((item) => {
            const style = getComputedStyle(item);
            return (
              (style.transitionProperty !== "none" &&
                seconds(style.transitionDuration) > 0.02) ||
              (style.animationName !== "none" &&
                seconds(style.animationDuration) > 0.02)
            );
          })
          .map((item) => item.tagName),
      };
    });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const byDefault = await read();
  await page.emulateMedia({ reducedMotion: "reduce" });
  const reduced = await read();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  return {
    checked: reduced.checked,
    moving_when_reduced: reduced.moving,
    moving_by_default: byDefault.moving.length,
  };
}

// The same page in a narrow viewport, as 200% and 400% zoom lay out on a 1280-wide window.
async function sidewaysAtZoom(page: Page): Promise<Record<string, number>> {
  const results: Record<string, number> = {};
  for (const [zoom, width] of Object.entries({ "200%": 640, "400%": 320 })) {
    await page.setViewportSize({ width, height: 400 });
    results[zoom] = await page.evaluate(
      () =>
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth,
    );
  }
  await page.setViewportSize({ width: 1280, height: 800 });
  return results;
}

async function measure(
  page: Page,
  surface: Surface,
  theme: Theme,
): Promise<Measured> {
  await page.addScriptTag({ content: MEASURE });
  // First, from the top of the page. Any focus before this would move where Tab starts from.
  const keyboard = await walkKeyboard(page);
  type Text = { sample: string; ratio: number; need: number };
  type Boundary = { slot: string; label: string; ratio: number };
  type Stop = { element: string; outline_width: string; ratio: number };
  const text = (await page.evaluate("window.__contrast.text()")) as Text[];
  const boundaries = (await page.evaluate(
    "window.__contrast.boundaries()",
  )) as Boundary[];
  const raw = (await page.evaluate(
    "window.__contrast.rawControls()",
  )) as string[];
  const screenshot = `${surface.name}-${theme}.png`;
  await page.screenshot({ path: `${OUT}/${screenshot}`, fullPage: true });
  const axe = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const stops: Stop[] = [];
  for (let index = 0; index < TAB_STOPS; index += 1) {
    await page.keyboard.press("Tab");
    const stop = (await page.evaluate(
      "window.__contrast.focused()",
    )) as Stop | null;
    if (stop !== null) stops.push(stop);
  }
  // The tab stops above are mostly navigation, so each of this page's own controls is focused too.
  const controls = await page
    .locator("main")
    .locator("input, select, textarea, button, a")
    .all();
  for (const control of controls.slice(0, FOCUSED_CONTROLS)) {
    if (
      !(await control.isVisible()) ||
      (await control.isDisabled().catch(() => false))
    )
      continue;
    await control.focus();
    await page.keyboard.press("Shift+Tab");
    await page.keyboard.press("Tab");
    const stop = (await page.evaluate(
      "window.__contrast.focused()",
    )) as Stop | null;
    if (stop !== null) stops.push(stop);
  }
  const disabled = await readDisabled(page);
  const motion = await readMotion(page);
  const zoom = await sidewaysAtZoom(page);
  let hover: Measured["hover"] = null;
  const first = page.locator("main button:not(:disabled)").first();
  if ((await first.count()) > 0) {
    await first.hover();
    hover = (await page.evaluate(
      "window.__contrast.hover()",
    )) as Measured["hover"];
  }
  return {
    surface: surface.name,
    theme,
    screenshot,
    text_checked: text.length,
    lowest_text_ratio: text.length
      ? Math.min(...text.map((item) => item.ratio))
      : null,
    text_failures: text.filter((item) => item.ratio < item.need),
    boundaries,
    boundary_failures: boundaries.filter(
      (item) => item.ratio < NON_TEXT_MINIMUM,
    ),
    raw_controls: raw,
    focus_stops: stops,
    focus_failures: stops.filter((item) => item.ratio < NON_TEXT_MINIMUM),
    hover,
    axe_violations: axe.violations.map((violation) => ({
      id: violation.id,
      nodes: violation.nodes.length,
      summary: violation.nodes[0]?.failureSummary?.slice(0, 200) ?? "",
    })),
    keyboard,
    disabled,
    zoom,
    motion,
  };
}

test("every named surface is captured in both themes, with measured contrast and axe", async ({
  browser,
}) => {
  test.setTimeout(600_000);
  mkdirSync(OUT, { recursive: true });
  const owner = await browser.newContext();
  const ownerPage = await owner.newPage();
  await signIn(ownerPage, EMAIL_A, PASSWORD_A);
  const ids = await arrange(ownerPage);
  await owner.close();

  const results: Measured[] = [];
  for (const theme of THEMES) {
    const contexts = {
      "signed-out": await themed(browser, theme),
      owner: await themed(browser, theme),
      "no-key": await themed(browser, theme),
    };
    const ownerSetup = await contexts.owner.newPage();
    await signIn(ownerSetup, EMAIL_A, PASSWORD_A);
    await ownerSetup.close();
    const keySetup = await contexts["no-key"].newPage();
    await signIn(keySetup, EMAIL_D, PASSWORD_D);
    await keySetup.close();
    for (const surface of surfaces(ids)) {
      const page = await contexts[surface.context].newPage();
      // What is still in flight, so a page that never settles names its request.
      const pending = new Set<Request>();
      let requested = 0;
      page.on("request", (request) => {
        requested += 1;
        pending.add(request);
      });
      page.on("requestfinished", (request) => pending.delete(request));
      page.on("requestfailed", (request) => pending.delete(request));
      if (surface.arrange) await surface.arrange(page);
      await page.goto(surface.path);
      await surface.ready(page);
      if (!surface.arrange) {
        await page
          .waitForLoadState("networkidle", { timeout: 60_000 })
          .catch(async (error: Error) => {
            const connection = await page
              .locator("[data-connection]")
              .first()
              .getAttribute("data-connection")
              .catch(() => null);
            throw new Error(
              `${surface.name} (${theme}) never settled after ${requested} requests, connection ${connection}, open: ${[
                ...pending,
              ]
                .map((request) => `${request.method()} ${request.url()}`)
                .join(", ")}. ${error.message}`,
            );
          });
      }
      await expect(page.locator("html")).toHaveClass(new RegExp(theme));
      results.push(await measure(page, surface, theme));
      await page.close();
    }
    for (const context of Object.values(contexts)) await context.close();
  }

  const failed = results.filter(
    (item) =>
      item.text_failures.length ||
      item.boundary_failures.length ||
      item.focus_failures.length ||
      (item.hover !== null && item.hover.ratio < TEXT_MINIMUM) ||
      item.axe_violations.length ||
      item.raw_controls.length ||
      item.keyboard.stops === 0 ||
      item.keyboard.truncated ||
      item.keyboard.unreached_in_main.length ||
      item.keyboard.upward_in_main.length ||
      item.keyboard.positive_tabindex ||
      item.disabled.unnamed.length ||
      item.motion.moving_when_reduced.length ||
      Object.values(item.zoom).some((over) => over > 0),
  );
  writeFileSync(
    `${OUT}/results.json`,
    JSON.stringify(
      {
        schema_version: "autobots.visual-evidence/v1",
        pass_line: "WCAG 2.1 AA, Decision 0010",
        surfaces: results.length,
        with_findings: failed.map((item) => `${item.surface}-${item.theme}`),
        absent: ABSENT,
        results,
      },
      null,
      2,
    ),
  );
  expect(failed.map((item) => `${item.surface}-${item.theme}`)).toEqual([]);
});

test("the walk's checks fail when they should, on a page broken on purpose", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
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
    const main = document.querySelector("main") as HTMLElement;
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
  await signIn(page, EMAIL_A, PASSWORD_A);
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
  await signIn(page, EMAIL_A, PASSWORD_A);
  const widths = { "200%": 640, "400%": 320 };
  const results: Record<string, Record<string, number>> = {};
  for (const [zoom, width] of Object.entries(widths)) {
    await page.setViewportSize({ width, height: 400 });
    results[zoom] = {};
    for (const path of [
      "/",
      "/runs",
      "/experts",
      "/workflows",
      "/approvals",
      "/settings",
      "/settings/models",
      "/operations",
    ]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const over = await page.evaluate(
        () =>
          document.documentElement.scrollWidth -
          document.documentElement.clientWidth,
      );
      (results[zoom] as Record<string, number>)[path] = over;
    }
  }
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
  await signIn(page, EMAIL_A, PASSWORD_A);
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
  await signIn(page, EMAIL_A, PASSWORD_A);
  const state = async () => ({
    runs: (await (await page.request.get("/api/v1/runs")).json()).runs,
    approvals: (await (await page.request.get("/api/v1/approvals")).json())
      .approvals,
    workflows: (await (await page.request.get("/api/v1/workflows")).json())
      .workflows,
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
  expect(
    before.runs.some((run: { status: string }) => run.status === "running"),
  ).toBe(true);
  expect(
    before.approvals.some(
      (item: { status: string }) => item.status === "pending",
    ),
  ).toBe(true);
});
