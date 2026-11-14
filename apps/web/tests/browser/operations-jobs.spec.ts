import { parseJobsChart } from "@autobots/api-client";

import { expectNoA11yViolations, WCAG_22_AA } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { need } from "./support/env.ts";
import { objectOf, runDbHelper } from "./support/db-helpers.ts";
import { expect, test } from "./support/fixtures.ts";

// US-15.19, PRD-Studio OP-03 and Decision 0022 D14. tests/db/operations_live.py gives the ops-n workspace,
// in Costa Rica's time, runs whose status changes fall a set number of hours before now:
//   1 hour: one failed and one cancelled; 2 hours: one succeeded and one waiting for approval;
//   3 hours: one paused and one running, at their latest change; 5 hours: one waiting for input;
//   30 hours: one succeeded, outside the chart.
const SERIES = ["succeeded", "waited", "in_progress", "failed"] as const;
type Counts = Record<(typeof SERIES)[number], number>;
const NONE: Counts = { succeeded: 0, waited: 0, in_progress: 0, failed: 0 };
// Hours before the current one, and what each should count.
const EXPECTED: Record<number, Counts> = {
  1: { ...NONE, failed: 2 },
  2: { ...NONE, succeeded: 1, waited: 1 },
  3: { ...NONE, in_progress: 2 },
  5: { ...NONE, waited: 1 },
};

function costaRicaHour(date: Date): string {
  const hour = new Intl.DateTimeFormat("en-GB", {
    timeZone: "America/Costa_Rica",
    hour: "2-digit",
    hourCycle: "h23",
  }).format(date);
  return `${hour}:00`;
}

test.beforeAll(async () => {
  // The ops-n workspace is arranged, or this names the variable that's missing.
  need("AUTOBOTS_TEST_OPS_EMAIL");
  await runDbHelper(
    "operations_live.py",
    ["jobs"],
    objectOf({ action: "string" }),
  );
});

test("the chart shows 24 hours of jobs by outcome, with a legend, textures and a table of the same counts", async ({
  page,
}) => {
  await signIn(page, users.ops);
  const chart = await getJson(page, {
    path: "/api/v1/operations/jobs",
    parse: parseJobsChart,
  });
  expect(chart.timezone).toBe("America/Costa_Rica");
  expect(chart.hours).toHaveLength(24);
  const current = chart.hours.at(-1);
  if (current === undefined) throw new Error("The chart has no hours.");
  expect(current.hour).toBe(costaRicaHour(new Date(current.starts_at)));
  expect(current.hour).toBe(costaRicaHour(new Date()));
  chart.hours.forEach((hour, index) => {
    const before = chart.hours.length - 1 - index;
    const expected = EXPECTED[before] ?? NONE;
    for (const series of SERIES)
      expect(hour[series], `${series} ${before} hours before now`).toBe(
        expected[series],
      );
  });

  await page.goto("/operations");
  const section = page.locator('[data-field="jobs-chart"]');
  await expect(
    section.getByRole("heading", { name: "Jobs per hour, last 24 hours" }),
  ).toBeVisible();
  const plot = section.getByRole("img");
  await expect(plot).toBeVisible();
  await expect(plot).toHaveAccessibleName(
    "Jobs per hour over the last 24 hours: 1 succeeded, 2 waited for a person, 2 in progress, 2 failed or cancelled.",
  );
  await expect(section.locator('[data-field="jobs-legend"] > li')).toHaveText([
    "Succeeded 1",
    "Waited for a person 2",
    "In progress 2",
    "Failed or cancelled 2",
  ]);
  // Patterns as well as colour: waited and failed are textured, at 45° and 135°.
  await expect(section.locator("pattern#jobs-waited")).toHaveAttribute(
    "patternTransform",
    "rotate(45)",
  );
  await expect(section.locator("pattern#jobs-failed")).toHaveAttribute(
    "patternTransform",
    "rotate(135)",
  );
  await expect(section.locator("g[data-hour]")).toHaveCount(24);

  await section.getByText("Table of the same counts").click();
  const rows = section.locator('[data-field="jobs-table"] tbody tr');
  await expect(rows).toHaveCount(24);
  for (const [index, hour] of chart.hours.entries()) {
    const row = rows.nth(index);
    await expect(row.locator("th")).toHaveText(hour.hour);
    for (const series of SERIES)
      await expect(row.locator(`td[data-series="${series}"]`)).toHaveText(
        String(hour[series]),
      );
  }

  // The hover layer names the hour and its counts.
  await plot.hover({ position: { x: 20, y: 20 } });
  const box = await plot.boundingBox();
  expect(box).not.toBeNull();
  if (box !== null) {
    const twoBefore = 21;
    const x = box.width * ((32 + (twoBefore + 0.5) * (684 / 24)) / 720);
    await page.mouse.move(box.x + x, box.y + box.height / 2);
    const tooltip = section.locator('[data-field="jobs-tooltip"]');
    await expect(tooltip).toContainText(chart.hours[twoBefore]?.hour ?? "");
    await expect(tooltip).toContainText("Succeeded: 1");
    await expect(tooltip).toContainText("Waited for a person: 1");
  }

  await expectNoA11yViolations(page, { extraTags: WCAG_22_AA });
});

test("the chart's read holds hourly counts by outcome only, with no identifier or goal text", async ({
  page,
}) => {
  await signIn(page, users.ops);
  const body = await getJson(page, {
    path: "/api/v1/operations/jobs",
    parse: parseJobsChart,
  });
  expect(Object.keys(body).sort()).toEqual([
    "hours",
    "schema_version",
    "timezone",
  ]);
  for (const hour of body.hours)
    expect(Object.keys(hour).sort()).toEqual([
      "failed",
      "hour",
      "in_progress",
      "starts_at",
      "succeeded",
      "waited",
    ]);
  const text = JSON.stringify(body);
  expect(text).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/);
  for (const goal of ["Arranged chart job", "Operations job"])
    expect(text).not.toContain(goal);
});
