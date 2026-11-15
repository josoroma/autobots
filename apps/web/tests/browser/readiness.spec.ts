import { parseMemberReadiness } from "@autobots/api-client";
import type { Page } from "@playwright/test";

import { expectNoA11yViolations } from "./support/a11y.ts";
import { getJson } from "./support/api.ts";
import { users } from "./support/auth.ts";
import { expect, test } from "./support/fixtures.ts";
import { disconnectProviderKey, submitProviderKey } from "./support/keys.ts";

// US-15.3: readiness a member who isn't the owner can read. In the arranged project,
// scripts/qualify_identity.py runs each test on its own, by title: first with no worker heartbeat,
// then with an arranged one.

function chip(page: Page, name: string) {
  return page.locator(`[data-service="${name}"]`);
}

test("names the service that isn't ready", async ({ signedInPage }) => {
  const page = await signedInPage(users.reader);
  const line = page.locator("[data-health]");
  await expect(line).toHaveAttribute("data-health", "worker");
  await expect(line).toHaveText("Worker not ready");
  await expect(chip(page, "worker")).toHaveText("Worker not ready");
  await expect(chip(page, "api")).toHaveText("Python API ready");
  await expect(chip(page, "database")).toHaveText("Database ready");
  await expectNoA11yViolations(page);

  const body = await getJson(page, {
    path: "/api/v1/readiness",
    parse: parseMemberReadiness,
  });
  expect(Object.keys(body).sort()).toEqual([
    "ready",
    "schema_version",
    "services",
  ]);
  for (const item of body.services) {
    expect(Object.keys(item).sort()).toEqual(["code", "name", "state"]);
    expect(item.code).not.toMatch(/\d|\//);
  }

  // The screens stay usable.
  await page.getByRole("link", { name: "Runs", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Runs", level: 1 }),
  ).toBeVisible();
  await expect(page.locator("[data-health]")).toHaveText("Worker not ready");
});

test("all local services ready", async ({ signedInPage }) => {
  // Arranged: the owner saves a key the fake upstream accepts, and disconnects it afterwards.
  const owner = await signedInPage(users.owner);
  await owner.goto("/settings/models");
  await submitProviderKey(owner, "sk-or-valid-readiness");
  await expect(owner.getByText("The key authenticated.").first()).toBeVisible();

  try {
    const page = await signedInPage(users.reader);
    const line = page.locator("[data-health]");
    await expect(line).toHaveAttribute("data-health", "ready");
    await expect(line).toHaveText("All local services ready");
    await expect(chip(page, "api")).toHaveText("Python API ready");
    await expect(chip(page, "worker")).toHaveText("Worker ready");
    await expect(chip(page, "database")).toHaveText("Database ready");
    await expect(chip(page, "openrouter")).toHaveText(
      "OpenRouter authenticated",
    );
    await expectNoA11yViolations(page);
  } finally {
    await disconnectProviderKey(owner);
  }
});
