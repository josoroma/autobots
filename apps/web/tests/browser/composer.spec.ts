import { readFileSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Request } from "@playwright/test";

// US-15.9, PRD-Studio HM-02 and HM-03 and Decision 0022 D11, against an owner arranged by
// scripts/qualify_identity.py: the installation key, US$2.10 left of today's cap and one Expert,
// "Composer helper", which grants calculate and read_csv and binds the executor to Sol.
const EMAIL = process.env.AUTOBOTS_TEST_COMPOSER_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_COMPOSER_PASSWORD ?? "";
const EXPERT = process.env.AUTOBOTS_TEST_COMPOSER_EXPERT ?? "";
const UPSTREAM_LOG = process.env.AUTOBOTS_TEST_UPSTREAM_LOG ?? "";

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

async function runCount(page: Page): Promise<number> {
  return (await (await page.request.get("/api/v1/runs")).json()).total;
}

function admission(page: Page) {
  return page.waitForResponse(
    (reply) =>
      new URL(reply.url()).pathname === "/api/v1/runs" &&
      reply.request().method() === "POST",
  );
}

test.describe.configure({ mode: "serial" });

test("the budget chip offers what today's cap allows, and the run freezes the chosen limit", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/");
  const budget = page.getByLabel("Budget");
  await expect(page.locator('[data-field="daily-left"]')).toHaveText(
    "US$2.10 left of today's cap",
  );
  await expect(budget.locator("option")).toHaveText([
    "US$0.25",
    "US$0.50",
    "US$0.75",
    "US$1.00",
    "US$1.25",
    "US$1.50",
    "US$1.75",
    "US$2.00",
  ]);
  await expect(budget).toHaveValue("1000000");
  const disclosed = page.locator('[data-disclosure="budget"]');
  await expect(disclosed).toContainText("US$1.00");
  await budget.selectOption("1500000");
  await expect(disclosed).toContainText("US$1.50");
  await page
    .getByLabel("Goal", { exact: true })
    .fill("A run with a chosen budget");
  const sent = admission(page);
  await page.getByRole("button", { name: "Run", exact: true }).click();
  const reply = await sent;
  expect(reply.request().postDataJSON().budget_micro_usd).toBe(1_500_000);
  expect(reply.status()).toBe(202);
  const { run_id } = await reply.json();
  await expect(page.locator('[data-outcome="queued"]')).toBeVisible();
  const run = await (await page.request.get(`/api/v1/runs/${run_id}`)).json();
  expect(run.budget.limit_micro_usd).toBe(1_500_000);
  await noViolations(page);
});

test("a budget outside the range, off the step or above today's cap is refused, and the draft is kept", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/");
  await expect(page.getByLabel("Budget")).toHaveValue("1000000");
  const before = await runCount(page);
  const goal = page.getByLabel("Goal", { exact: true });
  await goal.fill("A draft that must survive");
  for (const [chosen, status, code] of [
    [5_250_000, 422, "budget_out_of_range"],
    [100_000, 422, "budget_out_of_range"],
    [1_100_000, 422, "budget_off_step"],
    [2_250_000, 409, "budget_above_daily_cap"],
  ] as const) {
    // The page can't offer these, so each request is changed on its way to the BFF.
    await page.route("**/api/v1/runs", async (route) => {
      const body = route.request().postDataJSON();
      await route.continue({
        postData: JSON.stringify({ ...body, budget_micro_usd: chosen }),
      });
    });
    const sent = admission(page);
    await page.getByRole("button", { name: "Run", exact: true }).click();
    const reply = await sent;
    expect(reply.status()).toBe(status);
    expect((await reply.json()).code).toBe(code);
    const outcome = page.locator('[data-outcome="budget_refused"]');
    await expect(outcome).toContainText("No run started. Your draft is kept.");
    await expect(goal).toHaveValue("A draft that must survive");
    await page.unroute("**/api/v1/runs");
  }
  expect(await runCount(page)).toBe(before);
  // A budget and an explicit limit together are refused too.
  const token = await (await page.request.get("/api/csrf")).json();
  const both = await page.request.post("/api/v1/runs", {
    headers: {
      [token.header]: token.token,
      Origin: new URL(page.url()).origin,
      "Idempotency-Key": `both-${Date.now()}`,
    },
    data: {
      goal_text: "Both",
      budget_micro_usd: 1_000_000,
      limit_micro_usd: 1_000_000,
    },
  });
  expect(both.status()).toBe(422);
  expect((await both.json()).code).toBe("budget_conflict");
  expect(await runCount(page)).toBe(before);
  await noViolations(page);
});

test("an Expert chip starts a direct session first, and no Expert admits a goal run", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/");
  const requests: Request[] = [];
  page.on("request", (request) => {
    const path = new URL(request.url()).pathname;
    if (
      request.method() === "POST" &&
      (path === "/api/v1/sessions" || path === "/api/v1/runs")
    ) {
      requests.push(request);
    }
  });
  await page.getByLabel("Expert").selectOption(EXPERT);
  await page.getByLabel("Goal", { exact: true }).fill("Work with the helper");
  const first = admission(page);
  await page.getByRole("button", { name: "Run", exact: true }).click();
  const withExpert = await first;
  expect(withExpert.status()).toBe(202);
  expect(requests.map((item) => new URL(item.url()).pathname)).toEqual([
    "/api/v1/sessions",
    "/api/v1/runs",
  ]);
  const session = await (await requests[0]!.response())!.json();
  expect(requests[0]!.postDataJSON()).toEqual({
    kind: "direct",
    experts: [{ expert_id: EXPERT }],
  });
  expect(requests[1]!.postDataJSON().session_id).toBe(session.id);
  const expertRun = (await withExpert.json()).run_id;

  requests.length = 0;
  await page.getByLabel("Expert").selectOption("");
  await page.getByLabel("Goal", { exact: true }).fill("Work alone");
  const second = admission(page);
  await page.getByRole("button", { name: "Run", exact: true }).click();
  const goalOnly = await second;
  expect(goalOnly.status()).toBe(202);
  expect(requests.map((item) => new URL(item.url()).pathname)).toEqual([
    "/api/v1/runs",
  ]);
  expect(requests[0]!.postDataJSON().session_id).toBeUndefined();
  const goalRun = (await goalOnly.json()).run_id;

  const listed = (await (await page.request.get("/api/v1/runs")).json()).runs;
  const row = (id: string) =>
    listed.find((item: { id: string }) => item.id === id);
  expect(row(expertRun)).toMatchObject({
    label_kind: "expert",
    label: "Composer helper",
  });
  expect(row(goalRun)).toMatchObject({ label_kind: "goal" });
  const workspace = await (
    await page.request.get(`/api/v1/runs/${expertRun}/workspace`)
  ).json();
  expect(workspace.expert?.name).toBe("Composer helper");
  await noViolations(page);
});

test("preview chips show each profile's roles and the granted tools, and nothing reaches OpenRouter", async ({
  page,
}) => {
  const logged = () =>
    readFileSync(UPSTREAM_LOG, "utf8").split("\n").filter(Boolean);
  await signIn(page);
  const seen = logged().length;
  const previews: string[] = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/v1/run-preview") {
      previews.push(request.url());
    }
  });
  await page.goto("/");
  await page.getByLabel("Goal", { exact: true }).fill("Preview only");
  await expect(
    page.locator('[data-preview-profile="openrouter_terra"]'),
  ).toHaveText("Terra · 13 roles");
  await expect(
    page.locator('[data-preview-profile="openrouter_sol"]'),
  ).toHaveText("Sol · researcher");
  await expect(page.locator("[data-preview-tool]")).toContainText([
    "calculate",
    "read_csv",
    "save_artifact",
  ]);
  await expect(page.locator('[data-preview-tool="propose_plan"]')).toHaveCount(
    0,
  );

  await page.getByLabel("Model for this run").selectOption("openrouter_sol");
  await expect(page.locator("[data-preview-profile]")).toHaveText([
    "Sol · 14 roles",
  ]);
  await page.getByLabel("Model for this run").selectOption("");
  await page.getByLabel("Expert").selectOption(EXPERT);
  await expect(page.locator("[data-preview-tool]")).toHaveText([
    "calculate",
    "read_csv",
  ]);
  await expect(
    page.locator('[data-preview-profile="openrouter_sol"]'),
  ).toHaveText("Sol · 2 roles");
  await expect(
    page.locator('[data-preview-profile="openrouter_terra"]'),
  ).toHaveText("Terra · 12 roles");
  expect(
    previews.some((url) => url.includes("run_profile=openrouter_sol")),
  ).toBe(true);
  expect(previews.some((url) => url.includes(`expert_id=${EXPERT}`))).toBe(
    true,
  );
  // Only key and catalog reads reach the fake OpenRouter, and no completion.
  const after = logged().slice(seen);
  expect(after.every((line) => /\/(models|key)$/.test(line))).toBe(true);
  await noViolations(page);
});

test("attached files show as chips with their name, type and size", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/");
  await page.getByLabel("Attach files").setInputFiles([
    {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("plain notes"),
    },
    {
      name: "rates.csv",
      mimeType: "text/csv",
      buffer: Buffer.alloc(2_048, 97),
    },
  ]);
  const chips = page.locator("[data-attached]");
  await expect(chips).toHaveCount(2);
  const notes = page.locator('[data-attached="inputs/notes.txt"]');
  await expect(notes.locator('[data-field="file-name"]')).toHaveText(
    "notes.txt",
  );
  await expect(notes.locator('[data-field="file-type"]')).toHaveText(
    "text/plain",
  );
  await expect(notes.locator('[data-field="file-size"]')).toHaveText("11 B");
  const rates = page.locator('[data-attached="inputs/rates.csv"]');
  await expect(rates.locator('[data-field="file-name"]')).toHaveText(
    "rates.csv",
  );
  await expect(rates.locator('[data-field="file-type"]')).toHaveText(
    "text/csv",
  );
  await expect(rates.locator('[data-field="file-size"]')).toHaveText("2.0 KB");
  await noViolations(page);
});
