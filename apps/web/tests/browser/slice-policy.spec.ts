import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// The model policy on Settings. Its name runs it with the slice suites, after settings.spec's versions.
const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const TERRA = "openrouter_terra";
const DEEPSEEK = "openrouter_deepseek_flash";
const POLICY = "/api/settings/model-policy";

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL_A);
  await page.getByLabel("Password").fill(PASSWORD_A);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

async function write(
  page: Page,
  key?: string,
): Promise<Record<string, string>> {
  const token = await (await page.request.get("/api/csrf")).json();
  return {
    [token.header]: token.token,
    Origin: new URL(page.url()).origin,
    "Content-Type": "application/json",
    ...(key === undefined ? {} : { "Idempotency-Key": key }),
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

async function storedPolicy(page: Page): Promise<{
  version: number;
  default_profile: string;
  role_overrides: Record<string, string>;
}> {
  return (await page.request.get(POLICY)).json();
}

// The worker's scripted route is Terra, so later suites start from the original policy.
async function restore(page: Page): Promise<void> {
  const current = await storedPolicy(page);
  const reply = await page.request.put(POLICY, {
    headers: await write(page),
    data: {
      expected_version: current.version,
      default_profile: TERRA,
      role_overrides: {},
    },
  });
  expect(reply.status()).toBe(200);
}

async function admit(page: Page, goal: string): Promise<string> {
  const reply = await page.request.post("/api/v1/runs", {
    headers: await write(page, `${goal}-${Date.now()}`),
    data: { goal_text: `slice-only-claims ${goal}`, limit_micro_usd: 1000 },
  });
  expect(reply.status()).toBe(202);
  return (await reply.json()).run_id;
}

async function frozenExecutor(page: Page, id: string): Promise<string> {
  const view = await (
    await page.request.get(`/api/v1/runs/${id}/workspace`)
  ).json();
  return view.role_map.find(
    (binding: { role: string }) => binding.role === "executor",
  ).profile;
}

async function cancel(page: Page, id: string): Promise<void> {
  const summary = await (await page.request.get(`/api/v1/runs/${id}`)).json();
  if (["succeeded", "failed", "cancelled"].includes(summary.status)) return;
  await page.request.post(`/api/v1/runs/${id}/cancel`, {
    headers: await write(page, `cancel-${id}`),
    data: { expected_version: summary.version },
  });
}

const select = (page: Page, role: string) =>
  page.getByLabel(role, { exact: true });

test("an owner saves a default of what is offered, and DeepSeek is listed but not offered", async ({
  page,
}) => {
  test.setTimeout(90_000);
  await signIn(page);
  await ensureKey(page);
  await restore(page);
  await page.goto("/");
  const before = await admit(page, "before-the-change");
  expect(await frozenExecutor(page, before)).toBe(TERRA);

  await page.goto("/settings/models");
  await expect(page.locator(`[data-approved-model="${TERRA}"]`)).toContainText(
    "openai/gpt-6.1-terra-20261026 (requested as openai/gpt-6.1-terra)",
  );
  await expect(
    page.locator(`[data-approved-model="${DEEPSEEK}"]`),
  ).toContainText(
    "deepseek/deepseek-v4.1-flash-20261017 (requested as deepseek/deepseek-v4.1-flash-1017)",
  );
  await expect(
    page.locator(`[data-approved-model="${DEEPSEEK}"]`),
  ).toContainText("not offered for new runs until it's qualified");
  // Approved and listed, and not something new work can choose.
  await expect(
    page.getByLabel("Workspace default").locator(`option[value="${DEEPSEEK}"]`),
  ).toHaveCount(0);
  await expect(
    select(page, "coder").locator(`option[value="${DEEPSEEK}"]`),
  ).toHaveCount(0);
  const version = (await storedPolicy(page)).version;
  await page.getByLabel("Workspace default").selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  expect((await storedPolicy(page)).version).toBe(version + 1);

  await page.goto("/");
  const after = await admit(page, "after-the-change");
  expect(await frozenExecutor(page, after)).toBe(TERRA);
  expect(await frozenExecutor(page, before)).toBe(TERRA);
  await cancel(page, after);
  await cancel(page, before);

  await page.goto("/settings/models");
  await expect(page.getByLabel("Workspace default")).toHaveValue(TERRA);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
  await restore(page);
});

test("the screen says only the executor dispatches, and a same-binding override reads as the same", async ({
  page,
}) => {
  await signIn(page);
  await restore(page);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect).toContainText(
    "Only the executor's binding dispatches in this release. Other roles that differ from it don't take effect.",
  );
  await expect(effect).toContainText(
    "A summarizer that differs pauses the run with route_not_bound",
  );
  await expect(effect.locator('[data-role-effect="same"]')).toBeVisible();

  // A role that differs needs a saved choice this screen can't make now: saved-choice.spec.ts.
  await select(page, "coder").selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  await expect(effect.locator('[data-role-effect="same"]')).toBeVisible();
  const stored = await storedPolicy(page);
  expect(stored.default_profile).toBe(TERRA);
  expect(stored.role_overrides).toEqual({ coder: TERRA });
  await restore(page);
});

test("a stale save is refused with a reload message, and the stored policy is unchanged", async ({
  page,
  browser,
}) => {
  await signIn(page);
  await restore(page);
  await page.goto("/settings/models");
  await expect(page.getByLabel("Workspace default")).toHaveValue(TERRA);

  // Someone else saves after this screen loaded.
  const context = await browser.newContext();
  const other = await context.newPage();
  await signIn(other);
  await other.goto("/settings/models");
  await select(other, "coder").selectOption(TERRA);
  await other.getByRole("button", { name: "Save policy" }).click();
  await expect(other.locator("[data-policy-message]")).toContainText("Saved.");
  await context.close();
  const stored = await storedPolicy(page);
  expect(stored.role_overrides).toEqual({ coder: TERRA });

  await select(page, "planner").selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText(
    "Reload the page",
  );
  expect(await storedPolicy(page)).toEqual(stored);
  await restore(page);
});
