/**
 * Pins the jobs chart's layout (PRD-Studio OP-03, Decision 0022 D14, WCMP-09): the round ticks, the
 * stacking order and gap, and where each bar and the tooltip sit, in the plot's own coordinates.
 * operations-jobs.spec.ts hovers at the same geometry, so the frame is pinned here too.
 */
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FRAME,
  layoutJobs,
  plotTitle,
  SERIES,
  seriesFill,
  ticks,
  tooltipLeft,
  type Bar,
  type Counts,
  type JobsLayout,
} from "../../lib/jobs-layout.ts";

const ZERO: Counts = { succeeded: 0, waited: 0, in_progress: 0, failed: 0 };

function close(actual: number, expected: number): void {
  assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} is not ${expected}`);
}

/** The bar at `index`, which the test expects to exist. */
function barAt(layout: JobsLayout, index: number): Bar {
  const bar = layout.bars[index];
  assert.ok(bar !== undefined, `no bar at ${index}`);
  return bar;
}

test("the frame is the one the suite hovers against", () => {
  assert.equal(FRAME.width, 720);
  assert.equal(FRAME.left, 32);
  assert.equal(FRAME.plotWidth, 684);
  assert.equal(FRAME.plotHeight, 170);
});

test("ticks count by one up to four, then by a round step past the tallest bar", () => {
  assert.deepEqual(ticks(0), [0]);
  assert.deepEqual(ticks(1), [0, 1]);
  assert.deepEqual(ticks(4), [0, 1, 2, 3, 4]);
  assert.deepEqual(ticks(5), [0, 2, 4, 6]);
  assert.deepEqual(ticks(10), [0, 3, 6, 9, 12]);
});

test("no hours draw no bars, on a scale of one", () => {
  const layout = layoutJobs([]);
  assert.deepEqual(layout.bars, []);
  assert.deepEqual(
    layout.ticks.map((tick) => tick.value),
    [0, 1],
  );
  assert.equal(layout.ticks[0]?.y, FRAME.top + FRAME.plotHeight);
  assert.equal(layout.ticks[1]?.y, FRAME.top);
  assert.deepEqual(layout.sums, ZERO);
});

test("hours with no jobs draw empty bars at the baseline", () => {
  const layout = layoutJobs(Array.from({ length: 24 }, () => ZERO));
  assert.equal(layout.bars.length, 24);
  close(layout.band, 28.5);
  for (const bar of layout.bars) {
    assert.deepEqual(bar.segments, []);
    assert.equal(bar.top, FRAME.top + FRAME.plotHeight);
  }
  close(barAt(layout, 0).width, 28.5 * 0.56);
  close(barAt(layout, 0).x, 32 + (28.5 - 28.5 * 0.56) / 2);
  close(barAt(layout, 2).bandX, 32 + 2 * 28.5);
  close(barAt(layout, 2).labelX, 32 + 2.5 * 28.5);
});

test("one tall hour stacks its outcomes in series order, with a gap between them", () => {
  const tall = { succeeded: 6, waited: 2, in_progress: 0, failed: 2 };
  const layout = layoutJobs([ZERO, tall]);
  assert.deepEqual(
    layout.ticks.map((tick) => tick.value),
    [0, 3, 6, 9, 12],
  );
  const bar = barAt(layout, 1);
  assert.deepEqual(
    bar.segments.map((segment) => segment.key),
    ["succeeded", "waited", "failed"],
  );
  const y = (value: number) => 8 + 170 - (value / 12) * 170;
  close(bar.top, y(10));
  assert.deepEqual(
    bar.segments.map((segment) => [segment.y, segment.height]),
    [
      [y(6), y(0) - y(6) - 2],
      [y(8), y(6) - y(8) - 2],
      [y(10), y(8) - y(10) - 2],
    ],
  );
  assert.deepEqual(layout.sums, tall);
});

test("a segment too short for the gap is still one unit tall", () => {
  const layout = layoutJobs([
    { succeeded: 999, waited: 1, in_progress: 0, failed: 0 },
  ]);
  assert.equal(barAt(layout, 0).segments[1]?.height, 1);
});

test("the tooltip follows the hour, and stops at 70% so it stays inside the plot", () => {
  assert.equal(tooltipLeft(0, 28.5), `${((32 + 0.5 * 28.5) / 720) * 100}%`);
  assert.equal(tooltipLeft(21, 28.5), "70%");
});

test("textured series fill with their pattern, and the title names every sum", () => {
  const fills = SERIES.map(seriesFill);
  assert.deepEqual(fills, [
    "var(--success-text)",
    "url(#jobs-waited)",
    "var(--live-text)",
    "url(#jobs-failed)",
  ]);
  assert.equal(
    plotTitle({ succeeded: 1, waited: 2, in_progress: 2, failed: 2 }),
    "Jobs per hour over the last 24 hours: 1 succeeded, 2 waited for a person, 2 in progress, 2 failed or cancelled.",
  );
});
