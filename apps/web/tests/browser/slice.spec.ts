import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const EMAIL = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  await page.goto("/settings/models");
  const source = page.locator('[data-field="source"]');
  await expect(source).toBeVisible();
  if ((await source.textContent())?.trim() === "None") {
    await page
      .getByLabel(/API key|Replace key/)
      .fill("sk-or-valid-arranged-first");
    await page.getByRole("button", { name: "Save & validate" }).click();
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
  await page.goto("/");
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

// Different every run, so nothing can pass by knowing the answer in advance.
const FIRST = 100 + Math.floor(Math.random() * 800);
const SECOND = 100 + Math.floor(Math.random() * 800);
const TOTAL = `Total: ${FIRST + SECOND}`;

async function admit(page: Page, goal: string): Promise<string> {
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, goal),
    data: {
      goal_text: `${goal}: report the total of the two counts`,
      limit_micro_usd: 1000000,
      acceptance_criteria: ["The report states the correct total"],
      required_artifacts: [{ name: "report.md", must_contain: [TOTAL] }],
      input_documents: [
        {
          path: "inputs/data.md",
          content: `apples: ${FIRST}\npears: ${SECOND}\n`,
        },
      ],
    },
  });
  expect(reply.status()).toBe(202);
  return (await reply.json()).run_id;
}

const status = (page: Page) => page.locator("[data-run-status]");

test("a goal is admitted, planned, executed, restarted and inspected, ending in a verified artifact", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  const id = await admit(page, "slice-complete");
  await page.goto(`/runs/${id}`);

  // The worker is killed inside a model call. Its lease runs out, and recovery stops at the unknown.
  await expect(status(page)).toHaveAttribute("data-run-status", "paused", {
    timeout: 40_000,
  });
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "uncertain model call",
  );
  await expect(page.getByText("Write the totals report: open")).toBeVisible();
  const refused = await page.request.post(`/api/v1/runs/${id}/resume`, {
    headers: await write(page, "resume-early"),
    data: { expected_version: await version(page, id) },
  });
  expect(refused.status()).toBe(409);
  expect((await refused.json()).code).toBe("uncertain_model_call");

  // The owner reports the charge from the provider's account, and resumes.
  const reconciled = await page.request.post(
    `/api/v1/runs/${id}/model-calls/reconcile`,
    {
      headers: await write(page, "reconcile"),
      data: { charged_micro_usd: 90 },
    },
  );
  expect((await reconciled.json()).reconciled_calls).toBe(1);
  const resumed = await page.request.post(`/api/v1/runs/${id}/resume`, {
    headers: await write(page, "resume"),
    data: { expected_version: await version(page, id) },
  });
  expect((await resumed.json()).status).toBe("queued");

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
  const workspace = await (
    await page.request.get(`/api/v1/runs/${id}/workspace`)
  ).json();
  expect(workspace.artifacts).toHaveLength(1);
  const download = await page.request.get(
    `/api/v1/artifacts/${workspace.artifacts[0].id}/download`,
  );
  expect(await download.text()).toContain(TOTAL);
  expect(workspace.run.budget.spent_micro_usd).toBeGreaterThan(0);
  expect(workspace.outstanding.uncertain_calls).toBe(0);
  expect(workspace.objective).toContain("slice-complete");
  expect(workspace.plan.version).toBe(1);
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
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations.map((violation) => violation.id)).toEqual([]);
});

test("a missing required artifact fails the run, whatever the model said", async ({
  page,
}) => {
  await signIn(page);
  const id = await admit(page, "slice-no-artifact");
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
  await signIn(page);
  const id = await admit(page, "slice-wrong-total");
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
  await signIn(page);
  const id = await admit(page, "slice-only-claims");
  await page.goto(`/runs/${id}`);
  await expect(status(page)).toHaveAttribute("data-run-status", "failed", {
    timeout: 40_000,
  });
  await expect(page.locator("[data-stop-reason]")).toContainText(
    "plan missing",
  );
});

async function version(page: Page, id: string): Promise<number> {
  return (await (await page.request.get(`/api/v1/runs/${id}`)).json()).version;
}
