import { mkdirSync, rmSync, writeFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const CATALOG_DOWN = process.env.AUTOBOTS_TEST_CATALOG_DOWN ?? "";
const BACKUPS = process.env.AUTOBOTS_TEST_BACKUP_DIR ?? "";
const NOT_ALLOWED = ["127.0.0.1", "postgres", "sk-or-", "eyj", "/users/"];
const AN_ID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/;

async function signIn(page: Page): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL_A);
  await page.getByLabel("Password").fill(PASSWORD_A);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

async function expectNothingPrivate(page: Page): Promise<void> {
  const text = (await page.locator("main").innerText()).toLowerCase();
  for (const leak of NOT_ALLOWED) expect(text).not.toContain(leak);
  expect(text).not.toMatch(AN_ID);
}

test("with no restore recorded and OpenRouter down, Operations says so and stays usable", async ({
  page,
}) => {
  await signIn(page);
  const requests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/chat/completions")) {
      requests.push(request.url());
    }
  });
  writeFileSync(CATALOG_DOWN, "");
  try {
    await page.goto("/operations");
    await expect(page.locator('[data-field="openrouter"]')).toContainText(
      "OpenRouter can't be reached",
    );
    await expect(page.locator('[data-field="restores"]')).toContainText(
      "No restore is recorded",
    );
    await expect(page.getByText("Ready. New work can start.")).toBeVisible();
    // Still usable: this saves, and reads back.
    await page.getByLabel(/Run content/).fill("");
    await page.getByLabel(/Retry keys/).fill("");
    await page.getByRole("button", { name: "Save retention" }).click();
    await expect(page.getByText(/Saved\. Nothing is removed/)).toBeVisible();
    await expectNothingPrivate(page);
  } finally {
    rmSync(CATALOG_DOWN);
  }
  expect(requests).toEqual([]);
});

test("Operations shows the delayed schedule, OpenRouter, the restore and each route's qualification", async ({
  page,
}) => {
  mkdirSync(`${BACKUPS}/arranged`, { recursive: true });
  const record = {
    at: "2026-11-06T12:00:00+00:00",
    result: "passed",
    checks_passed: 14,
    checks_total: 14,
  };
  writeFileSync(
    `${BACKUPS}/arranged/restores.jsonl`,
    `${JSON.stringify(record)}\n`,
  );
  try {
    await signIn(page);
    await page.goto("/operations");
    await expect(page.locator('[data-field="openrouter"]')).toContainText(
      "OpenRouter's catalog answered",
    );
    const delayed = page.locator('[data-field="delayed"]');
    await expect(delayed).toContainText("Arranged nightly report");
    await expect(delayed).toContainText("missed");
    await expect(delayed).toContainText("2026-11-05");
    await expect(delayed).toContainText("host away");
    const restores = page.locator('[data-field="restores"]');
    await expect(restores).toContainText("2026-11-06");
    await expect(restores).toContainText("verified, 14 of 14 checks");
    for (const [profile, limit] of [
      ["openrouter_terra", "only with closed objects"],
      ["openrouter_deepseek_flash", "Strict nested output is unsupported"],
    ]) {
      const route = page.locator(`[data-operations-route="${profile}"]`);
      await expect(route).toContainText("2026-11-05");
      await expect(route).toContainText(limit as string);
    }
    await expectNothingPrivate(page);
  } finally {
    rmSync(`${BACKUPS}/arranged`, { recursive: true });
  }
});
