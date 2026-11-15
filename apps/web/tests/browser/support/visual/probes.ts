/**
 * What the visual walk reads from a page besides contrast: keyboard order and reach, disabled
 * names, motion, shadowed cards and sideways scrolling at zoom (US-11.11, Decision 0010). Each
 * in-page function is self-contained, since Playwright sends its source to the page (TWEB-03).
 */
import type { Page } from "@playwright/test";

/** What a walk of the page by Tab found. */
export interface Keyboard {
  stops: number;
  truncated: boolean;
  main_controls: number;
  unreached_in_main: string[];
  upward_in_main: string[];
  positive_tabindex: number;
}

/** Disabled controls in main, and those with no name. */
export interface Disabled {
  count: number;
  unnamed: string[];
}

/** Elements that could move, with and without a reduced-motion preference. */
export interface Motion {
  checked: number;
  moving_when_reduced: string[];
  moving_by_default: number;
}

// A bound on the walk, not a limit on a page: each Runs row has its goal link and a Details button
// (US-15.17), so a full page of runs needs more than 200 stops. Every control must still be reached.
const KEYBOARD_CAP = 400;

/** The viewport the walk measures in, and that the zoom probe restores. */
export const WALK_VIEWPORT = { width: 1280, height: 800 } as const;

/** The widths at which a 1280-wide window lays out at 200% and at 400% zoom. */
export const ZOOM_WIDTHS = { "200%": 640, "400%": 320 } as const;
const ZOOM_HEIGHT = 400;

interface FocusStep {
  label: string;
  inMain: boolean;
  top: number;
}

/** Notes where focus is now, or null once focus has left the page. */
function noteFocus(reached: Element[]): FocusStep | null {
  const current = document.activeElement;
  if (current === null || current === document.body) return null;
  reached.push(current);
  return {
    label: `${current.tagName} ${current.textContent?.trim().slice(0, 30) ?? ""}`,
    inMain: current.closest("main") !== null,
    top: current.getBoundingClientRect().top + window.scrollY,
  };
}

/** Main's visible, enabled controls that Tab never reached, and the count of positive tabindexes. */
function mainCoverage(reached: Element[]): {
  main_controls: number;
  unreached: string[];
  positive: number;
} {
  const seen = new Set(reached);
  const controls = [
    ...document.querySelectorAll<HTMLElement>(
      "main a[href], main button, main input, main select, main textarea, main summary",
    ),
  ].filter(
    (item) =>
      item.tabIndex >= 0 &&
      !("disabled" in item && item.disabled) &&
      item.getClientRects().length > 0 &&
      // A closed `details` hides what's inside it, and its own summary is still a stop.
      (item.tagName === "SUMMARY" ||
        item.closest("details:not([open])") === null),
  );
  // Tab lands on one radio in a group, and arrow keys move within it.
  const radioReached = (item: HTMLElement) =>
    item instanceof HTMLInputElement &&
    item.type === "radio" &&
    [...seen].some(
      (other) =>
        other instanceof HTMLInputElement &&
        other.type === "radio" &&
        other.name === item.name,
    );
  return {
    main_controls: controls.length,
    unreached: controls
      .filter((item) => !seen.has(item) && !radioReached(item))
      .map(
        (item) =>
          `${item.tagName} ${item.id || item.textContent?.trim().slice(0, 30)}`,
      ),
    positive: [...document.querySelectorAll<HTMLElement>("[tabindex]")].filter(
      (item) => item.tabIndex > 0,
    ).length,
  };
}

/** Back to the top, so what follows starts where a person's first Tab would. */
function backToTop(): void {
  const first = document.querySelector<HTMLElement>(
    "a[href], button, input, select, textarea",
  );
  first?.focus();
  first?.blur();
}

/**
 * Tabs from the top, as a person would. Inside main, focus must reach each visible enabled
 * control and never jump back up the page. The platform follows document order, so that's what
 * could differ.
 */
export async function walkKeyboard(page: Page): Promise<Keyboard> {
  const reached = await page.evaluateHandle((): Element[] => []);
  const upward: string[] = [];
  let stops = 0;
  let previousTop: number | null = null;
  for (let index = 0; index < KEYBOARD_CAP; index += 1) {
    await page.keyboard.press("Tab");
    const step = await reached.evaluate(noteFocus);
    if (step === null) break;
    stops += 1;
    if (!step.inMain) continue;
    if (previousTop !== null && step.top < previousTop - 4)
      upward.push(step.label);
    previousTop = step.top;
  }
  const coverage = await reached.evaluate(mainCoverage);
  await page.evaluate(backToTop);
  return {
    stops,
    truncated: stops >= KEYBOARD_CAP,
    main_controls: coverage.main_controls,
    unreached_in_main: coverage.unreached,
    upward_in_main: upward,
    positive_tabindex: coverage.positive,
  };
}

/** Disabled controls in main, and which of them have no name a person could hear. */
export function readDisabled(page: Page): Promise<Disabled> {
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

function readMoving(): { checked: number; moving: string[] } {
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
}

/** What could move, not what happens to be moving: each element's own durations, with and without it. */
export async function readMotion(page: Page): Promise<Motion> {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  const byDefault = await page.evaluate(readMoving);
  await page.emulateMedia({ reducedMotion: "reduce" });
  const reduced = await page.evaluate(readMoving);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  return {
    checked: reduced.checked,
    moving_when_reduced: reduced.moving,
    moving_by_default: byDefault.moving.length,
  };
}

/** Main's sections that cast a shadow, by their heading's id or their class. */
export function readShadowedCards(page: Page): Promise<string[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll("main section")]
      .filter((element) => getComputedStyle(element).boxShadow !== "none")
      .map(
        (element) =>
          element.getAttribute("aria-labelledby") ||
          element.className.slice(0, 60),
      ),
  );
}

/** How far the page scrolls sideways at its current viewport, in CSS pixels. */
export function sidewaysOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () =>
      document.documentElement.scrollWidth -
      document.documentElement.clientWidth,
  );
}

/** For each zoom in ZOOM_WIDTHS, sets the viewport that zoom gives, then reads. */
export async function atEachZoom<T>(
  page: Page,
  read: () => Promise<T>,
): Promise<Record<string, T>> {
  const results: Record<string, T> = {};
  for (const [zoom, width] of Object.entries(ZOOM_WIDTHS)) {
    await page.setViewportSize({ width, height: ZOOM_HEIGHT });
    results[zoom] = await read();
  }
  return results;
}

/** The page's sideways overflow at each zoom, then the walk's viewport again. */
export async function sidewaysAtZoom(
  page: Page,
): Promise<Record<string, number>> {
  const results = await atEachZoom(page, () => sidewaysOverflow(page));
  await page.setViewportSize(WALK_VIEWPORT);
  return results;
}
