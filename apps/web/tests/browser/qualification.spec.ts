import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const TERRA = "openrouter_terra";
const DEEPSEEK = "openrouter_deepseek_flash";

// Run by scripts/qualify_identity.py, after the settings suite left workspace A a valid key.
async function openSettings(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL_A);
  await page.getByLabel("Password").fill(PASSWORD_A);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toHaveText(
    "The key authenticated.",
  );
  await expect(page.locator('[data-field="catalog"]')).toHaveText("Available");
}

test("after an API restart, each route shows its own stored status, date, configuration and limits", async ({
  page,
}) => {
  await openSettings(page);
  const deepseek = page.locator(`[data-route="${DEEPSEEK}"]`);
  const terra = page.locator(`[data-route="${TERRA}"]`);
  for (const route of [deepseek, terra]) {
    await expect(route.locator('[data-route-field="status"]')).toHaveText(
      "Qualified, with the limits below",
    );
    await expect(route.locator('[data-route-field="date"]')).toHaveText(
      "2026-11-05",
    );
    await expect(
      route.locator('[data-route-field="configuration"]'),
    ).toContainText("512 output tokens");
  }
  await expect(deepseek.locator('[data-route-field="limits"]')).toContainText(
    "Strict nested output is unsupported",
  );
  await expect(terra.locator('[data-route-field="limits"]')).toContainText(
    "only with closed objects",
  );
});

test("a route with no record reads as not qualified, with a valid key and an available catalog", async ({
  page,
}) => {
  await openSettings(page);
  const terra = page.locator(`[data-route="${TERRA}"]`);
  await expect(terra.locator('[data-route-field="status"]')).toHaveText(
    "Not qualified",
  );
  await expect(terra.locator('[data-route-field="date"]')).toHaveCount(0);
  await expect(terra.locator('[data-route-field="limits"]')).toHaveCount(0);
  await expect(
    page.locator(`[data-route="${DEEPSEEK}"] [data-route-field="status"]`),
  ).toHaveText("Qualified, with the limits below");
});
