import { expect, test, type Page } from "@playwright/test";

const OWNER_EMAIL = process.env.AUTOBOTS_TEST_OWNER_EMAIL ?? "";
const OWNER_PASSWORD = process.env.AUTOBOTS_TEST_OWNER_PASSWORD ?? "";
const WORKSPACE_A = process.env.AUTOBOTS_TEST_WORKSPACE_A ?? "";
const WORKSPACE_B = process.env.AUTOBOTS_TEST_WORKSPACE_B ?? "";
const SERVICE_KEY = process.env.AUTOBOTS_TEST_SERVICE_KEY ?? "";

async function signIn(
  page: Page,
  email: string,
  password: string,
): Promise<void> {
  await page.goto("/sign-in");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

test("the owner signs in through the form, and the API verifies identity and membership", async ({
  page,
  context,
}) => {
  const bodies: string[] = [];
  page.on("response", async (response) => {
    if (response.request().resourceType() !== "fetch")
      bodies.push(await response.text().catch(() => ""));
  });
  await signIn(page, OWNER_EMAIL, OWNER_PASSWORD);
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (item) => item.name === "autobots.session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "autobots.session",
  );
  expect(
    await page.evaluate(() => JSON.stringify({ ...localStorage })),
  ).not.toContain("access_token");
  const own = await page.request.get(`/api/v1/workspaces/${WORKSPACE_A}`);
  expect(own.status()).toBe(200);
  expect((await own.json()).id).toBe(WORKSPACE_A);
  const me = await (await page.request.get("/api/v1/session")).json();
  expect(me.workspace_ids).toEqual([WORKSPACE_A]);
  const other = await page.request.get(`/api/v1/workspaces/${WORKSPACE_B}`);
  expect(other.status()).toBe(403);
  for (const body of bodies) {
    expect(body).not.toContain(SERVICE_KEY);
    expect(body).not.toContain(OWNER_PASSWORD);
  }
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/signed-in.png`,
    fullPage: true,
  });
});

test("a wrong password shows a safe error, and no session", async ({
  page,
  context,
}) => {
  await signIn(page, OWNER_EMAIL, "not-the-password");
  await expect(
    page.getByText("That email and password did not work."),
  ).toBeVisible();
  expect(
    (await context.cookies()).some((item) => item.name === "autobots.session"),
  ).toBe(false);
  expect(
    (await page.request.get(`/api/v1/workspaces/${WORKSPACE_A}`)).status(),
  ).toBe(401);
  await page.screenshot({
    path: `${process.env.AUTOBOTS_WEB_SCREENSHOTS}/sign-in-failed.png`,
    fullPage: true,
  });
});

test("signing out ends access", async ({ page }) => {
  await signIn(page, OWNER_EMAIL, OWNER_PASSWORD);
  await expect(
    page.getByText("Signed in, with access to 1 workspace."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByText("You are not signed in.")).toBeVisible();
  expect(
    (await page.request.get(`/api/v1/workspaces/${WORKSPACE_A}`)).status(),
  ).toBe(401);
});

test("signing in needs the origin and CSRF checks", async ({ request }) => {
  const reply = await request.post("/api/session", {
    data: { email: OWNER_EMAIL, password: OWNER_PASSWORD },
  });
  expect(reply.status()).toBe(403);
});
