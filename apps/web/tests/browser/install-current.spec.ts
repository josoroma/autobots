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
