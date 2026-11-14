import { mkdirSync, rmSync, writeFileSync } from "node:fs";

import type { Page } from "@playwright/test";

import { signIn, users } from "./support/auth.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";

const stack = arranged({
  catalogDown: "AUTOBOTS_TEST_CATALOG_DOWN",
  backups: "AUTOBOTS_TEST_BACKUP_DIR",
});
const AN_ID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/;

async function expectNothingPrivate(page: Page): Promise<void> {
  expectNoPrivateValues(await page.locator("main").innerText(), {
    label: "Operations",
    extra: ["postgres", AN_ID],
    ignoreCase: true,
  });
}

test("with no restore recorded and OpenRouter down, Operations says so and stays usable", async ({
  page,
}) => {
  await signIn(page, users.owner);
  writeFileSync(stack.catalogDown, "");
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
    rmSync(stack.catalogDown);
  }
});

test("Operations shows the delayed schedule, OpenRouter, the restore and each route's qualification", async ({
  page,
}) => {
  mkdirSync(`${stack.backups}/arranged`, { recursive: true });
  const record = {
    at: "2026-11-06T12:00:00+00:00",
    result: "passed",
    checks_passed: 14,
    checks_total: 14,
  };
  writeFileSync(
    `${stack.backups}/arranged/restores.jsonl`,
    `${JSON.stringify(record)}\n`,
  );
  try {
    await signIn(page, users.owner);
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
    rmSync(`${stack.backups}/arranged`, { recursive: true });
  }
});
