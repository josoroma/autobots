/**
 * The visual walk's contrast measurements, made in the page in its own colors (US-11.11, DS-05).
 * Each kit is built by a self-contained function that Playwright sends to the page, so the
 * compiler checks the in-page code and each result type is declared here once (TWEB-03). The kits
 * stay in the page as handles and are called through them, never read back by name.
 */
import type { JSHandle, Page } from "@playwright/test";

/** WCAG 2.1 AA's contrast minimums, the walk's pass line (Decision 0010). */
export const PASS_LINE = { text: 4.5, largeText: 3, nonText: 3 } as const;

/** A color as sRGB channels from 0 to 255 and an alpha from 0 to 1. */
export type Rgba = [number, number, number, number];

/** Colors as the page draws them, read back through a canvas so any CSS color becomes sRGB. */
export interface ColorKit {
  rgba: (color: string) => Rgba;
  /** `top` composited over `bottom`. */
  over: (top: Rgba, bottom: Rgba) => Rgba;
  /** What is drawn behind the element: its own and its ancestors' backgrounds, over white. */
  behind: (element: Element) => Rgba;
  /** The WCAG contrast ratio, rounded to two decimals. */
  ratio: (a: Rgba, b: Rgba) => number;
  visible: (element: Element) => boolean;
  /** The element's opacity times its ancestors'. */
  opacity: (element: Element) => number;
}

export interface TextSample {
  sample: string;
  ratio: number;
  /** The minimum for this text's size and weight. */
  need: number;
}

export interface Boundary {
  slot: string;
  label: string;
  ratio: number;
  border: number;
  /** An inset underline drawn while the control isn't focused. */
  underline: boolean;
  /** One border of one color on all four sides (Decision 0023 E1). */
  even: boolean;
}

export interface FocusStop {
  element: string;
  outline_width: string;
  ratio: number;
}

export interface HoverSample {
  sample: string;
  ratio: number;
}

export interface ContrastKit {
  /** Each visible, enabled text element against what is behind it. */
  text: () => TextSample[];
  /** Each visible text field and select against what surrounds it. */
  boundaries: () => Boundary[];
  /** Controls that don't come from the shared components, which mark theirs with `data-slot`. */
  rawControls: () => string[];
  /** The focused element's outline or ring against what surrounds it. */
  focused: () => FocusStop | null;
  /** The button under the pointer inside main, in its hovered colors. */
  hover: () => HoverSample | null;
}

function createColorKit(): ColorKit {
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (context === null) throw new Error("No 2D canvas to read colors with");
  const rgba = (color: string): Rgba => {
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = "rgba(0, 0, 0, 0)";
    context.fillStyle = color;
    context.fillRect(0, 0, 1, 1);
    const [red = 0, green = 0, blue = 0, alpha = 0] = context.getImageData(
      0,
      0,
      1,
      1,
    ).data;
    return [red, green, blue, alpha / 255];
  };
  const over = (top: Rgba, bottom: Rgba): Rgba => {
    const alpha = top[3] + bottom[3] * (1 - top[3]);
    if (alpha === 0) return [0, 0, 0, 0];
    const mix = (channel: 0 | 1 | 2) =>
      (top[channel] * top[3] + bottom[channel] * bottom[3] * (1 - top[3])) /
      alpha;
    return [mix(0), mix(1), mix(2), alpha];
  };
  const behind = (element: Element): Rgba => {
    const layers: Rgba[] = [];
    for (let node: Element | null = element; node; node = node.parentElement) {
      const color = rgba(getComputedStyle(node).backgroundColor);
      if (color[3] > 0) layers.push(color);
      if (color[3] === 1) break;
    }
    let result = rgba(
      getComputedStyle(document.documentElement).backgroundColor,
    );
    if (result[3] < 1) result = over(result, [255, 255, 255, 1]);
    for (const layer of layers.reverse()) result = over(layer, result);
    return result;
  };
  const linear = (value: number): number => {
    const channel = value / 255;
    return channel <= 0.03928
      ? channel / 12.92
      : ((channel + 0.055) / 1.055) ** 2.4;
  };
  const luminance = ([red, green, blue]: Rgba): number =>
    0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
  const ratio = (a: Rgba, b: Rgba): number => {
    const high = Math.max(luminance(a), luminance(b));
    const low = Math.min(luminance(a), luminance(b));
    return Math.round(((high + 0.05) / (low + 0.05)) * 100) / 100;
  };
  const visible = (element: Element): boolean => {
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    return (
      style.visibility !== "hidden" &&
      style.display !== "none" &&
      box.width > 1 &&
      box.height > 1
    );
  };
  const opacity = (element: Element): number => {
    let value = 1;
    for (let node: Element | null = element; node; node = node.parentElement)
      value *= Number(getComputedStyle(node).opacity);
    return value;
  };
  return { rgba, over, behind, ratio, visible, opacity };
}

type Field = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

function createContrastKit({
  colors,
  minimums,
}: {
  colors: ColorKit;
  minimums: { text: number; largeText: number };
}): ContrastKit {
  const { rgba, over, behind, ratio, visible, opacity } = colors;
  // A color in a box-shadow, so a ring or an underline drawn as a shadow counts as what is visible.
  const SHADOW_COLORS = /(rgba?|oklch|lab|oklab|color)\([^)]*\)/g;
  const skipped = (element: Element): boolean =>
    ["SCRIPT", "STYLE", "NOSCRIPT", "OPTION"].includes(element.tagName) ||
    !visible(element) ||
    element.closest(":disabled") !== null;
  const needFor = (style: CSSStyleDeclaration): number => {
    const size = parseFloat(style.fontSize);
    const bold = Number(style.fontWeight) >= 700;
    return size >= 24 || (bold && size >= 18.66)
      ? minimums.largeText
      : minimums.text;
  };
  const text = (): TextSample[] => {
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
    );
    const seen = new Set<Element>();
    const found: TextSample[] = [];
    while (walker.nextNode()) {
      const value = (walker.currentNode.nodeValue ?? "").trim();
      const element = walker.currentNode.parentElement;
      if (!value || !element || seen.has(element) || skipped(element)) continue;
      seen.add(element);
      const style = getComputedStyle(element);
      const background = behind(element);
      const color = rgba(style.color);
      color[3] *= opacity(element);
      const shown = over(color, background);
      found.push({
        sample: value.slice(0, 50),
        ratio: ratio(shown, background),
        need: needFor(style),
      });
    }
    return found;
  };
  const boundary = (element: Field): Boundary => {
    const style = getComputedStyle(element);
    const outside = behind(element.parentElement || element);
    const border = ratio(over(rgba(style.borderTopColor), outside), outside);
    const shadow = style.boxShadow.match(SHADOW_COLORS)?.[0];
    const ratios = [border];
    if (shadow !== undefined)
      ratios.push(ratio(over(rgba(shadow), behind(element)), behind(element)));
    // Decision 0023 E1: one even border on all four sides, and no inset underline.
    const sides = [
      style.borderTopWidth,
      style.borderRightWidth,
      style.borderBottomWidth,
      style.borderLeftWidth,
    ];
    const sideColors = [
      style.borderTopColor,
      style.borderRightColor,
      style.borderBottomColor,
      style.borderLeftColor,
    ];
    return {
      slot: element.dataset.slot || "raw",
      label: element.id || element.name || element.tagName,
      ratio: Math.max(...ratios),
      border,
      underline: shadow !== undefined && document.activeElement !== element,
      even:
        new Set(sides).size === 1 &&
        new Set(sideColors).size === 1 &&
        parseFloat(style.borderTopWidth) > 0,
    };
  };
  const boundaries = (): Boundary[] =>
    [
      ...document.querySelectorAll<Field>(
        "input:not([type=radio]):not([type=checkbox]):not([type=hidden]), select, textarea",
      ),
    ]
      .filter(visible)
      .map(boundary);
  const rawControls = (): string[] =>
    [
      ...document.querySelectorAll<Field>(
        "input:not([type=hidden]), select, textarea",
      ),
    ]
      .filter((element) => !element.dataset.slot)
      .map((element) => element.id || element.name || element.tagName);
  const focused = (): FocusStop | null => {
    const element = document.activeElement;
    if (!element || element === document.body) return null;
    const style = getComputedStyle(element);
    const around = behind(element.parentElement || element);
    const against = (color: string) => ratio(over(rgba(color), around), around);
    const outline =
      parseFloat(style.outlineWidth) > 0 && style.outlineStyle !== "none"
        ? against(style.outlineColor)
        : 0;
    const rings = (style.boxShadow.match(SHADOW_COLORS) ?? []).map(against);
    return {
      element: element.tagName + (element.id ? "#" + element.id : ""),
      outline_width: style.outlineWidth,
      ratio: Math.max(outline, ...rings, 0),
    };
  };
  const hover = (): HoverSample | null => {
    const element = [...document.querySelectorAll("main button:hover")].pop();
    if (!element) return null;
    const style = getComputedStyle(element);
    const background = behind(element);
    return {
      sample: (element.textContent ?? "").trim().slice(0, 40),
      ratio: ratio(over(rgba(style.color), background), background),
    };
  };
  return { text, boundaries, rawControls, focused, hover };
}

/** Puts the contrast kit in the page, which keeps it until the page navigates. */
export async function openContrastKit(
  page: Page,
): Promise<JSHandle<ContrastKit>> {
  const colors = await page.evaluateHandle(createColorKit);
  return page.evaluateHandle(createContrastKit, {
    colors,
    minimums: { text: PASS_LINE.text, largeText: PASS_LINE.largeText },
  });
}
