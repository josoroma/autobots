import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const EMAIL_A = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const PASSWORD_A = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const EMAIL_C = process.env.AUTOBOTS_TEST_MEMBER_EMAIL ?? "";
const PASSWORD_C = process.env.AUTOBOTS_TEST_MEMBER_PASSWORD ?? "";

async function signIn(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText(/Signed in, with access to/)).toBeVisible();
}

test("the owner sees conditions, and no address or secret", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "Operations" })).toBeVisible();
  await expect(page.getByText("Ready. New work can start.")).toBeVisible();
  await expect(page.getByText("The database is answering.")).toBeVisible();
  // This suite runs before the slice starts its worker, so none is running.
  await expect(page.getByText(/No worker is running/)).toBeVisible();
  await expect(page.getByText(/Remote tracing: off/)).toBeVisible();
  await expect(page.getByText(/Last backup: none found/)).toBeVisible();
  const text = (await page.locator("main").innerText()).toLowerCase();
  for (const leak of ["127.0.0.1", "postgres", "sk-or-", "eyj"]) {
    expect(text).not.toContain(leak);
  }
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  expect(results.violations).toEqual([]);
});

test("retention saves, and a key window shorter than content is refused", async ({
  page,
}) => {
  await signIn(page, EMAIL_A, PASSWORD_A);
  await page.goto("/operations");
  await page.getByLabel(/Run content/).fill("30");
  await page.getByLabel(/Retry keys/).fill("7");
  await page.getByRole("button", { name: "Save retention" }).click();
  await expect(page.getByText(/Not saved/)).toBeVisible();
  // What was typed stays, so it can be corrected.
  await expect(page.getByLabel(/Run content/)).toHaveValue("30");
  await page.getByLabel(/Retry keys/).fill("60");
  await page.getByRole("button", { name: "Save retention" }).click();
  await expect(page.getByText(/Saved\. Nothing is removed/)).toBeVisible();
  // Back to keeping everything, since later suites use this workspace.
  await page.getByLabel(/Run content/).fill("");
  await page.getByLabel(/Retry keys/).fill("");
  await page.getByRole("button", { name: "Save retention" }).click();
  await expect(page.getByText(/Saved\. Nothing is removed/)).toBeVisible();
});

test("a member is refused", async ({ page }) => {
  await signIn(page, EMAIL_C, PASSWORD_C);
  await page.goto("/operations");
  await expect(
    page.getByText("Only the workspace owner can see Operations."),
  ).toBeVisible();
});
