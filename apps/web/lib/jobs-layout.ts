/**
 * The jobs chart's series and layout in plot coordinates (PRD-Studio OP-03, Decision 0022 D14,
 * WCMP-09): the round ticks, each hour's band and bar, and its outcomes stacked with a surface gap.
 * Pure and JSX-free, so `node --test` covers it; jobs-bars.tsx only draws what this returns.
 */
import type { JobHour } from "@autobots/api-client";

export type SeriesKey = "succeeded" | "waited" | "in_progress" | "failed";

/** One hour's counts by outcome. */
export type Counts = Pick<JobHour, SeriesKey>;

export interface Series {
  key: SeriesKey;
  label: string;
  color: string;
  /** The texture's angle in degrees, or null for a solid fill. */
  texture: number | null;
}

// Each series means an outcome, so it wears its status token, never a categorical hue. Stacked in
// the order that keeps neighbours furthest apart under colour blindness (validated: worst adjacent
// ΔE 8.9 light, 10.4 dark). Waited and failed also carry a texture, at 45° and 135°, so no series
// depends on colour alone (Decision 0022 D14).
export const SERIES: readonly Series[] = [
  {
    key: "succeeded",
    label: "Succeeded",
    color: "var(--success-text)",
    texture: null,
  },
  {
    key: "waited",
    label: "Waited for a person",
    color: "var(--attention)",
    texture: 45,
  },
  {
    key: "in_progress",
    label: "In progress",
    color: "var(--live-text)",
    texture: null,
  },
  {
    key: "failed",
    label: "Failed or cancelled",
    color: "var(--destructive)",
    texture: 135,
  },
];

const WIDTH = 720;
const HEIGHT = 200;
const LEFT = 32;
const RIGHT = 4;
const TOP = 8;
const BOTTOM = 22;

/** The SVG's view box and the plot inside it. */
export const FRAME = {
  width: WIDTH,
  height: HEIGHT,
  left: LEFT,
  top: TOP,
  plotWidth: WIDTH - LEFT - RIGHT,
  plotHeight: HEIGHT - TOP - BOTTOM,
} as const;

// A surface gap between stacked segments.
const GAP = 2;

/**
 * A textured series' pattern id. The ids are fixed, as operations-jobs.spec.ts reads
 * `pattern#jobs-waited`, so the chart renders once per page.
 */
export function patternId(key: SeriesKey): string {
  return `jobs-${key}`;
}

export function seriesFill(series: Series): string {
  return series.texture === null
    ? series.color
    : `url(#${patternId(series.key)})`;
}

export function total(hour: Counts): number {
  return SERIES.reduce((sum, series) => sum + hour[series.key], 0);
}

/** A few round ticks up to the tallest bar, so the grid stays recessive. */
export function ticks(top: number): number[] {
  if (top <= 4) return Array.from({ length: top + 1 }, (_, index) => index);
  const step = Math.ceil(top / 4);
  return Array.from({ length: Math.ceil(top / step) + 1 }, (_, i) => i * step);
}

export interface Segment {
  key: SeriesKey;
  fill: string;
  y: number;
  height: number;
}

export interface Bar {
  index: number;
  /** Where the hour's band starts, which is also its hover target. */
  bandX: number;
  /** The centre of the band, where the hour's label sits. */
  labelX: number;
  x: number;
  width: number;
  /** The top of the stack, where the bar's rounded end is. */
  top: number;
  segments: Segment[];
}

export interface JobsLayout {
  ticks: { value: number; y: number }[];
  band: number;
  bars: Bar[];
  sums: Counts;
}

function stack(hour: Counts, y: (value: number) => number): Segment[] {
  const segments: Segment[] = [];
  let base = 0;
  for (const series of SERIES) {
    const value = hour[series.key];
    if (value === 0) continue;
    const lower = y(base);
    base += value;
    const upper = y(base);
    segments.push({
      key: series.key,
      fill: seriesFill(series),
      y: upper,
      height: Math.max(lower - upper - GAP, 1),
    });
  }
  return segments;
}

export function layoutJobs(hours: readonly Counts[]): JobsLayout {
  const tallest = Math.max(1, ...hours.map(total));
  const values = ticks(tallest);
  const scaleTop = values.at(-1) ?? tallest;
  const band = FRAME.plotWidth / Math.max(hours.length, 1);
  const width = Math.max(4, band * 0.56);
  const y = (value: number) =>
    TOP + FRAME.plotHeight - (value / scaleTop) * FRAME.plotHeight;
  const sums: Counts = { succeeded: 0, waited: 0, in_progress: 0, failed: 0 };
  for (const hour of hours)
    for (const series of SERIES) sums[series.key] += hour[series.key];
  return {
    ticks: values.map((value) => ({ value, y: y(value) })),
    band,
    bars: hours.map((hour, index) => {
      const bandX = LEFT + index * band;
      return {
        index,
        bandX,
        labelX: bandX + band / 2,
        x: bandX + (band - width) / 2,
        width,
        top: y(total(hour)),
        segments: stack(hour, y),
      };
    }),
    sums,
  };
}

/** The tooltip's left edge for an hour, as a share of the plot, kept clear of the right edge. */
export function tooltipLeft(index: number, band: number): string {
  return `${Math.min(((LEFT + (index + 0.5) * band) / WIDTH) * 100, 70)}%`;
}

/** The plot's accessible name: every series' total in words. */
export function plotTitle(sums: Counts): string {
  const parts = SERIES.map(
    (series) => `${sums[series.key]} ${series.label.toLowerCase()}`,
  );
  return `Jobs per hour over the last 24 hours: ${parts.join(", ")}.`;
}
