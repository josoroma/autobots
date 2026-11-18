/**
 * One surface in one theme, measured against WCAG 2.1 AA (Decision 0010): contrast, focus,
 * hover, axe, keyboard, disabled names, motion and zoom, with a full-page screenshot (US-11.11).
 * A modal dialog makes the rest of the page inert, so on a dialog surface each probe reads the open
 * dialog, and axe still scans the whole page. Measured is one entry of results.json's `results`.
 */
import type { JSHandle, Page } from "@playwright/test";

import { scanA11y } from "../a11y.ts";
import {
  openContrastKit,
  PASS_LINE,
  type Boundary,
  type ContrastKit,
  type FocusStop,
  type HoverSample,
  type Scope,
  type TextSample,
} from "./contrast.ts";
import {
  readDisabled,
  readMotion,
  readShadowedCards,
  sidewaysAtZoom,
  walkKeyboard,
  type Disabled,
  type Keyboard,
  type Motion,
} from "./probes.ts";
import type { Theme } from "./surfaces.ts";

export interface Measured {
  surface: string;
  theme: Theme;
  screenshot: string;
  text_checked: number;
  lowest_text_ratio: number | null;
  text_failures: TextSample[];
  boundaries: Boundary[];
  boundary_failures: Boundary[];
  shadowed_cards: string[];
  raw_controls: string[];
  focus_stops: FocusStop[];
  focus_failures: FocusStop[];
  hover: HoverSample | null;
  axe_violations: { id: string; nodes: number; summary: string }[];
  /**
   * Null on a dialog surface. The walk Tabs through main, which the modal makes inert, and the
   * modal's own order is the browser's focus trap (Decision 0026 G3), which search.spec.ts,
   * tools.spec.ts and appearance.spec.ts drive by keyboard.
   */
  keyboard: Keyboard | null;
  disabled: Disabled;
  zoom: Record<string, number>;
  motion: Motion;
}

const TAB_STOPS = 8;
const FOCUSED_CONTROLS = 12;

/** A page's text and fields are read across it and its controls in main; a dialog's, inside it. */
const PAGE_SCOPE: Scope = { root: "body", controls: "main" };
const DIALOG_SCOPE: Scope = { root: "dialog[open]", controls: "dialog[open]" };

/**
 * The focus ring at the first Tab stops, which on a page are mostly navigation, and then on each
 * of the scope's own controls, focused by Tab from the control before it.
 */
async function readFocusStops(
  page: Page,
  kit: JSHandle<ContrastKit>,
  scope: Scope,
): Promise<FocusStop[]> {
  const stops: FocusStop[] = [];
  const note = async () => {
    const stop = await kit.evaluate((probe) => probe.focused());
    if (stop !== null) stops.push(stop);
  };
  for (let index = 0; index < TAB_STOPS; index += 1) {
    await page.keyboard.press("Tab");
    await note();
  }
  const controls = await page
    .locator(scope.controls)
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
    await note();
  }
  return stops;
}

/** The scope's first enabled button, hovered, in its hovered colors. */
async function readHover(
  page: Page,
  kit: JSHandle<ContrastKit>,
  scope: Scope,
): Promise<HoverSample | null> {
  const first = page.locator(`${scope.controls} button:not(:disabled)`).first();
  if ((await first.count()) === 0) return null;
  await first.hover();
  return kit.evaluate((probe) => probe.hover());
}

/**
 * Measures the page as it stands, or its open dialog when `dialog` is set, and saves its
 * screenshot as `<surface>-<theme>.png` in `out`. The keyboard walk comes first, since any focus
 * before it would move where Tab starts.
 */
export async function measure(
  page: Page,
  {
    surface,
    theme,
    out,
    dialog,
  }: { surface: string; theme: Theme; out: string; dialog: boolean },
): Promise<Measured> {
  const scope = dialog ? DIALOG_SCOPE : PAGE_SCOPE;
  const kit = await openContrastKit(page, scope);
  const keyboard = dialog ? null : await walkKeyboard(page);
  const text = await kit.evaluate((probe) => probe.text());
  const boundaries = await kit.evaluate((probe) => probe.boundaries());
  const raw = await kit.evaluate((probe) => probe.rawControls());
  const screenshot = `${surface}-${theme}.png`;
  await page.screenshot({ path: `${out}/${screenshot}`, fullPage: true });
  const violations = await scanA11y(page);
  const stops = await readFocusStops(page, kit, scope);
  const disabled = await readDisabled(page, scope.controls);
  const motion = await readMotion(page);
  const zoom = await sidewaysAtZoom(page, dialog ? scope.root : null);
  const hover = await readHover(page, kit, scope);
  const shadowed = await readShadowedCards(page, scope.controls);
  return {
    surface,
    theme,
    screenshot,
    text_checked: text.length,
    lowest_text_ratio: text.length
      ? Math.min(...text.map((item) => item.ratio))
      : null,
    text_failures: text.filter((item) => item.ratio < item.need),
    boundaries,
    boundary_failures: boundaries.filter(
      (item) => item.border < PASS_LINE.nonText || item.underline || !item.even,
    ),
    shadowed_cards: shadowed,
    raw_controls: raw,
    focus_stops: stops,
    focus_failures: stops.filter((item) => item.ratio < PASS_LINE.nonText),
    hover,
    axe_violations: violations.map((violation) => ({
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
