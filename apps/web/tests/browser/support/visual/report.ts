/**
 * The visual walk's findings by name, and its evidence file, results.json, in the
 * autobots.visual-evidence/v1 schema (US-11.11). WCAG 2.1 AA is the pass line, by Decision 0010.
 */
import { writeFileSync } from "node:fs";
import { join } from "node:path";

import { PASS_LINE } from "./contrast.ts";
import type { Measured } from "./measure.ts";
import { ABSENT, type Theme } from "./surfaces.ts";

/** A surface that never showed what it's captured for, so nothing on it was measured. */
export interface NeverReady {
  surface: string;
  theme: Theme;
  reason: string;
}

/** What one walk found, kept as it goes so a failure part way still leaves its evidence. */
export interface Walk {
  results: Measured[];
  neverReady: NeverReady[];
}

// Each check of the pass line, by the name a failing step reports.
const CHECKS: readonly (readonly [string, (item: Measured) => boolean])[] = [
  ["text contrast", (item) => item.text_failures.length > 0],
  ["control boundary", (item) => item.boundary_failures.length > 0],
  ["shadowed card", (item) => item.shadowed_cards.length > 0],
  ["focus contrast", (item) => item.focus_failures.length > 0],
  [
    "hover contrast",
    (item) => item.hover !== null && item.hover.ratio < PASS_LINE.text,
  ],
  ["axe violation", (item) => item.axe_violations.length > 0],
  ["raw control", (item) => item.raw_controls.length > 0],
  ["no tab stop", (item) => item.keyboard.stops === 0],
  ["keyboard walk cut short", (item) => item.keyboard.truncated],
  [
    "control unreached in main",
    (item) => item.keyboard.unreached_in_main.length > 0,
  ],
  [
    "focus moves up the page",
    (item) => item.keyboard.upward_in_main.length > 0,
  ],
  ["positive tabindex", (item) => item.keyboard.positive_tabindex > 0],
  ["unnamed disabled control", (item) => item.disabled.unnamed.length > 0],
  [
    "moves under reduced motion",
    (item) => item.motion.moving_when_reduced.length > 0,
  ],
  [
    "sideways scrolling at zoom",
    (item) => Object.values(item.zoom).some((over) => over > 0),
  ],
];

/** The checks the measured surface fails, by name; none when it meets the pass line. */
export function findingsOf(item: Measured): string[] {
  return CHECKS.filter(([, fails]) => fails(item)).map(([name]) => name);
}

const label = (item: { surface: string; theme: Theme }) =>
  `${item.surface}-${item.theme}`;

/** Writes `out`/results.json from what the walk has found so far. */
export function writeEvidence(
  out: string,
  { results, neverReady }: Walk,
): void {
  writeFileSync(
    join(out, "results.json"),
    JSON.stringify(
      {
        schema_version: "autobots.visual-evidence/v1",
        pass_line: "WCAG 2.1 AA, Decision 0010",
        surfaces: results.length,
        with_findings: [
          ...results.filter((item) => findingsOf(item).length > 0),
          ...neverReady,
        ].map(label),
        never_ready: neverReady,
        absent: ABSENT,
        results,
      },
      null,
      2,
    ),
  );
}
