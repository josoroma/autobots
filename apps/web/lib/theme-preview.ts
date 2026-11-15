/**
 * The Appearance control's theme swatches. Each previews its own theme whatever the page is in, so it
 * can't inherit `:root` inside a dark page and repeats the exact luma.css declaration instead (DS-01,
 * Decision 0021 R2). `PREVIEW_TOKENS` names the declaration each copies, and a unit test compares the
 * two, so the copy can't drift from the canonical palette (WSYS-19).
 */

export const PREVIEWS = {
  dark: {
    surface: "bg-[oklch(0.145_0_0)]",
    side: "bg-[oklch(0.205_0_0)]",
    bar: "bg-[oklch(0.269_0_0)]",
    accent: "bg-[oklch(0.623_0.214_259.815)]",
  },
  light: {
    surface: "bg-[oklch(1_0_0)]",
    side: "bg-[oklch(0.985_0_0)]",
    bar: "bg-[oklch(0.922_0_0)]",
    accent: "bg-[oklch(0.546_0.245_262.881)]",
  },
} as const;

export type PreviewTheme = keyof typeof PREVIEWS;

/** The luma.css custom property each swatch repeats, per theme. */
export const PREVIEW_TOKENS: Readonly<
  Record<PreviewTheme, Record<keyof (typeof PREVIEWS)["dark"], string>>
> = {
  dark: {
    surface: "--background",
    side: "--sidebar",
    bar: "--muted",
    accent: "--sidebar-primary",
  },
  light: {
    surface: "--background",
    side: "--sidebar",
    bar: "--border",
    accent: "--sidebar-primary",
  },
};
