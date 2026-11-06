import { expect, test, type Page } from "@playwright/test";

// What a run discloses, freezes and reports. Its name puts it with the slice suites.
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const TERRA = "openrouter_terra";
const DEEPSEEK = "openrouter_deepseek_flash";
const DEEPSEEK_CANONICAL = "deepseek/deepseek-v4.1-flash-20261017";
const TERRA_CANONICAL = "openai/gpt-6.1-terra-20261026";
const DATA =
  "selected instructions, conversation and context excerpts, retrieved material, tool outputs and required protocol metadata";

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL_A);
  await page.getByLabel("Password").fill(PASSWORD_A);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
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

async function ensureKey(page: Page): Promise<void> {
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
}

async function expectDisclosure(page: Page, model: string): Promise<void> {
  const disclosure = page.locator('[data-field="disclosure"]');
  await expect(disclosure.locator('[data-disclosure="model"]')).toContainText(
    model,
  );
  await expect(disclosure.locator('[data-disclosure="budget"]')).toContainText(
    "US$1.00",
  );
  await expect(disclosure.locator('[data-disclosure="data"]')).toContainText(
    DATA,
  );
  await expect(disclosure.locator('[data-disclosure="consent"]')).toHaveText(
    "Nothing is sent until you press Run.",
  );
  await disclosure.locator("summary").click();
  const roles = disclosure.locator('[data-disclosure="roles"] li');
  await expect(roles).toHaveCount(14);
  await expect(roles.filter({ hasText: "executor" })).toContainText(model);
}

test("each screen that creates a run says what it uses, sends and spends, and sends nothing first", async ({
  page,
}) => {
  await signIn(page);
  await ensureKey(page);
  const created: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (
      request.method() === "POST" &&
      (url.endsWith("/api/v1/runs") || url.endsWith("/executions"))
    ) {
      created.push(url);
    }
  });

  await page.goto("/");
  await expectDisclosure(page, TERRA_CANONICAL);

  // An Expert's session.
  const expert = await (
    await page.request.post("/api/v1/experts", {
      headers: await write(page, `disclose-expert-${Date.now()}`),
      data: { name: `Disclosing ${Date.now()}`, config: {} },
    })
  ).json();
  const session = await (
    await page.request.post("/api/v1/sessions", {
      headers: await write(page, `disclose-session-${Date.now()}`),
      data: { kind: "direct", experts: [{ expert_id: expert.id }] },
    })
  ).json();
  await page.goto(`/sessions/${session.id}`);
  await expectDisclosure(page, TERRA_CANONICAL);

  // A workflow's run.
  const workflow = await (
    await page.request.post("/api/v1/workflows", {
      headers: await write(page, `disclose-workflow-${Date.now()}`),
      data: { name: `Disclosing ${Date.now()}` },
    })
  ).json();
  const graph = {
    nodes: [
      { id: "in", block: "input", version: 1, config: { type: "string" } },
      { id: "out", block: "output", version: 1, config: {} },
    ],
    links: [
      {
        source: "in",
        source_port: "value",
        target: "out",
        target_port: "value",
      },
    ],
  };
  const published = await page.request.post(
    `/api/v1/workflows/${workflow.id}/versions`,
    {
      headers: await write(page, `disclose-version-${Date.now()}`),
      data: { expected_version: 0, graph },
    },
  );
  expect(published.status()).toBeLessThan(300);
  await page.goto(`/workflows/${workflow.id}`);
  await expectDisclosure(page, TERRA_CANONICAL);
  await expect(page.locator('[data-disclosure="data"]')).toContainText(
    "if an agent step runs",
  );
  expect(created).toEqual([]);
});

test("a person picks the other model for one run: it freezes, the default stays, and the workspace says what dispatches", async ({
  page,
}) => {
  await signIn(page);
  await ensureKey(page);
  const before = await (
    await page.request.get("/api/settings/model-policy")
  ).json();
  expect(before.default_profile).toBe(TERRA);
  await page.goto("/");
  await page.getByLabel("Model for this run").selectOption(DEEPSEEK);
  await expectDisclosure(page, DEEPSEEK_CANONICAL);
  await page
    .getByRole("textbox", { name: "Goal" })
    .fill("slice-only-claims one run");
  await page.getByRole("button", { name: "Run" }).click();
  const link = page
    .locator('[data-outcome="queued"]')
    .getByRole("link", { name: "Open this run" });
  await expect(link).toBeVisible();
  await link.click();
  const map = page.locator('[data-field="role-map"]');
  await expect(map.locator("li")).toHaveCount(14);
  for (const item of await map.locator("li").all()) {
    await expect(item).toContainText(DEEPSEEK_CANONICAL);
  }
  await expect(map).toContainText(
    "Only the executor's binding dispatches in this release",
  );
  const after = await (
    await page.request.get("/api/settings/model-policy")
  ).json();
  expect(after.default_profile).toBe(TERRA);
  expect(after.version).toBe(before.version);
  const id = page.url().split("/").pop() ?? "";
  const summary = await (await page.request.get(`/api/v1/runs/${id}`)).json();
  if (!["succeeded", "failed", "cancelled"].includes(summary.status)) {
    await page.request.post(`/api/v1/runs/${id}/cancel`, {
      headers: await write(page, `cancel-${id}`),
      data: { expected_version: summary.version },
    });
  }
});

test("the workspace shows budgets, and the inspector shows reported and estimated costs apart, errors and evidence", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await ensureKey(page);
  await page.goto("/");
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, `slice-failed-call-${Date.now()}`),
    data: {
      goal_text:
        "slice-failed-call slice-reasoned: report the total of the two counts",
      limit_micro_usd: 1000000,
      acceptance_criteria: ["The report states the correct total"],
      required_artifacts: [{ name: "report.md", must_contain: ["Total: 5"] }],
      input_documents: [
        { path: "inputs/data.md", content: "apples: 2\npears: 3\n" },
      ],
    },
  });
  expect(reply.status()).toBe(202);
  const id = (await reply.json()).run_id;
  await page.goto(`/runs/${id}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
    { timeout: 60_000 },
  );
  const budgets = page.locator('[data-field="budgets"]');
  await expect(budgets).toContainText("512 output tokens per call");
  await expect(budgets).toContainText("8K tokens of context");
  await expect(budgets).toContainText("Spend limit: US$1.00");

  await page.getByRole("link", { name: "Inspect this run" }).click();
  const failed = page.locator('[data-call="failed_before_acceptance"]').first();
  await expect(failed).toContainText("Error: provider error");
  await expect(failed.locator('[data-cost="reported"]')).toHaveText(
    "Reported charge: US$0",
  );
  await expect(failed.locator('[data-cost="estimated"]')).toContainText(
    "Estimated worst case, not a charge:",
  );
  const settled = page.locator('[data-call="succeeded"]').first();
  await expect(settled.locator('[data-cost="reported"]')).toContainText(
    "Reported charge: US$0.0001",
  );
  const evidence = page.locator('[data-field="evidence"]');
  await expect(evidence).toContainText("Reported the total of the two counts");
  const link = evidence.getByRole("link", { name: "outputs/report.md" });
  const download = await page.request.get(
    (await link.getAttribute("href")) ?? "",
  );
  expect(await download.text()).toContain("Total: 5");
  const body = await (
    await page.request.get(`/api/v1/runs/${id}/inspector`)
  ).text();
  const text = await page.locator("main").innerText();
  for (const leak of ["PROTECTED-REASONING", "reasoning_details", "sk-or-"]) {
    expect(body).not.toContain(leak);
    expect(text).not.toContain(leak);
  }
});

test("an unapproved model is refused, no run starts, and the draft is kept", async ({
  page,
}) => {
  await signIn(page);
  await ensureKey(page);
  await page.goto("/");
  const listed = async () =>
    (await (await page.request.get("/api/v1/runs")).json()).runs.length;
  const before = await listed();
  const draft = "A draft that must survive";
  await page.getByRole("textbox", { name: "Goal" }).fill(draft);
  // The picker only offers approved models, so the request is changed on its way, and the server decides.
  await page.route("**/api/v1/runs", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    const body = route.request().postDataJSON();
    return route.continue({
      postData: JSON.stringify({ ...body, run_profile: "openai/gpt-unknown" }),
    });
  });
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.locator('[data-outcome="model_refused"]')).toContainText(
    "isn't approved",
  );
  await page.unroute("**/api/v1/runs");
  await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(draft);
  expect(await listed()).toBe(before);
  const direct = await page.request.post("/api/v1/runs", {
    headers: await write(page, `refused-${Date.now()}`),
    data: { goal_text: "No", run_profile: "openrouter_astra" },
  });
  expect(direct.status()).toBe(422);
  expect(await listed()).toBe(before);
  await page.getByRole("textbox", { name: "Goal" }).fill("");
});
