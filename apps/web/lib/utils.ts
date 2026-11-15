import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

import { RADIUS_STEPS, SPACING_STEPS, TYPE_STEPS } from "./type-scale.ts";

// The theme's named steps join tailwind-merge's scales, so `text-meta` replaces `text-sm` instead of
// being taken for a color and replacing `text-muted-foreground` (R-68).
const twMerge = extendTailwindMerge({
  extend: {
    theme: {
      text: [...TYPE_STEPS],
      radius: [...RADIUS_STEPS],
      spacing: [...SPACING_STEPS],
    },
  },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
