import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// US-15.8, PRD-Studio MD-01 to MD-03, against the fixture catalog and an owner arranged by
// scripts/qualify_identity.py: no saved default, a `coder` override, and a run whose Expert
// binds the executor to Sol.
const EMAIL = process.env.AUTOBOTS_TEST_MODELS_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_MODELS_PASSWORD ?? "";
const RUN = process.env.AUTOBOTS_TEST_MODELS_RUN ?? "";
const TERRA = "openrouter_terra";
const SOL = "openrouter_sol";

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

function source(page: Page, role: string) {
  return page
    .locator(`label[for="role-${role}"]`)
    .locator("xpath=..")
    .locator("[data-binding-source]");
}

async function stored(page: Page): Promise<{
  version: number;
  default_profile: string | null;
  role_overrides: Record<string, string>;
}> {
  return (await page.request.get("/api/settings/model-policy")).json();
}

test.describe.configure({ mode: "serial" });

test("each profile shows catalog prices, capabilities and the fetch time, apart from qualification", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  const terra = page.locator(`[data-approved-model="${TERRA}"]`);
  await expect(terra.locator('[data-price="input"]')).toHaveText(
    "US$1.25 per 1M tokens",
  );
  await expect(terra.locator('[data-price="output"]')).toHaveText(
    "US$10.00 per 1M tokens",
  );
  const sol = page.locator(`[data-approved-model="${SOL}"]`);
  await expect(sol.locator('[data-price="input"]')).toHaveText(
    "US$3.00 per 1M tokens",
  );
  await expect(sol.locator('[data-price="output"]')).toHaveText(
    "US$15.00 per 1M tokens",
  );
  await expect(terra).toContainText("Capabilities, from the catalog");
  await expect(terra.locator("[data-capability]")).toHaveText([
    "max_tokens",
    "response_format",
    "tool_choice",
    "tools",
  ]);
  // The capabilities aren't a qualification, which the provider section records.
  await expect(terra.locator('[data-field="catalog-facts"]')).not.toContainText(
    /qualif/i,
  );
  const fetched = page.locator('[data-field="catalog-fetched"]');
  await expect(fetched).toContainText(/^Catalog fetched .+\d{1,2}:\d{2}:\d{2}/);
  await expect(fetched).toContainText(
    "Whether a route is qualified is recorded separately",
  );
  const models = await (await page.request.get("/api/models")).json();
  const reported = models.models.find(
    (model: { profile: string }) => model.profile === TERRA,
  );
  expect(reported.input_per_million_micro_usd).toBe(1_250_000);
  expect(reported.output_per_million_micro_usd).toBe(10_000_000);
  expect(Date.now() - Date.parse(models.fetched_at)).toBeLessThan(120_000);
  await noViolations(page);
});

test("each role says where its binding comes from, on Models and in the run's role map", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  await expect(page.getByLabel("Workspace default")).toHaveValue("");
  await expect(source(page, "coder")).toHaveAttribute(
    "data-binding-source",
    "workspace_override",
  );
  await expect(source(page, "coder")).toContainText("Workspace override");
  await expect(source(page, "researcher")).toHaveText(
    "Built-in default, openai/gpt-6.1-sol-20260929",
  );
  await expect(source(page, "planner")).toHaveText(
    "Built-in default, openai/gpt-6.1-terra-20261026",
  );
  const policy = await stored(page);
  expect(policy.default_profile).toBeNull();
  expect(policy.role_overrides).toEqual({ coder: TERRA });

  await page.goto(`/runs/${RUN}`);
  const map = page.locator('[data-field="role-map"]');
  const line = (role: string) =>
    map.locator("li").filter({ hasText: new RegExp(`^${role}:`) });
  await expect(line("executor")).toContainText("openai/gpt-6.1-sol-20260929");
  await expect(line("executor")).toContainText("· run override");
  await expect(line("coder")).toContainText("· workspace override");
  await expect(line("researcher")).toContainText("openai/gpt-6.1-sol-20260929");
  await expect(line("researcher")).toContainText("· built-in default");
  await noViolations(page);
});

test("Discard restores the saved form, Reset all clears overrides, and a stale Reset all is refused", async ({
  page,
  browser,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  const summary = page.locator('[data-field="policy-summary"]');
  await expect(summary).toHaveText(
    "13 of 14 roles follow the workspace default",
  );
  // A second saved override, so two exist.
  await page.getByLabel("planner", { exact: true }).selectOption(SOL);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  await expect(summary).toHaveText(
    "12 of 14 roles follow the workspace default",
  );
  const saved = await stored(page);
  expect(saved.role_overrides).toEqual({ coder: TERRA, planner: SOL });

  // Unsaved edits, then Discard.
  await page.getByLabel("Workspace default").selectOption(TERRA);
  await page.getByLabel("reviewer", { exact: true }).selectOption(SOL);
  await page.getByLabel("coder", { exact: true }).selectOption("");
  await page.getByRole("button", { name: "Discard" }).click();
  await expect(page.getByLabel("Workspace default")).toHaveValue("");
  await expect(page.getByLabel("reviewer", { exact: true })).toHaveValue("");
  await expect(page.getByLabel("coder", { exact: true })).toHaveValue(TERRA);
  await expect(page.getByLabel("planner", { exact: true })).toHaveValue(SOL);
  await expect(page.getByRole("button", { name: "Discard" })).toBeDisabled();
  expect(await stored(page)).toEqual(saved);

  // A screen loaded before the reset.
  const context = await browser.newContext();
  const stale = await context.newPage();
  await signIn(stale);
  await stale.goto("/settings/models");
  await expect(stale.locator('[data-field="policy-summary"]')).toHaveText(
    "12 of 14 roles follow the workspace default",
  );

  const reset = page.waitForResponse(
    (reply) =>
      reply.url().endsWith("/api/settings/model-policy/reset") &&
      reply.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Reset all" }).click();
  const sent = await reset;
  expect(sent.request().postDataJSON()).toEqual({
    expected_version: saved.version,
  });
  expect(sent.status()).toBe(200);
  await expect(page.locator("[data-policy-message]")).toContainText(
    "Every role override is cleared.",
  );
  await expect(summary).toHaveText(
    "14 of 14 roles follow the workspace default",
  );
  const cleared = await stored(page);
  expect(cleared).toMatchObject({
    version: saved.version + 1,
    default_profile: null,
    role_overrides: {},
  });

  await stale.getByRole("button", { name: "Reset all" }).click();
  await expect(stale.locator("[data-policy-message]")).toHaveText(
    "This policy changed after you opened it, so nothing was reset. Reload the page and try again.",
  );
  expect(await stored(page)).toEqual(cleared);
  await context.close();
  await page.reload();
  await expect(summary).toHaveText(
    "14 of 14 roles follow the workspace default",
  );
  await noViolations(page);
});
