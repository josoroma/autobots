import { createHash } from "node:crypto";

import { expect, test, type Page } from "@playwright/test";

// Run by hand on the persistent install, as the upgrade and operations runbooks say. No other suite
// runs it, and it writes nothing: it signs in and reads what the install already holds.
const EMAIL = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const RUN = process.env.AUTOBOTS_TEST_RUN ?? "";
const ARTIFACT_SHA = process.env.AUTOBOTS_TEST_ARTIFACT_SHA ?? "";

async function signIn(page: Page, password: string = PASSWORD): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("a wrong password is refused on the install", async ({ page }) => {
  await signIn(page, "not-the-owners-password");
  await expect(page.getByRole("alert")).toBeVisible();
  await page.goto("/");
  await expect(page.locator('[data-session="signed-in"]')).toHaveCount(0);
});

test("the owner signs in, and the finished run and its artifact bytes are there", async ({
  page,
}) => {
  await signIn(page);
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  await page.goto(`/runs/${RUN}`);
  await expect(page.locator("[data-run-status]")).toHaveAttribute(
    "data-run-status",
    "succeeded",
  );
  await expect(page.locator('[data-verification="passed"]')).toBeVisible();
  const link = page.getByRole("link", { name: "report.md" });
  const href = await link.getAttribute("href");
  const reply = await page.request.get(href ?? "");
  expect(reply.status()).toBe(200);
  const hash = createHash("sha256")
    .update(await reply.body())
    .digest("hex");
  expect(hash).toBe(ARTIFACT_SHA);
});

test("Settings and Operations read the install, with no key or address", async ({
  page,
}) => {
  await signIn(page);
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toHaveText(
    "The key authenticated.",
  );
  await expect(
    page.locator('[data-route="openrouter_terra"] [data-route-field="status"]'),
  ).toHaveText("Qualified, with the limits below");
  await page.goto("/operations");
  await expect(page.getByText("Ready. New work can start.")).toBeVisible();
  const text = await page.locator("main").innerText();
  for (const leak of ["127.0.0.1", "postgres", "sk-or-", "eyJ"]) {
    expect(text).not.toContain(leak);
  }
});

test("after the upgrade, Settings shows what its migration added", async ({
  page,
}) => {
  await signIn(page);
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
  await page.goto("/settings/models");
  await expect(
    page.locator('[data-route="openrouter_terra"] [data-route-field="limits"]'),
  ).toContainText("the pinned SDK removes the encrypted reasoning item's id");
});
