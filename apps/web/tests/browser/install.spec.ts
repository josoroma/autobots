import { createHash } from "node:crypto";

import { signIn, submitSignIn, users } from "./support/auth.ts";
import { arranged } from "./support/env.ts";
import { expect, test } from "./support/fixtures.ts";
import { expectNoPrivateValues } from "./support/leaks.ts";

// Run by hand on the persistent install, as the upgrade and operations runbooks say. No other suite
// runs it, and it writes nothing: it signs in and reads what the install already holds.
const install = arranged({
  run: "AUTOBOTS_TEST_RUN",
  artifactSha: "AUTOBOTS_TEST_ARTIFACT_SHA",
});

test("a wrong password is refused on the install", async ({ page }) => {
  await submitSignIn(page, {
    email: users.owner.email,
    password: "not-the-owners-password",
  });
  await expect(page.getByRole("alert")).toBeVisible();
  await page.goto("/");
  await expect(page.locator('[data-session="signed-in"]')).toHaveCount(0);
});

test("the owner signs in, and the finished run and its artifact bytes are there", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto(`/runs/${install.run}`);
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
  expect(hash).toBe(install.artifactSha);
});

test("Settings and Operations read the install, with no key or address", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/settings/models");
  await expect(page.locator('[data-field="auth"]')).toHaveText(
    "The key authenticated.",
  );
  await expect(
    page.locator('[data-route="openrouter_terra"] [data-route-field="status"]'),
  ).toHaveText("Qualified, with the limits below");
  await page.goto("/operations");
  await expect(page.getByText("Ready. New work can start.")).toBeVisible();
  expectNoPrivateValues(await page.locator("main").innerText(), {
    label: "Operations",
    extra: ["postgres"],
  });
});

test("after the upgrade, Settings shows what its migration added", async ({
  page,
}) => {
  await signIn(page, users.owner);
  await page.goto("/settings/models");
  await expect(
    page.locator('[data-route="openrouter_terra"] [data-route-field="limits"]'),
  ).toContainText("the pinned SDK removes the encrypted reasoning item's id");
});
