import type { Page } from "@playwright/test";

import { signIn, users } from "./support/auth.ts";
import { optional } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";

// Decision 0023, read-only on the persistent install: `persistent_install.py screens` runs the
// install-current project, signed in as the owner from the install's own record. It writes nothing,
// and no profile runs it.

// scripts/persistent_install.py names this directory, and a run by hand takes no screenshot.
async function shoot(page: Page, file: string): Promise<void> {
  const shots = optional("AUTOBOTS_TEST_SCREENSHOTS", "");
  if (shots)
    await page.screenshot({ path: `${shots}/${file}`, fullPage: true });
}

test("US-16.4: Settings → Models shows Sol qualified from today's live pass", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/settings/models");
  const sol = page.locator('[data-route="openrouter_sol"]');
  await expect(sol.locator('[data-route-field="status"]')).toHaveText(
    "Qualified, with the limits below",
  );
  await expect(sol.locator('[data-route-field="date"]')).toHaveText(
    "2026-11-08",
  );
  await expect(sol.locator('[data-route-field="limits"]')).toContainText(
    "each of two days, 2026-11-07 and 2026-11-08",
  );
  await expect(sol.locator('[data-route-field="configuration"]')).toContainText(
    "openai/gpt-6.1-sol",
  );
  await shoot(page, "models.png");
});

test("US-16.4: Operations reads the schema ready, with every shipped migration applied", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/operations");
  await expect(page.locator('[data-field="value-schema"]')).toHaveText(
    /^(\d+) of \1 migrations applied\.$/,
  );
  expectNoPrivateValues(await page.locator("main").innerText(), {
    label: "Operations",
  });
  await shoot(page, "operations.png");
});

test("US-16.5: Experts and Workflows show the concept seed", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/experts");
  for (const name of [
    "Market watcher",
    "Research analyst",
    "Brief writer",
    "Issue triager",
    "Code maintainer",
  ]) {
    await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  }
  await shoot(page, "experts.png");
  await page.goto("/workflows");
  for (const name of [
    "Weekly competitor brief",
    "Monthly FX and inflation note",
    "Nightly test triage",
    "Interview synthesis",
    "Release notes from merged PRs",
    "Vendor due diligence",
  ]) {
    await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
  }
  await shoot(page, "workflows.png");
});

test("US-16.5: Runs shows the real example runs with their outcomes", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/runs");
  await expect(
    page.getByText(/Work out what US\$1,000 grows to/).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/explain why keeping an AI agent's run records/).first(),
  ).toBeVisible();
  await expect(
    page.getByText(/Workflow Vendor due diligence/).first(),
  ).toBeVisible();
  await shoot(page, "runs.png");
});

test("US-16.5: Approvals shows the workflow's request waiting, with requester, run and fields", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/approvals");
  const main = page.locator("main");
  await expect(main.getByText(/workflow_approval/).first()).toBeVisible();
  await expect(main).toContainText(/Vendor due diligence/);
  await expect(main).toContainText(
    "This workflow has an approval step, so policy holds it for a person.",
  );
  expectNoPrivateValues(await main.innerText(), { label: "Approvals" });
  await shoot(page, "approvals.png");
});
