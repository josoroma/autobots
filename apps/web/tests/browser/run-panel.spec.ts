import type { Page } from "@playwright/test";

import { expectNoA11yViolations, WCAG_22_AA } from "./support/a11y.ts";
import { signIn, users } from "./support/auth.ts";
import { arranged } from "./support/env.ts";
import { objectOf, runDbHelper } from "./support/db-helpers.ts";
import { expect, test } from "./support/fixtures.ts";
import { readRun } from "./support/runs.ts";

// US-15.17, PRD-Studio RN-04: the side panel on Runs. tests/db/checks/task_timing_check.py arranges a running
// run with one done, one current and one to-do task and three metered calls, and a cancelled run.
const panelRun = arranged({
  id: "AUTOBOTS_TEST_PANEL_RUN",
  terminal: "AUTOBOTS_TEST_PANEL_TERMINAL",
  generation: "AUTOBOTS_TEST_PANEL_GENERATION",
  workspace: "AUTOBOTS_TEST_PANEL_WORKSPACE",
});

test.describe.configure({ mode: "serial" });

// Finds the run by its goal with the list's own filter, then selects its row's Details.
async function openPanel(
  page: Page,
  runId: string,
  goal: string,
): Promise<void> {
  await page.goto("/runs");
  await page
    .getByRole("searchbox", { name: "Filter by goal or Expert" })
    .fill(goal);
  const row = page.locator(`li[data-run="${runId}"]`);
  await row.locator('[data-field="details"]').click();
  await expect(page).toHaveURL(new RegExp(`[?&]run=${runId}`));
  await expect(page.locator(`section[data-panel="${runId}"]`)).toBeVisible();
}

// The current worker moves the run's version through two canonical transitions, leaving it running.
function moveVersion(): Promise<{ from: number; to: number; status: string }> {
  return runDbHelper(
    "task_timing_live.py",
    [panelRun.id, panelRun.generation, panelRun.workspace],
    objectOf({ from: "number", to: "number", status: "string" }),
  );
}

test("The panel shows the run's state, plan, task tools and times, spend, tokens and metered calls", async ({
  page,
}) => {
  const run = panelRun.id;
  await signIn(page, users.owner);
  await openPanel(page, run, "Summarize the quarter figures");
  const panel = page.locator(`section[data-panel="${run}"]`);
  await expect(panel.locator('[data-field="state"]')).toHaveText("Running");
  await expect(
    panel.getByRole("heading", { name: "Summarize the quarter figures" }),
  ).toBeVisible();
  await expect(panel.locator('[data-field="panel-expert"]')).toHaveText(
    "Figures analyst",
  );
  await expect(panel.locator('[data-field="panel-started"]')).toHaveText(
    /^\d{4}-\d{2}-\d{2}T/,
  );

  const tasks = panel.locator('[data-field="panel-plan"] > li');
  await expect(tasks).toHaveCount(3);
  await expect(tasks.locator('[data-field="task-marker"]')).toHaveText([
    "Done",
    "Current",
    "To do",
  ]);
  const gather = panel.locator('li[data-task="gather"]');
  await expect(gather.locator('[data-field="task-tools"]')).toHaveText(
    "calculate, save_artifact",
  );
  await expect(gather.locator('[data-field="task-wall"]')).toHaveText(
    /^\d+s$|^\d+m \d{2}s$/,
  );
  const write = panel.locator('li[data-task="write"]');
  await expect(write.locator('[data-field="task-tools"]')).toHaveText(
    "save_artifact",
  );
  await expect(write.locator('[data-field="task-wall"]')).toHaveText(
    /^\d+s$|^\d+m \d{2}s$/,
  );
  const review = panel.locator('li[data-task="review"]');
  await expect(review.locator('[data-field="task-tools"]')).toHaveText(
    "None used yet",
  );
  await expect(review.locator('[data-field="task-wall"]')).toHaveText("—");

  await expect(panel.locator('[data-field="panel-spend"]')).toHaveText(
    /^US\$0\.00 of US\$1\.00$/,
  );
  await expect(panel.locator('[data-field="panel-tokens"]')).toHaveText(
    "0 in, 0 out",
  );
  await expect(panel.locator('[data-field="panel-metered"]')).toHaveText(
    "3 of 20 metered tool calls",
  );
  await expect(panel.getByRole("link", { name: "Open run" })).toHaveAttribute(
    "href",
    `/runs/${run}`,
  );
  await expect(
    page.locator(`li[data-run="${run}"] [data-field="details"]`),
  ).toHaveAttribute("aria-expanded", "true");

  await expectNoA11yViolations(page, { extraTags: WCAG_22_AA });
});

test("A stale Pause is refused with a reload message, a fresh one pauses, and a finished run offers no controls", async ({
  page,
}) => {
  const run = panelRun.id;
  await signIn(page, users.owner);
  await openPanel(page, run, "Summarize the quarter figures");
  const panel = page.locator(`section[data-panel="${run}"]`);
  const loaded = Number(await panel.getAttribute("data-version"));
  const moved = await moveVersion();
  expect(moved.from).toBe(loaded);
  expect(moved.to).toBeGreaterThan(loaded);
  expect(moved.status).toBe("running");

  await panel.getByRole("button", { name: "Pause" }).click();
  const refusal = panel.getByRole("alert");
  await expect(refusal).toContainText(
    "This run changed after the panel loaded, so nothing was done.",
  );
  expect((await readRun(page, run)).status).toBe("running");

  await panel.getByRole("button", { name: "Reload the panel" }).click();
  await expect(panel).toHaveAttribute("data-version", String(moved.to));
  await expect(refusal).toHaveCount(0);
  await panel.getByRole("button", { name: "Pause" }).click();
  await expect(panel.locator('[data-field="state"]')).toHaveText("Paused");
  await expect(panel.getByRole("button", { name: "Resume" })).toBeVisible();
  const body = await readRun(page, run);
  expect(body.status).toBe("paused");
  expect(body.version).toBe(moved.to + 1);
  await expect(
    page.locator(`li[data-run="${run}"] [data-field="state"]`),
  ).toHaveText("Paused");

  await openPanel(page, panelRun.terminal, "An ended run for the panel");
  const ended = page.locator(`section[data-panel="${panelRun.terminal}"]`);
  await expect(ended.locator('[data-field="state"]')).toHaveText("Cancelled");
  await expect(ended.getByRole("link", { name: "Open run" })).toBeVisible();
  for (const name of ["Pause", "Resume", "Cancel run"])
    await expect(ended.getByRole("button", { name })).toHaveCount(0);
});
