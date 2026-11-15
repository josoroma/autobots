/**
 * The workspace's OpenRouter key, saved and removed through Settings → Models as a person would
 * (TWEB-02). The disposable stacks' fake upstream accepts a key starting `sk-or-valid-`.
 */
import { expect, type Locator, type Page } from "@playwright/test";

/** The arranged key most suites save, which the fake upstream authenticates. */
export const VALID_PROVIDER_KEY = "sk-or-valid-arranged-first";

/**
 * The provider card's own message, by its role. The policy panel beside it can show its loading line,
 * also a status, while a write is answered, so the lookup is scoped to the card its heading labels.
 */
export async function providerMessage(page: Page): Promise<Locator> {
  const card = page.locator('[aria-labelledby="openrouter-heading"]');
  await expect(
    card,
    "the provider card is labelled by its heading",
  ).toHaveCount(1);
  return card.getByRole("status");
}

/** Fills Models' key field and presses Save & validate, asserting nothing about the outcome. */
export async function submitProviderKey(
  page: Page,
  key: string,
): Promise<void> {
  await page.getByLabel(/API key|Replace key/).fill(key);
  await page.getByRole("button", { name: "Save & validate" }).click();
}

/** Opens Models and saves `key` unless a key is configured already. Leaves the page on Models. */
export async function ensureProviderKey(
  page: Page,
  key: string = VALID_PROVIDER_KEY,
): Promise<void> {
  await page.goto("/settings/models");
  const source = page.locator('[data-field="source"]');
  await expect(source).toBeVisible();
  if ((await source.textContent())?.trim() === "None") {
    await submitProviderKey(page, key);
    await expect(page.locator('[data-field="auth"]')).toHaveText(
      "The key authenticated.",
    );
  }
}

/** Opens Models and disconnects the saved key. */
export async function disconnectProviderKey(page: Page): Promise<void> {
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toBeVisible();
  await page.getByRole("button", { name: "Disconnect" }).click();
  await expect(page.locator('[data-field="source"]')).toHaveText("None");
}
