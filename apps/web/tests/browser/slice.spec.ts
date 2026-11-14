import {
  parseReconciliationResult,
  parseRunCommandResult,
  parseRunWorkspace,
} from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { expectRefusal, getJson, send } from "./support/api.ts";
import { signIn, users } from "./support/auth.ts";
import { twoCountsRun, WorkerScenario } from "./support/builders.ts";
import { expect, test } from "./support/fixtures.ts";
import { ensureProviderKey } from "./support/keys.ts";
import { admitRun, readRun, runCommand } from "./support/runs.ts";

// Different every run, so nothing can pass by knowing the answer in advance.
const FIRST = 100 + Math.floor(Math.random() * 800);
const SECOND = 100 + Math.floor(Math.random() * 800);
const TOTAL = `Total: ${FIRST + SECOND}`;

// Admission needs a usable key, so one is saved first if the workspace has none.
async function signInWithKey(page: Page): Promise<void> {
  await signIn(page, users.owner);
  await ensureProviderKey(page);
  await page.goto("/");
}

/** Admits the two-counts run for `scenario`, under the scenario as its key. */
function admit(page: Page, scenario: string): Promise<string> {
  return admitRun(
    page,
    twoCountsRun(scenario, { first: FIRST, second: SECOND }),
    {
      key: scenario,
    },
  );
}

async function version(page: Page, id: string): Promise<number> {
  return (await readRun(page, id)).version;
}

const status = (page: Page) => page.locator("[data-run-status]");

test("a goal is admitted, planned, executed, restarted and inspected, ending in a verified artifact", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signInWithKey(page);
  const id = await admit(page, WorkerScenario.complete);
  await page.goto(`/runs/${id}`);

  // The worker is killed inside a model call. Its lease runs out, and recovery stops at the unknown.
  await expect(status(page)).toHaveAttribute("data-run-status", "paused", {
    timeout: 40_000,
  });
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "uncertain model call",
  );
  await expect(page.getByText("Write the totals report: open")).toBeVisible();
  const refused = await runCommand(page, {
    run: id,
    command: "resume",
    expectedVersion: await version(page, id),
    key: "resume-early",
  });
  await expectRefusal(refused, { status: 409, code: "uncertain_model_call" });

  // The owner reports the charge from the provider's account, and resumes.
  const reconciled = await send(page, {
    path: `/api/v1/runs/${id}/model-calls/reconcile`,
    key: "reconcile",
    data: { charged_micro_usd: 90 },
    status: 200,
    parse: parseReconciliationResult,
  });
  expect(reconciled.reconciled_calls).toBe(1);
  const resumed = await runCommand(page, {
    run: id,
    command: "resume",
    expectedVersion: await version(page, id),
    key: "resume",
  });
  expect(parseRunCommandResult(await resumed.json()).status).toBe("queued");

  await expect(status(page)).toHaveAttribute("data-run-status", "succeeded", {
    timeout: 40_000,
  });
  await expect(page.locator('[data-verification="passed"]')).toBeVisible();
  await expect(
    page.getByText("Write the totals report: complete"),
  ).toBeVisible();
  await expect(
    page.locator('[data-artifact-status="published"]'),
  ).toContainText("report.md");
  await expect(page.locator("[data-connection]")).toHaveAttribute(
    "data-connection",
    "ended",
    { timeout: 15_000 },
  );

  // Inspected: the artifact is the verified bytes, once, and the record replays after a reload.
  const workspace = await getJson(page, {
    path: `/api/v1/runs/${id}/workspace`,
    parse: parseRunWorkspace,
  });
  expect(workspace.artifacts).toHaveLength(1);
  const download = await page.request.get(
    `/api/v1/artifacts/${workspace.artifacts[0]?.id}/download`,
  );
  expect(await download.text()).toContain(TOTAL);
  expect(workspace.run.budget.spent_micro_usd).toBeGreaterThan(0);
  expect(workspace.outstanding.uncertain_calls).toBe(0);
  expect(workspace.objective).toContain(WorkerScenario.complete);
  expect(workspace.plan?.version).toBe(1);
  expect(workspace.usage.model_calls).toBeGreaterThan(5);
  await page.reload();
  await expect(status(page)).toHaveAttribute("data-run-status", "succeeded");
  const sequences = await page
    .locator("[data-sequence]")
    .evaluateAll((items) =>
      items.map((item) => Number(item.getAttribute("data-sequence"))),
    );
  expect(sequences).toEqual(sequences.map((_, index) => index + 1));
  await expect(
    page.locator("[data-sequence]").filter({ hasText: "report.md published" }),
  ).toHaveCount(1);
  await expectNoA11yViolations(page);
});

test("a missing required artifact fails the run, whatever the model said", async ({
  page,
}) => {
  await signInWithKey(page);
  const id = await admit(page, WorkerScenario.noArtifact);
  await page.goto(`/runs/${id}`);
  await expect(status(page)).toHaveAttribute("data-run-status", "failed", {
    timeout: 40_000,
  });
  await expect(page.locator('[data-verification="failed"]')).toContainText(
    "artifact missing: report.md",
  );
  await expect(
    page.getByText("Write the totals report: complete"),
  ).toBeVisible();
});

test("a failed deterministic check fails the run, and the artifact is still inspectable", async ({
  page,
}) => {
  await signInWithKey(page);
  const id = await admit(page, WorkerScenario.wrongTotal);
  await page.goto(`/runs/${id}`);
  await expect(status(page)).toHaveAttribute("data-run-status", "failed", {
    timeout: 40_000,
  });
  await expect(page.locator('[data-verification="failed"]')).toContainText(
    "artifact check failed: report.md",
  );
  await expect(
    page.locator('[data-artifact-status="published"]'),
  ).toContainText("report.md");
});

test("an answer alone can't succeed", async ({ page }) => {
  await signInWithKey(page);
  const id = await admit(page, WorkerScenario.onlyClaims);
  await page.goto(`/runs/${id}`);
  await expect(status(page)).toHaveAttribute("data-run-status", "failed", {
    timeout: 40_000,
  });
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "plan missing",
  );
});
