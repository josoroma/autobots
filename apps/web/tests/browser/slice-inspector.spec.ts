import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

// The run list and inspector, with the scripted worker running. Its name puts it with the slice suites.
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_B = process.env.AUTOBOTS_TEST_OWNER_B_EMAIL ?? "";
const PASSWORD_B = process.env.AUTOBOTS_TEST_OWNER_B_PASSWORD ?? "";
const EMAIL_D = process.env.AUTOBOTS_TEST_NO_KEY_EMAIL ?? "";
const PASSWORD_D = process.env.AUTOBOTS_TEST_NO_KEY_PASSWORD ?? "";
const NO_KEY_RUN = process.env.AUTOBOTS_TEST_NO_KEY_RUN ?? "";
const TERRA = "openai/gpt-6.1-terra-20261026";

async function signIn(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
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

async function finishedRun(page: Page, goal: string): Promise<string> {
  await page.goto("/");
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, `${goal}-${Date.now()}`),
    data: {
      goal_text: `${goal}: report the total of the two counts`,
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
  return id;
}

test("the run list shows only this workspace's runs, with no key, and starts nothing", async ({
  page,
}) => {
  await signIn(page, EMAIL_D, PASSWORD_D);
  const status = await (
    await page.request.get("/api/settings/model-providers")
  ).json();
  expect(status.source).toBe("none");
  const posted: string[] = [];
  page.on("request", (request) => {
    if (request.method() !== "GET" && request.url().includes("/runs")) {
      posted.push(request.url());
    }
  });
  await page.goto("/");
  await page.getByRole("link", { name: "Runs" }).click();
  await expect(page.getByRole("heading", { name: "Runs" })).toBeVisible();
  const items = page.locator("[data-run]");
  await expect(items).toHaveCount(1);
  await expect(items.first()).toHaveAttribute("data-run", NO_KEY_RUN);
  await expect(items.first()).toContainText("Queued");
  await expect(items.first()).toContainText(
    "Arranged in a workspace with no key",
  );
  await expect(items.first().getByRole("link")).toHaveAttribute(
    "href",
    `/runs/${NO_KEY_RUN}`,
  );
  await page.reload();
  await expect(items).toHaveCount(1);
  expect(posted).toEqual([]);
  const after = await (
    await page.request.get(`/api/v1/runs/${NO_KEY_RUN}`)
  ).json();
  expect(after.status).toBe("queued");
  expect(after.version).toBe(1);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("the inspector shows what a finished run used, attempted and saved, and nothing private", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await ensureKey(page);
  const id = await finishedRun(page, "slice-reasoned");
  await page.getByRole("link", { name: "Inspect this run" }).click();
  await expect(
    page.getByRole("heading", { name: "Run inspector" }),
  ).toBeVisible();
  const reply = await page.request.get(`/api/v1/runs/${id}/inspector`);
  const body = await reply.text();
  const view = JSON.parse(body);
  expect(view.model_calls.length).toBeGreaterThan(5);
  expect(view.tool_attempts.length).toBeGreaterThan(3);
  expect(view.checkpoints.length).toBeGreaterThan(5);
  const calls = page.locator("[data-call]");
  await expect(calls).toHaveCount(view.model_calls.length);
  await expect(calls.first()).toContainText("executor, attempt 1: succeeded");
  await expect(calls.first()).toContainText("Provider openrouter");
  await expect(calls.first().locator("[data-canonical]")).toHaveText(TERRA);
  await expect(calls.first().locator("[data-wire]")).toHaveText(
    "fixture/model",
  );
  await expect(calls.first().locator("[data-upstream]")).toHaveText("unknown");
  await expect(calls.first()).toContainText("Tokens:");
  for (const tool of ["propose_plan", "save_artifact", "publish_artifact"]) {
    await expect(page.locator(`[data-tool="${tool}"]`).first()).toContainText(
      "succeeded",
    );
  }
  await expect(page.locator("[data-checkpoint]")).toHaveCount(
    view.checkpoints.length,
  );
  const text = await page.locator("main").innerText();
  for (const leak of [
    "PROTECTED-REASONING",
    "reasoning_details",
    "channel_values",
    "accumulated_output",
    "sk-or-",
    "eyJ",
    "Total: 5",
  ]) {
    expect(body).not.toContain(leak);
    expect(text).not.toContain(leak);
  }
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("another workspace's run is refused, on the route and on the screen", async ({
  page,
  browser,
}) => {
  test.setTimeout(120_000);
  await signIn(page, EMAIL_A, PASSWORD_A);
  await ensureKey(page);
  const id = await finishedRun(page, "slice-private");
  const context = await browser.newContext();
  const other = await context.newPage();
  await signIn(other, EMAIL_B, PASSWORD_B);
  const refused = await other.request.get(`/api/v1/runs/${id}/inspector`);
  expect(refused.status()).toBe(404);
  const refusedBody = await refused.text();
  expect(refusedBody).not.toContain("slice-private");
  await other.goto(`/runs/${id}/inspector`);
  await expect(other.locator('[data-state="unavailable"]')).toBeVisible();
  await expect(other.locator("main")).not.toContainText("slice-private");
  await other.goto("/runs");
  await expect(other.locator(`[data-run="${id}"]`)).toHaveCount(0);
  await context.close();
});

// R-28: the inspector says why it can't read a run, as the run page does, and only an outage offers
// Retry. The replies are arranged with page.route on the inspector read.
test("the inspector says why it can't read a run, and Retry reads it again", async ({
  page,
}) => {
  await signIn(page, EMAIL_D, PASSWORD_D);
  const inspector = (url: URL) =>
    url.pathname === `/api/v1/runs/${NO_KEY_RUN}/inspector`;
  let arranged: Parameters<Route["fulfill"]>[0] | null = null;
  await page.route(inspector, (route) =>
    arranged === null ? route.continue() : route.fulfill(arranged),
  );
  const state = page.locator('[data-state="unavailable"]');
  for (const [reply, reason, words] of [
    [
      {
        status: 403,
        json: { code: "workspace_required", message: "Choose a workspace." },
      },
      "denied",
      "Choose a workspace.",
    ],
    [
      { status: 401, json: { code: "not_signed_in", message: "Arranged." } },
      "signed_out",
      "You're signed out. Sign in to see this run.",
    ],
    [
      { status: 422, json: { code: "validation_error", message: "Arranged." } },
      "not_found",
      "That run is not available. Sign in with access to it, or check the link.",
    ],
    [
      { status: 200, json: { schema_version: 1, model_calls: "arranged" } },
      "out_of_date",
      "This page and the local service disagree. Reload after updating.",
    ],
  ] as const) {
    arranged = reply;
    await page.goto(`/runs/${NO_KEY_RUN}/inspector`);
    await expect(state).toHaveAttribute("data-reason", reason);
    await expect(state.getByRole("alert")).toHaveText(words);
    await expect(state.getByRole("button", { name: "Retry" })).toHaveCount(0);
  }
  arranged = {
    status: 503,
    json: {
      code: "service_unavailable",
      message: "The local API is unavailable.",
    },
  };
  await page.goto(`/runs/${NO_KEY_RUN}/inspector`);
  await expect(state).toHaveAttribute("data-reason", "unavailable");
  await expect(state.getByRole("alert")).toHaveText(
    "This run can't be read right now. Check that the local services are running, then try again.",
  );
  arranged = null;
  await state.getByRole("button", { name: "Retry" }).click();
  await expect(state).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Model calls" }),
  ).toBeVisible();
  await page.unroute(inspector);
});
