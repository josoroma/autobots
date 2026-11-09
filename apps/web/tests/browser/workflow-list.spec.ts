import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// US-15.13, PRD-Studio WF-01 and WF-03 to WF-05 and Decision 0022 D11, against an owner arranged by
// scripts/qualify_identity.py: a US$10.00 daily cap, "Weekly brief" (versions 1 and 2, a draft and
// three executions) and "Plain totals" (published versions only).
const EMAIL = process.env.AUTOBOTS_TEST_FLOWS_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_FLOWS_PASSWORD ?? "";
const BRIEF = process.env.AUTOBOTS_TEST_FLOWS_BRIEF ?? "";
const PLAIN = process.env.AUTOBOTS_TEST_FLOWS_PLAIN ?? "";
const RUNS = (process.env.AUTOBOTS_TEST_FLOWS_RUNS ?? "").split(",");

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

async function noViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
}

async function write(page: Page, key: string): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  };
}

test.describe.configure({ mode: "serial" });

test("the list's tabs, search and row facts", async ({ page }) => {
  await signIn(page);
  await page.goto("/workflows");
  const rows = page.locator("[data-workflow]");
  await expect(rows).toHaveCount(2);
  const brief = page.locator(`[data-workflow="${BRIEF}"]`);
  await expect(
    brief.getByRole("link", { name: "Weekly brief", exact: true }),
  ).toBeVisible();
  await expect(brief.locator('[data-field="description"]')).toHaveText(
    "Research, then a brief for review",
  );
  await expect(brief.locator('[data-field="experts"]')).toHaveText(
    "Research analyst → Brief writer",
  );
  await expect(brief).toContainText("Version 2");
  await expect(brief.locator('[data-field="has-draft"]')).toHaveText("Draft");
  await expect(brief.locator('[data-field="steps"]')).toHaveText("5");
  await expect(brief.locator('[data-field="last-execution"]')).toHaveText(
    /^Running, \d+ minutes ago$/,
  );
  await expect(brief.locator('[data-field="runs"]')).toHaveText("3");
  const plain = page.locator(`[data-workflow="${PLAIN}"]`);
  await expect(plain.locator('[data-field="description"]')).toHaveCount(0);
  await expect(plain.locator('[data-field="experts"]')).toHaveText("None");
  await expect(plain.locator('[data-field="has-draft"]')).toHaveCount(0);
  await expect(plain.locator('[data-field="last-execution"]')).toHaveText(
    "Never run",
  );
  await expect(plain.locator('[data-field="runs"]')).toHaveText("0");

  const tab = (name: string) =>
    page.getByRole("navigation", { name: "Workflow tabs" }).getByRole("link", {
      name: new RegExp(`^${name} \\d+$`),
    });
  await expect(tab("All")).toHaveText("All 2");
  await expect(tab("Published")).toHaveText("Published 2");
  await expect(tab("Drafts")).toHaveText("Drafts 1");
  await tab("Drafts").click();
  await expect(page).toHaveURL(/tab=drafts/);
  await expect(rows).toHaveCount(1);
  await expect(page.locator(`[data-workflow="${BRIEF}"]`)).toBeVisible();
  await tab("Published").click();
  await expect(rows).toHaveCount(2);
  await tab("All").click();
  await page.getByRole("searchbox", { name: "Search" }).fill("plain");
  await expect(page).toHaveURL(/q=plain/);
  await expect(rows).toHaveCount(1);
  await expect(page.locator(`[data-workflow="${PLAIN}"]`)).toBeVisible();
  await noViolations(page);
});

test("the preview's version switch shows each version's steps in order", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/workflows");
  await page.getByRole("link", { name: "Preview Weekly brief" }).click();
  const panel = page.locator(`[data-panel="${BRIEF}"]`);
  // The preview sits under the list: choosing it brings it into view, with focus on its heading.
  const heading = panel.getByRole("heading", { name: "Preview: Weekly brief" });
  await expect(heading).toBeFocused();
  await expect(heading).toBeInViewport();
  const version = panel.getByLabel("Version");
  await expect(version).toHaveValue("2");
  await expect(version.locator("option")).toHaveText([
    "Version 2",
    "Version 1",
    "Draft",
  ]);
  const steps = panel.locator("[data-step]");
  await expect(steps).toHaveCount(5);
  expect(
    await steps.evaluateAll((items) =>
      items.map((item) => item.getAttribute("data-step")),
    ),
  ).toEqual(["in", "research", "write", "gate", "out"]);
  const research = panel.locator('[data-step="research"]');
  await expect(research).toContainText("Find sources");
  await expect(research.locator('[data-field="step-expert"]')).toHaveText(
    "Research analyst",
  );
  await expect(research.locator('[data-field="step-model"]')).toHaveText(
    "openai/gpt-6.1-sol-20260929",
  );
  await expect(research.locator('[data-field="step-tools"]')).toHaveText(
    "calculate, read_csv",
  );
  const writing = panel.locator('[data-step="write"]');
  await expect(writing).toContainText("Write the weekly brief");
  await expect(writing.locator('[data-field="step-expert"]')).toHaveText(
    "Brief writer",
  );
  await expect(writing.locator('[data-field="step-model"]')).toHaveText(
    "openai/gpt-6.1-terra-20261026",
  );
  await expect(writing.locator('[data-field="step-tools"]')).toHaveText(
    "save_artifact",
  );
  await expect(
    panel.locator('[data-step="gate"] [data-field="approval-gate"]'),
  ).toHaveText("Approval gate: a person approves before the run continues.");

  await version.selectOption("1");
  await expect(page).toHaveURL(/version=1/);
  await expect(writing).toContainText("Write the brief");
  await expect(writing).not.toContainText("weekly");
  await version.selectOption("draft");
  await expect(writing).toContainText("Draft writer");
  await noViolations(page);
});

test("recent executions show version, state, spend estimated or reported, and duration", async ({
  page,
}) => {
  await signIn(page);
  await page.goto(`/workflows?workflow=${BRIEF}`);
  const panel = page.locator(`[data-panel="${BRIEF}"]`);
  const executions = panel.locator("[data-execution]");
  await expect(executions).toHaveCount(3);
  const expected = [
    ["Version 2", "Running", "≈ US$0.05, estimated", "still running"],
    ["Version 2", "Failed", "≈ US$0.04, estimated", "2m 00s"],
    ["Version 1", "Succeeded", "US$0.12, reported", "1m 05s"],
  ] as const;
  for (const [index, [label, state, spend, took]] of expected.entries()) {
    const row = executions.nth(index);
    await expect(row.getByRole("link")).toHaveText(label);
    await expect(row.locator('[data-field="state"]')).toHaveText(state);
    await expect(row.locator('[data-field="spend"]')).toHaveText(spend);
    await expect(row.locator('[data-field="duration"]')).toHaveText(took);
  }
  await expect(executions.nth(2).getByRole("link")).toHaveAttribute(
    "href",
    `/runs/${RUNS[0]}`,
  );
  await noViolations(page);
});

test("an execution's budget is frozen on its run, and one outside the range starts nothing", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/workflows");
  const base = `/api/v1/workflows/${PLAIN}/executions`;
  const count = async () =>
    (await (await page.request.get(base)).json()).executions.length;
  const before = await count();
  // The editor offers the full range, as more than US$5.00 is left today.
  await page.goto(`/workflows/${PLAIN}`);
  const budget = page.getByLabel("Budget");
  await expect(budget.locator("option")).toHaveCount(20);
  await expect(budget.locator("option").last()).toHaveText("US$5.00");
  await budget.selectOption("2500000");
  await page.getByLabel("Inputs").fill('{"in": "two fifty"}');
  const sent = page.waitForResponse(
    (reply) =>
      reply.url().endsWith(`/workflows/${PLAIN}/executions`) &&
      reply.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Run this version" }).click();
  const reply = await sent;
  expect(reply.status()).toBe(201);
  expect(reply.request().postDataJSON().budget_micro_usd).toBe(2_500_000);
  const { run_id } = await reply.json();
  const run = await (await page.request.get(`/api/v1/runs/${run_id}`)).json();
  expect(run.budget.limit_micro_usd).toBe(2_500_000);

  const refused = await page.request.post(base, {
    headers: await write(page, `over-${Date.now()}`),
    data: {
      version: 2,
      inputs: { in: "too much" },
      budget_micro_usd: 5_250_000,
    },
  });
  expect(refused.status()).toBe(422);
  expect((await refused.json()).code).toBe("budget_out_of_range");
  expect(await count()).toBe(before + 1);
});
