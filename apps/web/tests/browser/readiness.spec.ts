import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";

// US-15.3: readiness a member who isn't the owner can read. scripts/qualify_identity.py runs each
// test on its own: first with no worker heartbeat, then with an arranged one.
const READER_EMAIL = process.env.AUTOBOTS_TEST_READER_EMAIL ?? "";
const READER_PASSWORD = process.env.AUTOBOTS_TEST_READER_PASSWORD ?? "";
const OWNER_EMAIL = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const OWNER_PASSWORD = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";

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

async function noViolations(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((item) => item.id)).toEqual([]);
}

async function chip(page: Page, name: string) {
  return page.locator(`[data-service="${name}"]`);
}

async function asReader(browser: Browser): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await signIn(page, READER_EMAIL, READER_PASSWORD);
  return page;
}

test("names the service that isn't ready", async ({ browser }) => {
  const page = await asReader(browser);
  const line = page.locator("[data-health]");
  await expect(line).toHaveAttribute("data-health", "worker");
  await expect(line).toHaveText("Worker not ready");
  await expect(await chip(page, "worker")).toHaveText("Worker not ready");
  await expect(await chip(page, "api")).toHaveText("Python API ready");
  await expect(await chip(page, "database")).toHaveText("Database ready");
  await noViolations(page);

  const reply = await page.request.get("/api/v1/readiness");
  expect(reply.status()).toBe(200);
  const body = await reply.json();
  expect(Object.keys(body).sort()).toEqual([
    "ready",
    "schema_version",
    "services",
  ]);
  for (const item of body.services as Record<string, string>[]) {
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

test("all local services ready", async ({ browser }) => {
  // Arranged: the owner saves a key the fake upstream accepts, and disconnects it afterwards.
  const owner = await (await browser.newContext()).newPage();
  await signIn(owner, OWNER_EMAIL, OWNER_PASSWORD);
  await owner.goto("/settings/models");
  await owner.getByLabel(/API key|Replace key/).fill("sk-or-valid-readiness");
  await owner.getByRole("button", { name: "Save & validate" }).click();
  await expect(owner.getByText("The key authenticated.").first()).toBeVisible();

  try {
    const page = await asReader(browser);
    const line = page.locator("[data-health]");
    await expect(line).toHaveAttribute("data-health", "ready");
    await expect(line).toHaveText("All local services ready");
    await expect(await chip(page, "api")).toHaveText("Python API ready");
    await expect(await chip(page, "worker")).toHaveText("Worker ready");
    await expect(await chip(page, "database")).toHaveText("Database ready");
    await expect(await chip(page, "openrouter")).toHaveText(
      "OpenRouter authenticated",
    );
    await noViolations(page);
  } finally {
    await owner.goto("/settings/models");
    await owner.getByRole("button", { name: "Disconnect" }).click();
    await expect(owner.getByRole("button", { name: "Disconnect" })).toHaveCount(
      0,
    );
  }
});
