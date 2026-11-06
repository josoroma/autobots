import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const DEEPSEEK = "openrouter_deepseek_flash";
const TERRA = "openrouter_terra";

// Run by scripts/qualify_identity.py, which arranges each test's saved policy in the database first,
// since a saved choice naming DeepSeek can't be made through the product any more.
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

test("a saved default naming DeepSeek refuses new runs with no substitute, and isn't rewritten", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="not-offered"]')).toContainText(
    "isn't offered for new runs",
  );
  const choice = page.getByLabel("Workspace default");
  await expect(choice).toHaveValue(DEEPSEEK);
  await expect(choice.locator(`option[value="${DEEPSEEK}"]`)).toBeDisabled();

  const before = await (
    await page.request.get("/api/settings/model-policy")
  ).json();
  const runs = await (await page.request.get("/api/v1/runs")).json();
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, `saved-${Date.now()}`),
    data: { goal_text: "saved default" },
  });
  expect(refused.status()).toBe(409);
  const body = await refused.json();
  expect(body.code).toBe("model_not_offered");
  expect(body.message).toContain("isn't offered for new runs");
  expect((await (await page.request.get("/api/v1/runs")).json()).runs).toEqual(
    runs.runs,
  );

  await page.goto("/");
  await page.getByRole("textbox", { name: "Goal" }).fill("kept draft");
  await page.getByRole("button", { name: "Run" }).click();
  await expect(
    page.getByText(/isn't offered for new runs/).first(),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Goal" })).toHaveValue(
    "kept draft",
  );

  const after = await (
    await page.request.get("/api/settings/model-policy")
  ).json();
  expect(after.version).toBe(before.version);
  expect(after.default_profile).toBe(DEEPSEEK);

  // The way out is the owner's: choosing an offered model, on the screen.
  await page.goto("/settings/models");
  await choice.selectOption(TERRA);
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.locator("[data-policy-message]")).toContainText("Saved.");
  await expect(page.locator('[data-field="not-offered"]')).toHaveCount(0);
});

test("a saved override on another role reads as not taking effect, and still refuses", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect.locator('[data-role-effect="differs"]')).toHaveText(
    "These differ from the executor, so they don't take effect: coder.",
  );
  await expect(effect.locator('[data-role-effect="summarizer"]')).toHaveCount(
    0,
  );
  await expect(page.locator('[data-field="not-offered"]')).toBeVisible();
  const refused = await page.request.post("/api/v1/runs", {
    headers: await write(page, `override-${Date.now()}`),
    data: { goal_text: "saved override" },
  });
  expect(refused.status()).toBe(409);
});

test("a saved executor override says every other role differs, summarizer included", async ({
  page,
}) => {
  await signIn(page);
  await page.goto("/settings/models");
  const effect = page.locator('[data-field="role-effect"]');
  await expect(effect.locator('[data-role-effect="differs"]')).toContainText(
    ": coordinator, router, planner, researcher, coder,",
  );
  await expect(effect.locator('[data-role-effect="summarizer"]')).toBeVisible();
});
