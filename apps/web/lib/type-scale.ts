/**
 * The names of the theme's own type, radius and spacing steps in app/globals.css (R-68, DS-03). `cn`
 * reads them so that tailwind-merge treats `text-meta` as a font size, not a text color, and a
 * unit test keeps this list equal to the stylesheet's `@theme` block.
 */
export const TYPE_STEPS = [
  "kbd",
  "tag",
  "caption",
  "meta",
  "ui",
  "body",
  "intro",
  "lead",
  "goal",
  "banner",
  "display",
  "title",
  "hero",
] as const;

export const RADIUS_STEPS = ["inset"] as const;

export const SPACING_STEPS = ["dot"] as const;
