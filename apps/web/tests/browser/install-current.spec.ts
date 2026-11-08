import { expect, test, type Page } from "@playwright/test";

// Decision 0023, read-only on the persistent install: `persistent_install.py screens` runs it, signed in as
// the owner from the install's own record. It writes nothing. No other suite runs it.
const EMAIL = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const SHOTS = process.env.AUTOBOTS_TEST_SCREENSHOTS ?? "";

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

test("US-16.4: Settings → Models shows Sol qualified from today's live pass", async ({
  page,
}) => {
  await signIn(page);
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
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/models.png`, fullPage: true });
});

test("US-16.4: Operations reads the schema ready, with every shipped migration applied", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/operations");
  await expect(page.locator('[data-field="value-schema"]')).toHaveText(
    /^(\d+) of \1 migrations applied\.$/,
  );
  const text = await page.locator("main").innerText();
  for (const leak of ["127.0.0.1", "sk-or-", "eyJ"]) {
    expect(text).not.toContain(leak);
  }
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/operations.png`, fullPage: true });
});

test("US-16.5: Experts and Workflows show the concept seed", async ({
  page,
}) => {
  await signIn(page);
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
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/experts.png`, fullPage: true });
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
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/workflows.png`, fullPage: true });
});

test("US-16.5: Runs shows the real example runs with their outcomes", async ({
  page,
}) => {
  await signIn(page);
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
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/runs.png`, fullPage: true });
});

test("US-16.5: Approvals shows the workflow's request waiting, with requester, run and fields", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/approvals");
  const main = page.locator("main");
  await expect(main.getByText(/workflow_approval/).first()).toBeVisible();
  await expect(main).toContainText(/Vendor due diligence/);
  await expect(main).toContainText(
    "This workflow has an approval step, so policy holds it for a person.",
  );
  const text = await main.innerText();
  for (const leak of ["sk-or-", "eyJ", "127.0.0.1"]) {
    expect(text).not.toContain(leak);
  }
  if (SHOTS)
    await page.screenshot({ path: `${SHOTS}/approvals.png`, fullPage: true });
});
